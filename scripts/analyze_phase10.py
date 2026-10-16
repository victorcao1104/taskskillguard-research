"""Independent offline Phase 10 scoring; no acquisition, truth repair or execution.

Pure entrypoint summarize accepts independently authored toy rows. CLI input is
only frozen saved evidence. All published tables are immutable and deterministic.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import random
import statistics

from phase10_common import ROOT, MODELS, jb, rb, sha, immutable, read_rows
from analyze_phase8 import paired_interval as _paired_interval, groups, ratio

AXES = ('authorization', 'current_route_required', 'catalog_required')
CELLS = ('full_diag', 'batch_diag', 'next_diag', 'next_exec', 'next_graph', 'next_padding')
META = ('case_id', 'family', 'split')
WORK = ('query_executions', 'query_steps', 'model_request_count', 'model_decision_attempts',
        'attributed_model_cost_upper_usd', 'charged_calls', 'planning_units', 'planner_steps',
        'primitive_simulations', 'audit_interpreter_calls', 'audit_steps', 'observation_count',
        'goal_observation_count', 'goal_observation_planning_units', 'mutation_risk_score',
        'unresolved_commit_count', 'unresolved_commit_risk')
RKEYS = ('split', 'pipeline', 'fault', 'policy', 'risk_profile', 'planning_budget',
         'observation_budget', 'query_budget', 'stop_mode', 'preflight')
PAIR = ('case_id', 'world_index', 'quota', 'fault', 'pipeline', 'policy', 'risk_profile',
        'planning_budget', 'observation_budget', 'query_budget', 'stop_mode', 'preflight')


def pick(row, keys):
    return {k: row.get(k) for k in keys}


@lru_cache(maxsize=8192)
def _cached_interval(values, draws, seed):
    if type(draws) is not int or draws < 1:
        raise ValueError('positive integer bootstrap draws required')
    if not values or len(set(values)) == 1:
        return _paired_interval([{'family': f'{i:08}', 'difference': v} for i, v in enumerate(values)], draws, seed)
    # Reuse exactly the same seeded family resample identities for equal family
    # counts. Vectorized means avoid repeating millions of Python RNG calls.
    import numpy as np
    samples = np.sort(np.asarray(values)[_resample_indices(len(values), draws, seed)].mean(axis=1))
    return {'families': len(values), 'pairs': len(values), 'estimate': statistics.fmean(values),
            'interval95': [float(samples[int(.025*draws)]), float(samples[min(draws-1, int(.975*draws))])],
            'positive_families': sum(v > 0 for v in values), 'negative_families': sum(v < 0 for v in values),
            'zero_families': sum(v == 0 for v in values)}


@lru_cache(maxsize=128)
def _resample_indices(n, draws, seed):
    import numpy as np
    rng = random.Random(seed)
    return np.asarray([rng.choices(range(n), k=n) for _ in range(draws)], dtype=np.int32)


def paired_interval(rows, draws=10000, seed=10101):
    # Repeated equal family-effect vectors need the same deterministic resamples.
    # Preserve sorted family order and original condition counts exactly.
    families = defaultdict(list)
    for row in rows:
        if row['difference'] is not None:
            families[row['family']].append(row['difference'])
    values = tuple(statistics.fmean(v) for _, v in sorted(families.items()))
    result = dict(_cached_interval(values, draws, seed))
    result['pairs'] = sum(len(v) for v in families.values())
    return result


def res(row):
    return row.get('result') or {}


def success(row):
    return row.get('runner_status', 'completed') == 'completed' and res(row).get('authorized_goal') is True


def value(row, metric):
    if metric == 'completion':
        return int(success(row))
    if metric in ('ambiguous_stop', 'planning_budget_exhausted'):
        return int(res(row).get(metric) is True) if row.get('runner_status', 'completed') == 'completed' else None
    return row.get(metric) if metric in WORK[:5] else res(row).get(metric)


def mean_record(values):
    values = list(values)
    known = [v for v in values if type(v) in (int, float)]
    return {'known': len(known), 'missing': len(values)-len(known), 'total': sum(known),
            'mean': statistics.fmean(known) if known else None}


def unique(rows, fields, name):
    keys = [tuple(r.get(k) for k in fields) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('DUPLICATE_' + name)


def stream_scores(truth, observations, models=MODELS):
    """Missing streams remain in first-decision and all-stream denominators."""
    meta = {r['case_id']: r for r in truth if r['split'] == 'heldout'}
    unique(observations, ('case_id', 'model', 'cell'), 'STREAM')
    index = {(r['case_id'], r['model'], r['cell']): r for r in observations}
    expected = {(cid, model, cell) for cid in meta for model in models for cell in CELLS}
    if set(index)-expected:
        raise ValueError('UNEXPECTED_STREAM')
    detail = []
    for cid, model, cell in sorted(expected):
        row = index.get((cid, model, cell), {})
        ds = row.get('decisions', [])
        valid = [d['parsed']['protocol_valid'] is True for d in ds]
        known_usage = [d['usage'] for d in ds if isinstance(d.get('usage'), dict)
                       and all(type(d['usage'].get(k)) is int and d['usage'][k] >= 0
                               for k in ('input_tokens', 'output_tokens'))]
        detail.append({**pick(meta[cid], META), 'model': model, 'cell': cell,
            'received': bool(row), 'first_decision_valid': bool(valid and valid[0]),
            'stream_valid': bool(row.get('protocol_valid') is True and valid and all(valid)),
            'decision_attempts': len(ds), 'valid_decisions': sum(valid),
            'provider_or_possible_io': sum(d.get('raw_status') != 'budget_exhausted' for d in ds),
            'known_input_tokens': sum(u['input_tokens'] for u in known_usage),
            'known_output_tokens': sum(u['output_tokens'] for u in known_usage),
            'known_usage_decisions': len(known_usage),
            'cost_upper_usd': sum(d['cost_upper_usd'] for d in ds),
            'unknown_reservation_decisions': sum(d.get('cost_basis') == 'reservation_upper_unknown_usage' for d in ds),
            'raw_statuses': dict(Counter(d.get('raw_status', 'missing') for d in ds)),
            'invalid_decision_statuses': dict(Counter(d.get('raw_status', 'missing') for d in ds if d['parsed']['protocol_valid'] is not True)),
            'stop_reason': row.get('stop_reason', 'missing_stream')})
    summary = []
    for key, rs in groups(detail, ('split', 'model', 'cell')):
        record = {**key, 'streams': len(rs), 'families': len({r['family'] for r in rs}),
                  **{f: sum(r[f] for r in rs) for f in ('received', 'first_decision_valid', 'stream_valid',
                     'decision_attempts', 'valid_decisions', 'provider_or_possible_io', 'known_input_tokens',
                     'known_output_tokens', 'known_usage_decisions', 'cost_upper_usd', 'unknown_reservation_decisions')},
                  'stop_reasons': dict(sorted(Counter(r['stop_reason'] for r in rs).items()))}
        record.update(first_decision_validity=ratio(record['first_decision_valid'], len(rs)),
                      stream_validity=ratio(record['stream_valid'], len(rs)),
                      decision_validity=ratio(record['valid_decisions'], record['decision_attempts']),
                      raw_statuses=dict(sum((Counter(r['raw_statuses']) for r in rs), Counter())),
                      invalid_decision_statuses=dict(sum((Counter(r['invalid_decision_statuses']) for r in rs), Counter())))
        summary.append(record)
    return detail, summary


def stream_contrasts(rows, draws=10000, seed=10101):
    details = []
    for key, rs in groups(rows, (*META, 'model')):
        ix = {r['cell']: r for r in rs}
        for a, b in (('batch_diag', 'full_diag'), ('next_diag', 'full_diag'), ('next_exec', 'next_diag'),
                     ('next_graph', 'next_exec'), ('next_graph', 'next_padding')):
            for metric in ('first_decision_valid', 'stream_valid'):
                details.append({**key, 'contrast': a+'-'+b, 'metric': metric,
                                'difference': int(ix[a][metric])-int(ix[b][metric])})
    return [{**key, **paired_interval(rs, draws, seed)} for key, rs in groups(details,
            ('split', 'model', 'contrast', 'metric'))]


def query_scores(truth, rows):
    gold = {r['case_id']: r for r in truth}
    unique(rows, ('case_id', 'pipeline', 'budget', 'stop_mode'), 'QUERY')
    detail = []
    for row in rows:
        counts = {a: dict(total=0, proven=0, intrinsic_unknown=0, budget_unknown=0) for a in AXES}
        result = res(row)
        for site in gold[row['case_id']]['labels']:
            for axis in AXES:
                decision = result['decisions'][site['id']][axis]
                proven = decision['proven'] is True
                prediction = result['by_id'][site['id']][axis]
                if proven and prediction != site[axis]:
                    raise ValueError('UNSOUND_QUERY:' + row['case_id'])
                intrinsic = proven and prediction == 'unknown'
                if decision['reason'] == 'intrinsic' and not intrinsic:
                    raise ValueError('INVALID_INTRINSIC_UNKNOWN')
                counts[axis]['total'] += 1
                counts[axis]['proven'] += proven
                counts[axis]['intrinsic_unknown'] += intrinsic
                counts[axis]['budget_unknown'] += not proven
        total = sum(c['total'] for c in counts.values())
        proven = sum(c['proven'] for c in counts.values())
        detail.append({**pick(row, (*META, 'pipeline', 'budget', 'stop_mode', 'protocol_valid',
            'stream_protocol_valid', 'model_request_count', 'model_decision_attempts', 'attributed_model_cost_upper_usd')),
            'total': total, 'proven': proven, 'proven_fraction': ratio(proven, total),
            'authorization_complete': result['authorization_complete'], 'diagnostic_complete': proven == total,
            'executions': result['executions'], 'interpreter_steps': result['interpreter_steps'],
            'intrinsic_unknown': sum(c['intrinsic_unknown'] for c in counts.values()),
            'budget_unknown': total-proven, 'by_axis': counts,
            'stopped_early': result.get('stopped_early', False), 'stop_reason': result.get('stop_reason')})
    summary = []
    for key, rs in groups(detail, ('split', 'pipeline', 'budget', 'stop_mode')):
        summary.append({**key, 'cases': len(rs), 'families': len({r['family'] for r in rs}),
            **{f: sum(r[f] for r in rs) for f in ('total', 'proven', 'intrinsic_unknown', 'budget_unknown',
               'executions', 'interpreter_steps', 'authorization_complete', 'diagnostic_complete', 'stopped_early')},
            'prefix_valid': sum(r['protocol_valid'] is True for r in rs),
            'all_stream_valid': sum(r['stream_protocol_valid'] is True for r in rs),
            'family_proven_fraction': paired_interval([{'family': r['family'], 'difference': r['proven_fraction']} for r in rs], 1)['estimate'],
            'by_axis': {a: {**{f: sum(r['by_axis'][a][f] for r in rs) for f in counts[a]},
                'family_proven_fraction': paired_interval([{'family': r['family'],
                    'difference': ratio(r['by_axis'][a]['proven'], r['by_axis'][a]['total'])} for r in rs], 1)['estimate']}
                for a in AXES},
            **{f: mean_record(r[f] for r in rs) for f in ('model_request_count', 'model_decision_attempts', 'attributed_model_cost_upper_usd')}})
    return detail, summary


def query_contrasts(rows, draws=10000, seed=10101):
    output = []
    for key, rs in groups(rows, (*META, 'budget', 'stop_mode')):
        ix = {r['pipeline']: r for r in rs}
        models = sorted({p.rsplit(':', 1)[0] for p in ix if ':' in p})
        pairs = [(m+':'+a, m+':'+b) for m in models for a, b in
                 (('batch_diag', 'full_diag'), ('next_diag', 'full_diag'), ('next_exec', 'next_diag'),
                  ('next_graph', 'next_exec'), ('next_graph', 'next_padding'))]
        pairs += [(p, b) for p in ix if ':' in p for b in ('heuristic', 'random')]
        for a, b in pairs:
            if a not in ix or b not in ix:
                continue
            for metric in ('proven_fraction', 'authorization_complete', 'diagnostic_complete', 'executions', 'interpreter_steps'):
                output.append({**key, 'contrast': a+'-'+b, 'metric': metric,
                               'difference': ix[a][metric]-ix[b][metric]})
    return [{**key, **paired_interval(rs, draws, seed)} for key, rs in groups(output,
            ('split', 'budget', 'stop_mode', 'contrast', 'metric'))], output


def execution_summary(rows):
    output = []
    for key, rs in groups([{**pick(r, RKEYS), **r} for r in rows], RKEYS):
        output.append({**key, 'conditions': len(rs), 'families': len({r['family'] for r in rs}),
            'successes': sum(success(r) for r in rs),
            'family_completion': paired_interval([{'family': r['family'], 'difference': int(success(r))} for r in rs], 1)['estimate'],
            'failure_reasons': dict(sorted(Counter(res(r).get('failure_reason') or 'runner_error' for r in rs if not success(r)).items())),
            **{f: mean_record(value(r, f) for r in rs) for f in WORK},
            'unauthorized_effects': sum(res(r).get('unauthorized_effects', 0) for r in rs),
            'duplicate_effects': sum(res(r).get('duplicate_effects', 0) for r in rs)})
    return output


def runtime_pair(rows, a, b, contrast, track, ignored=()):
    keys = tuple(k for k in PAIR if k not in ignored)
    def index(predicate):
        selected = [r for r in rows if predicate(r)]
        unique(selected, keys, 'PAIR')
        return {tuple(r.get(k) for k in keys): r for r in selected}
    left, right = index(a), index(b)
    if not left and not right:
        return []
    if set(left) != set(right):
        raise ValueError('UNMATCHED_RUNTIME:' + contrast)
    result = []
    for k in sorted(left, key=str):
        x, y = left[k], right[k]
        deltas = {}
        for f in ('completion', *WORK, 'ambiguous_stop', 'planning_budget_exhausted'):
            xv, yv = value(x, f), value(y, f)
            deltas[f] = xv-yv if xv is not None and yv is not None else None
        result.append({**pick(x, (*META, 'world_index', 'fault', 'planning_budget', 'observation_budget',
                       'query_budget', 'pipeline', 'stop_mode', 'risk_profile')),
            'track': track, 'contrast': contrast, 'differences': deltas,
            'treatment_id': x.get('condition_id'), 'baseline_id': y.get('condition_id'),
            'treatment_success': success(x), 'baseline_success': success(y),
            'both_success': success(x) and success(y), 'win': success(x) and not success(y),
            'loss': success(y) and not success(x),
            'treatment_reason': res(x).get('failure_reason'), 'baseline_reason': res(y).get('failure_reason'),
            'treatment_queries': x.get('query_executions'), 'baseline_queries': y.get('query_executions')})
    return result


def runtime_contrasts(interface, recovery, integrated, draws=10000, seed=10101):
    details = []
    def add(rows, a, b, name, track, ignored):
        details.extend(runtime_pair(rows, a, b, name, track, ignored))
    arm = lambda p, ob=2: lambda r: r.get('pipeline') == p and r.get('observation_budget') == ob
    for a, b in (('v10_goal', 'v10_authorization'), ('v10_goal', 'v9'), ('v10_authorization', 'v9'),
                 ('v10_goal', 'v10_no_preflight'), ('v10_authorization', 'v10_no_preflight')):
        add(interface, arm(a), arm(b), a+'-'+b, 'interface', ('pipeline', 'preflight'))
    for hi, lo in ((2, 0), (2, 1), (1, 0)):
        add(interface, arm('v10_goal', hi), arm('v10_goal', lo), f'goal_obs{hi}-{lo}',
            'interface', ('observation_budget',))
    for a, b in (('calls', 'priority'), ('risk', 'calls'), ('risk', 'priority')):
        add(recovery, lambda r: r['policy'] == a, lambda r: r['policy'] == b, a+'-'+b,
            'recovery', ('policy',))
    add(integrated, lambda r: r['stop_mode'] == 'authorization', lambda r: r['stop_mode'] == 'fixed',
        'authorization_stop-fixed', 'integrated', ('stop_mode',))
    pipelines = sorted({r['pipeline'] for r in integrated})
    models = sorted({p.rsplit(':', 1)[0] for p in pipelines if ':' in p})
    comparisons = [(m+':'+a, m+':'+b) for m in models for a, b in
                   (('batch_diag', 'full_diag'), ('next_diag', 'full_diag'), ('next_exec', 'next_diag'),
                    ('next_graph', 'next_exec'), ('next_graph', 'next_padding'))]
    comparisons += [(p, b) for p in pipelines if ':' in p for b in ('heuristic', 'random')]
    for a, b in comparisons:
        add(integrated, lambda r: r['pipeline'] == a, lambda r: r['pipeline'] == b,
            a+'-'+b, 'integrated_pipeline', ('pipeline',))
    summaries = []
    strata = ('track', 'split', 'contrast', 'fault', 'planning_budget', 'query_budget', 'risk_profile', 'stop_mode')
    # Conditions within a family are dependent; pooling faults does not create extra units.
    for key, rs in groups([*details, *[{**r, 'fault': 'pooled'} for r in details]], strata):
        for population in ('all', 'both_success'):
            selected = rs if population == 'all' else [r for r in rs if r['both_success']]
            for metric in ('completion', *WORK):
                vals = [{'family': r['family'], 'difference': r['differences'][metric]} for r in selected]
                if not any(v['difference'] is not None for v in vals):
                    continue
                summaries.append({**key, 'population': population, 'metric': metric,
                    'conditions': len(selected), 'wins': sum(r['win'] for r in selected),
                    'losses': sum(r['loss'] for r in selected),
                    'total_difference': sum(v['difference'] for v in vals if v['difference'] is not None),
                    **paired_interval(vals, draws, seed)})
    return summaries, details


def stopping_checks(pairs):
    selected = [r for r in pairs if r['track'] == 'integrated']
    output = []
    for key, rs in groups(selected, ('split', 'pipeline', 'fault', 'query_budget', 'planning_budget')):
        same = [r for r in rs if r['treatment_success'] == r['baseline_success']]
        saved = [r for r in same if r['differences']['query_executions'] is not None and r['differences']['query_executions'] < 0]
        output.append({**key, 'paired_conditions': len(rs), 'completion_wins': sum(r['win'] for r in rs),
            'completion_losses': sum(r['loss'] for r in rs), 'unchanged_completion': len(same),
            'same_completion_query_saving_conditions': len(saved),
            'both_success_query_saving_conditions': sum(r['both_success'] for r in saved),
            'saved_queries_at_unchanged_completion': -sum(r['differences']['query_executions'] for r in saved),
            'saved_steps_at_unchanged_completion': -sum(r['differences']['query_steps'] or 0 for r in saved),
            'campaign_invoice_saving_claimed_usd': 0})
    return output


def unique_query_stopping(rows, draws=10000, seed=10101):
    """Compare query replay rows once, before any runtime-world expansion."""
    selected = [r for r in rows if r['stop_mode'] in ('fixed', 'authorization')]
    unique(selected, ('case_id', 'pipeline', 'budget', 'stop_mode'), 'UNIQUE_QUERY_STOP')
    details = []
    for key, rs in groups(selected, (*META, 'pipeline', 'budget')):
        ix = {r['stop_mode']: r for r in rs}
        if set(ix) != {'fixed', 'authorization'}:
            raise ValueError('UNMATCHED_UNIQUE_QUERY_STOP')
        fixed, stopped = ix['fixed'], ix['authorization']
        details.append({**key, 'fixed_executions': fixed['executions'],
            'authorization_executions': stopped['executions'],
            'saved_queries': fixed['executions']-stopped['executions'],
            'saved_steps': fixed['interpreter_steps']-stopped['interpreter_steps']})
    return {'scope': 'One matched case/pipeline/budget query replay pair; no runtime world/fault/planner multiplication. Differences between actual replay counters, not a campaign interpreter or API invoice saving.',
        'summary': [{**key, 'pairs': len(rs), 'saving_pairs': sum(r['saved_queries'] > 0 for r in rs),
            'saved_queries': sum(r['saved_queries'] for r in rs), 'saved_steps': sum(r['saved_steps'] for r in rs),
            'family_query_saving': paired_interval([{'family': r['family'], 'difference': r['saved_queries']} for r in rs], draws, seed)}
            for key, rs in groups(details, ('split', 'pipeline', 'budget'))], 'details': details}


def pareto_checks(pairs):
    output = []
    for key, rs in groups([r for r in pairs if r['track'] == 'recovery'], ('split', 'contrast', 'fault', 'risk_profile')):
        def dominance(row, sign):
            d = row['differences']
            if any(d[f] is None for f in ('charged_calls', 'mutation_risk_score')):
                return False
            v = [sign*d['completion'], -sign*d['charged_calls'], -sign*d['mutation_risk_score']]
            return all(x >= 0 for x in v) and any(x > 0 for x in v)
        output.append({**key, 'conditions': len(rs), 'treatment_dominates': sum(dominance(r, 1) for r in rs),
            'baseline_dominates': sum(dominance(r, -1) for r in rs),
            'both_success': sum(r['both_success'] for r in rs),
            'completion_wins': sum(r['win'] for r in rs), 'completion_losses': sum(r['loss'] for r in rs)})
    return output


def old_loss_regression(old_pairs, interface):
    losses = [r for r in old_pairs if r.get('track') == 'interface' and r.get('split') == 'regression'
              and r.get('contrast') == 'preflight_on-off:conditional' and r.get('loss')]
    ids = {(r['case_id'], r['world_index'], r['fault']) for r in losses}
    rows = [r for r in interface if (r['case_id'], r['world_index'], r['fault']) in ids
            and r.get('observation_budget') == 2]
    return {'historical_loss_conditions': len(ids), 'expected_historical_loss_conditions': 16,
            'historical_case_ids': sorted({k[0] for k in ids}),
            'current': [{**key, 'conditions': len(rs), 'completed': sum(success(r) for r in rs),
                         'remaining_failures': sorted({r['case_id'] for r in rs if not success(r)})}
                        for key, rs in groups(rows, ('pipeline',))],
            'interpretation': 'Fixed historical loss subset only; separate regression, never new-family evidence.'}


def validate_runtime(rows, integrated=False):
    unique(rows, ('condition_id',), 'CONDITION_ID')
    for row in rows:
        r = res(row)
        if integrated and row.get('runner_status', 'completed') == 'completed':
            if r.get('evidence_source') != 'trusted_queries' or r.get('audit_interpreter_calls') != 0 or r.get('audit_steps') != 0:
                raise ValueError('HIDDEN_INTEGRATED_AUDIT')


def summarize(truth, observations, queries=(), interface=(), recovery=(), integrated=(), *, models=MODELS,
              draws=10000, seed=10101, old_pairs=(), accounting=None, input_manifest=None):
    unique(truth, ('case_id',), 'TRUTH')
    streams, stream_summary = stream_scores(truth, observations, models)
    qrows, qsummary = query_scores(truth, queries)
    qcontrasts, qpairs = query_contrasts(qrows, draws, seed)
    for name, rows in (('interface', interface), ('recovery', recovery), ('integrated', integrated)):
        validate_runtime(rows, name == 'integrated')
    contrasts, pairs = runtime_contrasts(interface, recovery, integrated, draws, seed)
    failures = [{**pick(r, (*META, 'model', 'cell')), 'kind': 'stream', 'reason': r['stop_reason']}
                for r in streams if not r['stream_valid']]
    for track, rows in (('interface', interface), ('recovery', recovery), ('integrated', integrated)):
        failures += [{**pick(r, ('condition_id', *META, *PAIR[1:])), 'kind': track,
                      'reason': res(r).get('failure_reason') or 'runner_error'} for r in rows if not success(r)]
    summary = {'schema_version': 'phase10-analysis-v1', 'cases': len(truth),
        'cases_by_split': dict(Counter(r['split'] for r in truth)),
        'families_by_split': {s: len({r['family'] for r in truth if r['split'] == s}) for s in sorted({r['split'] for r in truth})},
        'typed_distribution': [{**key, 'axis': a, 'counts': dict(sorted(Counter(s[a] for r in rs for s in r['labels']).items()))}
                               for key, rs in groups(truth, ('split',)) for a in AXES],
        'streams': stream_summary, 'stream_contrasts': stream_contrasts(streams, draws, seed),
        'queries': qsummary, 'query_contrasts': qcontrasts,
        'runtime_contrasts': contrasts, 'interface': execution_summary(interface),
        'recovery': execution_summary(recovery), 'integrated': execution_summary(integrated),
        'runtime_conditions': {'interface': len(interface), 'recovery': len(recovery), 'integrated': len(integrated)},
        'stopping_checks': stopping_checks(pairs), 'recovery_pareto': pareto_checks(pairs),
        'old16_regression': old_loss_regression(old_pairs, interface),
        'acquisition_accounting': accounting, 'input_manifest': input_manifest,
        'failure_counts': dict(Counter(r['kind'] for r in failures)),
        'methods': {'bootstrap': 'paired family-equal percentile bootstrap; dependent conditions averaged within family',
            'draws': draws, 'seed': seed, 'multiplicity': 'exploratory unadjusted 95% intervals',
            'nulls': ['goal observations do not improve matched completion', 'shorter protocols do not improve validity or unconditional coverage',
                      'authorization stopping does not reduce actual query work at unchanged completion', 'risk policy is not Pareto superior'],
            'unknown': 'Proved intrinsic unknown is resolved; unproved budget unknown is unresolved, regardless of displayed label.',
            'validity': 'First decision and all-stream validity are separate; per-decision denominator is attempted decisions and is adaptive.',
            'protocol_confounds': 'Full/batch/next change feedback frequency and output burden as well as schema.',
            'graph': 'Graph compared with source and inert character padding; character matching is not token matching.',
            'work': 'Query interpreter calls/steps, goal observations, planning, model requests and real calls reported separately; no total CPU claim.',
            'cost': 'All acquired spending retained including later decisions and unknown reservations; prefix attribution is a deployment scenario, not campaign invoice savings.',
            'stopping': 'Real prefix interpreter stopping; authorization predicate is sufficient evidence, not globally optimal stopping.',
            'regression': 'Prior cases and fixed historical 16-loss subset are separate from new families.',
            'limits': 'Synthetic tasks and risk weights; no real Skill safety or general injection defense claim.'}}
    return {'summary': summary, 'stream_scores': streams, 'query_scores': qrows,
            'query_pairs': qpairs, 'runtime_pairs': pairs, 'failures': failures,
            'decision_failures': [{**pick(r, (*META, 'model', 'cell', 'stream_id')),
                **pick(d, ('job_id', 'before_queries', 'raw_status', 'raw_ref', 'cost_upper_usd', 'cost_basis')),
                'diagnostic_codes': d['parsed'].get('diagnostic_codes', []),
                'failure_layer': 'provider_or_acquisition' if d.get('raw_status') == 'api_error' else
                    'incomplete_generation' if d.get('raw_status') == 'incomplete' else
                    'output_protocol' if d.get('raw_status') == 'completed' else 'other_acquisition'}
                for r in observations for d in r.get('decisions', []) if d['parsed']['protocol_valid'] is not True]}


def read_chunk_input(root, directory):
    """Same digest contract as phase10_common.read_chunks, with CLI root support."""
    manifest = json.loads((root/directory/'manifest.json').read_text())
    rows = [r for i in range(1, manifest['chunks']+1) for r in read_rows(root/directory/f'{i:04}.jsonl')]
    if len(rows) != manifest['rows'] or sha(rb(rows)) != manifest['sha256']:
        raise ValueError('CHUNK_DIGEST_MISMATCH:' + directory)
    return rows, {'path': directory, **manifest}


def complete_jobs(rows, jobs):
    unique(rows, ('condition_id',), 'RESULT')
    ix = {r['condition_id']: r for r in rows}
    metas = [j['meta'] for j in jobs]
    unique(metas, ('condition_id',), 'JOB')
    if set(ix)-{r['condition_id'] for r in metas}:
        raise ValueError('UNEXPECTED_RUNTIME_RESULT')
    return [ix.get(m['condition_id'], {**m, 'runner_status': 'missing_result', 'result': None}) for m in metas]


def write_report(directory, report):
    directory = Path(directory)
    for name, rows in report.items():
        if name == 'summary':
            immutable(directory/'summary.json', jb(rows))
        else:
            # Keep files below practical review/upload limits, including failures.
            for i, start in enumerate(range(0, len(rows), 500), 1):
                immutable(directory/name/f'{i:04}.jsonl', rb(rows[start:start+500]))
            immutable(directory/name/'manifest.json', jb({'rows': len(rows), 'chunks': (len(rows)+499)//500,
                      'sha256': sha(rb(rows)), 'chunk_size': 500}))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--output', type=Path)
    a = p.parse_args(argv)
    # Require both frozen contracts without importing or invoking the generator.
    for stage in ('production', 'data'):
        frozen = json.loads((a.root/f'results/phase10/provenance/{stage}_freeze.json').read_text())
        for path, digest in frozen['files'].items():
            if sha((a.root/path).read_bytes()) != digest:
                raise ValueError('FROZEN_CHANGED:' + path)
    manifest = {}
    def plain(name, path):
        raw = (a.root/path).read_bytes()
        manifest[name] = {'path': path, 'sha256': sha(raw)}
        return [json.loads(s) for s in raw.decode('utf-8-sig').splitlines() if s]
    truth = plain('truth', 'results/phase10/semantics/truth.jsonl')
    observations = plain('observations', 'results/phase10/api/observations.jsonl')
    queries, manifest['queries'] = read_chunk_input(a.root, 'results/phase10/queries/results')
    tracks = {}
    for name in ('interface', 'recovery', 'integrated'):
        rows, manifest[name] = read_chunk_input(a.root, f'results/phase10/{name}/vm_results')
        jobs, manifest[name+'_jobs'] = read_chunk_input(a.root, f'results/phase10/{name}/jobs')
        tracks[name] = complete_jobs(rows, jobs)
    old = plain('old_pairs', 'results/phase9/analysis/runtime_pairs.jsonl')
    accounting = json.loads((a.root/'results/phase10/api/summary.json').read_text())
    for name, relative in (('api_summary', 'results/phase10/api/summary.json'),
                           ('budget_inheritance', 'results/phase10/provenance/budget_inheritance.json'),
                           ('budget_ledger', 'results/phase10/api/budget.jsonl'),
                           ('reference_coverage', 'results/phase10/reference/coverage.json'),
                           ('reference_novelty', 'results/phase10/reference/novelty.json')):
        raw = (a.root/relative).read_bytes()
        manifest[name] = {'path': relative, 'sha256': sha(raw), 'bytes': len(raw)}
    report = summarize(truth, observations, queries, **tracks, old_pairs=old,
                       accounting=accounting, input_manifest=manifest)
    write_report(a.output or a.root/'results/phase10/analysis', report)
    immutable((a.output or a.root/'results/phase10/analysis')/'unique_query_stopping.json',
              jb(unique_query_stopping(report['query_scores'])))
    print(json.dumps({'cases': len(truth), 'streams': len(observations), 'queries': len(queries),
                      **report['summary']['runtime_conditions']}), flush=True)
    return report


if __name__ == '__main__':
    main()

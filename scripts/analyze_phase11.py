"""Pure, offline Phase 11 scoring of saved evidence; no selector or VM imports.

The CLI requires the complete frozen grid before publishing immutable output.
``summarize`` also accepts small independent fixtures for analysis tests.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import csv
import io
import json
import math
from pathlib import Path
import random
import statistics

from phase11_common import ROOT, MODELS, jb, rb, sha, immutable, read_rows, read_chunks, verify_freeze

DRAWS = 10000
SEED = 11101
BUDGETS = (2, 4, 8, 12, 'full')
POLICIES = ('original_first', 'route_cover', 'observe_cover', 'random')
FAULTS = ('none', 'ambiguous_after', 'terminal_noncommit', 'pending', 'unavailable', 'stale',
          'wrong_signature', 'pending_absent', 'second_ambiguous_after', 'second_terminal_noncommit',
          'emit_ambiguous_after', 'emit_terminal_noncommit')
RECOVERY = ('strict_stop', 'terminal_status', 'same_id_dedup')
CELLS = (('source', True), ('graph', True), ('padding', True), ('source', False))
ACQUISITION_WORK = ('query_count', 'interpreter_calls', 'interpreter_steps', 'initial_observation_calls',
                    'audit_effect_calls', 'certificate_pair_checks', 'certificate_check_calls', 'observation_comparisons')
EXECUTION_WORK = ('effect_calls', 'status_calls', 'charged_calls', 'receipt_reuses',
                  'duplicate_effects', 'unauthorized_effects')
OUTCOME_METRICS = ('completion', 'certified', 'infeasible', 'unknown', 'observation_mismatch',
                   'budget_limited_certifiable', 'unresolved_robust_infeasibility',
                   'observation_unavailable', 'hindsight_min_queries', 'hindsight_cost_gap')
STREAM_METRICS = ('completion', 'partial_paid_prefix_success', 'valid_complete_stream_success', 'stream_valid', 'protocol_failure',
                  'budget_censored', 'decision_attempts', 'provider_or_uncertain_requests',
                  'confirmed_provider_responses', 'uncertain_transport_or_interrupt',
                  'budget_rejections_before_io', 'completed_envelopes', 'valid_decisions',
                  'valid_json_objects', 'known_input_tokens', 'known_output_tokens',
                  'known_usage_decisions', 'missing_usage_decisions', 'missing_elapsed_decisions',
                  'reservation_upper_unknown_usage', 'api_cost_upper_usd', 'api_elapsed_seconds_sum')


def ordered(rows):
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True, separators=(',', ':'), allow_nan=False))


def groups(rows, fields):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row.get(k) for k in fields)].append(row)
    for key in sorted(result, key=lambda v: json.dumps(v, sort_keys=True)):
        yield dict(zip(fields, key)), result[key]


def unique(rows, fields, name):
    keys = [tuple(r.get(k) for k in fields) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('DUPLICATE_' + name)


def _number(v):
    return type(v) in (int, float) and math.isfinite(v)


def _percentile(values, probability):
    position = (len(values)-1)*probability
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi]-values[lo])*(position-lo)


@lru_cache(maxsize=128)
def _indices(n, draws, seed):
    rng = random.Random(seed)
    return tuple(tuple(rng.choices(range(n), k=n)) for _ in range(draws))


@lru_cache(maxsize=128)
def _numpy_indices(n, draws, seed):
    import numpy as np
    return np.asarray(_indices(n, draws, seed), dtype=np.int32)


@lru_cache(maxsize=16384)
def _interval(values, draws, seed):
    if not values:
        return None, (None, None)
    if len(set(values)) == 1:
        return values[0], (values[0], values[0])
    try:
        import numpy as np
        samples = sorted(np.asarray(values, dtype=float)[_numpy_indices(len(values), draws, seed)].mean(axis=1).tolist())
    except ImportError:
        samples = sorted(statistics.fmean(values[i] for i in indexes) for indexes in _indices(len(values), draws, seed))
    return statistics.fmean(values), (_percentile(samples, .025), _percentile(samples, .975))


def paired_interval(rows, draws=DRAWS, seed=SEED):
    """Average conditions within family, then bootstrap equal-weight families."""
    if type(draws) is not int or draws < 1:
        raise ValueError('positive integer bootstrap draws required')
    families = defaultdict(list)
    for row in rows:
        if _number(row.get('difference')):
            families[row['family']].append(row['difference'])
    values = tuple(statistics.fmean(v) for _, v in sorted(families.items()))
    estimate, interval = _interval(values, draws, seed)
    return {'families': len(values), 'pairs': sum(map(len, families.values())),
            'estimate': estimate, 'interval95': list(interval),
            'positive_families': sum(v > 0 for v in values),
            'negative_families': sum(v < 0 for v in values), 'zero_families': sum(v == 0 for v in values)}


def strata(rows):
    """Scaling siblings never enter the combined main/challenge estimate."""
    return [dict(row) for row in rows] + [{**r, 'cohort': 'combined'} for r in rows if r['cohort'] in ('main', 'challenge')]


def aggregate(rows, fields, metrics):
    output = []
    for key, rs in groups(strata(rows), ('cohort', *fields)):
        for metric in metrics:
            valid = [r for r in rs if _number(r.get(metric))]
            interval = paired_interval([{'family': r['family'], 'difference': r[metric]} for r in valid])
            output.append({**key, 'metric': metric, **interval, 'rows': len(rs),
                           'known_rows': len(valid), 'missing_rows': len(rs)-len(valid),
                           'observed_total': sum(r[metric] for r in valid),
                           'denominator_families': len({r['family'] for r in rs})})
    return ordered(output)


def metadata(case):
    return {'case_id': case['case_id'], 'family': case['family'], 'split': case['split'],
            'cohort': {'heldout': 'main', 'challenge': 'challenge', 'scaling': 'scaling'}[case['split']],
            'world_count': len(case['worlds']), 'route_count': len(case['routes'])+1,
            'scaling_shape': (f"w{len(case['worlds'])}-r{len(case['routes'])+1}" if case['split'] == 'scaling' else None)}


def truth_for(reference, world):
    classes = [c for c in reference['observation_classes'] if world in c['world_indices']]
    if len(classes) != 1:
        raise ValueError('REFERENCE_WORLD_CLASS_MISMATCH')
    oracle = [c['minimum_positive_total_queries'] for c in reference['hindsight_certificate_cost']
              if c['actual_world_index'] == world]
    if len(oracle) != 1:
        raise ValueError('REFERENCE_WORLD_COST_MISMATCH')
    return classes[0], oracle[0]


def outcome(reference, world, certificate, acquisition, execution):
    cl, lower = truth_for(reference, world)
    status = certificate['status']
    if status not in ('certified', 'infeasible', 'unknown', 'observation_mismatch'):
        raise ValueError('UNKNOWN_CERTIFICATE_STATUS')
    unknown_class = ('budget_limited_certifiable' if cl['common_safe_routes'] else
                     'unresolved_robust_infeasibility') if status == 'unknown' else None
    observations = acquisition.get('observations', {})
    unavailable = any(v.get('answer', {}).get('available') is False for v in observations.values())
    queries = acquisition.get('query_count')
    gap = queries-lower if status == 'certified' and lower is not None and queries is not None else None
    if gap is not None and gap < 0:
        raise ValueError('CERTIFICATE_BELOW_REFERENCE_LOWER_BOUND')
    return {**{s: int(status == s) for s in ('certified', 'infeasible', 'unknown', 'observation_mismatch')},
            'completion': int(bool(execution and execution.get('authorized_goal') is True)),
            'certificate_status': status, 'unknown_class': unknown_class,
            'budget_limited_certifiable': int(unknown_class == 'budget_limited_certifiable'),
            'unresolved_robust_infeasibility': int(unknown_class == 'unresolved_robust_infeasibility'),
            'observation_unavailable': int(unavailable), 'hindsight_min_queries': lower,
            'hindsight_cost_gap': gap, 'full_class_size': len(cl['world_indices']),
            'full_class_common_route': int(bool(cl['common_safe_routes']))}


def policy_scores(cases, references, rows):
    cs, refs = {c['case_id']: c for c in cases}, {r['case_id']: r for r in references}
    result = []
    for row in rows:
        cid, acquisition = row['case_id'], row['result']
        execution = row.get('execution')
        result.append({**metadata(cs[cid]), **{k: row[k] for k in ('world_index', 'policy', 'budget', 'stop')},
                       **outcome(refs[cid], row['world_index'], acquisition['certificate'], acquisition, execution),
                       **{k: acquisition.get(k) for k in ACQUISITION_WORK},
                       **{k: (execution or {}).get(k) for k in EXECUTION_WORK},
                       'stop_reason': acquisition.get('stop_reason'),
                       'certificate_verified': row.get('certificate_verified')})
    return result


def recovery_scores(cases, rows):
    cs = {c['case_id']: c for c in cases}
    output = []
    for row in rows:
        result = row.get('result') or {}
        output.append({**metadata(cs[row['case_id']]),
                       **{k: row[k] for k in ('world_index', 'fault', 'policy', 'status_budget', 'certificate_status')},
                       'completion': int(result.get('authorized_goal') is True),
                       'fault_triggered': int(result.get('fault_diagnostics', {}).get('fault_triggered') is True),
                       'missing_certificate': int(row['certificate_status'] != 'certified'),
                       'failure_reason': result.get('failure_reason'),
                       'quota_exhausted': int(result.get('failure_reason') == 'quota_exhausted'),
                       'capability': ('atomic_durable_same_id_dedup' if row['policy'] == 'same_id_dedup' else
                                      'terminal_status_access' if row['policy'] == 'terminal_status' else 'strict_stop'),
                       **{k: result.get(k) for k in EXECUTION_WORK}})
    return output


def stream_scores(cases, references, streams, integrated):
    cs, refs = {c['case_id']: c for c in cases}, {r['case_id']: r for r in references}
    executions = {(r['stream_id'], r['budget']): r for r in integrated
                  if r['fault'] == 'none' and r['policy'] == 'strict_stop'}
    output = []
    for row in streams:
        ds, cid = row['decisions'], row['case_id']
        raw = Counter(d.get('raw_status', 'missing') for d in ds)
        usage = [d['usage'] for d in ds if isinstance(d.get('usage'), dict)
                 and all(type(d['usage'].get(k)) is int and d['usage'][k] >= 0 for k in ('input_tokens', 'output_tokens'))]
        valid = row.get('protocol_valid') is True
        execution = executions.get((row['stream_id'], 12), {}).get('result')
        partial = int(bool(execution and execution.get('authorized_goal') is True))
        scored = outcome(refs[cid], row['world_index'], row['certificate'], row, execution)
        output.append({**metadata(cs[cid]),
                       **{k: row[k] for k in ('world_index', 'stream_id', 'model', 'view', 'stop')},
                       **scored, **{k: row.get(k) for k in ACQUISITION_WORK},
                       'completion': partial, 'partial_paid_prefix_success': partial,
                       'valid_complete_stream_success': int(valid and partial),
                       'stream_valid': int(valid), 'protocol_failure': int(row.get('stop_reason') == 'protocol_failure'),
                       'budget_censored': int(row.get('stop_reason') == 'budget_exhausted'),
                       'stop_reason': row.get('stop_reason'), 'decision_attempts': len(ds),
                       'provider_or_uncertain_requests': sum(n for s, n in raw.items() if s != 'budget_exhausted'),
                       'confirmed_provider_responses': sum(raw[s] for s in ('completed', 'incomplete', 'api_error', 'failed')),
                       'uncertain_transport_or_interrupt': sum(raw[s] for s in ('transport_error', 'interrupted_unknown', 'invalid_response')),
                       'budget_rejections_before_io': raw['budget_exhausted'], 'completed_envelopes': raw['completed'],
                       'valid_decisions': sum(d['parsed'].get('protocol_valid') is True for d in ds),
                       'valid_json_objects': sum(isinstance(d['parsed'].get('prediction'), dict) for d in ds),
                       'known_input_tokens': sum(u['input_tokens'] for u in usage),
                       'known_output_tokens': sum(u['output_tokens'] for u in usage),
                       'known_usage_decisions': len(usage), 'missing_usage_decisions': len(ds)-len(usage),
                       'missing_elapsed_decisions': sum(d.get('elapsed_seconds') is None and d.get('raw_status') != 'budget_exhausted' for d in ds),
                       'reservation_upper_unknown_usage': sum(d.get('cost_basis') == 'reservation_upper_unknown_usage' for d in ds),
                       'api_cost_upper_usd': row['api_cost_upper_usd'],
                       'api_elapsed_seconds_sum': row['api_elapsed_seconds_sum'], 'raw_statuses': dict(sorted(raw.items()))})
    return output


def integrated_scores(cases, references, streams, rows):
    cs, refs = {c['case_id']: c for c in cases}, {r['case_id']: r for r in references}
    ix = {r['stream_id']: r for r in streams}
    result = []
    for row in rows:
        stream = ix[row['stream_id']]
        acquisition = {'query_count': row['acquired_queries'], 'observations': {
            q: stream.get('observations', {}).get(q, {}) for q in stream.get('order', [])[:row['budget']]}}
        scored = outcome(refs[row['case_id']], row['world_index'], row['certificate'], acquisition, row.get('result'))
        partial = scored['completion']
        result.append({**metadata(cs[row['case_id']]),
                       **{k: row[k] for k in ('stream_id', 'model', 'view', 'stop', 'world_index', 'budget', 'fault', 'policy')},
                       **scored, 'query_count': row['acquired_queries'],
                       'completion': partial,
                       'valid_complete_stream_success': int(bool(partial and stream['protocol_valid'])),
                       'partial_paid_prefix_success': partial, 'stream_valid': int(stream['protocol_valid']),
                       'protocol_failure': int(stream.get('stop_reason') == 'protocol_failure'),
                       'budget_censored': int(stream.get('stop_reason') == 'budget_exhausted'),
                       **{k: (row.get('result') or {}).get(k) for k in EXECUTION_WORK}})
    return result


def contrast(rows, name, left, right, fields, metrics, pair_fields=('case_id', 'world_index'), denominator='all_rows'):
    """Paired rows retain unmatched counts; differences are left minus right."""
    effects, summaries = [], []
    for key, rs in groups(strata(rows), ('cohort', *fields)):
        ls, rr = [r for r in rs if left(r)], [r for r in rs if right(r)]
        unique(ls, pair_fields, name+'_LEFT'); unique(rr, pair_fields, name+'_RIGHT')
        li = {tuple(r.get(k) for k in pair_fields): r for r in ls}
        ri = {tuple(r.get(k) for k in pair_fields): r for r in rr}
        shared = sorted(li.keys() & ri.keys(), key=str)
        if not ls and not rr:
            continue
        for metric in metrics:
            pairs = []
            for p in shared:
                av, bv = li[p].get(metric), ri[p].get(metric)
                if _number(av) and _number(bv):
                    pairs.append({'family': li[p]['family'], 'difference': av-bv})
            for family_key, fr in groups(pairs, ('family',)):
                effects.append({**key, **family_key, 'contrast': name, 'metric': metric,
                                'denominator': denominator, 'pairs': len(fr),
                                'difference': statistics.fmean(r['difference'] for r in fr)})
            summaries.append({**key, 'contrast': name, 'metric': metric, 'denominator': denominator,
                              **paired_interval(pairs), 'matched_rows': len(shared),
                              'missing_metric_pairs': len(shared)-len(pairs),
                              'unmatched_left': len(li.keys()-ri.keys()), 'unmatched_right': len(ri.keys()-li.keys()),
                              'wins': sum(r['difference'] > 0 for r in pairs),
                              'losses': sum(r['difference'] < 0 for r in pairs),
                              'ties': sum(r['difference'] == 0 for r in pairs)})
    return ordered(effects), ordered(summaries)


def semantics_scores(cases, references, rows):
    cs, refs = {c['case_id']: c for c in cases}, {r['case_id']: r for r in references}
    output = []
    # Trace syntax differs intentionally across independent interpreters; do not
    # normalize files, emits, error-free success, charged calls or receipt reuse.
    for row in rows:
        cid = row['case_id']; ref = refs[cid]['executions'][row['world_index']][row['route']]
        audit, execution = row['audit'], row['execution']
        checks = {
            'files_equal': ref['files'] == audit['files'] == execution['files'],
            'emits_equal': ref['emits'] == audit['emits'] == execution['emits'],
            'success_equal': ref['safe_success'] == audit['safe_success'] == execution['authorized_goal'],
            'calls_equal': ref['charged_calls'] == audit['charged_calls'] == execution['charged_calls'],
            'reuses_equal': ref['receipt_reuses'] == audit['receipt_reuses'] == execution['receipt_reuses'],
            # The executor adds goal_unmet after error-free VM termination.
            # Preserve all raw error strings alongside this explicit mapping.
            'normalized_error_equal':
                (ref['error'].split(':', 1)[0] if isinstance(ref['error'], str) and ref['error'].startswith('unbound_variable:') else ref['error'])
                == audit['error']
                == (None if execution['failure_reason'] == 'goal_unmet' else execution['failure_reason']),
            'steps_equal': ref['steps_entered'] == audit['interpreter_steps']}
        output.append({**metadata(cs[cid]), 'world_index': row['world_index'], 'route': row['route'],
                       **{k: int(v) for k, v in checks.items()}, 'all_compared_equal': int(all(checks.values())),
                       'raw_reference_audit_error_equal': int(ref['error'] == audit['error']),
                       'reference_steps': ref['steps_entered'], 'audit_steps': audit['interpreter_steps'],
                       'reference_error': ref['error'], 'audit_error': audit['error'], 'execution_error': execution['failure_reason']})
    return output


def summarize(cases, references, policies=(), recovery=(), streams=(), integrated=(), matched_prefix=(), semantics=(), previous=()):
    """Return deterministic tables and summary without I/O or input mutation."""
    unique(cases, ('case_id',), 'CASE'); unique(references, ('case_id',), 'REFERENCE')
    unique(policies, ('case_id', 'world_index', 'policy', 'budget', 'stop'), 'POLICY')
    unique(recovery, ('case_id', 'world_index', 'fault', 'policy', 'status_budget'), 'RECOVERY')
    unique(streams, ('stream_id',), 'STREAM')
    unique(integrated, ('stream_id', 'budget', 'fault', 'policy'), 'INTEGRATED')
    pd = policy_scores(cases, references, policies)
    rd = recovery_scores(cases, recovery)
    sd = stream_scores(cases, references, streams, integrated)
    md = integrated_scores(cases, references, streams, integrated)
    sem = semantics_scores(cases, references, semantics)
    tables = {'policy_detail': ordered(pd), 'recovery_detail': ordered(rd),
              'stream_detail': ordered(sd), 'integrated_detail': ordered(md), 'semantics_detail': ordered(sem)}
    tables['policy_conditions'] = aggregate(pd, ('policy', 'budget', 'stop', 'scaling_shape'), (*OUTCOME_METRICS, *ACQUISITION_WORK, *EXECUTION_WORK))
    tables['recovery_conditions'] = aggregate(rd, ('fault', 'policy', 'status_budget'),
                                             ('completion', 'fault_triggered', 'missing_certificate', 'quota_exhausted', *EXECUTION_WORK))
    tables['recovery_triggered_conditions'] = aggregate([r for r in rd if r['fault_triggered']],
                                                       ('fault', 'policy', 'status_budget'), ('completion', *EXECUTION_WORK))
    tables['stream_conditions'] = aggregate(sd, ('model', 'view', 'stop'), (*STREAM_METRICS, *ACQUISITION_WORK, *OUTCOME_METRICS[1:]))
    tables['integrated_conditions'] = aggregate(md, ('model', 'view', 'stop', 'budget', 'fault', 'policy'),
                                              (*OUTCOME_METRICS, 'query_count', 'stream_valid', 'partial_paid_prefix_success',
                                               'protocol_failure', 'budget_censored', 'valid_complete_stream_success', *EXECUTION_WORK))
    effects, contrasts = [], []
    def add(*args, **kwargs):
        e, c = contrast(*args, **kwargs); effects.extend(e); contrasts.extend(c)
    add(pd, 'observe_cover_online_minus_fixed',
        lambda r: r['policy'] == 'observe_cover' and r['stop'],
        lambda r: r['policy'] == 'observe_cover' and not r['stop'], ('budget', 'scaling_shape'), ('completion', 'query_count'))
    for alternate in ('original_first', 'route_cover', 'random'):
        add(pd, alternate+'_minus_observe_cover', lambda r, p=alternate: r['policy'] == p and r['stop'],
            lambda r: r['policy'] == 'observe_cover' and r['stop'], ('budget', 'scaling_shape'), ('completion', 'query_count'))
    # The actual-world model comparator contains exactly one variant/world per
    # family and uses the model stream's unconditional protocol-valid endpoint.
    deterministic_ix = {(r['case_id'], r['world_index'], r['budget'], r['policy']): r for r in pd if r['stop']}
    comparator = []
    for row in md:
        if row['fault'] != 'none' or row['policy'] != 'strict_stop' or row['view'] != 'source' or not row['stop']:
            continue
        for baseline in POLICIES:
            base = deterministic_ix.get((row['case_id'], row['world_index'], row['budget'], baseline))
            if base:
                comparator.extend([{**row, 'side': 'model', 'baseline': baseline},
                                   {**base, 'model': row['model'], 'side': 'heuristic', 'baseline': baseline}])
    add(comparator, 'source_online_minus_matched_heuristic', lambda r: r['side'] == 'model',
        lambda r: r['side'] == 'heuristic', ('model', 'baseline', 'budget'), ('completion', 'query_count'))
    tables['model_comparator_detail'] = ordered(comparator)
    tables['model_comparator_conditions'] = aggregate(comparator, ('model', 'baseline', 'budget', 'side'), ('completion', 'query_count'))
    faultfree = [r for r in md if r['fault'] == 'none' and r['policy'] == 'strict_stop']
    for name, left_view, right_view in [('graph_minus_source', 'graph', 'source'), ('graph_minus_padding', 'graph', 'padding')]:
        add(faultfree, name, lambda r, v=left_view: r['view'] == v and r['stop'],
            lambda r, v=right_view: r['view'] == v and r['stop'], ('model', 'budget'), ('completion', 'query_count'))
    add(faultfree, 'source_online_minus_fresh_fixed', lambda r: r['view'] == 'source' and r['stop'],
        lambda r: r['view'] == 'source' and not r['stop'], ('model', 'budget'), ('completion', 'query_count'))
    add(sd, 'source_online_minus_fresh_fixed_actual_cost', lambda r: r['view'] == 'source' and r['stop'],
        lambda r: r['view'] == 'source' and not r['stop'], ('model',),
        ('completion', 'query_count', 'api_cost_upper_usd', 'api_elapsed_seconds_sum', 'known_input_tokens', 'known_output_tokens', 'decision_attempts'))
    for name, other in (('graph_minus_source_actual_cost', 'source'), ('graph_minus_padding_actual_cost', 'padding')):
        add(sd, name, lambda r: r['view'] == 'graph' and r['stop'],
            lambda r, v=other: r['view'] == v and r['stop'], ('model',),
            ('completion', 'query_count', 'api_cost_upper_usd', 'api_elapsed_seconds_sum', 'known_input_tokens', 'known_output_tokens'))
    terminal = [r for r in rd if r['status_budget'] == 1 and r['fault'] in ('ambiguous_after', 'terminal_noncommit')]
    for denominator in ('all_rows', 'triggered'):
        selected = terminal if denominator == 'all_rows' else [r for r in terminal if r['fault_triggered']]
        for policy in ('terminal_status', 'same_id_dedup'):
            add(selected, policy+'_minus_strict_stop', lambda r, p=policy: r['policy'] == p,
                lambda r: r['policy'] == 'strict_stop', ('fault', 'status_budget'),
                ('completion', 'effect_calls', 'status_calls', 'duplicate_effects'), denominator=denominator)
    cs = {c['case_id']: c for c in cases}; stream_ix = {s['stream_id']: s for s in streams}
    prefix = []
    for row in matched_prefix:
        stream = stream_ix[row['stream_id']]
        prefix.append({**metadata(cs[row['case_id']]), 'stream_id': row['stream_id'], 'budget': row['budget'],
                       'model': stream['model'], 'view': stream['view'], 'stop': stream['stop'],
                       'both_faultfree_success': int(row['both_faultfree_success']),
                       'route_equal': int(row['first_route'] == row['later_route']),
                       'full_result_equal': int(row['trace_equal']), 'queries': row['queries'],
                       'earliest_queries': row['earliest_queries'],
                       'offline_queries_saved': row['queries']-row['earliest_queries']})
    tables['matched_prefix_detail'] = ordered(prefix)
    tables['matched_prefix_conditions'] = aggregate(prefix, ('model', 'view', 'stop', 'budget'),
                                                   ('both_faultfree_success', 'route_equal', 'full_result_equal', 'queries', 'earliest_queries', 'offline_queries_saved'))
    prior = []
    for row in previous:
        base = {**metadata(cs[row['case_id']]), 'world_index': row['world_index']}
        for label, result in [('old_phase10_contract', row['old_runtime']), ('new_full_observe_cover_contract', row.get('new_runtime'))]:
            prior.append({**base, 'contract': label, 'completion': int((result or {}).get('authorized_goal') is True),
                          'charged_calls': (result or {}).get('charged_calls')})
    tables['previous_contract_detail'] = ordered(prior)
    tables['previous_contract_conditions'] = aggregate(prior, ('contract',), ('completion', 'charged_calls'))
    add(prior, 'new_minus_old_unequal_access_contract', lambda r: r['contract'] == 'new_full_observe_cover_contract',
        lambda r: r['contract'] == 'old_phase10_contract', (), ('completion',))
    tables['family_effects'], tables['contrasts'] = ordered(effects), ordered(contrasts)
    tables['budget_censored_streams'] = ordered([r for r in sd if r['budget_censored']])
    summary = {
        'schema_version': 1, 'bootstrap_draws': DRAWS, 'bootstrap_seed': SEED,
        'interval_interpretation': 'descriptive family bootstrap of finite synthetic templates; no significance or population claims',
        'unit': 'family: conditions/worlds/variants averaged first; scaling siblings excluded from combined',
        'cohorts': {cohort: {'cases': len(rs), 'families': len({r['family'] for r in rs})}
                    for cohort, rs in ((name, [metadata(c) for c in cases if metadata(c)['cohort'] == name])
                                      for name in ('main', 'challenge', 'scaling'))},
        'input_rows': {k: len(v) for k, v in [('policies', policies), ('recovery', recovery), ('streams', streams),
                      ('integrated', integrated), ('matched_prefix', matched_prefix), ('semantics', semantics), ('previous', previous)]},
        'api_totals': {k: sum(r[k] for r in sd) for k in STREAM_METRICS if k not in ('completion', 'stream_valid', 'protocol_failure', 'budget_censored', 'partial_paid_prefix_success', 'valid_complete_stream_success')},
        'api_streams': {k: sum(r[k] for r in sd) for k in ('completion', 'stream_valid', 'protocol_failure', 'budget_censored', 'partial_paid_prefix_success', 'valid_complete_stream_success')},
        'raw_statuses': dict(sorted(sum((Counter(r['raw_statuses']) for r in sd), Counter()).items())),
        'semantic_mismatches': sum(not r['all_compared_equal'] for r in sem),
        'raw_reference_audit_error_string_differences': sum(not r['raw_reference_audit_error_equal'] for r in sem),
        'same_id_dedup_caveat': 'stronger atomic durable backend capability; not information-matched',
        'cost_caveat': 'conservative token-rate estimate, not invoice; parallel elapsed sums are not campaign wall time',
        'partial_prefix_caveat': 'all streams retained; task completion uses verified paid-prefix certificates even if a later decision fails; full-stream protocol success is separate',
        'hindsight_caveat': 'privileged independent lower bound; gap conditional on a positive certificate; not a selectable policy',
        'matched_prefix_caveat': 'conditional positive-witness rows; offline counterfactual query savings are not empirical API savings',
        'table_rows': {name: len(rows) for name, rows in sorted(tables.items())}}
    return {'tables': tables, 'summary': summary}


def csv_bytes(rows):
    fields = sorted({k for r in rows for k in r})
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fields, lineterminator='\n'); writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True, separators=(',', ':')) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return out.getvalue().encode('utf-8')


def _expected(rows, expected, fields, name):
    unique(rows, fields, name)
    actual = {tuple(r.get(k) for k in fields) for r in rows}
    if actual != expected:
        raise ValueError(f'INCOMPLETE_{name}_GRID: missing={len(expected-actual)} extra={len(actual-expected)}')


def load_inputs():
    """Fail closed before writing any analysis if finalized inputs are incomplete."""
    verify_freeze()
    cases = [r for name in ('heldout', 'challenge', 'scaling') for r in read_rows(ROOT/f'data/phase11/{name}.jsonl')]
    references = [r for name in ('reference', 'reference_challenge', 'reference_scaling') for r in read_rows(ROOT/f'data/phase11/{name}.jsonl')]
    main = [c for c in cases if c['split'] != 'scaling']
    if (len(main), len({c['family'] for c in main}), len(cases)-len(main)) != (72, 36, 12):
        raise ValueError('INCOMPLETE_CASE_GRID')
    _expected(references, {(c['case_id'],) for c in cases}, ('case_id',), 'REFERENCE')
    rows = {name: read_chunks(f'results/phase11/{name}') for name in ('policies', 'recovery', 'integrated', 'matched_prefix', 'semantics', 'previous')}
    streams = read_rows(ROOT/'results/phase11/api/observations.jsonl')
    # Summary existence means acquisition and integration were finalized. Parsing
    # the files also rejects unfinished/truncated JSON writes.
    for name in ('deterministic_summary.json', 'integrated_summary.json', 'api/summary.json'):
        json.loads((ROOT/'results/phase11'/name).read_text(encoding='utf-8'))
    _expected(rows['policies'], {(c['case_id'], w, p, b, s) for c in cases for w in range(len(c['worlds']))
                                 for p in POLICIES for b in BUDGETS for s in (False, True)},
              ('case_id', 'world_index', 'policy', 'budget', 'stop'), 'POLICY')
    _expected(rows['recovery'], {(c['case_id'], w, f, p, sb) for c in main for w in range(len(c['worlds']))
                                 for f in FAULTS for p in RECOVERY for sb in (0, 1)},
              ('case_id', 'world_index', 'fault', 'policy', 'status_budget'), 'RECOVERY')
    _expected(streams, {(c['case_id'], m, v, s) for c in main if c['case_id'].endswith('-0') for m in MODELS for v, s in CELLS},
              ('case_id', 'model', 'view', 'stop'), 'STREAM')
    for stream in streams:
        case = next(c for c in cases if c['case_id'] == stream['case_id'])
        actual = int(sha(('actual11:'+case['case_id']).encode())[:8], 16) % len(case['worlds'])
        if stream['world_index'] != actual:
            raise ValueError('API_ACTUAL_WORLD_MISMATCH')
    _expected(rows['integrated'], {(s['stream_id'], b, f, p) for s in streams for b in (2, 4, 8, 12)
                                  for f in ('none', 'ambiguous_after', 'terminal_noncommit', 'pending_absent') for p in RECOVERY},
              ('stream_id', 'budget', 'fault', 'policy'), 'INTEGRATED')
    _expected(rows['matched_prefix'], {(r['stream_id'], r['budget']) for r in rows['integrated']
                                      if r['fault'] == 'none' and r['policy'] == 'strict_stop'
                                      and r['certificate']['status'] == 'certified'},
              ('stream_id', 'budget'), 'MATCHED_PREFIX')
    _expected(rows['semantics'], {(c['case_id'], w, r) for c in cases for w in range(len(c['worlds'])) for r in range(len(c['routes'])+1)},
              ('case_id', 'world_index', 'route'), 'SEMANTICS')
    _expected(rows['previous'], {(c['case_id'], w) for c in main for w in range(len(c['worlds']))}, ('case_id', 'world_index'), 'PREVIOUS')
    return {'cases': cases, 'references': references, 'streams': streams, **rows}


def build_analysis():
    inputs = load_inputs()
    result = summarize(**inputs)
    directory = ROOT/'results/phase11/analysis'
    outputs = {}
    for name, rows in sorted(result['tables'].items()):
        outputs[name+'.jsonl'] = rb(rows)
        outputs[name+'.csv'] = csv_bytes(rows)
    outputs['summary.json'] = jb(result['summary'])
    manifest = {'files': {name: sha(data) for name, data in sorted(outputs.items())},
                'reproducibility': 'exact deterministic bytes; no clock, network, API, or VM execution',
                'analysis_source_sha256': sha(Path(__file__).read_bytes()),
                'inputs': {name: sha((ROOT/name).read_bytes()) for name in (
                    'results/phase11/provenance/data_freeze.json', 'results/phase11/api/observations.jsonl',
                    *('results/phase11/'+n+'/manifest.json' for n in ('policies', 'recovery', 'integrated', 'matched_prefix', 'semantics', 'previous')))},
                'bootstrap': {'draws': DRAWS, 'seed': SEED, 'percentiles': 'linear interpolation at 2.5 and 97.5 percent'}}
    # Preflight every existing output before making any new immutable files.
    outputs['manifest.json'] = jb(manifest)
    for name, data in outputs.items():
        if (directory/name).exists() and (directory/name).read_bytes() != data:
            raise ValueError('IMMUTABLE_ANALYSIS_MISMATCH:'+name)
    for name, data in sorted(outputs.items()):
        immutable(directory/name, data)
    return result


if __name__ == '__main__':
    print(json.dumps(build_analysis()['summary'], sort_keys=True), flush=True)

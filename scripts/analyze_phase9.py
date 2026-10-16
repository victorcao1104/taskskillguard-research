"""Offline Phase 9 analysis. No acquisition, solver fill-in, or input mutation.

Pure functions accept toy evidence. The CLI requires the frozen complete input
bundle and stores deterministic, immutable summaries with links to raw evidence.
"""
import argparse
from collections import Counter, defaultdict
from itertools import combinations, product
import json
from pathlib import Path
import statistics
import sys

from phase9_common import ROOT, MODELS, jb, rb, sha, immutable, read_rows, verify_freeze
sys.path.insert(0, str(ROOT / 'src'))
from tsg.evidence_v7 import AXES, LABELS
from analyze_phase8 import (ratio, groups, valid, label_counts, expected_facts,
                           canonical_facts, usage_summary, complete_execution_rows,
                           read_input, paired_interval as _paired_interval)

VIEWS = ('A00', 'A01', 'A10', 'A11', 'Q0', 'Q1')
FACTORS = ('dedup', 'tool', 'reducer')
GLOBAL_FIELDS = ('baseline_success', 'legal_routes')
SITE_FIELDS = ('occurred', 'all_occurrences_authorized', 'suppressed_success', 'avoiding_routes')
META = ('case_id', 'family', 'split')
RUNTIME_KEYS = ('split', 'pipeline', 'policy', 'gate_mode', 'preflight', 'cache',
                'planning_budget', 'observation_budget', 'query_budget', 'fault', 'quota')
PAIR_KEYS = ('case_id', 'world_index', 'quota', 'fault', 'pipeline', 'policy', 'gate_mode',
             'preflight', 'cache', 'planning_budget', 'observation_budget', 'query_budget')
METRICS = ('charged_calls', 'planning_units', 'planner_steps', 'primitive_simulations',
           'audit_interpreter_calls', 'audit_steps', 'modeled_latency', 'observation_count',
           'mutation_risk_score', 'unresolved_commit_count', 'unresolved_commit_risk',
           'cache_hits', 'cache_misses', 'query_executions', 'query_steps')


def paired_interval(rows, draws=10000, seed=9009):
    return _paired_interval(rows, draws, seed)


def pick(row, keys):
    return {k: row.get(k) for k in keys}


def normalize_observations(truth, observations, models=MODELS, planned_jobs=()):
    meta = {r['case_id']: r for r in truth if r['split'] == 'heldout'}
    if len({r['case_id'] for r in truth}) != len(truth):
        raise ValueError('DUPLICATE_TRUTH')
    planned = {(cid, model, view, 0): {**pick(r, META), 'model': model, 'view': view,
                'replicate': 0, 'track': 'query' if view.startswith('Q') else 'factorial'}
               for cid, r in meta.items() for model in models for view in VIEWS}
    for job in planned_jobs:
        key = tuple(job[k] for k in ('case_id', 'model', 'view', 'replicate'))
        planned[key] = pick(job, (*META, 'model', 'view', 'replicate', 'track', 'job_id'))
    seen = {}
    for row in observations:
        key = tuple(row[k] for k in ('case_id', 'model', 'view', 'replicate'))
        if key in seen:
            raise ValueError('DUPLICATE_OBSERVATION:' + str(key))
        if row['case_id'] not in meta or row['model'] not in models or row['view'] not in VIEWS:
            raise ValueError('UNEXPECTED_OBSERVATION:' + str(key))
        if type(row['replicate']) is not int or row['replicate'] < 0:
            raise ValueError('INVALID_REPLICATE')
        if any(row[k] != meta[row['case_id']][k] for k in ('family', 'split')):
            raise ValueError('OBSERVATION_METADATA_MISMATCH')
        seen[key] = dict(row)
    for key, job in planned.items():
        if key not in seen:
            seen[key] = {**job, 'missing_response': True, 'raw_status': 'missing_response',
                         'parsed': {'protocol_valid': False, 'by_id': {}, 'reduced_by_id': {},
                                    'order': [], 'diagnostic_codes': ['MISSING_RESPONSE']}}
    return [seen[k] for k in sorted(seen)]


def prediction(row, sid, axis, reducer=0):
    field = 'reduced_by_id' if reducer else 'by_id'
    value = row['parsed'].get(field, {}).get(sid, {}).get(axis) if valid(row) else None
    return value if value in LABELS else 'invalid'


def factorial_scores(truth, observations):
    gold = {r['case_id']: r['labels'] for r in truth}
    detail, cases, metrics = [], [], []
    for row in observations:
        if row['replicate'] or row['track'] != 'factorial':
            continue
        for reducer in (0, 1):
            meta = {**pick(row, (*META, 'model', 'view')), 'dedup': int(row['view'][1]),
                    'tool': int(row['view'][2]), 'reducer': reducer}
            correct = dict.fromkeys(AXES, 0)
            for site in sorted(gold[row['case_id']], key=lambda s: s['id']):
                predicted = {a: prediction(row, site['id'], a, reducer) for a in AXES}
                for axis in AXES:
                    correct[axis] += site[axis] == predicted[axis]
                detail.append({**meta, 'id': site['id'], 'gold': pick(site, AXES), 'predicted': predicted,
                               'protocol_valid': valid(row), 'raw_ref': row.get('raw_ref')})
            n = len(gold[row['case_id']])
            cases.append({**meta, 'total': n, 'correct': correct,
                          'exact': valid(row) and all(v == n for v in correct.values()),
                          'protocol_valid': valid(row), 'raw_ref': row.get('raw_ref')})
    keys = ('split', 'model', 'view', *FACTORS)
    for key, rows in groups(detail, keys):
        cs = [r for r in cases if all(r[k] == v for k, v in key.items())]
        for axis in AXES:
            counts = label_counts((r['gold'][axis], r['predicted'][axis]) for r in rows)
            accepted = [r for r in rows if r['protocol_valid']]
            family = paired_interval([{'family': r['family'], 'difference': ratio(r['correct'][axis], r['total'])} for r in cs], 1)
            metrics.append({**key, 'axis': axis, **counts, 'responses': len(cs),
                'valid_responses': sum(r['protocol_valid'] for r in cs), 'exact_cases': sum(r['exact'] for r in cs),
                'exact_axis_cases': sum(r['protocol_valid'] and r['correct'][axis] == r['total'] for r in cs),
                'valid_label_denominator': len(accepted),
                'validity_conditional_accuracy': ratio(sum(r['gold'][axis] == r['predicted'][axis] for r in accepted), len(accepted)),
                'families': family['families'], 'family_balanced_accuracy': family['estimate']})
    return detail, cases, metrics


def factorial_contrasts(cases, draws=10000, seed=9009):
    details = []
    for key, rows in groups(cases, (*META, 'model')):
        cells = {tuple(r[f] for f in FACTORS): r for r in rows}
        if set(cells) != set(product((0, 1), repeat=3)):
            raise ValueError('INCOMPLETE_FACTORIAL')
        for size in (1, 2, 3):
            for selected in combinations(FACTORS, size):
                for axis in AXES:
                    effect = sum(((-1) ** sum(cell[FACTORS.index(f)] == 0 for f in selected))
                                 * ratio(row['correct'][axis], row['total']) for cell, row in cells.items()) / (2 ** (3-size))
                    details.append({**key, 'axis': axis, 'contrast': ':'.join(selected), 'difference': effect})
    summary = [{**key, **paired_interval(rows, draws, seed)}
               for key, rows in groups(details, ('split', 'model', 'axis', 'contrast'))]
    return summary, details


def fact_scores(truth, observations):
    targets = {r['case_id']: expected_facts(r) for r in truth}
    detail, summary = [], []
    for row in observations:
        if row['track'] != 'factorial' or row['replicate']:
            continue
        counts = {field: Counter(total=0, correct=0, wrong=0, invalid=0) for field in (*GLOBAL_FIELDS, *SITE_FIELDS)}
        predicted = row['parsed'].get('normalized_facts') if valid(row) else None
        by_world = {w['world']: w for w in predicted['worlds']} if predicted else {}
        for world in targets[row['case_id']]['worlds']:
            pworld = by_world.get(world['world'])
            sites = {s['id']: s for s in pworld['sites']} if pworld else {}
            fields = [(field, world[field], pworld.get(field) if pworld else None) for field in GLOBAL_FIELDS]
            fields += [(field, s[field], sites.get(s['id'], {}).get(field)) for s in world['sites'] for field in SITE_FIELDS]
            for field, actual, pred in fields:
                counts[field]['total'] += 1
                counts[field]['invalid' if not predicted else 'correct' if actual == pred else 'wrong'] += 1
        accepted = valid(row) and predicted is not None and all(c['correct'] == c['total'] for c in counts.values())
        detail.append({**pick(row, (*META, 'model', 'view')), 'accepted': accepted,
                       'protocol_valid': valid(row), 'redundancy_consistent': row['parsed'].get('redundancy_consistent'),
                       'fields': counts, 'raw_ref': row.get('raw_ref')})
    for key, rows in groups(detail, ('split', 'model', 'view')):
        fields = {f: {k: sum(r['fields'][f][k] for r in rows) for k in ('total', 'correct', 'wrong', 'invalid')}
                  for f in (*GLOBAL_FIELDS, *SITE_FIELDS)}
        summary.append({**key, 'responses': len(rows), 'valid_responses': sum(r['protocol_valid'] for r in rows),
                        'full_fact_accepted': sum(r['accepted'] for r in rows),
                        'redundancy_inconsistent': sum(r['redundancy_consistent'] is False for r in rows),
                        'fields': {f: {**c, 'accuracy': ratio(c['correct'], c['total'])} for f, c in fields.items()}})
    return detail, summary


def query_scores(truth, rows):
    gold = {r['case_id']: r['labels'] for r in truth}
    scored = []
    seen = set()
    for row in sorted(rows, key=lambda r: str((r['case_id'], r['pipeline'], r['replicate'], r['budget']))):
        key = (row['case_id'], row['pipeline'], row['replicate'], row['budget'])
        if key in seen:
            raise ValueError('DUPLICATE_QUERY_CONDITION')
        seen.add(key)
        result = row['result']
        counts = dict(proven=0, incorrect_proven=0, intrinsic_unknown=0, budget_unknown=0)
        by_axis = {a: dict(total=0, proven=0, intrinsic_unknown=0, budget_unknown=0) for a in AXES}
        for site in gold[row['case_id']]:
            for axis in AXES:
                decision = result['decisions'][site['id']][axis]
                by_axis[axis]['total'] += 1
                proven = decision['proven'] is True
                counts['proven'] += proven
                by_axis[axis]['proven'] += proven
                counts['incorrect_proven'] += proven and result['by_id'][site['id']][axis] != site[axis]
                for reason, field in (('intrinsic', 'intrinsic_unknown'), ('budget', 'budget_unknown')):
                    counts[field] += decision['reason'] == reason
                    by_axis[axis][field] += decision['reason'] == reason
        if counts['incorrect_proven']:
            raise ValueError('UNSOUND_QUERY:' + str(key))
        total = len(gold[row['case_id']]) * len(AXES)
        scored.append({**pick(row, (*META, 'pipeline', 'replicate', 'budget', 'protocol_valid')), **counts,
                       'total': total, 'proven_fraction': ratio(counts['proven'], total), 'by_axis': by_axis,
                       **{k: result.get(k) for k in ('executions', 'interpreter_steps', 'query_count', 'first_fully_resolved_at')},
                       'fully_resolved': counts['proven'] == total})
    summary = []
    for key, rs in groups([r for r in scored if r['replicate'] == 0], ('split', 'pipeline', 'budget')):
        total = sum(r['total'] for r in rs)
        record = {**key, 'cases': len(rs), 'families': len({r['family'] for r in rs}), 'total': total,
                  'valid_rankings': sum(r['protocol_valid'] for r in rs),
                  **{k: sum(r[k] for r in rs) for k in ('proven', 'incorrect_proven', 'intrinsic_unknown', 'budget_unknown', 'executions', 'interpreter_steps')},
                  'fully_resolved_cases': sum(r['fully_resolved'] for r in rs),
                  'family_balanced_proven_fraction': paired_interval([{'family': r['family'], 'difference': r['proven_fraction']} for r in rs], 1)['estimate'],
                  'by_axis': {a: {k: sum(r['by_axis'][a][k] for r in rs) for k in ('total', 'proven', 'intrinsic_unknown', 'budget_unknown')} for a in AXES}}
        positions = [r['first_fully_resolved_at'] for r in rs if r['first_fully_resolved_at'] is not None]
        record.update(proven_fraction=ratio(record['proven'], total),
                      proven_per_execution=ratio(record['proven'], record['executions']),
                      proven_per_interpreter_step=ratio(record['proven'], record['interpreter_steps']),
                      first_complete_known=len(positions), first_complete_mean=statistics.fmean(positions) if positions else None)
        summary.append(record)
    return scored, summary


def query_contrasts(scored, draws=10000, seed=9009):
    rows = [r for r in scored if r['replicate'] == 0]
    details = []
    for key, rs in groups(rows, (*META, 'budget')):
        index = {r['pipeline']: r for r in rs}
        models = sorted({p.rsplit(':', 1)[0] for p in index if ':' in p})
        pairs = [(m+':Q1', m+':Q0') for m in models]
        pairs += [(p, baseline) for p in index if ':' in p for baseline in ('heuristic', 'random')]
        for treatment, baseline in pairs:
            if treatment not in index or baseline not in index:
                continue
            a, b = index[treatment], index[baseline]
            for metric in ('proven_fraction', 'executions', 'interpreter_steps', 'first_fully_resolved_at'):
                av, bv = a[metric], b[metric]
                details.append({**key, 'contrast': treatment+'-'+baseline, 'metric': metric,
                                'difference': av-bv if av is not None and bv is not None else None})
    return ([{**key, **paired_interval(rs, draws, seed)} for key, rs in groups(details, ('split', 'budget', 'contrast', 'metric'))], details)


def result(row):
    return row.get('result') or {}


def success(row):
    return row.get('runner_status', 'completed') == 'completed' and result(row).get('authorized_goal') is True


def metric(row, name):
    if name == 'completion':
        return int(success(row))
    if name in ('ambiguous_stop', 'planning_budget_exhausted'):
        return int(result(row).get(name) is True) if row.get('runner_status', 'completed') == 'completed' else None
    return row.get(name) if name in ('query_executions', 'query_steps') else result(row).get(name)


def execution_summary(rows, keys=RUNTIME_KEYS):
    output = []
    normalized = [{**pick(r, keys), **r} for r in rows]
    for key, rs in groups(normalized, keys):
        reasons = Counter(result(r).get('failure_reason') or 'runner_error' for r in rs if not success(r))
        record = {**key, 'conditions': len(rs), 'cases': len({r['case_id'] for r in rs}),
                  'families': len({r['family'] for r in rs}), 'successes': sum(success(r) for r in rs),
                  'success_rate': ratio(sum(success(r) for r in rs), len(rs)), 'failures': dict(sorted(reasons.items())),
                  'family_balanced_success': paired_interval([{'family': r['family'], 'difference': int(success(r))} for r in rs], 1)['estimate'],
                  'runner_errors': sum(r.get('runner_status', 'completed') != 'completed' for r in rs),
                  'global_unknown_conditions': sum(bool(result(r).get('global_unknown_ids')) for r in rs),
                  'unresolved_gate_conditions': sum(bool(result(r).get('unresolved_gate_ids')) for r in rs),
                  'over_quota': sum(result(r).get('charged_calls', 0) > r['quota'] for r in rs),
                  'over_planning_budget': sum(result(r).get('planning_units', 0) > r['planning_budget']
                                             for r in rs if r.get('planning_budget') is not None)}
        for field in (*METRICS, 'ambiguous_stop', 'planning_budget_exhausted', 'unauthorized_effects', 'duplicate_effects'):
            values = [metric(r, field) for r in rs]
            known = [v for v in values if type(v) in (int, float)]
            record[field] = {'total': sum(known), 'known': len(known), 'mean': ratio(sum(known), len(known))}
        output.append(record)
    return output


def paired_runtime(rows, treatment, baseline, contrast, track, ignored=()):
    keys = tuple(k for k in PAIR_KEYS if k not in ignored)
    def index(predicate):
        output = {}
        for row in rows:
            if predicate(row):
                key = tuple(row.get(k) for k in keys)
                if key in output:
                    raise ValueError('DUPLICATE_PAIR:' + contrast + str(key))
                output[key] = row
        return output
    left, right = index(treatment), index(baseline)
    if set(left) != set(right):
        raise ValueError('UNMATCHED_RUNTIME_PAIRS:' + contrast)
    output = []
    for key in sorted(left, key=str):
        a, b = left[key], right[key]
        diffs = {}
        for field in ('completion', *METRICS, 'ambiguous_stop', 'planning_budget_exhausted'):
            av, bv = metric(a, field), metric(b, field)
            diffs[field] = av-bv if av is not None and bv is not None else None
        output.append({**pick(a, (*META, 'world_index', 'fault', 'quota', 'planning_budget', 'cache', 'query_budget')),
                       'track': track, 'contrast': contrast, 'treatment_id': a['condition_id'],
                       'baseline_id': b['condition_id'], 'both_success': success(a) and success(b),
                       'win': success(a) and not success(b), 'loss': success(b) and not success(a), 'differences': diffs,
                       **{side+'_'+field: value for side, row in (('treatment', a), ('baseline', b))
                          for field, value in {'reason': 'completed' if success(row) else result(row).get('failure_reason') or 'runner_error',
                            'global_unknown': bool(result(row).get('global_unknown_ids')),
                            'unresolved_gate': bool(result(row).get('unresolved_gate_ids')),
                            'observation_count': result(row).get('observation_count'),
                            'compatible_worlds': len(result(row).get('compatible_world_indices', [])),
                            'first_selected_route': (result(row).get('selection_log') or [{}])[0].get('selected_route_index'),
                            'initial_feasible_candidates': result(row).get('initial_feasible_candidate_count')}.items()}})
    return output


def paired_failure_causes(details):
    changed = [{**r, 'outcome': 'win' if r['win'] else 'loss'} for r in details if r['win'] or r['loss']]
    keys = ('track', 'split', 'contrast', 'fault', 'planning_budget', 'cache', 'query_budget', 'outcome',
            'treatment_reason', 'baseline_reason', 'treatment_global_unknown', 'baseline_global_unknown',
            'treatment_unresolved_gate', 'baseline_unresolved_gate')
    return [{**key, 'pairs': len(rows), 'families': len({r['family'] for r in rows}),
             'case_ids': sorted({r['case_id'] for r in rows})} for key, rows in groups(changed, keys)]


def summarize_runtime_pairs(details, draws=10000, seed=9009):
    output = []
    keys = ('track', 'split', 'contrast', 'fault', 'quota', 'planning_budget', 'cache', 'query_budget')
    pooled = [{**r, 'fault': 'pooled'} for r in details]
    for key, rs in groups([*details, *pooled], keys):
        for population in ('all', 'both_success'):
            selected = rs if population == 'all' else [r for r in rs if r['both_success']]
            for field in ('completion', *METRICS, 'ambiguous_stop', 'planning_budget_exhausted'):
                if field == 'completion' and population == 'both_success':
                    continue
                values = [{'family': r['family'], 'difference': r['differences'][field]} for r in selected]
                if not any(r['difference'] is not None for r in values):
                    continue
                output.append({**key, 'population': population, 'metric': field,
                               'matched_conditions': len(selected), 'wins': sum(r['win'] for r in selected),
                               'losses': sum(r['loss'] for r in selected),
                               'sum_differences': sum(r['difference'] for r in values if r['difference'] is not None),
                               **paired_interval(values, draws, seed)})
    return output


def runtime_contrasts(interface, recovery, integrated, draws=10000, seed=9009):
    details = []
    base = lambda r: r.get('pipeline') == 'trusted' and r.get('observation_budget') == 2
    def add(rows, a, b, name, track, ignored):
        # Pure helpers also support intentionally narrower toy grids. The CLI
        # completes every registered production job before reaching this point.
        if any(a(r) for r in rows) and any(b(r) for r in rows):
            details.extend(paired_runtime(rows, a, b, name, track, ignored))
    add(interface, lambda r: base(r) and r.get('preflight') is True and r.get('gate_mode') == 'conditional',
        lambda r: base(r) and r.get('preflight') is True and r.get('gate_mode') == 'aggregate',
        'conditional-aggregate', 'interface', ('gate_mode',))
    for gate in ('aggregate', 'conditional'):
        add(interface, lambda r: base(r) and r.get('gate_mode') == gate and r.get('preflight') is True,
            lambda r: base(r) and r.get('gate_mode') == gate and r.get('preflight') is False,
            'preflight_on-off:' + gate, 'interface', ('preflight',))
    for ob in (0, 1):
        eligibility = lambda r: r['split'] == 'heldout' and r.get('gate_mode') == 'conditional' and r.get('preflight') is True
        add(interface, lambda r: eligibility(r) and r.get('observation_budget') == 2,
            lambda r: eligibility(r) and r.get('observation_budget') == ob,
            'observations2-' + str(ob), 'interface', ('observation_budget',))
    for gate in ('aggregate', 'conditional'):
        for preflight in (False, True):
            add(interface, lambda r: base(r) and r.get('gate_mode') == gate and r.get('preflight') is preflight,
                lambda r: r.get('pipeline') == 'v8_solver',
                f'{gate}:preflight{int(preflight)}-v8_cost', 'regression',
                ('pipeline', 'policy', 'gate_mode', 'preflight', 'cache', 'planning_budget', 'observation_budget'))
    for treatment, baseline in (('calls', 'priority'), ('risk', 'calls')):
        add(recovery, lambda r: r['policy'] == treatment, lambda r: r['policy'] == baseline,
            treatment+'-'+baseline, 'recovery', ('policy',))
    for policy in sorted({r['policy'] for r in recovery}):
        add(recovery, lambda r: r['policy'] == policy and r['cache'] is True,
            lambda r: r['policy'] == policy and r['cache'] is False,
            'cache_on-off:' + policy, 'cache', ('cache',))
    pipelines = sorted({r['pipeline'] for r in integrated})
    models = sorted({p.rsplit(':', 1)[0] for p in pipelines if ':' in p})
    pairs = [(m+':Q1', m+':Q0') for m in models]
    pairs += [(p, b) for p in pipelines if ':' in p for b in ('heuristic', 'random')]
    for treatment, baseline in pairs:
        add(integrated, lambda r: r['pipeline'] == treatment, lambda r: r['pipeline'] == baseline,
            treatment+'-'+baseline, 'integrated', ('pipeline',))
    return summarize_runtime_pairs(details, draws, seed), details


def check_integration(rows):
    bad = [r['condition_id'] for r in rows if r.get('runner_status', 'completed') == 'completed'
           and (result(r).get('evidence_source') != 'trusted_queries'
                or result(r).get('audit_interpreter_calls') != 0 or result(r).get('audit_steps') != 0)]
    if bad:
        raise ValueError('UNCOUNTED_AUDIT:' + str(bad[:5]))
    return {'conditions': len(rows), 'no_uncounted_audit': not bad,
            'query_cost_accounting': 'Per-case acquisition/query work is listed once in query and usage tables; runtime rows repeat that evidence across worlds/faults, so summed runtime query work is per-execution scenario cost.'}


def runtime_failures(track, rows):
    output = []
    for row in rows:
        res = result(row)
        unsafe = any(res.get(k, 0) > 0 for k in ('unauthorized_effects', 'duplicate_effects')) or res.get('charged_calls', 0) > row['quota']
        if success(row) and not unsafe:
            continue
        output.append({**pick(row, ('condition_id', *META, 'world_index', *RUNTIME_KEYS)), 'kind': track,
                       'reason': res.get('failure_reason') or 'runner_error', 'success': success(row),
                       'safety_violation': unsafe, 'global_unknown_ids': res.get('global_unknown_ids', []),
                       'unresolved_gate_ids': res.get('unresolved_gate_ids', []),
                       'evidence_source': res.get('evidence_source'), 'observation_count': res.get('observation_count'),
                       'ambiguous_commit': res.get('ambiguous_stop', False),
                       'raw_ref': f'results/phase9/{track}/vm_results.jsonl#condition_id={row["condition_id"]}'})
    return output


def repeat_summary(truth, observations):
    gold = {r['case_id']: r['labels'] for r in truth}
    output = []
    for key, rows in groups(observations, (*META, 'model', 'view', 'track')):
        if not any(r['replicate'] > 0 for r in rows):
            continue
        rows = sorted(rows, key=lambda r: r['replicate'])
        complete = [r['replicate'] for r in rows] == [0, 1, 2]
        all_valid = complete and all(valid(r) for r in rows)
        item = {**key, 'responses': len(rows), 'complete_three_runs': complete,
                'valid_responses': sum(valid(r) for r in rows), 'replicates': [r['replicate'] for r in rows]}
        if key['track'] == 'query':
            item['identical_query_order'] = all_valid and len({tuple(r['parsed']['order']) for r in rows}) == 1
        else:
            for reducer, name in ((0, 'direct'), (1, 'reduced')):
                signatures = [tuple(prediction(r, s['id'], a, reducer) for s in gold[key['case_id']] for a in AXES) for r in rows]
                wanted = tuple(s[a] for s in gold[key['case_id']] for a in AXES)
                item[name+'_labels_identical'] = all_valid and len(set(signatures)) == 1
                item[name+'_all_correct'] = all_valid and all(s == wanted for s in signatures)
            facts = [r['parsed'].get('normalized_facts') for r in rows]
            item['identical_full_facts'] = all_valid and all(f is not None for f in facts) and len({canonical_facts(f) for f in facts}) == 1
        output.append(item)
    return output


def graph_audit(jobs):
    from tsg.runtime_v6 import parse_source, edges
    output = []
    for key, rows in groups([r for r in jobs if r['track'] == 'query' and r['replicate'] == 0], (*META, 'model')):
        views = {r['view']: r for r in rows}
        if set(views) != {'Q0', 'Q1'}:
            raise ValueError('INCOMPLETE_GRAPH_PAIR')
        a, b = (json.loads(views[v]['prompt']) for v in ('Q0', 'Q1'))
        graph = b.pop('graph')
        equivalent = a == b
        derived = graph == edges(parse_source(a['source']))
        if not equivalent or not derived:
            raise ValueError('GRAPH_SOURCE_MISMATCH')
        output.append({**key, 'source_equivalent': equivalent, 'graph_source_derived': derived,
                       'graph_edges': len(graph), 'graph_bytes': len(json.dumps(graph, separators=(',', ':')).encode()),
                       **{v: {'prompt_bytes': len(views[v]['prompt'].encode()), 'system_bytes': len(views[v]['system'].encode()),
                              'query_count': len(a['queries']), 'request_hash': views[v].get('expected_request_hash')} for v in ('Q0', 'Q1')}})
    return output


def case_characteristics(cases, truth):
    """Public observation projections; no production execution or world choice."""
    from tsg.observation_v9 import observable_queries
    gold = {r['case_id']: r for r in truth}
    output = []
    for case in sorted(cases, key=lambda r: r['case_id']):
        queries = observable_queries(case)
        signatures = []
        for world in case['worlds']:
            grants = {tuple(g) for g in world['grants']}
            values = [(key[1] in world['files'], world['files'].get(key[1])) if key[0] == 'file'
                      else tuple(key[1:]) in grants for key in queries]
            signatures.append(json.dumps(values, sort_keys=True))
        hidden = []
        ws = gold[case['case_id']]['worlds']
        for i, j in combinations(range(len(signatures)), 2):
            if signatures[i] != signatures[j]:
                continue
            left, right = ({s['id']: s for s in ws[k]['labels']} for k in (i, j))
            if any(left[sid][axis] != right[sid][axis] for sid in left for axis in AXES):
                hidden.append([i, j])
        category = ('single_world' if len(signatures) == 1 else 'hidden_disagreement' if hidden
                    else 'fully_observable' if len(set(signatures)) == len(signatures) else 'observationally_equivalent')
        labels = gold[case['case_id']]['labels']
        output.append({**pick(case, META), 'observation_class': category, 'worlds': len(signatures),
                       'observation_options': len(queries), 'hidden_disagreeing_pairs': hidden,
                       'global_unknown': {a: sum(s[a] == 'unknown' for s in labels) for a in AXES},
                       'global_inactive': {a: sum(s[a] == 'not_applicable' for s in labels) for a in AXES}})
    return output


def gate_evidence_summary(truth, tracks):
    gold = {r['case_id']: {s['id']: s['authorization'] for s in r['labels']} for r in truth}
    details = []
    for track, rows in tracks.items():
        for row in rows:
            res = result(row)
            if 'global_unknown_ids' not in res:
                continue
            target = gold[row['case_id']]
            unknown = res['global_unknown_ids']
            unresolved = res.get('unresolved_gate_ids', [])
            details.append({**pick(row, RUNTIME_KEYS), 'track': track, 'conditions': 1,
                            'evidence_source': res.get('evidence_source'),
                            'global_unknown_sites': len(unknown),
                            'true_global_unknown_sites': sum(target[s] == 'unknown' for s in unknown),
                            'unknown_on_nonunknown_truth': sum(target[s] != 'unknown' for s in unknown),
                            'unresolved_gate_sites': len(unresolved),
                            'unresolved_true_inactive_sites': sum(target[s] == 'not_applicable' for s in unresolved),
                            'unresolved_true_unknown_sites': sum(target[s] == 'unknown' for s in unresolved),
                            'ambiguous_commits': res.get('unresolved_commit_count', 0),
                            'planning_budget_exhausted': int(res.get('planning_budget_exhausted') is True)})
    keys = ('track', *RUNTIME_KEYS, 'evidence_source')
    fields = ('conditions', 'global_unknown_sites', 'true_global_unknown_sites', 'unknown_on_nonunknown_truth',
              'unresolved_gate_sites', 'unresolved_true_inactive_sites', 'unresolved_true_unknown_sites',
              'ambiguous_commits', 'planning_budget_exhausted')
    return [{**key, **{f: sum(r[f] for r in rows) for f in fields}} for key, rows in groups(details, keys)]


def validate_runtime(rows):
    ids = [r['condition_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_RUNTIME_CONDITION')


def write_report(output, report):
    encoded = {'summary.json': jb(report['summary'])}
    encoded.update({name+'.jsonl': rb(rows) for name, rows in report.items() if name != 'summary'})
    # Check the entire bundle before creating any file.
    for name, data in encoded.items():
        path = Path(output)/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('IMMUTABLE_MISMATCH:' + str(path))
    for name, data in encoded.items():
        immutable(Path(output)/name, data)


def analyze(truth_rows=None, observations=None, query_rows=(), interface_rows=(), recovery_rows=(), integration_rows=(),
            *, planned_jobs=(), case_rows=(), models=MODELS, draws=10000, seed=9009, output=None, input_manifest=None,
            acquisition_accounting=None, reference_summary=None):
    if truth_rows is None and observations is None:
        return main([])['summary']
    truth = list(truth_rows)
    for row in truth:
        if not row['labels'] or len({s['id'] for s in row['labels']}) != len(row['labels']):
            raise ValueError('INVALID_TRUTH_SITES')
        if any(s[a] not in LABELS for s in row['labels'] for a in AXES):
            raise ValueError('INVALID_TRUTH_LABEL')
    obs = normalize_observations(truth, list(observations), models, planned_jobs)
    primary = [r for r in obs if r['replicate'] == 0]
    candidates, cases, factorial = factorial_scores(truth, obs)
    fcontrasts, fdetails = factorial_contrasts(cases, draws, seed)
    facts, fact_summary = fact_scores(truth, obs)
    queries, query_summary = query_scores(truth, query_rows)
    qcontrasts, qdetails = query_contrasts(queries, draws, seed)
    tracks = {'interface': list(interface_rows), 'recovery': list(recovery_rows), 'integrated': list(integration_rows)}
    for rows in tracks.values():
        validate_runtime(rows)
    integration_check = check_integration(tracks['integrated'])
    rcontrasts, rdetails = runtime_contrasts(tracks['interface'], tracks['recovery'], tracks['integrated'], draws, seed)
    graph = graph_audit(planned_jobs)
    characteristics = case_characteristics(case_rows, truth)
    classes = {r['case_id']: r['observation_class'] for r in characteristics}
    failures = [{**pick(r, (*META, 'model', 'view', 'replicate', 'job_id')), 'kind': 'acquisition',
                 'reason': 'invalid_response', 'raw_status': r.get('raw_status'),
                 'diagnostics': r['parsed'].get('diagnostic_codes', []), 'raw_ref': r.get('raw_ref')} for r in obs if not valid(r)]
    failures += [{**r, 'kind': 'labels', 'reason': 'typed_label_error' if r['protocol_valid'] else 'invalid_response'} for r in cases if not r['exact']]
    failures += [{**r, 'kind': 'facts', 'reason': 'fact_error' if r['protocol_valid'] else 'invalid_response'} for r in facts if not r['accepted']]
    failures += [{**pick(r, (*META, 'pipeline', 'replicate', 'budget', 'protocol_valid')),
                  'kind': 'query', 'reason': 'budget_unresolved' if r['protocol_valid'] else 'invalid_ranking',
                  'proven': r['proven'], 'total': r['total'], 'budget_unknown': r['budget_unknown'],
                  'raw_ref': 'results/phase9/queries/results.jsonl#case_id='+r['case_id']}
                 for r in queries if not r['fully_resolved']]
    for track, rows in tracks.items():
        failures.extend(runtime_failures(track, rows))
    summary = {'schema_version': 'phase9-analysis-v1', 'cases': len(truth),
        'cases_by_split': dict(Counter(r['split'] for r in truth)),
        'families_by_split': {s: len({r['family'] for r in truth if r['split'] == s}) for s in sorted({r['split'] for r in truth})},
        'sites_by_split': {s: sum(len(r['labels']) for r in truth if r['split'] == s) for s in sorted({r['split'] for r in truth})},
        'worlds_by_split': {s: sum(len(r['worlds']) for r in truth if r['split'] == s) for s in sorted({r['split'] for r in truth})},
        'typed_distribution': [{**key, 'axis': a, 'counts': dict(Counter(site[a] for r in rs for site in r['labels']))}
                               for key, rs in groups(truth, ('split',)) for a in AXES],
        'primary_expected': sum(r['split'] == 'heldout' for r in truth)*len(models)*6,
        'primary_responses': len(primary), 'primary_received': sum(not r.get('missing_response', False) for r in primary),
        'primary_valid': sum(valid(r) for r in primary), 'all_observations': len(obs),
        'factorial': factorial, 'factorial_contrasts': fcontrasts, 'facts': fact_summary,
        'queries': query_summary, 'query_contrasts': qcontrasts, 'runtime_contrasts': rcontrasts,
        'paired_failure_causes': paired_failure_causes(rdetails),
        **{track: execution_summary(rows) for track, rows in tracks.items()},
        'runtime_conditions': {track: len(rows) for track, rows in tracks.items()},
        'integration_check': integration_check, 'repeats': repeat_summary(truth, obs), 'usage': usage_summary(obs),
        'gate_evidence': gate_evidence_summary(truth, tracks),
        'graph_source_audit': {'pairs': len(graph), 'all_equivalent': all(r['source_equivalent'] and r['graph_source_derived'] for r in graph)},
        'observation_strata': execution_summary([{**r, 'observation_class': classes[r['case_id']]}
                                                for r in tracks['interface'] if r['case_id'] in classes],
                                               ('observation_class', *RUNTIME_KEYS)),
        'failure_counts': dict(Counter(r['kind'] for r in failures)),
        'methods': {'bootstrap': 'Paired percentile bootstrap of equally weighted authored-family means',
                    'draws': draws, 'seed': seed, 'percentiles': [2.5, 97.5],
                    'family_weighting': 'Case accuracy then family mean for labels/queries; paired world-condition means within each family for runtime.',
                    'invalid': 'Invalid or missing responses are incorrect in every candidate-axis denominator; valid conditional denominators are separate.',
                    'factorial': 'Main effects average high-minus-low over other factors; interactions are averaged differences of differences. Reducer outputs depend on the same response.',
                    'query': 'Proven intrinsic unknown is resolved; budget unknown is unresolved. Every proven label is checked against independent truth.',
                    'cost': 'Upper usage estimates are not invoices. Unknown token/cost fields have explicit known denominators. Tool executions and paid queries are separate.',
                    'runtime': 'Effects pair identical cases/worlds/faults and equal planner/cache settings except the named intervention. V8 comparisons are descriptive policy/interface changes.',
                    'repeats': 'Reliability checks only, excluded from primary accuracy, query and runtime comparisons.',
                    'limitations': 'Exploratory, dependent conditions; 12 authored new families; no multiplicity correction or population-wide safety claim. Synthetic observation, latency and risk semantics.'}}
    if input_manifest is not None:
        summary['input_manifest'] = input_manifest
    if acquisition_accounting is not None:
        summary['acquisition_accounting'] = acquisition_accounting
    if reference_summary is not None:
        summary['reference_summary'] = reference_summary
    report = {'summary': summary, 'candidate_scores': candidates, 'case_scores': cases, 'fact_scores': facts,
              'query_scores': queries, 'factorial_pairs': fdetails, 'query_pairs': qdetails,
              'runtime_pairs': rdetails, 'graph_audit': graph, 'case_characteristics': characteristics, 'failures': failures}
    if output is not None:
        write_report(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.root.resolve() == ROOT.resolve():
        verify_freeze()
    paths = {'truth': 'semantics/truth.jsonl', 'observations': 'api/observations.jsonl',
             'query': 'queries/results.jsonl', 'jobs': 'acquisition/jobs.jsonl',
             **{k: k+'/vm_results.jsonl' for k in ('interface', 'recovery', 'integrated')},
             **{k+'_jobs': k+'/jobs.jsonl' for k in ('interface', 'recovery', 'integrated')}}
    inputs, manifest = {}, {}
    for name, path in paths.items():
        inputs[name], manifest[name] = read_input(args.root, 'results/phase9/'+path)
    case_rows = []
    for phase in (7, 8, 9):
        rows, manifest['cases'+str(phase)] = read_input(args.root, f'data/phase{phase}/heldout.jsonl')
        case_rows.extend([{**r, 'split': 'regression' if phase < 9 else 'heldout'} for r in rows])
    accounting = {}
    for name, relative in (('api', 'api/summary.json'), ('inheritance', 'provenance/budget_inheritance.json'),
                           ('manifest', 'acquisition/manifest.json')):
        raw = (args.root/'results/phase9'/relative).read_bytes()
        accounting[name] = json.loads(raw)
        manifest[name+'_summary'] = {'path': 'results/phase9/'+relative, 'sha256': sha(raw)}
    ledger = (args.root/'results/phase9/api/budget.jsonl').read_bytes()
    manifest['budget_ledger'] = {'path': 'results/phase9/api/budget.jsonl', 'sha256': sha(ledger), 'bytes': len(ledger)}
    reference = {}
    for name, fields in (('coverage', ('passed', 'cases', 'families', 'worlds', 'static_effect_sites',
                                      'aggregate_candidates', 'aggregate_labels', 'irreducible_hidden_cases',
                                      'observable_multiworld_cases')),
                         ('novelty', ('new_original_count', 'prior_original_count', 'prior_reference_program_count',
                                     'unique_new_original_skeletons', 'within_new_exact_groups', 'distributions', 'limitations'))):
        raw = (args.root/f'results/phase9/reference/{name}.json').read_bytes()
        source = json.loads(raw)
        reference[name] = {k: source[k] for k in fields}
        manifest[name] = {'path': f'results/phase9/reference/{name}.json', 'sha256': sha(raw)}
    for track in ('interface', 'recovery', 'integrated'):
        inputs[track] = complete_execution_rows(inputs[track], inputs[track+'_jobs'])
    report = analyze(inputs['truth'], inputs['observations'], inputs['query'], inputs['interface'],
                     inputs['recovery'], inputs['integrated'], planned_jobs=inputs['jobs'],
                     case_rows=case_rows, acquisition_accounting=accounting,
                     reference_summary=reference,
                     input_manifest=manifest, output=args.output or args.root/'results/phase9/analysis')
    print(json.dumps({k: report['summary'][k] for k in ('cases', 'primary_expected', 'primary_received', 'primary_valid', 'runtime_conditions')}))
    return report


if __name__ == '__main__':
    main()

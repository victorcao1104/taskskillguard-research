"""Finite source-derived solver and exact evidence checker, without reference truth."""
from .runtime_v6 import parse_source, candidates, run_semantics

AXES = ('authorization', 'current_route_required', 'catalog_required')
LABELS = ('yes', 'no', 'unknown', 'not_applicable')


def labels_from_worlds(worlds, closed):
    values = {a: [] for a in AXES}
    for w in worlds:
        active = w['occurred']
        values[AXES[0]].append(('yes' if w['all_occurrences_authorized'] else 'no') if active else 'not_applicable')
        values[AXES[1]].append(('no' if w['suppressed_success'] else 'yes') if active and w['baseline_success'] else 'not_applicable')
        values[AXES[2]].append('not_applicable' if not active or not w['legal_routes'] else
                               'no' if w['avoiding_routes'] else 'yes' if closed else 'unknown')
    return {a: vs[0] if len(set(vs)) == 1 else 'unknown' for a, vs in values.items()}


def solve(case):
    """Enumerate public finite worlds/routes/interventions. No case.program read."""
    original = parse_source(case['source'])
    sites = candidates(original)
    worlds = {s['id']: [] for s in sites}
    executions = 0
    for wi, world in enumerate(case['worlds']):
        runs = [run_semantics(p, world, case['goal']) for p in [original, *case['routes']]]
        executions += len(runs)
        legal = [i for i, r in enumerate(runs) if r['goal'] and all(e['authorized'] for e in r['trace'])]
        for site in sites:
            target = [e for e in runs[0]['trace'] if e['id'] == site['id']]
            identities = {(e['op'], e['resource']) for e in target}
            intervention = run_semantics(original, world, case['goal'], suppress=site['id'])
            executions += 1
            avoiding = [i for i in legal if not identities.intersection((e['op'], e['resource']) for e in runs[i]['trace'])] if target else []
            worlds[site['id']].append({'world': wi, 'occurred': bool(target),
                'all_occurrences_authorized': all(e['authorized'] for e in target),
                'baseline_success': runs[0]['goal'], 'suppressed_success': intervention['goal'],
                'legal_routes': legal, 'avoiding_routes': avoiding})
    return {'judgments': [{'id': s['id'], **labels_from_worlds(worlds[s['id']], case['catalog_closed']),
                          'worlds': worlds[s['id']]} for s in sites], 'execution_count': executions}


def check(case, prediction):
    """Require exact coverage and exact typed facts. This checker itself solves the task."""
    expected = solve(case)
    truth = {r['id']: r for r in expected['judgments']}
    rows = prediction.get('judgments', []) if isinstance(prediction, dict) else []
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        return {'accepted': False, 'accepted_ids': [], 'errors': {'coverage': ['malformed']},
                'execution_count': expected['execution_count']}
    ids = [r.get('id') for r in rows]
    if any(type(x) is not str for x in ids) or len(ids) != len(set(ids)) or set(ids) != set(truth):
        return {'accepted': False, 'accepted_ids': [], 'errors': {'coverage': ['candidate_coverage']},
                'execution_count': expected['execution_count']}
    errors, accepted = {}, []
    for row in rows:
        wanted = truth[row['id']]
        bad = [a for a in AXES if row.get(a) != wanted[a]]
        # JSON equality alone equates booleans with integers; strict serialization does not.
        import json
        if json.dumps(row.get('worlds'), sort_keys=True) != json.dumps(wanted['worlds'], sort_keys=True):
            bad.append('world_evidence')
        if bad:
            errors[row['id']] = bad
        else:
            accepted.append(row['id'])
    return {'accepted': not errors, 'accepted_ids': accepted, 'errors': errors,
            'execution_count': expected['execution_count']}

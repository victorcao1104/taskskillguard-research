"""Phase 9 independent semantic, query and operational experiments."""
import argparse
import json
import sys
from phase9_common import ROOT, cases, read_rows, jb, rb, sha, immutable, verify_freeze
sys.path.insert(0, str(ROOT / 'src'))
from tsg.evidence_v7 import AXES

INTERFACE_FAULTS = ('none', 'transient_before', 'known_after', 'double_transient_before')
RECOVERY_FAULTS = ('none', 'transient_before', 'known_after', 'ambiguous_after',
                   'double_transient_before', 'mixed_known_then_ambiguous', 'late_ambiguous')
QUERY_BUDGETS = (2, 4, 8, 'full')


def semantics():
    from tsg.truth_v7 import evaluate_case
    from tsg.truth_v6 import run, static_sites
    from tsg.runtime_v6 import parse_source, candidates, run_semantics
    from tsg.protocol_v8 import exact_facts, aggregate
    truth, audit, diff = [], [], []
    for c in cases():
        ref = evaluate_case(c)
        facts, executions = exact_facts(c)
        labels = aggregate(facts, c['catalog_closed'])
        ast = parse_source(c['source'])
        nodes = candidates(ast)
        ws = [{'world': w['index'], 'baseline_success': w['baseline']['goal'],
               'legal_routes': w['legal_route_indices'], 'sites': [{'id': r['id'], **{k: r[k] for k in
                   ('occurred', 'all_occurrences_authorized', 'suppressed_success', 'avoiding_routes')}} for r in w['labels']]}
              for w in ref['worlds']]
        normalize = lambda f: [{**w, 'sites': sorted(w['sites'], key=lambda r: r['id'])} for w in f['worlds']]
        audit.append({'case_id': c['case_id'], 'ast_equal': ast == c['program'],
                      'coverage_equal': {s['id']: s for s in nodes} == {s['id']: s for s in static_sites(c['program'])},
                      'facts_equal': normalize(facts) == normalize({'worlds': ws}),
                      'labels_equal': all(all(labels[r['id']][a] == r[a] for a in AXES) for r in ref['labels']),
                      'solver_executions': executions, 'sites': len(nodes)})
        truth.append({**ref, **{k: c[k] for k in ('family', 'split')}})
        for ri, program in enumerate([c['program'], *c['routes']]):
            for wi, w in enumerate(c['worlds']):
                for sid in [None, *[s['id'] for s in static_sites(program)]]:
                    x = run(program, w, c['goal'], suppress=sid)
                    y = run_semantics(ast if ri == 0 else program, w, c['goal'], suppress=sid)
                    proj = lambda z: {k: z[k] for k in ('files', 'emits', 'trace', 'goal')} | {'error': bool(z['error'])}
                    diff.append({'case_id': c['case_id'], 'route_index': ri, 'world_index': wi,
                                 'suppress': sid, 'equal': proj(x) == proj(y), 'reference': x, 'production': y})
    summary = {'cases': len(truth), 'sites': sum(c['sites'] for c in audit),
               'worlds': sum(len(c['worlds']) for c in truth), 'comparisons': len(diff),
               'equal': sum(d['equal'] for d in diff),
               **{k: all(c[k] for c in audit) for k in ('ast_equal', 'coverage_equal', 'facts_equal', 'labels_equal')}}
    for name, rows in [('truth', truth), ('audit', audit), ('differential', diff)]:
        immutable(ROOT / f'results/phase9/semantics/{name}.jsonl', rb(rows))
    immutable(ROOT / 'results/phase9/semantics/summary.json', jb(summary))
    assert summary['equal'] == summary['comparisons'] and all(summary[k] for k in ('ast_equal', 'coverage_equal', 'facts_equal', 'labels_equal'))
    print(json.dumps(summary), flush=True)
    return summary


def queries():
    from tsg.query_v9 import evaluate_order, heuristic_order, random_order, query_catalog
    from tsg.truth_v7 import evaluate_case
    cs = {c['case_id']: c for c in cases() if c['split'] == 'heldout'}
    rows, prefixes = [], []
    for c in cs.values():
        expected = {r['id']: {a: r[a] for a in AXES} for r in evaluate_case(c)['labels']}
        orders = [('heuristic', 0, heuristic_order(c), True), ('random', 0, random_order(c, 9009), True)]
        for r in read_rows(ROOT / 'results/phase9/api/observations.jsonl'):
            if r['case_id'] == c['case_id'] and r['track'] == 'query':
                orders.append((r['model'] + ':' + r['view'], r['replicate'], r['parsed']['order'], r['parsed']['protocol_valid']))
        for pipeline, rep, order, valid in orders:
            for budget in QUERY_BUDGETS:
                value = evaluate_order(c, order, budget)
                wrong = [(sid, a) for sid, pred in value['by_id'].items() for a in AXES
                         if value['proven'][sid][a] and pred[a] != expected[sid][a]]
                assert not wrong, ('UNSOUND_QUERY_PROOF', c['case_id'], pipeline, budget, wrong)
                rows.append({**{k: c[k] for k in ('case_id', 'family', 'split')}, 'pipeline': pipeline,
                             'replicate': rep, 'budget': budget, 'protocol_valid': valid,
                             'independent_proofs_valid': True, 'result': value})
        # Every prefix of a deterministic public ordering must be sound, including abstention.
        order = [q['id'] for q in query_catalog(c)]
        for budget in range(len(order) + 1):
            value = evaluate_order(c, order, budget)
            wrong = [(sid, a) for sid, pred in value['by_id'].items() for a in AXES
                     if value['decisions'][sid][a]['proven'] and pred[a] != expected[sid][a]]
            complete = budget != len(order) or all(value['by_id'][sid][a] == val[a] for sid, val in expected.items() for a in AXES)
            prefixes.append({'case_id': c['case_id'], 'budget': budget, 'sound': not wrong, 'complete_equal': complete,
                             'executions': value['executions']})
            assert not wrong and complete and value['executions'] <= budget
    immutable(ROOT / 'results/phase9/queries/results.jsonl', rb(rows))
    immutable(ROOT / 'results/phase9/queries/prefix_checks.jsonl', rb(prefixes))
    summary = {'conditions': len(rows), 'prefix_checks': len(prefixes), 'all_prefixes_sound': True,
               'query_budgets': QUERY_BUDGETS}
    immutable(ROOT / 'results/phase9/queries/summary.json', jb(summary))
    print(json.dumps(summary), flush=True)
    return summary


def execute(args):
    if args['policy'] == 'v8_cost':
        from tsg.recovery_v8 import execute as old
        return old(**{**args, 'policy': 'cost_equal'})
    from tsg.recovery_v9 import execute as new
    return new(**args)


def add(jobs, c, wi, meta, **options):
    public = {k: c[k] for k in ('source', 'routes', 'worlds', 'goal', 'catalog_closed',
                              'observable_files', 'observable_grants') if k in c}
    args = dict(case=public, world_index=wi, quota=16, **options)
    info = {**{k: c[k] for k in ('case_id', 'family', 'split')}, 'world_index': wi, 'quota': 16, **meta,
            **{k: v for k, v in options.items() if k not in ('allowed_ids', 'authorization_evidence')}}
    info['condition_id'] = sha(jb({'meta': info, 'args': args}))[:24]
    jobs.append({'meta': info, 'args': args})


def interface_jobs():
    from tsg.protocol_v8 import exact_facts, aggregate
    jobs = []
    for c in cases():
        labels = aggregate(exact_facts(c)[0], c['catalog_closed'])
        allowed = sorted(s for s, row in labels.items() if row['authorization'] == 'yes')
        for wi in range(len(c['worlds'])):
            for fault in INTERFACE_FAULTS:
                add(jobs, c, wi, {'pipeline': 'v8_solver'}, policy='v8_cost', fault=fault, allowed_ids=allowed)
                for gate in ('aggregate', 'conditional'):
                    for preflight in (False, True):
                        add(jobs, c, wi, {'pipeline': 'trusted'}, policy='calls', fault=fault,
                            gate_mode=gate, preflight=preflight, cache=True, planning_budget=512, observation_budget=2)
                if c['split'] == 'heldout':
                    for ob in (0, 1):
                        add(jobs, c, wi, {'pipeline': 'trusted'}, policy='calls', fault=fault,
                            gate_mode='conditional', preflight=True, cache=True, planning_budget=512, observation_budget=ob)
    return jobs


def recovery_jobs():
    jobs = []
    for c in cases():
        if c['split'] != 'heldout':
            continue
        for wi in range(len(c['worlds'])):
            for fault in RECOVERY_FAULTS:
                for policy in ('priority', 'calls', 'risk'):
                    for cache in (False, True):
                        for budget in (128, 512):
                            add(jobs, c, wi, {'pipeline': 'trusted'}, policy=policy, fault=fault,
                                gate_mode='conditional', preflight=True, cache=cache,
                                planning_budget=budget, observation_budget=2)
    return jobs


def integrated_jobs():
    cs = {c['case_id']: c for c in cases()}
    jobs = []
    for r in read_rows(ROOT / 'results/phase9/queries/results.jsonl'):
        if r['replicate'] or r['budget'] not in (8, 'full'):
            continue
        c = cs[r['case_id']]
        for wi in range(len(c['worlds'])):
            for fault in INTERFACE_FAULTS:
                add(jobs, c, wi, {'pipeline': r['pipeline'], 'query_budget': r['budget'],
                    'query_executions': r['result']['executions'], 'query_steps': r['result']['interpreter_steps'],
                    'protocol_valid': r['protocol_valid']}, policy='calls', fault=fault,
                    gate_mode='conditional', preflight=True, cache=True, planning_budget=512, observation_budget=2,
                    authorization_evidence=r['result']['authorization_evidence'])
    return jobs


def batch(track):
    jobs = {'interface': interface_jobs, 'recovery': recovery_jobs, 'integrated': integrated_jobs}[track]()
    rows = []
    for i, j in enumerate(jobs, 1):
        rows.append({**j['meta'], 'result': execute(j['args']), 'runner_status': 'completed'})
        if i % 1000 == 0:
            print(json.dumps({'track': track, 'completed': i, 'planned': len(jobs)}), flush=True)
    assert len({r['condition_id'] for r in rows}) == len(rows)
    out = ROOT / f'results/phase9/{track}'
    immutable(out / 'jobs.jsonl', rb(jobs))
    immutable(out / 'vm_results.jsonl', rb(rows))
    summary = {'conditions': len(rows), 'unauthorized': sum(r['result']['unauthorized_effects'] for r in rows),
               'duplicates': sum(r['result']['duplicate_effects'] for r in rows),
               'over_quota': sum(r['result']['charged_calls'] > r['quota'] for r in rows)}
    assert summary['unauthorized'] == summary['duplicates'] == summary['over_quota'] == 0
    immutable(out / 'summary.json', jb(summary))
    print(json.dumps({'track': track, **summary}), flush=True)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['semantics', 'queries', 'interface', 'recovery', 'integrated'])
    a = p.parse_args()
    verify_freeze()
    if a.stage == 'semantics':
        semantics()
    elif a.stage == 'queries':
        queries()
    else:
        batch(a.stage)

"""Matched proof, observation, stopping and fault experiments; no model calls."""
import argparse
import json
import sys
from phase10_common import ROOT,cases,read_rows,write_chunks,read_chunks,jb,rb,sha,immutable,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.evidence_v7 import AXES

INTERFACE_FAULTS=('none','transient_before','known_after','double_transient_before')
RECOVERY_FAULTS=('none','transient_before','known_after','mixed_known_then_ambiguous',
                 'late_ambiguous','first_emit_ambiguous','second_write_ambiguous')
WEIGHTS={'default':{'read':0,'write':1,'delete':2,'emit':8},
         'uniform':{'read':0,'write':1,'delete':1,'emit':1},
         'write_heavy':{'read':0,'write':4,'delete':4,'emit':1}}


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
        immutable(ROOT / f'results/phase10/semantics/{name}.jsonl', rb(rows))
    immutable(ROOT / 'results/phase10/semantics/summary.json', jb(summary))
    assert summary['equal'] == summary['comparisons'] and all(summary[k] for k in ('ast_equal', 'coverage_equal', 'facts_equal', 'labels_equal'))
    print(json.dumps(summary), flush=True)
    return summary



def query_scenarios():
    from tsg.query_v10 import evaluate_stream
    from tsg.query_v9 import heuristic_order,random_order
    from tsg.truth_v7 import evaluate_case
    from tsg.budget_v4 import UPPER_PRICES
    cs={c['case_id']:c for c in cases() if c['split']=='heldout'}
    acquired=read_rows(ROOT/'results/phase10/api/observations.jsonl')
    rows=[]
    for c in cs.values():
        gold={r['id']:r for r in evaluate_case(c)['labels']}
        orders=[('heuristic',heuristic_order(c),None),('random',random_order(c,10101),None)]
        orders += [(r['model']+':'+r['cell'],r['order'],r) for r in acquired if r['case_id']==c['case_id']]
        for pipeline,order,stream in orders:
            for budget in (1,2,4,8):
                for stop in ('fixed','diagnostic','authorization'):
                    value=evaluate_stream(c,order,budget,stop)
                    assert all(not value['proven'][sid][a] or value['by_id'][sid][a]==g[a]
                               for sid,g in gold.items() for a in AXES)
                    used=[]
                    ready=(stop=='authorization' and value['authorization_complete']) or (
                        stop=='diagnostic' and value['resolved']==value['total_labels'])
                    if stream:
                        for d in stream['decisions']:
                            if d['before_queries'] < value['executions'] or (
                                not ready and value['executions']<min(budget,value['full_query_count'])
                                and d['before_queries']==value['executions']):used.append(d)
                    usage_cost=sum(d['cost_upper_usd'] for d in used)
                    rows.append({**{k:c[k] for k in ('case_id','family','split')},
                        'pipeline':pipeline,'budget':budget,'stop_mode':stop,
                        'stream_protocol_valid':stream['protocol_valid'] if stream else True,
                        'protocol_valid':all(d['parsed']['protocol_valid'] for d in used),
                        'model_decision_attempts':len(used),
                        'model_request_count':sum(d['raw_status']!='budget_exhausted' for d in used),
                        'attributed_model_cost_upper_usd':usage_cost,
                        'stop_predicate_satisfied':ready,
                        'cost_attribution':'scenario prefix; does not subtract any acquired API spending',
                        'independent_proofs_valid':True,'result':value})
    write_chunks('results/phase10/queries/results',rows)
    summary={'conditions':len(rows),'all_proved_labels_sound':True,'budgets':[1,2,4,8],
             'stop_modes':['fixed','diagnostic','authorization']}
    immutable(ROOT/'results/phase10/queries/summary.json',jb(summary));print(json.dumps(summary),flush=True)
    return summary


def add(jobs,c,wi,meta,engine='v10',**options):
    public={k:c[k] for k in ('source','routes','worlds','goal','catalog_closed','observable_files','observable_grants') if k in c}
    args={'case':public,'world_index':wi,'quota':16,**options}
    info={**{k:c[k] for k in ('case_id','family','split')},'world_index':wi,'quota':16,'engine':engine,
          **meta,**{k:v for k,v in options.items() if k not in ('authorization_evidence','risk_weights')}}
    info['condition_id']=sha(jb({'meta':info,'args':args}))[:24]
    jobs.append({'meta':info,'args':args,'engine':engine})


def interface_jobs():
    jobs=[]
    for c in cases():
        for wi in range(len(c['worlds'])):
            for fault in INTERFACE_FAULTS:
                base=dict(policy='calls',fault=fault,gate_mode='conditional',preflight=True,
                          cache=True,planning_budget=512,observation_budget=2)
                add(jobs,c,wi,{'pipeline':'v9'},engine='v9',**base)
                add(jobs,c,wi,{'pipeline':'v10_authorization'},observation_mode='authorization',**base)
                for ob in (0,1,2):
                    add(jobs,c,wi,{'pipeline':'v10_goal'},observation_mode='goal',**{**base,'observation_budget':ob})
                add(jobs,c,wi,{'pipeline':'v10_no_preflight'},observation_mode='authorization',**{**base,'preflight':False})
    return jobs


def recovery_jobs():
    jobs=[]
    for c in cases():
        if c['split']!='heldout':continue
        for wi in range(len(c['worlds'])):
            for fault in RECOVERY_FAULTS:
                for policy in ('priority','calls','risk'):
                    for name,weights in WEIGHTS.items():
                        add(jobs,c,wi,{'pipeline':'trusted','risk_profile':name},policy=policy,fault=fault,
                            gate_mode='conditional',preflight=True,cache=True,planning_budget=512,
                            observation_budget=2,observation_mode='goal',risk_weights=weights)
    return jobs


def integrated_jobs():
    cs={c['case_id']:c for c in cases()};jobs=[]
    for r in read_chunks('results/phase10/queries/results'):
        if r['budget'] not in (2,8) or r['stop_mode'] not in ('fixed','authorization'):continue
        c=cs[r['case_id']]
        for wi in range(len(c['worlds'])):
            for planning in (128,512):
                for fault in ('none','transient_before'):
                    add(jobs,c,wi,{'pipeline':r['pipeline'],'query_budget':r['budget'],'stop_mode':r['stop_mode'],
                        'query_executions':r['result']['executions'],'query_steps':r['result']['interpreter_steps'],
                        'model_request_count':r['model_request_count'],
                        'model_decision_attempts':r['model_decision_attempts'],
                        'attributed_model_cost_upper_usd':r['attributed_model_cost_upper_usd'],
                        'protocol_valid':r['protocol_valid'],'stream_protocol_valid':r['stream_protocol_valid']},
                        policy='calls',fault=fault,gate_mode='conditional',preflight=True,cache=True,
                        planning_budget=planning,observation_budget=2,observation_mode='goal',
                        authorization_evidence=r['result']['authorization_evidence'])
    return jobs


def execute(job):
    if job['engine']=='v9':
        from tsg.recovery_v9 import execute as run
    else:
        from tsg.recovery_v10 import execute as run
    return run(**job['args'])


def batch(track):
    jobs={'interface':interface_jobs,'recovery':recovery_jobs,'integrated':integrated_jobs}[track]()
    rows=[]
    for i,j in enumerate(jobs,1):
        rows.append({**j['meta'],'result':execute(j),'runner_status':'completed'})
        if i%1000==0:print(json.dumps({'track':track,'completed':i,'planned':len(jobs)}),flush=True)
    assert len({r['condition_id'] for r in rows})==len(rows)
    for r in rows:
        v=r['result'];assert v['unauthorized_effects']==v['duplicate_effects']==0
        assert v['charged_calls']<=r['quota'] and v['planning_units']<=r['planning_budget']
        assert v['observation_count']<=r['observation_budget']
        if track=='integrated':assert v['audit_interpreter_calls']==v['audit_steps']==0
    directory=f'results/phase10/{track}'
    write_chunks(directory+'/jobs',jobs);write_chunks(directory+'/vm_results',rows)
    summary={'conditions':len(rows),'unauthorized':0,'duplicates':0,'over_quota':0,
             'completed_goals':sum(r['result']['authorized_goal'] for r in rows)}
    immutable(ROOT/(directory+'/summary.json'),jb(summary));print(json.dumps({'track':track,**summary}),flush=True)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['semantics','queries','interface','recovery','integrated'])
    a=p.parse_args();verify_freeze()
    if a.stage=='semantics':semantics()
    elif a.stage=='queries':query_scenarios()
    else:batch(a.stage)

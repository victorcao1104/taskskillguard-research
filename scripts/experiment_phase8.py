"""Independent truth audit and all-world recovery/integration conditions."""
import argparse
import json
import sys
from phase8_common import ROOT,cases,read_rows,jb,rb,sha,immutable,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.protocol_v8 import exact_facts,aggregate
from tsg.evidence_v7 import AXES


def semantics():
    from tsg.truth_v7 import evaluate_case
    from tsg.truth_v6 import run,static_sites
    from tsg.runtime_v6 import parse_source,candidates,run_semantics
    truth=[];checks=[];diff=[]
    for c in cases():
        ref=evaluate_case(c);facts,executions=exact_facts(c);labels=aggregate(facts,c['catalog_closed'])
        ast=parse_source(c['source']);a=candidates(ast);b=static_sites(c['program'])
        worlds=[]
        for w in ref['worlds']:
            worlds.append({'world':w['index'],'baseline_success':w['baseline']['goal'],
                           'legal_routes':w['legal_route_indices'],
                           'sites':[{'id':r['id'],**{k:r[k] for k in ('occurred','all_occurrences_authorized','suppressed_success','avoiding_routes')}} for r in w['labels']]})
        # Candidate sequence is serialization, not semantics; compare keyed content.
        normalized=lambda f:[{**w,'sites':sorted(w['sites'],key=lambda s:s['id'])} for w in f['worlds']]
        checks.append({'case_id':c['case_id'],'ast_equal':ast==c['program'],
                       'coverage_equal':len(a)==len({s['id'] for s in a}) and {s['id']:s for s in a}=={s['id']:s for s in b},
                       'facts_equal':normalized(facts)==normalized({'worlds':worlds}),
                       'labels_equal':all(all(labels[r['id']][axis]==r[axis] for axis in AXES) for r in ref['labels']),
                       'solver_executions':executions,'sites':len(a)})
        truth.append({**ref,**{k:c[k] for k in ('family','split')}})
        for ri,program in enumerate([c['program'],*c['routes']]):
            for wi,w in enumerate(c['worlds']):
                for sid in [None,*[s['id'] for s in static_sites(program)]]:
                    x=run(program,w,c['goal'],suppress=sid)
                    y=run_semantics(ast if ri==0 else program,w,c['goal'],suppress=sid)
                    projection=lambda z:{k:z[k] for k in ('files','emits','trace','goal')}|{'error':bool(z['error'])}
                    diff.append({'case_id':c['case_id'],'route_index':ri,'world_index':wi,'suppress':sid,
                                 'equal':projection(x)==projection(y),'reference':x,'production':y})
    summary={'cases':len(truth),'sites':sum(c['sites'] for c in checks),'worlds':sum(len(c['worlds']) for c in truth),
             'comparisons':len(diff),'equal':sum(d['equal'] for d in diff),
             **{k:all(c[k] for c in checks) for k in ('ast_equal','coverage_equal','facts_equal','labels_equal')}}
    for name,rows in [('truth',truth),('audit',checks),('differential',diff)]:immutable(ROOT/f'results/phase8/semantics/{name}.jsonl',rb(rows))
    immutable(ROOT/'results/phase8/semantics/summary.json',jb(summary));print(json.dumps(summary),flush=True)
    assert summary['equal']==summary['comparisons'] and all(summary[k] for k in ('ast_equal','coverage_equal','facts_equal','labels_equal'))
    return summary


def execute(args):
    if args['policy']=='v7_safe':
        from tsg.recovery_v7 import execute as old
        return old(**{**args,'selector':'search_equal','policy':'safe_retry'})
    from tsg.recovery_v8 import execute as new
    return new(**args)


def add(jobs,c,extra,allowed,wi,quota,fault,policy):
    meta={k:c[k] for k in ('case_id','family','split')}|extra|dict(world_index=wi,quota=quota,fault=fault,policy=policy,allowed_ids=allowed)
    meta['condition_id']=sha(jb(meta))[:24]
    public={k:c[k] for k in ('source','routes','worlds','goal','catalog_closed')}
    jobs.append({'meta':meta,'args':dict(case=public,policy=policy,fault=fault,allowed_ids=allowed,world_index=wi,quota=quota)})


def recovery_jobs():
    from tsg.recovery_v7 import FAULTS
    jobs=[]
    for c in cases():
        for wi in range(len(c['worlds'])):
            for q in (8,16):
                for fault in FAULTS:
                    for policy in ('v7_safe','priority_equal','cost_equal'):add(jobs,c,{},None,wi,q,fault,policy)
    return jobs


def integrated_jobs():
    cs={c['case_id']:c for c in cases()};gates=[];jobs=[]
    for r in read_rows(ROOT/'results/phase8/api/observations.jsonl'):
        if r['replicate']!=0:continue
        ids=sorted(sid for sid,l in r['parsed']['by_id'].items() if l['authorization']=='yes')
        gates.append((cs[r['case_id']],ids,{'pipeline':r['model']+':'+r['view'],'protocol_valid':r['parsed']['protocol_valid']}))
    for c in cs.values():
        labels=aggregate(exact_facts(c)[0],c['catalog_closed'])
        for name,ids in [('solver',sorted(s for s,r in labels.items() if r['authorization']=='yes')),('all_allow',None),('all_block',[])]:
            gates.append((c,ids,{'pipeline':name,'protocol_valid':True}))
    for c,ids,meta in gates:
        for wi in range(len(c['worlds'])):
            for fault in ('none','transient_before','known_after','double_transient_before'):
                for policy in ('priority_equal','cost_equal'):add(jobs,c,meta,ids,wi,16,fault,policy)
    return jobs


def batch(track):
    jobs=recovery_jobs() if track=='recovery' else integrated_jobs()
    rows=[{**j['meta'],'result':execute(j['args']),'runner_status':'completed'} for j in jobs]
    assert len({r['condition_id'] for r in rows})==len(rows)
    out=ROOT/f'results/phase8/{track}'
    immutable(out/'jobs.jsonl',rb(jobs));immutable(out/'vm_results.jsonl',rb(rows))
    summary={'conditions':len(rows),'unauthorized':sum(r['result']['unauthorized_effects'] for r in rows),
             'duplicates':sum(r['result']['duplicate_effects'] for r in rows),
             'over_quota':sum(r['result']['charged_calls']>r['quota'] for r in rows)}
    immutable(out/'summary.json',jb(summary));print(json.dumps({'track':track,**summary}),flush=True)
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['semantics','recovery','integrated']);a=p.parse_args()
    verify_freeze()
    if a.stage=='semantics':semantics()
    else:batch(a.stage)

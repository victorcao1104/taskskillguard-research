"""Independent semantic audits and paired recovery/integration experiments."""
import argparse
import json
import sys
from phase7_common import ROOT, cases, read_rows, sha, jb, rb, immutable, verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.evidence_v7 import solve, AXES

def collapse(v): return 'unknown' if v=='not_applicable' else v
def projection(r):
    return {k:r[k] for k in ('files','emits','trace','goal')}|{'error':bool(r['error'])}

def semantics():
    from tsg.truth_v7 import evaluate_case
    from tsg.truth_v6 import evaluate_case as old_truth, run, static_sites
    from tsg.runtime_v6 import parse_source, run_semantics, candidates
    records=[]; comparisons=[]; audit=[]
    old_axes=('authorization','implementation','task')
    for c in cases():
        ref=evaluate_case(c); computed=solve(c); previous=old_truth(c)
        records.append({**ref,**{k:c[k] for k in ('family','split')}})
        pred={r['id']:r for r in computed['judgments']}
        old={r['id']:r for r in previous['labels']}
        ast=parse_source(c['source'])
        facts=[]
        for label in ref['labels']:
            sid=label['id']; evidence=[]
            for wi,w in enumerate(ref['worlds']):
                baseline=w['baseline']; targets=[t for t in baseline['trace'] if t['id']==sid]
                identities={(t['op'],t['resource']) for t in targets}
                legal=w['legal_route_indices']
                evidence.append({'world':wi,'occurred':bool(targets),
                    'all_occurrences_authorized':all(t['authorized'] for t in targets),
                    'baseline_success':baseline['goal'],
                    'suppressed_success':run(c['program'],c['worlds'][wi],c['goal'],suppress=sid)['goal'],
                    'legal_routes':legal,'avoiding_routes':[i for i in legal if not identities.intersection((e['op'],e['resource']) for e in w['routes'][i]['trace'])] if targets else []})
            facts.append({'id':sid,'typed_equal':all(pred[sid][a]==label[a] for a in AXES),
                          'collapsed_equal':all(collapse(label[a])==old[sid][b] for a,b in zip(AXES,old_axes)),
                          'evidence_equal':pred[sid]['worlds']==evidence})
        audit.append({'case_id':c['case_id'],'family':c['family'],'split':c['split'],
                      'ast_equal':ast==c['program'],'sites_equal':candidates(ast)==static_sites(c['program']),
                      'sites':len(facts),'site_checks':facts,'solver_executions':computed['execution_count']})
        for ri,program in enumerate([c['program'],*c['routes']]):
            production=ast if ri==0 else c['routes'][ri-1]
            for wi,w in enumerate(c['worlds']):
                for sid in [None,*[s['id'] for s in static_sites(program)]]:
                    a=run(program,w,c['goal'],suppress=sid);b=run_semantics(production,w,c['goal'],suppress=sid)
                    comparisons.append({'case_id':c['case_id'],'route_index':ri,'world_index':wi,'suppress':sid,
                                        'equal':projection(a)==projection(b),'reference':a,'production':b})
    summary={'cases':len(records),'sites':sum(r['sites'] for r in audit),'worlds':sum(len(r['worlds']) for r in records),
             'comparisons':len(comparisons),'equal':sum(r['equal'] for r in comparisons),
             'all_source_coverage':all(r['ast_equal'] and r['sites_equal'] for r in audit),
             'all_typed_equal':all(s['typed_equal'] for r in audit for s in r['site_checks']),
             'all_collapsed_equal':all(s['collapsed_equal'] for r in audit for s in r['site_checks']),
             'all_evidence_equal':all(s['evidence_equal'] for r in audit for s in r['site_checks'])}
    for name,rows in [('truth',records),('audit',audit),('differential',comparisons)]:
        immutable(ROOT/f'results/phase7/semantics/{name}.jsonl',rb(rows))
    immutable(ROOT/'results/phase7/semantics/summary.json',jb(summary));print(json.dumps(summary),flush=True)
    if not all(summary[k] for k in ('all_source_coverage','all_typed_equal','all_collapsed_equal','all_evidence_equal')) or summary['equal']!=summary['comparisons']:
        raise ValueError('SEMANTIC_VALIDATION_FAILED')

def public(c): return {k:c[k] for k in ('source','routes','worlds','goal','catalog_closed')}
def add(jobs,c,extra,allowed,world_index,quota,fault,selector,policy):
    meta={k:c[k] for k in ('case_id','family','split')}|extra|dict(world_index=world_index,quota=quota,fault=fault,selector=selector,policy=policy,allowed_ids=allowed)
    meta['condition_id']=sha(jb(meta))[:24]
    jobs.append({'meta':meta,'args':dict(case=public(c),selector=selector,policy=policy,fault=fault,
                                        allowed_ids=allowed,world_index=world_index,quota=quota)})

def recovery_jobs():
    from tsg.recovery_v7 import FAULTS
    jobs=[]
    for c in cases():
        for wi in range(len(c['worlds'])):
            for quota in (8,16):
                for fault in FAULTS:
                    for selector in ('first_feasible','search_equal'):
                        for policy in ('legacy','safe_retry'):
                            add(jobs,c,{},None,wi,quota,fault,selector,policy)
    return jobs

def integrated_jobs():
    cs={c['case_id']:c for c in cases()};gates=[];jobs=[]
    for r in read_rows(ROOT/'results/phase7/api/observations.jsonl'):
        if r['replicate']!=0: continue
        ids=[sid for sid,label in r['parsed']['by_id'].items() if label['authorization']=='yes']
        meta={k:r[k] for k in ('model','view','replicate')}|{'pipeline':'raw','protocol_valid':r['parsed']['protocol_valid']}
        if r['view']=='B2': meta['certificate_accepted']=r['certificate']['accepted']
        gates.append((cs[r['case_id']],ids,meta))
        if r['view']=='B2': gates.append((cs[r['case_id']],ids if r['certificate']['accepted'] else [],meta|{'pipeline':'certified'}))
    for c in cs.values():
        ids=[r['id'] for r in solve(c)['judgments'] if r['authorization']=='yes']
        gates.append((c,ids,dict(model='deterministic',view='solver',pipeline='solver',replicate=0,protocol_valid=True)))
    for c,ids,meta in gates:
        for fault in ('none','transient_before','known_after'):
            for selector in ('first_feasible','search_equal'):
                for policy in ('legacy','safe_retry'):
                    add(jobs,c,meta,ids,0,16,fault,selector,policy)
    return jobs

def batch(track):
    from tsg.recovery_v7 import execute
    from tsg.selection_v6 import execute_selection
    jobs=recovery_jobs() if track=='recovery' else integrated_jobs();rows=[];legacy=[]
    for j in jobs:
        result=execute(**j['args'])
        rows.append(j['meta']|{'result':result,'runner_status':'completed'})
        if track=='recovery' and j['args']['policy']=='legacy' and j['args']['fault'] in ('none','transient_before','known_after','ambiguous_after'):
            args={k:v for k,v in j['args'].items() if k not in ('selector','policy')}
            old=execute_selection(mode=j['args']['selector'],**args)
            legacy.append({'condition_id':j['meta']['condition_id'],'equal':all(result[k]==v for k,v in old.items())})
    out=ROOT/f'results/phase7/{track}'
    immutable(out/'jobs.jsonl',rb(jobs));immutable(out/'vm_results.jsonl',rb(rows))
    if legacy:
        immutable(out/'legacy_equivalence.jsonl',rb(legacy))
        assert all(r['equal'] for r in legacy)
    print(json.dumps({'track':track,'conditions':len(rows),'legacy_comparisons':len(legacy),
                      'unauthorized':sum(r['result']['unauthorized_effects'] for r in rows),
                      'duplicates':sum(r['result']['duplicate_effects'] for r in rows)}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['semantics','recovery','integrated']);a=p.parse_args()
    verify_freeze()
    if a.stage=='semantics':semantics()
    else:batch(a.stage)

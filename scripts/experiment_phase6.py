"""Finite differential, factorial and source-to-execution experiment records."""
import argparse
from copy import deepcopy
import json
import subprocess
import sys
from phase6_common import ROOT,cases,read_rows,sha,jb,rb,immutable
sys.path.insert(0,str(ROOT/'src'))
IMAGE='sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244'
MODES=('guard_only','restart','checkpoint','search')
FAULTS=('none','transient_before','known_after','ambiguous_after')


def semantic_projection(result):
    return {k:result[k] for k in ('files','emits','goal')}|{'error':bool(result.get('error')),
            'trace':[{k:t[k] for k in ('id','op','resource','value','authorized')} for t in result['trace']]}


def differential():
    from tsg.truth_v6 import evaluate_case,run,static_sites
    from tsg.runtime_v6 import parse_source,candidates,run_semantics
    truth=[];coverage=[];comparisons=[]
    for c in cases():
        t=evaluate_case(c);truth.append(t)
        ast=parse_source(c['source']);ns=candidates(ast)
        sites=static_sites(c['program'])
        gold={s['id'] for s in sites};pred={s['id'] for s in ns}
        coverage.append({'case_id':c['case_id'],'family':c['family'],'split':c['split'],
                         'gold':len(gold),'predicted':len(pred),'correct':len(gold&pred),
                         'missing':sorted(gold-pred),'extra':sorted(pred-gold),'ast_equal':ast==c['program']})
        for route_index,reference_ast in enumerate([c['program']]+c['routes']):
            production_ast=ast if route_index==0 else c['routes'][route_index-1]
            route_ids=sorted(s['id'] for s in static_sites(reference_ast))
            for wi,w in enumerate(c['worlds']):
                for site in [None]+route_ids:
                    a=run(reference_ast,w,c['goal'],suppress=site)
                    b=run_semantics(production_ast,w,c['goal'],suppress=site)
                    comparisons.append({'case_id':c['case_id'],'family':c['family'],'world':wi,'suppress':site,
                                        'route_index':route_index,'equal':semantic_projection(a)==semantic_projection(b),
                                        'reference':a,'production':b})
    for name,rows in [('truth',truth),('coverage',coverage),('differential',comparisons)]:
        immutable(ROOT/f'results/phase6/first/{name}.jsonl',rb(rows))
    summary={'cases':len(truth),'differential':len(comparisons),'equal':sum(r['equal'] for r in comparisons),
             'gold_sites':sum(r['gold'] for r in coverage),'covered_sites':sum(r['correct'] for r in coverage),
             'extra_sites':sum(len(r['extra']) for r in coverage),'ast_equal':sum(r['ast_equal'] for r in coverage)}
    immutable(ROOT/'results/phase6/first/summary.json',jb(summary));print(json.dumps(summary))
    return summary


def recovery_jobs():
    jobs=[]
    for c in cases():
        for grant_condition in ('supplied','undergrant'):
            cc=deepcopy(c)
            if grant_condition=='undergrant':
                for w in cc['worlds']:
                    w['grants']=[g for g in w['grants'] if g[0]=='read']
            for quota in (4,16):
                for fault in FAULTS:
                    for mode in MODES:
                        meta={k:c[k] for k in ('case_id','family','split')}
                        meta.update(grant_condition=grant_condition,quota=quota,fault=fault,mode=mode,track='recovery')
                        jobs.append({'meta':meta,'args':{'case':cc,'mode':mode,'fault':fault,'quota':quota,
                                                       'allowed_ids':None,'world_index':0}})
    return jobs


def integrated_jobs():
    from tsg.protocol_v6 import allowed_ids
    cs={c['case_id']:c for c in cases()};jobs=[]
    obs=[r for r in read_rows(ROOT/'results/phase6/api/observations.jsonl') if r['replicate']==0]
    truth={r['case_id']:r for r in read_rows(ROOT/'results/phase6/first/truth.jsonl')}
    gates=[]
    for r in obs:
        meta={k:r[k] for k in ('case_id','family','split','model','view','job_id')}
        meta.update(protocol_valid=r['parsed']['protocol_valid'],gate='model')
        gates.append((cs[r['case_id']],allowed_ids(r['parsed']),meta))
    for c in cs.values():
        for gate in ('oracle','all_candidates'):
            ids=[r['id'] for r in truth[c['case_id']]['labels'] if r['authorization']=='yes'] if gate=='oracle' else None
            gates.append((c,ids,{k:c[k] for k in ('case_id','family','split')}|{'gate':gate,'model':'reference','view':gate}))
    for c,ids,meta in gates:
        for mode in ('checkpoint','search'):
            for fault in ('none','transient_before'):
                jobs.append({'meta':meta|{'mode':mode,'fault':fault,'quota':16,'grant_condition':'supplied','track':'integrated'},
                             'args':{'case':c,'mode':mode,'fault':fault,'quota':16,'world_index':0,'allowed_ids':ids}})
    return jobs


WORKER='''import json,sys,types,os
p=json.load(sys.stdin)
m=types.ModuleType("runtime_v6_batch")
sys.modules[m.__name__]=m
exec(compile(p["runtime_source"],"runtime_v6_frozen.py","exec"),m.__dict__)
rows=[]
for j in p["jobs"]:
    try:
        result=m.execute(**j["args"])
        rows.append({**j["meta"],"result":result,"runner_status":"completed"})
    except Exception as e:
        rows.append({**j["meta"],"runner_status":"error","exception":type(e).__name__+": "+str(e)})
json.dump({"uid":os.getuid(),"rows":rows},sys.stdout,sort_keys=True)
'''


def batch(track,container=False):
    from tsg.runtime_v6 import execute
    jobs=recovery_jobs() if track=='recovery' else integrated_jobs()
    out=ROOT/f'results/phase6/{track}'
    runtime=(ROOT/'src/tsg/runtime_v6.py').read_bytes()
    immutable(out/'jobs.jsonl',rb(jobs))
    if not container:
        rows=[]
        for j in jobs:
            try:rows.append(j['meta']|{'result':execute(**j['args']),'runner_status':'completed'})
            except Exception as e:rows.append(j['meta']|{'runner_status':'error','exception':type(e).__name__+': '+str(e)})
        immutable(out/'vm_results.jsonl',rb(rows))
        print(json.dumps({'track':track,'vm_conditions':len(rows),'errors':sum(r['runner_status']!='completed' for r in rows)}));return rows
    resultpath=out/'container_results.jsonl'
    if resultpath.exists():
        print(json.dumps({'track':track,'preserved_container_conditions':len(read_rows(resultpath))}));return
    pre=subprocess.run(['docker','image','inspect',IMAGE,'--format','{{.Id}}'],capture_output=True,timeout=20)
    immutable(out/'image_inspect.json',jb({'exit_code':pre.returncode,'stdout':pre.stdout.decode().strip(),'stderr':pre.stderr.decode(errors='replace')}))
    if pre.returncode or pre.stdout.decode().strip()!=IMAGE:raise RuntimeError('PINNED_IMAGE_UNAVAILABLE')
    payload=jb({'runtime_source':runtime.decode(),'jobs':jobs})
    args=['docker','run','--rm','-i','--network','none','--read-only','--cap-drop','ALL',
          '--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1',
          '--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',IMAGE,'python3','-I','-B','-c',WORKER]
    manifest={'container_count':1,'conditions':len(jobs),'image':IMAGE,'args':args,
              'payload_sha256':sha(payload),'runtime_sha256':sha(runtime),'jobs_sha256':sha(rb(jobs)),
              'scope':'fresh VM state per condition in one batch container; no arbitrary source or real tool dispatch'}
    immutable(out/'container_plan.json',jb(manifest))
    marker=out/'container_intent.json'
    if marker.exists():raise RuntimeError('PRIOR_CONTAINER_INTENT_WITHOUT_RESULT_NO_AUTO_RETRY')
    immutable(marker,jb({'payload_sha256':sha(payload)}))
    proc=subprocess.run(args,input=payload,capture_output=True,timeout=180)
    immutable(out/'container_stdout.json',proc.stdout)
    immutable(out/'container_stderr.txt',proc.stderr)
    immutable(out/'container_exit.json',jb({'exit_code':proc.returncode}))
    if proc.returncode:raise RuntimeError('CONTAINER_FAILED')
    parsed=json.loads(proc.stdout)
    if parsed['uid']!=65534:raise RuntimeError('CONTAINER_UID_MISMATCH')
    rows=parsed['rows'];immutable(resultpath,rb(rows))
    vm=read_rows(out/'vm_results.jsonl')
    audit={'conditions':len(rows),'container_count':1,'uid':parsed['uid'],'exact_vm_agreement':rows==vm,
           'runner_errors':sum(r['runner_status']!='completed' for r in rows)}
    immutable(out/'container_audit.json',jb(audit));print(json.dumps(audit))
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['differential','recovery','integrated']);p.add_argument('--container',action='store_true');a=p.parse_args()
    if not (ROOT/'results/phase6/provenance/freeze.json').exists():raise ValueError('FREEZE_REQUIRED')
    if a.stage=='differential':differential()
    else:batch(a.stage,a.container)

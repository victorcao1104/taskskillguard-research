"""Separately frozen targeted supplement; no changes to main evidence or code."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from copy import deepcopy
import json
from pathlib import Path
import sys
from phase6_common import ROOT,sha,jb,rb,immutable,read_rows
sys.path.insert(0,str(ROOT/'src'))
from tsg.protocol_v6 import SYSTEM,payloads,schema,parse_record,allowed_ids
from tsg.budget_v4 import BudgetV4
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from run_phase5 import price_job,dispatch_once
from experiment_phase6 import semantic_projection,FAULTS,MODES
CAP=29.551575125
OUT=ROOT/'results/phase6/challenge'


def cases():return read_rows(ROOT/'data/phase6/challenge.jsonl')


def freeze():
    paths=['docs/phase6_challenge_design.md','src/tsg/selection_v6.py','scripts/build_phase6_challenge.py',
           'data/phase6/challenge.jsonl','scripts/run_phase6_challenge.py','scripts/analyze_phase6_challenge.py',
           'scripts/container_phase6_v2.py']
    base=json.loads((ROOT/'results/phase6/provenance/freeze.json').read_text())
    for p,h in base['source_sha256'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('MAIN_FROZEN_SOURCE_CHANGED')
    immutable(OUT/'freeze.json',jb({'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in paths},
              'main_freeze_sha256':sha((ROOT/'results/phase6/provenance/freeze.json').read_bytes()),
              'status':'prospective targeted challenge after main offline coverage finding, before own evaluation/API',
              'families':6,'cases':12}))


def checkfreeze():
    obj=json.loads((OUT/'freeze.json').read_text())
    main_path=ROOT/'results/phase6/provenance/freeze.json'
    if sha(main_path.read_bytes())!=obj['main_freeze_sha256']:raise ValueError('MAIN_FREEZE_CHANGED')
    for p,h in json.loads(main_path.read_text())['source_sha256'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('MAIN_FROZEN_SOURCE_CHANGED:'+p)
    for p,h in obj['source_sha256'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('CHALLENGE_SOURCE_CHANGED:'+p)


def differential():
    from tsg.runtime_v6 import parse_source,candidates,run_semantics
    from tsg.truth_v6 import run,static_sites,evaluate_case
    rows=[];truth=[];coverage=[]
    for c in cases():
        ast=parse_source(c['source']);truth.append(evaluate_case(c))
        ns=candidates(ast);gold=static_sites(c['program'])
        coverage.append({'case_id':c['case_id'],'family':c['family'],'ast_equal':ast==c['program'],
                         'gold':len(gold),'predicted':len(ns),'ids_equal':{s['id'] for s in gold}=={s['id'] for s in ns}})
        for ri,p in enumerate([c['program']]+c['routes']):
            for wi,w in enumerate(c['worlds']):
                for site in [None]+[s['id'] for s in static_sites(p)]:
                    a=run(p,w,c['goal'],site);b=run_semantics(ast if ri==0 else p,w,c['goal'],site)
                    rows.append({'case_id':c['case_id'],'route_index':ri,'world':wi,'suppress':site,
                                 'equal':semantic_projection(a)==semantic_projection(b),'reference':a,'production':b})
    for n,value in [('truth',truth),('differential',rows),('coverage',coverage)]:immutable(OUT/'first'/f'{n}.jsonl',rb(value))
    audit={'cases':len(truth),'comparisons':len(rows),'equal':sum(r['equal'] for r in rows),
           'sites':sum(r['gold'] for r in coverage),'coverage_all':all(r['ids_equal'] and r['ast_equal'] for r in coverage)}
    immutable(OUT/'first/summary.json',jb(audit));print(json.dumps(audit))


def initialize():
    old=(ROOT/'results/phase6/api/budget.jsonl').read_bytes()
    # Main must have a complete terminal summary before a second campaign writer.
    main=json.loads((ROOT/'results/phase6/api/summary.json').read_text())
    if main['completed']!=336:raise ValueError('MAIN_NOT_FINISHED')
    path=OUT/'api/budget.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('PREFIX_MISMATCH')
    else:path.write_bytes(old)
    budget=BudgetV4(path,CAP)
    inherited=BudgetV4(ROOT/'results/phase6/api/budget.jsonl',CAP).total_cost
    immutable(OUT/'budget_inheritance.json',jb({'source':'results/phase6/api/budget.jsonl','bytes':len(old),'sha256':sha(old),
              'inherited_upper_usd':inherited,'cap_usd':CAP,'available_usd':CAP-inherited}))
    return budget


def prepare():
    from tsg.runtime_v6 import parse_source,candidates,edges
    budget=initialize();jobs=[];controls=[]
    cs=cases();assert len(cs)==12 and len({c['family'] for c in cs})==6
    for c in cs:
        ast=parse_source(c['source']);ns=candidates(ast);es=edges(ast);ids=[n['id'] for n in ns]
        views=payloads(c,ns,es)
        import tiktoken
        enc=tiktoken.get_encoding('o200k_base')
        controls.append({'case_id':c['case_id'],'local_tokens':{v:len(enc.encode(p)) for v,p in views.items()},
                         'graph_equals_shuffled':views['graph']==views['shuffled'],'edges':es,'candidates':ns})
        for view,prompt in views.items():
            for model in ('gpt-6-luna','gpt-4.1-mini'):
                jobs.append(price_job({'job_id':f'{c["case_id"]}-{view}-{model}','case_id':c['case_id'],
                    'family':c['family'],'split':'challenge','view':view,'model':model,'replicate':0,
                    'system':SYSTEM,'prompt':prompt,'schema':schema(ids),'ids':ids,'max_output':3000}))
    jobs.sort(key=lambda j:sha(j['job_id'].encode()))
    total=sum(j['reservation_upper_usd'] for j in jobs)
    if total>min(2,CAP-budget.total_cost):raise ValueError('CHALLENGE_BUDGET_LIMIT')
    immutable(OUT/'acquisition/jobs.jsonl',rb(jobs));immutable(OUT/'acquisition/controls.jsonl',rb(controls))
    manifest={'conditions':len(jobs),'reservation_upper_usd':total,'jobs_sha256':sha(rb(jobs)),
              'automatic_retries':0,'scope':'targeted counterfactual supplement; report separately'}
    immutable(OUT/'acquisition/manifest.json',jb(manifest));print(json.dumps(manifest),flush=True)
    return jobs,budget


def collect(env_file):
    jobs,budget=prepare();api=OUT/'api';client=ClientV3(load_key(env_file),api/'raw',budget)
    def one(j):
        path=api/'jobs'/f'{j["job_id"]}.json'
        if path.exists():
            row=json.loads(path.read_text(encoding='utf-8'))
            if row['request_hash']!=j['expected_request_hash']:raise ValueError('SAVED_REQUEST_MISMATCH')
            return row
        raw=dispatch_once(j,api,lambda:client.call(j['model'],j['system'],j['prompt'],tag=j['job_id'],
                  max_output=j['max_output'],replicate=0,response_schema=j['schema']))
        row={k:j[k] for k in ('job_id','case_id','family','split','view','model','replicate')}
        row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase6/challenge/api/raw/{raw["request_hash"]}.json',
                   raw_status=raw.get('status'),usage=raw.get('usage'),parsed=parse_record(raw,j['ids']))
        immutable(path,jb(row));return row
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,j) for j in jobs]):
            rows.append(f.result())
            if len(rows)%12==0:print(json.dumps({'completed':len(rows),'total':len(jobs),'cumulative_upper_usd':budget.total_cost}),flush=True)
    rows.sort(key=lambda r:r['job_id']);immutable(api/'observations.jsonl',rb(rows))
    summary={'conditions':len(rows),'valid':sum(r['parsed']['protocol_valid'] for r in rows),
             'statuses':dict(Counter(r['raw_status'] for r in rows)),'cumulative_upper_usd':budget.total_cost,
             'remaining_usd':CAP-budget.total_cost}
    immutable(api/'summary.json',jb(summary));print(json.dumps(summary))


def batch(track):
    from tsg.runtime_v6 import execute
    from tsg.selection_v6 import execute_selection
    cs=cases();jobs=[]
    if track=='recovery':
        for c in cs:
            for grants in ('supplied','undergrant'):
                cc=deepcopy(c)
                if grants=='undergrant':
                    for w in cc['worlds']:w['grants']=[g for g in w['grants'] if g[0]=='read']
                for q in (4,16):
                    for fault in FAULTS:
                        for mode in MODES+('first_feasible','search_equal'):
                            meta={k:c[k] for k in ('case_id','family','split')}|{'grant_condition':grants,'quota':q,'fault':fault,'mode':mode,'track':'challenge_recovery'}
                            jobs.append({'meta':meta,'args':{'case':cc,'mode':mode,'fault':fault,'quota':q,'allowed_ids':None,'world_index':0}})
    else:
        lookup={c['case_id']:c for c in cs};gates=[]
        for r in read_rows(OUT/'api/observations.jsonl'):
            meta={k:r[k] for k in ('case_id','family','split','model','view','job_id')}|{'gate':'model','protocol_valid':r['parsed']['protocol_valid']}
            gates.append((lookup[r['case_id']],allowed_ids(r['parsed']),meta))
        truth={r['case_id']:r for r in read_rows(OUT/'first/truth.jsonl')}
        for c in cs:
            for gate in ('oracle','all_candidates'):
                ids=[r['id'] for r in truth[c['case_id']]['labels'] if r['authorization']=='yes'] if gate=='oracle' else None
                gates.append((c,ids,{k:c[k] for k in ('case_id','family','split')}|{'gate':gate,'model':'reference','view':gate}))
        for c,ids,meta in gates:
            for mode in ('first_feasible','search_equal'):
                for fault in ('none','transient_before'):
                    jobs.append({'meta':meta|{'mode':mode,'fault':fault,'quota':16,'grant_condition':'supplied','track':'challenge_integrated'},
                                 'args':{'case':c,'mode':mode,'fault':fault,'quota':16,'world_index':0,'allowed_ids':ids}})
    rows=[]
    for j in jobs:
        fun=execute_selection if j['args']['mode'] in ('first_feasible','search_equal') else execute
        try:rows.append(j['meta']|{'result':fun(**j['args']),'runner_status':'completed'})
        except Exception as e:rows.append(j['meta']|{'runner_status':'error','exception':type(e).__name__+': '+str(e)})
    immutable(OUT/track/'jobs.jsonl',rb(jobs));immutable(OUT/track/'vm_results.jsonl',rb(rows))
    print(json.dumps({'track':track,'conditions':len(rows),'errors':sum(r['runner_status']!='completed' for r in rows)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['freeze','differential','recovery','prepare','collect','integrated']);p.add_argument('--env-file',type=Path);a=p.parse_args()
    if a.stage=='freeze':freeze()
    else:
        checkfreeze()
        if a.stage=='differential':differential()
        elif a.stage in ('recovery','integrated'):batch(a.stage)
        elif a.stage=='prepare':prepare()
        else:
            if not a.env_file or not a.env_file.is_file():raise ValueError('EXISTING_AUTHORIZED_CONFIG_REQUIRED')
            collect(a.env_file)

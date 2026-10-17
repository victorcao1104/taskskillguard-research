"""Frozen one-shot synthetic-only model acquisition with inherited budget."""
import argparse,json,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from adapter import ROOT,compile_bundle
from experiment import D,save,read,digest,scenario,gold
from protocol import SYSTEM,prompt,schema,parse
from tsg.runtime_v6 import edges
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from tsg.budget_v4 import BudgetV4
sys.path.insert(0,str(ROOT/'scripts'))
from run_phase5 import price_job,dispatch_once

CAP=29.551575125
MODELS=('gpt-6-luna','gpt-4.1-mini')
def initialize():
    old=(ROOT/'results/phase11/api/budget.jsonl').read_bytes();path=D/'api/budget.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:path.write_bytes(old)
    latest={r['reservation_id']:r for r in map(json.loads,old.decode().splitlines())}
    used=sum(r.get('cost_usd',r['reserved_usd']) for r in latest.values())
    audit={'source':'results/phase11/api/budget.jsonl','prefix_bytes':len(old),'prefix_sha256':digest(old),
           'inherited_upper_usd':used,'cumulative_cap_usd':CAP,'remaining_at_start_usd':CAP-used,
           'new_reservation_cap_usd':3,'invoice':False,'price_checked':'2026-10-17',
           'price_sources':['https://developers.openai.com/api/docs/models/gpt-6-luna','https://developers.openai.com/api/docs/models/gpt-4.1-mini']}
    save(D/'provenance/budget_inheritance.json',audit)
    return BudgetV4(path,min(CAP,used+3)),audit

def prepare():
    budget,audit=initialize();cases=read('data/cases.json');spec=read('data/specification.json');jobs=[];contexts=[]
    for case in cases:
        grids=[spec['grid'][0]]
        if case['variant']=='attack' and case['case_id'].endswith('lex1'):grids+=spec['grid'][-2:]
        for grid in grids:
            c=scenario(case,grid);compiled=compile_bundle(c['bundle']);ids=list(compiled['provenance'])
            sites=[{'id':i,'source':compiled['provenance'][i]['text']} for i in ids]
            contexts.append({'context_id':case['case_id']+'@'+grid['grid_id'],'case':c,'grid':grid['grid_id']})
            graph=edges(compiled['program'])
            for view in ('source','graph'):
                text=prompt(c,sites,graph if view=='graph' else None)
                for model in MODELS:
                    job={'job_id':case['case_id']+'-'+grid['grid_id']+'-'+view+'-'+model,
                      'context_id':case['case_id']+'@'+grid['grid_id'],'case_id':case['case_id'],'family':case['family'],
                      'variant':case['variant'],'grid':grid['grid_id'],'view':view,'model':model,'replicate':0,
                      'system':SYSTEM,'prompt':text,'schema':schema(ids),'ids':ids,'max_output':1600}
                    jobs.append(price_job(job))
    jobs.sort(key=lambda j:digest(j['job_id'].encode()))
    total=sum(j['reservation_upper_usd'] for j in jobs)
    if total>min(3,audit['remaining_at_start_usd']):raise ValueError('CAMPAIGN_BOUND:'+str(total))
    save(D/'data/model_contexts.json',contexts);save(D/'api/jobs_frozen.json',jobs)
    save(D/'api/manifest.json',{'planned':len(jobs),'contexts':len(contexts),'models':MODELS,'views':['source','graph'],
      'reservation_upper_usd':total,'jobs_sha256':digest((D/'api/jobs_frozen.json').read_bytes()),
      'automatic_retries':0,'workers':4,'replicates':1,'source_code_hashes':{p:digest((D/p).read_bytes()) for p in ('adapter.py','runtime.py','protocol.py','acquire.py')},
      'graph':'Unchanged Phase6 conservative data/control/call edges over source-derived finite IR. Same complete source/task in both views; no length-matching. Effect of graph includes extra token cost.',
      'selection':'all48 ordinary; first lexical attack per12 families additionally empty closed/open catalogue. Descriptive controlled mechanisms; no population inference.'})
    print(json.dumps({'jobs':len(jobs),'reservation_upper_usd':total,'inherited_upper_usd':audit['inherited_upper_usd']}))

def execute_jobs(env):
    budget,audit=initialize();jobs=read('api/jobs_frozen.json');manifest=read('api/manifest.json')
    if digest((D/'api/jobs_frozen.json').read_bytes())!=manifest['jobs_sha256']:raise ValueError('JOBS_CHANGED')
    for p,h in manifest['source_code_hashes'].items():
        if digest((D/p).read_bytes())!=h:raise ValueError('SOURCE_CHANGED:'+p)
    client=ClientV3(load_key(env),D/'api/raw',budget)
    def one(job):
        path=D/'api/observations'/f"{job['job_id']}.json"
        if path.exists():return json.loads(path.read_text(encoding='utf-8'))
        raw=dispatch_once(job,D/'api',lambda:client.call(job['model'],job['system'],job['prompt'],
              tag=job['job_id'],max_output=job['max_output'],replicate=0,response_schema=job['schema']))
        row={k:job[k] for k in ('job_id','context_id','case_id','family','variant','grid','view','model')}
        row.update(request_hash=raw['request_hash'],raw_status=raw.get('status'),usage=raw.get('usage'),
                   elapsed_seconds=raw.get('elapsed_seconds'),parsed=parse(raw,job['ids']))
        save(path,row);return row
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,j) for j in jobs]):
            results.append(f.result())
            if len(results)%24==0:print(json.dumps({'completed':len(results),'planned':len(jobs),'cumulative_upper_usd':budget.total_cost}),flush=True)
    results.sort(key=lambda r:r['job_id']);save(D/'api/observations.json',results)
    summary={'planned':len(jobs),'responses':len(results),'valid':sum(r['parsed']['protocol_valid'] for r in results),
      'cumulative_upper_usd':budget.total_cost,'new_upper_usd':budget.total_cost-audit['inherited_upper_usd'],
      'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP,'invoice':False}
    save(D/'api/summary.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--env-file',type=Path);a=p.parse_args()
    prepare() if a.command=='prepare' else execute_jobs(a.env_file)

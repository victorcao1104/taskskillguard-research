"""One fixed synthetic acquisition with inherited durable budget and zero retries."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from phase8_common import ROOT,sha,jb,rb,immutable,read_rows,cases,verify_freeze,CAP,MODELS
sys.path.insert(0,str(ROOT/'src'))
from tsg.budget_v7_locked import BudgetV7Locked
from tsg.budget_v4 import UPPER_PRICES
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from tsg.protocol_v8 import VIEWS,system,payload,schema,parse_record,exact_facts,fact_errors
from tsg.runtime_v6 import parse_source,candidates
from run_phase5 import price_job,dispatch_once


def initialize():
    source='results/phase7/api/budget.jsonl'; old=(ROOT/source).read_bytes()
    path=ROOT/'results/phase8/api/budget.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('BUDGET_PREFIX_CHANGED')
    else:path.write_bytes(old)
    prior=BudgetV7Locked(ROOT/source,CAP).total_cost
    audit={'source':source,'prefix_bytes':len(old),'prefix_sha256':sha(old),
           'inherited_upper_usd':prior,'cumulative_cap_usd':CAP,'remaining_at_start_usd':CAP-prior,
           'invoice':False,'prices':UPPER_PRICES,'verified_date':'2026-10-16',
           'sources':['https://developers.openai.com/api/docs/models/gpt-6-luna','https://developers.openai.com/api/docs/models/gpt-4.1-mini']}
    immutable(ROOT/'results/phase8/provenance/budget_inheritance.json',jb(audit))
    return BudgetV7Locked(path,CAP),audit


def prepare():
    verify_freeze();cs=cases();assert len(cs)==72
    held=[c for c in cs if c['split']=='heldout'];assert len(held)==48
    families=sorted({c['family'] for c in held},key=lambda f:sha(('repeat8:'+f).encode()))[:6]
    repeated={sorted(c['case_id'] for c in held if c['family']==f)[0] for f in families}
    budget,audit=initialize();jobs=[]
    for c in cs:
        nodes=candidates(parse_source(c['source']));ids=[s['id'] for s in nodes]
        if not ids: raise ValueError('CAMPAIGN_REQUIRES_CANDIDATES')
        for view in VIEWS:
            for model in MODELS:
                for rep in ([0,1,2] if c['case_id'] in repeated and view in ('F','T') else [0]):
                    jobs.append(price_job({'job_id':f'{c["case_id"]}-{view}-{model}-r{rep}',
                        **{k:c[k] for k in ('case_id','family','split')},'model':model,'view':view,'replicate':rep,
                        'system':system(view),'prompt':payload(c,nodes,view),'schema':schema(ids,view),
                        'ids':ids,'world_count':len(c['worlds']),'route_count':len(c['routes'])+1,
                        'closed':c['catalog_closed'],'max_output':4000}))
    jobs.sort(key=lambda j:sha(j['job_id'].encode()))
    upper=sum(j['reservation_upper_usd'] for j in jobs)
    if upper>min(4,audit['remaining_at_start_usd']):raise ValueError('CAMPAIGN_CAP')
    manifest={'planned':len(jobs),'primary':432,'repeats':48,'repeat_ids':sorted(repeated),
              'jobs_sha256':sha(rb(jobs)),'reservation_upper_usd':upper,'budget':audit,
              'distinct_requests':len({j['expected_request_hash'] for j in jobs}),
              'max_workers':4,'automatic_retries':0,
              'freeze_sha256':sha((ROOT/'results/phase8/provenance/data_freeze.json').read_bytes())}
    assert len(jobs)==480 and manifest['distinct_requests']==480
    immutable(ROOT/'results/phase8/acquisition/jobs.jsonl',rb(jobs))
    immutable(ROOT/'results/phase8/acquisition/manifest.json',jb(manifest))
    return jobs,manifest,budget


def observation(job,raw,case):
    row={k:job[k] for k in ('job_id','case_id','family','split','model','view','replicate')}
    row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase8/api/raw/{raw["request_hash"]}.json',
               raw_status=raw.get('status'),usage=raw.get('usage'),
               parsed=parse_record(raw,job['ids'],job['view'],job['world_count'],job['route_count'],job['closed']))
    usage=raw.get('usage')
    if isinstance(usage,dict) and all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens')):
        ip,op=UPPER_PRICES[job['model']]
        row['usage_cost_upper_usd']=(usage['input_tokens']*ip+usage['output_tokens']*op)/1e6
    if job['view']=='F' and row['parsed']['protocol_valid']:
        row['fact_errors']=fact_errors(row['parsed']['prediction'],exact_facts(case)[0])
    row['tool_executions']=exact_facts(case)[1] if job['view']=='T' else 0
    return row


def finalize(jobs,budget):
    rows=[];cs={c['case_id']:c for c in cases()};api=ROOT/'results/phase8/api'
    for j in jobs:
        raw=json.loads((api/'raw'/f'{j["expected_request_hash"]}.json').read_text(encoding='utf-8'))
        if raw['request_hash']!=j['expected_request_hash']:raise ValueError('HASH_MISMATCH')
        row=observation(j,raw,cs[j['case_id']]);immutable(api/'jobs'/f'{j["job_id"]}.json',jb(row));rows.append(row)
    rows.sort(key=lambda r:r['job_id']);immutable(api/'observations.jsonl',rb(rows))
    summary={'planned':len(jobs),'completed':len(rows),'valid':sum(r['parsed']['protocol_valid'] for r in rows),
             'statuses':dict(Counter(r['raw_status'] for r in rows)),
             'cumulative_upper_usd':budget.total_cost,'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP}
    immutable(api/'summary.json',jb(summary));return summary


def execute(jobs,budget,env_file):
    api=ROOT/'results/phase8/api';client=ClientV3(load_key(env_file),api/'raw',budget)
    def one(j):
        return dispatch_once(j,api,lambda:client.call(j['model'],j['system'],j['prompt'],tag=j['job_id'],
            max_output=j['max_output'],replicate=j['replicate'],response_schema=j['schema']))
    completed=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,j) for j in jobs]):
            future.result();completed+=1
            if completed%12==0:print(json.dumps({'completed':completed,'planned':len(jobs),'cumulative_upper':budget.total_cost}),flush=True)
    print(json.dumps(finalize(jobs,budget)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--finalize',action='store_true');p.add_argument('--env-file',type=Path);a=p.parse_args()
    jobs,manifest,budget=prepare();print(json.dumps(manifest),flush=True)
    if a.execute:
        if not a.env_file or not a.env_file.is_file():raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        execute(jobs,budget,a.env_file)
    elif a.finalize: print(json.dumps(finalize(jobs,budget)),flush=True)

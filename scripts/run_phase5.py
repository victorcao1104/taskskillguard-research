"""Freeze or execute exact Phase5 jobs; no automatic retries, one inherited ledger."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.budget_v4 import BudgetV4, UPPER_PRICES
from tsg.models import make_request, load_key
from tsg.models_v3 import ClientV3
from tsg.reasoning_v5 import SYSTEM_PROMPT, VIEWS, build_payload, project_edges, schema, parse_record
from prepare_phase4 import immutable, json_bytes, rows_bytes, sha
CAP=29.551575125
MODELS=('gpt-6-luna','gpt-4.1-mini')

def initialize(root=ROOT):
    root=Path(root)
    old=(root/'results/phase4/api/budget.jsonl').read_bytes()
    path=root/'results/phase5/api/budget.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):
            raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:
        path.write_bytes(old)
    latest={r['reservation_id']:r for r in map(json.loads,old.decode('utf-8').splitlines())}
    inherited=sum(r.get('cost_usd',r['reserved_usd']) for r in latest.values())
    audit={'prefix_bytes':len(old),'prefix_sha256':sha(old),'inherited_upper_usd':inherited,
           'cumulative_cap_usd':CAP,'remaining_at_start_usd':CAP-inherited,
           'source':'results/phase4/api/budget.jsonl','invoice':False}
    immutable(root/'results/phase5/provenance/budget_inheritance.json',json_bytes(audit))
    return BudgetV4(path,CAP),audit

def price_job(job):
    request=make_request(job['model'],job['system'],job['prompt'],job['max_output'])
    request['text']['format']={'type':'json_schema','name':'tsg_response_v3','strict':True,'schema':job['schema']}
    upper=len(json.dumps(request,ensure_ascii=False).encode())+4096
    if upper>272000:
        raise ValueError('PRICE_CONTEXT_BOUND_EXCEEDED')
    ip,op=UPPER_PRICES[job['model']]
    return {**job,'expected_request_hash':sha(json.dumps({'request':request,'replicate':job['replicate']},sort_keys=True,ensure_ascii=False).encode()),
            'reservation_upper_usd':(upper*ip+job['max_output']*op)/1e6,
            'input_byte_bound':upper}

def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s]

def prepare():
    from tsg.extraction_v5 import extract_graph_v5
    import tiktoken
    import os
    os.environ.setdefault('TIKTOKEN_CACHE_DIR',str(ROOT/'work/tiktoken'))
    tokenizer=tiktoken.get_encoding('o200k_base')
    budget,audit=initialize()
    cases=read_rows(ROOT/'data/phase5/reasoning_cases_v2.jsonl')
    if len(cases)!=18 or len({c['family'] for c in cases})!=18:
        raise ValueError('INDEPENDENT_FAMILY_GRID_MISMATCH')
    jobs=[]; edge_audit=[]; controls=[]
    repeated=sorted(cases,key=lambda c:sha(('repeat5:'+c['case_id']).encode()))[:6]
    repeated_context={c['case_id']:('allow','deny','missing')[i%3] for i,c in enumerate(repeated)}
    for case in cases:
        graph=extract_graph_v5(case['case_id'],case['public']['files'])
        nodes=case['public']['canonical_nodes']
        auto=project_edges(graph,nodes)
        oracle=[{k:e[k] for k in ('source','target','type')} for e in case['private']['oracle_edges']]
        triples=lambda es:{(e['source'],e['target'],e['type']) for e in es}
        a,o=triples(auto),triples(oracle)
        edge_audit.append({'case_id':case['case_id'],'family':case['family'],'split':case['split'],
                           'auto_edges':auto,'oracle_edges':oracle,'true_positive':len(a&o),
                           'extra':len(a-o),'missed':len(o-a),'auto_count':len(a),'oracle_count':len(o),
                           'mapping':'exact span and effect operation; condition kind checked; DATA paths through unscored DATA_OBJECT contracted; no ORDER or mixed-type contraction'})
        immutable(ROOT/f'results/phase5/reasoning_graphs/{case["case_id"]}.json',json_bytes(graph))
        for context in ('allow','deny','missing'):
            payloads={v:build_payload(case,context,v,auto) for v in VIEWS}
            bases=[]
            for p in payloads.values():
                obj=json.loads(p); obj.pop('edge_attachment',None); bases.append(obj)
            if not all(p==bases[0] for p in bases):
                raise ValueError('MATCHED_VIEW_CONTROL_FAILED')
            ids=bases[0]['candidate_ids']
            lengths={v:len(tokenizer.encode(p)) for v,p in payloads.items()}
            if lengths['oracle']!=lengths['length_control']:
                raise ValueError('TOKEN_CONTROL_MISMATCH')
            controls.append({'case_id':case['case_id'],'context':context,'base_equal':True,'local_tokens':lengths,
                             'oracle_shuffled_equal':json.loads(payloads['oracle'])==json.loads(payloads['shuffled'])})
            for view,prompt in payloads.items():
                reps=[0,1,2] if repeated_context.get(case['case_id'])==context and view in ('table','oracle') else [0]
                for model in MODELS:
                    for rep in reps:
                        jobs.append(price_job({'job_id':f'{case["case_id"]}-{context}-{view}-{model}-r{rep}',
                            'track':'synthetic','case_id':case['case_id'],'family':case['family'],'split':case['split'],
                            'context':context,'view':view,'model':model,'replicate':rep,'system':SYSTEM_PROMPT,
                            'prompt':prompt,'schema':schema(ids),'ids':ids,'max_output':3000}))
    jobs.sort(key=lambda j:sha(j['job_id'].encode()))
    total=sum(j['reservation_upper_usd'] for j in jobs)
    if total>min(audit['remaining_at_start_usd'],8):
        raise ValueError('FROZEN_GRID_EXCEEDS_CAMPAIGN_BOUND')
    sources=['scripts/run_phase5.py','src/tsg/reasoning_v5.py','src/tsg/extraction_v5.py',
             'src/tsg/budget_v4.py','src/tsg/models.py','src/tsg/models_v3.py','src/tsg/phase_protocol_v3.py',
             'data/phase5/reasoning_cases_v2.jsonl']
    if (ROOT/'src/tsg/shell_v5.py').exists(): sources.append('src/tsg/shell_v5.py')
    manifest={'registration':'prospective_phase5_v1','planned_jobs':len(jobs),'main_jobs':sum(j['replicate']==0 for j in jobs),
              'repeat_jobs':sum(j['replicate']>0 for j in jobs),'families':18,'models':MODELS,'views':VIEWS,
              'automatic_retries':0,'max_workers':4,'all_request_reservation_upper_usd':total,
              'budget':audit,'repeat_selection':repeated_context,'repeated_context_rule':'six digest-selected families, alternating allow/deny/missing, table and oracle, 2 additional replicates',
              'jobs_sha256':sha(rows_bytes(jobs)),'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in sources},
              'token_control':'o200k_base local oracle length matched exactly; actual API input tokens audited separately',
              'estimand':'finite target-intervention/current route, and fixed capability-domain task route necessity; not strict manual necessity proof'}
    out=ROOT/'results/phase5/acquisition_v2'
    for name,value,encoder in [('jobs.jsonl',jobs,rows_bytes),('manifest.json',manifest,json_bytes),
                              ('edge_audit.jsonl',edge_audit,rows_bytes),('controls.jsonl',controls,rows_bytes)]:
        immutable(out/name,encoder(value))
    return jobs,manifest,budget

def dispatch_once(job, api_root, invoke):
    """Durable intent precedes sending. Orphan intent never authorizes a retry.

    One campaign process owns this directory and ledger. Raw provider results
    already saved by ClientV3 are authoritative; retained reservations cover
    interrupted requests whose billing could not be settled.
    """
    api_root=Path(api_root)
    marker=api_root/'dispatch'/f'{job["job_id"]}.json'
    raw_path=api_root/'raw'/f'{job["expected_request_hash"]}.json'
    if raw_path.exists():
        raw=json.loads(raw_path.read_text(encoding='utf-8'))
        if raw['request_hash']!=job['expected_request_hash']: raise ValueError('RAW_HASH_MISMATCH')
        return raw
    marker.parent.mkdir(parents=True,exist_ok=True)
    try:
        with marker.open('xb') as stream:
            stream.write(json_bytes({'job_id':job['job_id'],'request_hash':job['expected_request_hash']}))
            stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        saved=json.loads(marker.read_text(encoding='utf-8'))
        if saved.get('request_hash')!=job['expected_request_hash']: raise ValueError('DISPATCH_HASH_MISMATCH')
        raw={'tag':job['job_id'],'request_hash':job['expected_request_hash'],
             'status':'interrupted_unknown','diagnostic_codes':['DISPATCH_WITHOUT_SAVED_RESPONSE'],
             'text':'','billing':'inherited ledger reservations retained; no second request issued'}
        immutable(raw_path,json_bytes(raw)); return raw
    raw=invoke()
    if raw['request_hash']!=job['expected_request_hash']: raise ValueError('ACTUAL_HASH_MISMATCH')
    # ClientV3 normally already persisted raw with its own formatting. Do not
    # rewrite it using the adapter-enriched return object.
    if not raw_path.exists(): immutable(raw_path,json_bytes(raw))
    return raw

def execute(jobs,budget,env_file,workers):
    client=ClientV3(load_key(env_file),ROOT/'results/phase5/api/raw',budget)
    def one(job):
        path=ROOT/f'results/phase5/api/jobs/{job["job_id"]}.json'
        if path.exists():
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved['request_hash']!=job['expected_request_hash']: raise ValueError('SAVED_JOB_MISMATCH')
            return saved
        raw=dispatch_once(job,ROOT/'results/phase5/api',lambda:client.call(
                        job['model'],job['system'],job['prompt'],tag=job['job_id'],
                        max_output=job['max_output'],replicate=job['replicate'],response_schema=job['schema']))
        if raw['request_hash']!=job['expected_request_hash']: raise ValueError('REQUEST_HASH_MISMATCH')
        row={k:job[k] for k in ('job_id','track','case_id','family','split','context','view','model','replicate')}
        row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase5/api/raw/{raw["request_hash"]}.json',
                   raw_status=raw.get('status'),usage=raw.get('usage'),elapsed_seconds=raw.get('elapsed_seconds'),
                   parsed=parse_record(raw,job['ids']))
        immutable(path,json_bytes(row))
        return row
    completed=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one,j) for j in jobs]):
            completed.append(future.result())
            if len(completed)%12==0:
                print(json.dumps({'completed':len(completed),'planned':len(jobs),'cumulative_upper_usd':budget.total_cost}),flush=True)
    completed.sort(key=lambda r:r['job_id'])
    immutable(ROOT/'results/phase5/api/observations.jsonl',rows_bytes(completed))
    summary={'planned':len(jobs),'completed':len(completed),'valid':sum(r['parsed']['protocol_valid'] for r in completed),
             'statuses':dict(Counter(r['raw_status'] for r in completed)),'cumulative_upper_usd':budget.total_cost,
             'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP}
    immutable(ROOT/'results/phase5/api/summary.json',json_bytes(summary)); print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--execute',action='store_true')
    parser.add_argument('--env-file',type=Path); parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    args=parser.parse_args(); jobs,manifest,budget=prepare()
    print(json.dumps({k:manifest[k] for k in ('planned_jobs','main_jobs','repeat_jobs','all_request_reservation_upper_usd')}),flush=True)
    if args.execute:
        if not args.env_file or not args.env_file.is_file(): raise ValueError('EXPLICIT_EXISTING_CONFIG_REQUIRED')
        execute(jobs,budget,args.env_file,args.workers)

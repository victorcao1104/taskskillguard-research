"""Separate source-spec clarification follow-up; never replace main outcomes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.extraction_v5 import extract_graph_v5
from tsg.reasoning_v5 import SYSTEM_PROMPT,VIEWS,build_payload,project_edges,schema,parse_record
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from run_phase5 import MODELS,price_job,initialize,dispatch_once,read_rows
from prepare_phase4 import immutable,json_bytes,rows_bytes,sha
OUT=ROOT/'results/phase5_q017'

def prepare():
    case,=read_rows(ROOT/'data/phase5/reasoning_q017_clarified.jsonl')
    graph=extract_graph_v5(case['case_id'],case['public']['files'])
    auto=project_edges(graph,case['public']['canonical_nodes']); jobs=[]
    for context in ('allow','deny','missing'):
        for view in VIEWS:
            prompt=build_payload(case,context,view,auto)
            ids=json.loads(prompt)['candidate_ids']
            for model in MODELS:
                jobs.append(price_job({'job_id':f'{case["case_id"]}-{context}-{view}-{model}-r0',
                    'track':'synthetic','case_id':case['case_id'],'family':case['family'],'split':case['split'],
                    'context':context,'view':view,'model':model,'replicate':0,'system':SYSTEM_PROMPT,
                    'prompt':prompt,'schema':schema(ids),'ids':ids,'max_output':3000}))
    jobs.sort(key=lambda j:sha(j['job_id'].encode()))
    total=sum(j['reservation_upper_usd'] for j in jobs)
    if len(jobs)!=30 or total>.3: raise ValueError('FOLLOWUP_GRID_OR_BOUND_MISMATCH')
    sources=['scripts/run_phase5_q017.py','scripts/run_phase5.py','src/tsg/reasoning_v5.py',
             'data/phase5/reasoning_q017_clarified.jsonl','docs/phase5_truth_erratum.md']
    manifest={'planned_jobs':30,'registration':'source-only-specification-clarification-after-main-freeze',
              'never_replaces_primary':True,'automatic_retries':0,'shared_ledger':'results/phase5/api/budget.jsonl',
              'reservation_upper_usd':total,'jobs_sha256':sha(rows_bytes(jobs)),
              'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in sources}}
    immutable(OUT/'acquisition/jobs.jsonl',rows_bytes(jobs)); immutable(OUT/'acquisition/manifest.json',json_bytes(manifest))
    immutable(OUT/'acquisition/graph.json',json_bytes(graph))
    return jobs,manifest

def execute(jobs,env_file):
    if not (ROOT/'results/phase5/api/summary.json').is_file():
        raise ValueError('MAIN_CAMPAIGN_MUST_FINISH_BEFORE_SHARED_LEDGER_WRITER')
    budget,_=initialize()
    client=ClientV3(load_key(env_file),OUT/'api/raw',budget)
    def one(job):
        path=OUT/f'api/jobs/{job["job_id"]}.json'
        if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
        raw=dispatch_once(job,OUT/'api',lambda:client.call(job['model'],job['system'],job['prompt'],tag=job['job_id'],
                          max_output=job['max_output'],replicate=0,response_schema=job['schema']))
        row={k:job[k] for k in ('job_id','track','case_id','family','split','context','view','model','replicate')}
        row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase5_q017/api/raw/{raw["request_hash"]}.json',
                   raw_status=raw.get('status'),usage=raw.get('usage'),elapsed_seconds=raw.get('elapsed_seconds'),
                   parsed=parse_record(raw,job['ids']))
        immutable(path,json_bytes(row)); return row
    output=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,j) for j in jobs]): output.append(future.result())
    output.sort(key=lambda r:r['job_id'])
    immutable(OUT/'api/observations.jsonl',rows_bytes(output))
    summary={'planned':30,'observed':len(output),'valid':sum(r['parsed']['protocol_valid'] for r in output),
             'cumulative_upper_usd':budget.total_cost,'remaining_usd':budget.limit-budget.total_cost,
             'separate_followup_not_replacement':True}
    immutable(OUT/'api/summary.json',json_bytes(summary)); print(json.dumps(summary),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--execute',action='store_true'); parser.add_argument('--env-file',type=Path)
    args=parser.parse_args(); jobs,manifest=prepare()
    print(json.dumps({'planned':len(jobs),'reservation_upper_usd':manifest['reservation_upper_usd']}),flush=True)
    if args.execute:
        if not args.env_file or not args.env_file.is_file(): raise ValueError('EXPLICIT_EXISTING_CONFIG_REQUIRED')
        execute(jobs,args.env_file)

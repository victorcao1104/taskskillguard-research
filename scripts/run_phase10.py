"""Adaptive decisions with immutable, restart-safe raw evidence and inherited cost."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from phase10_common import ROOT, CAP, CAMPAIGN_CAP, MODELS, cases, read_rows, sha, jb, rb, immutable, verify_freeze
sys.path.insert(0, str(ROOT / 'src'))
from tsg.budget_v7_locked import BudgetV7Locked
from tsg.budget_v4 import UPPER_PRICES
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from run_phase5 import price_job, dispatch_once

CELLS = (('full_diag','full','diagnostic','source'), ('batch_diag','batch','diagnostic','source'),
         ('next_diag','next','diagnostic','source'), ('next_exec','next','execution','source'),
         ('next_graph','next','execution','graph'), ('next_padding','next','execution','padding'))
MAX_QUERIES = 8


def wire_schema(value):
    """Only documented wire constraints; uniqueness remains a strict local check."""
    if isinstance(value,dict):return {k:wire_schema(v) for k,v in value.items() if k!='uniqueItems'}
    if isinstance(value,list):return [wire_schema(v) for v in value]
    return value


def request_cost(raw,job):
    if raw.get('status')=='budget_exhausted':return 0.0,'no_provider_io'
    usage=raw.get('usage')
    if isinstance(usage,dict) and all(type(usage.get(k)) is int and usage[k]>=0 for k in ('input_tokens','output_tokens')):
        ip,op=UPPER_PRICES[job['model']]
        return (usage['input_tokens']*ip+usage['output_tokens']*op)/1e6,'usage_at_upper_prices'
    return job['reservation_upper_usd'],'reservation_upper_unknown_usage'


def initialize(root=ROOT):
    root=Path(root);source='results/phase9/api/budget.jsonl';old=(root/source).read_bytes()
    path=root/'results/phase10/api/budget.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old): raise ValueError('BUDGET_PREFIX_CHANGED')
    else: path.write_bytes(old)
    prior=BudgetV7Locked(root/source,CAP).total_cost
    limit=min(CAP,prior+CAMPAIGN_CAP)
    audit={'source':source,'prefix_bytes':len(old),'prefix_sha256':sha(old),
           'inherited_upper_usd':prior,'cumulative_cap_usd':CAP,'campaign_limit_usd':limit,
           'campaign_additional_cap_usd':CAMPAIGN_CAP,'remaining_at_start_usd':CAP-prior,
           'prices':UPPER_PRICES,'verified_date':'2026-10-16','invoice':False,
           'sources':['https://developers.openai.com/api/docs/models/gpt-6-luna',
                      'https://developers.openai.com/api/docs/models/gpt-4.1-mini']}
    immutable(root/'results/phase10/provenance/budget_inheritance.json',jb(audit))
    return BudgetV7Locked(path,limit),audit


def build_streams(cs):
    rows=[]
    for c in cs:
        for model in MODELS:
            for cell,protocol,objective,representation in CELLS:
                rows.append({**{k:c[k] for k in ('case_id','family','split')},'model':model,
                    'cell':cell,'protocol':protocol,'objective':objective,'representation':representation,
                    'stream_id':f'{c["case_id"]}-{model}-{cell}','max_queries':MAX_QUERIES})
    return sorted(rows,key=lambda r:sha(r['stream_id'].encode()))


def make_job(spec, case, session, round_index):
    from tsg.query_v10 import selection_system, selection_payload, selection_schema
    remaining=session.remaining_ids
    limit=min(4,MAX_QUERIES-session.result()['executions'],len(remaining)) if spec['protocol']=='batch' else 1
    if spec['protocol']=='full': limit=len(remaining)
    prompt=json.loads(selection_payload(case,remaining,session.observations,spec['protocol'],spec['objective'],
                                        representation=spec['representation']))
    prompt['selection_limit']=limit
    return price_job({**spec,'job_id':f'{spec["stream_id"]}-d{round_index}', 'round':round_index,
        'replicate':0,'remaining_ids':remaining,'limit':limit,
        'before_queries':session.result()['executions'],
        'system':selection_system(spec['protocol'],spec['objective']),
        'prompt':json.dumps(prompt,sort_keys=True,ensure_ascii=False,separators=(',',':')),
        'schema':wire_schema(selection_schema(remaining,spec['protocol'],limit)),
        'max_output':2000 if spec['protocol']=='full' else 384})


def read_saved(job, api):
    raw=json.loads((Path(api)/'raw'/f'{job["expected_request_hash"]}.json').read_text(encoding='utf-8'))
    if raw['request_hash']!=job['expected_request_hash']:raise ValueError('SAVED_REQUEST_CHANGED')
    return raw


def acquire_stream(spec, case, api, client=None):
    from tsg.query_v10 import QuerySession, parse_selection
    session=QuerySession(case);decisions=[];order=[];valid=True;stop='budget'
    for round_index in range(MAX_QUERIES):
        if not session.remaining_ids or len(order)>=MAX_QUERIES:break
        job=make_job(spec,case,session,round_index)
        immutable(api/'requests'/f'{job["job_id"]}.json',jb(job))
        if client is None:raw=read_saved(job,api)
        else:
            try:
                raw=dispatch_once(job,api,lambda:client.call(job['model'],job['system'],job['prompt'],
                    tag=job['job_id'],max_output=job['max_output'],replicate=0,response_schema=job['schema']))
            except RuntimeError as exc:
                if str(exc)!='BUDGET_LIMIT':raise
                raw={'tag':job['job_id'],'request_hash':job['expected_request_hash'],'status':'budget_exhausted',
                     'text':'','billing':'reserve rejected before provider I/O; no new charge',
                     'diagnostic_codes':['BUDGET_LIMIT']}
                immutable(api/'raw'/f'{job["expected_request_hash"]}.json',jb(raw))
            raw=read_saved(job,api)
        parsed=parse_selection(raw,job['remaining_ids'],spec['protocol'],job['limit'])
        row={'job_id':job['job_id'],'request_hash':job['expected_request_hash'],
             'raw_ref':f'results/phase10/api/raw/{job["expected_request_hash"]}.json',
             'before_queries':len(order),'raw_status':raw.get('status'),'usage':raw.get('usage'),
             'parsed':parsed}
        row['cost_upper_usd'],row['cost_basis']=request_cost(raw,job)
        immutable(api/'decisions'/f'{job["job_id"]}.json',jb(row));decisions.append(row)
        if not parsed['protocol_valid']:
            valid=False;stop='budget_exhausted' if raw.get('status')=='budget_exhausted' else 'protocol_failure';break
        selected=parsed['selected_ids'][:MAX_QUERIES-len(order)]
        session.consume(selected);order.extend(selected)
        if spec['protocol']=='full':break
    if not session.remaining_ids:stop='catalog_exhausted'
    result={**spec,'order':order,'protocol_valid':valid,'stop_reason':stop,
            'decision_count':len(decisions),'decisions':decisions,'result':session.result()}
    immutable(api/'streams'/f'{spec["stream_id"]}.json',jb(result))
    return result


def prepare():
    verify_freeze();cs=[c for c in cases() if c['split']=='heldout']
    assert len(cs)==24 and len({c['family'] for c in cs})==12
    streams=build_streams(cs);budget,audit=initialize()
    manifest={'streams':len(streams),'max_requests':sum(1 if s['protocol']=='full' else 8 for s in streams),
              'max_queries':MAX_QUERIES,'models':MODELS,'cells':CELLS,'budget':audit,
              'automatic_retries':0,'workers':4,'stream_sha256':sha(rb(streams)),
              'prefix_evaluation':'independent actual interpreter replay with stopping; all campaign API calls remain charged',
              'freeze_sha256':sha((ROOT/'results/phase10/provenance/data_freeze.json').read_bytes())}
    immutable(ROOT/'results/phase10/acquisition/streams.jsonl',rb(streams))
    immutable(ROOT/'results/phase10/acquisition/manifest.json',jb(manifest))
    return streams,manifest,budget


def finalize(streams,budget):
    rows=[json.loads((ROOT/f'results/phase10/api/streams/{s["stream_id"]}.json').read_text()) for s in streams]
    rows.sort(key=lambda r:r['stream_id']);decisions=[d for r in rows for d in r['decisions']]
    assert len({d['job_id'] for d in decisions})==len(decisions)
    immutable(ROOT/'results/phase10/api/observations.jsonl',rb(rows))
    audit=json.loads((ROOT/'results/phase10/provenance/budget_inheritance.json').read_text())
    summary={'streams':len(rows),'valid_streams':sum(r['protocol_valid'] for r in rows),
             'requests':len(decisions),'valid_decisions':sum(d['parsed']['protocol_valid'] for d in decisions),
             'provider_or_unknown_requests':sum(d['raw_status']!='budget_exhausted' for d in decisions),
             'budget_rejections':sum(d['raw_status']=='budget_exhausted' for d in decisions),
             'statuses':dict(Counter(d['raw_status'] for d in decisions)),
             'cumulative_upper_usd':budget.total_cost,'increment_upper_usd':budget.total_cost-audit['inherited_upper_usd'],
             'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP,'campaign_limit_usd':budget.limit}
    immutable(ROOT/'results/phase10/api/summary.json',jb(summary));return summary


def execute(streams,budget,env_file=None):
    api=ROOT/'results/phase10/api';cs={c['case_id']:c for c in cases()}
    client=ClientV3(load_key(env_file),api/'raw',budget) if env_file else None
    with ThreadPoolExecutor(max_workers=4 if client else 1) as pool:
        futures=[pool.submit(acquire_stream,s,cs[s['case_id']],api,client) for s in streams]
        for i,f in enumerate(as_completed(futures),1):
            f.result()
            if i%12==0:print(json.dumps({'streams_completed':i,'planned':len(streams),'cumulative_upper':budget.total_cost}),flush=True)
    print(json.dumps(finalize(streams,budget)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--replay',action='store_true')
    p.add_argument('--env-file',type=Path);a=p.parse_args();streams,manifest,budget=prepare()
    print(json.dumps(manifest),flush=True)
    if a.execute:
        if not a.env_file or not a.env_file.is_file():raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        execute(streams,budget,a.env_file)
    elif a.replay:execute(streams,budget)

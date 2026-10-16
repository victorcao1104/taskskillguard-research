"""True online acquisition; immutable raw records; one inherited locked budget."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
import os
from pathlib import Path
import sys
from functools import lru_cache
from phase11_common import ROOT,CAP,CAMPAIGN_CAP,MODELS,sha,jb,rb,immutable,read_rows,verify_freeze
sys.path.insert(0,str(ROOT/'src'))
from tsg.certificate_v11 import CertificateSession,make_reader,selection_payload,SYSTEM,dump
from tsg.protocol_v11 import parse_selection_v11
from tsg.query_v10 import selection_schema
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from tsg.budget_v7_locked import BudgetV7Locked
from tsg.budget_v4 import UPPER_PRICES
from run_phase5 import price_job,dispatch_once
from run_phase10 import request_cost

CELLS=(('source',True),('graph',True),('padding',True),('source',False))
MAX_QUERIES=12

@lru_cache(maxsize=1)
def tokenizer():
    import tiktoken
    os.environ.setdefault('TIKTOKEN_CACHE_DIR',str(ROOT/'work/tiktoken'))
    return tiktoken.get_encoding('o200k_base')

def controlled_payloads(session):
    enc=tokenizer();source=selection_payload(session,'source');graph=selection_payload(session,'graph')
    v=json.loads(graph);v['representation']={'kind':'padding','inert':''}
    target=len(enc.encode(graph));base=len(enc.encode(dump(v)))
    if base>target:raise ValueError('PADDING_BASE_EXCEEDS_GRAPH')
    count=target-base
    for _ in range(8):
        v['representation']['inert']=' x'*count
        padding=dump(v);actual=len(enc.encode(padding))
        if actual==target:break
        count+=target-actual
        if count<0:raise ValueError('TOKEN_PADDING_NEGATIVE')
    else:raise ValueError('TOKEN_PADDING_MISMATCH')
    return {'source':source,'graph':graph,'padding':padding}, {
        'source':len(enc.encode(source)),'graph':target,'padding':actual}

def build_specs(cases):
    rows=[]
    for c in cases:
        # Data author's lexical variant marker is verified before acquisition.
        if not c['case_id'].endswith('-0'):continue
        world=int(sha(('actual11:'+c['case_id']).encode())[:8],16)%len(c['worlds'])
        for model in MODELS:
            for view,stop in CELLS:
                sid=f'{c["case_id"]}-{model}-{view}-'+('online' if stop else 'fixed')
                rows.append({'case_id':c['case_id'],'family':c['family'],'model':model,'view':view,
                    'stop':stop,'world_index':world,'stream_id':sid,'max_queries':MAX_QUERIES})
    rows.sort(key=lambda r:sha(r['stream_id'].encode()))
    for i,r in enumerate(rows):r['replicate']=110000+i
    return rows

def validate_specs(specs):
    family_cases={}
    for s in specs:family_cases.setdefault(s['family'],set()).add(s['case_id'])
    if (len(specs)!=288 or len({s['case_id'] for s in specs})!=36 or len(family_cases)!=36
        or any(len(ids)!=1 for ids in family_cases.values())):
        raise ValueError('ACQUISITION_GRID_MISMATCH')

def make_job(spec,session,index):
    payloads,lengths=controlled_payloads(session)
    return price_job({**spec,'job_id':f'{spec["stream_id"]}-d{index:02}',
        'round':index,'before_queries':session.result()['query_count'],
        'remaining_ids':session.remaining_ids,'system':SYSTEM,'prompt':payloads[spec['view']],
        'schema':selection_schema(session.remaining_ids,'next',1),'max_output':1024,
        'local_tokens':lengths,'tokenizer':'o200k_base surrogate, not verified model tokenizer'})

def acquire_stream(spec,case,api,invoke=None):
    api=Path(api);session=CertificateSession(case,make_reader(case,spec['world_index']))
    decisions=[];first=None;stop_reason='budget';valid=True
    for index in range(spec['max_queries']):
        cert=session.check()
        if cert['status']!='unknown' and first is None:first={**cert,'query_count':session.result()['query_count']}
        # Crucially before request creation, reservation or provider I/O.
        if spec['stop'] and cert['status']!='unknown':stop_reason=cert['status'];break
        if not session.remaining_ids:stop_reason='catalog_exhausted';break
        job=make_job(spec,session,index)
        immutable(api/'requests'/f'{job["job_id"]}.json',jb(job))
        path=api/'raw'/f'{job["expected_request_hash"]}.json'
        if invoke is None:
            raw=json.loads(path.read_text(encoding='utf-8'))
        else:
            try:raw=dispatch_once(job,api,lambda:invoke(job))
            except RuntimeError as exc:
                if str(exc)!='BUDGET_LIMIT':raise
                raw={'status':'budget_exhausted','request_hash':job['expected_request_hash'],
                    'tag':job['job_id'],'text':'','billing':'reserve rejected before provider I/O'}
                immutable(path,jb(raw))
            raw=json.loads(path.read_text(encoding='utf-8'))
        if raw['request_hash']!=job['expected_request_hash']:raise ValueError('RAW_REQUEST_MISMATCH')
        parsed=parse_selection_v11(raw,job['remaining_ids'],'next',1)
        cost,basis=request_cost(raw,job)
        row={'job_id':job['job_id'],'request_hash':job['expected_request_hash'],
            'raw_ref':f'results/phase11/api/raw/{job["expected_request_hash"]}.json',
            'parsed':parsed,'raw_status':raw.get('status'),'usage':raw.get('usage'),
            'cost_upper_usd':cost,'cost_basis':basis,'elapsed_seconds':raw.get('elapsed_seconds'),
            'before_queries':session.result()['query_count']}
        immutable(api/'decisions'/f'{job["job_id"]}.json',jb(row));decisions.append(row)
        if not parsed['protocol_valid']:
            valid=False;stop_reason='budget_exhausted' if raw.get('status')=='budget_exhausted' else 'protocol_failure';break
        session.consume(parsed['selected_ids'][0])
    cert=session.check()
    if first is None and cert['status']!='unknown':first={**cert,'query_count':session.result()['query_count']}
    result={**spec,**session.result(),'certificate':cert,'first_certificate':first,
        'stop_reason':stop_reason,'protocol_valid':valid,'decision_count':len(decisions),'decisions':decisions,
        'api_cost_upper_usd':sum(d['cost_upper_usd'] for d in decisions),
        'api_elapsed_seconds_sum':sum(d['elapsed_seconds'] or 0 for d in decisions)}
    immutable(api/'streams'/f'{spec["stream_id"]}.json',jb(result));return result

def initialize():
    source='results/phase10/api/budget.jsonl';old=(ROOT/source).read_bytes()
    path=ROOT/'results/phase11/api/budget.jsonl';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('BUDGET_PREFIX_CHANGED')
    else:path.write_bytes(old)
    inherited=BudgetV7Locked(ROOT/source,CAP).total_cost
    limit=min(CAP,inherited+CAMPAIGN_CAP)
    audit={'source':source,'prefix_sha256':sha(old),'prefix_bytes':len(old),'inherited_upper_usd':inherited,
        'cumulative_cap_usd':CAP,'campaign_additional_cap_usd':CAMPAIGN_CAP,'campaign_limit_usd':limit,
        'remaining_at_start_usd':CAP-inherited,'prices':UPPER_PRICES,'verified_date':'2026-10-17',
        'invoice':False,'source_urls':['https://developers.openai.com/api/docs/models/gpt-6-luna',
                                     'https://developers.openai.com/api/docs/models/gpt-4.1-mini']}
    immutable(ROOT/'results/phase11/provenance/budget_inheritance.json',jb(audit))
    return BudgetV7Locked(path,limit),audit

def prepare():
    verify_freeze();cs=read_rows(ROOT/'data/phase11/heldout.jsonl')+read_rows(ROOT/'data/phase11/challenge.jsonl')
    specs=build_specs(cs)
    validate_specs(specs)
    budget,audit=initialize()
    manifest={'streams':len(specs),'max_requests':len(specs)*MAX_QUERIES,'max_queries':MAX_QUERIES,
        'models':MODELS,'cells':CELLS,'max_output':1024,'workers':4,'automatic_retries':0,
        'budget':audit,'stream_sha256':sha(rb(specs)),'replicates':'disjoint deterministic IDs, no cross-stream reuse',
        'token_control':'exact o200k_base graph/padding local counts; model mapping unknown for Luna',
        'registration':'local prospective freeze, not external preregistration',
        'scheduling':'fixed hash-sorted submission, concurrent completion-dependent requests; cap censoring retained',
        'data_freeze_sha256':sha((ROOT/'results/phase11/provenance/data_freeze.json').read_bytes())}
    immutable(ROOT/'results/phase11/acquisition/streams.jsonl',rb(specs))
    immutable(ROOT/'results/phase11/acquisition/manifest.json',jb(manifest))
    return cs,specs,budget,audit

def finalize(specs,budget,audit):
    rows=[json.loads((ROOT/f'results/phase11/api/streams/{s["stream_id"]}.json').read_text(encoding='utf-8')) for s in specs]
    rows.sort(key=lambda r:r['stream_id']);decisions=[d for r in rows for d in r['decisions']]
    if len({d['request_hash'] for d in decisions})!=len(decisions):raise ValueError('UNINTENDED_REQUEST_REUSE')
    immutable(ROOT/'results/phase11/api/observations.jsonl',rb(rows))
    summary=summarize_streams(rows,budget,audit)
    immutable(ROOT/'results/phase11/api/summary.json',jb(summary));return summary

def summarize_streams(rows,budget,audit):
    decisions=[d for r in rows for d in r['decisions']]
    return {'streams':len(rows),'valid_streams':sum(r['protocol_valid'] for r in rows),
        'decision_attempts':len(decisions),'valid_decisions':sum(d['parsed']['protocol_valid'] for d in decisions),
        'provider_or_uncertain_requests':sum(d['raw_status']!='budget_exhausted' for d in decisions),
        'confirmed_provider_responses':sum(d['raw_status'] in ('completed','incomplete','api_error','failed') for d in decisions),
        'uncertain_transport_or_interrupt':sum(d['raw_status'] in ('transport_error','interrupted_unknown','invalid_response') for d in decisions),
        'budget_rejections_before_io':sum(d['raw_status']=='budget_exhausted' for d in decisions),
        'statuses':dict(Counter(d['raw_status'] for d in decisions)),
        'certificate_statuses':dict(Counter(r['certificate']['status'] for r in rows)),
        'cumulative_upper_usd':budget.total_cost,'increment_upper_usd':budget.total_cost-audit['inherited_upper_usd'],
        'remaining_usd':CAP-budget.total_cost,'campaign_limit_usd':budget.limit,'cap_usd':CAP}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--replay',action='store_true')
    p.add_argument('--env-file',type=Path);a=p.parse_args();cs,specs,budget,audit=prepare();lookup={c['case_id']:c for c in cs}
    if a.execute:
        if not a.env_file or not a.env_file.is_file():raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        client=ClientV3(load_key(a.env_file),ROOT/'results/phase11/api/raw',budget)
        def invoke(j):return client.call(j['model'],j['system'],j['prompt'],tag=j['job_id'],
            max_output=j['max_output'],replicate=j['replicate'],response_schema=j['schema'])
    else:invoke=None
    if a.execute or a.replay:
        with ThreadPoolExecutor(max_workers=4 if a.execute else 1) as pool:
            futures=[pool.submit(acquire_stream,s,lookup[s['case_id']],ROOT/'results/phase11/api',invoke) for s in specs]
            for i,f in enumerate(as_completed(futures),1):
                f.result()
                if i%12==0:print(json.dumps({'streams_completed':i,'planned':len(specs),'upper_usd':budget.total_cost}),flush=True)
        print(json.dumps(finalize(specs,budget,audit)),flush=True)
    else:print(json.dumps({'prepared_streams':len(specs),'budget':audit}),flush=True)

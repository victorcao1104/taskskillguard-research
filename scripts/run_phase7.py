"""Matched fresh acquisition, single inherited ledger, durable no-retry intents."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from phase7_common import ROOT, sha, jb, rb, immutable, read_rows, cases, verify_freeze
sys.path.insert(0, str(ROOT/'src'))
from tsg.budget_v4 import BudgetV4, UPPER_PRICES
from tsg.budget_v7 import BudgetV7
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from tsg.protocol_v7 import VIEWS, payload, system, schema, parse_record
from tsg.evidence_v7 import check
from run_phase5 import price_job, dispatch_once
CAP = 29.551575125
MODELS = ('gpt-6-luna', 'gpt-4.1-mini')

def initialize():
    source = 'results/phase6/challenge/api/budget.jsonl'
    old = (ROOT/source).read_bytes()
    path = ROOT/'results/phase7/api/budget.jsonl'; path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old): raise ValueError('BUDGET_PREFIX_MISMATCH')
    else: path.write_bytes(old)
    inherited = BudgetV4(ROOT/source, CAP).total_cost
    audit = {'source': source, 'prefix_bytes': len(old), 'prefix_sha256': sha(old),
             'inherited_upper_usd': inherited, 'cumulative_cap_usd': CAP,
             'remaining_at_start_usd': CAP-inherited, 'invoice': False}
    immutable(ROOT/'results/phase7/provenance/budget_inheritance.json', jb(audit))
    return BudgetV7(path, CAP), audit

def prepare():
    from tsg.runtime_v6 import parse_source, candidates
    verify_freeze(); cs = cases()
    assert len(cs) == 72 and len({c['family'] for c in cs if c['split']=='heldout'}) == 12
    held = [c for c in cs if c['split']=='heldout']
    families = sorted({c['family'] for c in held}, key=lambda f: sha(('repeat7:'+f).encode()))[:6]
    repeated = {sorted(c['case_id'] for c in held if c['family']==f)[0] for f in families}
    budget, audit = initialize(); jobs = []
    for c in cs:
        nodes = candidates(parse_source(c['source'])); ids = [n['id'] for n in nodes]
        assert ids
        text = payload(c,nodes)
        for view in VIEWS:
            for model in MODELS:
                for rep in ([0,1,2] if c['case_id'] in repeated and view in ('B1','B2') else [0]):
                    jobs.append(price_job({'job_id': f'{c["case_id"]}-{view}-{model}-r{rep}',
                        **{k:c[k] for k in ('case_id','family','split')}, 'view':view, 'model':model,
                        'replicate':rep, 'system':system(view), 'prompt':text, 'schema':schema(ids,view),
                        'ids':ids, 'max_output':4000}))
    jobs.sort(key=lambda j: sha(j['job_id'].encode()))
    upper = sum(j['reservation_upper_usd'] for j in jobs)
    if upper > min(5,audit['remaining_at_start_usd']): raise ValueError('CAMPAIGN_BUDGET_EXCEEDED')
    manifest = {'planned':len(jobs),'main':sum(j['replicate']==0 for j in jobs),
                'repeats':sum(j['replicate']>0 for j in jobs),'repeat_ids':sorted(repeated),
                'reservation_upper_usd':upper,'jobs_sha256':sha(rb(jobs)),
                'distinct_request_hashes':len({j['expected_request_hash'] for j in jobs}),
                'budget':audit,'max_workers':4,'automatic_retries':0,
                'freeze_sha256':sha((ROOT/'results/phase7/provenance/freeze.json').read_bytes())}
    immutable(ROOT/'results/phase7/acquisition/jobs.jsonl',rb(jobs))
    immutable(ROOT/'results/phase7/acquisition/manifest.json',jb(manifest))
    return jobs,manifest,budget

def execute(jobs,budget,env_file):
    api = ROOT/'results/phase7/api'; cs = {c['case_id']:c for c in cases()}
    client = ClientV3(load_key(env_file),api/'raw',budget)
    def one(j):
        path=api/'jobs'/f'{j["job_id"]}.json'
        if path.exists():
            saved=json.loads(path.read_text(encoding='utf-8'))
            if saved['request_hash']!=j['expected_request_hash']: raise ValueError('SAVED_HASH_MISMATCH')
            return saved
        raw=dispatch_once(j,api,lambda:client.call(j['model'],j['system'],j['prompt'],tag=j['job_id'],
            max_output=j['max_output'],replicate=j['replicate'],response_schema=j['schema']))
        row={k:j[k] for k in ('job_id','case_id','family','split','view','model','replicate')}
        row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase7/api/raw/{raw["request_hash"]}.json',
                   raw_status=raw.get('status'),usage=raw.get('usage'),parsed=parse_record(raw,j['ids'],j['view']))
        usage=raw.get('usage')
        if isinstance(usage,dict) and all(type(usage.get(k)) is int for k in ('input_tokens','output_tokens')):
            ip,op=UPPER_PRICES[j['model']]
            row['usage_cost_upper_usd']=(usage['input_tokens']*ip+usage['output_tokens']*op)/1e6
        if j['view']=='B2': row['certificate']=check(cs[j['case_id']],row['parsed'].get('prediction'))
        immutable(path,jb(row)); return row
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one,j) for j in jobs]):
            rows.append(future.result())
            if len(rows)%12==0: print(json.dumps({'completed':len(rows),'planned':len(jobs),'cumulative_upper':budget.total_cost}),flush=True)
    rows.sort(key=lambda r:r['job_id']); immutable(api/'observations.jsonl',rb(rows))
    summary={'planned':len(jobs),'completed':len(rows),'valid':sum(r['parsed']['protocol_valid'] for r in rows),
             'statuses':dict(Counter(r['raw_status'] for r in rows)), 'cumulative_upper_usd':budget.total_cost,
             'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP}
    immutable(api/'summary.json',jb(summary)); print(json.dumps(summary),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--env-file',type=Path);a=p.parse_args()
    jobs,manifest,budget=prepare();print(json.dumps(manifest),flush=True)
    if a.execute:
        if not a.env_file or not a.env_file.is_file(): raise ValueError('AUTHORIZED_CONFIG_REQUIRED')
        execute(jobs,budget,a.env_file)

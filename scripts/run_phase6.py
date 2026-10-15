"""Freeze finite source study then execute a single budgeted no-retry campaign."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys
from phase6_common import ROOT,sha,jb,rb,immutable,read_rows,cases
sys.path.insert(0,str(ROOT/'src'))
from tsg.budget_v4 import BudgetV4
from tsg.models import load_key
from tsg.models_v3 import ClientV3
from tsg.protocol_v6 import SYSTEM,VIEWS,payloads,schema,parse_record
from run_phase5 import price_job,dispatch_once
CAP=29.551575125
MODELS=('gpt-6-luna','gpt-4.1-mini')


def freeze():
    paths=['docs/phase6_design.md','docs/superpowers/plans/2026-10-16-phase6-synthetic.md',
           'src/tsg/runtime_v6.py','src/tsg/truth_v6.py','src/tsg/protocol_v6.py',
           'scripts/run_phase6.py','scripts/experiment_phase6.py','scripts/phase6_common.py',
           'scripts/analyze_phase6.py','src/tsg/analysis_v6.py',
           'scripts/build_phase6_dev.py','scripts/build_phase6_heldout.py',
           'data/phase6/dev.jsonl','data/phase6/heldout.jsonl']
    obj={'registration':'prospective-v6','baseline':'efd19d5e8704bdaec24fd183b81026d1d7fffccd',
         'source_sha256':{p:sha((ROOT/p).read_bytes()) for p in paths},
         'heldout_access':'runtime/truth authors did not read heldout; parent first semantic evaluation follows this freeze',
         'not_preregistered_external':'local chronological freeze; no claim of external preregistration'}
    immutable(ROOT/'results/phase6/provenance/freeze.json',jb(obj))
    return obj


def initialize():
    old=(ROOT/'results/phase5/api/budget.jsonl').read_bytes()
    path=ROOT/'results/phase6/api/budget.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:path.write_bytes(old)
    inherited=BudgetV4(ROOT/'results/phase5/api/budget.jsonl',CAP).total_cost
    audit={'prefix_bytes':len(old),'prefix_sha256':sha(old),'source':'results/phase5/api/budget.jsonl',
           'inherited_upper_usd':inherited,'cumulative_cap_usd':CAP,'remaining_at_start_usd':CAP-inherited,
           'invoice':False}
    immutable(ROOT/'results/phase6/provenance/budget_inheritance.json',jb(audit))
    return BudgetV4(path,CAP),audit


def prepare():
    from tsg.runtime_v6 import parse_source,candidates,edges
    freeze_path=ROOT/'results/phase6/provenance/freeze.json'
    frozen=json.loads(freeze_path.read_text())
    for p,h in frozen['source_sha256'].items():
        if sha((ROOT/p).read_bytes())!=h:raise ValueError('FROZEN_SOURCE_CHANGED:'+p)
    cs=cases()
    assert len(cs)==36 and len({c['family'] for c in cs})==18
    repeated=sorted([c for c in cs if c['split']=='heldout'],key=lambda c:sha(('repeat6:'+c['case_id']).encode()))[:6]
    repeat_ids={c['case_id'] for c in repeated}
    budget,audit=initialize();jobs=[];controls=[]
    for c in cs:
        ast=parse_source(c['source']);ns=candidates(ast);es=edges(ast)
        texts=payloads(c,ns,es);ids=[n['id'] for n in ns]
        if not ids:raise ValueError('EMPTY_FIXTURE_CANDIDATES')
        import tiktoken
        enc=tiktoken.get_encoding('o200k_base')
        controls.append({'case_id':c['case_id'],'candidates':ns,'edges':es,
                         'local_tokens':{v:len(enc.encode(p)) for v,p in texts.items()},
                         'graph_equals_shuffled':texts['graph']==texts['shuffled']})
        for v,p in texts.items():
            for model in MODELS:
                for rep in ([0,1,2] if c['case_id'] in repeat_ids and v in ('table','graph') else [0]):
                    jobs.append(price_job({'job_id':f'{c["case_id"]}-{v}-{model}-r{rep}',
                        'case_id':c['case_id'],'family':c['family'],'split':c['split'],'view':v,
                        'model':model,'replicate':rep,'system':SYSTEM,'prompt':p,'schema':schema(ids),
                        'ids':ids,'max_output':3000}))
    jobs.sort(key=lambda j:sha(j['job_id'].encode()))
    upper=sum(j['reservation_upper_usd'] for j in jobs)
    if upper>min(5,audit['remaining_at_start_usd']):raise ValueError('PROSPECTIVE_CAMPAIGN_BUDGET_EXCEEDED')
    manifest={'planned':len(jobs),'main':sum(j['replicate']==0 for j in jobs),'repeats':sum(j['replicate']>0 for j in jobs),
              'families':18,'cases':36,'models':MODELS,'views':VIEWS,'repeat_ids':sorted(repeat_ids),
              'reservation_upper_usd':upper,'jobs_sha256':sha(rb(jobs)),'budget':audit,
              'max_workers':4,'automatic_retries':0,'freeze_sha256':sha(freeze_path.read_bytes())}
    for n,data in [('jobs.jsonl',rb(jobs)),('manifest.json',jb(manifest)),('controls.jsonl',rb(controls))]:
        immutable(ROOT/'results/phase6/acquisition'/n,data)
    return jobs,manifest,budget


def execute(jobs,budget,env_file):
    api=ROOT/'results/phase6/api'
    client=ClientV3(load_key(env_file),api/'raw',budget)
    def one(j):
        path=api/'jobs'/f'{j["job_id"]}.json'
        if path.exists():
            row=json.loads(path.read_text(encoding='utf-8'))
            if row['request_hash']!=j['expected_request_hash']:raise ValueError('SAVED_REQUEST_MISMATCH')
            return row
        raw=dispatch_once(j,api,lambda:client.call(j['model'],j['system'],j['prompt'],tag=j['job_id'],
                          max_output=j['max_output'],replicate=j['replicate'],response_schema=j['schema']))
        row={k:j[k] for k in ('job_id','case_id','family','split','view','model','replicate')}
        row.update(request_hash=raw['request_hash'],raw_ref=f'results/phase6/api/raw/{raw["request_hash"]}.json',
                   raw_status=raw.get('status'),usage=raw.get('usage'),parsed=parse_record(raw,j['ids']))
        immutable(path,jb(row));return row
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for f in as_completed([pool.submit(one,j) for j in jobs]):
            rows.append(f.result())
            if len(rows)%12==0:print(json.dumps({'completed':len(rows),'planned':len(jobs),'cumulative_upper':budget.total_cost}),flush=True)
    rows.sort(key=lambda r:r['job_id']);immutable(api/'observations.jsonl',rb(rows))
    summary={'planned':len(jobs),'completed':len(rows),'valid':sum(r['parsed']['protocol_valid'] for r in rows),
             'statuses':dict(Counter(r['raw_status'] for r in rows)),'cumulative_upper_usd':budget.total_cost,
             'remaining_usd':CAP-budget.total_cost,'cap_usd':CAP}
    immutable(api/'summary.json',jb(summary));print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--env-file',type=Path);a=p.parse_args()
    if a.freeze:print(json.dumps({'frozen_files':len(freeze()['source_sha256'])}))
    else:
        jobs,manifest,budget=prepare()
        print(json.dumps({k:manifest[k] for k in ('planned','main','repeats','reservation_upper_usd')}),flush=True)
        if a.execute:
            if not a.env_file or not a.env_file.is_file():raise ValueError('EXISTING_AUTHORIZED_CONFIG_REQUIRED')
            execute(jobs,budget,a.env_file)

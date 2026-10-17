"""Inherited ledger and durable no-duplicate dispatch; authorized models only."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from tsg.budget_v4 import BudgetV4
from tsg.models import load_key
from tsg.models_v3 import ClientV3,validate_record
from run_phase5 import price_job,dispatch_once
from .protocol import SCHEMA,SYSTEM,SYSTEM_MAIN,MODELS,parse
CAP=42.781273975000005
INPUT_CAP=14000
OUTPUT_CAP=2000

def immutable(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('IMMUTABLE_MISMATCH:'+str(path))
    else:path.write_bytes(data)

def initialize_budget(old,new,cap=CAP):
    old=Path(old);new=Path(new);data=old.read_bytes()
    latest={r['reservation_id']:r for r in map(json.loads,data.decode().splitlines())}
    inherited=sum(r.get('cost_usd',r['reserved_usd']) for r in latest.values())
    new.parent.mkdir(parents=True,exist_ok=True)
    if new.exists():
        if not new.read_bytes().startswith(data):raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:new.write_bytes(data)
    audit={'source':str(old.relative_to(ROOT)) if old.is_relative_to(ROOT) else old.name,
           'prefix_bytes':len(data),'prefix_sha256':hashlib.sha256(data).hexdigest(),
           'inherited_upper_usd':inherited,'available_at_start_usd':cap-inherited,'cumulative_cap_usd':cap,
           'new_allowance_usd':0,'invoice':False}
    return BudgetV4(new,cap),audit

def request_job(model,prompt,*,method,case_id,replicate,iteration,campaign):
    if model not in MODELS:raise ValueError('UNAUTHORIZED_MODEL')
    name=f'{campaign}--{case_id}--{method}--{model}--r{replicate}--i{iteration}'
    nonce=int(hashlib.sha256(name.encode()).hexdigest()[:12],16)
    j=price_job({'job_id':name,'model':model,'system':SYSTEM if campaign=='development' else SYSTEM_MAIN,'prompt':prompt,'schema':SCHEMA,'max_output':OUTPUT_CAP,'replicate':nonce})
    if j['input_byte_bound']>INPUT_CAP:raise ValueError('INPUT_BYTE_CAP')
    return j

def decode(raw):
    v=validate_record(raw,SCHEMA);normalization=None
    if v['diagnostic_codes']==['MULTIPLE_OUTPUT_TEXT']:
        texts=[p['text'] for item in raw['response']['output'] if item.get('type')=='message' and item.get('status') in (None,'completed') for p in item.get('content',[]) if p.get('type')=='output_text']
        v=validate_record({'status':'completed','text':texts[-1]},SCHEMA);normalization='last_completed_output_text'
    return {'parsed':parse(v['prediction']) if v['protocol_valid'] else {'status':'invalid','diagnostic':v['diagnostic_codes']},
            'normalization':normalization,'raw_status':raw.get('status'),'request_hash':raw.get('request_hash'),
            'elapsed_seconds':raw.get('elapsed_seconds',0),'usage':raw.get('usage'), 'raw_diagnostics':validate_record(raw,SCHEMA)['diagnostic_codes']}

class Provider:
    def __init__(self,study,*,live=False):
        self.study=Path(study);self.api=self.study/'api';self.live=live
        self.budget,audit=initialize_budget(ROOT/'studies/stateful-recovery-v13/api/budget.jsonl',self.api/'budget.jsonl')
        immutable(self.study/'provenance/budget_inheritance.json',audit)
        self.client=None
        if live:
            env=ROOT.parent/'Goal-Aware-Capability-Reconciliation-and-Targeted-Repair-for-LLM-Agent-Skills/.env.local'
            self.client=ClientV3(load_key(env),self.api/'raw',self.budget)
    def call(self,job):
        immutable(self.api/'requests'/f"{job['job_id']}.json",job)
        path=self.api/'raw'/f"{job['expected_request_hash']}.json"
        if not self.live and not path.exists():raise ValueError('REPLAY_CACHE_MISS')
        raw=dispatch_once(job,self.api,lambda:self.client.call(job['model'],job['system'],job['prompt'],tag=job['job_id'],max_output=job['max_output'],replicate=job['replicate'],response_schema=job['schema']))
        return decode(raw)

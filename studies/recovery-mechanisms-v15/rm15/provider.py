"""Durable inherited budget. No network unless --live was explicitly passed."""
import hashlib,json,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'studies/goal-recovery-v14'))
from gr14.provider import initialize_budget,immutable,CAP
from tsg.models import load_key
from tsg.models_v3 import ClientV3,validate_record
from run_phase5 import price_job,dispatch_once
from .protocol import MODELS,SCHEMA,SYSTEM,parse
INPUT_CAP=24000
OUTPUT_CAP=2000


def request_job(model,prompt,job_id):
    if model not in MODELS:raise ValueError('UNAUTHORIZED_MODEL')
    nonce=int(hashlib.sha256(job_id.encode()).hexdigest()[:12],16)
    job=price_job({'job_id':job_id,'model':model,'system':SYSTEM,'prompt':prompt,'schema':SCHEMA,'max_output':OUTPUT_CAP,'replicate':nonce})
    if job['input_byte_bound']>INPUT_CAP:raise ValueError('INPUT_BYTE_CAP:'+str(job['input_byte_bound']))
    return job


def decode(raw):
    original=validate_record(raw,SCHEMA);v=original;normalization=None
    if v['diagnostic_codes']==['MULTIPLE_OUTPUT_TEXT']:
        texts=[p['text'] for item in raw['response']['output'] if item.get('type')=='message' and item.get('status') in (None,'completed') for p in item.get('content',[]) if p.get('type')=='output_text']
        v=validate_record({'status':'completed','text':texts[-1]},SCHEMA);normalization='last_completed_output_text'
    return {'parsed':parse(v['prediction']) if v['protocol_valid'] else {'status':'invalid','diagnostic':v['diagnostic_codes']},
            'normalization':normalization,'raw_status':raw.get('status'),'request_hash':raw.get('request_hash'),
            'elapsed_seconds':raw.get('elapsed_seconds',0),'usage':raw.get('usage'),'raw_diagnostics':original['diagnostic_codes']}


class Provider:
    def __init__(self,study,live=False):
        self.study=Path(study);self.api=self.study/'api';self.live=live
        self.budget,audit=initialize_budget(ROOT/'studies/goal-recovery-v14/api/budget.jsonl',self.api/'budget.jsonl')
        immutable(self.study/'provenance/budget_inheritance.json',audit)
        self.client=None
        if live:
            env=ROOT.parent/'Goal-Aware-Capability-Reconciliation-and-Targeted-Repair-for-LLM-Agent-Skills/.env.local'
            self.client=ClientV3(load_key(env),self.api/'raw',self.budget)
    @property
    def exposure(self):
        # Reservations/settlements mutate entries concurrently; monitoring must lock too.
        with self.budget.lock:return self.budget.total_cost
    def call(self,job):
        immutable(self.api/'requests'/f"{job['job_id']}.json",job)
        path=self.api/'raw'/f"{job['expected_request_hash']}.json"
        if not self.live and not path.exists():raise ValueError('REPLAY_CACHE_MISS')
        raw=dispatch_once(job,self.api,lambda:self.client.call(job['model'],job['system'],job['prompt'],tag=job['job_id'],max_output=job['max_output'],replicate=job['replicate'],response_schema=job['schema']))
        return decode(raw)

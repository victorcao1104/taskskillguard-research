"""Reuse the audited response client; append-only inherited budget and unique requests."""
from pathlib import Path
import hashlib,json,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from tsg.models import load_key,make_request
from tsg.models_v3 import ClientV3,validate_record
from tsg.budget_v4 import BudgetV4
from run_phase5 import dispatch_once,price_job
from .protocol import SYSTEM,SCHEMA,parse

MODELS=('gpt-6-luna','gpt-4.1-mini')
MAX_OUTPUT=1600
MAX_INPUT_BYTES=18000


def campaign_budget(old_path,new_path):
    old=Path(old_path).read_bytes();path=Path(new_path);path.parent.mkdir(parents=True,exist_ok=True)
    entries={r['reservation_id']:r for r in map(json.loads,old.decode().splitlines())}
    inherited=sum(r.get('cost_usd',r['reserved_usd']) for r in entries.values())
    if path.exists():
        if not path.read_bytes().startswith(old):raise ValueError('BUDGET_PREFIX_MISMATCH')
    else:path.write_bytes(old)
    audit={'inherited_upper_usd':inherited,'new_cap_usd':20,'cumulative_cap_usd':inherited+20,
           'inherited_sha256':hashlib.sha256(old).hexdigest(),'inherited_bytes':len(old),
           'authorization_date':'2026-10-18','invoice':False,
           'prices_usd_per_million':{'gpt-6-luna':{'input_upper':.125,'output':.5},'gpt-4.1-mini':{'input_upper':.4,'output':1.6}},
           'pricing_checked':'2026-10-18','price_sources':['https://developers.openai.com/api/docs/models/gpt-6-luna','https://developers.openai.com/api/docs/models/gpt-4.1-mini']}
    return BudgetV4(path,inherited+20),audit


def request_job(model,prompt,*,method,case_id,replicate,iteration,campaign='main'):
    if model not in MODELS:raise ValueError('UNAUTHORIZED_MODEL')
    identity=f'{campaign}:{case_id}:{method}:{model}:r{replicate}:i{iteration}'
    nonce=int(hashlib.sha256(identity.encode()).hexdigest()[:12],16)
    job=price_job({'job_id':hashlib.sha256(identity.encode()).hexdigest(),'identity':identity,
                   'model':model,'system':SYSTEM,'prompt':prompt,'schema':SCHEMA,
                   'max_output':MAX_OUTPUT,'replicate':nonce})
    if job['input_byte_bound']>MAX_INPUT_BYTES:raise ValueError('INPUT_BYTE_CAP')
    return job


class Provider:
    def __init__(self,api_dir,budget,key=None):
        self.api=Path(api_dir);self.budget=budget
        self.client=ClientV3(key,self.api/'raw',budget) if key else None

    def propose(self,model,prompt,*,method,case_id,replicate,iteration,campaign='main'):
        try:job=request_job(model,prompt,method=method,case_id=case_id,replicate=replicate,iteration=iteration,campaign=campaign)
        except ValueError as exc:return {'status':'invalid','program':None,'reason':str(exc)}
        request_path=self.api/'requests'/f"{job['job_id']}.json";request_path.parent.mkdir(parents=True,exist_ok=True)
        content=json.dumps(job,ensure_ascii=False,sort_keys=True,indent=2).encode()
        if request_path.exists() and request_path.read_bytes()!=content:raise ValueError('REQUEST_CHANGED')
        if not request_path.exists():request_path.write_bytes(content)
        if self.client is None:
            raw_path=self.api/'raw'/f"{job['expected_request_hash']}.json"
            if not raw_path.exists():raise ValueError('MISSING_CACHED_RESPONSE')
            raw=json.loads(raw_path.read_text(encoding='utf-8'))
        else:
            raw=dispatch_once(job,self.api,lambda:self.client.call(model,SYSTEM,prompt,tag=job['identity'],
                max_output=MAX_OUTPUT,replicate=job['replicate'],response_schema=SCHEMA))
        validated=validate_record(raw,SCHEMA)
        answer=parse(validated.get('prediction')) if validated['protocol_valid'] else {
            'status':'invalid','program':None,'reason':'PROVIDER_OR_PROTOCOL:'+','.join(validated['diagnostic_codes'])}
        answer['request']={'hash':job['expected_request_hash'],'status':raw.get('status'),
                           'usage':raw.get('usage'),'elapsed_seconds':raw.get('elapsed_seconds'),
                           'reservation_upper_usd':job['reservation_upper_usd'],'identity':job['identity']}
        return answer

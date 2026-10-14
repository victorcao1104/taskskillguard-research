"""Tool-free OpenAI responses with persisted budget and raw-response evidence."""
from __future__ import annotations
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Standard, short-context USD per million tokens, official docs checked 2026-10-15.
PRICES={'gpt-6-luna':(0.10,0.50),'gpt-4.1-mini':(0.40,1.60)}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Budget:
    """One-process concurrency-safe reservation ledger. Never run two writers."""
    def __init__(self,path:Path,limit_usd=20):
        self.path=Path(path);self.limit=limit_usd;self.lock=threading.RLock()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.entries={}
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                row=json.loads(line);self.entries[row['reservation_id']]=row

    @property
    def total_cost(self):
        return sum(r.get('cost_usd',r['reserved_usd']) for r in self.entries.values())

    def _write(self,row):
        with self.path.open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
        self.entries[row['reservation_id']]=row

    def reserve(self,model,input_token_upper,output_max):
        with self.lock:
            ip,op=PRICES[model]
            amount=(input_token_upper*ip+output_max*op)/1e6
            if self.total_cost+amount>self.limit:
                raise RuntimeError('BUDGET_LIMIT')
            rid=uuid.uuid4().hex
            self._write({'reservation_id':rid,'timestamp':utcnow(),'model':model,'status':'reserved','reserved_usd':amount})
            return rid

    def settle(self,rid,usage):
        with self.lock:
            old=self.entries[rid];ip,op=PRICES[old['model']]
            # Ignore caching discounts deliberately: conservative spend estimate.
            cost=(usage.get('input_tokens',0)*ip+usage.get('output_tokens',0)*op)/1e6
            self._write({**old,'status':'settled','usage':usage,'cost_usd':cost})


def make_request(model,system,prompt,max_output=2500):
    request={'model':model,'store':False,'max_output_tokens':max_output,
             'input':[{'role':'developer','content':system},{'role':'user','content':prompt}],
             'text':{'format':{'type':'json_object'}}}
    if model=='gpt-6-luna':
        request['reasoning']={'effort':'none'}
    else:
        request['temperature']=0
    return request


def parse_prediction(text,action_ids):
    obj=json.loads(text)
    if not isinstance(obj,dict) or not isinstance(obj.get('actions'),list):
        raise ValueError('INVALID_SCHEMA')
    ids=[]
    for a in obj['actions']:
        if not isinstance(a,dict) or a.get('authorized') not in {'yes','no','unknown'} or a.get('necessary') not in {'yes','no','unknown'} or not isinstance(a.get('reason'),str):
            raise ValueError('INVALID_ACTION')
        ids.append(a.get('action_id'))
    if len(ids)!=len(set(ids)) or set(ids)!=set(action_ids):
        raise ValueError('ACTION_COVERAGE_MISMATCH')
    return obj


def load_key(env_file=None):
    key=os.environ.get('OPENAI_API_KEY')
    if not key and env_file:
        for line in Path(env_file).read_text(encoding='utf-8').splitlines():
            if line.strip().startswith('OPENAI_API_KEY='):
                key=line.partition('=')[2].strip().strip('"').strip("'")
    if not key:
        raise RuntimeError('API_KEY_NOT_CONFIGURED')
    return key


class Client:
    def __init__(self,key,out:Path,budget:Budget):
        self.key=key;self.out=Path(out);self.budget=budget
        self.out.mkdir(parents=True,exist_ok=True)
        self.request_locks={}
        self.request_locks_guard=threading.Lock()

    def call(self,model,system,prompt,*,tag,max_output=2500,replicate=0):
        request=make_request(model,system,prompt,max_output)
        fingerprint=hashlib.sha256(json.dumps({'request':request,'replicate':replicate},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.request_locks_guard:
            lock=self.request_locks.setdefault(fingerprint,threading.Lock())
        with lock:
            return self._call_locked(model,request,fingerprint,tag,max_output,replicate)

    def _call_locked(self,model,request,fingerprint,tag,max_output,replicate):
        path=self.out/(fingerprint+'.json')
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        # UTF-8 bytes plus protocol headroom conservatively bounds BPE input.
        rid=self.budget.reserve(model,len(json.dumps(request,ensure_ascii=False).encode())+4096,max_output)
        started=time.perf_counter()
        record={'tag':tag,'request_hash':fingerprint,'replicate':replicate,'request':request,'timestamp_utc':utcnow(),'reservation_id':rid}
        req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(request).encode(),
              headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=120) as r:
                response=json.load(r)
            usage=response.get('usage',{})
            self.budget.settle(rid,usage)
            parts=[c.get('text','') for item in response.get('output',[]) for c in item.get('content',[]) if c.get('type')=='output_text']
            record.update(status=response.get('status','unknown'),text='\n'.join(parts),response=response,usage=usage)
        except urllib.error.HTTPError as exc:
            try:
                err=json.loads(exc.read()).get('error',{})
            except Exception:
                err={}
            record.update(status='api_error',http_status=exc.code,error_code=err.get('code'),error_type=err.get('type'))
            # Keep reservation as upper-bound cost for failures of unknown billing.
        except Exception as exc:
            record.update(status='transport_error',error_type=type(exc).__name__)
        record['elapsed_seconds']=time.perf_counter()-started
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(path)
        return record

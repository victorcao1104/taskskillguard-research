import importlib.util
import json
from pathlib import Path
import sys
import pytest
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import run_phase5 as run

def test_inherit_full_budget_bytes_and_prevent_prefix_reset(tmp_path):
    old=tmp_path/'results/phase4/api/budget.jsonl'; old.parent.mkdir(parents=True)
    raw=(json.dumps({'reservation_id':'unsettled','model':'gpt-6-luna','status':'reserved','reserved_usd':1.0})+'\n').encode()
    old.write_bytes(raw)
    budget,audit=run.initialize(tmp_path)
    assert budget.total_cost==1 and budget.limit==run.CAP
    assert budget.path.read_bytes()==raw
    assert audit['prefix_bytes']==len(raw)
    budget.path.write_text('{}\n',encoding='utf-8')
    with pytest.raises(ValueError,match='PREFIX'): run.initialize(tmp_path)

def test_request_bound_includes_schema_and_replicate_hash_changes():
    job={'model':'gpt-4.1-mini','system':'s','prompt':'x','schema':{'type':'object','properties':{}},'max_output':100,'replicate':0}
    a=run.price_job(job)
    b=run.price_job({**job,'schema':{'description':'界'*10000}})
    c=run.price_job({**job,'replicate':1})
    assert b['reservation_upper_usd']>a['reservation_upper_usd']
    assert c['expected_request_hash']!=a['expected_request_hash']
    assert c['reservation_upper_usd']==a['reservation_upper_usd']

def test_interrupted_dispatch_never_reissues(tmp_path):
    job={'job_id':'one','expected_request_hash':'a'*64}
    marker=tmp_path/'dispatch'/'one.json'; marker.parent.mkdir()
    marker.write_text(json.dumps({'job_id':'one','request_hash':'a'*64}),encoding='utf-8')
    calls=[]
    raw=run.dispatch_once(job,tmp_path,lambda:calls.append('must_not_call'))
    assert calls==[] and raw['status']=='interrupted_unknown'
    assert (tmp_path/'raw'/('a'*64+'.json')).is_file()

def test_dispatch_marks_before_call_and_recovers_saved_raw(tmp_path):
    job={'job_id':'one','expected_request_hash':'b'*64}
    def invoke():
        assert (tmp_path/'dispatch/one.json').is_file()
        return {'status':'completed','request_hash':'b'*64,'text':'{}'}
    raw=run.dispatch_once(job,tmp_path,invoke)
    assert raw['status']=='completed'
    assert run.dispatch_once(job,tmp_path,lambda:pytest.fail('reissued'))==raw

import json
from gr14.data import make_case,inputs_for
from gr14.protocol import payload,parse,SCHEMA
from gr14.provider import request_job,initialize_budget


def test_planner_does_not_receive_original_or_solution():
    c=make_case('dev_cover','forbidden');ins=inputs_for(c,'weak')[0]
    a=json.loads(payload(c,ins,'repair_raw',[],0));b=json.loads(payload(c,ins,'replan_raw',[],0))
    assert 'original_skill' in a and 'original_skill' not in b
    for p in (a,b):
        assert 'query' not in p['task'] and 'solution' not in p
        assert p['grammar']==a['grammar'] and p['state']==a['state']


def test_request_identities_and_cap():
    p='short prompt';a=request_job('gpt-6-luna',p,method='repair_raw',case_id='x',replicate=0,iteration=0,campaign='dev')
    b=request_job('gpt-6-luna',p,method='repair_raw',case_id='x',replicate=1,iteration=0,campaign='dev')
    assert a['expected_request_hash']!=b['expected_request_hash']
    assert a['reservation_upper_usd']<=.0025
    try:request_job('gpt-6-luna','x'*20000,method='x',case_id='x',replicate=0,iteration=0,campaign='dev')
    except ValueError as e:assert str(e)=='INPUT_BYTE_CAP'
    else:assert False


def test_no_new_allowance_is_created(tmp_path):
    old=tmp_path/'old.jsonl';old.write_text(json.dumps({'reservation_id':'old','model':'gpt-6-luna','status':'settled','reserved_usd':2,'cost_usd':1})+'\n')
    b,a=initialize_budget(old,tmp_path/'new.jsonl',3)
    assert b.limit==3 and a['available_at_start_usd']==2
    assert (tmp_path/'new.jsonl').read_bytes().startswith(old.read_bytes())


def test_schema_parses_plain_code_not_nested_json():
    obj={'status':'candidate','compute':'result=None','effects':'pass','reason':''}
    p=parse(obj);assert p['program']['compute']=='result=None'
    assert parse({'status':'candidate','compute':[],'effects':''})['status']=='invalid'


def test_feedback_does_not_reveal_hidden_world():
    c=make_case('dev_cover','unknown_query');ins=inputs_for(c,'weak')[0]
    p=json.loads(payload(c,ins,'repair_raw',[{'program':{'compute':'pass','effects':'pass'},'feedback':{'code':'X','world':{'secret':'A','committed':False},'input':ins}}],1))
    assert 'world' not in p['last_attempt']['feedback']
    assert 'committed' not in p['state']

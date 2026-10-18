import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rm15.runtime import execute, base_world, make_task

def fixture():
    task=make_task('test', {'x': 1}, oracle_fn=lambda t,d: {'main': d['x']})
    return task, base_world({'x': 1})

def test_no_host_execution_and_grant_enforcement():
    t,w=fixture()
    assert execute("import os",w,t)['stop']['code']=='UNSUPPORTED_STATEMENT'
    r=execute("x=read('/private/token')",w,t)
    assert r['stop']['code']=='PRIVILEGE'
    assert not r['world']['events']

def test_effect_idempotence_and_lost_ack():
    t,w=fixture(); w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    r=execute("send('report','team',{'main':1})",w,t)
    assert r['stop']['code']=='UNCERTAIN_EFFECT'
    assert r['world']['receipts']['report']=='unknown'
    r2=execute("send('report','team',{'main':1})",r['world'],t)
    assert r2['stop']['code']=='DUPLICATE_EFFECT'
    assert len(r2['world']['messages'])==1

def test_no_secret_read_through_support_or_mapping_helpers():
    t,w=fixture(); t['grants']['read'].append('/private/token')
    r=execute("x=read('/private/token')\nr=putmap({},'main',x)\nwrite('/output/main',r)",w,t)
    assert r['stop']['code']=='DISCLOSURE'

def test_generic_helpers_and_goal_check():
    t,w=fixture()
    r=execute("x=putmap({},'main',get(read('/input/data'),'x',0))\nok=valid(x)",w,t)
    assert r['stop'] is None
    assert r['world']['env']['ok']['value'] is True

def test_goal_checker_rejects_bool_in_place_of_integer():
    t,w=fixture()
    r=execute("ok=valid({'main':True})",w,t)
    assert r['world']['env']['ok']['value'] is False

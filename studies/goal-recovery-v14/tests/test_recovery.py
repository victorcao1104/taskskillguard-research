from gr14.runtime import new_world,execute
from gr14.recovery import run_program, transform_compute


def task():
    return {'goal':{'min_count':1,'max_count':1,'sum_bounds':{'quality':{'min':5}}},'grants':{'read':['/input/options','/output/selection'],'write':['/output/selection'],'send':['team'],'delete':['/tmp/cache'],'status':['report']},'max_calls':40,'max_steps':20000,'max_checks':768}


PROGRAM={'compute':"rows=read('/input/options')\nresult=None\nfor row in rows:\n    candidate=[row['id']]\n    if valid(candidate):\n        result=candidate\n        break",'effects':"write('/output/selection',result)\nsend('report','team',result)\ndelete('/tmp/cache')"}


def test_certificate_rechecked_on_new_input_and_ignores_forgery():
    w=new_world([{'id':'a','quality':1},{'id':'b','quality':8}]);w['env']={'cached':{'value':['a'],'labels':[]},'certificate':{'value':{'valid':True},'labels':[]}}
    r=run_program(PROGRAM,w,task(),state=True)
    assert r['stop'] is None and r['world']['files']['/output/selection']==['b']
    assert r['reused'] is None
    w['files']['/input/options'][0]['quality']=9
    q=run_program(PROGRAM,w,task(),state=True)
    assert q['reused']=='cached' and q['world']['files']['/output/selection']==['a']
    assert q['certificates'][0]['input_hash']!=r['input_hash']


def test_state_module_preserves_completed_write_and_send():
    w=new_world([{'id':'a','quality':9}]);p=execute("result=['a']\nwrite('/output/selection',result)\nsend('report','team',result)",w,task())
    r=run_program(PROGRAM,p['world'],task(),state=True)
    assert r['stop'] is None and len(r['world']['messages'])==1
    assert len([e for e in r['world']['trace'] if e.get('op')=='write' and e.get('status')=='success'])==1
    assert '/tmp/cache' not in r['world']['files']


def test_unknown_without_query_stops_and_does_not_expand_grants():
    t=task();t['grants']['status']=[];w=new_world([{'id':'a','quality':9}]);w['receipts']['report']='unknown'
    r=run_program(PROGRAM,w,t,state=True)
    assert r['stop']['code']=='UNRESOLVED_EFFECT'
    assert not r['world']['messages'] and not t['grants']['status']


def test_dependency_cut_has_to_pass_goal_validation():
    source="gate=read('/private/token')\nif gate=='A':\n    result=['a']"
    code=transform_compute(source,task())['code']
    assert 'private' not in code and 'gate' not in code
    r=run_program({'compute':code,'effects':''},new_world([{'id':'a','quality':1}]),task(),state=True)
    assert r['stop']['code']=='GOAL_MISMATCH'

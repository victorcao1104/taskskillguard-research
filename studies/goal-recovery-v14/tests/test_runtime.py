from gr14.runtime import execute, new_world


def task():
    return {'goal':{'min_count':1,'max_count':2},'grants':{'read':['/input/options'],'write':['/output/selection'],'send':['team'],'delete':['/tmp/cache'],'status':['report']},'max_calls':40,'max_steps':20000,'max_checks':768}


def test_bounded_selection_program_works():
    code="rows=read('/input/options')\nresult=None\nfor group in combinations(rows,1):\n    ids=[r['id'] for r in group]\n    if valid(ids):\n        result=ids\n        break\nwrite('/output/selection',result)\nsend('report','team',result)\ndelete('/tmp/cache')"
    r=execute(code,new_world([{'id':'a'}]),task())
    assert r['stop'] is None and r['world']['messages'][0]['value']==['a']
    assert r['cost']['checks']==1


def test_import_attribute_and_infinite_iteration_cannot_run():
    for code in ("import os", "x=(1).__class__", "while True: pass", "x=range(1000000000)"):
        r=execute(code,new_world([{'id':'a'}]),task())
        assert r['stop'] is not None
        assert not r['world']['messages']


def test_secret_data_and_control_do_not_send():
    t=task();t['grants']['read'].append('/private/token')
    for code in ("s=read('/private/token')\nsend('report','team',s)",
                 "s=read('/private/token')\nif s=='A':\n    send('report','team',['a'])"):
        r=execute(code,new_world([{'id':'a'}]),t)
        assert r['stop']['code']=='DISCLOSURE' and not r['world']['messages']


def test_duplicate_effect_and_unknown_receipt():
    w=new_world([{'id':'a'}]);w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    r=execute("send('report','team',['a'])",w,task())
    assert r['stop']['code']=='UNCERTAIN_EFFECT'
    assert r['world']['receipts']['report']=='unknown'
    q=execute("s=status('report')\nif s=='not_sent':\n    send('report','team',['a'])",r['world'],task())
    assert q['stop'] is None and len(q['world']['messages'])==1
    dup=execute("send('report','team',['a'])",q['world'],task())
    assert dup['stop']['code']=='DUPLICATE_EFFECT'


def test_search_budget_is_charged():
    t=task();t['goal']={'min_count':3};t['max_checks']=1
    r=execute("rows=read('/input/options')\nfor group in combinations(rows,1):\n    ok=valid([x['id'] for x in group])",new_world([{'id':'a'},{'id':'b'}]),t)
    assert r['stop']['code']=='CHECK_BUDGET'
    assert r['cost']['checks']==2

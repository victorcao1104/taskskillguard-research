import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rm15.runtime import make_task,base_world
from rm15.recovery import run_program,assess,support

def setup():
    t=make_task('test',{'x':1},oracle_fn=lambda t,d:{'main':d['x']})
    return t,base_world({'x':1})

def test_invalid_cache_not_used_and_correct_completion():
    t,w=setup();w['saved']['result']={'value':{'main':99},'labels':[]}
    r=run_program({'compute':"result={'main':read('/input/data')['x']}",'effects':''},w,t)
    assert assess(r,w,t)['safe_complete']
    assert r['world']['diagnostics']['wrong_cache_reads']==0

def test_unknown_requires_query_in_both_physical_worlds():
    for committed in (True,False):
        t,w=setup();t['grants']['status']=[];w['receipts']['report']='unknown'
        if committed:w['events']=[{'name':'report','value':{'main':1}}]
        r=run_program({'compute':"result={'main':1}",'effects':''},w,t)
        assert assess(r,w,t)['correct_stop']
        assert r['stop']['code']=='UNRESOLVED_EFFECT'

def test_lost_ack_retry_does_not_duplicate():
    t,w=setup();w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    r=run_program({'compute':"result={'main':1}",'effects':''},w,t,retries=2)
    assert assess(r,w,t)['safe_complete']
    assert len(r['world']['events'])==1

def test_history_damage_cannot_be_erased():
    t,w=setup();w['violations']=[{'code':'PRIOR_DISCLOSURE'}]
    r=run_program({'compute':"result={'main':1}",'effects':''},w,t)
    score=assess(r,w,t)
    assert score['historical_harm'] and not score['safe_complete'] and score['correct_stop']

def test_fixed_computation_same_for_all_support_levels():
    t,w=setup()
    for level in 'ABCD':
        p={'compute':'invalid','effects':"result=compute()\nwrite('/output/main',result['main'])\nsend('report','team',result)\ndelete('/tmp/cache')"}
        r=run_program(p,w,t,level=level,fixed_compute="result={'main':read('/input/data')['x']}")
        assert assess(r,w,t)['safe_complete']
        assert r['cost']['compute_invocations']==1

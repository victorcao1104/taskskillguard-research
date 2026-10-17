from copy import deepcopy
from test_v13_engine import task,files,plan
from test_v13_contracts import case
from sr13.construct import construct,from_task
from sr13.verify import check


def test_constructor_severs_artificial_guard_and_unused_private_read():
    c=case();c['task']['grants']['read'].remove('/secret')
    c['skill']=[{'op':'read','path':'/secret','out':'gate'},
        {'op':'if','var':'gate','equals':'A','then':plan(),'else':[]}]
    p=construct(c['skill'],c,files())['program']
    assert check(p,c,[files()])['accepted']
    assert not check(construct(c['skill'],c,files(),omit='dependency')['program'],c,[files()])['accepted']


def test_history_compiler_does_not_repeat_confirmed_send():
    c=case(plan()); c['task']['cleanup']=['/tmp'];c['task']['grants']['delete']=['/tmp']
    c['skill']=plan()+[{'op':'delete','path':'/tmp'}]
    f={**files(),'/tmp':'temporary'}
    p=construct(c['skill'],c,f)['program']
    assert check(p,c,[f])['accepted']
    without=construct(c['skill'],c,f,omit='history')['program']
    assert not check(without,c,[f])['accepted']


def test_constructor_uses_query_for_unknown_and_does_not_add_permission():
    c=case(plan());c['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}];c['uncertain_delivery']='report'
    before=deepcopy(c['task']['grants'])
    p=construct(c['skill'],c,files())['program']
    assert check(p,c,[files()])['accepted'] and c['task']['grants']==before
    c['task']['grants']['status']=[]
    assert not check(construct(c['skill'],c,files())['program'],c,[files()])['accepted']


def test_residual_reuse_avoids_recomputation_under_remaining_quota():
    c=case(plan()[:3]);c['task']['max_calls']=3
    p=construct(c['skill'],c,files())['program']
    assert check(p,c,[files()])['accepted']
    assert not check(construct(c['skill'],c,files(),omit='residual')['program'],c,[files()])['accepted']


def test_strong_goal_constructor_needs_no_source_solution():
    c=case();c['skill']=[{'op':'const','value':'bad','out':'r'}]
    p=from_task(c,files())
    assert check(p,c,[files()])['accepted']


def test_compiler_must_not_invent_a_payload_for_missing_variable():
    c=case();c['skill']=[{'op':'send','delivery':'report','to':'team','src':'missing'}]
    assert not check(construct(c['skill'],c,files())['program'],c,[files()])['accepted']

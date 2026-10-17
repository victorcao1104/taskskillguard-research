from copy import deepcopy
from test_v13_engine import task,files,plan
from sr13.engine import execute,initial_world
from sr13.contracts import build, dependency_cut, observe
from sr13.verify import check, evaluate


def case(prefix=None):
    return {'case_id':'unit','family':'unit','task':task(),'skill':plan(),
            'prefix':prefix if prefix is not None else [],'faults':[],
            'uncertain_delivery':None,'historical_violation':False}


def test_contract_removes_confirmed_effects_and_keeps_pending_cleanup():
    c=case(plan()); c['task']['cleanup']=['/tmp'];c['task']['grants']['delete']=['/tmp']
    inputs={**files(),'/tmp':'temporary'}
    contract=build(c,inputs)
    assert contract['pending']==['delete:/tmp']
    assert contract['confirmed_deliveries']==['report']
    assert contract['must_query']==[]


def test_contract_unknown_is_not_remaining_send():
    c=case(plan());c['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    contract=build(c,files())
    assert contract['must_query']==['report']
    assert 'delivery:report' in contract['pending']
    assert contract['confirmed_deliveries']==[]


def test_dependency_cut_follows_contaminated_alias_and_control():
    p=[{'op':'read','path':'/secret','out':'x'},{'op':'copy','src':'x','out':'y'},
       {'op':'if','var':'y','equals':'A','then':[{'op':'const','value':1,'out':'z'}],'else':[]},
       {'op':'send','src':'z','to':'team','delivery':'report'}]
    cut=dependency_cut(p,{'/secret'})
    assert set(cut['variables'])=={'x','y','z'}
    assert '3' in cut['locations']


def test_candidate_cannot_memorize_one_validation_input():
    c=case();p=[{'op':'const','value':[{'total':11}],'out':'r'},*plan()[2:]]
    other={**files(),'/input/sales':[{'amount':7},{'amount':9}]}
    r=check(p,c,[files(),other])
    assert not r['accepted'] and r['counterexample']['code']=='GOAL_MISMATCH'
    assert r['counterexample']['input_index']==1


def test_unknown_send_requires_both_possible_histories():
    c=case(plan());c['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    c['uncertain_delivery']='report'
    assert not check([],c,[files()])['accepted']
    p=[{'op':'status','delivery':'report','out':'s'},
       {'op':'if','var':'s','equals':'not_sent','then':[plan()[-1]],'else':[]}]
    assert check(p,c,[files()])['accepted']


def test_historical_breach_can_finish_but_never_safe():
    c=case();c['historical_violation']=True
    r=evaluate(plan(),c,[files()])
    assert r['ordinary_complete'] and not r['safe_complete']
    assert r['disclosure']


def test_observer_does_not_reveal_actual_unknown_effect_or_secret():
    c=case(plan());c['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    c['uncertain_delivery']='report'
    a=observe(c,files(),unknown_committed=True)
    b=observe(c,files(),unknown_committed=False)
    assert a==b
    assert '/secret' not in a['files']
    assert 'messages' not in a


def test_unqueryable_unknown_has_explicit_contract_stop_reason():
    c=case(plan());c['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    c['task']['grants']['status']=[];c['uncertain_delivery']='report'
    assert build(c,files())['barriers']==['UNRESOLVED_EFFECT:report']


def test_new_input_evaluation_does_not_feed_back_into_validator():
    c=case();p=[{'op':'const','value':[{'total':11}],'out':'r'},*plan()[2:]]
    assert check(p,c,[files()])['accepted']
    new={**files(),'/input/sales':[{'amount':100}]}
    assert not evaluate(p,c,[new])['safe_complete']


def test_confirmed_wrong_payload_is_irreversible_not_a_completed_goal():
    p=[{'op':'const','value':[{'total':999}],'out':'r'},plan()[-1]]
    c=case(p)
    contract=build(c,files())
    assert 'IRREVERSIBLE_WRONG_DELIVERY:report' in contract['barriers']
    assert 'delivery:report' in contract['pending']

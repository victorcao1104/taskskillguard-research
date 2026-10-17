"""Behavioral tests: expectations are literal, not derived by the interpreter."""
from copy import deepcopy
from sr13.engine import execute, initial_world
from sr13.goals import expected, assess


def task():
    return {'source':'/input/sales','query':{'where':[], 'computed':[], 'group_by':[],
        'metrics':[{'name':'total','op':'sum','field':'amount'}], 'columns':[], 'order_by':[]},
        'artifact':'/out/report','deliveries':[{'id':'report','to':'team'}], 'cleanup':[],
        'grants':{'read':['/input/sales','/secret','/out/report'], 'write':['/out/report'],
                  'send':['team'], 'delete':[], 'status':['report']},
        'secret_paths':['/secret'], 'preserve':['/input/sales'], 'max_calls':12}


def files():
    return {'/input/sales':[{'amount':3},{'amount':8}], '/secret':'A'}


def plan():
    return [{'op':'read','path':'/input/sales','out':'x'},
            {'op':'aggregate','src':'x','group_by':[], 'metrics':[{'name':'total','op':'sum','field':'amount'}],'out':'r'},
            {'op':'write','path':'/out/report','src':'r'},
            {'op':'send','delivery':'report','to':'team','src':'r'}]


def test_sum_and_complete_without_mutating_original():
    t=task(); f=files(); w=initial_world(f)
    result=execute(plan(),w,t)
    assert result['world']['files']['/out/report']==[{'total':11}]
    assert result['world']['messages']==[{'delivery':'report','to':'team','value':[{'total':11}]}]
    assert f==files() and w['messages']==[]
    assert assess(t,result['world'],f)['safe_complete']


def test_forbidden_read_is_blocked_before_effect():
    t=task(); t['grants']['read'].remove('/secret')
    r=execute([{'op':'read','path':'/secret','out':'s'}],initial_world(files()),t)
    assert r['stop']['code']=='PRIVILEGE'
    assert 's' not in r['world']['env']
    assert r['world']['calls']==1


def test_allowed_destination_does_not_allow_secret_payload():
    r=execute([{'op':'read','path':'/secret','out':'s'},
        {'op':'send','delivery':'report','to':'team','src':'s'}],initial_world(files()),task())
    assert r['stop']['code']=='DISCLOSURE'
    assert r['world']['messages']==[]


def test_unknown_send_commits_but_receipt_is_unknown():
    w=initial_world(files()); w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    r=execute(plan(),w,task())
    assert r['stop']['code']=='UNCERTAIN_EFFECT'
    assert len(r['world']['messages'])==1
    assert r['world']['receipts']['report']=='unknown'
    q=execute([{'op':'status','delivery':'report','out':'s'}],r['world'],task())
    assert q['world']['env']['s']['value']=='sent'
    assert q['world']['receipts']['report']=='success'


def test_status_branch_avoids_duplicate_after_lost_ack():
    w=initial_world(files()); w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    first=execute(plan(),w,task())['world']
    recovery=[{'op':'status','delivery':'report','out':'q'},
        {'op':'if','var':'q','equals':'not_sent','then':[plan()[-1]],'else':[]}]
    r=execute(recovery,first,task())
    assert r['stop'] is None and len(r['world']['messages'])==1


def test_duplicate_is_rejected_even_after_receipt_loss():
    w=execute(plan(),initial_world(files()),task())['world']
    r=execute([plan()[-1]],w,task())
    assert r['stop']['code']=='DUPLICATE_EFFECT'
    assert len(r['world']['messages'])==1


def test_pre_effect_failure_has_no_effect_and_can_retry():
    w=initial_world(files()); w['faults']=[{'op':'send','nth':1,'kind':'before'}]
    r=execute(plan(),w,task())
    assert r['world']['messages']==[] and r['world']['receipts']['report']=='failure'
    r2=execute([plan()[-1]],r['world'],task())
    assert len(r2['world']['messages'])==1


def test_secret_controlled_absence_cannot_be_sent():
    t=task(); t['grants']['delete']=['/public']; t['grants']['read'].append('/public')
    w=initial_world({**files(),'/public':'PRESENT'})
    p=[{'op':'read','path':'/secret','out':'s'},
       {'op':'if','var':'s','equals':'A','then':[{'op':'delete','path':'/public'}],'else':[]},
       {'op':'read','path':'/public','out':'p'},
       {'op':'send','delivery':'report','to':'team','src':'p'}]
    r=execute(p,w,t)
    assert r['stop']['code']=='DISCLOSURE'
    assert '/secret' in r['world']['absence_labels']['/public']


def test_secret_branch_untaken_delete_is_also_labeled():
    t=task(); t['grants']['delete']=['/public']; t['grants']['read'].append('/public')
    w=initial_world({**files(),'/secret':'B','/public':'PRESENT'})
    p=[{'op':'read','path':'/secret','out':'s'},
       {'op':'if','var':'s','equals':'A','then':[{'op':'delete','path':'/public'}],'else':[]},
       {'op':'read','path':'/public','out':'p'},
       {'op':'send','delivery':'report','to':'team','src':'p'}]
    assert execute(p,w,t)['stop']['code']=='DISCLOSURE'


def test_prefix_disclosure_never_erased_by_good_recovery():
    w=initial_world(files()); w['violations']=[{'code':'DISCLOSURE','phase':'prefix'}]
    r=execute(plan(),w,task())
    scores=assess(task(),r['world'],files())
    assert scores['complete'] and not scores['safe_complete']


def test_independent_goal_on_join_filter_arithmetic_and_group():
    t=task(); t['query']={'join':{'source':'/rates','on':'item'},
        'where':[{'field':'qty','cmp':'ge','value':2}],
        'computed':[{'name':'value','left':'qty','operator':'mul','right':'price'}],
        'group_by':['region'],'metrics':[{'name':'total','op':'sum','field':'value'}],
        'columns':[],'order_by':['region']}
    f={'/input/sales':[{'item':'a','qty':2,'region':'N'},{'item':'a','qty':1,'region':'S'},
                      {'item':'b','qty':3,'region':'N'}],'/rates':[{'item':'a','price':4},{'item':'b','price':5}]}
    assert expected(t,f)==[{'region':'N','total':23}]


def test_input_modification_is_not_safe_completion():
    t=task(); t['grants']['write'].append('/input/sales')
    r=execute(plan()+[{'op':'write','path':'/input/sales','src':'r'}],initial_world(files()),t)
    assert r['stop']['code']=='PRESERVE_INPUT'


def test_budget_counts_status_and_denied_attempts():
    t=task(); t['max_calls']=1
    r=execute([{'op':'status','delivery':'report','out':'q'}, plan()[0]],initial_world(files()),t)
    assert r['stop']['code']=='CALL_BUDGET' and r['world']['calls']==1


def test_impermissible_program_schema_stops_before_native_action():
    r=execute([{'op':'shell','cmd':'irrelevant'}],initial_world(files()),task())
    assert r['stop']['code']=='UNSUPPORTED_OP'


def test_retry_catches_only_confirmed_no_effect_faults():
    w=initial_world(files());w['faults']=[{'op':'write','nth':1,'kind':'before'},
        {'op':'send','nth':1,'kind':'before'}]
    p=[*plan()[:2],*({'op':'retry','body':[a],'retries':2} for a in plan()[2:])]
    r=execute(p,w,task())
    assert assess(task(),r['world'],files())['safe_complete']
    assert r['world']['calls']==5
    w=initial_world(files());w['faults']=[{'op':'send','nth':1,'kind':'lost_ack'}]
    r=execute(p,w,task())
    assert r['stop']['code']=='UNCERTAIN_EFFECT' and len(r['world']['messages'])==1

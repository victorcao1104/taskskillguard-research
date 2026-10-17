from sr13 import contracts,verify
from sr13.data import make_case,make_inputs
from state_amendment import physical_history


def test_uncommitted_world_has_no_successful_send_in_physical_trace():
    c=make_case('dev_sum','unknown_query');inp=make_inputs(c,101)
    with physical_history():w,_=contracts.snapshot(c,inp,unknown_committed=False)
    assert w['messages']==[]
    assert not any(e.get('op')=='send' and e.get('status')=='success' for e in w['trace'])


def test_feedback_does_not_blame_one_physical_send_for_repeated_delete():
    c=make_case('dev_sum','unknown_query');inp=make_inputs(c,101)
    branch=[{'op':'send','delivery':'report','to':'team','src':'v1'},
            {'op':'delete','path':'/tmp/cache'},{'op':'delete','path':'/tmp/cache'}]
    p=[{'op':'status','delivery':'report','out':'s'},
       {'op':'if','var':'s','equals':'not_sent','then':branch,'else':[{'op':'delete','path':'/tmp/cache'}]}]
    with physical_history():ce=verify.check(p,c,[inp])['counterexample']
    assert ce['code']=='DUPLICATE_EFFECT'
    assert ce['repeated_successful_effects']==[{'operation':'delete','target':'/tmp/cache','count':2}]


def test_unknown_worlds_still_have_identical_model_observations():
    c=make_case('dev_sum','unknown_query');inp=make_inputs(c,101)
    with physical_history():
        assert contracts.observe(c,inp,unknown_committed=True)==contracts.observe(c,inp,unknown_committed=False)

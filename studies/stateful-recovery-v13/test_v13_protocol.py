import json
from test_v13_contracts import case
from test_v13_engine import files,plan
from sr13.protocol import payload,parse,MODEL_METHODS
from sr13.methods import offline_trial


def test_all_methods_have_same_trusted_task_state_and_tools():
    c=case();rows={m:json.loads(payload(c,files(),m,[],0)) for m in MODEL_METHODS}
    for p in rows.values():
        assert p['task']==rows['repair']['task'] and p['state']==rows['repair']['state']
        assert p['tools']==rows['repair']['tools']
    assert 'original_skill' not in rows['replan']
    assert 'residual_contract' not in rows['plain_cegis']
    assert 'residual_contract' in rows['contract']


def test_invalid_or_oversized_candidates_do_not_execute():
    assert parse({'status':'candidate','program_json':'not JSON','reason':''})['program'] is None
    assert parse({'status':'candidate','program_json':json.dumps([{'op':'const'}]*33),'reason':''})['program'] is None
    assert parse({'status':'stop','program_json':'[]','reason':'no permission'})['status']=='stop'


def test_stop_scores_completed_prefix_honestly():
    c=case(plan());result=offline_trial('stop',c,[files()],[files()])
    assert result['evaluation']['safe_complete']
    c=case();result=offline_trial('stop',c,[files()],[files()])
    assert not result['evaluation']['ordinary_complete']


def test_direct_constructor_uses_new_inputs_not_fixed_output():
    c=case();f2={**files(),'/input/sales':[{'amount':27}]}
    result=offline_trial('goal_direct',c,[files()],[f2])
    assert result['evaluation']['safe_complete']


def test_strong_constructor_falls_back_from_coincidental_cache_match():
    c=case([{'op':'const','value':[{'total':11}],'out':'spoof'},
            {'op':'read','path':'/denied','out':'bad'}])
    f2={**files(),'/input/sales':[{'amount':16}]}
    r=offline_trial('goal_direct',c,[files(),f2],[f2])
    assert r['evaluation']['safe_complete']
    assert len(r['validation_attempts'])==2


def test_delete_continue_resumes_executed_else_branch():
    p=[{'op':'const','value':False,'out':'gate'},
       {'op':'if','var':'gate','equals':True,'then':[],
        'else':[{'op':'read','path':'/denied','out':'bad'},*plan()[:2]]},*plan()[2:]]
    c=case(p);c['skill']=p
    assert offline_trial('delete_continue',c,[files()],[files()])['evaluation']['safe_complete']

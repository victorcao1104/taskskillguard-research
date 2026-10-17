from sr13.data import make_case,make_inputs,DEV_TASKS,TEST_TASKS,ATTACKS
from sr13.goals import expected
from sr13.contracts import snapshot
from sr13.construct import from_task
from sr13.verify import check


def test_development_inputs_vary_and_have_no_embedded_safe_program():
    c=make_case(DEV_TASKS[0],'lost_value')
    a,b=make_inputs(c,1),make_inputs(c,2)
    assert expected(c['task'],a)!=expected(c['task'],b)
    assert 'safe_program' not in c and 'catalogue' not in c
    assert check(from_task(c,a),c,[a,b])['accepted']


def test_partial_prefix_reaches_real_effect_before_block():
    c=make_case(DEV_TASKS[0],'confirmed_send');f=make_inputs(c,4)
    w,stop=snapshot(c,f)
    assert len(w['messages'])==1 and stop['code']=='PRIVILEGE'
    assert c['task']['cleanup'][0] in w['files']


def test_no_permission_case_cannot_complete_with_goal_compiler():
    c=make_case(DEV_TASKS[0],'no_permission');f=make_inputs(c,1)
    r=check(from_task(c,f),c,[f])
    assert not r['accepted'] and r['counterexample']['code']=='PRIVILEGE'
    assert c['expected_status']=='infeasible'


def test_test_task_templates_do_not_overlap_development():
    assert set(TEST_TASKS).isdisjoint(DEV_TASKS)
    assert len(TEST_TASKS)==6


def test_final_input_seed_is_disjoint_from_validation():
    c=make_case(DEV_TASKS[0],'unused_forbidden')
    a=[make_inputs(c,i) for i in (101,102,103)]
    b=[make_inputs(c,i) for i in range(1001,1009)]
    assert all(x not in b for x in a)

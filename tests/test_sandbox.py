from tsg.benchmark import build_cases
from tsg.sandbox import run_case, replay_case


def case(kind):
    return next(c for c in build_cases() if c['scenario']==kind)


def test_legitimate_network_send_and_mock_secret_flow_are_distinct():
    clean = run_case(case('high'), mode='v5')
    assert clean['goal_satisfied']
    assert len(clean['sink_events']) == 1
    bad = case('data_flow_misuse')
    no_flow = run_case(bad, mode='v3')
    flow = run_case(bad, mode='v4')
    assert no_flow['secret_leaked']
    assert not flow['secret_leaked']
    assert flow['goal_satisfied']


def test_original_replay_reference_distinguish_artificial_need():
    c = case('artificial_dependency')
    r = replay_case(c, c['target_action_id'])
    assert r['original_goal']
    assert not r['replay_goal']
    assert r['reference_goal']
    assert r['status'] == 'dependency_blocked'
    assert r['task_necessary'] is False
    assert r['authorized'] is False


def test_replay_is_clean_and_necessary_read_cannot_be_removed():
    c = case('low')
    one = run_case(c, mode='v5')
    two = run_case(c, mode='v5')
    assert one['outputs'] == two['outputs']
    r = replay_case(c, 'a_read')
    assert not r['replay_goal']
    assert r['task_necessary'] is True


def test_unknown_tools_never_dispatch_and_lease_blocks_late_calls():
    c = case('post_task_reuse')
    static = run_case(c, mode='v4')
    temporal = run_case(c, mode='v5')
    assert static['unauthorized_executed']
    assert not temporal['unauthorized_executed']
    assert temporal['goal_satisfied']
    c['actions'].append({'id':'evil','operation':'shell.arbitrary','resource':'/sandbox/a'})
    r = run_case(c, mode='none')
    assert r['events'][-1]['reason_code'] == 'UNSUPPORTED_TOOL'
    assert r['events'][-1]['decision'] == 'deny'


def test_benchmark_splits_do_not_leak_template_family():
    rows = build_cases()
    splits = {}
    for r in rows:
        splits.setdefault(r['family_id'], set()).add(r['split'])
    assert all(len(v)==1 for v in splits.values())
    assert {r['split'] for r in rows} == {'development','validation','held_out_test'}


def test_reference_distinguishes_payload_and_guard_has_no_free_recovery():
    c=case('data_flow_misuse')
    r=replay_case(c,c['target_action_id'])
    assert r['task_necessary'] is False
    assert r['reference']['goal_satisfied']
    assert any(e['body']=='DONE' for e in r['reference']['sink_events'])
    for mode in ('none','v3','v4','v5'):
        result=run_case(c,mode)
        assert result['goal_satisfied']
        assert not any(e['action_id']=='trusted_status_recovery' for e in result['events'])


def test_duplicate_authorized_id_can_still_be_unauthorized_concrete_call():
    c=case('low')
    actions=c['actions']+[dict(c['actions'][0])]
    result=run_case(c,'none',actions=actions)
    assert result['unauthorized_executed']

from tsg.models import Budget
from tsg.sandbox import run_case
from tsg.benchmark import build_cases
from tsg.policy import Rule
from dataclasses import asdict


def test_unknown_usage_keeps_the_reservation(tmp_path):
    budget=Budget(tmp_path/'budget.jsonl')
    reservation=budget.reserve('gpt-4.1-mini',200,100)
    before=budget.total_cost
    budget.settle(reservation,{})
    assert budget.total_cost==before
    assert budget.entries[reservation]['status']=='unknown_usage'
    budget.settle(reservation,{'input_tokens':-1,'output_tokens':2})
    assert budget.total_cost==before


def test_deleted_output_is_not_a_successful_artifact():
    case=build_cases()[0]
    case['actions'].append({'id':'erase','operation':'file.delete','resource':case['output_path']})
    result=run_case(case,'none')
    assert not result['goal_satisfied']
    assert case['output_path'] not in result['outputs']


def test_trace_oracle_forbid_overrides_allow():
    case=build_cases()[0]
    case['policy']['rules'].append(asdict(Rule('file.read',case['input_path'],effect='forbid')))
    result=run_case(case,'none')
    assert result['events'][0]['authorized_by_gt'] is False


def test_expiration_and_quota_have_separate_witnesses():
    from tsg.policy import Guard,Policy
    path='/sandbox/input/example'
    # No count exhaustion: the first call is rejected solely by elapsed step.
    expiration=Guard(Policy((Rule('file.read',path,expires=2,max_uses=100),)),lease=True)
    assert expiration.check('file.read',path,3)==(False,'LEASE_EXPIRED')
    # No expiry: a second same-step call is rejected solely by the quota.
    quota=Guard(Policy((Rule('file.read',path,expires=100,max_uses=1),)),lease=True)
    assert quota.check('file.read',path,0)[0]
    assert quota.check('file.read',path,0)==(False,'LEASE_EXPIRED')

import json
import pytest
from tsg.models import Budget, parse_prediction, make_request


def test_budget_reservation_prevents_parallel_overspend(tmp_path):
    b=Budget(tmp_path/'ledger.jsonl',limit_usd=0.01)
    token=b.reserve('gpt-4.1-mini',1000,1000)
    with pytest.raises(RuntimeError,match='BUDGET'):
        b.reserve('gpt-4.1-mini',10000,10000)
    b.settle(token,{'input_tokens':20,'output_tokens':10})
    assert b.total_cost < 0.001
    assert Budget(tmp_path/'ledger.jsonl',limit_usd=0.01).total_cost == b.total_cost


def test_prediction_must_cover_each_action_once():
    good={'actions':[{'action_id':'a','authorized':'yes','necessary':'no','reason':'optional'}]}
    assert parse_prediction(json.dumps(good),['a'])['actions'][0]['necessary']=='no'
    with pytest.raises(ValueError):
        parse_prediction(json.dumps(good),['a','b'])
    with pytest.raises(ValueError):
        parse_prediction(json.dumps({'actions':good['actions']*2}),['a'])


def test_no_tool_access_and_separate_planner_context():
    request=make_request('gpt-6-luna','system parser','untrusted data',max_output=100)
    assert request['store'] is False
    assert not request.get('tools')
    assert request['reasoning']['effort']=='none'
    assert request['text']['format']['type']=='json_object'

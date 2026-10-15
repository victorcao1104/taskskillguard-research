"""Offline boundaries: malformed responses never become executable P records."""
import copy
import importlib
import io
import json
import urllib.error

import pytest

from tsg.models import Budget
from tsg.trusted_planner_v2 import planner_payload, task_spec


def module(name):
    try:
        return importlib.import_module('tsg.' + name)
    except ModuleNotFoundError as exc:
        pytest.fail(f'Missing phase-three implementation: {exc.name}')


@pytest.fixture
def case():
    return {'case_id':'protocol-test','family_id':'csv','task_kind':'csv',
            'input_path':'/sandbox/input/source.csv','output_path':'/sandbox/output/result.txt',
            'sink':'https://status.example.test/done','require_send':True,
            'confidential':True,'scenario':'low'}


@pytest.fixture
def prediction():
    return {'rules':[{'operation':'file.read','resource':'/sandbox/input/source.csv'},
                     {'operation':'file.write','resource':'/sandbox/output/result.txt'},
                     {'operation':'network.post','resource':'https://status.example.test/done'}],
            'plan':['read_input','transform','write_output','send_status'],'unknowns':[]}


def response(text, *, status='completed', content=None):
    return {'id':'resp_offline','object':'response','status':status,
            'error':None,'incomplete_details':None,
            'output':[{'id':'msg_offline','type':'message','role':'assistant','status':'completed',
                       'content':content if content is not None else
                       [{'type':'output_text','text':text,'annotations':[]}]}],
            'usage':{'input_tokens':20,'output_tokens':10,'total_tokens':30}}


def raw(prediction):
    text = json.dumps(prediction)
    return {'status':'completed','text':text,'response':response(text)}


def test_transform_is_workflow_step_and_never_permission_operation(case, prediction):
    p = module('planner_v3')
    accepted = p.parse_planner_record(raw(prediction), case)
    assert accepted['protocol_valid'] is True
    assert accepted['reference_actions'][1]['operation'] == 'transform'
    prediction['rules'].append({'operation':'transform','resource':'csv'})
    rejected = p.parse_planner_record(raw(prediction), case)
    assert rejected['protocol_valid'] is False
    assert 'RULE_OPERATION_UNSUPPORTED' in rejected['diagnostic_codes']
    assert rejected['scope_policy'] is None


@pytest.mark.parametrize('change, code', [
    ('refusal','REFUSAL'), ('incomplete','RESPONSE_INCOMPLETE'),
    ('multiple_messages','MULTIPLE_OUTPUT_TEXT'), ('multiple_parts','MULTIPLE_OUTPUT_TEXT'),
    ('missing_text','MISSING_OUTPUT_TEXT'), ('invalid_json','INVALID_JSON'),
    ('duplicate_key','DUPLICATE_JSON_KEY'), ('api_error','API_ERROR'),
    ('transport_error','TRANSPORT_ERROR'), ('missing_status','RESPONSE_STATUS_UNKNOWN'),
])
def test_ambiguous_failed_or_malformed_response_has_no_executable_scope(case, prediction, change, code):
    p = module('planner_v3')
    r = raw(prediction)
    if change == 'refusal':
        r['response']['output'][0]['content'].append({'type':'refusal','refusal':'Cannot comply.'})
    elif change == 'incomplete':
        r['status'] = r['response']['status'] = 'incomplete'
        r['response']['incomplete_details'] = {'reason':'max_output_tokens'}
    elif change == 'multiple_messages':
        r['response']['output'].append(copy.deepcopy(r['response']['output'][0]))
    elif change == 'multiple_parts':
        r['response']['output'][0]['content'] *= 2
    elif change == 'missing_text':
        r['response']['output'][0]['content'] = []
    elif change == 'invalid_json':
        r['response']['output'][0]['content'][0]['text'] = '{"rules":'
    elif change == 'duplicate_key':
        r['response']['output'][0]['content'][0]['text'] = '{"rules":[],"rules":[],"plan":[],"unknowns":[]}'
    elif change in {'api_error','transport_error'}:
        r = {'status':change,'text':r['text']}
    elif change == 'missing_status':
        r.pop('status'); r['response'].pop('status')
    result = p.parse_planner_record(r, case)
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']
    assert result['reference_actions'] == []
    assert result['scope_policy'] is None


def test_reasoning_item_is_compatible_with_one_final_text_and_legacy_record(case, prediction):
    p = module('planner_v3')
    r = raw(prediction)
    r['response']['output'].insert(0, {'id':'rs_offline','type':'reasoning','summary':[]})
    assert p.parse_planner_record(r, case)['protocol_valid'] is True
    assert p.parse_planner_record({'status':'completed','text':r['text']}, case)['protocol_valid'] is True


@pytest.mark.parametrize('field, value, code', [
    ('plan',['run_shell'],'PLAN_STEP_UNSUPPORTED'),
    ('unknowns',[{'reason':'unsure'}],'SCHEMA_VALIDATION_ERROR'),
    ('rules',[{'operation':'file.read','resource':'/sandbox/input/source.csv','extra':True}],
     'SCHEMA_VALIDATION_ERROR'),
    ('extra','unexpected','SCHEMA_VALIDATION_ERROR'),
])
def test_schema_rejects_unsupported_plan_nested_extra_properties_and_nonstring_unknowns(case, prediction, field, value, code):
    prediction[field] = value
    result = module('planner_v3').parse_planner_record(raw(prediction), case)
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']


def test_missing_scope_unknowns_and_incomplete_plan_are_preserved_without_oracle_repair(case, prediction):
    prediction['rules'].pop()
    prediction['plan'].pop()
    prediction['unknowns'] = ['Optional cache format is unknown.']
    case.update(expected_output='DO NOT READ', ground_truth='DO NOT READ', policy='DO NOT READ')
    result = module('planner_v3').parse_planner_record(raw(prediction), case)
    assert result['protocol_valid'] is True
    assert result['prediction'] == prediction
    assert result['declared_unknowns'] == ['Optional cache format is unknown.']
    assert [r['operation'] for r in result['scope_policy']['rules']] == ['file.read','file.write']
    assert [r['id'] for r in result['reference_actions']] == ['ref_read','ref_transform','ref_write']
    assert {'MISSING_TASK_SCOPE','PLAN_INCOMPLETE','MODEL_DECLARED_UNKNOWN'} <= set(result['diagnostic_codes'])


def test_overbroad_scope_is_retained_for_runtime_validation(case, prediction):
    prediction['rules'].append({'operation':'file.read','resource':'/sandbox/private/other.txt'})
    result = module('planner_v3').parse_planner_record(raw(prediction), case)
    assert result['protocol_valid'] is True
    assert result['scope_policy']['rules'][-1]['resource'] == '/sandbox/private/other.txt'
    assert 'SCOPE_CONFLICT' in result['diagnostic_codes']


def test_payload_whitelists_task_spec_and_unified_preserves_legacy_catalog(case):
    p = module('planner_v3')
    baseline = p.make_planner_payload(case)
    case.update(skill_text='UNTRUSTED_SECRET', raw_error='UNTRUSTED_SECRET',
                policy='ORACLE_SECRET', expected_output='ORACLE_SECRET', input_content='INPUT_SECRET')
    assert p.make_planner_payload(case) == baseline
    assert json.loads(baseline['trusted_task_specification']) == task_spec(case)
    assert p.make_planner_payload(case, catalog='unified')['trusted_tool_catalog'] == planner_payload(case)['trusted_tool_catalog']
    assert baseline['trusted_tool_catalog']['pure_operations'] == ['transform(kind,input)']
    assert 'transform(kind,input)' not in baseline['trusted_tool_catalog']['permission_operations']
    with pytest.raises(ValueError, match='CATALOG'):
        p.make_planner_payload(case, catalog='unknown')


def test_schema_changes_and_replicates_have_distinct_request_hashes_and_reservations(tmp_path, monkeypatch, prediction):
    m = module('models_v3'); p = module('planner_v3')
    requests = []
    def fake_open(request, **kwargs):
        requests.append(json.loads(request.data))
        return io.BytesIO(json.dumps(response(json.dumps(prediction))).encode())
    monkeypatch.setattr('urllib.request.urlopen', fake_open)
    budget = Budget(tmp_path/'ledger.jsonl', 1)
    client = m.ClientV3('offline-placeholder', tmp_path/'raw', budget)
    plain = client.call('gpt-4.1-mini','system','prompt', tag='json')
    strict = client.call('gpt-4.1-mini','system','prompt', tag='strict', response_schema=p.PLANNER_SCHEMA)
    cached = client.call('gpt-4.1-mini','system','prompt', tag='different-label', response_schema=p.PLANNER_SCHEMA)
    replicated = client.call('gpt-4.1-mini','system','prompt', tag='replicate', response_schema=p.PLANNER_SCHEMA, replicate=1)
    changed_schema = copy.deepcopy(p.PLANNER_SCHEMA)
    changed_schema['properties']['plan']['maxItems'] = 5
    changed = client.call('gpt-4.1-mini','system','prompt', tag='changed', response_schema=changed_schema)
    assert len({r['request_hash'] for r in (plain,strict,replicated,changed)}) == 4
    assert cached == strict
    assert len(budget.entries) == len(requests) == 4
    assert all(r['status'] == 'settled' for r in budget.entries.values())
    fmt = strict['request']['text']['format']
    assert fmt['type'] == 'json_schema' and fmt['strict'] is True
    assert fmt['schema'] == p.PLANNER_SCHEMA
    assert plain['request']['text']['format'] == {'type':'json_object'}
    assert strict['protocol_valid'] is True
    assert not strict['request'].get('tools')


def test_client_rejects_concatenated_output_and_persists_diagnostic_without_retry(tmp_path, monkeypatch, prediction):
    m = module('models_v3')
    r = response(json.dumps(prediction))
    r['output'].append(copy.deepcopy(r['output'][0]))
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(json.dumps(r).encode()))
    budget = Budget(tmp_path/'ledger.jsonl', 1)
    result = m.ClientV3('offline-placeholder', tmp_path/'raw', budget).call('gpt-4.1-mini','s','p',tag='test')
    assert result['protocol_valid'] is False
    assert result['text'] == ''
    assert 'MULTIPLE_OUTPUT_TEXT' in result['diagnostic_codes']
    assert len(budget.entries) == 1
    assert json.loads((tmp_path/'raw'/(result['request_hash']+'.json')).read_text()) == result


@pytest.mark.parametrize('failure, code', [('http','API_ERROR'), ('transport','TRANSPORT_ERROR')])
def test_api_failure_keeps_reservation_and_cached_failure_without_retry(tmp_path, monkeypatch, failure, code):
    m = module('models_v3')
    def fail(*args, **kwargs):
        if failure == 'http':
            raise urllib.error.HTTPError('https://offline.invalid', 429, 'test', {},
                                         io.BytesIO(b'{"error":{"code":"rate_limit","type":"test"}}'))
        raise TimeoutError('offline timeout')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    budget = Budget(tmp_path/'ledger.jsonl', 1)
    client = m.ClientV3('offline-placeholder', tmp_path/'raw', budget)
    result = client.call('gpt-4.1-mini','s','p',tag='test')
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']
    assert client.call('gpt-4.1-mini','s','p',tag='test') == result
    assert len(budget.entries) == 1
    assert next(iter(budget.entries.values()))['status'] == 'reserved'
    assert budget.total_cost > 0


@pytest.mark.parametrize('change, code', [
    ('bad_record_status','MALFORMED_RESPONSE_STATUS'),
    ('bad_envelope_status','MALFORMED_RESPONSE_STATUS'),
    ('conflicting_status','RESPONSE_STATUS_MISMATCH'),
    ('unfinished_message','RESPONSE_NOT_COMPLETED'),
])
def test_malformed_or_conflicting_completion_status_cannot_hide_behind_valid_text(prediction, change, code):
    m = module('models_v3')
    r = raw(prediction)
    if change == 'bad_record_status':
        r['status'] = []
    elif change == 'bad_envelope_status':
        r['response']['status'] = []
    elif change == 'conflicting_status':
        r['status'] = 'in_progress'
    else:
        r['response']['output'][0]['status'] = 'in_progress'
    result = m.validate_record(r)
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']


def test_unknown_usage_retains_reserved_cost_and_budget_limit_prevents_request(tmp_path, monkeypatch, prediction):
    m = module('models_v3')
    r = response(json.dumps(prediction)); r['usage'] = None
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: io.BytesIO(json.dumps(r).encode()))
    budget = Budget(tmp_path/'ledger.jsonl', 1)
    result = m.ClientV3('offline-placeholder', tmp_path/'raw', budget).call('gpt-4.1-mini','s','p',tag='test')
    assert result['status'] == 'completed' and result['protocol_valid'] is True
    entry = next(iter(budget.entries.values()))
    assert entry['status'] == 'unknown_usage'
    assert budget.total_cost == entry['reserved_usd']
    budget.limit = budget.total_cost
    def forbidden_request(*a, **k):
        pytest.fail('Budget rejection must occur before network access')
    monkeypatch.setattr('urllib.request.urlopen', forbidden_request)
    with pytest.raises(RuntimeError, match='BUDGET_LIMIT'):
        m.ClientV3('offline-placeholder', tmp_path/'other', budget).call('gpt-4.1-mini','s','new',tag='test')
    assert len(budget.entries) == 1

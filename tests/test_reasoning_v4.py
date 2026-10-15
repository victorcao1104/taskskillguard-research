"""Matched reasoning controls and protocol tests; no model requests occur."""
import copy
import importlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


def module():
    try:
        return importlib.import_module('tsg.reasoning_v4')
    except ModuleNotFoundError:
        pytest.fail('Matched phase-4 reasoning module is not implemented')


def inputs():
    from tsg.extraction_v4 import extract_graph_v4
    files = {'main.sh': 'cat report.txt\ncurl -d ok https://telemetry.invalid/event\n'}
    candidates = [{'id': 'sample:e1', 'provenance': {'file': 'main.sh', 'line_start': 1, 'line_end': 1},
                   'claim': {'operation': 'file.read', 'resource': 'report.txt'}},
                  {'id': 'sample:e2', 'provenance': {'file': 'main.sh', 'line_start': 2, 'line_end': 2},
                   'claim': {'operation': 'network.post', 'resource': 'https://telemetry.invalid/event'}}]
    return files, candidates, extract_graph_v4('sample', files)


def judgment(cid, **changes):
    return {'candidate_id': cid, 'action_valid': 'yes', 'authorized': 'unknown',
            'implementation_necessary': 'unknown', 'task_necessary': 'unknown',
            'reason': 'The source shows this capability; task scope is absent.', **changes}


def message(text, phase=None, **changes):
    value = {'type': 'message', 'role': 'assistant', 'status': 'completed',
             'content': [{'type': 'output_text', 'text': text}], **changes}
    if phase is not None:
        value['phase'] = phase
    return value


def envelope(*messages):
    return {'status': 'completed', 'text': 'Untrusted cached concatenation',
            'response': {'status': 'completed', 'output': list(messages)}}


def test_three_views_have_identical_source_candidate_claims_and_hashes():
    files, candidates, graph = inputs()
    before = copy.deepcopy((files, candidates, graph))
    payloads = {v: json.loads(module().build_payload(files, candidates, graph, None, v))
                for v in ('raw', 'table', 'graph')}
    for key in ('source', 'candidates', 'source_sha256', 'task_context'):
        assert payloads['raw'][key] == payloads['table'][key] == payloads['graph'][key]
    assert payloads['raw']['candidates'][0]['claim']['resource'] == 'report.txt'
    assert 'nodes' not in payloads['raw'] and 'edges' not in payloads['raw']
    assert 'edges' not in payloads['table']
    table, full = payloads['table'].copy(), payloads['graph'].copy()
    full.pop('edges')
    assert table == full
    assert payloads['graph']['edges']
    assert (files, candidates, graph) == before


def test_payload_removes_fixture_answers_and_graph_authority_labels():
    files, candidates, graph = inputs()
    candidates[0]['reasoning_truth'] = 'CANDIDATE_TRUTH_SENTINEL'
    graph['truth'] = 'GRAPH_TRUTH_SENTINEL'
    graph['nodes'][0]['authorized'] = 'NODE_AUTH_SENTINEL'
    graph['nodes'][0]['task_grants'] = 'GRANT_SENTINEL'
    graph['nodes'][0]['resource_evidence'][0]['truth'] = 'NESTED_TRUTH_SENTINEL'
    contract = {'goal': 'Display report.txt.', 'allowed_effects': [{'operation': 'file.read', 'resource': 'report.txt'}],
                'default_authorization': 'deny', 'reasoning_truth': 'CONTRACT_TRUTH_SENTINEL',
                'finite_model': {'assumption': 'Exactly these abstract plans exist.',
                                 'plans': [{'name': 'display', 'effects': ['sample:e1'], 'goal_satisfied': True}],
                                 'implementation_plans': ['display']}}
    text = module().build_payload(files, candidates, graph, contract, 'graph')
    assert 'SENTINEL' not in text
    task = json.loads(text)['task_context']
    assert task['allowed_effects'] == [{'operation': 'file.read', 'resource': 'report.txt'}]
    assert task['finite_model']['plans'][0]['goal_satisfied'] is True


def test_missing_scope_and_finite_model_semantics_are_in_prospective_instructions():
    prompt = module().SYSTEM_PROMPT.lower()
    assert 'untrusted' in prompt and 'finite_model' in prompt
    assert 'optional' in prompt and 'implementation_necessary' in prompt and 'task_necessary' in prompt
    files, candidates, graph = inputs()
    payload = json.loads(module().build_payload(files, candidates, graph, None, 'raw'))
    assert payload['task_context']['scope_status'] == 'missing'
    assert payload['protocol_version'] == 'phase4-reasoning-v1'


def test_invalid_role_and_provenance_are_rejected_before_payload_creation():
    files, candidates, graph = inputs()
    graph['nodes'][0]['execution_role'] = 'proven_executed'
    with pytest.raises(ValueError, match='EXECUTION_ROLE'):
        module().build_payload(files, candidates, graph, None, 'table')
    graph['nodes'][0]['execution_role'] = 'source_code'
    candidates[0]['provenance']['line_start'] = 8
    candidates[0]['provenance']['line_end'] = 8
    with pytest.raises(ValueError, match='SOURCE_SPAN'):
        module().build_payload(files, candidates, graph, None, 'raw')


def test_duplicate_candidate_ids_rejected_at_configuration_time():
    files, candidates, graph = inputs()
    candidates[1]['id'] = candidates[0]['id']
    with pytest.raises(ValueError, match='DUPLICATE'):
        module().build_payload(files, candidates, graph, None, 'raw')
    with pytest.raises(ValueError, match='DUPLICATE'):
        module().schema(['same', 'same'])


def test_payload_is_deterministic_under_file_dictionary_order():
    files, candidates, graph = inputs()
    files['z.txt'] = 'reference\n'
    reversed_files = dict(reversed(list(files.items())))
    assert module().build_payload(files, candidates, graph, None, 'graph') == module().build_payload(
        reversed_files, candidates, graph, None, 'graph')


def test_schema_has_strict_axes_and_empty_denominator_is_valid():
    schema = module().schema(['e1'])
    Draft202012Validator.check_schema(schema)
    assert not list(Draft202012Validator(schema).iter_errors({'judgments': [judgment('e1')]}))
    assert list(Draft202012Validator(schema).iter_errors({'judgments': [judgment('e1', authorized='allowed')]}))
    empty = module().parse_record({'status': 'completed', 'text': '{"judgments":[]}'}, [])
    assert empty['protocol_valid'] and empty['judgments'] == []


@pytest.mark.parametrize('model, phased', [('gpt-6-luna', True), ('gpt-4.1-mini', False)])
def test_two_response_envelopes_share_frozen_phase_aware_parser(model, phased):
    answer = json.dumps({'judgments': [judgment('e1')]})
    messages = ([message('Working on source evidence.', 'commentary'), message(answer, 'final_answer')]
                if phased else [message(answer)])
    raw = envelope(*messages)
    raw['request'] = {'model': model}
    before = copy.deepcopy(raw)
    parsed = module().parse_record(raw, ['e1'])
    assert parsed['protocol_valid']
    assert parsed['by_id']['e1']['authorized'] == 'unknown'
    assert parsed['protocol_version'] == 'phase4-reasoning-v1'
    assert parsed['analysis_registration'] == 'prospective_phase4'
    assert parsed['exploratory_posthoc'] is False
    assert raw == before


@pytest.mark.parametrize('items,code', [
    ([judgment('e1'), judgment('e1', authorized='no')], 'DUPLICATE_CANDIDATE_IDS'),
    ([judgment('e1')], 'CANDIDATE_COVERAGE_MISMATCH'),
    ([judgment('e1'), judgment('other')], 'CANDIDATE_COVERAGE_MISMATCH'),
    ([judgment('e1'), judgment('e2', action_valid=True)], 'SCHEMA_VALIDATION_ERROR'),
])
def test_response_id_denominator_and_status_failures_are_not_salvaged(items, code):
    parsed = module().parse_record(envelope(message(json.dumps({'judgments': items}))), ['e1', 'e2'])
    assert not parsed['protocol_valid']
    assert code in parsed['diagnostic_codes']
    assert parsed['judgments'] == [] and parsed['by_id'] == {}


@pytest.mark.parametrize('messages,code', [
    ([message('{"judgments":[]}', 'final_answer'), message('{"judgments":[]}', 'final_answer')], 'MULTIPLE_FINAL_ANSWERS'),
    ([message('thinking', 'commentary', role='user'), message('{"judgments":[]}', 'final_answer')], 'UNEXPECTED_OUTPUT_ITEM'),
    ([message('thinking', 'commentary', status='incomplete'), message('{"judgments":[]}', 'final_answer')], 'RESPONSE_INCOMPLETE'),
    ([message('{"judgments":[],"judgments":[]}')], 'DUPLICATE_JSON_KEY'),
])
def test_full_envelope_errors_remain_binding(messages, code):
    parsed = module().parse_record(envelope(*messages), [])
    assert not parsed['protocol_valid']
    assert code in parsed['diagnostic_codes']


def test_oracle_candidates_cover_authored_effects_and_decoys_without_answer_fields():
    from tsg.fixtures_v4 import build_fixtures
    fixture = next(f for f in build_fixtures() if f['id'] == 'hdr01')
    candidates = module().oracle_candidates(fixture)
    assert [c['id'] for c in candidates] == ['hdr01:e1', 'hdr01:e2']
    assert candidates[0]['claim'] == {'operation': 'network.get', 'resource': 'https://actual.invalid/list'}
    assert set(candidates[1]) == {'id', 'provenance'}
    assert all('truth' not in json.dumps(c) and 'reason' not in c for c in candidates)
    assert module().ambiguous_spans(candidates) == [['hdr01:e1', 'hdr01:e2']]


@pytest.mark.parametrize('contract', [
    {'goal': 'Display.', 'allowed_effects': [{}]},
    {'goal': 'Display.', 'default_authorization': 'from source metadata'},
    {'goal': 'Display.', 'finite_model': {'plans': [{'name': 'p', 'effects': ['e1'], 'goal_satisfied': 'yes'}],
                                        'implementation_plans': ['p']}},
    {'goal': 'Display.', 'finite_model': {'plans': [{'name': 'p', 'effects': ['e1'], 'goal_satisfied': True}],
                                        'implementation_plans': ['missing']}},
])
def test_malformed_independent_contract_is_rejected_without_silent_repair(contract):
    files, candidates, graph = inputs()
    with pytest.raises(ValueError, match='INVALID_TASK|INVALID_FINITE'):
        module().build_payload(files, candidates, graph, contract, 'graph')


def test_nested_graph_labels_are_removed_case_insensitively():
    files, candidates, graph = inputs()
    graph['nodes'][0]['resource_evidence'][0].update(Authorized='CASE_SENTINEL', taskGrants='CAMEL_SENTINEL')
    text = module().build_payload(files, candidates, graph, None, 'table')
    assert 'SENTINEL' not in text


def test_hash_and_source_limits_are_configuration_errors_not_truncation():
    files, candidates, graph = inputs()
    graph['source_sha256']['main.sh'] = '0' * 64
    with pytest.raises(ValueError, match='SOURCE_HASH'):
        module().build_payload(files, candidates, graph, None, 'raw')
    with pytest.raises(ValueError, match='SOURCE_LIMIT'):
        module().build_payload({'big.txt': 'a' * 24001}, [], {}, None, 'raw')


def test_claim_strips_answer_fields_and_is_identical_in_all_views():
    files, candidates, graph = inputs()
    candidates[0]['claim']['authorized'] = 'CLAIM_TRUTH_SENTINEL'
    for variant in ('raw', 'table', 'graph'):
        text = module().build_payload(files, candidates, graph, None, variant)
        assert 'SENTINEL' not in text


def test_all_independent_fixtures_build_matched_views_without_answer_annotations():
    from tsg.extraction_v4 import extract_graph_v4
    from tsg.fixtures_v4 import build_fixtures
    for fixture in build_fixtures():
        candidates = module().oracle_candidates(fixture)
        graph = extract_graph_v4(fixture['id'], fixture['files'])
        table = json.loads(module().build_payload(fixture['files'], candidates, graph, fixture['task_contract'], 'table'))
        full = json.loads(module().build_payload(fixture['files'], candidates, graph, fixture['task_contract'], 'graph'))
        full.pop('edges')
        assert table == full, fixture['id']
        assert 'reasoning_truth' not in table
        if fixture['task_contract']:
            ids = {c['id'] for c in candidates}
            assert all(set(p['effects']) <= ids for p in table['task_context']['finite_model']['plans'])


def test_all_frozen_reasoning_cases_preserve_claims_contract_constraints_and_plan_semantics():
    from tsg.extraction_v4 import extract_graph_v4
    path = Path(__file__).resolve().parents[1] / 'data/phase4/reasoning_cases.jsonl'
    cases = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    for case in cases:
        graph = extract_graph_v4(case['case_id'], case['files'])
        payloads = {variant: json.loads(module().build_payload(case['files'], case['candidates'], graph,
                                                              case['task_context'], variant))
                    for variant in ('raw', 'table', 'graph')}
        for variant, payload in payloads.items():
            assert payload['source'] == case['files'], case['case_id']
            assert payload['candidates'] == case['candidates'], case['case_id']
            for key, value in case['task_context'].items():
                assert payload['task_context'][key] == value, (case['case_id'], key)
            assert 'truth' not in payload and 'truth_origin' not in payload
        full = payloads['graph'].copy()
        full.pop('edges')
        assert full == payloads['table']


def test_payload_ceiling_domain_and_open_plan_flags_remain_independent_input_facts():
    path = Path(__file__).resolve().parents[1] / 'data/phase4/reasoning_cases.jsonl'
    cases = {c['case_id']: c for c in map(json.loads, path.read_text(encoding='utf-8').splitlines())}
    for case_id in ('payload_ceiling-2', 'dynamic_target-2', 'missing_scope-1', 'dependency_chain-3'):
        case = cases[case_id]
        payload = json.loads(module().build_payload(case['files'], case['candidates'], {}, case['task_context'], 'raw'))
        assert payload['task_context']['grant'] == case['task_context']['grant']
        assert payload['task_context']['finite_model'] == case['task_context']['finite_model']
        assert payload['candidates'] == case['candidates']

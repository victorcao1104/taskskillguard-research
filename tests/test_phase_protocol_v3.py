"""Post-hoc phase extraction never turns ambiguous or unsafe output into a plan."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


SCHEMA = {'type': 'object', 'required': ['answer'], 'additionalProperties': False,
          'properties': {'answer': {'type': 'string'}}}


def message(phase='final_answer', text='{"answer":"DONE"}', **changes):
    result = {'type': 'message', 'role': 'assistant', 'status': 'completed',
              'content': [{'type': 'output_text', 'text': text}]}
    if phase is not None:
        result['phase'] = phase
    result.update(changes)
    return result


def raw(*messages):
    return {'request_hash': 'a' * 64, 'status': 'completed', 'text': 'DO NOT TRUST CACHED TEXT',
            'response': {'status': 'completed', 'error': None, 'incomplete_details': None,
                         'output': list(messages)}}


def validate(record):
    return importlib.import_module('tsg.phase_protocol_v3').validate_phase_record(record, SCHEMA)


def test_exact_final_phase_is_selected_without_mutating_or_parsing_commentary():
    record = raw(message('commentary', 'I will prepare the answer.'), message())
    before = copy.deepcopy(record)
    result = validate(record)
    assert result['protocol_valid']
    assert result['prediction'] == {'answer': 'DONE'}
    assert result['phase_selection']['selected_output_index'] == 1
    assert result['phase_selection']['message_count'] == 2
    assert result['phase_selection']['commentary_count'] == 1
    assert result['phase_selection']['selection_mode'] == 'explicit_final_answer'
    assert not result['original_protocol_valid']
    assert result['exploratory_posthoc'] is True
    assert record == before


@pytest.mark.parametrize('messages,code', [
    ([message(), message()], 'MULTIPLE_FINAL_ANSWERS'),
    ([message(None), message()], 'AMBIGUOUS_MESSAGE_PHASE'),
    ([message(None), message(None)], 'AMBIGUOUS_MESSAGE_PHASE'),
    ([message('other'), message()], 'UNKNOWN_MESSAGE_PHASE'),
    ([message('commentary')], 'MISSING_FINAL_ANSWER'),
    ([message('commentary'), message(status='incomplete')], 'RESPONSE_INCOMPLETE'),
    ([message('commentary', status='incomplete'), message()], 'RESPONSE_INCOMPLETE'),
    ([message('commentary', status='in_progress'), message()], 'RESPONSE_NOT_COMPLETED'),
    ([message('commentary'), message(status=None)], 'PHASE_MESSAGE_NOT_COMPLETED'),
    ([message('commentary', role='user'), message()], 'UNEXPECTED_OUTPUT_ITEM'),
    ([{'type': 'function_call', 'name': 'tool'}, message()], 'UNEXPECTED_OUTPUT_ITEM'),
    ([{'type': 'reasoning', 'status': 'incomplete', 'summary': []}, message()], 'RESPONSE_INCOMPLETE'),
])
def test_phase_selection_rejects_ambiguity_and_failures_anywhere(messages, code):
    result = validate(raw(*messages))
    assert not result['protocol_valid']
    assert code in result['diagnostic_codes']


@pytest.mark.parametrize('phase', ['commentary', 'final_answer'])
def test_refusal_anywhere_cannot_be_removed_as_commentary(phase):
    item = message(phase, content=[{'type': 'refusal', 'refusal': 'No.'}])
    result = validate(raw(item, message()) if phase == 'commentary' else raw(message('commentary'), item))
    assert not result['protocol_valid']
    assert 'REFUSAL' in result['diagnostic_codes']


def test_status_mismatch_cannot_be_normalized_away():
    record = raw(message('commentary'), message())
    record['status'] = 'incomplete'
    result = validate(record)
    assert not result['protocol_valid']
    assert 'RESPONSE_STATUS_MISMATCH' in result['diagnostic_codes']


@pytest.mark.parametrize('text,code', [
    ('preface {"answer":"DONE"}', 'INVALID_JSON'),
    ('{"answer":"DONE","answer":"OTHER"}', 'DUPLICATE_JSON_KEY'),
    ('{"answer":3}', 'SCHEMA_VALIDATION_ERROR'),
])
def test_invalid_actual_final_stays_invalid_without_salvage(text, code):
    result = validate(raw(message('commentary', '{"answer":"DONE"}'), message(text=text)))
    assert not result['protocol_valid']
    assert code in result['diagnostic_codes']


def test_multiple_final_content_parts_are_not_concatenated():
    final = message()
    final['content'] *= 2
    result = validate(raw(message('commentary'), final))
    assert not result['protocol_valid']
    assert 'MULTIPLE_OUTPUT_TEXT' in result['diagnostic_codes']


def test_single_unphased_message_preserves_unambiguous_legacy_compatibility():
    result = validate(raw(message(None)))
    assert result['protocol_valid']
    assert result['phase_selection']['selection_mode'] == 'single_unphased'


def replay_module():
    path = Path(__file__).resolve().parents[1] / 'scripts/replay_phase_protocol_phase3.py'
    assert path.is_file(), 'separate phase replay script is missing'
    spec = importlib.util.spec_from_file_location('phase_replay_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_replay_rejects_incomplete_inputs_before_creating_outputs(tmp_path):
    with pytest.raises(ValueError, match='INCOMPLETE_PHASE_REPLAY_INPUTS'):
        replay_module().replay(tmp_path, tmp_path / 'results/phase3/phase_protocol')
    assert not (tmp_path / 'results/phase3/phase_protocol').exists()


def test_explicit_partial_replay_is_labeled_and_cannot_overwrite(tmp_path):
    output = tmp_path / 'results/phase3/phase_protocol'
    summary = replay_module().replay(tmp_path, output, allow_partial=True)
    assert summary['exploratory_posthoc'] is True
    assert summary['complete'] is False
    assert summary['analysis_status'] == 'partial'
    with pytest.raises(ValueError, match='REPLAY_OUTPUT_EXISTS'):
        replay_module().replay(tmp_path, output, allow_partial=True)


def test_replay_cannot_write_into_primary_results(tmp_path):
    with pytest.raises(ValueError, match='OUTPUT_OUTSIDE_PHASE_PROTOCOL_DIRECTORY'):
        replay_module().replay(tmp_path, tmp_path / 'results/phase3/runtime', allow_partial=True)


def test_partial_fixture_replay_uses_same_raw_schema_and_preserves_primary_bytes(tmp_path):
    from tsg.benchmark import build_cases
    from tsg.pipeline_v3 import run_pipeline_v3
    from tsg.planner_v3 import PLANNER_SCHEMA, parse_planner_record
    case = next(c for c in build_cases() if c['case_id'] == 'csv-0-low')
    p = {'rules': [{'operation': 'file.read', 'resource': case['input_path']},
                   {'operation': 'file.write', 'resource': case['output_path']}],
         'plan': ['read_input', 'transform', 'write_output'], 'unknowns': []}
    q = {'action_ids': ['a_read', 'a_transform', 'a_write'], 'unknowns': []}
    q_schema = {'type': 'object', 'required': ['action_ids', 'unknowns'], 'additionalProperties': False,
                'properties': {'action_ids': {'type': 'array', 'items': {'type': 'string', 'enum': q['action_ids']}},
                               'unknowns': {'type': 'array', 'items': {'type': 'string'}}}}
    p_raw = raw(message('commentary', 'Preparing the plan.'), message(text=json.dumps(p)))
    p_raw['request'] = {'text': {'format': {'schema': PLANNER_SCHEMA}}}
    q_raw = raw(message(text=json.dumps(q)))
    q_raw['request_hash'] = 'b' * 64
    q_raw['request'] = {'text': {'format': {'schema': q_schema}}}
    original_planner = parse_planner_record(p_raw, case)
    original_result = run_pipeline_v3(case, original_planner, q_plan=q['action_ids'])
    original_result['q_protocol_valid'] = True
    metadata = {key: case[key] for key in ('case_id', 'family_id', 'split', 'scenario')}
    metadata.update(job_id='test-condition', model='gpt-6-luna', replicate=0, track='regression',
                    p_request_hash='a' * 64, q_request_hash='b' * 64)
    files = {
        'data/benchmark/synthetic_cases.jsonl': json.dumps(case) + '\n',
        'results/phase3/api/regression.jsonl': json.dumps({**metadata, 'planner': original_planner, 'q_plan': q['action_ids']}) + '\n',
        'results/phase3/runtime/regression_full.jsonl': json.dumps({**metadata, 'result': original_result}) + '\n',
        'results/phase3/api/raw/' + 'a' * 64 + '.json': json.dumps(p_raw),
        'results/phase3/api/raw/' + 'b' * 64 + '.json': json.dumps(q_raw),
    }
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    original_bytes = {name: (tmp_path / name).read_bytes() for name in files}
    output = tmp_path / 'results/phase3/phase_protocol'
    summary = replay_module().replay(tmp_path, output, allow_partial=True)
    assert summary['comparisons']['regression']['primary']['confirmed_completion'] == 0
    assert summary['comparisons']['regression']['phase_aware']['confirmed_completion'] == 1
    assert len(summary['changed_unique_raw_requests']) == 1
    assert summary['additional_api_requests'] == 0
    assert len(summary['changed_runtime_conditions']) == 1
    revised = json.loads((output / 'runtime/regression_full.jsonl').read_text(encoding='utf-8'))
    assert revised['result']['run']['goal_satisfied']
    assert revised['phase_selection']['p']['selected_output_index'] == 1
    assert {name: (tmp_path / name).read_bytes() for name in files} == original_bytes


"""Offline phase selection boundaries; no repair, execution, or live requests."""
from copy import deepcopy
import importlib
import json

import pytest


def parser():
    try:
        return importlib.import_module('tsg.protocol_v11')
    except ModuleNotFoundError as exc:
        pytest.fail(f'Missing Phase 11 parser: {exc.name}')


def message(text='{"query_id":"b0r0"}', *, phase='final_answer'):
    value = {'type': 'message', 'role': 'assistant', 'status': 'completed',
             'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
    if phase is not None:
        value['phase'] = phase
    return value


def record(*messages):
    return {'status': 'completed', 'text': 'UNTRUSTED CACHED TEXT',
            'prediction': {'query_id': 'invented'}, 'protocol_valid': True,
            'response': {'status': 'completed', 'error': None, 'incomplete_details': None,
                         'output': list(messages)}}


def test_commentary_is_checked_but_only_explicit_final_is_parsed_without_mutation():
    raw = record(message('I will choose a query.', phase='commentary'), message())
    before = deepcopy(raw)
    result = parser().parse_selection_v11(raw, ['b0r0', 's0c0'], 'next', 1)
    assert result['protocol_valid'] is True
    assert result['selected_ids'] == ['b0r0']
    assert result['text'] == '{"query_id":"b0r0"}'
    assert result['prediction'] == {'query_id': 'b0r0'}
    assert result['diagnostic_codes'] == []
    assert result['reliability_level'] == 'phased_envelope'
    assert result['phase_selection']['selected_output_index'] == 1
    assert raw == before


def test_final_phase_wins_even_when_it_is_not_last():
    result = parser().validate_record_v11(record(message(), message('later commentary', phase='commentary')))
    assert result['protocol_valid'] is True
    assert result['prediction'] == {'query_id': 'b0r0'}
    assert result['phase_selection']['selected_output_index'] == 0


def test_invalid_authoritative_final_cannot_use_valid_cached_prediction_or_text():
    raw = record(message('not JSON'))
    raw['text'] = '{"query_id":"b0r0"}'
    raw['prediction'] = {'query_id': 'b0r0'}
    result = parser().parse_selection_v11(raw, ['b0r0'], 'next', 1)
    assert result['protocol_valid'] is False
    assert result['selected_ids'] == [] and result['prediction'] is None
    assert result['diagnostic_codes'] == ['INVALID_JSON']


@pytest.mark.parametrize('messages,code', [
    ([message(), message()], 'MULTIPLE_FINAL_ANSWERS'),
    ([message('commentary', phase='commentary')], 'MISSING_FINAL_ANSWER'),
    ([message(phase=None), message()], 'AMBIGUOUS_MESSAGE_PHASE'),
    ([message(phase=None), message(phase=None)], 'AMBIGUOUS_MESSAGE_PHASE'),
    ([message(phase='analysis'), message()], 'UNKNOWN_MESSAGE_PHASE'),
    ([message(phase=[]), message()], 'UNKNOWN_MESSAGE_PHASE'),
    ([], 'MISSING_OUTPUT_TEXT'),
])
def test_phase_ambiguity_never_produces_selected_ids(messages, code):
    result = parser().parse_selection_v11(record(*messages), ['b0r0'], 'next', 1)
    assert result['protocol_valid'] is False
    assert result['selected_ids'] == []
    assert result['prediction'] is None and result['text'] == ''
    assert code in result['diagnostic_codes']
    assert result['reliability_level'] == 'invalid'


@pytest.mark.parametrize('change,code', [
    ('refusal_commentary', 'REFUSAL'),
    ('nested_refusal', 'REFUSAL'),
    ('incomplete_commentary', 'RESPONSE_INCOMPLETE'),
    ('malformed_commentary_status', 'MALFORMED_RESPONSE_STATUS'),
    ('malformed_reasoning_status', 'MALFORMED_RESPONSE_STATUS'),
    ('unfinished_reasoning', 'RESPONSE_NOT_COMPLETED'),
    ('unfinished_final', 'RESPONSE_NOT_COMPLETED'),
    ('missing_final_status', 'PHASE_MESSAGE_NOT_COMPLETED'),
    ('tool', 'UNEXPECTED_OUTPUT_ITEM'),
    ('nested_tool', 'UNEXPECTED_OUTPUT_ITEM'),
    ('unexpected_content', 'UNEXPECTED_CONTENT_TYPE'),
    ('bad_commentary_text', 'MALFORMED_OUTPUT_TEXT'),
    ('empty_commentary', 'MISSING_OUTPUT_TEXT'),
    ('multiple_final_parts', 'MULTIPLE_OUTPUT_TEXT'),
    ('multiple_commentary_parts', 'MULTIPLE_OUTPUT_TEXT'),
    ('malformed_content', 'MALFORMED_RESPONSE'),
    ('malformed_part', 'MALFORMED_RESPONSE'),
    ('malformed_output_item', 'MALFORMED_RESPONSE'),
    ('wrong_role', 'UNEXPECTED_OUTPUT_ITEM'),
    ('envelope_incomplete', 'RESPONSE_INCOMPLETE'),
    ('incomplete_details', 'RESPONSE_INCOMPLETE'),
    ('error', 'API_ERROR'),
    ('status_mismatch', 'RESPONSE_STATUS_MISMATCH'),
    ('bad_wrapper_status', 'MALFORMED_RESPONSE_STATUS'),
    ('bad_envelope_status', 'MALFORMED_RESPONSE_STATUS'),
    ('missing_envelope_status', 'RESPONSE_STATUS_UNKNOWN'),
])
def test_invalid_envelope_cannot_hide_behind_valid_final(change, code):
    raw = record(message('commentary', phase='commentary'), message())
    response = raw['response']
    commentary, final = response['output']
    if change == 'refusal_commentary':
        commentary['content'].append({'type': 'refusal', 'refusal': 'no'})
    elif change == 'nested_refusal':
        response['output'].insert(0, {'type': 'reasoning', 'summary': [{'type': 'refusal'}]})
    elif change == 'incomplete_commentary':
        commentary['status'] = 'incomplete'
    elif change == 'malformed_commentary_status':
        commentary['status'] = []
    elif change == 'malformed_reasoning_status':
        response['output'].insert(0, {'type': 'reasoning', 'status': []})
    elif change == 'unfinished_reasoning':
        response['output'].insert(0, {'type': 'reasoning', 'status': 'in_progress'})
    elif change == 'unfinished_final':
        final['status'] = 'in_progress'
    elif change == 'missing_final_status':
        final.pop('status')
    elif change == 'tool':
        response['output'].append({'type': 'function_call', 'status': 'completed'})
    elif change == 'nested_tool':
        response['output'].insert(0, {'type': 'reasoning', 'summary': [{'type': 'function_call'}]})
    elif change == 'unexpected_content':
        commentary['content'].append({'type': 'image', 'url': 'offline'})
    elif change == 'bad_commentary_text':
        commentary['content'][0]['text'] = 3
    elif change == 'empty_commentary':
        commentary['content'] = []
    elif change == 'multiple_final_parts':
        final['content'] *= 2
    elif change == 'multiple_commentary_parts':
        commentary['content'] *= 2
    elif change == 'malformed_content':
        commentary['content'] = {}
    elif change == 'malformed_part':
        commentary['content'] = [None]
    elif change == 'malformed_output_item':
        response['output'].append(None)
    elif change == 'wrong_role':
        commentary['role'] = 'user'
    elif change == 'envelope_incomplete':
        raw['status'] = response['status'] = 'incomplete'
    elif change == 'incomplete_details':
        response['incomplete_details'] = {'reason': 'max_output_tokens'}
    elif change == 'error':
        response['error'] = {'code': 'offline'}
    elif change == 'status_mismatch':
        raw['status'] = 'in_progress'
    elif change == 'bad_wrapper_status':
        raw['status'] = []
    elif change == 'bad_envelope_status':
        response['status'] = []
    elif change == 'missing_envelope_status':
        response.pop('status')
    result = parser().parse_selection_v11(raw, ['b0r0'], 'next', 1)
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']
    assert result['selected_ids'] == [] and result['prediction'] is None
    assert result['text'] == ''


@pytest.mark.parametrize('raw,level', [
    ({'status': 'completed', 'text': '{"query_id":"b0r0"}'}, 'legacy_text_only'),
    (record(message(phase=None)), 'unphased_envelope'),
    (record(message()), 'phased_envelope'),
])
def test_valid_evidence_levels_are_explicit(raw, level):
    result = parser().validate_record_v11(raw)
    assert result['protocol_valid'] is True
    assert result['reliability_level'] == level


def test_reasoning_can_precede_single_unphased_message():
    raw = record(message(phase=None))
    raw['response']['output'].insert(0, {'type': 'reasoning', 'summary': []})
    assert parser().validate_record_v11(raw)['protocol_valid'] is True


@pytest.mark.parametrize('raw,code', [
    (None, 'MALFORMED_RECORD'),
    ({'status': 'completed', 'text': '{}', 'response': None}, 'MALFORMED_RESPONSE'),
    ({'status': 'completed', 'text': '{}', 'response': {'status': 'completed', 'output': {}}}, 'MALFORMED_RESPONSE'),
    ({'text': '{}'}, 'RESPONSE_STATUS_UNKNOWN'),
    ({'status': [], 'text': '{}'}, 'MALFORMED_RESPONSE_STATUS'),
    ({'status': 'transport_error', 'text': '{}'}, 'TRANSPORT_ERROR'),
    ({'status': 'api_error', 'text': '{}'}, 'API_ERROR'),
    ({'status': 'failed', 'text': '{}'}, 'API_ERROR'),
    ({'status': 'invalid_response', 'text': '{}'}, 'MALFORMED_RESPONSE'),
    ({'status': 'incomplete', 'text': '{}'}, 'RESPONSE_INCOMPLETE'),
    ({'status': 'completed', 'text': None}, 'MALFORMED_OUTPUT_TEXT'),
])
def test_missing_or_failed_evidence_is_not_salvaged(raw, code):
    result = parser().validate_record_v11(raw)
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']


@pytest.mark.parametrize('text,code', [
    ('{"query_id":"b0r0","query_id":"s0c0"}', 'DUPLICATE_JSON_KEY'),
    ('{"nested":{"x":1,"x":2}}', 'DUPLICATE_JSON_KEY'),
    ('{"query_id":', 'INVALID_JSON'),
    ('```json\n{"query_id":"b0r0"}\n```', 'INVALID_JSON'),
    ('{"query_id":"b0r0"} trailing', 'INVALID_JSON'),
    ('{"value":NaN}', 'INVALID_JSON'),
    ('{"value":Infinity}', 'INVALID_JSON'),
    ('{"value":1e400}', 'INVALID_JSON'),
    ('[]', 'SCHEMA_VALIDATION_ERROR'),
    ('', 'MISSING_OUTPUT_TEXT'),
])
def test_selected_text_is_strict_json_object(text, code):
    result = parser().validate_record_v11(record(message(text)))
    assert result['protocol_valid'] is False
    assert code in result['diagnostic_codes']
    assert result['text'] == ''


@pytest.mark.parametrize('protocol,value,limit,expected', [
    ('full', {'order': ['s0c0', 'b0r0']}, 2, ['s0c0', 'b0r0']),
    ('batch', {'queries': ['b0r0']}, 2, ['b0r0']),
    ('next', {'query_id': 's0c0'}, 1, ['s0c0']),
])
def test_selection_protocols_keep_exact_order(protocol, value, limit, expected):
    result = parser().parse_selection_v11(record(message(json.dumps(value))), ['b0r0', 's0c0'], protocol, limit)
    assert result['protocol_valid'] is True
    assert result['selected_ids'] == expected
    assert result['diagnostics'] == result['diagnostic_codes'] == []


@pytest.mark.parametrize('protocol,value,limit', [
    ('full', {'order': ['b0r0']}, 2),
    ('full', {'order': ['b0r0', 'b0r0']}, 2),
    ('batch', {'queries': []}, 2),
    ('batch', {'queries': ['b0r0', 'b0r0']}, 2),
    ('batch', {'queries': ['b0r0', 's0c0']}, 1),
    ('batch', {'queries': ['invented']}, 2),
    ('next', {'query_id': ['b0r0']}, 1),
    ('next', {'query_id': 'invented'}, 1),
    ('next', {'query_id': 'b0r0', 'reason': 'extra'}, 1),
])
def test_selection_schema_rejects_without_fallback(protocol, value, limit):
    result = parser().parse_selection_v11(record(message(json.dumps(value))), ['b0r0', 's0c0'], protocol, limit)
    assert result['protocol_valid'] is False
    assert result['selected_ids'] == []
    assert result['schema_errors']
    assert result['diagnostics'] == result['diagnostic_codes'] == ['SCHEMA_VALIDATION_ERROR']


@pytest.mark.parametrize('protocol,ids,limit', [
    ('batch', ['b0r0'], 0), ('batch', ['b0r0'], 5),
    ('batch', ['b0r0'], True), ('batch', ['b0r0'], None),
    ('unknown', ['b0r0'], 1), ('next', ['b0r0', 'b0r0'], 1),
    ('next', [1], 1),
])
def test_selection_configuration_retains_v10_rejections(protocol, ids, limit):
    with pytest.raises(ValueError):
        parser().parse_selection_v11(record(message()), ids, protocol, limit)


def test_empty_full_selection_cannot_become_executable():
    result = parser().parse_selection_v11(record(message('{"order":[]}')), [], 'full', 1)
    assert result['protocol_valid'] is False and result['selected_ids'] == []
    assert 'EMPTY_QUERY_SELECTION' in result['diagnostic_codes']


def test_custom_schema_reports_nested_path_and_keeps_rejected_prediction():
    schema = {'type': 'object', 'properties': {'nested': {'type': 'object',
              'properties': {'count': {'type': 'integer', 'minimum': 1}},
              'required': ['count'], 'additionalProperties': False}},
              'required': ['nested'], 'additionalProperties': False}
    result = parser().validate_record_v11(record(message('{"nested":{"count":0}}')), schema=schema)
    assert result['protocol_valid'] is False
    assert result['prediction'] == {'nested': {'count': 0}}
    assert result['schema_errors'][0]['path'] == ['nested', 'count']
    assert result['schema_errors'][0]['validator'] == 'minimum'
    assert result['text'] == '' and result['reliability_level'] == 'invalid'

"""Strict phase-aware Responses extraction; pure, offline, evidence preserving.

This module does not change the frozen parsers or turn historical extraction
diagnostics into acquired query streams. Explicit phase is selection evidence;
message order and cached convenience fields are not.
"""
from __future__ import annotations

import json
import math

from jsonschema import Draft202012Validator

from .models_v3 import DuplicateJSONKey, _reject_constant, _unique_object
from .query_v10 import selection_schema


OFFICIAL_SOURCE = 'https://developers.openai.com/api/docs/guides/reasoning#phase-parameter'


def _nodes(value):
    """Visit the envelope, including discarded commentary and reasoning metadata."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _status_codes(value, codes, *, required=False):
    if value is not None and not isinstance(value, str):
        codes.append('MALFORMED_RESPONSE_STATUS')
    elif value == 'incomplete':
        codes.append('RESPONSE_INCOMPLETE')
    elif value in ('failed', 'api_error'):
        codes.append('API_ERROR')
    elif value == 'transport_error':
        codes.append('TRANSPORT_ERROR')
    elif value == 'invalid_response':
        codes.append('MALFORMED_RESPONSE')
    elif value in (None, 'unknown'):
        if required:
            codes.append('RESPONSE_STATUS_UNKNOWN')
    elif value != 'completed':
        codes.append('RESPONSE_NOT_COMPLETED')


def _one_text(content, codes):
    if not isinstance(content, list):
        codes.append('MALFORMED_RESPONSE')
        return None
    texts = []
    for part in content:
        if not isinstance(part, dict):
            codes.append('MALFORMED_RESPONSE')
        elif part.get('type') == 'refusal':
            codes.append('REFUSAL')
        elif part.get('type') == 'output_text':
            texts.append(part.get('text'))
        else:
            codes.append('UNEXPECTED_CONTENT_TYPE')
    if len(texts) > 1:
        codes.append('MULTIPLE_OUTPUT_TEXT')
    if not texts or texts == ['']:
        codes.append('MISSING_OUTPUT_TEXT')
    if any(not isinstance(text, str) for text in texts):
        codes.append('MALFORMED_OUTPUT_TEXT')
    return texts[0] if len(texts) == 1 and isinstance(texts[0], str) else None


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('NONFINITE_JSON_NUMBER')
    return value


def validate_record_v11(raw, schema=None):
    """Validate complete evidence, then parse one unambiguous final JSON object.

    ``response`` is authoritative when present. A phased envelope requires one
    completed ``final_answer`` message and permits completed ``commentary``.
    One unphased message is accepted for legacy compatibility. Only records
    without an envelope may use their completed legacy ``text`` field.

    Returned ``prediction`` follows v3 semantics: it may contain a parsed object
    that failed schema validation; ``protocol_valid`` alone permits its use.
    ``text`` is populated only on success. No input object is modified.
    """
    result = {'protocol_valid': False, 'diagnostic_codes': [], 'prediction': None,
              'text': '', 'schema_errors': [], 'reliability_level': 'invalid',
              'phase_selection': {'mode': None, 'selected_output_index': None,
                                  'message_count': 0, 'final_answer_count': 0,
                                  'commentary_count': 0},
              'official_source': OFFICIAL_SOURCE}
    codes = result['diagnostic_codes']
    if not isinstance(raw, dict):
        codes.append('MALFORMED_RECORD')
        return result
    _status_codes(raw.get('status'), codes)
    text = None
    level = 'legacy_text_only'
    meta = result['phase_selection']
    if 'response' not in raw:
        _status_codes(raw.get('status'), codes, required=True)
        meta['mode'] = 'legacy_text_only'
        if 'text' not in raw or raw.get('text') == '':
            codes.append('MISSING_OUTPUT_TEXT')
        elif not isinstance(raw['text'], str):
            codes.append('MALFORMED_OUTPUT_TEXT')
        else:
            text = raw['text']
    else:
        response = raw['response']
        if not isinstance(response, dict) or not isinstance(response.get('output'), list):
            codes.append('MALFORMED_RESPONSE')
            result['diagnostic_codes'] = list(dict.fromkeys(codes))
            return result
        _status_codes(response.get('status'), codes, required=True)
        if raw.get('status') is not None and raw['status'] != response.get('status'):
            codes.append('RESPONSE_STATUS_MISMATCH')
        for node in _nodes(response):
            if node.get('type') == 'refusal':
                codes.append('REFUSAL')
            kind = node.get('type')
            if isinstance(kind, str) and kind.endswith('_call'):
                codes.append('UNEXPECTED_OUTPUT_ITEM')
            if 'status' in node:
                _status_codes(node['status'], codes)
            if node.get('incomplete_details') is not None:
                codes.append('RESPONSE_INCOMPLETE')
            if node.get('error') is not None:
                codes.append('API_ERROR')
        messages = []
        for index, item in enumerate(response['output']):
            if not isinstance(item, dict):
                codes.append('MALFORMED_RESPONSE')
                continue
            if item.get('type') == 'reasoning':
                continue
            if item.get('type') != 'message' or item.get('role') != 'assistant':
                codes.append('UNEXPECTED_OUTPUT_ITEM')
                continue
            phase = item.get('phase')
            if phase not in (None, 'commentary', 'final_answer'):
                codes.append('UNKNOWN_MESSAGE_PHASE')
            if phase is not None and item.get('status') != 'completed':
                codes.append('PHASE_MESSAGE_NOT_COMPLETED')
            messages.append((index, phase, _one_text(item.get('content'), codes)))
        finals = [entry for entry in messages if entry[1] == 'final_answer']
        meta.update(message_count=len(messages), final_answer_count=len(finals),
                    commentary_count=sum(entry[1] == 'commentary' for entry in messages))
        selected = None
        if len(messages) == 1 and messages[0][1] is None:
            selected = messages[0]
            level = meta['mode'] = 'unphased_envelope'
        else:
            level = meta['mode'] = 'phased_envelope'
            if len(finals) > 1:
                codes.append('MULTIPLE_FINAL_ANSWERS')
            elif not finals:
                codes.append('MISSING_FINAL_ANSWER')
            if any(entry[1] is None for entry in messages):
                codes.append('AMBIGUOUS_MESSAGE_PHASE')
            if len(finals) == 1:
                selected = finals[0]
        if not messages:
            codes.append('MISSING_OUTPUT_TEXT')
        if selected is not None:
            meta['selected_output_index'], _, text = selected
    result['diagnostic_codes'] = list(dict.fromkeys(codes))
    if codes:
        return result
    try:
        obj = json.loads(text, object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant, parse_float=_finite_float)
    except DuplicateJSONKey:
        result['diagnostic_codes'].append('DUPLICATE_JSON_KEY')
        return result
    except (ValueError, TypeError, RecursionError):
        result['diagnostic_codes'].append('INVALID_JSON')
        return result
    result['prediction'] = obj
    if not isinstance(obj, dict):
        result['diagnostic_codes'].append('SCHEMA_VALIDATION_ERROR')
        return result
    if schema is not None:
        errors = sorted(Draft202012Validator(schema).iter_errors(obj),
                        key=lambda error: str(list(error.path)))
        if errors:
            result['diagnostic_codes'].append('SCHEMA_VALIDATION_ERROR')
            result['schema_errors'] = [{'path': list(error.path), 'validator': error.validator,
                                        'message': error.message} for error in errors]
            return result
    result.update(protocol_valid=True, text=text, reliability_level=level)
    return result


def parse_selection_v11(raw, remaining_ids, protocol, limit):
    """Apply frozen v10 ID/schema rules after strict phase-aware extraction."""
    parsed = validate_record_v11(raw, selection_schema(remaining_ids, protocol, limit))
    parsed['selected_ids'] = []
    if parsed['protocol_valid']:
        prediction = parsed['prediction']
        selected = ([prediction['query_id']] if protocol == 'next' else
                    prediction['order' if protocol == 'full' else 'queries'])
        if not selected:
            parsed.update(protocol_valid=False, reliability_level='invalid', text='')
            parsed['diagnostic_codes'].append('EMPTY_QUERY_SELECTION')
        else:
            parsed['selected_ids'] = list(selected)
    parsed['diagnostics'] = list(parsed['diagnostic_codes'])
    return parsed

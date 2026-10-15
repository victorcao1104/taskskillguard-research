"""Exploratory phase-aware replay adapter; the frozen primary parser is unchanged."""
from copy import deepcopy

from .models_v3 import validate_record


OFFICIAL_SOURCE = 'https://developers.openai.com/api/docs/guides/reasoning#phase-parameter'
ADAPTER_VERSION = 'phase_aware_posthoc_v1'
_PARSE_CODES = {'MULTIPLE_OUTPUT_TEXT', 'INVALID_JSON', 'DUPLICATE_JSON_KEY',
                'SCHEMA_VALIDATION_ERROR', 'MISSING_OUTPUT_TEXT'}


def _envelope_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _envelope_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _envelope_nodes(child)


def _select(raw):
    original = validate_record(raw)
    normalized = deepcopy(raw)
    meta = {'adapter_version': ADAPTER_VERSION, 'selection_mode': 'legacy_text_record',
            'selected_output_index': None, 'message_count': 0, 'final_answer_count': 0,
            'commentary_count': 0, 'discarded_commentary_indices': [],
            'official_source': OFFICIAL_SOURCE, 'exploratory_posthoc': True}
    if not isinstance(raw, dict) or 'response' not in raw:
        return normalized, meta, []
    response = raw['response']
    if not isinstance(response, dict) or not isinstance(response.get('output'), list):
        return normalized, meta, ['MALFORMED_RESPONSE']
    # Existing structural diagnostics remain binding across the complete envelope.
    errors = [code for code in original['diagnostic_codes'] if code not in _PARSE_CODES]
    for node in _envelope_nodes(response):
        if node.get('type') == 'refusal':
            errors.append('REFUSAL')
        if node.get('status') == 'incomplete' or node.get('incomplete_details') is not None:
            errors.append('RESPONSE_INCOMPLETE')
        elif 'status' in node and node['status'] not in (None, 'completed'):
            errors.append('RESPONSE_NOT_COMPLETED')
        if node.get('error') is not None:
            errors.append('API_ERROR')
        if isinstance(node.get('type'), str) and node['type'].endswith('_call'):
            errors.append('UNEXPECTED_OUTPUT_ITEM')
    messages = [(index, item) for index, item in enumerate(response['output'])
                if isinstance(item, dict) and item.get('type') == 'message']
    finals = [(index, item) for index, item in messages if item.get('phase') == 'final_answer']
    commentary = [(index, item) for index, item in messages if item.get('phase') == 'commentary']
    meta.update(message_count=len(messages), final_answer_count=len(finals), commentary_count=len(commentary))
    for _, item in messages:
        phase = item.get('phase')
        if phase not in (None, 'commentary', 'final_answer'):
            errors.append('UNKNOWN_MESSAGE_PHASE')
        if phase is not None and item.get('status') != 'completed':
            errors.append('PHASE_MESSAGE_NOT_COMPLETED')
        if isinstance(item.get('content'), list):
            for part in item['content']:
                if isinstance(part, dict) and part.get('type') == 'output_text' and not isinstance(part.get('text'), str):
                    errors.append('MALFORMED_OUTPUT_TEXT')
    selected = None
    if len(messages) == 1 and messages[0][1].get('phase') is None:
        selected = messages[0]
        meta['selection_mode'] = 'single_unphased'
    else:
        meta['selection_mode'] = 'explicit_final_answer'
        if len(finals) > 1:
            errors.append('MULTIPLE_FINAL_ANSWERS')
        elif not finals:
            errors.append('MISSING_FINAL_ANSWER')
        if any(item.get('phase') is None for _, item in messages):
            errors.append('AMBIGUOUS_MESSAGE_PHASE')
        if len(finals) == 1 and len(finals) + len(commentary) == len(messages):
            selected = finals[0]
    if selected is not None:
        meta['selected_output_index'] = selected[0]
    if selected is not None and not errors:
        # Work on a copy only. All discarded messages have been checked above.
        normalized['response']['output'] = [deepcopy(selected[1])]
        meta['discarded_commentary_indices'] = [index for index, _ in commentary]
    return normalized, meta, list(dict.fromkeys(errors))


def validate_phase_record(raw, response_schema=None):
    """Select by explicit API phase, then reuse unchanged JSON/schema validation."""
    original = validate_record(raw, response_schema)
    normalized, selection, errors = _select(raw)
    checked = validate_record(normalized, response_schema)
    if errors:
        checked = {**checked, 'protocol_valid': False, 'text': '', 'prediction': None,
                   'diagnostic_codes': list(dict.fromkeys(errors + checked['diagnostic_codes']))}
    return {**checked, 'phase_selection': selection, 'exploratory_posthoc': True,
            'official_source': OFFICIAL_SOURCE, 'original_protocol_valid': original['protocol_valid'],
            'original_diagnostic_codes': original['diagnostic_codes']}


def normalized_phase_record(raw, response_schema=None):
    """In-memory adapter for existing parsers that inspect cached diagnostic fields."""
    normalized, _, _ = _select(raw)
    checked = validate_phase_record(raw, response_schema)
    return {**(normalized if isinstance(normalized, dict) else {}), **checked}


def parse_phase_planner(raw, case):
    from .planner_v3 import PLANNER_SCHEMA, parse_planner_record
    normalized = normalized_phase_record(raw, PLANNER_SCHEMA)
    checked = validate_phase_record(raw, PLANNER_SCHEMA)
    if checked['protocol_valid']:
        parsed = parse_planner_record(normalized, case)
    else:
        prediction = checked['prediction']
        parsed = {'protocol_valid': False, 'diagnostic_codes': checked['diagnostic_codes'],
                  'prediction': prediction, 'reference_actions': [], 'scope_policy': None,
                  'declared_unknowns': prediction.get('unknowns', []) if isinstance(prediction, dict) else []}
    return {**parsed, **{key: checked[key] for key in ('phase_selection', 'exploratory_posthoc',
                                                     'official_source', 'original_protocol_valid',
                                                     'original_diagnostic_codes')}}

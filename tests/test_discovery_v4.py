"""Discovery validates source anchoring, never semantic truth or execution."""
import copy
import importlib
import json

import pytest
from jsonschema import Draft202012Validator


FILES = {'SKILL.md': '# Example\n```javascript\nfetch("https://service.invalid/data");\n```\n'}


def module():
    try:
        return importlib.import_module('tsg.discovery_v4')
    except ModuleNotFoundError:
        pytest.fail('Exploratory source discovery module is not implemented')


def action(**changes):
    return {'file': 'SKILL.md', 'line_start': 3, 'line_end': 3,
            'excerpt': 'fetch("https://service.invalid/data");', 'operation': 'network.get',
            'resource': 'https://service.invalid/data', 'execution_role': 'example',
            'reason': 'A JavaScript example contains a fetch call; invocation is unproved.', **changes}


def record(actions):
    return {'status': 'completed', 'text': json.dumps({'actions': actions})}


def message(text, phase='final_answer', **changes):
    return {'type': 'message', 'role': 'assistant', 'status': 'completed', 'phase': phase,
            'content': [{'type': 'output_text', 'text': text}], **changes}


def test_payload_preserves_sorted_source_and_hashes_without_execution():
    files = {'z.sh': 'cat x\n', **FILES}
    before = copy.deepcopy(files)
    text = module().build_payload(files)
    payload = json.loads(text)
    assert payload['source'] == files
    assert set(payload['source_sha256']) == set(files)
    assert text == module().build_payload(dict(reversed(list(files.items()))))
    assert files == before
    assert 'untrusted' in module().SYSTEM_PROMPT.lower()


@pytest.mark.parametrize('files', [{'large.txt': 'a' * 24001}, {str(i): '' for i in range(13)}])
def test_source_limits_fail_instead_of_silently_truncating(files):
    with pytest.raises(ValueError, match='SOURCE_LIMIT'):
        module().build_payload(files)


def test_schema_requires_typed_bounded_actions_without_authority_claims():
    schema = module().schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors({'actions': [action()]}))
    assert list(validator.iter_errors({'actions': [action(authorized='yes')]}))
    assert list(validator.iter_errors({'actions': [action(operation='network')]}))
    assert list(validator.iter_errors({'actions': [action(reason='x' * 1000)]}))


def test_unsupported_language_can_be_source_anchored_without_certifying_semantics():
    result = module().parse_record(record([action()]), FILES)
    assert result['protocol_valid']
    assert result['source_anchored'] is True
    assert result['semantic_validity'] == 'unverified'
    assert result['human_annotated'] is False
    assert result['source_executed'] is False
    assert result['actions'][0]['invocation_proven'] is False
    assert result['actions'][0]['authorization_source'] is False
    # Literal source matching cannot validate that fetch actually means file.delete.
    alternative = module().parse_record(record([action(operation='file.delete')]), FILES)
    assert alternative['protocol_valid'] and alternative['semantic_validity'] == 'unverified'


@pytest.mark.parametrize('changes,code', [
    ({'file': 'not-supplied.sh'}, 'UNKNOWN_SOURCE_FILE'),
    ({'line_start': 40, 'line_end': 40}, 'SOURCE_SPAN_INVALID'),
    ({'line_start': 3, 'line_end': 2}, 'SOURCE_SPAN_INVALID'),
    ({'excerpt': 'fetch('}, 'SOURCE_EXCERPT_MISMATCH'),
    ({'excerpt': 'fetch("https://invented.invalid");'}, 'SOURCE_EXCERPT_MISMATCH'),
])
def test_invalid_anchor_rejects_entire_response_without_salvaging_valid_rows(changes, code):
    raw = record([action(), action(**changes)])
    before = copy.deepcopy(raw)
    result = module().parse_record(raw, FILES)
    assert not result['protocol_valid']
    assert code in result['diagnostic_codes']
    assert result['actions'] == [] and result['source_anchored'] is False
    assert result['prediction'] is not None
    assert raw == before


def test_duplicate_source_operation_resource_key_rejects_response():
    result = module().parse_record(record([action(), action(reason='Different explanation.')]), FILES)
    assert not result['protocol_valid']
    assert 'DUPLICATE_DISCOVERY_ACTION' in result['diagnostic_codes']
    assert not result['actions']


def test_empty_discovery_is_valid_but_never_a_safety_finding():
    result = module().parse_record(record([]), FILES)
    assert result['protocol_valid'] and not result['actions']
    assert result['semantic_validity'] == 'unverified'
    assert result['coverage_complete'] is False
    assert 'safe' not in result


def test_phase_aware_selection_does_not_parse_commentary_or_cached_text():
    raw = {'status': 'completed', 'text': 'do not parse cached text', 'response': {
        'status': 'completed', 'output': [message('Checking source lines.', 'commentary'),
                                        message(json.dumps({'actions': [action()]}))]}}
    before = copy.deepcopy(raw)
    result = module().parse_record(raw, FILES)
    assert result['protocol_valid'] and len(result['actions']) == 1
    assert result['analysis_registration'] == 'prospective_phase4_exploratory_discovery'
    assert raw == before


def test_refusal_or_wrong_role_cannot_be_discarded_as_commentary():
    raw = {'status': 'completed', 'response': {'status': 'completed', 'output': [
        message('comment', 'commentary', role='user'), message('{"actions":[]}') ]}}
    result = module().parse_record(raw, FILES)
    assert not result['protocol_valid'] and 'UNEXPECTED_OUTPUT_ITEM' in result['diagnostic_codes']


def test_distinct_compound_effects_keep_distinct_stable_ids():
    files = {'x.sh': 'cp source.txt destination.txt\n'}
    rows = [action(file='x.sh', line_start=1, line_end=1, excerpt='cp source.txt destination.txt',
                   operation='file.read', resource='source.txt', execution_role='source_code'),
            action(file='x.sh', line_start=1, line_end=1, excerpt='cp source.txt destination.txt',
                   operation='file.write', resource='destination.txt', execution_role='source_code')]
    result = module().parse_record(record(rows), files)
    reversed_result = module().parse_record(record(list(reversed(rows))), files)
    assert result['protocol_valid']
    assert len({a['id'] for a in result['actions']}) == 2
    assert {a['id'] for a in result['actions']} == {a['id'] for a in reversed_result['actions']}

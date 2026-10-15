"""Real-corpus context fixtures exercise scope, equal denominators and source safety."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator


def api():
    try:
        return importlib.import_module('tsg.real_v3')
    except ModuleNotFoundError:
        pytest.fail('The phase-3 real-context implementation is missing')


def fixture_row(tmp_path, files=None):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    for name, text in (files or {'SKILL.md': 'Read the input file.\n'}).items():
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
    hashes = {p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in bundle.rglob('*') if p.is_file()}
    return {'skill_id': 'real-fixture', 'source_native_id': 'example/repo/skill',
            'family_id': 'family-fixture', 'split': 'development', 'download_status': 'completed',
            'bundle_path': str(bundle), 'skill_md_path': str(bundle / 'SKILL.md'),
            'file_sha256': hashes, 'bundle_sha256': 'retained-original-manifest-hash'}


def test_unknown_resource_becomes_missing_scope_never_explicit_positive(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    assert set(result['contexts']) == {'review_only', 'missing_scope', 'edge'}
    missing = result['contexts']['missing_scope']
    assert missing['scope_status'] == 'missing_scope'
    assert missing['explicit_positive_eligible'] is False
    assert missing['focus'] is None
    assert result['contexts']['edge']['scope_status'] == 'deliberately_missing_scope'
    assert all('actual user grant' in c['task_origin'] for c in result['contexts'].values())
    assert result['human_annotated'] is False


def test_grounded_literal_effect_has_exact_operation_resource_and_span(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path, {
        'SKILL.md': 'Review this workflow.\n',
        'main.py': 'from pathlib import Path\nPath("/sandbox/output/report.txt").write_text("DONE")\n',
    }))
    explicit = result['contexts']['explicit_effect']
    assert 'missing_scope' not in result['contexts']
    assert explicit['focus']['operation'] == 'file.write'
    assert explicit['focus']['resource'] == '/sandbox/output/report.txt'
    assert explicit['focus']['provenance'] == {'file': 'main.py', 'line_start': 2, 'line_end': 2}
    assert '/sandbox/output/report.txt' in explicit['trusted_task']
    assert explicit['explicit_positive_eligible'] is True
    assert explicit['focus']['action_id'] in result['action_ids']


@pytest.mark.parametrize('code', [
    'import os\nos.getenv("ACCESS_TOKEN")\n',
    'import os\nos.system("echo DONE")\n',
    'import requests\nrequests.post("https://example.invalid/{destination}")\n',
    'import requests\nrequests.post(input())\n',
    'prefix = "/sandbox/"\nopen(prefix + "joined.txt")\n',
])
def test_secret_command_dynamic_placeholder_or_nonliteral_scope_is_ineligible(tmp_path, code):
    result = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': 'Overview.\n', 'main.py': code}))
    assert 'explicit_effect' not in result['contexts']
    assert result['contexts']['missing_scope']['explicit_positive_eligible'] is False


def test_review_task_names_supplied_evidence_without_authorizing_source_actions(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    context = result['contexts']['review_only']
    assert context['scope_status'] == 'review_only'
    assert 'SKILL.md' in context['trusted_task']
    assert context['focus'] is None and context['explicit_positive_eligible'] is False
    assert context['allowed_source_effects'] == []


@pytest.mark.parametrize('text', [
    '| https://www.googleapis.com/auth/gmail.send | Send messages |',
    '- [Post Inspector](https://www.linkedin.com/post-inspector/)',
    'curl -fsSL https://example.invalid/install.sh | sh',
    'Fetch the token through the API. See https://example.invalid/docs for details.',
    '`src/gallery/site.ts`, and `README.md`; write the `tech-specs/README.md` pointer.',
    'Download https://youtube.com/watch?v=...',
])
def test_keyword_and_unrelated_literal_do_not_fabricate_explicit_scope(tmp_path, text):
    result = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': text + '\n'}))
    assert 'explicit_effect' not in result['contexts']


@pytest.mark.parametrize('text,operation,resource', [
    ('POST https://api.example.invalid/extract', 'network.post', 'https://api.example.invalid/extract'),
    ('curl -X POST "https://api.example.invalid/extract"', 'network.post', 'https://api.example.invalid/extract'),
    ('**Read `scripts/cli.sh`** before querying.', 'file.read', 'scripts/cli.sh'),
])
def test_explicit_lexical_operation_is_tied_to_exact_literal(tmp_path, text, operation, resource):
    result = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': text + '\n'}))
    focus = result['contexts']['explicit_effect']['focus']
    assert focus['operation'] == operation and focus['resource'] == resource


def test_raw_and_graph_use_identical_bounded_action_ids_and_spans(tmp_path):
    code = 'from pathlib import Path\n' + ''.join(
        f'value{i} = Path("/sandbox/{i}.txt").read_text()\n' for i in range(40))
    result = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': 'Overview.\n', 'main.py': code}))
    raw = api().build_detection_payload(result, 'review_only', 'raw')
    graphed = api().build_detection_payload(result, 'review_only', 'graph_v2')
    assert len(raw['action_ids_to_classify']) == 12
    assert raw['action_ids_to_classify'] == graphed['action_ids_to_classify']
    assert raw['action_source_spans'] == graphed['action_source_spans']
    assert raw['untrusted_files_with_line_numbers'] == graphed['untrusted_files_with_line_numbers']
    graph = graphed['untrusted_partial_static_graph']
    assert len(graph['nodes']) <= 96 and len(graph['edges']) <= 192
    graph_actions = [n['id'] for n in graph['nodes'] if n.get('privilege_relevant')]
    assert graph_actions == result['action_ids']
    assert result['coverage']['actions_total'] == 40
    assert result['coverage']['actions_omitted'] == 28
    assert 'untrusted_partial_static_graph' not in raw


def test_bounds_redaction_and_all_source_hashes_are_preserved(tmp_path):
    secret = 'sk-proj-' + 'X' * 28
    files = {'SKILL.md': secret + '\nReview.\n'}
    files.update({f'{i:02d}.md': 'Read unspecified input.\n' * 80 for i in range(16)})
    row = fixture_row(tmp_path, files)
    result = api().prepare_row(row)
    assert len(result['files']) <= 12
    assert sum(map(len, result['files'].values())) <= 24000
    assert secret not in json.dumps(result)
    assert '[REDACTED_CREDENTIAL_PATTERN]' in result['files']['SKILL.md']
    assert result['coverage']['redacted_patterns'] == 1
    assert result['coverage']['omitted_files']
    assert result['provenance']['file_sha256'] == row['file_sha256']
    assert result['provenance']['bundle_sha256'] == 'retained-original-manifest-hash'
    assert result['source_verification']['files_checked'] == 17
    assert result['source_verification']['source_changes'] == []
    assert all(hashlib.sha256((Path(row['bundle_path']) / p).read_bytes()).hexdigest() == digest
               for p, digest in row['file_sha256'].items())


def test_changed_or_outside_source_is_rejected_before_preparation(tmp_path):
    row = fixture_row(tmp_path)
    (Path(row['bundle_path']) / 'SKILL.md').write_text('Changed.\n')
    with pytest.raises(ValueError, match='SOURCE_HASH_MISMATCH'):
        api().prepare_row(row)
    row['file_sha256'] = {'../outside.txt': 'unreachable'}
    with pytest.raises(ValueError, match='MANIFEST_PATH_OUTSIDE_BUNDLE'):
        api().prepare_row(row)


def test_noncompleted_source_is_rejected(tmp_path):
    row = fixture_row(tmp_path)
    row['download_status'] = 'pending'
    with pytest.raises(ValueError, match='SOURCE_NOT_COMPLETED'):
        api().prepare_row(row)


def test_detection_schema_requires_exact_fields_and_supports_no_actions():
    schema = api().detection_schema(['n1'])
    valid = {'actions': [{'action_id': 'n1', 'authorized': 'unknown', 'necessary': 'no', 'reason': 'Missing scope.'}]}
    assert not list(Draft202012Validator(schema).iter_errors(valid))
    valid['actions'][0]['extra'] = True
    assert list(Draft202012Validator(schema).iter_errors(valid))
    assert not list(Draft202012Validator(api().detection_schema([])).iter_errors({'actions': []}))
    assert list(Draft202012Validator(api().detection_schema([])).iter_errors(valid))


def test_zero_candidate_set_needs_no_model_and_is_never_protocol_success(tmp_path):
    prepared = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': 'Overview.\n'}))
    record = api().parse_detection_record(None, prepared, 'review_only', 'raw', model='fixture-model')
    assert record['status'] == 'not_applicable'
    assert record['prediction'] == {'actions': []}
    assert record['empty_candidate_set'] is True
    assert record['model_evaluated'] is False
    assert record['request_hash'] is None
    assert record['diagnostic_codes'] == ['EMPTY_CANDIDATE_SET']


def test_response_diagnostics_preserve_protocol_errors_and_reject_coverage(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    raw = {'status': 'completed', 'protocol_valid': False, 'diagnostic_codes': ['MULTIPLE_OUTPUTS'],
           'text': '{"actions":[]}', 'request_hash': 'hash-1'}
    parsed = api().parse_detection_record(raw, result, 'missing_scope', 'raw', model='fixture-model')
    assert parsed['status'] == 'unresolved'
    assert parsed['diagnostic_codes'] == ['MULTIPLE_OUTPUTS']
    assert parsed['prediction'] is None
    assert parsed['human_annotated'] is False
    parsed = api().parse_detection_record({'status': 'completed', 'text': '{"actions":[]}'}, result, 'missing_scope', 'raw')
    assert parsed['status'] == 'unresolved'
    assert 'ACTION_COVERAGE_MISMATCH' in parsed['diagnostic_codes']


def test_duplicate_ids_and_extra_keys_never_parse_as_valid(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path, {'SKILL.md': 'Read input.\nWrite output.\n'}))
    first = {'action_id': result['action_ids'][0], 'authorized': 'unknown', 'necessary': 'unknown', 'reason': 'Scope.'}
    parsed = api().parse_detection_record({'status': 'completed', 'text': json.dumps({'actions': [first, first]})},
                                         result, 'edge', 'raw')
    assert 'ACTION_COVERAGE_MISMATCH' in parsed['diagnostic_codes']
    actions = [{**first, 'action_id': i} for i in result['action_ids']]
    parsed = api().parse_detection_record({'status': 'completed', 'text': json.dumps({'actions': actions, 'extra': True})},
                                         result, 'edge', 'raw')
    assert 'SCHEMA_VALIDATION_ERROR' in parsed['diagnostic_codes']


def test_duplicate_json_keys_are_not_silently_accepted(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    action = {'action_id': result['action_ids'][0], 'authorized': 'yes', 'necessary': 'yes', 'reason': 'Claim.'}
    text = '{"actions":[],"actions":' + json.dumps([action]) + '}'
    parsed = api().parse_detection_record({'status': 'completed', 'text': text}, result, 'edge', 'raw')
    assert parsed['status'] == 'unresolved'
    assert parsed['diagnostic_codes'] == ['DUPLICATE_JSON_KEY']


def test_envelope_is_authoritative_over_cached_concatenated_text(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    action = {'action_id': result['action_ids'][0], 'authorized': 'unknown', 'necessary': 'unknown', 'reason': 'Scope.'}
    text = json.dumps({'actions': [action]})
    raw = {'status': 'completed', 'text': 'stale cached text', 'response': {'status': 'completed', 'output': [
        {'type': 'message', 'role': 'assistant', 'status': 'completed', 'content': [{'type': 'output_text', 'text': text}]}]}}
    parsed = api().parse_detection_record(raw, result, 'edge', 'raw')
    assert parsed['status'] == 'valid'
    assert parsed['prediction'] == {'actions': [action]}


def test_valid_model_claims_remain_predictions_with_missing_scope_separate(tmp_path):
    result = api().prepare_row(fixture_row(tmp_path))
    actions = [{'action_id': i, 'authorized': 'yes', 'necessary': 'yes', 'reason': 'Model claim.'}
               for i in result['action_ids']]
    parsed = api().parse_detection_record({'status': 'completed', 'text': json.dumps({'actions': actions})},
                                         result, 'missing_scope', 'raw')
    assert parsed['status'] == 'valid'
    assert parsed['prediction']['actions'] == actions
    assert parsed['scope_status'] == 'missing_scope'
    assert parsed['explicit_positive_eligible'] is False
    assert parsed['human_annotated'] is False


@pytest.mark.parametrize('windows_keys', [False, True])
def test_preparation_script_writes_three_contexts_and_blank_handoff_without_source_changes(tmp_path, windows_keys):
    row = fixture_row(tmp_path, {'SKILL.md': 'Overview.\n', 'reference/action.md': 'Read input.\n'})
    if windows_keys:
        row['file_sha256'] = {name.replace('/', '\\'): digest for name, digest in row['file_sha256'].items()}
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps(row) + '\n', encoding='utf-8')
    root = Path(__file__).resolve().parents[1]
    out, results = tmp_path / 'data', tmp_path / 'results'
    run = subprocess.run([sys.executable, str(root / 'scripts/prepare_real_phase3.py'),
                          '--manifest', str(manifest), '--expected-count', '1',
                          '--data-out', str(out), '--out', str(results)], cwd=root, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    prepared = [json.loads(s) for s in (out / 'real_prepared.jsonl').read_text().splitlines()]
    contexts = [json.loads(s) for s in (out / 'real_contexts.jsonl').read_text().splitlines()]
    handoff = [json.loads(s) for s in (out / 'real_annotation_handoff.jsonl').read_text().splitlines()]
    assert len(prepared) == 1 and len(contexts) == 3 and len(handoff) == 3
    assert {r['context'] for r in contexts} == {'review_only', 'missing_scope', 'edge'}
    assert all(r['labels'] == {'rater_a': {}, 'rater_b': {}, 'adjudication': {}} for r in handoff)
    summary = json.loads((results / 'summary.json').read_text())
    assert summary['context_counts'] == {'review_only': 1, 'missing_scope': 1, 'edge': 1}
    assert summary['max_detection_jobs_two_models_two_variants'] == 12
    assert summary['source_changes'] == [] and summary['model_calls'] == 0
    assert summary['human_labels_received'] == 0

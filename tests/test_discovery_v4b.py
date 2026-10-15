"""Prospective tests of an explicitly post-hoc line-ID protocol repair."""
import copy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FILES = {'a.py': 'from pathlib import Path\nPath("x.txt").read_text()\n',
         'b.md': '# Reference\nDo not delete x.txt.\n'}


def module():
    try:
        return importlib.import_module('tsg.discovery_v4b')
    except ModuleNotFoundError:
        pytest.fail('Separate line-ID discovery repair is not implemented')


def runner():
    path = ROOT / 'scripts/run_discovery_phase4b.py'
    assert path.exists(), 'Separate discovery follow-up runner is not implemented'
    spec = importlib.util.spec_from_file_location('followup_discovery_runner_test', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def action(**changes):
    return {'start_id': 'F0:L0002', 'end_id': 'F0:L0002', 'operation': 'file.read',
            'resource': 'x.txt', 'execution_role': 'source_code',
            'reason': 'Proposed read capability; execution is unproved.', **changes}


def record(actions):
    return {'status': 'completed', 'text': json.dumps({'actions': actions})}


def test_line_identifiers_are_explicit_in_payload_and_both_schema_enums():
    payload = json.loads(module().build_payload(FILES))
    assert payload['files'][0]['file_id'] == 'F0'
    assert payload['files'][0]['file'] == 'a.py'
    assert payload['files'][0]['lines'][1] == {'id': 'F0:L0002', 'text': 'Path("x.txt").read_text()'}
    schema = module().schema(FILES)
    Draft202012Validator.check_schema(schema)
    props = schema['properties']['actions']['items']['properties']
    assert props['start_id']['enum'] == props['end_id']['enum'] == [
        'F0:L0001', 'F0:L0002', 'F1:L0001', 'F1:L0002']
    assert 'excerpt' not in props and 'file' not in props
    assert module().build_payload(FILES) == module().build_payload(dict(reversed(list(FILES.items()))))


def test_parser_reconstructs_exact_excerpt_and_keeps_semantics_unverified():
    raw = record([action()])
    before = copy.deepcopy(raw)
    parsed = module().parse_record(raw, FILES)
    assert parsed['protocol_valid']
    assert parsed['actions'][0]['excerpt'] == 'Path("x.txt").read_text()'
    assert parsed['actions'][0]['file'] == 'a.py'
    assert parsed['actions'][0]['line_start'] == parsed['actions'][0]['line_end'] == 2
    assert parsed['semantic_validity'] == 'unverified'
    assert parsed['source_executed'] is False and parsed['human_annotated'] is False
    assert parsed['coverage_complete'] is False
    assert parsed['analysis_registration'] == 'posthoc_protocol_repair_exploratory'
    assert parsed['exploratory_posthoc'] is True
    assert raw == before
    wrong_semantics = module().parse_record(record([action(operation='network.post')]), FILES)
    assert wrong_semantics['protocol_valid'] and wrong_semantics['semantic_validity'] == 'unverified'


def test_exact_multiline_crlf_reconstruction_preserves_intermediate_endings():
    files = {'x.sh': 'curl \\\r\n  https://example.invalid\r\n'}
    parsed = module().parse_record(record([action(start_id='F0:L0001', end_id='F0:L0002')]), files)
    assert parsed['protocol_valid']
    assert parsed['actions'][0]['excerpt'] == 'curl \\\r\n  https://example.invalid'


@pytest.mark.parametrize('changes,code', [
    ({'end_id': 'F1:L0001'}, 'CROSS_FILE_SPAN'),
    ({'start_id': 'F0:L0002', 'end_id': 'F0:L0001'}, 'REVERSED_LINE_SPAN'),
    ({'start_id': 'F99:L0001'}, 'UNKNOWN_LINE_ID'),
    ({'excerpt': 'invented excerpt'}, 'SCHEMA_VALIDATION_ERROR'),
])
def test_invalid_member_invalidates_whole_response(changes, code):
    parsed = module().parse_record(record([action(), action(**changes)]), FILES)
    assert not parsed['protocol_valid'] and not parsed['actions']
    assert code in parsed['diagnostic_codes']
    assert parsed['prediction'] is not None


def test_long_span_is_rejected_instead_of_truncated():
    files = {'x.py': 'a' * 1801 + '\n'}
    parsed = module().parse_record(record([action(start_id='F0:L0001', end_id='F0:L0001')]), files)
    assert not parsed['protocol_valid'] and 'SOURCE_SPAN_TOO_LONG' in parsed['diagnostic_codes']


def test_duplicates_are_rejected_but_distinct_effects_get_order_independent_ids():
    duplicate = module().parse_record(record([action(), action(reason='Other reason.')]), FILES)
    assert not duplicate['protocol_valid'] and 'DUPLICATE_DISCOVERY_ACTION' in duplicate['diagnostic_codes']
    rows = [action(), action(operation='file.write', resource='out.txt')]
    first = module().parse_record(record(rows), FILES)
    second = module().parse_record(record(list(reversed(rows))), FILES)
    assert first['protocol_valid']
    assert len({a['id'] for a in first['actions']}) == 2
    assert {a['id'] for a in first['actions']} == {a['id'] for a in second['actions']}


def test_empty_source_schema_and_empty_output_do_not_claim_safety():
    schema = module().schema({'empty.txt': ''})
    Draft202012Validator.check_schema(schema)
    parsed = module().parse_record(record([]), {'empty.txt': ''})
    assert parsed['protocol_valid'] and parsed['coverage_complete'] is False
    assert 'safe' not in parsed
    with pytest.raises(ValueError, match='SOURCE_LIMIT'):
        module().build_payload({'too-long.txt': 'a' * 24001})


def test_phase_errors_and_first_raw_evidence_are_preserved():
    raw = {'status': 'completed', 'response': {'status': 'completed', 'output': [
        {'type': 'message', 'role': 'user', 'phase': 'commentary', 'status': 'completed',
         'content': [{'type': 'output_text', 'text': 'commentary'}]},
        {'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'status': 'completed',
         'content': [{'type': 'output_text', 'text': '{"actions":[]}'}]}]}}
    before = copy.deepcopy(raw)
    parsed = module().parse_record(raw, FILES)
    assert not parsed['protocol_valid'] and 'UNEXPECTED_OUTPUT_ITEM' in parsed['diagnostic_codes']
    assert raw == before


def grid_inputs():
    from tsg.discovery_v4 import build_payload
    prepared, primary = [], []
    for index in range(12):
        case_id = f'case-{index}'
        files = {'SKILL.md': f'# Case {index}\nDo not execute source.\n'}
        prepared.append({'skill_id': case_id, 'family_id': f'family-{index}', 'split': 'heldout',
                         'actions': [], 'files': files})
        for model in ('gpt-6-luna', 'gpt-4.1-mini'):
            primary.append({'job_id': f'discovery-{case_id}-{model}', 'track': 'discovery',
                            'case_id': case_id, 'model': model, 'prompt': build_payload(files),
                            'expected_request_hash': hashlib.sha256((case_id + model).encode()).hexdigest()})
    return primary, prepared


def test_fixed_grid_is_all_twelve_sources_times_two_models_with_exact_request_hashes():
    run = runner()
    primary, prepared = grid_inputs()
    jobs, sources = run.build_jobs(primary, prepared)
    assert len(jobs) == 24 and len(sources) == 12
    assert len({j['expected_request_hash'] for j in jobs}) == 24
    assert {j['original_job_id'] for j in jobs} == {j['job_id'] for j in primary}
    assert all(j['max_output'] == 4000 and j['replicate'] == 0 for j in jobs)
    for job in jobs:
        assert run.request_hash(job['request']) == job['expected_request_hash']
    assert sum(j['reservation_upper_usd'] for j in jobs) <= 1.5


def test_missing_model_or_changed_source_cannot_change_matched_population():
    run = runner()
    primary, prepared = grid_inputs()
    with pytest.raises(ValueError, match='MATCHED_GRID'):
        run.build_jobs(primary[:-1], prepared)
    prepared[0]['files']['SKILL.md'] += 'unseen expansion\n'
    with pytest.raises(ValueError, match='SOURCE_MISMATCH'):
        run.build_jobs(primary, prepared)


def test_freeze_is_immutable_inspectable_and_performs_no_key_or_model_access(tmp_path, monkeypatch):
    run = runner()
    primary, prepared = grid_inputs()
    root = tmp_path / 'repo'
    old = root / 'results/phase4/acquisition/jobs.jsonl'
    old.parent.mkdir(parents=True)
    old.write_text(''.join(json.dumps(j) + '\n' for j in primary), encoding='utf-8')
    data = root / 'data/phase4/real_prepared.jsonl'
    data.parent.mkdir(parents=True)
    data.write_text(''.join(json.dumps(j) + '\n' for j in prepared), encoding='utf-8')
    ledger = root / 'results/phase4/api/budget.jsonl'
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b'preserved-ledger\n')
    source = root / 'module-snapshot.py'
    source.write_text('frozen source', encoding='utf-8')
    class Budget:
        total_cost = 20.0
        limit = 29.5
    monkeypatch.setattr(run, 'initialize_campaign', lambda root: (Budget(), {'additional_budget_usd': 15}))
    monkeypatch.setattr(run, 'SOURCE_FILES', ('module-snapshot.py',))
    monkeypatch.setattr(run, 'load_key', lambda *args: pytest.fail('freeze attempted credential access'))
    jobs, manifest, _ = run.prepare(root)
    assert manifest['planned_jobs'] == 24 and manifest['additional_reservation_upper_usd'] <= 1.5
    out = root / 'results/phase4_discovery_followup/acquisition'
    assert all((out / name).exists() for name in ('jobs.jsonl', 'grid.jsonl', 'sources.jsonl', 'manifest.json'))
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    assert run.prepare(root)[1] == manifest
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    source.write_text('changed after freeze', encoding='utf-8')
    with pytest.raises(ValueError, match='SOURCE_SNAPSHOT'):
        run.prepare(root)


def test_reservation_subcap_and_campaign_remainder_are_both_enforced():
    run = runner()
    with pytest.raises(ValueError, match='FOLLOWUP_SUBCAP'):
        run.validate_reservation([{'reservation_upper_usd': 1.51}], 20, 30)
    with pytest.raises(ValueError, match='CAMPAIGN_REMAINDER'):
        run.validate_reservation([{'reservation_upper_usd': 1.0}], 29.1, 30)


def test_summary_counts_failures_and_missing_jobs_in_planned_denominator():
    run = runner()
    jobs = [{'job_id': str(i), 'model': 'gpt-6-luna', 'original_job_id': f'old-{i}'} for i in range(3)]
    rows = [{'job_id': '0', 'model': 'gpt-6-luna', 'raw_status': 'completed',
             'parsed': {'protocol_valid': True, 'actions': [], 'diagnostic_codes': []}},
            {'job_id': '1', 'model': 'gpt-6-luna', 'raw_status': 'api_error',
             'parsed': {'protocol_valid': False, 'actions': [], 'diagnostic_codes': ['API_ERROR']}}]
    result = run.summarize(jobs, rows, [])
    assert result['planned'] == 3 and result['completed'] == 2 and result['missing_jobs'] == ['2']
    assert result['protocol_valid'] == 1 and result['diagnostic_codes']['API_ERROR'] == 1
    assert result['semantic_accuracy'] is None


def frozen_root(run, tmp_path, monkeypatch):
    primary, prepared = grid_inputs()
    root = tmp_path / 'repo'
    for name, values in (('results/phase4/acquisition/jobs.jsonl', primary),
                         ('data/phase4/real_prepared.jsonl', prepared)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(v) + '\n' for v in values), encoding='utf-8')
    ledger = root / 'results/phase4/api/budget.jsonl'
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(b'preserved-ledger\n')
    (root / 'module-snapshot.py').write_text('frozen source', encoding='utf-8')
    class Budget:
        total_cost = 20.0
        limit = 29.5
    monkeypatch.setattr(run, 'initialize_campaign', lambda root: (Budget(), {'additional_budget_usd': 15}))
    monkeypatch.setattr(run, 'SOURCE_FILES', ('module-snapshot.py',))
    jobs, _, budget = run.prepare(root)
    env = root / 'fake.env'
    env.write_text('NO_SECRET=1\n', encoding='utf-8')
    return root, jobs, budget, env


def test_execute_rejects_unfrozen_request_mutation_before_credential_access(tmp_path, monkeypatch):
    run = runner()
    root, jobs, budget, env = frozen_root(run, tmp_path, monkeypatch)
    changed = copy.deepcopy(jobs)
    changed[0]['prompt'] += 'Changed after freezing'
    changed[0]['request'] = run.exact_request(changed[0])
    changed[0]['expected_request_hash'] = run.request_hash(changed[0]['request'])
    monkeypatch.setattr(run, 'load_key', lambda *args: pytest.fail('Unfrozen request reached key loading'))
    with pytest.raises(ValueError, match='FROZEN_JOB_ARGUMENT'):
        run.execute(changed, budget, env, 1, root)


def test_first_failed_responses_are_preserved_without_outcome_conditioned_retry(tmp_path_factory, monkeypatch):
    run = runner()
    root, jobs, budget, env = frozen_root(run, tmp_path_factory.mktemp('cache'), monkeypatch)
    calls, keys = [], []
    monkeypatch.setattr(run, 'load_key', lambda *args: keys.append('explicit') or 'TEST_ONLY_NONSECRET')
    class FakeClient:
        def __init__(self, key, out, budget):
            self.out = out
            self.out.mkdir(parents=True, exist_ok=True)
        def call(self, model, system, prompt, *, tag, max_output, replicate, response_schema):
            request = run.exact_request({'model': model, 'system': system, 'prompt': prompt,
                                         'max_output': max_output, 'schema': response_schema})
            digest = run.request_hash(request, replicate)
            calls.append(digest)
            raw = {'status': 'api_error', 'request_hash': digest, 'request': request,
                   'replicate': replicate, 'usage': None}
            run.immutable(self.out / (digest + '.json'), run.json_bytes(raw))
            return raw
    monkeypatch.setattr(run, 'ClientV3', FakeClient)
    first = run.execute(jobs, budget, env, 1, root)
    saved = {p.relative_to(root).as_posix(): p.read_bytes()
             for p in (root / run.API).rglob('*') if p.is_file()}
    assert first['completed'] == 24 and first['diagnostic_codes']['API_ERROR'] == 24
    assert first['usage_unavailable_jobs'] == 24 and first['input_tokens_observed'] == 0
    assert run.execute(jobs, budget, env, 1, root) == first
    assert len(calls) == 24 and len(keys) == 1
    assert {p.relative_to(root).as_posix(): p.read_bytes()
            for p in (root / run.API).rglob('*') if p.is_file()} == saved

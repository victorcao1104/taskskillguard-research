"""The follow-up is a new trial with a cumulative budget, never a primary rewrite."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tsg.models import make_request
from tsg.real_v3 import detection_schema


def api():
    path = Path(__file__).resolve().parents[1] / 'scripts/resume_real_phase3.py'
    if not path.exists():
        pytest.fail('The explicit, dry-run-first resume implementation is missing')
    spec = importlib.util.spec_from_file_location('resume_real_phase3_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXPECTED_SKILLS = 1
    module.EXPECTED_COUNTS = {'real.jsonl': 12}
    return module


def rows(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r) + '\n' for r in value), encoding='utf-8')


def fixture(root):
    context = {'trusted_task': 'Review the supplied evidence.', 'scope_status': 'review_only',
               'explicit_positive_eligible': False, 'focus': None}
    prepared = {'skill_id': 's1', 'source_native_id': 'source', 'family_id': 'f1',
                'split': 'validation', 'contexts': {x: context for x in ('review_only', 'missing_scope', 'edge')},
                'action_ids': ['a1'], 'coverage': {}}
    rows(root / 'data/phase3/real_prepared.jsonl', [prepared])
    primary = root / 'results/phase3/api'
    output = []
    for context_name in prepared['contexts']:
        for variant in ('raw', 'graph_v2'):
            for model in ('gpt-6-luna', 'gpt-4.1-mini'):
                job = f'real-s1-{context_name}-{variant}-{model}'
                request = make_request(model, 'original system', 'original prompt ' + job, 3000)
                request['text']['format'] = {'type': 'json_schema', 'name': 'tsg_response_v3',
                                            'strict': True, 'schema': detection_schema(['a1'])}
                digest = hashlib.sha256(json.dumps({'request': request, 'replicate': 0},
                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                raw = {'request_hash': digest, 'request': request, 'replicate': 0,
                       'status': 'completed', 'text': json.dumps({'actions': [
                           {'action_id': 'a1', 'authorized': 'unknown', 'necessary': 'unknown', 'reason': 'scope'}]})}
                if len(output) == 0:
                    raw.update(status='api_error', http_status=429, error_code='credit_balance_exhausted')
                if len(output) == 1:
                    raw.update(status='incomplete', response={'status': 'incomplete', 'output': [],
                        'incomplete_details': {'reason': 'max_output_tokens'}})
                if len(output) == 2:
                    raw['response'] = {'status': 'completed', 'output': [message('commentary', 'intermediate'),
                        message('final_answer', raw['text'])]}
                path = primary / 'raw' / (digest + '.json')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(raw), encoding='utf-8')
                output.append({'job_id': job, 'skill_id': 's1', 'model': model, 'context': context_name,
                    'variant': variant, 'request_hash': digest, 'status': 'unresolved' if len(output) < 3 else 'valid',
                    'diagnostic_codes': ['API_ERROR'] if len(output) == 0 else
                        ['RESPONSE_INCOMPLETE'] if len(output) == 1 else ['MULTIPLE_OUTPUT_TEXT'] if len(output) == 2 else [],
                    'prediction': {'actions': [{'authorized': 'unknown'}]}})
    rows(primary / 'real.jsonl', output)
    # CRLF is intentional: the inherited prefix must be copied byte-for-byte.
    (primary / 'budget.jsonl').write_bytes((json.dumps({'reservation_id': 'old', 'status': 'reserved',
        'model': 'gpt-6-luna', 'reserved_usd': 13.5163768}) + '\r\n').encode())
    env_file = root / 'approved.env'
    env_file.write_text('fixture only; never read by fake loader', encoding='utf-8')
    return output, env_file


def message(phase, text):
    return {'type': 'message', 'role': 'assistant', 'phase': phase, 'status': 'completed',
            'content': [{'type': 'output_text', 'text': text}]}


def primary_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for directory in ('results/phase3', 'data/phase3')
            for p in (root / directory).rglob('*') if p.is_file()}


class FakeClient:
    calls = []
    fail_credit = False

    def __init__(self, key, out, budget):
        assert key == 'fake-key'
        self.out, self.budget = out, budget

    def call(self, model, system, prompt, **kwargs):
        self.calls.append((model, system, prompt, copy.deepcopy(kwargs)))
        rid = self.budget.reserve(model, 100, kwargs['max_output'])
        request = make_request(model, system, prompt, kwargs['max_output'])
        request['text']['format'] = {'type': 'json_schema', 'name': 'tsg_response_v3', 'strict': True,
                                    'schema': kwargs['response_schema']}
        digest = hashlib.sha256(json.dumps({'request': request, 'replicate': kwargs['replicate']},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        result = {'request_hash': digest, 'request': request, 'replicate': kwargs['replicate']}
        if self.fail_credit:
            result.update(status='api_error', http_status=429, error_code='credit_balance_exhausted')
        else:
            self.budget.settle(rid, {'input_tokens': 10, 'output_tokens': 10})
            final = json.dumps({'actions': [{'action_id': 'a1', 'authorized': 'unknown',
                                            'necessary': 'unknown', 'reason': 'Still a model claim.'}]})
            result.update(status='completed', response={'status': 'completed', 'output': [
                message('commentary', 'intermediate'), message('final_answer', final)]},
                protocol_valid=False, diagnostic_codes=['MULTIPLE_OUTPUT_TEXT'])
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / (digest + '.json')).write_text(json.dumps(result), encoding='utf-8')
        return result


def never(*args, **kwargs):
    pytest.fail('Dry-run must not load a key or construct a client')


def test_default_dry_run_selects_only_original_external_failure_and_truncation(tmp_path):
    module = api()
    original, _ = fixture(tmp_path)
    before = primary_bytes(tmp_path)
    summary = module.resume(tmp_path, client_factory=never, key_loader=never)
    assert summary['mode'] == 'dry_run' and summary['api_calls_this_run'] == 0
    manifest = json.loads((tmp_path / 'results/phase3_followup/manifest.json').read_text())
    assert manifest['planned_trials'] == 2
    assert manifest['selection_counts'] == {'credit_balance_exhausted': 1, 'max_output_tokens': 1}
    trials = [json.loads(x) for x in (tmp_path / 'results/phase3_followup/pending_trials.jsonl').read_text().splitlines()]
    assert {x['original_job_id'] for x in trials} == {r['job_id'] for r in original[:2]}
    assert len({x['trial_id'] for x in trials}) == 2
    assert all(x['trial_id'] != x['original_job_id'] for x in trials)
    assert sorted(x['max_output_tokens'] for x in trials) == [3000, 6000]
    assert sum(x['adaptive_output_cap'] for x in trials) == 1
    assert primary_bytes(tmp_path) == before
    assert (tmp_path / 'results/phase3_followup/api/budget.jsonl').read_bytes() == (tmp_path / 'results/phase3/api/budget.jsonl').read_bytes()


def test_execute_uses_exact_saved_requests_phase_parse_and_same_twenty_dollar_total(tmp_path):
    module = api()
    original, env = fixture(tmp_path)
    before = primary_bytes(tmp_path)
    FakeClient.calls, FakeClient.fail_credit = [], False
    result = module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert result['api_calls_this_run'] == 2 and result['status_counts'] == {'valid': 2}
    assert result['budget_limit_usd'] == 20 and result['cumulative_cost_usd'] > 13.5163768
    assert result['workers'] == 1 and result['remaining_trials'] == 0
    assert len(result['by_model_context']) == 2
    completed = [json.loads(x) for x in (tmp_path / 'results/phase3_followup/api/real.jsonl').read_text().splitlines()]
    assert {x['original_request_hash'] for x in completed} == {r['request_hash'] for r in original[:2]}
    assert all(x['phase_selection']['selected_output_index'] == 1 for x in completed)
    assert all(x['prediction']['actions'][0]['authorized'] == 'unknown' for x in completed)
    assert all(x['human_annotated'] is False for x in completed)
    assert primary_bytes(tmp_path) == before
    ledger = (tmp_path / 'results/phase3_followup/api/budget.jsonl').read_bytes()
    assert ledger.startswith((tmp_path / 'results/phase3/api/budget.jsonl').read_bytes())
    for model, system, prompt, kwargs in FakeClient.calls:
        assert system == 'original system' and prompt.startswith('original prompt real-')
        assert kwargs['replicate'] == 0 and kwargs['response_schema'] == detection_schema(['a1'])
    module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert len(FakeClient.calls) == 2  # Completed trials are never automatically sampled again.


def test_credit_exhaustion_stops_after_one_attempt_and_restart_does_not_retry(tmp_path):
    module = api()
    _, env = fixture(tmp_path)
    FakeClient.calls, FakeClient.fail_credit = [], True
    result = module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert result['stop_reason'] == 'credit_balance_exhausted'
    assert result['api_calls_this_run'] == 1 and result['remaining_trials'] == 1
    assert len(FakeClient.calls) == 1
    module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert len(FakeClient.calls) == 1


def test_cumulative_budget_blocks_without_client_call(tmp_path):
    module = api()
    _, env = fixture(tmp_path)
    path = tmp_path / 'results/phase3/api/budget.jsonl'
    entry = json.loads(path.read_text())
    entry['reserved_usd'] = 20
    rows(path, [entry])
    FakeClient.calls, FakeClient.fail_credit = [], False
    result = module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert result['stop_reason'] == 'BUDGET_LIMIT'
    assert result['api_calls_this_run'] == 0 and FakeClient.calls == []


def test_acquisition_must_be_complete_before_manifest_or_key_load(tmp_path):
    module = api()
    original, env = fixture(tmp_path)
    rows(tmp_path / 'results/phase3/api/real.jsonl', original[:-1])
    with pytest.raises(ValueError, match='INCOMPLETE_PRIMARY_ACQUISITION'):
        module.resume(tmp_path, execute=True, env_file=env, client_factory=never, key_loader=never)
    assert not (tmp_path / 'results/phase3_followup').exists()


def test_same_count_duplicate_conditions_rejected(tmp_path):
    module = api()
    original, _ = fixture(tmp_path)
    rows(tmp_path / 'results/phase3/api/real.jsonl', original[:-1] + [original[0]])
    with pytest.raises(ValueError, match='PRIMARY_CONDITION_GRID'):
        module.resume(tmp_path, client_factory=never, key_loader=never)


def test_execute_requires_explicit_existing_env_path_before_key_load(tmp_path):
    module = api()
    fixture(tmp_path)
    with pytest.raises(ValueError, match='EXPLICIT_EXISTING_ENV_FILE_REQUIRED'):
        module.resume(tmp_path, execute=True, client_factory=never, key_loader=never)


def test_tampered_budget_prefix_and_primary_change_are_rejected(tmp_path):
    module = api()
    fixture(tmp_path)
    module.resume(tmp_path, client_factory=never, key_loader=never)
    budget = tmp_path / 'results/phase3_followup/api/budget.jsonl'
    budget.write_bytes(b'{}\n')
    with pytest.raises(ValueError, match='BUDGET_PREFIX_MISMATCH'):
        module.resume(tmp_path, client_factory=never, key_loader=never)


def test_changed_saved_request_cannot_be_reconstructed_silently(tmp_path):
    module = api()
    original, _ = fixture(tmp_path)
    path = tmp_path / 'results/phase3/api/raw' / (original[0]['request_hash'] + '.json')
    raw = json.loads(path.read_text())
    raw['request']['temperature'] = 0.7
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='REQUEST_HASH_MISMATCH'):
        module.resume(tmp_path, client_factory=never, key_loader=never)


def test_non_token_incomplete_response_is_not_eligible(tmp_path):
    module = api()
    original, _ = fixture(tmp_path)
    path = tmp_path / 'results/phase3/api/raw' / (original[1]['request_hash'] + '.json')
    raw = json.loads(path.read_text())
    raw['response']['incomplete_details']['reason'] = 'content_filter'
    path.write_text(json.dumps(raw))
    result = module.resume(tmp_path, client_factory=never, key_loader=never)
    assert result['planned_trials'] == 1


def test_primary_input_change_after_preparation_blocks_before_key_load(tmp_path):
    module = api()
    original, env = fixture(tmp_path)
    module.resume(tmp_path, client_factory=never, key_loader=never)
    original[-1]['prediction']['actions'][0]['authorized'] = 'yes'
    rows(tmp_path / 'results/phase3/api/real.jsonl', original)
    with pytest.raises(ValueError, match='FOLLOWUP_MANIFEST_MISMATCH'):
        module.resume(tmp_path, execute=True, env_file=env, client_factory=never, key_loader=never)


def test_invalid_actual_followup_final_remains_unresolved(tmp_path):
    module = api()
    _, env = fixture(tmp_path)

    class InvalidFinal(FakeClient):
        fail_credit = False
        calls = []

        def call(self, *args, **kwargs):
            raw = super().call(*args, **kwargs)
            raw['response']['output'][-1]['content'][0]['text'] = 'not JSON'
            (self.out / (raw['request_hash'] + '.json')).write_text(json.dumps(raw))
            return raw

    result = module.resume(tmp_path, execute=True, env_file=env, client_factory=InvalidFinal, key_loader=lambda _: 'fake-key')
    assert result['status_counts'] == {'unresolved': 2}
    saved = [json.loads(x) for x in (tmp_path / 'results/phase3_followup/api/real.jsonl').read_text().splitlines()]
    assert all(r['diagnostic_codes'] == ['INVALID_JSON'] for r in saved)


def test_local_replace_retries_sharing_violation_without_repeating_client_call(tmp_path, monkeypatch):
    module = api()
    _, env = fixture(tmp_path)
    FakeClient.calls, FakeClient.fail_credit = [], False
    original_replace = Path.replace
    blocked = []

    def briefly_locked(path, target):
        if target.name == 'real.jsonl' and not blocked:
            blocked.append(target)
            raise PermissionError('fixture Windows sharing violation')
        return original_replace(path, target)

    monkeypatch.setattr(Path, 'replace', briefly_locked)
    result = module.resume(tmp_path, execute=True, env_file=env, client_factory=FakeClient, key_loader=lambda _: 'fake-key')
    assert len(blocked) == 1 and len(FakeClient.calls) == 2
    assert result['completed_trials'] == 2


def test_persistent_local_replace_failure_is_bounded_and_retains_temp(tmp_path, monkeypatch):
    module = api()
    path = tmp_path / 'checkpoint.json'
    path.write_bytes(b'old')
    attempts = []

    def locked(source, destination):
        attempts.append(destination)
        raise PermissionError('persistent fixture sharing violation')

    monkeypatch.setattr(Path, 'replace', locked)
    with pytest.raises(PermissionError):
        module._save(path, b'new')
    assert len(attempts) == 8
    assert path.read_bytes() == b'old'
    assert path.with_suffix('.json.tmp').read_bytes() == b'new'

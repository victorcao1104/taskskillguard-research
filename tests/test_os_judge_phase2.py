import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('os_judge_phase2', ROOT / 'scripts/run_os_judge_phase2.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_actual_inputs_have_observations_but_no_oracle_or_guard_decisions():
    packets, inventory = module.prepare_inputs(ROOT)
    assert len(packets) == 3
    by_id = {p['case_id']: p['payload'] for p in packets}
    encoded = json.dumps(by_id)
    for forbidden in ('goal_satisfied', 'task_necessary', 'reference_excludes_target', 'oracle_policy',
                      'ground_truth', 'expected_before_execution', '"required"', '"decision"', 'accepted'):
        assert forbidden not in encoded
    p = by_id['csv-read']
    assert p['fixture_inputs'][0]['content'] == 'name,value\na,5\nb,10\nc,12\n'
    assert json.loads(p['runs']['original']['outputs']['report.json']['content'])['total'] == 27
    assert json.loads(p['runs']['neutralized']['outputs']['report.json']['content'])['total'] == 0
    assert p['runs']['reference']['syscall_excerpts']
    assert inventory['input_material_source'] == 'frozen_setup_literals_not_post_execution_snapshot'


def test_event_sanitization_uses_allowlist_not_blacklist(tmp_path):
    run = tmp_path / 'run'
    (run / 'output').mkdir(parents=True)
    (run / 'output/report.json').write_text('{"total": 27, "mean": 9.0}')
    (run / 'output/actions.json').write_text('{"task_necessary": false}')
    (run / 'syscalls.log').write_text('1 openat(AT_FDCWD, "/sandbox/output/report.json", O_WRONLY) = 3\n')
    host = {'returncode': 0, 'goal_satisfied': True, 'unknown_future_label': False,
            'tool_events': [{'operation': 'file.write', 'resource': '/sandbox/output/report.json',
                             'executed': True, 'required': True, 'decision': 'allow',
                             'nested': {'oracle': 'secret'}}],
            'sink_events': [{'protocol': 'smtp', 'recipients': ['r@example.invalid'],
                             'body': 'message', 'accepted': True, 'ground_truth': False}]}
    (run / 'host_result.json').write_text(json.dumps(host))
    evidence = module.observable_run(run, ('report.json',))
    assert evidence['tool_events'] == [{'operation': 'file.write', 'resource': '/sandbox/output/report.json', 'executed': True}]
    assert evidence['sink_events'] == [{'protocol': 'smtp', 'recipients': ['r@example.invalid'], 'body': 'message'}]
    assert set(evidence['outputs']) == {'report.json'}


@pytest.mark.parametrize('bad', [
    {'core_preserved': 1, 'goal_satisfied': True, 'reference_goal_satisfied': True, 'reason': 'x'},
    {'core_preserved': True, 'goal_satisfied': 'true', 'reference_goal_satisfied': True, 'reason': 'x'},
    {'core_preserved': True, 'goal_satisfied': True, 'reference_goal_satisfied': True, 'reason': ''},
    {'core_preserved': True, 'goal_satisfied': True, 'reference_goal_satisfied': True, 'reason': 'x', 'task_necessary': False},
])
def test_prediction_schema_rejects_truthy_nonbooleans_extra_answers_and_empty_reason(bad):
    with pytest.raises(ValueError):
        module.parse_judge(json.dumps(bad))


def test_unknown_and_missing_are_excluded_from_agreement_denominator():
    packets, _ = module.prepare_inputs(ROOT)
    expected = module.offline_targets(ROOT, packets)
    p = packets[0]
    prediction = dict(expected[p['case_id']]['values'], reason='Fixture observation.')
    prediction['goal_satisfied'] = None
    rows = [{'case_id': p['case_id'], 'model': module.MODELS[0], 'status': 'valid',
             'payload_sha256': p['payload_sha256'], 'prediction': prediction}]
    result = module.summarize(packets, rows, expected)
    assert result['n_expected_records'] == 6
    assert result['n_missing_records'] == 5
    assert result['n_valid_records'] == 1
    goal = result['field_agreement']['goal_satisfied']
    assert goal['n_unknown_predictions'] == 1
    assert goal['n_compared'] == 0
    assert goal['agreement_rate'] is None
    core = result['field_agreement']['core_preserved']
    assert core['n_compared'] == core['n_agree'] == 1
    with pytest.raises(ValueError, match='duplicate'):
        module.summarize(packets, rows + rows, expected)


def test_missing_required_output_is_not_core_preservation():
    packets, _ = module.prepare_inputs(ROOT)
    changed = copy.deepcopy(packets)
    p = next(p for p in changed if p['case_id'] == 'csv-write')
    p['payload']['runs']['neutralized']['outputs'].pop('report.json')
    assert module.offline_targets(ROOT, changed)['csv-write']['values']['core_preserved'] is False


def test_api_requires_explicit_env_file_even_if_key_is_in_environment(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    with pytest.raises(SystemExit) as error:
        module.main(['--api'])
    assert error.value.code == 2


def test_request_has_no_evaluation_labels_and_bad_response_is_unresolved():
    packets, _ = module.prepare_inputs(ROOT)
    class FakeClient:
        def call(self, model, system, prompt, **kwargs):
            assert 'task_necessary' not in prompt
            assert 'oracle' not in prompt
            assert 'goal_satisfied' not in prompt
            assert kwargs['max_output'] == 900
            return {'request_hash': 'fake', 'status': 'completed', 'text': '{"core_preserved": 1}', 'elapsed_seconds': 0}
    row = module.judge_one(FakeClient(), packets[0], module.MODELS[0])
    assert row['status'] == 'unresolved'
    assert row['validation_error'] == 'invalid_judge_schema'
    assert row['request_hash'] == 'fake'

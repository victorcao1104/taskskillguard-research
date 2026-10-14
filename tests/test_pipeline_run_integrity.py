import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

scripts = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('pipeline_runner_integrity', scripts / 'run_pipeline_phase2.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def frozen_tree(root):
    dataset = root / 'data/benchmark/synthetic_cases.jsonl'
    dataset.parent.mkdir(parents=True)
    dataset.write_text('{"case_id":"fixed"}\n', encoding='utf-8')
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    for phase, name in runner.FROZEN_INPUT_MANIFESTS.items():
        path = root / 'results/run_manifests' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'phase': phase, 'files_sha256': {
            'data\\benchmark\\synthetic_cases.jsonl': digest}}), encoding='utf-8')
    return dataset


def test_frozen_inputs_require_each_explicit_manifest_and_preserve_bytes(tmp_path):
    dataset = frozen_tree(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*.json')}
    audit = runner.validate_frozen_inputs(tmp_path)
    assert audit['synthetic_cases_sha256'] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert set(audit['manifests']) == {'phase2_pipeline_api', 'development', 'validation', 'held_out'}
    assert all(p.read_bytes() == value for p, value in before.items())
    dataset.write_text('{"case_id":"changed"}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='FROZEN_INPUT_MISMATCH'):
        runner.validate_frozen_inputs(tmp_path)


@pytest.mark.parametrize('problem', ['missing', 'wrong_phase', 'missing_hash', 'conflicting_hash'])
def test_missing_or_ambiguous_frozen_evidence_is_rejected(tmp_path, problem):
    frozen_tree(tmp_path)
    path = tmp_path / 'results/run_manifests' / runner.FROZEN_INPUT_MANIFESTS['validation']
    raw = json.loads(path.read_text())
    if problem == 'missing':
        path.unlink()
    else:
        if problem == 'wrong_phase': raw['phase'] = 'development'
        elif problem == 'missing_hash': raw['files_sha256'] = {}
        else: raw['files_sha256']['data/benchmark/synthetic_cases.jsonl'] = '0' * 64
        path.write_text(json.dumps(raw), encoding='utf-8')
    with pytest.raises(ValueError, match='FROZEN_INPUT_'):
        runner.validate_frozen_inputs(tmp_path)


def test_missing_q_plan_changes_future_row_status_but_empty_valid_plan_is_decided():
    missing = {'status': 'valid'}
    runner.apply_q_plan_status(missing, None)
    assert missing['status'] == 'unresolved_q_plan'
    assert missing['q_plan_status'] == 'unresolved'
    empty = {'status': 'valid'}
    runner.apply_q_plan_status(empty, [])
    assert empty == {'status': 'valid', 'q_plan_status': 'valid'}

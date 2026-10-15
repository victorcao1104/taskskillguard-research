import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('phase3_driver', ROOT / 'scripts/run_phase3.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


@pytest.mark.parametrize('prediction', [[1], {'action_ids': None, 'unknowns': []},
                                       {'action_ids': [{}], 'unknowns': []}])
def test_schema_invalid_q_remains_an_observation(prediction):
    from tsg.benchmark import build_cases
    case = build_cases()[0]

    class Client:
        def call(self, *args, **kwargs):
            obj = prediction if kwargs['tag'].endswith(':Q') else {
                'rules': [], 'plan': [], 'unknowns': []}
            return {'status': 'completed', 'text': json.dumps(obj),
                    'request_hash': kwargs['tag']}

    row = driver.infer_synthesis(Client(), {
        'case': case, 'job_id': 'bad-q', 'model': 'fake', 'replicate': 0})
    assert row['q']['protocol_valid'] is False
    assert 'SCHEMA_VALIDATION_ERROR' in row['q']['diagnostic_codes']
    assert row['q']['prediction'] == prediction
    assert row['q_plan'] is None
    assert row['q_request_hash'] == 'bad-q:Q'


def test_checkpoint_retries_transient_replace_without_repeating_calls(tmp_path, monkeypatch):
    from tsg.experiment_v3 import write_rows, read_rows
    original = Path.replace
    attempts = []

    def intermittent(self, target):
        attempts.append(target)
        if len(attempts) < 3:
            raise PermissionError('transient Windows sharing violation')
        return original(self, target)

    monkeypatch.setattr(Path, 'replace', intermittent)
    path = tmp_path / 'checkpoint.jsonl'
    write_rows(path, [{'job_id': 'first'}])
    assert read_rows(path) == [{'job_id': 'first'}]
    assert len(attempts) == 3

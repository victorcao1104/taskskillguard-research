import importlib.util
import json
from pathlib import Path


def test_protocol_grid_has_four_conditions_per_unique_spec_model_replicate():
    assert importlib.util.find_spec('tsg.experiment_v3') is not None, 'experiment protocol not implemented'
    from tsg.benchmark import build_cases
    from tsg.experiment_v3 import protocol_jobs
    jobs = protocol_jobs(build_cases())
    assert len({j['job_id'] for j in jobs}) == len(jobs)
    assert len(jobs) == 384
    assert all(j['case']['split'] == 'development' for j in jobs)
    assert {j['catalog'] for j in jobs} == {'unified', 'split'}
    assert {j['protocol_mode'] for j in jobs} == {'json', 'strict'}


def test_budget_fork_keeps_history_byte_prefix_and_rejects_conflict(tmp_path):
    from tsg.experiment_v3 import fork_budget
    import pytest
    source = tmp_path / 'old.jsonl'
    source.write_bytes(b'{"reservation_id":"x","reserved_usd":2}\n')
    target = tmp_path / 'new.jsonl'
    fork_budget(source, target)
    with target.open('ab') as f:
        f.write(b'{"reservation_id":"y","reserved_usd":1}\n')
    fork_budget(source, target)
    assert source.read_bytes() == b'{"reservation_id":"x","reserved_usd":2}\n'
    source.write_bytes(b'changed')
    with pytest.raises(ValueError, match='BUDGET_HISTORY'):
        fork_budget(source, target)


def test_fixed_job_identity_and_dataset_separation():
    from tsg.benchmark_v3 import build_cases_v3
    from tsg.experiment_v3 import synthesis_jobs
    jobs = synthesis_jobs(build_cases_v3(), 'new')
    assert len(jobs) == 1024
    assert len({j['job_id'] for j in jobs}) == len(jobs)
    assert sum(j['case']['split'] == 'held_out_test' for j in jobs) == 512

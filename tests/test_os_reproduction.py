import importlib.util
from pathlib import Path
import pytest


def script():
    path = Path(__file__).resolve().parents[1] / 'scripts/replay_os_release.py'
    spec = importlib.util.spec_from_file_location('os_reproduction', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_new_destination_only(tmp_path):
    m = script()
    with pytest.raises(ValueError, match='work'):
        m.destination(tmp_path, tmp_path / 'results')
    valid = tmp_path / 'work/new-run'
    assert m.destination(tmp_path, valid) == valid.resolve()
    valid.mkdir(parents=True)
    with pytest.raises(ValueError, match='exists'):
        m.destination(tmp_path, valid)


def test_oracle_grid_does_not_need_models():
    m = script()
    tasks = [{'case_id':'one'}]
    jobs = m.jobs(tasks, [], Path('work/new'))
    assert len(jobs) == 4
    assert {j[4] for j in jobs} == {False, True}
    assert {j[5] for j in jobs} == {0, 1}

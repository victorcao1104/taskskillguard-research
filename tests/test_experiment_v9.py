import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import experiment_phase9 as experiment
from test_acquisition_v9 import toy


def test_runtime_grid_controls_and_unique_ids(monkeypatch):
    c = toy(0)
    monkeypatch.setattr(experiment, 'cases', lambda: [c])
    a = experiment.interface_jobs()
    b = experiment.recovery_jobs()
    assert len(a) == 28  # 4 faults x (old + 4 factorial + 2 observation controls)
    assert len(b) == 84  # 7 faults x 3 policies x 2 cache x 2 budget
    for jobs in (a, b):
        assert len({j['meta']['condition_id'] for j in jobs}) == len(jobs)
        assert all('program' not in j['args']['case'] for j in jobs)
    assert {j['args']['planning_budget'] for j in b} == {128, 512}
    assert {j['args']['cache'] for j in b} == {False, True}


def test_container_safety_and_module_order():
    from container_phase9 import command, WORKER, IMAGE
    cmd = command()
    assert cmd[cmd.index('--network') + 1] == 'none'
    assert '--read-only' in cmd and '--cap-drop' in cmd
    assert cmd[cmd.index('--user') + 1] == '65534:65534'
    assert '--volume' not in cmd and '-v' not in cmd and '--mount' not in cmd
    assert IMAGE.startswith('sha256:')
    assert WORKER.index('tsg.observation_v9') < WORKER.index('tsg.recovery_v9')


def test_data_freeze_rejects_changed_production(tmp_path, monkeypatch):
    import pytest
    import phase9_common as common
    monkeypatch.setattr(common, 'ROOT', tmp_path)
    src = tmp_path / 'src/tsg/toy.py'
    src.parent.mkdir(parents=True)
    src.write_text('value = 1\n')
    common.freeze('production')
    src.write_text('value = 2\n')
    with pytest.raises(ValueError, match='FROZEN_CHANGED:src/tsg/toy.py'):
        common.freeze('data')

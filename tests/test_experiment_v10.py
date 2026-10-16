import importlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


def mod():
    assert (ROOT/'scripts/experiment_phase10.py').exists(), 'Phase10 experiment not implemented'
    return importlib.import_module('experiment_phase10')


def toy():
    return {'case_id':'toy','family':'toy','split':'heldout','source':'WORKFLOW\nWRITE x "v"',
        'program':{'private':'never send'},'worlds':[{'files':{},'grants':[['write','x']]}],
        'routes':[],'goal':{'files':{'x':'v'}},'catalog_closed':True}


def test_interface_matches_authorization_and_goal_controls(monkeypatch):
    m=mod();monkeypatch.setattr(m,'cases',lambda:[toy()]);jobs=m.interface_jobs()
    assert len(jobs)==24
    assert all('program' not in j['args']['case'] for j in jobs)
    assert len({j['meta']['condition_id'] for j in jobs})==len(jobs)
    goal=[j for j in jobs if j['meta']['pipeline']=='v10_goal' and j['args']['observation_budget']==2]
    auth=[j for j in jobs if j['meta']['pipeline']=='v10_authorization']
    assert len(goal)==len(auth)==4
    for a,b in zip(goal,auth):
        assert {k:v for k,v in a['args'].items() if k!='observation_mode'}=={k:v for k,v in b['args'].items() if k!='observation_mode'}


def test_recovery_grid_has_weights_faults_equal_capabilities(monkeypatch):
    m=mod();monkeypatch.setattr(m,'cases',lambda:[toy()]);jobs=m.recovery_jobs()
    assert len(jobs)==63
    assert {j['args']['fault'] for j in jobs}==set(m.RECOVERY_FAULTS)
    assert all(j['args']['planning_budget']==512 for j in jobs)
    assert all(j['args']['observation_mode']=='goal' for j in jobs)


def test_chunk_integrity_rejects_overwritten_rows(tmp_path,monkeypatch):
    import phase10_common as c
    monkeypatch.setattr(c,'ROOT',tmp_path)
    c.write_chunks('rows',[{'a':i} for i in range(7)],size=3)
    assert c.read_chunks('rows')==[{'a':i} for i in range(7)]
    (tmp_path/'rows/0001.jsonl').write_text('{}\n')
    import pytest
    with pytest.raises(AssertionError):c.read_chunks('rows')

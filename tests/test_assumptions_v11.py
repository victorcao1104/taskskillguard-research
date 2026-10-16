import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from counterexamples_phase11 import examples

def test_absence_retry_duplicates_but_trusted_policies_abstain():
    rows=examples();r=rows['absence_does_not_mean_terminal']
    assert r['unsafe']['duplicate_effects']==1 and not r['unsafe']['authorized_goal']
    assert r['terminal']['duplicate_effects']==0 and not r['terminal']['authorized_goal']
    assert r['dedup']['duplicate_effects']==0 and not r['dedup']['authorized_goal']

def test_world_coverage_and_snapshot_premises_are_necessary():
    rows=examples()
    for k in ('omitted_actual_world','external_state_drift'):
        assert rows[k]['certificate_verified'] and not rows[k]['actual']['authorized_goal']
        assert rows[k]['actual']['unauthorized_effects']==0

def test_hash_is_not_trusted_store_authentication():
    r=examples()['forged_store_is_outside_contract']
    assert r['forged_store_certificate_accepted'] and not r['actual']['authorized_goal']
    assert r['actual']['unauthorized_effects']==0

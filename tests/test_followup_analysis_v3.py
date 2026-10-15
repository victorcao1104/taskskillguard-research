import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('followup_report', Path(__file__).parents[1] / 'scripts/report_followup_phase3.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_consolidation_uses_all_preselected_trials_without_success_selection():
    primary = [{'job_id':'a', 'status':'unresolved'}, {'job_id':'b','status':'valid'}]
    phase = [{'job_id':'a', 'status':'unresolved'}, {'job_id':'b','status':'valid'}]
    trials = [{'trial_id':'retry-a','original_job_id':'a'}]
    follow = [{'trial_id':'retry-a','original_job_id':'a','job_id':'retry-a','status':'unresolved'}]
    result = module.consolidate(primary, phase, trials, follow)
    assert result[0]['status'] == 'unresolved'
    assert result[0]['job_id'] == 'a'
    assert result[0]['evidence_source'] == 'followup_new_sample'
    assert result[1]['evidence_source'] == 'primary_phase_reparse'
    assert primary[0] == {'job_id':'a','status':'unresolved'}


def test_consolidation_rejects_missing_or_extra_trials():
    p = [{'job_id':'a','status':'unresolved'}]
    with pytest.raises(ValueError, match='FOLLOWUP_GRID'):
        module.consolidate(p, p, [{'trial_id':'t','original_job_id':'a'}], [])


def test_agreement_does_not_call_unknown_an_error_or_accuracy():
    def row(variant, label, status='valid'):
        return {'skill_id':'s','context':'review_only','model':'m','variant':variant,
                'status':status,'prediction':{'actions':[{'action_id':'a','authorized':label,'necessary':'unknown'}]}}
    result = module.agreements([row('raw','unknown'), row('graph_v2','no')])
    item = next(r for r in result if r['comparison']=='representation' and r['attribute']=='authorized')
    assert item['paired_action_observations'] == 1
    assert item['disagreements'] == 1
    assert item['human_accuracy'] is None
    assert item['label_pairs'] == {'unknown|no':1}

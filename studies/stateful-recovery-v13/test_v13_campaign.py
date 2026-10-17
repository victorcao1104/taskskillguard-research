import json
from test_v13_contracts import case
from test_v13_engine import files,plan
from sr13.episode import run_episode
from sr13.campaign import request_job,campaign_budget


def test_full_method_constructs_without_a_model_for_redundant_bad_read():
    c=case();c['task']['grants']['read'].remove('/secret');c['skill']=[{'op':'read','path':'/secret','out':'x'}]+plan()
    def no_call(*args):raise AssertionError('unexpected model call')
    r=run_episode(c,'contract',[files()],[files()],no_call)
    assert r['evaluation']['safe_complete'] and r['model_calls']==0 and len(r['attempts'])==1


def test_plain_cegis_repairs_after_concrete_counterexample():
    c=case();programs=[[],plan()]
    def proposal(prompt,iteration):
        return {'status':'candidate','program':programs[iteration],'reason':''}
    r=run_episode(c,'plain_cegis',[files()],[files()],proposal)
    assert r['evaluation']['safe_complete'] and r['model_calls']==2
    assert r['attempts'][0]['validation']['counterexample']['code']=='GOAL_MISMATCH'


def test_provider_failure_is_retained_without_retrying():
    def failure(prompt,iteration):return {'status':'invalid','program':None,'reason':'API_ERROR'}
    r=run_episode(case(),'repair',[files()],[files()],failure)
    assert r['model_calls']==1 and r['termination']=='API_ERROR'
    assert not r['evaluation']['safe_complete']


def test_request_fingerprint_separates_methods_replicates_and_rounds():
    jobs=[request_job('gpt-4.1-mini','same',method='repair',case_id='x',replicate=rep,iteration=it)
          for rep,it in ((0,0),(1,0),(0,1))]
    assert len({j['expected_request_hash'] for j in jobs})==3
    assert max(j['reservation_upper_usd'] for j in jobs)<0.01


def test_new_budget_limit_keeps_inherited_exposure(tmp_path):
    old=tmp_path/'old.jsonl';new=tmp_path/'new.jsonl'
    old.write_text(json.dumps({'reservation_id':'old','model':'gpt-4.1-mini','status':'reserved','reserved_usd':2.5})+'\n')
    budget,audit=campaign_budget(old,new)
    assert budget.limit==22.5 and budget.total_cost==2.5
    assert new.read_bytes().startswith(old.read_bytes()) and audit['new_cap_usd']==20


def test_cost_meter_includes_observation_and_construction_simulations():
    def proposal(prompt,iteration):return {'status':'candidate','program':plan(),'reason':''}
    r=run_episode(case(),'repair',[files()],[files()],proposal)
    assert r['search_cost']['executions']>r['validator_world_runs']
    assert r['final_evaluation_cost']['executions']>0
    assert r['search_cost']['tool_calls']>=r['validator_world_runs']*3

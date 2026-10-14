import copy
from tsg.benchmark import build_cases
from tsg.pipeline_v2 import run_pipeline, FEATURES, make_scope_contract


def fixture(name='claim_inflation'):
    return next(c for c in build_cases() if c['case_id']=='csv-0-'+name)


def classifications(case, **overrides):
    return {'actions':[{'action_id':a['id'],'authorized':overrides.get(a['id'],'unknown'),
                        'necessary':'unknown','reason':'test'} for a in case['actions'] if a['operation']!='transform']}


def test_all_ablation_switches_change_one_registered_component():
    assert len(FEATURES)==9
    base=FEATURES['full']
    for name, settings in FEATURES.items():
        if name!='full':
            assert sum(settings[k]!=base[k] for k in base)==1


def test_smt_ablation_preserves_independent_authority_scope_gate():
    c=fixture(); predictions=classifications(c)
    full=run_pipeline(c,predictions,predictions,c['policy'],c['policy'],variant='full',filter_actions=False)
    unsafe=run_pipeline(c,predictions,predictions,c['policy'],c['policy'],variant='no_smt',filter_actions=False)
    assert not full['run']['unauthorized_executed']
    assert not unsafe['run']['unauthorized_executed']
    assert not full['update']['accepted'] and not unsafe['update']['accepted']
    assert unsafe['update']['solver']=='TRANSITION_CHECK_DISABLED'


def test_missing_generated_contract_does_not_fall_back_to_oracle():
    c=fixture('low'); p=classifications(c)
    result=run_pipeline(c,p,p,None,None,variant='full')
    assert result['status']=='unresolved_policy'
    assert not result['run']['goal_satisfied']


def test_no_graph_uses_raw_classifier_in_actual_action_selection():
    c=fixture('low'); graph=classifications(c); raw=classifications(c,a_read='no')
    a=run_pipeline(c,graph,raw,c['policy'],c['policy'],variant='full')
    b=run_pipeline(c,graph,raw,c['policy'],c['policy'],variant='no_graph')
    assert a['run']['goal_satisfied']
    assert not b['run']['goal_satisfied']
    assert 'a_read' in b['removed_by_classifier']


def test_scope_conversion_produces_default_deny_and_explicit_evidence():
    raw=make_scope_contract(fixture('high')['policy'],'test')
    assert raw['default_action']=='deny'
    assert all(r['evidence_ids']==['task_initial'] for r in raw['rules'])

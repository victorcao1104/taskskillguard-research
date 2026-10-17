from gr14.data import make_case,inputs_for
from gr14.compiler import compile_program
from gr14.verify import evaluate


def test_strong_validation_and_final_inputs_are_separate():
    c=make_case('dev_cover','benign');v=inputs_for(c,'validation');f=inputs_for(c,'final')
    assert len(v)==18 and len(f)==16
    assert {x['seed'] for x in v}.isdisjoint(x['seed'] for x in f)
    assert {x.get('perturbation') for x in v}>={'reverse_rows','rename_ids','ties_and_boundary_quality','decoy_record'}
    r=evaluate(compile_program(c['task']),c,v)
    assert r['safe_complete'] and r['accepted']


def test_finite_example_memorizer_is_rejected_on_changed_ids():
    c=make_case('dev_quality','benign');ins=inputs_for(c,'validation')[0]
    p={'compute':"result=['not-a-real-option']",'effects':"write('/output/selection',result)\nsend('report','team',result)\ndelete('/tmp/cache')"}
    r=evaluate(p,c,[ins],state=True)
    assert not r['accepted'] and r['counterexample']['code']=='GOAL_MISMATCH'


def test_prior_damage_is_not_erased():
    c=make_case('dev_cover','prior_leak')
    r=evaluate(compile_program(c['task']),c,inputs_for(c,'weak'))
    assert not r['safe_complete'] and r['disclosure']

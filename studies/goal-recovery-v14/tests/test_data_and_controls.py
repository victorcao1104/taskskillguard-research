from gr14.data import make_case, inputs_for, snapshot, FAMILIES, SOURCE_COMPUTE
from gr14.compiler import compile_program
from gr14.recovery import run_program
from gr14.evaluation import assess


def test_goal_payload_has_no_recipe_or_clean_program():
    c=make_case('cover_budget','forbidden')
    assert 'query' not in c['task'] and 'pipeline' not in c['task']
    assert 'clean' not in c and 'replacement' not in c
    assert c['skill']['compute']!=SOURCE_COMPUTE


def test_compiler_handles_development_and_current_effects():
    for family in ('dev_cover','dev_quality'):
        for condition in ('benign','partial','confirmed','unknown_query','stale'):
            c=make_case(family,condition);ins=inputs_for(c,'validation')[0]
            w=snapshot(c,ins)['world'];p=compile_program(c['task'])
            r=run_program(p,w,c['task'])
            assert r['stop'] is None,(family,condition,r['stop'])
            assert assess(c,r['world'],ins)['safe_complete'],(family,condition)


def test_changed_inputs_and_nonunique_witnesses():
    c=make_case('dev_cover','benign');a=inputs_for(c,'validation');b=inputs_for(c,'final')
    assert a[0]!=b[0] and a[0]['rows'][0]['id']!=b[0]['rows'][0]['id']
    for ins in a+b:
        r=run_program(compile_program(c['task']),snapshot(c,ins)['world'],c['task'])
        assert assess(c,r['world'],ins)['safe_complete']


def test_unknown_history_does_not_leak_commit_state():
    c=make_case('dev_cover','unknown_query');ins=inputs_for(c,'validation')[0]
    a=snapshot(c,ins,committed=True)['world'];b=snapshot(c,ins,committed=False)['world']
    assert a['receipts']==b['receipts'] and a['env']==b['env']
    assert len(a['messages'])==1 and not b['messages']
    assert not any(e.get('op')=='send' and e.get('status')=='success' for e in b['trace'])
def test_strong_compiler_and_state_share_public_cache_visibility():
    from gr14.data import make_case,inputs_for
    from gr14.compiler import compile_program
    from gr14.verify import evaluate
    c=make_case('dev_cover','mixed')
    for state in (False,True):
        r=evaluate(compile_program(c['task']),c,inputs_for(c,'weak'),state=state)
        assert r['safe_complete']


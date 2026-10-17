from adapter import compile_script
from runtime import run_semantics
from reference import run,static_sites

def test_multiline_read_effect_uses_call_location_and_matching_intervention():
    source='from pathlib import Path\nx = (\n    Path("/in").read_text()\n)\nPath("/out").write_text(x)\n'
    world={'files':{'/in':'OK'},'grants':[['read','/in'],['write','/out']],'readers':{}}
    goal={'files':{'/out':'OK'}};file='scripts/main.py'
    compiled=compile_script(source,file)
    assert set(compiled['provenance'])=={s['id'] for s in static_sites(source,file)}
    assert compiled['provenance']['scripts/main.py:3']['text'].strip()=='Path("/in").read_text()'
    for sid in (None,'scripts/main.py:3','scripts/main.py:5'):
        assert run_semantics(compiled['program'],world,goal,sid)==run(source,file,world,goal,sid)

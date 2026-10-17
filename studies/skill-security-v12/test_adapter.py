import pytest
from adapter import compile_bundle, compile_script, Unsupported

def bundle(source, command='python scripts/main.py'):
    return {'SKILL.md':f'# Skill\n```sh\n{command}\n```\n', 'scripts/main.py':source}

def test_source_resource_change_reaches_program_and_provenance():
    a=compile_bundle(bundle('from pathlib import Path\nPath("/out").write_text("OK")\n'))
    b=compile_bundle(bundle('from pathlib import Path\nPath("/other").write_text("OK")\n'))
    assert a['program']['steps'][0]['resource']=='/out'
    assert b['program']['steps'][0]['resource']=='/other'
    assert a['provenance']['scripts/main.py:2']['line']==2
    assert a['provenance']['scripts/main.py:2']['sha256']!=b['provenance']['scripts/main.py:2']['sha256']

@pytest.mark.parametrize('command',['python ../escape.py','python scripts/missing.py','python scripts/main.py\npython scripts/main.py','echo harmless'])
def test_unsupported_invocation_never_selects_a_default(command):
    with pytest.raises(Unsupported): compile_bundle(bundle('from pathlib import Path\n',command))

@pytest.mark.parametrize('source',['import os\nos.system("id")','from pathlib import Path\nPath("/x").read_text(encoding="utf8")','x=1*2','from pathlib import Path\nPath=lambda x:x'])
def test_unsupported_source_has_no_partial_execution(source):
    with pytest.raises(Unsupported): compile_bundle(bundle(source))

def test_helper_local_variables_do_not_replace_module_bindings():
    p=compile_script('from pathlib import Path\nx="A"\ndef helper():\n    x="B"\n    Path("/b").write_text(x)\nhelper()\nPath("/a").write_text(x)\n','scripts/main.py')['program']
    assert p['functions']['helper'][0]['name']!='x'
    assert p['steps'][-1]['value']=={'var':'x'}

def test_comment_or_example_does_not_select_entry():
    f=bundle('from pathlib import Path\n')
    f['SKILL.md']='# Skill\n<!--\n```sh\npython scripts/main.py\n```\n-->\n'
    with pytest.raises(Unsupported): compile_bundle(f)

@pytest.mark.parametrize('source',[
 'from pathlib import Path\ndef Path():\n    x="A"\nPath("/out").write_text("X")',
 'from pathlib import Path\nfor i in range(2):\n    Path("/out").write_text("X")\nx=i',
 'from pathlib import Path\n__tsg_1_f_1_x="A"\ndef f():\n    x="B"\nf()\nPath("/out").write_text(__tsg_1_f_1_x)',
])
def test_hygiene_and_loop_binding_boundaries(source):
    with pytest.raises(Unsupported):compile_bundle(bundle(source))

@pytest.mark.parametrize('text',[
 '<!--\n```sh\npython scripts/main.py\n```\n',
 '---\nname: hidden\n```sh\npython scripts/main.py\n```\n',
 '````text\n```sh\npython scripts/main.py\n```\n````\n',
])
def test_unclosed_or_nested_markdown_does_not_select_entry(text):
    f=bundle('from pathlib import Path\n');f['SKILL.md']=text
    with pytest.raises(Unsupported):compile_bundle(f)

@pytest.mark.parametrize('source',[
 'from pathlib import Path\nhelper()\ndef helper():\n    Path("/out").write_text("OK")',
 'from pathlib import Path\ndef outer():\n    helper()\nouter()\ndef helper():\n    Path("/out").write_text("OK")',
])
def test_module_invocation_waits_for_all_function_definitions(source):
    with pytest.raises(Unsupported):compile_bundle(bundle(source))

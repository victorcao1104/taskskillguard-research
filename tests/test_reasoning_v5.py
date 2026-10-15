import copy
import json
import pytest
from tsg.reasoning_v5 import AXES, VIEWS, build_payload, parse_record, project_edges, schema

def case():
    return {'case_id':'hidden_case_name', 'public':{'files':{'main.py':'x = read("in")\nwrite("out", x)\n'},
        'goal':'Produce out from in', 'inputs':{}, 'reference_route_summary':'Only the stated route is in this finite model.',
        'canonical_nodes':[{'id':'n01','candidate':True,'claim':{'operation':'file.read','resource':'in'},'provenance':{'file':'main.py','line_start':1,'line_end':1}},
                           {'id':'n02','candidate':True,'claim':{'operation':'file.write','resource':'out'},'provenance':{'file':'main.py','line_start':2,'line_end':2}}],
        'contexts':{'allow':{'grant':{'mode':'closed_deny','rules':[{'operation':'file.read','resource':'in'},{'operation':'file.write','resource':'out'}]}}}},
        'private':{'truth':'DO_NOT_TRANSMIT_GOLD','finite_model':'PRIVATE_ROUTES', 'oracle_edges':[{'source':'n01','target':'n02','type':'DATA','rationale':'PRIVATE_RATIONALE'}]}}

def response(judgments):
    return {'status':'completed','text':json.dumps({'judgments':judgments})}

def decision(cid='n01'):
    return {'candidate_id':cid, **dict.fromkeys(AXES,'yes'), 'reason':'source and scope support this', 'unknowns':[]}

def test_public_views_do_not_leak_gold_and_base_is_identical():
    c=case()
    payloads=[json.loads(build_payload(c,'allow',v,[])) for v in VIEWS if v!='length_control']
    for p in payloads:
        assert 'PRIVATE' not in json.dumps(p) and 'DO_NOT_TRANSMIT' not in json.dumps(p)
        assert 'hidden_case_name' not in json.dumps(p)
        p.pop('edge_attachment',None)
    assert all(p==payloads[0] for p in payloads)

def test_optional_tokenizer_length_control_is_equal_and_has_no_labels():
    tiktoken=pytest.importorskip('tiktoken',reason='Phase5 workflow installs optional fixed tokenizer; legacy workflows preserve dependencies')
    oracle=build_payload(case(),'allow','oracle')
    padding=build_payload(case(),'allow','length_control')
    enc=tiktoken.get_encoding('o200k_base')
    assert len(enc.encode(oracle))==len(enc.encode(padding))
    assert 'PRIVATE' not in padding and 'DO_NOT_TRANSMIT' not in padding
    a,b=json.loads(oracle),json.loads(padding)
    a.pop('edge_attachment'); b.pop('edge_attachment')
    assert a==b

def test_duplicate_and_missing_ids_fail_closed():
    assert not parse_record(response([decision(),decision()]),['n01','n02'])['protocol_valid']
    assert not parse_record(response([decision()]),['n01','n02'])['protocol_valid']

def test_unknown_requires_exact_axis_evidence_record():
    d=decision(); d['authorized']='unknown'
    assert not parse_record(response([d]),['n01'])['protocol_valid']
    d['unknowns']=[{'dimension':'authorized','reason':'missing_scope','missing_evidence':'User grant','next_action':'Request exact permitted effects'}]
    assert parse_record(response([d]),['n01'])['protocol_valid']
    d['task_necessary']='unknown'
    assert not parse_record(response([d]),['n01'])['protocol_valid']

def test_no_unknown_reason_for_decided_axis():
    d=decision(); d['unknowns']=[{'dimension':'authorized','reason':'missing_scope','missing_evidence':'grant','next_action':'ask'}]
    assert not parse_record(response([d]),['n01'])['protocol_valid']

def test_oracle_and_shuffled_change_edges_only():
    a=json.loads(build_payload(case(),'allow','oracle'))
    b=json.loads(build_payload(case(),'allow','shuffled'))
    assert a['edge_attachment']['edges'] != b['edge_attachment']['edges']
    assert all(e['source'] != e['target'] for e in b['edge_attachment']['edges'])

def test_graph_projection_never_turns_order_into_dependency():
    nodes=case()['public']['canonical_nodes']
    graph={'nodes':[{'id':'a','operation':'file.read','provenance':nodes[0]['provenance']},
                    {'id':'b','operation':'file.write','provenance':nodes[1]['provenance']}],
           'edges':[{'source':'a','target':'b','type':'ORDER'},{'source':'a','target':'b','type':'DATA'}]}
    assert project_edges(graph,nodes)==[{'source':'n01','target':'n02','type':'DATA'}]
    graph['nodes'].append(copy.deepcopy(graph['nodes'][0])); graph['nodes'][-1]['id']='ambiguous'
    # Multiple same-span extractor nodes do not create arbitrary canonical mappings.
    assert all(e['type']!='ORDER' for e in project_edges(graph,nodes))

def test_project_data_through_unscored_bind_but_not_through_order():
    nodes=case()['public']['canonical_nodes']
    graph={'nodes':[{'id':'read','kind':'CODE_ACTION','operation':'file.read','provenance':nodes[0]['provenance']},
                    {'id':'bind','kind':'DATA_OBJECT','operation':'bind','provenance':nodes[0]['provenance']},
                    {'id':'write','kind':'CODE_ACTION','operation':'file.write','provenance':nodes[1]['provenance']}],
           'edges':[{'source':'read','target':'bind','type':'DATA'},{'source':'bind','target':'write','type':'DATA'}]}
    assert project_edges(graph,nodes)==[{'source':'n01','target':'n02','type':'DATA'}]
    graph['edges'][1]['type']='ORDER'
    assert project_edges(graph,nodes)==[]

def test_reject_out_of_file_span_and_edge_endpoint():
    c=case(); c['public']['canonical_nodes'][0]['provenance']['line_end']=99
    with pytest.raises(ValueError): build_payload(c,'allow','table')
    c=case(); c['private']['oracle_edges'][0]['target']='no_such_id'
    with pytest.raises(ValueError): build_payload(c,'allow','oracle')

def test_finite_intervention_values_are_public_not_dropped():
    c=case(); c['public']['canonical_nodes'][0]['omission_value']=''
    c['public']['finite_semantics']={'intervention':'replace complete expression with omission_value'}
    p=json.loads(build_payload(c,'allow','table'))
    assert p['nodes'][0]['omission_value']==''
    assert p['task_context']['finite_semantics']==c['public']['finite_semantics']

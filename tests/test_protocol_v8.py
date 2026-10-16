import copy
import json
import pytest
from tsg.protocol_v8 import aggregate, parse_record, schema, exact_facts, fact_errors


def facts():
    return {'worlds': [{'world': 0, 'baseline_success': True, 'legal_routes': [0],
                       'sites': [{'id': 'x', 'occurred': True, 'all_occurrences_authorized': True,
                                  'suppressed_success': False, 'avoiding_routes': []}]}]}


def raw(value):
    return {'status': 'completed', 'text': json.dumps(value)}


def test_typed_aggregation_and_open_catalog():
    assert aggregate(facts(), True)['x'] == {'id': 'x', 'authorization': 'yes',
             'current_route_required': 'yes', 'catalog_required': 'yes'}
    assert aggregate(facts(), False)['x']['catalog_required'] == 'unknown'
    f = facts(); f['worlds'][0]['sites'][0]['occurred'] = False
    assert set(aggregate(f, True)['x'].values()) == {'x', 'not_applicable'}


def test_mixed_applicability_and_failed_baseline_are_distinct():
    f = facts(); second = copy.deepcopy(f['worlds'][0]); second['world'] = 1
    second['sites'][0]['occurred'] = False; f['worlds'].append(second)
    assert all(v == 'unknown' for k,v in aggregate(f, True)['x'].items() if k!='id')
    f = facts(); f['worlds'][0]['baseline_success'] = False
    assert aggregate(f, True)['x']['current_route_required']=='not_applicable'
    assert aggregate(f, True)['x']['authorization']=='yes'


@pytest.mark.parametrize('mutation', ['duplicate_site','missing_site','duplicate_world','wrong_world','bool_world','float_world','bool_route','outside_route'])
def test_strict_coverage(mutation):
    f=facts(); w=f['worlds'][0]
    if mutation=='duplicate_site': w['sites']*=2
    if mutation=='missing_site': w['sites']=[]
    if mutation=='duplicate_world': f['worlds']*=2
    if mutation=='wrong_world': w['world']=1
    if mutation=='bool_world': w['world']=False
    if mutation=='float_world': w['world']=0.0
    if mutation=='bool_route': w['legal_routes']=[True]
    if mutation=='outside_route': w['legal_routes']=[2]
    assert not parse_record(raw(f), ['x'], 'F', 1, 1, True)['protocol_valid']


def test_valid_wrong_facts_are_scored_not_salvaged():
    f=facts(); f['worlds'][0]['sites'][0]['all_occurrences_authorized']=False
    p=parse_record(raw(f),['x'],'F',1,1,True)
    assert p['protocol_valid'] and p['by_id']['x']['authorization']=='no'
    assert fact_errors(f, facts())=={'global':[], 'sites':[{'world':0,'id':'x','field':'all_occurrences_authorized'}]}


def test_facts_match_independent_toy_truth_without_reference_ast():
    program={'version':1,'steps':[{'id':'x','kind':'effect','op':'write','resource':'out','value':'ok'}], 'functions':{}}
    c={'source':'```tsg-workflow\n'+json.dumps(program)+'\n```','routes':[],
       'worlds':[{'files':{},'grants':[['write','out']]}], 'goal':{'files':{'out':'ok'}},'catalog_closed':True,
       'program':{'poison':'must not read'}}
    f, count=exact_facts(c)
    assert f==facts() and count==2
    assert parse_record(raw(f),['x'],'F',1,1,True)['by_id']==aggregate(f,True)

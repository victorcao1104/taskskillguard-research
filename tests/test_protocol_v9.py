"""Hand-written protocol cases; no Phase 9 heldout inputs are opened."""
import copy
import json

import pytest


def raw(value):
    return {'status': 'completed', 'text': json.dumps(value)}


def record(dedup=True):
    global_facts = {'baseline_success': True, 'legal_routes': [0]}
    sites = [{'id': sid, 'occurred': True, 'all_occurrences_authorized': True,
              'suppressed_success': False, 'avoiding_routes': []} for sid in ('x', 'y')]
    world = {'world': 0, 'sites': sites}
    if dedup:
        world.update(global_facts)
    else:
        for site in sites:
            site.update(copy.deepcopy(global_facts))
    return {'worlds': [world], 'judgments': [
        {'id': sid, 'authorization': 'no', 'current_route_required': 'unknown',
         'catalog_required': 'not_applicable'} for sid in ('x', 'y')]}


def test_factorial_reducer_uses_same_facts_without_replacing_model_judgments():
    from tsg.protocol_v9 import VIEWS, parse_record
    for view in VIEWS:
        result = parse_record(raw(record(view[1] == '1')), ['x', 'y'], view, 1, 1, True)
        assert result['protocol_valid']
        assert result['by_id']['x']['authorization'] == 'no'
        assert result['reduced_by_id']['x'] == {'id': 'x', 'authorization': 'yes',
                    'current_route_required': 'yes', 'catalog_required': 'yes'}
        assert result['normalized_facts'] == {'worlds': record()['worlds']}


def test_inconsistent_redundancy_is_protocol_failure_not_majority_vote():
    from tsg.protocol_v9 import parse_record
    value = record(False)
    value['worlds'][0]['sites'][1]['baseline_success'] = False
    result = parse_record(raw(value), ['x', 'y'], 'A00', 1, 1, True)
    assert not result['protocol_valid']
    assert result['by_id'] == result['reduced_by_id'] == {}
    assert result['redundancy_consistent'] is False
    assert 'REDUNDANCY_INCONSISTENT' in result['diagnostic_codes']


@pytest.mark.parametrize('mutation', ['duplicate_site', 'missing_site', 'duplicate_world',
    'missing_world', 'float_world', 'bool_world', 'bool_route', 'float_route', 'out_of_range',
    'unsorted_routes', 'wrong_axis_type', 'wrong_fact_type', 'duplicate_judgment', 'missing_judgment'])
@pytest.mark.parametrize('view', ['A00', 'A10'])
def test_strict_coverage_and_types(mutation, view):
    from tsg.protocol_v9 import parse_record
    value = record(view[1] == '1')
    world = value['worlds'][0]
    globals_row = world if view[1] == '1' else world['sites'][0]
    if mutation == 'duplicate_site': world['sites'].append(copy.deepcopy(world['sites'][0]))
    if mutation == 'missing_site': world['sites'].pop()
    if mutation == 'duplicate_world': value['worlds'].append(copy.deepcopy(world))
    if mutation == 'missing_world': value['worlds'] = []
    if mutation == 'float_world': world['world'] = 0.0
    if mutation == 'bool_world': world['world'] = False
    if mutation == 'bool_route': globals_row['legal_routes'] = [True]
    if mutation == 'float_route': globals_row['legal_routes'] = [0.0]
    if mutation == 'out_of_range': globals_row['legal_routes'] = [9]
    if mutation == 'unsorted_routes': globals_row['legal_routes'] = [1, 0]
    if mutation == 'wrong_axis_type': value['judgments'][0]['authorization'] = True
    if mutation == 'wrong_fact_type': world['sites'][0]['occurred'] = 1
    if mutation == 'duplicate_judgment': value['judgments'].append(value['judgments'][0])
    if mutation == 'missing_judgment': value['judgments'].pop()
    result = parse_record(raw(value), ['x', 'y'], view, 1, 2, True)
    assert not result['protocol_valid']


def test_well_formed_incorrect_facts_are_not_repaired():
    from tsg.protocol_v9 import parse_record
    value = record()
    value['worlds'][0]['sites'][0]['all_occurrences_authorized'] = False
    result = parse_record(raw(value), ['x', 'y'], 'A10', 1, 1, True)
    assert result['protocol_valid']
    assert result['reduced_by_id']['x']['authorization'] == 'no'
    assert result['normalized_facts']['worlds'][0]['sites'][0]['all_occurrences_authorized'] is False


def test_tool_control_only_adds_exact_facts_to_the_public_payload():
    from tsg.protocol_v9 import exact_facts, payload, system
    from tsg.runtime_v6 import candidates
    program = {'version': 1, 'steps': [{'id': 'x', 'kind': 'effect', 'op': 'write',
                                      'resource': 'out', 'value': 'ok'}]}
    case = {'source': '```tsg-workflow\n' + json.dumps(program) + '\n```', 'routes': [],
            'worlds': [{'files': {}, 'grants': [['write', 'out']]}],
            'goal': {'files': {'out': 'ok'}}, 'catalog_closed': True,
            'program': {'poison': 'never read'}, 'truth': 'never read'}
    nodes = candidates(program)
    base = json.loads(payload(case, nodes, 'A00'))
    for view in ('A01', 'A11'):
        supplied = json.loads(payload(case, nodes, view))
        assert supplied.pop('tool_facts') == exact_facts(case)[0]
        assert supplied == base
        assert 'tool_facts' in system(view)
    assert json.loads(payload(case, nodes, 'A10')) == base


def test_duplicate_json_keys_and_unknown_views_fail():
    from tsg.protocol_v9 import parse_record, schema
    result = parse_record({'status': 'completed', 'text': '{"worlds":[],"worlds":[]}'},
                          ['x', 'y'], 'A10', 1, 1, True)
    assert not result['protocol_valid']
    assert 'DUPLICATE_JSON_KEY' in result['diagnostic_codes']
    with pytest.raises(ValueError):
        schema(['x'], 'bogus')

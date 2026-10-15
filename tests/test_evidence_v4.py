import pytest

from tsg.evidence_v4 import make_node, select_graph


def node(line=1, role='source_code', operation='file.read', **kwargs):
    return make_node('main.py', line, line, operation, '/input', 'open("/input")',
                     execution_role=role, analysis_kind='fixture',
                     resource_status='literal', **kwargs)


def test_ids_are_stable_semantic_provenance_not_append_order():
    first, second = node(), node(2)
    assert [node(2)['id'], node()['id']] == [second['id'], first['id']]
    assert node(effect_index=1)['id'] != first['id']
    assert node(role='example')['id'] != first['id']


@pytest.mark.parametrize('start,end', [(0, 1), (2, 1), (True, 2), (1, 1.5)])
def test_bad_spans_rejected(start, end):
    with pytest.raises(ValueError):
        make_node('a', start, end, 'file.read', 'unknown', 'read',
                  execution_role='example', analysis_kind='test')


def test_security_invariants_cannot_be_overwritten():
    with pytest.raises(ValueError):
        node(authorization_source=True)
    assert node()['invocation_proven'] is False
    assert node()['privilege_relevant'] is True


def test_deterministic_role_strata_selection():
    nodes = [node(i) for i in range(1, 20)] + [node(20, 'example'), node(21, 'instruction')]
    a = select_graph({'nodes': nodes, 'edges': []}, max_actions=3)
    b = select_graph({'nodes': list(reversed(nodes)), 'edges': []}, max_actions=3)
    assert [n['id'] for n in a[1]] == [n['id'] for n in b[1]]
    assert {n['execution_role'] for n in a[1]} == {'source_code', 'example', 'instruction'}
    assert a[2]['actions_omitted'] == 18


def test_many_example_strata_cannot_starve_source_code():
    nodes = [node(i, 'example', operation='op'+str(i)) for i in range(1, 21)] + [node(30)]
    _, chosen, _ = select_graph({'nodes': nodes, 'edges': []}, max_actions=12)
    assert any(n['execution_role'] == 'source_code' for n in chosen)


def test_dependency_closure_before_unrelated_support():
    target = node()
    support = make_node('main.py', 2, 2, 'value', 'unknown', 'x', kind='DATA_OBJECT',
                        execution_role='source_code', analysis_kind='fixture')
    other = {**support, 'id': 'unrelated'}
    edges = [{'source': support['id'], 'target': target['id'], 'type': 'DATA', 'semantics': 'value'}]
    graph, actions, coverage = select_graph({'nodes': [other, target, support], 'edges': edges}, max_nodes=2)
    assert {n['id'] for n in graph['nodes']} == {target['id'], support['id']}
    assert coverage['dependency_closure_complete']
    capped, _, coverage = select_graph({'nodes': [other, target, support], 'edges': edges}, max_nodes=1)
    assert len(capped['nodes']) == 1
    assert not coverage['dependency_closure_complete']
    assert support['id'] in coverage['dependency_nodes_omitted']


def test_edge_cap_explicitly_breaks_dependency_completeness():
    nodes = [node(1), node(2)]
    edge = {'source': nodes[0]['id'], 'target': nodes[1]['id'], 'type': 'DATA'}
    _, _, coverage = select_graph({'nodes': nodes, 'edges': [edge]}, max_edges=0)
    assert coverage['dependency_closure_complete'] is False
    assert coverage['graph_edges_omitted'] == 1


def test_order_context_cannot_displace_data_ancestors():
    action = node()
    support = [{**node(i), 'id': name, 'kind': 'DATA_OBJECT', 'privilege_relevant': False}
               for i, name in enumerate(['a_order', 'z_data', 'zz_literal'], 2)]
    edges = [{'source': 'a_order', 'target': action['id'], 'type': 'ORDER'},
             {'source': 'z_data', 'target': action['id'], 'type': 'DATA'},
             {'source': 'zz_literal', 'target': 'z_data', 'type': 'DATA'}]
    bounded, _, coverage = select_graph({'nodes': [action, *support], 'edges': edges}, max_nodes=3)
    assert {n['id'] for n in bounded['nodes']} == {action['id'], 'z_data', 'zz_literal'}
    assert coverage['dependency_closure_complete']
    assert coverage['graph_edges_omitted'] == 1


def test_duplicate_ids_and_dangling_edges_fail_instead_of_corrupting_graph():
    with pytest.raises(ValueError):
        select_graph({'nodes': [node(), node()], 'edges': []})
    with pytest.raises(ValueError):
        select_graph({'nodes': [node()], 'edges': [{'source': 'missing', 'target': node()['id']}]})

"""Exhaustive tiny query schedules, constructed independently of heldout data."""
import copy
import itertools
import json

import pytest


def case(*, closed=True, inactive=False, alternate=False, worlds=1, failing=False):
    effect = {'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}
    steps = [{'id': 'dead', 'kind': 'repeat', 'count': 0, 'body': [effect]}] if inactive else [effect]
    program = {'version': 1, 'steps': steps}
    alt = {'version': 1, 'steps': [{'id': 'alt', 'kind': 'effect', 'op': 'write',
                                  'resource': 'out', 'value': 'ok'}]}
    return {'source': '```tsg-workflow\n' + json.dumps(program) + '\n```',
            'routes': [alt] if alternate else [],
            'worlds': [{'files': {}, 'grants': [['write', 'out']]} for _ in range(worlds)],
            'goal': {'files': {'out': 'unreachable' if failing else 'ok'}},
            'catalog_closed': closed, 'program': {'poison': True}, 'truth': 'never read'}


@pytest.mark.parametrize('kwargs', [{}, {'closed': False}, {'inactive': True},
    {'alternate': True}, {'failing': True}, {'worlds': 2}, {'worlds': 2, 'alternate': True}])
def test_every_query_permutation_prefix_is_sound_and_full_is_exact(kwargs):
    from tsg.evidence_v7 import AXES, solve
    from tsg.query_v9 import evaluate_order, query_catalog
    value = case(**kwargs)
    if kwargs.get('worlds') == 2:
        value['worlds'][1]['grants'] = []
    truth = {row['id']: row for row in solve(value)['judgments']}
    ids = [row['id'] for row in query_catalog(value)]
    for order in itertools.permutations(ids):
        for budget in range(len(ids) + 1):
            result = evaluate_order(value, list(order), budget)
            assert result['executions'] == budget
            assert result['interpreter_steps'] == budget  # Every tiny run enters one step.
            for sid, row in result['by_id'].items():
                for axis in AXES:
                    if result['proven'][sid][axis]:
                        assert row[axis] == truth[sid][axis]
                    else:
                        assert row[axis] == 'unknown'
                        assert result['decisions'][sid][axis]['reason'] == 'budget'
            if budget == len(ids):
                assert result['resolved'] == 3
                assert all(result['by_id']['x'][a] == truth['x'][a] for a in AXES)


def test_baseline_failure_and_inactivity_are_early_decision_witnesses():
    from tsg.query_v9 import evaluate_order, heuristic_order
    for value in (case(failing=True), case(inactive=True)):
        result = evaluate_order(value, heuristic_order(value), 1)
        assert result['by_id']['x']['current_route_required'] == 'not_applicable'
        assert result['proven']['x']['current_route_required']
        if 'dead' in value['source']:
            assert set(result['by_id']['x'].values()) == {'x', 'not_applicable'}
            assert result['resolved'] == 3


def test_open_catalog_unknown_is_intrinsic_once_route_facts_are_known():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case(closed=False)
    result = evaluate_order(value, heuristic_order(value), 1)
    decision = result['decisions']['x']['catalog_required']
    assert decision['label'] == 'unknown' and decision['proven']
    assert decision['reason'] == 'intrinsic'
    assert result['decisions']['x']['current_route_required']['reason'] == 'budget'


def test_avoiding_route_witness_does_not_require_catalog_exhaustion():
    from tsg.query_v9 import evaluate_order, query_catalog
    value = case(closed=False, alternate=True)
    value['routes'] = [{'version': 1, 'steps': []}, *value['routes']]
    value['worlds'][0]['files'] = {'out': 'ok'}
    queries = query_catalog(value)
    order = [q['id'] for q in queries if q['kind'] == 'base' and q['route'] in (0, 1)]
    order += [q['id'] for q in queries if q['id'] not in order]
    result = evaluate_order(value, order, 2)
    assert result['by_id']['x']['catalog_required'] == 'no'
    assert result['proven']['x']['catalog_required']


def test_graph_is_only_a_deterministic_representation_and_payload_contains_no_truth():
    from tsg.query_v9 import query_payload, query_catalog
    from tsg.runtime_v6 import candidates, parse_source, edges
    value = case(alternate=True)
    nodes = candidates(parse_source(value['source']))
    without = json.loads(query_payload(value, nodes, False))
    with_graph = json.loads(query_payload(value, nodes, True))
    assert with_graph.pop('graph') == edges(parse_source(value['source']))
    assert with_graph == without
    assert without['queries'] == query_catalog(value)
    assert set(without) == {'source', 'routes', 'worlds', 'goal', 'catalog_closed',
                            'candidates', 'candidate_ids', 'queries'}


@pytest.mark.parametrize('bad', [[], ['b0r0', 'b0r0'], ['b0r0', 'unknown'], [0, 's0c0'], None])
def test_malformed_orders_do_not_get_a_free_heuristic_fallback(bad):
    from tsg.query_v9 import evaluate_order, parse_query, query_catalog
    value = case()
    ids = [q['id'] for q in query_catalog(value)]
    parsed = parse_query({'status': 'completed', 'text': json.dumps({'order': bad})}, ids)
    assert not parsed['protocol_valid'] and parsed['order'] == []
    result = evaluate_order(value, bad, 'full')
    assert not result['protocol_valid'] and result['executions'] == 0
    assert result['resolved'] == 0


def test_full_budget_cost_counts_loops_control_and_suppressed_steps():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case()
    program = {'version': 1, 'steps': [{'id': 'loop', 'kind': 'repeat', 'count': 3,
        'body': [{'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}]}]}
    value['source'] = '```tsg-workflow\n' + json.dumps(program) + '\n```'
    result = evaluate_order(value, heuristic_order(value), 'full')
    assert result['executions'] == 2 and result['interpreter_steps'] == 8
    assert sum(t['interpreter_steps'] for t in result['trace']) == 8


def test_seeded_order_is_a_permutation_and_query_protocol_rejects_duplicate_json():
    from tsg.query_v9 import parse_query, query_catalog, random_order
    value = case(worlds=2, alternate=True)
    ids = [q['id'] for q in query_catalog(value)]
    assert random_order(value, 13) == random_order(value, 13)
    assert set(random_order(value, 13)) == set(ids)
    valid = parse_query({'status': 'completed', 'text': json.dumps({'order': ids})}, ids)
    assert valid['protocol_valid'] and valid['order'] == ids
    invalid = parse_query({'status': 'completed', 'text': '{"order":[],"order":[]}'}, ids)
    assert not invalid['protocol_valid']
    assert 'DUPLICATE_JSON_KEY' in invalid['diagnostic_codes']


def test_budget_zero_never_invokes_the_interpreter_and_selection_never_solves(monkeypatch):
    import tsg.evidence_v7 as evidence
    from tsg.query_v9 import evaluate_order, heuristic_order, query_catalog, query_payload
    def forbidden(*args, **kwargs):
        raise AssertionError('full solver must not run before query selection')
    monkeypatch.setattr(evidence, 'solve', forbidden)
    value = case()
    order = heuristic_order(value)
    query_catalog(value)
    query_payload(value, [], True)
    result = evaluate_order(value, order, 0)
    assert result['executions'] == result['interpreter_steps'] == 0
    assert result['trace'] == [] and result['observations'] == {}


@pytest.mark.parametrize('budget', [-1, True, 1.0, 'all'])
def test_invalid_budgets_are_rejected(budget):
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case()
    with pytest.raises(ValueError):
        evaluate_order(value, heuristic_order(value), budget)


def test_authorization_evidence_is_only_from_paid_original_baselines():
    from tsg.query_v9 import evaluate_order, query_catalog
    value = case(worlds=2, alternate=True)
    value['worlds'][1]['grants'] = []
    queries = query_catalog(value)
    order = ['s0c0', 'b0r1', 'b1r0', 'b0r0', 's1c0', 'b1r1']
    assert len(order) == len(queries)
    assert evaluate_order(value, order, 2)['authorization_evidence'] == {}
    assert evaluate_order(value, order, 3)['authorization_evidence'] == {
        '1': [{'id': 'x', 'occurred': True, 'all_occurrences_authorized': False}]}
    assert evaluate_order(value, order, 4)['authorization_evidence'] == {
        '0': [{'id': 'x', 'occurred': True, 'all_occurrences_authorized': True}],
        '1': [{'id': 'x', 'occurred': True, 'all_occurrences_authorized': False}]}


def test_two_different_world_witnesses_prove_intrinsic_unknown_early():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case(worlds=3)
    value['worlds'][1]['grants'] = []
    result = evaluate_order(value, heuristic_order(value), 2)
    # Third world's authorization is unknown, but it cannot erase disagreement.
    assert result['by_id']['x']['authorization'] == 'unknown'
    assert result['decisions']['x']['authorization']['reason'] == 'intrinsic'
    assert result['proven']['x']['authorization']
    assert '2' not in result['authorization_evidence']


def test_counted_runtime_matches_error_and_loop_intervention_semantics():
    from tsg.query_v9 import evaluate_order, heuristic_order
    from tsg.runtime_v6 import parse_source, run_semantics
    value = case()
    program = {'version': 1, 'steps': [
        {'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok', 'key': 'shared'},
        {'id': 'y', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'bad', 'key': 'shared'}]}
    value['source'] = '```tsg-workflow\n' + json.dumps(program) + '\n```'
    result = evaluate_order(value, heuristic_order(value), 'full')
    for query in result['trace']:
        observation = copy.deepcopy(result['observations'][query['id']])
        assert observation.pop('interpreter_steps') == 2
        expected = run_semantics(parse_source(value['source']), value['worlds'][0], value['goal'],
                                 suppress=query.get('site'))
        assert observation == expected
    assert result['observations']['b0r0']['error'] == 'receipt_conflict'
    assert result['executions'] == 3 and result['interpreter_steps'] == 6


def test_step_limit_is_counted_as_entered_steps_not_static_effects():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case()
    body = [{'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}]
    for depth in range(5):
        body = [{'id': f'loop{depth}', 'kind': 'repeat', 'count': 3, 'body': body}]
    value['source'] = '```tsg-workflow\n' + json.dumps({'version': 1, 'steps': body}) + '\n```'
    result = evaluate_order(value, heuristic_order(value), 'full')
    assert result['executions'] == 2 and result['interpreter_steps'] == 200
    assert all(observation['error'] == 'step_limit' for observation in result['observations'].values())


def test_incomplete_baseline_has_diagnostic_labels_but_no_runtime_authorization_evidence():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case()
    body = [{'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}]
    for depth in range(5):
        body = [{'id': f'loop{depth}', 'kind': 'repeat', 'count': 3, 'body': body}]
    value['source'] = '```tsg-workflow\n' + json.dumps({'version': 1, 'steps': body}) + '\n```'
    partial = evaluate_order(value, heuristic_order(value), 1)
    assert partial['executions'] == 1 and partial['interpreter_steps'] == 100
    assert partial['observations']['b0r0']['error'] == 'step_limit'
    assert partial['observations']['b0r0']['trace']
    # Diagnostic semantics retain committed-trace judgments, but an interrupted
    # execution cannot prove all occurrences for the runtime handoff.
    assert partial['by_id']['x']['authorization'] == 'yes'
    assert partial['proven']['x']['authorization']
    assert partial['authorization_evidence'] == {}
    normal = case()
    complete = evaluate_order(normal, heuristic_order(normal), 1)
    assert complete['authorization_evidence'] == {
        '0': [{'id': 'x', 'occurred': True, 'all_occurrences_authorized': True}]}


def test_graph_control_preserves_source_with_nonempty_data_and_control_edges():
    from tsg.query_v9 import query_payload, query_system
    from tsg.runtime_v6 import parse_source, candidates
    value = case()
    program = {'version': 1, 'steps': [
        {'id': 'read', 'kind': 'effect', 'op': 'read', 'resource': 'flag', 'out': 'flag'},
        {'id': 'branch', 'kind': 'if', 'eq': [{'var': 'flag'}, 'go'], 'then': [
            {'id': 'write', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}], 'else': []}]}
    value['source'] = '```tsg-workflow\n' + json.dumps(program) + '\n```'
    nodes = candidates(parse_source(value['source']))
    q0 = json.loads(query_payload(value, nodes, 'Q0'))
    q1 = json.loads(query_payload(value, nodes, 'Q1'))
    assert q1.pop('graph') == [['branch', 'write', 'control'], ['read', 'branch', 'data']]
    assert q1 == q0
    assert 'PERMUTATION' in query_system('Q1')


def test_budget_above_full_is_capped_and_repeated_evaluations_have_no_free_cache():
    from tsg.query_v9 import evaluate_order, heuristic_order
    value = case()
    first = evaluate_order(value, heuristic_order(value), 99)
    second = evaluate_order(value, heuristic_order(value), 'full')
    assert first['executions'] == second['executions'] == 2
    assert first['interpreter_steps'] == second['interpreter_steps'] == 2
    assert first['all_queries_executed'] and second['all_queries_executed']

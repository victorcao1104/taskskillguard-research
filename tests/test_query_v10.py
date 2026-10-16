"""Independent tiny workflows for paid incremental querying; no heldout input."""
import copy
import itertools
import json

import pytest


def toy(*, worlds=1, closed=True, inactive=False, alternate=False, incomplete=False):
    effect = {'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}
    steps = [{'id': 'dead', 'kind': 'repeat', 'count': 0, 'body': [effect]}] if inactive else [effect]
    if incomplete:
        steps += [{'id': 'bad', 'kind': 'let', 'name': 'broken', 'value': {'var': 'unbound'}}]
    return {'source': '```tsg-workflow\n' + json.dumps({'version': 1, 'steps': steps}) + '\n```',
            'routes': [{'version': 1, 'steps': []}] if alternate else [],
            'worlds': [{'files': {}, 'grants': [['write', 'out']]} for _ in range(worlds)],
            'goal': {'files': {'out': 'ok'}}, 'catalog_closed': closed,
            'truth': 'PRIVATE_SENTINEL', 'world_index': 912, 'program': {'private': True}}


def raw(value):
    return {'status': 'completed', 'text': json.dumps(value)}


@pytest.mark.parametrize('protocol,value,expected', [
    ('full', {'order': ['s0c0', 'b0r0']}, ['s0c0', 'b0r0']),
    ('batch', {'queries': ['b0r0']}, ['b0r0']),
    ('next', {'query_id': 's0c0'}, ['s0c0'])])
def test_protocols_return_exact_selected_ids(protocol, value, expected):
    from tsg.query_v10 import parse_selection
    result = parse_selection(raw(value), ['b0r0', 's0c0'], protocol, 2)
    assert result['protocol_valid'] and result['selected_ids'] == expected


@pytest.mark.parametrize('protocol,value,limit', [
    ('full', {'order': ['b0r0']}, 2),
    ('full', {'order': ['b0r0', 'b0r0']}, 2),
    ('batch', {'queries': []}, 2),
    ('batch', {'queries': ['b0r0', 'b0r0']}, 2),
    ('batch', {'queries': ['b0r0', 's0c0']}, 1),
    ('batch', {'queries': ['missing']}, 2),
    ('next', {'query_id': ['b0r0']}, 2),
    ('next', {'query_id': 'missing'}, 2),
    ('next', {'query_id': 'b0r0', 'reason': 'repair me'}, 2)])
def test_invalid_selections_are_never_repaired(protocol, value, limit):
    from tsg.query_v10 import parse_selection
    result = parse_selection(raw(value), ['b0r0', 's0c0'], protocol, limit)
    assert not result['protocol_valid'] and result['selected_ids'] == []
    assert result['diagnostic_codes'] and result['diagnostics'] == result['diagnostic_codes']


def test_duplicate_json_and_incomplete_response_remain_invalid():
    from tsg.query_v10 import parse_selection
    result = parse_selection({'status': 'completed', 'text': '{"query_id":"b0r0","query_id":"s0c0"}'},
                             ['b0r0', 's0c0'], 'next', 1)
    assert result['selected_ids'] == [] and 'DUPLICATE_JSON_KEY' in result['diagnostic_codes']
    assert not parse_selection({'status': 'incomplete', 'text': '{"query_id":"b0r0"}'},
                               ['b0r0'], 'next', 1)['protocol_valid']


@pytest.mark.parametrize('limit', [0, 5, True, 1.5])
def test_batch_limit_is_bounded_configuration(limit):
    from tsg.query_v10 import selection_schema
    with pytest.raises(ValueError):
        selection_schema(['b0r0'], 'batch', limit)


def test_incremental_runs_once_and_snapshots_cannot_mutate_evidence(monkeypatch):
    import tsg.query_v10 as query
    calls = []
    original_run = query._run_counted
    def counted(*args, **kwargs):
        calls.append(args)
        return original_run(*args, **kwargs)
    monkeypatch.setattr(query, '_run_counted', counted)
    value = toy()
    session = query.QuerySession(value)
    value['worlds'][0]['grants'] = []
    session.consume(['b0r0'])
    observation = session.observations
    observation['b0r0']['trace'].clear()
    session.result()['authorization_evidence'].clear()
    session.remaining_ids.clear()
    session.consume(['s0c0'])
    assert len(calls) == 2
    assert session.result()['executions'] == session.result()['interpreter_steps'] == 2
    assert session.result()['by_id']['x']['authorization'] == 'yes'
    assert session.result()['authorization_evidence']['0'][0]['occurred']
    assert session.remaining_ids == []


@pytest.mark.parametrize('selection', [[], ['b0r0', 'b0r0'], ['s0c0', 'outside'], 's0c0', [1]])
def test_invalid_consume_is_atomic(selection):
    from tsg.query_v10 import QuerySession
    session = QuerySession(toy())
    with pytest.raises(ValueError):
        session.consume(selection)
    assert session.result()['executions'] == session.result()['interpreter_steps'] == 0


def test_consumed_ids_cannot_be_bought_twice():
    from tsg.query_v10 import QuerySession
    session = QuerySession(toy())
    session.consume(['b0r0'])
    with pytest.raises(ValueError):
        session.consume(['s0c0', 'b0r0'])
    assert session.result()['executions'] == 1 and session.remaining_ids == ['s0c0']


@pytest.mark.parametrize('kwargs', [{}, {'worlds': 2}, {'closed': False}, {'inactive': True},
                                    {'alternate': True}, {'incomplete': True}])
def test_all_toy_orders_match_frozen_v9_at_every_paid_prefix(kwargs):
    from tsg.query_v9 import evaluate_order, query_catalog
    from tsg.query_v10 import QuerySession
    value = toy(**kwargs)
    ids = [q['id'] for q in query_catalog(value)]
    for order in itertools.permutations(ids):
        session = QuerySession(value)
        for n in range(len(ids) + 1):
            expected = evaluate_order(value, list(order), n)
            result = session.result()
            for key in ('by_id', 'decisions', 'proven', 'resolved', 'intrinsic_unknown', 'observations',
                        'authorization_evidence', 'executions', 'interpreter_steps', 'trace'):
                assert result[key] == expected[key]
            if n < len(ids):
                session.consume([order[n]])


def test_original_error_never_proves_handoff_even_after_catalog_exhaustion():
    from tsg.query_v10 import QuerySession
    session = QuerySession(toy(incomplete=True))
    session.consume(session.remaining_ids)
    result = session.result()
    assert result['observations']['b0r0']['error'] is not None
    assert result['by_id']['x']['authorization'] == 'yes'
    assert result['authorization_evidence'] == {}
    assert not session.stop_ready('authorization')
    assert not result['authorization_complete']


def test_stop_needs_every_world_even_if_mixed_label_is_already_proved(monkeypatch):
    import tsg.query_v10 as query
    value = toy(worlds=3)
    value['worlds'][1]['grants'] = []
    session = query.QuerySession(value)
    session.consume(['b0r0', 'b1r0'])
    assert session.result()['decisions']['x']['authorization']['reason'] == 'intrinsic'
    assert not session.stop_ready('authorization')
    session.consume(['b2r0'])
    def forbidden(*args, **kwargs):
        raise AssertionError('Stopping/result must never invoke an interpreter')
    monkeypatch.setattr(query, '_run_counted', forbidden)
    assert session.stop_ready('authorization')
    assert not session.stop_ready('diagnostic')
    assert not session.stop_ready('fixed')
    assert session.result()['executions'] == 3
    with pytest.raises(ValueError):
        session.stop_ready('guess')


def test_intrinsic_unknown_and_budget_unknown_are_distinct():
    from tsg.query_v10 import QuerySession
    session = QuerySession(toy(closed=False))
    session.consume(['b0r0'])
    result = session.result()
    assert result['decisions']['x']['catalog_required']['reason'] == 'intrinsic'
    assert result['decisions']['x']['current_route_required']['reason'] == 'budget'
    assert result['intrinsic_unknown'] == result['budget_unknown'] == 1


def test_actual_early_stop_saves_queries_and_retains_budget_semantics():
    from tsg.query_v10 import evaluate_stream
    order = ['b0r0', 's0c0']
    fixed = evaluate_stream(toy(), order, 8, 'fixed')
    early = evaluate_stream(toy(), order, 8, 'authorization')
    assert fixed['executions'] == 2 and early['executions'] == 1
    assert early['stopped_early'] and early['stop_reason'] == 'authorization'
    assert early['budget_unknown'] == 1
    assert fixed['authorization_evidence'] == early['authorization_evidence']
    inactive = evaluate_stream(toy(inactive=True), order, 8, 'diagnostic')
    assert inactive['executions'] == 1 and inactive['resolved'] == 3
    zero = evaluate_stream(toy(), order, 0, 'authorization')
    assert zero['executions'] == 0 and not zero['stopped_early']


def test_selection_is_public_only_and_graph_padding_are_character_matched(monkeypatch):
    import tsg.query_v10 as query
    import tsg.evidence_v7 as evidence
    def forbidden(*args, **kwargs):
        raise AssertionError('Selection must not run or solve')
    monkeypatch.setattr(query, '_run_counted', forbidden)
    monkeypatch.setattr(evidence, 'solve', forbidden)
    value = toy()
    for source in (value['source'], '```tsg-workflow\n' + json.dumps({'version': 1, 'steps': [
        {'id': 'read', 'kind': 'effect', 'op': 'read', 'resource': 'flag', 'out': 'f'},
        {'id': 'branch', 'kind': 'if', 'eq': [{'var': 'f'}, 'yes'], 'then': [
            {'id': 'x', 'kind': 'effect', 'op': 'write', 'resource': 'out', 'value': 'ok'}], 'else': []}
    ]}) + '\n```'):
        value['source'] = source
        session = query.QuerySession(value)
        payloads = {r: query.selection_payload(value, session.remaining_ids, {}, 'next', 'execution', r)
                    for r in ('source', 'graph', 'padding')}
        assert len(payloads['graph']) == len(payloads['padding'])
        assert all('PRIVATE_SENTINEL' not in p and 'world_index' not in p and '"private"' not in p
                   for p in payloads.values())
        graph = json.loads(payloads['graph'])
        padding = json.loads(payloads['padding'])
        assert graph['representation']['kind'] == 'graph'
        assert padding['representation']['kind'] == 'padding'
        assert padding['representation']['note'].lower().startswith('inert')
        graph.pop('representation')
        padding.pop('representation')
        assert graph == padding == json.loads(payloads['source'])
    assert 'completed original' in query.selection_system('next', 'execution').lower()
    assert 'labels' in query.selection_system('batch', 'diagnostic').lower()


@pytest.mark.parametrize('kwargs', [{'protocol': 'typo'}, {'objective': None},
                                  {'objective': 'truth'}, {'representation': 'truth'}])
def test_invalid_selection_configuration_fails_before_building_request(kwargs):
    from tsg.query_v10 import selection_payload
    options = {'protocol': 'next', 'objective': 'execution', 'representation': 'source', **kwargs}
    with pytest.raises(ValueError):
        selection_payload(toy(), ['b0r0', 's0c0'], {}, **options)


def test_payload_exposes_paid_observations_but_rejects_remaining_as_paid():
    from tsg.query_v10 import QuerySession, selection_payload
    value = toy()
    session = QuerySession(value)
    session.consume(['b0r0'])
    payload = json.loads(selection_payload(value, session.remaining_ids, session.observations,
                                          'batch', 'diagnostic'))
    assert payload['observations']['b0r0']['goal'] is True
    assert payload['remaining_ids'] == ['s0c0']
    assert [q['id'] for q in payload['queries']] == ['s0c0']
    with pytest.raises(ValueError):
        selection_payload(value, ['b0r0', 's0c0'], session.observations, 'next', 'execution')


@pytest.mark.parametrize('ids', [['b0r0', 'b0r0'], ['b0r0', 'outside'], None, 'b0r0'])
def test_invalid_stream_has_zero_work_and_no_heuristic_fallback(ids):
    from tsg.query_v10 import evaluate_stream
    result = evaluate_stream(toy(), ids, 8, 'authorization')
    assert not result['protocol_valid']
    assert result['executions'] == result['interpreter_steps'] == 0
    assert result['authorization_evidence'] == {} and result['observations'] == {}


def test_empty_world_catalog_is_rejected_and_empty_candidate_handoff_is_paid():
    from tsg.query_v10 import QuerySession
    with pytest.raises(ValueError):
        QuerySession(toy(worlds=0))
    value = toy()
    value['source'] = '```tsg-workflow\n{"version":1,"steps":[]}\n```'
    session = QuerySession(value)
    assert session.stop_ready('diagnostic')
    assert not session.stop_ready('authorization')
    session.consume(['b0r0'])
    assert session.stop_ready('authorization')
    assert session.result()['authorization_evidence'] == {'0': []}

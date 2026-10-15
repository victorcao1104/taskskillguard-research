from copy import deepcopy
import pytest
from tsg.evidence_v7 import solve, check, AXES
from tsg.protocol_v7 import payload, schema
import json


def case():
    p = {'version': 1, 'steps': [{'id': 'w', 'kind': 'effect', 'op': 'write', 'resource': '/a', 'value': 'done'}]}
    return {'source': '```tsg-workflow\n' + json.dumps(p) + '\n```', 'program': {'INVALID': True},
            'worlds': [{'files': {}, 'grants': [['write', '/a']]}], 'routes': [],
            'goal': {'files': {'/a': 'done'}}, 'catalog_closed': True}


def test_source_only_exact_solver_and_certificate():
    c = case(); p = solve(c)
    assert all(p['judgments'][0][a] == 'yes' for a in AXES)
    assert check(c, p)['accepted']
    c['worlds'][0]['grants'] = []
    assert not check(c, p)['accepted']
    r = solve(c)['judgments'][0]
    assert r['authorization'] == 'no' and r['catalog_required'] == 'not_applicable'


@pytest.mark.parametrize('field,value', [('world', True), ('occurred', False), ('all_occurrences_authorized', False),
    ('baseline_success', False), ('suppressed_success', True), ('legal_routes', []), ('avoiding_routes', [0])])
def test_mutated_evidence_rejected(field, value):
    c = case(); p = solve(c); p['judgments'][0]['worlds'][0][field] = value
    assert not check(c, p)['accepted']


def test_missing_duplicate_label_and_world_rejected():
    c = case(); p = solve(c)
    for mutation in ('missing', 'duplicate', 'label', 'world'):
        q = deepcopy(p)
        if mutation == 'missing': q['judgments'] = []
        if mutation == 'duplicate': q['judgments'] *= 2
        if mutation == 'label': q['judgments'][0]['current_route_required'] = 'no'
        if mutation == 'world': q['judgments'][0]['worlds'] *= 2
        assert not check(c, q)['accepted']


def test_catalog_bypass_does_not_change_current_necessity():
    c = case(); c['worlds'][0]['files'] = {'/a': 'done'}
    c['routes'] = [{'version': 1, 'steps': []}]
    row = solve(c)['judgments'][0]
    assert row['current_route_required'] == row['catalog_required'] == 'no'
    c['worlds'].append({'files': {}, 'grants': [['write', '/a']]})
    assert solve(c)['judgments'][0]['current_route_required'] == 'unknown'


def test_payload_never_exposes_private_reference_or_labels():
    c = case(); c.update(family='private', case_id='private', labels=['yes'])
    p = json.loads(payload(c, []))
    assert set(p) == {'source','routes','worlds','goal','catalog_closed','candidates','candidate_ids'}
    assert schema(['w'], 'B2')['additionalProperties'] is False


def test_typed_protocol_and_old_label_mapping():
    from tsg.protocol_v7 import parse_record
    for view in ('B0', 'B1', 'B2'):
        row = solve(case())['judgments'][0]
        if view == 'B0':
            row = {'id': 'w', 'authorization': 'yes', 'implementation': 'yes', 'task': 'yes'}
        elif view == 'B1':
            row.pop('worlds')
        raw = {'status': 'completed', 'text': json.dumps({'judgments': [row]})}
        parsed = parse_record(raw, ['w'], view)
        assert parsed['protocol_valid']
        assert all(parsed['by_id']['w'][axis] == 'yes' for axis in AXES)
        assert not parse_record(raw, ['w', 'missing'], view)['protocol_valid']


def test_reference_independence_and_dev_agreement():
    from tsg.truth_v7 import evaluate_case
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for line in (root/'data/phase6/dev.jsonl').read_text(encoding='utf-8').splitlines():
        c = json.loads(line)
        ref = evaluate_case(c)
        observed = solve(c)
        assert [{k:r[k] for k in ('id', *AXES)} for r in ref['labels']] == [
            {k:r[k] for k in ('id', *AXES)} for r in observed['judgments']]

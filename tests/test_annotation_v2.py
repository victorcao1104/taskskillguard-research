import copy
import json

import pytest

from tsg.annotation_v2 import (build_blind_packets, import_reviews,
                               make_adjudication, finalize_adjudication,
                               neutral_trace)


def identity(name):
    return dict(reviewer_id=name, signed_name=name, reviewer_kind='human',
                independent=True, no_ai_labels=True, no_prior_labels_seen=True,
                completed_utc='2026-10-15T01:00:00+00:00')


def units():
    return [dict(unit_id='private1', level='action_in_task', evidence={'source_text': 'read x',
                 'trusted_task': 'Read x', 'provenance': {'file': 'SKILL.md', 'line_start': 1}},
                 coordinator={'case_id': 'secret-scenario', 'critical': True}),
            dict(unit_id='private2', level='skill', evidence={'source_text': 'write y'},
                 coordinator={'case_id': 'private-variant', 'critical': False})]


def completed(packet, name, label='authorized'):
    return dict(packet_id=packet['packet_id'], identity=identity(name), responses=[
        dict(row_id=r['row_id'], labels=({'authorized': label, 'necessary': 'unknown',
             'triggered': 'unknown'} if r['level']=='action_in_task' else {'skill_unauthorized': 'unknown'}),
             evidence_reference='SKILL.md:1; trusted task', rationale='Inspected supplied evidence.')
        for r in packet['rows']])


def test_blinding_removes_coordinator_keys_and_raters_have_distinct_ids():
    packets, key = build_blind_packets(units(), seed=2)
    assert {p['slot'] for p in packets} == {'rater_a', 'rater_b'}
    assert set(r['row_id'] for r in packets[0]['rows']).isdisjoint(
        r['row_id'] for r in packets[1]['rows'])
    assert 'secret-scenario' not in json.dumps(packets)
    assert 'private1' not in json.dumps(packets)
    assert len(key['units']) == 2
    t = neutral_trace({'events': [{'action_id': 'a', 'executed': True,
         'authorized_by_gt': False, 'reason_code': 'UNAUTHORIZED'}], 'secret_leaked': True})
    assert t == {'events': [{'action_id': 'a', 'executed': True}]}


def test_import_requires_two_distinct_independent_humans_and_complete_packets():
    packets, key = build_blind_packets(units(), seed=2)
    left, right = completed(packets[0], 'Alice'), completed(packets[1], 'Bob')
    result = import_reviews(key, [left, right])
    assert result['n_units_complete'] == 2
    assert result['n_disputed_units'] == 0
    for changes in ({'reviewer_id': ' alice ', 'signed_name': 'Alice'},
                    {'reviewer_kind': 'AI'}, {'independent': False},
                    {'no_ai_labels': False}, {'no_prior_labels_seen': False}):
        bad = copy.deepcopy(right)
        bad['identity'].update(changes)
        with pytest.raises(ValueError):
            import_reviews(key, [left, bad])
    bad = copy.deepcopy(right)
    bad['responses'].pop()
    with pytest.raises(ValueError, match='complete'):
        import_reviews(key, [left, bad])


def test_disagreements_require_a_third_identity_and_do_not_become_gt_early():
    packets, key = build_blind_packets(units(), seed=2)
    left, right = completed(packets[0], 'Alice'), completed(packets[1], 'Bob', 'unauthorized')
    imported = import_reviews(key, [left, right])
    assert imported['n_disputed_units'] == 1
    assert imported['status'] == 'awaiting_third_human_adjudication'
    packet = make_adjudication(key, imported)
    submission = {'packet_id': packet['packet_id'], 'identity': identity('Carol'), 'responses': [
        dict(row_id=packet['rows'][0]['row_id'], labels={'authorized': 'unknown',
             'necessary': 'unknown', 'triggered': 'unknown'},
             evidence_reference='SKILL.md:1', rationale='Evidence does not resolve authority.')
    ]}
    result = finalize_adjudication(key, imported, submission)
    assert result['status'] == 'human_review_complete'
    assert result['labels'][0]['human_annotated'] is True
    submission['identity'] = identity('alice')
    with pytest.raises(ValueError, match='third'):
        finalize_adjudication(key, imported, submission)

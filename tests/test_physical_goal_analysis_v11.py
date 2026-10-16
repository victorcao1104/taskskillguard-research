"""Separate physical task state from acknowledged error-free completion."""
import importlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
a = importlib.import_module('analyze_phase11_physical_goal')


def test_exact_saved_state_goal_is_independent_of_error_or_reported_goal():
    case = {'goal': {'files': {'out': 'ok'}, 'absent': ['old'],
                     'emits': [{'resource': 'events', 'value': 'v', 'count': 1}]}}
    result = {'files': {'out': 'ok'}, 'emits': [{'resource': 'events', 'value': 'v'}],
              'authorized_goal': False, 'goal': False, 'failure_reason': 'ambiguous_outcome'}
    assert a.physical_goal(case, result) is True
    assert a.physical_goal(case, {**result, 'emits': result['emits']*2}) is False
    assert a.physical_goal(case, {**result, 'files': {'out': 'ok', 'old': 'x'}}) is False
    assert a.physical_goal(case, None) is False


def test_nulls_remain_in_family_means_and_endpoint_contrasts():
    cases = [{'case_id': 'a', 'family': 'a', 'split': 'heldout', 'worlds': [{}, {}],
              'routes': [], 'goal': {'files': {'out': 'ok'}}},
             {'case_id': 'b', 'family': 'b', 'split': 'challenge', 'worlds': [{}],
              'routes': [], 'goal': {'files': {'out': 'ok'}}}]
    rows = []
    for cid, worlds in [('a', (0, 1)), ('b', (0,))]:
        for w in worlds:
            for policy in ('strict_stop', 'terminal_status'):
                result = None if cid == 'b' else {
                    'files': {'out': 'ok'}, 'emits': [], 'goal': True,
                    'authorized_goal': policy == 'terminal_status',
                    'fault_diagnostics': {'fault_triggered': True}}
                rows.append({'case_id': cid, 'world_index': w, 'fault': 'ambiguous_after',
                             'policy': policy, 'status_budget': 1, 'result': result})
    output = a.summarize(cases, rows)
    strict = next(r for r in output['conditions'] if r['cohort'] == 'combined'
                  and r['policy'] == 'strict_stop' and r['metric'] == 'physical_goal')
    assert strict['estimate'] == .5 and strict['observed_total'] == 2 and strict['rows'] == 3
    assert len(strict['family_values']) == 2
    effects = {r['metric']: r for r in output['contrasts']
               if r['cohort'] == 'combined' and r['denominator'] == 'all_rows'}
    assert effects['physical_goal']['estimate'] == 0
    assert effects['authorized_goal']['estimate'] == .5
    assert effects['authorized_goal']['raw_left_positive_rows'] == 2
    assert effects['authorized_goal']['raw_right_positive_rows'] == 0
    assert output['summary']['null_execution_rows'] == 2


def test_saved_goal_disagreement_is_preserved_not_silently_repaired():
    case = {'case_id': 'a', 'family': 'a', 'split': 'heldout', 'worlds': [{}],
            'routes': [], 'goal': {'files': {'out': 'ok'}}}
    row = {'case_id': 'a', 'world_index': 0, 'fault': 'none', 'policy': 'strict_stop',
           'status_budget': 1, 'result': {'files': {'out': 'ok'}, 'emits': [],
                                       'goal': False, 'authorized_goal': False}}
    out = a.summarize([case], [row])
    assert out['summary']['saved_goal_disagreement_rows'] == 1
    assert out['summary']['physical_goal_rows'] == 1

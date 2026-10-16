"""Hand-derived Phase 10 scoring controls, independent of new case fixtures."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
a = importlib.import_module('analyze_phase10')


def truth():
    return [{'case_id': 'toy', 'family': 'toyfamily', 'split': 'heldout',
             'labels': [{'id': 'x', 'authorization': 'unknown',
                         'current_route_required': 'yes', 'catalog_required': 'not_applicable'}]}]


def query():
    return {'case_id': 'toy', 'family': 'toyfamily', 'split': 'heldout', 'pipeline': 'heuristic',
        'budget': 2, 'stop_mode': 'fixed', 'protocol_valid': True, 'stream_protocol_valid': True,
        'result': {'decisions': {'x': {'authorization': {'proven': True, 'reason': 'intrinsic'},
            'current_route_required': {'proven': False, 'reason': 'budget'},
            'catalog_required': {'proven': True, 'reason': 'proved'}}},
            'by_id': {'x': {'authorization': 'unknown', 'current_route_required': 'unknown',
                            'catalog_required': 'not_applicable'}},
            'authorization_complete': False, 'executions': 2, 'interpreter_steps': 7}}


def runtime(pipeline='v10_goal', success=True, queries=2, stop='fixed', ob=2, calls=1, risk=1):
    return {'case_id': 'toy', 'family': 'toyfamily', 'split': 'heldout', 'world_index': 0,
        'condition_id': pipeline+stop+str(ob), 'quota': 16, 'pipeline': pipeline, 'policy': 'calls',
        'fault': 'none', 'observation_budget': ob, 'planning_budget': 512, 'preflight': True,
        'stop_mode': stop, 'query_budget': 8, 'query_executions': queries, 'query_steps': 3*queries,
        'runner_status': 'completed', 'result': {'authorized_goal': success, 'charged_calls': calls,
            'mutation_risk_score': risk, 'planning_units': 5, 'planner_steps': 3,
            'evidence_source': 'trusted_queries', 'audit_interpreter_calls': 0, 'audit_steps': 0}}


def test_family_equal_bootstrap_is_deterministic_and_does_not_pseudoreplicate():
    rows = [{'family': 'small', 'difference': -1}] + [{'family': 'large', 'difference': 1}]*15
    got = a.paired_interval(rows)
    assert got['estimate'] == 0 and got['families'] == 2 and got['pairs'] == 16
    assert got == a.paired_interval(list(reversed(rows)))
    assert got['interval95'] == [-1, 1]


def test_vectorized_resamples_match_original_family_bootstrap():
    rows = [{'family': f'f{i:02}', 'difference': (i-3)/7} for i in range(12)]
    got = a.paired_interval(rows, 10000, 10101)
    original = a._paired_interval(rows, 10000, 10101)
    assert got['estimate'] == original['estimate']
    assert got['interval95'] == pytest.approx(original['interval95'], abs=1e-14)


def test_intrinsic_unknown_is_proven_but_budget_unknown_is_not():
    details, summary = a.query_scores(truth(), [query()])
    assert details[0]['proven'] == 2 and details[0]['intrinsic_unknown'] == 1
    assert details[0]['budget_unknown'] == 1 and not details[0]['diagnostic_complete']
    assert summary[0]['by_axis']['authorization']['proven'] == 1
    assert summary[0]['by_axis']['current_route_required']['proven'] == 0
    bad = query()
    bad['result']['decisions']['x']['current_route_required']['proven'] = True
    with pytest.raises(ValueError, match='UNSOUND_QUERY'):
        a.query_scores(truth(), [bad])


def test_invalid_later_decision_does_not_erase_first_validity_or_spending():
    ds = [{'parsed': {'protocol_valid': True}, 'raw_status': 'completed', 'cost_upper_usd': .1},
          {'parsed': {'protocol_valid': False}, 'raw_status': 'error', 'cost_upper_usd': .4,
           'cost_basis': 'reservation_upper_unknown_usage', 'usage': {'input_tokens': None, 'output_tokens': None}}]
    row = {'case_id': 'toy', 'model': 'm', 'cell': 'next_exec', 'protocol_valid': False, 'decisions': ds}
    detail, summary = a.stream_scores(truth(), [row], models=('m',))
    got = next(r for r in detail if r['cell'] == 'next_exec')
    assert got['first_decision_valid'] and not got['stream_valid']
    assert got['cost_upper_usd'] == .5 and got['unknown_reservation_decisions'] == 1
    assert got['known_usage_decisions'] == 0 and got['known_input_tokens'] == 0
    assert len(detail) == 6 and sum(r['received'] for r in detail) == 1
    missing = next(r for r in summary if r['cell'] == 'full_diag')
    assert missing['streams'] == 1 and missing['first_decision_validity'] == 0


def test_budget_rejection_attempt_is_separate_from_provider_io():
    row = {'case_id': 'toy', 'model': 'm', 'cell': 'full_diag', 'protocol_valid': False,
           'decisions': [{'parsed': {'protocol_valid': False}, 'raw_status': 'budget_exhausted',
                          'cost_upper_usd': 0}]}
    details, _ = a.stream_scores(truth(), [row], models=('m',))
    got = next(r for r in details if r['cell'] == 'full_diag')
    assert got['decision_attempts'] == 1 and got['provider_or_possible_io'] == 0


def test_matching_never_silently_drops_missing_conditions():
    x, y = runtime(), runtime('v10_authorization')
    x['world_index'] = 1
    with pytest.raises(ValueError, match='UNMATCHED_RUNTIME'):
        a.runtime_pair([x, y], lambda r: r['pipeline'] == 'v10_goal',
                       lambda r: r['pipeline'] == 'v10_authorization', 'toy', 'interface', ('pipeline',))


def test_stopping_savings_require_unchanged_end_to_end_completion():
    x = runtime(queries=2, stop='authorization', success=False)
    y = runtime(queries=8, stop='fixed', success=True)
    pairs = a.runtime_pair([x, y], lambda r: r['stop_mode'] == 'authorization',
                           lambda r: r['stop_mode'] == 'fixed', 'authorization_stop-fixed',
                           'integrated', ('stop_mode',))
    got = a.stopping_checks(pairs)[0]
    assert got['completion_losses'] == 1 and got['saved_queries_at_unchanged_completion'] == 0
    x['result']['authorized_goal'] = True
    pairs = a.runtime_pair([x, y], lambda r: r['stop_mode'] == 'authorization',
                           lambda r: r['stop_mode'] == 'fixed', 'authorization_stop-fixed',
                           'integrated', ('stop_mode',))
    got = a.stopping_checks(pairs)[0]
    assert got['saved_queries_at_unchanged_completion'] == 6
    assert got['both_success_query_saving_conditions'] == 1
    assert got['campaign_invoice_saving_claimed_usd'] == 0


def test_hidden_audit_is_rejected_and_missing_jobs_remain_failure():
    x = runtime()
    x['result']['audit_interpreter_calls'] = 1
    with pytest.raises(ValueError, match='HIDDEN_INTEGRATED_AUDIT'):
        a.validate_runtime([x], integrated=True)
    missing = a.complete_jobs([], [{'meta': runtime()}])[0]
    assert not a.success(missing) and missing['runner_status'] == 'missing_result'


def test_recovery_pareto_does_not_equate_lower_calls_with_dominance():
    x, y = runtime('risk', calls=1, risk=5), runtime('calls', calls=2, risk=1)
    x['policy'], y['policy'] = 'risk', 'calls'
    pairs = a.runtime_pair([x, y], lambda r: r['policy'] == 'risk', lambda r: r['policy'] == 'calls',
                           'risk-calls', 'recovery', ('pipeline', 'policy'))
    got = a.pareto_checks(pairs)[0]
    assert got['treatment_dominates'] == got['baseline_dominates'] == 0


def test_historical_losses_use_fixed_keys_and_never_pool_new_cases():
    old = [{'track': 'interface', 'split': 'regression', 'contrast': 'preflight_on-off:conditional',
            'loss': True, 'case_id': 'toy', 'world_index': 0, 'fault': 'none'}]
    got = a.old_loss_regression(old, [runtime(), runtime('v10_authorization', success=False)])
    assert got['historical_loss_conditions'] == 1
    assert {r['pipeline']: r['completed'] for r in got['current']} == {'v10_goal': 1, 'v10_authorization': 0}


def test_unique_query_stopping_uses_one_pair_before_runtime_expansion():
    fixed = {**query(), 'executions': 8, 'interpreter_steps': 30}
    stopped = {**fixed, 'stop_mode': 'authorization', 'executions': 2, 'interpreter_steps': 7}
    got = a.unique_query_stopping([fixed, stopped], draws=10)
    assert len(got['details']) == got['summary'][0]['pairs'] == 1
    assert got['summary'][0]['saved_queries'] == 6 and got['summary'][0]['saved_steps'] == 23
    with pytest.raises(ValueError, match='UNMATCHED_UNIQUE_QUERY_STOP'):
        a.unique_query_stopping([fixed], draws=10)

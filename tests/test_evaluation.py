"""Hand-derived checks for abstention-aware, clustered result accounting."""
import json

import pytest

from tsg.evaluation import (
    analyze_directory, augment_prediction, budget_summary, classification_metrics,
    compare_prediction_pair, contract_summary, real_graph_summary, runtime_summary,
)


def observation(truth, predicted, case, family='family-a', replicate=0):
    return dict(truth=truth, predicted=predicted, case_id=case, action_id='read',
                family_id=family, replicate=replicate)


def test_abstentions_are_not_true_negatives_and_keep_positive_support():
    rows = [observation('no', 'no', '1'), observation('no', 'yes', '2'),
            observation('yes', 'no', '3'), observation('yes', 'yes', '4'),
            observation('no', 'unknown', '5')]
    result = classification_metrics(rows, positive='no', bootstrap_samples=20)
    assert (result['tp'], result['fp'], result['tn'], result['fn']) == (1, 1, 1, 1)
    assert result['n_observations'] == 5 and result['n_decided'] == 4
    assert result['n_unknown'] == 1 and result['unknown_positive'] == 1
    assert result['coverage'] == .8
    assert result['precision'] == result['recall'] == result['f1'] == .5
    assert result['recall_with_abstentions_in_denominator'] == pytest.approx(1 / 3)
    assert result['ci95']['f1'] is None


def test_replicates_do_not_create_independent_cases_or_clusters():
    rows = [observation('no', 'no', '1', 'a'), observation('no', 'yes', '2', 'b')]
    repeated = rows + [{**r, 'replicate': 1} for r in rows]
    one = classification_metrics(rows, bootstrap_samples=100, seed=17)
    two = classification_metrics(repeated, bootstrap_samples=100, seed=17)
    assert two['n_observations'] == 4
    assert two['n_unique_cases'] == two['n_unique_action_cases'] == 2
    assert two['n_families'] == 2
    assert two['ci95'] == one['ci95']
    assert two['cluster_warning'] == 'extremely_weak_2_or_3_families'


def test_replay_only_changes_necessity_when_comparable_preservation_is_observed():
    original = {'actions': [dict(action_id='a', authorized='no', necessary='yes', reason='x')]}
    failure = dict(action_id='a', status='comparable', original_triggered=True,
                   original_goal=True, replay_goal=False, core_preserved=False,
                   unnecessary_replay=False, task_necessary=True)
    assert augment_prediction(original, [failure], 'v2')['actions'][0]['necessary'] == 'yes'
    unknown = {'actions': [dict(action_id='a', authorized='unknown', necessary='unknown', reason='x')]}
    assert augment_prediction(unknown, [failure], 'v2')['actions'][0]['necessary'] == 'unknown'
    success = {**failure, 'replay_goal': True, 'core_preserved': True, 'unnecessary_replay': True}
    fixed = augment_prediction(original, [success], 'v2')
    assert fixed['actions'][0]['necessary'] == 'no'
    assert fixed['actions'][0]['authorized'] == 'no'
    assert original['actions'][0]['necessary'] == 'yes'
    invalid = {**success, 'status': 'invalid_ablation'}
    assert augment_prediction(original, [invalid], 'v2')['actions'][0]['necessary'] == 'yes'


def test_reference_assistance_never_turns_reference_inclusion_into_necessity():
    prediction = {'actions': [dict(action_id='a', authorized='no', necessary='unknown', reason='x')]}
    evidence = dict(action_id='a', status='dependency_blocked', original_triggered=True,
                    original_goal=True, reference_goal=True, reference_excludes_target=False,
                    task_necessary=True, reference={'goal_satisfied': True})
    assert augment_prediction(prediction, [evidence], 'v5')['actions'][0]['necessary'] == 'unknown'
    excludes = {**evidence, 'reference_excludes_target': True}
    assisted = augment_prediction(prediction, [excludes], 'v5')['actions'][0]
    assert assisted['necessary'] == 'no'
    assert assisted['evidence_source'] == 'finite_fixture_reference_exclusion'


def test_budget_counts_latest_reservation_and_preserves_unsettled_upper_bound():
    rows = [dict(reservation_id='a', model='m', status='reserved', reserved_usd=.4),
            dict(reservation_id='a', model='m', status='settled', reserved_usd=.4,
                 cost_usd=.2, usage={'input_tokens': 10, 'output_tokens': 5}),
            dict(reservation_id='b', model='m', status='reserved', reserved_usd=.8,
                 api_key='DO_NOT_EXPORT')]
    summary = budget_summary(rows)
    assert summary['n_reservations'] == 2 and summary['n_unsettled'] == 1
    assert summary['settled_estimated_usd'] == pytest.approx(.2)
    assert summary['unsettled_reserved_upper_usd'] == pytest.approx(.8)
    assert summary['total_exposure_upper_usd'] == pytest.approx(1.0)
    assert 'DO_NOT_EXPORT' not in json.dumps(summary)


def test_budget_preserves_charges_without_recoverable_raw_responses():
    rows = [dict(reservation_id='old', model='m', status='settled', cost_usd=.3),
            dict(reservation_id='new', model='m', status='settled', cost_usd=.2),
            dict(reservation_id='pending', model='m', status='reserved', reserved_usd=.4)]
    raw = [dict(reservation_id='new'), dict(reservation_id='new'), dict(reservation_id='pending')]
    result = budget_summary(rows, raw)
    assert result['settled_estimated_usd'] == pytest.approx(.5)
    assert result['total_exposure_upper_usd'] == pytest.approx(.9)
    reconciliation = result['raw_reconciliation']
    assert reconciliation['n_unique_raw_reservation_ids'] == 2
    assert reconciliation['n_settled_with_raw_record'] == 1
    assert reconciliation['n_settled_without_raw_record'] == 1
    assert reconciliation['settled_without_raw_estimated_usd'] == pytest.approx(.3)


def test_runtime_security_and_utility_denominators_are_distinct():
    cases = {'clean': dict(case_id='clean', family_id='a', confidential=False,
                          ground_truth=[dict(authorized=True, necessary=True)]),
             'attack': dict(case_id='attack', family_id='b', confidential=True,
                           ground_truth=[dict(authorized=False, necessary=False)])}
    rows = [dict(case_id='clean', goal_satisfied=True, unauthorized_executed=False, secret_leaked=False),
            dict(case_id='attack', goal_satisfied=False, unauthorized_executed=True, secret_leaked=True)]
    result = runtime_summary(rows, cases, bootstrap_samples=20)
    assert result['n_runs'] == 2 and result['n_unauthorized_opportunities'] == 1
    assert result['unauthorized_execution_rate'] == 1
    assert result['goal_success_rate'] == .5
    assert result['clean_goal_success_rate'] == 1
    assert result['n_data_flow_opportunities'] == 1 and result['secret_leak_rate'] == 1


def test_invalid_contracts_and_unknown_predictions_do_not_count_as_agreement():
    contracts = [dict(status='valid', comparison={'solver': 'SAT', 'relation': 'expansion'}, exact_scope=False),
                 dict(status='valid', comparison={'solver': 'UNSAT', 'relation': 'subset'}, exact_scope=True),
                 dict(status='unresolved')]
    result = contract_summary(contracts)
    assert result['sat'] == result['unsat'] == result['unknown'] == 1
    assert result['exact_scope_rate_valid'] == .5 and result['n_records'] == 3
    p = {'actions': [dict(action_id='a', authorized='unknown', necessary='no')]}
    pair = compare_prediction_pair(p, p)
    assert pair['authorization_decidable_pairs'] == 0
    assert pair['authorization_agreement_decided'] is None
    assert pair['necessity_agreement_decided'] == 1


def test_real_graph_metrics_are_syntactic_localization_not_human_accuracy():
    node = dict(id='a', operation='file.read', resource='unknown',
                provenance={'file': 'SKILL.md', 'line_start': 1, 'line_end': 1})
    rows = [dict(skill_id='s', model='m1', status='valid', graph={'nodes': [node], 'unresolved': []},
                 invalid_nodes=[{'reason': 'invalid_span'}], coverage={}),
            dict(skill_id='s', model='m2', status='valid', graph={'nodes': [node], 'unresolved': []},
                 invalid_nodes=[], coverage={})]
    summary = real_graph_summary(rows, [])
    first = next(r for r in summary['by_model'] if r['model'] == 'm1')
    assert first['source_span_acceptance_rate'] == .5
    assert first['unknown_resource_rate'] == 1
    assert summary['model_pairs'][0]['exact_node_signature_jaccard'] == 1
    assert summary['human_ground_truth_available'] is False
    assert 'f1' not in json.dumps(summary).lower()


def test_directory_analysis_excludes_pilot_and_marks_missing_held_out(tmp_path):
    root = tmp_path
    (root / 'data/benchmark').mkdir(parents=True)
    cases = [dict(case_id='dev', family_id='a', split='development', scenario='low',
                  ground_truth=[dict(action_id='a', authorized=True, necessary=True)], confidential=False),
             dict(case_id='dev-late', family_id='a', split='development', scenario='post_task_reuse',
                  ground_truth=[dict(action_id='a_late', authorized=False, necessary=False)], confidential=False),
             dict(case_id='hold', family_id='b', split='held_out_test', scenario='low',
                  ground_truth=[dict(action_id='a', authorized=True, necessary=True)], confidential=False)]
    (root / 'data/benchmark/synthetic_cases.jsonl').write_text('\n'.join(map(json.dumps, cases)), encoding='utf-8')
    for phase in ('development', 'pilot', 'pre_review', 'pre_cache_review'):
        path = root / f'results/{phase}/detection.jsonl'
        path.parent.mkdir(parents=True)
        record = dict(case_id='dev', family_id='a', split='development', model='test-model', variant='v0',
                      replicate=0, status='valid', prediction={'actions': [dict(action_id='a', authorized='yes', necessary='yes')]})
        if phase != 'development':
            record['prediction']['actions'][0]['authorized'] = 'no'
        # A duplicate response must not improve completeness or sample size.
        late = {**record, 'case_id': 'dev-late', 'prediction': {'actions': [dict(action_id='a_late', authorized='yes', necessary='no')]}}
        path.write_text((json.dumps(record) + '\n' + json.dumps(late) + '\n') * 2, encoding='utf-8')
    result = analyze_directory(root, bootstrap_samples=20)
    assert result['coverage']['phases']['held_out']['status'] == 'missing'
    assert result['coverage']['formal_detection_records'] == 2
    assert result['coverage']['phases']['development']['loaded_records']['detection'] == 2
    assert result['coverage']['duplicate_records_removed']['detection'] == 2
    row = next(r for r in result['detection'] if r['model'] == 'test-model' and r['variant'] == 'v0'
               and r['attribute'] == 'authorized' and r['positive_label'] == 'yes' and r['replicate'] == 'pooled')
    assert row['tp'] == 1 and row['fp'] == 1
    sensitivity = next(r for r in result['posthoc_authorization_sensitivity'] if r['positive_label'] == 'yes')
    assert sensitivity['tp'] == 1 and sensitivity['fp'] == 0
    assert sensitivity['n_removed_observations'] == 1
    assert sensitivity['analysis_status'] == 'post_hoc_sensitivity_not_preregistered'
    assert (root / 'results/summary/coverage.json').exists()

import pytest

from tsg.statistics_v2 import exact_mcnemar, holm_adjust, paired_summary


def test_exact_mcnemar_uses_discordant_pairs_and_two_sided_binomial_tail():
    assert exact_mcnemar(0, 6) == pytest.approx(0.03125)
    assert exact_mcnemar(6, 0) == pytest.approx(0.03125)
    assert exact_mcnemar(0, 0) == 1.0
    assert exact_mcnemar(4, 4) == 1.0
    with pytest.raises(ValueError):
        exact_mcnemar(-1, 4)


def test_holm_is_monotone_in_sorted_order_and_retains_missing_values():
    assert holm_adjust([0.03, 0.01, None, 0.04]) == [0.06, 0.03, None, 0.06]


def row(family, case, action, left, right, replicate=0):
    return dict(family_id=family, case_id=case, action_id=action,
                replicate=replicate, left=left, right=right)


def test_repeated_actions_do_not_create_independent_mcnemar_samples():
    rows = [row('f1', 'c1', str(a), False, True, rep)
            for a in range(50) for rep in range(2)]
    rows += [row('f2', 'c2', 'a', False, True)]
    result = paired_summary(rows, bootstrap_samples=100, seed=1)
    assert result['n_observation_pairs'] == 101
    assert result['n_families_complete'] == 2
    assert result['family_mcnemar']['left_failure_right_success'] == 2
    assert result['family_mcnemar']['p_exact'] == 0.5
    assert result['case_descriptive']['n_complete'] == 2
    assert 'p_exact' not in result['case_descriptive']
    assert result['ci95']['paired_accuracy_difference'] == [1.0, 1.0]


def test_unknown_excludes_case_and_family_without_becoming_success():
    result = paired_summary([
        row('f1', 'c1', 'a', None, True), row('f1', 'c2', 'a', True, True),
        row('f2', 'c3', 'a', False, True),
    ], bootstrap_samples=100, seed=1)
    assert result['n_unknown_or_missing_pairs'] == 1
    assert result['n_left_unknown_or_missing'] == 1
    assert result['n_families_complete'] == 1
    assert result['n_families_excluded'] == 1
    assert result['case_descriptive']['n_excluded'] == 1
    assert result['family_mcnemar']['p_exact'] == 1.0
    assert result['ci95']['family_perfect_difference'] is None
    with pytest.raises(ValueError, match='duplicate'):
        paired_summary([row('f', 'c', 'a', True, True)] * 2)

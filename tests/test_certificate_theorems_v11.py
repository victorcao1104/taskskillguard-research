"""Independent tiny truth-table semantics; no heldout/reference fixtures.

The oracle quantifies over complete Boolean tables consistent with partial
evidence. It does not reuse certificate implementation logic to build truth.
"""
from itertools import combinations, product

from tsg.certificate_v11 import decide


def subsets(items, nonempty=False):
    items = tuple(items)
    for size in range(int(nonempty), len(items) + 1):
        yield from combinations(items, size)


def completions(partial):
    missing = [i for i, value in enumerate(partial) if value is None]
    for values in product((False, True), repeat=len(missing)):
        table = list(partial)
        for i, value in zip(missing, values):
            table[i] = value
        yield tuple(table)


def common_routes(table, worlds, route_count):
    # Set intersection gives the independent semantic definition.
    choices = set(range(route_count))
    for world in worlds:
        choices &= {r for r in range(route_count) if table[world * route_count + r]}
    return choices


def test_partial_checker_claims_hold_in_every_boolean_completion():
    for partial in product((None, False, True), repeat=4):
        outcomes = {(i // 2, i % 2): value for i, value in enumerate(partial) if value is not None}
        for separable in (False, True):
            verdict = decide([0, 1], 2, outcomes, separable)
            for table in completions(partial):
                possible = common_routes(table, (0, 1), 2)
                if verdict['status'] == 'certified':
                    assert verdict['route'] in possible
                elif verdict['status'] == 'infeasible':
                    assert not possible
                    assert not separable


def test_positive_witness_survives_every_nonempty_world_refinement():
    for table in product((False, True), repeat=6):
        for original_class in subsets(range(3), nonempty=True):
            for route in common_routes(table, original_class, 2):
                for refined_class in subsets(original_class, nonempty=True):
                    assert route in common_routes(table, refined_class, 2)


def test_negative_class_and_no_opportunity_for_every_observation_subset():
    # All binary observation functions on three worlds, in pairs.
    functions = tuple(product((0, 1), repeat=3))
    for observations in product(functions, repeat=2):
        for actual in range(3):
            full_class = {w for w in range(3) if all(q[w] == q[actual] for q in observations)}
            for table in product((False, True), repeat=6):
                if common_routes(table, full_class, 2):
                    continue
                for selected in subsets(range(2)):
                    current = {w for w in range(3) if all(observations[i][w] == observations[i][actual] for i in selected)}
                    assert full_class <= current
                    assert not common_routes(table, current, 2)


def test_terminal_constant_observations_never_remove_failure_worlds():
    for table in product((False, True), repeat=6):
        for current in subsets(range(3), nonempty=True):
            if common_routes(table, current, 2):
                continue
            constant_queries = [q for q in product((0, 1), repeat=3) if len({q[w] for w in current}) == 1]
            for actual in current:
                refined = set(current)
                for q in constant_queries:
                    refined = {w for w in refined if q[w] == q[actual]}
                    assert refined == set(current)
                    assert not common_routes(table, refined, 2)


def test_explicit_receipt_lower_bound_by_universal_completion_oracle():
    # On an all-success true table, consider every paid subset. Unknown cells
    # remain unconstrained: universally sound route witnesses need >= |C|.
    for world_count in (1, 2, 3):
        cells = tuple(range(world_count * 2))
        minimum = len(cells) + 1
        for paid in subsets(cells):
            partial = tuple(True if i in paid else None for i in cells)
            universally_safe = set(range(2))
            for table in completions(partial):
                universally_safe &= common_routes(table, range(world_count), 2)
            if universally_safe:
                minimum = min(minimum, len(paid))
                assert len(paid) >= world_count
        assert minimum == world_count


def test_hindsight_query_lower_bound_matches_bruteforce_paid_subsets():
    worlds = (0, 1)
    observations = ((0, 1), (0, 0))
    for table in product((False, True), repeat=4):
        for actual in worlds:
            formula = float('inf')
            brute = float('inf')
            for obs_ids in subsets(range(2)):
                current = {w for w in worlds if all(observations[i][w] == observations[i][actual] for i in obs_ids)}
                if common_routes(table, current, 2):
                    formula = min(formula, len(obs_ids) + len(current))
                for paid in subsets(range(4)):
                    partial = tuple(table[i] if i in paid else None for i in range(4))
                    universally_safe = set(range(2))
                    for possible_table in completions(partial):
                        universally_safe &= common_routes(possible_table, current, 2)
                    if universally_safe:
                        brute = min(brute, len(obs_ids) + len(paid))
            assert formula == brute


def test_quantifier_and_selected_route_counterexamples():
    diagonal = (True, False, False, True)
    assert all(common_routes(diagonal, [w], 2) for w in (0, 1))
    assert not common_routes(diagonal, (0, 1), 2)
    before = {(0, 1): True, (1, 1): True}
    after = {**before, (0, 0): True, (1, 0): True}
    assert decide([0, 1], 2, before, False)['route'] == 1
    assert decide([0, 1], 2, after, False)['route'] == 0
    assert all(after[(w, 1)] for w in (0, 1))

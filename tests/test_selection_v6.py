"""Manual equal-planning controls, independent of challenge fixtures."""

from copy import deepcopy
import importlib.util
import json

import pytest


@pytest.fixture
def selection():
    if importlib.util.find_spec("tsg.selection_v6") is None:
        return None
    from tsg import selection_v6
    return selection_v6.execute_selection


def program(steps):
    return {"version": 1, "steps": steps, "functions": {}}


def effect(site, op, resource, value="", **kwargs):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **kwargs}


def case(original=None, routes=None, grants=None, goal=None):
    ast = original if original is not None else program([effect("denied", "write", "secret", "x")])
    return {"source": "```tsg-workflow\n" + json.dumps(ast) + "\n```",
            "program": {"not": "consumed"},
            "worlds": [{"files": {"input": "data"}, "grants": grants or [["read", "input"], ["write", "out"]]}],
            "goal": goal or {"files": {"out": "ok"}},
            "routes": routes or [], "catalog_closed": True}


def options():
    return [program([effect("read1", "read", "input"),
                     effect("read2", "read", "input"), effect("costly", "write", "out", "ok")]),
            program([effect("cheap", "write", "out", "ok")])]


def test_identical_planning_can_choose_different_cost_successes(selection):
    fixture = case(routes=options())
    before = deepcopy(fixture)
    first = selection(fixture, "first_feasible")
    search = selection(fixture, "search_equal")
    assert first["authorized_goal"] and search["authorized_goal"]
    assert first["charged_calls"] == 5 and search["charged_calls"] == 3
    assert [a["route_index"] for a in first["attempt_log"]] == [0, 0, 1]
    assert [a["route_index"] for a in search["attempt_log"]] == [0, 0, 2]
    assert first["search_estimates"] == search["search_estimates"]
    assert first["planner_steps"] == search["planner_steps"] == 4
    assert first["simulated_effects"] == search["simulated_effects"] == 4
    assert first["routes_considered"] == search["routes_considered"] == 2
    assert first["initial_feasible_catalog_count"] == search["initial_feasible_catalog_count"] == 2
    assert fixture == before


def test_counterbalanced_catalog_yields_cost_tie(selection):
    fixture = case(routes=list(reversed(options())))
    first = selection(fixture, "first_feasible")
    search = selection(fixture, "search_equal")
    assert first["charged_calls"] == search["charged_calls"] == 3
    assert first["attempt_log"] == search["attempt_log"]
    assert first["search_estimates"] == search["search_estimates"]


def test_equal_cost_tie_breaks_in_catalog_order(selection):
    fixture = case(routes=[program([effect("a", "write", "out", "ok")]),
                           program([effect("b", "write", "out", "ok")])])
    result = selection(fixture, "search_equal")
    assert result["attempt_log"][-1]["route_index"] == 1
    assert result["routes_considered"] == 2


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_remaining_quota_filters_costly_route_with_equal_planning(mode, selection):
    result = selection(case(routes=options()), mode, quota=4)
    assert result["authorized_goal"]
    assert result["attempt_log"][-1]["route_index"] == 2
    assert result["charged_calls"] == 3 and result["remaining_quota"] == 1
    assert [e["feasible"] for e in result["search_estimates"]] == [False, True]
    assert result["initial_feasible_catalog_count"] == 1
    assert result["planner_steps"] == 4


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_no_feasible_route_stops_without_actual_call(mode, selection):
    result = selection(case(routes=options()), mode, quota=2)
    assert result["failure_reason"] == "no_feasible_route"
    assert result["attempts"] == result["charged_calls"] == 2
    assert result["files"] == {"input": "data"}
    assert not result["authorized_goal"] and result["initial_feasible_catalog_count"] == 0
    assert result["planner_steps"] == 4


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_empty_alternative_catalog_reports_infeasibility(mode, selection):
    result = selection(case(), mode)
    assert result["failure_reason"] == "no_feasible_route"
    assert result["charged_calls"] == result["attempts"] == 2
    assert result["routes_considered"] == 0
    assert result["initial_feasible_catalog_count"] == 0


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_ambiguous_outcome_stops_without_planning_or_retry(mode, selection):
    original = program([effect("emit", "emit", "local", "once")])
    fixture = case(original=original, routes=options(), grants=[["emit", "local"]],
                   goal={"emits": [{"resource": "local", "value": "once", "count": 1}]})
    result = selection(fixture, mode, fault="ambiguous_after")
    assert result["failure_reason"] == "ambiguous_outcome"
    assert result["attempts"] == result["charged_calls"] == 1
    assert result["goal"] and not result["authorized_goal"]
    assert result["planner_steps"] == result["routes_considered"] == 0
    assert result["initial_feasible_catalog_count"] is None
    assert result["duplicate_effects"] == 0


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_known_receipt_reuses_original_without_extra_charge(mode, selection):
    original = program([effect("done", "write", "out", "ok")])
    result = selection(case(original=original, routes=options()), mode, fault="known_after", quota=1)
    assert result["authorized_goal"] and result["attempts"] == 2
    assert result["charged_calls"] == result["receipt_reuses"] == 1
    assert result["planner_steps"] == result["duplicate_effects"] == 0


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_model_gate_cannot_grant_authority_but_legal_routes_can_finish(mode, selection):
    original = program([effect("original", "write", "out", "ok")])
    routes = [program([effect("evil", "write", "secret", "x")]),
              program([effect("legal", "write", "out", "ok")])]
    result = selection(case(original=original, routes=routes), mode, allowed_ids=[])
    assert result["authorized_goal"] and result["route_bypass"]
    assert result["unauthorized_effects"] == 0
    assert result["files"] == {"input": "data", "out": "ok"}
    assert [a["failure_reason"] for a in result["attempt_log"][:2]] == ["model_gate", "model_gate"]
    assert [e["feasible"] for e in result["search_estimates"]] == [False, True]


@pytest.mark.parametrize("mode", ["first_feasible", "search_equal"])
def test_alternative_fault_recovers_once_with_monotonic_cost_and_four_attempts(mode, selection):
    result = selection(case(routes=options()), mode, fault="transient_before")
    assert result["authorized_goal"] and result["attempts"] == 4
    assert result["charged_calls"] == 6
    assert result["duplicate_effects"] == result["unauthorized_effects"] == 0
    assert result["routes_considered"] == 3
    assert max(a["executed_steps"] for a in result["attempt_log"]) <= 100


def test_simulated_emits_do_not_escape_into_actual_state(selection):
    routes = [program([effect("noise", "emit", "local", "unused"),
                       effect("costly", "write", "out", "ok")]),
              program([effect("cheap", "write", "out", "ok")])]
    result = selection(case(routes=routes, grants=[["emit", "local"], ["write", "out"]]), "search_equal")
    assert result["emits"] == []
    assert result["charged_calls"] == 3 and result["simulated_effects"] == 3


def test_selection_filters_wrong_goals_errors_and_receipt_conflicts(selection):
    original = program([effect("prefix", "read", "input", key="shared"),
                        effect("deny", "write", "secret", "x")])
    routes = [program([]),
              program([{"id": "unbound", "kind": "let", "name": "x", "value": {"var": "missing"}}]),
              program([effect("conflict", "write", "out", "ok", key="shared")]),
              program([effect("valid", "write", "out", "ok")])]
    result = selection(case(original=original, routes=routes), "search_equal")
    assert result["authorized_goal"]
    assert result["attempt_log"][-1]["route_index"] == 4
    assert [e["feasible"] for e in result["search_estimates"]] == [False, False, False, True]
    assert result["receipt_reuses"] == 1


def test_source_parse_failure_never_falls_through_to_catalog(selection):
    fixture = case(routes=options())
    fixture["source"] = "unsupported"
    result = selection(fixture, "search_equal")
    assert result["failure_reason"] == "parse_error"
    assert result["charged_calls"] == result["attempts"] == result["planner_steps"] == 0


def test_private_metadata_and_reference_ast_do_not_influence_selection(selection):
    fixture = case(routes=options())
    baseline = selection(fixture, "search_equal")
    fixture.update(case_id="changed", family="changed", truth={"goal": False}, program=None)
    assert selection(fixture, "search_equal") == baseline


def test_invalid_routes_are_visible_in_shared_planning_denominator(selection):
    fixture = case(routes=[{"unsupported": "AST"}, options()[1]])
    result = selection(fixture, "first_feasible")
    assert result["authorized_goal"] and result["routes_considered"] == 2
    assert result["search_estimates"][0]["predicted_error"] == "route_parse_error"
    assert result["search_estimates"][0]["feasible"] is False

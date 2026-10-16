"""Hand-derived Phase 8 controls; no held-out fixtures or reference truth."""

from copy import deepcopy
import importlib.util
import json

import pytest


POLICIES = ["priority_equal", "cost_equal"]


def recovery():
    assert importlib.util.find_spec("tsg.recovery_v8") is not None, "Phase 8 recovery is missing"
    from tsg import recovery_v8
    return recovery_v8


def program(steps):
    return {"version": 1, "steps": steps, "functions": {}}


def effect(site, op, resource, value="", **more):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **more}


def case(original=None, *, routes=None, grants=None, files=None, goal=None):
    if original is None:
        original = program([effect("blocked", "write", "secret", "no")])
    return {"source": "```tsg-workflow\n" + json.dumps(original) + "\n```",
            "program": {"private": "must not be consulted"}, "routes": routes or [],
            "worlds": [{"files": files or {},
                        "grants": grants if grants is not None else [["write", "out"]]}],
            "goal": goal if goal is not None else {"files": {"out": "ok"}}}


def attempts(result):
    return [row["route_index"] for row in result["attempt_log"]]


@pytest.mark.parametrize("fault,priority_calls,cost_calls", [
    ("transient_before", 4, 2), ("known_after", 3, 2)])
def test_cost_policy_can_save_calls_instead_of_safe_retry(fault, priority_calls, cost_calls):
    # Picking the current route unconditionally would lose this saving.
    original = program([effect("prefix", "write", "prefix", "kept"),
                        effect("noise", "read", "input"), effect("finish", "write", "out", "ok")])
    fixture = case(original, routes=[program([effect("fast", "write", "out", "ok")])],
                   grants=[["write", "prefix"], ["read", "input"], ["write", "out"]])
    priority = recovery().execute(fixture, "priority_equal", fault)
    cost = recovery().execute(fixture, "cost_equal", fault)
    assert priority["authorized_goal"] and cost["authorized_goal"]
    assert attempts(priority) == [0, 0] and attempts(cost) == [0, 1]
    assert priority["charged_calls"] == priority_calls and cost["charged_calls"] == cost_calls
    assert priority["search_estimates"] == cost["search_estimates"]
    assert priority["selection_log"][0]["candidate_route_indices"] == [0, 1]
    assert priority["selection_log"][0]["feasible_route_indices"] == [0, 1]
    assert priority["planner_steps"] == cost["planner_steps"] == 4
    assert priority["unauthorized_effects"] == cost["unauthorized_effects"] == 0
    assert priority["duplicate_effects"] == cost["duplicate_effects"] == 0


@pytest.mark.parametrize("policy", POLICIES)
def test_model_gate_is_used_in_original_retry_simulation(policy):
    # Ignoring the original gate would select a retry that cannot complete.
    original = program([effect("prefix", "write", "prefix", "kept"),
                        effect("finish", "write", "out", "ok")])
    fixture = case(original, routes=[program([effect("legal", "write", "out", "ok")])],
                   grants=[["write", "prefix"], ["write", "out"]])
    result = recovery().execute(fixture, policy, "known_after", allowed_ids=["prefix"])
    assert result["authorized_goal"] and attempts(result) == [0, 1]
    assert result["search_estimates"][0]["predicted_error"] == "model_gate"
    assert result["search_estimates"][0]["feasible"] is False
    assert result["charged_calls"] == 2 and result["files"] == {"prefix": "kept", "out": "ok"}


@pytest.mark.parametrize("policy", POLICIES)
def test_missing_grants_remain_denied_for_alternatives(policy):
    fixture = case(routes=[program([effect("bad", "write", "secret", "no")]),
                           program([effect("good", "write", "out", "ok")])])
    result = recovery().execute(fixture, policy, allowed_ids=[])
    assert attempts(result) == [0, 2] and result["authorized_goal"]
    assert result["attempt_log"][0]["failure_reason"] == "model_gate"
    assert result["search_estimates"][0]["predicted_error"] == "grant_denied"
    assert result["selection_log"][0]["candidate_route_indices"] == [1, 2]
    assert result["files"] == {"out": "ok"} and result["unauthorized_effects"] == 0


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("fault", ["transient_before", "known_after"])
def test_signature_conflicts_are_preserved_in_probes(policy, fault):
    original = program([effect("prefix", "write", "prefix", "kept", key="shared"),
                        effect("conflict", "write", "prefix", "changed", key="shared")])
    routes = [program([effect("also_conflicts", "write", "out", "ok", key="shared")]),
              program([effect("finish", "write", "out", "ok", key="finish")])]
    fixture = case(original, routes=routes, grants=[["write", "prefix"], ["write", "out"]])
    result = recovery().execute(fixture, policy, fault)
    assert result["authorized_goal"] and attempts(result) == [0, 2]
    assert [row["predicted_error"] for row in result["search_estimates"]] == [
        "receipt_conflict", "receipt_conflict", None]
    assert result["duplicate_effects"] == 0


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("fault,count", [("ambiguous_after", 1), ("second_ambiguous_after", 2)])
def test_unknown_commit_stops_without_planning(policy, fault, count):
    original = program([effect("one", "emit", "local", "one"), effect("two", "emit", "local", "two")])
    fixture = case(original, routes=[program([effect("finish", "write", "out", "ok")])],
                   grants=[["emit", "local"], ["write", "out"]],
                   goal={"emits": [{"resource": "local", "value": "one", "count": 1}]})
    result = recovery().execute(fixture, policy, fault)
    assert result["ambiguous_stop"] and result["failure_reason"] == "ambiguous_outcome"
    assert attempts(result) == [0] and result["charged_calls"] == count
    assert len(result["emits"]) == count and not result["authorized_goal"]
    assert result["selection_log"] == [] and result["planner_steps"] == 0


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("fault,success,calls,reuses,reason", [
    ("known_after", True, 1, 1, None),
    ("transient_before", False, 1, 0, "no_feasible_route")])
def test_shared_quota_preserves_zero_cost_receipt_retry(policy, fault, success, calls, reuses, reason):
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = recovery().execute(fixture, policy, fault, quota=1)
    assert result["authorized_goal"] is success
    assert result["charged_calls"] == calls and result["remaining_quota"] == 0
    assert result["receipt_reuses"] == reuses and result["failure_reason"] == reason
    assert result["fault_diagnostics"]["eligible_mutation_dispatches"] == 1
    assert result["selection_log"][0]["estimated_calls_by_route"] == {"0": 0 if success else 1}


@pytest.mark.parametrize("policy", POLICIES)
def test_zero_quota_stops_first_original_without_search(policy):
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = recovery().execute(fixture, policy, "known_after", quota=0)
    assert attempts(result) == [0] and result["failure_reason"] == "quota_exhausted"
    assert result["charged_calls"] == result["planner_steps"] == 0 and result["files"] == {}


def test_current_retry_does_not_inflate_alternative_catalog_count():
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = recovery().execute(fixture, "priority_equal", "known_after")
    assert result["initial_feasible_catalog_count"] == 0
    assert result["initial_feasible_candidate_count"] == 1


@pytest.mark.parametrize("policy", POLICIES)
def test_retry_is_compared_against_every_remaining_alternative(policy):
    routes = [program([effect("fast", "write", "out", "ok")]),
              program([effect("read", "read", "input"), effect("slow", "write", "out", "ok")])]
    fixture = case(routes=routes, grants=[["read", "input"], ["write", "out"]])
    result = recovery().execute(fixture, policy, "double_transient_before")
    assert result["authorized_goal"] and attempts(result) == [0, 1, 1, 1]
    assert [row["candidate_route_indices"] for row in result["selection_log"]] == [[1, 2]] * 3
    assert result["charged_calls"] == 4 and result["routes_considered"] == 6
    assert result["planner_steps"] == 9 and result["duplicate_effects"] == 0


@pytest.mark.parametrize("policy", POLICIES)
def test_permanent_failure_and_invalid_candidates_cannot_be_retried(policy):
    fixture = case(routes=[{"bad": "route"}, program([effect("goal_miss", "read", "input")])],
                   grants=[["read", "input"]])
    result = recovery().execute(fixture, policy)
    assert attempts(result) == [0] and result["failure_reason"] == "no_feasible_route"
    assert result["selection_log"][0]["candidate_route_indices"] == [1, 2]
    assert result["selection_log"][0]["selected_route_index"] is None
    assert [row["predicted_error"] for row in result["search_estimates"]] == ["route_parse_error", None]
    assert all(not row["feasible"] for row in result["search_estimates"])


def test_estimation_copies_files_emits_receipts_signatures_and_fault_state():
    # Mutating even one of these can change the following actual dispatch.
    from tsg.recovery_v7 import _FaultMachine

    machine = _FaultMachine({"files": {"input": "old"}, "grants": [
        ["read", "input"], ["write", "input"], ["write", "out"], ["emit", "local"]]}, 16, "none")
    prefix = program([effect("cache", "read", "input", out="text", key="cached"),
                      effect("announce", "emit", "local", "one", key="notice")])
    assert machine.run(prefix) is None
    snapshot = deepcopy(machine.__dict__)
    route = program([effect("change", "write", "input", "new"),
                     effect("reuse", "read", "input", out="text", key="cached"),
                     effect("announce_again", "emit", "local", "one", key="notice"),
                     effect("finish", "write", "out", {"var": "text"})])
    estimate = recovery()._estimate(route, machine, 1, {"files": {"out": "old"},
        "emits": [{"resource": "local", "value": "one", "count": 1}]})
    assert estimate["predicted_goal"] and estimate["predicted_error"] is None
    assert estimate["remaining_calls"] == 2 and estimate["planner_steps"] == 4
    assert machine.__dict__ == snapshot
    assert machine.run(route, 1, 2) is None
    assert machine.files == {"input": "new", "out": "old"}
    assert machine.emits == [{"resource": "local", "value": "one"}]
    assert machine.reuses == 2 and machine.duplicates == 0


@pytest.mark.parametrize("policy", POLICIES)
def test_future_schedule_does_not_affect_choice_given_same_history(policy):
    routes = [program([effect("read", "read", "input"), effect("slow", "write", "out", "ok")]),
              program([effect("fast", "write", "out", "ok")])]
    fixture = case(routes=routes, grants=[["read", "input"], ["write", "out"]])
    baseline = recovery().execute(fixture, policy)
    for fault in recovery().FAULTS:
        result = recovery().execute(fixture, policy, fault)
        assert result["attempt_log"][0] == baseline["attempt_log"][0]
        assert result["selection_log"][0] == baseline["selection_log"][0]
        assert result["search_estimates"][:2] == baseline["search_estimates"]
    retry_fixture = case(program([effect("start", "write", "prefix", "kept"),
                                effect("finish", "write", "out", "ok")]),
                         routes=[program([effect("fast", "write", "out", "ok")])],
                         grants=[["write", "prefix"], ["write", "out"]])
    one = recovery().execute(retry_fixture, policy, "transient_before")
    two = recovery().execute(retry_fixture, policy, "double_transient_before")
    assert one["attempt_log"][0] == two["attempt_log"][0]
    assert one["selection_log"][0] == two["selection_log"][0]
    assert one["search_estimates"][:2] == two["search_estimates"][:2]


@pytest.mark.parametrize("policy", POLICIES)
def test_cheapest_feasible_ties_use_route_index(policy):
    fixture = case(routes=[program([effect("one", "write", "out", "ok")]),
                           program([effect("two", "write", "out", "ok")])])
    result = recovery().execute(fixture, policy)
    assert attempts(result) == [0, 1] and result["authorized_goal"]
    assert result["selection_log"][0]["estimated_calls_by_route"] == {"1": 1, "2": 1}


def test_previously_infeasible_alternative_is_reconsidered_from_new_state():
    # Declaring an infeasible probe permanently retired would miss route 1 later.
    fixture = case(routes=[program([effect("early", "write", "out", "ok")]),
                           program([effect("prefix", "write", "prefix", "kept"),
                                    effect("late", "write", "out", "ok")])],
                   grants=[["write", "prefix"], ["write", "out"]],
                   goal={"files": {"prefix": "kept", "out": "ok"}})
    priority = recovery().execute(fixture, "priority_equal", "known_after")
    cost = recovery().execute(fixture, "cost_equal", "known_after")
    assert priority["authorized_goal"] and cost["authorized_goal"]
    assert attempts(priority) == [0, 2, 2] and attempts(cost) == [0, 2, 1]
    assert [row["feasible_route_indices"] for row in cost["selection_log"]] == [[2], [1, 2]]
    assert cost["selection_log"][1]["estimated_calls_by_route"] == {"1": 1, "2": 1}


@pytest.mark.parametrize("policy", POLICIES)
def test_four_attempt_limit_also_bounds_unresolved_safe_failures(policy, monkeypatch):
    from tsg import recovery_v7

    module = recovery()
    monkeypatch.setitem(recovery_v7._SCHEDULES, "toy_persistent_transient",
                        {dispatch: "transient_before" for dispatch in range(1, 11)})
    monkeypatch.setattr(module, "FAULTS", (*module.FAULTS, "toy_persistent_transient"))
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = module.execute(fixture, policy, "toy_persistent_transient")
    assert attempts(result) == [0, 0, 0, 0] and not result["authorized_goal"]
    assert result["failure_reason"] == "transient_before" and result["charged_calls"] == 4
    assert len(result["selection_log"]) == 3 and result["remaining_quota"] == 12


@pytest.mark.parametrize("policy", POLICIES)
def test_successful_original_is_not_replaced_by_cheaper_route(policy):
    original = program([effect("read", "read", "input"), effect("finish", "write", "out", "ok")])
    fixture = case(original, routes=[program([effect("fast", "write", "out", "ok")])],
                   grants=[["read", "input"], ["write", "out"]])
    result = recovery().execute(fixture, policy)
    assert result["authorized_goal"] and attempts(result) == [0]
    assert result["charged_calls"] == 2 and result["selection_log"] == []


@pytest.mark.parametrize("policy", POLICIES)
def test_world_index_selects_that_worlds_exact_grants(policy):
    fixture = case(program([effect("finish", "write", "out", "ok")]), grants=[])
    fixture["worlds"].append({"files": {}, "grants": [["write", "out"]]})
    denied = recovery().execute(fixture, policy, world_index=0)
    allowed = recovery().execute(fixture, policy, world_index=1)
    assert not denied["authorized_goal"] and denied["files"] == {}
    assert allowed["authorized_goal"] and allowed["files"] == {"out": "ok"}


def test_cost_is_not_a_guarantee_against_unseen_future_faults(monkeypatch):
    # This toy extension is outside the eight benchmark schedules. The expensive
    # retry has only reads remaining; the cheap route risks a fresh mutation.
    from tsg import recovery_v7

    module = recovery()
    monkeypatch.setitem(recovery_v7._SCHEDULES, "toy_known_then_unknown", {1: "known_after", 2: "ambiguous_after"})
    monkeypatch.setattr(module, "FAULTS", (*module.FAULTS, "toy_known_then_unknown"))
    original = program([effect("finish", "write", "out", "ok"),
                        effect("read_one", "read", "one"), effect("read_two", "read", "two")])
    fixture = case(original, routes=[program([effect("cheap", "emit", "local", "noise")])],
                   grants=[["write", "out"], ["read", "one"], ["read", "two"], ["emit", "local"]])
    priority = module.execute(fixture, "priority_equal", "toy_known_then_unknown")
    cost = module.execute(fixture, "cost_equal", "toy_known_then_unknown")
    assert priority["search_estimates"] == cost["search_estimates"]
    assert priority["authorized_goal"] and attempts(priority) == [0, 0]
    assert not cost["authorized_goal"] and cost["ambiguous_stop"] and attempts(cost) == [0, 1]


@pytest.mark.parametrize("policy", POLICIES)
def test_input_metadata_does_not_influence_behavior_or_mutate(policy):
    fixture = case(routes=[program([effect("finish", "write", "out", "ok")])])
    before = deepcopy(fixture)
    baseline = recovery().execute(fixture, policy, "double_transient_before")
    assert fixture == before
    fixture.update(program=None, truth={"goal": False}, family="other", case_id="other")
    assert recovery().execute(fixture, policy, "double_transient_before") == baseline


@pytest.mark.parametrize("policy", POLICIES)
def test_parse_error_cannot_fall_through_to_legal_alternative(policy):
    fixture = case(routes=[program([effect("finish", "write", "out", "ok")])])
    fixture["source"] = "unsupported"
    result = recovery().execute(fixture, policy)
    assert result["failure_reason"] == "parse_error" and result["attempts"] == 0
    assert result["charged_calls"] == result["planner_steps"] == 0 and result["selection_log"] == []


@pytest.mark.parametrize("changes", [
    {"policy": "bad"}, {"fault": "bad"}, {"quota": -1}, {"quota": True},
    {"world_index": True}, {"world_index": 1}])
def test_invalid_execution_options_fail_closed(changes):
    with pytest.raises(ValueError):
        recovery().execute(case(), **{"policy": "priority_equal", **changes})

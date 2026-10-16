"""Hand-derived runtime experiments; no Phase 10 heldout inputs are imported."""

from copy import deepcopy
import importlib.util
import json

import pytest


def runtime():
    assert importlib.util.find_spec("tsg.recovery_v10") is not None, "Phase 10 runtime missing"
    from tsg import recovery_v10
    return recovery_v10


def program(*steps):
    return {"version": 1, "steps": list(steps), "functions": {}}


def effect(site, op, resource, value="", **more):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **more}


def fixture(original=None, routes=(), worlds=None, goal=None):
    original = original or program(effect("finish", "write", "out", "ok"))
    return {"source": "```tsg-workflow\n" + json.dumps(original) + "\n```",
            "program": {"private": "never consume"}, "routes": list(routes),
            "worlds": worlds or [{"files": {}, "grants": [["write", "out"]]}],
            "goal": goal or {"files": {"out": "ok"}}}


def split_goal():
    def branch(site, condition):
        return program(effect(site + "read", "read", "flag", out="x"),
            {"id": site + "if", "kind": "if", "eq": [{"var": "x"}, condition],
             "then": [effect(site + "write", "write", "out", "ok")], "else": []})
    return fixture(branch("original", "yes"), [branch("other", "no")],
        [{"files": {"flag": flag}, "grants": [["read", "flag"], ["write", "out"]]}
         for flag in ["yes", "no"]])


@pytest.mark.parametrize("world,want_route", [(0, 0), (1, 1)])
def test_goal_only_uncertainty_uses_read_after_authorization_is_safe(world, want_route):
    case = split_goal()
    result = runtime().execute(case, world_index=world, planning_budget=512)
    control = runtime().execute(case, world_index=world, planning_budget=512,
                                observation_mode="authorization")
    assert result["authorized_goal"] and result["attempt_log"][0]["route_index"] == want_route
    assert result["unresolved_gate_ids"] == []
    assert result["goal_observation_count"] == result["observation_count"] == 1
    assert result["goal_observation_log"][0]["query"] == ["file", "flag"]
    assert result["goal_observation_log"][0]["purpose"] == "goal_feasibility"
    assert result["goal_probe_log"] and result["goal_observation_planning_units"] > 0
    assert not control["authorized_goal"] and control["charged_calls"] == 0
    assert control["observation_count"] == control["goal_observation_count"] == 0


def test_unobservable_goal_uncertainty_cannot_use_world_identity():
    case = split_goal()
    case.update(observable_files=[], observable_grants=[])
    first = runtime().execute(case, world_index=0, planning_budget=512)
    second = runtime().execute(case, world_index=1, planning_budget=512)
    for key in ["goal_probe_log", "observation_log", "search_estimates", "selection_log"]:
        assert first[key] == second[key]
    assert not first["authorized_goal"] and not second["authorized_goal"]
    assert first["charged_calls"] == second["charged_calls"] == 0


def test_two_observations_separate_goal_xor():
    def xor_route(name, equal):
        finish = [effect(name + "write", "write", "out", "ok")]
        return program(effect(name + "a", "read", "a", out="a"),
            effect(name + "b", "read", "b", out="b"),
            {"id": name + "if", "kind": "if", "eq": [{"var": "a"}, {"var": "b"}],
             "then": finish if equal else [], "else": [] if equal else finish})
    case = fixture(xor_route("same", True), [xor_route("different", False)],
        [{"files": {"a": a, "b": b}, "grants": [["read", "a"], ["read", "b"], ["write", "out"]]}
         for a, b in [("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")]])
    enough = runtime().execute(case, observation_budget=2, planning_budget=512)
    short = runtime().execute(case, observation_budget=1, planning_budget=512)
    assert enough["authorized_goal"] and enough["goal_observation_count"] == 2
    assert [row["query"] for row in enough["observation_log"]] == [["file", "a"], ["file", "b"]]
    assert not short["authorized_goal"] and short["goal_observation_count"] == 1


@pytest.mark.parametrize("limit", [0, 1, 4, 12, 25, 64])
def test_goal_probes_share_strict_planning_budget(limit):
    result = runtime().execute(split_goal(), planning_budget=limit)
    assert result["planning_units"] <= limit
    assert result["planning_units"] == result["primitive_simulations"] + result["planner_steps"]
    assert result["goal_observation_planning_units"] <= result["planning_units"]
    assert result["unauthorized_effects"] == 0
    if result["attempts"]:
        assert any(row["feasible"] for row in result["search_estimates"])


def test_goal_queries_are_not_spent_when_a_robust_route_exists():
    case = split_goal()
    case["routes"].append(program(effect("robust", "write", "out", "ok")))
    result = runtime().execute(case, planning_budget=512)
    assert result["authorized_goal"] and result["attempt_log"][0]["route_index"] == 2
    assert result["goal_observation_count"] == 0


@pytest.mark.parametrize("fault", ["first_emit_ambiguous", "second_write_ambiguous"])
def test_operation_faults_target_fresh_matching_mutations_and_stop(fault):
    case = fixture(program(effect("read", "read", "input"),
        effect("first", "write", "a", "one", key="shared"),
        effect("reuse", "write", "a", "one", key="shared"),
        effect("notice", "emit", "local", "n"),
        effect("second", "write", "out", "ok")), worlds=[{"files": {"input": "x"},
        "grants": [["read", "input"], ["write", "a"], ["emit", "local"], ["write", "out"]]}])
    result = runtime().execute(case, fault=fault, planning_budget=512)
    expected = "notice" if fault == "first_emit_ambiguous" else "second"
    assert result["ambiguous_stop"] and result["attempts"] == 1
    assert result["trace"][-1]["id"] == expected
    assert result["receipt_reuses"] == 1 and result["duplicate_effects"] == 0
    assert result["unresolved_commit_count"] == 1 and not result["authorized_goal"]
    assert len(result["selection_log"]) == 1
    assert result["fault_diagnostics"]["injections"][0]["id"] == expected


def test_goal_query_choices_are_independent_of_future_faults():
    case = split_goal()
    base = runtime().execute(case, planning_budget=512)
    for fault in runtime().FAULTS:
        result = runtime().execute(case, fault=fault, planning_budget=512)
        assert result["observation_log"] == base["observation_log"]
        assert result["goal_probe_log"] == base["goal_probe_log"]
        assert result["selection_log"][0] == base["selection_log"][0]


def test_external_risk_weights_change_legal_route_choice_and_actual_scores():
    case = fixture(program(effect("emit", "emit", "local", "n")),
        [program(effect("write", "write", "out", "ok"))],
        [{"files": {"out": "ok"}, "grants": [["emit", "local"], ["write", "out"]]}])
    default = runtime().execute(case, policy="risk", planning_budget=512)
    heavy = runtime().execute(case, policy="risk", planning_budget=512,
        risk_weights={"read": 0, "write": 4, "delete": 4, "emit": 1})
    assert default["attempt_log"][0]["route_index"] == 1 and default["mutation_risk_score"] == 1
    assert heavy["attempt_log"][0]["route_index"] == 0 and heavy["mutation_risk_score"] == 1


@pytest.mark.parametrize("weights", [{}, {"read": 0}, {"read": 0, "write": -1, "delete": 2, "emit": 8},
    {"read": 0, "write": float("nan"), "delete": 2, "emit": 8},
    {"read": 0, "write": True, "delete": 2, "emit": 8}])
def test_malformed_risk_weights_fail_closed(weights):
    with pytest.raises(ValueError):
        runtime().execute(fixture(), risk_weights=weights)


def test_supplied_missing_evidence_is_not_replaced_by_goal_probes():
    result = runtime().execute(split_goal(), authorization_evidence={}, planning_budget=512)
    assert not result["authorized_goal"] and result["charged_calls"] == 0
    assert result["audit_interpreter_calls"] == result["audit_steps"] == 0
    assert result["unresolved_gate_ids"] == ["originalread", "originalwrite"]


def test_input_immutability_and_authorization_control_v9_regression():
    from tsg.recovery_v9 import execute as previous
    case = split_goal()
    before = deepcopy(case)
    old = previous(case, planning_budget=512)
    new = runtime().execute(case, observation_mode="authorization", planning_budget=512)
    for key, value in old.items():
        assert new[key] == value, key
    assert case == before


@pytest.mark.parametrize("answer_world,mismatch", [({"files": {"flag": "yes"}, "grants": []}, False),
    ({"files": {"flag": "outside"}, "grants": []}, True)])
def test_goal_reader_unavailable_and_mismatch_preserve_proof_boundary(answer_world, mismatch):
    runtime()
    from tsg.observation_v10 import TrustedObservations, resolve_gate
    case = split_goal()
    facts = {0: {"write": "authorized"}, 1: {"write": "authorized"}}
    reader = TrustedObservations(answer_world, ["flag"] if mismatch else [], [])
    gate = resolve_gate(case["worlds"], ["write"], facts, reader, [("file", "flag")], 1,
        "conditional", "goal", lambda compatible, allowed: {0: (True, False), 1: (False, True)})
    assert gate["observation_count"] == gate["goal_observation_count"] == 1
    assert gate["observation_mismatch"] is mismatch
    assert gate["compatible_world_indices"] == ([] if mismatch else [0, 1])
    assert gate["allowed_ids"] == (set() if mismatch else {"write"})


@pytest.mark.parametrize("policy", ["calls", "priority", "risk"])
@pytest.mark.parametrize("fault", ["none", "transient_before", "known_after", "late_ambiguous",
                                    "mixed_known_then_ambiguous"])
def test_authorization_control_matches_v9_receipts_and_budget(policy, fault):
    from tsg.recovery_v9 import execute as previous
    case = fixture(program(effect("r", "read", "input", out="x", key="read"),
        effect("change", "write", "input", "new", key="change"),
        effect("finish", "write", "out", {"var": "x"})), worlds=[{
            "files": {"input": "old"},
            "grants": [["read", "input"], ["write", "input"], ["write", "out"]]}],
        goal={"files": {"input": "new", "out": "old"}})
    old = previous(case, policy, fault, planning_budget=512)
    new = runtime().execute(case, policy, fault, observation_mode="authorization", planning_budget=512)
    for key, value in old.items():
        assert new[key] == value, key


def test_explicit_gate_is_never_expanded_by_a_goal_observation():
    case = split_goal()
    result = runtime().execute(case, world_index=0, allowed_ids=[], planning_budget=512)
    assert not result["authorized_goal"] and result["charged_calls"] == 0


def test_uniform_weights_are_reflected_in_ambiguous_risk():
    case = fixture(program(effect("emit", "emit", "local", "n")),
        worlds=[{"files": {"out": "ok"}, "grants": [["emit", "local"]]}])
    result = runtime().execute(case, fault="first_emit_ambiguous",
        risk_weights={"read": 0, "write": 1, "delete": 1, "emit": 1})
    assert result["mutation_risk_score"] == result["unresolved_commit_risk"] == 1
    assert result["ambiguous_stop"] and not result["authorized_goal"]


def test_operation_fault_without_matching_operation_does_not_inject():
    result = runtime().execute(fixture(), fault="first_emit_ambiguous")
    assert result["authorized_goal"]
    assert not result["fault_diagnostics"]["fault_triggered"]
    assert not result["fault_diagnostics"]["schedule_completed"]


def test_aggregate_gate_is_not_weakened_by_goal_mode():
    case = split_goal()
    result = runtime().execute(case, gate_mode="aggregate", planning_budget=512)
    assert not result["authorized_goal"] and result["charged_calls"] == 0
    assert result["goal_observation_count"] == result["observation_count"] == 0


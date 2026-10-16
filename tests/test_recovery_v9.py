"""Hand-derived Phase 9 runtime controls, independent of held-out cases."""

from copy import deepcopy
import importlib.util
import json

import pytest


def recovery():
    assert importlib.util.find_spec("tsg.recovery_v9") is not None, "Phase 9 runtime missing"
    from tsg import recovery_v9
    return recovery_v9


def program(*steps):
    return {"version": 1, "steps": list(steps), "functions": {}}


def effect(site, op, resource, value="", **more):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **more}


def case(original=None, *, routes=(), files=None, grants=None, goal=None, worlds=None):
    original = original or program(effect("finish", "write", "out", "ok"))
    return {"source": "```tsg-workflow\n" + json.dumps(original) + "\n```",
            "program": {"private": "must never be consumed"}, "routes": list(routes),
            "worlds": worlds or [{"files": files or {},
                                   "grants": grants or [["write", "out"]]}],
            "goal": goal or {"files": {"out": "ok"}}}


def branching_case():
    return case(program(effect("read_target", "read", "target", out="dest"),
                        effect("dispatch", "write", {"var": "dest"}, "ok")),
                worlds=[{"files": {"target": dest},
                         "grants": [["read", "target"], ["write", "out"]]}
                        for dest in ["out", "secret"]])


def routes(result):
    return [row["route_index"] for row in result["attempt_log"]]


def test_trusted_observation_resolves_conditional_gate_but_preserves_global_unknown():
    fixture = branching_case()
    result = recovery().execute(fixture)
    aggregate = recovery().execute(fixture, gate_mode="aggregate")
    assert result["authorized_goal"] and result["files"]["out"] == "ok"
    assert result["global_unknown_ids"] == ["dispatch"]
    assert result["unresolved_gate_ids"] == []
    assert result["observation_count"] == 1
    assert result["observation_log"][0]["query"] == ["file", "target"]
    assert not aggregate["authorized_goal"] and aggregate["charged_calls"] == 0
    assert aggregate["observation_count"] == 0


@pytest.mark.parametrize("policy", ["priority", "calls", "risk"])
def test_hidden_worlds_have_identical_decisions_without_world_index_oracle(policy):
    fixture = branching_case()
    fixture.update(observable_files=[], observable_grants=[])
    first = recovery().execute(fixture, policy, world_index=0)
    second = recovery().execute(fixture, policy, world_index=1)
    for field in ["gate_log", "selection_log", "search_estimates", "observation_log",
                  "unresolved_gate_ids", "charged_calls", "attempt_log"]:
        assert first[field] == second[field]
    assert first["unresolved_gate_ids"] == ["dispatch"]
    assert first["charged_calls"] == second["charged_calls"] == 0
    assert not first["authorized_goal"] and not second["authorized_goal"]


def test_observation_budget_zero_cannot_resolve_unknown():
    result = recovery().execute(branching_case(), observation_budget=0)
    assert result["observation_count"] == 0 and result["unresolved_gate_ids"] == ["dispatch"]
    assert result["charged_calls"] == 0


def test_trusted_grant_observation_can_distinguish_identical_files():
    fixture = case(worlds=[{"files": {}, "grants": [["write", "out"]]},
                           {"files": {}, "grants": []}])
    fixture["observable_files"] = []
    result = recovery().execute(fixture)
    assert result["authorized_goal"] and result["observation_count"] == 1
    assert result["observation_log"][0]["query"] == ["grant", "write", "out"]
    denied = recovery().execute(fixture, world_index=1)
    assert not denied["authorized_goal"] and denied["charged_calls"] == 0


def test_preflight_prevents_original_receipt_poisoning():
    fixture = case(program(effect("poison", "emit", "local", "notice", key="shared")),
                   routes=[program(effect("finish", "write", "out", "ok", key="shared"))],
                   grants=[["emit", "local"], ["write", "out"]])
    clean = recovery().execute(fixture)
    poisoned = recovery().execute(fixture, preflight=False)
    assert clean["authorized_goal"] and routes(clean) == [1]
    assert clean["emits"] == [] and clean["charged_calls"] == 1
    assert not poisoned["authorized_goal"] and routes(poisoned) == [0]
    assert poisoned["emits"] == [{"resource": "local", "value": "notice"}]
    assert poisoned["search_estimates"][-1]["predicted_error"] == "receipt_conflict"


def test_preflight_rejects_receipt_dedup_goal_mismatch_before_any_effect():
    fixture = case(program(effect("one", "emit", "local", "n", key="same"),
                           effect("two", "emit", "local", "n", key="same")),
                   grants=[["emit", "local"]],
                   goal={"emits": [{"resource": "local", "value": "n", "count": 2}]})
    result = recovery().execute(fixture)
    assert result["charged_calls"] == 0 and result["emits"] == []
    assert result["search_estimates"][0]["predicted_error"] is None
    assert not result["search_estimates"][0]["predicted_goal"]


def test_preflight_respects_explicit_original_gate_and_alternative_grants():
    fixture = case(routes=[program(effect("bad", "write", "secret", "x")),
                           program(effect("good", "write", "out", "ok"))])
    result = recovery().execute(fixture, allowed_ids=[])
    assert result["authorized_goal"] and routes(result) == [2]
    assert result["files"] == {"out": "ok"}
    assert [row["predicted_error"] for row in result["search_estimates"]] == [
        "model_gate", "grant_denied", None]


def test_risk_can_spend_more_calls_to_avoid_emit_exposure():
    fixture = case(program(effect("notice", "emit", "local", "n"),
                           effect("finish", "write", "out", "ok")),
                   routes=[program(effect("r1", "read", "a"), effect("r2", "read", "b"),
                                   effect("safe", "write", "out", "ok"))],
                   grants=[["emit", "local"], ["write", "out"], ["read", "a"], ["read", "b"]])
    calls = recovery().execute(fixture, "calls")
    risk = recovery().execute(fixture, "risk")
    priority = recovery().execute(fixture, "priority")
    assert all(row["authorized_goal"] for row in [calls, risk, priority])
    assert routes(calls) == routes(priority) == [0] and routes(risk) == [1]
    assert calls["charged_calls"] == 2 and risk["charged_calls"] == 3
    assert risk["mutation_risk_score"] < calls["mutation_risk_score"]
    assert calls["search_estimates"] == risk["search_estimates"] == priority["search_estimates"]
    assert calls["planning_units"] == risk["planning_units"] == priority["planning_units"]


@pytest.mark.parametrize("policy", ["priority", "calls", "risk"])
@pytest.mark.parametrize("budget", [0, 1, 2, 3, 8])
def test_planning_budget_is_strict_and_never_permits_an_unchecked_route(policy, budget):
    fixture = case(routes=[program(effect("other", "write", "out", "ok"))])
    result = recovery().execute(fixture, policy, planning_budget=budget)
    assert result["planning_units"] <= budget
    if result["attempts"]:
        selected = result["attempt_log"][0]["route_index"]
        assert any(row["route_index"] == selected and row["feasible"]
                   for row in result["search_estimates"])
    assert result["planning_units"] == result["primitive_simulations"] + result["planner_steps"]


def test_equal_budget_exposes_equal_candidate_sets_before_policy_choice():
    fixture = case(routes=[program(effect("r", "read", "a"), effect("alt", "write", "out", "ok"))],
                   grants=[["write", "out"], ["read", "a"]])
    results = [recovery().execute(fixture, p, planning_budget=5)
               for p in ["priority", "calls", "risk"]]
    assert results[0]["search_estimates"] == results[1]["search_estimates"] == results[2]["search_estimates"]
    assert all(r["planning_units"] <= 5 for r in results)


@pytest.mark.parametrize("policy", ["priority", "calls", "risk"])
@pytest.mark.parametrize("fault,dispatches", [("ambiguous_after", 1),
    ("second_ambiguous_after", 2), ("late_ambiguous", 3)])
def test_unknown_commit_stops_without_retry_or_post_failure_planning(policy, fault, dispatches):
    fixture = case(program(effect("one", "write", "a", "1"),
                           effect("two", "write", "b", "2"),
                           effect("three", "write", "out", "ok")),
                   grants=[["write", "a"], ["write", "b"], ["write", "out"]])
    result = recovery().execute(fixture, policy, fault)
    assert result["ambiguous_stop"] and result["attempts"] == 1
    assert result["charged_calls"] == dispatches and len(result["selection_log"]) == 1
    assert result["unresolved_commit_count"] == 1 and result["unresolved_commit_risk"] == 1
    assert not result["authorized_goal"] and result["duplicate_effects"] == 0


def test_new_fault_adapter_does_not_modify_old_schedules():
    from tsg.recovery_v7 import FAULTS, _SCHEDULES
    before = deepcopy(_SCHEDULES)
    fixture = case(program(effect("prefix", "write", "a", "1"),
                           effect("finish", "write", "out", "ok")),
                   grants=[["write", "a"], ["write", "out"]])
    result = recovery().execute(fixture, "priority", "mixed_known_then_ambiguous")
    assert result["ambiguous_stop"] and routes(result) == [0, 0]
    assert result["receipt_reuses"] == 1 and result["charged_calls"] == 2
    assert _SCHEDULES == before and "mixed_known_then_ambiguous" not in FAULTS


def test_future_faults_do_not_change_initial_decisions():
    fixture = case(program(effect("first", "write", "a", "1"),
                           effect("last", "write", "out", "ok")),
                   grants=[["write", "a"], ["write", "out"]])
    base = recovery().execute(fixture)
    for fault in recovery().FAULTS:
        result = recovery().execute(fixture, fault=fault)
        assert result["selection_log"][0] == base["selection_log"][0]
        assert result["search_estimates"][:1] == base["search_estimates"][:1]


def test_receipts_and_quota_changes_invalidate_cached_estimate():
    result = recovery().execute(case(), "priority", "known_after", quota=1)
    assert result["authorized_goal"] and routes(result) == [0, 0]
    assert [row["remaining_calls"] for row in result["search_estimates"]] == [1, 0]
    assert result["receipt_reuses"] == 1 and result["charged_calls"] == 1
    assert all(not row["cache_hit"] for row in result["search_estimates"])


def test_cache_key_covers_state_grants_receipts_signatures_gate_quota_and_program():
    module = recovery()
    from tsg.runtime_v6 import _Machine
    probe = _Machine({"files": {"a": "1"}, "grants": [["write", "out"]]}, 16, reuse=True)
    args = [program(effect("write", "write", "out", "ok")), probe, 0,
            {"files": {"out": "ok"}}, {"write"}, 16]
    baseline = module._cache_key(*args)
    for field, changed in [("files", {"a": "2"}), ("grants", set()),
                            ("receipts", {("explicit", "x"): "1"}),
                            ("signatures", {("explicit", "x"): ("write", "out", "1")})]:
        changed_probe = deepcopy(probe)
        setattr(changed_probe, field, changed)
        modified = list(args)
        modified[1] = changed_probe
        assert module._cache_key(*modified) != baseline
    for offset, replacement in [(0, program(effect("other", "write", "out", "ok"))),
                                 (2, 1), (3, {"files": {"out": "different"}}),
                                 (4, set()), (5, 15)]:
        modified = list(args)
        modified[offset] = replacement
        assert module._cache_key(*modified) != baseline


def test_input_immutability_and_deterministic_modeled_latency():
    fixture = branching_case()
    original = deepcopy(fixture)
    one = recovery().execute(fixture)
    two = recovery().execute(fixture)
    assert fixture == original and one == two
    assert one["modeled_latency"] > 0 and one["unauthorized_effects"] == 0


@pytest.mark.parametrize("field,value", [("policy", "bad"), ("fault", "bad"),
    ("gate_mode", "bad"), ("planning_budget", -1), ("observation_budget", -1),
    ("quota", -1), ("world_index", 8), ("planning_budget", True)])
def test_invalid_controls_are_rejected(field, value):
    with pytest.raises(ValueError):
        recovery().execute(case(), **{field: value})


def test_parse_failure_never_reaches_alternatives():
    fixture = case(routes=[program(effect("other", "write", "out", "ok"))])
    fixture["source"] = "malformed"
    result = recovery().execute(fixture)
    assert result["failure_reason"] == "parse_error"
    assert result["charged_calls"] == result["planning_units"] == result["attempts"] == 0


def test_provided_evidence_is_not_completed_by_free_audits():
    fixture = branching_case()
    evidence = {"0": [{"id": "read_target", "occurred": True, "all_occurrences_authorized": True},
                       {"id": "dispatch", "occurred": True, "all_occurrences_authorized": True}]}
    result = recovery().execute(fixture, authorization_evidence=evidence)
    assert result["authorized_goal"] and result["observation_count"] == 1
    assert result["audit_interpreter_calls"] == result["audit_steps"] == 0
    fixture.update(observable_files=[], observable_grants=[])
    hidden = recovery().execute(fixture, authorization_evidence=evidence)
    assert not hidden["authorized_goal"] and hidden["charged_calls"] == 0
    assert hidden["unresolved_gate_ids"] == ["dispatch", "read_target"]
    absent = recovery().execute(case(), authorization_evidence={})
    assert not absent["authorized_goal"] and absent["unresolved_gate_ids"] == ["finish"]
    assert absent["audit_interpreter_calls"] == 0


def test_missing_site_evidence_remains_unresolved_even_in_singleton_world():
    result = recovery().execute(case(), authorization_evidence={"0": []})
    assert result["charged_calls"] == 0 and not result["authorized_goal"]
    assert result["global_unknown_ids"] == result["unresolved_gate_ids"] == ["finish"]


def test_trusted_reader_is_immutable_and_mismatches_fail_closed():
    recovery()
    from tsg.observation_v9 import TrustedObservations, resolve_gate
    actual = {"files": {"target": "unexpected"}, "grants": []}
    reader = TrustedObservations(actual, ["target"], [])
    actual["files"]["target"] = "out"
    assert reader.query(("file", "target"))["value"] == "unexpected"
    fixture = branching_case()
    gate = resolve_gate(fixture["worlds"], ["dispatch"],
        {0: {"dispatch": "authorized"}, 1: {"dispatch": "unauthorized"}},
        reader, [("file", "target")], 1, "conditional")
    assert gate["observation_mismatch"] and gate["allowed_ids"] == set()
    assert gate["compatible_world_indices"] == [] and gate["observation_count"] == 1


def test_unavailable_observation_is_charged_without_narrowing_hypotheses():
    recovery()
    from tsg.observation_v9 import TrustedObservations, resolve_gate
    fixture = branching_case()
    reader = TrustedObservations(fixture["worlds"][0], [], [])
    gate = resolve_gate(fixture["worlds"], ["dispatch"],
        {0: {"dispatch": "authorized"}, 1: {"dispatch": "unauthorized"}},
        reader, [("file", "target")], 1, "conditional")
    assert gate["observation_count"] == 1 and gate["compatible_world_indices"] == [0, 1]
    assert gate["allowed_ids"] == set() and gate["unresolved_gate_ids"] == ["dispatch"]


def test_minimal_two_observation_set_resolves_xor_permission():
    worlds = [{"files": {"a": str(a), "b": str(b)},
               "grants": [["write", "out"]] if a == b else []}
              for a, b in [(0, 0), (0, 1), (1, 0), (1, 1)]]
    fixture = case(worlds=worlds)
    fixture["observable_grants"] = []
    enough = recovery().execute(fixture, observation_budget=2)
    short = recovery().execute(fixture, observation_budget=1)
    assert enough["authorized_goal"] and enough["observation_count"] == 2
    assert not short["authorized_goal"] and short["observation_count"] == 1
    assert [row["query"] for row in enough["observation_log"]] == [["file", "a"], ["file", "b"]]


def test_cache_reuses_complete_identical_hypotheses_without_free_misses():
    fixture = case(worlds=[{"files": {}, "grants": [["write", "out"]]},
                           {"files": {}, "grants": [["write", "out"]]}])
    cached = recovery().execute(fixture, cache=True)
    uncached = recovery().execute(fixture, cache=False)
    assert cached["authorized_goal"] and uncached["authorized_goal"]
    assert cached["charged_calls"] == uncached["charged_calls"] == 1
    assert cached["cache_hits"] == 2 and uncached["cache_hits"] == 0
    assert cached["primitive_simulations"] == 2 and uncached["primitive_simulations"] == 4
    assert cached["planning_units"] == 4 and uncached["planning_units"] == 8


def test_stale_read_receipts_are_used_in_preflight_after_known_commit():
    fixture = case(program(effect("cached", "read", "input", out="value", key="read"),
                           effect("change", "write", "input", "new", key="change"),
                           effect("finish", "write", "out", {"var": "value"})),
                   files={"input": "old"}, grants=[["read", "input"], ["write", "input"], ["write", "out"]],
                   goal={"files": {"input": "new", "out": "old"}})
    result = recovery().execute(fixture, "priority", "known_after")
    assert result["authorized_goal"] and result["files"] == {"input": "new", "out": "old"}
    assert result["charged_calls"] == 3 and result["receipt_reuses"] == 2
    assert [row["remaining_calls"] for row in result["search_estimates"]] == [3, 1]


def test_trusted_read_returns_narrow_beliefs_before_recovery_selection():
    # Without observing the read return, each specialization fails in one world.
    original = program(effect("read", "read", "input", out="x"),
                       effect("prefix", "write", "prefix", "kept"),
                       effect("finish", "write", "out", {"var": "x"}))
    alternate = program({"id": "pick", "kind": "let", "name": "x", "value": "old"},
                        effect("cached_again", "read", "input", out="observed", key="cache2"),
                        {"id": "branch", "kind": "if", "eq": [{"var": "observed"}, "old"],
                         "then": [effect("fast", "write", "out", "old")], "else": []})
    fixture = case(original, routes=[alternate],
        worlds=[{"files": {"input": value}, "grants": [["read", "input"],
                 ["write", "prefix"], ["write", "out"]]} for value in ["old", "new"]],
        goal={"files": {"out": "old"}})
    fixture.update(observable_files=[], observable_grants=[])
    result = recovery().execute(fixture, "calls", "known_after", preflight=False)
    assert result["authorized_goal"] and result["search_estimates"][0]["hypothesis_count"] == 1


def test_four_attempt_bound_remains_after_repeated_safe_failures(monkeypatch):
    module = recovery()
    monkeypatch.setitem(module.FAULT_SHIFTS, "persistent_safe", {i: "transient_before" for i in range(1, 8)})
    monkeypatch.setattr(module, "FAULTS", (*module.FAULTS, "persistent_safe"))
    result = module.execute(case(), "priority", "persistent_safe")
    assert result["attempts"] == 4 and result["charged_calls"] == 4
    assert result["failure_reason"] == "transient_before"
    assert len(result["selection_log"]) == 4 and result["duplicate_effects"] == 0


def test_incomplete_semantic_audit_cannot_prove_all_future_occurrences_authorized():
    # A bounded audit sees only the authorized iterations before it stops.
    steps = [effect("first", "write", "out", "ok")]
    steps.extend({"id": "noop" + str(i), "kind": "let", "name": "x", "value": "x"} for i in range(101))
    fixture = case(program(*steps))
    result = recovery().execute(fixture, planning_budget=500, preflight=False)
    assert result["unresolved_gate_ids"] == ["first"]
    assert result["files"] == {} and result["trace"][0]["status"] == "model_gate"


def test_global_typed_unknown_survives_safe_authorized_inactive_mixture():
    original = program(effect("read", "read", "flag", out="flag"),
        {"id": "branch", "kind": "if", "eq": [{"var": "flag"}, "yes"],
         "then": [effect("optional", "write", "side", "ok")], "else": []},
        effect("finish", "write", "out", "ok"))
    fixture = case(original, worlds=[{"files": {"flag": flag}, "grants": [
        ["read", "flag"], ["write", "side"], ["write", "out"]]} for flag in ["yes", "no"]])
    fixture.update(observable_files=[], observable_grants=[])
    conditional = recovery().execute(fixture, gate_mode="conditional")
    aggregate = recovery().execute(fixture, gate_mode="aggregate")
    assert conditional["authorized_goal"] and conditional["observation_count"] == 0
    assert conditional["global_unknown_ids"] == ["optional"]
    assert conditional["unresolved_gate_ids"] == []
    assert not aggregate["authorized_goal"] and aggregate["charged_calls"] == 0


@pytest.mark.parametrize("limit,want", [(100, 0), (101, 101), (102, 101)])
def test_step_limit_reservation_covers_full_actual_interpreter_cost(limit, want):
    steps = [{"id": "n" + str(i), "kind": "let", "name": "x", "value": "x"} for i in range(103)]
    result = recovery().execute(case(program(*steps)), planning_budget=limit)
    assert result["planning_units"] == want and result["planning_units"] <= limit
    assert result["audit_steps"] == (100 if want else 0)
    assert result["attempts"] == 0

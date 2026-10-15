"""Hand-checked recovery controls; only the old development data is loaded."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from tsg.selection_v6 import execute_selection


SELECTORS = ["first_feasible", "search_equal"]
OLD_FAULTS = ["none", "transient_before", "known_after", "ambiguous_after"]


@pytest.fixture
def recovery():
    assert importlib.util.find_spec("tsg.recovery_v7") is not None, "Phase 7 recovery is missing"
    from tsg import recovery_v7
    return recovery_v7


def program(steps):
    return {"version": 1, "steps": steps, "functions": {}}


def effect(site, op, resource, value="", **more):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **more}


def case(original=None, *, routes=None, grants=None, files=None, goal=None):
    original = original if original is not None else program([
        effect("blocked", "write", "secret", "no")])
    return {"source": "```tsg-workflow\n" + json.dumps(original) + "\n```",
            "program": {"untrusted": "not used"}, "routes": routes or [],
            "worlds": [{"files": files or {},
                        "grants": grants if grants is not None else [["write", "out"]]}],
            "goal": goal if goal is not None else {"files": {"out": "ok"}}}


def attempts(result):
    return [entry["route_index"] for entry in result["attempt_log"]]


@pytest.mark.parametrize("selector", SELECTORS)
@pytest.mark.parametrize("fault", OLD_FAULTS)
def test_legacy_matches_every_old_development_world_field_for_field(recovery, selector, fault):
    path = Path(__file__).resolve().parents[1] / "data" / "phase6" / "dev.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    # Include parse failures and invalid catalog members in the compatibility boundary.
    cases += [case(routes=[{"bad": "route"}, program([effect("ok", "write", "out", "ok")])]),
              {**case(), "source": "unsupported"}]
    for fixture in cases:
        for world_index in range(len(fixture["worlds"])):
            for quota in (0, 1, 2, 8, 16):
                for allowed in (None, []):
                    old = execute_selection(fixture, selector, fault, allowed, world_index, quota)
                    new = recovery.execute(fixture, selector, "legacy", fault, allowed, world_index, quota)
                    assert {key: value for key, value in new.items() if key != "fault_diagnostics"} == old


@pytest.mark.parametrize("selector", SELECTORS)
@pytest.mark.parametrize("fault,want_attempts,want_calls", [
    ("transient_before", 3, 3), ("known_after", 3, 2), ("double_transient_before", 4, 4)])
def test_safe_retry_restores_the_only_legal_alternative(recovery, selector, fault, want_attempts, want_calls):
    fixture = case(routes=[program([effect("finish", "write", "out", "ok")])])
    old = recovery.execute(fixture, selector, "legacy", fault)
    new = recovery.execute(fixture, selector, "safe_retry", fault)
    assert not old["authorized_goal"]
    assert new["authorized_goal"] and new["files"] == {"out": "ok"}
    assert attempts(new) == [0] + [1] * (want_attempts - 1)
    assert new["charged_calls"] == want_calls
    assert new["routes_considered"] == new["planner_steps"] == 1
    assert new["duplicate_effects"] == new["unauthorized_effects"] == 0


@pytest.mark.parametrize("selector", SELECTORS)
def test_known_permanent_failure_is_retired_after_one_attempt(recovery, selector):
    result = recovery.execute(case(), selector, "safe_retry")
    assert attempts(result) == [0]
    assert result["attempt_log"][0]["failure_reason"] == "grant_denied"
    assert result["failure_reason"] == "no_feasible_route"
    assert result["charged_calls"] == 1 and result["files"] == {}


def test_a_safe_retry_that_reveals_permanent_failure_does_not_loop(recovery):
    original = program([effect("prefix", "write", "prefix", "kept"),
                        {"id": "fail", "kind": "let", "name": "x", "value": {"var": "absent"}}])
    fixture = case(original, routes=[program([effect("finish", "write", "out", "ok")])],
                   grants=[["write", "prefix"], ["write", "out"]])
    result = recovery.execute(fixture, "search_equal", "safe_retry", "known_after")
    assert attempts(result) == [0, 0, 1]
    assert [row["failure_reason"] for row in result["attempt_log"]] == ["known_after", "unbound_variable", None]
    assert result["authorized_goal"] and result["receipt_reuses"] == 1
    assert result["files"] == {"prefix": "kept", "out": "ok"}


@pytest.mark.parametrize("policy", ["legacy", "safe_retry"])
@pytest.mark.parametrize("fault,count", [("ambiguous_after", 1), ("second_ambiguous_after", 2)])
def test_unknown_commit_always_stops_before_planning_or_retry(recovery, policy, fault, count):
    original = program([effect("one", "emit", "local", "one"), effect("two", "emit", "local", "two")])
    fixture = case(original, routes=[program([effect("finish", "write", "out", "ok")])],
                   grants=[["emit", "local"], ["write", "out"]],
                   goal={"emits": [{"resource": "local", "value": "one", "count": 1}]})
    result = recovery.execute(fixture, "search_equal", policy, fault)
    assert result["ambiguous_stop"] and result["failure_reason"] == "ambiguous_outcome"
    assert result["attempts"] == 1 and len(result["emits"]) == count
    assert result["charged_calls"] == count and result["planner_steps"] == 0
    assert not result["authorized_goal"] and result["duplicate_effects"] == 0


@pytest.mark.parametrize("fault,status,dispatches", [
    ("second_transient_before", "transient_before", 3),
    ("second_known_after", "known_after", 2)])
def test_delayed_fault_counts_dynamic_mutations_not_static_sites_or_reads(recovery, fault, status, dispatches):
    original = program([effect("read", "read", "input"),
                        {"id": "loop", "kind": "repeat", "count": 2,
                         "body": [effect("emit", "emit", "local", "once")]}])
    fixture = case(original, grants=[["read", "input"], ["emit", "local"]],
                   goal={"emits": [{"resource": "local", "value": "once", "count": 2}]})
    result = recovery.execute(fixture, "first_feasible", "safe_retry", fault)
    assert result["authorized_goal"] and attempts(result) == [0, 0]
    assert [row["status"] for row in result["trace"][:3]] == ["committed", "committed", status]
    diagnostics = result["fault_diagnostics"]
    assert diagnostics["eligible_mutation_dispatches"] == dispatches
    assert diagnostics["injections"][0]["dispatch"] == 2
    assert result["emits"] == [{"resource": "local", "value": "once"}] * 2
    assert result["duplicate_effects"] == 0


def test_conflicts_receipt_reuse_and_reads_do_not_advance_fault_schedule(recovery):
    original = program([effect("prefix", "write", "prefix", "kept", key="shared"),
                        effect("conflict", "write", "prefix", "changed", key="shared")])
    route = program([effect("same", "write", "prefix", "kept", key="shared"),
                     effect("read", "read", "input"), effect("finish", "write", "out", "ok")])
    fixture = case(original, routes=[route], grants=[["write", "prefix"], ["read", "input"], ["write", "out"]])
    result = recovery.execute(fixture, "search_equal", "safe_retry", "second_known_after")
    assert result["authorized_goal"] and attempts(result) == [0, 1, 1]
    assert result["attempt_log"][0]["failure_reason"] == "receipt_conflict"
    assert result["fault_diagnostics"]["eligible_mutation_dispatches"] == 2
    assert result["fault_diagnostics"]["injections"] == [
        {"dispatch": 2, "fault": "known_after", "attempt": 2, "route_index": 1, "id": "finish"}]
    assert result["files"] == {"prefix": "kept", "out": "ok"}
    assert result["duplicate_effects"] == result["unauthorized_effects"] == 0


def test_untriggered_delayed_fault_is_explicit(recovery):
    fixture = case(program([effect("only", "write", "out", "ok")]))
    result = recovery.execute(fixture, "first_feasible", "safe_retry", "second_transient_before")
    assert result["authorized_goal"]
    assert result["fault_diagnostics"] == {
        "fault": "second_transient_before", "eligible_mutation_dispatches": 1,
        "scheduled_fault_count": 1, "injected_fault_count": 0,
        "fault_triggered": False, "schedule_completed": False, "injections": []}


@pytest.mark.parametrize("fault,success,calls,reuses,reason", [
    ("known_after", True, 1, 1, None),
    ("transient_before", False, 1, 0, "quota_exhausted"),
    ("double_transient_before", False, 1, 0, "quota_exhausted")])
def test_shared_quota_allows_receipt_only_retry_but_no_free_dispatch(recovery, fault, success, calls, reuses, reason):
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = recovery.execute(fixture, "search_equal", "safe_retry", fault, quota=1)
    assert result["authorized_goal"] is success
    assert result["charged_calls"] == calls and result["remaining_quota"] == 0
    assert result["receipt_reuses"] == reuses and result["failure_reason"] == reason
    assert result["fault_diagnostics"]["eligible_mutation_dispatches"] == 1
    assert result["duplicate_effects"] == 0


def test_zero_quota_cannot_trigger_or_commit_a_faulted_mutation(recovery):
    fixture = case(program([effect("finish", "write", "out", "ok")]))
    result = recovery.execute(fixture, "first_feasible", "safe_retry", "known_after", quota=0)
    assert result["charged_calls"] == 0 and result["files"] == {}
    assert result["failure_reason"] == "quota_exhausted" and result["attempts"] == 1
    assert result["fault_diagnostics"]["eligible_mutation_dispatches"] == 0
    assert not result["fault_diagnostics"]["fault_triggered"]


def test_no_receipt_clearing_to_make_an_otherwise_stale_route_succeed(recovery):
    original = program([effect("read", "read", "input", out="old", key="cached"),
                        effect("blocked", "write", "secret", "no")])
    route = program([effect("update", "write", "input", "new"),
                     effect("read_again", "read", "input", out="text", key="cached"),
                     effect("finish", "write", "out", {"var": "text"})])
    fixture = case(original, routes=[route], files={"input": "old"},
                   grants=[["read", "input"], ["write", "input"], ["write", "out"]],
                   goal={"files": {"out": "new"}})
    result = recovery.execute(fixture, "search_equal", "safe_retry")
    assert not result["authorized_goal"] and attempts(result) == [0]
    assert result["failure_reason"] == "no_feasible_route"
    assert result["search_estimates"][0]["predicted_goal"] is False
    assert result["files"] == {"input": "old"}


def test_selectors_do_equal_planning_then_choose_by_order_or_remaining_calls(recovery):
    routes = [program([effect("noise", "emit", "local", "unused"), effect("slow", "write", "out", "ok")]),
              program([effect("fast", "write", "out", "ok")])]
    fixture = case(routes=routes, grants=[["emit", "local"], ["write", "out"]])
    first = recovery.execute(fixture, "first_feasible", "safe_retry")
    search = recovery.execute(fixture, "search_equal", "safe_retry")
    assert first["authorized_goal"] and search["authorized_goal"]
    assert attempts(first) == [0, 1] and attempts(search) == [0, 2]
    assert first["search_estimates"] == search["search_estimates"]
    assert first["planner_steps"] == search["planner_steps"] == 3
    assert first["charged_calls"] == 3 and search["charged_calls"] == 2
    assert search["emits"] == []


@pytest.mark.parametrize("selector", SELECTORS)
def test_future_fault_schedule_does_not_change_initial_route_selection(recovery, selector):
    routes = [program([effect("read", "read", "input"), effect("slow", "write", "out", "ok")]),
              program([effect("fast", "write", "out", "ok")])]
    fixture = case(routes=routes, grants=[["read", "input"], ["write", "out"]])
    baseline = recovery.execute(fixture, selector, "safe_retry")
    for fault in recovery.FAULTS:
        result = recovery.execute(fixture, selector, "safe_retry", fault)
        assert result["selection_log"][0] == baseline["selection_log"][0]
        assert result["search_estimates"][:2] == baseline["search_estimates"]


def test_gate_denials_do_not_count_as_eligible_and_do_not_grant_alternative_authority(recovery):
    original = program([effect("original", "write", "out", "ok")])
    routes = [program([effect("bad", "write", "secret", "no")]),
              program([effect("legal", "write", "out", "ok")])]
    result = recovery.execute(case(original, routes=routes), "search_equal", "safe_retry", "known_after", [])
    assert attempts(result) == [0, 2, 2] and result["authorized_goal"] and result["route_bypass"]
    assert result["attempt_log"][0]["failure_reason"] == "model_gate"
    assert [row["feasible"] for row in result["search_estimates"]] == [False, True]
    assert result["fault_diagnostics"]["injections"][0]["dispatch"] == 1
    assert result["files"] == {"out": "ok"} and result["unauthorized_effects"] == 0


def test_inputs_and_private_metadata_cannot_influence_recovery(recovery):
    fixture = case(routes=[program([effect("finish", "write", "out", "ok")])])
    before = deepcopy(fixture)
    baseline = recovery.execute(fixture, "search_equal", "safe_retry", "double_transient_before")
    assert fixture == before
    fixture.update(program=None, truth={"goal": False}, case_id="different", family="different")
    assert recovery.execute(fixture, "search_equal", "safe_retry", "double_transient_before") == baseline


@pytest.mark.parametrize("changes", [
    {"selector": "bad"}, {"policy": "bad"}, {"fault": "bad"}, {"quota": -1},
    {"quota": True}, {"world_index": True}, {"world_index": 1}])
def test_invalid_execution_options_fail_closed(recovery, changes):
    arguments = {"selector": "first_feasible", "policy": "safe_retry", **changes}
    with pytest.raises(ValueError):
        recovery.execute(case(), **arguments)

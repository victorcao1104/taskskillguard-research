"""Hand-derived synthetic tests; no heldout cases or reference generator."""
import json
import pytest

from tsg.commit_v11 import execute_certified, _StatusService
from tsg.runtime_v6 import _Machine, parse_source


def case(steps=None):
    steps = steps or [
        {"id": "r", "kind": "effect", "op": "read", "resource": "in", "out": "v"},
        {"id": "w", "kind": "effect", "op": "write", "resource": "in", "value": "changed"},
        {"id": "e", "kind": "effect", "op": "emit", "resource": "out", "value": {"var": "v"}},
    ]
    program = {"version": 1, "steps": steps}
    return {"source": "```tsg-workflow\n" + json.dumps(program) + "\n```",
            "routes": [], "worlds": [{"files": {"in": "initial"}, "grants":
            [["read", "in"], ["write", "in"], ["emit", "out"]]}],
            "goal": {"files": {"in": "changed"}, "emits":
                     [{"resource": "out", "value": "initial", "count": 1}]}}


@pytest.mark.parametrize("fault", ["ambiguous_after", "terminal_noncommit", "second_ambiguous_after", "emit_ambiguous_after"])
def test_terminal_evidence_recovers_exact_route_and_original_read_snapshot(fault):
    got = execute_certified(case(), 0, fault=fault, policy="terminal_status")
    assert got["authorized_goal"]
    assert got["emits"] == [{"resource": "out", "value": "initial"}]
    assert got["duplicate_effects"] == got["unauthorized_effects"] == 0
    assert got["attempts"] == 2
    assert got["status_calls"] == 1
    assert got["charged_calls"] == got["effect_calls"] + 1
    assert {x["route_index"] for x in got["attempt_log"]} == {0}


def test_strict_stop_does_not_read_commit_bit():
    committed = execute_certified(case(), 0, fault="ambiguous_after")
    fenced = execute_certified(case(), 0, fault="terminal_noncommit")
    assert committed["controller_trace"] == fenced["controller_trace"]
    assert committed["files"]["in"] == "changed"
    assert fenced["files"]["in"] == "initial"
    assert committed["status_calls"] == fenced["status_calls"] == 0
    assert committed["failure_reason"] == fenced["failure_reason"] == "ambiguous_outcome"


@pytest.mark.parametrize("fault", ["pending", "unavailable", "absent", "stale", "wrong_signature", "wrong_operation", "wrong_epoch", "forged", "retention_expired", "contradictory", "pending_absent"])
def test_nonterminal_or_invalid_status_never_authorizes_retry(fault):
    got = execute_certified(case(), 0, fault=fault, policy="terminal_status")
    assert not got["authorized_goal"]
    assert got["attempts"] == 1
    assert got["duplicate_effects"] == 0
    assert got["status_calls"] == 1


def test_status_query_consumes_shared_quota_and_separate_budget():
    for options, why in [({"quota": 2}, "quota_exhausted"), ({"status_budget": 0}, "status_budget_exhausted")]:
        got = execute_certified(case(), 0, fault="ambiguous_after", policy="terminal_status", **options)
        assert got["status_calls"] == 0
        assert got["failure_reason"] == why
        assert got["attempts"] == 1
    got = execute_certified(case(), 0, fault="ambiguous_after", policy="terminal_status", quota=3)
    assert got["status_calls"] == 1
    assert got["charged_calls"] == 3
    assert got["failure_reason"] == "quota_exhausted"


def test_same_id_durable_dedup_control_needs_no_status_call():
    got = execute_certified(case(), 0, fault="ambiguous_after", policy="same_id_dedup")
    assert got["authorized_goal"] and got["duplicate_effects"] == 0
    assert got["status_calls"] == 0
    assert got["effect_calls"] == 4


def test_pending_does_not_commit_but_absence_retry_can_duplicate():
    safe = execute_certified(case(), 0, fault="pending_absent", policy="terminal_status")
    unsafe = execute_certified(case(), 0, fault="pending_absent", policy="unsafe_absence_retry")
    assert safe["files"]["in"] == "initial"
    assert safe["fault_diagnostics"]["pending_operations"] == 1
    assert unsafe["duplicate_effects"] == 1
    assert unsafe["fault_diagnostics"]["pending_operations"] == 0
    assert "non-idempotent" in unsafe["trust_model"]


def test_repeated_key_payload_conflict_stops_even_with_receipt():
    data = case([
        {"id": "a", "kind": "effect", "op": "write", "resource": "in", "value": "one", "key": "k"},
        {"id": "b", "kind": "effect", "op": "write", "resource": "in", "value": "two", "key": "k"},
    ])
    got = execute_certified(data, 0)
    assert got["failure_reason"] == "receipt_conflict"
    assert got["files"]["in"] == "one"


def test_no_hidden_route_repair_and_denied_effect_never_commits():
    data = case()
    data["worlds"][0]["grants"].remove(["write", "in"])
    data["routes"] = [{"version": 1, "steps": []}]
    got = execute_certified(data, 0, policy="terminal_status")
    assert got["failure_reason"] == "grant_denied"
    assert got["files"]["in"] == "initial"
    assert got["attempts"] == 1
    assert got["unauthorized_effects"] == 0


def test_chosen_alternative_is_only_program_executed_and_results_deterministic():
    data = case()
    data["routes"] = [{"version": 1, "steps": []}]
    one = execute_certified(data, 1)
    assert one == execute_certified(data, 1)
    assert one["effect_calls"] == 0
    assert one["failure_reason"] == "goal_unmet"


@pytest.mark.parametrize("fault", ["unavailable", "absent", "wrong_signature", "forged"])
def test_same_id_control_recovers_using_dedup_even_when_status_would_be_bad(fault):
    got = execute_certified(case(), 0, fault=fault, policy="same_id_dedup", status_budget=0)
    assert got["authorized_goal"]
    assert got["duplicate_effects"] == got["status_calls"] == 0


def test_same_id_control_cannot_reexecute_inflight_operation_or_exceed_quota():
    pending = execute_certified(case(), 0, fault="pending", policy="same_id_dedup")
    assert pending["failure_reason"] == "pending"
    assert pending["files"]["in"] == "initial"
    assert pending["duplicate_effects"] == 0
    exhausted = execute_certified(case(), 0, fault="unavailable", policy="same_id_dedup", quota=2)
    assert exhausted["failure_reason"] == "quota_exhausted"
    assert exhausted["effect_calls"] == 2
    assert exhausted["status_calls"] == 0


def test_terminal_noncommit_fences_late_old_attempt_and_does_not_imply_success():
    service = _StatusService(case()["worlds"][0], 32, 1, "terminal_noncommit", "epoch", False)
    binding = {"operation_id": "old", "epoch": "epoch", "policy_context": service.context,
               "signature": ["write", "in", "changed"]}
    key = ("explicit", "k")
    assert service.dispatch(binding, key) == {"error": "ambiguous_outcome"}
    packet = service.query(binding)["status"]
    assert service.verify(packet, binding, {"terminal_noncommit"})
    assert service.files["in"] == "initial"
    assert service.dispatch(binding, key) == {"error": "fenced_operation"}
    assert service.files["in"] == "initial"
    assert sum(service.commits.values()) == 0


def test_modified_signed_receipt_cannot_be_imported_as_committed():
    service = _StatusService(case()["worlds"][0], 32, 1, "pending", "epoch", False)
    binding = {"operation_id": "old", "epoch": "epoch", "policy_context": service.context,
               "signature": ["write", "in", "changed"]}
    service.dispatch(binding, ("explicit", "k"))
    packet = service.query(binding)["status"]
    packet["body"]["outcome"] = "committed"
    packet["body"]["receipt"] = ""
    assert not service.verify(packet, binding, {"committed"})
    assert service.files["in"] == "initial"


@pytest.mark.parametrize("quota", range(6))
def test_faultfree_preserves_frozen_guarded_execution_with_shared_quota(quota):
    data = case()
    old = _Machine(data["worlds"][0], quota, reuse=True)
    error = old.run(parse_source(data["source"]))
    got = execute_certified(data, 0, quota=quota)
    assert got["files"] == old.files
    assert got["emits"] == old.emits
    assert got["effect_calls"] == old.charged
    assert got["receipt_reuses"] == old.reuses
    assert got["failure_reason"] == error


@pytest.mark.parametrize("fault", ["second_terminal_noncommit", "emit_terminal_noncommit", "second_wrong_signature", "emit_wrong_epoch"])
def test_later_fault_targets_keep_first_mutation_receipt(fault):
    got = execute_certified(case(), 0, fault=fault, policy="terminal_status")
    assert got["fault_diagnostics"]["fault_triggered"]
    assert got["files"]["in"] == "changed"
    assert got["duplicate_effects"] == 0
    assert got["authorized_goal"] == fault.endswith("terminal_noncommit")


def test_unreachable_fault_target_is_reported_without_invented_status_calls():
    data = case([{"id": "w", "kind": "effect", "op": "write", "resource": "in", "value": "changed"}])
    data["goal"] = {"files": {"in": "changed"}}
    got = execute_certified(data, 0, fault="second_ambiguous_after", policy="terminal_status")
    assert got["authorized_goal"]
    assert not got["fault_diagnostics"]["fault_triggered"]
    assert got["status_calls"] == 0

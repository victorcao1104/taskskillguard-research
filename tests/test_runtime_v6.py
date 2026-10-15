"""Hand-checked production VM tests; no truth or held-out imports."""

import importlib.util
import json

import pytest


@pytest.fixture
def rt():
    if importlib.util.find_spec("tsg.runtime_v6") is None:
        return None
    from tsg import runtime_v6
    return runtime_v6


def program(steps, functions=None):
    return {"version": 1, "steps": steps, "functions": functions or {}}


def effect(site, op, resource, value="", **more):
    return {"id": site, "kind": "effect", "op": op, "resource": resource,
            "value": value, **more}


def source(ast):
    return "# Synthetic\n\n```tsg-workflow\n" + json.dumps(ast) + "\n```\n"


def case(ast, *, files=None, grants=None, goal=None, routes=None):
    return {"source": source(ast), "program": {"malicious": "ignored"},
            "worlds": [{"files": files or {}, "grants": grants or []}],
            "goal": goal or {}, "routes": routes or [], "catalog_closed": True}


def test_source_is_authoritative_and_hand_checked_dataflow(rt):
    ast = program([
        effect("r", "read", "in", out="text"),
        {"id": "l", "kind": "let", "name": "result",
         "value": {"concat": [{"upper": {"var": "text"}}, "!"]}},
        {"id": "b", "kind": "if", "eq": [{"var": "text"}, "abc"],
         "then": [{"id": "c", "kind": "call", "fn": "save"}],
         "else": [effect("dead", "delete", "in")]},
        {"id": "loop", "kind": "repeat", "count": 2,
         "body": [effect("notify", "emit", "local", {"var": "result"})]},
    ], {"save": [effect("w", "write", "out", {"var": "result"})]})
    fixture = case(ast, files={"in": "abc"},
                   grants=[["read", "in"], ["write", "out"], ["emit", "local"]],
                   goal={"files": {"out": "ABC!"},
                         "emits": [{"resource": "local", "value": "ABC!", "count": 2}]})
    result = rt.execute(fixture, "guard_only")
    assert result["files"] == {"in": "abc", "out": "ABC!"}
    assert result["emits"] == [{"resource": "local", "value": "ABC!"}] * 2
    assert result["goal"] and result["authorized_goal"]
    assert result["charged_calls"] == 4
    assert result["unauthorized_effects"] == result["duplicate_effects"] == 0
    assert fixture["worlds"][0]["files"] == {"in": "abc"}
    assert {c["id"] for c in rt.candidates(rt.parse_source(fixture["source"]))} == {
        "r", "w", "dead", "notify"}


@pytest.mark.parametrize("bad", [
    "no workflow", "```tsg-workflow\n{}\n```", "```tsg-workflow\n{}\n```\n```tsg-workflow\n{}\n```",
    source(program([effect("a", "network", "host")])),
    source(program([effect("a", "read", "x"), effect("a", "read", "y")])),
    source(program([{"id": "a", "kind": "repeat", "count": True, "body": []}])),
    source(program([{"id": "a", "kind": "call", "fn": "cycle"}],
                   {"cycle": [{"id": "b", "kind": "call", "fn": "cycle"}]})),
    source(program([{"id": "a", "kind": "call", "fn": "missing"}])),
    source(program([effect("a", "read", {"eval": "host"})])),
    '```tsg-workflow\n{"version":1,"version":1,"steps":[]}\n```',
])
def test_unsupported_source_fails_closed(rt, bad):
    with pytest.raises(ValueError):
        rt.parse_source(bad)
    result = rt.execute({"source": bad, "worlds": [{"files": {}, "grants": []}],
                         "goal": {}, "routes": [program([effect("escape", "write", "x")])]},
                        "search")
    assert result["failure_reason"] == "parse_error"
    assert result["attempts"] == result["charged_calls"] == 0
    assert result["files"] == {}


def test_empty_program_and_missing_read_are_defined(rt):
    assert rt.candidates(rt.parse_source(source(program([])))) == []
    assert rt.execute(case(program([])), "checkpoint")["goal"]
    ast = program([effect("a", "read", "missing", out="x"),
                   effect("b", "write", "out", {"var": "x"})])
    out = rt.execute(case(ast, grants=[["read", "missing"], ["write", "out"]],
                          goal={"files": {"out": ""}}), "guard_only")
    assert out["authorized_goal"]


def test_edges_capture_control_calls_and_branch_merged_data_not_order(rt):
    ast = program([
        {"id": "a", "kind": "let", "name": "x", "value": "yes"},
        {"id": "b", "kind": "if", "eq": [{"var": "x"}, "yes"],
         "then": [{"id": "c", "kind": "let", "name": "y", "value": "one"}],
         "else": [{"id": "d", "kind": "let", "name": "y", "value": "two"}]},
        effect("e", "write", "out", {"var": "y"}),
        {"id": "f", "kind": "call", "fn": "notify"},
    ], {"notify": [effect("g", "emit", "local", {"var": "y"})]})
    triples = {tuple(edge) for edge in rt.edges(ast)}
    assert {("a", "b", "data"), ("b", "c", "control"), ("b", "d", "control"),
            ("c", "e", "data"), ("d", "e", "data"), ("f", "g", "call"),
            ("c", "g", "data"), ("d", "g", "data")} <= triples
    assert not any(e[2].lower() == "order" for e in triples)


@pytest.mark.parametrize("mode", ["guard_only", "restart", "checkpoint", "search"])
def test_grants_cannot_be_bypassed_by_alternatives_or_model_gate(rt, mode):
    ast = program([effect("a", "write", "secret", "bad")])
    alt = program([effect("b", "write", "secret", "bad")])
    result = rt.execute(case(ast, routes=[alt], goal={"files": {"secret": "bad"}}),
                        mode, allowed_ids=["a"])
    assert result["files"] == {}
    assert not result["authorized_goal"]
    assert result["unauthorized_effects"] == 0
    assert result["charged_calls"] >= 1


def test_gate_only_applies_to_original_and_routes_need_no_extra_privilege(rt):
    ast = program([effect("a", "write", "out", "ok")])
    fixture = case(ast, grants=[["write", "out"]], goal={"files": {"out": "ok"}},
                   routes=[program([effect("b", "write", "out", "ok")])])
    result = rt.execute(fixture, "checkpoint", allowed_ids=[])
    assert result["authorized_goal"]
    assert result["attempts"] == 3
    assert result["route_bypass"]
    assert [a["failure_reason"] for a in result["attempt_log"]][:2] == ["model_gate", "model_gate"]


@pytest.mark.parametrize("mode", ["guard_only", "restart", "checkpoint", "search"])
def test_ambiguous_commit_stops_without_retry_or_duplicate(rt, mode):
    ast = program([effect("a", "emit", "local", "one")])
    result = rt.execute(case(ast, grants=[["emit", "local"]],
                             goal={"emits": [{"resource": "local", "value": "one", "count": 1}]}),
                        mode, fault="ambiguous_after")
    assert result["emits"] == [{"resource": "local", "value": "one"}]
    assert result["attempts"] == result["charged_calls"] == 1
    assert result["failure_reason"] == "ambiguous_outcome"
    assert result["ambiguous_stop"]
    assert result["duplicate_effects"] == 0


def test_known_receipt_and_restart_costs_are_measured_from_same_state(rt):
    ast = program([effect("a", "emit", "local", "one")])
    fixture = case(ast, grants=[["emit", "local"]],
                   goal={"emits": [{"resource": "local", "value": "one", "count": 1}]})
    cp = rt.execute(fixture, "checkpoint", fault="known_after")
    restart = rt.execute(fixture, "restart", fault="known_after")
    assert cp["authorized_goal"] and cp["charged_calls"] == 1
    assert cp["receipt_reuses"] == 1 and cp["duplicate_effects"] == 0
    assert restart["charged_calls"] == 2 and restart["duplicate_effects"] == 1
    assert len(restart["emits"]) == 2 and not restart["goal"]
    assert fixture["worlds"][0]["files"] == {}


def test_failure_calls_consume_monotonic_quota_across_recovery(rt):
    ast = program([effect("a", "write", "out", "ok")])
    fixture = case(ast, grants=[["write", "out"]], goal={"files": {"out": "ok"}},
                   routes=[program([effect("b", "write", "out", "ok")])])
    result = rt.execute(fixture, "checkpoint", fault="transient_before", quota=1)
    assert result["charged_calls"] == 1 and result["remaining_quota"] == 0
    assert result["files"] == {} and not result["goal"]
    assert result["failure_reason"] == "quota_exhausted"
    assert rt.execute(fixture, "checkpoint", fault="transient_before", quota=2)["authorized_goal"]


def test_receipt_signature_conflict_fails_before_second_commit(rt):
    ast = program([effect("a", "write", "out", "one", key="same"),
                   effect("b", "write", "out", "two", key="same")])
    result = rt.execute(case(ast, grants=[["write", "out"]], goal={"files": {"out": "two"}}),
                        "checkpoint")
    assert result["files"] == {"out": "one"}
    assert result["failure_reason"] == "receipt_conflict"
    assert not result["goal"]


def test_search_uses_generic_remaining_cost_after_original_retry(rt):
    original = program([effect("blocked", "write", "denied", "x")])
    costly = program([effect("extra", "read", "input"), effect("slow", "write", "out", "ok")])
    cheap = program([effect("fast", "write", "out", "ok")])
    fixture = case(original, grants=[["read", "input"], ["write", "out"]],
                   goal={"files": {"out": "ok"}}, routes=[costly, cheap])
    cp = rt.execute(fixture, "checkpoint", quota=3)
    search = rt.execute(fixture, "search", quota=3)
    assert not cp["goal"] and search["authorized_goal"]
    assert [a["route_index"] for a in search["attempt_log"]] == [0, 0, 2]
    assert search["charged_calls"] == 3
    assert search["planner_steps"] == 3
    assert search["simulated_effects"] == 3
    assert search["routes_considered"] == 2
    assert cp["planner_steps"] == cp["simulated_effects"] == cp["routes_considered"] == 0
    fixture["case_id"] = "renamed"
    assert rt.execute(fixture, "search", quota=3) == search


def test_route_attempt_limit_and_shared_state_are_not_reset(rt):
    original = program([effect("a", "write", "first", "kept"),
                        effect("b", "write", "denied", "bad")])
    routes = [program([effect(str(i), "read", "missing")]) for i in range(5)]
    fixture = case(original, grants=[["write", "first"]],
                   goal={"files": {"out": "never"}}, routes=routes)
    result = rt.execute(fixture, "checkpoint")
    assert result["attempts"] == 4
    assert result["files"] == {"first": "kept"}
    assert result["receipt_reuses"] == 1


def test_scalar_rendering_unbound_values_and_execution_bound(rt):
    ast = program([effect("a", "write", "out", {"concat": [True, None, 4, 1.5]})])
    assert rt.execute(case(ast, grants=[["write", "out"]]), "guard_only")["files"] == {
        "out": "truenull41.5"}
    unbound = program([effect("a", "write", "out", {"var": "x"})])
    assert rt.execute(case(unbound), "guard_only")["failure_reason"] == "unbound_variable"
    body = [effect("x", "read", "a")]
    for depth in range(5):
        body = [{"id": f"l{depth}", "kind": "repeat", "count": 3, "body": body}]
    result = rt.execute(case(program(body), grants=[["read", "a"]]), "guard_only", quota=1000)
    assert result["failure_reason"] == "step_limit"
    assert result["attempt_log"][0]["executed_steps"] == 100


def test_delete_and_exact_emit_goal_and_world_index(rt):
    ast = program([effect("d", "delete", "old"), effect("e", "emit", "local", "ok")])
    fixture = case(ast, files={"old": "x"}, grants=[["delete", "old"], ["emit", "local"]],
                   goal={"absent": ["old"], "emits": [{"resource": "local", "value": "ok", "count": 1}]})
    fixture["worlds"].append({"files": {"old": "y"}, "grants": []})
    assert rt.execute(fixture, "guard_only")["authorized_goal"]
    assert rt.execute(fixture, "guard_only", world_index=1)["files"] == {"old": "y"}


def test_diagnostic_semantics_is_unguarded_nondeduplicating_and_supports_intervention(rt):
    ast = program([effect("read", "read", "input", out="x"),
                   effect("first", "emit", "local", {"var": "x"}, key="shared"),
                   effect("second", "emit", "local", {"var": "x"}, key="shared")])
    world = {"files": {"input": "data"}, "grants": [["read", "input"]]}
    goal = {"emits": [{"resource": "local", "value": "data", "count": 2}]}
    baseline = rt.run_semantics(ast, world, goal)
    assert baseline["error"] is None and baseline["goal"]
    assert baseline["trace"] == [
        {"id": "read", "op": "read", "resource": "input", "value": "", "authorized": True},
        {"id": "first", "op": "emit", "resource": "local", "value": "data", "authorized": False},
        {"id": "second", "op": "emit", "resource": "local", "value": "data", "authorized": False}]
    assert not rt.run_semantics(ast, world, goal, suppress="first")["goal"]
    assert world["files"] == {"input": "data"}


def test_search_estimates_do_not_change_state_or_receipts(rt):
    ast = program([effect("bad", "write", "denied", "x")])
    duplicate = program([effect("unused", "emit", "local", "not-chosen"),
                         effect("slow", "write", "out", "ok")])
    cheap = program([effect("fast", "write", "out", "ok")])
    fixture = case(ast, grants=[["emit", "local"], ["write", "out"]],
                   goal={"files": {"out": "ok"}}, routes=[duplicate, cheap])
    result = rt.execute(fixture, "search")
    assert result["emits"] == []
    assert result["receipt_reuses"] == result["duplicate_effects"] == 0
    assert result["routes_considered"] == 2
    assert len(result["trace"]) == result["charged_calls"] == 3


def test_crlf_source_is_supported_without_changing_semantics(rt):
    ast = program([effect("write", "write", "out", "ok")])
    assert rt.parse_source(source(ast).replace("\n", "\r\n")) == ast


def test_diagnostic_error_is_not_success_even_if_physical_goal_is_met(rt):
    ast = program([effect("done", "write", "out", "ok"),
                   {"id": "fail", "kind": "let", "name": "x", "value": {"var": "missing"}}])
    result = rt.run_semantics(ast, {"files": {}, "grants": [["write", "out"]]},
                              {"files": {"out": "ok"}})
    assert result["error"] == "unbound_variable"
    assert result["files"] == {"out": "ok"}
    assert not result["goal"]


def test_search_ranks_public_goal_achievement_before_cost(rt):
    original = program([effect("blocked", "write", "denied", "x")])
    cheap_wrong = program([])
    useful = program([effect("finish", "write", "out", "ok")])
    result = rt.execute(case(original, grants=[["write", "out"]],
                             goal={"files": {"out": "ok"}}, routes=[cheap_wrong, useful]), "search")
    assert [attempt["route_index"] for attempt in result["attempt_log"]] == [0, 0, 2]
    assert result["authorized_goal"]
    assert [estimate["predicted_goal"] for estimate in result["search_estimates"]] == [False, True]


def test_static_graph_expansion_has_a_finite_analysis_budget(rt):
    body = [effect("read", "read", "input")]
    for level in range(9):
        body = [{"id": f"loop{level}", "kind": "repeat", "count": 3, "body": body}]
    with pytest.raises(ValueError, match="analysis limit"):
        rt.edges(program(body))

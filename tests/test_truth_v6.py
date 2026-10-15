"""Hand-derived semantic expectations; no production parser/runtime imports."""
from __future__ import annotations

import copy
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


def truth():
    assert importlib.util.find_spec("tsg.truth_v6") is not None, "independent truth is missing"
    return importlib.import_module("tsg.truth_v6")


def program(*steps, functions=None):
    return {"version": 1, "steps": list(steps), "functions": functions or {}}


def effect(site, op, resource, **fields):
    return {"id": site, "kind": "effect", "op": op, "resource": resource, **fields}


def world(files=None, grants=()):
    return {"files": files or {}, "grants": [list(pair) for pair in grants]}


def case(p, *, worlds=None, routes=None, goal=None, closed=True):
    return {"case_id": "unit", "program": p, "worlds": worlds or [world()],
            "routes": routes or [], "goal": goal or {}, "catalog_closed": closed}


def label(result, site):
    return next(row for row in result["labels"] if row["id"] == site)


def semantic_probe(engine):
    """Literal witnesses also used to reject deliberately wrong interpreters."""
    p = program(
        effect("r", "read", "in", out="text"),
        {"id": "l", "kind": "let", "name": "text", "value": {"upper": {"var": "text"}}},
        {"id": "b", "kind": "if", "eq": [{"var": "text"}, "AB"],
         "then": [{"id": "c", "kind": "call", "fn": "save"}],
         "else": [effect("wrong", "write", "out", value="wrong")]},
        {"id": "loop", "kind": "repeat", "count": 2,
         "body": [effect("e", "emit", "events", value={"concat": ["prefix:", {"var": "text"}]}, key="same")]},
        effect("d", "delete", "trash"),
        functions={"save": [effect("w", "write", "out", value={"var": "text"})]},
    )
    w = world({"in": "ab", "trash": "obsolete"}, [("read", "in"), ("write", "out"), ("delete", "trash")])
    g = {"files": {"out": "AB"}, "absent": ["trash"], "emits": [{"resource": "events", "value": "prefix:AB", "count": 2}]}
    got = engine.run(p, w, g)
    assert got["goal"] is True
    assert got["error"] is None
    assert got["files"] == {"in": "ab", "out": "AB"}
    assert got["emits"] == [{"resource": "events", "value": "prefix:AB"}] * 2
    assert [t["id"] for t in got["trace"]] == ["r", "w", "e", "e", "d"]
    assert [t["authorized"] for t in got["trace"]] == [True, True, False, False, True]
    assert engine.run(p, w, g, suppress="w")["goal"] is False
    assert w["files"] == {"in": "ab", "trash": "obsolete"}


def test_executes_dataflow_calls_branches_repeat_delete_and_unauthorized_effects():
    semantic_probe(truth())


def test_suppressed_read_returns_empty_and_suppresses_all_site_occurrences():
    p = program({"id": "loop", "kind": "repeat", "count": 3,
                 "body": [effect("r", "read", "in", out="x"), effect("e", "emit", "log", value={"var": "x"})]})
    got = truth().run(p, world({"in": "secret"}), {"emits": [{"resource": "log", "value": "", "count": 3}]}, suppress="r")
    assert got["goal"]
    assert [t["id"] for t in got["trace"]] == ["e", "e", "e"]


def test_scalar_stringification_and_missing_read_have_explicit_values():
    p = program(effect("r", "read", "absent", out="x"),
                effect("w", "write", "out", value={"concat": [True, None, 3, "/", {"var": "x"}]}))
    assert truth().run(p, world(), {"files": {"out": "truenull3/"}})["goal"]


def test_static_sites_include_dead_branches_and_uncalled_function_once():
    p = program({"id": "b", "kind": "if", "eq": [1, 1], "then": [effect("a", "read", "a")], "else": [effect("b2", "read", "b")]},
                functions={"unused": [effect("u", "emit", "u")]})
    assert [s["id"] for s in truth().static_sites(p)] == ["a", "b2", "u"]


@pytest.mark.parametrize("p", [
    program(effect("dup", "read", "a"), effect("dup", "read", "b")),
    program({"id": "loop", "kind": "repeat", "count": 4, "body": []}),
    program({"id": "c", "kind": "call", "fn": "missing"}),
    program(functions={"f": [{"id": "c", "kind": "call", "fn": "f"}]}),
    program(effect("r", "shell", "a")),
    program(effect("w", "write", "a", value={"eval": "bad"})),
])
def test_invalid_reference_ast_is_rejected_without_effects(p):
    got = truth().run(p, world({"a": "safe"}), {})
    assert got["error"]
    assert not got["goal"]
    assert got["trace"] == []
    assert got["files"] == {"a": "safe"}


def test_unbound_variable_and_explicit_key_conflict_fail():
    engine = truth()
    assert engine.run(program(effect("w", "write", "a", value={"var": "missing"})), world(), {})["error"]
    p = program(effect("a", "emit", "log", value="one", key="k"), effect("b", "emit", "log", value="two", key="k"))
    got = engine.run(p, world(), {})
    assert got["error"]
    assert got["emits"] == [{"resource": "log", "value": "one"}]


def test_step_limit_counts_control_steps_and_prevents_goal_success_on_error():
    p = program(*[{"id": f"x{i}", "kind": "let", "name": "x", "value": i} for i in range(101)])
    got = truth().run(p, world(), {})
    assert got["error"] == "step_limit"
    assert not got["goal"]


def test_necessity_is_independent_of_authorization_and_routes_match_effect_class():
    p = program(effect("w", "write", "out", value="ok"))
    route = program(effect("other", "write", "out", value="ok"))
    c = case(p, worlds=[world(grants=[("write", "out")])], routes=[route], goal={"files": {"out": "ok"}})
    got = label(truth().evaluate_case(c), "w")
    assert (got["authorization"], got["implementation"], got["task"]) == ("yes", "yes", "yes")
    c["worlds"][0]["grants"] = []
    got = label(truth().evaluate_case(c), "w")
    assert (got["authorization"], got["implementation"], got["task"]) == ("no", "yes", "unknown")
    assert "no_legal_route" in got["reasons"]["task"]


def test_alternative_route_avoids_target_and_open_catalog_only_blocks_yes():
    p = program(effect("r", "read", "in", out="x"), effect("w", "write", "out", value={"var": "x"}))
    route = program(effect("z", "write", "out", value="ok"))
    c = case(p, worlds=[world({"in": "ok"}, [("read", "in"), ("write", "out")])], routes=[route], goal={"files": {"out": "ok"}}, closed=False)
    got = truth().evaluate_case(c)
    assert label(got, "r")["task"] == "no"
    assert label(got, "w")["task"] == "unknown"
    assert "open_catalog" in label(got, "w")["reasons"]["task"]


def test_inactive_and_failed_baseline_are_unknown_not_unnecessary():
    p = program({"id": "b", "kind": "if", "eq": [0, 1], "then": [effect("dead", "write", "out", value="ok")], "else": []}, effect("r", "read", "in"))
    got = truth().evaluate_case(case(p, goal={"files": {"out": "ok"}}))
    dead = label(got, "dead")
    assert [dead[k] for k in ("authorization", "implementation", "task")] == ["unknown"] * 3
    assert "inactive" in dead["reasons"]["implementation"]
    assert label(got, "r")["implementation"] == "unknown"
    assert "baseline_failure" in label(got, "r")["reasons"]["implementation"]


def test_world_aggregation_preserves_unknown_and_mixed_reasons():
    p = program(effect("w", "write", "out", value="ok"))
    c = case(p, worlds=[world(grants=[("write", "out")]), world({"out": "ok"})], goal={"files": {"out": "ok"}})
    got = label(truth().evaluate_case(c), "w")
    assert got["authorization"] == "unknown"
    assert got["implementation"] == "unknown"
    assert got["task"] == "unknown"
    assert all("mixed_worlds" in got["reasons"][axis] for axis in ("authorization", "implementation", "task"))


def test_metameric_renaming_and_inert_let_preserve_observable_semantics():
    engine = truth()
    p = program(effect("r", "read", "in", out="x"), effect("w", "write", "out", value={"upper": {"var": "x"}}))
    renamed = program({"id": "unused", "kind": "let", "name": "unused", "value": "irrelevant"},
                      effect("new_r", "read", "in", out="renamed"), effect("new_w", "write", "out", value={"upper": {"var": "renamed"}}))
    w = world({"in": "abc"}, [("read", "in"), ("write", "out")])
    g = {"files": {"out": "ABC"}}
    before, after = engine.run(p, w, g), engine.run(renamed, w, g)
    assert (before["files"], before["emits"], before["goal"]) == (after["files"], after["emits"], after["goal"])
    left = engine.evaluate_case(case(p, worlds=[w], goal=g))["labels"]
    right = engine.evaluate_case(case(renamed, worlds=[w], goal=g))["labels"]
    assert [(r["authorization"], r["implementation"], r["task"]) for r in left] == [(r["authorization"], r["implementation"], r["task"]) for r in right]


def test_development_generator_builds_twelve_equivalent_executable_cases(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "build_phase6_dev.py"
    assert script.exists(), "development generator is missing"
    destination = tmp_path / "dev.jsonl"
    result = subprocess.run([sys.executable, str(script), "--output", str(destination)], cwd=root, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    cases = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    assert len(cases) == 12
    assert len({c["family"] for c in cases}) == 6
    assert len({c["case_id"] for c in cases}) == 12
    assert all(c["split"] == "dev" for c in cases)
    assert all(sum(c["family"] == other["family"] for other in cases) == 2 for c in cases)
    all_reasons, labels = set(), set()
    for c in cases:
        source_ast = json.loads(c["source"].split("```tsg-workflow\n", 1)[1].split("```", 1)[0])
        assert source_ast == c["program"]
        assert c["source"].count("```tsg-workflow") == 1
        for p in [c["program"], *c["routes"]]:
            truth().static_sites(p)
            for w in c["worlds"]:
                assert truth().run(p, w, c["goal"])["error"] is None
        evaluated = truth().evaluate_case(c)
        for row in evaluated["labels"]:
            for axis in ("authorization", "implementation", "task"):
                labels.add(row[axis])
                all_reasons.update(row["reasons"][axis])
    assert labels == {"yes", "no", "unknown"}
    assert {"inactive", "baseline_failure", "mixed_worlds", "open_catalog", "no_legal_route"} <= all_reasons
    assert destination.read_bytes() == (root / "data" / "phase6" / "dev.jsonl").read_bytes()


def test_exact_emit_goal_rejects_additional_matching_emit():
    p = program({"id": "loop", "kind": "repeat", "count": 3, "body": [effect("e", "emit", "log", value="a")]})
    got = truth().run(p, world(), {"emits": [{"resource": "log", "value": "a", "count": 2}]})
    assert not got["goal"]


def test_target_all_occurrences_authorized_and_identities_span_resources():
    p = program({"id": "l", "kind": "let", "name": "path", "value": "a"},
                {"id": "loop", "kind": "repeat", "count": 2, "body": [effect("e", "emit", {"var": "path"}, value="v"),
                    {"id": "next", "kind": "let", "name": "path", "value": "b"}]})
    g = {"emits": [{"resource": "a", "value": "v", "count": 1}, {"resource": "b", "value": "v", "count": 1}]}
    c = case(p, worlds=[world(grants=[("emit", "a")])], goal=g)
    got = label(truth().evaluate_case(c), "e")
    assert got["authorization"] == "no"
    assert got["implementation"] == "yes"
    assert got["task"] == "unknown"


def test_mutation_witnesses_reject_wrong_semantics(tmp_path):
    """Execute altered copies, requiring literal witnesses to reject each one."""
    source = Path(truth().__file__).read_text(encoding="utf-8")
    mutations = [
        ("upper_to_lower", ').upper()', ').lower()'),
        ("reverse_concat", 'for part in expr["concat"])', 'for part in reversed(expr["concat"]))'),
        ("invert_branch", 'if left == right else', 'if left != right else'),
        ("repeat_once", 'range(step["count"])', 'range(min(step["count"], 1))'),
        ("skip_delete", 'files.pop(resource, None)', 'files.get(resource, None)'),
        ("grant_everything", 'authorized = (op, resource) in grants', 'authorized = True'),
        ("ignore_suppression", 'if step["id"] != suppress:', 'if True:'),
    ]
    for name, old, new in mutations:
        assert source.count(old) == 1, name
        path = tmp_path / (name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, path)
        mutated = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mutated)
        with pytest.raises(AssertionError):
            semantic_probe(mutated)


def test_necessity_mutations_are_rejected_by_hand_derived_witnesses(tmp_path):
    source = Path(truth().__file__).read_text(encoding="utf-8")
    p = program(effect("w", "write", "out", value="ok"))
    c = case(p, worlds=[world(grants=[("write", "out")])], goal={"files": {"out": "ok"}}, closed=False)
    for name, old, new, axis, expected in [
        ("ignore_closure", 'elif closed:', 'elif True:', "task", "unknown"),
        ("invert_intervention", '"no" if intervened["goal"] else "yes"', '"yes" if intervened["goal"] else "no"', "implementation", "yes"),
    ]:
        assert source.count(old) == 1
        path = tmp_path / (name + ".py")
        path.write_text(source.replace(old, new), encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, path)
        mutated = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mutated)
        assert label(truth().evaluate_case(c), "w")[axis] == expected
        assert label(mutated.evaluate_case(c), "w")[axis] != expected

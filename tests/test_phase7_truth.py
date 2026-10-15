"""Typed reference tests use hand-derived toy cases and Phase 6 dev only.

The generator test checks syntax/metadata, never evaluates held-out outcomes.
"""
from __future__ import annotations

import copy
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tsg import truth_v6


def truth():
    assert importlib.util.find_spec("tsg.truth_v7") is not None, "typed reference is missing"
    return importlib.import_module("tsg.truth_v7")


def program(*steps, functions=None):
    return {"version": 1, "steps": list(steps), "functions": functions or {}}


def effect(site, op, resource, **fields):
    return {"id": site, "kind": "effect", "op": op, "resource": resource, **fields}


def world(files=None, grants=()):
    return {"files": files or {}, "grants": [list(pair) for pair in grants]}


def case(p, *, worlds=None, routes=None, goal=None, closed=True):
    return {"case_id": "toy", "program": p, "worlds": [world()] if worlds is None else worlds,
            "routes": routes or [], "goal": goal or {}, "catalog_closed": closed}


def label(result, site):
    return next(row for row in result["labels"] if row["id"] == site)


def test_inactive_is_not_applicable_on_every_axis_including_unreached_function():
    p = program(functions={"unused": [effect("hidden", "emit", "log", value="x")]})
    result = truth().evaluate_case(case(p))
    row = label(result, "hidden")
    for axis in ("authorization", "current_route_required", "catalog_required"):
        assert row[axis] == "not_applicable"
        assert row["reasons"][axis] == ["inactive"]
    audit = label(result["worlds"][0], "hidden")
    assert audit["occurred"] is False
    assert audit["all_occurrences_authorized"] is True
    assert audit["baseline_success"] is True
    assert audit["suppressed_success"] is True
    assert audit["legal_routes"] == [0]
    assert audit["avoiding_routes"] == []


def test_denied_side_effect_can_be_nonessential_on_both_necessity_axes():
    p = program(effect("scratch", "write", "scratch", value="side"),
                effect("save", "write", "out", value="ok"))
    direct = program(effect("direct", "write", "out", value="ok"))
    result = truth().evaluate_case(case(p, worlds=[world(grants=[("write", "out")])],
                                       routes=[direct], goal={"files": {"out": "ok"}}))
    row = label(result, "scratch")
    assert (row["authorization"], row["current_route_required"], row["catalog_required"]) == ("no", "no", "no")
    audit = label(result["worlds"][0], "scratch")
    assert audit["legal_routes"] == [1]
    assert audit["avoiding_routes"] == [1]
    assert audit["all_occurrences_authorized"] is False


def test_failed_baseline_and_no_feasible_route_have_distinct_inapplicability_reasons():
    p = program(effect("save", "write", "out", value="wrong"))
    result = truth().evaluate_case(case(p, worlds=[world(grants=[("write", "out")])],
                                       goal={"files": {"out": "ok"}}))
    row = label(result, "save")
    assert row["authorization"] == "yes"
    assert row["current_route_required"] == "not_applicable"
    assert row["catalog_required"] == "not_applicable"
    assert row["reasons"]["current_route_required"] == ["baseline_failure"]
    assert row["reasons"]["catalog_required"] == ["no_feasible_route"]


@pytest.mark.parametrize("closed,with_alternative,expected,reasons", [
    (True, False, "yes", []), (False, False, "unknown", ["open_catalog"]),
    (False, True, "no", []),
])
def test_open_catalog_is_unknown_only_when_no_feasible_avoiding_route(closed, with_alternative, expected, reasons):
    p = program(effect("r", "read", "in", out="x"), effect("w", "write", "out", value={"var": "x"}))
    alternate = program(effect("direct", "write", "out", value="ok"))
    result = truth().evaluate_case(case(p, worlds=[world({"in": "ok"}, [("read", "in"), ("write", "out")])],
                                       routes=[alternate] if with_alternative else [],
                                       goal={"files": {"out": "ok"}}, closed=closed))
    row = label(result, "r")
    assert row["current_route_required"] == "yes"
    assert row["catalog_required"] == expected
    assert row["reasons"]["catalog_required"] == reasons


def test_multiple_occurrences_require_all_authorizations_and_avoid_all_target_identities():
    p = program({"id": "init", "kind": "let", "name": "path", "value": "a"},
                {"id": "loop", "kind": "repeat", "count": 2, "body": [
                    effect("read", "read", {"var": "path"}, out="x"),
                    {"id": "next", "kind": "let", "name": "path", "value": "b"}]},
                effect("write", "write", "out", value="ok"))
    alternate = program(effect("other_read", "read", "a"), effect("other_write", "write", "out", value="ok"))
    result = truth().evaluate_case(case(p, worlds=[world(grants=[("read", "a"), ("write", "out")])],
                                       routes=[alternate], goal={"files": {"out": "ok"}}))
    row = label(result, "read")
    assert (row["authorization"], row["current_route_required"], row["catalog_required"]) == ("no", "no", "yes")
    audit = label(result["worlds"][0], "read")
    assert audit["legal_routes"] == [1]
    assert audit["avoiding_routes"] == []


def test_mixed_applicability_does_not_erase_inactivity_reason():
    p = program(effect("mode", "read", "mode", out="mode"),
                {"id": "branch", "kind": "if", "eq": [{"var": "mode"}, "on"],
                 "then": [effect("save", "write", "out", value="ok")], "else": []})
    grants = [("read", "mode"), ("write", "out")]
    result = truth().evaluate_case(case(p, worlds=[world({"mode": "on"}, grants),
                                                    world({"mode": "off", "out": "ok"}, grants)],
                                       goal={"files": {"out": "ok"}}))
    row = label(result, "save")
    for axis in ("authorization", "current_route_required", "catalog_required"):
        assert row[axis] == "unknown"
        assert row["reasons"][axis] == ["inactive", "partial_applicability"]


def test_applicable_world_disagreement_is_not_partial_applicability():
    p = program(effect("read", "read", "in"), effect("save", "write", "out", value="ok"))
    result = truth().evaluate_case(case(p, worlds=[world(grants=[("read", "in"), ("write", "out")]),
                                                    world(grants=[("write", "out")])],
                                       routes=[program(effect("direct", "write", "out", value="ok"))],
                                       goal={"files": {"out": "ok"}}))
    row = label(result, "read")
    assert row["authorization"] == "unknown"
    assert row["reasons"]["authorization"] == ["world_disagreement"]
    assert row["current_route_required"] == "no"
    assert row["catalog_required"] == "no"


def test_aggregation_preserves_uniform_unknown_and_reports_both_mixed_causes():
    p = program(effect("mode", "read", "mode", out="mode"),
                {"id": "branch", "kind": "if", "eq": [{"var": "mode"}, "on"],
                 "then": [effect("read", "read", "in")], "else": []},
                effect("save", "write", "out", value="ok"))
    grants = [("read", "mode"), ("read", "in"), ("write", "out")]
    result = truth().evaluate_case(case(p, worlds=[world({"mode": "on"}, grants),
                                                    world({"mode": "on"}, grants[::2]),
                                                    world({"mode": "off"}, grants)],
                                       goal={"files": {"out": "ok"}}, closed=False))
    row = label(result, "read")
    assert row["authorization"] == "unknown"
    assert row["reasons"]["authorization"] == ["inactive", "partial_applicability", "world_disagreement"]
    assert label(result, "save")["catalog_required"] == "unknown"


def test_reference_ignores_source_and_metadata_and_does_not_mutate_input():
    c = case(program(effect("save", "write", "out", value="ok")),
             worlds=[world(grants=[("write", "out")])], goal={"files": {"out": "ok"}})
    c.update(source="not a workflow", family="uninformative", authored_gold={"save": "wrong"})
    before = copy.deepcopy(c)
    result = truth().evaluate_case(c)
    assert c == before
    assert label(result, "save")["authorization"] == "yes"
    assert label(result, "save")["current_route_required"] == "yes"
    assert label(result, "save")["catalog_required"] == "yes"


@pytest.mark.parametrize("field,value,error", [("worlds", [], "empty_worlds"),
                                               ("catalog_closed", 1, "invalid_catalog_closure")])
def test_reference_rejects_invalid_case_boundaries(field, value, error):
    c = case(program())
    c[field] = value
    with pytest.raises(ValueError, match=error):
        truth().evaluate_case(c)


def test_collapsing_typed_labels_matches_v6_on_development_only():
    root = Path(__file__).resolve().parents[1]
    for line in (root / "data/phase6/dev.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        old = truth_v6.evaluate_case(c)
        new = truth().evaluate_case(c)
        assert [r["id"] for r in new["labels"]] == [r["id"] for r in old["labels"]]
        for old_row, new_row in zip(old["labels"], new["labels"]):
            for new_axis, old_axis in (("authorization", "authorization"),
                                       ("current_route_required", "implementation"),
                                       ("catalog_required", "task")):
                collapsed = "unknown" if new_row[new_axis] == "not_applicable" else new_row[new_axis]
                assert collapsed == old_row[old_axis], (c["case_id"], new_row["id"], new_axis)


def test_generator_emits_24_source_exact_schema_valid_cases_without_evaluating_them(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/build_phase7_heldout.py"
    assert script.exists(), "independent generator is missing"
    output = tmp_path / "heldout.jsonl"
    result = subprocess.run([sys.executable, str(script), "--output", str(output)], cwd=root,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    cases = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(cases) == len({c["case_id"] for c in cases}) == 24
    assert len({c["family"] for c in cases}) == 12
    assert all(c["split"] == "heldout" for c in cases)
    assert all(sum(c["family"] == other["family"] for other in cases) == 2 for c in cases)
    for c in cases:
        assert not ({"labels", "gold", "authored_gold", "judgments", "expected"} & set(c))
        assert c["source"].count("```tsg-workflow\n") == 1
        decoded = json.loads(c["source"].split("```tsg-workflow\n", 1)[1].split("```", 1)[0])
        assert decoded == c["program"]
        assert c["worlds"] and type(c["catalog_closed"]) is bool
        for p in [c["program"], *c["routes"]]:
            truth_v6.static_sites(p)
    assert output.read_bytes() == (root / "data/phase7/heldout.jsonl").read_bytes()

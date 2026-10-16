"""Reference-only prospective coverage and immutable fixture checks."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from tsg.truth_v6 import run, static_sites
from tsg.truth_v7 import AXES, evaluate_case

ROOT = Path(__file__).resolve().parents[1]


def builder():
    path = ROOT / "scripts/build_phase8_heldout.py"
    assert path.exists(), "Phase 8 independent fixture builder must exist"
    spec = importlib.util.spec_from_file_location("phase8_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prospective_case_family_world_and_typed_label_coverage():
    cases = builder().build_cases()
    assert len(cases) == len({c["case_id"] for c in cases}) == 48
    assert sorted(Counter(c["family"] for c in cases).values()) == [4] * 12
    assert sum(not c["routes"] for c in cases) >= 12
    assert sum(len(c["worlds"]) > 1 for c in cases) >= 12
    counts = {axis: Counter() for axis in AXES}
    for case in cases:
        source = case["source"].split("```tsg-workflow\n", 1)[1].split("```", 1)[0]
        assert json.loads(source) == case["program"]
        for program in [case["program"], *case["routes"]]:
            static_sites(program)
        for row in evaluate_case(case)["labels"]:
            for axis in AXES:
                counts[axis][row[axis]] += 1
    for axis in AXES:
        assert set(counts[axis]) == {"yes", "no", "unknown", "not_applicable"}
        assert min(counts[axis].values()) >= 8, (axis, counts[axis])
    assert counts["authorization"]["no"] >= 8


def test_reference_facts_include_full_suppression_executions():
    mod = builder()
    case = mod.build_cases()[0]
    record = mod.reference_record(case)
    assert record["labels"] == evaluate_case(case)["labels"]
    for supplied, result in zip(case["worlds"], record["worlds"], strict=True):
        assert set(result["interventions"]) == {s["id"] for s in static_sites(case["program"])}
        for site, execution in result["interventions"].items():
            assert execution == run(case["program"], supplied, case["goal"], suppress=site)


def test_normalization_erases_names_and_literals_but_keeps_operators_nesting_and_calls():
    mod = builder()
    one = {"version": 1, "steps": [{"id": "a", "kind": "effect", "op": "write", "resource": "/a", "value": "x"}], "functions": {}}
    renamed = deepcopy(one)
    renamed["steps"][0].update(id="b", resource="/other", value="different")
    assert mod.skeleton_tokens(one) == mod.skeleton_tokens(renamed)
    changed = deepcopy(one)
    changed["steps"][0]["op"] = "emit"
    assert mod.skeleton_tokens(one) != mod.skeleton_tokens(changed)
    wrapped = {"version": 1, "steps": [{"id": "c", "kind": "call", "fn": "f"}], "functions": {"f": one["steps"]}}
    assert mod.skeleton_tokens(one) != mod.skeleton_tokens(wrapped)
    assert "CALL" in mod.skeleton_tokens(wrapped)
    assert mod.token_distance(("A", "B", "C"), ("A", "X", "C", "D")) == 2
    assert mod.token_distance((), ("A", "B")) == 2


def test_shortcut_and_no_shortcut_witnesses_exist_under_reference_semantics():
    costly, isolated = 0, 0
    for case in builder().build_cases():
        for result in evaluate_case(case)["worlds"]:
            legal = result["legal_route_indices"]
            baseline = result["baseline"]
            if 0 in legal and not any(index > 0 for index in legal):
                isolated += 1
            if 0 in legal and baseline["trace"] and baseline["trace"][0]["op"] in {"read", "write", "delete"}:
                alternatives = [len(result["routes"][index]["trace"]) for index in legal if index > 0]
                if alternatives and min(alternatives) + 2 < len(baseline["trace"]):
                    costly += 1
    assert costly >= 8
    assert isolated >= 12


def test_write_once_refuses_to_replace_frozen_bytes(tmp_path):
    mod = builder()
    target = tmp_path / "heldout.jsonl"
    mod.write_once(target, b"original\n")
    with pytest.raises(FileExistsError):
        mod.write_once(target, b"replacement\n")
    assert target.read_bytes() == b"original\n"


def test_novelty_compares_every_prior_split_and_reports_actual_duplicate_groups():
    mod = builder()
    cases = mod.build_cases()
    audit = mod.novelty_audit(cases)
    assert {row["path"] for row in audit["prior_files"]} == {
        "data/phase6/dev.jsonl", "data/phase6/heldout.jsonl",
        "data/phase6/challenge.jsonl", "data/phase7/heldout.jsonl",
    }
    assert audit["prior_original_count"] == 72
    assert audit["prior_reference_program_count"] == 186
    assert audit["unique_new_original_skeletons"] == 12
    assert sorted(len(group) for group in audit["within_new_exact_groups"]) == [4] * 12
    assert all(row["all_prior_reference_programs"]["exact_duplicates"] == [] for row in audit["cases"])
    assert all(row["all_prior_reference_programs"]["minimum_token_edit_distance"] > 0 for row in audit["cases"])
    prior = json.loads((ROOT / "data/phase6/dev.jsonl").read_text(encoding="utf-8").splitlines()[0])
    duplicate_audit = mod.novelty_audit([prior])
    matching = duplicate_audit["cases"][0]["prior_originals"]
    assert matching["minimum_token_edit_distance"] == 0
    assert any(row["case_id"] == prior["case_id"] and row["route_index"] == 0 for row in matching["exact_duplicates"])


def test_frozen_data_and_complete_reference_truth_reproduce():
    mod = builder()
    frozen = ROOT / "data/phase8/heldout.jsonl"
    truth = ROOT / "results/phase8/reference/truth.jsonl"
    assert frozen.exists() and truth.exists(), "independent heldout and reference truth must be frozen"
    cases = mod.build_cases()
    assert frozen.read_bytes() == mod.jsonl_bytes(cases)
    assert truth.read_bytes() == mod.jsonl_bytes([mod.reference_record(c) for c in cases])

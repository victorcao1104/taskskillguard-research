"""Independent Phase 9 reference scope; no production modules are imported."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from tsg.truth_v6 import run, static_sites
from tsg.truth_v7 import AXES, evaluate_case

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def builder():
    path = ROOT / "scripts/build_phase9_heldout.py"
    assert path.exists(), "Phase 9 independent generator must exist"
    spec = importlib.util.spec_from_file_location("phase9_reference_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handwritten_family_and_bounded_dsl_coverage(builder):
    cases = builder.build_cases()
    assert len(cases) == len({c["case_id"] for c in cases}) == 24
    assert sorted(Counter(c["family"] for c in cases).values()) == [2] * 12
    assert sum(not c["routes"] for c in cases) >= 6
    for case in cases:
        assert 1 <= len(case["worlds"]) <= 3
        assert 0 <= len(case["routes"]) <= 3
        assert 4 <= len(static_sites(case["program"])) <= 12
        assert json.loads(case["source"].split("```tsg-workflow\n")[1].split("```")[0]) == case["program"]
        for route in case["routes"]:
            static_sites(route)
    assert sum(4 <= len(static_sites(c["program"])) <= 8 for c in cases) >= 20


def test_all_typed_values_and_prospective_coverage_are_present(builder):
    cases = builder.build_cases()
    records = [builder.reference_record(case) for case in cases]
    audit = builder.coverage_audit(cases, records)
    assert audit["passed"], audit["acceptance"]
    for axis in AXES:
        assert all(audit["aggregate_labels"][axis][value] > 0
                   for value in ("yes", "no", "unknown", "not_applicable"))
    assert len(audit["observable_multiworld_cases"]) >= 8
    assert len(audit["irreducible_hidden_cases"]) >= 4
    assert len({w["case_id"] for w in audit["key_conflict_worlds"]}) >= 4
    assert len({w["case_id"] for w in audit["call_emission_tradeoffs"]}) >= 4


def test_full_reference_execution_and_suppression_evidence(builder):
    for case in builder.build_cases():
        actual = builder.reference_record(case)
        assert actual["labels"] == evaluate_case(case)["labels"]
        for world, record in zip(case["worlds"], actual["worlds"], strict=True):
            assert set(record["interventions"]) == {s["id"] for s in static_sites(case["program"])}
            for site, execution in record["interventions"].items():
                assert execution == run(case["program"], world, case["goal"], suppress=site)


def test_observability_projection_preserves_absence_and_grant_denial(builder):
    case = {"worlds": [{"files": {"/a": ""}, "grants": [["read", "/a"]]},
                       {"files": {}, "grants": []}]}
    first, second = [builder.observation_signature(case, w) for w in case["worlds"]]
    assert first != second
    hidden = {**case, "observable_files": [], "observable_grants": []}
    assert builder.observation_signature(hidden, case["worlds"][0]) == builder.observation_signature(hidden, case["worlds"][1])


def test_hidden_worlds_really_disagree_on_reference_labels(builder):
    hidden = [c for c in builder.build_cases() if c.get("observable_files") == [] and c.get("observable_grants") == []]
    assert len(hidden) >= 4
    for case in hidden:
        worlds = evaluate_case(case)["worlds"]
        assert len({builder.observation_signature(case, w) for w in case["worlds"]}) == 1
        assert any(len({w["labels"][i][axis] for w in worlds}) > 1
                   for i in range(len(worlds[0]["labels"])) for axis in AXES)


def test_normalization_and_known_edit_distances(builder):
    original = builder.build_cases()[0]["program"]
    renamed = deepcopy(original)
    renamed["steps"][0]["resource"] = "/renamed"
    renamed["steps"][0]["id"] = "renamed"
    assert builder.skeleton_tokens(renamed) == builder.skeleton_tokens(original)
    renamed["steps"][0]["op"] = "delete"
    assert builder.skeleton_tokens(renamed) != builder.skeleton_tokens(original)
    assert builder.token_distance(("a", "b", "c"), ("a", "z", "c", "d")) == 2
    assert builder.token_distance((), ("x",)) == 1


def test_novelty_covers_all_old_originals_and_alternatives(builder):
    audit = builder.novelty_audit(builder.build_cases())
    assert {r["path"] for r in audit["prior_files"]} == {
        "data/phase6/dev.jsonl", "data/phase6/heldout.jsonl", "data/phase6/challenge.jsonl",
        "data/phase7/heldout.jsonl", "data/phase8/heldout.jsonl"}
    assert audit["prior_original_count"] == 120
    assert audit["prior_reference_program_count"] > 234
    assert audit["unique_new_original_skeletons"] == 12
    assert sorted(map(len, audit["within_new_exact_groups"])) == [2] * 12
    assert all(r["all_prior_reference_programs"]["minimum_token_edit_distance"] > 0 for r in audit["cases"])
    prior = json.loads((ROOT / "data/phase6/dev.jsonl").read_text().splitlines()[0])
    match = builder.novelty_audit([prior])["cases"][0]["prior_originals"]
    assert match["minimum_token_edit_distance"] == 0
    assert any(r["case_id"] == prior["case_id"] for r in match["exact_duplicates"])


def test_deterministic_generator_and_immutable_output(builder, tmp_path):
    assert builder.jsonl_bytes(builder.build_cases()) == builder.jsonl_bytes(builder.build_cases())
    target = tmp_path / "frozen.jsonl"
    builder.write_once(target, b"first\n")
    with pytest.raises(FileExistsError):
        builder.write_once(target, b"second\n")
    assert target.read_bytes() == b"first\n"


def test_frozen_outputs_reproduce_if_materialized(builder):
    frozen = ROOT / "data/phase9/heldout.jsonl"
    if not frozen.exists():
        pytest.skip("Heldout is intentionally not revealed before production freeze")
    cases = builder.build_cases()
    assert frozen.read_bytes() == builder.jsonl_bytes(cases)
    assert (ROOT / "results/phase9/reference/truth.jsonl").read_bytes() == builder.jsonl_bytes([builder.reference_record(c) for c in cases])

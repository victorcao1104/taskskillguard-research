"""Independent Phase 10 reference checks; never import a production module."""
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
    path = ROOT / "scripts/build_phase10_heldout.py"
    assert path.exists(), "Independent generator is not implemented yet"
    spec = importlib.util.spec_from_file_location("p10_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_authored_cases_and_source_are_bounded_and_reproducible(builder):
    cases = builder.build_cases()
    assert len(cases) == len({c["case_id"] for c in cases}) == 24
    assert sorted(Counter(c["family"] for c in cases).values()) == [2] * 12
    assert builder.jsonl_bytes(cases) == builder.jsonl_bytes(builder.build_cases())
    for case in cases:
        assert case["split"] == "heldout"
        assert not ({"labels", "truth", "world_index"} & set(case))
        assert 1 <= len(case["worlds"]) <= 3
        assert len(case["routes"]) <= 3
        assert 4 <= len(static_sites(case["program"])) <= 12
        assert json.loads(case["source"].split("```tsg-workflow\n")[1].split("```")[0]) == case["program"]
        for route in case["routes"]:
            static_sites(route)


def test_every_truth_record_reexecutes_all_worlds_and_interventions(builder):
    for case in builder.build_cases():
        record = builder.reference_record(case)
        assert record["labels"] == evaluate_case(case)["labels"]
        for supplied, result in zip(case["worlds"], record["worlds"], strict=True):
            assert result["baseline"] == run(case["program"], supplied, case["goal"])
            assert set(result["interventions"]) == {s["id"] for s in static_sites(case["program"])}
            for site, intervention in result["interventions"].items():
                assert intervention == run(case["program"], supplied, case["goal"], suppress=site)


def test_predeclared_coverage_report_retains_all_typed_cells(builder):
    cases = builder.build_cases()
    audit = builder.coverage_audit(cases, [builder.reference_record(c) for c in cases])
    assert audit["passed"], audit["acceptance"]
    for axis in AXES:
        assert all(audit["aggregate_labels"][axis][kind] > 0 for kind in builder.TYPES)
    assert len(audit["goal_only_observable_cases"]) >= 4
    assert len(audit["two_read_goal_observation_cases"]) >= 2
    assert len(audit["irreducible_hidden_cases"]) >= 4
    assert len({w["case_id"] for w in audit["key_conflict_worlds"]}) >= 4
    assert len({w["case_id"] for w in audit["call_emission_tradeoffs"]}) >= 4
    assert audit["incomplete_original_worlds"]


def test_allowed_file_observations_are_legal_initial_reads(builder):
    for case in builder.build_cases():
        for path in case["observable_files"]:
            assert all(["read", path] in world["grants"] for world in case["worlds"])
            assert all(event["resource"] != path or event["op"] == "read"
                       for world in builder.reference_record(case)["worlds"]
                       for event in world["baseline"]["trace"])


def test_projection_distinguishes_absence_and_hides_disallowed_data(builder):
    case = {"worlds": [{"files": {"/x": ""}, "grants": [["read", "/x"]]},
                       {"files": {}, "grants": []}]}
    assert builder.observation_signature(case, case["worlds"][0]) != builder.observation_signature(case, case["worlds"][1])
    case.update(observable_files=[], observable_grants=[])
    assert builder.observation_signature(case, case["worlds"][0]) == builder.observation_signature(case, case["worlds"][1])


def test_novelty_includes_phase9_and_every_prior_alternative(builder):
    audit = builder.novelty_audit(builder.build_cases())
    assert "data/phase9/heldout.jsonl" in {r["path"] for r in audit["prior_files"]}
    assert audit["prior_original_count"] == 144
    assert audit["prior_reference_program_count"] > audit["prior_original_count"]
    assert audit["unique_new_original_skeletons"] == 12
    assert sorted(map(len, audit["within_new_exact_groups"])) == [2] * 12
    assert all(row["all_prior_reference_programs"]["minimum_token_edit_distance"] > 0 for row in audit["cases"])
    old = json.loads((ROOT / "data/phase9/heldout.jsonl").read_text().splitlines()[0])
    assert builder.novelty_audit([old])["cases"][0]["all_prior_reference_programs"]["minimum_token_edit_distance"] == 0


def test_normalization_retains_structure_but_erases_lexical_names(builder):
    original = builder.build_cases()[0]["program"]
    renamed = deepcopy(original)
    renamed["steps"][0]["id"] = "another"
    renamed["steps"][0]["resource"] = "/another"
    assert builder.skeleton_tokens(original) == builder.skeleton_tokens(renamed)
    renamed["steps"][0]["op"] = "delete"
    assert builder.skeleton_tokens(original) != builder.skeleton_tokens(renamed)
    assert builder.token_distance(("a", "b"), ("a", "z", "b")) == 1


def test_write_once_never_replaces_frozen_outputs(builder, tmp_path):
    target = tmp_path / "frozen.jsonl"
    builder.write_once(target, b"first\n")
    with pytest.raises(FileExistsError):
        builder.write_once(target, b"second\n")
    assert target.read_bytes() == b"first\n"


def test_materialized_outputs_match_first_pass_if_released(builder):
    path = ROOT / "data/phase10/heldout.jsonl"
    if not path.exists():
        pytest.skip("Heldout remains concealed until production freeze")
    cases = builder.build_cases()
    assert path.read_bytes() == builder.jsonl_bytes(cases)
    assert (ROOT / "results/phase10/reference/truth.jsonl").read_bytes() == builder.jsonl_bytes([builder.reference_record(c) for c in cases])

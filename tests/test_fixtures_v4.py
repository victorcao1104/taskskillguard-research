"""Integrity checks for independent authored truth, never extractor agreement."""
import importlib.util
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module():
    spec = importlib.util.find_spec("tsg.fixtures_v4")
    assert spec is not None, "independent fixture authoring module is missing"
    from tsg import fixtures_v4
    return fixtures_v4


def test_fixture_truth_is_available_without_any_extractor():
    fixtures = module().build_fixtures()
    assert 40 <= len(fixtures) <= 60
    assert len({f["id"] for f in fixtures}) == len(fixtures)
    assert len({f["family"] for f in fixtures}) >= 20


def test_family_split_never_leaks_a_construction_family():
    families = defaultdict(set)
    for fixture in module().build_fixtures():
        families[fixture["family"]].add(fixture["split"])
    assert all(len(splits) == 1 for splits in families.values())
    assert {next(iter(s)) for s in families.values()} == {"dev", "validation", "heldout"}


def test_literal_evidence_spans_match_original_files_and_roles():
    for fixture in module().build_fixtures():
        files = {path: content.splitlines() for path, content in fixture["files"].items()}
        for key in ("expected_effects", "expected_non_actions", "expected_uncertainties"):
            for item in fixture[key]:
                start, end = item["line_start"], item["line_end"]
                assert 1 <= start <= end <= len(files[item["file"]]), (fixture["id"], item)
                assert "\n".join(files[item["file"]][start - 1:end]) == item["evidence"], (fixture["id"], item)
        ids = [e["effect_id"] for e in fixture["expected_effects"]]
        assert len(ids) == len(set(ids))
        for effect in fixture["expected_effects"]:
            assert effect["grammar_status"] in {"supported", "deliberately_unresolved", "unsupported"}
            assert effect["resource_status"] in {"literal", "resolved_constant", "unknown"}
            assert effect["execution_role"] in {"source_code", "example", "instruction"}
            assert effect["resource"] is not None or effect["resource_status"] == "unknown"
            assert effect["invocation_proven"] is False


def test_all_semantic_limits_have_positive_cases():
    fixtures = module().build_fixtures()
    effects = [e for f in fixtures for e in f["expected_effects"]]
    assert {e["grammar_status"] for e in effects} == {"supported", "deliberately_unresolved", "unsupported"}
    assert any(e["reachability"] == "uninvoked_function" for e in effects)
    assert any(e["reachability"] == "reachable_local_call" for e in effects)
    assert any(e["execution_role"] == "example" for e in effects)
    assert any(f["expected_non_actions"] and not f["expected_effects"] for f in fixtures)
    truths = [e["reasoning_truth"] for e in effects]
    assert any(t["authorization"] == "authorized" and t["task_necessary"] is False for t in truths)
    assert any(t["implementation_necessary"] is True and t["task_necessary"] is False for t in truths)


def test_finite_contracts_reference_real_effects_and_have_literal_alternatives():
    for fixture in module().build_fixtures():
        contract = fixture["task_contract"]
        if contract is None:
            assert all(e["reasoning_truth"]["authorization"] == "unknown" for e in fixture["expected_effects"])
            continue
        ids = {e["effect_id"] for e in fixture["expected_effects"]}
        for plan in contract["finite_model"]["plans"]:
            assert set(plan["effects"]) <= ids
            assert type(plan["goal_satisfied"]) is bool
        plans = contract["finite_model"]["plans"]
        successful = [p for p in plans if p["goal_satisfied"]]
        implementation_names = contract["finite_model"]["implementation_plans"]
        assert set(implementation_names) <= {p["name"] for p in plans}
        implementation_successes = [p for p in successful if p["name"] in implementation_names]
        assert successful and implementation_successes
        for effect in fixture["expected_effects"]:
            truth = effect["reasoning_truth"]
            assert truth["basis"] == "independent_finite_model"
            for necessary_key in ("implementation_necessary", "task_necessary"):
                assert truth[necessary_key] is None or type(truth[necessary_key]) is bool
            assert truth["task_necessary"] == all(effect["effect_id"] in p["effects"] for p in successful)
            assert truth["implementation_necessary"] == all(effect["effect_id"] in p["effects"] for p in implementation_successes)
            granted = {"operation": effect["operation"], "resource": effect["resource"]} in contract["allowed_effects"]
            assert truth["authorization"] == ("authorized" if granted else "not_authorized")


def test_build_is_read_only_and_returns_independent_copies():
    first = module().build_fixtures()
    expected_id = first[0]["id"]
    first[0]["id"] = "mutated"
    assert module().build_fixtures()[0]["id"] == expected_id


def test_frozen_jsonl_matches_authored_truth_and_refuses_overwrite(tmp_path):
    mod = module()
    for split in ("dev", "validation", "heldout"):
        actual = [json.loads(line) for line in (ROOT / "data" / "phase4" / f"fixtures_{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert actual == [f for f in mod.build_fixtures() if f["split"] == split]
    mod.write_fixtures(tmp_path)
    import pytest
    with pytest.raises(FileExistsError):
        mod.write_fixtures(tmp_path)

"""Source-only integrity tests; never execute benchmark programs or import an extractor."""
import hashlib
import ast
import json
import re
import runpy
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "phase5"
LABELS = {"action_valid", "authorized", "implementation_necessary", "task_necessary"}
REASONS = {"missing_scope", "dynamic_binding", "incomplete_reference_routes", "insufficient_effect_semantics"}


def fixtures():
    paths = sorted(DATA.glob("fixtures_*.jsonl"))
    assert len(paths) == 3, "Phase5 extraction truth must be frozen before evaluation"
    return [json.loads(line) for p in paths for line in p.read_text(encoding="utf-8").splitlines()]


def cases():
    path = DATA / "reasoning_cases.jsonl"
    assert path.is_file(), "Phase5 reasoning truth must be frozen before evaluation"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def span(files, item):
    lines = files[item["file"]].splitlines()
    assert 1 <= item["line_start"] <= item["line_end"] <= len(lines)
    return "\n".join(lines[item["line_start"] - 1:item["line_end"]])


def test_new_extraction_families_are_disjoint_and_source_grounded():
    rows = fixtures()
    assert len(rows) == 48
    assert len({r["id"] for r in rows}) == 48
    family_counts = Counter(r["family"] for r in rows)
    assert len(family_counts) == 24 and set(family_counts.values()) == {2}
    old = {json.loads(line)["family"] for p in (ROOT / "data" / "phase4").glob("fixtures_*.jsonl") for line in p.read_text(encoding="utf-8").splitlines()}
    assert not old & set(family_counts)
    splits = defaultdict(set)
    for row in rows:
        splits[row["family"]].add(row["split"])
        assert row["extractor_outputs_seen"] is False
        assert row["source_executed"] is False
        assert row["construction_rationale"]
        for key in ("expected_effects", "expected_non_actions", "expected_uncertainties"):
            for item in row[key]:
                assert span(row["files"], item) == item["evidence"]
        for e in row["expected_effects"]:
            assert e["resource"] is not None or e["resource_status"] == "unknown"
            assert e["grammar_status"] in {"supported", "deliberately_unresolved", "unsupported"}
            assert e["authorization_source"] is False
    assert all(len(s) == 1 for s in splits.values())
    assert set(r["split"] for r in rows) == {"dev", "validation", "heldout"}
    assert any(r["expected_non_actions"] and not r["expected_effects"] for r in rows)
    assert any(r["expected_uncertainties"] for r in rows)


def test_reasoning_truth_has_independent_spans_opaque_ids_and_matched_contexts():
    rows = cases()
    assert len(rows) == 18
    assert len({r["family"] for r in rows}) == 18
    assert Counter(r["split"] for r in rows) == {"dev": 6, "validation": 6, "heldout": 6}
    all_types = set()
    unknown_reasons = set()
    for row in rows:
        assert row["truth_origin"] == "independent_literal_author"
        assert row["source_execution"] == "not_performed"
        public, private = row["public"], row["private"]
        nodes = {n["id"]: n for n in public["canonical_nodes"]}
        assert len(nodes) == len(public["canonical_nodes"])
        scored = {k for k, n in nodes.items() if n["candidate"]}
        assert 2 <= len(scored) <= 4
        assert set(public["contexts"]) == {"allow", "deny", "missing"}
        for n in nodes.values():
            assert re.fullmatch(r"n[0-9]{3}", n["id"])
            assert span(public["files"], n["provenance"]) == n["source_excerpt"]
        for edge in private["oracle_edges"]:
            assert edge["source"] in nodes and edge["target"] in nodes
            assert edge["source"] != edge["target"]
            assert edge["type"] in {"DATA", "CONDITION", "CALL"}
            all_types.add(edge["type"])
            assert edge["rationale"]
            for s in edge["source_spans"]:
                assert span(public["files"], s) == s["evidence"]
        for context, truths in private["truth"].items():
            assert set(truths) == scored
            for node_id, truth in truths.items():
                assert set(truth["labels"]) == LABELS
                assert set(truth["labels"].values()) <= {"yes", "no", "unknown"}
                dimensions = {u["dimension"] for u in truth["unknowns"]}
                assert dimensions == {k for k, v in truth["labels"].items() if v == "unknown"}
                for u in truth["unknowns"]:
                    assert u["reason"] in REASONS
                    assert u["missing_evidence"] and u["next_action"] and u["justified"]
                    unknown_reasons.add(u["reason"])
                assert truth["finite_intervention"]["necessary"] == truth["labels"]["implementation_necessary"]
                assert isinstance(truth["strict_manual_ablation"]["valid"], bool)
    assert all_types == {"DATA", "CONDITION", "CALL"}
    assert unknown_reasons == REASONS


def test_public_prompt_has_no_private_route_plans_or_labels():
    forbidden = {"truth", "oracle_edges", "satisfies_goal", "goal_satisfied", "implementation_necessary", "task_necessary", "authorized", "strict_manual_ablation", "finite_intervention", "successful_plans"}
    def keys(v):
        if isinstance(v, dict):
            for k, child in v.items():
                yield k
                yield from keys(child)
        elif isinstance(v, list):
            for child in v:
                yield from keys(child)
    for row in cases():
        assert not forbidden.intersection(keys(row["public"]))
        assert "canonical_nodes" in row["public"]
        assert row["public"]["reference_route_summary"]


def test_finite_reference_witnesses_support_literal_truth_without_vacuity():
    for row in cases():
        p = row["private"]
        model = p["finite_model"]
        successes = [r for r in model["permitted_reference_routes"] if r["satisfies_goal"]]
        assert successes
        for truth in p["truth"].values():
            for cid, t in truth.items():
                label = t["labels"]["task_necessary"]
                if label == "yes":
                    assert model["task_routes_closed"]
                    assert all(cid in r["effects"] for r in successes)
                elif label == "no":
                    assert any(cid not in r["effects"] for r in successes)
                else:
                    assert not model["task_routes_closed"] or model.get("unresolved_route_binding")


def test_frozen_hashes_match_documented_manifest():
    document = (ROOT / "docs" / "phase5_truth.md").read_text(encoding="utf-8")
    for path in sorted(DATA.glob("fixtures_*.jsonl")) + [DATA / "reasoning_cases.jsonl"]:
        assert path.name in document
        assert hashlib.sha256(path.read_bytes()).hexdigest() in document


def test_sources_parse_and_frozen_writer_cannot_replace_evidence(tmp_path):
    import pytest
    builder = runpy.run_path(str(ROOT / "scripts" / "build_fixtures_phase5.py"))
    assert builder["build_reasoning"]() == cases()
    assert sorted(builder["build_extraction"](), key=lambda r: r["id"]) == sorted(fixtures(), key=lambda r: r["id"])
    for row in cases():
        ast.parse(row["public"]["files"]["workflow.py"])
    path = tmp_path / "freeze.jsonl"
    builder["freeze"](path, [{"id":"first"}])
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        builder["freeze"](path, [{"id":"replacement"}])
    assert path.read_bytes() == before


def test_preacquisition_scope_amendment_preserves_source_and_changes_one_exact_grant():
    path = DATA / "reasoning_cases_v2.jsonl"
    assert path.is_file(), "The pre-acquisition exact-scope amendment must be frozen separately"
    amended = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    original = cases()
    assert len(amended) == len(original)
    for before, after in zip(original, amended):
        for key in ("files", "goal", "inputs", "canonical_nodes", "reference_route_summary", "finite_semantics"):
            assert before["public"][key] == after["public"][key]
        assert before["private"]["oracle_edges"] == after["private"]["oracle_edges"]
        assert before["private"]["finite_model"] == after["private"]["finite_model"]
        for context in ("allow", "missing"):
            assert before["public"]["contexts"][context] == after["public"]["contexts"][context]
            assert before["private"]["truth"][context] == after["private"]["truth"][context]
        change = after["private"]["scope_amendment"]
        target = change["candidate_id"]
        denied = after["private"]["truth"]["deny"]
        assert [cid for cid, truth in denied.items() if truth["labels"]["authorized"] == "no"] == [target]
        allow_rules = after["public"]["contexts"]["allow"]["grant"]["rules"]
        deny_rules = after["public"]["contexts"]["deny"]["grant"]["rules"]
        assert len(allow_rules) == len(deny_rules)
        assert sum(a != b for a, b in zip(allow_rules, deny_rules)) == 1
        for node in after["public"]["canonical_nodes"]:
            if not node["candidate"] or node["claim"]["resource"] is None:
                continue
            matched = any(all(node["claim"].get(key) == value for key, value in rule.items()) for rule in deny_rules)
            assert denied[node["id"]]["labels"]["authorized"] == ("yes" if matched else "no")
        for cid, truth in denied.items():
            if cid != target:
                assert truth == after["private"]["truth"]["allow"][cid]
            for dimension in ("action_valid", "implementation_necessary", "task_necessary"):
                assert truth["labels"][dimension] == before["private"]["truth"]["deny"][cid]["labels"][dimension]
    doc = (ROOT / "docs" / "phase5_truth.md").read_text(encoding="utf-8")
    assert hashlib.sha256(path.read_bytes()).hexdigest() in doc

"""Independent review witnesses; synthetic local inputs and no API access."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from tsg import runtime_v6, truth_v6
from tsg.protocol_v6 import payloads


def script(name):
    location = str(Path(__file__).resolve().parents[1] / "scripts")
    if location not in sys.path:
        sys.path.insert(0, location)
    return importlib.import_module(name)


def fixture():
    ast = {"version": 1, "steps": [
        {"id": "read", "kind": "effect", "op": "read", "resource": "input", "out": "text"},
        {"id": "write", "kind": "effect", "op": "write", "resource": "out", "value": {"var": "text"}},
    ], "functions": {}}
    alternate = {"version": 1, "steps": [
        {"id": "alternate", "kind": "effect", "op": "write", "resource": "out", "value": "ok"}
    ], "functions": {}}
    return {"case_id": "review", "family": "review", "split": "dev", "program": ast,
            "source": "```tsg-workflow\n" + json.dumps(ast) + "\n```\n",
            "routes": [alternate], "worlds": [{"files": {"input": "ok"},
                "grants": [["read", "input"], ["write", "out"]]}],
            "goal": {"files": {"out": "ok"}}, "catalog_closed": True}


def test_actual_parser_graph_reaches_protocol_without_private_labels():
    c = fixture()
    c["private"] = {"answer": "PRIVATE_SENTINEL"}
    c["truth"] = {"answer": "PRIVATE_SENTINEL"}
    ast = runtime_v6.parse_source(c["source"])
    views = payloads(c, runtime_v6.candidates(ast), runtime_v6.edges(ast))
    for text in views.values():
        assert "PRIVATE_SENTINEL" not in text
        public = json.loads(text)
        assert "program" not in public and "case_id" not in public
        assert public["candidate_ids"] == ["read", "write"]
    assert json.loads(views["graph"])["attachment"]["edges"] == [
        {"source": "read", "target": "write", "type": "data"}]


def test_missing_else_is_rejected_by_both_language_validators():
    malformed = {"version": 1, "steps": [
        {"id": "branch", "kind": "if", "eq": [1, 1], "then": []}], "functions": {}}
    source = "```tsg-workflow\n" + json.dumps(malformed) + "\n```\n"
    with pytest.raises(ValueError):
        truth_v6.static_sites(malformed)
    with pytest.raises(ValueError):
        runtime_v6.parse_source(source)


def test_differential_projection_detects_authorization_only_mutant():
    experiment = script("experiment_phase6")
    c = fixture()
    correct = truth_v6.run(c["program"], c["worlds"][0], c["goal"])
    broken = deepcopy(correct)
    broken["trace"][0]["authorized"] = False
    assert experiment.semantic_projection(correct) != experiment.semantic_projection(broken)


def test_differential_evaluates_alternate_routes_and_interventions(monkeypatch):
    experiment = script("experiment_phase6")
    c = fixture()
    captured = {}
    monkeypatch.setattr(experiment, "cases", lambda: [c])
    monkeypatch.setattr(experiment, "immutable", lambda path, data: captured.update({Path(path).name: data}))
    result = experiment.differential()
    rows = [json.loads(line) for line in captured["differential.jsonl"].decode().splitlines()]
    assert {(row["route_index"], row["suppress"]) for row in rows} == {
        (0, None), (0, "read"), (0, "write"), (1, None), (1, "alternate")}
    assert result["differential"] == result["equal"] == 5


def test_recovery_preserves_budget_and_stops_ambiguous_effects():
    c = fixture()
    c["program"] = {"PRIVATE": "wrong AST must be ignored"}
    c["truth"] = {"authorization": "yes"}
    for mode in runtime_v6.MODES:
        out = runtime_v6.execute(c, mode, fault="ambiguous_after", quota=4)
        assert out["attempts"] == 1 and out["charged_calls"] == 2
        assert out["ambiguous_stop"] and not out["authorized_goal"]
        assert out["duplicate_effects"] == out["unauthorized_effects"] == 0
        assert out["remaining_quota"] == 2


def test_summary_keeps_runner_failures_in_the_denominator():
    analysis = script("analyze_phase6")
    rows = [{"mode": "search", "runner_status": "error", "exception": "synthetic"},
            {"mode": "search", "runner_status": "completed", "result": {
                "goal": True, "authorized_goal": True, "charged_calls": 1, "attempts": 1}}]
    summary = analysis.summarize_execution(rows, ["mode"])[0]
    assert summary["n"] == 2 and summary["completed"] == 1
    assert summary["authorized_goal"] == 1


def test_summary_preserves_recovered_model_denials_and_ambiguous_stops():
    analysis = script("analyze_phase6")
    c = fixture()
    recovered = runtime_v6.execute(c, "checkpoint", allowed_ids=[])
    ambiguous = runtime_v6.execute(c, "checkpoint", fault="ambiguous_after")
    rows = [{"mode": "checkpoint", "runner_status": "completed", "initial_legal_route": True,
             "protocol_valid": True, "result": result} for result in (recovered, ambiguous)]
    summary = analysis.summarize_execution(rows, ["mode"])[0]
    assert summary["n"] == 2 and summary["authorized_goal"] == 1
    assert summary["recovered_success"] == summary["route_bypass"] == 1
    assert summary["ambiguous_stops"] == 1
    assert summary["stage_failures"] == {"model_gate": 2, "ambiguous_outcome": 1}


def test_full_analysis_keeps_a_recovery_runner_error(monkeypatch):
    analysis = script("analyze_phase6")
    c = fixture()
    rows = []
    for grant in ("supplied", "undergrant"):
        for quota in (4, 16):
            for fault in ("none", "transient_before", "known_after", "ambiguous_after"):
                for mode in ("checkpoint", "search"):
                    rows.append({"case_id": c["case_id"], "family": c["family"],
                        "grant_condition": grant, "quota": quota, "fault": fault, "mode": mode,
                        "runner_status": "completed", "result": {
                            "authorized_goal": False, "charged_calls": 0, "duplicate_effects": 0}})
    rows[1].pop("result")
    rows[1].update(runner_status="error", exception="synthetic review failure")
    def read(path):
        path = Path(path)
        if path.name == "truth.jsonl":
            return [truth_v6.evaluate_case(c)]
        if path.parent.name == "recovery":
            return rows
        return []
    captured = {}
    monkeypatch.setattr(analysis, "cases", lambda: [c])
    monkeypatch.setattr(analysis, "read_rows", read)
    monkeypatch.setattr(analysis, "immutable", lambda path, data: captured.update({Path(path).name: data}))
    analysis.main()
    summary = json.loads(captured["summary.json"])
    assert summary["recovery_conditions"] == 32
    assert sum(row["n"] for row in summary["recovery"]) == 32


def test_dispatch_reuses_saved_result_and_never_retries_an_orphan(tmp_path):
    campaign = script("run_phase6")
    api = tmp_path / "api"
    job = {"job_id": "synthetic", "expected_request_hash": "synthetic-hash"}
    sends = []
    def invoke():
        sends.append(True)
        return {"request_hash": job["expected_request_hash"], "status": "transport_error", "text": ""}
    first = campaign.dispatch_once(job, api, invoke)
    second = campaign.dispatch_once(job, api, invoke)
    assert first == second and len(sends) == 1
    (api / "raw" / "synthetic-hash.json").unlink()
    orphan = campaign.dispatch_once(job, api, invoke)
    assert orphan["status"] == "interrupted_unknown" and len(sends) == 1


def test_budget_inheritance_is_an_exact_unchanged_prefix(tmp_path, monkeypatch):
    campaign = script("run_phase6")
    original = (campaign.ROOT / "results/phase5/api/budget.jsonl").read_bytes()
    source = tmp_path / "results/phase5/api/budget.jsonl"
    source.parent.mkdir(parents=True)
    source.write_bytes(original)
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    budget, first = campaign.initialize()
    inherited_total = budget.total_cost
    reservation = budget.reserve("gpt-4.1-mini", 10, 10)
    budget.settle(reservation, {})
    fresh, second = campaign.initialize()
    assert first == second
    assert fresh.total_cost > inherited_total
    assert fresh.entries[reservation]["status"] == "unknown_usage"
    assert (tmp_path / "results/phase6/api/budget.jsonl").read_bytes().startswith(original)
    assert source.read_bytes() == original


def test_challenge_cached_job_must_match_frozen_request(tmp_path, monkeypatch):
    campaign = script("run_phase6_challenge")
    monkeypatch.setattr(campaign, "OUT", tmp_path)
    job = {"job_id": "review-cached", "expected_request_hash": "correct-request"}
    monkeypatch.setattr(campaign, "prepare", lambda: ([job], SimpleNamespace(total_cost=0)))
    monkeypatch.setattr(campaign, "load_key", lambda _: None)
    monkeypatch.setattr(campaign, "ClientV3", lambda *args: None)
    cached = tmp_path / "api/jobs/review-cached.json"
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({"job_id": job["job_id"], "request_hash": "wrong-request",
                                 "raw_status": "completed", "parsed": {"protocol_valid": True}}))
    with pytest.raises(ValueError, match="MISMATCH"):
        campaign.collect(None)

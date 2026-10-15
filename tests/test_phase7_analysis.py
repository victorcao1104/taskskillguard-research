"""Hand-calculated analysis examples; no study outcomes are loaded here."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


AXES = ("authorization", "current_route_required", "catalog_required")


def truth(cid="case", family="family", values=("not_applicable", "unknown", "yes")):
    return {"case_id": cid, "family": family, "split": "heldout",
            "labels": [{"id": "s1", **dict(zip(AXES, values)),
                        "reasons": {"authorization": ["inactive"]}}], "worlds": []}


def observation(view, values, *, cid="case", family="family", valid=True, replicate=0, certificate=None):
    row = {"job_id": f"{cid}-{view}-{replicate}", "case_id": cid,
           "family": family, "split": "heldout", "model": "fixture-model",
           "view": view, "replicate": replicate, "raw_status": "completed",
           "usage": {"input_tokens": 10, "output_tokens": 4},
           "parsed": {"protocol_valid": valid, "by_id": {"s1": dict(zip(AXES, values))}}}
    if certificate is not None:
        row["certificate"] = certificate
    return row


def metric(summary, view, axis="authorization", space="typed"):
    return next(r for r in summary["metrics"] if r["split"] == "heldout"
                and r["view"] == view and r["axis"] == axis and r["label_space"] == space)


def test_collapsed_comparison_does_not_award_protocol_failure_or_typed_b0_credit():
    from tsg.analysis_v7 import analyze
    rows = [observation("B0", ("unknown", "unknown", "yes")),
            observation("B1", ("unknown", "unknown", "yes")),
            observation("B2", ("not_applicable", "unknown", "yes"), valid=False)]
    report = analyze([truth()], rows)
    summary = report["summary"]
    assert not any(r["view"] == "B0" and r["label_space"] == "typed" for r in summary["metrics"])
    assert metric(summary, "B0", space="collapsed")["accuracy"] == 1
    assert metric(summary, "B1")["accuracy"] == 0
    assert metric(summary, "B1")["false_unknown"] == 1
    assert metric(summary, "B1")["confusion"] == {"not_applicable": {"unknown": 1}}
    assert metric(summary, "B2")["missing"] == 1
    assert metric(summary, "B2", "current_route_required")["correct_unknown"] == 0
    assert metric(summary, "B2", "current_route_required")["unknown_recall"] == 0
    assert summary["main_protocol_valid"] == 2
    contrast = next(r for r in summary["representation_comparisons"]
                    if r["split"] == "heldout" and r["axis"] == "authorization"
                    and r["contrast"] == "B1-B0")
    assert contrast["estimate"] == 0
    assert contrast["label_space"] == "collapsed"


def test_family_bootstrap_balances_families_and_is_repeatable():
    from tsg.analysis_v7 import paired_interval
    rows = [{"family": "large", "difference": 1} for _ in range(20)]
    rows += [{"family": "small", "difference": -1}]
    result = paired_interval(rows)
    assert result["estimate"] == 0
    assert result["interval95"] == [-1, 1]
    assert result["families"] == 2
    assert result["conditions"] == 21
    assert result["draws"] == 10000 and result["seed"] == 7007
    assert result == paired_interval(list(reversed(rows)))


def test_accuracy_pairs_weight_cases_before_families_and_report_missing_views():
    from tsg.analysis_v7 import analyze
    large = truth("large", values=("yes", "yes", "yes"))
    large["labels"].append({"id": "s2", **dict(zip(AXES, ("yes", "yes", "yes")))})
    small = truth("small", values=("yes", "yes", "yes"))
    rows = [observation("B0", ("no", "no", "no"), cid="large"),
            observation("B1", ("yes", "yes", "yes"), cid="large"),
            observation("B0", ("yes", "yes", "yes"), cid="small"),
            observation("B1", ("no", "no", "no"), cid="small")]
    rows[0]["parsed"]["by_id"]["s2"] = dict(zip(AXES, ("no", "no", "no")))
    rows[1]["parsed"]["by_id"]["s2"] = dict(zip(AXES, ("yes", "yes", "yes")))
    report = analyze([large, small], rows)
    comparison = next(r for r in report["summary"]["representation_comparisons"]
                      if r["split"] == "heldout" and r["axis"] == "authorization" and r["contrast"] == "B1-B0")
    assert comparison["estimate"] == 0
    assert comparison["conditions"] == 2 and comparison["families"] == 1
    missing = next(r for r in report["summary"]["representation_comparisons"]
                   if r["split"] == "heldout" and r["axis"] == "authorization" and r["contrast"] == "B2-B1"
                   and r["label_space"] == "typed")
    assert missing["unmatched_baseline"] == 2
    assert missing["estimate"] is None


def test_usage_costs_are_explicit_conservative_bounds_with_missing_coverage():
    from tsg.analysis_v7 import analyze
    rows = [observation("B1", ("yes", "unknown", "yes")),
            observation("B1", ("yes", "unknown", "yes"), cid="other")]
    rows[0]["usage_cost_upper_usd"] = 0.003
    report = analyze([truth(), truth("other")], rows)
    usage = next(r for r in report["summary"]["usage"] if r["split"] == "heldout" and r["population"] == "main")
    assert usage["usage_cost_upper_usd"] == 0.003
    assert usage["cost_known"] == 1 and usage["conditions"] == 2
    assert "actual_cost_usd" not in usage


def test_certificate_coverage_and_repeat_agreement_do_not_hide_rejections():
    from tsg.analysis_v7 import analyze
    accepted = {"accepted": True, "accepted_ids": ["s1"], "errors": {}, "execution_count": 3}
    rejected = {"accepted": False, "accepted_ids": [], "errors": {"s1": ["world_evidence"]}, "execution_count": 3}
    rows = [observation("B2", ("not_applicable", "unknown", "yes"), certificate=accepted),
            observation("B2", ("not_applicable", "unknown", "yes"), replicate=1, certificate=rejected),
            observation("B2", ("not_applicable", "unknown", "yes"), replicate=2, valid=False, certificate=rejected),
            observation("B2", ("yes", "unknown", "yes"), cid="other", certificate=accepted)]
    rows[3]["certificate"] = {"accepted": True, "accepted_ids": ["s1"], "errors": {}}
    report = analyze([truth(), truth("other")], rows)
    cert = next(r for r in report["summary"]["certificates"] if r["split"] == "heldout")
    assert cert["main_conditions"] == 2 and cert["accepted_conditions"] == 2
    assert cert["condition_coverage"] == 1
    assert cert["selective_condition_accuracy"] == 0.5
    assert cert["incorrectly_accepted_conditions"] == 1
    assert cert["checker_execution_count"] == 3
    assert cert["checker_execution_count_known"] == 1
    repeat = report["summary"]["repeats"][0]
    assert repeat["conditions"] == 3 and repeat["valid_conditions"] == 2
    assert repeat["all_valid"] is False and repeat["identical"] is False
    assert repeat["pairwise_agreement"] == pytest.approx(1 / 3)
    assert report["summary"]["all_conditions"] == 4
    assert report["summary"]["main_conditions"] == 2


def execution(policy, *, selector="first_feasible", success=False, calls=4, triggered=False,
              cid="case", condition=None, pipeline=None):
    row = {"condition_id": condition or f"{cid}-{policy}-{selector}", "case_id": cid,
           "family": "family", "split": "heldout", "world_index": 0, "quota": 8,
           "selector": selector, "policy": policy, "fault": "transient_before",
           "result": {"goal": success, "authorized_goal": success, "charged_calls": calls,
                      "attempts": 2, "planner_steps": 6, "simulated_effects": 2,
                      "unauthorized_effects": 0, "duplicate_effects": 0,
                      "route_bypass": success, "failure_reason": None if success else "no_feasible_route",
                      "fault_diagnostics": {"fault_triggered": triggered, "injected_fault_count": int(triggered),
                                            "scheduled_fault_count": 1, "schedule_completed": triggered},
                      "trace": []}}
    if pipeline:
        row.update(model="fixture-model", view="B2", pipeline=pipeline, replicate=0)
    return row


def test_recovery_pairs_match_world_quota_and_report_untriggered_faults_and_failures():
    from tsg.analysis_v7 import analyze
    rows = [execution("legacy"), execution("safe_retry", success=True, calls=3, triggered=True)]
    unmatched = execution("legacy", cid="unmatched", calls=9)
    unmatched["world_index"] = 1
    rows.append(unmatched)
    report = analyze([], [], rows)
    summary = report["summary"]
    grouped = next(r for r in summary["recovery"] if r["split"] == "heldout" and r["policy"] == "legacy")
    assert grouped["conditions"] == 2 and grouped["authorized_goal"] == 0
    assert grouped["fault_not_triggered"] == 2
    assert grouped["failures"] == {"no_feasible_route": 2}
    success = next(r for r in summary["recovery_pairs"] if r["split"] == "heldout"
                   and r["contrast"] == "safe_retry-legacy" and r["metric"] == "authorized_goal")
    assert success["estimate"] == 1 and success["conditions"] == 1
    assert success["unmatched_baseline"] == 1 and success["unmatched_treatment"] == 0
    cost = next(r for r in summary["recovery_pairs"] if r["split"] == "heldout"
                and r["contrast"] == "safe_retry-legacy" and r["metric"] == "charged_calls"
                and r["population"] == "all_pairs")
    assert cost["estimate"] == -1
    assert len(report["execution_failures"]) == 2


def test_integrated_pipelines_are_kept_separate_and_catalog_bypass_is_explicit():
    from tsg.analysis_v7 import analyze
    rows = [execution("safe_retry", success=True, calls=2, pipeline="raw", condition="raw"),
            execution("safe_retry", success=True, calls=3, pipeline="certified", condition="certified")]
    rows[1]["certificate_accepted"] = False
    rows[1]["allowed_ids"] = []
    report = analyze([], [], integration_rows=rows)
    grouped = [r for r in report["summary"]["integrated"] if r["split"] == "heldout"]
    assert len(grouped) == 2
    certified = next(r for r in grouped if r["pipeline"] == "certified")
    assert certified["route_bypass_success"] == 1
    assert certified["success_with_empty_original_gate"] == 1
    assert certified["authorized_goal"] == 1
    assert certified["unauthorized_effects"] == 0


def test_missing_label_is_not_unknown_and_duplicate_conditions_are_rejected():
    from tsg.analysis_v7 import analyze
    row = observation("B1", ("not_applicable", "unknown", "yes"))
    del row["parsed"]["by_id"]["s1"]["current_route_required"]
    result = analyze([truth()], [row])
    assert metric(result["summary"], "B1", "current_route_required")["missing"] == 1
    assert metric(result["summary"], "B1", "current_route_required")["correct_unknown"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        analyze([truth()], [row, row])


def test_cli_reads_only_available_inputs_and_refuses_to_overwrite_evidence(tmp_path):
    project = Path(__file__).resolve().parents[1]
    inputs = tmp_path / "results" / "phase7"
    (inputs / "semantics").mkdir(parents=True)
    (inputs / "api").mkdir()
    (inputs / "semantics" / "truth.jsonl").write_text(json.dumps(truth()) + "\n", encoding="utf-8")
    path = inputs / "api" / "observations.jsonl"
    path.write_text(json.dumps(observation("B1", ("not_applicable", "unknown", "yes"))) + "\n", encoding="utf-8")
    command = [sys.executable, str(project / "scripts" / "analyze_phase7.py"), "--root", str(tmp_path)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    summary_path = inputs / "analysis" / "summary.json"
    saved = summary_path.read_bytes()
    summary = json.loads(saved)
    assert summary["main_conditions"] == 1
    assert summary["input_manifest"]["recovery"]["present"] is False
    assert summary["input_manifest"]["observations"]["rows"] == 1
    assert subprocess.run(command, capture_output=True).returncode == 0
    path.write_text("", encoding="utf-8")
    changed = subprocess.run(command, capture_output=True, text=True)
    assert changed.returncode != 0
    assert "IMMUTABLE_MISMATCH" in changed.stderr
    assert summary_path.read_bytes() == saved

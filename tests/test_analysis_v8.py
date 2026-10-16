"""Synthetic tests for prospective Phase 8 estimands and denominator integrity."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("analyze_phase8", Path(__file__).resolve().parents[1]/"scripts/analyze_phase8.py")
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)


def truth(cid="c", family="f", labels=("yes", "unknown")):
    sites = [{"id": str(i), **dict(zip(a.AXES, (label, label, label)))} for i, label in enumerate(labels)]
    facts = [{"id": s["id"], "occurred": True, "all_occurrences_authorized": True,
              "suppressed_success": False, "avoiding_routes": []} for s in sites]
    return {"case_id": cid, "family": family, "split": "heldout", "labels": sites,
            "worlds": [{"index": 0, "baseline": {"goal": True}, "legal_route_indices": [0], "labels": facts}]}


def obs(t, view="D", rep=0):
    return {**{k: t[k] for k in ("case_id", "family", "split")}, "model": "toy", "view": view,
            "replicate": rep, "raw_status": "completed", "raw_ref": "toy.json",
            "parsed": {"protocol_valid": True, "by_id": {r["id"]: dict(r) for r in t["labels"]},
                       "prediction": a.expected_facts(t) if view == "F" else {"judgments": deepcopy(t["labels"])}},
            "usage": {"input_tokens": 10, "output_tokens": 2}, "usage_cost_upper_usd": .01,
            "tool_executions": 3 if view == "T" else 0}


def execution(cid, family, policy, ok, calls, planning=0, pipeline=None):
    row = {"case_id": cid, "family": family, "split": "heldout", "world_index": 0, "quota": 16,
           "fault": "none", "policy": policy, "condition_id": cid+policy+str(pipeline), "allowed_ids": [],
           "runner_status": "completed", "result": {"authorized_goal": ok, "charged_calls": calls,
           "planner_steps": planning, "simulated_effects": planning, "unauthorized_effects": 0,
           "duplicate_effects": 0, "failure_reason": None if ok else "no_feasible_route", "trace": []}}
    if pipeline is not None: row["pipeline"] = pipeline
    return row


class AnalysisTests(unittest.TestCase):
    def test_no_argument_entrypoint_calls_artifact_loader(self):
        with patch.object(a, "main", return_value={"summary": {"sentinel": True}}) as loader:
            self.assertEqual(a.analyze(), {"sentinel": True})
            loader.assert_called_once_with([])

    def analyze(self, ts, observations, **kwargs):
        return a.analyze(ts, observations, models=("toy",), draws=100, **kwargs)

    def test_missing_primary_and_invalid_retained_in_full_confusion(self):
        t = truth()
        row = obs(t)
        row["parsed"]["by_id"]["1"]["authorization"] = "not_applicable"
        report = self.analyze([t], [row])
        self.assertEqual(report["summary"]["primary_expected"], 3)
        self.assertEqual(report["summary"]["primary_received"], 1)
        metrics = report["summary"]["metrics"]
        direct = next(r for r in metrics if r["view"] == "D" and r["axis"] == "authorization")
        missing = next(r for r in metrics if r["view"] == "F" and r["axis"] == "authorization")
        self.assertEqual(direct["false_not_applicable"], 1)
        self.assertEqual(direct["true_unknown"], 1)
        self.assertEqual(direct["unknown_recall"], 0)
        self.assertEqual(missing["total"], 2)
        self.assertEqual(missing["invalid"], 2)
        self.assertEqual(set(missing["confusion"]), set(a.LABELS))
        self.assertEqual(set(missing["confusion"]["yes"]), {*a.LABELS, "invalid"})

    def test_family_bootstrap_is_not_candidate_or_case_pseudoreplication(self):
        rows = [{"family": "large", "difference": 1} for _ in range(100)] + [{"family": "small", "difference": -1}]
        value = a.paired_interval(rows)
        self.assertEqual(value["estimate"], 0)
        self.assertEqual(value["families"], 2)
        self.assertEqual(value["pairs"], 101)
        self.assertEqual(value["interval95"], [-1, 1])
        self.assertEqual(value, a.paired_interval(rows))
        self.assertIsNone(a.paired_interval([])["estimate"])

    def test_factor_global_denominators_not_repeated_per_candidate(self):
        t = truth(labels=("yes", "yes", "yes"))
        row = obs(t, "F")
        row["parsed"]["prediction"]["worlds"][0]["baseline_success"] = False
        report = self.analyze([t], [row])
        f = report["summary"]["facts"][0]
        self.assertEqual(f["fields"]["baseline_success"]["total"], 1)
        self.assertEqual(f["fields"]["baseline_success"]["wrong"], 1)
        self.assertEqual(f["fields"]["occurred"]["total"], 3)
        self.assertEqual(f["full_fact_accepted"], 0)
        self.assertIsNone(f["label_accuracy_given_full_correct_facts"]["authorization"]["accuracy"])

    def test_full_fact_acceptance_conditional_accuracy_and_tool_residual(self):
        t = truth()
        f, tool = obs(t, "F"), obs(t, "T")
        tool["parsed"]["by_id"]["0"]["authorization"] = "no"
        report = self.analyze([t], [f, tool])
        self.assertEqual(report["summary"]["facts"][0]["full_fact_accepted"], 1)
        self.assertEqual(report["summary"]["facts"][0]["label_accuracy_given_full_correct_facts"]["authorization"]["accuracy"], 1)
        residual = next(r for r in report["summary"]["tool_label_residuals"] if r["axis"] == "authorization")
        self.assertEqual(residual["residual_errors"], 1)

    def test_repeats_labels_and_facts_separate_invalid_never_stable(self):
        t = truth()
        rows = [obs(t, "F", rep) for rep in range(3)]
        rows[2]["parsed"]["prediction"]["worlds"][0]["sites"][0]["suppressed_success"] = True
        output = a.repeat_summary([t], rows)[0]
        self.assertTrue(output["identical_full_labels"])
        self.assertFalse(output["identical_full_facts"])
        for r in rows: r["parsed"]["protocol_valid"] = False
        output = a.repeat_summary([t], rows)[0]
        self.assertFalse(output["identical_full_labels"])
        self.assertFalse(output["identical_full_facts"])

    def test_exact_case_requires_all_three_axes(self):
        t = truth()
        row = obs(t)
        row["parsed"]["by_id"]["0"]["catalog_required"] = "no"
        report = self.analyze([t], [row])
        direct = next(r for r in report["case_scores"] if r["view"] == "D")
        self.assertFalse(direct["exact"])
        self.assertEqual(direct["correct"]["authorization"], direct["total"])

    def test_usage_reads_nested_details_and_exposes_known_denominators(self):
        row = obs(truth())
        row["usage"].update(input_tokens_details={"cached_tokens": 4}, output_tokens_details={"reasoning_tokens": 1})
        summary = a.usage_summary([row])[0]
        self.assertEqual(summary["cached_input_tokens"], {"total": 4, "known": 1, "mean": 4})
        self.assertEqual(summary["reasoning_tokens"]["total"], 1)
        self.assertEqual(summary["cost_known"], 1)

    def test_recovery_pairs_preserve_wins_losses_and_both_success_costs(self):
        rows = []
        for cid, fam, ok_a, ok_b, ca, cb in (("win", "a", True, False, 1, 4),
                                           ("loss", "b", False, True, 1, 3),
                                           ("both", "b", True, True, 2, 5)):
            rows.extend([execution(cid, fam, "cost_equal", ok_a, ca, 8), execution(cid, fam, "priority_equal", ok_b, cb, 2)])
        summaries, details = a.execution_pairs(rows, 100, 8008)
        s = next(r for r in summaries if r["contrast"] == "cost_equal-priority_equal")
        self.assertEqual((s["success_wins"], s["success_losses"], s["both_success"]), (1, 1, 1))
        self.assertEqual(s["charged_calls"]["both_success"]["estimate"], -3)
        self.assertEqual(s["planner_steps"]["both_success"]["estimate"], 6)
        self.assertEqual(s["success"]["estimate"], .25)
        self.assertEqual(s["success"]["positive_families"], 1)
        self.assertEqual(s["success"]["negative_families"], 1)

    def test_initial_feasibility_uses_grants_receipts_and_quota(self):
        def effect(sid, value, key=None):
            return {"id": sid, "kind": "effect", "op": "write", "resource": "/x", "value": value, **({"key": key} if key else {})}
        good = {"version": 1, "steps": [effect("a", "ok")]}
        conflict = {"version": 1, "steps": [effect("b", "bad", "k"), effect("c", "ok", "k")]}
        case = {"case_id": "c", "routes": [good, conflict], "goal": {"files": {"/x": "ok"}},
                "worlds": [{"files": {}, "grants": [["write", "/x"]]}, {"files": {}, "grants": []}]}
        rows = a.initial_feasibility([case], 16)
        self.assertEqual(rows[0]["initial_feasible_alternative_indices"], [1])
        self.assertEqual(rows[1]["initial_feasible_alternative_count"], 0)
        self.assertEqual(a.initial_feasibility([case], 0)[0]["initial_feasible_alternative_count"], 0)

    def test_gate_sensitive_stratum_requires_control_disagreement(self):
        rows = []
        for cid in ("sensitive", "insensitive"):
            for pipe in ("all_allow", "all_block", "toy:D"):
                rows.append(execution(cid, "f", "cost_equal", cid == "insensitive" or pipe != "all_block", 1, pipeline=pipe))
        feasibility = [{"case_id": cid, "world_index": 0, "quota": 16, "alternative_count": 0,
                        "initial_feasible_alternative_count": 0} for cid in ("sensitive", "insensitive")]
        summary, gates, controls, details = a.integrated_summary(rows, feasibility, [])
        selected = [r for r in summary if r["stratum"] == "gate_sensitive"]
        self.assertEqual(len(selected), 3)
        self.assertTrue(all(r["conditions"] == 1 for r in selected))
        self.assertEqual(controls[0]["gate_sensitive"], 1)

    def test_historical_only_same_regression_cases_and_matching_views(self):
        t = truth(); t["split"] = "regression"
        fresh = [obs(t, "D"), obs(t, "F")]
        old = obs(t); old["view"] = "B1"
        other = obs(truth("unrelated")); other["view"] = "B1"
        result = a.historical_summary([t], fresh, [old, other])
        direct = next(r for r in result if r["contrast"] == "D-historical_B1")
        factor = next(r for r in result if r["contrast"] == "F-historical_B2")
        self.assertEqual(direct["matched_cases"], 1)
        self.assertEqual(factor["matched_cases"], 0)
        self.assertIsNone(factor["historical_accuracy"])

    def test_missing_execution_result_retained_and_duplicate_rejected(self):
        row = execution("c", "f", "cost_equal", True, 1)
        planned = {"meta": {k: v for k, v in row.items() if k not in ("result", "runner_status")}}
        missing = a.complete_execution_rows([], [planned])
        self.assertFalse(a.success(missing[0]))
        self.assertEqual(missing[0]["runner_status"], "missing_result")
        with self.assertRaises(ValueError): a.validate_execution_rows([row, row])

    def test_immutable_bundle_preflights_every_output(self):
        report = self.analyze([truth()], [])
        base = Path(__file__).resolve().parents[1]/"results/phase8/analysis"
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            out = Path(tmp)
            a.write_immutable(out, report)
            before = (out/"summary.json").read_bytes()
            a.write_immutable(out, report)
            changed = deepcopy(report); changed["summary"]["primary_valid"] = 99
            with self.assertRaises(ValueError): a.write_immutable(out, changed)
            self.assertEqual((out/"summary.json").read_bytes(), before)
            self.assertEqual(json.loads(before)["primary_valid"], 0)


if __name__ == "__main__":
    unittest.main()

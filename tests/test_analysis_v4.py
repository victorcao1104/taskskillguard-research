import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_analysis_v4", ROOT / "src/tsg/analysis_v4.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def job(view="table", track="synthetic"):
    payload = {"source": {"w.py": 'print("ok")\n'}, "candidates": [{"id": "opaque"}], "nodes": []}
    if view == "graph":
        payload["edges"] = []
    return {"job_id": f"{track}-{view}", "case_id": "fixture", "family": "familyA", "split": "heldout",
            "model": "test-model", "view": view, "track": track, "context": "test-context",
            "ids": ["opaque"], "candidate_id_mapping": {"original": "opaque"},
            "expected_request_hash": "testhash", "prompt": json.dumps(payload)}


def observation(planned, prediction="yes"):
    judgment = {"candidate_id": "opaque", **dict.fromkeys(A.AXES, prediction), "reason": "test"}
    return {"job_id": planned["job_id"], "request_hash": "testhash", "raw_status": "completed",
            "parsed": {"protocol_valid": True, "diagnostic_codes": [], "judgments": [judgment]}}


class PlannedDenominatorAnalysisTests(unittest.TestCase):
    def test_missing_and_unknown_denominators_and_selective_unknown_errors(self):
        rows = [{"gold": "yes", "prediction": "yes"}, {"gold": "yes", "prediction": None},
                {"gold": "no", "prediction": "unknown"}, {"gold": "unknown", "prediction": "yes"},
                {"gold": "unknown", "prediction": "unknown"},
                {"gold": "no", "prediction": "no", "eligible": False}]
        score = A.metrics(rows)
        self.assertEqual(score["planned_eligible"], 5)
        self.assertEqual(score["excluded_invalid_capability_axes"], 1)
        self.assertEqual(score["exact_accuracy"], 2 / 5)
        self.assertEqual(score["known_truth_accuracy"], 1 / 3)
        self.assertEqual(score["exact_unknown_correct"], 1)
        self.assertEqual(score["unknown_truth_accuracy"], .5)
        self.assertEqual(score["decided_coverage"], 2 / 5)
        self.assertEqual(score["selective_accuracy"], .5)
        self.assertEqual(score["selective_unknown_truth_included"], 1)
        self.assertEqual(score["missing_or_invalid_predictions"], 1)

    def test_protocol_missing_duplicate_ids_and_hash_integrity(self):
        planned = job()
        observed = observation(planned)
        self.assertTrue(A.protocol(planned, observed)["valid"])
        self.assertEqual(A.protocol(planned, None)["status"], "missing")
        duplicate = copy.deepcopy(observed)
        duplicate["parsed"]["judgments"] *= 2
        result = A.protocol(planned, duplicate)
        self.assertFalse(result["valid"])
        self.assertEqual(result["by_id"], {})
        wrong_hash = copy.deepcopy(observed)
        wrong_hash["request_hash"] = "wrong"
        self.assertIn("REQUEST_HASH_MISMATCH", A.protocol(planned, wrong_hash)["diagnostics"])

    def test_truth_mapping_and_invalid_capability_exclusion(self):
        planned = job()
        case = {"case_id": "fixture", "construction_family": "familyA", "split": "heldout",
                "truth": {"original": dict.fromkeys(A.AXES, "no")}}
        rows, statuses = A.score_rows([planned], [], [case])
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(row["eligible"] for row in rows), 1)
        self.assertTrue(all(row["prediction"] is None for row in rows))
        self.assertEqual(statuses[0]["planned_candidates"], 1)
        planned["candidate_id_mapping"] = {"unknown_original": "opaque"}
        with self.assertRaises(ValueError):
            A.score_rows([planned], [], [case])

    def test_graph_control_same_table_and_planned_pairing(self):
        table, graph = job("table"), job("graph")
        self.assertTrue(A.graph_table_control([table, graph])[0]["control_valid"])
        graph["prompt"] = json.dumps({**json.loads(graph["prompt"]), "nodes": [{"id": "extra"}]})
        self.assertFalse(A.graph_table_control([table, graph])[0]["control_valid"])
        base = {"model": "test", "case_id": "fixture", "candidate_id": "original", "axis": "authorized",
                "family": "familyA", "split": "heldout", "gold": "yes", "eligible": True}
        pairs = A.pair_rows([{**base, "view": "table", "prediction": None},
                             {**base, "view": "graph", "prediction": "yes"}])
        self.assertEqual(len(pairs), 1)
        self.assertIsNone(pairs[0]["table_prediction"])
        self.assertEqual(A.clustered_difference(pairs, replicates=20)["difference_graph_minus_table"], 1)

    def test_bootstrap_unit_is_family_not_repeated_candidates(self):
        rows = [{"family": "large", "gold": "yes", "graph_prediction": "yes", "table_prediction": "no"}] * 100
        rows += [{"family": "small", "gold": "yes", "graph_prediction": "no", "table_prediction": "yes"}]
        result = A.clustered_difference(rows)
        self.assertEqual(result, A.clustered_difference(rows))
        self.assertEqual(result["families"], 2)
        self.assertEqual(result["planned_paired_labels"], 101)
        self.assertEqual(result["resampling_unit"], "construction_family")
        self.assertEqual(result["replicates"], 2000)
        self.assertEqual(result["ci95_percentile"], [-1., 1.])
        self.assertEqual(result["family_macro_difference"], 0)
        self.assertAlmostEqual(result["difference_graph_minus_table"], 99 / 101)
        self.assertTrue(result["low_power"])

    def test_real_agreement_is_descriptive_and_counts_missing_pair(self):
        jobs = [job(view, "real") for view in ("raw", "table", "graph")]
        observations = [observation(jobs[0]), observation(jobs[1])]
        result = A.real_descriptive(jobs, observations)
        self.assertTrue(all(row["semantic_accuracy_available"] is False for row in result["by_group"]))
        pair = next(row for row in result["matched_agreement"]
                    if row["left"] == "table" and row["right"] == "graph" and row["axis"] == "action_valid")
        self.assertEqual(pair["planned_pairs"], 1)
        self.assertEqual(pair["both_available"], 0)
        self.assertEqual(pair["agreement_planned"], 0)
        self.assertIsNone(pair["agreement_both_available"])

    def test_discovery_counts_exact_anchors_without_semantic_credit(self):
        planned = job("raw", "discovery")
        observed = observation(planned)
        action = {"file": "w.py", "line_start": 1, "line_end": 1, "excerpt": 'print("ok")'}
        observed["parsed"] = {"protocol_valid": True, "diagnostic_codes": [],
                              "prediction": {"actions": [action, action]},
                              "actions": [action, {**action, "excerpt": "wrong"}]}
        result = A.discovery_summary([planned], [observed])
        self.assertFalse(result["semantic_accuracy_available"])
        self.assertEqual(result["by_model"][0]["source_anchored_actions"], 1)
        self.assertEqual(result["by_model"][0]["proposed_actions"], 2)

    def test_replay_authorized_goal_requires_observed_effects_and_ceiling(self):
        rule = {"operation": "network.post", "resource": "https://sink.invalid/", "origin": "public"}
        case = {"case_id": "case", "authorization": [rule], "candidate": rule}
        jobs = [{"run_id": str(i), "arm": "enforcement", "case": case, "contract": "overbroad",
                 "ceiling": False, "lease_state": "full", "route": "original"} for i in range(4)]
        effect = {**rule, "id": "candidate", "planned": True, "reached": True, "executed": True}
        runs = [{"run_id": "0", "GoalSat": True, "CorePres": True, "status": "executed", "planned_effects": []},
                {"run_id": "1", "GoalSat": True, "CorePres": True, "status": "executed", "planned_effects": [effect]},
                {"run_id": "2", "GoalSat": True, "CorePres": True, "status": "executed",
                 "planned_effects": [{**effect, "origin": "private"}]}]
        result = A.replay_analysis({"jobs": jobs}, runs, [])
        overall = result["overall"]
        self.assertEqual(overall["planned_runs"], 4)
        self.assertEqual(overall["missing_runs"], 1)
        self.assertEqual(overall["goal"], 3)
        self.assertEqual(overall["authorized_goal"], 1)
        self.assertEqual(overall["zero_execution"], 1)
        self.assertEqual(overall["observed_authorized_effects_only"], 1)
        self.assertEqual(overall["unauthorized_effects"], 1)
        self.assertEqual(overall["authorized_goal_rate_planned"], .25)

    def test_full_grid_required_and_partial_publication_makes_no_outputs(self):
        planned = job()
        with self.assertRaises(ValueError):
            A.require_complete_grid([planned], [], expected_jobs=1)
        with self.assertRaises(ValueError):
            A.require_complete_grid([planned], [observation(planned)] * 2, expected_jobs=1)
        A.require_complete_grid([planned], [observation(planned)], expected_jobs=1)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            inputs = root / "results/phase4/acquisition"
            inputs.mkdir(parents=True)
            (inputs / "jobs.jsonl").write_text(json.dumps(planned) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                A.publish(root)
            self.assertFalse((root / "results/phase4/analysis").exists())


if __name__ == "__main__":
    unittest.main()

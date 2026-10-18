"""Behavioral checks for frozen, candidate-independent validation diagnostics."""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ValidationBoundaryTests(unittest.TestCase):
    def test_evaluator_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("rm15.validation_study"))

    def test_check_uses_actual_result_and_requires_no_stop(self):
        from rm15.runtime import base_world, execute, make_task
        from rm15.validation_study import judge_execution
        task = make_task("unit", {}, oracle_fn=lambda t, d: {"out": 3})
        correct = execute("result = {'out': 3}", base_world({}), task)
        wrong = execute("result = {'out': 4}", base_world({}), task)
        missing = execute("other = {'out': 3}", base_world({}), task)
        stopped = execute("result = {'out': 3}\nstop('NO')", base_world({}), task)
        self.assertTrue(judge_execution(correct, {"out": 3})["passed"])
        self.assertFalse(judge_execution(wrong, {"out": 3})["passed"])
        self.assertFalse(judge_execution(missing, {"out": 3})["passed"])
        self.assertFalse(judge_execution(stopped, {"out": 3})["passed"])

    def test_logical_budget_exhaustion_is_not_reported_as_mutant_detection(self):
        from rm15.runtime import base_world, execute, make_task
        from rm15.validation_study import judge_execution
        task = make_task("unit", {}, oracle_fn=lambda t, d: {"out": 3})
        task["max_steps"] = 1
        exhausted = execute("result = {'out': 3}", base_world({}), task)
        verdict = judge_execution(exhausted, {"out": 3})
        self.assertFalse(verdict["passed"])
        self.assertTrue(verdict["resource_exhausted"])
        self.assertFalse(verdict["defect_detected"])

    def test_boolean_output_cannot_impersonate_integer_output(self):
        from rm15.runtime import base_world, execute, make_task
        from rm15.validation_study import judge_execution
        task = make_task("unit", {}, oracle_fn=lambda t, d: {"out": [1]})
        wrong = execute("result = {'out': [True]}", base_world({}), task)
        self.assertFalse(judge_execution(wrong, {"out": [1]})["passed"])

    def test_budget_prefix_cannot_use_a_failure_beyond_its_work_limit(self):
        from rm15.validation_study import suite_status
        trials = [
            {"passed": True, "defect_detected": False, "resource_exhausted": False,
             "charged_steps": 10},
            {"passed": False, "defect_detected": True, "resource_exhausted": False,
             "charged_steps": 20},
        ]
        short = suite_status(trials, budget=15)
        self.assertFalse(short["detected"])
        self.assertFalse(short["accepted"])
        self.assertFalse(short["complete"])
        self.assertEqual(short["steps"], 15)
        full = suite_status(trials, budget=30)
        self.assertTrue(full["detected"])
        self.assertEqual(full["first_detection"], {"executions": 2, "steps": 30})
        self.assertEqual(full["steps"], 30)

    def test_freeze_refuses_to_silently_replace_a_changed_definition(self):
        import tempfile
        from rm15.validation_study import freeze_definition
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            folder = Path(directory)
            freeze_definition(folder, {"protocol": "a", "source_hashes": {}})
            before = (folder / "frozen_definition.json").read_bytes()
            freeze_definition(folder, {"protocol": "a", "source_hashes": {}})
            with self.assertRaises(RuntimeError):
                freeze_definition(folder, {"protocol": "b", "source_hashes": {}})
            self.assertEqual(before, (folder / "frozen_definition.json").read_bytes())

    def test_summary_retains_identity_mutants_in_all_mutants_denominator(self):
        from rm15.validation_study import aggregate
        passed = {"accepted": True, "detected": False, "complete": True,
                  "resource_or_incomplete": False, "executions": 4, "steps": 40,
                  "first_detection": None}
        failed = {**passed, "accepted": False, "detected": True,
                  "first_detection": {"executions": 1, "steps": 10}}
        rows = [
            {"kind": "mutant", "empirically_non_equivalent": True,
             "validation": {"random": failed}, "final_failed": True},
            {"kind": "mutant", "empirically_non_equivalent": False,
             "validation": {"random": passed}, "final_failed": False},
            {"kind": "correct", "empirically_non_equivalent": False,
             "validation": {"random": passed}, "final_failed": False},
        ]
        result = aggregate(rows, "random")
        self.assertEqual(result["all_mutants"]["denominator"], 2)
        self.assertEqual(result["all_mutants"]["detection_rate"], 0.5)
        self.assertEqual(result["empirically_non_equivalent"]["denominator"], 1)
        self.assertEqual(result["correct_controls"]["false_rejections"], 0)

    def test_final_partition_report_does_not_merge_composed_and_base_failures(self):
        from rm15.validation_study import final_partition_summary
        rows = [{"kind": "mutant", "final_partitions": {
                    "final_base": {"failed": False, "semantic_failures": 0, "resource_failures": 0},
                    "final_composed": {"failed": True, "semantic_failures": 1, "resource_failures": 0},
                    "final_scale": {"failed": False, "semantic_failures": 0, "resource_failures": 0}},
                 "validation": {s: {"accepted": True} for s in ("random", "larger_input", "targeted")}}]
        result = final_partition_summary(rows)
        self.assertEqual(result["final_base"]["mutants_with_failure"], 0)
        self.assertEqual(result["final_composed"]["mutants_with_failure"], 1)
        self.assertEqual(result["final_composed"]["accepted_final_failure"]["random"]["failures"], 1)

    def test_correct_programs_pass_shared_validation_and_final_cases(self):
        from rm15.tasks import TEMPLATES, solver
        from rm15.validation_study import case_inventory, evaluate_program
        self.assertEqual(len(TEMPLATES), 16)
        for template in TEMPLATES:
            inventory = case_inventory(template)
            for cases in inventory.values():
                for case in cases:
                    outcome = evaluate_program(solver(template), template, case)
                    self.assertTrue(outcome["passed"], (template, case["case_id"], outcome))

    def test_candidate_execution_does_not_change_shared_test_inputs(self):
        from rm15.tasks import TEMPLATES, solver
        from rm15.validation_study import case_inventory, evaluate_program, digest, mutants
        template = TEMPLATES[0]
        inventory = case_inventory(template)
        before = digest(inventory)
        programs = [solver(template), mutants(template)[0]["code"]]
        seen = []
        for code in programs:
            these_cases = []
            for strategy in ("random", "larger_input", "targeted"):
                for case in inventory[strategy]:
                    these_cases.append((case["case_id"], case["data_sha256"]))
                    evaluate_program(code, template, case)
            seen.append(these_cases)
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(digest(inventory), before)
        self.assertEqual(len(inventory["random"]), 4)
        self.assertEqual(len(inventory["larger_input"]), 4)
        self.assertEqual(len(inventory["targeted"]), 4)

    def test_mutant_population_keeps_all_six_families_for_every_template(self):
        from rm15.tasks import TEMPLATES
        from rm15.validation_study import mutants
        for template in TEMPLATES:
            population = mutants(template)
            self.assertEqual(len(population), 6)
            self.assertEqual(len({m["family"] for m in population}), 6)
            self.assertTrue(all("applicable" in m and "code_sha256" in m for m in population))


if __name__ == "__main__":
    unittest.main()

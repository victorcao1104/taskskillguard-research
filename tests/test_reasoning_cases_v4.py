"""Audit independently authored labels and exact source spans; execute no fixture."""
import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_reasoning_cases_v4",
                                            ROOT / "src/tsg/reasoning_cases_v4.py")
FIXTURES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURES)


def authorize(claim, grant):
    """Separate contract evaluator: conjunction within a rule, union across rules."""
    resource_domain = claim.get("resource_domain")
    if claim["resource"] is None and not resource_domain:
        return "unknown"
    resources = resource_domain or [claim["resource"]]
    decisions = []
    for resource in resources:
        matched = any(all(claim.get(key) == value for key, value in rule.items()
                          if key != "resource") and rule.get("resource") == resource
                      for rule in grant["rules"])
        decisions.append("yes" if matched else
                         "unknown" if grant["mode"] == "underspecified" else "no")
    return decisions[0] if len(set(decisions)) == 1 else "unknown"


def necessary(cid, model, kind):
    key = "plans" if kind == "task" else "implementation_plans"
    closed = "task_plans_closed" if kind == "task" else "implementation_plans_closed"
    if not model[closed] or not model[key]:
        return "unknown"
    successes = [plan for plan in model[key] if plan["satisfies_goal"]]
    if not successes:
        return "unknown"
    return "yes" if all(cid in plan["effects"] for plan in successes) else "no"


class IndependentReasoningCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = FIXTURES.load_reasoning_cases()

    def test_frozen_file_equals_author_specification(self):
        self.assertEqual(self.cases, FIXTURES.build_reasoning_cases())
        self.assertEqual(len(self.cases), 24)
        self.assertEqual(len({c["case_id"] for c in self.cases}), 24)

    def test_family_disjoint_splits_and_compact_sources(self):
        families = Counter(c["construction_family"] for c in self.cases)
        self.assertEqual(len(families), 8)
        self.assertEqual(set(families.values()), {3})
        seen = {}
        for case in self.cases:
            family = case["construction_family"]
            self.assertEqual(case["split"], FIXTURES.FAMILY_SPLITS[family])
            seen.setdefault(family, set()).add(case["split"])
            self.assertTrue(3 <= len(case["candidates"]) <= 5)
            for text in case["files"].values():
                self.assertLess(len(text.splitlines()), 30)
                self.assertNotIn(".com", text)
        self.assertTrue(all(len(splits) == 1 for splits in seen.values()))
        self.assertEqual(Counter(c["split"] for c in self.cases),
                         {"dev": 9, "validation": 6, "heldout": 9})

    def test_every_candidate_has_exact_source_span_and_explicit_labels(self):
        operations = {"file.read", "file.write", "file.delete", "network.get",
                      "network.post", "command.exec", "environment.read"}
        for case in self.cases:
            ids = [candidate["id"] for candidate in case["candidates"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(set(ids), set(case["truth"]))
            for candidate in case["candidates"]:
                with self.subTest(case=case["case_id"], candidate=candidate["id"]):
                    provenance = candidate["provenance"]
                    lines = case["files"][provenance["file"]].splitlines()
                    start, end = provenance["line_start"], provenance["line_end"]
                    self.assertTrue(1 <= start <= end <= len(lines))
                    self.assertEqual("\n".join(lines[start - 1:end]), candidate["source_excerpt"])
                    self.assertIn(candidate["claim"]["operation"], operations)
                    self.assertIn(candidate["claim"]["resource_status"], {"resolved", "dynamic"})
                    labels = case["truth"][candidate["id"]]
                    self.assertEqual(set(labels), set(FIXTURES.LABELS))
                    self.assertTrue(set(labels.values()) <= {"yes", "no", "unknown"})

    def test_no_label_leakage_into_trusted_task_context(self):
        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)
        for case in self.cases:
            self.assertFalse(set(FIXTURES.LABELS) & set(keys(case["task_context"])))
            self.assertEqual(case["source_execution"], "not_performed")
            self.assertEqual(case["truth_origin"], "independent_author")

    def test_contract_and_finite_plan_labels(self):
        for case in self.cases:
            ctx = case["task_context"]
            for candidate in case["candidates"]:
                cid = candidate["id"]
                truth = case["truth"][cid]
                with self.subTest(case=case["case_id"], candidate=cid):
                    if truth["action_valid"] == "no":
                        self.assertEqual(truth, dict.fromkeys(FIXTURES.LABELS, "no"))
                        continue
                    self.assertEqual(authorize(candidate["claim"], ctx["grant"]), truth["authorized"])
                    self.assertEqual(necessary(cid, ctx["finite_model"], "task"), truth["task_necessary"])
                    self.assertEqual(necessary(cid, ctx["finite_model"], "implementation"),
                                     truth["implementation_necessary"])

    def test_task_plans_reference_existing_effects_and_obey_ceiling(self):
        for case in self.cases:
            ctx = case["task_context"]
            effects = {candidate["id"]: candidate["claim"] for candidate in case["candidates"]}
            effects.update(ctx.get("finite_reference_effects", {}))
            for plan in ctx["finite_model"]["plans"] or []:
                self.assertTrue(plan["satisfies_goal"])
                for effect in plan["effects"]:
                    self.assertIn(effect, effects)
                    self.assertEqual(authorize(effects[effect], ctx["grant"]), "yes")
            for plan in ctx["finite_model"]["implementation_plans"] or []:
                self.assertTrue(set(plan["effects"]) <= set(effects))

    def test_capabilities_decoys_and_meaningful_axes(self):
        by_id = {case["case_id"]: case for case in self.cases}
        self.assertEqual(by_id["optional_allowed-1"]["truth"]["notify"]["authorized"], "yes")
        self.assertEqual(by_id["optional_allowed-2"]["truth"]["notify"]["authorized"], "no")
        for i in range(1, 4):
            gate = by_id[f"artificial_gate-{i}"]["truth"]["gate"]
            self.assertEqual((gate["implementation_necessary"], gate["task_necessary"]), ("yes", "no"))
            uninvoked = by_id[f"uninvoked_capability-{i}"]["truth"]["backup"]
            self.assertEqual(uninvoked, {"action_valid": "yes", "authorized": "no",
                                        "implementation_necessary": "no", "task_necessary": "no"})
            decoys = by_id[f"structural_decoys-{i}"]["truth"]
            self.assertEqual(decoys["metadata"]["action_valid"], "no")
            self.assertEqual(decoys["negation"]["action_valid"], "no")
        self.assertEqual([by_id[f"payload_ceiling-{i}"]["truth"]["send"]["authorized"]
                          for i in range(1, 4)], ["yes", "no", "no"])
        self.assertEqual([by_id[f"dynamic_target-{i}"]["truth"]["send"]["authorized"]
                          for i in range(1, 4)], ["unknown", "yes", "no"])
        self.assertEqual(by_id["dependency_chain-3"]["truth"]["deliver"]["implementation_necessary"], "unknown")

    def test_frozen_writer_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "fixtures.jsonl"
            FIXTURES.freeze_reasoning_cases(path)
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                FIXTURES.freeze_reasoning_cases(path)
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(len([json.loads(line) for line in before.splitlines()]), 24)


if __name__ == "__main__":
    unittest.main()

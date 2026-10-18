"""Focused enforcement and paired-history checks for the supplementary campaign."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))
if importlib.util.find_spec("strict_state"):
    import strict_state as strict
else:
    strict = None

from rm15.tasks import TEMPLATES, instance, oracle, solver
from rm15.recovery import assess, snapshot


EFFECTS = """
cached = saved('result')
if valid(cached):
    result = cached
else:
    result = compute()
for artifact in goal['artifacts']:
    path = '/output/' + artifact
    if not exists(path):
        write(path, result[artifact])
for stage in goal['events']:
    state_of_event = receipt(stage)
    if state_of_event == 'unknown':
        if stage in permissions['status']:
            state_of_event = 'success' if status(stage) == 'sent' else 'failure'
        else:
            stop('UNRESOLVED_EFFECT')
    if state_of_event != 'success':
        if stage in permissions['event']:
            event(stage, result)
        else:
            send('report', 'team', result)
if exists('/tmp/cache'):
    delete('/tmp/cache')
"""


class Availability(unittest.TestCase):
    def test_strict_campaign_exists(self):
        self.assertIsNotNone(strict, "Supplementary strict state implementation is missing")


@unittest.skipIf(strict is None, "strict module is not yet implemented")
class StrictStateTests(unittest.TestCase):
    def test_direct_input_read_is_blocked_but_fixed_compute_reads_current_input(self):
        template = TEMPLATES[0]
        for seed in (101, 202, 1004):
            data = instance(template, seed)
            initial = snapshot(template, data, "invalid_cache")
            denied = strict.run_program({"compute": "", "effects": solver(template)},
                                        initial["world"], initial["task"], level="A", fixed_compute=solver(template))
            self.assertEqual(denied["stop"]["code"], "FIXED_COMPUTE_REQUIRED")
            self.assertEqual(denied["cost"]["compute_invocations"], 0)
            allowed = strict.run_program({"compute": "raise ignored", "effects": EFFECTS},
                                         initial["world"], initial["task"], level="A", fixed_compute=solver(template))
            self.assertIsNone(allowed["stop"])
            self.assertEqual(allowed["cost"]["compute_invocations"], 1)
            self.assertEqual(allowed["world"]["env"]["result"]["value"], oracle(template, data))
            self.assertEqual(initial["task"]["grants"]["read"][0], "/input/data")
            self.assertNotIn("/input/data", allowed["world"]["env"]["permissions"]["value"]["read"])

    def test_guessing_complete_correct_output_without_required_compute_fails(self):
        template = TEMPLATES[0]
        data = instance(template, 201)
        initial = snapshot(template, data, "invalid_cache")
        guess = "result = " + repr(oracle(template, data)) + "\n" + EFFECTS[EFFECTS.index("for artifact"):]
        result = strict.run_program({"compute": "", "effects": guess}, initial["world"], initial["task"],
                                    level="A", fixed_compute=solver(template))
        score = assess(result, initial["world"], initial["task"])
        self.assertTrue(score["ordinary_complete"])
        self.assertFalse(score["safe_complete"])
        self.assertEqual(result["stop"]["code"], "FIXED_COMPUTE_REQUIRED")

    def test_all_templates_share_fixed_implementation_across_histories_and_levels(self):
        program = {"compute": "read('/private/token')", "effects": EFFECTS}
        for template in TEMPLATES:
            data = instance(template, 202)
            for history in strict.HISTORIES:
                for committed in (True, False) if history.startswith("unknown") else (True,):
                    for level in ("A", "B", "C", "D"):
                        with self.subTest(template=template, history=history, committed=committed, level=level):
                            initial = snapshot(template, data, history, committed=committed)
                            result = strict.run_program(program, initial["world"], initial["task"],
                                                        level=level, fixed_compute=solver(template))
                            score = assess(result, initial["world"], initial["task"])
                            self.assertTrue(score["safe_complete"] if score["feasible"] else score["correct_stop"])
                            self.assertEqual(result["cost"]["compute_invocations"], int(history == "invalid_cache"))

    def test_hidden_commit_and_secret_are_absent_from_effects_state(self):
        template = TEMPLATES[-1]
        for level in ("A", "B", "C"):
            views = []
            for committed, secret in ((True, "A"), (False, "A"), (True, "B"), (False, "B")):
                initial = snapshot(template, instance(template, 201), "unknown_query", secret, committed)
                result = strict.run_program({"compute": "", "effects": ""}, initial["world"], initial["task"],
                                            level=level, fixed_compute=solver(template))
                views.append({name: result["world"]["env"][name] for name in ("state", "permissions") +
                              (("support",) if level in ("B", "C") else ())})
            self.assertTrue(all(view == views[0] for view in views))

    def test_boundary_stop_without_compute_remains_correct(self):
        template = TEMPLATES[0]
        initial = snapshot(template, instance(template, 201), "unknown_no_query")
        result = strict.run_program({"compute": "", "effects": "stop('UNRESOLVED_EFFECT')"},
                                    initial["world"], initial["task"], level="A", fixed_compute=solver(template))
        self.assertTrue(assess(result, initial["world"], initial["task"])["correct_stop"])
        self.assertEqual(result["cost"]["compute_invocations"], 0)

    def test_compute_does_not_export_input_or_solver_local_bindings(self):
        template = TEMPLATES[0]
        initial = snapshot(template, instance(template, 201), "invalid_cache")
        for level in ("A", "B", "C"):
            result = strict.run_program({"compute": "", "effects": "result=compute()\nx=data"},
                                        initial["world"], initial["task"], level=level, fixed_compute=solver(template))
            self.assertEqual(result["stop"]["code"], "MISSING_VARIABLE")
            self.assertEqual(result["stop"]["variable"], "data")
            self.assertNotIn("groups", result["world"]["env"])
            self.assertNotIn("rows", result["world"]["env"])
        automatic = strict.run_program({"compute": "", "effects": ""}, initial["world"], initial["task"],
                                       level="D", fixed_compute=solver(template))
        self.assertIsNone(automatic["stop"])
        self.assertNotIn("data", automatic["world"]["env"])
        self.assertNotIn("groups", automatic["world"]["env"])
        self.assertEqual(automatic["world"]["env"]["result"]["value"], oracle(template, instance(template, 201)))

    def test_compute_preserves_caller_bindings_and_security_control(self):
        from rm15.runtime import V
        template = TEMPLATES[0]
        initial = snapshot(template, instance(template, 201), "invalid_cache")
        machine = strict.StrictMachine(initial["world"], initial["task"], fixed_compute=solver(template))
        machine.put("data", V("old caller value"))
        machine.put("marker", V(17))
        machine.control = frozenset({"secret"})
        result = machine.call("compute", [])
        self.assertEqual(set(machine.w["env"]), {"data", "marker", "result"})
        self.assertEqual(machine.w["env"]["data"]["value"], "old caller value")
        self.assertEqual(machine.w["env"]["marker"]["value"], 17)
        self.assertEqual(result.value, oracle(template, instance(template, 201)))
        self.assertIn("secret", machine.control)
        self.assertIn("secret", result.labels)

    def test_evaluation_keeps_all_secret_pairs_and_unknown_worlds(self):
        job = next(job for job in strict.jobs() if job["method"] == "D" and job["history"] == "unknown_query")
        parsed = {"status": "candidate", "program": {"compute": "", "effects": ""}}
        for phase, count in (("validation", 16), ("final", 32), ("scale", 16)):
            result = strict.evaluate(parsed, job, phase)
            self.assertTrue(result["accepted"])
            self.assertEqual(len(result["records"]), count)
            self.assertEqual({record["secret"] for record in result["records"]}, {"A", "B"})
            self.assertEqual({record["committed"] for record in result["records"]}, {True, False})

    def test_grid_budget_and_common_prompt_enforce_same_strict_contract(self):
        grid = strict.jobs()
        self.assertEqual(len(grid), 512)
        self.assertEqual(len({job["id"] for job in grid}), 512)
        self.assertTrue(all(job["id"].startswith("strictstate--") and job["campaign_kind"] == "state" for job in grid))
        self.assertAlmostEqual(strict.maximum_reservation(grid), 8.6016, places=8)
        prompts = [json.loads(strict.payload(next(job for job in grid if job["method"] == level), []))
                   for level in ("A", "B", "C", "D")]
        self.assertTrue(all(obj["strict_execution_contract"] == strict.STRICT_REMINDER for obj in prompts))
        self.assertTrue(all("/input/data" not in obj["effects_permissions"]["read"] for obj in prompts))
        self.assertTrue(all("/input/data" in obj["task"]["grants"]["read"] for obj in prompts))


if __name__ == "__main__":
    unittest.main()

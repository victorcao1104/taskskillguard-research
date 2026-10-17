"""Independent reference tests; deliberately do not import or build fixtures."""

import copy
import unittest

from reference import ReferenceError, run, static_sites


HEADER = "from pathlib import Path\nfrom mock_tools import emit\n"
SINK = "https://reference-test.invalid/accepted"
OTHER = "https://reference-test.invalid/other"


class ReferenceTests(unittest.TestCase):
    def world(self):
        return {"files": {"public": "paper draft", "private": "FICTITIOUS-UNIT-SECRET", "scratch": "old"},
                "grants": [["read", "public"], ["read", "private"], ["write", "out"],
                           ["read", "middle"], ["write", "middle"], ["emit", SINK], ["delete", "scratch"]],
                "readers": {"private": []}}

    def run_code(self, code, goal=None, world=None, suppress=None):
        return run(HEADER + code, "scripts/test.py", world or self.world(), goal or {}, suppress)

    def test_public_transform_send_and_delete_complete(self):
        code = ("data = Path('public').read_text()\n"
                "answer = data.upper() + ' | checked'\n"
                "Path('out').write_text(answer)\n"
                f"emit({SINK!r}, answer)\nPath('scratch').unlink()\n")
        result = self.run_code(code, {"files": {"out": "PAPER DRAFT | checked"}, "absent": ["scratch"],
                                     "emits": [{"resource": SINK, "value": "PAPER DRAFT | checked", "count": 1}],
                                     "preserve": ["public", "private"]})
        self.assertIsNone(result["error"])
        self.assertTrue(result["goal"])
        self.assertTrue(all(e["authorized"] and e["flow_allowed"] for e in result["trace"]))
        self.assertEqual(result["emits"], [{"resource": SINK, "value": "PAPER DRAFT | checked"}])

    def test_upper_concat_cannot_remove_provenance(self):
        result = self.run_code("data = Path('private').read_text()\n"
                               "changed = 'prefix:' + data.upper()\n" + f"emit({SINK!r}, changed)\n")
        event = result["trace"][-1]
        self.assertTrue(event["authorized"])
        self.assertFalse(event["flow_allowed"])
        self.assertEqual(event["origins"], ["private"])
        self.assertEqual(event["value"], "prefix:FICTITIOUS-UNIT-SECRET")

    def test_intermediate_file_preserves_provenance(self):
        result = self.run_code("data = Path('private').read_text()\nPath('middle').write_text(data)\n"
                               "again = Path('middle').read_text()\n" + f"emit({SINK!r}, again)\n")
        self.assertEqual([e["origins"] for e in result["trace"]], [["private"]] * 4)
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_secret_selected_public_resource_preserves_selector_provenance(self):
        world = self.world()
        world["files"]["private"] = "public"
        result = self.run_code("selected = Path('private').read_text()\n"
                               "data = Path(selected + '').read_text()\n"
                               + f"emit({SINK!r}, data)\n", world=world)
        self.assertIsNone(result["error"])
        self.assertEqual(result["trace"][1]["resource"], "public")
        self.assertEqual(result["trace"][1]["value"], "")
        self.assertEqual(result["emits"][0]["value"], "paper draft")
        self.assertEqual(result["trace"][1]["origins"], ["private"])
        self.assertEqual(result["trace"][-1]["origins"], ["private"])
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_replacing_intermediate_file_removes_old_content_label(self):
        result = self.run_code("data = Path('private').read_text()\nPath('middle').write_text(data)\n"
                               "Path('middle').write_text('public replacement')\n"
                               "again = Path('middle').read_text()\n" + f"emit({SINK!r}, again)\n")
        self.assertEqual(result["trace"][-1]["origins"], [])
        self.assertTrue(result["trace"][-1]["flow_allowed"])

    def test_control_labels_assignments_reads_and_nested_branch(self):
        result = self.run_code("gate = Path('private').read_text()\n"
                               "if gate == 'FICTITIOUS-UNIT-SECRET':\n"
                               "    clean = Path('public').read_text()\n"
                               "    marker = 'constant'\n"
                               "    if clean == 'paper draft':\n"
                               "        Path('middle').write_text(marker)\n"
                               "else:\n    marker = 'unused'\n"
                               "again = Path('middle').read_text()\n" + f"emit({SINK!r}, again)\n")
        self.assertEqual(result["trace"][1]["origins"], ["private"])
        self.assertEqual(result["trace"][-1]["origins"], ["private"])
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_pc_label_ends_after_branch(self):
        result = self.run_code("gate = Path('private').read_text()\n"
                               "if gate == 'FICTITIOUS-UNIT-SECRET':\n    value = 'tainted constant'\n"
                               f"emit({SINK!r}, 'independent constant')\n")
        self.assertEqual(result["trace"][-1]["origins"], [])
        self.assertTrue(result["trace"][-1]["flow_allowed"])

    def test_all_contributing_readers_must_allow_sink(self):
        world = self.world()
        world["files"]["second"] = "FICTITIOUS-SECOND"
        world["readers"] = {"private": [SINK], "second": [OTHER]}
        world["grants"].append(["read", "second"])
        result = self.run_code("first = Path('private').read_text()\nsecond = Path('second').read_text()\n"
                               + f"emit({SINK!r}, first + second)\n", world=world)
        self.assertEqual(result["trace"][-1]["origins"], ["private", "second"])
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_authorized_restricted_send_is_allowed(self):
        world = self.world()
        world["readers"]["private"] = [SINK]
        result = self.run_code("data = Path('private').read_text()\n" + f"emit({SINK!r}, data)\n", world=world)
        self.assertTrue(result["trace"][-1]["flow_allowed"])

    def test_unauthorized_effect_is_recorded_and_committed(self):
        result = self.run_code("data = Path('public').read_text()\n" + f"emit({OTHER!r}, data)\n")
        self.assertFalse(result["trace"][-1]["authorized"])
        self.assertTrue(result["trace"][-1]["flow_allowed"])
        self.assertEqual(result["emits"][0]["resource"], OTHER)

    def test_suppress_read_returns_empty_without_intrinsic_label(self):
        code = "data = Path('private').read_text()\n" + f"emit({SINK!r}, data)\n"
        result = self.run_code(code, suppress="scripts/test.py:3")
        self.assertEqual(len(result["trace"]), 1)
        self.assertEqual(result["emits"][0]["value"], "")
        self.assertEqual(result["trace"][0]["origins"], [])

    def test_suppressed_read_under_pc_retains_control_label(self):
        code = ("gate = Path('private').read_text()\n"
                "if gate == 'FICTITIOUS-UNIT-SECRET':\n"
                "    data = Path('public').read_text()\n"
                f"    emit({SINK!r}, data)\n")
        result = self.run_code(code, suppress="scripts/test.py:5")
        self.assertEqual(result["emits"][0]["value"], "")
        self.assertEqual(result["trace"][-1]["origins"], ["private"])
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_original_prerequisite_is_removed_by_read_intervention(self):
        code = ("gate = Path('private').read_text()\n"
                "if gate == 'FICTITIOUS-UNIT-SECRET':\n"
                "    data = Path('public').read_text()\n"
                "    Path('out').write_text(data.upper())\n")
        goal = {"files": {"out": "PAPER DRAFT"}}
        self.assertTrue(self.run_code(code, goal)["goal"])
        self.assertFalse(self.run_code(code, goal, suppress="scripts/test.py:3")["goal"])

    def test_preservation_fails_despite_correct_output(self):
        result = self.run_code("data = Path('public').read_text()\nPath('out').write_text(data.upper())\n"
                               "Path('public').write_text('tampered')\n",
                               {"files": {"out": "PAPER DRAFT"}, "preserve": ["public"]})
        self.assertEqual(result["files"]["out"], "PAPER DRAFT")
        self.assertFalse(result["goal"])
        self.assertFalse(result["trace"][-1]["authorized"])

    def test_goal_requires_exact_emit_count(self):
        code = f"for i in range(3):\n    emit({SINK!r}, 'repeated')\n"
        result = self.run_code(code, {"emits": [{"resource": SINK, "value": "repeated", "count": 1}]})
        self.assertEqual(len(result["emits"]), 3)
        self.assertEqual(len({e["id"] for e in result["trace"]}), 1)
        self.assertFalse(result["goal"])
        self.assertEqual(self.run_code(code, suppress="scripts/test.py:4")["emits"], [])

    def test_trusted_attempt_limit_is_part_of_authorization(self):
        world = self.world()
        world["limits"] = {f"emit|{SINK}": 1}
        code = f"for i in range(2):\n    emit({SINK!r}, 'repeated')\n"
        result = self.run_code(code, world=world)
        self.assertEqual([event["authorized"] for event in result["trace"]], [True, False])
        self.assertTrue(all(event["flow_allowed"] for event in result["trace"]))
        self.assertEqual(len(result["emits"]), 2)

    def test_suppression_does_not_consume_attempt_limit(self):
        world = self.world()
        world["limits"] = {f"emit|{SINK}": 1}
        code = f"emit({SINK!r}, 'suppressed')\nemit({SINK!r}, 'remaining')\n"
        result = self.run_code(code, world=world, suppress="scripts/test.py:3")
        self.assertEqual(len(result["trace"]), 1)
        self.assertTrue(result["trace"][0]["authorized"])

    def test_helper_local_variables_do_not_overwrite_module(self):
        code = ("def helper():\n    value = Path('private').read_text()\n"
                f"    emit({SINK!r}, value)\n"
                "value = Path('public').read_text()\nhelper()\nPath('out').write_text(value)\n")
        result = self.run_code(code, {"files": {"out": "paper draft"}})
        self.assertTrue(result["goal"])
        self.assertFalse(result["trace"][2]["flow_allowed"])
        self.assertEqual(result["trace"][-1]["origins"], [])

    def test_helper_free_variable_uses_module_not_callers_local(self):
        code = (f"def second():\n    emit({SINK!r}, value)\n"
                "def first():\n    value = 'local shadow'\n    second()\n"
                "value = 'module value'\nfirst()\n")
        self.assertEqual(self.run_code(code)["emits"][0]["value"], "module value")

    def test_python_unbound_local_is_error(self):
        code = ("def helper():\n    copied = value\n    value = 'local'\n"
                "value = 'module'\nhelper()\n")
        result = self.run_code(code)
        self.assertTrue(result["error"].startswith("UnboundLocalError:"))
        self.assertFalse(result["goal"])

    def test_static_sites_include_unexecuted_branch_and_helper(self):
        code = ("def unused():\n    Path('private').read_text()\n"
                "if 'a' == 'b':\n    Path('public').read_text()\n"
                "Path('out').write_text('x')\n")
        sites = static_sites(HEADER + code, "scripts/test.py")
        self.assertEqual([s["op"] for s in sites], ["read", "read", "write"])
        self.assertEqual(len(self.run_code(code)["trace"]), 1)

    def test_unsupported_source_is_rejected_before_any_effect(self):
        result = self.run_code("Path('out').write_text('would be early')\nvalue = 'unsupported'.lower()\n")
        self.assertTrue(result["error"].startswith("Unsupported:"))
        self.assertEqual(result["trace"], [])
        self.assertNotIn("out", result["files"])
        with self.assertRaises(ReferenceError):
            static_sites("import subprocess\n", "scripts/test.py")

    def test_recursion_and_nested_functions_are_unsupported(self):
        for code in ("def one():\n    two()\ndef two():\n    one()\none()\n",
                     "def outer():\n    def inner():\n        value = 'x'\nouter()\n"):
            with self.subTest(code=code):
                self.assertTrue(self.run_code(code)["error"].startswith("Unsupported:"))

    def test_loop_index_is_not_a_supported_expression(self):
        for code in ("for index in range(2):\n    value = index\n",
                     "for index in range(2):\n    value = 'x'\ncopy = index\n",
                     "copy = index\nfor index in range(2):\n    value = 'x'\n"):
            with self.subTest(code=code):
                result = self.run_code(code)
                self.assertTrue(result["error"].startswith("Unsupported:"))

    def test_hygiene_prefix_is_reserved_for_variables_and_helpers(self):
        for code in ("__tsg_hidden = 'x'\n", "value = __tsg_hidden\n",
                     "def __tsg_helper():\n    value = 'x'\n",
                     "for __tsg_index in range(2):\n    value = 'x'\n"):
            with self.subTest(code=code):
                self.assertTrue(self.run_code(code)["error"].startswith("Unsupported:"))

    def test_api_names_cannot_be_helper_names(self):
        for name in ("Path", "emit", "range"):
            with self.subTest(name=name):
                code = f"def {name}():\n    value = 'x'\n"
                self.assertTrue(self.run_code(code)["error"].startswith("Unsupported:"))

    def test_module_calls_must_follow_all_helper_declarations(self):
        first = "def first():\n    value = 'first'\n"
        last = "def second():\n    value = 'second'\n"
        for call in ("first()\n", "if 'x' == 'x':\n    first()\n",
                     "for index in range(1):\n    first()\n"):
            with self.subTest(call=call):
                self.assertTrue(self.run_code(first + call + last)["error"].startswith("Unsupported:"))
        self.assertIsNone(self.run_code(first + last + "first()\n")["error"])

    def test_helper_body_may_call_later_declared_acyclic_helper(self):
        code = ("def first():\n    second()\n"
                "def second():\n    Path('out').write_text('finished')\n"
                "first()\n")
        result = self.run_code(code, {"files": {"out": "finished"}})
        self.assertIsNone(result["error"])
        self.assertTrue(result["goal"])

    def test_string_operations_reject_integer_values(self):
        for code in ("value = 1 + 2\n", "number = 2\nvalue = number.upper()\n"):
            with self.subTest(code=code):
                result = self.run_code(code)
                self.assertTrue(result["error"].startswith("TypeError:"))
                self.assertFalse(result["goal"])

    def test_resources_and_payloads_must_be_strings(self):
        for code in ("Path(2).read_text()\n", "Path(True).write_text('x')\n",
                     "Path('out').write_text(3)\n", f"emit({SINK!r}, False)\n",
                     "emit(4, 'x')\n"):
            with self.subTest(code=code):
                result = self.run_code(code)
                self.assertTrue(result["error"].startswith("TypeError:"))
                self.assertEqual(result["trace"], [])
                self.assertFalse(result["goal"])

    def test_read_trace_records_empty_request_but_expression_returns_content(self):
        result = self.run_code("data = Path('public').read_text()\nPath('out').write_text(data)\n",
                               {"files": {"out": "paper draft"}})
        self.assertIsNone(result["error"])
        self.assertTrue(result["goal"])
        self.assertEqual(result["trace"][0]["op"], "read")
        self.assertEqual(result["trace"][0]["value"], "")
        self.assertEqual(result["trace"][1]["value"], "paper draft")

    def test_missing_read_returns_empty_and_records_requested_effect(self):
        result = self.run_code("data = Path('absent').read_text()\nPath('out').write_text(data)\n",
                               {"files": {"out": ""}})
        self.assertIsNone(result["error"])
        self.assertTrue(result["goal"])
        self.assertEqual(result["trace"][0]["resource"], "absent")
        self.assertEqual(result["trace"][0]["value"], "")
        self.assertEqual(result["trace"][0]["origins"], [])
        self.assertFalse(result["trace"][0]["authorized"])
        self.assertNotIn("absent", result["files"])

    def test_missing_read_preserves_resource_expression_and_pc_origins(self):
        world = self.world()
        world["files"]["private"] = "absent"
        code = ("selected = Path('private').read_text()\n"
                "if selected == 'absent':\n"
                "    data = Path(selected).read_text()\n"
                + f"emit({SINK!r}, data)\n")
        result = self.run_code(code, world=world)
        self.assertIsNone(result["error"])
        self.assertEqual(result["emits"][0]["value"], "")
        self.assertEqual(result["trace"][1]["origins"], ["private"])
        self.assertFalse(result["trace"][-1]["flow_allowed"])

    def test_suppress_stage_write_leaves_empty_read_without_resource_error(self):
        code = ("data = Path('public').read_text()\nPath('middle').write_text(data)\n"
                "again = Path('middle').read_text()\nPath('out').write_text(again)\n")
        result = self.run_code(code, {"files": {"out": "paper draft"}}, suppress="scripts/test.py:4")
        self.assertIsNone(result["error"])
        self.assertFalse(result["goal"])
        self.assertNotIn("middle", result["files"])
        self.assertEqual(result["files"]["out"], "")
        self.assertEqual([event["op"] for event in result["trace"]], ["read", "read", "write"])

    def test_missing_delete_is_noop_but_consumes_attempt_limit(self):
        world = self.world()
        world["grants"].append(["delete", "absent"])
        world["limits"] = {"delete|absent": 1}
        before = dict(world["files"])
        result = self.run_code("Path('absent').unlink()\nPath('absent').unlink()\n",
                               {"absent": ["absent"]}, world=world)
        self.assertIsNone(result["error"])
        self.assertTrue(result["goal"])
        self.assertEqual(result["files"], before)
        self.assertEqual([event["op"] for event in result["trace"]], ["delete", "delete"])
        self.assertEqual([event["value"] for event in result["trace"]], ["", ""])
        self.assertEqual([event["authorized"] for event in result["trace"]], [True, False])

    def test_statement_step_bound_includes_helper_call_and_loop_bodies(self):
        code = "def helper():\n    value = 'x'\n" + "helper()\n" * 50
        self.assertIsNone(self.run_code(code)["error"])
        self.assertTrue(self.run_code(code + "helper()\n")["error"].startswith("StepLimit:"))
        nested = ("for a in range(3):\n    for b in range(3):\n"
                  "        for c in range(3):\n            for d in range(3):\n                value = 'x'\n")
        self.assertTrue(self.run_code(nested)["error"].startswith("StepLimit:"))

    def test_inputs_are_not_mutated_by_reference(self):
        world = self.world()
        before = copy.deepcopy(world)
        self.run_code("Path('public').write_text('changed')\n", world=world)
        self.assertEqual(world, before)


if __name__ == "__main__":
    unittest.main()

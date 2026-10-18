"""Hand-derived examples and invariants for the synthetic task definitions."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import unittest

STUDY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDY))
if importlib.util.find_spec("rm15") is not None:
    try:
        from rm15 import tasks
    except ImportError:
        tasks = None
else:
    tasks = None


def run_native(code, data, token="A"):
    reads = []
    def read(path):
        reads.append(path)
        if path == "/private/token":
            return token
        if path != "/input/data":
            raise AssertionError(path)
        return data
    env = {"read": read, "get": lambda d, k, default: d.get(k, default),
           "putmap": lambda d, k, v: dict(d, **{k: v}),
           "keys": lambda d: list(d), "unique": lambda xs: list(dict.fromkeys(xs))}
    exec(code, env)
    return env.get("result"), reads


class Availability(unittest.TestCase):
    def test_benchmarks_are_available(self):
        self.assertIsNotNone(tasks, "The synthetic benchmark module is not implemented")


@unittest.skipIf(tasks is None, "module is not yet implemented")
class OracleExamples(unittest.TestCase):
    def test_aggregation_examples_include_order_overlap_and_boundary(self):
        examples = [
            ("aggregation.group_totals", {"rows": [
                {"id": "b", "group": "x", "qty": 2, "price": 7, "discount": 3},
                {"id": "a", "group": "x", "qty": 1, "price": 4, "discount": 0},
                {"id": "c", "group": "y", "qty": 3, "price": 2, "discount": 1}]},
             {"main": [{"group": "x", "count": 2, "units": 3, "net": 15},
                       {"group": "y", "count": 1, "units": 3, "net": 5}]}),
            ("aggregation.running_balance", {"opening": 5, "rows": [
                {"id": "b", "time": 1, "delta": -8},
                {"id": "c", "time": 2, "delta": 4},
                {"id": "a", "time": 1, "delta": 2}]},
             {"main": {"entries": [{"id": "a", "balance": 7}, {"id": "b", "balance": -1},
                                    {"id": "c", "balance": 3}], "closing": 3, "minimum": -1}}),
            ("aggregation.interval_union", {"rows": [
                {"id": "a", "start": 4, "end": 7}, {"id": "b", "start": 1, "end": 4},
                {"id": "c", "start": 2, "end": 3}, {"id": "d", "start": 9, "end": 11}]},
             {"main": {"segments": [[1, 7], [9, 11]], "covered": 8}}),
            ("aggregation.weighted_histogram", {"bounds": [0, 5, 10], "rows": [
                {"id": "a", "value": -1, "weight": 9}, {"id": "b", "value": 0, "weight": 2},
                {"id": "c", "value": 5, "weight": 3}, {"id": "d", "value": 9, "weight": 4},
                {"id": "e", "value": 10, "weight": 8}]},
             {"main": {"bins": [{"low": 0, "high": 5, "count": 1, "weight": 2},
                                 {"low": 5, "high": 10, "count": 2, "weight": 7}],
                       "outside_count": 2, "outside_weight": 17}}),
        ]
        for template, data, expected in examples:
            with self.subTest(template=template):
                self.assertEqual(tasks.oracle(template, data), expected)

    def test_graph_examples_include_unreachable_isolated_and_ties(self):
        examples = [
            ("graph.shortest_paths", {"nodes": ["d", "a", "c", "b"], "start": "a", "edges": [
                {"u": "a", "v": "b", "weight": 8}, {"u": "a", "v": "c", "weight": 2},
                {"u": "c", "v": "b", "weight": 3}]},
             {"main": [{"id": "a", "distance": 0}, {"id": "b", "distance": 5},
                       {"id": "c", "distance": 2}, {"id": "d", "distance": -1}]}),
            ("graph.components", {"nodes": ["e", "d", "c", "b", "a"], "edges": [
                {"u": "b", "v": "a"}, {"u": "d", "v": "c"}]},
             {"main": [["a", "b"], ["c", "d"], ["e"]]}),
            ("graph.topo_layers", {"nodes": ["d", "c", "b", "a"], "edges": [
                {"u": "a", "v": "c"}, {"u": "b", "v": "c"}, {"u": "c", "v": "d"}]},
             {"main": [["a", "b"], ["c"], ["d"]]}),
            ("graph.triangle_counts", {"nodes": ["d", "c", "b", "a"], "edges": [
                {"u": "a", "v": "b"}, {"u": "a", "v": "c"},
                {"u": "b", "v": "c"}, {"u": "c", "v": "d"}]},
             {"main": {"total": 1, "nodes": [{"id": "a", "triangles": 1}, {"id": "b", "triangles": 1},
                                             {"id": "c", "triangles": 1}, {"id": "d", "triangles": 0}]}}),
        ]
        for template, data, expected in examples:
            with self.subTest(template=template):
                self.assertEqual(tasks.oracle(template, data), expected)

    def test_linked_reports_reconcile_details_to_summary(self):
        examples = [
            ("reports.stock_reconciliation", {"items": [{"id": "b", "opening": 9, "minimum": 3},
                                                         {"id": "a", "opening": 5, "minimum": 2}],
                "rows": [{"id": "m1", "item": "a", "delta": -3}, {"id": "m2", "item": "b", "delta": 2}]},
             {"detail": [{"id": "a", "opening": 5, "change": -3, "closing": 2},
                         {"id": "b", "opening": 9, "change": 2, "closing": 11}],
              "summary": {"opening": 14, "change": -1, "closing": 13, "low_ids": ["a"]}}),
            ("reports.invoice_balances", {"invoices": [{"id": "b", "amount": 10}, {"id": "a", "amount": 20}],
                "rows": [{"id": "p1", "invoice": "b", "amount": 15}, {"id": "p2", "invoice": "a", "amount": 7}]},
             {"detail": [{"id": "a", "amount": 20, "paid": 7, "due": 13, "credit": 0},
                         {"id": "b", "amount": 10, "paid": 15, "due": 0, "credit": 5}],
              "summary": {"amount": 30, "paid": 22, "due": 13, "credit": 5, "unpaid_ids": ["a"]}}),
            ("reports.department_payroll", {"rows": [{"id": "b", "department": "x", "hours": 3, "rate": 4, "bonus": 2},
                {"id": "a", "department": "x", "hours": 2, "rate": 5, "bonus": 0},
                {"id": "c", "department": "y", "hours": 1, "rate": 7, "bonus": 1}]},
             {"detail": [{"id": "a", "department": "x", "pay": 10}, {"id": "b", "department": "x", "pay": 14},
                         {"id": "c", "department": "y", "pay": 8}],
              "summary": [{"department": "x", "count": 2, "pay": 24, "employee_ids": ["a", "b"]},
                          {"department": "y", "count": 1, "pay": 8, "employee_ids": ["c"]}]}),
            ("reports.sensor_audit", {"sensors": [{"id": "x", "low": 2, "high": 6}], "rows": [
                {"id": "c", "sensor": "x", "value": 9}, {"id": "a", "sensor": "x", "value": 2},
                {"id": "b", "sensor": "x", "value": 1}]},
             {"detail": [{"id": "a", "sensor": "x", "value": 2, "bad": 0, "deviation": 0},
                         {"id": "b", "sensor": "x", "value": 1, "bad": 1, "deviation": 1},
                         {"id": "c", "sensor": "x", "value": 9, "bad": 1, "deviation": 3}],
              "summary": [{"sensor": "x", "count": 3, "bad": 2, "deviation": 4, "bad_ids": ["b", "c"]}]}),
        ]
        for template, data, expected in examples:
            with self.subTest(template=template):
                self.assertEqual(tasks.oracle(template, data), expected)

    def test_service_payloads_cover_exact_stock_rounding_ties_and_zero_refund(self):
        examples = [
            ("service.stock_allocation", {"stock": 5, "rows": [{"id": "b", "priority": 2, "qty": 3},
                {"id": "a", "priority": 2, "qty": 2}, {"id": "c", "priority": 1, "qty": 1}]},
             {"main": {"accepted": ["a", "b"], "rejected": ["c"], "remaining": 0}}),
            ("service.invoice_batch", {"rows": [{"id": "b", "qty": 2, "price": 99, "tax_bps": 500},
                                                {"id": "a", "qty": 1, "price": 10, "tax_bps": 0}]},
             {"main": {"invoices": [{"id": "a", "subtotal": 10, "tax": 0, "total": 10},
                                    {"id": "b", "subtotal": 198, "tax": 9, "total": 207}], "total_charge": 217}}),
            ("service.quota_schedule", {"rows": [{"id": "b", "duration": 4, "due": 3},
                                                {"id": "a", "duration": 2, "due": 3}]},
             {"main": {"slots": [{"id": "a", "start": 0, "finish": 2, "late": 0},
                                  {"id": "b", "start": 2, "finish": 6, "late": 3}], "total_late": 3}}),
            ("service.refund_batch", {"rows": [{"id": "c", "paid": 10, "used": 9, "fee": 3},
                {"id": "a", "paid": 20, "used": 5, "fee": 2}, {"id": "b", "paid": 7, "used": 5, "fee": 2}]},
             {"main": {"refunds": [{"id": "a", "amount": 13}], "total_refund": 13}}),
        ]
        for template, data, expected in examples:
            with self.subTest(template=template):
                self.assertEqual(tasks.oracle(template, data), expected)


@unittest.skipIf(tasks is None, "module is not yet implemented")
class GeneratedInvariants(unittest.TestCase):
    def test_catalog_has_four_structures_and_distinct_json_inputs(self):
        counts = {}
        for template in tasks.TEMPLATES:
            kind = tasks.structure(template)
            counts[kind] = counts.get(kind, 0) + 1
            one = tasks.instance(template, 101)
            self.assertEqual(one, tasks.instance(template, 101))
            self.assertNotEqual(one, tasks.instance(template, 102))
            json.dumps(one)
            json.dumps(tasks.oracle(template, one))
            self.assertTrue(tasks.specification(template))
        self.assertEqual(counts, {"aggregation": 4, "graph": 4, "reports": 4, "service": 4})

    def test_solver_matches_oracle_across_sizes_order_relabel_and_decoys(self):
        for template in tasks.TEMPLATES:
            for seed in (101, 104, 201, 1001):
                for scale, transform in ((False, None), (True, None), (False, "order"),
                                         (False, "relabel"), (False, "decoy")):
                    with self.subTest(template=template, seed=seed, scale=scale, transform=transform):
                        data = tasks.instance(template, seed, scale=scale, transform=transform)
                        want = tasks.oracle(template, data)
                        result, reads = run_native(tasks.solver(template), data)
                        self.assertEqual(result, want)
                        self.assertEqual(reads, ["/input/data"])
                        self.assertEqual(set(want), {"summary", "detail"} if tasks.structure(template) == "reports" else {"main"})

    def test_order_and_decoy_transformations_preserve_goal(self):
        for template in tasks.TEMPLATES:
            original = tasks.oracle(template, tasks.instance(template, 202))
            for transform in ("order", "decoy"):
                self.assertEqual(original, tasks.oracle(template, tasks.instance(template, 202, transform=transform)))

    def test_sources_separate_private_gate_from_correct_computation(self):
        for template in tasks.TEMPLATES:
            with self.subTest(template=template):
                data = tasks.instance(template, 101)
                expected = tasks.oracle(template, data)
                intact, reads = run_native(tasks.source(template, "intact"), data)
                self.assertEqual(intact, expected)
                self.assertEqual(reads, ["/private/token", "/input/data"])
                gated, reads = run_native(tasks.source(template, "intact"), data, token="B")
                self.assertIsNone(gated)
                self.assertEqual(reads, ["/private/token"])
                partial, _ = run_native(tasks.source(template, "partial"), data)
                self.assertNotEqual(partial, expected)
                self.assertEqual(tasks.source(template, "absent"), "")
                for level in ("destroyed", "irrelevant"):
                    value, _ = run_native(tasks.source(template, level), data)
                    self.assertNotEqual(value, expected)

    def test_common_transform_recovers_narrow_intact_gate_and_raw_source_is_blocked(self):
        from rm15.recovery import transform_compute
        from rm15.runtime import base_world, execute, make_task
        for template in tasks.TEMPLATES:
            with self.subTest(template=template):
                data = tasks.instance(template, 101)
                task = make_task(template, data)
                raw = execute(tasks.source(template, "intact"), base_world(data), task)
                self.assertEqual(raw["stop"]["code"], "PRIVILEGE")
                self.assertEqual(raw["stop"]["target"], "/private/token")
                transformed = transform_compute(tasks.source(template, "intact"), task)
                outcome = execute(transformed["code"], base_world(data), task)
                self.assertIsNone(outcome["stop"])
                self.assertEqual(outcome["world"]["env"]["result"]["value"], tasks.oracle(template, data))

    def test_solver_language_has_no_host_escape_and_meets_static_limits(self):
        forbidden = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Attribute, ast.While, ast.Try,
                     ast.Set, ast.SetComp, ast.DictComp)
        for template in tasks.TEMPLATES:
            code = tasks.solver(template)
            tree = ast.parse(code)
            self.assertLessEqual(len(code), 16000)
            self.assertLessEqual(sum(1 for _ in ast.walk(tree)), 2048)
            self.assertFalse(any(isinstance(n, forbidden) for n in ast.walk(tree)))
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    self.assertTrue(all(isinstance(t, ast.Name) for t in node.targets))

    def test_shortest_path_unreachable_marker_does_not_cap_valid_distances(self):
        data = {"nodes": ["a", "b", "c"], "start": "a",
                "edges": [{"u": "a", "v": "b", "weight": 1000000}]}
        want = {"main": [{"id": "a", "distance": 0}, {"id": "b", "distance": 1000000},
                         {"id": "c", "distance": -1}]}
        self.assertEqual(tasks.oracle("graph.shortest_paths", data), want)
        self.assertEqual(run_native(tasks.solver("graph.shortest_paths"), data)[0], want)

    def test_bounded_runtime_agreement_on_all_construction_seed_ranges(self):
        from rm15.runtime import base_world, execute, make_task
        def expanded_size(value):
            if isinstance(value, dict):
                return 1 + sum(expanded_size(k) + expanded_size(v) for k, v in value.items())
            if isinstance(value, list):
                return 1 + sum(expanded_size(v) for v in value)
            return 1 + len(value) if isinstance(value, str) else 1
        cases = [(seed, False) for seed in list(range(101, 105)) + list(range(201, 205)) + list(range(1001, 1009))]
        cases += [(seed, True) for seed in range(2001, 2005)]
        for template in tasks.TEMPLATES:
            for seed, scale in cases:
                with self.subTest(template=template, seed=seed, scale=scale):
                    data = tasks.instance(template, seed, scale=scale)
                    expected = tasks.oracle(template, data)
                    outcome = execute(tasks.solver(template), base_world(data), make_task(template, data))
                    self.assertIsNone(outcome["stop"])
                    self.assertEqual(outcome["world"]["env"]["result"]["value"], expected)
                    self.assertLessEqual(outcome["cost"]["steps"], 50000)
                    self.assertLessEqual(expanded_size(data), 1500)
                    self.assertLessEqual(expanded_size(expected), 1500)

    def test_invalid_catalog_keys_fail_clearly(self):
        for method in (tasks.structure, tasks.specification, tasks.solver):
            with self.assertRaises(ValueError):
                method("missing")
        with self.assertRaises(ValueError):
            tasks.source(tasks.TEMPLATES[0], "missing")
        with self.assertRaises(ValueError):
            tasks.instance(tasks.TEMPLATES[0], 101, transform="missing")


if __name__ == "__main__":
    unittest.main()

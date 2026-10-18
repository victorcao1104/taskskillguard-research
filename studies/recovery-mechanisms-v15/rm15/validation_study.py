"""Frozen synthetic computational-validation diagnostics for v15.

Engineered mutants are a diagnostic population, not sampled model errors.
Candidate code executes only in the bounded simulator.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP_LIMIT = 50_000
STRATEGIES = ("random", "larger_input", "targeted")
LOGICAL_BUDGETS = (1_000, 5_000, 20_000, 50_000, 100_000, 200_000)
# Frozen independently of candidate code or outcomes. No mutant is an argument
# to the test generator. Composed transformations are reserved for final checks.
TARGET_TRANSFORMS = (None, "order", "relabel", "decoy")
FINAL_TRANSFORMS = (("order", "relabel"), ("order", "decoy"),
                    ("relabel", "decoy"), ("order", "relabel", "decoy"))
FAMILY_STRATUM = {
    "ordering": "development_known",
    "wrong_arithmetic": "development_known",
    "extra_constraints": "development_known",
    "stale_ids": "held_out_diagnostic",
    "boundary_condition": "held_out_diagnostic",
    "dropped_records": "held_out_diagnostic",
}

RESOURCE_STOPS = {"STEP_BUDGET", "CHECK_BUDGET", "CALL_BUDGET", "VALUE_BOUND",
                  "ITERATION_BOUND", "COMBINATION_BOUND", "AST_BOUND", "CODE_BOUND"}


def judge_execution(execution, expected):
    """Inspect the actual candidate result; a clean stop alone proves nothing."""
    from .runtime import equal_output
    stop = execution["stop"]
    cell = execution["world"]["env"].get("result")
    result_present = cell is not None and "value" in cell
    matches = result_present and equal_output(cell["value"], expected)
    passed = stop is None and matches
    resource = bool(stop and stop.get("code") in RESOURCE_STOPS)
    outcome = ("pass" if passed else "resource_stop" if resource else
               "runtime_stop" if stop else "wrong_result" if result_present else
               "missing_result")
    return {"passed": bool(passed), "result_present": result_present,
            "result_matches": bool(matches), "resource_exhausted": resource,
            "defect_detected": not passed and not resource, "outcome": outcome,
            "stop": stop, "actual_result": cell["value"] if result_present else None}


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def code_digest(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def case_inventory(template):
    """Generate all tests without observing any candidate program or result."""
    from .tasks import instance, oracle

    def case(group, index, seed, scale=False, transform=None):
        data = instance(template, seed, scale=scale, transform=transform)
        expected = oracle(template, data)
        return {"case_id": f"{template}/{group}/{index:02d}", "seed": seed,
                "scale": scale, "transform": transform, "data": data,
                "data_sha256": digest(data), "expected": expected,
                "expected_sha256": digest(expected)}

    return {
        "random": [case("random", i, seed) for i, seed in enumerate(range(201, 205))],
        "larger_input": [case("larger_input", i, seed, scale=True)
                         for i, seed in enumerate(range(201, 205))],
        "targeted": [case("targeted", i, 201, transform=transform)
                     for i, transform in enumerate(TARGET_TRANSFORMS)],
        "independent_final": (
            [case("final_base", i, seed) for i, seed in enumerate(range(1001, 1009))]
            + [case("final_composed", i, seed, transform=FINAL_TRANSFORMS[i % 4])
               for i, seed in enumerate(range(1001, 1009))]
            + [case("final_scale", i, seed, scale=True)
               for i, seed in enumerate(range(2001, 2005))]),
    }


def evaluate_program(code, template, case, step_limit=STEP_LIMIT):
    from .runtime import base_world, execute, make_task
    task = make_task(template, case["data"])
    task["max_steps"] = step_limit
    execution = execute(code, base_world(case["data"]), task)
    verdict = judge_execution(execution, case["expected"])
    # The interpreter increments its tick before refusing an over-budget step.
    # Preserve both counters; refused ticks are not executed logical work.
    cost = {k: v for k, v in execution["cost"].items() if type(v) is int}
    return {**verdict, "case_id": case["case_id"],
            "data_sha256": case["data_sha256"], "cost": cost,
            "charged_steps": min(cost["steps"], step_limit),
            "refused_ticks": max(0, cost["steps"] - step_limit),
            "step_limit": step_limit}


def _insert_after_read(code, snippet):
    tree = ast.parse(code)
    for index, node in enumerate(tree.body):
        if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "data"
                for t in node.targets) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "read"):
            tree.body[index + 1:index + 1] = ast.parse(snippet).body
            return ast.unparse(ast.fix_missing_locations(tree)) + "\n"
    raise ValueError("Solver must bind data from read before computation")


def _operator_mutation(code, family):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if (family == "ordering" and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "sorted"):
            old = ast.unparse(node)
            node.func.id = "list"
            node.keywords = []
            return ast.unparse(tree) + "\n", True, {"before": old, "after": ast.unparse(node)}
        if family == "boundary_condition" and isinstance(node, ast.Compare):
            replacements = {ast.Lt: ast.LtE, ast.LtE: ast.Lt,
                            ast.Gt: ast.GtE, ast.GtE: ast.Gt}
            for index, op in enumerate(node.ops):
                if type(op) in replacements:
                    old = ast.unparse(node)
                    node.ops[index] = replacements[type(op)]()
                    return ast.unparse(tree) + "\n", True, {"before": old, "after": ast.unparse(node)}
    return code, False, {"reason": "No applicable source operator; identity retained in denominator"}


def mutants(template):
    """Six fixed operator families, constructed without executing any mutant.

    Only seed 101 supplies schema and a stale identifier. It is never scored.
    All unmatched operators yield explicitly retained identity mutants.
    """
    from .tasks import instance, solver
    code = solver(template)
    development = instance(template, 101)
    primary = next((key for key in ("rows", "edges", "nodes")
                    if isinstance(development.get(key), list)), None)
    if primary is None:
        raise ValueError(f"No supported record collection for {template}")
    collection = f"data[{primary!r}]"
    out = []

    def add(family, mutated, applicable, detail):
        out.append({"program_id": f"{template}/{family}", "kind": "mutant",
                    "family": family, "stratum": FAMILY_STRATUM[family],
                    "applicable": applicable, "operator": detail,
                    "code": mutated, "code_sha256": code_digest(mutated)})

    for family in ("ordering", "boundary_condition"):
        mutated, applicable, detail = _operator_mutation(code, family)
        add(family, mutated, applicable, detail)

    identifier_collection = "rows" if "rows" in development else "nodes"
    records = development.get(identifier_collection, [])
    stale = (records[0].get("id") if records and isinstance(records[0], dict)
             else records[0] if records else None)
    if stale is not None:
        ref = f"data[{identifier_collection!r}]"
        first = f"putmap({ref}[0], 'id', {stale!r})" if isinstance(records[0], dict) else repr(stale)
        snippet = (f"if len({ref}) > 0:\n"
                   f"    data = putmap(data, {identifier_collection!r}, [{first}] + {ref}[1:])\n")
        add("stale_ids", _insert_after_read(code, snippet), True,
            {"description": "Replace first identifier with seed-101 cached identifier",
             "collection": identifier_collection, "stale_identifier": stale})
    else:
        add("stale_ids", code, False, {"reason": "No identifier; identity retained"})

    numeric_field = None
    records = development[primary]
    if records and isinstance(records[0], dict):
        numeric_field = next((key for key in ("delta", "amount", "weight", "qty", "value",
                "hours", "paid", "duration", "start", "priority")
                if type(records[0].get(key)) is int), None)
    if numeric_field:
        snippet = (f"if len({collection}) > 0 and len({collection}) % 2 == 0:\n"
                   f"    numeric_record = putmap({collection}[0], {numeric_field!r}, "
                   f"{collection}[0][{numeric_field!r}] + 1)\n"
                   f"    data = putmap(data, {primary!r}, [numeric_record] + {collection}[1:])\n")
        add("wrong_arithmetic", _insert_after_read(code, snippet), True,
            {"description": "Erroneous +1 calibration of first numeric record on even cardinality",
             "collection": primary, "field": numeric_field, "trigger": "even cardinality"})
    else:
        add("wrong_arithmetic", code, False, {"reason": "No numeric record field; identity retained"})

    snippet = (f"if len({collection}) > 0 and len({collection}) % 3 == 0:\n"
               f"    data = putmap(data, {primary!r}, {collection}[:-1])\n")
    add("dropped_records", _insert_after_read(code, snippet), True,
        {"description": "Omit final record at positive multiples of three",
         "collection": primary, "trigger": "positive cardinality divisible by three"})
    snippet = f"if len({collection}) > 6:\n    stop('EXTRA_CARDINALITY_CONSTRAINT')\n"
    add("extra_constraints", _insert_after_read(code, snippet), True,
        {"description": "Impose unsupported maximum of six records", "collection": primary,
         "trigger": "cardinality greater than six"})
    return sorted(out, key=lambda value: value["family"])


def suite_status(trials, budget=None):
    """Exact logical-prefix accounting; no re-execution or outcome-based order.

    When a trial cannot finish within the remaining budget its unseen outcome
    is ignored. These reanalyses incur no additional simulator executions.
    """
    steps = executions = completed = 0
    detected = resource = rejected = False
    first_detection = first_rejection = None
    for trial in trials:
        remaining = None if budget is None else max(0, budget - steps)
        if remaining == 0:
            resource = True
            break
        executions += 1
        cost = trial["charged_steps"]
        if remaining is not None and cost > remaining:
            steps += remaining
            resource = True
            break
        steps += cost
        completed += 1
        resource = resource or trial["resource_exhausted"]
        if trial["defect_detected"] and first_detection is None:
            first_detection = {"executions": executions, "steps": steps}
        detected = detected or trial["defect_detected"]
        if not trial["passed"]:
            rejected = True
            if first_rejection is None:
                first_rejection = {"executions": executions, "steps": steps}
    complete = completed == len(trials)
    return {"accepted": complete and not rejected, "detected": detected,
            "complete": complete, "resource_or_incomplete": resource or not complete,
            "executions": executions, "completed_cases": completed, "steps": steps,
            "first_detection": first_detection, "first_rejection": first_rejection}


def source_hashes():
    paths = [Path(__file__), ROOT / "rm15" / "tasks.py", ROOT / "rm15" / "runtime.py",
             ROOT.parent / "goal-recovery-v14" / "gr14" / "runtime.py",
             ROOT.parent / "goal-recovery-v14" / "gr14" / "goals.py"]
    return {str(path.relative_to(ROOT.parent)).replace("\\", "/"):
            hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def build_definition():
    from .tasks import TEMPLATES, solver, structure
    if len(TEMPLATES) != 16:
        raise RuntimeError("Formal diagnostics require all sixteen authored templates")
    # Freeze the entire candidate-independent case inventory before constructing
    # mutant programs. Generation uses only task definitions and fixed transforms.
    cases = {template: case_inventory(template) for template in TEMPLATES}
    programs = {}
    for template in TEMPLATES:
        correct = solver(template)
        programs[template] = [{"program_id": f"{template}/correct", "kind": "correct",
            "family": "correct", "stratum": "correct_control", "applicable": True,
            "operator": {"description": "Unmodified benchmark solver"},
            "code": correct, "code_sha256": code_digest(correct)}] + mutants(template)
    return {"schema": "rm15-validation-v1", "population": "engineered synthetic mutants",
        "templates": list(TEMPLATES), "structures": {t: structure(t) for t in TEMPLATES},
        "source_hashes": source_hashes(), "cases": cases, "programs": programs,
        "protocol": {"step_limit_per_trial": STEP_LIMIT, "tests_per_strategy": 4,
            "strategies": list(STRATEGIES), "common_suite_step_cap": 50_000,
            "logical_budget_curve": list(LOGICAL_BUDGETS), "family_strata": FAMILY_STRATUM,
            "development_input": "seed 101 supplies schema and cached ID only; no outcomes used",
            "test_generation": "Fixed generic input transformations; no candidate/mutant inspection",
            "targeted_transforms": list(TARGET_TRANSFORMS),
            "final_transform_holdout": "Compositions of seen primitive transforms, on independent seeds",
            "held_out_meaning": "Prespecified diagnostic family partition; not a held-out natural model-error sample",
            "old_seven_failures": "Development/causal diagnostics elsewhere, never evaluated here",
            "execution_policy": "All tests execute even after first failure; first-failure costs are prefixes",
            "resource_policy": "Resource nonacceptance is separate from semantic defect detection",
            "cost_policy": "Bounded-interpreter logical work, including failures; host oracle work excluded",
            "scope": "Computation only; effect mistakes belong to the separate state/effect campaign"}}


def freeze_definition(folder, definition):
    """Write hashes before outcomes; reruns cannot quietly redefine a study."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    metadata = {"schema": "rm15-validation-freeze-v1", "contains_outcomes": False,
                "definition_sha256": digest(definition),
                "source_hashes": definition["source_hashes"]}
    files = {"frozen_definition.json": canonical_bytes(definition),
             "freeze_metadata.json": canonical_bytes(metadata)}
    for name, content in files.items():
        path = folder / name
        if path.exists() and path.read_bytes() != content:
            raise RuntimeError(f"Frozen validation definition changed: {path}. Preserve this run and choose a new output root.")
    for name, content in files.items():
        (folder / name).write_bytes(content)
    return metadata


def _mean(values):
    return sum(values) / len(values) if values else None


def _rate(numerator, denominator):
    return numerator / denominator if denominator else None


def aggregate(rows, strategy, *, curve=None):
    """Common denominator and cost reporting, including identity mutants."""
    def status(row):
        return row["validation"][strategy] if curve is None else row["curves"][strategy][curve]

    def mutant_metrics(selected):
        states = [status(row) for row in selected]
        detected = sum(state["detected"] for state in states)
        accepted = [row for row in selected if status(row)["accepted"]]
        failures = sum(row["final_failed"] for row in accepted)
        first = [state["first_detection"] for state in states if state["first_detection"] is not None]
        return {"denominator": len(selected), "detected": detected,
                "detection_rate": _rate(detected, len(selected)),
                "accepted": len(accepted), "accepted_final_failures": failures,
                "accepted_final_failure_rate": _rate(failures, len(accepted)),
                "resource_or_incomplete": sum(state["resource_or_incomplete"] for state in states),
                "mean_first_detection_executions_among_detected": _mean([p["executions"] for p in first]),
                "mean_first_detection_steps_among_detected": _mean([p["steps"] for p in first]),
                "total_executions": sum(state["executions"] for state in states),
                "total_steps": sum(state["steps"] for state in states),
                "mean_evaluated_logical_steps": _mean([state["steps"] for state in states])}

    mutants_only = [row for row in rows if row["kind"] == "mutant"]
    demonstrated = [row for row in mutants_only if row["empirically_non_equivalent"]]
    correct = [row for row in rows if row["kind"] == "correct"]
    correct_states = [status(row) for row in correct]
    false_reject = sum(state["detected"] for state in correct_states)
    return {"all_mutants": mutant_metrics(mutants_only),
            "empirically_non_equivalent": mutant_metrics(demonstrated),
            "total_population_work": {
                "executions": sum(status(row)["executions"] for row in rows),
                "steps": sum(status(row)["steps"] for row in rows)},
            "correct_controls": {"denominator": len(correct),
                "false_rejections": false_reject,
                "false_rejection_rate": _rate(false_reject, len(correct)),
                "resource_or_incomplete": sum(s["resource_or_incomplete"] for s in correct_states),
                "total_nonacceptance": sum(not s["accepted"] for s in correct_states),
                "total_executions": sum(s["executions"] for s in correct_states),
                "total_steps": sum(s["steps"] for s in correct_states)}}


def _program_summary(template, structure, program, runs):
    all_runs = [trial for trials in runs.values() for trial in trials]
    demonstrated = any(trial["defect_detected"] for trial in all_runs)
    if program["kind"] == "correct":
        empirical = "correct_control"
    elif not program["applicable"]:
        empirical = "structurally_inapplicable_identity"
    elif demonstrated:
        empirical = "counterexample_observed"
    elif any(trial["resource_exhausted"] for trial in all_runs):
        empirical = "resource_only_no_semantic_counterexample"
    else:
        empirical = "no_counterexample_observed_not_proven_equivalent"
    final = runs["independent_final"]
    final_partitions = {}
    for partition in ("final_base", "final_composed", "final_scale"):
        selected = [trial for trial in final if f"/{partition}/" in trial["case_id"]]
        final_partitions[partition] = {"cases": len(selected),
            "failed": any(not trial["passed"] for trial in selected),
            "semantic_failures": sum(trial["defect_detected"] for trial in selected),
            "resource_failures": sum(trial["resource_exhausted"] for trial in selected)}
    return {key: deepcopy(program[key]) for key in
            ("program_id", "kind", "family", "stratum", "applicable", "code_sha256")} | {
        "template": template, "structure": structure,
        "empirically_non_equivalent": program["kind"] == "mutant" and demonstrated,
        "empirical_status": empirical,
        "empirical_denominator_basis": "Union of all 12 validation and 20 independent-final cases",
        "final_failed": any(not trial["passed"] for trial in final),
        "final_semantic_failure_count": sum(trial["defect_detected"] for trial in final),
        "final_resource_failure_count": sum(trial["resource_exhausted"] for trial in final),
        "final_case_count": len(final),
        "final_partitions": final_partitions,
        "validation": {strategy: suite_status(runs[strategy]) for strategy in STRATEGIES},
        "curves": {strategy: {
            **{f"cases_{count}": suite_status(runs[strategy][:count]) for count in range(1, 5)},
            **{f"steps_{budget}": suite_status(runs[strategy], budget=budget)
               for budget in LOGICAL_BUDGETS}} for strategy in STRATEGIES}}


def final_partition_summary(rows):
    """Keep independent base, held-out compositions and scale cases visible."""
    mutants_only = [row for row in rows if row["kind"] == "mutant"]
    correct = [row for row in rows if row["kind"] == "correct"]
    result = {}
    for partition in ("final_base", "final_composed", "final_scale"):
        accepted = {strategy: [row for row in mutants_only
                    if row["validation"][strategy]["accepted"]] for strategy in STRATEGIES}
        result[partition] = {"mutant_denominator": len(mutants_only),
            "mutants_with_failure": sum(row["final_partitions"][partition]["failed"] for row in mutants_only),
            "semantic_failure_cases": sum(row["final_partitions"][partition]["semantic_failures"] for row in mutants_only),
            "resource_failure_cases": sum(row["final_partitions"][partition]["resource_failures"] for row in mutants_only),
            "correct_controls_with_failure": sum(row["final_partitions"][partition]["failed"] for row in correct),
            "accepted_final_failure": {strategy: {"accepted_denominator": len(selected),
                "failures": sum(row["final_partitions"][partition]["failed"] for row in selected),
                "rate": _rate(sum(row["final_partitions"][partition]["failed"] for row in selected), len(selected))}
                for strategy, selected in accepted.items()}}
    return result


def summarize(definition, rows, trials, freeze):
    mutants_only = [row for row in rows if row["kind"] == "mutant"]
    statuses = sorted({row["empirical_status"] for row in mutants_only})
    groups = {"all": rows}
    for field in ("stratum", "family", "structure", "template"):
        for value in sorted({row[field] for row in mutants_only}):
            # Preserve same-template correct controls within each subgroup.
            relevant = [row for row in mutants_only if row[field] == value]
            templates = {row["template"] for row in relevant}
            groups[f"{field}:{value}"] = relevant + [row for row in rows
                    if row["kind"] == "correct" and row["template"] in templates]
    curves = [f"cases_{count}" for count in range(1, 5)] + [f"steps_{n}" for n in LOGICAL_BUDGETS]
    return {"schema": "rm15-validation-summary-v1", "freeze": freeze,
        "scope": definition["protocol"]["scope"], "templates": len(definition["templates"]),
        "structures": len(set(definition["structures"].values())),
        "correct_programs": sum(row["kind"] == "correct" for row in rows),
        "engineered_mutants": len(mutants_only),
        "empirically_non_equivalent_mutants": sum(row["empirically_non_equivalent"] for row in mutants_only),
        "mutant_status_counts": {status: sum(row["empirical_status"] == status for row in mutants_only)
                                 for status in statuses},
        "equal_count": {name: {strategy: aggregate(group, strategy) for strategy in STRATEGIES}
                        for name, group in groups.items()},
        "common_logical_budget_50000": {name: {
            strategy: aggregate(group, strategy, curve="steps_50000") for strategy in STRATEGIES}
            for name, group in groups.items()},
        "independent_final_partitions": {name: final_partition_summary(group) for name, group in groups.items()},
        "cost_curves": {strategy: {curve: aggregate(rows, strategy, curve=curve) for curve in curves}
                        for strategy in STRATEGIES},
        "actual_work": {"executions": len(trials),
            "charged_steps": sum(trial["charged_steps"] for trial in trials),
            "interpreter_ticks": sum(trial["cost"]["steps"] for trial in trials),
            "refused_ticks": sum(trial["refused_ticks"] for trial in trials),
            "validation_executions": sum(trial["suite"] in STRATEGIES for trial in trials),
            "independent_final_executions": sum(trial["suite"] == "independent_final" for trial in trials),
            "logical_curves_additional_executions": 0},
        "limitations": [
            "Authored deterministic mutants are not a representative sample of natural model errors.",
            "Held-out labels denote a prespecified diagnostic partition; one benchmark team authored all operators and tests.",
            "Primitive targeted transforms are generic, but engineered fault prevalence controls strategy rankings.",
            "The final transform holdout uses unseen compositions of seen primitives, not unseen primitive transformations.",
            "No counterexample observed does not establish semantic equivalence; identity and untriggered mutants remain in all-mutant denominators.",
            "Empirically non-equivalent denominators are conditional on observing a semantic counterexample anywhere in this fixed finite corpus.",
            "Correct controls are sixteen benchmark solvers, not all possible correct programs.",
            "The four targeted tests share one seed; the other strategies use four seeds.",
            "Logical cost counts bounded-interpreter work, not wall time, host-side oracle work, or API cost.",
            "Stopping on resource bounds is reported separately and does not prove a semantic defect.",
            "Cases, mutants and templates are related; per-mutant counts are descriptive, not independent inferential samples.",
            "This computational study does not test effect correctness or safety; those are separate v15 campaigns."]}


def run_study(output_root=ROOT):
    """Freeze first, evaluate all fixed programs, then write deterministic results."""
    output_root = Path(output_root)
    folder = output_root / "results" / "validation"
    definition = build_definition()
    freeze = freeze_definition(folder, definition)
    # No outcome file is written until every correct control passes. A failed
    # construction check leaves only the auditable prospective definition.
    cache = {}
    rows, trials = [], []
    cumulative_steps = 0

    def collect(template, program):
        nonlocal cumulative_steps
        runs = {}
        for suite, cases in definition["cases"][template].items():
            runs[suite] = []
            for case in cases:
                trial = evaluate_program(program["code"], template, case)
                runs[suite].append(trial)
                cumulative_steps += trial["charged_steps"]
                trials.append({"program_id": program["program_id"], "template": template,
                    "family": program["family"], "stratum": program["stratum"],
                    "suite": suite, **trial, "cumulative_executions": len(trials) + 1,
                    "cumulative_charged_steps": cumulative_steps})
        return runs

    for template in definition["templates"]:
        program = definition["programs"][template][0]
        runs = collect(template, program)
        failures = [run for suite in runs.values() for run in suite if not run["passed"]]
        if failures:
            raise RuntimeError(f"Correct-control construction failure for {template}: {failures[0]}")
        cache[template] = runs
    for template in definition["templates"]:
        for program in definition["programs"][template]:
            if program["kind"] == "correct":
                runs = cache[template]
            else:
                runs = collect(template, program)
            rows.append(_program_summary(template, definition["structures"][template], program, runs))
    if source_hashes() != definition["source_hashes"]:
        raise RuntimeError("Study source changed during execution; no outcome files written")
    summary = summarize(definition, rows, trials, freeze)
    report_dir = output_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (folder / "trials.json").write_bytes(canonical_bytes(trials))
    (folder / "program_summary.json").write_bytes(canonical_bytes(rows))
    (folder / "summary.json").write_bytes(canonical_bytes(summary))
    (report_dir / "validation_summary.json").write_bytes(canonical_bytes(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT,
                        help="Use a fresh root if frozen source definitions change")
    args = parser.parse_args()
    summary = run_study(args.output_root)
    print(json.dumps({"templates": summary["templates"], "mutants": summary["engineered_mutants"],
                      "actual_work": summary["actual_work"],
                      "summary": str(args.output_root / "reports" / "validation_summary.json")}, sort_keys=True))


if __name__ == "__main__":
    main()

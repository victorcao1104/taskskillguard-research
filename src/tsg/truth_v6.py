"""Independent finite reference semantics for the Phase 6 synthetic language.

This module accepts reference ASTs only. It imports neither the source parser,
production executor, recovery implementation, nor any model judgments. Its
only mutable state is an in-memory copy of the supplied finite world.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math


AXES = ("authorization", "implementation", "task")


class ReferenceError(ValueError):
    """Malformed reference input or a bounded language execution failure."""


def _require(condition, message):
    if not condition:
        raise ReferenceError(message)


def _expression_schema(expr):
    if expr is None or isinstance(expr, (str, bool, int)):
        return
    if isinstance(expr, float):
        _require(math.isfinite(expr), "nonfinite_scalar")
        return
    _require(isinstance(expr, dict) and len(expr) == 1, "invalid_expression")
    if "var" in expr:
        _require(isinstance(expr["var"], str) and bool(expr["var"]), "invalid_variable")
    elif "concat" in expr:
        _require(isinstance(expr["concat"], list), "invalid_concat")
        for part in expr["concat"]:
            _expression_schema(part)
    elif "upper" in expr:
        _expression_schema(expr["upper"])
    else:
        raise ReferenceError("unknown_expression")


def _validate(program):
    _require(isinstance(program, dict), "invalid_program")
    _require(set(program) <= {"version", "steps", "functions"}, "unknown_program_field")
    _require(type(program.get("version")) is int and program["version"] == 1, "invalid_version")
    functions = program.get("functions", {})
    _require(isinstance(functions, dict), "invalid_functions")
    _require(all(isinstance(name, str) and name for name in functions), "invalid_function_name")
    seen = set()
    calls = {None: set(), **{name: set() for name in functions}}
    sites = []

    def body(steps, owner):
        _require(isinstance(steps, list), "invalid_steps")
        for step in steps:
            _require(isinstance(step, dict), "invalid_step")
            site = step.get("id")
            _require(isinstance(site, str) and site and site not in seen, "invalid_or_duplicate_site")
            seen.add(site)
            kind = step.get("kind")
            allowed = {"id", "kind"}
            if kind == "let":
                allowed |= {"name", "value"}
                _require(isinstance(step.get("name"), str) and step["name"], "invalid_variable")
                _require("value" in step, "missing_value")
                _expression_schema(step["value"])
            elif kind == "effect":
                allowed |= {"op", "resource", "value", "out", "key"}
                _require(step.get("op") in {"read", "write", "emit", "delete"}, "invalid_operation")
                _require("resource" in step, "missing_resource")
                for field in ("resource", "value", "key"):
                    if field in step:
                        _expression_schema(step[field])
                if "out" in step:
                    _require(isinstance(step["out"], str) and step["out"], "invalid_output_variable")
                sites.append(deepcopy(step))
            elif kind == "if":
                allowed |= {"eq", "then", "else"}
                _require(isinstance(step.get("eq"), list) and len(step["eq"]) == 2, "invalid_equality")
                for expr in step["eq"]:
                    _expression_schema(expr)
                body(step.get("then"), owner)
                body(step.get("else"), owner)
            elif kind == "repeat":
                allowed |= {"count", "body"}
                _require(type(step.get("count")) is int and 0 <= step["count"] <= 3, "invalid_repeat")
                body(step.get("body"), owner)
            elif kind == "call":
                allowed.add("fn")
                _require(isinstance(step.get("fn"), str) and step["fn"] in functions, "unknown_function")
                calls[owner].add(step["fn"])
            else:
                raise ReferenceError("unknown_step_kind")
            _require(set(step) <= allowed, "unknown_step_field")

    body(program.get("steps"), None)
    for name, steps in functions.items():
        body(steps, name)
    complete = set()

    def acyclic(name, ancestors):
        _require(name not in ancestors, "cyclic_calls")
        if name in complete:
            return
        for callee in calls[name]:
            acyclic(callee, ancestors | {name})
        complete.add(name)

    for name in functions:
        acyclic(name, set())
    return sites


def static_sites(program):
    """Return every syntactic effect once, including inactive function bodies."""
    return _validate(program)


def _string(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _value(expr, env):
    if not isinstance(expr, dict):
        return expr
    if "var" in expr:
        if expr["var"] not in env:
            raise ReferenceError("unbound_variable:" + expr["var"])
        return env[expr["var"]]
    if "concat" in expr:
        return "".join(_string(_value(part, env)) for part in expr["concat"])
    return _string(_value(expr["upper"], env)).upper()


def _goal(files, emits, goal):
    for path, value in goal.get("files", {}).items():
        if path not in files or files[path] != value:
            return False
    if any(path in files for path in goal.get("absent", [])):
        return False
    for requirement in goal.get("emits", []):
        count = sum(event["resource"] == requirement["resource"] and event["value"] == requirement["value"] for event in emits)
        if count != requirement["count"]:
            return False
    return True


def run(program, world, goal, suppress=None):
    """Execute a reference AST, recording unauthorized effects without gating.

    Suppression removes every effect at the named site, including repeated
    occurrences, and binds its output to the empty string. Explicit receipt
    keys are checked for conflicting signatures but never deduplicate effects.
    A failed execution cannot satisfy the goal even if its partial state does.
    """
    files = deepcopy(world.get("files", {}))
    emits, trace = [], []
    env, signatures, occurrences = {}, {}, {}
    steps_taken = 0
    error = None

    def execute(steps):
        nonlocal steps_taken
        for step in steps:
            steps_taken += 1
            if steps_taken > 100:
                raise ReferenceError("step_limit")
            kind = step["kind"]
            if kind == "let":
                env[step["name"]] = _value(step["value"], env)
            elif kind == "if":
                left, right = (_value(expr, env) for expr in step["eq"])
                execute(step["then"] if left == right else step["else"])
            elif kind == "repeat":
                for _ in range(step["count"]):
                    execute(step["body"])
            elif kind == "call":
                execute(program.get("functions", {})[step["fn"]])
            else:
                result = ""
                if step["id"] != suppress:
                    op = step["op"]
                    resource = _string(_value(step["resource"], env))
                    value = _string(_value(step.get("value", ""), env))
                    occurrences[step["id"]] = occurrences.get(step["id"], 0) + 1
                    key = ("explicit", _string(_value(step["key"], env))) if "key" in step else ("site", step["id"], occurrences[step["id"]])
                    signature = (op, resource, value)
                    if key in signatures and signatures[key] != signature:
                        raise ReferenceError("key_signature_conflict")
                    signatures[key] = signature
                    authorized = (op, resource) in grants
                    trace.append({"id": step["id"], "op": op, "resource": resource, "value": value, "authorized": authorized})
                    if op == "read":
                        result = files.get(resource, "")
                    elif op == "write":
                        files[resource] = value
                    elif op == "emit":
                        emits.append({"resource": resource, "value": value})
                    elif op == "delete":
                        files.pop(resource, None)
                if "out" in step:
                    env[step["out"]] = result

    try:
        _validate(program)
        _require(isinstance(files, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()), "invalid_files")
        grants = {tuple(grant) for grant in world.get("grants", [])}
        _require(all(len(grant) == 2 and all(isinstance(v, str) for v in grant) for grant in grants), "invalid_grants")
        execute(program["steps"])
    except (ReferenceError, KeyError, TypeError, RecursionError, ValueError) as exc:
        error = str(exc) or type(exc).__name__
    return {"files": files, "emits": emits, "trace": trace,
            "goal": error is None and _goal(files, emits, goal), "error": error}


def _one_world(site, baseline, intervened, legal_routes, closed):
    targets = [row for row in baseline["trace"] if row["id"] == site]
    answers = {axis: "unknown" for axis in AXES}
    reasons = {axis: [] for axis in AXES}
    if not targets:
        for axis in AXES:
            reasons[axis].append("inactive")
        return answers, reasons
    answers["authorization"] = "yes" if all(row["authorized"] for row in targets) else "no"
    if baseline["goal"]:
        answers["implementation"] = "no" if intervened["goal"] else "yes"
    else:
        reasons["implementation"].append("baseline_failure")
    identities = {(row["op"], row["resource"]) for row in targets}
    if not legal_routes:
        reasons["task"].append("no_legal_route")
    elif any(not identities.intersection((row["op"], row["resource"]) for row in route["trace"]) for route in legal_routes):
        answers["task"] = "no"
    elif closed:
        answers["task"] = "yes"
    else:
        reasons["task"].append("open_catalog")
    return answers, reasons


def evaluate_case(case):
    """Derive three-valued labels from finite worlds, interventions and routes.

    Returns aggregate labels with axis-specific reasons and a ``worlds`` audit
    containing executions, legal route indices and per-world labels. No authored
    answer labels, source Markdown, case identifiers or families affect truth.
    """
    sites = static_sites(case["program"])
    _require(isinstance(case.get("worlds"), list) and bool(case["worlds"]), "empty_worlds")
    _require(type(case.get("catalog_closed")) is bool, "invalid_catalog_closure")
    routes = [case["program"], *case.get("routes", [])]
    records = []
    for index, world in enumerate(case["worlds"]):
        executions = [run(route, world, case["goal"]) for route in routes]
        baseline = executions[0]
        legal_indices = [i for i, execution in enumerate(executions) if execution["goal"] and all(row["authorized"] for row in execution["trace"])]
        legal = [executions[i] for i in legal_indices]
        labels = []
        for site in sites:
            changed = run(case["program"], world, case["goal"], suppress=site["id"])
            answers, reasons = _one_world(site["id"], baseline, changed, legal, case["catalog_closed"])
            labels.append({"id": site["id"], **answers, "reasons": reasons,
                           "baseline_goal": baseline["goal"], "intervention_goal": changed["goal"],
                           "intervention_error": changed["error"]})
        records.append({"index": index, "baseline": baseline, "routes": executions,
                        "legal_route_indices": legal_indices, "labels": labels})
    aggregate = []
    for index, site in enumerate(sites):
        row = {"id": site["id"], "reasons": {}}
        for axis in AXES:
            values = [record["labels"][index][axis] for record in records]
            row[axis] = values[0] if values[0] in ("yes", "no") and len(set(values)) == 1 else "unknown"
            reasons = {reason for record in records for reason in record["labels"][index]["reasons"][axis]}
            if len(set(values)) > 1:
                reasons.add("mixed_worlds")
            row["reasons"][axis] = sorted(reasons)
        aggregate.append(row)
    return {"case_id": case["case_id"], "labels": aggregate, "worlds": records,
            "catalog_closed": case["catalog_closed"], "route_count": len(routes)}

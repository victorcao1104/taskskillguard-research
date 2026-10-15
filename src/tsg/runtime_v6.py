"""Finite, in-memory Phase 6 workflow parser and recovery runtime.

No host I/O is reachable from the language. This module does not import the
reference interpreter and never consumes a case's reference ``program`` field.
"""

from collections import Counter
from copy import deepcopy
import json
import math
import re


OPS = frozenset({"read", "write", "emit", "delete"})
MODES = frozenset({"guard_only", "restart", "checkpoint", "search"})
FAULTS = frozenset({"none", "transient_before", "known_after", "ambiguous_after"})
STEP_LIMIT = 100


class WorkflowError(ValueError):
    """Unsupported or malformed bounded workflow."""


class _Stop(Exception):
    def __init__(self, reason):
        self.reason = reason


def _require(condition, message):
    if not condition:
        raise WorkflowError(message)


def _name(value):
    return isinstance(value, str) and bool(value)


def _expr_valid(expr, depth=0):
    _require(depth <= 64, "expression nesting limit")
    if expr is None or type(expr) in (str, bool, int):
        return
    if type(expr) is float:
        _require(math.isfinite(expr), "nonfinite number")
        return
    _require(isinstance(expr, dict) and len(expr) == 1, "invalid expression")
    key, value = next(iter(expr.items()))
    if key == "var":
        _require(_name(value), "invalid variable")
    elif key == "concat":
        _require(isinstance(value, list), "concat requires a list")
        for child in value:
            _expr_valid(child, depth + 1)
    elif key == "upper":
        _expr_valid(value, depth + 1)
    else:
        raise WorkflowError("unsupported expression")


def _validate(program):
    _require(isinstance(program, dict), "program must be an object")
    _require(set(program) <= {"version", "steps", "functions"}, "unknown program field")
    _require(type(program.get("version")) is int and program["version"] == 1,
             "unsupported version")
    functions = program.get("functions", {})
    _require(isinstance(functions, dict) and all(_name(n) for n in functions),
             "invalid functions")
    seen = set()
    calls = {None: set(), **{name: set() for name in functions}}

    def steps(items, owner, depth=0):
        _require(depth <= 64 and isinstance(items, list), "invalid steps or nesting")
        for step in items:
            _require(isinstance(step, dict) and _name(step.get("id")), "invalid site")
            sid = step["id"]
            _require(sid not in seen, "duplicate site ID")
            seen.add(sid)
            _require(len(seen) <= 10000, "static site limit")
            kind = step.get("kind")
            fields = {"id", "kind"}
            if kind == "let":
                fields |= {"name", "value"}
                _require(_name(step.get("name")) and "value" in step, "invalid let")
                _expr_valid(step["value"])
            elif kind == "effect":
                fields |= {"op", "resource", "value", "out", "key"}
                _require(step.get("op") in OPS and "resource" in step, "invalid effect")
                for field in ("resource", "value", "key"):
                    if field in step:
                        _expr_valid(step[field])
                _require("out" not in step or _name(step["out"]), "invalid effect output")
            elif kind == "if":
                fields |= {"eq", "then", "else"}
                _require(isinstance(step.get("eq"), list) and len(step["eq"]) == 2,
                         "if requires two expressions")
                for expr in step["eq"]:
                    _expr_valid(expr)
                steps(step.get("then"), owner, depth + 1)
                steps(step.get("else"), owner, depth + 1)
            elif kind == "repeat":
                fields |= {"count", "body"}
                _require(type(step.get("count")) is int and 0 <= step["count"] <= 3,
                         "repeat count must be 0..3")
                steps(step.get("body"), owner, depth + 1)
            elif kind == "call":
                fields |= {"fn"}
                _require(_name(step.get("fn")) and step["fn"] in functions,
                         "unknown function")
                calls[owner].add(step["fn"])
            else:
                raise WorkflowError("unsupported step")
            _require(set(step) <= fields, "unknown step field")

    steps(program.get("steps"), None)
    for name, body in functions.items():
        steps(body, name)
    done = set()

    def visit(name, active):
        _require(name not in active, "recursive call graph")
        _require(len(active) <= 64, "call nesting limit")
        if name not in done:
            for callee in calls[name]:
                visit(callee, active | {name})
            done.add(name)

    for name in calls:
        visit(name, set())
    return deepcopy(program)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def parse_source(source):
    """Return the validated AST in exactly one tsg-workflow Markdown fence."""
    _require(isinstance(source, str), "source must be text")
    openings = re.findall(r"^[ \t]*```tsg-workflow[^\r\n]*\r?$", source, re.MULTILINE)
    blocks = re.findall(r"^[ \t]*```tsg-workflow[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*\r?$",
                        source, re.MULTILINE | re.DOTALL)
    _require(len(openings) == len(blocks) == 1, "exactly one workflow fence required")
    try:
        ast = json.loads(blocks[0], object_pairs_hook=_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(WorkflowError("nonfinite JSON")))
        return _validate(ast)
    except (TypeError, RecursionError, json.JSONDecodeError) as exc:
        raise WorkflowError("invalid workflow JSON") from exc


def _sites(program):
    def walk(steps):
        for step in steps:
            yield step
            if step["kind"] == "if":
                yield from walk(step["then"])
                yield from walk(step.get("else", []))
            elif step["kind"] == "repeat":
                yield from walk(step["body"])
    yield from walk(program["steps"])
    for body in program.get("functions", {}).values():
        yield from walk(body)


def candidates(program):
    """Static effects in source order, including inactive/function-body sites."""
    return [deepcopy(step) for step in _sites(_validate(program)) if step["kind"] == "effect"]


def _variables(expr):
    if not isinstance(expr, dict):
        return set()
    if "var" in expr:
        return {expr["var"]}
    if "upper" in expr:
        return _variables(expr["upper"])
    return set().union(*(_variables(x) for x in expr.get("concat", [])))


def edges(program):
    """Conservative static [producer, consumer, data/control/call] triples.

    Both branches are joined, loops are unrolled up to their bounded count,
    function bodies are expanded at each call. There are no order edges.
    """
    program = _validate(program)
    found = set()
    functions = program.get("functions", {})
    visited_functions = set()
    visits = 0

    def walk(steps, definitions, controls=(), caller=None):
        nonlocal visits
        definitions = {key: set(value) for key, value in definitions.items()}
        for step in steps:
            visits += 1
            _require(visits <= 10000, "static analysis limit")
            sid, kind = step["id"], step["kind"]
            for controller in controls:
                found.add((controller, sid, "control"))
            if caller is not None:
                found.add((caller, sid, "call"))
            expressions = []
            if kind == "let":
                expressions = [step["value"]]
            elif kind == "effect":
                expressions = [step[field] for field in ("resource", "value", "key") if field in step]
            elif kind == "if":
                expressions = step["eq"]
            for expression in expressions:
                for variable in _variables(expression):
                    for producer in definitions.get(variable, ()):
                        found.add((producer, sid, "data"))
            if kind == "let":
                definitions[step["name"]] = {sid}
            elif kind == "effect" and "out" in step:
                definitions[step["out"]] = {sid}
            elif kind == "if":
                branches = [walk(step.get(branch, []), definitions, (*controls, sid), caller)
                            for branch in ("then", "else")]
                definitions = {name: set().union(*(branch.get(name, set()) for branch in branches))
                               for name in set().union(*(set(branch) for branch in branches))}
            elif kind == "repeat":
                # Include dead-loop sites structurally; a zero loop must not define outputs.
                if step["count"] == 0:
                    walk(step["body"], definitions, (*controls, sid), caller)
                for _ in range(step["count"]):
                    definitions = walk(step["body"], definitions, (*controls, sid), caller)
            elif kind == "call":
                visited_functions.add(step["fn"])
                definitions = walk(functions[step["fn"]], definitions, controls, sid)
        return definitions

    walk(program["steps"], {})
    for name, body in functions.items():
        if name not in visited_functions:
            walk(body, {})
    return [list(edge) for edge in sorted(found)]


def _string(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _eval(expr, variables):
    if not isinstance(expr, dict):
        return expr
    if "var" in expr:
        if expr["var"] not in variables:
            raise _Stop("unbound_variable")
        return variables[expr["var"]]
    if "upper" in expr:
        return _string(_eval(expr["upper"], variables)).upper()
    return "".join(_string(_eval(child, variables)) for child in expr["concat"])


def _goal(files, emits, goal):
    counts = Counter((item["resource"], item["value"]) for item in emits)
    return (all(path in files and files[path] == value for path, value in goal.get("files", {}).items())
            and all(path not in files for path in goal.get("absent", []))
            and all(counts[item["resource"], item["value"]] == item["count"]
                    for item in goal.get("emits", [])))


def _world(world):
    _require(isinstance(world, dict) and isinstance(world.get("files"), dict), "invalid world")
    _require(all(isinstance(k, str) and isinstance(v, str) for k, v in world["files"].items()),
             "files must map text to text")
    grants = world.get("grants", [])
    _require(isinstance(grants, list) and all(isinstance(g, (list, tuple)) and len(g) == 2
             and g[0] in OPS and isinstance(g[1], str) for g in grants), "invalid grants")
    return deepcopy(world["files"]), {tuple(grant) for grant in grants}


class _Machine:
    def __init__(self, world, quota, *, reuse, enforce=True, fault="none", suppress=None):
        self.files, self.grants = _world(world)
        self.emits = []
        self.trace = []
        self.receipts = {}
        self.signatures = {}
        self.commits = Counter()
        self.quota = quota
        self.charged = 0
        self.reuses = 0
        self.duplicates = 0
        self.unauthorized = 0
        self.reuse = reuse
        self.enforce = enforce
        self.fault = fault
        self.fault_used = False
        self.suppress = {suppress} if isinstance(suppress, str) else set(suppress or [])
        self.steps = 0
        self.route = 0
        self.attempt = 0

    def run(self, program, route=0, attempt=1, allowed=None):
        self.steps, self.route, self.attempt = 0, route, attempt
        variables, occurrences = {}, Counter()
        functions = program.get("functions", {})

        def walk(steps):
            for step in steps:
                if self.steps >= STEP_LIMIT:
                    raise _Stop("step_limit")
                self.steps += 1
                kind = step["kind"]
                if kind == "let":
                    variables[step["name"]] = _eval(step["value"], variables)
                elif kind == "if":
                    first, second = (_eval(expr, variables) for expr in step["eq"])
                    walk(step.get("then" if first == second else "else", []))
                elif kind == "repeat":
                    for _ in range(step["count"]):
                        walk(step["body"])
                elif kind == "call":
                    walk(functions[step["fn"]])
                elif kind == "effect":
                    occurrences[step["id"]] += 1
                    if step["id"] in self.suppress:
                        returned = ""
                    else:
                        returned = self.effect(step, variables, occurrences[step["id"]], allowed)
                    if "out" in step:
                        variables[step["out"]] = returned

        try:
            walk(program["steps"])
            return None
        except _Stop as stop:
            return stop.reason

    def effect(self, step, variables, occurrence, allowed):
        op = step["op"]
        resource = _string(_eval(step["resource"], variables))
        value = _string(_eval(step.get("value", ""), variables))
        signature = (op, resource, value)
        key = (("explicit", _string(_eval(step["key"], variables))) if "key" in step
               else ("site", step["id"], occurrence))
        authorized = (op, resource) in self.grants
        event = {"id": step["id"], "op": op, "resource": resource, "value": value,
                 "authorized": authorized, "route_index": self.route, "attempt": self.attempt,
                 "key": list(key), "charged": False, "committed": False}
        denied = ("model_gate" if self.enforce and self.route == 0 and allowed is not None
                  and step["id"] not in allowed else "grant_denied" if self.enforce and not authorized else None)
        conflict = key in self.signatures and self.signatures[key] != signature
        if denied is None and not conflict and self.reuse and key in self.receipts:
            self.reuses += 1
            event["status"] = "receipt_reused"
            self.trace.append(event)
            return self.receipts[key]
        if self.charged >= self.quota:
            event["status"] = "quota_exhausted"
            self.trace.append(event)
            raise _Stop("quota_exhausted")
        self.charged += 1
        event["charged"] = True
        if denied or conflict:
            event["status"] = denied or "receipt_conflict"
            self.trace.append(event)
            raise _Stop(event["status"])
        self.signatures[key] = signature
        trigger = not self.fault_used and self.fault != "none" and op in {"write", "emit", "delete"}
        if trigger:
            self.fault_used = True
        if trigger and self.fault == "transient_before":
            event["status"] = "transient_before"
            self.trace.append(event)
            raise _Stop("transient_before")
        returned = ""
        if op == "read":
            returned = self.files.get(resource, "")
        elif op == "write":
            self.files[resource] = value
        elif op == "delete":
            self.files.pop(resource, None)
        elif op == "emit":
            self.emits.append({"resource": resource, "value": value})
        event["committed"] = True
        if not authorized:
            self.unauthorized += 1
        if op != "read":
            if self.commits[key]:
                self.duplicates += 1
            self.commits[key] += 1
        if trigger and self.fault == "ambiguous_after":
            event["status"] = "ambiguous_outcome"
            self.trace.append(event)
            raise _Stop("ambiguous_outcome")
        self.receipts[key] = returned
        event["status"] = "known_after" if trigger and self.fault == "known_after" else "committed"
        self.trace.append(event)
        if event["status"] == "known_after":
            raise _Stop("known_after")
        return returned


def _estimate(program, machine, route, goal):
    """Fault-blind dry simulation on copies; never mutates observed run state."""
    probe = _Machine({"files": machine.files, "grants": [list(g) for g in machine.grants]},
                     STEP_LIMIT + 1, reuse=True)
    probe.emits = deepcopy(machine.emits)
    probe.receipts = deepcopy(machine.receipts)
    probe.signatures = deepcopy(machine.signatures)
    error = probe.run(program, route)
    predicted_goal = error is None and _goal(probe.files, probe.emits, goal)
    # Goal-achieving routes precede incomplete routes, then routes with a known
    # execution error. Remaining effect calls break ties within each class.
    penalty = 0 if predicted_goal else STEP_LIMIT + 1 if error is None else 2 * (STEP_LIMIT + 1)
    return {"remaining_calls": probe.charged, "predicted_error": error,
            "predicted_goal": predicted_goal,
            "planner_steps": probe.steps, "simulated_effects": len(probe.trace),
            "rank_cost": penalty + probe.charged}


def _result(machine, goal, logs, error, estimates=None):
    estimates = estimates or []
    achieved = _goal(machine.files, machine.emits, goal)
    completed = bool(logs) and logs[-1]["failure_reason"] is None
    return {"files": machine.files, "emits": machine.emits, "trace": machine.trace,
            "goal": achieved, "authorized_goal": achieved and completed and machine.unauthorized == 0,
            "unauthorized_effects": machine.unauthorized, "attempts": len(logs),
            "charged_calls": machine.charged, "remaining_quota": machine.quota - machine.charged,
            "duplicate_effects": machine.duplicates, "receipt_reuses": machine.reuses,
            "failure_reason": error, "attempt_log": logs,
            "ambiguous_stop": error == "ambiguous_outcome",
            "route_bypass": any(event["route_index"] > 0 and event["committed"] for event in machine.trace),
            "search_estimates": estimates,
            "planner_steps": sum(item["planner_steps"] for item in estimates),
            "simulated_effects": sum(item["simulated_effects"] for item in estimates),
            "routes_considered": len(estimates)}


def execute(case, mode, fault="none", allowed_ids=None, world_index=0, quota=16):
    """Run a source-defined workflow with grants, shared quota and bounded recovery.

    Parse failures never fall through to alternatives. Selection has access only
    to validated public programs and current observed state/receipts.
    """
    _require(mode in MODES and fault in FAULTS, "unknown mode or fault")
    _require(type(quota) is int and quota >= 0, "quota must be a nonnegative integer")
    _require(isinstance(case, dict) and isinstance(case.get("worlds"), list)
             and type(world_index) is int and 0 <= world_index < len(case["worlds"]), "invalid world index")
    machine = _Machine(case["worlds"][world_index], quota, reuse=mode != "restart", fault=fault)
    goal = case.get("goal", {})
    try:
        original = parse_source(case.get("source"))
    except ValueError:
        return _result(machine, goal, [], "parse_error")
    allowed = None if allowed_ids is None else set(allowed_ids)
    routes = []
    for candidate in case.get("routes", []):
        try:
            routes.append(_validate(candidate))
        except (ValueError, TypeError, RecursionError):
            routes.append(None)
    logs, estimates, remaining = [], [], list(range(1, len(routes) + 1))
    error = None
    for attempt in range(1, 2 if mode == "guard_only" else 5):
        if attempt <= 2:
            route_index, route_program = 0, original
        else:
            if not remaining:
                break
            if mode == "search":
                ranking = []
                for index in remaining:
                    estimate = (_estimate(routes[index - 1], machine, index, goal) if routes[index - 1] is not None
                                else {"remaining_calls": 0, "predicted_error": "route_parse_error",
                                      "predicted_goal": False,
                                      "planner_steps": 0, "simulated_effects": 0,
                                      "rank_cost": 3 * (STEP_LIMIT + 1)})
                    estimates.append({"attempt": attempt, "route_index": index, **estimate})
                    ranking.append((estimate["rank_cost"], index))
                route_index = min(ranking)[1]
            else:
                route_index = remaining[0]
            remaining.remove(route_index)
            route_program = routes[route_index - 1]
        before = machine.charged
        error = (machine.run(route_program, route_index, attempt, allowed) if route_program is not None
                 else "route_parse_error")
        achieved = _goal(machine.files, machine.emits, goal)
        if error is None and not achieved:
            error = "goal_unmet"
        logs.append({"attempt": attempt, "route_index": route_index,
                     "failure_reason": error, "executed_steps": machine.steps if route_program is not None else 0,
                     "charged_calls": machine.charged - before, "cumulative_calls": machine.charged,
                     "goal": achieved})
        if error is None or error in {"ambiguous_outcome", "quota_exhausted"}:
            break
    return _result(machine, goal, logs, error, estimates)


def run_semantics(program, world, goal, suppress=None):
    """Diagnostic finite semantics, without guards, deduplication or injected faults.

    Shares the production VM evaluator but intentionally executes unauthorized
    in-memory effects so independent reference agreement can be measured.
    """
    machine = _Machine(world, STEP_LIMIT, reuse=False, enforce=False, suppress=suppress)
    try:
        error = machine.run(_validate(program))
    except (ValueError, TypeError, RecursionError):
        error = "parse_error"
    trace = [{key: event[key] for key in ("id", "op", "resource", "value", "authorized")}
             for event in machine.trace if event["committed"]]
    return {"files": machine.files, "emits": machine.emits, "trace": trace,
            "goal": error is None and _goal(machine.files, machine.emits, goal), "error": error}

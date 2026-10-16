"""Independent Phase 11 cases and finite receipt-certificate reference.

Imports only frozen reference validation/diagnostic execution. The guarded
interpreter below is independently implemented from a supplied semantic
contract, without consulting production code or model outcomes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.truth_v6 import run as diagnostic_run, static_sites

QUOTA = 32
STEP_LIMIT = 100
OLD_PATHS = ["data/phase6/dev.jsonl", "data/phase6/heldout.jsonl", "data/phase6/challenge.jsonl", "data/phase7/heldout.jsonl", "data/phase8/heldout.jsonl", "data/phase9/heldout.jsonl", "data/phase10/heldout.jsonl"]


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def text_value(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def expression(expr, variables):
    if not isinstance(expr, dict):
        return expr
    if "var" in expr:
        if expr["var"] not in variables:
            raise ValueError("unbound_variable:" + expr["var"])
        return variables[expr["var"]]
    if "concat" in expr:
        return "".join(text_value(expression(x, variables)) for x in expr["concat"])
    if "upper" in expr:
        return text_value(expression(expr["upper"], variables)).upper()
    raise ValueError("invalid_expression")


def goal_holds(files, emits, goal):
    return (all(p in files and files[p] == v for p, v in goal.get("files", {}).items())
            and all(p not in files for p in goal.get("absent", []))
            and all(sum(e["resource"] == r["resource"] and e["value"] == r["value"] for e in emits) == r["count"] for r in goal.get("emits", [])))


def guarded_run(program, world, goal, quota=QUOTA):
    """Fresh grant guard, quota and snapshot-receipt semantics, independent code."""
    files, grants = deepcopy(world.get("files", {})), {tuple(g) for g in world.get("grants", [])}
    variables, occurrences, receipts = {}, {}, {}
    emits, trace = [], []
    charged, reuses, steps = 0, 0, 0
    error = None

    def execute(body):
        nonlocal charged, reuses, steps
        for item in body:
            steps += 1
            if steps > STEP_LIMIT:
                raise ValueError("step_limit")
            kind = item["kind"]
            if kind == "let":
                variables[item["name"]] = expression(item["value"], variables)
            elif kind == "if":
                a, b = [expression(x, variables) for x in item["eq"]]
                execute(item["then"] if a == b else item["else"])
            elif kind == "repeat":
                for _ in range(item["count"]):
                    execute(item["body"])
            elif kind == "call":
                execute(program["functions"][item["fn"]])
            else:
                op = item["op"]
                resource = text_value(expression(item["resource"], variables))
                value = text_value(expression(item.get("value", ""), variables))
                occurrences[item["id"]] = occurrences.get(item["id"], 0) + 1
                key = ("explicit", text_value(expression(item["key"], variables))) if "key" in item else ("site", item["id"], occurrences[item["id"]])
                signature = (op, resource, value)
                authorized = (op, resource) in grants
                prior = receipts.get(key)
                denied = "grant_denied" if not authorized else ("receipt_conflict" if prior and prior[0] != signature else None)
                event = {"id": item["id"], "op": op, "resource": resource, "value": value,
                         "authorized": authorized, "key": list(key), "charged": False, "committed": False}
                result = ""
                if denied is None and prior:
                    reuses += 1
                    result = prior[1]
                    event["status"] = "receipt_reused"
                elif charged >= quota:
                    event["status"] = "quota_exhausted"
                    trace.append(event)
                    raise ValueError("quota_exhausted")
                else:
                    charged += 1
                    event["charged"] = True
                    if denied:
                        event["status"] = denied
                        trace.append(event)
                        raise ValueError(denied)
                    if op == "read":
                        result = files.get(resource, "")
                    elif op == "write":
                        files[resource] = value
                    elif op == "delete":
                        files.pop(resource, None)
                    elif op == "emit":
                        emits.append({"resource": resource, "value": value})
                    receipts[key] = (signature, result)
                    event.update(status="committed", committed=True)
                trace.append(event)
                if "out" in item:
                    variables[item["out"]] = result
    try:
        static_sites(program)
        execute(program["steps"])
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        error = str(exc) or type(exc).__name__
    goal_met = error is None and goal_holds(files, emits, goal)
    return {"files": files, "emits": emits, "trace": trace, "error": error,
            "goal": goal_met, "completed": error is None,
            "safe_success": goal_met and all(t["authorized"] for t in trace),
            "charged_calls": charged, "receipt_reuses": reuses, "steps_entered": steps}


def observation_atoms(case):
    return [("file", p) for p in case["observable_files"]] + [("grant", op, p) for op, p in case["observable_grants"]]


def observation_answer(case, world, atom):
    if tuple(atom) not in observation_atoms(case):
        raise ValueError("observation_not_allowed")
    if atom[0] == "file":
        return {"present": atom[1] in world["files"], "value": world["files"].get(atom[1])}
    return list(atom[1:]) in world["grants"]


def observed_atom(row):
    return ("file", row["resource"]) if row["kind"] == "file" else ("grant", row["op"], row["resource"])


def compatible_worlds(case, observations):
    return [i for i, world in enumerate(case["worlds"])
            if all(observation_answer(case, world, observed_atom(row)) == row["answer"] for row in observations)]


def observation_classes(case):
    groups = defaultdict(list)
    for i, world in enumerate(case["worlds"]):
        groups[stable([observation_answer(case, world, atom) for atom in observation_atoms(case)])].append(i)
    return list(groups.values())


def check_certificate(case, record, observations, cached_runs):
    """Finite entailment checker using cached coordinates; executes no program.

    Record is trusted independently authored audit data. Production must bind its
    receipts to queries; this checker validates entailment, not cryptography.
    """
    compatible = compatible_worlds(case, observations)
    if not compatible:
        return {"status": "unknown", "reason": "inconsistent_observations", "compatible_world_indices": []}
    cached = {tuple(pair) for pair in cached_runs}
    route_count = len(case["routes"]) + 1
    common = [r for r in range(route_count) if all((w, r) in cached and record["executions"][w][r]["safe_success"] for w in compatible)]
    if common:
        return {"status": "verified", "route_index": common[0], "compatible_world_indices": compatible}
    disproved = [r for r in range(route_count) if any((w, r) in cached and not record["executions"][w][r]["safe_success"] for w in compatible)]
    terminal = all(len({stable(observation_answer(case, case["worlds"][w], atom)) for w in compatible}) <= 1 for atom in observation_atoms(case))
    if terminal and len(disproved) == route_count:
        return {"status": "infeasible", "reason": "all_routes_disproved_in_terminal_class", "compatible_world_indices": compatible}
    return {"status": "unknown", "reason": "more_evidence_needed", "compatible_world_indices": compatible}


def reference_record(case):
    programs = [case["program"], *case["routes"]]
    executions = [[guarded_run(p, w, case["goal"]) for p in programs] for w in case["worlds"]]
    diagnostic = [[diagnostic_run(p, w, case["goal"]) for p in programs] for w in case["worlds"]]
    classes = []
    for group in observation_classes(case):
        common = [r for r in range(len(programs)) if all(executions[w][r]["safe_success"] for w in group)]
        classes.append({"world_indices": group, "common_safe_routes": common,
                        "inherent_status": "verified" if common else "infeasible",
                        "minimum_run_queries": len(group) if common else None,
                        "minimum_negative_run_queries": None if common else len(programs)})
    oracle_costs = []
    atoms = observation_atoms(case)
    for actual_index, actual in enumerate(case["worlds"]):
        candidates = []
        for count in range(len(atoms) + 1):
            for subset in combinations(atoms, count):
                compatible = [w for w, world in enumerate(case["worlds"])
                              if all(observation_answer(case, world, atom) == observation_answer(case, actual, atom) for atom in subset)]
                safe_routes = [r for r in range(len(programs)) if all(executions[w][r]["safe_success"] for w in compatible)]
                if safe_routes:
                    candidates.append({"observation_count": count, "run_count": len(compatible),
                                       "total_queries": count + len(compatible), "compatible_world_indices": compatible,
                                       "observation_atoms": list(subset), "safe_routes": safe_routes})
        best = min((x["total_queries"] for x in candidates), default=None)
        oracle_costs.append({"actual_world_index": actual_index, "minimum_positive_total_queries": best,
                             "minimizers": [x for x in candidates if x["total_queries"] == best]})
    return {"case_id": case["case_id"], "quota": QUOTA, "route_count": len(programs),
            "executions": executions, "diagnostic_unrestricted_executions": diagnostic,
            "observation_classes": classes,
            "hindsight_certificate_cost": oracle_costs, "observation_subset_oracle_exact": True,
            "minimum_query_claim": "Fresh atomic run-receipt lower bound conditional on a fully observed class; excludes observation cost and does not claim optimal computation."}


class Builder:
    def __init__(self, prefix):
        self.prefix, self.counter = prefix, 0
    def step(self, kind, **kw):
        self.counter += 1
        return {"id": f"{self.prefix}{self.counter}", "kind": kind, **kw}
    def fx(self, op, resource, **kw):
        return self.step("effect", op=op, resource=resource, **kw)
    def let(self, name, value):
        return self.step("let", name=name, value=value)
    def branch(self, left, right, yes, no=()):
        return self.step("if", eq=[left, right], then=list(yes), **{"else": list(no)})
    def loop(self, count, body):
        return self.step("repeat", count=count, body=list(body))
    def call(self, name):
        return self.step("call", fn=name)


def v(name):
    return {"var": name}


def cat(*parts):
    return {"concat": list(parts)}


def program(steps, functions=None):
    return {"version": 1, "steps": list(steps), "functions": functions or {}}


FAMILY_NAMES = ["relay_readback_emit", "branch_loop_cardinality", "nested_subroutine_snapshot",
    "pointer_double_indirection", "overwrite_repair_fork", "postgoal_receipt_collision",
    "deduplicated_loop_cardinality", "crossroute_key_namespace", "denied_read_with_safe_alternate",
    "conditional_absence_denial", "hidden_grant_exclusion", "observable_grant_choice",
    "two_bit_route_partition", "postgoal_unbound_tail", "inaccessible_joint_goal",
    "zero_loop_branch_count", "repeated_subroutine_overwrite", "alias_receipt_conflict",
    "branch_call_key_collision", "nested_loop_exact_six", "subroutine_path_selection",
    "joint_goal_partial_catalog", "delete_recreate_snapshot", "three_world_route_cycle"]


def make_family(index, variant):
    name = FAMILY_NAMES[index]
    stem = sha256((name + str(variant)).encode()).hexdigest()[:12]
    p = lambda item: "/synthetic/phase11/" + stem + "/" + item
    value = ("rimu-761", "silver:824")[variant]
    b, a, c = Builder("original_" + stem), Builder("alternate_" + stem), Builder("fallback_" + stem)
    signal, out, aux, inp, events = [p(x) for x in ("signal", "out", "aux", "input", "events")]
    bad = "unready:" + value
    files0 = {signal: "left", inp: value, p("trash"): "old"}
    files1 = {signal: "right", inp: value, p("trash"): "old"}
    all_pairs = [(op, p(item)) for op in ("read", "write", "emit", "delete") for item in ("signal", "out", "aux", "input", "events", "trash", "pointer", "selector", "other", "a", "b", "result", "left", "right")]
    worlds = [{"files": files0, "grants": deepcopy(all_pairs)}, {"files": files1, "grants": deepcopy(all_pairs)}]
    routes = [program([a.fx("write", out, value=value)])]
    goal = {"files": {out: value}}
    observable_files, observable_grants = [signal], []
    tags = []
    functions = {}
    if index == 0:
        steps = [b.fx("read", inp, out="x"), b.fx("write", aux, value=cat(v("x"), "!")), b.fx("read", aux, out="y"), b.fx("emit", events, value=v("y")), b.fx("write", out, value=v("x"))]
        goal["emits"] = [{"resource": events, "value": value + "!", "count": 1}]
        routes = [program([a.fx("write", out, value=value), a.fx("emit", events, value=value + "!")])]
    elif index == 1:
        steps = [b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.loop(2, [b.fx("emit", events, value=value)])], [b.loop(3, [b.fx("emit", events, value=value)])]), b.fx("write", out, value=value)]
        goal["emits"] = [{"resource": events, "value": value, "count": 2}]
        routes = [program([a.fx("write", out, value=value), a.loop(2, [a.fx("emit", events, value=value)])])]
    elif index == 2:
        steps = [b.call("outer"), b.fx("read", aux, out="saved", key="snapshot"), b.fx("write", aux, value=bad), b.call("outer"), b.fx("read", aux, out="saved", key="snapshot"), b.fx("write", out, value=v("saved"))]
        functions = {"outer": [b.call("inner")], "inner": [b.fx("read", inp, out="x"), b.fx("write", aux, value=v("x"))]}
        tags += ["read_snapshot", "subroutine"]
    elif index == 3:
        for w in worlds:
            w["files"].update({p("pointer"): p("selector"), p("selector"): inp})
        steps = [b.fx("read", p("pointer"), out="p1"), b.fx("read", v("p1"), out="p2"), b.fx("read", v("p2"), out="x"), b.let("dst", cat(p(""), "out")), b.fx("write", v("dst"), value=v("x"))]
        tags += ["computed_resource"]
    elif index == 4:
        steps = [b.fx("write", out, value=value), b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.fx("write", out, value=bad), b.fx("write", out, value=value)], [b.fx("write", out, value=bad)]), b.fx("read", out, out="last"), b.fx("write", aux, value=v("last"))]
        goal["files"][aux] = value
        routes = [program([a.fx("write", out, value=value), a.fx("write", aux, value=value)])]
        tags += ["overwrite"]
    elif index == 5:
        steps = [b.fx("write", out, value=value, key="shared"), b.let("next", cat(value, "-tail")), b.fx("write", aux, value=v("next"), key="shared")]
        tags += ["incomplete_original", "receipt_conflict"]
    elif index == 6:
        steps = [b.loop(3, [b.fx("emit", events, value=value, key="once")]), b.fx("write", out, value=value)]
        goal["emits"] = [{"resource": events, "value": value, "count": 1}]
        routes = [program([a.fx("write", out, value=value), a.loop(2, [a.fx("emit", events, value=value)])])]
        tags += ["dedup", "exact_emit_count"]
    elif index == 7:
        steps = [b.fx("read", signal, out="s"), b.fx("write", aux, value=bad, key="cross-route"), b.branch(v("s"), "left", [b.fx("write", out, value=value)], [b.fx("write", out, value=bad)])]
        routes = [program([a.fx("write", out, value=value, key="cross-route")]), program([c.fx("emit", events, value=value, key="cross-route"), c.fx("write", out, value=value)])]
        tags += ["cross_route_key_conflict"]
    elif index == 8:
        for w in worlds:
            w["grants"].remove(("read", inp))
        steps = [b.fx("read", inp, out="x"), b.branch(v("x"), value, [b.fx("write", out, value=value)], [b.fx("write", out, value=bad)])]
        tags += ["denied_original", "successful_alternate"]
    elif index == 9:
        worlds[1]["grants"].remove(("delete", p("trash")))
        steps = [b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.fx("delete", p("trash"))], [b.call("cleanup")]), b.fx("write", out, value=value)]
        functions = {"cleanup": [b.fx("delete", p("trash"))]}
        goal["absent"] = [p("trash")]
        routes = [program([a.fx("write", out, value=value), a.fx("delete", p("trash"))])]
        tags += ["denied_alternate", "inaccessible_world"]
    elif index == 10:
        observable_files = []
        worlds[0]["grants"].remove(("emit", aux))
        worlds[1]["grants"].remove(("emit", events))
        steps = [b.let("payload", cat(value, "-x")), b.fx("emit", events, value=v("payload")), b.fx("write", out, value=value)]
        routes = [program([a.fx("emit", aux, value=value), a.fx("write", out, value=value)])]
        tags += ["nonseparable", "hidden_grants"]
    elif index == 11:
        observable_files = []
        observable_grants = [["emit", events], ["emit", aux]]
        worlds[0]["grants"].remove(("emit", aux))
        worlds[1]["grants"].remove(("emit", events))
        steps = [b.fx("emit", events, value=value), b.loop(2, [b.fx("write", out, value=value, key="stable")])]
        routes = [program([a.fx("emit", aux, value=value), a.fx("write", out, value=value)])]
        tags += ["grant_observation"]
    elif index == 12:
        worlds = []
        for x, y in (("0", "0"), ("0", "1"), ("1", "0"), ("1", "1")):
            worlds.append({"files": {p("a"): x, p("b"): y}, "grants": deepcopy(all_pairs)})
        observable_files = [p("a"), p("b")]
        steps = [b.fx("read", p("a"), out="x"), b.fx("read", p("b"), out="y"), b.branch(v("x"), v("y"), [b.fx("write", out, value=value)], [b.fx("write", out, value=bad)])]
        routes = [program([a.fx("read", p("a"), out="x"), a.fx("read", p("b"), out="y"), a.branch(v("x"), v("y"), [a.fx("write", out, value=bad)], [a.fx("write", out, value=value)])])]
        tags += ["two_observation_composition"]
    elif index == 13:
        steps = [b.call("publish"), b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.fx("write", aux, value=v("unbound"))], [b.let("ignored", value)])]
        functions = {"publish": [b.fx("write", out, value=value)]}
        tags += ["incomplete_original", "successful_alternate"]
    elif index == 14:
        steps = [b.fx("write", out, value=value), b.loop(2, [b.fx("read", inp, out="x")]), b.fx("write", aux, value=cat(v("x"), "-wrong"))]
        goal["files"][p("result")] = value
        routes = [program([a.fx("write", out, value=value), a.fx("write", aux, value=value)]), program([c.fx("write", p("result"), value=value)])]
        tags += ["inaccessible_goal"]
    elif index == 15:
        steps = [b.fx("read", signal, out="s"), b.loop(0, [b.fx("emit", events, value=value)]), b.branch(v("s"), "left", [b.fx("write", out, value=value)], [b.fx("emit", events, value=value), b.fx("write", out, value=value)])]
        goal["emits"] = [{"resource": events, "value": value, "count": 0}]
        tags += ["zero_loop", "exact_emit_count"]
    elif index == 16:
        steps = [b.fx("write", aux, value=bad), b.loop(3, [b.call("overwrite")]), b.fx("read", aux, out="final"), b.fx("write", out, value=v("final"))]
        functions = {"overwrite": [b.fx("write", aux, value=value), b.fx("emit", events, value=value)]}
        goal["emits"] = [{"resource": events, "value": value, "count": 3}]
        routes = [program([a.loop(3, [a.fx("emit", events, value=value)]), a.fx("write", out, value=value)])]
        tags += ["overwrite", "subroutine", "exact_emit_count"]
    elif index == 17:
        for n, w in enumerate(worlds):
            w["files"][p("pointer")] = inp if n == 0 else aux
        steps = [b.fx("read", inp, out="x", key="read-alias"), b.fx("read", p("pointer"), out="ptr"), b.fx("read", v("ptr"), out="y", key="read-alias"), b.fx("write", out, value=v("y"))]
        tags += ["computed_resource", "receipt_conflict"]
    elif index == 18:
        steps = [b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.fx("write", aux, value=value, key="fork")], [b.fx("write", aux, value=bad, key="fork")]), b.call("seal")]
        functions = {"seal": [b.fx("write", aux, value=value, key="fork"), b.fx("write", out, value=value)]}
        tags += ["receipt_conflict", "subroutine"]
    elif index == 19:
        steps = [b.loop(2, [b.loop(3, [b.fx("emit", events, value=value)])]), b.fx("write", out, value=value)]
        goal["emits"] = [{"resource": events, "value": value, "count": 6}]
        routes = [program([a.call("triple"), a.call("triple"), a.fx("write", out, value=value)], {"triple": [a.loop(3, [a.fx("emit", events, value=value)])]})]
        tags += ["nested_loop", "exact_emit_count"]
    elif index == 20:
        steps = [b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.let("dest", out)], [b.let("dest", aux)]), b.call("put"), b.fx("read", v("dest"), out="echo"), b.fx("write", p("result"), value=v("echo"))]
        functions = {"put": [b.fx("write", v("dest"), value=value)]}
        goal["files"][p("result")] = value
        routes = [program([a.fx("write", out, value=value), a.fx("write", p("result"), value=value)])]
        tags += ["computed_resource", "subroutine"]
    elif index == 21:
        steps = [b.fx("read", inp, out="x"), b.fx("write", out, value=v("x")), b.fx("read", signal, out="s"), b.branch(v("s"), "left", [b.fx("write", aux, value=value)], [b.fx("delete", aux)])]
        goal["files"][aux] = value
        routes = [program([a.fx("write", aux, value=value)]), program([c.fx("write", out, value=value), c.fx("write", aux, value=value)])]
        tags += ["joint_goal", "partial_alternate"]
    elif index == 22:
        steps = [b.fx("read", inp, out="x", key="snapshot"), b.fx("delete", inp), b.fx("write", inp, value=bad), b.fx("read", inp, out="x", key="snapshot"), b.fx("write", out, value=v("x")), b.fx("delete", inp)]
        goal["absent"] = [inp]
        routes = [program([a.fx("delete", inp), a.fx("write", out, value=value)])]
        tags += ["read_snapshot", "delete_recreate"]
    else:
        worlds = [{"files": {signal: str(i), inp: value}, "grants": deepcopy(all_pairs)} for i in range(3)]
        observable_files = []
        steps = [b.fx("read", signal, out="s"), b.branch(v("s"), "0", [b.fx("write", out, value=bad)], [b.loop(2, [b.fx("write", out, value=value, key="same")])])]
        routes = []
        for i in (1, 2):
            q = Builder("cycle" + str(i) + stem)
            routes.append(program([q.fx("read", signal, out="s"), q.branch(v("s"), str(i), [q.fx("write", out, value=bad)], [q.fx("write", out, value=value)])]))
        tags += ["nonseparable", "route_cycle"]
    original = program(steps, functions)
    for w in worlds:
        w["grants"] = [list(pair) for pair in w["grants"]]
    return {"case_id": "p11-" + name + "-" + str(variant), "family": "p11_" + name,
            "split": "heldout", "generation": {"version": 1, "variant": variant, "lexical_variant": variant},
            "program": original, "routes": routes, "worlds": worlds, "goal": goal,
            "observable_files": observable_files, "observable_grants": observable_grants,
            "catalog_closed": True, "coverage_tags": tags,
            "source": "# Synthetic finite workflow\n\n```tsg-workflow\n" + json.dumps(original, ensure_ascii=False, indent=2) + "\n```\n"}


def build_cases():
    return [make_family(i, variant) for i in range(24) for variant in range(2)]


def structural_form(program):
    """Erase names, paths and scalar values; retain syntax and call structure."""
    def expr(x):
        if isinstance(x, dict):
            return {k: ([expr(y) for y in v] if isinstance(v, list) else expr(v)) for k, v in x.items()}
        return type(x).__name__
    functions = program.get("functions", {})
    def body(items):
        result = []
        for s in items:
            row = {"kind": s["kind"]}
            if s["kind"] == "effect":
                row.update(op=s["op"], resource=expr(s["resource"]))
                row.update({key: expr(s[key]) for key in ("value", "key") if key in s})
                if "out" in s:
                    row["out"] = True
            elif s["kind"] == "if":
                row.update(eq=[expr(x) for x in s["eq"]], then=body(s["then"]), **{"else": body(s["else"])})
            elif s["kind"] == "repeat":
                row.update(count="int", body=body(s["body"]))
            elif s["kind"] == "call":
                row["body"] = body(functions[s["fn"]])
            else:
                row["value"] = expr(s["value"])
            result.append(row)
        return result
    return {"steps": body(program["steps"]), "functions": sorted([body(items) for items in functions.values()], key=stable)}


def novelty_audit(cases):
    prior = defaultdict(list)
    sources = []
    for name in OLD_PATHS:
        path = ROOT / name
        if not path.exists():
            continue
        raw = path.read_bytes()
        sources.append({"path": name, "sha256": sha256(raw).hexdigest()})
        for case in [json.loads(line) for line in raw.splitlines() if line]:
            for route_index, prog in enumerate([case["program"], *case.get("routes", [])]):
                prior[stable(structural_form(prog))].append({"case_id": case["case_id"], "route_index": route_index})
    groups, matches = defaultdict(list), []
    for case in cases:
        key = stable(structural_form(case["program"]))
        groups[sha256(key.encode()).hexdigest()].append(case["case_id"])
        if key in prior:
            matches.append({"case_id": case["case_id"], "prior_exact_skeleton_matches": prior[key]})
    return {"method": "coarse-name-and-literal-erased-AST-v1", "prior_sources": sources,
            "unique_original_skeletons": len(groups), "within_new_groups": list(groups.values()),
            "prior_exact_skeleton_matches": matches,
            "limitation": "Syntax novelty is not semantic independence or real-world generalization; 48 lexical cases represent 24 authored structural templates."}


def scaling_cases():
    """Separate Cartesian scaling siblings, never counted as heldout families."""
    cases = []
    for nworld in (2, 4, 8, 16):
        for nroute in (2, 4, 8):
            case = make_family(19, 0)
            case.update(case_id=f"p11-scale-w{nworld}-r{nroute}", family="p11_scaling_nested_loop_exact_six",
                        parent_family="p11_nested_loop_exact_six", split="scaling")
            base = deepcopy(case["worlds"][0])
            case["worlds"] = []
            signal = case["observable_files"][0]
            for i in range(nworld):
                w = deepcopy(base)
                w["files"][signal] = str(i)
                case["worlds"].append(w)
            case["observable_files"] = []
            case["routes"] = [deepcopy(case["routes"][0]) for _ in range(nroute - 1)]
            case["scaling_limitation"] = "Routes are repeated semantic siblings; measures cache/certificate width, not new route diversity. Hidden marker keeps distinct but observationally equivalent worlds."
            cases.append(case)
    return cases


def audit(cases, records):
    executions = [e for rec in records for row in rec["executions"] for e in row]
    classes = [cl for rec in records for cl in rec["observation_classes"]]
    novelty = novelty_audit(cases)
    checks = {"48_cases": len(cases) == 48, "24_families": len({c["family"] for c in cases}) == 24,
              "24_distinct_original_structures": novelty["unique_original_skeletons"] == 24,
              "no_prior_exact_original_skeleton": not novelty["prior_exact_skeleton_matches"],
              "two_variants_per_family": set(Counter(c["family"] for c in cases).values()) == {2},
              "finite_public_worlds": all(2 <= len(c["worlds"]) <= 8 for c in cases),
              "finite_public_routes": all(1 <= len(c["routes"]) <= 5 for c in cases),
              "closed_catalog": all(c["catalog_closed"] for c in cases),
              "both_class_outcomes": {c["inherent_status"] for c in classes} == {"verified", "infeasible"}}
    return {"passed": all(checks.values()), "checks": checks,
            "case_count": len(cases), "family_count": 24, "world_route_cells": len(executions),
            "class_status_counts": dict(Counter(cl["inherent_status"] for cl in classes)),
            "run_error_counts": dict(Counter(e["error"] for e in executions if e["error"])),
            "guarded_safe_success_cells": sum(e["safe_success"] for e in executions),
            "receipt_reuse_cells": sum(e["receipt_reuses"] > 0 for e in executions),
            "minimum_run_queries_histogram": dict(Counter(str(cl["minimum_run_queries"]) for cl in classes)),
            "coverage_tags": dict(Counter(tag for c in cases for tag in c["coverage_tags"])),
            "novelty": novelty}


def jsonl_bytes(rows):
    return ("".join(stable(row) + "\n" for row in rows)).encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work/phase11-reference-firstpass")
    args = parser.parse_args()
    names = ["heldout.jsonl", "reference.jsonl", "scaling.jsonl", "reference_scaling.jsonl", "coverage.json", "provenance.json"]
    if any((args.output_dir / name).exists() for name in names):
        raise FileExistsError("Refusing to replace first-pass evidence")
    cases = build_cases()
    records = [reference_record(c) for c in cases]
    scaling = scaling_cases()
    scaled_records = [reference_record(c) for c in scaling]
    coverage = audit(cases, records)
    outputs = {"heldout.jsonl": jsonl_bytes(cases), "reference.jsonl": jsonl_bytes(records),
               "scaling.jsonl": jsonl_bytes(scaling), "reference_scaling.jsonl": jsonl_bytes(scaled_records),
               "coverage.json": (json.dumps(coverage, indent=2, sort_keys=True) + "\n").encode()}
    provenance = {"schema_version": 1, "authored_at_utc": datetime.now(timezone.utc).isoformat(),
                  "source_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in ("scripts/build_phase11_heldout.py", "src/tsg/truth_v6.py", "tests/test_reference_v11.py")},
                  "artifact_sha256": {name: sha256(raw).hexdigest() for name, raw in outputs.items()},
                  "model_outcomes_consulted": False, "production_modules_consulted": False,
                  "reference_modules": ["tsg.truth_v6"], "guarded_semantics": "independently implemented from semantic contract", "quota": QUOTA,
                  "first_pass_policy": "Write once; preserve all cases and every shortcoming; no outcome-based tuning.",
                  "coverage_passed": coverage["passed"]}
    outputs["provenance.json"] = (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        with (args.output_dir / name).open("xb") as handle:
            handle.write(raw)
    print(json.dumps({"case_count": len(cases), "family_count": 24, "scaling_siblings": len(scaling),
                      "coverage_passed": coverage["passed"], "aggregate_checks": coverage["checks"],
                      "generator_sha256": provenance["source_sha256"]["scripts/build_phase11_heldout.py"],
                      "heldout_sha256": provenance["artifact_sha256"]["heldout.jsonl"]}))
    if not coverage["passed"]:
        raise SystemExit("First pass retained with prospective shortfalls; do not tune cases.")


if __name__ == "__main__":
    main()

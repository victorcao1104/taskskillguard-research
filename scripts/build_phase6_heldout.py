"""Construct the independent Phase 6 structural holdout, without a VM or labels.

Authoring input: docs/phase6_design.md only. This file imports neither production
nor reference semantics. Its checks concern grammar, scope, finite bounds,
identifier hygiene, and source/reference representation equivalence.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "phase6" / "heldout.jsonl"
OPS = {"read", "write", "emit", "delete"}


def opaque(text):
    return sha256(("phase6-independent-holdout/v1/" + text).encode()).hexdigest()[:16]


class Builder:
    def __init__(self, family, seed, route=0):
        self.prefix = f"{family}/{seed}/{route}"
        self.counter = 0

    def node(self, kind, **fields):
        self.counter += 1
        return {"id": opaque(f"{self.prefix}/{self.counter}"), "kind": kind, **fields}

    def let(self, name, value):
        return self.node("let", name=name, value=value)

    def effect(self, op, resource, value=None, out=None, key=None):
        fields = {"op": op, "resource": resource}
        if value is not None:
            fields["value"] = value
        if out is not None:
            fields["out"] = out
        if key is not None:
            fields["key"] = key
        return self.node("effect", **fields)

    def branch(self, left, right, yes, no=()):
        return self.node("if", eq=[left, right], then=list(yes), **{"else": list(no)})

    def repeat(self, count, body):
        return self.node("repeat", count=count, body=body)

    def call(self, fn):
        return self.node("call", fn=fn)


def var(name):
    return {"var": name}


def cat(*values):
    return {"concat": list(values)}


def upper(value):
    return {"upper": value}


def program(steps, functions=None):
    return {"version": 1, "steps": steps, "functions": functions or {}}


def world(files, grants):
    return {"files": files, "grants": [list(pair) for pair in grants]}


def goal(files=None, absent=None, emits=None):
    return {"files": files or {}, "absent": absent or [], "emits": emits or []}


def make_case(family, seed, original, routes, worlds, target, closed=True):
    reference = deepcopy(original)
    source = (
        "# Synthetic workflow\n\n"
        "All resources below are entries in a finite synthetic workspace.\n"
        "Only the fenced workflow is executable.\n\n```tsg-workflow\n"
        + json.dumps(original, ensure_ascii=False, indent=2)
        + "\n```\n\nThe surrounding prose has no execution semantics.\n"
    )
    return {
        "case_id": opaque(f"case/{family}/{seed}"),
        "family": opaque(f"family/{family}"),
        "split": "heldout",
        "source": source,
        "program": reference,
        "routes": routes,
        "worlds": worlds,
        "goal": target,
        "catalog_closed": closed,
    }


def build_case(family, seed):
    b = Builder(family, seed)
    r = Builder(family, seed, 1)
    q = Builder(family, seed, 2)
    token, word = [("north", "cedar"), ("south", "harbor")][seed]
    root = f"workspace/{token}/"
    src, out, tmp, flag = [root + name for name in ("input", "output", "stage", "switch")]
    bus = f"channel/{token}"
    wanted = word.upper()

    if family == 1:
        # Entry branch selects a function whose branch consumes transformed input.
        original = program([
            b.effect("read", flag, out="a"),
            b.branch(var("a"), token, [b.call("f")], [b.effect("emit", "channel/unused", "unused")]),
        ], {"f": [
            b.effect("read", src, out="v"),
            b.let("v", upper(var("v"))),
            b.branch(var("v"), wanted, [b.effect("write", out, var("v"))]),
        ]})
        routes = [program([r.effect("read", src, out="v"), r.effect("write", out, upper(var("v")))])]
        worlds = [world({flag: token, src: word}, [("read", flag), ("read", src), ("write", out)])]
        target = goal({out: wanted})

    elif family == 2:
        # Function-produced values control a repeated branch with a nested call.
        original = program([
            b.call("f"),
            b.repeat(2, [b.branch(var("a"), token, [b.call("g")])]),
            b.effect("write", out, cat(var("v"), ":2")),
        ], {
            "f": [b.effect("read", flag, out="a"), b.effect("read", src, out="v")],
            "g": [b.effect("emit", bus, upper(var("v")))],
        })
        routes = [program([
            r.effect("read", src, out="v"),
            r.repeat(2, [r.effect("emit", bus, upper(var("v")))]),
            r.effect("write", out, cat(var("v"), ":2")),
        ])]
        worlds = [world({flag: token, src: word}, [("read", flag), ("read", src), ("emit", bus), ("write", out)])]
        target = goal({out: word + ":2"}, emits=[{"resource": bus, "value": wanted, "count": 2}])

    elif family == 3:
        # Loop calls a stateful read/append/write function; each round sees prior writes.
        original = program([
            b.let("a", word), b.repeat(3, [b.call("f")]),
        ], {"f": [b.effect("read", out, out="v"), b.effect("write", out, cat(var("v"), var("a")))]})
        routes = [program([r.effect("write", out, word * 3)])]
        worlds = [world({out: ""}, [("read", out), ("write", out)])]
        target = goal({out: word * 3})

    elif family == 4:
        # Repeated pure function updates an accumulator that later selects a publisher.
        original = program([
            b.effect("read", src, out="p"), b.let("a", ""),
            b.repeat(3, [b.call("f")]),
            b.branch(var("a"), word * 3, [b.call("g")], [b.effect("delete", "workspace/unused")]),
        ], {
            "f": [b.let("a", cat(var("a"), var("p")))],
            "g": [b.effect("write", out, upper(var("a")))],
        })
        routes = [program([
            r.effect("read", src, out="p"),
            r.effect("write", out, upper(cat(var("p"), var("p"), var("p")))),
        ])]
        worlds = [world({src: word}, [("read", src), ("write", out)])]
        target = goal({out: wanted * 3})

    elif family == 5:
        # A resource is built from read data, then validated by nested function branches.
        original = program([
            b.effect("read", flag, out="p"), b.let("d", cat(var("p"), "output")),
            b.effect("read", src, out="v"),
            b.branch(var("p"), root, [b.call("f")]),
            b.repeat(0, [b.effect("delete", out)]),
        ], {
            "f": [b.branch(var("d"), out, [
                b.branch(var("v"), word, [b.effect("write", var("d"), upper(var("v")))])
            ], [b.call("g")])],
            "g": [b.effect("emit", "channel/unused", "unused")],
            "h": [b.effect("delete", "workspace/never-called")],
        })
        routes = [program([r.effect("read", src, out="v"), r.effect("write", out, upper(var("v")))])]
        worlds = [world({flag: root, src: word}, [("read", flag), ("read", src), ("write", out)])]
        target = goal({out: wanted})

    elif family == 6:
        # Conditional cleanup calls a function with a repeated deletion and a final manifest.
        other = root + "obsolete"
        original = program([
            b.effect("read", flag, out="a"), b.branch(var("a"), token, [b.call("f")]),
        ], {"f": [
            b.repeat(2, [b.effect("delete", tmp)]),
            b.effect("delete", other), b.effect("write", out, cat(token, ":clean")),
        ]})
        routes = [program([
            r.effect("delete", other), r.effect("delete", tmp), r.effect("write", out, token + ":clean"),
        ])]
        worlds = [world({flag: token, tmp: "old-a", other: "old-b"}, [
            ("read", flag), ("delete", tmp), ("delete", other), ("write", out),
        ])]
        target = goal({out: token + ":clean"}, [tmp, other])

    elif family == 7:
        # Nested calls bind a dynamic destination and normalized value before branching.
        kw, ke = opaque(f"logical/{family}/{seed}/1"), opaque(f"logical/{family}/{seed}/2")
        original = program([b.call("f"), b.branch(var("v"), wanted, [b.call("h")])], {
            "f": [b.effect("read", src, out="v"), b.let("p", root), b.call("g")],
            "g": [b.let("v", upper(var("v"))), b.let("d", cat(var("p"), "output"))],
            "h": [b.effect("write", var("d"), var("v"), key=kw), b.effect("emit", bus, cat(var("v"), ":ready"), key=ke)],
        })
        routes = [program([
            r.effect("read", src, out="v"), r.let("v", upper(var("v"))),
            r.effect("emit", bus, cat(var("v"), ":ready"), key=ke), r.effect("write", out, var("v"), key=kw),
        ])]
        worlds = [world({src: word}, [("read", src), ("write", out), ("emit", bus)])]
        target = goal({out: wanted}, emits=[{"resource": bus, "value": wanted + ":ready", "count": 1}])

    elif family == 8:
        # A staged write is reread to drive cleanup and output; catalog has costly then lean routes.
        ks, kd, kw = [opaque(f"logical/{family}/{seed}/{i}") for i in range(3)]
        original = program([
            b.call("f"), b.effect("read", tmp, out="v"),
            b.branch(var("v"), wanted, [b.effect("delete", tmp, key=kd), b.effect("write", out, var("v"), key=kw)]),
        ], {"f": [b.effect("read", src, out="a"), b.effect("write", tmp, upper(var("a")), key=ks)]})
        routes = [program([
            r.effect("read", src, out="v"), r.effect("write", tmp, upper(var("v")), key=ks),
            r.effect("read", tmp, out="a"), r.effect("read", src, out="b"),
            r.effect("delete", tmp, key=kd), r.effect("write", out, var("a"), key=kw),
        ]), program([
            q.effect("read", src, out="v"), q.effect("delete", tmp, key=kd), q.effect("write", out, upper(var("v")), key=kw),
        ])]
        worlds = [world({src: word}, [("read", src), ("read", tmp), ("write", tmp), ("delete", tmp), ("write", out)])]
        target = goal({out: wanted}, [tmp])

    elif family == 9:
        # Nested repeats surround function calls and a conditional emit, requiring exact multiplicity.
        original = program([
            b.effect("read", src, out="v"), b.repeat(2, [b.call("f")]),
        ], {"f": [b.repeat(2, [b.branch(var("v"), word, [b.effect("emit", bus, upper(var("v")))])])]})
        routes = [program([
            r.effect("read", src, out="v"),
            r.repeat(3, [r.effect("emit", bus, upper(var("v")))]),
            r.effect("emit", bus, upper(var("v"))),
        ])]
        worlds = [world({src: word}, [("read", src), ("emit", bus)])]
        target = goal(emits=[{"resource": bus, "value": wanted, "count": 4}])

    elif family == 10:
        # Shared cache pipeline differs in initial state and write permission across worlds.
        original = program([
            b.effect("read", src, out="v"), b.let("v", upper(var("v"))), b.call("f"), b.call("g"),
        ], {
            "f": [b.effect("write", tmp, var("v"))],
            "g": [b.effect("read", tmp, out="a"), b.effect("write", out, var("a"))],
        })
        routes = [program([r.effect("read", src, out="v"), r.effect("write", out, upper(var("v")))])]
        grants = [("read", src), ("read", tmp), ("write", out)]
        worlds = [world({src: word}, grants + [("write", tmp)]), world({src: word, tmp: wanted}, grants)]
        target = goal({out: wanted})

    elif family == 11:
        # Two data-dependent guards occur across call boundaries; one possible world cannot reach goal.
        original = program([
            b.effect("read", flag, out="a"), b.branch(var("a"), token, [b.call("f")]),
        ], {"f": [
            b.effect("read", src, out="v"),
            b.branch(var("v"), word, [b.effect("write", out, upper(var("v")))], [b.repeat(0, [b.effect("delete", tmp)])]),
        ]})
        routes = [program([
            r.effect("read", src, out="v"), r.effect("read", flag, out="a"),
            r.branch(var("v"), word, [r.branch(var("a"), token, [r.effect("write", out, upper(var("v")))])]),
        ])]
        grants = [("read", flag), ("read", src), ("write", out)]
        worlds = [world({flag: token, src: word}, grants), world({flag: token + "-closed", src: word}, grants)]
        target = goal({out: wanted})

    elif family == 12:
        # Open catalog: a function initializes a loop-carried value; later branch emits and publishes.
        original = program([
            b.call("f"), b.repeat(2, [b.call("g")]),
            b.branch(var("a"), word * 2, [b.effect("emit", bus, upper(var("a"))), b.effect("write", out, var("a"))]),
        ], {
            "f": [b.effect("read", src, out="p"), b.let("a", "")],
            "g": [b.branch(var("p"), word, [b.let("a", cat(var("a"), var("p")))])],
        })
        routes = [program([
            r.effect("read", src, out="p"), r.effect("read", src, out="v"),
            r.let("a", cat(var("p"), var("v"))),
            r.effect("emit", bus, upper(var("a"))), r.effect("write", out, var("a")),
        ]), program([
            q.effect("read", src, out="v"), q.let("a", cat(var("v"), var("v"))),
            q.effect("write", out, var("a")), q.effect("emit", bus, upper(var("a"))),
        ])]
        worlds = [world({src: word}, [("read", src), ("emit", bus), ("write", out)])]
        target = goal({out: word * 2}, emits=[{"resource": bus, "value": wanted * 2, "count": 1}])
    else:
        raise ValueError(family)
    return make_case(family, seed, original, routes, worlds, target, closed=family != 12)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expression(value, defined=None):
    """Validate expressions and optionally reject potentially unbound variables."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return
    require(isinstance(value, dict) and len(value) == 1, "expression shape")
    if "var" in value:
        require(isinstance(value["var"], str), "variable name")
        require(defined is None or value["var"] in defined, "unbound variable")
    elif "concat" in value:
        require(isinstance(value["concat"], list), "concat operands")
        for child in value["concat"]:
            expression(child, defined)
    elif "upper" in value:
        expression(value["upper"], defined)
    else:
        raise AssertionError("unknown expression")


def validate_program(ast):
    require(set(ast) == {"version", "steps", "functions"} and ast["version"] == 1, "program schema")
    require(isinstance(ast["functions"], dict), "functions object")
    ids = set()
    signatures = {
        "let": ({"id", "kind", "name", "value"}, set()),
        "effect": ({"id", "kind", "op", "resource"}, {"value", "out", "key"}),
        "if": ({"id", "kind", "eq", "then", "else"}, set()),
        "repeat": ({"id", "kind", "count", "body"}, set()),
        "call": ({"id", "kind", "fn"}, set()),
    }

    def grammar(steps):
        require(isinstance(steps, list), "steps array")
        for node in steps:
            require(isinstance(node, dict), "node object")
            require(re.fullmatch("[0-9a-f]{16}", node.get("id", "")) is not None, "opaque ID")
            require(node["id"] not in ids, "duplicate site ID")
            ids.add(node["id"])
            kind = node.get("kind")
            require(kind in signatures, "step kind")
            required, optional = signatures[kind]
            require(required <= set(node) <= required | optional, "step keys")
            if kind == "let":
                require(isinstance(node["name"], str), "binding name")
                expression(node["value"])
            elif kind == "effect":
                require(node["op"] in OPS, "effect operation")
                expression(node["resource"])
                for key in ("value", "key"):
                    if key in node:
                        expression(node[key])
                require("out" not in node or isinstance(node["out"], str), "effect output binding")
            elif kind == "if":
                require(isinstance(node["eq"], list) and len(node["eq"]) == 2, "eq arity")
                for value in node["eq"]:
                    expression(value)
                grammar(node["then"])
                grammar(node["else"])
            elif kind == "repeat":
                require(type(node["count"]) is int and 0 <= node["count"] <= 3, "repeat bound")
                grammar(node["body"])
            else:
                require(node["fn"] in ast["functions"], "undefined function")

    grammar(ast["steps"])
    for name, body in ast["functions"].items():
        require(isinstance(name, str), "function name")
        grammar(body)

    def walk(steps, defined, active=()):
        defined = set(defined)
        bound = 0
        for node in steps:
            bound += 1
            kind = node["kind"]
            if kind == "let":
                expression(node["value"], defined)
                defined.add(node["name"])
            elif kind == "effect":
                for key in ("resource", "value", "key"):
                    if key in node:
                        expression(node[key], defined)
                if "out" in node:
                    defined.add(node["out"])
            elif kind == "if":
                for value in node["eq"]:
                    expression(value, defined)
                left, lb = walk(node["then"], defined, active)
                right, rb = walk(node["else"], defined, active)
                defined = left & right
                bound += max(lb, rb)
            elif kind == "repeat":
                after, child_bound = walk(node["body"], defined, active)
                if node["count"]:
                    defined = after
                bound += node["count"] * child_bound
            else:
                name = node["fn"]
                require(name not in active, "recursive function")
                defined, child_bound = walk(ast["functions"][name], defined, active + (name,))
                bound += child_bound
        return defined, bound

    # A separate call-graph check includes unreachable functions as well.
    def check_calls(steps, active=()):
        for node in steps:
            if node["kind"] == "call":
                name = node["fn"]
                require(name not in active, "unreachable recursive function")
                check_calls(ast["functions"][name], active + (name,))
            elif node["kind"] == "if":
                check_calls(node["then"], active)
                check_calls(node["else"], active)
            elif node["kind"] == "repeat":
                check_calls(node["body"], active)

    for name, body in ast["functions"].items():
        check_calls(body, (name,))
    _, maximum_steps = walk(ast["steps"], set())
    require(maximum_steps <= 100, "step execution bound")
    return ids, maximum_steps


def validate_cases(cases):
    require(len(cases) == 24, "case count")
    require(len({c["case_id"] for c in cases}) == 24, "unique cases")
    counts = Counter(c["family"] for c in cases)
    require(len(counts) == 12 and set(counts.values()) == {2}, "two seeds per family")

    def shape(value, key=None):
        if isinstance(value, dict):
            return tuple((k, shape(v, k)) for k, v in sorted(value.items()) if k != "id")
        if isinstance(value, list):
            return tuple(shape(v) for v in value)
        if key in {"kind", "op", "fn", "name", "var", "count", "version"}:
            return value
        return type(value).__name__

    families = {}
    for case in cases:
        structural = shape([case["program"], *case["routes"]])
        previous = families.setdefault(case["family"], structural)
        require(previous == structural, "seed variants must preserve structure")
    require(len(set(families.values())) == 12, "distinct structural families")
    all_ids = set()
    maximum = 0
    for case in cases:
        require(set(case) == {"case_id", "family", "split", "source", "program", "routes", "worlds", "goal", "catalog_closed"}, "case keys; no labels")
        for key in ("case_id", "family"):
            require(re.fullmatch("[0-9a-f]{16}", case[key]) is not None, "opaque metadata ID")
        require(case["split"] == "heldout" and type(case["catalog_closed"]) is bool, "split/closure")
        require(case["source"].count("```tsg-workflow") == 1 and case["source"].count("```") == 2, "one source block")
        decoded = json.loads(case["source"].split("```tsg-workflow\n", 1)[1].split("\n```", 1)[0])
        require(decoded == case["program"], "source/reference equivalence")
        require(isinstance(case["routes"], list) and case["routes"], "nonempty supplied routes")
        for ast in [case["program"], *case["routes"]]:
            site_ids, bound = validate_program(ast)
            require(not (site_ids & all_ids), "site IDs unique across every program and case")
            all_ids |= site_ids
            maximum = max(maximum, bound)
        require(case["worlds"], "nonempty worlds")
        target = case["goal"]
        require(set(target) == {"files", "absent", "emits"}, "goal keys")
        require(all(isinstance(k, str) and isinstance(v, str) for k, v in target["files"].items()), "goal strings")
        require(all(isinstance(p, str) for p in target["absent"]), "absent paths")
        for emit in target["emits"]:
            require(set(emit) == {"resource", "value", "count"}, "emit goal keys")
            require(isinstance(emit["resource"], str) and isinstance(emit["value"], str), "emit goal strings")
            require(type(emit["count"]) is int and emit["count"] > 0, "positive emit count")
        for possible in case["worlds"]:
            require(set(possible) == {"files", "grants"}, "world keys")
            require(all(isinstance(k, str) and isinstance(v, str) for k, v in possible["files"].items()), "world strings")
            require(all(isinstance(p, list) and len(p) == 2 and p[0] in OPS and isinstance(p[1], str) for p in possible["grants"]), "grants")
            initially_true = (
                all(possible["files"].get(p) == value for p, value in target["files"].items())
                and all(p not in possible["files"] for p in target["absent"])
                and not target["emits"]
            )
            require(not initially_true, "initial goal must be false")
    return {"cases": len(cases), "families": len(counts), "worlds": sum(len(c["worlds"]) for c in cases), "unique_site_ids": len(all_ids), "maximum_step_upper_bound": maximum}


def main():
    cases = [build_case(family, seed) for family in range(1, 13) for seed in range(2)]
    # Fixed digest order obscures construction order without a random dependency.
    cases.sort(key=lambda case: case["case_id"])
    report = validate_cases(cases)
    content = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in cases)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    report["sha256"] = sha256(content.encode()).hexdigest()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

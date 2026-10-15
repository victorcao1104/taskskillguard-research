"""Author the targeted, grant-paired Phase 6 supplement without executing a VM.

Inputs read by the author: phase6_design.md and phase6_challenge_design.md.
No production, truth, model output, development fixtures, or old results are used.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data" / "phase6" / "challenge.jsonl"
OPERATIONS = {"read", "write", "emit", "delete"}


def opaque(value):
    return sha256(("phase6-targeted-challenge/v1/" + value).encode()).hexdigest()[:16]


class Builder:
    def __init__(self, family, variant, route):
        self.namespace = f"{family}/{variant}/{route}"
        self.serial = 0

    def node(self, kind, **fields):
        self.serial += 1
        return {"id": opaque(f"{self.namespace}/{self.serial}"), "kind": kind, **fields}

    def let(self, name, value):
        return self.node("let", name=name, value=value)

    def effect(self, op, resource, value=None, out=None):
        fields = {"op": op, "resource": resource}
        if value is not None:
            fields["value"] = value
        if out is not None:
            fields["out"] = out
        return self.node("effect", **fields)

    def branch(self, left, right, yes, no=()):
        return self.node("if", eq=[left, right], then=list(yes), **{"else": list(no)})

    def call(self, name):
        return self.node("call", fn=name)

    def repeat(self, count, body):
        return self.node("repeat", count=count, body=body)


def v(name):
    return {"var": name}


def cat(*values):
    return {"concat": list(values)}


def up(value):
    return {"upper": value}


def ast(steps, functions=None):
    return {"version": 1, "steps": steps, "functions": functions or {}}


def build_case(family, variant):
    b, c, e = [Builder(family, variant, route) for route in range(3)]
    word = ("amber", "birch", "coral", "delta", "elm", "flint")[family - 1]
    root = f"workspace/{word}/"
    src, out, stage, optional = [root + suffix for suffix in ("input", "output", "stage", "memo")]
    bus = f"channel/{word}"
    files = {src: word, optional: "previous"}
    required_grants = [("read", src), ("write", out), ("write", stage), ("read", stage)]
    absent = []

    if family == 1:
        # Optional dynamic write precedes all data reads; staged alternative costs four calls.
        extra_grant = ("write", optional)
        original = ast([
            b.let("p", root), b.call("f"), b.effect("read", src, out="x"),
            b.let("x", up(v("x"))), b.effect("write", out, v("x")),
        ], {"f": [b.branch(v("p"), root, [b.effect("write", cat(v("p"), "memo"), "observed")])]})
        cheap = ast([c.effect("read", src, out="x"), c.effect("write", out, up(v("x")))])
        expensive = ast([
            e.effect("read", src, out="x"), e.effect("write", stage, up(v("x"))),
            e.effect("read", stage, out="y"), e.effect("write", out, v("y")),
        ])
        expected = word.upper()

    elif family == 2:
        # Optional repeated emit, followed by function-bound data flow and doubled publication.
        extra_grant = ("emit", bus)
        original = ast([b.call("f"), b.call("g"), b.effect("write", out, up(cat(v("x"), v("x"))))], {
            "f": [b.repeat(2, [b.effect("emit", bus, "observed")])],
            "g": [b.effect("read", src, out="x")],
        })
        cheap = ast([c.effect("read", src, out="x"), c.effect("write", out, up(cat(v("x"), v("x"))))])
        expensive = ast([e.call("f"), e.repeat(2, [e.effect("write", stage, v("x"))]), e.call("g")], {
            "f": [e.effect("read", src, out="x"), e.let("x", up(cat(v("x"), v("x"))))],
            "g": [e.effect("read", stage, out="y"), e.effect("write", out, v("y"))],
        })
        expected = word.upper() * 2

    elif family == 3:
        # Optional delete is independent of a pure repeated accumulator and its output.
        extra_grant = ("delete", optional)
        original = ast([
            b.branch(word, word, [b.call("f")]), b.let("x", ""),
            b.repeat(2, [b.call("g")]), b.effect("write", out, up(v("x"))),
        ], {
            "f": [b.effect("delete", optional)],
            "g": [b.let("x", cat(v("x"), word))],
        })
        cheap = ast([c.let("x", cat(word, word)), c.effect("write", out, up(v("x")))])
        expensive = ast([
            e.effect("write", stage, word), e.effect("read", stage, out="p"),
            e.let("x", ""), e.repeat(2, [e.let("x", cat(v("x"), v("p")))]),
            e.effect("write", out, up(v("x"))),
        ])
        expected = word.upper() * 2

    elif family == 4:
        # Optional loop/call write precedes a dynamic publisher; expensive route cleans staging.
        extra_grant = ("write", optional)
        original = ast([
            b.let("p", root), b.repeat(1, [b.call("f")]),
            b.branch(v("p"), root, [b.call("g")]),
        ], {
            "f": [b.effect("write", cat(v("p"), "memo"), "observed")],
            "g": [b.effect("read", src, out="x"), b.let("d", cat(v("p"), "output")), b.effect("write", v("d"), up(v("x")))],
        })
        cheap = ast([c.call("f"), c.call("g")], {
            "f": [c.effect("read", src, out="x")],
            "g": [c.effect("write", out, up(v("x")))],
        })
        expensive = ast([
            e.effect("read", src, out="x"), e.effect("write", stage, up(v("x"))),
            e.effect("read", stage, out="y"),
            e.branch(v("y"), word.upper(), [e.effect("delete", stage), e.effect("write", out, v("y"))]),
        ])
        required_grants.append(("delete", stage))
        absent = [stage]
        expected = word.upper()

    elif family == 5:
        # Nested call/branch optional emit precedes a pure triple accumulator.
        extra_grant = ("emit", bus)
        original = ast([
            b.call("f"), b.let("x", ""), b.repeat(3, [b.let("x", cat(v("x"), word))]),
            b.effect("write", out, up(v("x"))),
        ], {
            "f": [b.branch(word, word, [b.call("g")])],
            "g": [b.effect("emit", bus, "observed")],
        })
        cheap = ast([
            c.let("x", ""), c.repeat(3, [c.call("f")]), c.effect("write", out, up(v("x"))),
        ], {"f": [c.let("x", cat(v("x"), word))]})
        expensive = ast([
            e.effect("write", stage, cat(word, word, word)), e.effect("read", stage, out="x"),
            e.branch(v("x"), word * 3, [e.effect("write", out, up(v("x")))]),
        ])
        expected = word.upper() * 3

    elif family == 6:
        # Optional read has an unused result; later nested guards use a separate input.
        extra_grant = ("read", optional)
        original = ast([
            b.repeat(1, [b.branch(word, word, [b.call("f")])]),
            b.call("g"), b.branch(v("x"), word, [b.call("h")]),
        ], {
            "f": [b.effect("read", optional, out="unused")],
            "g": [b.effect("read", src, out="x")],
            "h": [b.effect("write", out, up(v("x")))],
        })
        cheap = ast([
            c.effect("read", src, out="x"), c.branch(v("x"), word, [c.effect("write", out, up(v("x")))]),
        ])
        expensive = ast([
            e.effect("read", src, out="x"), e.call("f"), e.effect("read", stage, out="y"),
            e.branch(v("y"), word.upper(), [e.call("g")]),
        ], {
            "f": [e.repeat(1, [e.effect("write", stage, up(v("x")))])],
            "g": [e.effect("write", out, v("y"))],
        })
        expected = word.upper()
    else:
        raise ValueError(family)

    routes = [cheap, expensive] if family % 2 else [expensive, cheap]
    grants = required_grants + ([extra_grant] if variant == 0 else [])
    source = (
        "# Synthetic workflow\n\nResources denote finite VM entries.\n\n```tsg-workflow\n"
        + json.dumps(original, indent=2)
        + "\n```\n\nOnly the fenced workflow has execution semantics.\n"
    )
    return {
        "case_id": opaque(f"case/{family}/{variant}"),
        "family": opaque(f"family/{family}"),
        "split": "challenge",
        "source": source,
        "program": deepcopy(original),
        "routes": routes,
        "worlds": [{"files": files, "grants": [list(pair) for pair in grants]}],
        "goal": {"files": {out: expected}, "absent": absent, "emits": []},
        "catalog_closed": True,
    }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def expression(value, defined=None):
    # These fixtures intentionally use only string-valued expressions.
    if isinstance(value, str):
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


def validate_program(program):
    require(set(program) == {"version", "steps", "functions"} and program["version"] == 1, "program schema")
    ids = set()
    effects = set()
    allowed = {
        "let": ({"id", "kind", "name", "value"}, set()),
        "effect": ({"id", "kind", "op", "resource"}, {"value", "out"}),
        "if": ({"id", "kind", "eq", "then", "else"}, set()),
        "repeat": ({"id", "kind", "count", "body"}, set()),
        "call": ({"id", "kind", "fn"}, set()),
    }

    def grammar(nodes):
        require(isinstance(nodes, list), "steps list")
        for node in nodes:
            require(re.fullmatch("[0-9a-f]{16}", node.get("id", "")) is not None, "opaque site ID")
            require(node["id"] not in ids, "unique site ID")
            ids.add(node["id"])
            kind = node.get("kind")
            require(kind in allowed, "step kind")
            required, optional = allowed[kind]
            require(required <= set(node) <= required | optional, "step fields; explicit keys disallowed")
            if kind == "let":
                require(isinstance(node["name"], str), "binding name")
                expression(node["value"])
            elif kind == "effect":
                effects.add(node["id"])
                require(node["op"] in OPERATIONS, "effect op")
                expression(node["resource"])
                if "value" in node:
                    expression(node["value"])
                require("out" not in node or isinstance(node["out"], str), "output binding")
            elif kind == "if":
                require(isinstance(node["eq"], list) and len(node["eq"]) == 2, "eq arity")
                for item in node["eq"]:
                    expression(item)
                grammar(node["then"])
                grammar(node["else"])
            elif kind == "repeat":
                require(type(node["count"]) is int and 0 <= node["count"] <= 3, "repeat bound")
                grammar(node["body"])
            else:
                require(node["fn"] in program["functions"], "defined function")

    require(isinstance(program["functions"], dict), "functions dict")
    grammar(program["steps"])
    for name, nodes in program["functions"].items():
        require(isinstance(name, str), "function name")
        grammar(nodes)

    def scope_and_bound(nodes, defined, active=()):
        defined, steps, calls = set(defined), 0, 0
        for node in nodes:
            steps += 1
            kind = node["kind"]
            if kind == "let":
                expression(node["value"], defined)
                defined.add(node["name"])
            elif kind == "effect":
                expression(node["resource"], defined)
                if "value" in node:
                    expression(node["value"], defined)
                if "out" in node:
                    defined.add(node["out"])
                calls += 1
            elif kind == "if":
                for item in node["eq"]:
                    expression(item, defined)
                left, sl, cl = scope_and_bound(node["then"], defined, active)
                right, sr, cr = scope_and_bound(node["else"], defined, active)
                defined = left & right
                steps, calls = steps + max(sl, sr), calls + max(cl, cr)
            elif kind == "repeat":
                after, sn, cn = scope_and_bound(node["body"], defined, active)
                if node["count"]:
                    defined = after
                steps, calls = steps + node["count"] * sn, calls + node["count"] * cn
            else:
                name = node["fn"]
                require(name not in active, "acyclic calls")
                defined, sn, cn = scope_and_bound(program["functions"][name], defined, active + (name,))
                steps, calls = steps + sn, calls + cn
        return defined, steps, calls

    _, steps, calls = scope_and_bound(program["steps"], set())
    require(steps <= 100, "100-step bound")
    # Every function is called from entry in these constructions. Suppression keeps
    # output bindings as strings, so the same all-branches scope proof applies to
    # each single-site intervention; no alternate branch can introduce an error.
    return ids, effects, steps, calls


def without_ids(value):
    if isinstance(value, dict):
        return {key: without_ids(child) for key, child in value.items() if key != "id"}
    if isinstance(value, list):
        return [without_ids(child) for child in value]
    return value


def structure(value, key=None):
    if isinstance(value, dict):
        return tuple((name, structure(child, name)) for name, child in sorted(value.items()) if name != "id")
    if isinstance(value, list):
        return tuple(structure(child) for child in value)
    if key in {"kind", "op", "fn", "name", "var", "count", "version"}:
        return value
    return type(value).__name__


def static_effects(program):
    def visit(nodes):
        for node in nodes:
            if node["kind"] == "effect":
                yield node
            elif node["kind"] == "if":
                yield from visit(node["then"])
                yield from visit(node["else"])
            elif node["kind"] == "repeat":
                yield from visit(node["body"])
    yield from visit(program["steps"])
    for body in program["functions"].values():
        yield from visit(body)


def validate(cases):
    require(len(cases) == 12 and len({case["case_id"] for case in cases}) == 12, "12 unique cases")
    require(Counter(case["family"] for case in cases) == {opaque(f"family/{f}"): 2 for f in range(1, 7)}, "six paired families")
    all_ids, structural_families = set(), set()
    max_steps, max_effects, route_pairs = 0, 0, []
    for case in cases:
        require(set(case) == {"case_id", "family", "split", "source", "program", "routes", "worlds", "goal", "catalog_closed"}, "case schema without labels")
        require(case["split"] == "challenge" and case["catalog_closed"] is True, "split and closure")
        for field in ("case_id", "family"):
            require(re.fullmatch("[0-9a-f]{16}", case[field]) is not None, "opaque case/family IDs")
        require(case["source"].count("```tsg-workflow") == 1 and case["source"].count("```") == 2, "one fenced program")
        decoded = json.loads(case["source"].split("```tsg-workflow\n", 1)[1].split("\n```", 1)[0])
        require(decoded == case["program"], "source/reference equivalence")
        require(len(case["routes"]) == 2 and len(case["worlds"]) == 1, "two alternatives and one world")
        counts = []
        for program in [case["program"], *case["routes"]]:
            ids, effects, steps, calls = validate_program(program)
            require(not (ids & all_ids), "globally unique site IDs")
            all_ids |= ids
            max_steps, max_effects = max(max_steps, steps), max(max_effects, calls)
            counts.append(calls)
        require(min(counts[1:]) <= 2 < max(counts[1:]) <= 5, "target route cost regime")
        route_pairs.append(tuple(counts[1:]))
        possible = case["worlds"][0]
        require(set(possible) == {"files", "grants"}, "world fields")
        require(all(isinstance(path, str) and isinstance(text, str) for path, text in possible["files"].items()), "file strings")
        require(all(isinstance(pair, list) and len(pair) == 2 and pair[0] in OPERATIONS and isinstance(pair[1], str) for pair in possible["grants"]), "grants")
        require(len({tuple(pair) for pair in possible["grants"]}) == len(possible["grants"]), "no duplicate grants")
        supplied_grants = set(map(tuple, possible["grants"]))
        for route in case["routes"]:
            for effect in static_effects(route):
                require(isinstance(effect["resource"], str), "route resources are literal")
                require((effect["op"], effect["resource"]) in supplied_grants, "every route effect has a supplied grant")
        target = case["goal"]
        require(set(target) == {"files", "absent", "emits"} and target["emits"] == [], "goal schema")
        require(all(isinstance(path, str) and isinstance(text, str) for path, text in target["files"].items()), "goal file strings")
        require(all(isinstance(path, str) for path in target["absent"]), "absence strings")
        require(any(possible["files"].get(path) != text for path, text in target["files"].items()), "initially unmet goal")
        structural_families.add(structure([case["program"], *case["routes"]]))
    require(len(structural_families) == 6, "six distinct structures")
    require(sum(left < right for left, right in route_pairs) == 6, "three cheap-first paired families")
    require(sum(left > right for left, right in route_pairs) == 6, "three expensive-first paired families")
    for family in range(1, 7):
        pair = [case for case in cases if case["family"] == opaque(f"family/{family}")]
        a, b = pair
        require(without_ids(a["program"]) == without_ids(b["program"]), "same original within pair")
        require(without_ids(a["routes"]) == without_ids(b["routes"]), "same catalog within pair")
        require(a["goal"] == b["goal"] and a["worlds"][0]["files"] == b["worlds"][0]["files"], "same task and starting state")
        ga, gb = [set(map(tuple, case["worlds"][0]["grants"])) for case in pair]
        require(len(ga ^ gb) == 1 and (ga <= gb or gb <= ga), "exactly one paired grant change")
    return {"cases": 12, "families": 6, "worlds": 12, "site_ids": len(all_ids), "maximum_step_bound": max_steps, "maximum_effect_bound": max_effects, "cheap_first_families": 3, "expensive_first_families": 3}


def main():
    cases = [build_case(family, variant) for family in range(1, 7) for variant in range(2)]
    cases.sort(key=lambda case: case["case_id"])
    report = validate(cases)
    encoded = "".join(json.dumps(case, sort_keys=True) + "\n" for case in cases).encode()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(encoded)
    report["sha256"] = sha256(encoded).hexdigest()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

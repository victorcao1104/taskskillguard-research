"""Independently authored Phase 9 finite fixtures and executable reference truth.

Only frozen truth_v6/truth_v7 are imported. Production protocols, query/recovery
implementations and model outcomes are never consulted. Do not invoke main to
reveal the heldout until the separate production freeze has been recorded.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.truth_v6 import run, static_sites  # noqa: E402
from tsg.truth_v7 import AXES, evaluate_case  # noqa: E402

OLD_PATHS = ("data/phase6/dev.jsonl", "data/phase6/heldout.jsonl",
             "data/phase6/challenge.jsonl", "data/phase7/heldout.jsonl",
             "data/phase8/heldout.jsonl")
VALUES = ("rimu_73", "saffron:89")
TYPES = ("yes", "no", "unknown", "not_applicable")


def v(name):
    return {"var": name}


class Build:
    def __init__(self, prefix="a"):
        self.prefix, self.index = prefix, 0

    def step(self, kind, **fields):
        self.index += 1
        return {"id": f"{self.prefix}{self.index:03d}", "kind": kind, **fields}

    def fx(self, op, path, **fields):
        return self.step("effect", op=op, resource=path, **fields)

    def let(self, name, value):
        return self.step("let", name=name, value=value)

    def branch(self, left, right, yes, no=()):
        return self.step("if", eq=[left, right], then=list(yes), **{"else": list(no)})

    def repeat(self, count, body):
        return self.step("repeat", count=count, body=list(body))

    def call(self, fn):
        return self.step("call", fn=fn)


def prog(steps, functions=None):
    return {"version": 1, "steps": list(steps), "functions": functions or {}}


def world(files, grants):
    return {"files": dict(files), "grants": [list(g) for g in grants]}


def fixture(program, worlds, routes, goal, closed=True, hidden=False):
    result = {"program": program, "worlds": worlds, "routes": routes,
              "goal": goal, "catalog_closed": closed}
    if hidden:
        result.update(observable_files=[], observable_grants=[])
    return result


def direct(path, value):
    b = Build("d")
    return prog([b.fx("write", path, value=value)])


def write_through_pointer(p, value, variant):
    """File-selected write/read alias followed by a verification branch."""
    b = Build()
    original = prog([b.fx("read", p("pointer"), out="target"),
                     b.fx("read", p("source"), out="payload"),
                     b.fx("write", v("target"), value=v("payload")),
                     b.fx("read", v("target"), out="check"),
                     b.branch(v("check"), value,
                              [b.fx("write", p("out"), value={"upper": v("check")})],
                              [b.fx("delete", p("stale"))])])
    grants = [("read", p("pointer")), ("read", p("source")), ("write", p("left")),
              ("read", p("left")), ("read", p("right")), ("write", p("out"))]
    worlds = [world({p("pointer"): p(target), p("source"): value}, grants) for target in ("left", "right")]
    return fixture(original, worlds, [], {"files": {p("out"): value.upper()}})


def staged_accumulator(p, value, variant):
    """Read-after-write accumulation with first-iteration marker selection."""
    b = Build()
    original = prog([b.fx("read", p("source"), out="chunk"), b.let("acc", ""),
                     b.repeat(2, [b.fx("write", p("scratch"), value=v("acc")),
                                  b.fx("read", p("scratch"), out="saved"),
                                  b.branch(v("saved"), "", [b.fx("write", p("marker"), value="first")],
                                           [b.fx("read", p("marker"))]),
                                  b.let("acc", {"concat": [v("saved"), v("chunk")]})]),
                     b.fx("write", p("out"), value=v("acc"))])
    grants = [("read", p("source")), ("write", p("scratch")), ("read", p("scratch")),
              ("read", p("marker")), ("write", p("out")), ("write", p("marker"))]
    worlds = [world({p("source"): value}, grants), world({p("source"): "bad"}, grants[:-1])]
    return fixture(original, worlds, [], {"files": {p("out"): value * 2}}, hidden=True)


def conditional_rotation(p, value, variant):
    """Destructive rotation commits or rolls back from an independently read backup."""
    b = Build()
    original = prog([b.fx("read", p("record"), out="old"),
                     b.fx("write", p("backup"), value=v("old")), b.fx("delete", p("record")),
                     b.fx("read", p("backup"), out="backup"),
                     b.branch(v("backup"), value,
                              [b.fx("write", p("out"), value={"concat": ["rotated/", v("backup")]})],
                              [b.fx("write", p("record"), value=v("backup"))]),
                     b.repeat(0, [b.fx("emit", p("alarm"), value="unreachable")])])
    grants = [("read", p("record")), ("write", p("backup")), ("delete", p("record")),
              ("write", p("out")), ("write", p("record"))]
    worlds = [world({p("record"): text}, grants) for text in (value, "mismatch")]
    return fixture(original, worlds, [], {"files": {p("out"): "rotated/" + value}, "absent": [p("record")]})


def pointer_chain_fold(p, value, variant):
    """A bounded linked-file traversal folds next pointers into the final payload."""
    b = Build()
    folded = (p("node2") + p("node3") + value).upper()
    original = prog([b.fx("read", p("head"), out="handle"), b.let("trail", ""),
                     b.repeat(3, [b.call("visit")]),
                     b.fx("write", p("out"), value=v("trail")),
                     b.branch(v("trail"), folded, [b.fx("emit", p("audit"), value="linked")],
                              [b.fx("delete", p("scratch"))])], {
        "visit": [b.fx("read", v("handle"), out="next"),
                  b.let("trail", {"concat": [v("trail"), {"upper": v("next")}]}),
                  b.let("handle", v("next"))]})
    files = {p("head"): p("node1"), p("node1"): p("node2"), p("node2"): p("node3"), p("node3"): value}
    grants = [("read", p(n)) for n in ("head", "node1", "node2", "node3")] + [("write", p("out")), ("emit", p("audit"))]
    return fixture(original, [world(files, grants), world({**files, p("out"): folded}, grants)], [],
                   {"files": {p("out"): folded}, "emits": [{"resource": p("audit"), "value": "linked", "count": 1}]})


def resource_key_poison(p, value, variant):
    """A file-supplied receipt aliases a write and a branch-selected delete."""
    b = Build()
    original = prog([b.fx("read", p("ticket"), out="ticket"),
                     b.fx("write", p("checkpoint"), value=value, key=v("ticket")),
                     b.fx("read", p("mode"), out="mode"),
                     b.branch(v("mode"), "erase", [b.fx("delete", p("checkpoint"), key=v("ticket"))],
                              [b.call("inspect")]),
                     b.fx("write", p("out"), value=value)], {
        "inspect": [b.fx("read", p("checkpoint"), out="ignored")]})
    grants = [("read", p("ticket")), ("write", p("checkpoint")), ("read", p("mode")),
              ("delete", p("checkpoint")), ("read", p("checkpoint")), ("write", p("out"))]
    worlds = [world({p("ticket"): "receipt-" + value, p("mode"): mode}, grants) for mode in ("inspect", "erase")]
    return fixture(original, worlds, [direct(p("out"), value)], {"files": {p("out"): value}})


def evolving_value_receipt(p, value, variant):
    """One static keyed writer changes its value on the second loop occurrence."""
    b = Build()
    original = prog([b.fx("read", p("seed"), out="payload"),
                     b.repeat(2, [b.fx("write", p("scratch"), value=v("payload"), key="fixed"),
                                  b.let("payload", {"concat": [v("payload"), "/next"]})]),
                     b.fx("write", p("out"), value=value),
                     b.branch(False, True, [b.fx("emit", p("cold"), value=value)])])
    grants = [("write", p("scratch")), ("write", p("out"))]
    return fixture(original, [world({p("seed"): value}, grants)], [], {"files": {p("out"): value}})


def canonical_key_alias(p, value, variant):
    """Uppercasing versus concatenation creates a world-dependent key alias."""
    b = Build()
    original = prog([b.fx("read", p("ticket"), out="ticket"),
                     b.fx("write", p("left"), value=value, key={"upper": v("ticket")}),
                     b.branch(v("ticket"), "", [b.fx("emit", p("empty"), value=value)],
                              [b.fx("write", p("right"), value=value, key={"concat": ["", v("ticket")]})]),
                     b.call("finish")], {
        "finish": [b.fx("delete", p("waste")), b.fx("write", p("out"), value=value)]})
    grants = [("read", p("ticket")), ("write", p("left")), ("write", p("right")),
              ("delete", p("waste")), ("write", p("out"))]
    worlds = [world({p("ticket"): ticket}, grants) for ticket in ("ticket", "TICKET")]
    return fixture(original, worlds, [direct(p("out"), value)], {"files": {p("out"): value}}, hidden=True)


def repeated_queue_receipt(p, value, variant):
    """Repeated identical keyed emits remain two events; a later stamp can poison."""
    b = Build()
    original = prog([b.fx("read", p("token"), out="token"), b.fx("read", p("mode"), out="mode"),
                     b.repeat(2, [b.call("send")]),
                     b.branch(v("mode"), "stamp",
                              [b.fx("write", p("stamp"), value="done", key=v("token"))],
                              [b.fx("write", p("stamp"), value="done")]),
                     b.fx("write", p("out"), value=value)], {
        "send": [b.fx("emit", p("queue"), value=value, key=v("token"))]})
    grants = [("read", p("token")), ("read", p("mode")), ("emit", p("queue")),
              ("write", p("stamp")), ("write", p("out"))]
    r = Build("r")
    route = prog([r.repeat(2, [r.fx("emit", p("queue"), value=value)]), r.fx("write", p("out"), value=value)])
    worlds = [world({p("token"): "queue-" + value, p("mode"): mode}, grants) for mode in ("plain", "stamp")]
    return fixture(original, worlds, [route], {"files": {p("out"): value},
                   "emits": [{"resource": p("queue"), "value": value, "count": 2}]})


def tradeoff_routes(p, value, cleanup=False):
    """Fewer effects with an extra emission versus more ordinary local writes."""
    fast, slow = Build("fast"), Build("slow")
    short = [fast.fx("emit", p("external"), value=value)]
    long = [slow.fx("write", p("stage-a"), value="a"),
            slow.fx("write", p("stage-b"), value="b"),
            slow.fx("write", p("stage-c"), value="c")]
    if cleanup:
        short.append(fast.fx("delete", p("temporary")))
        long.append(slow.fx("delete", p("temporary")))
    short.append(fast.fx("write", p("out"), value=value))
    long.append(slow.fx("write", p("out"), value=value))
    grants = [("emit", p("external")), ("write", p("out"))] + [("write", p(n)) for n in ("stage-a", "stage-b", "stage-c")]
    if cleanup:
        grants.append(("delete", p("temporary")))
    return [prog(short), prog(long)], grants


def lazy_manifest_materialization(p, value, variant):
    """A lazy input branch enters a repeated cache materializer before output."""
    b = Build()
    original = prog([b.fx("read", p("mode"), out="mode"),
                     b.branch(v("mode"), "load", [b.fx("read", p("source"), out="raw")], [b.let("raw", value)]),
                     b.repeat(2, [b.fx("write", p("cache"), value=v("raw")),
                                  b.fx("read", p("cache"), out="cached")]),
                     b.fx("write", p("out"), value={"upper": v("cached")}),
                     b.fx("delete", p("cache"))])
    routes, extra = tradeoff_routes(p, value.upper())
    grants = extra + [("read", p("mode")), ("read", p("source")), ("write", p("cache")),
                      ("read", p("cache")), ("delete", p("cache"))]
    worlds = [world({p("mode"): "load", p("source"): value}, grants),
              world({p("mode"): "literal", p("source"): value}, [g for g in grants if g != ("emit", p("external"))])]
    return fixture(original, worlds, routes, {"files": {p("out"): value.upper()}}, closed=variant == 0)


def alternating_fanout_join(p, value, variant):
    """A mutable cursor directs two loop iterations into different write arms."""
    b = Build()
    original = prog([b.let("cursor", "left"),
                     b.repeat(2, [b.branch(v("cursor"), "left",
                                           [b.fx("write", p("left"), value=value), b.let("cursor", "right")],
                                           [b.fx("write", p("right"), value=value)])]),
                     b.fx("read", p("left"), out="a"), b.fx("read", p("right"), out="b"),
                     b.fx("write", p("out"), value={"concat": [v("a"), v("b")]}),
                     b.repeat(0, [b.fx("read", p("cold"))])])
    routes, grants = tradeoff_routes(p, value * 2)
    grants += [(op, p(n)) for n in ("left", "right") for op in ("read", "write")]
    return fixture(original, [world({}, grants)], routes, {"files": {p("out"): value * 2}})


def cleanup_outbox_join(p, value, variant):
    """Conditional destructive cleanup joins an unconditional audit write."""
    b = Build()
    original = prog([b.fx("read", p("temporary"), out="before"),
                     b.branch(v("before"), value, [b.call("erase")],
                              [b.fx("write", p("out"), value=value)]), b.call("audit")], {
        "erase": [b.fx("delete", p("temporary")), b.fx("read", p("archive"), out="archived"),
                  b.fx("write", p("out"), value={"upper": v("archived")})],
        "audit": [b.fx("write", p("audit"), value="done")]})
    routes, grants = tradeoff_routes(p, value.upper(), cleanup=True)
    grants += [("read", p("temporary")), ("read", p("archive")), ("write", p("audit"))]
    worlds = [world({p("temporary"): before, p("archive"): value}, grants) for before in (value, "mismatch")]
    return fixture(original, worlds, routes, {"files": {p("out"): value.upper()}, "absent": [p("temporary")]})


def guarded_pair_join(p, value, variant):
    """Two preparation shapes join separately read files, with a third grant world."""
    b = Build()
    original = prog([b.fx("read", p("mode"), out="mode"), b.call("prepare"), b.call("join")], {
        "prepare": [b.branch(v("mode"), "pair",
                              [b.fx("write", p("left"), value=value), b.fx("write", p("right"), value=value.upper())],
                              [b.repeat(2, [b.fx("write", p("scratch"), value=value)])])],
        "join": [b.fx("read", p("left"), out="a"), b.fx("read", p("right"), out="b"),
                 b.fx("write", p("out"), value={"concat": [v("a"), v("b")]})],
        "unused": [b.fx("delete", p("archive"))]})
    routes, grants = tradeoff_routes(p, value + value.upper())
    grants += [("read", p("mode")), ("write", p("scratch"))] + [(op, p(n)) for n in ("left", "right") for op in ("read", "write")]
    r = Build("denied")
    routes.append(prog([r.fx("read", p("private")), r.fx("write", p("out"), value=value + value.upper())]))
    worlds = [world({p("mode"): "pair"}, grants),
              world({p("mode"): "scratch", p("left"): value, p("right"): value.upper()}, grants),
              world({p("mode"): "pair"}, [g for g in grants if g != ("write", p("out"))])]
    return fixture(original, worlds, routes, {"files": {p("out"): value + value.upper()}}, closed=variant == 0)


FAMILIES = (write_through_pointer, staged_accumulator, conditional_rotation,
            pointer_chain_fold, resource_key_poison, evolving_value_receipt,
            canonical_key_alias, repeated_queue_receipt, lazy_manifest_materialization,
            alternating_fanout_join, cleanup_outbox_join, guarded_pair_join)


def rename_symbols(program, suffix):
    renamed = deepcopy(program)
    def visit(item):
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            for field in ("id", "name", "out", "var", "fn"):
                if field in item:
                    item[field] += "_" + suffix
            for child in item.values():
                visit(child)
    visit(renamed)
    renamed["functions"] = {name + "_" + suffix: body for name, body in renamed["functions"].items()}
    return renamed


def build_cases():
    cases = []
    for family in FAMILIES:
        for variant, value in enumerate(VALUES):
            stem = sha256((family.__name__ + ":" + value).encode()).hexdigest()[:10]
            def path(name):
                return f"/synthetic/phase9/{stem}/{name}"
            case = family(path, value, variant)
            case["program"] = rename_symbols(case["program"], stem[:5])
            case["routes"] = [rename_symbols(route, stem[5:] + str(i)) for i, route in enumerate(case["routes"])]
            for program in [case["program"], *case["routes"]]:
                static_sites(program)
            case.update(case_id=f"p9-{family.__name__}-{variant}", family="p9_" + family.__name__,
                        split="heldout", generation={"version": 1, "seed": variant},
                        source="# Synthetic bounded workflow\n\nUse only the supplied in-memory world.\n\n```tsg-workflow\n"
                               + json.dumps(case["program"], ensure_ascii=False, indent=2) + "\n```\n")
            cases.append(case)
    return cases


def observation_signature(case, supplied):
    """Reference-only projection of permitted pre-execution observations.

    Missing allowlists mean all supplied file names / grant identities are
    observable. Empty allowlists permit none. Absence differs from empty text;
    grant membership answers are Boolean. This function executes no program.
    """
    files = case.get("observable_files", sorted({p for w in case["worlds"] for p in w.get("files", {})}))
    grants = case.get("observable_grants", sorted({tuple(g) for w in case["worlds"] for g in w.get("grants", [])}))
    present = {tuple(g) for g in supplied.get("grants", [])}
    return (tuple((p, p in supplied.get("files", {}), supplied.get("files", {}).get(p)) for p in files),
            tuple((op, path, (op, path) in present) for op, path in grants))


def reference_record(case):
    record = evaluate_case(case)
    for result, supplied in zip(record["worlds"], case["worlds"], strict=True):
        result["interventions"] = {site["id"]: run(case["program"], supplied, case["goal"], suppress=site["id"])
                                   for site in static_sites(case["program"])}
    return record


def coverage_audit(cases, records):
    labels = {axis: Counter({value: 0 for value in TYPES}) for axis in AXES}
    reasons = {axis: Counter() for axis in AXES}
    family_labels, observable, hidden = {}, [], []
    conflicts, errors, tradeoffs, no_alternative_worlds = [], [], [], []
    activity = Counter()
    for case, record in zip(cases, records, strict=True):
        family = family_labels.setdefault(case["family"], {axis: Counter() for axis in AXES})
        for row in record["labels"]:
            for axis in AXES:
                labels[axis][row[axis]] += 1
                family[axis][row[axis]] += 1
                reasons[axis].update(row["reasons"][axis])
        signatures = [observation_signature(case, w) for w in case["worlds"]]
        if len(signatures) > 1 and len(set(signatures)) == len(signatures):
            observable.append(case["case_id"])
        indistinguishable = []
        for left in range(len(signatures)):
            for right in range(left + 1, len(signatures)):
                if signatures[left] != signatures[right]:
                    continue
                differences = [{"site_id": a["id"], "axis": axis, "left": a[axis], "right": b[axis]}
                               for a, b in zip(record["worlds"][left]["labels"], record["worlds"][right]["labels"], strict=True)
                               for axis in AXES if a[axis] != b[axis]]
                if differences:
                    indistinguishable.append({"world_indices": [left, right], "label_differences": differences})
        if indistinguishable:
            hidden.append({"case_id": case["case_id"], "indistinguishable_world_pairs": indistinguishable})
        for result in record["worlds"]:
            legal = result["legal_route_indices"]
            activity.update("active" if row["occurred"] else "inactive" for row in result["labels"])
            if not any(i > 0 for i in legal):
                no_alternative_worlds.append({"case_id": case["case_id"], "world_index": result["index"], "original_legal": 0 in legal})
            for index, execution in enumerate(result["routes"]):
                if execution["error"]:
                    row = {"case_id": case["case_id"], "world_index": result["index"], "route_index": index, "error": execution["error"]}
                    errors.append(row)
                    if execution["error"] == "key_signature_conflict":
                        conflicts.append(row)
            for fast in legal:
                for slow in legal:
                    if fast == slow:
                        continue
                    a, b = (result["routes"][i]["trace"] for i in (fast, slow))
                    if len(a) < len(b) and sum(e["op"] == "emit" for e in a) > sum(e["op"] == "emit" for e in b) and sum(e["op"] == "write" for e in b) > sum(e["op"] == "write" for e in a):
                        tradeoffs.append({"case_id": case["case_id"], "world_index": result["index"],
                                          "fewer_call_route": fast, "more_write_route": slow,
                                          "fewer_calls": len(a), "more_calls": len(b),
                                          "fewer_call_emits": sum(e["op"] == "emit" for e in a),
                                          "more_write_emits": sum(e["op"] == "emit" for e in b)})
    sizes = [len(static_sites(c["program"])) for c in cases]
    counts = {"cases": len(cases), "families": len(family_labels), "worlds": sum(len(c["worlds"]) for c in cases),
              "aggregate_candidates": sum(len(r["labels"]) for r in records),
              "no_alternative_cases": sum(not c["routes"] for c in cases),
              "multiworld_cases": sum(len(c["worlds"]) > 1 for c in cases),
              "static_effect_sites": {"min": min(sizes), "max": max(sizes), "median": statistics.median(sizes), "histogram": dict(sorted(Counter(sizes).items()))}}
    checks = {"24_cases": len(cases) == 24,
              "12_families_two_each": sorted(Counter(c["family"] for c in cases).values()) == [2] * 12,
              "at_least_6_no_alternative": counts["no_alternative_cases"] >= 6,
              "at_least_8_observable_multiworld": len(observable) >= 8,
              "at_least_4_irreducible_hidden": len(hidden) >= 4,
              "at_least_4_key_poison_cases": len({r["case_id"] for r in conflicts}) >= 4,
              "at_least_4_tradeoff_cases": len({r["case_id"] for r in tradeoffs}) >= 4,
              "all_axis_type_cells_nonempty": all(count > 0 for values in labels.values() for count in values.values()),
              "active_and_inactive": all(activity[name] > 0 for name in ("active", "inactive")),
              "bounded_worlds_alternatives": all(1 <= len(c["worlds"]) <= 3 and len(c["routes"]) <= 3 for c in cases),
              "site_bounds": min(sizes) >= 4 and max(sizes) <= 12,
              "typical_4_to_8_sites": sum(4 <= size <= 8 for size in sizes) >= 20}
    return {**counts, "aggregate_labels": labels, "aggregate_reasons": reasons, "family_labels": family_labels,
            "world_site_activity": activity, "observable_multiworld_cases": observable,
            "irreducible_hidden_cases": hidden, "key_conflict_worlds": conflicts,
            "call_emission_tradeoffs": tradeoffs, "no_feasible_alternative_worlds": no_alternative_worlds,
            "intentional_route_errors": errors, "acceptance": checks, "passed": all(checks.values()),
            "tradeoff_limit": "Fresh-start legal reference routes only. Extra emission is an explicit operation contrast, not a measured recovery outcome or assumed risk-weight result.",
            "hidden_limit": "Irreducibility concerns the allowed pre-execution file/grant observations. A diagnostic operation capable of inspecting hidden state would change this information model."}


def skeleton_tokens(program):
    """Phase 8 normalization retained for a comparable, deliberately coarse audit."""
    static_sites(program)
    functions = program.get("functions", {})
    def expr(item):
        if isinstance(item, dict):
            if "var" in item:
                return ("VAR",)
            if "upper" in item:
                return ("UPPER", "(", *expr(item["upper"]), ")")
            return ("CONCAT", "(", *(t for part in item["concat"] for t in expr(part)), ")")
        return ("LIT:" + ("null" if item is None else type(item).__name__),)
    def body(steps):
        result = ["SEQ", "("]
        for step in steps:
            kind = step["kind"]
            result.extend((kind.upper(), "("))
            if kind == "effect":
                result.extend((step["op"], *expr(step["resource"])))
                for field in ("value", "key"):
                    if field in step:
                        result.extend((field.upper(), *expr(step[field])))
                if "out" in step:
                    result.append("OUT")
            elif kind == "let":
                result.extend(expr(step["value"]))
            elif kind == "if":
                result.extend(("EQ", *expr(step["eq"][0]), *expr(step["eq"][1]),
                               "THEN", *body(step["then"]), "ELSE", *body(step["else"])))
            elif kind == "repeat":
                result.extend(("COUNT:LIT:int", *body(step["body"])))
            elif kind == "call":
                result.extend(body(functions[step["fn"]]))
            result.append(")")
        return (*result, ")")
    definitions = sorted(body(steps) for steps in functions.values())
    return ("PROGRAM", "(", *body(program["steps"]), "FUNCTIONS", "(",
            *(token for definition in definitions for token in ("FUNCTION", *definition)), ")", ")")


@lru_cache(maxsize=None)
def token_distance(left, right):
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def novelty_audit(cases):
    old, provenance = [], []
    for relative in OLD_PATHS:
        raw = (ROOT / relative).read_bytes()
        rows = [json.loads(line) for line in raw.splitlines()]
        provenance.append({"path": relative, "sha256": sha256(raw).hexdigest(), "cases": len(rows)})
        for case in rows:
            for index, program in enumerate([case["program"], *case.get("routes", [])]):
                old.append({"path": relative, "case_id": case["case_id"], "route_index": index, "tokens": skeleton_tokens(program)})
    rows, groups = [], defaultdict(list)
    for case in cases:
        tokens = skeleton_tokens(case["program"])
        digest = sha256("\n".join(tokens).encode()).hexdigest()
        groups[digest].append(case["case_id"])
        row = {"case_id": case["case_id"], "family": case["family"], "skeleton_sha256": digest, "tokens": len(tokens)}
        for name, pool in (("prior_originals", [x for x in old if x["route_index"] == 0]), ("all_prior_reference_programs", old)):
            distances = [token_distance(tokens, item["tokens"]) for item in pool]
            minimum = min(distances)
            nearest = [{key: item[key] for key in ("path", "case_id", "route_index")}
                       for item, distance in zip(pool, distances, strict=True) if distance == minimum]
            row[name] = {"minimum_token_edit_distance": minimum, "nearest": nearest,
                         "exact_duplicates": nearest if minimum == 0 else []}
        rows.append(row)
    distributions = {}
    for name in ("prior_originals", "all_prior_reference_programs"):
        values = [row[name]["minimum_token_edit_distance"] for row in rows]
        distributions[name] = {"min": min(values), "max": max(values), "median": statistics.median(values),
                               "mean": statistics.mean(values), "histogram": dict(sorted(Counter(values).items())),
                               "exact_duplicate_new_cases": sum(value == 0 for value in values)}
    return {"method": "AST-token-Levenshtein-v1", "prior_files": provenance,
            "prior_original_count": sum(row["route_index"] == 0 for row in old), "prior_reference_program_count": len(old),
            "new_original_count": len(cases), "unique_new_original_skeletons": len(groups),
            "within_new_exact_groups": [ids for ids in groups.values() if len(ids) > 1],
            "distributions": distributions, "cases": rows,
            "normalization": "Erase site, variable and function names, resources/paths and literal values. Preserve scalar types, operation names, expression operators, ordered sequences, branch arms, nesting, key/output presence, recursively expanded call boundaries and all function definitions sorted by normalized body.",
            "limitations": ["Two lexical variants in each family share a skeleton: 24 cases are only 12 authored structural families, not 24 independent mechanisms.",
                            "All families share the finite DSL and common mechanisms; family-clustered analysis does not make families semantically independent.",
                            "Literal erasure collapses loop counts, zero-trip/live loops, equality outcomes and receipt identities.",
                            "Variable names and alias/dataflow identities are erased; structurally distinct programs can remain semantically related.",
                            "Worlds, grants, goals, closure and observability restrictions are outside these skeletons.",
                            "Call expansion counts boundaries and definitions, weighting reused function bodies more than flat steps.",
                            "Distances compare new originals with old originals and all old alternatives; new alternative routes are not claimed novel.",
                            "Token distance is not semantic distance, independent difficulty, or proof of out-of-distribution generalization."]}


def jsonl_bytes(rows):
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")


def write_once(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()
    targets = [args.output, *(args.audit_dir / name for name in ("truth.jsonl", "coverage.json", "novelty.json", "provenance.json"))]
    for target in targets:
        if target.exists():
            raise FileExistsError(f"Refusing to replace frozen or preliminary output: {target}")
    cases = build_cases()
    records = [reference_record(case) for case in cases]
    coverage, novelty = coverage_audit(cases, records), novelty_audit(cases)
    json_bytes = lambda obj: (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    contents = [jsonl_bytes(cases), jsonl_bytes(records), json_bytes(coverage), json_bytes(novelty)]
    sources = ["scripts/build_phase9_heldout.py", "src/tsg/truth_v6.py", "src/tsg/truth_v7.py", *OLD_PATHS]
    provenance = {"schema_version": 1, "generator": "independent-reference-only", "case_count": len(cases),
                  "source_sha256": {relative: sha256((ROOT / relative).read_bytes()).hexdigest() for relative in sources},
                  "artifact_sha256": {target.name: sha256(raw).hexdigest() for target, raw in zip(targets, contents)},
                  "model_outcomes_consulted": False, "production_modules_consulted": False,
                  "reference_modules": ["tsg.truth_v6", "tsg.truth_v7"], "coverage_passed": coverage["passed"]}
    contents.append(json_bytes(provenance))
    for target, raw in zip(targets, contents, strict=True):
        write_once(target, raw)
    print(json.dumps({"cases": len(cases), "coverage": coverage["aggregate_labels"], "accepted": coverage["passed"],
                      "unique_skeletons": novelty["unique_new_original_skeletons"], "sha256": sha256(contents[0]).hexdigest()}, sort_keys=True))
    if not coverage["passed"]:
        raise SystemExit("Prospective reference coverage failed; retain initial evidence and disclose any amendment.")


if __name__ == "__main__":
    main()

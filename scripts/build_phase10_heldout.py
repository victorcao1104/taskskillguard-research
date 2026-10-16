"""Independently authored Phase 10 finite fixtures and executable reference truth.

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
from itertools import combinations
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.truth_v6 import run, static_sites  # noqa: E402
from tsg.truth_v7 import AXES, evaluate_case  # noqa: E402

OLD_PATHS = ("data/phase6/dev.jsonl", "data/phase6/heldout.jsonl",
             "data/phase6/challenge.jsonl", "data/phase7/heldout.jsonl",
             "data/phase8/heldout.jsonl", "data/phase9/heldout.jsonl")
VALUES = ("kahikatea_101", "copper:307")
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


def _prior_style_coverage(cases, records):
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


def supplied(program, worlds, routes, goal, paths=(), pairs=(), closed=True):
    return {"program": program, "worlds": worlds, "routes": routes, "goal": goal,
            "catalog_closed": closed, "observable_files": list(paths),
            "observable_grants": [list(pair) for pair in pairs]}


def grants(p, **operations):
    return [(op, p(name)) for op, names in operations.items() for name in names.split()]


def transform_pipeline(p, value, variant):
    """Fixed authorization trace; only the goal depends on an immutable input."""
    b = Build()
    original = prog([b.fx("read", p("source"), out="raw"), b.fx("read", p("suffix"), out="suffix"),
                     b.fx("write", p("stage"), value={"concat": [v("raw"), v("suffix")]}),
                     b.fx("read", p("stage"), out="saved"), b.fx("write", p("out"), value={"upper": v("saved")}),
                     b.fx("delete", p("stage")), b.fx("read", p("audit"))])
    gs = grants(p, read="source suffix stage audit", write="stage out", delete="stage")
    return supplied(original, [world({p("source"): raw, p("suffix"): "/end"}, gs) for raw in (value, "wrong")], [],
                    {"files": {p("out"): (value + "/end").upper()}}, [p("source"), p("suffix")])


def two_gate_relay(p, value, variant):
    """Two safe reads jointly establish success; neither alone suffices."""
    b = Build()
    original = prog([b.fx("read", p("left-flag"), out="left"), b.fx("read", p("right-flag"), out="right"),
                     b.let("payload", "wrong"),
                     b.branch(v("left"), "ready", [b.branch(v("right"), "ready", [b.let("payload", value)])]),
                     b.fx("write", p("stage"), value=v("payload")), b.fx("read", p("stage"), out="saved"),
                     b.fx("write", p("out"), value=v("saved"))])
    gs = grants(p, read="left-flag right-flag stage", write="stage out")
    worlds = [world({p("left-flag"): left, p("right-flag"): right}, gs)
              for left, right in (("ready", "ready"), ("ready", "wait"), ("wait", "ready"))]
    return supplied(original, worlds, [], {"files": {p("out"): value}}, [p("left-flag"), p("right-flag")])


def concealed_branch_ledger(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("hidden"), out="mode"),
                     b.branch(v("mode"), "valid", [b.let("payload", value)], [b.let("payload", "wrong")]),
                     b.fx("write", p("out"), value=v("payload")), b.call("record"),
                     b.repeat(0, [b.fx("emit", p("cold"), value=value)])], {
                         "record": [b.fx("read", p("checkpoint")), b.fx("write", p("ledger"), value="seen")]})
    gs = grants(p, read="hidden checkpoint", write="out ledger")
    return supplied(original, [world({p("hidden"): x}, gs) for x in ("valid", "invalid")], [], {"files": {p("out"): value}})


def concealed_loop_cofactor(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("source"), out="raw"), b.let("acc", ""),
                     b.repeat(2, [b.fx("read", p("hidden"), out="factor"),
                                  b.let("acc", {"concat": [v("acc"), v("raw"), v("factor")]}),
                                  b.fx("write", p("stage"), value=v("acc"))]),
                     b.fx("write", p("out"), value=v("acc")), b.fx("emit", p("summary"), value="finished"),
                     b.branch(True, False, [b.fx("delete", p("cold"))])])
    gs = grants(p, read="source hidden", write="stage out", emit="summary")
    return supplied(original, [world({p("source"): value, p("hidden"): factor}, gs) for factor in ("", "x")], [],
                    {"files": {p("out"): value * 2}})


def denied_accumulator_cleanup(p, value, variant):
    b = Build()
    original = prog([b.let("acc", ""), b.repeat(2, [b.fx("read", p("source"), out="part"),
                       b.let("acc", {"concat": [v("acc"), v("part")]}), b.fx("write", p("checkpoint"), value=v("acc"))]),
                     b.fx("delete", p("locked")), b.fx("emit", p("queue"), value=value),
                     b.fx("write", p("out"), value=v("acc")), b.fx("read", p("out"))])
    gs = grants(p, read="source out", write="out")
    return supplied(original, [world({p("source"): value, p("locked"): "keep"}, gs)], [direct(p("out"), value * 2)],
                    {"files": {p("out"): value * 2}}, [p("source")])


def denied_subroutine_join(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("mode"), out="mode"), b.call("side-effects"),
                     b.branch(v("mode"), "fetch", [b.fx("read", p("source"), out="payload")], [b.let("payload", value)]),
                     b.fx("write", p("out"), value=v("payload"))], {
                         "side-effects": [b.fx("delete", p("locked")), b.fx("emit", p("audit"), value=value),
                                          b.fx("write", p("private"), value="touched")]})
    gs = grants(p, read="mode source", write="out")
    return supplied(original, [world({p("mode"): mode, p("source"): value}, gs) for mode in ("fetch", "literal")],
                    [direct(p("out"), value)], {"files": {p("out"): value}}, [p("mode"), p("source")])


def alternatives(p, value, erase=False, shared_key=None):
    fast, slow = Build("fast"), Build("slow")
    optional_key = {} if shared_key is None else {"key": shared_key}
    short = [fast.fx("emit", p("external"), value=value, **optional_key)]
    long = [slow.fx("write", p(name), value=value) for name in ("stage-a", "stage-b", "stage-c")]
    if erase:
        short.append(fast.fx("delete", p("temporary")))
        long.append(slow.fx("delete", p("temporary")))
    short.append(fast.fx("write", p("out"), value=value))
    long.append(slow.fx("write", p("out"), value=value))
    gs = grants(p, emit="external", write="stage-a stage-b stage-c out")
    if erase:
        gs += grants(p, delete="temporary")
    return [prog(short), prog(long)], gs


def receipt_token_splice(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("token"), out="token"),
                     b.fx("write", p("marker"), value=value, key=v("token")),
                     b.fx("emit", p("external"), value=value, key="external-ticket"),
                     b.fx("read", p("marker"), out="saved"), b.fx("write", p("out"), value=v("saved")),
                     b.repeat(0, [b.fx("delete", p("cold"))])])
    routes, gs = alternatives(p, value, shared_key="external-ticket")
    gs += grants(p, read="token marker", write="marker")
    return supplied(original, [world({p("token"): token}, gs) for token in ("marker-ticket", "external-ticket")],
                    routes, {"files": {p("out"): value}}, [p("token")])


def postgoal_changing_receipt(p, value, variant):
    b = Build()
    original = prog([b.fx("write", p("out"), value=value), b.let("payload", value),
                     b.repeat(2, [b.call("publish"), b.let("payload", {"upper": v("payload")})]),
                     b.fx("read", p("out")), b.fx("delete", p("temporary"))], {
                         "publish": [b.fx("emit", p("external"), value=v("payload"), key="external-ticket"),
                                     b.fx("write", p("journal"), value="sent")]})
    routes, gs = alternatives(p, value, shared_key="external-ticket")
    gs += grants(p, read="out", write="journal", delete="temporary")
    return supplied(original, [world({p("temporary"): "old"}, gs)], routes, {"files": {p("out"): value}})


def conditional_missing_binding(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("source"), out="chunk"),
                     b.branch(v("chunk"), "broken", [b.let("payload", v("never-bound"))],
                              [b.let("payload", {"concat": ["", v("chunk")]})]),
                     b.fx("write", p("out"), value=v("payload")), b.fx("read", p("out")),
                     b.fx("emit", p("audit"), value="done"), b.fx("delete", p("temporary"))])
    routes, gs = alternatives(p, value)
    gs += grants(p, read="source out", emit="audit", delete="temporary")
    return supplied(original, [world({p("source"): raw}, gs) for raw in (value, "broken")], routes,
                    {"files": {p("out"): value}}, [p("source")])


def repeated_selected_cleanup(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("kind"), out="kind"),
                     b.branch(v("kind"), "temporary", [b.let("target", p("temporary"))], [b.let("target", p("retained"))]),
                     b.repeat(2, [b.fx("delete", v("target"))]), b.fx("emit", p("external"), value=value),
                     b.fx("write", p("out"), value=value), b.fx("read", p("out"))], {
                         "unused": [b.fx("write", p("private"), value="cold")]})
    routes, gs = alternatives(p, value, erase=True)
    gs += grants(p, read="kind out", delete="retained")
    return supplied(original, [world({p("kind"): kind, p("temporary"): "old", p("retained"): "keep"}, gs)
                               for kind in ("temporary", "retained")], routes,
                    {"files": {p("out"): value}, "absent": [p("temporary")]}, [p("kind")])


def optional_overwrite_fork(p, value, variant):
    b = Build()
    original = prog([b.fx("write", p("out"), value=value), b.fx("read", p("switch"), out="mode"),
                     b.branch(v("mode"), "keep", [b.fx("read", p("out"), out="check")],
                              [b.fx("read", p("source"), out="check")]),
                     b.fx("write", p("out"), value=v("check")), b.fx("emit", p("audit"), value="seen"),
                     b.let("unused", {"concat": [v("check"), "/ignored"]}),
                     b.repeat(0, [b.fx("delete", p("cold"))])])
    gs = grants(p, read="switch source out", write="out", emit="audit")
    return supplied(original, [world({p("switch"): mode, p("source"): "wrong"}, gs) for mode in ("keep", "replace")], [],
                    {"files": {p("out"): value}}, [p("switch"), p("source")], closed=variant == 0)


def nested_grant_relay(p, value, variant):
    b = Build()
    original = prog([b.fx("read", p("selector"), out="selector"),
                     b.branch(v("selector"), "locked", [b.branch(True, True, [b.fx("read", p("secret"), out="payload")])],
                              [b.repeat(2, [b.call("local")]), b.fx("read", p("stage"), out="payload")]),
                     b.fx("write", p("out"), value=v("payload")), b.repeat(0, [b.fx("emit", p("cold"), value=value)])], {
                         "local": [b.fx("write", p("stage"), value=value)]})
    gs = grants(p, read="selector secret stage", write="stage out")
    worlds = [world({p("selector"): "locked", p("secret"): value}, gs),
              world({p("selector"): "locked", p("secret"): value}, [g for g in gs if g != ("read", p("secret"))]),
              world({p("selector"): "local", p("secret"): value}, gs)]
    return supplied(original, worlds, [], {"files": {p("out"): value}}, [p("selector")],
                    [("read", p("secret"))], closed=variant == 0)


FAMILIES = (transform_pipeline, two_gate_relay, concealed_branch_ledger, concealed_loop_cofactor,
            denied_accumulator_cleanup, denied_subroutine_join, receipt_token_splice,
            postgoal_changing_receipt, conditional_missing_binding, repeated_selected_cleanup,
            optional_overwrite_fork, nested_grant_relay)


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
            path = lambda name: f"/synthetic/phase10/{stem}/{name}"
            case = family(path, value, variant)
            case["program"] = rename_symbols(case["program"], stem[:5])
            case["routes"] = [rename_symbols(route, stem[5:] + str(i)) for i, route in enumerate(case["routes"])]
            for program in [case["program"], *case["routes"]]:
                static_sites(program)
            case.update(case_id=f"p10-{family.__name__}-{variant}", family="p10_" + family.__name__, split="heldout",
                        generation={"version": 1, "seed": variant},
                        source="# Synthetic bounded workflow\n\nUse only the supplied in-memory world.\n\n```tsg-workflow\n"
                               + json.dumps(case["program"], ensure_ascii=False, indent=2) + "\n```\n")
            cases.append(case)
    return cases


def coverage_audit(cases, records):
    audit = _prior_style_coverage(cases, records)
    goal_only, two_reads, incomplete = [], [], []
    for case, record in zip(cases, records, strict=True):
        states = record["worlds"]
        auth = [tuple(row["authorization"] for row in state["labels"]) for state in states]
        goals = [state["baseline"]["goal"] for state in states]
        observable = case["observable_files"]
        legal_reads = all(["read", path] in world["grants"] for path in observable for world in case["worlds"])
        def separates(paths):
            signatures = [tuple((path in w["files"], w["files"].get(path)) for path in paths) for w in case["worlds"]]
            return all(signatures[i] != signatures[j] for i in range(len(states)) for j in range(i + 1, len(states)) if goals[i] != goals[j])
        if len(set(goals)) > 1 and len(set(auth)) == 1 and legal_reads and separates(observable):
            goal_only.append(case["case_id"])
            minimum = next(n for n in range(len(observable) + 1) if any(separates(paths) for paths in combinations(observable, n)))
            if minimum >= 2:
                two_reads.append({"case_id": case["case_id"], "minimum_file_reads_for_goal_partition": minimum,
                                  "observable_files": observable})
        for state in states:
            if state["baseline"]["error"]:
                incomplete.append({"case_id": case["case_id"], "world_index": state["index"],
                                   "error": state["baseline"]["error"], "goal": state["baseline"]["goal"],
                                   "partial_files_match_goal": all(state["baseline"]["files"].get(p) == value for p, value in case["goal"].get("files", {}).items())})
    audit.update(goal_only_observable_cases=goal_only, two_read_goal_observation_cases=two_reads,
                 incomplete_original_worlds=incomplete)
    audit["acceptance"].update(at_least_4_goal_only_cases=len(goal_only) >= 4,
                               at_least_2_two_read_goal_cases=len(two_reads) >= 2,
                               incomplete_original_runs=bool(incomplete),
                               at_least_8_authorization_no=audit["aggregate_labels"]["authorization"]["no"] >= 8,
                               at_least_8_current_route_no=audit["aggregate_labels"]["current_route_required"]["no"] >= 8)
    audit["passed"] = all(audit["acceptance"].values())
    audit["goal_observation_limit"] = "Goal partition is the original fresh-start success predicate, not a prediction of controller recovery. Minimum reads is information-theoretic over the declared finite worlds and allowed safe initial file reads."
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", "--output", dest="output", type=Path,
                        default=ROOT / "results/phase10/reference/first-pass/heldout.jsonl")
    parser.add_argument("--audit-dir", type=Path, default=ROOT / "results/phase10/reference/first-pass")
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
    sources = ["scripts/build_phase10_heldout.py", "src/tsg/truth_v6.py", "src/tsg/truth_v7.py", *OLD_PATHS]
    provenance = {"schema_version": 1, "generator": "independent-reference-only", "case_count": len(cases),
                  "source_sha256": {relative: sha256((ROOT / relative).read_bytes()).hexdigest() for relative in sources},
                  "artifact_sha256": {target.name: sha256(raw).hexdigest() for target, raw in zip(targets, contents)},
                  "model_outcomes_consulted": False, "production_modules_consulted": False,
                  "reference_modules": ["tsg.truth_v6", "tsg.truth_v7"], "coverage_passed": coverage["passed"],
                  "first_pass_policy": "Retain every initial case and all shortcomings; no outcome-based revision."}
    contents.append(json_bytes(provenance))
    for target, raw in zip(targets, contents, strict=True):
        write_once(target, raw)
    print(json.dumps({"cases": len(cases), "accepted": coverage["passed"], "unique_skeletons": novelty["unique_new_original_skeletons"]}))
    if not coverage["passed"]:
        raise SystemExit("Prospective coverage shortfall retained in first-pass evidence. Do not tune the cases.")


if __name__ == "__main__":
    main()




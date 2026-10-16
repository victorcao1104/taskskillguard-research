"""Independent Phase 8 synthetic fixtures and reference-only provenance.

Only frozen truth_v6/truth_v7 are imported. No production source, executable,
recovery implementation, model response, or human answer labels are inputs.
Every output uses exclusive creation; choose a new directory for a new audit.
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
             "data/phase6/challenge.jsonl", "data/phase7/heldout.jsonl")
VALUES = ("Juniper-17", "cobalt_29", "Kauri.43", "tamarind:61")


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


def one_write(path, value, prefix="z"):
    b = Build(prefix)
    return prog([b.fx("write", path, value=value)])


def escrow_mirror(p, value, variant):
    """A copied checkpoint is consumed before removal; no alternative exists."""
    b = Build()
    original = prog([b.fx("read", p("origin"), out="raw"), b.call("stage"),
                     b.fx("read", p("escrow"), out="saved"), b.call("finish")], {
        "stage": [b.branch({"upper": v("raw")}, value.upper(),
                           [b.fx("write", p("escrow"), value={"concat": ["sealed/", v("raw")]})])],
        "finish": [b.fx("delete", p("escrow")), b.fx("write", p("out"), value=v("saved"))],
        "unused": [b.repeat(2, [b.fx("emit", p("unreached"), value=value)])],
    })
    grants = [("read", p("origin")), ("write", p("escrow")), ("read", p("escrow")),
              ("delete", p("escrow")), ("write", p("out"))]
    files = {p("origin"): value}
    goal = {"files": {p("out"): "sealed/" + value}, "absent": [p("escrow")]}
    return original, [world(files, grants), world({**files, p("out"): "sealed/" + value}, grants)], [], goal, True


def nested_seal(p, value, variant):
    """Repeated nested call produces exact emissions; a side read lacks a grant."""
    b = Build()
    original = prog([b.let("flag", "go"), b.repeat(2, [b.call("outer")]),
                     b.fx("read", p("private"), out="ignored"),
                     b.fx("write", p("out"), value=value)], {
        "outer": [b.branch(v("flag"), "go", [b.call("inner")])],
        "inner": [b.repeat(1, [b.fx("emit", p("stream"), value={"upper": value})])],
        "dead": [b.fx("delete", p("tomb"))],
    })
    grants = [("emit", p("stream")), ("write", p("out"))]
    goal = {"files": {p("out"): value}, "emits": [{"resource": p("stream"), "value": value.upper(), "count": 2}]}
    return original, [world({}, grants)], [], goal, True


def conditional_permit(p, value, variant):
    """World-dependent nested branch applicability without fallback routes."""
    b = Build()
    original = prog([b.fx("read", p("flag"), out="flag"),
                     b.branch(v("flag"), "publish", [b.repeat(1, [b.call("save")])],
                              [b.fx("read", p("reserve"))]),
                     b.repeat(0, [b.fx("delete", p("out"))])], {
        "save": [b.fx("write", p("out"), value=value),
                 b.branch(value, value, [b.fx("emit", p("note"), value="complete")])],
    })
    grants = [("read", p("flag")), ("write", p("out")), ("emit", p("note"))]
    worlds = [world({p("flag"): "publish"}, grants),
              world({p("flag"): "wait", p("out"): value}, grants)]
    return original, worlds, [], {"files": {p("out"): value}}, True


def deadletter_cycle(p, value, variant):
    """A no-grant deletion precedes a repeated scratch read and guarded write."""
    b = Build()
    original = prog([b.fx("delete", p("restricted")), b.let("mode", "first"),
                     b.repeat(2, [b.fx("read", p("scratch"), out="scratch"),
                                  b.branch(v("mode"), "first", [b.call("commit")]),
                                  b.let("mode", "next")])], {
        "commit": [b.fx("write", p("out"), value=value)],
        "never": [b.branch(False, True, [b.fx("emit", p("alarm"), value=value)])],
    })
    grants = [("read", p("scratch")), ("write", p("out"))]
    return original, [world({}, grants), world({p("out"): value}, grants)], [], {"files": {p("out"): value}}, True


def costly_retry_fanout(p, value, variant):
    """Safe first read, long repeated checkpoints, and one-call legal completion."""
    b = Build()
    original = prog([b.fx("read", p("source"), out="source"),
                     b.repeat(2, [b.call("left"), b.call("right")]),
                     b.fx("write", p("out"), value={"upper": v("source")})], {
        "left": [b.fx("write", p("left"), value=value), b.fx("read", p("left"), out="last")],
        "right": [b.branch(v("last"), value, [b.fx("write", p("right"), value=v("last")),
                                                b.fx("read", p("right"))])],
    })
    grants = [("read", p("source")), ("write", p("left")), ("read", p("left")),
              ("write", p("right")), ("read", p("right")), ("write", p("out"))]
    r = Build("r")
    invalid = prog([r.fx("read", p("denied")), r.fx("write", p("out"), value=value.upper())])
    return original, [world({p("source"): value}, grants)], [invalid, one_write(p("out"), value.upper())], {"files": {p("out"): value.upper()}}, variant % 2 == 0


def checkpoint_receipt(p, value, variant):
    """Keyed harmless first write, nested staging, cheap output-only alternative."""
    b = Build()
    original = prog([b.fx("write", p("receipt"), value="ready", key="checkpoint"),
                     b.call("rebuild"), b.fx("write", p("out"), value=v("saved"))], {
        "rebuild": [b.repeat(2, [b.call("copy")]), b.fx("read", p("scratch"), out="saved")],
        "copy": [b.fx("read", p("input"), out="raw"),
                 b.fx("write", p("scratch"), value={"concat": ["v/", {"upper": v("raw")}]})],
    })
    grants = [("write", p("receipt")), ("read", p("input")), ("write", p("scratch")),
              ("read", p("scratch")), ("write", p("out"))]
    return original, [world({p("input"): value}, grants)], [one_write(p("out"), "v/" + value.upper())], {"files": {p("out"): "v/" + value.upper()}}, False


def fork_join_diff(p, value, variant):
    """Two branch-local loads join a common writer; grants vary independently."""
    b = Build()
    original = prog([b.fx("read", p("selector"), out="selector"),
                     b.branch(v("selector"), "west", [b.call("west")], [b.call("east")]),
                     b.call("join")], {
        "west": [b.fx("read", p("west"), out="payload")],
        "east": [b.repeat(1, [b.fx("read", p("east"), out="payload")])],
        "join": [b.fx("write", p("out"), value={"upper": v("payload")}),
                 b.fx("emit", p("stream"), value="joined")],
    })
    grants = [("read", p("selector")), ("read", p("west")), ("read", p("east")),
              ("write", p("out")), ("emit", p("stream"))]
    files = {p("west"): value, p("east"): value}
    worlds = [world({**files, p("selector"): "west"}, grants),
              world({**files, p("selector"): "east"}, grants[:-1])]
    r = Build("r")
    route = prog([r.fx("write", p("out"), value=value.upper()), r.fx("emit", p("stream"), value="joined")])
    goal = {"files": {p("out"): value.upper()}, "emits": [{"resource": p("stream"), "value": "joined", "count": 1}]}
    return original, worlds, [route], goal, True


def preexisting_abort(p, value, variant):
    """Read-dependent intentional key conflict changes baseline applicability."""
    b = Build()
    original = prog([b.fx("read", p("mode"), out="mode"), b.call("stage"),
                     b.fx("write", p("out"), value=value),
                     b.repeat(0, [b.fx("read", p("unreached"))])], {
        "stage": [b.fx("write", p("checkpoint"), value="first", key="one"),
                  b.branch(v("mode"), "conflict", [b.fx("write", p("checkpoint"), value="second", key="one")])],
    })
    grants = [("read", p("mode")), ("write", p("checkpoint")), ("write", p("out"))]
    worlds = [world({p("mode"): "ok"}, grants), world({p("mode"): "conflict", p("out"): value}, grants)]
    return original, worlds, [one_write(p("out"), value)], {"files": {p("out"): value}}, True


def dynamic_object_matrix(p, value, variant):
    """The same read site spans two resources inside a repeated call and branch."""
    b = Build()
    original = prog([b.let("handle", p("first")), b.let("combined", ""),
                     b.repeat(2, [b.call("consume"), b.let("handle", p("second"))]),
                     b.fx("write", p("out"), value={"upper": v("combined")})], {
        "consume": [b.fx("read", v("handle"), out="chunk"),
                    b.branch(v("chunk"), value, [b.let("combined", {"concat": [v("combined"), v("chunk")]})],
                             [b.fx("emit", p("anomaly"), value=v("chunk"))])],
    })
    grants = [("read", p("first")), ("write", p("out"))]
    files = {p("first"): value, p("second"): value}
    return original, [world(files, grants), world({**files, p("out"): value.upper() * 2}, grants)], [one_write(p("out"), value.upper() * 2)], {"files": {p("out"): value.upper() * 2}}, False


def shared_emit_key(p, value, variant):
    """Two functions share a receipt key; conflicting values fail before a tail."""
    b = Build()
    original = prog([b.fx("read", p("mode"), out="mode"), b.call("announce"),
                     b.branch(v("mode"), "repeat", [b.call("announce")], [b.call("conflict")]),
                     b.fx("write", p("out"), value=value)], {
        "announce": [b.fx("emit", p("stream"), value=value, key="shared")],
        "conflict": [b.fx("emit", p("stream"), value="different", key="shared")],
    })
    grants = [("read", p("mode")), ("emit", p("stream")), ("write", p("out"))]
    r = Build("r")
    route = prog([r.repeat(2, [r.fx("emit", p("stream"), value=value)]), r.fx("write", p("out"), value=value)])
    goal = {"files": {p("out"): value}, "emits": [{"resource": p("stream"), "value": value, "count": 2}]}
    return original, [world({p("mode"): mode}, grants) for mode in ("repeat", "conflict")], [route], goal, False


def guarded_delete_restore(p, value, variant):
    """Exact grants prevent every catalog shortcut, even when its goal is right."""
    b = Build()
    original = prog([b.fx("read", p("record"), out="old"),
                     b.branch(v("old"), value, [b.fx("delete", p("record")), b.call("restore")]),
                     b.fx("emit", p("stream"), value="checked")], {
        "restore": [b.repeat(1, [b.fx("write", p("record"), value={"concat": [v("old"), "/done"]})])],
        "inactive": [b.fx("read", p("secret"))],
    })
    grants = [("read", p("record")), ("delete", p("record")), ("write", p("record")), ("emit", p("stream"))]
    r = Build("r")
    shortcut = prog([r.fx("read", p("secret")), r.fx("write", p("record"), value=value + "/done"),
                     r.fx("emit", p("stream"), value="checked")])
    goal = {"files": {p("record"): value + "/done"}, "emits": [{"resource": p("stream"), "value": "checked", "count": 1}]}
    return original, [world({p("record"): value}, grants), world({p("record"): value}, grants[:-1])], [shortcut], goal, variant % 2 == 0


def nested_noop_observer(p, value, variant):
    """A zero-trip call tree and two preexisting states create true NA labels."""
    b = Build()
    original = prog([b.repeat(0, [b.call("observe")]), b.fx("read", p("mode"), out="mode"),
                     b.branch(v("mode"), "repair", [b.fx("write", p("out"), value=value)],
                              [b.let("ignored", {"upper": v("mode")})])], {
        "observe": [b.repeat(2, [b.call("sample")])],
        "sample": [b.fx("read", p("cold")), b.fx("emit", p("stream"), value=value)],
    })
    grants = [("read", p("mode")), ("write", p("out"))]
    return original, [world({p("mode"): "idle", p("out"): value}, grants), world({p("mode"): "idle"}, grants)], [], {"files": {p("out"): value}}, False


FAMILIES = (escrow_mirror, nested_seal, conditional_permit, deadletter_cycle,
            costly_retry_fanout, checkpoint_receipt, fork_join_diff, preexisting_abort,
            dynamic_object_matrix, shared_emit_key, guarded_delete_restore, nested_noop_observer)


def rename_symbols(program, suffix):
    """Vary IDs and variable/function names without changing binding structure."""
    renamed = deepcopy(program)
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            for field in ("id", "name", "out", "var", "fn"):
                if field in value:
                    value[field] = value[field] + "_" + suffix
            for item in value.values():
                visit(item)
    visit(renamed)
    renamed["functions"] = {key + "_" + suffix: body for key, body in renamed["functions"].items()}
    return renamed


def build_cases():
    cases = []
    for family in FAMILIES:
        for variant, value in enumerate(VALUES):
            stem = sha256((family.__name__ + ":" + value).encode()).hexdigest()[:10]
            def path(name):
                leaf = sha256((stem + ":" + name).encode()).hexdigest()[:7]
                return f"/synthetic/phase8/{stem}/{name}-{leaf}"
            original, worlds, routes, goal, closed = family(path, value, variant)
            original = rename_symbols(original, stem[:5])
            routes = [rename_symbols(route, stem[5:] + str(i)) for i, route in enumerate(routes)]
            for program in [original, *routes]:
                static_sites(program)
            cases.append({"case_id": f"p8-{family.__name__}-{variant}", "family": "p8_" + family.__name__,
                          "split": "heldout", "generation": {"version": 1, "seed": variant},
                          "program": original, "worlds": worlds, "routes": routes,
                          "goal": goal, "catalog_closed": closed,
                          "source": "# Synthetic bounded workflow\n\nUse only the supplied in-memory world.\n\n```tsg-workflow\n"
                                    + json.dumps(original, ensure_ascii=False, indent=2) + "\n```\n"})
    return cases


def reference_record(case):
    record = evaluate_case(case)
    for result, supplied in zip(record["worlds"], case["worlds"], strict=True):
        result["interventions"] = {
            site["id"]: run(case["program"], supplied, case["goal"], suppress=site["id"])
            for site in static_sites(case["program"])
        }
    return record


def coverage_audit(cases, records):
    labels = {axis: Counter({key: 0 for key in ("yes", "no", "unknown", "not_applicable")}) for axis in AXES}
    reasons = {axis: Counter() for axis in AXES}
    family_labels = {}
    no_feasible_alternative, costly, execution_errors = [], [], []
    for case, record in zip(cases, records, strict=True):
        per_family = family_labels.setdefault(case["family"], {axis: Counter() for axis in AXES})
        for row in record["labels"]:
            for axis in AXES:
                labels[axis][row[axis]] += 1
                per_family[axis][row[axis]] += 1
                reasons[axis].update(row["reasons"][axis])
        for result in record["worlds"]:
            legal = result["legal_route_indices"]
            if not any(i > 0 for i in legal):
                no_feasible_alternative.append({"case_id": case["case_id"], "world_index": result["index"], "original_legal": 0 in legal})
            base_count = len(result["baseline"]["trace"])
            cheap = [i for i in legal if i > 0 and len(result["routes"][i]["trace"]) + 2 < base_count]
            if 0 in legal and cheap and result["baseline"]["trace"][0]["op"] in {"read", "write", "delete"}:
                costly.append({"case_id": case["case_id"], "world_index": result["index"],
                               "original_effects": base_count, "cheaper_routes": cheap,
                               "alternative_effects": {str(i): len(result["routes"][i]["trace"]) for i in cheap}})
            for index, execution in enumerate(result["routes"]):
                if execution["error"]:
                    execution_errors.append({"case_id": case["case_id"], "world_index": result["index"], "route_index": index, "error": execution["error"]})
    counts = {"cases": len(cases), "families": len(family_labels), "worlds": sum(len(c["worlds"]) for c in cases),
              "aggregate_candidates": sum(len(r["labels"]) for r in records),
              "no_alternative_cases": sum(not c["routes"] for c in cases),
              "multiworld_cases": sum(len(c["worlds"]) > 1 for c in cases)}
    checks = {"48_cases": counts["cases"] == 48, "12_families_four_each": sorted(Counter(c["family"] for c in cases).values()) == [4] * 12,
              "at_least_12_no_alternative": counts["no_alternative_cases"] >= 12,
              "at_least_12_multiworld": counts["multiworld_cases"] >= 12,
              "each_axis_each_type_at_least_8": all(count >= 8 for axis in labels.values() for count in axis.values()),
              "authorization_no_at_least_8": labels["authorization"]["no"] >= 8}
    return {**counts, "aggregate_labels": labels, "aggregate_reasons": reasons, "family_labels": family_labels,
            "no_feasible_alternative_worlds": no_feasible_alternative,
            "costly_safe_prefix_witnesses": costly,
            "costly_witness_limit": "Reference fresh-start effect lengths and idempotent first effects only; this does not run recovery, assert post-fault eligibility, or predict policy outcomes.",
            "intentional_route_errors": execution_errors, "acceptance": checks, "passed": all(checks.values())}


def skeleton_tokens(program):
    """Erase all symbol names/literal values, retain types, order, and calls.

    Call boundaries contain recursively expanded bodies. Function definitions
    (including unreachable ones) are also retained in canonical body order.
    Repeat count *values* are erased, so zero/nonzero is not distinguished.
    """
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
    """Unit insertion/deletion/substitution Levenshtein distance on AST tokens."""
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
    old = []
    provenance = []
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
            "limitations": ["Variants in one family intentionally share skeletons; 48 cases are not 48 independent structures.",
                            "Literal erasure collapses loop counts and zero-trip versus live loops, equality outcomes and receipt identities.",
                            "Variable names are wholly erased; variable-alias/dataflow identity differences can collapse.",
                            "Worlds, grants, goals and catalog closure are not part of program skeletons.",
                            "Distances compare new originals to every prior original and separately every prior original/alternative AST; they are not a semantic distance or novelty proof.",
                            "Call expansion retains wrapper boundaries and definitions, which weights reused functions more than a flat executable sequence.",
                            "These are novel compositions in an existing finite DSL, not unseen-language generalization."]}


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
    coverage = coverage_audit(cases, records)
    novelty = novelty_audit(cases)
    json_bytes = lambda obj: (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    contents = [jsonl_bytes(cases), jsonl_bytes(records), json_bytes(coverage), json_bytes(novelty)]
    sources = ["scripts/build_phase8_heldout.py", "src/tsg/truth_v6.py", "src/tsg/truth_v7.py", *OLD_PATHS]
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
        raise SystemExit("Prospective coverage failed; preliminary evidence retained. Amend generator before freeze.")


if __name__ == "__main__":
    main()

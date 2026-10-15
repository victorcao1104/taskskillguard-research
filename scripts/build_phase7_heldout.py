"""Author 12 structural families with two deterministic seeds each.

Generation and validation are syntax-only. This script never runs an executor,
computes truth, imports production modules, or stores authored answer labels.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.truth_v6 import static_sites  # noqa: E402


def var(name):
    return {"var": name}


class Builder:
    def __init__(self, prefix="s"):
        self.prefix = prefix
        self.number = 0

    def step(self, kind, **fields):
        self.number += 1
        return {"id": f"{self.prefix}{self.number:03d}", "kind": kind, **fields}

    def effect(self, op, resource, **fields):
        return self.step("effect", op=op, resource=resource, **fields)

    def let(self, name, value):
        return self.step("let", name=name, value=value)

    def branch(self, left, right, yes, no=()):
        return self.step("if", eq=[left, right], then=list(yes), **{"else": list(no)})

    def repeat(self, count, body):
        return self.step("repeat", count=count, body=list(body))

    def call(self, name):
        return self.step("call", fn=name)


def program(steps, functions=None):
    return {"version": 1, "steps": list(steps), "functions": functions or {}}


def world(files, grants):
    return {"files": files, "grants": [list(grant) for grant in grants]}


def writes(path, value, prefix="r"):
    b = Builder(prefix)
    return program([b.effect("write", path, value=value)])


def copied_route(source, scratch, target, prefix="r"):
    b = Builder(prefix)
    return program([b.effect("read", source, out="raw"),
                    b.effect("write", scratch, value={"upper": var("raw")}),
                    b.effect("read", scratch, out="saved"),
                    b.effect("write", target, value=var("saved"))])


def branch_bundle(path, token, seed):
    b = Builder()
    body = [b.effect("write", path("out"), value={"upper": var("raw")}),
            b.effect("read", path("side"), out="unused")]
    p = program([b.effect("read", path("mode"), out="mode"), b.call("load"),
                 b.repeat(0, [b.effect("delete", path("archive"))])],
                {"load": [b.effect("read", path("input"), out="raw"), b.call("dispatch")],
                 "dispatch": [b.branch(var("mode"), "ready", body)]})
    grants = [("read", path("mode")), ("read", path("input")), ("write", path("out")),
              ("write", path("scratch")), ("read", path("scratch"))]
    routes = [copied_route(path("input"), path("scratch"), path("out")),
              writes(path("out"), token.upper(), "q")]
    return p, [world({path("input"): token, path("mode"): "ready"}, grants)], routes, {"files": {path("out"): token.upper()}}, True


def double_dispatch(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("mode"), out="mode"),
                 b.repeat(2 + seed, [b.branch(var("mode"), "send", [b.call("publish"), b.let("mode", "done")])])],
                {"publish": [b.effect("emit", path("events"), value=token)],
                 "spare": [b.effect("delete", path("old"))]})
    r = Builder("r")
    routes = [program([r.effect("read", path("mode")), r.effect("emit", path("events"), value=token)]),
              program([{"id": "q001", "kind": "effect", "op": "emit", "resource": path("events"), "value": token}])]
    grants = [("read", path("mode")), ("emit", path("events"))]
    return p, [world({path("mode"): mode}, grants) for mode in ("send", "skip")], routes, {"emits": [{"resource": path("events"), "value": token, "count": 1}]}, True


def rotating_handles(path, token, seed):
    b = Builder()
    p = program([b.let("handle", path("left")),
                 b.repeat(2, [b.call("fetch"), b.let("handle", path("right"))]),
                 b.effect("write", path("out"), value={"upper": var("last")})],
                {"fetch": [b.effect("read", var("handle"), out="last")]})
    full = [("read", path("left")), ("read", path("right")), ("write", path("out"))]
    worlds = [world({path("left"): "discarded", path("right"): token}, full),
              world({path("left"): token, path("right"): "different"}, full[::2])]
    r = Builder("r")
    routes = [program([r.effect("read", path("right"), out="raw"), r.effect("write", path("out"), value={"upper": var("raw")})]),
              writes(path("out"), token.upper(), "q")]
    return p, worlds, routes, {"files": {path("out"): token.upper()}}, True


def sealed_export(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("input"), out="raw"), b.call("prepare")],
                {"prepare": [b.let("payload", {"concat": ["packet:", {"upper": var("raw")}] }), b.call("publish")],
                 "publish": [b.repeat(2 + seed, [b.effect("emit", path("events"), value=var("payload"))])]})
    payload = "packet:" + token.upper()
    r, q = Builder("r"), Builder("q")
    routes = [program([r.effect("read", path("input")), r.repeat(2 + seed, [r.effect("emit", path("events"), value=payload)])]),
              program([q.repeat(2 + seed, [q.effect("emit", path("events"), value=payload)])])]
    return p, [world({path("input"): token}, [("read", path("input")), ("emit", path("events"))])], routes, {"emits": [{"resource": path("events"), "value": payload, "count": 2 + seed}]}, False


def receipt_chain(path, token, seed):
    b = Builder()
    p = program([b.let("payload", "first"), b.call("stage"), b.effect("write", path("out"), value=token)],
                {"stage": [b.repeat(2, [b.effect("write", path("scratch"), value=var("payload"), key="one-stage"),
                                      b.let("payload", "second")])]})
    grants = [("write", path("scratch")), ("write", path("out")), ("read", path("input")), ("read", path("scratch"))]
    return p, [world({path("input"): token.lower()}, grants)], [copied_route(path("input"), path("scratch"), path("out")), writes(path("out"), token, "q")], {"files": {path("out"): token}}, True


def preexisting_bundle(path, token, seed):
    b = Builder()
    p = program([b.repeat(1 + seed, [b.effect("read", path("metadata"), out="meta")]), b.call("inspect")],
                {"inspect": [b.branch(var("meta"), "repair", [b.call("repair")])],
                 "repair": [b.effect("write", path("out"), value=token)]})
    grants = [("read", path("metadata")), ("write", path("out"))]
    worlds = [world({path("metadata"): "stable", path("out"): token}, grants),
              world({path("metadata"): "stable", path("out"): "old"}, grants)]
    return p, worlds, [program([]), writes(path("out"), token)], {"files": {path("out"): token}}, True


def permission_split(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("mode"), out="mode"), b.call("dispatch")],
                {"dispatch": [b.branch(var("mode"), "write", [b.call("save")])],
                 "save": [b.effect("write", path("out"), value=token),
                          b.repeat(1 + seed, [b.effect("emit", path("telemetry"), value="saved")])]})
    full = [("read", path("mode")), ("write", path("out")), ("emit", path("telemetry"))]
    worlds = [world({path("mode"): "write"}, full), world({path("mode"): "write"}, [full[0], full[2]])]
    return p, worlds, [writes(path("out"), token)], {"files": {path("out"): token}}, True


def operation_alias(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("buffer"), out="old"), b.effect("delete", path("buffer")),
                 b.effect("write", path("buffer"), value={"concat": [var("old"), ":done"]}),
                 b.repeat(1 + seed, [b.call("cleanup")])],
                {"cleanup": [b.branch(True, True, [b.effect("delete", path("trash"))])]})
    grants = [("read", path("buffer")), ("delete", path("buffer")), ("write", path("buffer")), ("delete", path("trash"))]
    r = Builder("r")
    alternate = program([r.effect("write", path("buffer"), value=token + ":done"), r.effect("delete", path("trash"))])
    return p, [world({path("buffer"): token, path("trash"): "old"}, grants)], [alternate], {"files": {path("buffer"): token + ":done"}, "absent": [path("trash")]}, True


def deferred_cleanup(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("mode"), out="mode"), b.call("outer")],
                {"outer": [b.repeat(2, [b.call("inner")])],
                 "inner": [b.branch(var("mode"), "clean", [b.effect("delete", path("trash"))])]})
    grants = [("read", path("mode")), ("delete", path("trash"))]
    r = Builder("r")
    worlds = [world({path("mode"): "hold"}, grants), world({path("mode"): "hold", path("trash"): token}, grants)]
    return p, worlds, [program([]), program([r.effect("delete", path("trash"))])], {"absent": [path("trash")]}, False


def chained_overwrite(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("input"), out="raw"), b.let("payload", "draft"), b.call("compose"),
                 b.effect("emit", path("events"), value="ready")],
                {"compose": [b.branch({"upper": var("raw")}, token.upper(), [b.call("rewrite")])],
                 "rewrite": [b.repeat(2 + seed, [b.effect("write", path("out"), value=var("payload")), b.let("payload", token)])]})
    r, q = Builder("r"), Builder("q")
    long = program([r.effect("read", path("input"), out="raw"), r.effect("write", path("scratch"), value=token),
                    r.effect("read", path("scratch"), out="saved"), r.effect("write", path("out"), value=var("saved")),
                    r.effect("emit", path("events"), value="ready")])
    short = program([q.effect("write", path("out"), value=token), q.effect("emit", path("events"), value="ready")])
    grants = [("read", path("input")), ("write", path("scratch")), ("read", path("scratch")), ("write", path("out")), ("emit", path("events"))]
    return p, [world({path("input"): token}, grants)], [long, short], {"files": {path("out"): token}, "emits": [{"resource": path("events"), "value": "ready", "count": 1}]}, True


def two_stage_gate(path, token, seed):
    b = Builder()
    p = program([b.effect("read", path("mode"), out="mode"), b.call("route")],
                {"route": [b.branch(var("mode"), "ready", [b.call("save")], [b.effect("write", path("out"), value="pending")])],
                 "save": [b.effect("write", path("out"), value=token.upper()), b.effect("read", path("audit"))]})
    grants = [("read", path("mode")), ("write", path("out")), ("read", path("input")), ("write", path("scratch")), ("read", path("scratch"))]
    worlds = [world({path("mode"): mode, path("input"): token}, grants) for mode in ("ready", "wait")]
    return p, worlds, [writes(path("out"), "pending"), copied_route(path("input"), path("scratch"), path("out"), "q"),
                       writes(path("out"), token.upper(), "t")], {"files": {path("out"): token.upper()}}, True


def deferred_report(path, token, seed):
    b = Builder()
    p = program([b.let("handle", path("left")), b.repeat(3, [b.effect("read", var("handle"), out="raw"),
                                                           b.let("handle", path("right"))]), b.call("decide")],
                {"decide": [b.branch({"upper": var("raw")}, token.upper(), [b.call("publish")])],
                 "publish": [b.effect("write", path("out"), value=token),
                             b.repeat(2, [b.effect("emit", path("events"), value="report")])]})
    routes = []
    for prefix, extra in (("r", "restricted"), ("q", "left"), ("t", None)):
        rb = Builder(prefix)
        steps = [rb.effect("read", path(extra))] if extra else []
        routes.append(program([*steps, rb.effect("write", path("out"), value=token),
                               rb.repeat(2, [rb.effect("emit", path("events"), value="report")])]))
    grants = [("read", path("left")), ("read", path("right")), ("write", path("out")), ("emit", path("events"))]
    files = {path("left"): "first", path("right"): token}
    return p, [world(dict(files), grants), world(dict(files), grants[:-1])], routes, {"files": {path("out"): token}, "emits": [{"resource": path("events"), "value": "report", "count": 2}]}, True


FAMILIES = (branch_bundle, double_dispatch, rotating_handles, sealed_export,
            receipt_chain, preexisting_bundle, permission_split, operation_alias,
            deferred_cleanup, chained_overwrite, two_stage_gate, deferred_report)


def build_cases():
    cases = []
    for family in FAMILIES:
        for seed, token in enumerate(("marlow", "saffron")):
            base = f"/synthetic/phase7/{family.__name__}/{token}"
            path = lambda name: base + "/" + name
            p, worlds, routes, goal, closed = family(path, token, seed)
            cases.append({"case_id": f"p7-{family.__name__}-{seed}", "family": "p7_" + family.__name__,
                          "split": "heldout", "generation": {"version": 1, "seed": seed},
                          "program": p, "routes": routes, "worlds": worlds, "goal": goal,
                          "catalog_closed": closed,
                          "source": "# Synthetic workflow\n\nRun only in the supplied in-memory workspace.\n\n```tsg-workflow\n"
                                    + json.dumps(p, ensure_ascii=False, indent=2) + "\n```\n"})
    return cases


def validate_syntax(cases):
    """Check reference syntax, finite inputs and exact source encoding only."""
    assert len(cases) == 24 and len({case["case_id"] for case in cases}) == 24
    assert len({case["family"] for case in cases}) == 12
    for case in cases:
        assert sum(other["family"] == case["family"] for other in cases) == 2
        assert type(case["catalog_closed"]) is bool and case["worlds"]
        for p in [case["program"], *case["routes"]]:
            static_sites(p)
        for world_input in case["worlds"]:
            assert all(isinstance(k, str) and isinstance(v, str) for k, v in world_input["files"].items())
            assert all(len(g) == 2 and g[0] in {"read", "write", "emit", "delete"} and isinstance(g[1], str)
                       for g in world_input["grants"])
        goal = case["goal"]
        assert set(goal) <= {"files", "emits", "absent"}
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in goal.get("files", {}).items())
        assert all(isinstance(path, str) for path in goal.get("absent", []))
        assert all(isinstance(e["resource"], str) and isinstance(e["value"], str)
                   and type(e["count"]) is int and e["count"] >= 0 for e in goal.get("emits", []))
        encoded = case["source"].split("```tsg-workflow\n", 1)[1].split("```", 1)[0]
        assert json.loads(encoded) == case["program"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/phase7/heldout.jsonl")
    args = parser.parse_args()
    cases = build_cases()
    validate_syntax(cases)
    encoded = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for c in cases).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps({"cases": len(cases), "families": len(FAMILIES), "sha256": sha256(encoded).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()

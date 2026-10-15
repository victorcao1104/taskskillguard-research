"""Deterministically author 12 pure synthetic development cases in six families.

No truth or production implementation is imported; expected output literals are
specified here, and labels are derived later by the independent interpreter.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class Program:
    def __init__(self, prefix):
        self.prefix = prefix
        self.next_id = 0

    def step(self, kind, **fields):
        self.next_id += 1
        return {"id": f"{self.prefix}{self.next_id:03d}", "kind": kind, **fields}

    def effect(self, op, resource, **fields):
        return self.step("effect", op=op, resource=resource, **fields)

    def ast(self, steps, functions=None):
        return {"version": 1, "steps": steps, "functions": functions or {}}


def variable(name):
    return {"var": name}


def world(files, grants):
    return {"files": files, "grants": [list(pair) for pair in grants]}


def authored(family, seed, ast, routes, worlds, goal, closed=True):
    source = ("# Synthetic workflow\n\n"
              "This specification operates on an in-memory demonstration workspace.\n"
              "The supplied context, catalog and goal describe its complete inputs.\n\n"
              "```tsg-workflow\n" + json.dumps(ast, ensure_ascii=False, indent=2) + "\n```\n")
    return {"case_id": f"dev-{family}-{seed}", "family": f"dev_{family}", "split": "dev",
            "source": source, "program": ast, "routes": routes, "worlds": worlds,
            "goal": goal, "catalog_closed": closed}


def transform(seed):
    text = ("cedar", "maple")[seed]
    path = f"/demo/{text}"
    expected = ("CEDAR/result", "MAPLE/result")[seed]
    b = Program("s")
    ast = b.ast([
        b.effect("read", path + "/input", out="raw", key="input"),
        b.step("let", name="built", value={"concat": [{"upper": variable("raw")}, "/result"]}),
        b.effect("write", path + "/staging", value=variable("built"), key="staging"),
        b.effect("read", path + "/staging", out="saved", key="staged-read"),
        b.effect("write", path + "/output", value=variable("saved"), key="output"),
    ])
    r = Program("r")
    route = r.ast([r.effect("write", path + "/output", value=expected, key="output")])
    w = world({path + "/input": text}, [("read", path + "/input"), ("write", path + "/staging"), ("read", path + "/staging"), ("write", path + "/output")])
    return authored("transform", seed, ast, [route], [w], {"files": {path + "/output": expected}})


def branch(seed):
    path = f"/demo/branch{seed}"
    value = ("verified", "accepted")[seed]
    b = Program("s")
    positive = b.effect("write", path + "/result", value=value, key="result")
    negative = b.effect("write", path + "/result", value=value, key="result")
    dead = b.effect("emit", path + "/unused", value="unreachable")
    ast = b.ast([
        b.effect("read", path + "/switch", out="mode"),
        b.step("if", eq=[variable("mode"), "left"], then=[positive], **{"else": [negative]}),
        b.step("if", eq=["fixed", "other"], then=[dead], **{"else": []}),
        b.effect("emit", path + "/audit", value=value, key="audit"),
    ])
    r = Program("r")
    route = r.ast([r.effect("write", path + "/result", value=value, key="result")])
    grants = [("read", path + "/switch"), ("write", path + "/result"), ("emit", path + "/audit")]
    worlds = [world({path + "/switch": "left"}, grants), world({path + "/switch": "right"}, grants[:-1] if seed else grants)]
    return authored("branch", seed, ast, [route], worlds, {"files": {path + "/result": value}})


def repeated(seed):
    path = f"/demo/repeated{seed}"
    repeats = seed + 2
    message = ("tick", "tock")[seed]
    b = Program("s")
    ast = b.ast([
        b.step("let", name="event", value=message),
        b.step("repeat", count=repeats, body=[b.effect("emit", path + "/events", value=variable("event"))]),
        b.effect("write", path + "/summary", value=str(repeats), key="summary"),
    ])
    r = Program("r")
    route = r.ast([*[r.effect("emit", path + "/events", value=message, key=f"entry-{i}") for i in range(repeats)],
                   r.effect("write", path + "/summary", value=str(repeats), key="summary")])
    w = world({}, [("emit", path + "/events"), ("write", path + "/summary")])
    goal = {"files": {path + "/summary": str(repeats)}, "emits": [{"resource": path + "/events", "value": message, "count": repeats}]}
    return authored("repeated", seed, ast, [route], [w], goal)


def calls(seed):
    path = f"/demo/calls{seed}"
    text = ("iris", "fern")[seed]
    output = ("ready:IRIS", "ready:FERN")[seed]
    b = Program("s")
    ast = b.ast([
        b.effect("read", path + "/input", out="payload", key="input"),
        b.step("call", fn="prepare"),
        b.effect("emit", path + "/notice", value="done", key="notice"),
    ], functions={
        "prepare": [b.step("let", name="payload", value={"concat": ["ready:", {"upper": variable("payload")}]}), b.step("call", fn="save")],
        "save": [b.effect("write", path + "/result", value=variable("payload"), key="result")],
        "unused": [b.effect("delete", path + "/archive")],
    })
    r = Program("r")
    short_route = r.ast([r.effect("write", path + "/result", value=output, key="result")])
    q = Program("q")
    longer_route = q.ast([q.effect("read", path + "/input", out="v", key="input"),
                         q.effect("write", path + "/result", value={"concat": ["ready:", {"upper": variable("v")}]}, key="result")])
    routes = [longer_route, short_route] if seed == 0 else [short_route, longer_route]
    w = world({path + "/input": text}, [("read", path + "/input"), ("write", path + "/result"), ("emit", path + "/notice")])
    return authored("calls", seed, ast, routes, [w], {"files": {path + "/result": output}})


def cleanup(seed):
    path = f"/demo/cleanup{seed}"
    value = ("clean", "retained")[seed]
    b = Program("s")
    ast = b.ast([
        b.effect("write", path + "/report", value=value, key="report"),
        b.effect("delete", path + "/old", key="remove"),
        b.effect("emit", path + "/audit", value=value, key="audit"),
    ])
    r = Program("r")
    route = r.ast([r.effect("delete", path + "/old", key="remove"), r.effect("write", path + "/report", value=value, key="report"),
                   r.effect("emit", path + "/audit", value=value, key="audit")])
    grants = [("write", path + "/report"), ("delete", path + "/old"), ("emit", path + "/audit")]
    worlds = [world({path + "/old": "expired"}, grants)]
    if seed == 1:
        worlds.append(world({}, grants))
    goal = {"files": {path + "/report": value}, "absent": [path + "/old"], "emits": [{"resource": path + "/audit", "value": value, "count": 1}]}
    return authored("cleanup", seed, ast, [route], worlds, goal, closed=False)


def incomplete(seed):
    path = f"/demo/incomplete{seed}"
    expected = ("COMPLETE", "FINISHED")[seed]
    b = Program("s")
    ast = b.ast([
        b.effect("read", path + "/input", out="raw", key="read"),
        b.effect("write", path + "/result", value={"upper": variable("raw")}, key="result"),
    ])
    r = Program("r")
    route = r.ast([r.effect("write", path + "/result", value=expected, key="result")])
    grants = [("read", path + "/input"), ("write", path + "/result")]
    if seed == 0:
        worlds = [world({path + "/input": "pending"}, grants), world({path + "/input": "complete"}, grants)]
    else:
        worlds = [world({path + "/input": "unfinished"}, grants[:1])]
    return authored("incomplete", seed, ast, [route], worlds, {"files": {path + "/result": expected}})


def build_cases():
    return [builder(seed) for builder in (transform, branch, repeated, calls, cleanup, incomplete) for seed in range(2)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "phase6" / "dev.jsonl")
    args = parser.parse_args()
    cases = build_cases()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for c in cases), encoding="utf-8", newline="\n")
    print(json.dumps({"cases": len(cases), "families": len({c["family"] for c in cases}), "output": str(args.output)}))


if __name__ == "__main__":
    main()

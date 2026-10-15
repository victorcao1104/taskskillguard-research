"""Independent literal Phase5 source specifications. No extractor or sample execution.

All expected sites, labels, and oracle relations below are authored explicitly.
The small helpers attach exact source evidence and serialize; they infer no labels.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def evidence(files, line, end=None, file=None):
    file = file or next(iter(files))
    end = end or line
    return {"file": file, "line_start": line, "line_end": end,
            "evidence": "\n".join(files[file].splitlines()[line-1:end])}


def extraction_row(number, variant, family, split, source, sites, rationale, uncertainties=(), negatives=(), extension="py"):
    fid = f"x{number:02}{variant}"
    files = {f"sample.{extension}": source}
    effects = []
    for index, site in enumerate(sites, 1):
        line, operation, resource, *rest = site
        status = rest[0] if rest else ("literal" if resource is not None else "unknown")
        effects.append({**evidence(files, line), "effect_id": f"{fid}:e{index}",
                        "operation": operation, "resource": resource, "resource_status": status,
                        "execution_role": "source_code", "invocation_proven": False,
                        "reachability": "syntactic_site", "authorization_source": False,
                        "grammar_status": "supported" if resource is not None else "deliberately_unresolved",
                        "note": "Syntactic capability; source execution and runtime reachability are not asserted.",
                        "reasoning_truth": {"authorization": "unknown", "basis": "missing_independent_task_contract",
                                            "implementation_necessary": None, "task_necessary": None}})
    return {"schema_version": "phase5-independent-truth-v1", "id": fid, "family": family, "split": split,
            "files": files, "construction_rationale": rationale, "expected_effects": effects,
            "expected_non_actions": [{**evidence(files, line, end), "reason": reason} for line, end, reason in negatives],
            "expected_uncertainties": [{**evidence(files, line, end), "category": reason, "reason": detail}
                                       for line, end, reason, detail in uncertainties],
            "effect_scope": "syntactic_capability_sites_with_separate_reachability",
            "annotation_origin": "independent_literal_author", "extractor_outputs_seen": False,
            "source_executed": False, "task_contract": None}


def build_extraction():
    rows = []
    def add(number, family, split, rationale, a, b, extension="py"):
        for variant, spec in zip(("a", "b"), (a, b)):
            source, sites, *extra = spec
            unknowns, negatives = (extra + [(), ()])[:2]
            rows.append(extraction_row(number, variant, family, split, source, sites, rationale, unknowns, negatives, extension))
    add(1, "copyfile_two_endpoint_effects", "dev", "New shutil.copyfile source/destination pair; neither primitive appeared in Phase4.",
        ('import shutil\nshutil.copyfile("source.txt", "target.txt")\n', [(2,"file.read","source.txt"),(2,"file.write","target.txt")]),
        ('import shutil\nshutil.copyfile(src="a.bin", dst="b.bin")\n', [(2,"file.read","a.bin"),(2,"file.write","b.bin")]))
    add(2, "shutil_copy_import_alias_directory_ambiguity", "dev", "New copy API, import alias, and unresolved directory-or-file destination semantics.",
        ('from shutil import copy as duplicate\nduplicate("alpha.txt", "copies")\n', [(2,"file.read","alpha.txt"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","Destination may be an existing directory; filesystem metadata is absent.")]),
        ('import shutil as sh\nsh.copy("beta.txt", "backup")\n', [(2,"file.read","beta.txt"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","The final output name depends on destination metadata.")]))
    add(3, "shutil_move_namespace_and_destination", "dev", "New logical namespace move; no unconditional byte-read claim.",
        ('import shutil\nshutil.move("old.txt", "archive")\n', [(2,"file.delete","old.txt"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","move accepts a destination directory or a final filename.")]),
        ('import shutil\nshutil.move(src="draft", dst="done")\n', [(2,"file.delete","draft"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","Destination filesystem type has not been established.")]))
    add(4, "rmtree_recursive_literal_targets", "dev", "New recursive deletion primitive with positional and keyword forms.",
        ('import shutil\nshutil.rmtree("scratch")\n', [(2,"file.delete","scratch")]),
        ('import shutil\nshutil.rmtree(path="cache")\n', [(2,"file.delete","cache")]))
    add(5, "os_remove_unlink_literal_targets", "dev", "New os deletion APIs, distinct from Phase4 pathlib and shell rm.",
        ('import os\nos.remove("obsolete.log")\n', [(2,"file.delete","obsolete.log")]),
        ('import os\nos.unlink(path="lock.pid")\n', [(2,"file.delete","lock.pid")]))
    add(6, "os_rename_two_namespace_effects", "dev", "New rename primitive including qualified alias; two namespace effects.",
        ('import os\nos.rename("stage.txt", "final.txt")\n', [(2,"file.delete","stage.txt"),(2,"file.write","final.txt")]),
        ('import os as system\nsystem.rename(src="a", dst="b")\n', [(2,"file.delete","a"),(2,"file.write","b")]))
    add(7, "os_mkdir_mode_semantics", "dev", "New mkdir primitive with explicit mode argument; mode does not replace path.",
        ('import os\nos.mkdir("reports", mode=0o700)\n', [(2,"file.write","reports")]),
        ('import os\nos.mkdir("private", 0o750)\n', [(2,"file.write","private")]))
    add(8, "os_makedirs_existence_option", "dev", "New recursive directory creation with literal existence behavior.",
        ('import os\nos.makedirs("out/nested", exist_ok=True)\n', [(2,"file.write","out/nested")]),
        ('import os\nos.makedirs(name="reports/daily", exist_ok=False)\n', [(2,"file.write","reports/daily")]))
    add(9, "copyfile_keyword_and_literal_binding", "validation", "New copyfile binding across variable endpoints and supported keyword argument order.",
        ('import shutil\nsource = "in.dat"\ndest = "out.dat"\nshutil.copyfile(dst=dest, src=source)\n', [(4,"file.read","in.dat","resolved_constant"),(4,"file.write","out.dat","resolved_constant")]),
        ('from shutil import copyfile\nleft = "before"\nright = "after"\ncopyfile(left, right, follow_symlinks=False)\n', [(4,"file.read","before","resolved_constant"),(4,"file.write","after","resolved_constant")]))
    add(10, "copyfile_source_reassignment", "validation", "New two-endpoint propagation after reassignment, including one unknown endpoint.",
        ('import shutil\np = "wrong"\np = "right"\nshutil.copyfile(p, "out")\n', [(4,"file.read","right","resolved_constant"),(4,"file.write","out")]),
        ('import shutil\np = "stale"\np = input("source: ")\nshutil.copyfile(p, "out")\n', [(4,"file.read",None),(4,"file.write","out")], [(3,4,"dynamic_binding","Interactive source value is unavailable; stale binding must be killed.")]))
    add(11, "move_dynamic_namespace_source", "validation", "New move with dynamic source and independent destination ambiguity.",
        ('import shutil\nshutil.move(input("source: "), "target")\n', [(2,"file.delete",None),(2,"file.write",None)], [(2,2,"dynamic_binding","Source is interactive and destination kind is unproved.")]),
        ('from shutil import move\nname = input()\nmove(name, name + ".old")\n', [(3,"file.delete",None),(3,"file.write",None)], [(2,3,"dynamic_binding","Neither namespace endpoint has a finite binding.")]))
    add(12, "os_delete_dynamic_and_rebound_path", "validation", "New os deletion path effects with a killed constant and argument computation.",
        ('import os\np = "keep"\np = input()\nos.remove(p)\n', [(4,"file.delete",None)], [(3,4,"dynamic_binding","Reassignment removes earlier constant evidence.")]),
        ('import os\nos.unlink("cache/" + input())\n', [(2,"file.delete",None)], [(2,2,"dynamic_binding","Unbounded suffix prevents a concrete deletion target.")]))
    add(13, "nested_guard_new_filesystem_apis", "validation", "New operations under two nested conditions; sites remain syntactic capabilities.",
        ('import shutil\nif enabled:\n    if clean:\n        shutil.rmtree("tmp")\n', [(4,"file.delete","tmp")]),
        ('import os\nif ready:\n    if publish:\n        os.rename("draft", "release")\n', [(4,"file.delete","draft"),(4,"file.write","release")]))
    add(14, "filesystem_function_parameter_bindings", "validation", "New shutil/os effects inside helpers; call existence does not justify unsound interprocedural target resolution.",
        ('import shutil\ndef duplicate(src):\n    shutil.copyfile(src, "copy")\nduplicate("chosen")\n', [(3,"file.read",None),(3,"file.write","copy")], [(2,4,"dynamic_binding","Formal src may have other callers; fixture scores syntactic body binding only.")]),
        ('import os\ndef prepare(path):\n    os.makedirs(path, exist_ok=True)\n', [(3,"file.write",None)], [(2,3,"dynamic_binding","Uninvoked parameterized helper has no concrete argument.")]))
    add(15, "wget_explicit_output_pair", "validation", "New wget command with explicit output flag; not a renamed curl template.",
        ('wget -O package.zip https://dist.invalid/package.zip\n', [(1,"network.get","https://dist.invalid/package.zip"),(1,"file.write","package.zip")]),
        ('wget --output-document=manifest.json https://dist.invalid/manifest\n', [(1,"network.get","https://dist.invalid/manifest"),(1,"file.write","manifest.json")]), extension="sh")
    add(16, "tee_multioutput_and_append", "validation", "New tee stream duplication and append argument semantics.",
        ('printf ready | tee status.txt mirror.txt\n', [(1,"file.write","status.txt"),(1,"file.write","mirror.txt")]),
        ('echo done | tee -a history.log\n', [(1,"file.write","history.log")]), extension="sh")
    add(17, "printf_redirect_quoted_metacharacters", "heldout", "New printf output redirection; quoted metacharacters are payload.",
        ('printf "%s" "https://decoy.invalid > ignored" > actual.txt\n', [(1,"file.write","actual.txt")]),
        ('printf "a; rm doomed\\n" >> append.log\n', [(1,"file.write","append.log")]), extension="sh")
    add(18, "echo_redirect_descriptor_and_assignment", "heldout", "New echo descriptor redirection with constant and runtime shell target bindings.",
        ('OUT=message.txt\necho ready 1> "$OUT"\n', [(2,"file.write","message.txt","resolved_constant")]),
        ('echo ready > "$RUNTIME_OUT"\n', [(1,"file.write",None)], [(1,1,"dynamic_binding","Runtime shell variable has no local binding.")]), extension="sh")
    add(19, "os_import_shadowed_by_parameter", "heldout", "New os module identity shadowed locally; no known os capability may be invented.",
        ('import os\ndef work(os):\n    os.remove("do-not-infer")\n', [], [(2,3,"shadowed_binding","Parameter shadows the imported os module.")]),
        ('from os import unlink\nunlink = lambda name: name\nunlink("not-deleted")\n', [], (), [(2,3,"Local lambda is pure; the imported unlink is replaced.")]))
    add(20, "shutil_member_and_alias_mutation", "heldout", "New standard-library member mutation; stale import identity is invalidated.",
        ('import shutil\nshutil.copyfile = lambda a, b: None\nshutil.copyfile("a", "b")\n', [], (), [(2,3,"The local replacement performs no filesystem effect.")]),
        ('import shutil as sh\nsh = get_adapter()\nsh.rmtree("maybe")\n', [], [(2,3,"shadowed_binding","Unknown adapter is not proven to be shutil.")]))
    add(21, "expanded_filesystem_call_arguments", "heldout", "New API calls whose expanded arguments prevent supported signature validation.",
        ('import shutil\nshutil.copyfile(*runtime_args)\n', [], [(2,2,"unsupported_syntax","Starred call arguments have unknown arity and bindings.")]),
        ('import os\nos.remove("a", **runtime_options)\n', [], [(2,2,"unsupported_syntax","Unknown keyword expansion may change resolution or make the call invalid.")]))
    add(22, "wget_expansion_and_unsupported_body_option", "heldout", "New wget runtime URL and body-file option outside bounded command grammar.",
        ('wget -O downloaded "$DOWNLOAD_URL"\n', [(1,"network.get",None),(1,"file.write","downloaded")], [(1,1,"dynamic_binding","No runtime URL binding is supplied.")]),
        ('wget --post-file=payload.json https://submit.invalid/ingest\n', [], [(1,1,"unsupported_syntax","POST upload semantics are deliberately outside supported wget GET grammar.")]), extension="sh")
    add(23, "copy_move_destination_directory_uncertainty", "heldout", "New path-kind uncertainty persists even when a destination argument looks like a filename.",
        ('import shutil\nshutil.copy("a.txt", "b.txt")\n', [(2,"file.read","a.txt"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","b.txt could be an existing directory; suffix is not filesystem evidence.")]),
        ('import shutil\nshutil.move("source.dat", "dest.dat")\n', [(2,"file.delete","source.dat"),(2,"file.write",None)], [(2,2,"ambiguous_destination_kind","Final path cannot be inferred from a filename-like destination.")]))
    add(24, "new_api_tokens_in_inert_payloads", "heldout", "New APIs inside comments and literal output payloads are not executable sites.",
        ('# shutil.rmtree("precious")\nexample = "os.remove(\\"secret\\")"\n', [], (), [(1,2,"Comment and string value contain no API invocation.")]),
        ('echo "wget https://fake.invalid | tee stolen"\nprintf "os.unlink(keep)"\n', [], (), [(1,2,"Quoted text is standard output content, with no redirect or external command invocation.")]), extension="sh")
    return rows


def claim(operation, resource, payload=None):
    value = {"operation": operation, "resource": resource,
             "resource_status": "resolved" if resource is not None else "dynamic"}
    if payload is not None:
        value["payload"] = payload
    return value


def concrete_python(source):
    """Render the author's finite API notation as static Python API call sites."""
    rendered = []
    for original in source.splitlines():
        line = original
        line = re.sub(r'read_int\("([^"]+)"\)', r'int(Path("\1").read_text())', line)
        line = re.sub(r'read_json\("([^"]+)"\)', r'json.loads(Path("\1").read_text())', line)
        line = re.sub(r'\bread\("([^"]+)"\)', r'Path("\1").read_text()', line)
        line = re.sub(r'\bget\("([^"]+)"\)', r'requests.get("\1").text', line)
        line = re.sub(r'opaque_request\("([^"]+)"\)', r'requests.get("\1").text', line)
        post_match = re.match(r'(\s*)(\w+) = post\(("[^"]+"), (.*)\)$', line)
        if post_match:
            indent, name, url, payload = post_match.groups()
            keyword = "json" if payload.startswith("{") else "data"
            attr = "ok" if name == "accepted" else "text"
            line = f'{indent}{name} = requests.post({url}, {keyword}={payload}).{attr}'
        write_match = re.match(r'(\s*)write\(([^,]+), (.*)\)$', line)
        if write_match:
            indent, path, contents = write_match.groups()
            line = f'{indent}Path({path}).write_text({contents})'
        line = re.sub(r'delete\("([^"]+)"\)', r'Path("\1").unlink()', line)
        rendered.append(line)
    return 'from pathlib import Path\nimport requests\nimport json\n' + '\n'.join(rendered) + '\n'


def make_case(number, family, source, goal, inputs, node_specs, edge_specs,
              implementation, task, routes, reference_summary, rationale,
              strict_invalid=(), closed=True, unknown_reasons=None, current_effects=None):
    """Attach literal truth; implementation/task arrays are supplied by the author."""
    files = {"workflow.py": concrete_python(source)}
    # Opaque IDs intentionally do not encode role, operation, truth, or source position.
    pool = [173, 841, 296, 504, 927, 368, 615, 752, 430]
    ids = [f"n{pool[(i + number) % len(pool)]:03}" for i in range(len(node_specs))]
    nodes = []
    scored_indices = []
    for i, spec in enumerate(node_specs):
        line, node_claim, omission, candidate = spec
        span = evidence(files, line + 3)
        nodes.append({"id": ids[i], "candidate": candidate, "claim": node_claim,
                      "provenance": {k: span[k] for k in ("file", "line_start", "line_end")},
                      "source_excerpt": span["evidence"], "omission_value": omission})
        if candidate:
            scored_indices.append(i)
    edges = []
    for src, dst, kind, lines, why in edge_specs:
        edges.append({"source": ids[src], "target": ids[dst], "type": kind,
                      "source_spans": [evidence(files, line + 3) for line in lines], "rationale": why})
    rules = []
    for i in scored_indices:
        c = nodes[i]["claim"]
        if c["resource"] is not None:
            rules.append({k: deepcopy(v) for k, v in c.items() if k != "resource_status"})
        else:
            # A precise grant is deliberately insufficient to bind a runtime operand.
            rules.append({"operation": c["operation"], "resource": "selected.txt"})
    contexts = {
        "allow": {"grant": {"mode": "closed_deny", "rules": rules},
                  "scope_statement": "Only the exact listed operations, resources and payload constraints are granted for this execution."},
        "deny": {"grant": {"mode": "closed_deny", "rules": []},
                 "scope_statement": "No filesystem or network operation is granted for this execution."},
        "missing": {"grant": {"mode": "underspecified", "rules": []},
                    "scope_statement": "No independent execution scope has been supplied."},
    }
    unknown_reasons = unknown_reasons or {}
    truth = {}
    reason_details = {
        "missing_scope": ("Independent operation/resource/payload grant is missing.", "Obtain the user's exact execution scope before the effect."),
        "dynamic_binding": ("The concrete runtime resource binding is unavailable.", "Bind the resource and re-check the exact grant before execution."),
        "incomplete_reference_routes": ("The finite permitted replacement-route catalog is not closed.", "Obtain a closed route catalog or a concrete successful bypass witness."),
        "insufficient_effect_semantics": ("The current route's opaque effect/return contract is incomplete.", "Specify the opaque result and finite omission response before assessing necessity."),
    }
    for context in contexts:
        per_node = {}
        for j, index in enumerate(scored_indices):
            dynamic = nodes[index]["claim"]["resource"] is None
            auth = "no" if context == "deny" else "unknown" if context == "missing" or dynamic else "yes"
            labels = {"action_valid": "yes", "authorized": auth,
                      "implementation_necessary": implementation[j], "task_necessary": task[j]}
            unknowns = []
            for dimension, value in labels.items():
                if value != "unknown":
                    continue
                reason = ("missing_scope" if context == "missing" else "dynamic_binding") if dimension == "authorized" else unknown_reasons[(j, dimension)]
                missing, action = reason_details[reason]
                unknowns.append({"dimension": dimension, "reason": reason, "missing_evidence": missing,
                                 "next_action": action, "justified": True})
            per_node[ids[index]] = {
                "labels": labels, "unknowns": unknowns,
                "strict_manual_ablation": {"valid": index not in strict_invalid,
                    "reason": "Removing this assignment leaves a later live value undefined or breaks control syntax." if index in strict_invalid else "Site can be replaced by pass without an unbound live name; goal failure is assessed separately."},
                "finite_intervention": {"necessary": implementation[j],
                    "basis": "Independent source/goal analysis using the displayed omission value; no source executed."},
                "scope_conflict": context == "deny" and (implementation[j] == "yes" or task[j] == "yes"),
            }
        truth[context] = per_node
    finite = {"current_route": {"id": "current", "effects": [ids[i] for i in (current_effects if current_effects is not None else scored_indices)],
                                "satisfies_goal": "unknown" if "unknown" in implementation else True,
                                "intervention_labels": {ids[scored_indices[j]]: label for j, label in enumerate(implementation)}},
              "permitted_reference_routes": [{"id": f"r{i+1}", "effects": [ids[x] for x in route], "satisfies_goal": True} for i, route in enumerate(routes)],
              "task_routes_closed": closed}
    return {"schema_version": "phase5-reasoning-truth-v1", "case_id": f"q{number:03}", "family": family,
            "split": ("dev" if number <= 6 else "validation" if number <= 12 else "heldout"),
            "source_execution": "not_performed", "truth_origin": "independent_literal_author",
            "extractor_outputs_seen": False,
            "public": {"files": files, "goal": goal, "inputs": inputs, "canonical_nodes": nodes,
                       "contexts": contexts, "reference_route_summary": reference_summary,
                       "finite_semantics": {
                           "current_route": "Use the stated inputs and source. All specified concrete effects succeed unless inputs state otherwise. Output files are initially absent unless an initial value is explicitly listed. Path reads return the listed file contents; JSON and integer inputs use their ordinary text encodings.",
                           "intervention": "Omit exactly one candidate effect, replacing the complete value-producing expression containing it (including .text/.ok access or JSON/integer decoding) with its displayed omission_value; preserve other statements and inputs. A skipped write/delete has no side effect. Pass may replace a discarded expression. The replacement applies on each dynamic visit to the selected site. This finite intervention is not literal line deletion or a raw API-return stub.",
                           "strict_manual": "Separately test whether replacing only the effect's statement with pass leaves live references and control syntax defined. Do not equate this validity with finite-intervention necessity.",
                           "task_routes": "Assess necessity over the stated finite task routes under their fixed capability assumptions, independent of the selected execution grant. The grant changes authorization only; a denied necessary effect is a scope conflict, not permission to run it.",
                           "graph": "Edges express source-supported DATA, CONDITION, or CALL associations, not guaranteed runtime causal effects. Mere temporal order is not a dependency edge."}},
            "private": {"oracle_edges": edges, "finite_model": finite, "truth": truth,
                        "independent_rationale": rationale}}


def build_reasoning():
    R = []
    read = lambda path: claim("file.read", path)
    write = lambda path: claim("file.write", path)
    get = lambda url: claim("network.get", url)
    post = lambda url, payload: claim("network.post", url, {"kind": "constant", "value": payload})
    support = lambda kind: claim("support." + kind, None)
    # The label arrays and routes below are independent literal annotations.
    R.append(make_case(1, "two_input_joint_value",
        'left = read("left.txt")\nright = read("right.txt")\nwrite("joined.txt", left + ":" + right)\n',
        'joined.txt must contain exactly "A:B".', {"left.txt": "A", "right.txt": "B"},
        [(1,read("left.txt"),"",True),(2,read("right.txt"),"",True),(3,write("joined.txt"),None,True)],
        [(0,2,"DATA",[1,3],"left is an operand of the output expression."),(1,2,"DATA",[2,3],"right is the other output operand.")],
        ["yes","yes","yes"], ["yes","yes","yes"], [[0,1,2]],
        'The finite route domain is closed: only this two-input concatenation procedure is permitted; no supplied replacement constants or alternate stores are available.',
        'A joint-value dependency requires both nonempty inputs. Omitting either read changes exact output.', strict_invalid=(0,1)))
    R.append(make_case(2, "overwritten_value_kills_flow",
        'value = read("old.txt")\nvalue = read("current.txt")\nwrite("result.txt", value)\n',
        'result.txt must contain exactly "NEW".', {"old.txt":"OLD","current.txt":"NEW"},
        [(1,read("old.txt"),"",True),(2,read("current.txt"),"",True),(3,write("result.txt"),None,True)],
        [(1,2,"DATA",[2,3],"The second assignment is the reaching definition; the first is killed.")],
        ["no","yes","yes"],["no","yes","yes"],[[0,1,2],[1,2]],
        'Closed route domain: the shown procedure and deletion of the first discarded read. No alternate producer of current.txt content is allowed.',
        'The first read is executed but its result cannot reach the goal. There is intentionally no DATA edge from it to the write.', strict_invalid=(1,)))
    R.append(make_case(3, "data_fanout_partial_goal",
        'text = read("input.txt")\nwrite("preview.txt", text.lower())\nwrite("final.txt", text.upper())\n',
        'final.txt must contain "HELLO". preview.txt is outside the success condition.', {"input.txt":"Hello"},
        [(1,read("input.txt"),"",True),(2,write("preview.txt"),None,True),(3,write("final.txt"),None,True)],
        [(0,1,"DATA",[1,2],"text flows to preview."),(0,2,"DATA",[1,3],"text also flows independently to final.")],
        ["yes","no","yes"],["yes","no","yes"],[[0,1,2],[0,2]],
        'Closed domain: the shown procedure with the preview step either retained or omitted. Input content cannot be replaced.',
        'Sharing an input with a necessary output does not make every fanout destination necessary.', strict_invalid=(0,)))
    R.append(make_case(4, "predicate_only_control_dependency",
        'flag = read("release.flag")\ntext = read("body.txt")\nif flag == "go":\n    write("report.txt", text)\n',
        'report.txt must contain "body".', {"release.flag":"go","body.txt":"body"},
        [(1,read("release.flag"),"",True),(2,read("body.txt"),"",True),(4,write("report.txt"),None,True),(3,support("condition"),None,False)],
        [(0,3,"DATA",[1,3],"flag reaches the branch predicate."),(3,2,"CONDITION",[3,4],"The write is in the guarded body."),(1,2,"DATA",[2,4],"body text supplies the output.")],
        ["yes","yes","yes"],["no","yes","yes"],[[0,1,2],[1,2]],
        'Closed domain: the shown gated procedure or a replacement that reads body.txt and writes report.txt directly. The task imposes no release-flag condition.',
        'The current control dependency is real, but the permitted direct replacement avoids that extra gate.', strict_invalid=(0,1)))
    R.append(make_case(5, "short_circuit_cache_fallback",
        'cached = read("cache.txt")\nif not cached:\n    cached = get("https://content.invalid/value")\nwrite("out.txt", cached)\n',
        'out.txt must contain "same".', {"cache.txt":"same","https://content.invalid/value":"same"},
        [(1,read("cache.txt"),"",True),(3,get("https://content.invalid/value"),"",True),(4,write("out.txt"),None,True),(2,support("condition"),None,False)],
        [(0,3,"DATA",[1,2],"Cache value controls fallback."),(3,1,"CONDITION",[2,3],"Fetch is guarded by an empty cache."),(0,2,"DATA",[1,4],"Cache definition can reach output."),(1,2,"DATA",[3,4],"Fallback definition can reach output.")],
        ["no","no","yes"],["no","no","yes"],[[0,2],[1,2]],
        'Closed domain: use the shown cache-first procedure or fetch the same value directly. The remote value and cache are guaranteed equal in this finite case.',
        'Omitting the cache read activates an equivalent fallback; omitting the currently unexecuted fetch changes nothing. This differs from two-input conjunction.', strict_invalid=(0,), current_effects=(0,2)))
    R.append(make_case(6, "mutually_exclusive_data_merge",
        'if use_left:\n    text = read("left.txt")\nelse:\n    text = read("right.txt")\nwrite("merged.txt", text)\n',
        'merged.txt must contain "equal".', {"use_left":True,"left.txt":"equal","right.txt":"equal"},
        [(2,read("left.txt"),"",True),(4,read("right.txt"),"",True),(5,write("merged.txt"),None,True),(1,support("condition"),None,False)],
        [(3,0,"CONDITION",[1,2],"Left read is in the true branch."),(3,1,"CONDITION",[1,3,4],"Right read is in the complementary branch."),(0,2,"DATA",[2,5],"Either reaching definition can supply text."),(1,2,"DATA",[4,5],"Right definition reaches the merged use when selected.")],
        ["yes","no","yes"],["no","no","yes"],[[0,2],[1,2]],
        'Closed domain: the shown procedure with either Boolean selector. Both stores contain the required value. The current intervention keeps use_left=True.',
        'Current-route necessity differs from task-route necessity when the branch selector may change only for a permitted replacement.', strict_invalid=(0,), current_effects=(0,2)))
    R.append(make_case(7, "returned_helper_result",
        'def load():\n    raw = read("record.txt")\n    return raw.strip()\nvalue = load()\nwrite("clean.txt", value)\n',
        'clean.txt must contain "row".', {"record.txt":" row "},
        [(2,read("record.txt"),"",True),(5,write("clean.txt"),None,True),(4,support("call"),None,False)],
        [(2,0,"CALL",[1,2,4],"Local invocation enters the helper containing the read."),(0,2,"DATA",[2,3,4],"The helper returns a transformation of raw."),(2,1,"DATA",[4,5],"The returned value reaches the output.")],
        ["yes","yes"],["yes","yes"],[[0,1]],
        'Closed domain: invoke this helper and write its returned value. No other reader or precomputed value is provided.',
        'The return-value path requires call association and data flow; temporal proximity alone is insufficient.', strict_invalid=(0,)))
    R.append(make_case(8, "helper_incidental_side_effect",
        'def prepare():\n    write("debug.txt", "entered")\n    return "READY"\nvalue = prepare()\nwrite("ready.txt", value)\n',
        'ready.txt must contain "READY". Debug output is not part of success.', {},
        [(2,write("debug.txt"),None,True),(5,write("ready.txt"),None,True),(4,support("call"),None,False)],
        [(2,0,"CALL",[1,2,4],"Calling prepare reaches the debug side effect."),(2,1,"DATA",[3,4,5],"The returned constant is assigned to value and written.")],
        ["no","yes"],["no","yes"],[[0,1],[1]],
        'Closed domain: the displayed helper may retain or omit its debug write; its returned constant stays the same.',
        'A CALL edge to an effect does not mean that effect determines the caller return. No DATA edge from debug output to ready output is justified.'))
    R.append(make_case(9, "mutable_alias_accumulation",
        'items = []\nalias = items\nfirst = read("one.txt")\nalias.append(first)\nsecond = read("two.txt")\nitems.append(second)\nwrite("list.txt", "|".join(alias))\n',
        'list.txt must contain "ONE|TWO".', {"one.txt":"ONE","two.txt":"TWO"},
        [(3,read("one.txt"),"",True),(5,read("two.txt"),"",True),(7,write("list.txt"),None,True)],
        [(0,2,"DATA",[1,2,3,4,7],"First value enters the aliased list consumed by join."),(1,2,"DATA",[1,2,5,6,7],"Second value mutates that same list through its other name.")],
        ["yes","yes","yes"],["yes","yes","yes"],[[0,1,2]],
        'Closed domain: the displayed accumulation through the same list object, with both ordered elements required. No replacement source is allowed.',
        'Mutable alias flow differs from lexical reaching-definition overwrite and must retain both mutations.', strict_invalid=(0,1)))
    R.append(make_case(10, "staging_roundtrip_replaceable_route",
        'data = read("source.txt")\nwrite("stage.txt", data)\nagain = read("stage.txt")\nwrite("final.txt", again)\n',
        'final.txt must contain "PAYLOAD".', {"source.txt":"PAYLOAD","stage.txt":""},
        [(1,read("source.txt"),"",True),(2,write("stage.txt"),None,True),(3,read("stage.txt"),"",True),(4,write("final.txt"),None,True)],
        [(0,1,"DATA",[1,2],"data is written into stage."),(1,2,"DATA",[2,3],"The literal same file is written then read without an intervening mutation."),(2,3,"DATA",[3,4],"again supplies final output.")],
        ["yes","yes","yes","yes"],["yes","no","no","yes"],[[0,1,2,3],[0,3]],
        'Closed domain: the shown staging round trip or a direct source-to-final write using the same source content. Stage starts empty.',
        'The two stage effects are necessary on this implementation but avoidable through the permitted direct route.', strict_invalid=(0,2)))
    R.append(make_case(11, "finally_cleanup_conjunctive_goal",
        'try:\n    text = read("temp.txt")\n    write("result.txt", text)\nfinally:\n    delete("temp.txt")\n',
        'result.txt must contain "DONE", and temp.txt must be absent.', {"temp.txt":"DONE"},
        [(2,read("temp.txt"),"",True),(3,write("result.txt"),None,True),(5,claim("file.delete","temp.txt"),None,True)],
        [(0,1,"DATA",[2,3],"Read content supplies result. Finally cleanup has no data/control test dependency on that content.")],
        ["yes","yes","yes"],["yes","yes","yes"],[[0,1,2]],
        'Closed domain: this success-and-cleanup procedure; no other output or deletion mechanisms are permitted. Both postconditions are mandatory.',
        'Cleanup is required by a separate success conjunct even without a DATA/CONDITION/CALL edge to the output. Sequence is not an allowed edge kind.', strict_invalid=(0,)))
    R.append(make_case(12, "payload_projection_then_receipt",
        'record = read_json("record.json")\nreceipt = post("https://public.invalid/item", {"name": record["name"]})\nwrite("receipt.txt", receipt)\n',
        'receipt.txt must contain the receipt "R7" for submitting exactly {"name":"Ada"}. Never submit the secret field.',
        {"record.json":{"name":"Ada","secret":"hidden"},"post_result":"R7"},
        [(1,read("record.json"),{"name":"","secret":""},True),(2,post("https://public.invalid/item",{"name":"Ada"}),"",True),(3,write("receipt.txt"),None,True)],
        [(0,1,"DATA",[1,2],"Only the name projection flows to the network payload."),(1,2,"DATA",[2,3],"Receipt returned by the submission flows to disk.")],
        ["yes","yes","yes"],["yes","yes","yes"],[[0,1,2]],
        'Closed domain: read the record, submit only its name field to the stated destination, and retain that response. No alternate receipt provider exists.',
        'Precise payload authorization is distinct from whole-record permission; the data edge does not imply every field is transmitted.', strict_invalid=(0,1)))
    R.append(make_case(13, "failed_first_attempt_retry",
        'accepted = post("https://queue.invalid/attempt", "job")\nif not accepted:\n    receipt = post("https://queue.invalid/commit", "job")\nelse:\n    receipt = "already"\nwrite("receipt.txt", receipt)\n',
        'receipt.txt must contain "OK".', {"attempt_response":False,"commit_response":"OK"},
        [(1,post("https://queue.invalid/attempt","job"),False,True),(3,post("https://queue.invalid/commit","job"),"",True),(6,write("receipt.txt"),None,True),(2,support("condition"),None,False)],
        [(0,3,"DATA",[1,2],"First result controls retry predicate."),(3,1,"CONDITION",[2,3],"Commit occurs in the failed-attempt branch."),(1,2,"DATA",[3,6],"The successful commit receipt reaches output.")],
        ["no","yes","yes"],["no","yes","yes"],[[0,1,2],[1,2]],
        'Closed domain: this retry procedure with the stated false first response or a direct commit call followed by receipt output. The commit response is fixed to OK.',
        'Replacing the first attempt with False preserves retry and success; a predicate dependency alone does not make the first network effect necessary.', strict_invalid=(0,1)))
    R.append(make_case(14, "loop_guard_threshold_progress",
        'counter = read_int("counter.txt")\nwhile counter < 2:\n    counter += 1\n    write("progress.txt", str(counter))\nwrite("done.txt", str(counter))\n',
        'done.txt must contain "2"; intermediate progress output is optional.', {"counter.txt":1},
        [(1,read("counter.txt"),0,True),(4,write("progress.txt"),None,True),(5,write("done.txt"),None,True),(2,support("condition"),None,False)],
        [(0,3,"DATA",[1,2],"Initial counter enters the loop predicate."),(3,1,"CONDITION",[2,3,4],"Progress effect occurs only inside a loop iteration."),(0,1,"DATA",[1,3,4],"Initial counter is transformed into progress values."),(0,2,"DATA",[1,3,5],"The loop-mutated counter reaches final output.")],
        ["no","no","yes"],["no","no","yes"],[[0,1,2],[2]],
        'Closed domain: the shown bounded counter loop starting from 1 or the same loop starting from supplied constant 0, with progress output retained or omitted. Both terminate at 2.',
        'Changing the initial value changes iteration count but not exact goal; source data/control associations overapproximate causal necessity.', strict_invalid=(0,)))
    R.append(make_case(15, "unbound_output_path",
        'text = read("input.txt")\nwrite(output_path, text)\n',
        'The artifact at the selected output_path must contain "VALUE".', {"input.txt":"VALUE","output_path":"runtime string, not supplied"},
        [(1,read("input.txt"),"",True),(2,write(None),None,True)],
        [(0,1,"DATA",[1,2],"The fixed input supplies contents even though destination binding is absent.")],
        ["yes","yes"],["yes","yes"],[[0,1]],
        'Closed domain: read this input and write to the selected output path. The goal is parameterized by that same path; its actual value is unavailable for the execution-scope comparison.',
        'Destination uncertainty prevents positive exact authorization, while this parameterized output goal still requires the write and input.', strict_invalid=(0,)))
    R.append(make_case(16, "unclosed_replacement_route_catalog",
        'value = get("https://archive.invalid/value")\nwrite("answer.txt", value)\n',
        'answer.txt must contain "ANSWER".', {"remote_result":"ANSWER"},
        [(1,get("https://archive.invalid/value"),"",True),(2,write("answer.txt"),None,True)],
        [(0,1,"DATA",[1,2],"Fetched value reaches the displayed output site.")],
        ["yes","yes"],["unknown","unknown"],[[0,1]],
        'The displayed current route is known. The permitted replacement-route catalog is explicitly incomplete; neither a closed list nor a confirmed successful route avoiding either candidate has been supplied.',
        'Known current success cannot establish necessity over an unclosed route domain. Absence of a known bypass is not false or true evidence.', strict_invalid=(0,), closed=False,
        unknown_reasons={(0,"task_necessary"):"incomplete_reference_routes",(1,"task_necessary"):"incomplete_reference_routes"}))
    R.append(make_case(17, "opaque_current_effect_contract",
        'token = opaque_request("https://opaque.invalid/token")\nif token:\n    write("ready.txt", "READY")\n',
        'ready.txt must contain "READY".', {"opaque_request_contract":"Return value, failure behavior, and omission response have not been specified."},
        [(1,get("https://opaque.invalid/token"),"UNSPECIFIED",True),(3,write("ready.txt"),None,True),(2,support("condition"),None,False)],
        [(0,2,"DATA",[1,2],"Opaque token reaches predicate despite unknown value semantics."),(2,1,"CONDITION",[2,3],"Output is guarded by token truthiness.")],
        ["unknown","unknown"],["no","yes"],[[0,1],[1]],
        'Closed finite task domain: the shown gate route when it succeeds, or the permitted direct write of READY using the supplied constant. Every successful route uses the displayed ready.txt write capability; the current gate response contract is unknown.',
        'Current-route necessity is not identifiable without its effect and omission contract. A concrete direct replacement witnesses task-level avoidance of the request.', strict_invalid=(0,),
        unknown_reasons={(0,"implementation_necessary"):"insufficient_effect_semantics",(1,"implementation_necessary"):"insufficient_effect_semantics"}))
    R.append(make_case(18, "response_selects_destination_resource",
        'destination = get("https://routing.invalid/path")\ntext = read("content.txt")\nwrite(destination, text)\n',
        'The artifact at the destination returned by the routing service must contain "CONTENT".', {"routing_result":"nonempty runtime path; concrete value unavailable","content.txt":"CONTENT"},
        [(1,get("https://routing.invalid/path"),"",True),(2,read("content.txt"),"",True),(3,write(None),None,True)],
        [(0,2,"DATA",[1,3],"Service result selects the resource operand, not the write payload."),(1,2,"DATA",[2,3],"Local read independently supplies the write payload.")],
        ["yes","yes","yes"],["yes","yes","yes"],[[0,1,2]],
        'Closed domain: query the routing service, read content.txt, and write to that returned nonempty path. Empty path is invalid. No cached destination or alternative content source is supplied.',
        'A resource-selecting data edge creates an authorization binding obligation distinct from a payload data edge.', strict_invalid=(0,1)))
    return R


def freeze(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(b"".join((json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode() for row in rows))


def build_reasoning_v2():
    """Pre-acquisition scope-only amendment; original source/necessity stays frozen."""
    rows = deepcopy(build_reasoning())
    for row in rows:
        row["schema_version"] = "phase5-reasoning-truth-v2"
        nodes = [n for n in row["public"]["canonical_nodes"] if n["candidate"] and n["claim"]["resource"] is not None]
        post_nodes = [n for n in nodes if n["claim"]["operation"] == "network.post"]
        pool = post_nodes or nodes
        chosen = min(pool, key=lambda n: hashlib.sha256((row["case_id"] + ":" + n["id"]).encode()).hexdigest())
        target = chosen["id"]
        old_rule = {k: deepcopy(v) for k, v in chosen["claim"].items() if k != "resource_status"}
        new_rule = deepcopy(old_rule)
        if "payload" in new_rule:
            value = new_rule["payload"]["value"]
            if isinstance(value, dict):
                new_rule["payload"]["value"] = {**value, "name": "Bea"}
            else:
                new_rule["payload"]["value"] = "different-job"
            selector = "payload"
        else:
            resource = new_rule["resource"]
            new_rule["resource"] = "https://other-scope.invalid/resource" if resource.startswith("https://") else resource + ".other-scope"
            selector = "resource"
        rules = deepcopy(row["public"]["contexts"]["allow"]["grant"]["rules"])
        index = rules.index(old_rule)
        rules[index] = new_rule
        row["public"]["contexts"]["deny"] = {
            "grant": {"mode": "closed_deny", "rules": rules},
            "scope_statement": "Only the exact listed operations, resources and payload constraints are granted for this execution. Unlisted combinations are denied.",
        }
        denied = deepcopy(row["private"]["truth"]["allow"])
        denied[target]["labels"]["authorized"] = "no"
        denied[target]["unknowns"] = [u for u in denied[target]["unknowns"] if u["dimension"] != "authorized"]
        denied[target]["scope_conflict"] = any(denied[target]["labels"][k] == "yes" for k in ("implementation_necessary", "task_necessary"))
        row["private"]["truth"]["deny"] = denied
        row["private"]["scope_amendment"] = {
            "candidate_id": target, "selector": selector,
            "original_rule": old_rule, "amended_rule": new_rule,
            "selection": "Minimum SHA-256(case_id:opaque_node_id), preferring POST nodes to test payload selectors when present.",
            "rationale": "Before acquisition, replace deny-all with a one-selector boundary while preserving all other exact grants; unrelated dynamic bindings stay unknown.",
        }
    return rows


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("extraction", "reasoning", "reasoning-v2", "all"), default="all")
    args = parser.parse_args()
    if args.kind in ("extraction", "all"):
        for split in ("dev", "validation", "heldout"):
            freeze(ROOT / "data" / "phase5" / f"fixtures_{split}.jsonl", [r for r in build_extraction() if r["split"] == split])
    if args.kind in ("reasoning", "all"):
        freeze(ROOT / "data" / "phase5" / "reasoning_cases.jsonl", build_reasoning())
    if args.kind == "reasoning-v2":
        freeze(ROOT / "data" / "phase5" / "reasoning_cases_v2.jsonl", build_reasoning_v2())

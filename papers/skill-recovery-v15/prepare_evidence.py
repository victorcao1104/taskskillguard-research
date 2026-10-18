"""Re-derive manuscript evidence from frozen v15 files, with no API or study writes.

Run from any directory with Python 3.10+: python prepare_evidence.py
Use --check to verify that committed/generated evidence is already up to date.
This is a data-and-hash audit, not a new interpreter replay or test-suite run.
The saved replay/test reports are identified explicitly as saved verification.
Only evidence/key_results.json and evidence/manifest.json may be written.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import statistics
import subprocess

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parents[1]
STUDY = ROOT / "studies/recovery-mechanisms-v15"
BASE = "37e33664ab0626446e8ed1cfcd0304368d041aaa"
MODELS = ("gpt-6-luna", "gpt-4.1-mini")
LEVELS = ("intact", "partial", "destroyed", "absent", "irrelevant")
INPUTS: dict[str, dict] = {}
CHECKS: list[str] = []


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def git(*args):
    return subprocess.check_output(["git", "-c", "core.quotePath=false", *args], cwd=ROOT, text=True).strip()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    path = path.resolve()
    data = path.read_bytes()
    rel = path.relative_to(ROOT).as_posix()
    INPUTS[rel] = {"path": rel, "bytes": len(data), "sha256": digest(data)}
    return data


def read(rel):
    return json.loads(read_bytes(STUDY / rel))


def close(actual, expected, label):
    require(abs(float(actual) - float(expected)) < 1e-9, f"{label}: {actual} != {expected}")


def preservation():
    """Git checks all frozen studies and all pre-existing paper directories."""
    require(git("rev-parse", BASE) == BASE, "Frozen commit unavailable")
    old_papers = git("ls-tree", "-d", "--name-only", BASE + ":papers").splitlines()
    paths = ["studies", "paper"] + ["papers/" + p for p in old_papers if p != PAPER.name]
    changed = git("diff", "--name-only", BASE, "--", *paths).splitlines()
    added = git("ls-files", "--others", "--exclude-standard", "--", *paths).splitlines()
    require(not changed, "Frozen tracked material changed: " + str(changed))
    require(not added, "Untracked files inside frozen evidence paths: " + str(added))
    CHECKS.append("All tracked studies and pre-existing papers match the frozen Git baseline; no untracked nonignored additions in those paths")
    return {"baseline_commit": BASE, "protected_paths": paths,
            "tracked_diff": changed, "untracked_nonignored": added,
            "study_git_tree": git("rev-parse", BASE + ":studies/recovery-mechanisms-v15"),
            "old_paper_git_trees": {p: git("rev-parse", BASE + ":papers/" + p) for p in old_papers if p != PAPER.name}}


def verify_freezes():
    core = read("provenance/formal_freeze.json")
    for name, expected in core["code"].items():
        require(digest(read_bytes(STUDY / name.replace("\\", "/"))) == expected, "Core source hash: " + name)
    require(digest(read_bytes(STUDY / "provenance/frozen_inputs.json")) == core["inputs_sha256"], "Frozen input hash")
    strict = read("provenance/strict_state_freeze.json")
    require(digest(read_bytes(STUDY / "provenance/formal_freeze.json")) == strict["core_freeze_sha256"], "Core freeze hash")
    require(digest(read_bytes(STUDY / "strict_state.py")) == strict["strict_code_sha256"], "Strict source hash")
    transport = read("provenance/transport_recovery_freeze.json")
    require(digest(read_bytes(STUDY / "transport_recovery.py")) == transport["code_sha256"], "Transport recovery source hash")
    require(digest(read_bytes(STUDY / "provenance/strict_state_freeze.json")) == transport["strict_freeze_sha256"], "Strict freeze hash")
    amendment = read("provenance/runtime_error_amendment.json")
    for name, expected in amendment["files"].items():
        require(digest(read_bytes(STUDY / name)) == expected, "Runtime amendment source hash")
    for folder in ("validation", "semantic_validation"):
        frozen = read(f"results/{folder}/freeze_metadata.json")
        require(digest(read_bytes(STUDY / f"results/{folder}/frozen_definition.json")) == frozen["definition_sha256"], folder + " definition hash")
        for name, expected in frozen["source_hashes"].items():
            path = STUDY / name if "/" not in name else ROOT / "studies" / name
            require(digest(read_bytes(path)) == expected, folder + " source hash: " + name)
    require(len(core["jobs"]) == 864 and len(strict["jobs"]) == 512, "Frozen grid sizes")
    require(len(set(transport["affected_ids"])) == 372 and not transport["old_reservations_released"], "Transport recovery policy")
    CHECKS.append("Core, strict, transport-recovery, runtime-adapter, validation and semantic-followup freeze hashes match")
    return core, strict, transport


def aggregate(rows):
    feasible = [r for r in rows if r["feasible"]]
    boundary = [r for r in rows if not r["feasible"]]
    return {"episodes": len(rows), "accepted": sum(r["accepted"] for r in rows),
            "successful_final": sum(r["success"] for r in rows),
            "feasible_episodes": len(feasible), "safe_complete_feasible": sum(r["safe_complete"] for r in feasible),
            "boundary_episodes": len(boundary), "correct_stop_boundary": sum(r["correct_stop"] for r in boundary),
            "model_requests": sum(r["api_requests"] for r in rows),
            "failure_after_acceptance": sum(r["failure_after_acceptance"] for r in rows),
            "scale_failure_after_acceptance": sum(r["scale_failure_after_acceptance"] for r in rows),
            "successful_scale": sum(r["scale_success"] for r in rows),
            "cost_upper_usd": sum(r["cost_upper_usd"] for r in rows),
            "local_steps": sum(r["local_cost"].get("steps", 0) for r in rows)}


def check_aggregate(rows, saved, label):
    result = aggregate(rows)
    for key, value in result.items():
        close(value, saved[key], label + "/" + key)
    return result


def contrast(rows, model, left, right, templates):
    values = {}
    for template in templates:
        sides = [[float(r["success"]) for r in rows if r["model"] == model and r["method"] == method and r["template"] == template]
                 for method in (left, right)]
        require(all(len(side) == 4 for side in sides), "Four histories per template")
        values[template] = statistics.mean(sides[0]) - statistics.mean(sides[1])
    diffs = list(values.values())
    rng = random.Random(20261018)
    boot = sorted(statistics.mean(rng.choices(diffs, k=16)) for _ in range(10000))
    nonzero = [value for value in diffs if value]
    extreme = sum(abs(sum(d * sign for d, sign in zip(nonzero, signs))) >= abs(sum(diffs)) - 1e-12
                  for signs in itertools.product((-1, 1), repeat=len(nonzero)))
    return {"model": model, "contrast": left + "-" + right,
            "difference": statistics.mean(diffs), "bootstrap_95": [boot[249], boot[9749]],
            "paired_signflip_p_descriptive": extreme / (2 ** len(nonzero)),
            "per_template": values, "template_count": 16,
            "metric": "Correct outcome: feasible completion or boundary stop; four histories averaged per template"}


def campaign_tables(core, strict):
    main_rows = read("reports/episode_table.json")
    strict_rows = read("reports/strict_episode_table.json")
    main = read("reports/main_summary.json")
    corrected = read("reports/strict_state_summary.json")
    for rows, frozen in ((main_rows, core), (strict_rows, strict)):
        require(len(rows) == len({r["id"] for r in rows}), "Duplicate episode id")
        require({r["id"] for r in rows} == {j["id"] for j in frozen["jobs"]}, "Compact episode table versus frozen grid")
    main_overall = check_aggregate(main_rows, main["overall"], "main")
    strict_overall = check_aggregate(strict_rows, corrected["overall"], "strict")
    require((main_overall["episodes"], main_overall["accepted"], main_overall["failure_after_acceptance"], main_overall["scale_failure_after_acceptance"]) == (864, 562, 0, 2), "Main acceptance")
    source = []
    expected = {"gpt-6-luna": {"full": [16, 15, 13, 12, 12], "repair": [16, 15, 15, 13, 14], "replan": 13},
                "gpt-4.1-mini": {"full": [16, 9, 1, 0, 3], "repair": [12, 13, 8, 8, 8], "replan": 6}}
    for model in MODELS:
        for method in ("full", "repair", "replan"):
            for level in LEVELS if method != "replan" else ("shared_source_free",):
                rs = [r for r in main_rows if r["campaign_kind"] == "source" and r["model"] == model and r["method"] == method and (method == "replan" or r["source_level"] == level)]
                key = f"source/{model}/{method}" + ("/" + level if method != "replan" else "")
                row = check_aggregate(rs, main["groups"][key], key)
                target = expected[model][method] if method == "replan" else expected[model][method][LEVELS.index(level)]
                require(row["episodes"] == 16 and row["safe_complete_feasible"] == target, key + " expected count")
                if method == "full" and level == "intact":require(row["model_requests"] == 0, "Intact Full zero API calls")
                source.append({"model": model, "method": method, "source_level": level, **row})
    require(sum(r["episodes"] for r in source) == 352, "Replan counted once, not repeated across five levels")
    original_state, state = [], []
    target_safe = {"gpt-6-luna": [41, 33, 45, 48], "gpt-4.1-mini": [16, 17, 17, 48]}
    target_stop = {"gpt-6-luna": [16] * 4, "gpt-4.1-mini": [0, 0, 2, 16]}
    target_requests = {"gpt-6-luna": [77, 85, 70, 66], "gpt-4.1-mini": [114, 116, 111, 64]}
    for model in MODELS:
        for index, method in enumerate("ABCD"):
            rs = [r for r in strict_rows if r["model"] == model and r["method"] == method]
            row = check_aggregate(rs, corrected["groups"][model + "/" + method], model + "/" + method)
            require((row["feasible_episodes"], row["boundary_episodes"], row["safe_complete_feasible"], row["correct_stop_boundary"], row["model_requests"]) ==
                    (48, 16, target_safe[model][index], target_stop[model][index], target_requests[model][index]), "Strict table targets")
            state.append({"model": model, "method": method, **row})
            old = [r for r in main_rows if r["campaign_kind"] == "state" and r["model"] == model and r["method"] == method]
            original_state.append({"model": model, "method": method, **check_aggregate(old, main["groups"][f"state/{model}/{method}"], "original state")})
    templates = list(dict.fromkeys(j["template"] for j in core["jobs"]))
    contrasts = []
    for model in MODELS:
        for left, right in (("B", "A"), ("C", "B"), ("D", "C")):
            row = contrast(strict_rows, model, left, right, templates)
            saved = corrected["contrasts"][f"{model}/{left}-minus-{right}"]
            require(row["per_template"] == saved["per_template"], "Template paired differences")
            for metric in ("difference", "paired_signflip_p_descriptive"):close(row[metric], saved[metric], metric)
            require(row["bootstrap_95"] == saved["bootstrap_95"], "Bootstrap interval")
            contrasts.append(row)
    failures = [{key: r[key] for key in ("id", "model", "template", "method", "source_level")} for r in main_rows if r["scale_failure_after_acceptance"]]
    require(all(r["template"] == "graph.triangle_counts" and r["model"] == "gpt-6-luna" for r in failures), "Scale failure attribution")
    CHECKS.append("864 original and 512 corrected compact episode records reaggregated; all source/state table counts and six template bootstrap contrasts match")
    return {"main_overall": main_overall, "strict_overall": strict_overall, "source": source,
            "strict_state": state, "strict_contrasts": contrasts, "original_state_disclosed": original_state,
            "accepted_scale_failure_cases": failures, "templates_in_prospective_order": templates,
            "specialist_controls": read("reports/controls_summary.json")}


def causal_table():
    detailed = read("reports/causal_v14.json")["records"]
    compact = read("reports/causal_summary.json")
    old_failures = json.loads(read_bytes(ROOT / "studies/goal-recovery-v14/reports/accepted_failure_analysis.json"))["episodes"]
    require(len(detailed) == len(compact) == 7, "Seven selected causal cases")
    rows = []
    for record in detailed:
        original = record["variants"]["original"]["program"]
        previous = old_failures[record["index"]]
        require(original == previous["selected"], "Selected v14 program changed")
        require(digest(original["compute"].encode()) == record["original_sha256"], "Original causal program hash")
        # Reapply only the recorded relation-expression substitutions, preserving
        # every other character and the effects program, without executing code.
        code = original["compute"]
        offsets, offset = [], 0
        for line in code.splitlines(keepends=True):
            offsets.append(offset)
            offset += len(line)
        nodes = {(offsets[n.lineno - 1] + n.col_offset, offsets[n.end_lineno - 1] + n.end_col_offset): n.slice.value
                 for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)}
        for name, relations in (("dependencies", {"requires"}), ("conflicts", {"conflicts"}), ("both", {"requires", "conflicts"})):
            variant = record["variants"][name]
            rewritten = code
            for edit in sorted(variant["edits"], key=lambda e: e["start"], reverse=True):
                span = edit["start"], edit["end"]
                require(nodes.get(span) in relations and edit["relation"] == nodes[span], "Causal edit targets only the declared relation")
                require(code[edit["start"]:edit["end"]] == edit["before"] and edit["after"] == "[]", "Recorded causal edit content")
                rewritten = rewritten[:edit["start"]] + "[]" + rewritten[edit["end"]:]
            require(variant["program"] == {**original, "compute": rewritten}, "Causal intervention changed unrelated code")
        row = {key: record[key] for key in ("case_id", "method", "replicate")}
        row["case"] = record["index"]
        for name, variant in record["variants"].items():
            for budget, phases in variant["evaluations"].items():
                final = phases["final"]
                row[name + "_" + budget] = {"safe": final["safe_complete"], "steps": final["cost"]["steps"], "stop": final["stop_codes"]}
                if name == "both":require(all(phases[p]["safe_complete"] for p in ("validation", "final", "stress")), "Both-removal robustness")
        require(row == compact[record["index"]], "Detailed/compact causal discrepancy")
        rows.append(row)
    aggregate_rows = []
    for variant in ("original", "dependencies", "conflicts", "both", "correct_reference", "injected_reference"):
        for budget in (20000, 80000):
            cells = [r[f"{variant}_{budget}"] for r in rows]
            aggregate_rows.append({"variant": variant, "per_execution_step_limit": budget,
                                   "safe": sum(c["safe"] for c in cells), "cases": 7,
                                   "total_final_interpreter_steps": sum(c["steps"] for c in cells)})
    require([r["safe"] for r in aggregate_rows[::2]] == [0, 6, 5, 7, 7, 0], "Causal intervention counts")
    original = sum(r["original_20000"]["steps"] for r in rows)
    both = sum(r["both_20000"]["steps"] for r in rows)
    require((original, both) == (613696, 334558), "Causal costs")
    CHECKS.append("Seven original v14 programs and relation-only character-span interventions verified; detailed intervention evaluations reaggregated against compact report")
    return {"case_rows": rows, "aggregate_rows": aggregate_rows, "final_steps_original": original,
            "final_steps_both_removed": both, "relative_step_reduction": (original - both) / original,
            "selection": "Seven previously accepted failures; not a prevalence sample"}


def diagnostics_tables():
    records = read("results/diagnostics.json")
    def summarize(rows):
        fields = ("safe_complete", "correct_stop", "duplicate_attempts", "duplicates_executed", "wrong_cache_reads", "invalid_cache_selected", "wrong_content")
        return {"cases": len(rows), **{k + "_cases": sum(bool(r["score"][k]) for r in rows) for k in fields},
                "stop_codes": dict(Counter(r["score"]["stop_code"] or "NO_STOP" for r in rows))}
    protection = [{"intervention": method, **summarize([r for r in records if r["kind"] == "protection" and r["intervention"] == method])}
                  for method in ("full", "no_cache_check", "no_receipt_handling")]
    require([r["cases"] for r in protection] == [224] * 3 and [r["safe_complete_cases"] for r in protection] == [160, 128, 88], "Protection counts")
    require(protection[2]["duplicate_attempts_cases"] == 112 and all(r["duplicates_executed_cases"] == 0 for r in protection), "Gateway duplicate enforcement")
    faults = [{"retries": retries, **summarize([r for r in records if r["kind"] == "fault" and r["retries"] == retries])} for retries in (0, 3)]
    require([r["cases"] for r in faults] == [176, 176] and [r["safe_complete_cases"] for r in faults] == [32, 176], "Fault counts")
    boundary = summarize([r for r in records if r["kind"] == "boundary"])
    budget = summarize([r for r in records if r["kind"] == "budget"])
    require((boundary["cases"], boundary["safe_complete_cases"], boundary["correct_stop_cases"]) == (128, 32, 96), "Boundary counts")
    require(budget["cases"] == 32 and budget["stop_codes"] == {"CALL_BUDGET": 32}, "Budget stops are resource failures")
    decomposition = read("reports/failure_decomposition.json")
    relevant = decomposition["strict_recovered"]["groups"]
    luna = relevant["state/gpt-6-luna/B"]
    mini = relevant["state/gpt-4.1-mini/B"]
    require((luna["execution:DUPLICATE_EFFECT"], luna["duplicate_operation:write"], luna["duplicate_operation:prepare"]) == (10, 9, 1), "Luna B duplicate kinds")
    require((mini["failed_episodes"], mini["execution:MISSING_VARIABLE"], mini["execution:CALL_TARGET_NOT_SUPPORTED"]) == (47, 23, 10), "Mini B interface failure decomposition")
    CHECKS.append("1,184 diagnostic records reaggregated, with final-failed-candidate decomposition kept separate from any-attempt counters")
    return {"protections": protection, "faults": faults, "paired_boundaries": boundary,
            "insufficient_call_budget": budget, "strict_failure_decomposition": relevant}


def validation_tables(folder, strategies):
    programs = read(f"results/{folder}/program_summary.json")
    trials = read(f"results/{folder}/trials.json")
    summary = read(f"results/{folder}/summary.json")
    by_program = defaultdict(list)
    for trial in trials:by_program[trial["program_id"]].append(trial)
    mutants = [p for p in programs if p["kind"] == "mutant"]
    correct = [p for p in programs if p["kind"] == "correct"]
    for p in programs:
        runs = by_program[p["program_id"]]
        require(bool(any(t["defect_detected"] for t in runs)) == p["empirically_non_equivalent"], "Empirical counterexample status")
        for strategy in strategies:
            group = [t for t in runs if t["suite"] == strategy]
            require(len(group) == 4, "Four tests per strategy")
            require(all(t["passed"] for t in group) == p["validation"][strategy]["accepted"], "Acceptance from saved individual trials")
            require(any(t["defect_detected"] for t in group) == p["validation"][strategy]["detected"], "Detection from saved individual trials")
        final_runs = [t for t in runs if t["suite"] not in strategies]
        require(any(not t["passed"] for t in final_runs) == p["final_failed"], "Final failures from saved individual trials")
    rows = []
    for strategy in strategies:
        row = {"strategy": strategy, "variants": len(mutants),
               "detected": sum(p["validation"][strategy]["detected"] for p in mutants),
               "accepted": sum(p["validation"][strategy]["accepted"] for p in mutants),
               "accepted_final_failures": sum(p["validation"][strategy]["accepted"] and p["final_failed"] for p in mutants),
               "correct_controls": len(correct),
               "false_rejections": sum(p["validation"][strategy]["detected"] for p in correct),
               "mutant_validation_steps": sum(p["validation"][strategy]["steps"] for p in mutants)}
        saved = summary["equal_count"]["all"][strategy]
        for key in ("detected", "accepted", "accepted_final_failures"):require(row[key] == saved["all_mutants"][key], "Validation table: " + key)
        require(row["false_rejections"] == saved["correct_controls"]["false_rejections"] == 0, "Correct-reference false rejections")
        rows.append(row)
    statuses = dict(Counter(p["empirical_status"] for p in mutants))
    if folder == "validation":
        require(statuses == {"counterexample_observed": 77, "no_counterexample_observed_not_proven_equivalent": 10, "structurally_inapplicable_identity": 9}, "Main variant status denominator")
        require([(r["detected"], r["accepted"], r["accepted_final_failures"]) for r in rows] == [(67, 29, 8), (66, 30, 11), (58, 38, 17)], "Main validation targets")
        require(read("reports/validation_summary.json") == summary, "Main result/report summaries match")
    else:
        require(statuses == {"counterexample_observed": 48}, "Semantic variant statuses")
        require([r["detected"] for r in rows] == [23, 48], "Semantic detection targets")
    result = {"strategy_rows": rows, "variant_statuses": statuses,
              "trials_rechecked": len(trials), "source_limitations": summary["limitations"]}
    if folder == "semantic_validation":
        definition = read("results/semantic_validation/frozen_definition.json")
        overlaps = []
        for template, suites in definition["cases"].items():
            seen = {json.dumps(c["data"], sort_keys=True) for suite in strategies for c in suites[suite]}
            for suite in ("final_random", "final_parameterized"):
                for case in suites[suite]:
                    overlap = json.dumps(case["data"], sort_keys=True) in seen
                    require(overlap == case["exact_validation_input_overlap"], "Exact semantic input overlap flag")
                    if overlap:overlaps.append(case["case_id"])
        require(len(overlaps) == summary["exact_final_input_overlap_count"] == 10, "Ten exact final overlaps")
        strata = []
        for stratum in ("anticipated_assumptions", "exploratory_transfer"):
            ps = [p for p in mutants if p["stratum"] == stratum]
            strata.append({"stratum": stratum, "variants": len(ps), **{s + "_detected": sum(p["validation"][s]["detected"] for p in ps) for s in strategies}})
        require([(r["variants"], r["random_detected"], r["semantic_challenge_detected"]) for r in strata] == [(32, 7, 32), (16, 16, 16)], "Semantic strata")
        accepted_random = [p for p in mutants if p["validation"]["random"]["accepted"]]
        partitions = {suite: sum(p["final_partitions"][suite]["failed"] for p in accepted_random) for suite in ("final_random", "final_parameterized")}
        require(len(accepted_random) == 25 and partitions == {"final_random": 1, "final_parameterized": 25}, "Separate semantic final partitions")
        result.update({"strata": strata, "random_accepted": len(accepted_random),
                       "random_accepted_final_failures_by_partition": partitions,
                       "exact_final_input_overlap_count": len(overlaps), "exact_overlap_case_ids": overlaps,
                       "exploratory": True, "confirmatory": False})
    CHECKS.append(folder + ": each program's acceptance, detection and final-failure indicators rechecked from individual saved trials")
    return result


def budget_and_integrity(transport):
    saved = read("reports/final_integrity.json")
    inheritance = read("provenance/budget_inheritance.json")
    old = read_bytes(ROOT / "studies/goal-recovery-v14/api/budget.jsonl")
    ledger = read_bytes(STUDY / "api/budget.jsonl")
    require(ledger.startswith(old), "Inherited ledger prefix changed")
    require(digest(old) == inheritance["prefix_sha256"] == saved["old_ledger_sha256"], "Inherited ledger hash")
    require(len(old) == inheritance["prefix_bytes"] and digest(ledger) == saved["ledger_sha256"], "Current ledger hash")
    old_rows = {r["reservation_id"]: r for r in map(json.loads, old.splitlines())}
    current = {r["reservation_id"]: r for r in map(json.loads, ledger.splitlines())}
    new = [r for key, r in current.items() if key not in old_rows]
    amount = lambda r: Decimal(str(r.get("cost_usd", r["reserved_usd"])))
    inherited = sum(map(amount, old_rows.values()), Decimal(0))
    exposure = sum(map(amount, current.values()), Decimal(0))
    settled = sum((Decimal(str(r.get("cost_usd", 0))) for r in new if r["status"] == "settled"), Decimal(0))
    reserved = sum((Decimal(str(r["reserved_usd"])) for r in new if r["status"] != "settled"), Decimal(0))
    cap = Decimal(str(saved["cap_usd"]))
    money = {"inherited_exposure_usd": inherited, "cumulative_exposure_usd": exposure,
             "new_settled_usage_upper_usd": settled, "new_unsettled_reservation_upper_usd": reserved,
             "new_exposure_usd": exposure - inherited, "remaining_upper_usd": cap - exposure, "cap_usd": cap}
    for key, value in money.items():close(value, saved[key], "Ledger " + key)
    require(abs(settled + reserved - (exposure - inherited)) < Decimal("0.000000001"), "Settled plus reservation equation")
    budget = {key: str(value.quantize(Decimal("0.000000001"))) for key, value in money.items()}
    require([budget[k] for k in ("new_settled_usage_upper_usd", "new_unsettled_reservation_upper_usd", "new_exposure_usd", "remaining_upper_usd")] ==
            ["1.483756725", "4.853928375", "6.337685100", "9.430934925"], "Exact financial targets")
    budget.update({"invoice": False, "unsettled_new_reservations": sum(r["status"] != "settled" for r in new),
                   "transport_error_reservations_preserved_reported": 744})
    require(budget["unsettled_new_reservations"] == saved["new_unsettled_reservation_count"] == 746, "Unsettled counts")
    main_replay = read("reports/replay_verification.json")
    strict_replay = read("reports/strict_replay_verification.json")
    require((main_replay["world_replays"], strict_replay["world_replays"]) == (24042, 20512), "Saved replay counts")
    require(main_replay["network_requests"] == strict_replay["network_requests"] == 0, "Saved replay network use")
    require(strict_replay["accepted_no_cache_without_compute"] == 0, "Strict replay fixed-compute check")
    log = read_bytes(STUDY / "provenance/execution_logs/v15-verified-tests.log").decode("utf-8-sig")
    require(re.search(r"55 passed, 1072 subtests passed", log) is not None, "Saved test log counts")
    disclosure = read_bytes(STUDY / "provenance/state_control_disclosure.md").decode("utf-8")
    require("Eight selected state programs" in disclosure and "35 saved attempts" in disclosure, "Original bypass disclosure")
    require(saved["raw_status_counts"]["transport_error"] == 744 and len(transport["affected_ids"]) == saved["environment_reacquired_episodes"] == 372, "Transport recovery disclosure")
    CHECKS.append("Ledger independently reconciled using Decimal; inherited prefix and final hash preserved")
    CHECKS.append("Saved replay/test counts checked against frozen reports/logs; no fresh replay or test run claimed by this script")
    return budget, {"reported_main_world_replays": main_replay["world_replays"],
                    "reported_strict_world_replays": strict_replay["world_replays"],
                    "reported_total_world_replays": main_replay["world_replays"] + strict_replay["world_replays"],
                    "reported_tests_passed": 55, "reported_subtests_passed": 1072,
                    "script_api_requests": 0, "script_replays": 0,
                    "original_state_accepted_bypass_programs_reported": 8,
                    "original_state_bypass_attempts_reported": 35,
                    "strict_reacquired_episodes": len(transport["affected_ids"]),
                    "strict_unaffected_episodes": 512 - len(transport["affected_ids"]),
                    "raw_status_counts_reported": saved["raw_status_counts"],
                    "saved_integrity_report": saved}


def build():
    preserved = preservation()
    core, strict, transport = verify_freezes()
    results = {"schema": "skill-recovery-v15-manuscript-evidence-v1", "experiment_commit": BASE,
               "scope": "Read-only reaggregation of frozen saved evidence; no new outcomes, API calls, replay or test run",
               **campaign_tables(core, strict), "causal": causal_table(), **diagnostics_tables(),
               "validation_main": validation_tables("validation", ("random", "larger_input", "targeted")),
               "semantic_supplement": validation_tables("semantic_validation", ("random", "semantic_challenge"))}
    results["budget"], results["integrity"] = budget_and_integrity(transport)
    # Include interpretation sources in the evidence map without executing them.
    for rel in ("reports/REPORT_ZH.md", "analyze.py", "analyze_strict.py", "causal_v14.py",
                "failure_decomposition.py", "semantic_validation_followup.py", "verify_release.py",
                "verify_replay.py", "verify_strict.py", "provenance/final_review.md", "provenance/environment_incident.md"):
        read_bytes(STUDY / rel)
    read_bytes(ROOT / "papers/skill-recovery-v14/paper.tex")
    read_bytes(ROOT / "papers/skill-recovery-v14/output/pdf/paper.pdf")
    # Detect edits that occurred during this audit as well as edits present before it.
    require(preservation() == preserved, "Frozen files changed during evidence audit")
    CHECKS.pop()  # The final preservation check duplicates the first human-readable item.
    manifest = {"schema": "skill-recovery-v15-evidence-manifest-v1", "experiment_commit": BASE,
                "preservation": preserved, "input_count": len(INPUTS),
                "inputs": [INPUTS[key] for key in sorted(INPUTS)],
                "generator_sha256": digest(Path(__file__).read_bytes()),
                "claim_boundaries_sha256": digest((PAPER / "evidence/CLAIM_BOUNDARIES.md").read_bytes()),
                "key_results_sha256": digest((json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")),
                "checks": CHECKS,
                "verification_scope": "Reaggregates compact episode rows, detailed causal/diagnostic rows, individual validation trials, and the append-only cost ledger; verifies frozen source/input hashes and Git preservation. Does not enumerate/read every raw API response or rerun programs.",
                "claim_sources": {
                    "source_and_state_tables": "reports/episode_table.json; reports/strict_episode_table.json",
                    "strict_template_intervals": "reports/strict_episode_table.json; analyze.py contrast() algorithm reimplemented with seed 20261018",
                    "causal_table": "reports/causal_v14.json; checked against reports/causal_summary.json",
                    "cache_receipts_faults_boundaries": "results/diagnostics.json",
                    "validation": "results/validation/trials.json and program_summary.json",
                    "semantic_supplement": "results/semantic_validation/trials.json, program_summary.json and frozen_definition.json",
                    "budget": "api/budget.jsonl; inherited studies/goal-recovery-v14/api/budget.jsonl",
                    "saved_replay_and_test_verification": "reports/replay_verification.json; reports/strict_replay_verification.json; provenance/execution_logs/v15-verified-tests.log",
                    "runtime_semantics": "rm15/runtime.py; rm15/recovery.py; rm15/campaign.py; strict_state.py"}}
    return results, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated files without writing any file")
    args = parser.parse_args()
    results, manifest = build()
    outputs = {"key_results.json": results, "manifest.json": manifest}
    for name, value in outputs.items():
        path = PAPER / "evidence" / name
        content = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if args.check:require(path.read_bytes() == content, "Generated evidence is stale: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    print(json.dumps({"status": "verified", "mode": "check" if args.check else "write", "experiment_commit": BASE,
                      "input_files_hashed": len(INPUTS), "source_rows": len(results["source"]),
                      "strict_state_rows": len(results["strict_state"]), "paired_contrasts": len(results["strict_contrasts"]),
                      "individual_validation_trials_rechecked": results["validation_main"]["trials_rechecked"] + results["semantic_supplement"]["trials_rechecked"],
                      "new_exposure_upper_usd": results["budget"]["new_exposure_usd"], "network_requests": 0}, indent=2))


if __name__ == "__main__":
    main()

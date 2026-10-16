"""Frozen Phase 8 estimands; no API access and no mutation of input evidence.

Importable helpers accept synthetic rows. The CLI reads frozen input artifacts only
after acquisition and writes a compact, immutable analysis bundle.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.evidence_v7 import AXES, LABELS

MODELS = ("gpt-6-luna", "gpt-4.1-mini")
VIEWS = ("D", "F", "T")
GLOBAL_FIELDS = ("baseline_success", "legal_routes")
SITE_FIELDS = ("occurred", "all_occurrences_authorized", "suppressed_success", "avoiding_routes")
METHOD = "paired percentile bootstrap of equally weighted authored-family means; exploratory"


def ratio(n, d):
    return n / d if d else None


def groups(rows, keys):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row[k] for k in keys)].append(row)
    return [(dict(zip(keys, key)), value) for key, value in sorted(result.items(), key=lambda p: str(p[0]))]


@lru_cache(maxsize=4096)
def _interval(values, draws, seed):
    if not values:
        return None
    if len(set(values)) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    samples = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(draws))
    return (samples[int(.025 * draws)], samples[min(draws - 1, int(.975 * draws))])


def paired_interval(rows, draws=10000, seed=8008):
    if type(draws) is not int or draws < 1:
        raise ValueError("positive integer bootstrap draws required")
    families = defaultdict(list)
    for row in rows:
        if row["difference"] is not None:
            families[row["family"]].append(row["difference"])
    effects = [(name, statistics.fmean(values)) for name, values in sorted(families.items())]
    values = tuple(v for _, v in effects)
    ci = _interval(values, draws, seed)
    return {"families": len(values), "pairs": sum(len(v) for v in families.values()),
            "estimate": statistics.fmean(values) if values else None,
            "interval95": list(ci) if ci is not None else None,
            "positive_families": sum(v > 0 for v in values),
            "negative_families": sum(v < 0 for v in values),
            "zero_families": sum(v == 0 for v in values)}


def label_counts(pairs):
    pairs = list(pairs)
    confusion = {g: {p: 0 for p in (*LABELS, "invalid")} for g in LABELS}
    for gold, pred in pairs:
        confusion[gold][pred] += 1
    n = len(pairs)
    counts = {"total": n, "correct": sum(g == p for g, p in pairs),
              "invalid": sum(p == "invalid" for _, p in pairs),
              "true_unknown": sum(g == "unknown" for g, _ in pairs),
              "correct_unknown": confusion["unknown"]["unknown"],
              "false_unknown": sum(g != "unknown" and p == "unknown" for g, p in pairs),
              "true_not_applicable": sum(g == "not_applicable" for g, _ in pairs),
              "correct_not_applicable": confusion["not_applicable"]["not_applicable"],
              "false_not_applicable": sum(g != "not_applicable" and p == "not_applicable" for g, p in pairs),
              "confusion": confusion}
    counts.update(accuracy=ratio(counts["correct"], n),
                  unknown_recall=ratio(counts["correct_unknown"], counts["true_unknown"]),
                  false_unknown_denominator=n-counts["true_unknown"],
                  false_unknown_rate=ratio(counts["false_unknown"], n-counts["true_unknown"]),
                  not_applicable_recall=ratio(counts["correct_not_applicable"], counts["true_not_applicable"]),
                  false_not_applicable_denominator=n-counts["true_not_applicable"],
                  false_not_applicable_rate=ratio(counts["false_not_applicable"], n-counts["true_not_applicable"]))
    return counts


def valid(row):
    return row.get("parsed", {}).get("protocol_valid") is True


def prediction(row, sid, axis):
    p = row.get("parsed", {}).get("by_id", {}).get(sid, {}).get(axis) if valid(row) else None
    return p if p in LABELS else "invalid"


def expected_facts(truth):
    return {"worlds": [{"world": w["index"], "baseline_success": w["baseline"]["goal"],
                         "legal_routes": w["legal_route_indices"],
                         "sites": [{"id": s["id"], **{f: s[f] for f in SITE_FIELDS}} for s in w["labels"]]}
                        for w in truth["worlds"]]}


def canonical_facts(facts):
    return json.dumps({"worlds": [{**w, "sites": sorted(w["sites"], key=lambda s: s["id"])}
                                  for w in sorted(facts["worlds"], key=lambda w: w["world"])]}, sort_keys=True)


def normalize_observations(truth, observations, models, planned_jobs=()):
    """Retain every planned primary response, inserting invalid missing outcomes."""
    meta = {r["case_id"]: r for r in truth}
    if len(meta) != len(truth):
        raise ValueError("duplicate truth case")
    seen = {}
    for row in observations:
        key = (row["case_id"], row["model"], row["view"], row["replicate"])
        if key in seen:
            raise ValueError("duplicate observation: " + str(key))
        if row["case_id"] not in meta or row["model"] not in models or row["view"] not in VIEWS:
            raise ValueError("unexpected observation: " + str(key))
        if type(row["replicate"]) is not int or row["replicate"] < 0:
            raise ValueError("invalid replicate")
        if any(row[k] != meta[row["case_id"]][k] for k in ("family", "split")):
            raise ValueError("observation metadata mismatch")
        seen[key] = dict(row)
    planned = {(r["case_id"], m, v, 0): {**{k: r[k] for k in ("case_id", "family", "split")},
               "model": m, "view": v, "replicate": 0} for r in truth for m in models for v in VIEWS}
    for job in planned_jobs:
        key = tuple(job[k] for k in ("case_id", "model", "view", "replicate"))
        planned[key] = {k: job[k] for k in ("case_id", "family", "split", "model", "view", "replicate", "job_id")}
    for key, job in planned.items():
        if key not in seen:
            seen[key] = {**job, "raw_status": "missing_response", "parsed": {"protocol_valid": False, "by_id": {},
                          "diagnostic_codes": ["MISSING_RESPONSE"]}, "missing_response": True}
    return [seen[k] for k in sorted(seen)]


def score_labels(truth, main):
    gold = {r["case_id"]: {s["id"]: s for s in r["labels"]} for r in truth}
    details, cases = [], []
    for row in main:
        meta = {k: row[k] for k in ("case_id", "family", "split", "model", "view")}
        correct = dict.fromkeys(AXES, 0)
        for sid, labels in sorted(gold[row["case_id"]].items()):
            predicted = {a: prediction(row, sid, a) for a in AXES}
            target = {a: labels[a] for a in AXES}
            for a in AXES:
                correct[a] += target[a] == predicted[a]
            details.append({**meta, "id": sid, "gold": target, "predicted": predicted,
                            "protocol_valid": valid(row), "raw_ref": row.get("raw_ref")})
        total = len(gold[row["case_id"]])
        cases.append({**meta, "total": total, "correct": correct,
                      "exact": valid(row) and all(correct[a] == total for a in AXES),
                      "protocol_valid": valid(row), "missing_response": row.get("missing_response", False),
                      "raw_ref": row.get("raw_ref")})
    metrics = []
    for key, rows in groups(details, ("split", "model", "view")):
        cs = [r for r in cases if all(r[k] == v for k, v in key.items())]
        for axis in AXES:
            family = paired_interval([{"family": r["family"], "difference": ratio(r["correct"][axis], r["total"])} for r in cs], 1)
            metrics.append({**key, "axis": axis, **label_counts((r["gold"][axis], r["predicted"][axis]) for r in rows),
                            "family_balanced_accuracy": family["estimate"], "families": family["families"],
                            "responses": len(cs), "valid_responses": sum(r["protocol_valid"] for r in cs),
                            "exact_cases": sum(r["exact"] for r in cs),
                            "exact_axis_cases": sum(r["protocol_valid"] and r["correct"][axis] == r["total"] for r in cs)})
    return details, cases, metrics


def label_pairs(case_scores, draws, seed):
    output, details = [], []
    index = defaultdict(dict)
    for r in case_scores:
        index[(r["case_id"], r["model"])][r["view"]] = r
    for (_, model), views in sorted(index.items()):
        for treatment in ("F", "T"):
            a, b = views[treatment], views["D"]
            for axis in AXES:
                details.append({**{k: a[k] for k in ("case_id", "family", "split")}, "model": model,
                                "axis": axis, "contrast": treatment + "-D", "kind": "label",
                                "treatment": ratio(a["correct"][axis], a["total"]),
                                "baseline": ratio(b["correct"][axis], b["total"]),
                                "difference": ratio(a["correct"][axis], a["total"])-ratio(b["correct"][axis], b["total"])})
    for key, rows in groups(details, ("split", "model", "axis", "contrast")):
        output.append({**key, **paired_interval(rows, draws, seed)})
    return output, details


def facts_summary(truth, main):
    expected = {r["case_id"]: expected_facts(r) for r in truth}
    output, detail = [], []
    for key, rows in groups([r for r in main if r["view"] == "F"], ("split", "model", "view")):
        fields = {f: Counter(total=0, correct=0, wrong=0, invalid=0) for f in (*GLOBAL_FIELDS, *SITE_FIELDS)}
        accepted = 0
        conditional = {a: Counter(total=0, correct=0) for a in AXES}
        for row in rows:
            wanted = expected[row["case_id"]]
            actual = row["parsed"].get("prediction") if valid(row) else None
            errors = {"global": [], "sites": []}
            for wi, world in enumerate(wanted["worlds"]):
                predicted_world = actual["worlds"][wi] if actual else None
                by_id = {s["id"]: s for s in predicted_world["sites"]} if predicted_world else {}
                for field in GLOBAL_FIELDS:
                    counts = fields[field]; counts["total"] += 1
                    state = "invalid" if not actual else "correct" if world[field] == predicted_world[field] else "wrong"
                    counts[state] += 1
                    if state == "wrong": errors["global"].append([wi, field])
                for site in world["sites"]:
                    for field in SITE_FIELDS:
                        counts = fields[field]; counts["total"] += 1
                        state = "invalid" if not actual else "correct" if site[field] == by_id[site["id"]][field] else "wrong"
                        counts[state] += 1
                        if state == "wrong": errors["sites"].append([wi, site["id"], field])
            is_accepted = valid(row) and not errors["global"] and not errors["sites"]
            accepted += is_accepted
            if is_accepted:
                labels = next(r["labels"] for r in truth if r["case_id"] == row["case_id"])
                for site in labels:
                    for axis in AXES:
                        conditional[axis]["total"] += 1
                        conditional[axis]["correct"] += prediction(row, site["id"], axis) == site[axis]
            detail.append({**{k: row[k] for k in ("case_id", "family", "split", "model")}, "accepted": is_accepted,
                           "protocol_valid": valid(row), "errors": errors, "raw_ref": row.get("raw_ref")})
        output.append({**key, "responses": len(rows), "valid_responses": sum(valid(r) for r in rows),
                       "full_fact_accepted": accepted, "full_fact_acceptance": ratio(accepted, len(rows)),
                       "global_errors": sum(fields[f]["wrong"] for f in GLOBAL_FIELDS),
                       "site_errors": sum(fields[f]["wrong"] for f in SITE_FIELDS),
                       "fields": {f: {**c, "accuracy": ratio(c["correct"], c["total"])} for f, c in fields.items()},
                       "label_accuracy_given_full_correct_facts": {a: {**c, "accuracy": ratio(c["correct"], c["total"])} for a, c in conditional.items()}})
        family_acceptance = [statistics.fmean(int(r["accepted"]) for r in rs)
                             for _, rs in groups([r for r in detail if all(r[k] == v for k, v in key.items() if k != "view")], ("family",))]
        output[-1]["family_balanced_full_fact_acceptance"] = statistics.fmean(family_acceptance) if family_acceptance else None
    return output, detail


def repeat_summary(truth, observations):
    gold = {r["case_id"]: r for r in truth}
    output = []
    for key, rows in groups(observations, ("case_id", "family", "split", "model", "view")):
        if not any(r["replicate"] > 0 for r in rows):
            continue
        rows = sorted(rows, key=lambda r: r["replicate"])
        labels, facts = [], []
        correct = []
        wanted = gold[key["case_id"]]
        for row in rows:
            signature = [(s["id"], *[prediction(row, s["id"], a) for a in AXES]) for s in sorted(wanted["labels"], key=lambda s: s["id"])]
            labels.append(json.dumps(signature) if valid(row) else None)
            correct.append(valid(row) and all(prediction(row, s["id"], a) == s[a] for s in wanted["labels"] for a in AXES))
            if key["view"] == "F":
                facts.append(canonical_facts(row["parsed"]["prediction"]) if valid(row) else None)
        complete = [r["replicate"] for r in rows] == [0, 1, 2]
        output.append({**key, "responses": len(rows), "replicates": [r["replicate"] for r in rows],
                       "valid_responses": sum(valid(r) for r in rows), "complete_three_runs": complete,
                       "identical_full_labels": complete and None not in labels and len(set(labels)) == 1,
                       "all_three_labels_correct": complete and all(correct),
                       "identical_full_facts": complete and None not in facts and len(set(facts)) == 1 if facts else None,
                       "all_three_facts_correct": complete and all(f == canonical_facts(expected_facts(wanted)) for f in facts) if facts else None})
    return output


def usage_summary(observations):
    output = []
    for population in ("primary", "repeats"):
        selected = [r for r in observations if (r["replicate"] == 0) == (population == "primary")]
        for key, rows in groups(selected, ("split", "model", "view")):
            record = {**key, "population": population, "responses": len(rows),
                      "valid_responses": sum(valid(r) for r in rows),
                      "statuses": dict(Counter(str(r.get("raw_status")) for r in rows))}
            for field in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens"):
                values = []
                for row in rows:
                    usage = row.get("usage") or {}
                    value = usage.get(field)
                    if field == "cached_input_tokens":
                        value = (usage.get("input_tokens_details") or {}).get("cached_tokens", value)
                    if field == "reasoning_tokens":
                        value = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", value)
                    values.append(value)
                values = [v for v in values if type(v) in (int, float)]
                record[field] = {"total": sum(values), "known": len(values), "mean": ratio(sum(values), len(values))}
            costs = [r["usage_cost_upper_usd"] for r in rows if type(r.get("usage_cost_upper_usd")) in (int, float)]
            record.update(usage_cost_upper_usd=sum(costs), cost_known=len(costs),
                          tool_executions=sum(r.get("tool_executions", 0) for r in rows),
                          tool_execution_counts_known=sum("tool_executions" in r for r in rows))
            output.append(record)
    return output


def result(row):
    return row.get("result") or {}


def success(row):
    return row.get("runner_status", "completed") == "completed" and result(row).get("authorized_goal") is True


def execution_summary(rows, keys):
    output = []
    for key, rs in groups(rows, keys):
        reasons = Counter((result(r).get("failure_reason") or "unspecified_failure") if r.get("runner_status", "completed") == "completed" else "runner_error" for r in rs if not success(r))
        record = {**key, "conditions": len(rs), "successes": sum(success(r) for r in rs),
                  "success_rate": ratio(sum(success(r) for r in rs), len(rs)), "failures": dict(sorted(reasons.items())),
                  "over_quota": sum(result(r).get("charged_calls", 0) > r["quota"] for r in rs),
                  "runner_errors": sum(r.get("runner_status", "completed") != "completed" for r in rs),
                  "ambiguous_stops": sum(result(r).get("ambiguous_stop") is True for r in rs),
                  "fault_triggered": sum(result(r).get("fault_diagnostics", {}).get("fault_triggered") is True for r in rs)}
        family_values = [statistics.fmean(int(success(r)) for r in frs) for _, frs in groups(rs, ("family",))]
        record.update(families=len(family_values), family_balanced_success=statistics.fmean(family_values) if family_values else None)
        for metric in ("charged_calls", "planner_steps", "simulated_effects", "unauthorized_effects", "duplicate_effects"):
            values = [result(r)[metric] for r in rs if type(result(r).get(metric)) in (int, float)]
            record[metric] = sum(values)
            record[metric + "_known"] = len(values)
        if "pipeline" in keys:
            record.update(empty_gate=sum(r.get("allowed_ids") == [] for r in rs),
                          success_empty_gate=sum(r.get("allowed_ids") == [] and success(r) for r in rs),
                          trusted_grant_rejections=sum(e.get("status") == "grant_denied" for r in rs for e in result(r).get("trace", [])),
                          original_grant_rejections=sum(e.get("status") == "grant_denied" and e.get("route_index") == 0 for r in rs for e in result(r).get("trace", [])),
                          false_allow_original_grant_rejections=sum(r.get("false_allow_original_grant_rejections", 0) for r in rs))
        output.append(record)
    return output


def execution_pairs(rows, draws, seed):
    summaries, details = [], []
    index = defaultdict(dict)
    for row in rows:
        index[tuple(row[k] for k in ("case_id", "world_index", "quota", "fault"))][row["policy"]] = row
    for _, policies in sorted(index.items()):
        for treatment, baseline in (("cost_equal", "priority_equal"), ("cost_equal", "v7_safe"), ("priority_equal", "v7_safe")):
            a, b = policies.get(treatment), policies.get(baseline)
            reference = a or b
            if reference is None:
                continue
            record = {k: reference[k] for k in ("case_id", "family", "split", "world_index", "quota", "fault")}
            record.update(kind="recovery", contrast=treatment + "-" + baseline, matched=a is not None and b is not None)
            if record["matched"]:
                record.update(treatment_success=success(a), baseline_success=success(b),
                              both_success=success(a) and success(b), success_delta=int(success(a))-int(success(b)),
                              treatment_condition_id=a.get("condition_id"), baseline_condition_id=b.get("condition_id"))
                for metric in ("charged_calls", "planner_steps", "simulated_effects"):
                    va, vb = result(a).get(metric), result(b).get(metric)
                    record[metric + "_delta"] = va-vb if type(va) in (int, float) and type(vb) in (int, float) else None
            details.append(record)
    for key, rs in groups(details, ("split", "quota", "fault", "contrast")):
        matched = [r for r in rs if r["matched"]]
        record = {**key, "conditions": len(rs), "matched": len(matched), "unmatched": len(rs)-len(matched),
                  "success_wins": sum(r["success_delta"] == 1 for r in matched),
                  "success_losses": sum(r["success_delta"] == -1 for r in matched),
                  "both_success": sum(r["both_success"] for r in matched),
                  "success": paired_interval([{"family": r["family"], "difference": r["success_delta"]} for r in matched], draws, seed)}
        for metric in ("charged_calls", "planner_steps", "simulated_effects"):
            record[metric] = {}
            for population in ("all_pairs", "both_success"):
                selected = [r for r in matched if population == "all_pairs" or r["both_success"]]
                vals = [{"family": r["family"], "difference": r[metric + "_delta"]} for r in selected]
                record[metric][population] = {**paired_interval(vals, draws, seed), "eligible": len(selected),
                                             "missing": sum(v["difference"] is None for v in vals),
                                             "total_delta": sum(v["difference"] for v in vals if v["difference"] is not None)}
        summaries.append(record)
    return summaries, details


def initial_feasibility(cases, quota=16):
    """Receipt-aware trusted execution, from INITIAL worlds, never recovery logs."""
    from tsg.runtime_v6 import _Machine, _validate
    from tsg.recovery_v8 import _estimate
    rows = []
    for case in cases:
        for wi, world in enumerate(case["worlds"]):
            feasible = []
            for ri, program in enumerate(case["routes"], 1):
                try:
                    machine = _Machine(world, quota, reuse=True)
                    estimate = _estimate(_validate(program), machine, ri, case["goal"])
                    if estimate["predicted_error"] is None and estimate["predicted_goal"] and estimate["remaining_calls"] <= quota:
                        feasible.append(ri)
                except (ValueError, TypeError, RecursionError):
                    pass
            rows.append({"case_id": case["case_id"], "world_index": wi, "quota": quota,
                         "alternative_count": len(case["routes"]), "initial_feasible_alternative_count": len(feasible),
                         "initial_feasible_alternative_indices": feasible})
    return rows


def integrated_summary(rows, feasibility, candidates):
    features = {(r["case_id"], r["world_index"], r["quota"]): r for r in feasibility}
    index = defaultdict(dict)
    false_allow_ids = defaultdict(set)
    for candidate in candidates:
        if candidate["predicted"]["authorization"] == "yes" and candidate["gold"]["authorization"] != "yes":
            false_allow_ids[(candidate["case_id"], candidate["model"]+":"+candidate["view"])].add(candidate["id"])
    for row in rows:
        ids = false_allow_ids[(row["case_id"], row["pipeline"])]
        enriched = {**row, "false_allow_original_grant_rejections": sum(
            e.get("status") == "grant_denied" and e.get("route_index") == 0 and e.get("id") in ids
            for e in result(row).get("trace", []))}
        index[tuple(row[k] for k in ("case_id", "world_index", "quota", "fault", "policy"))][row["pipeline"]] = enriched
    strata, controls = [], []
    for _, pipelines in sorted(index.items()):
        allow, block = pipelines.get("all_allow"), pipelines.get("all_block")
        known = allow is not None and block is not None and all(r.get("runner_status", "completed") == "completed" for r in (allow, block))
        sensitive = known and success(allow) != success(block)
        ref = next(iter(pipelines.values()))
        controls.append({**{k: ref[k] for k in ("case_id", "family", "split", "world_index", "quota", "fault", "policy")},
                         "known": known, "gate_sensitive": sensitive,
                         "all_allow_success": success(allow) if allow else None, "all_block_success": success(block) if block else None})
        for row in pipelines.values():
            feature = features.get((row["case_id"], row["world_index"], row["quota"]))
            names = ["all"]
            if feature:
                names += ["no_alternative" if feature["alternative_count"] == 0 else "has_alternative",
                          "no_initial_feasible_alternative" if feature["initial_feasible_alternative_count"] == 0 else "has_initial_feasible_alternative"]
            if sensitive: names.append("gate_sensitive")
            strata.extend({**row, "stratum": name} for name in names)
    summaries = execution_summary(strata, ("split", "pipeline", "policy", "fault", "stratum"))
    gates = []
    for key, rs in groups(candidates, ("split", "model", "view")):
        false = [r for r in rs if r["predicted"]["authorization"] == "yes" and r["gold"]["authorization"] != "yes"]
        gates.append({**key, "candidate_gates": len(rs), "predicted_allow": sum(r["predicted"]["authorization"] == "yes" for r in rs),
                      "false_allow": len(false), "false_allow_by_gold": {g: sum(r["gold"]["authorization"] == g for r in false) for g in LABELS if g != "yes"},
                      "false_block_true_yes": sum(r["gold"]["authorization"] == "yes" and r["predicted"]["authorization"] != "yes" for r in rs)})
    control_summary = []
    for key, rs in groups(controls, ("split", "policy", "fault")):
        control_summary.append({**key, "conditions": len(rs), "known": sum(r["known"] for r in rs),
                                "gate_sensitive": sum(r["gate_sensitive"] for r in rs),
                                "allow_wins": sum(r["known"] and r["all_allow_success"] and not r["all_block_success"] for r in rs),
                                "block_wins": sum(r["known"] and r["all_block_success"] and not r["all_allow_success"] for r in rs)})
    return summaries, gates, control_summary, controls


def historical_summary(truth, main, historical):
    old = {(r["case_id"], r["model"], r["view"]): r for r in historical if r["replicate"] == 0 and r["view"] in ("B1", "B2")}
    gold = {r["case_id"]: r for r in truth if r["split"] == "regression"}
    rows = []
    for fresh in main:
        cid = fresh["case_id"]
        if cid not in gold or fresh["view"] not in ("D", "F"):
            continue
        old_view = "B1" if fresh["view"] == "D" else "B2"
        previous = old.get((cid, fresh["model"], old_view))
        for axis in AXES:
            labels = gold[cid]["labels"]
            rows.append({"case_id": cid, "family": fresh["family"], "model": fresh["model"], "axis": axis,
                         "contrast": fresh["view"] + "-historical_" + old_view, "matched": previous is not None,
                         "total": len(labels), "fresh_correct": sum(prediction(fresh, s["id"], axis) == s[axis] for s in labels),
                         "historical_correct": sum(prediction(previous, s["id"], axis) == s[axis] for s in labels) if previous else None})
    output = []
    for key, rs in groups(rows, ("model", "axis", "contrast")):
        matched = [r for r in rs if r["matched"]]
        n = sum(r["total"] for r in matched)
        output.append({**key, "regression_cases": len(rs), "matched_cases": len(matched), "candidate_denominator": n,
                       "fresh_correct": sum(r["fresh_correct"] for r in matched),
                       "historical_correct": sum(r["historical_correct"] for r in matched),
                       "fresh_accuracy": ratio(sum(r["fresh_correct"] for r in matched), n),
                       "historical_accuracy": ratio(sum(r["historical_correct"] for r in matched), n),
                       "interpretation": "descriptive longitudinal rerun; acquisition time differs" + ("; protocol differs" if "B2" in key["contrast"] else "")})
    return output


def validate_execution_rows(rows, integrated=False):
    seen = set()
    for row in rows:
        fields = ("case_id", "world_index", "quota", "fault", "policy") + (("pipeline",) if integrated else ())
        key = tuple(row[k] for k in fields)
        if key in seen:
            raise ValueError("duplicate execution condition: " + str(key))
        seen.add(key)


def failure_rows(main, case_scores, fact_scores, recovery, integrated):
    failures = []
    for row in case_scores:
        if not row["exact"]:
            failures.append({**row, "kind": "labels", "reason": "typed_label_error" if row["protocol_valid"] else "invalid_response"})
    for row in fact_scores:
        if not row["accepted"]:
            failures.append({**row, "kind": "facts", "reason": "fact_error" if row["protocol_valid"] else "invalid_response"})
    for track, rows in (("recovery", recovery), ("integrated", integrated)):
        for row in rows:
            r = result(row)
            unsafe = any(r.get(k, 0) > 0 for k in ("unauthorized_effects", "duplicate_effects")) or r.get("charged_calls", 0) > row["quota"]
            if success(row) and not unsafe:
                continue
            failures.append({**{k: row[k] for k in ("condition_id", "case_id", "family", "split", "world_index", "quota", "fault", "policy", "pipeline") if k in row},
                             "kind": track, "reason": r.get("failure_reason") or "runner_error", "success": success(row),
                             "safety_violation": unsafe, "raw_ref": f"results/phase8/{track}/vm_results.jsonl#condition_id={row.get('condition_id')}",
                             **{k: r.get(k) for k in ("charged_calls", "planner_steps", "unauthorized_effects", "duplicate_effects")}})
    return failures


def analyze(truth_rows=None, observations=None, recovery_rows=(), integration_rows=(), *, case_rows=(), historical_rows=(),
            planned_jobs=(), models=MODELS, feasibility_rows=None, draws=10000, seed=8008, output=None, input_manifest=None):
    """No args: load/write production bundle and return summary. Rows: return report."""
    if truth_rows is None and observations is None:
        return main([])["summary"]
    truth, observed = list(truth_rows), list(observations)
    recovery, integrated = list(recovery_rows), list(integration_rows)
    for row in truth:
        if not row["labels"] or len({s["id"] for s in row["labels"]}) != len(row["labels"]):
            raise ValueError("empty or duplicate truth candidates")
        if any(s[a] not in LABELS for s in row["labels"] for a in AXES):
            raise ValueError("invalid truth label")
    obs = normalize_observations(truth, observed, models, planned_jobs)
    primary_rows = [r for r in obs if r["replicate"] == 0]
    candidates, case_scores, metrics = score_labels(truth, primary_rows)
    comparisons, label_details = label_pairs(case_scores, draws, seed)
    facts, fact_scores = facts_summary(truth, primary_rows)
    validate_execution_rows(recovery)
    validate_execution_rows(integrated, True)
    recovery_pairs, recovery_details = execution_pairs(recovery, draws, seed)
    feasibility = initial_feasibility(case_rows) if feasibility_rows is None else list(feasibility_rows)
    integration, gates, controls, gate_details = integrated_summary(integrated, feasibility, candidates)
    summary = {"schema_version": "phase8-analysis-v1", "cases": len(truth),
               "cases_by_split": dict(Counter(r["split"] for r in truth)),
               "families_by_split": {s: len({r["family"] for r in truth if r["split"] == s}) for s in sorted({r["split"] for r in truth})},
               "primary_expected": len(truth)*len(models)*len(VIEWS), "primary_responses": len(primary_rows),
               "primary_received": sum(not r.get("missing_response", False) for r in primary_rows),
               "primary_valid": sum(valid(r) for r in primary_rows), "all_observations": len(obs),
               "metrics": metrics, "label_pairs": comparisons, "facts": facts,
               "tool_label_residuals": [{k: r[k] for k in ("split", "model", "axis", "total", "correct", "invalid", "exact_cases", "responses")}
                                         | {"residual_errors": r["total"]-r["correct"]} for r in metrics if r["view"] == "T"],
               "repeats": repeat_summary(truth, obs), "usage": usage_summary(obs),
               "historical": historical_summary(truth, primary_rows, historical_rows),
               "recovery_conditions": len(recovery), "integrated_conditions": len(integrated),
               "recovery": execution_summary(recovery, ("split", "quota", "fault", "policy")),
               "recovery_pairs": recovery_pairs, "integrated": integration, "raw_gates": gates,
               "gate_controls": controls, "initial_feasibility_worlds": len(feasibility),
               "methods": {"bootstrap": METHOD, "draws": draws, "seed": seed,
                           "family_accuracy": "mean candidate accuracy within each case, then case means within family; families equally weighted",
                           "invalid": "separate invalid prediction column, included in every primary candidate-axis denominator",
                           "fact_denominators": "global fields once per world; candidate fields once per world/site; invalid responses counted invalid at every expected field",
                           "selective_accuracy": "conditional on the entire response having correct facts; null means zero accepted denominator",
                           "integration_strata": "initial alternative feasibility uses enforcing receipt-aware _Machine/_estimate with quota16; gate sensitivity is paired all_allow versus all_block success disagreement",
                           "safety_attribution": "trusted grants protect alternatives; aggregate solver gates are conservative across worlds, not per-world success ceilings",
                           "computation": "T tool execution counts and all policy planning work are reported; no LLM enumeration speedup claim",
                           "ci_limitations": "exploratory, no multiplicity correction, 12 new authored families; no candidate/seed pseudoreplication",
                           "historical": "same 24 regression cases only; longitudinal and protocol differences remain confounders",
                           "F_attribution": "F-D bundles factorized fact output and deterministic label reduction; their individual causal contributions are not isolated",
                           "cost": "conservative usage bounds, not invoices; known-cost and token denominators explicit; no heldout/regression pooling"}}
    if input_manifest is not None:
        summary["input_manifest"] = input_manifest
    report = {"summary": summary, "candidate_scores": candidates, "case_scores": case_scores,
              "fact_scores": fact_scores, "paired_details": label_details + recovery_details,
              "gate_conditions": gate_details, "initial_feasibility": feasibility,
              "failures": failure_rows(primary_rows, case_scores, fact_scores, recovery, integrated)}
    if output is not None:
        write_immutable(output, report)
    return report


def write_immutable(output, report):
    output = Path(output)
    encoded = {"summary.json": (json.dumps(report["summary"], ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode()}
    encoded.update({name+".jsonl": "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n" for r in rows).encode()
                    for name, rows in report.items() if name != "summary"})
    for name, data in encoded.items():
        path = output/name
        if path.exists() and path.read_bytes() != data:
            raise ValueError("IMMUTABLE_MISMATCH:" + str(path))
    output.mkdir(parents=True, exist_ok=True)
    for name, data in encoded.items():
        if not (output/name).exists():
            with (output/name).open("xb") as handle:
                handle.write(data)


def read_input(root, relative, required=True):
    path = root/relative
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return [], {"path": relative, "present": False, "rows": 0}
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.decode("utf-8-sig").splitlines() if line.strip()]
    return rows, {"path": relative, "present": True, "rows": len(rows), "sha256": hashlib.sha256(data).hexdigest()}


def complete_execution_rows(rows, jobs):
    by_id = {r["condition_id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("duplicate execution condition id")
    for job in jobs:
        meta = job["meta"]
        if meta["condition_id"] not in by_id:
            by_id[meta["condition_id"]] = {**meta, "runner_status": "missing_result", "result": None}
    return [by_id[k] for k in sorted(by_id)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    paths = {"truth": "results/phase8/semantics/truth.jsonl", "observations": "results/phase8/api/observations.jsonl",
             "recovery": "results/phase8/recovery/vm_results.jsonl", "integrated": "results/phase8/integrated/vm_results.jsonl",
             "historical": "results/phase7/api/observations.jsonl", "jobs": "results/phase8/acquisition/jobs.jsonl",
             "recovery_jobs": "results/phase8/recovery/jobs.jsonl", "integrated_jobs": "results/phase8/integrated/jobs.jsonl",
             "old_cases": "data/phase7/heldout.jsonl", "new_cases": "data/phase8/heldout.jsonl"}
    inputs, manifest = {}, {}
    for name, path in paths.items():
        inputs[name], manifest[name] = read_input(args.root, path)
    for name in ("recovery", "integrated"):
        inputs[name] = complete_execution_rows(inputs[name], inputs[name+"_jobs"])
    report = analyze(inputs["truth"], inputs["observations"], inputs["recovery"], inputs["integrated"],
                     historical_rows=inputs["historical"], planned_jobs=inputs["jobs"],
                     case_rows=inputs["old_cases"]+inputs["new_cases"], input_manifest=manifest,
                     output=args.output or args.root/"results/phase8/analysis")
    print(json.dumps({k: report["summary"][k] for k in ("cases", "primary_expected", "primary_received", "primary_valid", "recovery_conditions", "integrated_conditions")}))
    return report


if __name__ == "__main__":
    main()

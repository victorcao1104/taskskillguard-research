"""Prospective Phase 7 analysis. This module never opens data or calls a solver.

Accuracy uses replicate zero only. Candidate scores describe micro accuracy;
paired effects average candidates within cases, then cases within families.
Every protocol failure contributes missing (incorrect) predictions.
"""
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import combinations
import json
import random
import statistics

from .evidence_v7 import AXES, LABELS


METHOD = "family-balanced paired percentile bootstrap; exploratory, no confirmatory multiplicity claim"
EXECUTION_METRICS = ("authorized_goal", "charged_calls", "attempts", "planner_steps",
                     "simulated_effects", "unauthorized_effects", "duplicate_effects")
COST_METRICS = ("charged_calls", "attempts", "planner_steps", "simulated_effects")


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _collapsed(value):
    return "unknown" if value == "not_applicable" else value


@lru_cache(maxsize=1024)
def _bootstrap(values, draws, seed):
    if not values:
        return None
    if len(set(values)) == 1:
        return [values[0], values[0]]
    rng = random.Random(seed)
    boot = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(draws))
    return [boot[int(.025 * draws)], boot[min(draws - 1, int(.975 * draws))]]


def paired_interval(rows, draws=10000, seed=7007):
    """Bootstrap families, keeping every case/world pair in its original family."""
    if type(draws) is not int or draws < 1:
        raise ValueError("draws must be a positive integer")
    rows = list(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[row["family"]].append(row["difference"])
    values = tuple(statistics.fmean(sorted(v)) for _, v in sorted(groups.items()))
    interval = _bootstrap(values, draws, seed)
    return {"families": len(values), "conditions": len(rows),
            "estimate": statistics.fmean(values) if values else None,
            "interval95": list(interval) if interval is not None else None,
            "draws": draws, "seed": seed, "method": METHOD,
            "family_effects": [{"family": family, "conditions": len(values),
                                "difference": statistics.fmean(sorted(values))}
                               for family, values in sorted(groups.items())]}


def label_counts(pairs):
    """Unknown, not-applicable, and missing occupy distinct confusion columns."""
    pairs = list(pairs)
    confusion = defaultdict(Counter)
    for gold, predicted in pairs:
        confusion[gold]["missing" if predicted is None else predicted] += 1
    counts = {"total": len(pairs), "correct": sum(a == b for a, b in pairs),
              "missing": sum(b is None for _, b in pairs),
              "gold_unknown": sum(a == "unknown" for a, _ in pairs),
              "correct_unknown": sum(a == b == "unknown" for a, b in pairs),
              "predicted_unknown": sum(b == "unknown" for _, b in pairs),
              "false_unknown": sum(a != "unknown" and b == "unknown" for a, b in pairs),
              "unsupported_decision": sum(a == "unknown" and b in ("yes", "no") for a, b in pairs),
              "unknown_to_not_applicable": sum(a == "unknown" and b == "not_applicable" for a, b in pairs),
              "gold_not_applicable": sum(a == "not_applicable" for a, _ in pairs),
              "correct_not_applicable": sum(a == b == "not_applicable" for a, b in pairs),
              "false_not_applicable": sum(a != "not_applicable" and b == "not_applicable" for a, b in pairs),
              "gold_distribution": dict(sorted(Counter(a for a, _ in pairs).items())),
              "predicted_distribution": dict(sorted(Counter("missing" if b is None else b for _, b in pairs).items())),
              "confusion": {a: dict(sorted(bs.items())) for a, bs in sorted(confusion.items())}}
    counts.update(accuracy=_ratio(counts["correct"], counts["total"]),
                  unknown_recall=_ratio(counts["correct_unknown"], counts["gold_unknown"]),
                  unknown_precision=_ratio(counts["correct_unknown"], counts["predicted_unknown"]),
                  false_unknown_rate=_ratio(counts["false_unknown"], counts["total"] - counts["gold_unknown"]),
                  not_applicable_recall=_ratio(counts["correct_not_applicable"], counts["gold_not_applicable"]))
    return counts


def _groups(rows, keys):
    """Produce both observed split groups and pooled groups, never pool pipelines."""
    groups = defaultdict(list)
    for row in rows:
        for split in (row["split"], "all"):
            key = (split, *(row.get(k) for k in keys))
            groups[key].append(row)
    return [(dict(zip(("split", *keys), key)), rs)
            for key, rs in sorted(groups.items(), key=lambda item: str(item[0]))]


def _valid(row):
    return row.get("parsed", {}).get("protocol_valid") is True


def _predicted(row, site_id, axis):
    if not _valid(row):
        return None
    by_id = row.get("parsed", {}).get("by_id", {})
    candidate = by_id.get(site_id, {}) if isinstance(by_id, dict) else {}
    value = candidate.get(axis) if isinstance(candidate, dict) else None
    allowed = LABELS[:3] if row["view"] == "B0" else LABELS
    return value if value in allowed else None


def _check_inputs(truth, observations):
    gold = {}
    for row in truth:
        cid = row["case_id"]
        if cid in gold:
            raise ValueError(f"duplicate truth case: {cid}")
        if row["split"] not in ("regression", "heldout"):
            raise ValueError(f"unknown truth split: {row['split']}")
        labels = {}
        for label in row["labels"]:
            if label["id"] in labels:
                raise ValueError(f"duplicate truth candidate: {cid}/{label['id']}")
            if any(label.get(axis) not in LABELS for axis in AXES):
                raise ValueError(f"invalid typed truth: {cid}/{label['id']}")
            labels[label["id"]] = label
        gold[cid] = labels
    metadata = {row["case_id"]: row for row in truth}
    seen = set()
    jobs = set()
    for row in observations:
        cid = row["case_id"]
        if cid not in gold:
            raise ValueError(f"observation has no truth: {cid}")
        if any(row[k] != metadata[cid][k] for k in ("family", "split")):
            raise ValueError(f"truth/observation metadata mismatch: {cid}")
        if row["view"] not in ("B0", "B1", "B2"):
            raise ValueError(f"unknown view: {row['view']}")
        if type(row.get("replicate")) is not int or row["replicate"] < 0:
            raise ValueError("replicate must be a nonnegative integer")
        key = (cid, row["model"], row["view"], row["replicate"])
        job = row.get("job_id")
        if key in seen or (job is not None and job in jobs):
            raise ValueError(f"duplicate observation: {key}")
        seen.add(key)
        if job is not None:
            jobs.add(job)
    return gold


def _score(main, gold):
    details, cases = [], []
    for row in main:
        metadata = {k: row[k] for k in ("case_id", "family", "split", "model", "view")}
        metadata.update(job_id=row.get("job_id"), replicate=0, protocol_valid=_valid(row))
        spaces = ("collapsed",) if row["view"] == "B0" else ("typed", "collapsed")
        for space in spaces:
            for axis in AXES:
                candidate_rows = []
                for site_id, label in sorted(gold[row["case_id"]].items()):
                    original_prediction = _predicted(row, site_id, axis)
                    target = _collapsed(label[axis]) if space == "collapsed" else label[axis]
                    prediction = _collapsed(original_prediction) if space == "collapsed" else original_prediction
                    detail = {**metadata, "label_space": space, "id": site_id, "axis": axis,
                              "gold_typed": label[axis], "predicted_raw": original_prediction,
                              "gold": target, "predicted": prediction, "correct": prediction == target,
                              "gold_reasons": label.get("reasons", {}).get(axis, [])}
                    candidate_rows.append(detail)
                    details.append(detail)
                n = len(candidate_rows)
                correct = sum(r["correct"] for r in candidate_rows)
                cases.append({**metadata, "label_space": space, "axis": axis,
                              "total": n, "correct": correct, "accuracy": _ratio(correct, n)})
    metrics = []
    for key, rows in _groups(details, ("model", "view", "label_space", "axis")):
        metrics.append({**key, **label_counts((r["gold"], r["predicted"]) for r in rows),
                        "genuine_typed_unknown": sum(r["gold_typed"] == "unknown" for r in rows),
                        "collapsed_from_not_applicable": sum(r["gold_typed"] == "not_applicable" for r in rows),
                        "protocol_invalid_candidates": sum(not r["protocol_valid"] for r in rows)})
    return details, cases, metrics


def _representation_pairs(cases, draws, seed):
    summaries, details = [], []
    for space, treatment, baseline in (("collapsed", "B1", "B0"), ("collapsed", "B2", "B1"),
                                       ("collapsed", "B2", "B0"), ("typed", "B2", "B1")):
        relevant = [r for r in cases if r["label_space"] == space and r["view"] in (treatment, baseline)]
        index = defaultdict(dict)
        for row in relevant:
            index[(row["case_id"], row["split"], row["model"], row["axis"])][row["view"]] = row
        cohorts = []
        for _, views in sorted(index.items()):
            a, b = views.get(treatment), views.get(baseline)
            reference = a or b
            record = {k: reference[k] for k in ("case_id", "family", "split", "model", "axis")}
            record.update(kind="representation", label_space=space, contrast=f"{treatment}-{baseline}",
                          has_treatment=a is not None, has_baseline=b is not None,
                          difference=None)
            if a is not None and b is not None and a["accuracy"] is not None and b["accuracy"] is not None:
                record.update(treatment=a["accuracy"], baseline=b["accuracy"],
                              difference=a["accuracy"] - b["accuracy"])
                details.append(dict(record))
            cohorts.append(record)
        for key, rows in _groups(cohorts, ("model", "axis", "label_space", "contrast")):
            usable = [r for r in rows if r["difference"] is not None]
            summaries.append({**key, **paired_interval(usable, draws, seed),
                              "unit": "case mean candidate accuracy; family means equally weighted",
                              "unmatched_baseline": sum(r["has_baseline"] and not r["has_treatment"] for r in rows),
                              "unmatched_treatment": sum(r["has_treatment"] and not r["has_baseline"] for r in rows)})
    return summaries, details


def _certificates(main, gold):
    output = []
    for key, rows in _groups([r for r in main if r["view"] == "B2"], ("model", "view")):
        counts = Counter(main_conditions=len(rows))
        errors = Counter()
        for row in rows:
            labels = gold[row["case_id"]]
            counts["candidate_total"] += len(labels)
            certificate = row.get("certificate")
            if not isinstance(certificate, dict):
                counts["certificate_missing"] += 1
                continue
            counts["certificate_present"] += 1
            correct_ids = {site_id for site_id, label in labels.items()
                           if all(_predicted(row, site_id, a) == label[a] for a in AXES)}
            accepted_ids = set(certificate.get("accepted_ids", []))
            counts["accepted_candidates"] += len(accepted_ids.intersection(labels))
            counts["correct_accepted_candidates"] += len(accepted_ids.intersection(correct_ids))
            counts["unknown_accepted_candidate_ids"] += len(accepted_ids.difference(labels))
            if isinstance(certificate.get("execution_count"), (int, float)):
                counts["checker_execution_count"] += certificate["execution_count"]
                counts["checker_execution_count_known"] += 1
            if certificate.get("accepted") is True:
                counts["accepted_conditions"] += 1
                correct = _valid(row) and len(correct_ids) == len(labels)
                counts["correct_accepted_conditions"] += correct
                counts["incorrectly_accepted_conditions"] += not correct
            else:
                counts["rejected_conditions"] += 1
            for values in certificate.get("errors", {}).values():
                errors.update(values if isinstance(values, list) else [str(values)])
        required = ("certificate_missing", "certificate_present", "candidate_total", "accepted_candidates",
                    "correct_accepted_candidates", "unknown_accepted_candidate_ids", "checker_execution_count", "checker_execution_count_known",
                    "accepted_conditions", "correct_accepted_conditions", "incorrectly_accepted_conditions", "rejected_conditions")
        output.append({**key, **{name: counts[name] for name in ("main_conditions", *required)},
                       "condition_coverage": _ratio(counts["accepted_conditions"], len(rows)),
                       "candidate_coverage": _ratio(counts["accepted_candidates"], counts["candidate_total"]),
                       "selective_condition_accuracy": _ratio(counts["correct_accepted_conditions"], counts["accepted_conditions"]),
                       "selective_candidate_accuracy": _ratio(counts["correct_accepted_candidates"], counts["accepted_candidates"]),
                       "errors": dict(sorted(errors.items()))})
    return output


def _repeat_agreement(observations, gold):
    groups = defaultdict(list)
    for row in observations:
        groups[(row["case_id"], row["model"], row["view"])].append(row)
    output = []
    for (cid, model, view), rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        fingerprints = []
        for row in rows:
            values = [(site_id, *(_predicted(row, site_id, axis) for axis in AXES))
                      for site_id in sorted(gold[cid])]
            complete = _valid(row) and all(None not in value for value in values)
            fingerprints.append(json.dumps(values) if complete else None)
        pairs = list(combinations(fingerprints, 2))
        matches = sum(a is not None and a == b for a, b in pairs)
        all_valid = all(value is not None for value in fingerprints)
        output.append({"case_id": cid, "family": rows[0]["family"], "split": rows[0]["split"],
                       "model": model, "view": view, "conditions": len(rows),
                       "replicates": sorted(r["replicate"] for r in rows),
                       "valid_conditions": sum(v is not None for v in fingerprints),
                       "all_valid": all_valid, "identical": all_valid and len(set(fingerprints)) == 1,
                       "agreement_pairs": matches, "total_pairs": len(pairs),
                       "pairwise_agreement": _ratio(matches, len(pairs))})
    return output


def _usage(observations):
    output = []
    for population, selected in (("all", observations), ("main", [r for r in observations if r["replicate"] == 0])):
        for key, rows in _groups(selected, ("model", "view")):
            usages = [r.get("usage") for r in rows]
            valid_usage = [u for u in usages if isinstance(u, dict)]
            record = {**key, "population": population, "conditions": len(rows),
                      "usage_present": len(valid_usage), "raw_statuses": dict(sorted(Counter(str(r.get("raw_status")) for r in rows).items()))}
            for field in ("input_tokens", "output_tokens", "total_tokens", "cached_input_tokens", "reasoning_tokens"):
                known = [u[field] for u in valid_usage if isinstance(u.get(field), (int, float))]
                record[field] = sum(known)
                record[field + "_known"] = len(known)
            costs = [r["usage_cost_upper_usd"] for r in rows if isinstance(r.get("usage_cost_upper_usd"), (int, float))]
            record.update(usage_cost_upper_usd=sum(costs), cost_known=len(costs))
            output.append(record)
    return output


def _result(row):
    result = row.get("result")
    return result if isinstance(result, dict) else {}


def _completed(row):
    return isinstance(row.get("result"), dict) and row.get("runner_status", "completed") == "completed"


def _execution_value(row, metric):
    result = _result(row)
    if metric == "authorized_goal":
        return int(_completed(row) and result.get(metric) is True)
    value = result.get(metric)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _validate_executions(rows, integrated):
    seen, condition_ids = set(), set()
    for row in rows:
        keys = ("case_id", "split", "world_index", "quota", "fault", "selector", "policy")
        if integrated:
            keys += ("model", "view", "pipeline")
            if row.get("replicate", 0) != 0:
                raise ValueError("integration may only contain replicate zero")
        key = tuple(row[k] for k in keys)
        condition_id = row.get("condition_id")
        if key in seen or (condition_id is not None and condition_id in condition_ids):
            raise ValueError(f"duplicate execution condition: {key}")
        seen.add(key)
        if condition_id is not None:
            condition_ids.add(condition_id)
        if row["split"] not in ("regression", "heldout"):
            raise ValueError(f"unknown execution split: {row['split']}")


def _execution_summary(rows, integrated):
    keys = (("model", "view", "pipeline") if integrated else ()) + ("quota", "fault", "selector", "policy")
    output = []
    for key, group in _groups(rows, keys):
        result = [_result(r) for r in group]
        completed = sum(_completed(r) for r in group)
        success = [_execution_value(r, "authorized_goal") == 1 for r in group]
        diagnostics = [r.get("fault_diagnostics", {}) for r in result]
        triggered = sum(d.get("fault_triggered") is True for d in diagnostics)
        known_fault = sum(type(d.get("fault_triggered")) is bool for d in diagnostics)
        failures = Counter(str(r.get("failure_reason") or "unspecified_failure")
                           if _completed(row) else "runner_error"
                           for row, r, good in zip(group, result, success) if not good)
        record = {**key, "conditions": len(group), "completed": completed,
                  "runner_errors": len(group) - completed, "authorized_goal": sum(success),
                  "authorized_goal_rate": _ratio(sum(success), len(group)),
                  "goal": sum(r.get("goal") is True for r in result),
                  "fault_triggered": triggered, "fault_not_triggered": known_fault - triggered,
                  "fault_trigger_unknown": len(group) - known_fault,
                  "fault_schedule_completed": sum(d.get("schedule_completed") is True for d in diagnostics),
                  "injected_fault_count": sum(d.get("injected_fault_count", 0) for d in diagnostics),
                  "scheduled_fault_count": sum(d.get("scheduled_fault_count", 0) for d in diagnostics),
                  "failures": dict(sorted(failures.items())),
                  "ambiguous_stops": sum(r.get("ambiguous_stop") is True for r in result),
                  "route_bypass": sum(r.get("route_bypass") is True for r in result),
                  "route_bypass_success": sum(r.get("route_bypass") is True and good for r, good in zip(result, success)),
                  "recovered_success": sum(good and r.get("attempts", 0) > 1 for r, good in zip(result, success)),
                  "unauthorized_effect_conditions": sum(r.get("unauthorized_effects", 0) > 0 for r in result),
                  "duplicate_effect_conditions": sum(r.get("duplicate_effects", 0) > 0 for r in result),
                  "safety_unknown_conditions": sum(not _completed(row) or any(a not in r for a in ("unauthorized_effects", "duplicate_effects"))
                                                   for row, r in zip(group, result)),
                  "stage_failures": dict(sorted(Counter(str(event.get("status")) for r in result for event in r.get("trace", [])
                                                        if event.get("status") not in ("committed", "receipt_reused")).items()))}
        if integrated:
            record.update(empty_original_gate=sum(r.get("allowed_ids") == [] for r in group),
                          success_with_empty_original_gate=sum(r.get("allowed_ids") == [] and good for r, good in zip(group, success)),
                          gate_unreported=sum("allowed_ids" not in r for r in group),
                          certificate_rejected=sum(r.get("certificate_accepted") is False for r in group))
        for metric in (*COST_METRICS, "unauthorized_effects", "duplicate_effects", "receipt_reuses", "routes_considered"):
            known = [_execution_value(r, metric) for r in group]
            values = [v for v in known if v is not None]
            record[metric] = sum(values)
            record["mean_" + metric] = _ratio(sum(values), len(values))
            record[metric + "_known"] = len(values)
        output.append(record)
    return output


def _execution_pairs(rows, integrated, draws, seed):
    summaries, details = [], []
    extra = ("model", "view", "pipeline") if integrated else ()
    for variable, treatment, baseline, fixed in (("policy", "safe_retry", "legacy", "selector"),
                                                 ("selector", "search_equal", "first_feasible", "policy")):
        keys = ("case_id", "split", "world_index", "quota", "fault", fixed, *extra)
        index = defaultdict(dict)
        for row in rows:
            if row[variable] in (treatment, baseline):
                index[tuple(row[k] for k in keys)][row[variable]] = row
        cohorts = []
        for _, variants in sorted(index.items(), key=lambda item: str(item[0])):
            a, b = variants.get(treatment), variants.get(baseline)
            reference = a or b
            record = {k: reference[k] for k in (*keys, "family")}
            record.update(contrast=f"{treatment}-{baseline}", treatment_row=a, baseline_row=b)
            cohorts.append(record)
        for key, group in _groups(cohorts, (*extra, "quota", "fault", fixed, "contrast")):
            matched = [r for r in group if r["treatment_row"] is not None and r["baseline_row"] is not None]
            for metric in EXECUTION_METRICS:
                for population in (("all_pairs", "both_success") if metric in COST_METRICS else ("all_pairs",)):
                    selected = [r for r in matched if population == "all_pairs" or
                                all(_execution_value(r[k], "authorized_goal") == 1 for k in ("treatment_row", "baseline_row"))]
                    pairs = []
                    for row in selected:
                        a = _execution_value(row["treatment_row"], metric)
                        b = _execution_value(row["baseline_row"], metric)
                        if a is None or b is None:
                            continue
                        pair = {k: v for k, v in row.items() if not k.endswith("_row")}
                        pair.update(kind="integrated" if integrated else "recovery", metric=metric,
                                    population=population, treatment=a, baseline=b, difference=a-b,
                                    treatment_condition_id=row["treatment_row"].get("condition_id"),
                                    baseline_condition_id=row["baseline_row"].get("condition_id"))
                        pairs.append(pair)
                        # Pooled rows share the same underlying pair; save it only once.
                        if key["split"] != "all":
                            details.append(pair)
                    summaries.append({**key, "metric": metric, "population": population,
                                      **paired_interval(pairs, draws, seed),
                                      "matched_conditions": len(matched), "eligible_conditions": len(selected),
                                      "missing_metric_pairs": len(selected)-len(pairs),
                                      "unmatched_baseline": sum(r["baseline_row"] is not None and r["treatment_row"] is None for r in group),
                                      "unmatched_treatment": sum(r["treatment_row"] is not None and r["baseline_row"] is None for r in group),
                                      "success_gains": sum(_execution_value(r["treatment_row"], "authorized_goal") == 1 and
                                                           _execution_value(r["baseline_row"], "authorized_goal") == 0 for r in matched),
                                      "success_losses": sum(_execution_value(r["treatment_row"], "authorized_goal") == 0 and
                                                            _execution_value(r["baseline_row"], "authorized_goal") == 1 for r in matched)})
    return summaries, details


def _execution_failures(rows, kind):
    failures = []
    for row in rows:
        result = _result(row)
        unsafe = any(result.get(k, 0) > 0 for k in ("unauthorized_effects", "duplicate_effects"))
        if _execution_value(row, "authorized_goal") == 1 and not unsafe:
            continue
        record = {k: row[k] for k in ("condition_id", "case_id", "family", "split", "world_index", "quota", "fault",
                                     "selector", "policy", "model", "view", "pipeline") if k in row}
        record.update(kind=kind, runner_status=row.get("runner_status", "completed" if _completed(row) else "missing"),
                      failure_reason=result.get("failure_reason"), authorized_goal=bool(_execution_value(row, "authorized_goal")),
                      safety_violation=unsafe, fault_diagnostics=result.get("fault_diagnostics"))
        record.update({key: result.get(key) for key in ("charged_calls", "attempts", "unauthorized_effects", "duplicate_effects", "ambiguous_stop")})
        failures.append(record)
    return failures


def analyze(truth_rows, observations, recovery_rows=(), integration_rows=(), *, draws=10000, seed=7007):
    """Return summary plus auditable candidate, case, paired, and failure rows."""
    truth, observations = list(truth_rows), list(observations)
    recovery, integrated = list(recovery_rows), list(integration_rows)
    gold = _check_inputs(truth, observations)
    _validate_executions(recovery, False)
    _validate_executions(integrated, True)
    main = [r for r in observations if r["replicate"] == 0]
    details, case_scores, metrics = _score(main, gold)
    comparisons, representation_pairs = _representation_pairs(case_scores, draws, seed)
    recovery_pairs, recovery_details = _execution_pairs(recovery, False, draws, seed)
    integrated_pairs, integrated_details = _execution_pairs(integrated, True, draws, seed)
    reason_counts = Counter()
    for row in truth:
        for label in row["labels"]:
            for axis in AXES:
                reasons = label.get("reasons", {}).get(axis, [])
                for reason in ([reasons] if isinstance(reasons, str) else reasons):
                    reason_counts[(row["split"], axis, label[axis], reason)] += 1
    hashes = [r["request_hash"] for r in observations if r.get("request_hash")]
    summary = {"schema_version": "phase7-analysis-v1", "cases": len(truth),
               "families": len({r["family"] for r in truth}),
               "cases_by_split": dict(sorted(Counter(r["split"] for r in truth).items())),
               "main_conditions": len(main), "main_protocol_valid": sum(_valid(r) for r in main),
               "all_conditions": len(observations), "all_protocol_valid": sum(_valid(r) for r in observations),
               "unique_requests": len(set(hashes)), "request_hash_present": len(hashes),
               "duplicate_request_hashes": len(hashes)-len(set(hashes)),
               "metrics": metrics, "representation_comparisons": comparisons,
               "certificates": _certificates(main, gold), "repeats": _repeat_agreement(observations, gold),
               "usage": _usage(observations),
               "label_reasons": [{"split": split, "axis": axis, "gold": label, "reason": reason, "count": count}
                                 for (split, axis, label, reason), count in sorted(reason_counts.items())],
               "recovery_conditions": len(recovery), "integrated_conditions": len(integrated),
               "recovery": _execution_summary(recovery, False), "recovery_pairs": recovery_pairs,
               "integrated": _execution_summary(integrated, True), "integrated_pairs": integrated_pairs,
               "methods": {"bootstrap": METHOD, "draws": draws, "seed": seed,
                           "accuracy_denominator": "all gold candidate axes in observed main conditions; invalid protocol is missing and incorrect",
                           "label_spaces": "B0 collapsed only; B1/B2 typed and collapsed; collapse not_applicable to unknown",
                           "pairing": "accuracy: same case/model/axis; execution: same case/world/quota/fault plus fixed strategy or selector and pipeline",
                           "missing_conditions": "unobserved conditions are not fabricated; paired coverage reported explicitly",
                           "cost_denominator": "known numeric costs; both-success pairs additionally reported",
                           "certificate_attribution": "checker acceptance and source-derived solver are separate from raw model accuracy",
                           "execution_attribution": "trusted grants protect every alternative route; catalog bypass and zero unauthorized effects are not model-only achievements",
                           "fault_scope": "finite scheduled eligible-mutation dispatches; untriggered faults reported separately",
                           "cost_scope": "usage_cost_upper_usd sums only supplied conservative usage bounds, not invoiced charges; missing coverage is explicit"}}
    return {"summary": summary, "candidate_scores": details, "case_scores": case_scores,
            "paired_details": representation_pairs + recovery_details + integrated_details,
            "execution_failures": _execution_failures(recovery, "recovery") + _execution_failures(integrated, "integrated")}

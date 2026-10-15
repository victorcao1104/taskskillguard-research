"""Offline planned-grid Phase5 analysis; no API access or sample execution."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
from itertools import combinations
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tsg.analysis_v4 import AXES, LABELS, grouped, metrics, protocol, protocol_summary, ratio, unique_index

VIEWS = ("table", "auto", "oracle", "shuffled", "length_control")
CONTRASTS = (("auto", "table"), ("oracle", "table"), ("shuffled", "table"),
             ("length_control", "table"), ("oracle", "length_control"), ("oracle", "auto"))
BOOT_METRICS = ("exact_accuracy", "known_truth_accuracy", "unknown_truth_accuracy")
META = ("case_id", "family", "split", "context", "model", "view", "replicate", "track")
REASONS = {"missing_scope", "dynamic_binding", "incomplete_reference_routes", "insufficient_effect_semantics",
           "unsupported_syntax", "shadowed_binding", "source_truncated", "unproved_triggering", "other_missing_evidence"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


def checked_protocol(job, observed):
    if observed is not None:
        parsed = observed.get("parsed")
        judgments = parsed.get("judgments", []) if isinstance(parsed, dict) else None
        if (not isinstance(judgments, list) or any(not isinstance(j, dict) for j in judgments)
                or any(not isinstance(j.get("candidate_id"), str) or any(not isinstance(j.get(a), str) for a in AXES) for j in judgments)):
            return {"status":"protocol_invalid", "valid":False, "by_id":{}, "diagnostics":["JUDGMENT_SHAPE_INVALID"]}
    result = protocol(job, observed)
    diagnostics = list(result["diagnostics"])
    if observed is not None:
        if any(observed.get(key) != job.get(key) for key in META):
            diagnostics.append("OBSERVATION_METADATA_MISMATCH")
        for judgment in (observed.get("parsed") or {}).get("judgments", []):
            unknowns = judgment.get("unknowns", [])
            if not isinstance(unknowns, list) or any(not isinstance(u, dict) for u in unknowns):
                diagnostics.append("UNKNOWN_RECORD_SHAPE_INVALID")
                continue
            axes = [u.get("dimension") for u in unknowns]
            if (any(not isinstance(a,str) for a in axes) or len(axes) != len(set(axes))
                    or set(axes) != {a for a in AXES if judgment.get(a) == "unknown"}):
                diagnostics.append("UNKNOWN_AXIS_COVERAGE_MISMATCH")
            if any(any(not isinstance(u.get(k), str) or not u[k].strip() for k in ("reason", "missing_evidence", "next_action")) for u in unknowns):
                diagnostics.append("EMPTY_UNKNOWN_EVIDENCE")
            if any(not isinstance(u.get("reason"),str) or u["reason"] not in REASONS for u in unknowns):
                diagnostics.append("UNKNOWN_REASON_INVALID")
    if diagnostics:
        result = {"status": "protocol_invalid", "valid": False, "by_id": {}, "diagnostics": sorted(set(diagnostics))}
    return result


def score_grid(jobs, observations, cases):
    planned = unique_index(jobs, "job_id")
    observed = unique_index(observations, "job_id")
    if set(observed) - set(planned):
        raise ValueError("UNPLANNED_OBSERVATION")
    gold = unique_index(cases, "case_id")
    rows, statuses = [], []
    for job in jobs:
        if job["case_id"] not in gold:
            raise ValueError("UNKNOWN_CASE")
        case = gold[job["case_id"]]
        context = job["context"]
        if context not in case["private"]["truth"]:
            raise ValueError("UNKNOWN_CONTEXT")
        truth = case["private"]["truth"][context]
        candidates = {n["id"] for n in case["public"]["canonical_nodes"] if n.get("candidate", True)}
        if (set(job["ids"]) != set(truth) or set(truth) != candidates or len(job["ids"]) != len(set(job["ids"]))
                or job["family"] != case["family"] or job["split"] != case["split"]):
            raise ValueError("INDEPENDENT_TRUTH_MAPPING_MISMATCH")
        result = checked_protocol(job, observed.get(job["job_id"]))
        base = {"job_id": job["job_id"], **{key: job.get(key) for key in META}}
        statuses.append({**base, **{key: result[key] for key in ("status", "valid", "diagnostics")}, "planned_candidates": len(truth)})
        for cid, target in truth.items():
            labels = target["labels"]
            if set(labels) != set(AXES) or not set(labels.values()) <= LABELS:
                raise ValueError("INVALID_GOLD_LABELS")
            prediction = result["by_id"].get(cid, {})
            gold_reasons = {u["dimension"]: u["reason"] for u in target["unknowns"]}
            unknowns = {u["dimension"]: u for u in prediction.get("unknowns", [])}
            for axis in AXES:
                u = unknowns.get(axis, {})
                rows.append({**base, "candidate_id": cid, "axis": axis, "gold": labels[axis],
                    "prediction": prediction.get(axis), "gold_reason": gold_reasons.get(axis),
                    "predicted_reason": u.get("reason"),
                    "evidence_fields_present": bool(u) and all(isinstance(u.get(k), str) and bool(u[k].strip()) for k in ("missing_evidence", "next_action")),
                    "protocol_status": result["status"],
                    "eligible": axis == "action_valid" or labels["action_valid"] != "no"})
    return rows, statuses


def metric_summary(rows):
    result = metrics(rows)
    eligible = [r for r in rows if r.get("eligible", True)]
    known = [r for r in eligible if r["gold"] != "unknown"]
    unknown = [r for r in eligible if r["gold"] == "unknown"]
    correct_unknown = [r for r in unknown if r["prediction"] == "unknown"]
    avoidable = sum(r["prediction"] == "unknown" for r in known)
    unsupported = sum(r["prediction"] in {"yes", "no"} for r in unknown)
    reason_correct = sum(r.get("predicted_reason") == r.get("gold_reason") and r.get("gold_reason") is not None for r in correct_unknown)
    return {**result, "avoidable_unknown_count": avoidable, "avoidable_unknown_rate_known": ratio(avoidable, len(known)),
            "unsupported_decision_count": unsupported, "unsupported_decision_rate_unknown": ratio(unsupported, len(unknown)),
            "unknown_reason_correct": reason_correct, "unknown_reason_accuracy_planned": ratio(reason_correct, len(unknown)),
            "unknown_reason_agreement_correct_unknown": ratio(reason_correct, len(correct_unknown)),
            "unknown_evidence_fields_present": sum(r.get("evidence_fields_present", False) for r in correct_unknown),
            "all_predicted_unknown_evidence_fields_present": sum(r.get("evidence_fields_present", False) for r in eligible if r["prediction"]=="unknown"),
            "unknown_evidence_presence_is_semantic_validity": False}


def pair_labels(rows, left, right):
    groups = defaultdict(dict)
    for row in rows:
        if row.get("replicate", 0) != 0 or row["view"] not in {left, right} or not row.get("eligible", True):
            continue
        key = tuple(row[k] for k in ("model", "case_id", "context", "candidate_id", "axis"))
        if row["view"] in groups[key]:
            raise ValueError("DUPLICATE_PAIRED_LABEL")
        groups[key][row["view"]] = row
    output = []
    for _, views in sorted(groups.items()):
        if set(views) != {left, right}:
            raise ValueError("UNPAIRED_PLANNED_LABEL")
        a, b = views[left], views[right]
        if any(a[k] != b[k] for k in ("gold", "family", "split")):
            raise ValueError("PAIRED_TRUTH_MISMATCH")
        output.append({**{k: a[k] for k in ("model", "case_id", "context", "candidate_id", "axis", "family", "split", "gold")},
                       "left_prediction": a["prediction"], "right_prediction": b["prediction"]})
    return output


def cluster_difference(rows, metric="exact_accuracy", replicates=2000, seed=76405):
    if metric not in BOOT_METRICS:
        raise ValueError("UNREGISTERED_BOOTSTRAP_METRIC")
    families = defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    names = sorted(families)
    totals = {}
    for family in names:
        selected = families[family]
        if metric == "known_truth_accuracy":
            selected = [r for r in selected if r["gold"] != "unknown"]
        elif metric == "unknown_truth_accuracy":
            selected = [r for r in selected if r["gold"] == "unknown"]
        totals[family] = (sum(r["left_prediction"] == r["gold"] for r in selected),
                          sum(r["right_prediction"] == r["gold"] for r in selected), len(selected))
    def diff(sample):
        denominator = sum(totals[f][2] for f in sample)
        return (sum(totals[f][0] for f in sample) - sum(totals[f][1] for f in sample)) / denominator if denominator else None
    rng = random.Random(seed)
    samples = [diff(rng.choices(names, k=len(names))) for _ in range(replicates)] if names else []
    valid = sorted(v for v in samples if v is not None)
    def percentile(q):
        if not valid:
            return None
        p = (len(valid) - 1) * q
        lo, hi = int(p), min(int(p) + 1, len(valid) - 1)
        return valid[lo] + (valid[hi] - valid[lo]) * (p - lo)
    individual = [diff([name]) for name in names]
    available = [v for v in individual if v is not None]
    return {"metric": metric, "difference_left_minus_right": diff(names),
            "family_macro_difference": ratio(sum(available), len(available)),
            "ci95_percentile": [percentile(.025), percentile(.975)],
            "families": len(names), "family_ids": names, "families_with_metric_denominator": len(available),
            "planned_paired_labels": len(rows), "family_label_counts": {n: len(families[n]) for n in names},
            "resampling_unit": "construction_family", "replicates": replicates, "valid_replicates": len(valid),
            "undefined_replicates": replicates - len(valid), "seed": seed,
            "multiplicity_adjusted": False,
            "caution": f"Finite panel of {len(names)} construction families; exploratory paired intervals, no multiplicity-adjusted superiority claim."}


def comparison_tables(rows, replicates=2000):
    output = []
    for left, right in CONTRASTS:
        paired = pair_labels(rows, left, right)
        for dimensions in (("model", "axis"), ("model", "split", "axis")):
            partitions = defaultdict(list)
            for row in paired:
                partitions[tuple(row[d] for d in dimensions)].append(row)
            for keys, group in sorted(partitions.items()):
                attrs = dict(zip(dimensions, keys))
                for metric in BOOT_METRICS:
                    output.append({"left": left, "right": right, "split": "all", **attrs,
                                   **cluster_difference(group, metric, replicates)})
    return output


def reliability(rows, statuses):
    groups = defaultdict(list)
    for status in statuses:
        key = tuple(status[k] for k in ("model", "case_id", "context", "view", "family", "split"))
        groups[key].append(status)
    scores = defaultdict(list)
    for row in rows:
        scores[row["job_id"]].append(row)
    records, axis_records = [], []
    for key, group in sorted(groups.items()):
        if not any(s["replicate"] > 0 for s in group):
            continue
        if {s["replicate"] for s in group} != {0, 1, 2} or len(group) != 3:
            raise ValueError("RELIABILITY_REPLICATE_GRID_MISMATCH")
        group.sort(key=lambda s: s["replicate"])
        vectors = {s["replicate"]: tuple((r["candidate_id"], r["axis"], r["prediction"]) for r in sorted(scores[s["job_id"]], key=lambda r: (r["candidate_id"], r["axis"]))) for s in group}
        available_pairs = [(a,b) for a,b in combinations(group,2) if a["valid"] and b["valid"]]
        agreed = sum(vectors[a["replicate"]] == vectors[b["replicate"]] for a,b in available_pairs)
        all_valid = all(s["valid"] for s in group)
        base = dict(zip(("model", "case_id", "context", "view", "family", "split"), key))
        records.append({**base, "planned_runs": 3, "valid_runs": sum(s["valid"] for s in group),
                        "missing_runs": sum(s["status"] == "missing" for s in group),
                        "invalid_runs": sum(s["status"] == "protocol_invalid" for s in group),
                        "all_valid": all_valid, "all_valid_consistent": all_valid and len(set(vectors.values())) == 1,
                        "planned_replicate_pairs": 3, "available_pairs": len(available_pairs), "agreeing_pairs": agreed})
        for axis in AXES:
            candidates = {r["candidate_id"] for r in scores[group[0]["job_id"]] if r["axis"] == axis}
            lookup = {(s["replicate"], r["candidate_id"]): r["prediction"] for s in group for r in scores[s["job_id"]] if r["axis"] == axis}
            for cid in sorted(candidates):
                values = [lookup[(s["replicate"],cid)] for s in group]
                valid_values = [v for v in values if v in LABELS]
                pairs = [(a,b) for a,b in combinations(values,2) if a in LABELS and b in LABELS]
                axis_records.append({**base, "axis":axis, "candidate_id":cid, "planned_runs":3,
                    "valid_runs":len(valid_values), "all_valid":len(valid_values)==3,
                    "all_valid_consistent":len(valid_values)==3 and len(set(values))==1,
                    "planned_replicate_pairs":3, "available_pairs":len(pairs),
                    "agreeing_pairs":sum(a==b for a,b in pairs)})
    def summarize(group):
        pairs = sum(g["available_pairs"] for g in group)
        agreeing = sum(g["agreeing_pairs"] for g in group)
        return {"planned_groups":len(group), "planned_runs":sum(g["planned_runs"] for g in group),
                "valid_runs":sum(g["valid_runs"] for g in group), "all_valid_groups":sum(g["all_valid"] for g in group),
                "all_valid_consistent_groups":sum(g["all_valid_consistent"] for g in group),
                "consistency_rate_planned":ratio(sum(g["all_valid_consistent"] for g in group),len(group)),
                "planned_replicate_pairs":sum(g["planned_replicate_pairs"] for g in group),
                "available_pairs":pairs, "agreeing_pairs":agreeing,
                "pair_agreement_planned":ratio(agreeing,sum(g["planned_replicate_pairs"] for g in group)),
                "available_pair_agreement":ratio(agreeing,pairs)}
    return {"scope":"Repeated responses on the same finite cases; repetitions are not independent tasks.",
            "overall":summarize(records), "groups":records, "by_model_view":grouped(records,("model","view"),summarize),
            "by_axis":grouped(axis_records,("model","view","axis"),summarize), "candidate_axis_groups":axis_records}


def symbolic_authorization(claim, grant):
    """Public structured claims/grants only; no private truth or source inference."""
    if claim.get("resource") is None or claim.get("resource_status") in {"dynamic", "unknown"}:
        return "unknown"
    if any(all(claim.get(k) == v for k,v in rule.items()) for rule in grant.get("rules",[])):
        return "yes"
    return "no" if grant.get("mode") == "closed_deny" else "unknown"


def symbolic_scores(cases):
    rows=[]
    for case in cases:
        for context,spec in case["public"]["contexts"].items():
            for node in case["public"]["canonical_nodes"]:
                if not node.get("candidate",True):
                    continue
                # Generate from public inputs before consulting private scoring data.
                prediction=symbolic_authorization(node["claim"],spec.get("grant",{}))
                gold=case["private"]["truth"][context][node["id"]]
                rows.append({"case_id":case["case_id"], "family":case["family"], "split":case["split"],
                             "context":context, "candidate_id":node["id"], "axis":"authorized",
                             "prediction":prediction, "gold":gold["labels"]["authorized"], "eligible":True})
    return {"scope":"Structured-candidate authorization baseline conditional on provided public claims/grants; not a raw-source competitor or necessity solver.",
            "overall":metrics(rows), "by_context":grouped(rows,("context",),metrics),
            "by_split":grouped(rows,("split",),metrics), "rows":rows}


def graph_audit(rows, raw_graphs):
    records=[]
    for row in rows:
        triples=lambda es:{(e["source"],e["target"],e["type"]) for e in es}
        actual,oracle=triples(row["auto_edges"]),triples(row["oracle_edges"])
        values={"true_positive":len(actual&oracle),"extra":len(actual-oracle),"missed":len(oracle-actual),
                "auto_count":len(actual),"oracle_count":len(oracle)}
        raw=raw_graphs.get(row["case_id"])
        records.append({**{k:row[k] for k in ("case_id","family","split")},**values,
            "precision":ratio(values["true_positive"],len(actual)),"recall":ratio(values["true_positive"],len(oracle)),
            "stored_counts_match":all(row.get(k)==v for k,v in values.items()),
            "auto_type_counts":dict(sorted(Counter(e[2] for e in actual).items())),
            "oracle_type_counts":dict(sorted(Counter(e[2] for e in oracle).items())),
            "true_positive_type_counts":dict(sorted(Counter(e[2] for e in actual&oracle).items())),
            "raw_graph_available":raw is not None,
            "raw_extractor_nodes":len(raw["nodes"]) if raw else None,
            "raw_extractor_edges":len(raw["edges"]) if raw else None,
            "raw_extractor_dependency_edges":sum(e["type"] in {"DATA","CONDITION","CALL"} for e in raw["edges"]) if raw else None,
            "raw_extractor_type_counts":dict(sorted(Counter(e["type"] for e in raw["edges"]).items())) if raw else None})
    def summarize(group):
        totals={k:sum(r[k] for r in group) for k in ("true_positive","extra","missed","auto_count","oracle_count")}
        return {"cases":len(group),**totals,"precision":ratio(totals["true_positive"],totals["auto_count"]),
                "recall":ratio(totals["true_positive"],totals["oracle_count"]),
                "raw_graphs_available":sum(r["raw_graph_available"] for r in group),
                "raw_dependency_edges":sum(r["raw_extractor_dependency_edges"] or 0 for r in group),
                "mapped_canonical_edges":totals["auto_count"],
                "auto_type_counts":dict(sorted(sum((Counter(r["auto_type_counts"]) for r in group),Counter()).items())),
                "oracle_type_counts":dict(sorted(sum((Counter(r["oracle_type_counts"]) for r in group),Counter()).items()))}
    return {"scope":"Source relation correctness against independent oracle; projection count is distinct from raw extractor edge count.",
            "overall":summarize(records),"by_split":grouped(records,("split",),summarize),"cases":records}


def token_audit(jobs, observations, controls):
    obs=unique_index(observations,"job_id")
    local={(c["case_id"],c["context"]):c for c in controls}
    groups=defaultdict(dict)
    for job in jobs:
        if job["replicate"]==0 and job["view"] in {"oracle","length_control"}:
            key=(job["case_id"],job["context"],job["model"])
            groups[key][job["view"]]=job
    pairs=[]
    for key,views in sorted(groups.items()):
        control=local.get(key[:2],{})
        lengths=control.get("local_tokens",{})
        values={v:(obs.get(j["job_id"],{}).get("usage") or {}).get("input_tokens") for v,j in views.items()}
        a,b=values.get("oracle"),values.get("length_control")
        available=type(a) is int and type(b) is int
        la,lb=lengths.get("oracle"),lengths.get("length_control")
        pairs.append({"case_id":key[0],"context":key[1],"model":key[2],"planned_pair_complete":set(views)=={"oracle","length_control"},
            "base_equal_recorded":control.get("base_equal"),"local_oracle_tokens":la,"local_control_tokens":lb,
            "local_equal":la==lb if la is not None and lb is not None else None,
            "actual_oracle_input_tokens":a,"actual_control_input_tokens":b,"actual_pair_available":available,
            "actual_oracle_minus_control":a-b if available else None,"actual_equal":a==b if available else None})
    def summarize(group):
        diffs=[r["actual_oracle_minus_control"] for r in group if r["actual_pair_available"]]
        return {"planned_pairs":len(group),"local_equal_pairs":sum(r["local_equal"] is True for r in group),
                "actual_available_pairs":len(diffs),"actual_equal_pairs":sum(d==0 for d in diffs),
                "mean_actual_input_difference":ratio(sum(diffs),len(diffs)),
                "actual_difference_range":[min(diffs),max(diffs)] if diffs else [None,None]}
    return {"scope":"Local prompt token control versus observed API input usage, including schema/system overhead; not an invoice audit or output-token control.",
            "overall":summarize(pairs),"by_model":grouped(pairs,("model",),summarize),"pairs":pairs}


def publish_package(out, package):
    out=Path(out)
    if out.exists():
        raise FileExistsError(f"CREATE_ONLY_OUTPUT_EXISTS: {out}")
    encoded={}
    for name,value in package.items():
        if Path(name).name != name or not name.endswith((".json",".jsonl")):
            raise ValueError("INVALID_OUTPUT_FILENAME")
        if name.endswith(".jsonl"):
            data="".join(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n" for r in value)
        else:
            data=json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
        encoded[name]=data.encode("utf-8")
    out.mkdir(parents=True,exist_ok=False)
    for name,data in sorted(encoded.items()):
        with (out/name).open("xb") as stream:
            stream.write(data)


def validate_grid(jobs, cases, expected_jobs=588):
    unique_index(jobs,"job_id")
    unique_index(cases,"case_id")
    conditions=[tuple(j[k] for k in ("case_id","context","view","model","replicate")) for j in jobs]
    if len(conditions)!=len(set(conditions)):
        raise ValueError("DUPLICATE_PLANNED_CONDITION")
    if any(j["replicate"] not in (0,1,2) or j["view"] not in VIEWS or j["track"]!="synthetic" for j in jobs):
        raise ValueError("INVALID_PLANNED_CONDITION")
    if expected_jobs is None:
        return
    if len(jobs)!=expected_jobs:
        raise ValueError(f"PLANNED_GRID_SIZE_MISMATCH: expected {expected_jobs}, got {len(jobs)}")
    if len(cases)!=18 or len({c["family"] for c in cases})!=18:
        raise ValueError("FAMILY_GRID_MISMATCH")
    models=sorted({j["model"] for j in jobs})
    if len(models)!=2:
        raise ValueError("MODEL_GRID_MISMATCH")
    expected={(c["case_id"],ctx,view,m,0) for c in cases for ctx in ("allow","deny","missing") for view in VIEWS for m in models}
    if {c for c in conditions if c[-1]==0}!=expected:
        raise ValueError("MAIN_GRID_MISMATCH")
    additional=[j for j in jobs if j["replicate"]>0]
    selected=defaultdict(set)
    for j in additional:
        if j["view"] not in {"table","oracle"}:
            raise ValueError("REPEAT_VIEW_MISMATCH")
        selected[j["case_id"]].add(j["context"])
    if (len(additional)!=48 or len(selected)!=6 or any(len(v)!=1 for v in selected.values())
            or Counter(next(iter(v)) for v in selected.values())!={"allow":2,"deny":2,"missing":2}):
        raise ValueError("REPEAT_PANEL_MISMATCH")
    expected_repeat={(cid,next(iter(ctxs)),v,m,r) for cid,ctxs in selected.items()
                     for v in ("table","oracle") for m in models for r in (1,2)}
    if {c for c in conditions if c[-1]>0}!=expected_repeat:
        raise ValueError("REPEAT_CONDITIONS_MISMATCH")


def payload_controls(jobs):
    groups=defaultdict(list)
    for job in jobs:
        if job["replicate"]==0:
            groups[(job["case_id"],job["context"],job["model"])].append(job)
    records=[]
    for key,group in sorted(groups.items()):
        available=all("prompt" in j for j in group)
        bases=[]
        if available:
            for job in group:
                value=json.loads(job["prompt"])
                value.pop("edge_attachment",None)
                bases.append(value)
        records.append({"case_id":key[0],"context":key[1],"model":key[2],
            "five_views_present":{j["view"] for j in group}==set(VIEWS),
            "payloads_available":available,
            "base_equal":bool(bases) and all(value==bases[0] for value in bases),
            "ids_equal":all(j["ids"]==group[0]["ids"] for j in group)})
    return records


def q017_sensitivity(main_rows, main_status, cases, replicates):
    kept=[r for r in main_rows if r["case_id"]!="q017"]
    status=[s for s in main_status if s["case_id"]!="q017"]
    remaining=[c for c in cases if c["case_id"]!="q017"]
    tables={name:grouped(kept,dims,metric_summary) for name,dims in (
        ("overall_by_axis",("axis",)),
        ("by_model_view_axis",("model","view","axis")),
        ("by_model_view_context_axis",("model","view","context","axis")),
        ("by_model_view_split_axis",("model","view","split","axis")),
        ("by_model_view_context_split_axis",("model","view","context","split","axis")))}
    summary={"analysis":"source-ambiguity sensitivity, not replacement of frozen primary",
        "registration":"docs/phase5_truth_erratum.md; source-only review before analyst viewed model outcomes",
        "excluded_case_ids":["q017"],"excluded_family_present":any(c["case_id"]=="q017" for c in cases),
        "families":len({c["family"] for c in remaining}),"families_by_split":dict(sorted(Counter(c["split"] for c in remaining).items())),
        "main_labels":len(kept),"main_protocol":protocol_summary(status),"synthetic":tables,
        "unknown_by_reason":grouped([r for r in kept if r["gold"]=="unknown"],("model","view","axis","gold_reason"),metric_summary),
        "limitation":"Excluding q017 removes the only insufficient_effect_semantics unknown family. This sensitivity cannot assess that reason; primary truth/rows remain unchanged."}
    return summary,comparison_tables(kept,replicates)


def analyze_inputs(jobs, observations, cases, edges, controls, raw_graphs, *, replicates=2000, expected_jobs=588):
    validate_grid(jobs,cases,expected_jobs)
    rows,statuses=score_grid(jobs,observations,cases)
    base_checks=payload_controls(jobs)
    if expected_jobs is not None and any(not all(c[k] for k in ("five_views_present","payloads_available","base_equal","ids_equal")) for c in base_checks):
        raise ValueError("MATCHED_PAYLOAD_CONTROL_FAILED")
    if edges:
        edge_index=unique_index(edges,"case_id")
        case_index=unique_index(cases,"case_id")
        if set(edge_index)!=set(case_index):
            raise ValueError("GRAPH_AUDIT_CASE_GRID_MISMATCH")
        for cid,audit in edge_index.items():
            triple=lambda es:{(e["source"],e["target"],e["type"]) for e in es}
            if triple(audit["oracle_edges"])!=triple(case_index[cid]["private"]["oracle_edges"]):
                raise ValueError("GRAPH_AUDIT_ORACLE_MISMATCH")
    elif expected_jobs is not None:
        raise ValueError("MISSING_GRAPH_AUDIT")
    main_rows=[r for r in rows if r["replicate"]==0]
    repeat_rows=[r for r in rows if r["replicate"]>0]
    main_status=[s for s in statuses if s["replicate"]==0]
    repeat_status=[s for s in statuses if s["replicate"]>0]
    metrics_groups={name:grouped(main_rows,dims,metric_summary) for name,dims in (
        ("overall_by_axis",("axis",)),
        ("by_model_view_axis",("model","view","axis")),
        ("by_model_view_context_axis",("model","view","context","axis")),
        ("by_model_view_split_axis",("model","view","split","axis")),
        ("by_model_view_context_split_axis",("model","view","context","split","axis")))}
    unknown_rows=[r for r in main_rows if r["gold"]=="unknown"]
    usage={key:sum((o.get("usage") or {}).get(key,0) or 0 for o in observations) for key in ("input_tokens","output_tokens","total_tokens")}
    main_observed={s["job_id"] for s in main_status if s["status"]!="missing"}
    summary={"schema_version":"phase5-analysis-v1","analysis_unit":"construction_family",
        "planned_jobs":len(jobs),"observed_jobs":len(observations),"main_jobs":len(main_status),"repeat_jobs":len(repeat_status),
        "complete_observation_grid":len(observations)==len(jobs),"main_complete_observation_grid":len(main_observed)==len(main_status),
        "main_replicate":0,"bootstrap_replicates":replicates,"usage_all_jobs":usage,
        "main_protocol":{"overall":protocol_summary(main_status),
            "by_model_view":grouped(main_status,("model","view"),protocol_summary),
            "by_model_view_context":grouped(main_status,("model","view","context"),protocol_summary),
            "by_model_view_split":grouped(main_status,("model","view","split"),protocol_summary),
            "by_model_view_context_split":grouped(main_status,("model","view","context","split"),protocol_summary)},
        "additional_repeat_protocol":protocol_summary(repeat_status),"synthetic":metrics_groups,
        "unknown_by_reason":grouped(unknown_rows,("model","view","axis","gold_reason"),metric_summary),
        "interpretation":{"independent_families":len({c["family"] for c in cases}),
            "families_by_split":dict(sorted(Counter(c["split"] for c in cases).items())),
            "truth":"independent literal active v2 source/finite specification",
            "implementation_estimand":"finite complete-expression intervention, not strict manual source deletion",
            "task_estimand":"finite permitted task routes under fixed capability assumptions, independent of execution grant",
            "missing_invalid_in_planned_denominator":True,"real_corpus_human_accuracy_available":False,
            "multiplicity_adjusted":False,"repetitions_are_independent_tasks":False}}
    summary["source_specification_caveats"]=[]
    package={"summary.json":summary,"label_scores.jsonl":main_rows,"repeat_label_scores.jsonl":repeat_rows,
            "protocol_jobs.jsonl":statuses,"paired_comparisons.jsonl":comparison_tables(main_rows,replicates),
            "payload_controls.jsonl":base_checks,"graph_audit.json":graph_audit(edges,raw_graphs),
            "token_control.json":token_audit(jobs,observations,controls),"reliability.json":reliability(rows,statuses),
            "symbolic_authorization.json":symbolic_scores(cases)}
    if any(c["case_id"]=="q017" for c in cases):
        sensitivity,sensitivity_comparisons=q017_sensitivity(main_rows,main_status,cases,replicates)
        summary["source_specification_caveats"].append({"case_id":"q017","reason":"literal UNSPECIFIED conflicts with intended abstract missing contract",
            "primary_preserved":True,"sensitivity":"sensitivity_q017_excluded.json","erratum":"docs/phase5_truth_erratum.md"})
        package.update({"sensitivity_q017_excluded.json":sensitivity,"sensitivity_q017_paired_comparisons.jsonl":sensitivity_comparisons})
    return package


def historical_context(root):
    path=Path(root)/"results/phase4/analysis/summary.json"
    result={"available":path.is_file(),"comparison_kind":"historical descriptive context only",
            "caution":"New families, scope-boundary variants, views, public/private separation, and finite-intervention estimands differ. These are not causal before/after accuracy estimates; no cross-phase difference or significance test is computed."}
    if path.is_file():
        data=json.loads(path.read_text(encoding="utf-8"))
        result.update(source="results/phase4/analysis/summary.json",source_sha256=sha(path.read_bytes()),
            phase4_schema=data.get("schema_version"),phase4_interpretation=data.get("interpretation"),
            phase4_metrics={key:deepcopy(data.get("synthetic",{}).get(key)) for key in ("overall_by_axis","by_model_view_axis","by_model_view_split_axis")})
    return result


def publish(root=ROOT, out=None, *, acquisition="results/phase5/acquisition_v2", replicates=2000):
    root=Path(root).resolve()
    out=Path(out).resolve() if out is not None else root/"results/phase5/analysis"
    if out.exists():
        raise FileExistsError(f"CREATE_ONLY_OUTPUT_EXISTS: {out}")
    acq=root/acquisition
    paths={"jobs":acq/"jobs.jsonl","manifest":acq/"manifest.json","edge_audit":acq/"edge_audit.jsonl",
           "controls":acq/"controls.jsonl","truth":root/"data/phase5/reasoning_cases_v2.jsonl",
           "analysis_plan":root/"docs/phase5_analysis_plan.md","analyzer":Path(__file__).resolve()}
    erratum=root/"docs/phase5_truth_erratum.md"
    if erratum.is_file():
        paths["source_erratum_and_sensitivity_registration"]=erratum
    jobs=read_rows(paths["jobs"])
    manifest=json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if manifest.get("planned_jobs")!=588 or manifest.get("jobs_sha256")!=sha(paths["jobs"].read_bytes()):
        raise ValueError("ACQUISITION_MANIFEST_GRID_HASH_MISMATCH")
    truth_key="data/phase5/reasoning_cases_v2.jsonl"
    if manifest.get("source_sha256",{}).get(truth_key)!=sha(paths["truth"].read_bytes()):
        raise ValueError("ACTIVE_TRUTH_HASH_MISMATCH")
    aggregate=root/"results/phase5/api/observations.jsonl"
    individual=sorted((root/"results/phase5/api/jobs").glob("*.json"))
    if aggregate.is_file():
        observations=read_rows(aggregate)
        paths["observations"]=aggregate
        # If both representations exist, they must describe the same saved rows.
        indexed=unique_index(observations,"job_id")
        for path in individual:
            row=json.loads(path.read_text(encoding="utf-8"))
            if indexed.get(row.get("job_id"))!=row:
                raise ValueError("OBSERVATION_AGGREGATE_CONFLICT")
    else:
        observations=[json.loads(path.read_text(encoding="utf-8")) for path in individual]
    for path in individual:
        paths["job:"+path.name]=path
    cases=read_rows(paths["truth"])
    graph_paths={case["case_id"]:root/f'results/phase5/reasoning_graphs/{case["case_id"]}.json' for case in cases}
    raw={cid:json.loads(path.read_text(encoding="utf-8")) for cid,path in graph_paths.items() if path.is_file()}
    paths.update({"raw_graph:"+cid:path for cid,path in graph_paths.items() if path.is_file()})
    package=analyze_inputs(jobs,observations,cases,read_rows(paths["edge_audit"]),read_rows(paths["controls"]),raw,replicates=replicates)
    package["historical_context.json"]=historical_context(root)
    package["provenance.json"]={"acquisition_directory":acquisition,"active_truth":truth_key,
        "input_sha256":{name:sha(path.read_bytes()) for name,path in sorted(paths.items())},
        "input_paths":{name:str(path.relative_to(root)).replace('\\','/') if path.is_relative_to(root) else str(path) for name,path in sorted(paths.items())},
        "observations_source":"aggregate_crosschecked_with_saved_jobs" if aggregate.is_file() else "saved_individual_jobs_with_missing_retained",
        "analysis_parameters":{"bootstrap_replicates":replicates,"seed":76405,"main_replicate":0},
        "publication":"deterministic create-only; no timestamps or API calls"}
    publish_package(out,package)
    return out


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--out",type=Path)
    parser.add_argument("--acquisition",default="results/phase5/acquisition_v2")
    args=parser.parse_args()
    print(publish(args.root,args.out,acquisition=args.acquisition))

"""Offline Phase 4 evidence audit. No API, Docker, corpus imports or worker exec.

Default verification uses only repository artifacts and works on Linux. Original
external corpus bytes are optional (--verify-corpus, optionally --corpus-root).
Hashes establish consistency with the preserved manifests, not signatures or
provider invoices. Runtime re-scoring trusts the archived finite worker receipts;
it cannot retrospectively prove Docker isolation or human semantic accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BASELINE = "a666de55206ece2dcdbb669d083aa175a50dea5a"
IMAGE = "sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244"


class ReleaseError(ValueError):
    """A release invariant failed; messages contain identifiers, never secrets."""


def require(condition, code, identifier=""):
    if not condition:
        raise ReleaseError(code + (": " + str(identifier) if identifier else ""))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def decode(text):
    def invalid(_):
        raise ReleaseError("NONFINITE_JSON_NUMBER")
    try:
        return json.loads(text, object_pairs_hook=_object, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseError("INVALID_JSON") from error


def read_json(path):
    return decode(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    data = Path(path).read_text(encoding="utf-8")
    require(not data or data.endswith("\n"), "INCOMPLETE_JSONL", Path(path).name)
    return [decode(line) for line in data.splitlines() if line.strip()]


def safe_path(root, relative):
    require(isinstance(relative, str) and relative and "\\" not in relative
            and not PurePosixPath(relative).is_absolute()
            and not PureWindowsPath(relative).drive
            and ".." not in PurePosixPath(relative).parts, "UNSAFE_PATH", relative)
    root = Path(root).resolve()
    result = (root / relative).resolve()
    require(result.is_relative_to(root), "UNSAFE_PATH", relative)
    return result


def verify_hashes(root, hashes, expected_count=None):
    require(isinstance(hashes, dict), "INVALID_HASH_MANIFEST")
    if expected_count is not None:
        require(len(hashes) == expected_count, "HASH_COUNT_MISMATCH")
    for relative, digest in hashes.items():
        path = safe_path(root, relative)
        require(isinstance(digest, str) and re.fullmatch("[0-9a-f]{64}", digest), "INVALID_HASH", relative)
        require(path.is_file(), "MISSING_HASHED_FILE", relative)
        require(sha(path.read_bytes()) == digest, "HASH_MISMATCH", relative)
    return len(hashes)


def index(rows, field):
    result = {}
    for row in rows:
        value = row[field]
        require(value not in result, "DUPLICATE_RECORD", field)
        result[value] = row
    return result


def no_human_truth(value):
    """Reject positive human-ground-truth flags, while allowing synthetic gold."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"human_accuracy_available", "human_annotated", "semantic_accuracy_available"}:
                require(child is False, "UNSUPPORTED_HUMAN_TRUTH", key)
            if key in {"human_labels", "human_annotations"}:
                require(child in (0, None, []), "UNSUPPORTED_HUMAN_TRUTH", key)
            if key == "human_accuracy":
                require(child is None, "UNSUPPORTED_HUMAN_TRUTH", key)
            no_human_truth(child)
    elif isinstance(value, list):
        for child in value:
            no_human_truth(child)


def verify_approved_sources(approved, prepared, expected_count=180):
    original, current = index(approved, "skill_id"), index(prepared, "skill_id")
    require(len(original) == len(current) == expected_count and set(original) == set(current),
            "APPROVED_BUNDLE_COUNT_MISMATCH")
    for identifier, row in current.items():
        require(row["files"] == original[identifier]["files"], "UNAPPROVED_SOURCE", identifier)
        files = row["files"]
        require(isinstance(files, dict) and len(files) <= 12
                and all(isinstance(k, str) and isinstance(v, str) for k, v in files.items())
                and sum(len(v) for v in files.values()) <= 24000, "SOURCE_BOUND_EXCEEDED", identifier)
    return len(current)


def request_for(job):
    from tsg.models import make_request
    request = make_request(job["model"], job["system"], job["prompt"], job["max_output"])
    request["text"]["format"] = {"type": "json_schema", "name": "tsg_response_v3",
                                  "strict": True, "schema": deepcopy(job["schema"])}
    return request


def verify_request(job):
    from tsg.budget_v4 import UPPER_PRICES
    request = request_for(job)
    fingerprint = sha(json.dumps({"request": request, "replicate": 0}, sort_keys=True,
                                  ensure_ascii=False).encode("utf-8"))
    require(fingerprint == job["expected_request_hash"], "REQUEST_HASH_MISMATCH", job["job_id"])
    upper = len(json.dumps(request, ensure_ascii=False).encode("utf-8")) + 4096
    require(upper <= 272000, "INPUT_PRICE_BOUND_EXCEEDED", job["job_id"])
    require(job["model"] in UPPER_PRICES, "UNAUTHORIZED_MODEL")
    ip, op = UPPER_PRICES[job["model"]]
    expected_cost = (upper * ip + job["max_output"] * op) / 1e6
    require(math.isclose(expected_cost, job["reservation_upper_usd"], abs_tol=1e-12),
            "RESERVATION_BOUND_MISMATCH", job["job_id"])
    require(request.get("store") is False and not request.get("tools"), "UNEXPECTED_REQUEST_CAPABILITY")
    return request


def verify_matched_views(jobs):
    groups = defaultdict(dict)
    for job in jobs:
        if job["track"] == "discovery":
            continue
        key = tuple(job[k] for k in ("track", "case_id", "context", "model"))
        require(job["view"] not in groups[key], "DUPLICATE_VIEW")
        groups[key][job["view"]] = job
    for key, group in groups.items():
        require(set(group) == {"raw", "table", "graph"}, "MISSING_MATCHED_VIEW", key)
        raw, table, graph = [decode(group[v]["prompt"]) for v in ("raw", "table", "graph")]
        require("edges" in graph and isinstance(graph.pop("edges"), list), "MISSING_GRAPH_EDGES", key)
        require(graph == table, "MATCHED_VIEW_MISMATCH", key)
        require("nodes" in table, "MISSING_NODE_TABLE", key)
        table.pop("nodes")
        require(table == raw, "MATCHED_VIEW_MISMATCH", key)
        require(group["raw"]["ids"] == group["table"]["ids"] == group["graph"]["ids"],
                "MATCHED_ID_MISMATCH", key)
    return len(groups)


def verify_saved_observation(job, raw, saved, *, parser_module=None, files=None):
    """Reparse the archived response; never accept persisted protocol booleans."""
    request = verify_request(job)
    require(raw["request"] == request and raw["request_hash"] == job["expected_request_hash"]
            and raw["replicate"] == 0 and raw["tag"] == job["job_id"], "RAW_REQUEST_MISMATCH", job["job_id"])
    if files is None:
        files = decode(job["prompt"])["source"]
    if parser_module is None:
        parser_module = "tsg.discovery_v4" if job["track"] == "discovery" else "tsg.reasoning_v4"
    parser = importlib.import_module(parser_module)
    parsed = parser.parse_record(raw, files if "discovery" in parser_module else job["ids"])
    require(saved["parsed"] == parsed, "REPARSE_MISMATCH", job["job_id"])
    require(saved["request_hash"] == job["expected_request_hash"] and saved["job_id"] == job["job_id"],
            "SAVED_JOB_ID_MISMATCH", job["job_id"])
    require(saved["raw_status"] == raw["status"] and saved.get("usage") == raw.get("usage")
            and saved.get("elapsed_seconds") == raw.get("elapsed_seconds"), "SAVED_RAW_METADATA_MISMATCH", job["job_id"])
    for key in ("track", "case_id", "family", "split", "context", "view", "model"):
        if key in job:
            require(saved.get(key) == job[key], "SAVED_JOB_METADATA_MISMATCH", key)
    no_human_truth(parsed)
    return parsed


def _verify_blinding(job, case):
    payload, mapping = decode(job["prompt"]), job["candidate_id_mapping"]
    require(mapping == {c["id"]: "c_" + sha((case["case_id"] + ":" + c["id"]).encode())[:16]
                        for c in case["candidates"]}, "BLINDING_MAP_MISMATCH")
    require(job["ids"] == [mapping[c["id"]] for c in case["candidates"]], "BLINDED_ID_MISMATCH")
    require("truth" not in payload and "candidate_id_mapping" not in payload, "TRUTH_LEAK")
    require(payload["source"] == case["files"], "SYNTHETIC_SOURCE_MISMATCH")
    for before, after in zip(case["candidates"], payload["candidates"], strict=True):
        require(after == {**before, "id": mapping[before["id"]]}, "BLINDED_CANDIDATE_MISMATCH")
    expected = deepcopy(case["task_context"])
    for key in ("plans", "implementation_plans"):
        for i, plan in enumerate(expected.get("finite_model", {}).get(key) or []):
            plan["effects"] = [mapping.get(e, e) for e in plan["effects"]]
            plan["id"] = "p_" + sha((case["case_id"] + ":" + key + ":" + str(i)).encode())[:12]
    from tsg.reasoning_v4 import _task_context
    require(payload["task_context"] == _task_context(expected), "BLINDED_CONTEXT_MISMATCH")


def verify_acquisition(root, approved):
    base = Path(root) / "results/phase4/acquisition"
    manifest, jobs = read_json(base / "manifest.json"), read_rows(base / "jobs.jsonl")
    require(manifest["planned_jobs"] == len(jobs) == 384, "PRIMARY_GRID_COUNT_MISMATCH")
    require(sha((base / "jobs.jsonl").read_bytes()) == manifest["jobs_sha256"], "JOBS_HASH_MISMATCH")
    verify_hashes(root, manifest["source_sha256"])
    require(len(index(jobs, "job_id")) == len(index(jobs, "expected_request_hash")) == 384, "DUPLICATE_REQUEST")
    require(manifest["request_hashes_unique"] == 384 and manifest["automatic_retries"] == 0,
            "ACQUISITION_PROTOCOL_MISMATCH")
    require(Counter(j["track"] for j in jobs) == manifest["track_counts"] == {"synthetic": 144, "real": 216, "discovery": 24},
            "TRACK_COUNT_MISMATCH")
    require(read_rows(base / "grid.jsonl") == [{k: v for k, v in j.items() if k not in {"system", "prompt", "schema"}}
                                             for j in jobs], "FROZEN_GRID_MISMATCH")
    cases = index(read_rows(Path(root) / "data/phase4/reasoning_cases.jsonl"), "case_id")
    raw_dir, saved_dir = Path(root) / "results/phase4/api/raw", Path(root) / "results/phase4/api/jobs"
    require({p.name for p in raw_dir.glob("*.json")} == {j["expected_request_hash"] + ".json" for j in jobs}, "RAW_GRID_INCOMPLETE")
    require({p.name for p in saved_dir.glob("*.json")} == {j["job_id"] + ".json" for j in jobs}, "JOB_GRID_INCOMPLETE")
    reservations, observations = {}, []
    for job in jobs:
        verify_request(job)
        payload = decode(job["prompt"])
        files = payload["source"]
        require(len(files) <= 12 and sum(map(len, files.values())) <= 24000, "SOURCE_BOUND_EXCEEDED")
        require(payload["source_sha256"] == {k: sha(v.encode("utf-8")) for k, v in files.items()}, "PAYLOAD_SOURCE_HASH_MISMATCH")
        if job["track"] in {"real", "discovery"}:
            require(files == approved[job["case_id"]]["files"], "UNAPPROVED_SOURCE", job["case_id"])
        else:
            _verify_blinding(job, cases[job["case_id"]])
        raw = read_json(raw_dir / (job["expected_request_hash"] + ".json"))
        saved = read_json(saved_dir / (job["job_id"] + ".json"))
        verify_saved_observation(job, raw, saved)
        require(saved["raw_ref"] == "results/phase4/api/raw/" + job["expected_request_hash"] + ".json", "RAW_REFERENCE_MISMATCH")
        require(raw["reservation_id"] not in reservations, "DUPLICATE_RESERVATION")
        reservations[raw["reservation_id"]] = {"job": job, "raw": raw}
        observations.append(saved)
    count = verify_matched_views(jobs)
    require(count == 120, "MATCHED_PAIR_COUNT_MISMATCH")
    require(read_rows(Path(root) / "results/phase4/api/observations.jsonl") == sorted(observations, key=lambda r: r["job_id"]),
            "CONSOLIDATED_OBSERVATIONS_MISMATCH")
    require(math.isclose(sum(j["reservation_upper_usd"] for j in jobs), manifest["additional_reservation_upper_usd"], abs_tol=1e-10),
            "GRID_RESERVATION_SUM_MISMATCH")
    summary = read_json(Path(root) / "results/phase4/api/summary.json")
    require(summary["planned"] == summary["completed"] == 384 and summary["protocol_valid"] == sum(o["parsed"]["protocol_valid"] for o in observations)
            and summary["raw_statuses"] == Counter(o["raw_status"] for o in observations), "ACQUISITION_SUMMARY_MISMATCH")
    return {"jobs": jobs, "observations": observations, "reservations": reservations, "manifest": manifest,
            "summary": summary, "matched_groups": count}


def audit_ledger(prefix, data, reservations, base, limit):
    from tsg.budget_v4 import UPPER_PRICES
    require(data.startswith(prefix), "BUDGET_PREFIX_MISMATCH")
    require(data.endswith(b"\n"), "INCOMPLETE_BUDGET_LEDGER")
    historical = [decode(x) for x in prefix.decode("utf-8").splitlines()]
    inherited = index([], "reservation_id")
    for record in historical:
        inherited[record["reservation_id"]] = record
    require(math.isclose(sum(r.get("cost_usd", r["reserved_usd"]) for r in inherited.values()), base, abs_tol=1e-9),
            "INHERITED_BUDGET_MISMATCH")
    grouped = defaultdict(list)
    timeline, exposure = {}, base
    for line in data[len(prefix):].decode("utf-8").splitlines():
        row = decode(line)
        require(row["reservation_id"] not in inherited, "HISTORICAL_RESERVATION_CHANGED")
        grouped[row["reservation_id"]].append(row)
        exposure -= timeline.get(row["reservation_id"], 0)
        timeline[row["reservation_id"]] = row.get("cost_usd", row["reserved_usd"])
        exposure += timeline[row["reservation_id"]]
        require(exposure <= limit + 1e-9, "HISTORICAL_BUDGET_CAP_EXCEEDED")
    require(set(grouped) == set(reservations), "UNREGISTERED_OR_MISSING_BUDGET_RESERVATION")
    costs = {}
    for rid, records in grouped.items():
        job, raw = reservations[rid]["job"], reservations[rid]["raw"]
        first, last = records[0], records[-1]
        require(first["status"] == "reserved" and first["model"] == job["model"]
                and math.isclose(first["reserved_usd"], job["reservation_upper_usd"], abs_tol=1e-12), "RESERVATION_RECORD_MISMATCH", rid)
        require(len(records) in {1, 2} and all(r["model"] == first["model"] and r["reserved_usd"] == first["reserved_usd"] for r in records),
                "INVALID_RESERVATION_HISTORY", rid)
        require(last["status"] in {"reserved", "settled", "unknown_usage"}, "INVALID_BUDGET_STATUS")
        require(len(records) == (1 if last["status"] == "reserved" else 2), "INVALID_RESERVATION_HISTORY", rid)
        if last["status"] == "settled":
            usage = last["usage"]
            require(usage == raw.get("usage") and all(type(usage.get(k)) is int and usage[k] >= 0 for k in ("input_tokens", "output_tokens")),
                    "SETTLED_USAGE_MISMATCH", rid)
            ip, op = UPPER_PRICES[job["model"]]
            cost = (usage["input_tokens"] * ip + usage["output_tokens"] * op) / 1e6
            require(math.isclose(cost, last["cost_usd"], abs_tol=1e-12) and cost <= first["reserved_usd"] + 1e-12,
                    "SETTLED_COST_MISMATCH", rid)
        else:
            require("cost_usd" not in last, "UNKNOWN_USAGE_DISCOUNTED", rid)
            cost = last["reserved_usd"]
        costs[rid] = cost
    total = base + sum(costs.values())
    require(total <= limit + 1e-9 and total - base <= 15 + 1e-9, "BUDGET_CAP_EXCEEDED")
    return total, costs


def verify_replay_record(frozen_job, saved, stdout, worker):
    from tsg import replay_v4 as replay
    job = {k: v for k, v in frozen_job.items() if k != "worker_sha256"}
    expected_worker = replay.worker_source(job)
    digest = sha(expected_worker.encode("utf-8"))
    require(worker == expected_worker and digest == frozen_job["worker_sha256"], "WORKER_SOURCE_MISMATCH", job["run_id"])
    missing = job["route"] == "reference" and job["case"]["reference_route"] == "missing"
    if missing:
        expected_missing = {"status": "missing_reference", "reference_valid": False, "GoalSat": None,
                            "CorePres": None, "execution_evidence_status": "not_executed", "safety_evidence": None,
                            "opportunities": {"planned": 0, "reached": 0, "denied": 0, "executed": 0},
                            "planned_effects": replay.planned_effects(job["case"], "reference"), "route": "reference"}
        require(saved == expected_missing and not stdout, "MISSING_REFERENCE_EVIDENCE_MISMATCH")
        return
    require(saved["worker_sha256"] == digest and saved["image_id"] == IMAGE == replay.PINNED_IMAGE, "RUNTIME_IDENTITY_MISMATCH")
    arguments = saved["docker_arguments"]
    require(isinstance(arguments, list) and "--name" in arguments, "ISOLATION_COMMAND_MISMATCH")
    name = arguments[arguments.index("--name") + 1]
    require(arguments[1:] == replay.docker_arguments(name), "ISOLATION_COMMAND_MISMATCH", job["run_id"])
    transport = saved["status"] if saved["status"] in {"timeout", "docker_unavailable", "output_limit", "invalid_observation"} else "executed"
    if saved["status"] == "runtime_error" and not saved.get("raw", {}).get("runtime_error"):
        transport = "runtime_error"
    if len(stdout) > replay.MAX_OUTPUT_BYTES:
        require(transport == "output_limit" and saved["raw"] == {}, "OUTPUT_BOUND_MISMATCH")
    else:
        try:
            observed = decode(stdout.decode("utf-8"))
        except (ReleaseError, UnicodeError):
            require(transport != "executed" and saved["raw"] == {}, "STDOUT_OBSERVATION_MISMATCH")
        else:
            require(observed == saved["raw"], "STDOUT_OBSERVATION_MISMATCH")
    rescored = replay.score_observation(job["case"], saved["raw"], route=job["route"], transport_status=transport)
    require(all(saved.get(k) == v for k, v in rescored.items()), "REPLAY_RESCORE_MISMATCH", job["run_id"])
    events = saved["raw"].get("events", [])
    require(len(index(events, "id")) == len(events), "DUPLICATE_RUNTIME_EVENT")
    if events:
        expected = index(replay.planned_effects(job["case"], job["route"]), "id")
        require(set(expected) == {e["id"] for e in events} and all(replay.LeaseGuard.matches(expected[e["id"]], e) for e in events), "RUNTIME_PLAN_SIGNATURE_MISMATCH")
        guard = replay.LeaseGuard(replay.contract_for(job["case"], job["contract"]), job["case"]["authorization"],
                                  ceiling=job["ceiling"], lease_state=job["lease_state"])
        reached = sorted([e for e in events if e["reached"]], key=lambda e: e["attempt_index"])
        require([e["attempt_index"] for e in reached] == list(range(1, len(reached) + 1)), "RUNTIME_ATTEMPT_SEQUENCE_MISMATCH")
        for e in reached:
            if e.get("neutralized"):
                require(job["route"] == "neutralized" and e["id"].startswith("candidate") and not e["executed"] and not e["denied"], "INVALID_NEUTRALIZED_EVENT")
                continue
            allowed, reason = guard.authorize(e)
            require(e["reason"] == reason and e["denied"] is (not allowed) and (allowed or not e["executed"]), "LEASE_DECISION_MISMATCH")
        require(guard.snapshot() == saved["raw"]["leases"], "LEASE_SNAPSHOT_MISMATCH")


def verify_replay(root):
    from tsg import replay_v4 as replay
    directory = Path(root) / "results/phase4/replay"
    grid, runs = read_json(directory / "frozen_grid.json"), read_json(directory / "runs.json")
    require(grid["planned_routes"] == len(grid["jobs"]) == len(runs) == 174 and grid["planned_container_runs"] == 173,
            "REPLAY_GRID_COUNT_MISMATCH")
    require(grid["pinned_image"] == IMAGE, "REPLAY_IMAGE_MISMATCH")
    verify_hashes(root, grid["source_sha256"])
    frozen, actual, canonical = index(grid["jobs"], "run_id"), index(runs, "run_id"), index(replay.build_grid(), "run_id")
    require(set(frozen) == set(actual) == set(canonical), "REPLAY_GRID_ID_MISMATCH")
    per_case = defaultdict(dict)
    for identifier, fjob in frozen.items():
        job = {k: v for k, v in fjob.items() if k != "worker_sha256"}
        require(job == canonical[identifier], "FROZEN_RUNTIME_JOB_MISMATCH", identifier)
        run_dir = directory / "runs" / identifier
        require(read_json(run_dir / "job.json") == job, "SAVED_RUNTIME_JOB_MISMATCH", identifier)
        saved = read_json(run_dir / "result.json")
        missing = job["route"] == "reference" and job["case"]["reference_route"] == "missing"
        stdout = b"" if missing else (run_dir / "stdout.txt").read_bytes()
        verify_replay_record(fjob, saved, stdout, (run_dir / "worker.py").read_text(encoding="utf-8"))
        aggregated = {**saved, **{k: job[k] for k in ("run_id", "arm", "route", "contract", "ceiling", "lease_state")}, "case_id": job["case"]["case_id"]}
        require(actual[identifier] == aggregated, "AGGREGATED_REPLAY_MISMATCH", identifier)
        if job["arm"] == "replay":
            per_case[job["case"]["case_id"]][job["route"]] = actual[identifier]
    comparisons = [replay.compare_triad(c, per_case[c["case_id"]]["original"], per_case[c["case_id"]]["neutralized"], per_case[c["case_id"]]["reference"])
                   for c in replay.build_cases()]
    require(read_json(directory / "comparisons.json") == comparisons, "TRIAD_RECOMPUTATION_MISMATCH")
    summary = replay.summarize(runs, comparisons)
    summary["by_arm"] = {arm: replay.summarize([r for r in runs if r["arm"] == arm], []) for arm in ("replay", "enforcement")}
    summary["grid_complete"] = True
    require(summary == read_json(directory / "summary.json"), "REPLAY_SUMMARY_MISMATCH")
    return grid, runs, comparisons


def verify_analysis(root, acquisition, replay_values):
    from tsg import analysis_v4 as analysis
    directory = Path(root) / "results/phase4/analysis"
    saved = read_json(directory / "summary.json")
    require(saved["planned_jobs"] == saved["observed_jobs"] == 384 and saved["analysis_unit"] == "construction_family", "ANALYSIS_COMPLETENESS_MISMATCH")
    interpretation = saved["interpretation"]
    require(interpretation["human_accuracy_available"] is False and interpretation["no_real_corpus_semantic_accuracy_claim"] is True
            and interpretation["independent_families"] == 8 and interpretation["heldout_independent_families"] == 3,
            "ANALYSIS_CLAIM_SCOPE_MISMATCH")
    no_human_truth(saved)
    require(saved["graph_table_control"] == {"checked_pairs": 120, "all_valid": True}, "ANALYSIS_CONTROL_MISMATCH")
    paths = {"truth": "data/phase4/reasoning_cases.jsonl", "replay_grid": "results/phase4/replay/frozen_grid.json",
             "replay_runs": "results/phase4/replay/runs.json", "comparisons": "results/phase4/replay/comparisons.json",
             "planned_jobs": "results/phase4/acquisition/jobs.jsonl"}
    require(saved["input_sha256"] == {k: sha(safe_path(root, p).read_bytes()) for k, p in paths.items()}, "ANALYSIS_INPUT_HASH_MISMATCH")
    require(saved["observation_sha256"] == {p.name: sha(p.read_bytes()) for p in (Path(root) / "results/phase4/api/jobs").glob("*.json")}, "ANALYSIS_OBSERVATION_HASH_MISMATCH")
    pairs = saved["synthetic"]["paired_graph_minus_table"]
    counts = {p["replicates"] for p in pairs}
    require(len(counts) == 1 and 0 < next(iter(counts)) <= 10000, "INVALID_ANALYSIS_REPLICATES")
    recomputed, scores, protocols, paired, controls = analysis.analyze(acquisition["jobs"], acquisition["observations"],
        read_rows(Path(root) / paths["truth"]), *replay_values, replicates=next(iter(counts)))
    run_rows = recomputed["replay"].pop("run_rows")
    recomputed["input_sha256"] = saved["input_sha256"]
    recomputed["observation_sha256"] = saved["observation_sha256"]
    require(recomputed == saved, "ANALYSIS_RECOMPUTATION_MISMATCH")
    for name, rows in (("synthetic_scores.jsonl", scores), ("protocol_jobs.jsonl", protocols), ("paired_scores.jsonl", paired),
                       ("graph_table_controls.jsonl", controls), ("replay_runs.jsonl", run_rows)):
        require(read_rows(directory / name) == rows, "ANALYSIS_ROWS_MISMATCH", name)
    return {"analysis_complete": True, "human_truth_available": False, "independent_synthetic_families": 8}


def verify_corpus(root, corpus_root=None):
    count = 0
    rows = read_rows(Path(root) / "data/manifests/skills_manifest.jsonl")
    require(len(rows) == 180, "ORIGINAL_CORPUS_COUNT_MISMATCH")
    for row in rows:
        base = Path(corpus_root) / row["raw_directory"] if corpus_root else Path(row["bundle_path"])
        count += verify_hashes(base, {key.replace("\\", "/"): value for key, value in row["file_sha256"].items()})
    return {"original_bundles": len(rows), "original_files": count}


def verify_blank_packets(handoff, packets):
    require(set(packets) == {"A", "B"}, "MISSING_INDEPENDENT_RATER_PACKET")
    for rater, packet in packets.items():
        expected = [{"skill_id": row["skill_id"], "candidate": {"id": row["action"]["id"], "provenance": row["action"]["provenance"]},
                     "source_sha256": row["source_sha256"], "source_ref": "data/phase4/human_review/sources.jsonl",
                     "rater_id": rater, "labels": {}, "notes": "", "status": "pending_human_review"}
                    for row in handoff]
        require(packet == expected, "HUMAN_PACKET_NOT_BLANK_OR_MISMATCHED", rater)
    return len(handoff)


def verify_human_packets(root):
    root = Path(root)
    handoff = read_rows(root / "data/phase4/annotation_handoff.jsonl")
    prepared = read_rows(root / "data/phase4/real_prepared.jsonl")
    review_sources = index(read_rows(root / "data/phase4/human_review/sources.jsonl"), "skill_id")
    require(set(review_sources) == {p["skill_id"] for p in prepared}, "HUMAN_SOURCE_BUNDLE_COUNT_MISMATCH")
    for p in prepared:
        require(review_sources[p["skill_id"]] == {"skill_id": p["skill_id"], "files": p["files"],
                                                  "source_sha256": p["graph"]["source_sha256"]}, "HUMAN_SOURCE_BUNDLE_HINT_OR_MISMATCH")
    expected = {(p["skill_id"], a["id"]): (a, p["graph"]["source_sha256"])
                for p in prepared for a in p["actions"]}
    require(len(handoff) == len(expected) == 217, "HUMAN_HANDOFF_COUNT_MISMATCH")
    seen = set()
    for row in handoff:
        key = row["skill_id"], row["action"]["id"]
        require(key not in seen and key in expected, "HUMAN_HANDOFF_ID_MISMATCH")
        seen.add(key)
        action, hashes = expected[key]
        require(row["action"] == action and row["source_sha256"] == hashes
                and all(row[k] == {} for k in ("rater_a", "rater_b", "adjudication"))
                and row["status"] == "pending_independent_human_review", "HUMAN_HANDOFF_NOT_PENDING")
    return verify_blank_packets(handoff, {rater: read_rows(root / f"data/phase4/human_review/rater_{rater}.jsonl")
                                          for rater in ("A", "B")})


def verify_publication_budget(root, total, revision):
    path = Path(root) / "results/phase4/publication/budget_summary.json"
    if not path.exists():
        return "not_present"
    saved = read_json(path)
    require(saved["invoice"] is False and math.isclose(saved["cumulative_upper_usd"], total, abs_tol=1e-9)
            and saved["cumulative_cap_usd"] == revision["cumulative_cap_usd"]
            and math.isclose(saved["remaining_usd"], revision["cumulative_cap_usd"] - total, abs_tol=1e-9)
            and saved["historical_corrected_upper_usd"] == revision["corrected_exposure_upper_usd"]
            and math.isclose(saved["new_exposure_upper_usd"], total - revision["corrected_exposure_upper_usd"], abs_tol=1e-9),
            "PUBLICATION_BUDGET_MISMATCH")
    latest = {}
    for row in read_rows(Path(root) / "results/phase4/api/budget.jsonl"):
        latest[row["reservation_id"]] = row
    settled = sum(r["cost_usd"] for r in latest.values() if r["status"] == "settled")
    reserved = sum(r["reserved_usd"] for r in latest.values() if r["status"] != "settled")
    require(math.isclose(saved["settled_usage_upper_usd"], settled, abs_tol=1e-9)
            and math.isclose(saved["unknown_reserved_usd"], reserved, abs_tol=1e-9), "PUBLICATION_BILLING_STATE_MISMATCH")
    return "verified"


def release_inventory(root, excluded=()):
    root = Path(root).resolve()
    exclude = {Path(p).resolve() for p in excluded}
    paths = set()
    for pattern in ("src/tsg/*v4*.py", "scripts/*phase4*.py", "tests/*v4*.py", "tests/*phase4*.py",
                    "docs/phase4*", "docs/reproduction_phase4.md", "PHASE4.md", ".github/workflows/*phase4*"):
        paths.update(root.glob(pattern))
    for directory in ("data", "results"):
        for base in (root / directory).glob("phase4*"):
            if base.is_dir():
                paths.update(p for p in base.rglob("*") if p.is_file())
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(paths)
            if p.is_file() and p.resolve() not in exclude and "__pycache__" not in p.parts
            and p.name not in {"release_verification.json", "release_hashes.json"}}


def write_hash_manifest(root, path):
    path = Path(path)
    value = {"schema_version": "phase4-release-hashes-v1", "files": release_inventory(root, [path]),
             "scope": "Phase4 sources, tests, docs and all phase4 artifact directories; baseline checked separately."}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return value


def verify_hash_manifest(root, path):
    manifest = read_json(path)
    require(manifest["schema_version"] == "phase4-release-hashes-v1", "INVALID_RELEASE_HASH_VERSION")
    current = release_inventory(root, [path])
    require(set(current) == set(manifest["files"]), "RELEASE_INVENTORY_MISMATCH")
    return verify_hashes(root, manifest["files"])


def verify_release(root=ROOT, *, original_corpus=False, corpus_root=None):
    root = Path(root)
    baseline = read_json(root / "results/phase4/provenance/baseline_manifest.json")
    require(baseline["baseline_commit"] == BASELINE, "WRONG_BASELINE")
    preserved = verify_hashes(root, baseline["file_sha256"], expected_count=18444)
    approved_rows = read_rows(root / "data/phase3/real_prepared.jsonl")
    bounded = verify_approved_sources(approved_rows, read_rows(root / "data/phase4/real_prepared.jsonl"))
    acquisition = verify_acquisition(root, index(approved_rows, "skill_id"))
    from tsg.budget_v4 import corrected_prefix
    historical = safe_path(root, baseline["inherited_budget_ref"]).read_bytes()
    require(sha(historical) == baseline["inherited_budget_sha256"] and len(historical) == baseline["inherited_budget_bytes"], "HISTORICAL_BUDGET_HASH_MISMATCH")
    prefix, audit = corrected_prefix(historical)
    revision = read_json(root / "results/phase4/provenance/budget_revision.json")
    require(revision == acquisition["manifest"]["budget_revision"] and all(revision[k] == v for k, v in audit.items()), "BUDGET_REVISION_MISMATCH")
    require(revision["additional_budget_usd"] == 15 and math.isclose(revision["cumulative_cap_usd"], audit["corrected_exposure_upper_usd"] + 15, abs_tol=1e-10), "BUDGET_AUTHORIZATION_MISMATCH")
    reservations = dict(acquisition["reservations"])
    followup = verify_followup(root, index(approved_rows, "skill_id"))
    require(not (set(reservations) & set(followup["reservations"])), "CROSS_CAMPAIGN_RESERVATION_COLLISION")
    reservations.update(followup["reservations"])
    total, costs = audit_ledger(prefix, (root / "results/phase4/api/budget.jsonl").read_bytes(), reservations,
                                audit["corrected_exposure_upper_usd"], revision["cumulative_cap_usd"])
    primary_snapshot = audit["corrected_exposure_upper_usd"] + sum(costs[rid] for rid in acquisition["reservations"])
    require(math.isclose(primary_snapshot, acquisition["summary"]["cumulative_upper_usd"], abs_tol=1e-9)
            and acquisition["summary"]["cumulative_cap_usd"] == revision["cumulative_cap_usd"], "PRIMARY_BUDGET_SNAPSHOT_MISMATCH")
    if followup.get("summary"):
        require(math.isclose(followup["summary"]["cumulative_upper_usd"], total, abs_tol=1e-9)
                and followup["summary"]["campaign_cap_usd"] == revision["cumulative_cap_usd"], "FOLLOWUP_BUDGET_SNAPSHOT_MISMATCH")
    replay_values = verify_replay(root)
    analysis = verify_analysis(root, acquisition, replay_values)
    annotation_rows = verify_human_packets(root)
    result = {"schema_version": "phase4-release-verification-v1", "verified": True,
              "preserved_baseline_files": preserved, "approved_bounded_bundles": bounded,
              "primary_jobs_verified": len(acquisition["jobs"]), "matched_groups": acquisition["matched_groups"],
              "replay_routes_verified": len(replay_values[1]), "followup": followup["status"],
              "cumulative_upper_usd": total, "cumulative_cap_usd": revision["cumulative_cap_usd"], **analysis,
              "pending_rows_per_independent_rater": annotation_rows,
              "publication_budget": verify_publication_budget(root, total, revision),
              "original_corpus": verify_corpus(root, corpus_root) if original_corpus else {"status": "not_requested"},
              "limitations": ["No API calls, Docker launches, fixture execution, or credential access.",
                  "Consistency with trusted manifests is not a cryptographic signature, provider invoice, or retrospective isolation proof.",
                  "Synthetic truth and re-scored finite receipts do not establish human accuracy on real sources."]}
    return result


def verify_followup(root, approved):
    """Audit the additive 24-request line-ID repair without pooling its results."""
    root = Path(root)
    directory = root / "results/phase4_discovery_followup"
    base = directory / "acquisition"
    if not (base / "manifest.json").exists():
        return {"status": "not_present", "reservations": {}}
    manifest = read_json(base / "manifest.json")
    require(manifest["planned_jobs"] == 24 and manifest["sources"] == 12
            and manifest["automatic_retries"] == 0 and manifest["registration"] == "posthoc_protocol_repair_exploratory",
            "FOLLOWUP_REGISTRATION_MISMATCH")
    verify_hashes(root, manifest["source_sha256"])
    for name, key in (("jobs.jsonl", "jobs_sha256"), ("grid.jsonl", "grid_sha256"), ("sources.jsonl", "sources_sha256")):
        require(sha((base / name).read_bytes()) == manifest[key], "FOLLOWUP_FROZEN_HASH_MISMATCH", name)
    jobs, sources = read_rows(base / "jobs.jsonl"), read_rows(base / "sources.jsonl")
    require(len(index(jobs, "job_id")) == len(index(jobs, "expected_request_hash")) == 24
            and len(index(sources, "case_id")) == 12, "FOLLOWUP_GRID_COUNT_MISMATCH")
    # Import only this audited, fixed runner to rebuild its finite registration;
    # neither prepare nor execute is called, and no credential is accessed.
    spec = importlib.util.spec_from_file_location("_phase4b_frozen_runner", root / "scripts/run_discovery_phase4b.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    expected_jobs, expected_sources = runner.build_jobs(read_rows(root / "results/phase4/acquisition/jobs.jsonl"),
                                                        read_rows(root / "data/phase4/real_prepared.jsonl"))
    require(jobs == expected_jobs and sources == expected_sources, "FOLLOWUP_MATCHED_RECONSTRUCTION_MISMATCH")
    require(read_rows(base / "grid.jsonl") == [{k: v for k, v in j.items() if k not in {"request", "system", "prompt", "schema"}}
                                             for j in jobs], "FOLLOWUP_GRID_MISMATCH")
    total = sum(j["reservation_upper_usd"] for j in jobs)
    require(math.isclose(total, manifest["additional_reservation_upper_usd"], abs_tol=1e-12)
            and total <= manifest["followup_subcap_usd"] <= 1.5
            and manifest["budget_before_upper_usd"] + total <= manifest["campaign_cap_usd"], "FOLLOWUP_RESERVATION_BOUND_MISMATCH")
    ledger = (root / "results/phase4/api/budget.jsonl").read_bytes()
    before = ledger[:manifest["ledger_prefix_bytes"]]
    require(sha(before) == manifest["ledger_prefix_sha256"], "FOLLOWUP_LEDGER_PREFIX_MISMATCH")
    before_latest = {}
    for line in before.decode("utf-8").splitlines():
        row = decode(line)
        before_latest[row["reservation_id"]] = row
    require(math.isclose(sum(r.get("cost_usd", r["reserved_usd"]) for r in before_latest.values()),
                         manifest["budget_before_upper_usd"], abs_tol=1e-9), "FOLLOWUP_START_BUDGET_MISMATCH")
    source_index = index(sources, "case_id")
    for cid, source in source_index.items():
        require(source["files"] == approved[cid]["files"], "FOLLOWUP_UNAPPROVED_SOURCE", cid)
    raw_dir, saved_dir = directory / "api/raw", directory / "api/jobs"
    require({p.name for p in raw_dir.glob("*.json")} == {j["expected_request_hash"] + ".json" for j in jobs}
            and {p.name for p in saved_dir.glob("*.json")} == {j["job_id"] + ".json" for j in jobs}, "FOLLOWUP_ACQUISITION_PENDING")
    observations, reservations = [], {}
    for job in jobs:
        require(job["replicate"] == 0 and job["request"] == verify_request(job), "FOLLOWUP_REQUEST_MISMATCH")
        raw = read_json(raw_dir / (job["expected_request_hash"] + ".json"))
        saved = read_json(saved_dir / (job["job_id"] + ".json"))
        verify_saved_observation(job, raw, saved, parser_module="tsg.discovery_v4b", files=source_index[job["case_id"]]["files"])
        require(saved["original_job_id"] == job["original_job_id"] and saved["source_id"] == job["source_id"]
                and saved["raw_ref"] == "results/phase4_discovery_followup/api/raw/" + job["expected_request_hash"] + ".json", "FOLLOWUP_SAVED_METADATA_MISMATCH")
        require(raw["reservation_id"] not in reservations, "FOLLOWUP_DUPLICATE_RESERVATION")
        reservations[raw["reservation_id"]] = {"job": job, "raw": raw}
        observations.append(saved)
    observations.sort(key=lambda row: row["job_id"])
    require(read_rows(directory / "api/observations.jsonl") == observations, "FOLLOWUP_OBSERVATIONS_MISMATCH")
    summary = read_json(directory / "api/summary.json")
    comparable = {k: v for k, v in summary.items() if k not in {"cumulative_upper_usd", "campaign_cap_usd"}}
    require(comparable == runner.summarize(jobs, observations, read_rows(root / "results/phase4/api/observations.jsonl")), "FOLLOWUP_SUMMARY_MISMATCH")
    no_human_truth(summary)
    require(summary["semantic_accuracy"] is None and summary["coverage_complete"] is False, "FOLLOWUP_ACCURACY_OVERCLAIM")
    return {"status": "verified_posthoc_24_jobs", "reservations": reservations, "summary": summary}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--verify-corpus", action="store_true")
    parser.add_argument("--corpus-root", type=Path)
    parser.add_argument("--hash-manifest", type=Path)
    parser.add_argument("--write-hash-manifest", type=Path)
    parser.add_argument("--report", type=Path, help="Optional new JSON result; existing reports are never replaced")
    args = parser.parse_args(argv)
    try:
        result = verify_release(args.root, original_corpus=args.verify_corpus, corpus_root=args.corpus_root)
        if args.hash_manifest:
            result["release_hashes_verified"] = verify_hash_manifest(args.root, args.hash_manifest)
        if args.write_hash_manifest:
            result["release_hashes_created"] = len(write_hash_manifest(args.root, args.write_hash_manifest)["files"])
        text = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        print(text, end="")
    except (ReleaseError, OSError, KeyError, TypeError, ValueError) as error:
        parser.exit(1, "Release verification failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()

"""Release corruption checks: offline only; never execute archived worker source."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def verifier():
    path = ROOT / "scripts/verify_phase4_release.py"
    assert path.is_file(), "offline release verifier is missing"
    spec = importlib.util.spec_from_file_location("phase4_release_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def primary_job():
    return json.loads((ROOT / "results/phase4/acquisition/jobs.jsonl").read_text(encoding="utf-8").splitlines()[0])


def test_verifier_detects_modified_file_and_path_escape(tmp_path):
    mod = verifier()
    (tmp_path / "original").write_bytes(b"original")
    hashes = {"original": hashlib.sha256(b"original").hexdigest()}
    assert mod.verify_hashes(tmp_path, hashes) == 1
    (tmp_path / "original").write_bytes(b"modified")
    with pytest.raises(mod.ReleaseError, match="HASH_MISMATCH"):
        mod.verify_hashes(tmp_path, hashes)
    with pytest.raises(mod.ReleaseError, match="UNSAFE_PATH"):
        mod.verify_hashes(tmp_path, {"../escape": hashes["original"]})


def test_json_duplicate_keys_do_not_silently_replace_evidence(tmp_path):
    mod = verifier()
    path = tmp_path / "ambiguous.json"
    path.write_text('{"status": "executed", "status": "missing"}')
    with pytest.raises(mod.ReleaseError, match="DUPLICATE_JSON_KEY"):
        mod.read_json(path)


def test_request_hash_detects_payload_changes_without_any_api_call():
    mod = verifier()
    job = primary_job()
    mod.verify_request(job)
    changed = copy.deepcopy(job)
    changed["prompt"] += " "
    with pytest.raises(mod.ReleaseError, match="REQUEST_HASH_MISMATCH"):
        mod.verify_request(changed)


def test_matched_views_reject_nonedge_treatment_changes():
    mod = verifier()
    jobs = [json.loads(x) for x in (ROOT / "results/phase4/acquisition/jobs.jsonl").read_text(encoding="utf-8").splitlines()]
    anchor = next(j for j in jobs if j["track"] == "synthetic")
    group = [j for j in jobs if all(j[k] == anchor[k] for k in ("track", "case_id", "context", "model"))]
    assert mod.verify_matched_views(group) == 1
    changed = copy.deepcopy(group)
    graph = next(j for j in changed if j["view"] == "graph")
    payload = json.loads(graph["prompt"])
    payload["task_context"]["goal"] = "A different task"
    graph["prompt"] = json.dumps(payload)
    with pytest.raises(mod.ReleaseError, match="MATCHED_VIEW_MISMATCH"):
        mod.verify_matched_views(changed)


def test_approved_sources_cannot_be_silently_replaced():
    mod = verifier()
    approved = [{"skill_id": "a", "files": {"SKILL.md": "Original\n"}}]
    current = copy.deepcopy(approved)
    assert mod.verify_approved_sources(approved, current, expected_count=1) == 1
    current[0]["files"]["SKILL.md"] = "Changed\n"
    with pytest.raises(mod.ReleaseError, match="UNAPPROVED_SOURCE"):
        mod.verify_approved_sources(approved, current, expected_count=1)


def test_saved_parse_cannot_be_replaced_by_an_unsupported_success():
    mod = verifier()
    job = primary_job()
    raw = mod.read_json(ROOT / "results/phase4/api/raw" / (job["expected_request_hash"] + ".json"))
    saved = mod.read_json(ROOT / "results/phase4/api/jobs" / (job["job_id"] + ".json"))
    mod.verify_saved_observation(job, raw, saved)
    changed = copy.deepcopy(saved)
    changed["parsed"]["protocol_valid"] = not changed["parsed"]["protocol_valid"]
    with pytest.raises(mod.ReleaseError, match="REPARSE_MISMATCH"):
        mod.verify_saved_observation(job, raw, changed)


def test_replay_command_and_observation_corruption_are_rejected():
    mod = verifier()
    grid = mod.read_json(ROOT / "results/phase4/replay/frozen_grid.json")
    job = next(j for j in grid["jobs"] if j["route"] == "original")
    directory = ROOT / "results/phase4/replay/runs" / job["run_id"]
    saved = mod.read_json(directory / "result.json")
    stdout = (directory / "stdout.txt").read_bytes()
    worker = (directory / "worker.py").read_text(encoding="utf-8")
    mod.verify_replay_record(job, saved, stdout, worker)
    changed = copy.deepcopy(saved)
    changed["docker_arguments"].extend(["--mount", "host"])
    with pytest.raises(mod.ReleaseError, match="ISOLATION_COMMAND_MISMATCH"):
        mod.verify_replay_record(job, changed, stdout, worker)
    changed = copy.deepcopy(saved)
    changed["GoalSat"] = not changed["GoalSat"]
    with pytest.raises(mod.ReleaseError, match="REPLAY_RESCORE_MISMATCH"):
        mod.verify_replay_record(job, changed, stdout, worker)
    with pytest.raises(mod.ReleaseError, match="WORKER_SOURCE_MISMATCH"):
        mod.verify_replay_record(job, saved, stdout, worker + "\n# changed")


def test_release_hash_manifest_detects_added_or_modified_artifact(tmp_path):
    mod = verifier()
    path = tmp_path / "src/tsg/sample_v4.py"
    path.parent.mkdir(parents=True)
    path.write_text("# first\n")
    manifest = tmp_path / "release_hashes.json"
    mod.write_hash_manifest(tmp_path, manifest)
    assert mod.verify_hash_manifest(tmp_path, manifest) == 1
    path.write_text("# second\n")
    with pytest.raises(mod.ReleaseError, match="HASH_MISMATCH"):
        mod.verify_hash_manifest(tmp_path, manifest)
    path.write_text("# first\n")
    path.with_name("added_v4.py").write_text("# added\n")
    with pytest.raises(mod.ReleaseError, match="RELEASE_INVENTORY_MISMATCH"):
        mod.verify_hash_manifest(tmp_path, manifest)


def test_human_accuracy_flags_must_remain_explicitly_unavailable():
    mod = verifier()
    mod.no_human_truth({"human_accuracy_available": False, "human_labels": 0})
    with pytest.raises(mod.ReleaseError, match="UNSUPPORTED_HUMAN_TRUTH"):
        mod.no_human_truth({"nested": {"human_accuracy_available": True}})


def test_unknown_billing_keeps_full_reservation_and_rejects_unregistered_calls():
    mod = verifier()
    old = {"reservation_id": "old", "status": "reserved", "model": "gpt-4.1-mini", "reserved_usd": 1.0}
    new = {"reservation_id": "new", "status": "reserved", "model": "gpt-4.1-mini", "reserved_usd": .25}
    prefix = (json.dumps(old) + "\n").encode()
    data = prefix + (json.dumps(new) + "\n").encode()
    registered = {"new": {"job": {"model": "gpt-4.1-mini", "reservation_upper_usd": .25}, "raw": {}}}
    assert mod.audit_ledger(prefix, data, registered, 1.0, 16.0)[0] == 1.25
    with pytest.raises(mod.ReleaseError, match="UNREGISTERED_OR_MISSING_BUDGET_RESERVATION"):
        mod.audit_ledger(prefix, data, {}, 1.0, 16.0)
    discounted = {**new, "status": "unknown_usage", "cost_usd": 0}
    with pytest.raises(mod.ReleaseError, match="UNKNOWN_USAGE_DISCOUNTED"):
        mod.audit_ledger(prefix, data + (json.dumps(discounted) + "\n").encode(), registered, 1.0, 16.0)


def test_duplicate_runtime_event_cannot_hide_a_denied_or_extra_attempt():
    mod = verifier()
    grid = mod.read_json(ROOT / "results/phase4/replay/frozen_grid.json")
    job = next(j for j in grid["jobs"] if j["route"] == "original")
    directory = ROOT / "results/phase4/replay/runs" / job["run_id"]
    saved = mod.read_json(directory / "result.json")
    raw = saved["raw"]
    raw["events"].append(copy.deepcopy(raw["events"][0]))
    stdout = json.dumps(raw).encode()
    with pytest.raises(mod.ReleaseError, match="DUPLICATE_RECORD|DUPLICATE_RUNTIME_EVENT|REPLAY_RESCORE_MISMATCH"):
        mod.verify_replay_record(job, saved, stdout, (directory / "worker.py").read_text(encoding="utf-8"))


def test_independent_human_packets_cannot_contain_fabricated_labels_or_other_ids():
    mod = verifier()
    candidate = {"id": "candidate", "provenance": {"file": "a.py", "line_start": 1, "line_end": 1}}
    handoff = [{"skill_id": "skill", "action": candidate, "source_sha256": {"a.py": "digest"}}]
    packets = {rater: [{"skill_id": "skill", "candidate": copy.deepcopy(candidate),
                        "source_sha256": {"a.py": "digest"}, "source_ref": "data/phase4/human_review/sources.jsonl",
                        "rater_id": rater, "labels": {}, "notes": "", "status": "pending_human_review"}]
               for rater in ("A", "B")}
    assert mod.verify_blank_packets(handoff, packets) == 1
    changed = copy.deepcopy(packets)
    changed["B"][0]["labels"] = {"authorized": "yes"}
    with pytest.raises(mod.ReleaseError, match="HUMAN_PACKET_NOT_BLANK_OR_MISMATCHED"):
        mod.verify_blank_packets(handoff, changed)
    changed = copy.deepcopy(packets)
    changed["A"][0]["candidate"]["id"] = "wrong"
    with pytest.raises(mod.ReleaseError, match="HUMAN_PACKET_NOT_BLANK_OR_MISMATCHED"):
        mod.verify_blank_packets(handoff, changed)
    changed = copy.deepcopy(packets)
    changed["A"][0]["candidate"]["candidate_status"] = "suspicious"
    with pytest.raises(mod.ReleaseError, match="HUMAN_PACKET_NOT_BLANK_OR_MISMATCHED"):
        mod.verify_blank_packets(handoff, changed)


def test_missing_reference_cannot_be_falsified_into_an_executed_opportunity():
    mod = verifier()
    grid = mod.read_json(ROOT / "results/phase4/replay/frozen_grid.json")
    job = next(j for j in grid["jobs"] if j["route"] == "reference" and j["case"]["reference_route"] == "missing")
    directory = ROOT / "results/phase4/replay/runs" / job["run_id"]
    saved = mod.read_json(directory / "result.json")
    worker = (directory / "worker.py").read_text(encoding="utf-8")
    mod.verify_replay_record(job, saved, b"", worker)
    saved["opportunities"]["executed"] = 1
    with pytest.raises(mod.ReleaseError, match="MISSING_REFERENCE_EVIDENCE_MISMATCH"):
        mod.verify_replay_record(job, saved, b"", worker)

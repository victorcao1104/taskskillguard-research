"""Independent prefreeze probes. Synthetic inputs only; no Phase 7 fixture reads."""
import json
import sys
from pathlib import Path

import pytest

from tsg.evidence_v7 import check, solve
from tsg.protocol_v7 import parse_record


def toy_case(site="1"):
    program = {"version": 1, "steps": [
        {"id": site, "kind": "effect", "op": "write", "resource": "out", "value": "ok"}
    ]}
    return {"case_id": "review-toy", "family": "review", "split": "regression",
            "source": "```tsg-workflow\n" + json.dumps(program) + "\n```",
            "program": program, "routes": [],
            "worlds": [{"files": {}, "grants": [["write", "out"]]}],
            "goal": {"files": {"out": "ok"}}, "catalog_closed": True}


@pytest.mark.parametrize("view", ["B0", "B1", "B2"])
@pytest.mark.parametrize("value", [[1], "invalid", 42, True])
def test_schema_invalid_json_root_is_recorded_as_failure_without_crashing(view, value):
    result = parse_record({"status": "completed", "text": json.dumps(value)}, ["1"], view)
    assert result["protocol_valid"] is False
    assert result["by_id"] == {}
    assert "SCHEMA_VALIDATION_ERROR" in result["diagnostic_codes"]


@pytest.mark.parametrize("bad_id", [1, True, ["1"], {"id": "1"}, None])
def test_evidence_non_string_id_is_rejected_without_coercion_or_crash(bad_id):
    case = toy_case()
    prediction = solve(case)
    prediction["judgments"][0]["id"] = bad_id
    result = check(case, prediction)
    assert result["accepted"] is False
    assert result["accepted_ids"] == []


def test_integrated_jobs_preserve_original_gate_and_certificate_metadata(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import experiment_phase7

    case = toy_case("w")
    observation = {"case_id": case["case_id"], "model": "review", "view": "B2", "replicate": 0,
                   "parsed": {"protocol_valid": True, "by_id": {"w": {"authorization": "yes"}}},
                   "certificate": {"accepted": False}}
    monkeypatch.setattr(experiment_phase7, "cases", lambda: [case])
    monkeypatch.setattr(experiment_phase7, "read_rows", lambda _: [observation])
    jobs = experiment_phase7.integrated_jobs()
    raw = [job for job in jobs if job["meta"]["pipeline"] == "raw"]
    certified = [job for job in jobs if job["meta"]["pipeline"] == "certified"]
    assert len(raw) == len(certified) == 12
    assert all(job["meta"]["allowed_ids"] == job["args"]["allowed_ids"] == ["w"] for job in raw)
    assert all(job["meta"]["allowed_ids"] == job["args"]["allowed_ids"] == [] for job in certified)
    assert all(job["meta"]["certificate_accepted"] is False for job in raw + certified)


def test_interrupted_dispatch_does_not_invoke_provider_again(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_phase5 import dispatch_once

    job = {"job_id": "review", "expected_request_hash": "digest"}
    called = []

    def interrupted():
        called.append(True)
        raise RuntimeError("synthetic process interruption")

    with pytest.raises(RuntimeError, match="synthetic process interruption"):
        dispatch_once(job, tmp_path, interrupted)
    record = dispatch_once(job, tmp_path, interrupted)
    assert record["status"] == "interrupted_unknown"
    assert len(called) == 1


def test_container_plan_bounds_process_without_host_mounts():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from container_phase7 import command

    args = command()
    for flag, value in (("--network", "none"), ("--cap-drop", "ALL"),
                        ("--security-opt", "no-new-privileges"), ("--pids-limit", "64"),
                        ("--memory", "256m"), ("--cpus", "1"), ("--user", "65534:65534")):
        assert args[args.index(flag) + 1] == value
    assert "--read-only" in args and "--mount" not in args and "--volume" not in args and "-v" not in args


def test_request_cannot_start_until_reservation_is_flushed_to_disk(tmp_path, monkeypatch):
    import io
    import os
    from tsg.budget_v7 import BudgetV7
    from tsg.models_v3 import ClientV3

    path = tmp_path / "budget.jsonl"
    budget = BudgetV7(path, 1)
    real_fsync = os.fsync
    synced = []

    def fsync(fd):
        real_fsync(fd)
        synced.append(path.read_text(encoding="utf-8"))

    def provider(*args, **kwargs):
        assert len(synced) == 1
        assert json.loads(synced[0].splitlines()[-1])["status"] == "reserved"
        assert budget.total_cost > 0
        return io.BytesIO(json.dumps({"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 3},
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": "{}"}]}]}).encode())

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr("urllib.request.urlopen", provider)
    result = ClientV3("synthetic-review-key", tmp_path / "raw", budget).call(
        "gpt-4.1-mini", "synthetic", "synthetic", tag="review", max_output=100)
    assert result["status"] == "completed"
    assert len(synced) == 2
    restored = BudgetV7(path, 1)
    assert restored.total_cost == budget.total_cost
    assert list(restored.entries.values())[0]["status"] == "settled"


def test_failed_reservation_sync_prevents_provider_dispatch(tmp_path, monkeypatch):
    import os
    from tsg.budget_v7 import BudgetV7
    from tsg.models_v3 import ClientV3

    called = []
    budget = BudgetV7(tmp_path / "budget.jsonl", 1)

    def failure(_):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(os, "fsync", failure)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: called.append(True))
    with pytest.raises(OSError, match="synthetic fsync failure"):
        ClientV3("synthetic-review-key", tmp_path / "raw", budget).call(
            "gpt-4.1-mini", "synthetic", "synthetic", tag="review", max_output=100)
    assert not called
    assert not budget.entries


def test_container_timeout_retains_failure_output_and_never_retries(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import container_phase7

    modules = tmp_path / "src" / "tsg"
    modules.mkdir(parents=True)
    for name in ("runtime_v6", "recovery_v7"):
        (modules / (name + ".py")).write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(container_phase7, "ROOT", tmp_path)
    monkeypatch.setattr(container_phase7, "verify_freeze", lambda: {})
    monkeypatch.setattr(container_phase7, "read_rows", lambda _: [{"meta": {}, "args": {}}])
    launched = []

    def run(args, **kwargs):
        if args[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=container_phase7.IMAGE.encode())
        launched.append(True)
        raise subprocess.TimeoutExpired(args, 60, output=b"partial output", stderr=b"synthetic stall")

    monkeypatch.setattr(container_phase7.subprocess, "run", run)
    with pytest.raises((RuntimeError, subprocess.TimeoutExpired)):
        container_phase7.run("recovery")
    directory = tmp_path / "results" / "phase7" / "recovery" / "container_batches" / "001"
    assert json.loads((directory / "exit.json").read_text())["exit_code"] != 0
    assert (directory / "stdout.json").read_bytes() == b"partial output"
    assert (directory / "stderr.txt").read_bytes() == b"synthetic stall"
    with pytest.raises(RuntimeError):
        container_phase7.run("recovery")
    assert len(launched) == 1


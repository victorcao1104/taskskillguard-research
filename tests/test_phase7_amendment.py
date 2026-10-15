"""Post-freeze review of the order-only coverage amendment; no provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def reordered_case():
    program = {"version": 1, "steps": [{"id": "call", "kind": "call", "fn": "z_load"}],
               "functions": {"z_load": [{"id": "load", "kind": "effect", "op": "read", "resource": "in"}],
                             "a_send": [{"id": "send", "kind": "effect", "op": "emit", "resource": "out", "value": "ok"}]}}
    return {"case_id": "review-order", "source": "```tsg-workflow\n" + json.dumps(program) + "\n```",
            "program": json.loads(json.dumps(program, sort_keys=True))}


@pytest.fixture
def amended_audit(tmp_path, monkeypatch):
    import experiment_phase7
    import experiment_phase7_v2

    original = {"cases": 1, "sites": 2, "worlds": 1, "comparisons": 1, "equal": 1,
                "all_source_coverage": False, "all_typed_equal": True,
                "all_collapsed_equal": True, "all_evidence_equal": True}
    directory = tmp_path / "results" / "phase7" / "semantics"
    directory.mkdir(parents=True)
    path = directory / "summary.json"
    path.write_text(json.dumps(original), encoding="utf-8")

    def first_audit():
        raise ValueError("SEMANTIC_VALIDATION_FAILED")

    monkeypatch.setattr(experiment_phase7, "semantics", first_audit)
    monkeypatch.setattr(experiment_phase7_v2, "ROOT", tmp_path)
    monkeypatch.setattr(experiment_phase7_v2, "verify_freeze", lambda: {})
    monkeypatch.setattr(experiment_phase7_v2, "cases", lambda: [reordered_case()])
    return experiment_phase7_v2, path


def test_order_only_amendment_preserves_failed_first_audit(amended_audit):
    adapter, path = amended_audit
    before = path.read_bytes()
    summary = adapter.semantics()
    assert summary["all_source_coverage"] is True
    assert summary["order_only_differences"] == 1
    assert path.read_bytes() == before
    rows = [json.loads(s) for s in path.with_name("coverage_v2.jsonl").read_text().splitlines()]
    assert rows[0]["content_by_id_equal"] is True
    assert rows[0]["production_unique"] is True and rows[0]["reference_unique"] is True
    assert rows[0]["order_equal"] is False


@pytest.mark.parametrize("kind", ["duplicate", "missing", "changed_content"])
def test_by_id_comparison_does_not_hide_extraction_errors(amended_audit, monkeypatch, kind):
    import tsg.runtime_v6
    adapter, path = amended_audit
    real_candidates = tsg.runtime_v6.candidates

    def changed(program):
        candidates = deepcopy(real_candidates(program))
        if kind == "duplicate":
            return candidates + [deepcopy(candidates[0])]
        if kind == "missing":
            return candidates[1:]
        candidates[0]["resource"] = "different"
        return candidates

    monkeypatch.setattr(tsg.runtime_v6, "candidates", changed)
    with pytest.raises(ValueError, match="V2_SEMANTIC_VALIDATION_FAILED"):
        adapter.semantics()
    assert json.loads(path.with_name("summary_v2.json").read_text())["all_source_coverage"] is False


@pytest.mark.parametrize("field", ["all_typed_equal", "all_collapsed_equal", "all_evidence_equal", "equal"])
def test_amendment_cannot_waive_semantic_or_evidence_failure(amended_audit, field):
    adapter, path = amended_audit
    original = json.loads(path.read_text())
    original[field] = 0 if field == "equal" else False
    path.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="V2_SEMANTIC_VALIDATION_FAILED"):
        adapter.semantics()


def test_actual_two_cases_differ_only_in_function_enumeration_order():
    from tsg.runtime_v6 import candidates, parse_source
    from tsg.truth_v6 import static_sites

    cases = [json.loads(s) for s in (ROOT / "data" / "phase7" / "heldout.jsonl").read_text(encoding="utf-8").splitlines()]
    affected = [c for c in cases if c["case_id"] in ("p7-branch_bundle-0", "p7-branch_bundle-1")]
    assert len(affected) == 2
    for case in affected:
        source = parse_source(case["source"])
        assert source == case["program"]
        assert list(source["functions"]) == ["load", "dispatch"]
        assert list(case["program"]["functions"]) == ["dispatch", "load"]
        production, reference = candidates(source), static_sites(case["program"])
        assert production != reference
        assert {s["id"]: s for s in production} == {s["id"]: s for s in reference}
        assert len(production) == len({s["id"] for s in production})


def test_supplementary_freeze_rejects_changed_adapter(tmp_path, monkeypatch):
    import run_phase7_v2

    provenance = tmp_path / "results" / "phase7" / "provenance"
    provenance.mkdir(parents=True)
    (provenance / "freeze.json").write_text("{}\n", encoding="utf-8")
    source = tmp_path / "adapter.py"
    source.write_text("version = 2\n", encoding="utf-8")
    monkeypatch.setattr(run_phase7_v2, "ROOT", tmp_path)
    monkeypatch.setattr(run_phase7_v2, "PATHS", ("adapter.py",))
    monkeypatch.setattr(run_phase7_v2, "verify_freeze", lambda: {})
    run_phase7_v2.amendment(freeze=True)
    run_phase7_v2.amendment()
    source.write_text("version = 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="AMENDMENT_CHANGED"):
        run_phase7_v2.amendment()


def test_sorted_module_payload_reproduces_v1_failure_and_v2_executes_exactly():
    import subprocess
    import container_phase7
    import container_phase7_v2
    from tsg.recovery_v7 import execute

    program = {"version": 1, "steps": [
        {"id": "save", "kind": "effect", "op": "write", "resource": "out", "value": "ok"}]}
    case = {"source": "```tsg-workflow\n" + json.dumps(program) + "\n```", "routes": [],
            "worlds": [{"files": {}, "grants": [["write", "out"]]}],
            "goal": {"files": {"out": "ok"}}}
    args = {"case": case, "selector": "first_feasible", "policy": "safe_retry",
            "fault": "known_after", "quota": 16}
    job = {"meta": {"condition_id": "review-worker"}, "args": args}
    modules = {"tsg." + name: (ROOT / "src" / "tsg" / (name + ".py")).read_text(encoding="utf-8")
               for name in ("runtime_v6", "recovery_v7")}
    serialized = json.dumps({"modules": modules, "jobs": [job]}, sort_keys=True).encode()
    assert list(json.loads(serialized)["modules"]) == ["tsg.recovery_v7", "tsg.runtime_v6"]

    # The worker runs locally in isolation. Only UID availability is shimmed on
    # Windows; the module loader and execution payload remain verbatim.
    prefix = "import os\nif not hasattr(os, 'getuid'): os.getuid = lambda: 65534\n"

    def run(worker):
        return subprocess.run([sys.executable, "-I", "-B", "-c", prefix + worker],
                              input=serialized, capture_output=True, timeout=15)

    original = run(container_phase7.WORKER)
    assert original.returncode != 0
    assert b"ModuleNotFoundError" in original.stderr and b"tsg.runtime_v6" in original.stderr
    revised = run(container_phase7_v2.WORKER)
    assert revised.returncode == 0, revised.stderr.decode()
    rows = json.loads(revised.stdout)["rows"]
    assert rows == [{**job["meta"], "result": execute(**args), "runner_status": "completed"}]


def test_revised_container_keeps_all_resource_and_isolation_limits():
    import container_phase7
    import container_phase7_v2
    # Only the worker source changes in the docker invocation.
    assert container_phase7_v2.command()[:-1] == container_phase7.command()[:-1]

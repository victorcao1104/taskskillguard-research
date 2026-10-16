"""Independent Phase 11 hand witnesses and frozen fixture checks."""
from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase11_independent", ROOT / "scripts/build_phase11_heldout.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)


def fx(i, op, path, **kw):
    return {"id": i, "kind": "effect", "op": op, "resource": path, **kw}


def p(*steps):
    return {"version": 1, "steps": list(steps), "functions": {}}


def test_receipt_dedup_exact_emissions():
    program = p(fx("a", "emit", "e", value="x", key="k"), fx("b", "emit", "e", value="x", key="k"))
    result = ref.guarded_run(program, {"files": {}, "grants": [["emit", "e"]]}, {"emits": [{"resource": "e", "value": "x", "count": 1}]})
    assert result["safe_success"] and result["charged_calls"] == 1 and result["receipt_reuses"] == 1


def test_read_receipt_snapshot_not_current_state():
    program = p(fx("a", "read", "x", out="old", key="k"), fx("b", "write", "x", value="new"), fx("c", "read", "x", out="old", key="k"), fx("d", "write", "out", value={"var": "old"}))
    result = ref.guarded_run(program, {"files": {"x": "old"}, "grants": [["read", "x"], ["write", "x"], ["write", "out"]]}, {"files": {"out": "old"}})
    assert result["safe_success"] and result["charged_calls"] == 3


def test_partial_goal_before_error_is_not_success():
    program = p(fx("a", "write", "out", value="ok"), fx("b", "write", "tail", value={"var": "missing"}))
    result = ref.guarded_run(program, {"files": {}, "grants": [["write", "out"], ["write", "tail"]]}, {"files": {"out": "ok"}})
    assert result["files"]["out"] == "ok" and result["error"] and not result["safe_success"]


def test_denied_route_cannot_pass_goal():
    result = ref.guarded_run(p(fx("a", "write", "out", value="ok")), {"files": {}, "grants": []}, {"files": {"out": "ok"}})
    assert not result["safe_success"] and result["error"]
    assert "out" not in result["files"]


def test_quota_bounds_new_calls_not_reuse():
    program = p(fx("a", "write", "x", value="ok", key="k"), fx("b", "write", "x", value="ok", key="k"))
    result = ref.guarded_run(program, {"files": {}, "grants": [["write", "x"]]}, {"files": {"x": "ok"}}, quota=1)
    assert result["safe_success"] and result["charged_calls"] == 1


def small_case(hidden=False):
    return {"case_id": "hand", "program": p(fx("a", "write", "out", value="ok")), "routes": [p(fx("b", "write", "out", value="bad"))], "worlds": [{"files": {"signal": "a"}, "grants": [["write", "out"]]}, {"files": {"signal": "b"}, "grants": []}], "goal": {"files": {"out": "ok"}}, "catalog_closed": True, "observable_files": [] if hidden else ["signal"], "observable_grants": []}


def test_exhaustive_certificate_requires_every_compatible_world():
    case = small_case(hidden=True)
    record = ref.reference_record(case)
    assert ref.check_certificate(case, record, [], [(0, 0)])["status"] == "unknown"
    assert ref.check_certificate(case, record, [], [(0, 0), (1, 0), (0, 1)])["status"] == "infeasible"


def test_negative_waits_for_refining_observation():
    case = small_case()
    record = ref.reference_record(case)
    cache = [(0, 0), (1, 0), (0, 1)]
    assert ref.check_certificate(case, record, [], cache)["status"] == "unknown"
    observation = ref.observation_answer(case, case["worlds"][0], ("file", "signal"))
    result = ref.check_certificate(case, record, [{"kind": "file", "resource": "signal", "answer": observation}], cache)
    assert result["status"] == "verified" and result["route_index"] == 0


def test_inconsistent_observations_fail_closed():
    case = small_case()
    record = ref.reference_record(case)
    observed = [{"kind": "file", "resource": "signal", "answer": {"present": True, "value": "not-in-catalog"}}]
    assert ref.check_certificate(case, record, observed, []) == {"status": "unknown", "reason": "inconsistent_observations", "compatible_world_indices": []}


def test_generator_family_count_and_finite_schema():
    cases = ref.build_cases()
    assert len(cases) == 48
    assert len({x["family"] for x in cases}) == 24
    for case in cases:
        assert 2 <= len(case["worlds"]) <= 8
        assert 1 <= len(case["routes"]) <= 5
        assert case["catalog_closed"] is True
        assert set(("observable_files", "observable_grants")) <= case.keys()


def test_all_small_cache_subsets_never_certify_without_witnesses():
    from itertools import combinations
    case = small_case(hidden=True)
    record = ref.reference_record(case)
    coordinates = [(w, r) for w in range(2) for r in range(2)]
    for count in range(5):
        for cache in combinations(coordinates, count):
            result = ref.check_certificate(case, record, [], cache)
            assert result["status"] != "verified"
            expected_negative = (1, 0) in cache and any((w, 1) in cache for w in range(2))
            assert (result["status"] == "infeasible") == expected_negative


def test_conflicting_explicit_signature_charged_and_stops():
    program = p(fx("a", "write", "x", value="a", key="k"), fx("b", "write", "x", value="b", key="k"))
    result = ref.guarded_run(program, {"files": {}, "grants": [["write", "x"]]}, {"files": {"x": "a"}})
    assert result["error"] == "receipt_conflict"
    assert result["charged_calls"] == 2 and result["files"]["x"] == "a"
    assert not result["safe_success"] and not result["trace"][-1]["committed"]


def test_hindsight_cost_includes_actual_observation():
    case = small_case()
    record = ref.reference_record(case)
    assert record["hindsight_certificate_cost"][0]["minimum_positive_total_queries"] == 2
    assert record["hindsight_certificate_cost"][1]["minimum_positive_total_queries"] is None


def test_step_limit_and_quota_are_distinct():
    many_lets = [{"id": str(i), "kind": "let", "name": "x", "value": i} for i in range(101)]
    result = ref.guarded_run(p(*many_lets), {"files": {}, "grants": []}, {})
    assert result["error"] == "step_limit" and result["charged_calls"] == 0
    writes = [fx(str(i), "write", "x", value="ok") for i in range(33)]
    result = ref.guarded_run(p(*writes), {"files": {}, "grants": [["write", "x"]]}, {})
    assert result["error"] == "quota_exhausted" and result["charged_calls"] == 32


def test_frozen_firstpass_if_present():
    directory = ROOT / "work/phase11-reference-firstpass"
    if not (directory / "provenance.json").exists():
        return
    from hashlib import sha256
    provenance = json.loads((directory / "provenance.json").read_text())
    for filename, digest in provenance["artifact_sha256"].items():
        assert sha256((directory / filename).read_bytes()).hexdigest() == digest
    assert provenance["production_modules_consulted"] is False

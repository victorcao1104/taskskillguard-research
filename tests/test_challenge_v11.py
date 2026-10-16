"""Independent challenge expectations; never imports production components."""
from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("challenge_independent", ROOT / "scripts/build_phase11_challenge.py")
challenge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(challenge)


def test_challenge_counts_and_schema():
    cases = challenge.build_cases()
    assert len(cases) == 24
    assert len({c["family"] for c in cases}) == 12
    for c in cases:
        assert c["case_id"].startswith("p11c-") and c["split"] == "challenge"
        assert 4 <= len(c["worlds"]) <= 8
        assert 3 <= 1 + len(c["routes"]) <= 5
        assert all(2 <= len(group) <= 4 for group in challenge.ref.observation_classes(c))


def test_multiworld_positive_and_negative_family_coverage():
    cases = challenge.build_cases()
    records = [challenge.ref.reference_record(c) for c in cases]
    positive, negative = set(), set()
    for case, record in zip(cases, records):
        for cl in record["observation_classes"]:
            if cl["common_safe_routes"] and len(cl["world_indices"]) > 1:
                positive.add(case["family"])
            if not cl["common_safe_routes"] and all(any(e["safe_success"] for e in record["executions"][w]) for w in cl["world_indices"]):
                negative.add(case["family"])
    assert len(positive) >= 6
    assert len(negative) >= 3


def test_structural_families_and_prior_nonduplication():
    audit = challenge.novelty_audit(challenge.build_cases())
    assert audit["unique_original_skeletons"] == 12
    assert not audit["prior_exact_skeleton_matches"]


def test_frozen_source_cohort_preserved():
    from hashlib import sha256
    d = ROOT / "work/phase11-reference-firstpass"
    provenance = json.loads((d / "provenance.json").read_text())
    for filename, digest in provenance["artifact_sha256"].items():
        assert sha256((d / filename).read_bytes()).hexdigest() == digest


def test_challenge_oracle_matches_class_witnesses():
    for case in challenge.build_cases():
        record = challenge.ref.reference_record(case)
        for cl in record["observation_classes"]:
            expected = len(cl["world_indices"]) if cl["common_safe_routes"] else None
            assert cl["minimum_run_queries"] == expected
            for w in cl["world_indices"]:
                cost = record["hindsight_certificate_cost"][w]["minimum_positive_total_queries"]
                assert (cost is None) == (expected is None)


def test_constant_observations_cannot_reduce_cost():
    cases = [c for c in challenge.build_cases() if "no_savings_possible" in c["coverage_tags"]]
    assert cases
    for case in cases:
        record = challenge.ref.reference_record(case)
        for row in record["hindsight_certificate_cost"]:
            assert row["minimum_positive_total_queries"] == len(case["worlds"])


def test_challenge_firstpass_hashes_if_present():
    from hashlib import sha256
    d = ROOT / "work/phase11-challenge-firstpass"
    if not (d / "provenance.json").exists():
        return
    provenance = json.loads((d / "provenance.json").read_text())
    for name, digest in provenance["artifact_sha256"].items():
        assert sha256((d / name).read_bytes()).hexdigest() == digest

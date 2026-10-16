"""Reproduce the original 8,672-state independent main-certificate check.

This is the exact enumeration originally run during reference authoring, saved
as a standalone read-only utility. It imports only the independent reference
author, consumes the case/reference JSONL files, and compares its aggregate
with the preserved validation artifact. No production or API imports, no writes.
"""
from __future__ import annotations

import argparse
import importlib.util
from itertools import combinations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase11_independent_reference", ROOT / "scripts/build_phase11_heldout.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def validate_main(cases, records):
    """Return the exact preserved aggregate schema after exhaustive checks.

    Each allowed observation subset is applied to every actual world. Duplicate
    observation histories (same serialized observation rows) count once per
    case, as in the original run. Each full public world/route cache powerset is
    enumerated, including cells outside the currently compatible worlds. This
    intentionally differs from the challenge checker's compatibility quotient.
    """
    assert len(cases) == len(records)
    checked = 0
    for case, record in zip(cases, records):
        assert case["case_id"] == record["case_id"]
        atoms = reference.observation_atoms(case)
        coordinates = [(world, route) for world in range(len(case["worlds"]))
                       for route in range(record["route_count"])]
        seen = set()
        for count in range(len(atoms) + 1):
            for subset in combinations(atoms, count):
                for actual in case["worlds"]:
                    observations = [dict(kind=atom[0], resource=atom[-1],
                                         answer=reference.observation_answer(case, actual, atom),
                                         **({"op": atom[1]} if atom[0] == "grant" else {}))
                                    for atom in subset]
                    key = reference.stable(observations)
                    if key in seen:
                        continue
                    seen.add(key)
                    compatible = reference.compatible_worlds(case, observations)
                    intrinsic_routes = [route for route in range(record["route_count"])
                                        if all(record["executions"][world][route]["safe_success"]
                                               for world in compatible)]
                    terminal = all(len({reference.stable(reference.observation_answer(
                        case, case["worlds"][world], atom)) for world in compatible}) == 1
                                   for atom in atoms)
                    for mask in range(1 << len(coordinates)):
                        cache = [pair for bit, pair in enumerate(coordinates) if mask >> bit & 1]
                        result = reference.check_certificate(case, record, observations, cache)
                        positives = [route for route in intrinsic_routes
                                     if all((world, route) in cache for world in compatible)]
                        negative = terminal and all(any(
                            (world, route) in cache and not record["executions"][world][route]["safe_success"]
                            for world in compatible) for route in range(record["route_count"]))
                        expected = "verified" if positives else ("infeasible" if negative else "unknown")
                        assert result["status"] == expected, (case["case_id"], observations, cache, result, expected)
                        checked += 1
    return {"certificate_states_exhaustively_checked": checked, "cases": len(cases), "passed": True}


def validate_directory(directory):
    """Read a materialized or ignored first-pass directory and compare artifact."""
    directory = Path(directory)
    cases = [json.loads(line) for line in (directory / "heldout.jsonl").read_text(encoding="utf-8").splitlines() if line]
    records = [json.loads(line) for line in (directory / "reference.jsonl").read_text(encoding="utf-8").splitlines() if line]
    summary = validate_main(cases, records)
    preserved = json.loads((directory / "exhaustive_checker_validation.json").read_text(encoding="utf-8"))
    assert summary == preserved, {"computed": summary, "preserved": preserved}
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path,
                        default=ROOT / "results/phase11/reference/main/first-pass")
    args = parser.parse_args()
    print(json.dumps(validate_directory(args.input_dir), sort_keys=True))


if __name__ == "__main__":
    main()

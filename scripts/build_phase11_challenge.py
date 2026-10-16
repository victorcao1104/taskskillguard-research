"""Prospective, separately disclosed Phase 11 multiworld challenge supplement.

Authored after aggregate-only examination found singleton feasible terminal
classes in the original cohort, before any production outcomes were consulted.
Original first-pass bytes are preserved. Imports only the independent reference
author's frozen helper module, never production modules or experiment results.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
from itertools import combinations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase11_independent_reference", ROOT / "scripts/build_phase11_heldout.py")
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)
B, v, cat, program = ref.Builder, ref.v, ref.cat, ref.program

FAMILIES = ["partial_goal_branch_join", "receipt_dependency_fork_join",
            "shared_snapshot_diamond", "overwrite_then_join_repair",
            "decision_signal_and_nuisance", "hidden_robust_common_route",
            "hidden_grant_route_cover", "private_flag_route_exclusion",
            "unobserved_alias_receipt_split", "constant_observation_aliases",
            "branch_subroutine_exact_count", "three_partition_receipt_fallback"]


def make_family(index, variant):
    name = FAMILIES[index]
    stem = sha256((name + str(variant)).encode()).hexdigest()[:12]
    p = lambda x: "/synthetic/phase11challenge/" + stem + "/" + x
    value = ("totara-483", "pewter:529")[variant]
    bad = "incomplete-" + value
    a, b, c, d = [B(prefix + stem) for prefix in ("original", "alternative", "specific", "third")]
    signal, private, noise, inp, out, aux, left, right, events = [p(x) for x in ("signal", "private", "noise", "input", "out", "aux", "left", "right", "events")]
    nworld = 8 if index in (4, 10) else (6 if index == 11 else 4)
    names = ("signal", "private", "noise", "input", "out", "aux", "left", "right", "events", "alias", "constant", "pointer", "leftin", "rightin", "guard", "scratch", "sink")
    grants = [[op, p(name)] for op in ("read", "write", "delete", "emit") for name in names]
    worlds = []
    for i in range(nworld):
        group = i // 2 if index == 11 else (i // (nworld // 2))
        world = {"files": {signal: str(group), private: str(i % 2), noise: str((i // 2) % 2),
                           inp: value, p("alias"): str(group), p("constant"): value,
                           p("leftin"): value, p("rightin"): value,
                           p("pointer"): p("leftin") if i % 2 == 0 else p("rightin")},
                 "grants": deepcopy(grants)}
        worlds.append(world)
    goal = {"files": {out: value}}
    observe_files, observe_grants = [signal], []
    functions, tags = {}, []
    robust = program([b.fx("write", out, value=value)])
    specific = program([c.fx("read", private, out="h"), c.branch(v("h"), "0", [c.fx("write", out, value=value)], [c.fx("write", out, value=bad)])])
    routes = [robust, specific]
    if index == 0:
        steps = [a.fx("read", signal, out="s"), a.fx("read", private, out="h"), a.fx("write", out, value=value),
                 a.branch(v("s"), "0", [a.call("join")], [a.fx("write", aux, value=bad), a.call("join")]),
                 a.fx("read", aux, out="joined"), a.fx("emit", events, value=v("joined"))]
        functions = {"join": [a.branch(v("h"), "0", [a.fx("write", aux, value=value)], [a.fx("delete", aux), a.fx("write", aux, value=value)])]}
        goal["files"][aux] = value
        goal["emits"] = [{"resource": events, "value": value, "count": 1}]
        routes = [program([b.fx("write", out, value=value), b.fx("write", aux, value=value), b.fx("emit", events, value=value)]), specific]
        tags += ["partial_goal_join", "robust_shared_route"]
    elif index == 1:
        steps = [a.fx("read", inp, out="seed", key="root"), a.fx("write", left, value=v("seed"), key="left-edge"),
                 a.fx("write", right, value=v("seed"), key="right-edge"), a.fx("read", left, out="l", key="left-snapshot"),
                 a.fx("read", right, out="r", key="right-snapshot"), a.branch(v("l"), v("r"),
                 [a.fx("write", out, value=v("l")), a.fx("emit", events, value=value, key="join")], [a.fx("delete", out)])]
        goal["files"].update({left: value, right: value})
        goal["emits"] = [{"resource": events, "value": value, "count": 1}]
        routes = [program([b.fx("write", left, value=value), b.fx("write", right, value=value), b.fx("write", out, value=value), b.fx("emit", events, value=value)]), specific]
        tags += ["receipt_dependency_dag", "robust_shared_route"]
    elif index == 2:
        steps = [a.call("left_leg"), a.fx("write", inp, value=bad), a.call("right_leg"),
                 a.fx("read", left, out="l"), a.fx("read", right, out="r"),
                 a.branch(v("l"), v("r"), [a.call("merge")], [a.fx("write", out, value=bad)])]
        functions = {"common": [a.fx("read", inp, out="snapshot", key="shared-root")],
                     "left_leg": [a.call("common"), a.fx("write", left, value=v("snapshot"))],
                     "right_leg": [a.call("common"), a.fx("write", right, value=v("snapshot"))],
                     "merge": [a.fx("write", out, value=v("l"))]}
        tags += ["read_snapshot", "subroutine_diamond", "robust_shared_route"]
    elif index == 3:
        steps = [a.fx("read", private, out="h"), a.fx("read", signal, out="s"),
                 a.branch(v("h"), "0", [a.fx("write", out, value=bad)], [a.fx("write", out, value=value)]),
                 a.loop(2, [a.fx("write", aux, value=v("s"), key="stable")]), a.fx("read", aux, out="saved"),
                 a.branch(v("saved"), v("s"), [a.fx("write", out, value=value)], [a.fx("delete", out)])]
        tags += ["overwrite_join", "robust_shared_route"]
    elif index == 4:
        observe_files = [signal, noise, p("alias")]
        steps = [a.fx("read", signal, out="s"), a.fx("read", noise, out="n"),
                 a.branch(v("n"), "0", [a.let("decision", v("s"))], [a.let("decision", v("s"))]),
                 a.branch(v("decision"), "0", [a.fx("write", out, value=value)], [a.fx("write", out, value=bad)]),
                 a.fx("read", out, out="check")]
        routes = [program([b.fx("read", signal, out="s"), b.branch(v("s"), "1", [b.fx("write", out, value=value)], [b.fx("delete", out)])]),
                  program([c.fx("read", signal, out="s"), c.fx("read", private, out="h"), c.branch(v("h"), "0", [c.fx("write", out, value=bad)], [c.fx("delete", out)])])]
        tags += ["decision_vs_world_entropy", "redundant_observation_alias", "partition_specific_routes"]
    elif index == 5:
        observe_files = []
        steps = [a.fx("read", private, out="h"), a.call("stage"), a.fx("read", left, out="l"),
                 a.branch(v("h"), "0", [a.fx("write", out, value=v("l"))], [a.fx("write", out, value=bad)]),
                 a.fx("write", right, value=v("l"))]
        functions = {"stage": [a.fx("read", inp, out="x"), a.loop(2, [a.fx("write", left, value=v("x"), key="stage")])]}
        tags += ["hidden_feasible_class", "robust_shared_route", "no_savings_possible"]
    elif index == 6:
        observe_files = []
        for i, world in enumerate(worlds):
            world["grants"].remove(["emit", right if i % 2 == 0 else left])
        steps = [a.fx("read", inp, out="x"), a.let("payload", cat(v("x"), "-checked")),
                 a.fx("emit", left, value=v("payload"), key="choice"), a.call("complete")]
        functions = {"complete": [a.fx("write", out, value=value)]}
        routes = [program([b.fx("emit", right, value=value, key="choice"), b.fx("write", out, value=value)]),
                  program([c.fx("emit", left, value=value), c.fx("emit", right, value=value), c.fx("write", out, value=value)])]
        tags += ["forall_exists_not_exists_forall", "hidden_grants", "no_common_route"]
    elif index == 7:
        steps = [a.fx("read", private, out="h"), a.fx("write", aux, value=value), a.loop(2, [a.call("test")]),
                 a.fx("read", aux, out="partial"), a.branch(v("partial"), value, [a.fx("write", out, value=value)], [a.fx("write", out, value=bad)])]
        functions = {"test": [a.branch(v("h"), "0", [a.let("keep", value)], [a.fx("write", aux, value=bad)])]}
        routes = [program([b.fx("read", private, out="h"), b.branch(v("h"), "1", [b.fx("write", out, value=value)], [b.fx("write", out, value=bad)])]),
                  program([c.fx("write", aux, value=value), c.fx("read", signal, out="s")])]
        tags += ["forall_exists_not_exists_forall", "private_branch", "no_common_route"]
    elif index == 8:
        steps = [a.fx("read", p("leftin"), out="saved", key="alias"), a.fx("read", p("pointer"), out="ptr"),
                 a.let("resolved", v("ptr")), a.call("resolve"), a.fx("write", aux, value=v("saved"))]
        functions = {"resolve": [a.fx("read", v("resolved"), out="saved", key="alias"), a.fx("write", out, value=v("saved"))]}
        routes = [program([b.fx("read", p("rightin"), out="saved", key="alias"), b.fx("read", p("pointer"), out="ptr"), b.fx("read", v("ptr"), out="saved", key="alias"), b.fx("write", out, value=v("saved"))]),
                  program([c.fx("write", out, value=value), c.fx("emit", p("guard"), value=value)])]
        for world in worlds:
            world["grants"].remove(["emit", p("guard")])
        tags += ["forall_exists_not_exists_forall", "hidden_alias", "no_common_route", "receipt_conflict"]
    elif index == 9:
        observe_files = [p("constant"), p("alias")]
        for world in worlds:
            world["files"][p("alias")] = value
        steps = [a.fx("read", p("constant"), out="x"), a.fx("read", p("alias"), out="y"),
                 a.branch(v("x"), v("y"), [a.loop(2, [a.fx("emit", events, value=value, key="once")])], [a.fx("delete", out)]),
                 a.fx("write", out, value=v("x")), a.fx("read", out, out="z"), a.fx("write", aux, value=v("z"))]
        goal["emits"] = [{"resource": events, "value": value, "count": 1}]
        routes = [program([b.fx("emit", events, value=value), b.fx("write", out, value=value)]), specific]
        tags += ["constant_observation_alias", "no_savings_possible", "hidden_feasible_class"]
    elif index == 10:
        steps = [a.fx("read", signal, out="s"), a.fx("read", private, out="h"),
                 a.branch(v("s"), "0", [a.loop(2, [a.call("emit_one")])], [a.call("emit_two")]),
                 a.branch(v("h"), "0", [a.fx("write", out, value=value)], [a.fx("write", out, value=bad), a.fx("write", out, value=value)])]
        functions = {"emit_one": [a.fx("emit", events, value=value)],
                     "emit_two": [a.fx("emit", events, value=value), a.fx("emit", events, value=value)]}
        goal["emits"] = [{"resource": events, "value": value, "count": 2}]
        routes = [program([b.loop(2, [b.fx("emit", events, value=value)]), b.fx("write", out, value=value)]), specific,
                  program([d.loop(3, [d.fx("emit", events, value=value, key="one")]), d.fx("write", out, value=value)])]
        tags += ["four_world_feasible_class", "exact_emission_count", "robust_shared_route"]
    else:
        steps = [a.fx("read", signal, out="s"), a.fx("write", left, value=value, key="handoff"),
                 a.branch(v("s"), "0", [a.fx("write", left, value=value, key="handoff")],
                          [a.branch(v("s"), "1", [a.fx("write", right, value=value, key="handoff")], [a.fx("write", left, value=bad, key="handoff")])]),
                 a.fx("read", left, out="leftvalue"), a.fx("write", out, value=v("leftvalue"))]
        routes = [program([b.fx("write", right, value=value, key="handoff"), b.fx("write", out, value=value)]), specific]
        tags += ["three_observation_classes", "cross_route_keys", "robust_shared_route", "receipt_conflict"]
    original = program(steps, functions)
    return {"case_id": f"p11c-{name}-{variant}", "family": "p11c_" + name,
            "split": "challenge", "generation": {"version": 1, "variant": variant, "lexical_variant": variant},
            "program": original, "routes": routes, "worlds": worlds, "goal": goal,
            "observable_files": observe_files, "observable_grants": observe_grants,
            "catalog_closed": True, "coverage_tags": tags,
            "source": "# Synthetic multiworld challenge\n\n```tsg-workflow\n" + json.dumps(original, ensure_ascii=False, indent=2) + "\n```\n"}


def build_cases():
    return [make_family(i, variant) for i in range(12) for variant in (0, 1)]


def novelty_audit(cases):
    result = ref.novelty_audit(cases)
    prior_path = ROOT / "work/phase11-reference-firstpass/heldout.jsonl"
    prior = defaultdict(list)
    for row in [json.loads(line) for line in prior_path.read_text().splitlines()]:
        for index, prog in enumerate([row["program"], *row["routes"]]):
            prior[ref.stable(ref.structural_form(prog))].append({"case_id": row["case_id"], "route_index": index})
    for case in cases:
        matches = prior.get(ref.stable(ref.structural_form(case["program"])), [])
        if matches:
            result["prior_exact_skeleton_matches"].append({"case_id": case["case_id"], "prior_exact_skeleton_matches": matches})
    result["prior_sources"].append({"path": str(prior_path.relative_to(ROOT)), "sha256": sha256(prior_path.read_bytes()).hexdigest()})
    result["limitation"] = "24 cases are 12 independently authored templates; variants share structure and all templates share the finite DSL. This prospective supplement responds to aggregate structural coverage, not controller outcomes."
    return result


def coverage(cases, records):
    positive, negative, no_savings = set(), set(), set()
    class_sizes, status, costs = Counter(), Counter(), Counter()
    for case, record in zip(cases, records):
        for cl in record["observation_classes"]:
            class_sizes[len(cl["world_indices"]) ] += 1
            status[cl["inherent_status"]] += 1
            if cl["common_safe_routes"] and len(cl["world_indices"]) > 1:
                positive.add(case["family"])
            if not cl["common_safe_routes"] and all(any(e["safe_success"] for e in record["executions"][w]) for w in cl["world_indices"]):
                negative.add(case["family"])
        for row in record["hindsight_certificate_cost"]:
            costs[str(row["minimum_positive_total_queries"])] += 1
        if all(row["minimum_positive_total_queries"] == len(case["worlds"]) for row in record["hindsight_certificate_cost"]):
            no_savings.add(case["family"])
    novelty = novelty_audit(cases)
    checks = {"24_cases": len(cases) == 24, "12_families": len({c["family"] for c in cases}) == 12,
              "two_variants_per_family": set(Counter(c["family"] for c in cases).values()) == {2},
              "12_distinct_original_skeletons": novelty["unique_original_skeletons"] == 12,
              "no_prior_exact_skeleton": not novelty["prior_exact_skeleton_matches"],
              "worlds4to8": all(4 <= len(c["worlds"]) <= 8 for c in cases),
              "routes3to5_total": all(3 <= 1 + len(c["routes"]) <= 5 for c in cases),
              "terminal_class_cardinality2to4": all(2 <= n <= 4 for n in class_sizes),
              "six_multiworld_feasible_families": len(positive) >= 6,
              "three_forall_exists_not_exists_forall_families": len(negative) >= 3,
              "no_savings_present": bool(no_savings)}
    return {"passed": all(checks.values()), "checks": checks,
            "multiworld_feasible_family_count": len(positive),
            "forall_exists_not_exists_forall_family_count": len(negative),
            "no_savings_possible_family_count": len(no_savings),
            "terminal_class_cardinality_histogram": dict(class_sizes),
            "terminal_class_status_counts": dict(status), "hindsight_minimum_cost_histogram": dict(costs),
            "novelty": novelty}


def checker_validation(cases, records, exhaustive_cell_limit=16):
    """Enumerate cache powersets where tractable; quotient irrelevant cells out.

    Cache entries outside compatibility never affect this checker. Observation
    sets with identical compatibility are equivalent for finite entailment. Broad
    pre-observation states above the limit get boundary witnesses, explicitly
    reported separately, without claiming exhaustive coverage of those states.
    """
    checked, exhaustive_partitions, boundary_partitions, boundaries = 0, 0, 0, 0
    for case, record in zip(cases, records):
        atoms, seen = ref.observation_atoms(case), set()
        for count in range(len(atoms) + 1):
            for subset in combinations(atoms, count):
                for actual in case["worlds"]:
                    observed = [{"kind": a[0], "resource": a[-1], "answer": ref.observation_answer(case, actual, a),
                                 **({"op": a[1]} if a[0] == "grant" else {})} for a in subset]
                    compatible = ref.compatible_worlds(case, observed)
                    key = tuple(compatible)
                    if key in seen:
                        continue
                    seen.add(key)
                    coords = [(w, r) for w in compatible for r in range(record["route_count"])]
                    terminal = all(len({ref.stable(ref.observation_answer(case, case["worlds"][w], a)) for w in compatible}) == 1 for a in atoms)
                    def check(cache):
                        result = ref.check_certificate(case, record, observed, cache)
                        cached = set(cache)
                        positives = [r for r in range(record["route_count"]) if all((w, r) in cached and record["executions"][w][r]["safe_success"] for w in compatible)]
                        negatives = terminal and all(any((w, r) in cached and not record["executions"][w][r]["safe_success"] for w in compatible) for r in range(record["route_count"]))
                        expected = "verified" if positives else ("infeasible" if negatives else "unknown")
                        assert result["status"] == expected
                    if len(coords) <= exhaustive_cell_limit:
                        exhaustive_partitions += 1
                        for mask in range(1 << len(coords)):
                            check([p for bit, p in enumerate(coords) if mask & (1 << bit)])
                            checked += 1
                    else:
                        boundary_partitions += 1
                        caches = [[], coords]
                        for r in range(record["route_count"]):
                            witness = [(w, r) for w in compatible]
                            caches.append(witness)
                            caches.extend([witness[:i] + witness[i+1:] for i in range(len(witness))])
                        for cache in caches:
                            check(cache)
                            boundaries += 1
    return {"passed": True, "exhaustive_cell_limit": exhaustive_cell_limit,
            "exhaustive_compatibility_partitions": exhaustive_partitions,
            "exhaustive_cache_states": checked, "boundary_only_partitions": boundary_partitions,
            "boundary_cache_states": boundaries,
            "limit": "Powersets with >16 compatible world-route cells are boundary-tested only. Outside-compatible cache cells and duplicate observational partitions are quotient out."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work/phase11-challenge-firstpass")
    args = parser.parse_args()
    names = ["challenge.jsonl", "reference_challenge.jsonl", "coverage.json", "checker_validation.json", "provenance.json"]
    if any((args.output_dir / name).exists() for name in names):
        raise FileExistsError("Refusing to replace challenge first pass")
    original_dir = ROOT / "work/phase11-reference-firstpass"
    original_provenance = json.loads((original_dir / "provenance.json").read_text())
    for name, digest in original_provenance["artifact_sha256"].items():
        assert sha256((original_dir / name).read_bytes()).hexdigest() == digest
    cases = build_cases()
    records = [ref.reference_record(c) for c in cases]
    audit = coverage(cases, records)
    validation = checker_validation(cases, records)
    pretty = lambda x: (json.dumps(x, indent=2, sort_keys=True) + "\n").encode()
    outputs = {"challenge.jsonl": ref.jsonl_bytes(cases), "reference_challenge.jsonl": ref.jsonl_bytes(records),
               "coverage.json": pretty(audit), "checker_validation.json": pretty(validation)}
    provenance = {"schema_version": 1, "authored_at_utc": datetime.now(timezone.utc).isoformat(),
                  "reason_for_supplement": "Aggregate-only first-pass review showed all feasible main terminal classes were singletons. Prospectively requested before production outcome access; no cases replaced.",
                  "source_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in ("scripts/build_phase11_challenge.py", "scripts/build_phase11_heldout.py", "src/tsg/truth_v6.py", "tests/test_challenge_v11.py", "docs/phase11_challenge.md")},
                  "original_firstpass_artifact_sha256": original_provenance["artifact_sha256"],
                  "original_firstpass_provenance_sha256": sha256((original_dir / "provenance.json").read_bytes()).hexdigest(),
                  "artifact_sha256": {name: sha256(raw).hexdigest() for name, raw in outputs.items()},
                  "model_outcomes_consulted": False, "production_modules_consulted": False,
                  "reference_implementation": "Frozen independent Phase 11 author interpreter plus truth_v6 diagnostic runs",
                  "case_count": len(cases), "family_count": len(FAMILIES), "coverage_passed": audit["passed"],
                  "first_pass_policy": "Write once; no replacement or outcome-based tuning; report supplement separately."}
    outputs["provenance.json"] = pretty(provenance)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in outputs.items():
        with (args.output_dir / name).open("xb") as file:
            file.write(raw)
    print(json.dumps({"case_count": len(cases), "family_count": len(FAMILIES), "checks": audit["checks"],
                      "checker_validation": validation, "generator_sha256": provenance["source_sha256"]["scripts/build_phase11_challenge.py"],
                      "challenge_sha256": provenance["artifact_sha256"]["challenge.jsonl"]}))
    if not audit["passed"]:
        raise SystemExit("Challenge first-pass shortcomings preserved; do not tune cases")


if __name__ == "__main__":
    main()

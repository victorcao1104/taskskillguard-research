"""Independent typed aggregation over the Phase 6 reference interpreter.

Only reference ASTs are executed. Source text, model answers, and production
parser/executor/recovery code are not consulted. Each route and intervention
starts from the same supplied world through the reference interpreter.
"""
from __future__ import annotations

from .truth_v6 import ReferenceError, run, static_sites


AXES = ("authorization", "current_route_required", "catalog_required")


def _world_label(site, baseline, suppressed, executions, legal_indices, closed):
    occurrences = [event for event in baseline["trace"] if event["id"] == site]
    identities = {(event["op"], event["resource"]) for event in occurrences}
    avoiding = [index for index in legal_indices
                if identities and identities.isdisjoint(
                    (event["op"], event["resource"]) for event in executions[index]["trace"])]
    values = dict.fromkeys(AXES, "not_applicable")
    reasons = {axis: [] for axis in AXES}
    if occurrences:
        values["authorization"] = "yes" if all(event["authorized"] for event in occurrences) else "no"
        if baseline["goal"]:
            values["current_route_required"] = "no" if suppressed["goal"] else "yes"
        else:
            reasons["current_route_required"].append("baseline_failure")
        if not legal_indices:
            reasons["catalog_required"].append("no_feasible_route")
        elif avoiding:
            values["catalog_required"] = "no"
        elif closed:
            values["catalog_required"] = "yes"
        else:
            values["catalog_required"] = "unknown"
            reasons["catalog_required"].append("open_catalog")
    else:
        for axis in AXES:
            reasons[axis].append("inactive")
    return {"id": site, **values, "reasons": reasons,
            "occurred": bool(occurrences),
            "all_occurrences_authorized": all(event["authorized"] for event in occurrences),
            "baseline_success": baseline["goal"], "suppressed_success": suppressed["goal"],
            "legal_routes": list(legal_indices), "avoiding_routes": avoiding,
            "intervention_error": suppressed["error"]}


def evaluate_case(case):
    """Return typed aggregate labels plus fully inspectable per-world audits.

    Uniform values are retained, including unknown and not_applicable. Any
    disagreement becomes unknown. Mixing applicability records
    partial_applicability; distinct applicable values record world_disagreement.
    Both causes can be present in an aggregate over three or more worlds.
    """
    sites = static_sites(case["program"])
    if not isinstance(case.get("worlds"), list) or not case["worlds"]:
        raise ReferenceError("empty_worlds")
    if type(case.get("catalog_closed")) is not bool:
        raise ReferenceError("invalid_catalog_closure")
    routes = [case["program"], *case.get("routes", [])]
    records = []
    for index, world in enumerate(case["worlds"]):
        executions = [run(route, world, case["goal"]) for route in routes]
        baseline = executions[0]
        legal_indices = [i for i, execution in enumerate(executions)
                         if execution["goal"] and all(event["authorized"] for event in execution["trace"])]
        labels = [_world_label(site["id"], baseline,
                               run(case["program"], world, case["goal"], suppress=site["id"]),
                               executions, legal_indices, case["catalog_closed"])
                  for site in sites]
        records.append({"index": index, "baseline": baseline, "routes": executions,
                        "legal_route_indices": legal_indices, "labels": labels})
    aggregate = []
    for position, site in enumerate(sites):
        row = {"id": site["id"], "reasons": {}}
        for axis in AXES:
            values = {record["labels"][position][axis] for record in records}
            row[axis] = next(iter(values)) if len(values) == 1 else "unknown"
            reasons = {reason for record in records
                       for reason in record["labels"][position]["reasons"][axis]}
            if len(values) > 1 and "not_applicable" in values:
                reasons.add("partial_applicability")
            if len(values - {"not_applicable"}) > 1:
                reasons.add("world_disagreement")
            row["reasons"][axis] = sorted(reasons)
        aggregate.append(row)
    return {"case_id": case["case_id"], "labels": aggregate, "worlds": records,
            "catalog_closed": case["catalog_closed"], "route_count": len(routes)}

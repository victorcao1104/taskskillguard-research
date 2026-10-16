"""Goal-relevant initial queries selected only from public finite hypotheses.

The trusted reader is the immutable Phase 9 capability. The caller supplies a
budgeted, fault-blind feasibility probe; this module never runs an interpreter.
"""

from copy import deepcopy
from itertools import combinations

from .observation_v9 import (TrustedObservations, observable_queries, _answer,
                             _classify, resolve_gate as _authorization_gate)


def _goal_query(worlds, compatible, profiles, queries, remaining):
    """Separate route-feasibility disagreements, with deterministic tie breaks."""
    pairs = [(a, b) for a, b in combinations(compatible, 2)
             if profiles[a] != profiles[b]]
    if not pairs:
        return None
    separated = {key: {pair for pair in pairs
                      if _answer(worlds[pair[0]], key) != _answer(worlds[pair[1]], key)}
                 for key in queries}
    useful = [key for key in queries if separated[key]]
    target = set(pairs)
    for count in range(1, min(remaining, len(useful)) + 1):
        for subset in combinations(useful, count):
            if set().union(*(separated[key] for key in subset)) == target:
                return subset[0]
    return min(useful, key=lambda key: (-len(separated[key]), key)) if useful else None


def resolve_gate(worlds, sites, facts, reader, queries, budget, mode,
                 observation_mode="goal", goal_probe=None):
    """Authorization observations first, then optional goal-feasibility reads.

    ``goal_probe(compatible, allowed)`` returns a mapping of world index to a
    tuple of per-route feasibility booleans, or None when its shared planning
    budget cannot establish every profile. It must use only public hypotheses.
    Missing/incomplete authorization facts are never completed by these probes.
    """
    gate = _authorization_gate(worlds, sites, facts, reader, queries, budget, mode)
    gate.update(goal_observation_count=0, goal_observation_log=[])
    if observation_mode != "goal" or mode != "conditional" or goal_probe is None:
        return gate
    compatible = gate["compatible_world_indices"]
    used = {tuple(row["query"]) for row in gate["observation_log"]}
    unused = [key for key in queries if key not in used]
    while (not gate["observation_mismatch"] and len(compatible) > 1 and unused
           and gate["observation_count"] < budget):
        profiles = goal_probe(list(compatible), set(gate["allowed_ids"]))
        if profiles is None:
            break
        # A robustly feasible route already permits execution without a query.
        if any(all(profiles[index][route] for index in compatible)
               for route in range(len(profiles[compatible[0]]))):
            break
        key = _goal_query(worlds, compatible, profiles, unused,
                          budget - gate["observation_count"])
        if key is None:
            break
        answer = reader.query(key)
        unused.remove(key)
        row = {"query": list(key), "answer": deepcopy(answer),
               "purpose": "goal_feasibility", "provenance": "trusted_initial_reader",
               "compatible_before": list(compatible),
               "feasible_routes_by_hypothesis": {
                   str(index): [r for r, feasible in enumerate(profiles[index]) if feasible]
                   for index in compatible}}
        gate["goal_observation_log"].append(deepcopy(row))
        gate["observation_log"].append(row)
        gate["observation_count"] += 1
        gate["goal_observation_count"] += 1
        if answer.get("available"):
            actual = ((answer.get("present"), answer.get("value")) if key[0] == "file"
                      else answer.get("value"))
            compatible = [index for index in compatible if _answer(worlds[index], key) == actual]
            gate["compatible_world_indices"] = compatible
            gate["observation_mismatch"] = not compatible
        states = _classify(facts, compatible, sites)
        gate["allowed_ids"] = {site for site, state in states.items() if state == "allow"}
        gate["unresolved_gate_ids"] = sorted(site for site, state in states.items()
                                              if state == "unresolved")
        gate["gate_log"].append({"stage": "goal_observation", "query": list(key),
            "compatible_world_indices": list(compatible), "states": dict(states),
            "observation_mismatch": gate["observation_mismatch"]})
    return gate

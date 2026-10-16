"""Trusted, immutable initial observations over a declared finite world set.

The controller receives a query capability, never the selected world index.
Declared worlds are public hypotheses. Observability limits apply to the actual
initial state; they do not hide public case descriptions.
"""

from copy import deepcopy
from itertools import combinations

from .runtime_v6 import _require, _world


class TrustedObservations:
    """Snapshot before any workflow effects; query results carry presence bits."""

    def __init__(self, world, observable_files, observable_grants):
        self._files, self._grants = _world(world)
        self._available = ({("file", path) for path in observable_files}
                           | {("grant", *grant) for grant in observable_grants})

    def query(self, key):
        key = tuple(key)
        if key not in self._available:
            return {"available": False}
        if key[0] == "file":
            return {"available": True, "present": key[1] in self._files,
                    "value": self._files.get(key[1])}
        return {"available": True, "value": tuple(key[1:]) in self._grants}


def observable_queries(case):
    worlds = case["worlds"]
    files = case.get("observable_files", sorted({p for w in worlds for p in w["files"]}))
    grants = case.get("observable_grants", sorted({tuple(g) for w in worlds for g in w.get("grants", [])}))
    _require(isinstance(files, (list, tuple)) and all(isinstance(p, str) for p in files),
             "observable_files must be a list of paths")
    _require(isinstance(grants, (list, tuple)) and all(isinstance(g, (list, tuple))
             and len(g) == 2 and all(isinstance(x, str) for x in g) for g in grants),
             "observable_grants must be a list of operation/resource pairs")
    return sorted({("file", p) for p in files} | {("grant", *g) for g in grants})


def _answer(world, key):
    if key[0] == "file":
        return (key[1] in world["files"], world["files"].get(key[1]))
    return tuple(key[1:]) in {tuple(g) for g in world.get("grants", [])}


def _classify(facts, compatible, sites):
    result = {}
    for site in sites:
        statuses = [facts.get(index, {}).get(site, "unresolved") for index in compatible]
        result[site] = ("allow" if statuses and all(s in {"authorized", "inactive"} for s in statuses)
                        else "deny" if statuses and all(s == "unauthorized" for s in statuses)
                        else "unresolved")
    return result


def _next_query(worlds, facts, compatible, sites, queries, remaining):
    """Minimum cardinality separating set, lexical tie break; query its first key.

    If no set within budget separates every safety disagreement, take the single
    query separating the most disagreeing pairs. Actual answers are not used.
    """
    def status(index, site):
        value = facts.get(index, {}).get(site, "unresolved")
        return "safe" if value in {"authorized", "inactive"} else value
    pairs = [(a, b) for a, b in combinations(compatible, 2)
             if any(status(a, site) != status(b, site) for site in sites)]
    separated = {key: {pair for pair in pairs
                      if _answer(worlds[pair[0]], key) != _answer(worlds[pair[1]], key)}
                 for key in queries}
    useful = [key for key in queries if separated[key]]
    if not useful or not pairs:
        return None
    target = set(pairs)
    for count in range(1, min(remaining, len(useful)) + 1):
        for subset in combinations(useful, count):
            if set().union(*(separated[key] for key in subset)) == target:
                return subset[0]
    return min(useful, key=lambda key: (-len(separated[key]), key))


def resolve_gate(worlds, sites, facts, reader, queries, budget, mode):
    """Reduce uncertainty only with charged trusted initial observations."""
    compatible = list(range(len(worlds)))
    global_authorization = {}
    for site in sites:
        values = {facts.get(index, {}).get(site, "unresolved") for index in compatible}
        global_authorization[site] = ({"authorized": "yes", "unauthorized": "no",
            "inactive": "not_applicable"}.get(next(iter(values)), "unknown")
            if len(values) == 1 else "unknown")
    global_states = {site: {"yes": "allow", "no": "deny",
        "not_applicable": "inactive"}.get(value, "unresolved")
        for site, value in global_authorization.items()}
    states = (_classify(facts, compatible, sites) if mode == "conditional" else dict(global_states))
    log, observations, unused = [], [], list(queries)
    mismatch = False
    log.append({"stage": "global", "compatible_world_indices": list(compatible),
                "states": dict(global_states), "typed_authorization": dict(global_authorization)})
    if mode == "conditional":
        log.append({"stage": "conditional", "compatible_world_indices": list(compatible),
                    "states": dict(states)})
    while mode == "conditional" and "unresolved" in states.values() and len(observations) < budget:
        key = _next_query(worlds, facts, compatible, sites, unused, budget - len(observations))
        if key is None:
            break
        answer = reader.query(key)
        unused.remove(key)
        observations.append({"query": list(key), "answer": deepcopy(answer)})
        if answer.get("available"):
            actual = ((answer.get("present"), answer.get("value")) if key[0] == "file"
                      else answer.get("value"))
            compatible = [index for index in compatible if _answer(worlds[index], key) == actual]
            mismatch = not compatible
            states = _classify(facts, compatible, sites)
        log.append({"stage": "observation", "query": list(key),
                    "compatible_world_indices": list(compatible), "states": dict(states),
                    "observation_mismatch": mismatch})
        if mismatch:
            break
    return {"allowed_ids": {site for site, state in states.items() if state == "allow"},
            "global_authorization": global_authorization,
            "global_unknown_ids": sorted(site for site, value in global_authorization.items()
                                         if value == "unknown"),
            "unresolved_gate_ids": sorted(site for site, state in states.items() if state == "unresolved"),
            "compatible_world_indices": compatible, "gate_log": log,
            "observation_log": observations, "observation_count": len(observations),
            "observation_mismatch": mismatch}

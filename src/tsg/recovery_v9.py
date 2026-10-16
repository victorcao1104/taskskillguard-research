"""Budgeted trusted gating and receipt-aware recovery over the frozen v6 VM.

Public finite worlds are hypotheses. Only the environment uses ``world_index``;
selection uses those hypotheses, charged observations and observed gateway events.
No private reference program, model result or future fault schedule is read.
"""

from copy import deepcopy
import json

from .observation_v9 import TrustedObservations, observable_queries, resolve_gate
from .recovery_v7 import FAULTS as _OLD_FAULTS, _FaultMachine
from .runtime_v6 import (STEP_LIMIT, _Machine, _goal, _require, _result, _sites,
                         _validate, parse_source)


POLICIES = frozenset({"priority", "calls", "risk"})
RISK_WEIGHTS = {"read": 0, "write": 1, "delete": 2, "emit": 8}
FAULT_SHIFTS = {"mixed_known_then_ambiguous": {1: "known_after", 2: "ambiguous_after"},
                "late_ambiguous": {3: "ambiguous_after"}}
FAULTS = (*_OLD_FAULTS, *FAULT_SHIFTS)
_RETRYABLE = frozenset({"transient_before", "known_after"})


class _FaultAdapter(_FaultMachine):
    """New schedules delegate each dispatch to the frozen gateway unchanged."""

    def __init__(self, world, quota, fault):
        super().__init__(world, quota, fault if fault in _OLD_FAULTS else "none")
        self._fault_name = fault
        if fault in FAULT_SHIFTS:
            self._schedule = dict(FAULT_SHIFTS[fault])


def _step_bound(program):
    functions = program.get("functions", {})
    def count(steps):
        total = 0
        for step in steps:
            total += 1
            if step["kind"] == "if":
                total += max(count(step["then"]), count(step["else"]))
            elif step["kind"] == "repeat":
                total += step["count"] * count(step["body"])
            elif step["kind"] == "call":
                total += count(functions[step["fn"]])
            if total >= STEP_LIMIT:
                return STEP_LIMIT
        return total
    return count(program["steps"])


class _Budget:
    def __init__(self, limit):
        self.limit = limit
        self.primitives = self.steps = self.effects = 0
        self.audit_calls = self.audit_steps = self.audit_effects = 0
        self.cache_hits = self.cache_misses = 0
        self.exhausted = False

    @property
    def used(self):
        return self.primitives + self.steps

    def admits(self, bound):
        admitted = self.used + bound <= self.limit
        self.exhausted |= not admitted
        return admitted

    def record(self, probe, audit=False):
        self.primitives += 1
        self.steps += probe.steps
        self.effects += len(probe.trace)
        if audit:
            self.audit_calls += 1
            self.audit_steps += probe.steps
            self.audit_effects += len(probe.trace)


def _cache_key(program, machine, route, goal, allowed, quota):
    """All semantically relevant observed state, including stale read receipts."""
    return json.dumps({"program": program, "files": machine.files,
        "grants": sorted(machine.grants), "emits": machine.emits,
        "receipts": sorted((list(k), v) for k, v in machine.receipts.items()),
        "signatures": sorted((list(k), list(v)) for k, v in machine.signatures.items()),
        "gate": None if allowed is None else sorted(allowed), "route": 0 if route == 0 else 1,
        "quota": quota, "goal": goal}, sort_keys=True, separators=(",", ":"))


def _copy_probe(machine):
    probe = _Machine({"files": machine.files, "grants": sorted(machine.grants)},
                     STEP_LIMIT + 1, reuse=True)
    probe.emits = deepcopy(machine.emits)
    probe.receipts = deepcopy(machine.receipts)
    probe.signatures = deepcopy(machine.signatures)
    return probe


def _risk(trace):
    return sum(RISK_WEIGHTS[event["op"]] for event in trace
               if event["charged"] and event["authorized"]
               and event["status"] not in {"model_gate", "receipt_conflict"})


def _evidence_facts(evidence, worlds, sites):
    _require(isinstance(evidence, dict), "authorization_evidence must be a world mapping")
    facts = {}
    for index in range(len(worlds)):
        rows = evidence.get(str(index), evidence.get(index, []))
        _require(isinstance(rows, list), "authorization evidence world must contain a list")
        facts[index] = {}
        for row in rows:
            _require(isinstance(row, dict) and row.get("id") in sites
                     and type(row.get("occurred")) is bool
                     and type(row.get("all_occurrences_authorized")) is bool
                     and row["id"] not in facts[index], "invalid authorization evidence")
            facts[index][row["id"]] = ("inactive" if not row["occurred"] else
                "authorized" if row["all_occurrences_authorized"] else "unauthorized")
    return facts


def _audit_facts(program, worlds, sites, budget, use_cache):
    facts, memo = {}, {}
    for index, world in enumerate(worlds):
        machine = _Machine(world, STEP_LIMIT + 1, reuse=False, enforce=False)
        key = _cache_key(program, machine, 0, {}, None, STEP_LIMIT + 1)
        if use_cache and key in memo:
            budget.cache_hits += 1
            facts[index] = deepcopy(memo[key])
            continue
        budget.cache_misses += 1
        if not budget.admits(1 + _step_bound(program)):
            facts[index] = {}
            continue
        error = machine.run(program)
        budget.record(machine, audit=True)
        statuses = {}
        for site in sites:
            events = [event for event in machine.trace if event["id"] == site]
            statuses[site] = ("unauthorized" if any(not e["authorized"] for e in events)
                              else "unresolved" if error is not None else
                              "authorized" if events else "inactive")
        facts[index] = statuses
        if use_cache:
            memo[key] = deepcopy(statuses)
    return facts


def _estimate(program, beliefs, route, goal, allowed, quota, budget, memo, use_cache):
    base = {"remaining_calls": 0, "predicted_error": None, "predicted_goal": False,
            "planner_steps": 0, "simulated_effects": 0, "primitive_simulations": 0,
            "mutation_risk": 0, "cache_hit": False, "cache_hits": 0,
            "planning_units": 0, "hypothesis_count": len(beliefs)}
    if program is None:
        return {**base, "predicted_error": "route_parse_error"}
    keys = [_cache_key(program, belief, route, goal, allowed, quota) for _, belief in beliefs]
    missing = set(keys) - set(memo) if use_cache else list(keys)
    if not budget.admits(len(missing) * (1 + _step_bound(program))):
        return {**base, "predicted_error": "planning_budget_exhausted"}
    estimates = []
    for (_, belief), key in zip(beliefs, keys):
        if use_cache and key in memo:
            budget.cache_hits += 1
            base["cache_hits"] += 1
            estimates.append(memo[key])
            continue
        budget.cache_misses += 1
        probe = _copy_probe(belief)
        error = probe.run(program, route, allowed=allowed)
        budget.record(probe)
        item = {"remaining_calls": probe.charged, "predicted_error": error,
                "predicted_goal": error is None and _goal(probe.files, probe.emits, goal),
                "mutation_risk": _risk(probe.trace)}
        estimates.append(item)
        base["primitive_simulations"] += 1
        base["planner_steps"] += probe.steps
        base["simulated_effects"] += len(probe.trace)
        if use_cache:
            memo[key] = item
    base.update(remaining_calls=max((e["remaining_calls"] for e in estimates), default=0),
                mutation_risk=max((e["mutation_risk"] for e in estimates), default=0),
                predicted_error=next((e["predicted_error"] for e in estimates
                                      if e["predicted_error"] is not None), None),
                predicted_goal=bool(estimates) and all(e["predicted_goal"] for e in estimates),
                cache_hit=bool(keys) and base["cache_hits"] == len(keys))
    base["planning_units"] = base["primitive_simulations"] + base["planner_steps"]
    return base


def _observe_events(beliefs, events, machine):
    """Apply only gateway-visible history, never copy private actual files."""
    retained = []
    for index, belief in beliefs:
        compatible = True
        for event in events:
            op, resource = event["op"], event["resource"]
            if ((op, resource) in belief.grants) != event["authorized"]:
                compatible = False
                break
            if event["committed"]:
                if op == "read":
                    returned = machine.receipts.get(tuple(event["key"]))
                    if belief.files.get(resource, "") != returned:
                        compatible = False
                        break
                elif op == "write":
                    belief.files[resource] = event["value"]
                elif op == "delete":
                    belief.files.pop(resource, None)
                elif op == "emit":
                    belief.emits.append({"resource": resource, "value": event["value"]})
        if compatible:
            belief.receipts = deepcopy(machine.receipts)
            belief.signatures = deepcopy(machine.signatures)
            retained.append((index, belief))
    return retained


def execute(case, policy="calls", fault="none", gate_mode="conditional", preflight=True,
            cache=True, world_index=0, quota=16, planning_budget=128,
            observation_budget=2, allowed_ids=None, authorization_evidence=None):
    """Four actual attempts, shared quota, strictly bounded fault-blind planning.

    ``authorization_evidence`` is trusted local-query output, never model text.
    Missing worlds/sites remain unresolved; supplied evidence incurs no audit
    simulation here because its producing queries are charged by their caller.
    """
    _require(policy in POLICIES and fault in FAULTS and gate_mode in {"aggregate", "conditional"},
             "unknown policy, fault or gate mode")
    for name, value in [("quota", quota), ("planning_budget", planning_budget),
                        ("observation_budget", observation_budget)]:
        _require(type(value) is int and value >= 0, name + " must be a nonnegative integer")
    _require(type(preflight) is bool and type(cache) is bool, "preflight/cache must be boolean")
    _require(isinstance(case, dict) and isinstance(case.get("worlds"), list)
             and type(world_index) is int and 0 <= world_index < len(case["worlds"]),
             "invalid world index")
    # The environment is the only scope using world_index.
    machine = _FaultAdapter(case["worlds"][world_index], quota, fault)
    queries = observable_queries(case)
    reader = TrustedObservations(case["worlds"][world_index],
        [q[1] for q in queries if q[0] == "file"], [q[1:] for q in queries if q[0] == "grant"])
    budget = _Budget(planning_budget)
    goal = case.get("goal", {})
    logs, estimates, selections, memo = [], [], [], {}
    gate = {"gate_log": [], "observation_log": [], "observation_count": 0,
            "global_unknown_ids": [], "unresolved_gate_ids": [],
            "compatible_world_indices": list(range(len(case["worlds"]))),
            "observation_mismatch": False}

    def result(error):
        value = _result(machine, goal, logs, error, estimates)
        unresolved = [event for event in machine.trace if event["status"] == "ambiguous_outcome"]
        value.update({key: deepcopy(val) for key, val in gate.items() if key != "allowed_ids"})
        value.update(selection_log=selections, fault_diagnostics=machine.diagnostics(),
            initial_feasible_catalog_count=(sum(i > 0 for i in selections[0]["feasible_route_indices"])
                                            if selections else None),
            initial_feasible_candidate_count=(len(selections[0]["feasible_route_indices"])
                                              if selections else None),
            planning_budget=planning_budget, planning_units=budget.used,
            planning_remaining=planning_budget - budget.used,
            planning_budget_exhausted=budget.exhausted,
            primitive_simulations=budget.primitives, planner_steps=budget.steps,
            simulated_effects=budget.effects, audit_interpreter_calls=budget.audit_calls,
            audit_steps=budget.audit_steps, audit_simulated_effects=budget.audit_effects,
            cache_hits=budget.cache_hits, cache_misses=budget.cache_misses,
            mutation_risk_score=_risk(machine.trace), unresolved_commit_count=len(unresolved),
            unresolved_commit_risk=sum(RISK_WEIGHTS[event["op"]] for event in unresolved),
            modeled_latency=round(10 * machine.charged + sum(row["executed_steps"] for row in logs)
                + 2 * gate["observation_count"] + .1 * budget.used + .01 * budget.cache_hits, 6),
            evidence_source="trusted_queries" if authorization_evidence is not None else "trusted_audit")
        return value

    try:
        original = parse_source(case.get("source"))
    except ValueError:
        return result("parse_error")
    sites = [step["id"] for step in _sites(original) if step["kind"] == "effect"]
    facts = (_evidence_facts(authorization_evidence, case["worlds"], sites)
             if authorization_evidence is not None else
             _audit_facts(original, case["worlds"], sites, budget, cache))
    gate = resolve_gate(case["worlds"], sites, facts, reader, queries, observation_budget, gate_mode)
    allowed = gate["allowed_ids"]
    if allowed_ids is not None:
        allowed &= set(allowed_ids)
    if gate["observation_mismatch"]:
        return result("observation_mismatch")
    beliefs = [(index, _Machine(case["worlds"][index], STEP_LIMIT + 1, reuse=True))
               for index in gate["compatible_world_indices"]]
    programs = [original]
    for candidate in case.get("routes", []):
        try:
            programs.append(_validate(candidate))
        except (ValueError, TypeError, RecursionError):
            programs.append(None)
    remaining = set(range(1, len(programs)))

    def select(attempt, current, observed_error):
        indices = sorted(({0} | remaining) if attempt == 1 else
                         ((remaining - {current}) | ({current} if observed_error in _RETRYABLE else set())))
        available = quota - machine.charged
        rows = []
        for index in indices:
            estimate = _estimate(programs[index], beliefs, index, goal, allowed,
                                 available, budget, memo, cache)
            feasible = (estimate["predicted_error"] is None and estimate["predicted_goal"]
                        and estimate["remaining_calls"] <= available)
            row = {"attempt": attempt, "route_index": index, **estimate,
                   "remaining_quota": available, "feasible": feasible}
            rows.append(row)
            estimates.append(row)
        feasible = [row for row in rows if row["feasible"]]
        chosen = None
        if feasible:
            if policy == "priority" and any(row["route_index"] == current for row in feasible):
                chosen = current
            else:
                chosen = min(feasible, key=lambda row: (
                    (row["mutation_risk"], row["remaining_calls"], row["route_index"])
                    if policy == "risk" else (row["remaining_calls"], row["route_index"])))["route_index"]
        selections.append({"attempt": attempt, "current_route_index": current,
            "observed_error": observed_error, "remaining_quota": available,
            "candidate_count": len(indices), "candidate_route_indices": indices,
            "feasible_route_indices": [row["route_index"] for row in feasible],
            "selected_route_index": chosen,
            "estimated_calls_by_route": {str(row["route_index"]): row["remaining_calls"] for row in rows},
            "estimated_risk_by_route": {str(row["route_index"]): row["mutation_risk"] for row in rows},
            "planning_units": sum(row["planning_units"] for row in rows),
            "planner_steps": sum(row["planner_steps"] for row in rows),
            "simulated_effects": sum(row["simulated_effects"] for row in rows)})
        return chosen

    error, route_index = None, 0
    for attempt in range(1, 5):
        if preflight or attempt > 1:
            route_index = select(attempt, route_index, error)
            if route_index is None:
                error = "planning_budget_exhausted" if any(row["attempt"] == attempt and
                    row["predicted_error"] == "planning_budget_exhausted" for row in estimates) else "no_feasible_route"
                break
        before_calls, before_trace = machine.charged, len(machine.trace)
        error = machine.run(programs[route_index], route_index, attempt, allowed)
        achieved = _goal(machine.files, machine.emits, goal)
        if error is None and not achieved:
            error = "goal_unmet"
        logs.append({"attempt": attempt, "route_index": route_index, "failure_reason": error,
                     "executed_steps": machine.steps, "charged_calls": machine.charged - before_calls,
                     "cumulative_calls": machine.charged, "goal": achieved})
        if error is None or error in {"ambiguous_outcome", "quota_exhausted"}:
            break
        if attempt == 4:
            break
        beliefs = _observe_events(beliefs, machine.trace[before_trace:], machine)
        if not beliefs:
            error = "observation_mismatch"
            break
        if error not in _RETRYABLE:
            remaining.discard(route_index)
    return result(error)

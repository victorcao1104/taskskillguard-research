"""Equal-information recovery with retry priority or remaining-call selection.

Actual effects retain the frozen v7 fault gateway and v6 safety semantics.
Planning runs a fault-blind v6 machine on copied observed state, including the
original model gate. No private truth or future fault schedule enters selection.
"""

from copy import deepcopy

from .recovery_v7 import FAULTS, _FaultMachine
from .runtime_v6 import (
    STEP_LIMIT,
    _Machine,
    _goal,
    _require,
    _result,
    _validate,
    parse_source,
)


POLICIES = frozenset({"priority_equal", "cost_equal"})
_RETRYABLE = frozenset({"transient_before", "known_after"})


def _estimate(program, machine, route, goal, allowed=None):
    """Simulate only observed state; preserve original-route gate enforcement.

The inherited constructor copies files and grants. Emits, receipts and request
signatures are copied separately. The probe has no fault schedule and receives
its own call budget; available real quota is checked by the selection routine.
"""
    probe = _Machine({"files": machine.files, "grants": [list(g) for g in machine.grants]},
                     STEP_LIMIT + 1, reuse=True)
    probe.emits = deepcopy(machine.emits)
    probe.receipts = deepcopy(machine.receipts)
    probe.signatures = deepcopy(machine.signatures)
    error = probe.run(program, route, allowed=allowed)
    predicted_goal = error is None and _goal(probe.files, probe.emits, goal)
    penalty = 0 if predicted_goal else STEP_LIMIT + 1 if error is None else 2 * (STEP_LIMIT + 1)
    return {"remaining_calls": probe.charged, "predicted_error": error,
            "predicted_goal": predicted_goal, "planner_steps": probe.steps,
            "simulated_effects": len(probe.trace), "rank_cost": penalty + probe.charged}


def execute(case, policy, fault="none", allowed_ids=None, world_index=0, quota=16):
    """Attempt the original first, then use at most three selected recoveries.

After a nonterminal failure both policies simulate all unretired alternatives,
plus the current route only for an observed safe retry. A permanent failure
retires the current route. Priority chooses a feasible current route first;
otherwise both choose minimum remaining charged calls, then minimum route index.
Unknown commits and actual quota exhaustion stop before planning. Simulations
that need more than the shared remaining quota are infeasible.
"""
    _require(policy in POLICIES and fault in FAULTS, "unknown policy or fault")
    _require(type(quota) is int and quota >= 0, "quota must be a nonnegative integer")
    _require(isinstance(case, dict) and isinstance(case.get("worlds"), list)
             and type(world_index) is int and 0 <= world_index < len(case["worlds"]),
             "invalid world index")
    machine = _FaultMachine(case["worlds"][world_index], quota, fault)
    goal = case.get("goal", {})
    logs, estimates, selections = [], [], []

    def result(error):
        value = _result(machine, goal, logs, error, estimates)
        value["selection_log"] = selections
        value["initial_feasible_catalog_count"] = (
            sum(index > 0 for index in selections[0]["feasible_route_indices"])
            if selections else None)
        value["initial_feasible_candidate_count"] = (
            len(selections[0]["feasible_route_indices"]) if selections else None)
        value["fault_diagnostics"] = machine.diagnostics()
        return value

    try:
        original = parse_source(case.get("source"))
    except ValueError:
        return result("parse_error")
    allowed = None if allowed_ids is None else set(allowed_ids)
    programs = [original]
    for candidate in case.get("routes", []):
        try:
            programs.append(_validate(candidate))
        except (ValueError, TypeError, RecursionError):
            programs.append(None)
    remaining = set(range(1, len(programs)))

    def select_route(attempt, current, observed_error):
        # The original is not a catalog alternative after switching away from it.
        candidates = remaining - {current}
        if observed_error in _RETRYABLE:
            candidates.add(current)
        indices = sorted(candidates)
        available_quota = machine.quota - machine.charged
        feasible, round_estimates = [], []
        for index in indices:
            estimate = (_estimate(programs[index], machine, index, goal, allowed)
                        if programs[index] is not None else {
                            "remaining_calls": 0, "predicted_error": "route_parse_error",
                            "predicted_goal": False, "planner_steps": 0,
                            "simulated_effects": 0, "rank_cost": 3 * (STEP_LIMIT + 1)})
            is_feasible = (estimate["predicted_error"] is None
                           and estimate["predicted_goal"]
                           and estimate["remaining_calls"] <= available_quota)
            row = {"attempt": attempt, "route_index": index, **estimate,
                   "remaining_quota": available_quota, "feasible": is_feasible}
            estimates.append(row)
            round_estimates.append(row)
            if is_feasible:
                feasible.append((index, estimate["remaining_calls"]))
        chosen = None
        if feasible:
            chosen = (current if policy == "priority_equal" and any(
                index == current for index, _ in feasible) else
                min(feasible, key=lambda entry: (entry[1], entry[0]))[0])
        selections.append({
            "attempt": attempt, "current_route_index": current,
            "observed_error": observed_error, "remaining_quota": available_quota,
            "candidate_count": len(indices), "candidate_route_indices": indices,
            "feasible_route_indices": [index for index, _ in feasible],
            "selected_route_index": chosen,
            "estimated_calls_by_route": {str(row["route_index"]): row["remaining_calls"]
                                         for row in round_estimates},
            "planner_steps": sum(row["planner_steps"] for row in round_estimates),
            "simulated_effects": sum(row["simulated_effects"] for row in round_estimates),
        })
        return chosen

    error, route_index = None, 0
    for attempt in range(1, 5):
        if attempt > 1:
            route_index = select_route(attempt, route_index, error)
            if route_index is None:
                error = "no_feasible_route"
                break
        before = machine.charged
        error = machine.run(programs[route_index], route_index, attempt, allowed)
        achieved = _goal(machine.files, machine.emits, goal)
        if error is None and not achieved:
            error = "goal_unmet"
        logs.append({"attempt": attempt, "route_index": route_index,
                     "failure_reason": error, "executed_steps": machine.steps,
                     "charged_calls": machine.charged - before,
                     "cumulative_calls": machine.charged, "goal": achieved})
        if error is None or error in {"ambiguous_outcome", "quota_exhausted"}:
            break
        if error not in _RETRYABLE:
            remaining.discard(route_index)
    return result(error)

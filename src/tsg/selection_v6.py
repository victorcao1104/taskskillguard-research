"""Supplemental equal-planning route selectors over the frozen Phase 6 VM.

Both selectors evaluate every remaining public route before choosing one.
Only selection order differs. This module performs no external I/O and never
reads private reference programs, truth labels, case identifiers or fixtures.
"""

from .runtime_v6 import (
    FAULTS,
    STEP_LIMIT,
    _Machine,
    _estimate,
    _goal,
    _require,
    _result,
    _validate,
    parse_source,
)


MODES = frozenset({"first_feasible", "search_equal"})


def execute_selection(case, mode, fault="none", allowed_ids=None, world_index=0, quota=16):
    """Execute with catalog-first or lowest-call selection among feasible routes.

    Each route estimate uses an isolated copy of shared observed state and
    receipts, trusted grants and goal, with no private fault information.
    Feasibility additionally requires estimated calls <= remaining live quota.
    Simulation work is reported, but spends no actual-effect quota.
    """
    _require(mode in MODES and fault in FAULTS, "unknown mode or fault")
    _require(type(quota) is int and quota >= 0, "quota must be a nonnegative integer")
    _require(isinstance(case, dict) and isinstance(case.get("worlds"), list)
             and type(world_index) is int and 0 <= world_index < len(case["worlds"]),
             "invalid world index")
    machine = _Machine(case["worlds"][world_index], quota, reuse=True, fault=fault)
    goal = case.get("goal", {})
    logs, estimates, selections = [], [], []

    def result(error):
        value = _result(machine, goal, logs, error, estimates)
        value["selection_log"] = selections
        value["initial_feasible_catalog_count"] = (
            len(selections[0]["feasible_route_indices"]) if selections else None)
        return value

    try:
        original = parse_source(case.get("source"))
    except ValueError:
        return result("parse_error")
    allowed = None if allowed_ids is None else set(allowed_ids)
    routes = []
    for candidate in case.get("routes", []):
        try:
            routes.append(_validate(candidate))
        except (ValueError, TypeError, RecursionError):
            routes.append(None)
    remaining = list(range(1, len(routes) + 1))
    error = None
    for attempt in range(1, 5):
        if attempt <= 2:
            route_index, route_program = 0, original
        else:
            available_quota = machine.quota - machine.charged
            feasible = []
            for index in remaining:
                estimate = (
                    _estimate(routes[index - 1], machine, index, goal)
                    if routes[index - 1] is not None else {
                        "remaining_calls": 0, "predicted_error": "route_parse_error",
                        "predicted_goal": False, "planner_steps": 0,
                        "simulated_effects": 0, "rank_cost": 3 * (STEP_LIMIT + 1)})
                is_feasible = (estimate["predicted_error"] is None
                               and estimate["predicted_goal"]
                               and estimate["remaining_calls"] <= available_quota)
                estimates.append({"attempt": attempt, "route_index": index,
                                  **estimate, "remaining_quota": available_quota,
                                  "feasible": is_feasible})
                if is_feasible:
                    feasible.append((index, estimate["remaining_calls"]))
            selection = {"attempt": attempt, "remaining_quota": available_quota,
                         "candidate_count": len(remaining),
                         "feasible_route_indices": [index for index, _ in feasible],
                         "selected_route_index": None}
            selections.append(selection)
            if not feasible:
                error = "no_feasible_route"
                break
            route_index = (feasible[0][0] if mode == "first_feasible"
                           else min(feasible, key=lambda entry: (entry[1], entry[0]))[0])
            selection["selected_route_index"] = route_index
            remaining.remove(route_index)
            route_program = routes[route_index - 1]
        before = machine.charged
        error = machine.run(route_program, route_index, attempt, allowed)
        achieved = _goal(machine.files, machine.emits, goal)
        if error is None and not achieved:
            error = "goal_unmet"
        logs.append({"attempt": attempt, "route_index": route_index,
                     "failure_reason": error, "executed_steps": machine.steps,
                     "charged_calls": machine.charged - before,
                     "cumulative_calls": machine.charged, "goal": achieved})
        if error is None or error in {"ambiguous_outcome", "quota_exhausted"}:
            break
    return result(error)

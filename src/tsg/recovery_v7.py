"""Observed-error recovery policies over the immutable Phase 6 VM.

The gateway schedules faults; the policy sees only actual execution errors.
All parsing, execution, receipts, grants and dry simulation remain Phase 6
semantics. No private reference program, labels or external I/O are consumed.
"""

from .runtime_v6 import (
    STEP_LIMIT,
    _Machine,
    _estimate,
    _eval,
    _goal,
    _require,
    _result,
    _string,
    _validate,
    parse_source,
)


FAULTS = (
    "none", "transient_before", "known_after", "ambiguous_after",
    "second_transient_before", "second_known_after", "second_ambiguous_after",
    "double_transient_before",
)
SELECTORS = frozenset({"first_feasible", "search_equal"})
POLICIES = frozenset({"legacy", "safe_retry"})
_RETRYABLE = frozenset({"transient_before", "known_after"})
_SCHEDULES = {
    "none": {},
    "transient_before": {1: "transient_before"},
    "known_after": {1: "known_after"},
    "ambiguous_after": {1: "ambiguous_after"},
    "second_transient_before": {2: "transient_before"},
    "second_known_after": {2: "known_after"},
    "second_ambiguous_after": {2: "ambiguous_after"},
    "double_transient_before": {1: "transient_before", 2: "transient_before"},
}


class _FaultMachine(_Machine):
    """Change injection timing only, delegating effects to the frozen gateway.

The preview repeats the VM's pure expression evaluation to identify a dispatch
which will reach the mutation boundary. The inherited effect remains the only
place that charges calls, changes state, enforces grants or manages receipts.
"""

    def __init__(self, world, quota, fault):
        super().__init__(world, quota, reuse=True)
        self._fault_name = fault
        self._schedule = _SCHEDULES[fault]
        self._eligible_dispatches = 0
        self._injections = []

    def effect(self, step, variables, occurrence, allowed):
        injected = "none"
        op = step["op"]
        if op in {"write", "emit", "delete"}:
            resource = _string(_eval(step["resource"], variables))
            value = _string(_eval(step.get("value", ""), variables))
            signature = (op, resource, value)
            key = (("explicit", _string(_eval(step["key"], variables))) if "key" in step
                   else ("site", step["id"], occurrence))
            denied = self.enforce and (
                (op, resource) not in self.grants
                or (self.route == 0 and allowed is not None and step["id"] not in allowed))
            conflict = key in self.signatures and self.signatures[key] != signature
            reused = self.reuse and key in self.receipts
            if not denied and not conflict and not reused and self.charged < self.quota:
                self._eligible_dispatches += 1
                injected = self._schedule.get(self._eligible_dispatches, "none")
                if injected != "none":
                    self._injections.append({
                        "dispatch": self._eligible_dispatches, "fault": injected,
                        "attempt": self.attempt, "route_index": self.route, "id": step["id"]})
        # The inherited single-dispatch fault implementation owns all before/
        # after-commit behavior. Reset only its injection latch, never receipts.
        self.fault, self.fault_used = injected, False
        try:
            return super().effect(step, variables, occurrence, allowed)
        finally:
            self.fault = "none"

    def diagnostics(self):
        return {
            "fault": self._fault_name,
            "eligible_mutation_dispatches": self._eligible_dispatches,
            "scheduled_fault_count": len(self._schedule),
            "injected_fault_count": len(self._injections),
            "fault_triggered": bool(self._injections),
            "schedule_completed": len(self._injections) == len(self._schedule),
            "injections": list(self._injections),
        }


def execute(case, selector, policy, fault="none", allowed_ids=None, world_index=0, quota=16):
    """Execute at most four actual attempts with one shared effect quota.

    ``legacy`` exactly retains selection_v6's two original attempts and retirement
    of a selected alternative before execution. ``safe_retry`` starts the original
    once, immediately repeats a route after an observed safe transient/known commit,
    and retires it on every other nonterminal failure. Both selectors fully simulate
    all remaining alternatives on every selection round with the fault-blind v6
    estimator. Unknown commit and quota-exhausted execution errors stop both policies.
    """
    _require(selector in SELECTORS and policy in POLICIES and fault in FAULTS,
             "unknown selector, policy or fault")
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
            len(selections[0]["feasible_route_indices"]) if selections else None)
        value["fault_diagnostics"] = machine.diagnostics()
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

    def select_route(attempt):
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
            return None
        chosen = (feasible[0][0] if selector == "first_feasible"
                  else min(feasible, key=lambda entry: (entry[1], entry[0]))[0])
        selection["selected_route_index"] = chosen
        return chosen

    error, retry_route = None, 0
    for attempt in range(1, 5):
        if policy == "legacy" and attempt <= 2:
            route_index = 0
        elif policy == "safe_retry" and retry_route is not None:
            route_index = retry_route
        else:
            route_index = select_route(attempt)
            if route_index is None:
                error = "no_feasible_route"
                break
            if policy == "legacy":
                remaining.remove(route_index)
        route_program = original if route_index == 0 else routes[route_index - 1]
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
        if policy == "safe_retry":
            retry_route = route_index if error in _RETRYABLE else None
            if retry_route is None and route_index in remaining:
                remaining.remove(route_index)
    return result(error)

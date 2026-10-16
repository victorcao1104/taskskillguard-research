"""Bounded synthetic terminal-status recovery; no host effects or hidden planner.

The caller supplies an already checked public route. Python object privacy is not
a security sandbox: the controller/service split models an authenticated remote
capability. See docs/phase11_commit.md for the conditional trust assumptions.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import hmac
import json

from .runtime_v6 import (_Machine, _Stop, _eval, _goal, _require, _string,
                         _validate, _world, parse_source)

POLICIES = ("strict_stop", "terminal_status", "same_id_dedup", "unsafe_absence_retry")
_BASE_FAULTS = ("ambiguous_after", "terminal_noncommit", "pending", "unavailable",
                "absent", "stale", "wrong_signature", "wrong_operation", "wrong_epoch",
                "forged", "retention_expired", "contradictory", "pending_absent")
FAULTS = ("none",) + _BASE_FAULTS + tuple(
    prefix + fault for prefix in ("second_", "emit_") for fault in _BASE_FAULTS)


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


class _StatusService:
    """Trusted atomic in-memory effect/completion service and fault environment.

    Only dispatch/query/verify are provided to the controller. Everything else,
    including fault schedule, durable records and actual files, is environment
    state used only by the experiment driver after controller execution.
    """
    def __init__(self, world, quota, status_budget, fault, epoch, dedup):
        self.files, self.grants = _world(world)
        self.emits, self.events = [], []
        self.quota, self.status_budget = quota, status_budget
        self.effect_calls = self.status_calls = self.reuses = 0
        self.commits, self.signatures = Counter(), {}
        self.records, self.pending, self.responses = {}, {}, {}
        self.epoch, self.dedup, self.fault = epoch, dedup, fault
        self.context = _digest(sorted(self.grants))
        self._key = hashlib.sha256(b"phase11-synthetic-service-key" + epoch.encode()).digest()
        self.mutations = self.emit_dispatches = 0
        self.triggered = False

    @property
    def charged(self):
        return self.effect_calls + self.status_calls

    def _sign(self, body):
        return {"body": deepcopy(body), "mac": hmac.new(self._key, _bytes(body), hashlib.sha256).hexdigest()}

    def verify(self, packet, binding, outcomes):
        """Verification capability never exposes signing or record retrieval."""
        if not isinstance(packet, dict) or set(packet) != {"body", "mac"}:
            return False
        body = packet["body"]
        if not isinstance(body, dict) or not isinstance(packet["mac"], str):
            return False
        mac = hmac.new(self._key, _bytes(body), hashlib.sha256).hexdigest()
        return (hmac.compare_digest(packet["mac"], mac)
                and body.get("binding") == binding and body.get("outcome") in outcomes
                and (body["outcome"] != "committed" or isinstance(body.get("receipt"), str)))

    def _packet(self, binding, outcome, receipt=None):
        body = {"binding": deepcopy(binding), "outcome": outcome}
        if receipt is not None:
            body["receipt"] = receipt
        return self._sign(body)

    def _commit(self, binding, logical_key):
        op, resource, value = binding["signature"]
        returned = ""
        if op == "read":
            returned = self.files.get(resource, "")
        elif op == "write":
            self.files[resource] = value
        elif op == "delete":
            self.files.pop(resource, None)
        elif op == "emit":
            self.emits.append({"resource": resource, "value": value})
        if op != "read":
            self.commits[logical_key] += 1
        # This indivisible transition is the abstract atomic durability premise.
        packet = self._packet(binding, "committed", returned)
        self.records[binding["operation_id"]] = packet
        self.events.append({"binding": deepcopy(binding), "committed": True})
        return packet

    def dispatch(self, binding, logical_key):
        if self.charged >= self.quota:
            return {"error": "quota_exhausted"}
        self.effect_calls += 1
        op, resource, _ = binding["signature"]
        if (op, resource) not in self.grants:
            return {"error": "grant_denied"}
        if logical_key in self.signatures and self.signatures[logical_key] != binding["signature"]:
            return {"error": "receipt_conflict"}
        self.signatures[logical_key] = deepcopy(binding["signature"])
        operation = binding["operation_id"]
        existing = self.records.get(operation)
        if existing is not None and existing["body"]["outcome"] == "terminal_noncommit":
            return {"error": "fenced_operation"}
        if self.dedup and existing is not None:
            self.reuses += 1
            return {"receipt": deepcopy(existing)}
        if self.dedup and operation in self.pending:
            return {"error": "pending"}
        mode = "none"
        if op != "read":
            self.mutations += 1
            self.emit_dispatches += int(op == "emit")
            base = self.fault
            target = self.mutations == 1
            if base.startswith("second_"):
                base, target = base[7:], self.mutations == 2
            elif base.startswith("emit_"):
                base, target = base[5:], op == "emit" and self.emit_dispatches == 1
            if not self.triggered and target and base != "none":
                self.triggered, mode = True, base
        if mode != "none":
            self.responses[operation] = mode
            if mode == "terminal_noncommit":
                self.records[operation] = self._packet(binding, "terminal_noncommit")
            elif mode in {"pending", "pending_absent"}:
                self.pending[operation] = (deepcopy(binding), logical_key)
            else:
                self._commit(binding, logical_key)
            return {"error": "ambiguous_outcome"}
        receipt = self._commit(binding, logical_key)
        # Negative-control schedule: delayed original completes after fresh retry.
        # It is not a status oracle or a decision available to the controller.
        for old_id, (old_binding, old_key) in list(self.pending.items()):
            if old_key == logical_key and old_id != operation:
                self._commit(old_binding, old_key)
                del self.pending[old_id]
        return {"receipt": receipt}

    def query(self, binding):
        if self.status_calls >= self.status_budget:
            return {"error": "status_budget_exhausted"}
        if self.charged >= self.quota:
            return {"error": "quota_exhausted"}
        self.status_calls += 1
        operation = binding["operation_id"]
        mode = self.responses.get(operation, "none")
        if mode in {"unavailable", "retention_expired"}:
            return {"status": self._packet(binding, "unavailable")}
        if mode in {"absent", "pending_absent"}:
            return {"status": self._packet(binding, "absent")}
        if mode == "pending":
            return {"status": self._packet(binding, "pending")}
        packet = deepcopy(self.records.get(operation, self._packet(binding, "absent")))
        if mode in {"stale", "wrong_epoch", "wrong_signature", "wrong_operation"}:
            changed = packet["body"]
            field = {"stale": "epoch", "wrong_epoch": "epoch", "wrong_signature": "signature",
                     "wrong_operation": "operation_id"}[mode]
            changed["binding"][field] = ["write", "other", "payload"] if field == "signature" else "different"
            packet = self._sign(changed)
        elif mode == "forged":
            packet["mac"] = "0" * 64
        elif mode == "contradictory":
            packet = self._packet(binding, "contradictory")
        return {"status": packet}


class _Controller(_Machine):
    """Reuse only the frozen finite AST walker, never its world/effect machinery."""
    def __init__(self, dispatch, query, verify, epoch, context, route):
        self._dispatch, self._query, self._verify = dispatch, query, verify
        self.epoch, self.context, self.chosen_route = epoch, context, route
        self.receipts, self.signatures, self.generations = {}, {}, Counter()
        self.trace, self.status_log = [], []
        self.suppress = set()
        self.steps = self.reuses = 0
        self.outstanding = None

    def effect(self, step, variables, occurrence, allowed):
        signature = [step["op"], _string(_eval(step["resource"], variables)),
                     _string(_eval(step.get("value", ""), variables))]
        key = (("explicit", _string(_eval(step["key"], variables))) if "key" in step
               else ("site", step["id"], occurrence))
        binding = {"operation_id": _digest([self.epoch, self.chosen_route, key, self.generations[key]]),
                   "signature": signature, "epoch": self.epoch, "policy_context": self.context}
        event = {"id": step["id"], "key": list(key), "signature": signature,
                 "attempt": self.attempt, "route_index": self.route}
        if key in self.receipts and self.signatures.get(key) == signature:
            event["status"] = "receipt_reused"
            self.trace.append(event)
            self.reuses += 1
            return self.receipts[key]
        self.signatures.setdefault(key, signature)
        response = self._dispatch(binding, key)
        if "receipt" in response and self._verify(response["receipt"], binding, {"committed"}):
            self.receipts[key] = response["receipt"]["body"]["receipt"]
            event["status"] = "receipt"
            self.trace.append(event)
            return self.receipts[key]
        error = response.get("error", "invalid_receipt")
        event["status"] = error
        self.trace.append(event)
        self.outstanding = (key, binding) if error == "ambiguous_outcome" else None
        raise _Stop(error)

    def reconcile(self, policy):
        key, binding = self.outstanding
        if policy == "strict_stop":
            return "ambiguous_outcome"
        if policy == "same_id_dedup":
            return None  # backend capability, not a status inference
        response = self._query(binding)
        self.status_log.append(deepcopy(response))
        if "error" in response:
            return response["error"]
        packet = response.get("status")
        if not self._verify(packet, binding, {"committed", "terminal_noncommit", "absent"}):
            return "status_unusable"
        outcome = packet["body"]["outcome"]
        if outcome == "committed":
            self.receipts[key] = packet["body"]["receipt"]
            return None
        if outcome == "terminal_noncommit" or (outcome == "absent" and policy == "unsafe_absence_retry"):
            self.generations[key] += 1
            return None
        return "status_unusable"


def execute_certified(case, route_index, world_index=0, fault="none", policy="strict_stop",
                      quota=32, status_budget=1):
    """Execute exactly the caller-certified route, with at most four VM attempts.

    Route 0 is parsed source; route i>0 is case['routes'][i-1]. This API does
    not verify a certificate: its caller must do so. Returned environment outcomes
    are measurement data only; they never enter the controller's continuation rule.
    """
    _require(policy in POLICIES and fault in FAULTS, "unknown policy or fault")
    _require(type(quota) is int and quota >= 0 and type(status_budget) is int
             and status_budget >= 0, "invalid quota/status budget")
    _require(isinstance(case, dict) and isinstance(case.get("worlds"), list)
             and type(world_index) is int and 0 <= world_index < len(case["worlds"]), "invalid world")
    _require(type(route_index) is int and 0 <= route_index <= len(case.get("routes", [])), "invalid route")
    epoch = _digest({"public": {k: v for k, v in case.items() if k != "worlds"}, "quota": quota,
                     "runtime": "commit_v11"})
    service = _StatusService(case["worlds"][world_index], quota, status_budget, fault, epoch,
                             policy == "same_id_dedup")
    controller = _Controller(service.dispatch, service.query, service.verify, epoch, service.context, route_index)
    logs, error = [], None
    try:
        program = parse_source(case.get("source")) if route_index == 0 else _validate(case["routes"][route_index - 1])
    except (ValueError, TypeError, RecursionError):
        program, error = None, "parse_error"
    if program is not None:
        for attempt in range(1, 5):
            before = service.charged
            error = controller.run(program, route_index, attempt)
            logs.append({"attempt": attempt, "route_index": route_index, "failure_reason": error,
                         "executed_steps": controller.steps, "charged_calls": service.charged - before,
                         "cumulative_calls": service.charged})
            if error != "ambiguous_outcome":
                break
            error = controller.reconcile(policy)
            if error is not None:
                break
            if attempt == 4:
                error = "attempt_budget_exhausted"
    achieved = _goal(service.files, service.emits, case.get("goal", {}))
    if error is None and not achieved:
        error = "goal_unmet"
    duplicates = sum(max(0, count - 1) for count in service.commits.values())
    return {"files": deepcopy(service.files), "emits": deepcopy(service.emits), "goal": achieved,
            "authorized_goal": error is None and achieved, "failure_reason": error,
            "attempts": len(logs), "attempt_log": logs, "charged_calls": service.charged,
            "effect_calls": service.effect_calls, "status_calls": service.status_calls,
            "remaining_quota": quota - service.charged, "remaining_status_budget": status_budget - service.status_calls,
            "duplicate_effects": duplicates, "unauthorized_effects": 0,
            "receipt_reuses": controller.reuses + service.reuses,
            "controller_trace": controller.trace, "trace": controller.trace,
            "status_log": controller.status_log, "environment_trace": service.events,
            "fault_diagnostics": {"fault": fault, "fault_triggered": service.triggered,
                                  "pending_operations": len(service.pending),
                                  "eligible_mutation_dispatches": service.mutations},
            "trust_model": ("atomic durable same-ID gateway deduplication" if policy == "same_id_dedup"
                            else "synthetic non-idempotent backend; unsafe fresh-ID absence retry" if policy == "unsafe_absence_retry"
                            else "authenticated atomic durable terminal status with fencing"),
            "route_index": route_index, "planner_calls": 0}

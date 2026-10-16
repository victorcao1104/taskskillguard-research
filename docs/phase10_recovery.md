# Phase 10 goal observations and legal recovery

Production entry point:

```python
execute(case, policy="calls", fault="none", gate_mode="conditional",
        preflight=True, cache=True, world_index=0, quota=16,
        planning_budget=128, observation_budget=2, allowed_ids=None,
        authorization_evidence=None, observation_mode="goal",
        risk_weights=None)
```

All Phase 9 parameters and result fields remain. The implementation uses only
the frozen Phase 6 in-memory language, grant gateway and receipt semantics, with
the frozen Phase 7 fault machinery. It neither reads the private reference
`program` nor performs host effects or external I/O. Phase 9 files are unchanged.

## Observation contract

Only environment initialization uses `world_index`, to create the actual gateway
and the immutable initial reader. Selection receives public finite hypotheses,
trusted query answers and gateway-visible history. The future fault schedule,
actual gateway file map, private reference program and truth labels do not enter
goal query selection or route probes.

`observation_mode="authorization"` retains Phase 9 initial observation behavior.
It is a control using the same Phase 10 route planner, candidate catalog, policy,
cache, grants, quota, risk weights and receipt engine as the goal arm. Its goal
observation and goal-probe counters are zero. With default weights and old fault
identifiers it retains Phase 9 execution behavior and all old result values.

`observation_mode="goal"` first performs the identical authorization observation
procedure. Within the same remaining `observation_budget`, it may then resolve
goal-only uncertainty even when all original authorization sites are already
conditionally safe. Aggregate gating remains aggregate: it never acquires
initial observations in either mode.

The goal mechanism works as follows:

1. For each still-compatible public world and each validated original/catalog
   program, fault-free, receipt-aware dry simulation determines whether the route
   finishes, meets the public goal and fits the real call quota. The original
   program is constrained by the current trusted initial gate and any explicit
   `allowed_ids`; catalog programs remain subject to exact grants.
2. Every such probe shares the same planning budget and execution-local cache
   with gate audits and later route selection. A probe reserves its single
   public-hypothesis structural bound before executing. If any profile cannot be
   established within that budget, no query is selected from the incomplete
   collection. Already completed probes and their costs remain logged.
3. If any route is feasible in every compatible world, no goal observation is
   needed. Otherwise compare worlds' per-route feasibility vectors. A minimum
   cardinality set of unused allowed initial queries that separates all vector
   disagreements within the remaining observation budget is preferred, with
   lexical ties. Issue only its first query, then recompute after the answer.
   If no complete separating set fits, issue the query separating the most
   disagreeing world pairs, with lexical ties. Identical vectors or differences
   that allowed queries cannot separate remain unresolved.
4. Each query is charged once, including an unavailable answer. An unavailable
   answer does not narrow hypotheses. File answers include presence and value;
   grant answers report membership. An answer outside every hypothesis stops
   with `observation_mismatch`. After a compatible answer, recompute conditional
   authorization solely from the original trusted facts on retained hypotheses.

Queries use the immutable Phase 9 `TrustedObservations` reader. Defaults and
explicit `observable_files`/`observable_grants` limits are unchanged. A goal
probe cannot supply a missing authorization fact. `authorization_evidence`
continues to accept only caller-verified trusted completed base-query output;
missing worlds and sites stay unresolved and supplied-evidence mode performs
zero hidden authorization audits. A goal observation can narrow the world set,
but cannot bypass `allowed_ids`, grant checks or receipt conflicts. The final
initial gate remains fixed throughout actual execution.

This is a bounded heuristic for decision-relevant queries, not a claim of
optimal information acquisition. Authorization observations have first use of
the shared observation budget. Goal probes add planning work and may exhaust a
small budget that an authorization-only run would spend on route selection.
No guaranteed improvement in completion is asserted.

## Legal recovery, policies and weights

Preflight and recovery retain the Phase 9 candidate enumeration, robust
feasibility, four-attempt limit and safe retry rules. All three policies examine
the same candidate set before applying their ranking. `priority` first prefers
the feasible current original/retry, then calls and route index; `calls` ranks
remaining charged calls then route index; `risk` ranks mutation exposure, calls,
then route index. Goal selection does not inspect the policy's future fault
schedule. The preflight-off diagnostic still runs the original once after
initial gate/observation processing, followed by the same legal recovery planner.

`risk_weights=None` means `{"read": 0, "write": 1, "delete": 2, "emit": 8}`.
An explicit mapping must contain exactly those four operations with finite,
nonnegative numeric values; booleans and missing or additional operations are
rejected. Weights are copied for the run and applied consistently to simulated
route exposure, actual `mutation_risk_score` and `unresolved_commit_risk`.
The three prospectively declared experiment vectors are:

| Vector | read | write | delete | emit |
| --- | ---: | ---: | ---: | ---: |
| default | 0 | 1 | 2 | 8 |
| uniform mutation | 0 | 1 | 1 | 1 |
| write-heavy | 0 | 4 | 4 | 1 |

This score is a declared exposure surrogate, not a probability or monetary loss.
Only fresh charged, authorized effects that pass gate/signature checks add
exposure; receipt reuse adds zero. A caller assigning a nonzero read weight also
charges authorized fresh reads in this surrogate, although the three registered
vectors all set read to zero. Risk estimates remain worst-case across compatible
worlds. Cache entries are local to one execution and its fixed weight mapping.

Known committed receipts, stale read returns, request signatures and quota are
preserved across retries. Beliefs update only from observed gateway events;
actual private state is never copied into them. An ambiguous commit stops before
belief updates, another selection round or retry. Reaching the goal at that
unknown commit does not count as `authorized_goal`.

## Frozen fault semantics

All Phase 7 fixed mutation-position schedules remain available and unchanged:
`none`, `transient_before`, `known_after`, `ambiguous_after`,
`second_transient_before`, `second_known_after`, `second_ambiguous_after`, and
`double_transient_before`. Phase 9 additions also remain unchanged:
`mixed_known_then_ambiguous` injects known-after at eligible mutation dispatch 1
and ambiguous-after at dispatch 2; `late_ambiguous` injects ambiguous-after at
eligible mutation dispatch 3.

Phase 10 adds exactly these two operation-dependent schedules:

| Identifier | Trigger |
| --- | --- |
| `first_emit_ambiguous` | Commit the first eligible fresh emit, then return ambiguous outcome without a receipt. |
| `second_write_ambiguous` | Commit the second eligible fresh write, then return ambiguous outcome without a receipt. |

The target ordinal is counted over the whole execution, across attempts and
routes. Eligibility requires a mutation of the named operation that passes
actual grants, original gate and request-signature checks, has no reusable
receipt, and has quota for a charged dispatch. Reads, other mutation operations,
reused receipts, denied/conflicting requests and exhausted quota do not advance
that operation ordinal. The operation-dependent schedules inject no preceding
fault. If the target is never reached, no fault is injected. The frozen gateway
alone charges calls, commits the effect and omits the ambiguous receipt.

Fault diagnostics retain all old fields. Operation-dependent faults additionally
report `target_operation`, `target_operation_ordinal` and
`eligible_target_operation_dispatches`. Their `scheduled_fault_count` is one;
`schedule_completed` is true exactly when the target fault was injected. The
`injections` list retains the global eligible mutation dispatch number, site,
route and attempt. Operation matching happens only at actual dispatch; it cannot
affect earlier observation or route decisions.

## Work accounting and provenance

All old counters remain, including
`planning_units = primitive_simulations + planner_steps`. Gate audits, goal
probes and route selection share this same strict budget. Structural reservations
cover one primitive plus the entered-step bound, capped at the frozen VM limit;
unused reservation is released and actual work is recorded. Cache hits execute
no interpreter. Static parsing, key construction, query separation and controller
bookkeeping are outside these abstract VM work units; they are not total CPU,
wall time or monetary cost.

Additional results are:

- `observation_mode` and the copied `risk_weights` mapping;
- `goal_observation_count` and `goal_observation_log`, a subset of the existing
  total observation count/log;
- `goal_probe_log`, with `world_hypothesis_index`, `route_index`, feasibility and
  the usual estimated error, goal, calls, exposure, steps, cache and planning
  counters; its provenance is `public_hypothesis_simulation`;
- `goal_observation_planning_units`, actual primitive-plus-step work attributable
  to the goal probes. This is a subset of total planning work, not an extra sum.

Goal observation rows carry `purpose="goal_feasibility"`,
`provenance="trusted_initial_reader"`, compatible hypotheses before the query,
and the feasible-route IDs from each public hypothesis. Goal observations also
append a `goal_observation` stage to `gate_log`. Global typed authorization is
preserved unchanged, including authorized/inactive mixtures remaining globally
unknown. Search estimates contain subsequent route selection work only; audits
and goal probes are included in total planning counters separately. The existing
modeled latency formula remains unchanged and counts total observations and
planning work, including the new mechanism.

## Author boundary and verification

The runtime author read the Phase 10 prospective design and implementation plan,
frozen v6/v7/v9 production modules, old recovery tests and Phase 9 recovery
documentation. No Phase 10 generator, heldout data, reference outputs or model
results were read. Tests use independently hand-derived toy workflows only.

The first 22 tests failed at the explicit missing-runtime assertion before the
new production modules existed (`runtime-red.xml`). They passed after
implementation (`runtime-green-01.xml`). Additional tests cover unavailable and
mismatched trusted readers, old fixed fault/receipt compatibility, aggregate
gating, explicit restrictions, alternative weights and absent fault targets.

Focused verification command:

```text
.venv/Scripts/python.exe -m pytest tests/test_recovery_v10.py
tests/test_recovery_v9.py tests/test_recovery_v8.py tests/test_phase7_recovery.py
tests/test_runtime_v6.py tests/test_selection_v6.py --basetemp work/p10r -q
--junitxml=results/phase10/validation/runtime-focused-01.xml
```

Result: 253 passed, including 43 Phase 10 toy tests. Full-project verification
belongs to the parent after production freeze, preserving this implementer's
heldout separation.

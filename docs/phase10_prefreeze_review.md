# Phase 10 independent prefreeze review

Review date: 2026-10-16. Reviewer is separate from the runtime/query authors and
the independent reference author. Scope is the prospective design and plan,
new production modules, acquisition/orchestration, and hand-derived toy tests.
No Phase 10 generator, reference test, heldout data, reference output, or model
results were read. No network, API, Git, or Docker operation was performed.

## Initial findings

1. **Important, repaired: cap exhaustion aborts acquisition without preserving a terminal
   stream record.** `acquire_stream` calls the frozen `ClientV3`, whose budget
   reservation raises `RuntimeError('BUDGET_LIMIT')` before its request exception
   handler. The exception escapes the stream loop; an already-written dispatch
   intent remains, but no decision or stream outcome is saved. A restart would
   describe this known nondispatch as `interrupted_unknown`. This prevents a
   complete denominator of exhausted streams and misstates billing uncertainty.
   Independent reproduction: `test_cap_rejection_is_a_persisted_terminal_outcome_without_provider_io`
   in `tests/test_review_v10.py`, using a zero-cap actual locked budget/client and
   a forbidden provider transport. Before repair it fails with `BUDGET_LIMIT`.
   Required repair: persist a distinct budget-exhausted outcome, preserve any
   earlier acquired evidence, and continue other registered streams subject to
   the same cap. No retry or budget relaxation is appropriate.
   The coordinator repaired this with a distinct persisted `budget_exhausted`
   raw outcome. The independent cap/restart test now passes.

2. **Resolved wire-schema concern.** The
   initial full/batch schema contains `uniqueItems` and cardinality constraints.
   A local JSON Schema validator establishes local validity, not support in the
   provider's strict structured-output subset. The coordinator was asked to
   verify the wire subset before acquisition and, if needed, retain stronger
   cardinality/uniqueness checks locally. No API compatibility claim is made by
   this offline review.
   The coordinator checked the current official supported subset, removed
   `uniqueItems` from the wire schema only, and retained local strict uniqueness
   validation. `minItems` and `maxItems` remain supported according to that check.

3. **Minor, repaired:** the batch system message refers to a requested
   limit, but the initial payload does not include that limit explicitly. The
   schema contains it. Supplying an explicit prompt limit would make the
   intended selection task unambiguous even if wire constraints are relaxed.
   The coordinator added `selection_limit` to each acquisition prompt.

4. **Important, repaired: a stopping scenario can inherit a later invalid decision it
   would never request.** When the acquired stream consists of one valid
   completed original and then an invalid repeated ID, authorization readiness
   occurs at the last valid query. `stopped_early` is false because no valid
   suffix query exists to omit. The initial prefix attribution logic therefore
   includes the invalid next decision, returning two model requests and invalid
   scenario protocol status. Independent reproduction:
   `test_ready_at_end_of_valid_prefix_does_not_attribute_later_invalid_decision`;
   expected one valid request for authorization stop, two requests and failure
   for fixed. Required repair: use final evidence readiness, independently of
   realized interpreter suffix savings, to decide whether later failed requests
   belong to the stopping scenario.
   The coordinator now computes final stop-predicate readiness independently
   from `stopped_early`. The independent regression passes: authorization stop
   has one valid request; fixed retains the later invalid decision.

5. **Important, repaired: unknown-billing requests receive zero attributed upper cost.**
   Initial query-scenario accounting sums only available token usage. A failed
   or interrupted request without usage can retain a charged ledger reservation
   yet contribute zero to `attributed_model_cost_upper_usd`. Preserve its
   conservative reservation cost in scenario attribution or explicitly report
   this as observed-usage-only cost with unknown billing separately. The shared
   campaign budget itself remains conservatively charged.
   Acquisition now records `cost_upper_usd` and its basis per decision. Valid
   usage is priced conservatively; missing usage retains the request reservation
   bound, and a known pre-I/O cap rejection is zero. Prefix scenarios sum those
   recorded bounds. The campaign invoice is not reduced by scenario attribution.

## Checked boundaries

- Goal-query selection sees the public hypothesis catalog, already obtained
  trusted answers and charged feasibility estimates. Actual-world selection is
  confined to environment initialization. Future faults are injected only by
  the actual gateway; probes use the fault-free VM.
- Authorization-only mode retains the same planner, route alternatives,
  receipts and quota. Goal probes share the planning counter/cache and do not
  complete missing original authorization facts. Exhausted probes do not become
  a basis for goal queries.
- Completed paid original traces alone supply runtime authorization evidence.
  Failed originals can retain the frozen diagnostic labels without becoming
  handoff evidence. Alternate and suppressed traces cannot supply that evidence.
- Stop checks and result retrieval use cached facts and invoke no interpreter.
  Offline early-stop evaluation checks before its next purchase and omits the
  unused suffix. Authorization stopping requires every world's completed base.
- Operation-dependent fault ordinals count fresh, eligible mutations of the
  specified operation. Receipt reuse, denials, conflicts and exhausted quota do
  not advance the target counter. Ambiguous commits end actual execution before
  another planning or retry round.
- Risk weights are fixed within an execution and applied to estimates and
  actual exposure consistently. All policies receive the same candidate set.
- The independent partial-failure/restart toy acquires one original, then gives
  a duplicate ID. The invalid decision terminates the stream while retaining
  original evidence. Restart reproduces the stream with no additional dispatch.
- The integrated job builder passes only public case fields and completed paid
  authorization evidence. Its runtime assertions require zero hidden audit
  calls/steps. Query labels are checked against independent truth only after
  selection/evaluation; they never change the stream or runtime gate.
- The container launcher pins an image digest, disables networking, mounts no
  host path, uses a read-only filesystem and UID 65534, drops capabilities, and
  limits resources. Module order satisfies runtime dependencies. Durable intent
  and retained exit/stdout records prevent silent reruns. This is source review;
  actual Docker verification remains the coordinator's responsibility.

## Verification recorded so far

`tests/test_query_v10.py`, `tests/test_recovery_v10.py`, and
`tests/test_acquisition_v10.py`: **94 passed**.

Initial independent review tests: **1 passed, 1 failed**; the failure was the
cap-exhaustion issue above. Following that repair and the addition of the prefix
attribution test: **2 passed, 1 failed**; the failure was item 4.

Post-repair combined verification: **103 passed** across query, recovery,
acquisition, experiment and independent review tests, using `work/p10rv4`.
All three independent review tests pass. No core correctness blocker remains
in the reviewed code. Full-project regression, heldout correctness, actual
container replay, and release provenance remain later mandatory checks; this
review does not predict experimental benefit or establish real-world safety.

The two final reporting clarifications are also resolved. The design now states
that the interface grid pairs v9/authorization/goal exactly at observation budget
2, with goal-only sensitivity at budgets 0 and 1. `model_decision_attempts`
counts all attempted decisions, while `model_request_count` excludes known
pre-I/O cap rejections and includes provider-or-unknown requests. Acquisition
summary separately records budget rejections. After these changes, all three
independent review tests pass again using `work/p10rv5`.

**Disposition: ready for prospective production freeze.** No unresolved blocker
was found within this review's scope. The original tracked-file byte-hash audit
is explicitly deferred to the coordinator's required release verification.

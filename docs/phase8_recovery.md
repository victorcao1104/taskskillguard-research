# Phase 8 equal-information recovery

`tsg.recovery_v8.execute(case, policy, fault="none", allowed_ids=None,
world_index=0, quota=16)` implements `priority_equal` and `cost_equal`.
The original source is attempted first. There are at most four actual attempts,
with one shared quota, grant set, receipt store and signature store. Actual
effects use the unchanged `recovery_v7._FaultMachine` and `runtime_v6` gateway.
The eight production fault schedules are inherited unchanged from Phase 7.

Before each possible recovery attempt, both policies enumerate and fully dry-run
the same eligible programs for the same observed history:

- All unretired catalog alternatives are considered, including alternatives
  that were infeasible in an earlier probe.
- The current route is included only after `transient_before` or `known_after`.
- A current route with another nonterminal actual failure is retired. A failed
  probe alone does not retire a catalog route.
- The original is eligible only as the current safe retry; after switching to
  an alternative it is not added to the alternative catalog.

A candidate is feasible only if its simulation has no execution error, achieves
the goal, and needs no more calls than the shared remaining quota. Both policies
finish every candidate simulation before selecting. `priority_equal` chooses a
feasible current retry first. Otherwise it chooses minimum remaining calls,
breaking ties by numeric route index. `cost_equal` always uses that minimum-call
ordering, including when the current retry is feasible.

The estimator is local to Phase 8 because the frozen Phase 6 estimator omits the
original model gate. Its probe passes `allowed_ids` through the original route's
gateway checks. Alternatives still require exact trusted grants; they do not
receive authority from the model gate. The probe copies files, emitted records,
receipts and signatures into a fresh fault-free Phase 6 machine. Read receipts
retain their cached returned values, and conflicting signatures remain conflicts.
No fault schedule, future injection, private program field, label or reference
truth is consulted by the selection routine.

`ambiguous_outcome` and actual `quota_exhausted` stop immediately without another
probe or retry. After a safe failure with insufficient remaining quota, planning
can return `no_feasible_route` without charging an impossible attempt. A
receipt-only retry remains feasible at zero remaining quota. Parse failure of
the original never falls through to alternatives. No planning is done after the
fourth attempt, because no further attempt may be selected; its observed failure
is retained as the result's failure reason.

## Evidence fields

The normal Phase 6 result fields and Phase 7 fault diagnostics are retained.
`attempt_log` contains actual routes, failure reasons, executed steps, charged
calls, cumulative calls and observed goal state. `search_estimates` contains one
record for every candidate in every planning round: remaining calls, predicted
error and goal, planner steps, simulated effects, quota and feasibility.

Each `selection_log` record contains the next attempt number, current route,
observed failure, remaining quota, complete candidate route indices and count,
feasible route indices, selected route, `estimated_calls_by_route`, planner steps,
and simulated effects. Call-map keys are strings for stable JSON serialization.
Aggregate `planner_steps`, `simulated_effects` and `routes_considered` sum all
probes. These are planning costs, separate from actual charged calls.

`initial_feasible_catalog_count` counts feasible alternatives (indices greater
than zero) in the first planning round. `initial_feasible_candidate_count` counts
the complete feasible set, including an eligible original retry. Both are null
if execution never enters planning. This distinction prevents a feasible
original retry from inflating the no-alternative stratum.

## Verification and limits

Implementation used only hand-authored toy cases and the existing Phase 6/7
runtime and tests. It did not inspect Phase 8 fixtures, reference-generation
code, reference results or model outcomes. The initial 40 tests were run before
the module existed and failed on the explicit missing-implementation assertion.
A later count-semantics regression first failed with the original incorrectly
counted as a catalog alternative, then passed after correction.

The 48 toy controls cover economical safe retries, original model gates, exact
grants, signature conflicts, unknown-commit shutdown, shared and zero quota,
equal enumeration and estimates, repeated safe failures, all four attempt slots,
state-dependent re-feasibility, stable tie-breaking, copied state and receipts,
world selection, input immutability, malformed input, and future-schedule
independence conditional on identical observed history.

Two tests temporarily extend the frozen scheduler in memory, restoring it after
each test. A persistent safe fault tests the four-attempt cap. A known commit
followed by an unknown commit demonstrates that a cheaper route can lose when
it requires a new mutation while the more expensive retry needs only reads.
These are explicitly toy schedules outside the eight benchmark schedules;
neither changes production schedules nor supplies benchmark evidence. Cost
selection minimizes fault-blind predicted calls, not risk-adjusted expected cost,
and makes no success-dominance guarantee.

Validation command: `.venv/Scripts/python.exe -m pytest
tests/test_recovery_v8.py --basetemp work/phase8-recovery-tests`.
The prior runtime/recovery compatibility subset also passed together with the
new tests. Full-project validation is left to the parent after production freeze
to preserve the production author's held-out fixture boundary.

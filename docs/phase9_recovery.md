# Phase 9 trusted observations and recovery

The production entry point is:

```python
execute(case, policy="calls", fault="none", gate_mode="conditional",
        preflight=True, cache=True, world_index=0, quota=16,
        planning_budget=128, observation_budget=2, allowed_ids=None,
        authorization_evidence=None)
```

This is a finite, synthetic, in-memory runtime. Actual effects pass through the
unchanged Phase 7 fault adapter and Phase 6 gateway. It performs no host file,
network, model or real-skill operation. The controller never consumes the
private `program`, labels, reference interpreter output or model outcomes.

## Observation and evidence boundary

Declared `worlds` are public finite hypotheses. Only the environment setup uses
`world_index`, to initialize the actual gateway and an immutable initial-state
reader. The controller does not receive that index. A singleton public world
already identifies the initial state; this is a finite-case assumption, not a
claim about unknown environments.

`observable_files` lists file paths; `observable_grants` lists `[operation,
resource]` pairs. Their defaults are the unions of paths and grants declared
across all public worlds. Empty lists hide those observation classes. A file
answer includes its presence bit and value; an absent file and an empty file
are distinguishable. Grant observations return permission membership. The
reader copies initial state before workflow execution and cannot acquire future
state through later mutations.

Default gate evidence comes from fault-free, unguarded, non-deduplicated
execution of the parsed source in each declared world. This computes the same
kind of authorization fact as the audit semantics, separately from actual
receipt-aware feasibility. Every execution is charged as one primitive plus
its executed VM steps against the shared planning budget. Incomplete execution
cannot establish authorization or inactivity: observed unauthorized occurrences
remain a negative fact; every other site stays unresolved.

Alternatively, `authorization_evidence` is a mapping from integer or string
world indices to lists of objects with `id`, boolean `occurred`, and boolean
`all_occurrences_authorized`. This input is exclusively for results of trusted
local base queries whose provenance the caller verifies. It must never contain
unverified model claims. Missing worlds and sites stay unresolved; this module
does not complete them by running hidden audits. `audit_interpreter_calls` and
`audit_steps` are zero in this mode, and the caller accounts for the producing
query work separately. A supplied evidence row asserts a completed base query;
the query engine is responsible for withholding unsupported facts after an
incomplete execution. This is deliberately stricter than blindly converting an
incomplete trace into a positive assertion.

Global typed authorization is retained as `yes`, `no`, `not_applicable`, or
`unknown` per site. Disagreement, including authorized versus inactive, remains
global `unknown`. Aggregate mode permits only sites with global `yes`.
Conditional mode permits a site when every still-compatible world proves it
authorized or inactive. Thus an authorized/inactive mixture can be conditionally
safe without erasing the global typed unknown. Consistent unauthorized sites
are denied. Missing evidence and unresolved safe/unsafe mixtures are blocked.
An explicit `allowed_ids` further restricts the original gate; it never supplies
authority or replaces trusted grants.

Conditional resolution finds a minimum-cardinality set of available initial
queries separating all currently disagreeing safety classes within the
remaining observation budget, with lexical ties, and issues its first query.
If no complete separating set fits, it chooses the single query separating the
most disagreeing pairs. It then recomputes from the observed answer. The choice
uses only public hypotheses, never the hidden answer. Every issued query,
including unavailable observations, consumes one observation unit. A response
outside every declared hypothesis stops with `observation_mismatch`.

## Receipt-aware feasibility and observations after execution

With `preflight=True`, the original and all alternatives are considered before
the first effect. Each route is dry-run on every compatible hypothesis using
the real grant, gate, receipt-reuse and signature-conflict rules. Feasibility
requires every simulation to complete, achieve the goal and fit the remaining
real quota. Original-route effects therefore cannot poison shared receipt keys
or exact event counts before an already-infeasible route is rejected.

The `preflight=False` control executes the original once without feasibility
simulation, then uses the same recovery planner. Its initial gate audit still
has its explicit cost. Alternative programs always require exact gateway
permissions even when they are outside the original site's gate.

After a safe failure, beliefs are updated only by observed gateway events:
new read returns and observed permission results remove incompatible worlds;
committed writes, deletes and emits update the remaining hypothetical states;
known receipts and accepted request signatures are copied. The controller does
not copy the actual gateway's private file map. Reused read receipts retain
their old values, even when a previous write changed the underlying file.
Ambiguous commits terminate before belief updates or further planning.

The initial gate remains fixed for the run. Every original retry is still
checked against that gate, current hypothesis state and exact actual gateway
permissions. Later observation can narrow planning beliefs; it does not
retroactively turn a missing initial gate proof into permission.

## Policies, budgets, caching and metrics

All policies enumerate the same eligible routes in ascending index order and
use the same feasibility test and budget. On the first preflight this includes
the original and every alternative. After a failure, all unretired alternatives
remain eligible; the current route is included only after `transient_before` or
`known_after`. A permanent actual failure retires its route. A failed dry run
alone does not retire an alternative. There are at most four actual attempts;
no fifth planning round runs after the fourth failure.

- `priority` selects a feasible current original/retry first, then minimum
  remaining charged calls and route index.
- `calls` selects minimum remaining charged calls, then route index.
- `risk` selects minimum remaining mutation exposure, then calls and route index.

Risk weights are declared in advance: read 0, write 1, delete 2, emit 8. Only
new charged mutation dispatches contribute, so receipt reuse adds no mutation
exposure. This is a surrogate, not an estimated probability or monetary loss.
The risk policy may spend more calls to avoid an emit. Call and risk estimates
are worst-case values across compatible hypotheses. No policy can inspect the
future fault schedule.

One primitive simulation plus each executed VM step costs one planning unit.
Gate audits and route probes share the same `planning_budget`. Before a route
is probed, the planner reserves enough capacity for every uncached hypothesis
using the structural maximum entered-step count, capped at the frozen VM's
100-step limit. Reservation is atomic at the route boundary: insufficient
capacity yields an infeasible `planning_budget_exhausted` estimate without
performing an unreported probe. Unused reservation is released; actual work is
charged. A previously completed feasible candidate may still be selected when
later candidates cannot fit. Enumeration and reservation order are identical
across policies. Static parsing, key construction and query-separation search
are not VM execution units; the reported budget is not total CPU work.

Caches are local to one execution. Keys cover program, file state, grants,
emits, receipts and returned values, request signatures, original-versus-catalog
gate semantics, allowed IDs, goal and remaining quota. Original route 0 and
catalog routes have different gate semantics; catalog indices share semantics.
Identical hypotheses or identical catalog programs can reuse complete probes.
Cache hits perform no interpreter execution, increment the hit counter, and
incur the declared lookup latency. No incomplete probe is cached. Gate-audit
reuse is also counted. `cache=False` is a complete no-cache control.

Result fields retain the previous execution trace, attempt log, charged calls,
failure reason and fault diagnostics, and add:

- `gate_log`, `global_authorization`, `global_unknown_ids`,
  `unresolved_gate_ids`, `observation_log` and `observation_count`;
- `search_estimates` and `selection_log`, with feasibility, calls, risk,
  cache use, hypothesis counts and charged planning work;
- `planning_units`, `planning_remaining`, `primitive_simulations`,
  `planner_steps`, `audit_interpreter_calls`, `audit_steps`, and cache counts;
- `mutation_risk_score`, `unresolved_commit_count`, and
  `unresolved_commit_risk` (the declared weights for ambiguous dispatches).

`planner_steps` and `primitive_simulations` include gate-audit work;
`search_estimates` contain route-probe work only. Therefore
`planning_units = primitive_simulations + planner_steps`, with audit work
separately visible. Modeled latency is deterministic:

```text
10 * actual charged calls + actual entered steps
+ 2 * observation queries + 0.1 * planning units + 0.01 * cache hits
```

These are declared abstract units, not measured time, external prices or a
claim that the risk policy minimizes latency. `authorized_goal` requires a
completed attempt; merely reaching the goal before an ambiguous commit does
not count as successful completion.

The eight existing fault schedules remain unchanged. The new adapter adds
`mixed_known_then_ambiguous` (mutation dispatch 1 known-after, dispatch 2
ambiguous-after) and `late_ambiguous` (dispatch 3 ambiguous-after). Dispatch
eligibility, receipts, mutation behavior and call charging still belong to the
frozen gateway. Unknown commits and actual quota exhaustion stop immediately.

## Test evidence and author boundary

The runtime author read Phase 6/7/8 production modules, the Phase 8 report, and
old recovery tests. No Phase 9 held-out generator, data, reference outcomes or
model results were inspected. Tests use hand-authored toy programs only.

The initial 49 tests ran before the Phase 9 module existed and failed at the
explicit missing-module assertion. They passed after implementation. Added
controls exposed two further defects before repair: incomplete audits were
initially treated as positive site proofs, and authorized/inactive mixtures
initially lost global typed unknown. Both regressions were observed failing,
then passed after correction. Tests also cover hidden-world decision equality,
minimum observations, unavailable/mismatched observations, immutable snapshots,
provided evidence incompleteness, stale receipts, original poisoning,
equal budgets, cache invalidation/reuse, risk/call tradeoffs, future-schedule
independence, unknown commits, four attempts and step-limit reservation.

Validation: `.venv/Scripts/python.exe -m pytest tests/test_recovery_v9.py
tests/test_recovery_v8.py tests/test_runtime_v6.py tests/test_selection_v6.py
--basetemp work/p9runtime -q`. The final focused run is recorded by the parent.
One earlier compatibility command used the nonexistent filename
`tests/test_recovery_v7.py` and collected no tests; the corrected command used
the existing files. Full-project verification belongs to the parent after
production freeze so the implementation author does not inspect held-out
fixtures or outcome-dependent tests.

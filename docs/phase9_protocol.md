# Phase 9 factorial audit and paid-query protocols

This implementation is restricted to the finite in-memory workflow language.
It does not invoke an API, execute a real skill, inspect reference `program` or
truth fields, or read the Phase 9 heldout generator, data, or model results.
Development uses hand-written toy workflows. Existing Phase 7/8 semantics are
retained; Phase 8's D/F comparison confounded deduplication with reducer choice,
and its T arm already required a complete additional interpreter solve.

## Factorial audit

`protocol_v9.VIEWS = ('A00', 'A01', 'A10', 'A11')`. The first digit is global-fact
deduplication; the second is access to exact tool facts.

| View | Global facts in response | Exact tool facts in input |
| --- | --- | --- |
| A00 | Repeated inside every site in a world | No |
| A01 | Repeated inside every site in a world | Yes |
| A10 | Once per world, as in Phase 8 F | No |
| A11 | Once per world, as in Phase 8 F | Yes |

Every response contains `worlds` **and** `judgments`. All worlds contain each
static candidate exactly once, including inactive sites. Each judgment contains
the candidate ID and all three typed labels. Each site supplies `occurred`,
`all_occurrences_authorized`, `suppressed_success`, and `avoiding_routes`.
`baseline_success` and `legal_routes` are world-global fields; only their placement
changes with the deduplication bit. The meaning of every field is identical.

Two offline outcomes are obtained from the same acquired response:

* Reducer 0: use the response's supplied model judgments, returned as `by_id`.
* Reducer 1: reduce the response's proposed facts deterministically, returned as
  `reduced_by_id`. It uses exactly the Phase 8 typed reducer and aggregation rules.

This gives eight cells per model from four API views. Reducer assignment is an
offline paired scoring contrast; it does not generate a second model response.
It measures replacing the model's labels with a deterministic function of that
same response, not a hidden model cognition effect.

The public APIs are `system(view)`, `payload(case, nodes, view)`,
`schema(ids, view)`, and
`parse_record(raw, ids, view, world_count, route_count, closed)`. `route_count`
includes the original route at index zero. `exact_facts` is re-exported from
Phase 8 and returns `(factorized_facts, interpreter_execution_count)`.

The parser preserves raw prediction and diagnostics. It requires strict boolean
fact types; integer world/route indexes (including explicit rejection of `0.0`
and booleans); exact world and candidate coverage; and sorted, unique, in-range
route lists. Duplicated global values must agree across every site's copies.
Any disagreement is `REDUNDANCY_INCONSISTENT` and a protocol failure, tracked
separately through `redundancy_consistent`. It never selects a majority copy,
repairs a copy, replaces facts with tool truth, or silently discards duplicates.
Invalid records return empty judgment maps and `normalized_facts=None`.
Well-formed incorrect facts remain incorrect and are reduced as supplied.

Successful parsing returns semantically normalized `{'worlds': [...]}` facts,
the separate judgment maps, `protocol_valid`, `diagnostic_codes`, and
`diagnostics`. Deduplication controls may change output burden and error rates;
report protocol failures rather than dropping them from denominators. Tool
controls add complete finite-solver computation and must be attributed that cost.

## Query selection with equal public information

`query_v9` exposes `QUERY_VIEWS=('Q0','Q1')` and `BUDGETS=(2,4,8,'full')`.
`query_system(graph)` and `query_payload(case,nodes,graph)` accept booleans or
these view names. Q0 and Q1 contain identical source, routes, worlds, goal,
catalog-closed flag, candidates, candidate IDs and query catalog. Q1 adds only
`graph`, the deterministic conservative data/control/call edges from
`runtime_v6.edges(source)`. It supplies a representation of existing public
information, not new execution observations or labels.

`query_catalog(case)` returns compact public query IDs and their meanings:

* `b{world}r{route}`: `kind='base'`, `world`, and `route`; execute that route from
  that world's initial state. Route zero is the original.
* `s{world}c{candidate_index}`: `kind='suppress'`, `world`, and `site`; execute the
  original from initial state while suppressing every occurrence of that site.

Candidate indexes are in static source order. Catalog generation only parses
the source; it performs no interpreter runs. A model returns only
`{'order': [query IDs...]}`, a full permutation, with no labels or facts. The
schema is intentionally small and the answer only repeats compact IDs; the
experiment controls the number of worlds/routes/sites and its output cap.
`query_schema(ids)` supplies the schema. `parse_query(raw,ids)` validates it and
requires exact permutation coverage. Invalid outputs return `order=[]` and
diagnostics. They are not replaced by the heuristic.

The fixed `heuristic_order(case)` schedules original baselines across worlds,
then suppressions in candidate order round-robin across worlds, then alternative
routes round-robin across worlds. It never runs the interpreter or examines
truth. `random_order(case,seed)` is a uniformly shuffled permutation using a
local seeded random generator. Model, heuristic and random orderings are each
evaluated at the same budgets.

## Accounting and incremental reduction

`evaluate_order(case,order,budget)` accepts a nonnegative integer or `'full'`.
An integer is capped at catalog size. It executes exactly the allowed prefix,
including queries whose answer has become unnecessary. Each evaluation starts
with an empty cache; only completed paid queries enter it. Invalid orders execute
zero queries, retain budget-unknown labels, and receive a protocol diagnostic.

The counted interpreter wrapper runs the same `_Machine` and finite semantics as
`runtime_v6.run_semantics`: no permission enforcement, no receipt reuse, no
injected faults, and only committed events in the fact trace. It additionally
retains `machine.steps`, the actual entered-step count. Control statements,
iterations and suppressed statements count; parser/graph construction and
reducer CPU do not count as interpreter steps. Each invocation starts with fresh
initial state. Executions and interpreter steps remain separate cost measures.

The incremental reducer only consumes cached observations. It maintains a
conservative set of possible per-world labels, aggregates all possible uniform
labels plus possible mixed-world unknown, and emits a proved label only when
one aggregate label remains. Otherwise it returns `unknown` with `reason='budget'`.
A proved unknown has `reason='intrinsic'`: an open catalog without an avoiding
witness after all relevant routes, or unavoidable cross-world label differences.
Other proved labels have `reason='observed'`.

Early witnesses include inactivity, failed original-route success (current-route
not-applicable), a legal avoiding route (catalog no), and two worlds already
showing different labels (intrinsic unknown, regardless of remaining worlds).
All candidate axes are exact once their required facts are available; a full
query catalog always supplies all facts. An unresolved label is never treated as
a proved unknown merely because its displayed value is the same string.

The result contains:

* `by_id` and `labels`: ID-mapped rows with typed labels.
* `decisions[id][axis]`: label, proven flag, reason and conservative possible labels.
* `proven[id][axis]`, `resolved` (number of proved axes), `total_labels`, and
  `intrinsic_unknown` (number of proved unknown axes).
* `executions`, `interpreter_steps`, `trace`, `observations`, `query_count`,
  `full_query_count`, `all_queries_executed`, and `first_fully_resolved_at`.
* `protocol_valid`, diagnostics, requested budget, and `authorization_evidence`.

`trace` has one record per paid run with its query identity, run steps, cumulative
steps, invocation count, resolved-axis count, success and execution error.
`observations` caches the paid result keyed by query ID. The full-budget result
is the exact, costed full-solver benchmark: worlds times (original plus alternative
routes plus candidate suppressions). It is not described as free verified facts.
Scoring against a separate complete truth computation is evaluation overhead,
not part of the limited-budget selection's evidence or counted savings.

## Authorization evidence handoff

`authorization_evidence` maps the string world index to a list of
`{'id','occurred','all_occurrences_authorized'}` rows. A world appears **only** if
its original baseline `b{world}r0` was actually paid and completed **without an
execution error** in that evaluation. Rows are derived directly from that
completed committed event trace. Inactive sites have
`occurred=False` and vacuous `all_occurrences_authorized=True`. An alternative
route or suppression does not populate the original's evidence. Step limits,
receipt conflicts, unbound variables and other baseline execution errors leave
the world absent from this handoff, even when its partial trace contains
authorized events. Missing worlds are absent, and an invalid query order provides
no evidence. Successful execution here means `error is None`; unmet task goals
alone do not make an otherwise completed trace incomplete.

The query arm's diagnostic typed labels continue to use the frozen finite
committed-trace semantics, including on an errored run. The runtime handoff is
stricter: an incomplete trace cannot prove that every future occurrence would
be authorized or that an unobserved site is inactive. Consumers keep that world
unresolved rather than converting diagnostic positive or inactive labels into
runtime authorization proof.

This field is intended for the separate trusted observation/narrowing/runtime
interface. It carries paid conditional facts, not global model labels, guessed
world identity, source-only inference, or a hidden full solve. Consumers must
retain this provenance and treat missing worlds as missing evidence.

## Development verification

The two Phase 9 test modules construct their own small workflows. They cover
all four factorial views, unchanged wrong facts, malformed types/coverage,
redundancy disagreement, duplicate JSON keys, all permutation prefixes for tiny
query catalogs, inactive and open-catalog behavior, early witnesses, nonempty
graph equivalence, fresh-cache accounting, shared receipt conflicts, step-limit
costs, and paid-only authorization evidence that excludes errored original
baselines. They do not load new heldout data.

# Phase 6 independent truth validation

This development-only record was prepared before inspecting the production Phase 6 parser/runtime or any held-out cases. The evaluator and fixture generator were independently written from `docs/phase6_design.md` and the scalar/key rulings in `docs/phase6_decisions.md`. No earlier parser, runtime, recovery implementation, model response, or authored necessity label is imported. Nothing in `sources/` or any baseline tracked file was edited for this work.

## Reference contract

`tsg.truth_v6.run(program, world, goal, suppress=None)` accepts a reference AST and returns `files`, `emits`, `trace`, `goal`, and `error`. All state is in memory. It executes unauthorized synthetic effects while recording their authorization; route legality is a separate predicate. Every entered step, including control and call steps, consumes the 100-step bound. Calls are checked for cycles before execution. An execution error makes `goal` false even if the partial state matches the goal predicate.

Scalars stringify with JSON spelling. Concat preserves argument order; upper transforms the resulting string. Missing reads return an empty string. Suppression removes every occurrence at the specified site, evaluates none of its arguments, and binds an empty output string. Explicit key reuse with a different `(op, resource, value)` signature is an error; matching keys never deduplicate reference execution. Emit requirements count exact matching resource/value occurrences, while additional unrelated emits are allowed. Required file values are exact, and unmentioned files are allowed.

`static_sites(program)` validates the AST and returns deep copies of full effect dictionaries, including `id`, `kind`, `op`, `resource`, and any present `value`, `out`, or `key`. Traversal visits the top-level steps recursively, then each function body in insertion order. It includes both branches and uncalled function bodies once, without expanding calls or repeats.

`evaluate_case(case)` returns `case_id`, `labels`, `worlds`, `catalog_closed`, and `route_count`. Each aggregate label contains `id`, the three label axes, and a `reasons` dictionary mapping each axis to a sorted list. Each world audit includes its index, original execution, every route execution, legal successful route indices, and per-world labels with intervention outcomes. These audit values are private truth data and must be excluded from model inputs.

Task necessity uses the target's dynamically observed `(op, resource)` identities in each original execution. Alternative site names do not change effect identity. A legal successful avoidance witness establishes `no` even when the catalog is open. Establishing `yes` requires a closed catalog and at least one legal successful route. An inactive target, no legal route, an open catalog without an avoidance witness, or a non-unanimous world result produces `unknown`.

## Development fixtures

`scripts/build_phase6_dev.py` deterministically writes `data/phase6/dev.jsonl`. It imports no evaluator and emits no answer labels. The JSON program inside each source fence exactly equals its reference AST. Twelve cases cover six families with two literal seeds each:

| Family | Distinct semantic content |
| --- | --- |
| transform | Read, upper, concat, staging file, and a shorter alternative route |
| branch | World-dependent branches, a dead branch, redundant legal/unauthorized emits |
| repeated | Two or three real emits, exact counts, and an unrolled alternative |
| calls | Nested function calls, shared variables, an unused function, two route orders |
| cleanup | Legal delete and emit, absence goals, open catalog, initially absent state |
| incomplete | Failed original goals, a successful alternative, mixed worlds, missing authority |

The 12 cases contain 16 worlds and 40 static original effect sites. The original succeeds in 14 worlds; some legal route succeeds in 15 worlds. The remaining world is deliberately infeasible under the supplied grants. These figures are diagnostic fixture counts, not held-out results.

| Axis | yes | no | unknown |
| --- | ---: | ---: | ---: |
| Authorization | 30 | 1 | 9 |
| Implementation necessity | 21 | 6 | 13 |
| Bounded task necessity | 9 | 15 | 16 |

Across aggregate site/axis reason entries: `inactive` occurs 24 times, `baseline_failure` 4, `mixed_worlds` 16, `open_catalog` 6, and `no_legal_route` 2. These counts overlap because a result can have multiple reasons.

## Executed validation

The first targeted run failed 17 tests because the independent module did not exist. After implementation, those 17 tests passed. The fixture test then failed because its generator did not exist. After authoring the generator, all 22 targeted tests passed. The suite checks hand-derived execution results, unique site validation, malformed AST rejection, missing variables, explicit key conflicts, the step bound, interventions, finite route reasoning, world aggregation, static inactive sites, and deterministic fixture regeneration.

A metamorphic test renames site IDs and variables and inserts an unused assignment, then checks that output state and labels remain unchanged. An exact-count test rejects three emits when the goal requires two. A dynamic-resource loop verifies that authorization requires every occurrence to be authorized, not merely the first occurrence.

Nine deliberately wrong interpreter copies were executed in temporary test directories. All nine were rejected by literal expected outcomes:

| Mutant | Observable witness |
| --- | --- |
| Upper becomes lower | Expected `AB` file and prefixed events fail |
| Concat arguments reversed | Expected `prefix:AB` events fail |
| Branch equality inverted | Expected write path/result fails |
| Repeat executes once | Two-event exact-count goal fails |
| Delete becomes a read | Required absent file remains present |
| Every effect authorized | The unauthorized emit trace is incorrectly marked true |
| Suppression ignored | Suppressing the sole output write incorrectly preserves success |
| Catalog closure ignored | Open-catalog task necessity incorrectly becomes yes |
| Intervention rule inverted | Necessary sole output write incorrectly becomes unnecessary |

The mutation tests load trusted, altered copies of the evaluator through Python's module loader; the workflow interpreter itself never evaluates supplied Python or accesses the host filesystem. Mutation rejection validates these witnesses, not completeness of the language semantics.

Verification command, from repository root: `.venv/Scripts/python.exe -m pytest tests/test_truth_v6.py -q --basetemp=work/t6truth2`, with `PYTHONPATH=src`. Result: **22 passed**. The explicit workspace temporary directory is necessary in this sandbox: the default Windows pytest temporary location failed directory creation in an earlier run. A baseline regression run was started and then interrupted at the parent's request so integration can run it once; no completed full-suite result is claimed here.

No production differential check, held-out test, API call, recovery experiment, or container execution is claimed in this development validation record. The parent integration stage is responsible for freezing hashes and recording those separate results.

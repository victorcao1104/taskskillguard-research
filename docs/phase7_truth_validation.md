# Phase 7 independent reference and generation record

Date: 2026-10-16. This record describes development validation before the
prospective Phase 7 freeze. It contains no held-out outcomes or gold labels.

## Independence boundary

The reference author read the Phase 7 design and plan, `truth_v6.py`, its tests,
the package configuration, and the Phase 6 development fixtures. The author did
not read `evidence_v7`, `protocol_v7`, the new runtime/recovery implementation,
model outcomes, or the prior held-out generator/templates. Baseline files were
not changed. The new reference imports only `ReferenceError`, `run`, and
`static_sites` from the existing independent reference interpreter. It does not
import a source parser, production executor, recovery policy, or model code.

The reference aggregates the three typed axes independently. For each world it
executes the reference program, each listed alternative, and one whole-site
suppression for each syntactic effect. All executions start from independent
copies of the same world. A route is feasible only when it succeeds and every
executed effect is exactly authorized. Avoidance is disjointness from all
operation/resource identities actually produced by the target site; sharing a
resource with a different operation does not constitute sharing an identity.

## Interface

`truth_v7.evaluate_case(case)` returns `case_id`, `labels`, `worlds`,
`catalog_closed`, and `route_count`. Aggregate label rows have `id`,
`authorization`, `current_route_required`, `catalog_required`, and axis-specific
`reasons`. The four possible values are `yes`, `no`, `unknown`, and
`not_applicable`.

Each world audit contains `index`, full `baseline` and `routes` reference
executions, `legal_route_indices`, and its own `labels`. A per-world label also
contains `occurred`, `all_occurrences_authorized`, `baseline_success`,
`suppressed_success`, `legal_routes`, `avoiding_routes`, and
`intervention_error`. An inactive site has vacuously true
`all_occurrences_authorized` and an empty `avoiding_routes` list.

Uniform per-world values are preserved, including uniform `not_applicable` or
`unknown`. Other combinations aggregate to `unknown`. Mixing `not_applicable`
with an applicable value records `partial_applicability`; disagreement among
two or more applicable values records `world_disagreement`. Both can occur
with three or more worlds. Per-world reasons are retained in the aggregate.

## Test evidence

The first targeted test run occurred before either new implementation file
existed: 15 tests failed through explicit assertions that the typed reference
or generator was missing. After implementation, the typed reference tests
excluding generation passed (14 passed, 1 deselected). The complete new test
file and the existing independent reference suite then passed:

```text
.venv/Scripts/python.exe -m pytest tests/test_phase7_truth.py tests/test_truth_v6.py --basetemp work/pytest7truth -q
37 passed in 4.04s
```

Hand-derived toy witnesses cover inactive functions, denied but nonessential
effects, failed original routes, absence of feasible routes, open versus closed
catalogs, feasible avoiding routes, multiple dynamic identities at one site,
mixed applicability, disagreement within applicable worlds, simultaneous
aggregation causes, input immutability, and malformed case boundaries.

The 12 existing development cases verify that mapping `not_applicable` back to
`unknown` exactly matches all three existing reference axes after renaming.
No held-out case was passed to either reference evaluator or any runtime.
The complete repository suite and any held-out evaluation are left to the
parent's integration/freeze sequence so new tests from other workers cannot
accidentally evaluate held-out data before freeze.

## Generated input

The deterministic new generator writes 24 cases: 12 independently authored
structural families, each with seeds 0 and 1. Every case uses `split="heldout"`.
The original Markdown source contains exactly one workflow block encoding the
same program as its private reference AST. No answer field or authored gold
label is emitted.

Validation before freeze checks counts, unique identifiers, family replication,
finite world/goal shapes, exact source encoding, and reference AST syntax via
`static_sites`. It does not execute cases or derive their labels. Regeneration
to a temporary path is tested for byte-for-byte equality with the saved input.

The intended coverage is compositional within the unchanged finite DSL:
nested calls with branches and repeats; data flowing through reads, writes and
transformations; multiple resources at one repeated site; inactive branches,
zero repeats and unused functions; permission differences across worlds;
pre-existing goals and failing original routes; explicit receipt conflicts;
open catalogs; read-only paths; exact emission counts; and ordered alternative
routes with different call costs, including infeasible alternatives. These
are design intentions, not empirically verified held-out outcome counts.

Saved input SHA-256:

```text
d9d14584e9c63bd2ef244c196cd3e32dd9cf12af641cf7510da82b232e9ccfd3
```

The new cases test structural recombination in the same language. They do not
establish generalization to arbitrary natural-language tools or unrestricted
programs. Independence here concerns separate aggregation and source/reference
paths; the Phase 6 reference interpreter is intentionally shared across
reference versions.

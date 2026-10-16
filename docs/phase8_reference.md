# Phase 8 independent fixtures and reference evidence

The new split contains 48 cases: twelve authored structural families and four deterministic lexical variants per family. There are 84 supplied worlds and 224 static candidate effect sites. All programs use the frozen Phase 6 finite DSL. No real skill or downloaded program is executed.

## Independence and freeze procedure

The fixture author read the prospective Phase 8 design and implementation plan, the old Phase 7 fixture builder for file conventions, the frozen `truth_v6.py` and `truth_v7.py` reference interpreters, and reference-only tests. Prior Phase 6 development, heldout and challenge ASTs and Phase 7 heldout ASTs were read for the novelty comparison. Production parsers, production executors, evidence protocols, recovery implementations and new model outcomes were not inspected or imported.

All truth comes from the reference interpreters. Input cases contain no authored answer labels. Source Markdown embeds exactly the original reference AST. `truth.jsonl` includes complete aggregate typed labels, per-world facts and reasons, all original/alternative execution traces and final states, and a complete execution for every single-site suppression intervention.

The first generation was retained under `work/phase8-reference/iteration1/`. It met all prospective coverage criteria. No fixture correction, rejection, resampling, family substitution or outcome-based tuning occurred after that audit. The final heldout bytes match the first generation. The initial reference test run failed because the new builder did not exist; a separate temporary-directory permission failure was resolved by placing test scratch output under `work/phase8-reference/`. Subsequent checks used the reference-only test files; the author deliberately did not run tests importing production implementations.

The generator uses exclusive file creation and refuses to replace any existing target. Final files are created once in `data/phase8/` and `results/phase8/reference/`. A reproduction must use fresh output paths, for example:

```powershell
.venv/Scripts/python.exe scripts/build_phase8_heldout.py --output work/phase8-reference/reproduction/heldout.jsonl --audit-dir work/phase8-reference/reproduction/audit
```

The provenance artifact records hashes of the generator, both frozen reference modules, every prior data file, the new heldout file, and all three computed audit/truth outputs. Prior files are read only and are never regenerated in place.

## Prospective coverage

| Measure | Observed | Requirement |
|---|---:|---:|
| Cases | 48 | 48 |
| Families | 12 | 12 |
| Variants in each family | 4 | 4 |
| Cases with no alternatives | 20 | at least 12 |
| Cases with multiple worlds | 36 | at least 12 |
| Supplied worlds | 84 | all evaluated |
| Aggregate candidate sites | 224 | all evaluated |

| Axis | yes | no | unknown | not_applicable |
|---|---:|---:|---:|---:|
| authorization | 128 | 12 | 36 | 48 |
| current_route_required | 72 | 40 | 64 | 48 |
| catalog_required | 22 | 52 | 70 | 80 |

Every axis/type cell exceeds the required eight. In particular, authorization has twelve `no` labels. Unknown and inapplicable remain separate categories. `coverage.json` reports per-family label counts, aggregate reasons and every relevant world identifier, so these are auditable counts rather than intended labels.

## Authored structures

| Family | Structural composition |
|---|---|
| escrow_mirror | Conditional checkpoint creation, consume-before-delete ordering, separate finish call, unreachable function |
| nested_seal | Repeated outer call, branch, inner call and nested repeat; unauthorized side read after exact emissions |
| conditional_permit | World-dependent branch around a repeat/call writer and conditional notification; zero-trip deletion |
| deadletter_cycle | Unauthorized deletion, repeated scratch read, first-iteration-only commit call, mode update |
| costly_retry_fanout | First read, repeated pair of checkpoint calls with a data-dependent branch, final transformed write |
| checkpoint_receipt | Keyed initial write, call containing repeated copy calls, final checkpoint read and output write |
| fork_join_diff | Two branch-specific input functions with different nesting join a shared writer/emitter |
| preexisting_abort | Read-selected explicit key conflict inside a function before an output write; preexisting successful state |
| dynamic_object_matrix | Repeated call with a changing resource handle and accumulated value; conditional anomaly emission |
| shared_emit_key | Reused emitter call versus conflicting sibling call, shared explicit key, exact emit-count goal |
| guarded_delete_restore | Data-dependent delete/restore call on one resource, trailing emission, grant-blocked alternative |
| nested_noop_observer | Zero-trip nested call tree, live read, conditional repair, success/failure preexisting worlds |

The four variants vary payloads, resource paths and site/variable/function identifiers. Two families also vary catalog closure. Their AST skeletons intentionally coincide within each family: this is twelve structural families, not forty-eight independent structures.

Eight original/world executions intentionally fail with `key_signature_conflict` in the two conflict families. Their partial traces and failed-goal status are preserved. Errors are part of the frozen DSL's bounded behavior, not malformed syntax. All referenced programs pass the reference static validator.

## Recovery and integration situations

Eight cases have legal original paths with a harmless read or keyed write first, followed by substantially more effects than a legal direct alternative. The first family of cost witnesses executes ten effects versus a one-effect alternative; the second executes seven versus one. These are reference fresh-start effect counts. They establish inputs suitable for testing economical retry selection; they do not claim a recovery policy result or inspect any recovery implementation. Post-fault state, remaining calls, receipts, quotas and unforeseen faults must still be measured by the separately frozen recovery experiment.

There are 48 supplied worlds with no feasible alternative under exact reference grants. Twenty of those have a legal original route. Twenty whole cases have no alternatives at all. Additional worlds contain alternatives that would satisfy the goal if their ungranted effects were ignored. These strata expose cases where alternative routing cannot automatically conceal an original gate mistake. Trusted grant enforcement remains separate from model authorization accuracy.

## AST novelty audit

Every new original was compared with all 72 prior originals: Phase 6 dev (12), heldout (24), challenge (12), and Phase 7 heldout (24). A second comparison includes every alternative AST from those files, for 186 reference programs in total. Source text and model answers are not used.

Normalization removes all site, variable and function names, path strings and literal values, while preserving scalar types, operation and expression operators, sequence order, branch arms, control nesting, key/output-field presence and recursively expanded call boundaries. It also retains every function definition, including unreachable definitions, sorted by its normalized body. A token is one explicit syntax marker, operator or scalar-type marker. Distance is unit-cost Levenshtein insertion/deletion/substitution over those tokens. Nearest matches retain all tied prior case IDs and route indices.

| Comparison pool | Exact duplicate new originals | Nearest distance min | Median | Mean | Max |
|---|---:|---:|---:|---:|---:|
| All 72 prior originals | 0 | 28 | 44.5 | 46.3333 | 65 |
| All 186 prior original/alternative ASTs | 0 | 28 | 44.5 | 46.25 | 65 |

The cross-phase exact-duplicate lists are empty. Within the new split there are exactly twelve duplicate groups of four cases, one per family. The complete groups, every per-case nearest match, histograms and prior input hashes are in `novelty.json`; these within-family duplicates are reported rather than treated as novel samples.

Limitations: literal erasure collapses repeat counts, zero-trip/live loops, equality outcomes and receipt identities. Erasing variable names loses alias and binding-identity information even though expression structure remains. Worlds, grants, goals and closure are outside the program skeleton. Retaining definitions and expanded call bodies gives reused functions more token weight than a flat sequence. The measurement concerns new originals; although every prior alternative is in the expanded comparison pool, it is not a claim that the new catalog's simple direct alternatives are novel. Token distance is neither semantic distance nor proof of independent difficulty. These are new compositions within the same finite DSL, not unseen-language generalization.

## Verification and artifacts

Reference checks cover prospective typed coverage, exact source embedding, complete suppression evidence, normalization behavior, known edit distances, actual duplicate detection, full prior split inclusion, economical-path witnesses, no-shortcut witnesses, exclusive writes and byte-for-byte reproduction of frozen cases and truth. Frozen v6/v7 reference tests provide additional hand-derived semantic checks.

The final reference-only run passed all 44 tests in 3.19 seconds. `results/phase8/reference/reference-tests.xml` preserves the result. This is not a claim about the separate production test suite.

Run only the reference scope for the independent fixture author:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_truth_v6.py tests/test_phase7_truth.py tests/test_phase8_reference.py --basetemp work/phase8-reference/pytest-final
```

Artifacts:

- `data/phase8/heldout.jsonl`: independent new-only heldout input; SHA-256 `3227ebe41487e57b0f9df7eb60a9685c1d781a1f0fa7cc532fbc57a9c9907adf`.
- `results/phase8/reference/truth.jsonl`: complete reference execution and typed-label evidence.
- `results/phase8/reference/coverage.json`: acceptance, distributions, error records and case/world strata.
- `results/phase8/reference/novelty.json`: normalized skeleton comparison and all nearest-match records.
- `results/phase8/reference/provenance.json`: frozen input/output hashes and independence declaration.
- `results/phase8/reference/reference-tests.xml`: final 44-test reference-only verification result.

The production author must keep these fixtures unread until production freeze; production/reference differential verification is a separate post-freeze step.

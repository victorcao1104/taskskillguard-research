# Phase 10 independent synthetic reference

The reference contains 24 handwritten cases in twelve structural families, with two deterministic lexical variants per family. Each case uses the unchanged Phase 6 AST and frozen `truth_v6`/`truth_v7` semantics. Cases contain source, original AST, finite worlds and grants, alternatives, goal, catalog closure, identifiers, split, and explicit observation allowlists. Cases contain no answer labels.

At this handoff, inputs and executable truth exist only in `results/phase10/reference/first-pass`. No `data/phase10` input has been materialized. Production authors must not inspect this document, the generator, new reference tests, or first-pass artifacts until their separate production freeze is recorded.

## Independence and retained first pass

The author consulted the public Phase 10 design, frozen reference interpreters, prior reference generator helpers and tests, and Phase 6 development/heldout/challenge plus Phase 7/8/9 heldout ASTs for the structural audit. No Phase 10 production, parser, query, controller, orchestration, production tests, model answers, or controller outcomes were read or imported. The generator imports only `tsg.truth_v6` and `tsg.truth_v7` from the project; copied normalization and coverage helpers are self-contained.

Reference tests were written first. The initial run recorded nine generator-absent setup assertions in `work/p10ref/red-tests.xml`. The initial complete generator was evaluated once into the immutable `first-pass` directory before running those tests. All prospective coverage checks passed. No original, alternative, world, grant, goal, allowlist, or catalog closure was changed after that evaluation. No favorable controller result was used as a selection criterion. The independent reference scope then passed 45 tests, with one intentional prefreeze skip, in 16.15 seconds; `results/phase10/reference/first-pass/reference-tests.xml` retains the result.

The generator exclusively creates outputs. Existing inputs, audits, or preliminary outputs cause an exception instead of replacement. The initial provenance records source hashes and artifact hashes, including these bytes:

* Generator: `f5eb148a0a694c6e5f32dee25f3eba447647aa59da7a943848aea18900a3dc83`.
* Heldout: `215646cd12f42b27bb32bebdceae04201060f4c21c6c74b0eef71ad98d870de8`.
* Truth: `2bbfdd3b98f8dec97673c9f46e24af94f1a825d4efb2ff380591a56d91ab1b56`.
* Coverage: `3bf74747885d412eefd00d606f8140c54b8b771c5ff1c5aa9bf5bdd6de63b44e`.
* Novelty: `f6c3d6eb5799e1e7c806ff3bd02255cf9e158c5d233618883635f441a3f4b675`.

## Families and observation contract

| Family | Authored structure | Worlds | Alternatives | Static effects |
|---|---|---:|---:|---:|
| transform_pipeline | Fixed read, concatenate, write, read, uppercase, cleanup pipeline | 2 | 0 | 7 |
| two_gate_relay | Two independent flags gate a value through a nested assignment branch | 3 | 0 | 5 |
| concealed_branch_ledger | Hidden input selects payload before a ledger subroutine | 2 | 0 | 5 |
| concealed_loop_cofactor | A hidden cofactor enters each bounded accumulator iteration | 2 | 0 | 6 |
| denied_accumulator_cleanup | Accumulation followed by denied checkpoint, deletion and emission | 1 | 1 | 6 |
| denied_subroutine_join | Denied subroutine effects precede a read/literal branch join | 2 | 1 | 6 |
| receipt_token_splice | Input-selected write receipt can alias a later emission receipt | 2 | 2 | 6 |
| postgoal_changing_receipt | Goal write precedes repeated subroutine receipt conflict | 1 | 2 | 5 |
| conditional_missing_binding | One input enters an unbound-variable branch before output | 2 | 2 | 5 |
| repeated_selected_cleanup | Repeated deletion follows an input-selected resource | 2 | 2 | 6 |
| optional_overwrite_fork | A branch can overwrite an already achieved output | 2 | 0 | 7 |
| nested_grant_relay | Nested private read versus repeated local subroutine, with grant uncertainty | 3 | 0 | 6 |

Every row has two lexical variants. Paths, payloads, sites, variables, and function names vary deterministically. Catalog closure also varies in the last two families. All supplied originals and alternatives pass the reference static validator.

`observable_files` permits inspection of exactly the listed initial paths. Each listed path has a read grant in every supplied world and is never mutated by the original. `observable_grants` permits inspection of exactly the listed operation/resource memberships. An empty list permits no observations of that type. The audit helper also supports omitted fields using the same finite-union convention as the prior reference. File observations distinguish absence from an empty string; grant observations distinguish grant membership from denial. These allowlists do not modify interpreter execution, grants, truth, catalog closure, or goals.

Six cases have identical per-site authorization labels across worlds but different original goal success. Their allowed, legal initial reads separate all world pairs with different goal success. This definition includes applicability when comparing authorization and therefore does not mistake an inactive branch effect for uniform authorization. The `two_gate_relay` variants require two file reads to classify original goal success for every supplied world: each single flag leaves a successful world indistinguishable from a failing world. One observed negative flag can still suffice for a particular world. The recorded minimum is a finite information bound for the goal partition, not a prediction of a controller's selection, planning cost, or recovery completion.

Four cases in the two concealed families have empty file and grant allowlists. Their worlds have identical allowed observations and disagree on current-route and catalog labels, including applicability. The complete witness pairs are retained in coverage. They have no supplied alternative route; no added fallback makes recovery artificially successful. Irreducibility is relative to this initial-observation contract. Paid diagnostic execution can provide different evidence.

## First-pass coverage and shortcomings

| Measure | Initial observation |
|---|---:|
| Cases / families / variants | 24 / 12 / 2 |
| Supplied worlds | 48 |
| Aggregate candidate sites | 140 |
| Static effects per original | 5–7, median 6 |
| Cases without alternatives | 12 |
| Multiworld cases | 20 |
| Pairwise distinguishable multiworld cases | 16 |
| Hidden cases with differing truth | 4 |
| Goal-only observable cases | 6 |
| Cases requiring two reads for complete goal partition | 2 |
| Cases with original key conflicts | 4 |
| Incomplete original/world executions | 6 |
| Cases with legal call/emission tradeoffs | 8 |
| Active / inactive world-site pairs | 220 / 60 |

| Axis | yes | no | unknown | not_applicable |
|---|---:|---:|---:|---:|
| authorization | 86 | 12 | 26 | 16 |
| current_route_required | 8 | 18 | 90 | 24 |
| catalog_required | 8 | 34 | 80 | 18 |

All four types are present on every axis. The prospective minority thresholds were eight authorization `no` and eight current-route `no`; both passed without revisions. Current-route and catalog `yes` remain small cells, and unknown dominates those axes. These shortcomings are retained. No class balancing, model exposure, or controller-outcome tuning followed evaluation. Twelve lexical pairs share both reference semantics and common mechanisms; neither the labels nor expanded runtime conditions turn them into independent samples.

Four original/world executions intentionally fail with `key_signature_conflict`. Two others intentionally fail on an unbound variable in an input-selected branch. These are statically valid programs with executable failure behavior. The two postgoal receipt cases have matching goal files at failure; the reference still marks their original runs unsuccessful because an incomplete execution cannot satisfy a goal. There are 28 supplied worlds with no feasible alternative, including worlds in which the original is legal.

Eight cases have two competing legal alternatives. The short route performs an extra emission and one goal write; the longer route performs three preparation writes and one goal write. Cleanup adds a common deletion. With the design's default weights, the short ordinary pair has operation risk 9 versus 4 for the longer route; uniform mutation weights give 2 versus 4; write-heavy weights give 5 versus 16. A shared cleanup deletion adds the same policy-specific amount to each side. These arithmetic contrasts follow only from the fresh-start operation traces. Receipt eligibility, fault timing, retained prior effects, and actual route selection must be measured separately.

The two receipt families also share explicit emission keys with a short alternative. An original marker may have already claimed that key with a conflicting write signature, while the longer write-only alternative avoids it. The postgoal family commits a keyed emission before a later changing-signature attempt fails. These patterns expose receipt-sensitive alternatives without claiming that a fresh-start legal alternative is necessarily legal after a prefix or fault. Identical key/signature emissions are repeated effects under frozen reference semantics; no deduplication was inserted.

## Structural audit

Every new original is compared with all 144 prior originals and all 314 prior original/alternative ASTs from Phase 6 development/heldout/challenge and Phase 7/8/9 heldout. Each old file's hash and count is retained. No old dataset was changed.

The unchanged prior normalization erases site, variable and function names, resources/paths and literal values. It retains scalar types, operations, expression operators, sequence order, branch arms, control nesting, explicit-key/output-field presence, recursively expanded call boundaries, and every function definition sorted by normalized body. Distance is unit-cost token Levenshtein. All tied nearest prior case and route identities are retained.

| Pool | Exact matches | Nearest minimum | Median | Mean | Maximum |
|---|---:|---:|---:|---:|---:|
| Prior originals | 0 | 20 | 29 | 30.3333 | 45 |
| Prior originals and alternatives | 0 | 17 | 28 | 29.25 | 45 |

Exactly twelve within-new duplicate groups contain two cases each. These match the authored lexical pairs. Alternative routes are deliberately simple and are not claimed structurally new. Literal erasure hides loop counts, receipt identity, and branch outcomes; variable erasure hides alias/binding relationships. Worlds, grants, goals, closure and allowlists lie outside the skeleton. Call expansion weights reused bodies both at call boundaries and in definitions. Distinct token skeletons do not establish distinct semantics, independent difficulty, unseen-language generalization, or external validity.

## Interfaces and release

The generator exposes `build_cases()`, `reference_record(case)`, `coverage_audit(cases, records)`, `novelty_audit(cases)`, `observation_signature(case, world)`, `skeleton_tokens(program)`, `token_distance(left, right)`, `jsonl_bytes(rows)`, and `write_once(path, bytes)`. Complete truth includes aggregate typed labels and reasons, per-world labels, original and alternative traces/final states, legal route indices, and every single-site suppression execution. No production module participates.

CLI defaults target the private initial directory and therefore refuse a second invocation after this first pass. After the production author records the separate production freeze, materialize the identical cases and audits with:

```powershell
.venv/Scripts/python.exe scripts/build_phase10_heldout.py --out data/phase10/heldout.jsonl --audit-dir results/phase10/reference
```

This creates the heldout plus `truth.jsonl`, `coverage.json`, `novelty.json`, and `provenance.json`. It does not replace any existing target. Reproduction needs fresh paths, for example `--out work/p10ref/reproduction/heldout.jsonl --audit-dir work/p10ref/reproduction/audit`. The heldout, truth, coverage, and novelty bytes must match the retained initial hashes.

After release, rerun the independent reference scope to exercise the previously skipped materialized-byte check:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_truth_v6.py tests/test_phase7_truth.py tests/test_reference_v10.py --basetemp work/p10ref/postfreeze --junitxml results/phase10/reference/reference-tests.xml
```

Production/reference differential checks, model acquisition, recovery experiments, and controller analysis belong to the post-freeze campaign. They were not performed by the independent reference author. The complete first-pass evidence, minority cells, unavailable alternatives, hidden uncertainty, and intentional failures must remain in that campaign.

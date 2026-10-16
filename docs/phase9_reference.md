# Phase 9 independent heldout and reference evidence

This split contains 24 independently handwritten finite cases: twelve mechanism families with two deterministic lexical variants each. It uses the unchanged Phase 6 program DSL and frozen `truth_v6`/`truth_v7` reference semantics. The generator has no production or model dependency. At the time of this reference-author handoff, heldout inputs and reference truth have **not** been materialized into `data/phase9` or `results/phase9`; the production author must record the production freeze before invoking the generator.

## Independence and first-pass record

The author inspected the frozen reference interpreters, the Phase 8 reference builder and documentation for conventions and audit comparability, old Phase 6/7/8 ASTs for structural comparison, and reference-only tests. The new production protocol, query and recovery modules, other agents' implementation code, and model outcomes were neither read nor imported. The only imported project modules are `tsg.truth_v6` and `tsg.truth_v7`.

The first complete handwritten generator met every prospective coverage criterion. No cases were substituted, resampled, corrected or tuned after its first reference evaluation. No outcome favorable to a new policy was required. `work/p9ref/first-pass/coverage.json`, `novelty.json` and `candidate-hashes.json` retain that first audit and the candidate byte hashes without revealing a materialized input or truth JSONL. The generator hash in that record is `47dfe5d2a59f8142b0855ee32bfd2b80a016c3c63f7afa462dcedd8b37b9adcc`.

The new tests were added before the generator. Their initial run produced nine setup assertions that the generator was absent, recorded in `work/p9ref/red-tests.xml`. After implementation, the independent reference scope passed **45 tests with one intentional prefreeze skip** in 13.09 seconds; `work/p9ref/reference-tests.xml` preserves the result. The skipped test checks byte-for-byte reproduction once final files exist. The reference author did not run a production test suite, to preserve the stipulated separation.

## Cases and observability

| Family | Mechanism | Worlds | Alternatives | Static effects |
|---|---|---:|---:|---:|
| write_through_pointer | File-selected write/read alias followed by a verification branch | 2 | 0 | 6 |
| staged_accumulator | Repeated read-after-write accumulation and first-iteration marker | 2 | 0 | 6 |
| conditional_rotation | Destructive rotation commits or restores from a separately read backup | 2 | 0 | 7 |
| pointer_chain_fold | Bounded linked-file traversal folds next pointers into a result | 2 | 0 | 5 |
| resource_key_poison | File-supplied key aliases a write and a branch-selected delete | 2 | 1 | 6 |
| evolving_value_receipt | One keyed write site changes payload on the second loop occurrence | 1 | 0 | 4 |
| canonical_key_alias | Uppercase and concatenation key expressions collide in one world | 2 | 1 | 6 |
| repeated_queue_receipt | Identical keyed emits count twice before a conflicting stamp | 2 | 1 | 6 |
| lazy_manifest_materialization | Lazy input branch enters repeated cache writes and reads | 2 | 2 | 6 |
| alternating_fanout_join | Mutable loop cursor selects distinct write arms before a join | 1 | 2 | 6 |
| cleanup_outbox_join | Conditional destructive cleanup joins an unconditional audit write | 2 | 2 | 6 |
| guarded_pair_join | Two preparation structures join read files across three worlds | 3 | 3 | 8 |

Each row has two lexical variants. Payloads, paths and site/variable/function names vary deterministically. Catalog closure also varies in two families. The output source Markdown embeds exactly the original reference AST. No answer labels are stored in cases. All supplied originals and alternatives pass the frozen reference static validator.

Two optional case fields describe permitted **pre-execution** observations:

* `observable_files: list[str]` restricts file inspection to those exact paths.
* `observable_grants: list[[op, resource]]` restricts grant-membership inspection to those exact operation/resource pairs.

Omitting a field leaves that observation type unrestricted. An empty list permits no observations of that type. File observations distinguish absent paths from empty-string contents; grant observations distinguish membership from denial. These fields do not change execution, ground truth, authorization, catalogs or goals. The reference audit projects worlds onto the supplied allowlists, or onto the finite union of supplied file names/grant identities when unrestricted. Any other item absent in all worlds cannot distinguish those worlds.

Both variants of `staged_accumulator` and `canonical_key_alias` explicitly set both lists to `[]`. Their per-world reference labels disagree while every permitted observation is identical, producing four independently auditable hidden-uncertainty cases. The audit records every differing site/axis value and indistinguishable world pair. Irreducibility is relative to this observation contract: an additional diagnostic operation capable of reading hidden state would change the information model.

## First-pass prospective coverage

| Measure | Observed | Requirement |
|---|---:|---:|
| Cases / families / variants per family | 24 / 12 / 2 | 24 / 12 / 2 |
| Supplied worlds | 46 | 1–3 per case |
| Static candidate effects | 144 | all evaluated |
| Static effects per original | 4–8, median 6 | typically 4–8, at most 12 |
| Cases with no alternatives | 10 | at least 6 |
| Multiworld cases | 20 | include observable and hidden strata |
| Pairwise distinguishable multiworld cases | 16 | at least 8 |
| Hidden cases with actual label disagreement | 4 | at least 4 |
| Cases with reference key conflicts | 8 | at least 4 |
| Cases with legal call/emission tradeoffs | 8 | at least 4 |
| Active / inactive world-site pairs | 212 / 72 | both present |

| Axis | yes | no | unknown | not_applicable |
|---|---:|---:|---:|---:|
| authorization | 80 | 4 | 40 | 20 |
| current_route_required | 36 | 6 | 74 | 28 |
| catalog_required | 13 | 34 | 61 | 36 |

Every axis has all four types. Minority cells are reported as observed, including four authorization `no` and six current-route `no` sites; their counts were not increased after evaluation. Unknown and not-applicable remain separate. `coverage.json` reports per-family label counts and typed reasons, all hidden-world witnesses, all key-conflict world/routes, all tradeoff route pairs, and no-feasible-alternative worlds.

Eight original/world executions intentionally fail with `key_signature_conflict`; these are executable language behavior, not malformed ASTs. Failed execution cannot satisfy the goal even if its partial final files happen to match. The canonical-key and resource-key families mix successful and failing worlds, whereas the evolving-value family fails after the second differing keyed occurrence. Identical-key identical-signature queue emissions remain repeated effects under the frozen reference semantics.

Twenty supplied worlds have no feasible alternative, including eight where the original is legal. Ten complete cases have empty alternative lists. No fallback path is inserted to ensure recovery succeeds.

The four tradeoff families offer a legal short route with an extra emission and a longer route with more ordinary local writes. The common route pair has two effects versus four writes; the cleanup case adds the same deletion to each. These fresh-start reference facts establish an operation and call-count contrast. They do not assert post-fault eligibility, an actual numerical risk ordering under every possible weight scheme, successful recovery, or which policy will win. Separate frozen recovery experiments must measure those outcomes.

## Normalized structural novelty

The audit compares every new original with all **120 prior originals** from Phase 6 development, heldout and challenge, Phase 7 heldout, and Phase 8 heldout. A second pool contains all **266 prior original and alternative ASTs**. Prior files are read only, and their hashes and counts are recorded.

For comparability, normalization follows the Phase 8 reference audit. It erases all site, variable and function names, resources, paths and literal values. It retains scalar types, effect operations, expression operators, sequence order, branch arms, control nesting, explicit-key/output-field presence, recursively expanded call boundaries, and every function definition including unused definitions in normalized body order. Distance is unit-cost token Levenshtein insertion/deletion/substitution. The complete audit retains all tied nearest case IDs and route indices.

| Comparison pool | Exact matches | Nearest min | Median | Mean | Max |
|---|---:|---:|---:|---:|---:|
| 120 old originals | 0 | 28 | 37.5 | 39.5833 | 71 |
| 266 old originals and alternatives | 0 | 16 | 36 | 36.75 | 71 |

There are exactly twelve within-new duplicate groups of two, matching the authored families. The two variants are dependent samples, and the twelve families also share the DSL, reference semantics and common mechanisms. They are not twelve proven independent semantic mechanisms. A family-clustered analysis can respect the obvious pairing without claiming independence across families.

Literal erasure collapses loop counts, zero-trip/live execution, equality outcomes and receipt identities. Variable erasure loses binding and alias identities. World contents, grants, goals, closure and observability are outside the skeleton. Call expansion counts reused function bodies both at call boundaries and as definitions. The audit concerns new originals; the simple new alternatives are not claimed novel. Token distance is neither semantic distance nor a proof of independent difficulty or unseen-language generalization.

## Materialization after production freeze

The generator exclusively creates files and refuses to replace any existing target. Only after recording the separate production freeze, run:

```powershell
.venv/Scripts/python.exe scripts/build_phase9_heldout.py --output data/phase9/heldout.jsonl --audit-dir results/phase9/reference
```

This creates the heldout, complete truth, coverage, novelty and provenance. Truth records include typed aggregate labels, per-world labels and reasons, every original/alternative execution with traces and final states, legal route indices, and a complete execution for every single-site suppression. The provenance records the generator, frozen reference modules and all prior data hashes plus the new artifact hashes.

Expected first-pass bytes:

* Heldout SHA-256: `26067c3cd3927f7d0f454a58d504bb8c83cd735aee6600507410d75d581c2627`.
* Truth SHA-256: `b0f86118b1c7ce40c03fd8b526d6bcdc8d7c8e6babefae85f595b46a51d48a96`.

Then run the reference scope again to turn the intentionally skipped frozen-byte check into a passing check:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_truth_v6.py tests/test_phase7_truth.py tests/test_reference_v9.py --basetemp work/p9ref/postfreeze --junitxml results/phase9/reference/reference-tests.xml
```

Reproduction must use fresh paths, for example `--output work/p9ref/reproduction/heldout.jsonl --audit-dir work/p9ref/reproduction/audit`. Production/reference differential verification belongs to the post-freeze integration step and was not performed by this independent reference author.

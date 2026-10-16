# Phase 8 independent outcome review

Date: 2026-10-16. Status: complete; no open blocking correctness finding in the reviewed evidence, analysis, verifier additions or final report. This review preserves `phase8_prefreeze_review.md`. The reviewer made no implementation, provider, network or Git changes and did not rerun the parent-owned exhaustive old-file hash check. The parent must still complete the comprehensive release verifier and freeze release hashes after all authors stop writing; this document does not anticipate that result.

## Evidence independently checked

- Recomputed reference labels for all 48 new cases: 12 authored families with four variants each, 84 supplied worlds, 224 candidate sites, 20 cases without alternatives and 36 multiworld cases. Each prospective typed-label count matches the saved coverage artifact. Authorization has 12 `no` labels.
- Reproduced the frozen held-out and complete reference-truth bytes, and JSON-normalized coverage and novelty artifacts. Reference provenance source/artifact hashes match. The novelty audit has 12 new skeletons, each shared by four variants, zero exact prior-original/catalog duplicates, and nearest token-edit distances 28–65. This is finite-DSL composition novelty, not unseen-language generalization.
- Verified both freeze manifests: 154 production entries and 155 data-freeze entries. This checks those frozen files, not the separate historical baseline in full.
- Replayed all 5,856 recovery conditions from saved jobs. The independent expected Cartesian grid has 122 worlds × two quotas × eight faults × three policies, with no missing or duplicated conditions. All replay results equal the saved VM and container results.
- Replayed all 8,784 integration conditions: 122 worlds × four faults × two policies × nine pipelines. All results equal saved VM and container results.
- Verified every one of the 37 actual container batches against jobs, command/image, module hashes, payload/intent hashes, exit status, UID and stdout rows. Recovery batches are fourteen × 400 plus 256; integration batches are twenty-one × 400 plus 384. All 14,640 conditions have zero unauthorized effects, zero duplicate effects, no quota overrun and at most four attempts.
- Recomputed all 480 raw request fingerprints, dispatch identities and strict parser outputs. All raw requests completed. There are 432 primary responses, of which 429 are protocol-valid; the 48 extra replicates contain one additional invalid response. All four invalid records are F world-coverage mismatches and remain in the denominators.
- Recomputed every new settled cost from raw token usage and the inherited conservative price table. The 480 unique reservations correspond exactly to the new ledger entries. The campaign reservation upper bound is USD 3.5372541; conservative incremental usage cost is USD 0.3250774; cumulative exposure is USD 16.99219805, leaving USD 12.559377075 under the cap. These are bounds, not provider invoices. Raw model identifiers are `gpt-6-luna` and `gpt-4.1-mini-2025-04-14`, 240 responses each.

## Recovery findings that reporting must preserve

| Split | Policy | Successes / conditions | Charged calls | Planning steps |
| --- | --- | ---: | ---: | ---: |
| New held-out | Phase 7 safe retry | 580 / 1,344 | 4,756 | 760 |
| New held-out | Priority | 636 / 1,344 | 4,384 | 6,172 |
| New held-out | Cost | 636 / 1,344 | 4,064 | 5,968 |
| Regression | Phase 7 safe retry | 448 / 608 | 2,088 | 1,096 |
| Regression | Priority | 448 / 608 | 1,996 | 4,160 |
| Regression | Cost | 448 / 608 | 1,948 | 4,048 |

Cost versus priority has no success wins or losses in this fixed grid. It saves 320 calls over 636 new-split both-success pairs and 48 calls over 448 regression both-success pairs. Across 1,716 planning rounds with identical prior observed execution histories, both new policies have exactly equal candidate estimates. Their later paths and total planning work can differ.

Against Phase 7 safe retry, the new cost policy has 56 new-split success wins and no losses; it also spends 5,208 additional planning steps. Its 692-call reduction across all new-split pairs must not be confused with the 360-call reduction among the 580 both-success pairs. The fixed eight schedules do not establish universal dominance under unseen faults; the prospective toy counterexample remains relevant.

## Model and integration findings that reporting must preserve

The independent reference-based label recount agrees with the saved parsed predictions. Invalid responses contribute invalid candidate-axis predictions, not `unknown` or `not_applicable`. Complete F facts are correct in only 1/48 new Luna responses, 0/48 new mini responses and 0/24 regression responses for either model. Improved aggregate labels therefore do not establish reliable complete execution evidence. T still makes label errors despite receiving exact facts.

The held-out integration grid has 672 conditions per pipeline. All-allow succeeds 416, all-block 288 and the aggregate solver gate 352. The gate-sensitive subset has 192 conditions per pipeline: all-allow wins 160 and all-block wins 32. Both directions are retained. On that subset Luna D/F/T succeeds 144/80/104; mini succeeds 152/120/128; solver succeeds 96. Thus the model label improvements do not imply improved integrated success, and the conservative aggregate solver gate is not a per-world success ceiling.

All nine pipelines succeed in the same 272 of 304 regression conditions. That split has no observed gate-sensitive conditions, so equal regression success cannot validate the model classifier. Direct enforcing-VM checks from the initial worlds find 48/84 new worlds and 4/38 regression worlds without a feasible alternative; 36 new worlds and zero regression worlds have no alternative at all. Alternative count and initial feasibility remain separate strata. Zero unauthorized effects is attributable to the trusted gateway, not proof of correct model authorization judgments.

## Review findings and verification status

The analysis initially read optional cached/reasoning token counts from flat usage keys, while provider records store them in nested details. This was reported before the analysis bundle was written. The implementation now reads `input_tokens_details.cached_tokens` and `output_tokens_details.reasoning_tokens`; input/output totals and conservative costs were unaffected.

The verifier's initial version reproduced requests, semantics, execution and analysis, but did not itself recompute reference coverage/novelty/provenance or settled dollar costs. The reviewer independently checked those artifacts and found them correct, and requested equivalent verifier assertions plus saved container-audit count validation before final release.

The verifier now contains those reference, provenance, settled-cost, reservation and saved container-audit assertions. The reviewer independently matched the saved analysis's 36 label/confusion metrics, all 24 paired family-bootstrap label intervals using a separate 10,000-draw seed-8008 calculation, 16 usage groups, 96 recovery-pair summaries, four fact-field summaries and 720 integration-stratum summaries. F-minus-D authorization intervals include zero for both models; the mini catalog interval also includes zero. Claims must retain the exploratory, twelve-family limitation.

A subsequent supplemental diagnostic issue was reported: a missing `model_gate` event produces `site=None`, but diagnostic version 1 assigns its missing F authorization the string `invalid`. All 18 affected conditions actually have `F_protocol_valid=True` and fail with `no_feasible_route`. This is diagnostic labeling, not a change to the four real protocol-invalid responses or the core model/integration results. Version 2 now uses null and `original_path_failure_without_model_gate`; all other version-1 fields remain unchanged in all 120 diagnostic rows. The original script and evidence remain available, and the verifier recomputes both versions. The report explicitly discloses the correction.

## Final report and handoff

The reviewer checked `docs/phase8_report.md`, `PHASE8.md`, the reproduction guide and both rendered figures. The report's label counts, unknown/NA counts, fact-field denominators, token means and cost increases, historical same-case comparisons, recovery tables and gate-sensitive counts match the independently checked evidence. Its 3,288 additional planning steps versus Phase 7 correctly refer to the 580 both-success pairs; the all-pair increase is 5,208. It distinguishes those populations rather than presenting one as the other.

The recovery chart initially called its 84-world denominator “tasks.” The corrected image was visually inspected and now says “Completed worlds / 84.” Both figures are legible and match the reported values. The report keeps the 12-family dependence, exploratory uncorrected intervals, synthetic finite-DSL scope, post-outcome diagnostic status and analysis-code timing explicit. It makes no universal policy-dominance, real-skill safety, model-necessity or new graph-benefit claim. It distinguishes conservative cross-world audit gates from current-world execution success and attributes enforced safety to the trusted gateway.

The final fresh focused invocation passed 81 tests in 3.07 seconds:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_analysis_v8.py tests/test_phase8_reference.py tests/test_protocol_v8.py tests/test_recovery_v8.py --basetemp work/phase8-outcome-review-tests -p no:cacheprovider
```

The review also inspected the parent's retained full-suite XML: the final file has 1,186 entries including subtests, zero failures/errors and four skips; the earlier long-path attempt with four failures remains preserved. The parent reports 1,032 passed tests plus 150 passed subtests after shortening the Windows scratch path. This review does not replace the separate comprehensive old-file and final release-hash verification.

All reviewer checks were offline. The reviewer stopped writing this document after this final handoff so the release manifest can include stable review bytes.

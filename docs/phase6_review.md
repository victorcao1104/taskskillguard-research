# Phase 6 independent review

Review date: 2026-10-16. The reviewer inspected the prospective design, decisions, implementation plan, reference semantics, production runtime, model protocol, campaign preparation, analysis, and release verifier. No held-out fixture, generator, or design was inspected before the parent's freeze announcement. This review used no API, credential, real Skill, network, or Git mutation. Only this document and `tests/test_phase6_review.py` were added by the reviewer.

## Pre-freeze findings and disposition

1. **P1, graph interface mismatch, repaired.** `runtime_v6.edges()` returned triples while `protocol_v6.payloads()` originally indexed dictionaries. Real parser graphs would fail request preparation even though the protocol's synthetic dictionary test passed. The parent added a triple adapter; the review test sends a graph from the actual parser through all protocol views and checks its public payload.
2. **P2, incomplete semantic comparison, repaired.** Differential equality originally omitted the effect trace and tested only original routes. An authorization-only trace mutation could therefore leave every equality flag true. The parent added normalized full traces and every route/world/site-intervention combination. Independent witnesses require both mutation detection and alternate-route coverage.
3. **P2, language validator disagreement, repaired.** Production accepted an `if` without `else`; the reference interpreter rejected it. The prospective language requires both. Production now rejects the malformed form; the review test checks both validators.
4. **P2, execution failure reporting, repaired.** Recovery comparisons indexed missing `result` objects directly, and summaries omitted recovered-stage denials, route bypass, ambiguous stops, initial catalog infeasibility, and search computation. The parent added safe failure handling and those counters. The review injects a runner error and verifies it remains in the denominator without aborting analysis.
5. **Graph expansion bound.** The first focused run observed the runtime author's graph-bound test failing, with 61 other tests passing. The runtime author subsequently added the finite expansion guard. This was an in-progress implementation issue, not a held-out repair.
6. **Protocol completeness, retained limitation.** The reviewer flagged the missing step-bound and explicit-key conflict rules in the system prompt; the parent had already completed the freeze by receipt of that note. The frozen prompt was retained. Independent post-freeze checks found no errors in all 94 original/alternative-world executions or all 159 original-site interventions, so these omitted rules do not affect this dataset's labels. The prompt is nevertheless not a complete specification of every supported edge case.

## Independent witnesses

Command: `.venv/Scripts/python.exe -m pytest tests/test_phase6_review.py --basetemp work/p6review -q`.

Pre-freeze result: **9 passed in 13.76 seconds**. These checks cover the actual parser-to-prompt interface, private-field exclusion, mandatory-else agreement, authorization-only mutation detection, alternate-route and intervention comparisons, ambiguous-outcome stopping and monotonic quota, runner-error denominators, durable dispatch/no-retry behavior, and exact budget-prefix inheritance with unknown reservations retained. Dispatch tests use only local fake invocation functions; budget tests write copied ledgers beneath the explicit pytest temporary directory.

The reference module imports no production semantics or model labels. Production parses source and ignores the reference AST, and model requests select public fields explicitly. Both recovery comparators receive the same public route catalog, grants, initial state, receipts, and charged-call quota. Search additionally computes dry simulations on copies and reports that computation. A model's necessity labels do not grant authority. Model denials can be bypassed through supplied alternative routes, which still require trusted grants; integrated success must therefore be interpreted alongside route-bypass and stage-failure counts.

The study tests finite synthetic semantics. Independent implementation and mutant rejection do not establish completeness of either interpreter or generalization to arbitrary Skills. Initial catalog infeasibility is relative to routes executed independently from the initial world, not a proof that every possible sequential composition is infeasible. No experiment result, CI result, or remote publication is asserted by this pre-freeze section.

## Frozen evidence review

After the parent's freeze announcement, the reviewer checked all 14 frozen hashes against current bytes; all matched. The held-out generator imports neither interpreter and contains no model/answer labels. Its source and reference AST are two representations of the same author-owned construction, so their equality is representation validation rather than independent author agreement. A coarse original-AST comparison that ignores site IDs, scalar literal content, variable names, and function names found no overlap between the 24 held-out cases and development programs. This supports new compositions within the language, not an external holdout or new-operator generalization.

The preserved first evaluation contains 374 comparisons over all routes, worlds, and site interventions; all 374 agree in files, emits, successful goal status, error presence, and full normalized effect trace. All 128 original static effect sites were recovered, with zero extras and 36 exact source/reference AST matches. The subsequent focused run across the four Phase 6 suites and independent review suite passed **71 tests in 16.32 seconds**. This is not a full historical regression result.

The held-out label distribution has substantial coverage limitations:

| Axis | yes | no | unknown |
| --- | ---: | ---: | ---: |
| Authorization | 70 | 0 | 18 |
| Implementation necessity | 68 | 0 | 20 |
| Bounded task necessity | 46 | 18 | 24 |

Thus held-out scores cannot estimate recognition of explicit authorization denials or unnecessary implementation effects. There is only one authorization `no` among the 40 development sites. Unknown behavior and bounded task alternatives remain testable. These limitations must remain visible alongside overall accuracy.

The first VM recovery factorial contains 2,304 completed conditions and zero runner errors or unauthorized effects. For all **576 individual search/checkpoint pairs**, authorized completion, charged calls, duplicate effects, and attempts are identical. Search adds 774 planner steps, 654 simulated effects, and 382 route estimates. The evidence therefore shows no recovery advantage from search on this grid and does show additional planning work. Across modes, 280 ambiguous stops have zero duplicate effects; an ambiguous physical goal match is not counted as authorized completion.

The trusted grant guard enforces zero unauthorized effects in every strategy. This is not evidence that model judgments improve security beyond that guard. The `route_bypass` counter records any alternative-route commit; it does not by itself prove that a model denial was bypassed. Recovered model denials must be read from stage traces. The independent review suite includes a witness for recovered denials and ambiguous-stop summary accounting.

Request preparation preserves 336 conditions (288 main and 48 repetitions), with a prospective conservative reservation upper bound of USD 2.093838075, below the USD 5 campaign limit. All public fields are equal across each case's views, all source strings equal their fixtures, no private top-level fields are sent, and all graph/padding local token lengths match. Two development cleanup cases have empty graphs, so their graph and shuffled views coincide. Across two models this produces **332 distinct requests for 336 conditions**; those four duplicated conditions are not independent model calls.

All 336 observations are completed and protocol-valid. The reviewer reparsed all observations from the 332 distinct raw records and obtained exact equality with stored parsed records. There are 332 distinct reservation IDs. The completed main campaign retains the exact inherited ledger prefix and has conservative cumulative upper total **USD 16.3384652**, an increment of USD 0.183014275 from USD 16.155450925. The cumulative cap remains USD 29.551575125. These are conservative ledger figures, not an invoice.

Both successful container batches exactly match their VM evidence: 2,304 recovery and 1,440 integrated conditions, with zero runner errors or unauthorized effects. The original recovery launch failed because the pinned image's inherited entrypoint ran a different worker. Its exit-1, empty stdout, and error stderr are preserved. The separate v2 adapter supplies `--entrypoint python3` and retains no network, read-only filesystem, dropped capabilities, non-root UID 65534, process/memory/CPU limits, and no host mounts. Its plan hashes the same frozen runtime and job records. The changed launch mechanism is an explicit amendment; it does not replace first semantic evidence.

Main model outcomes do not support a consistent graph advantage. On held-out sites, gpt-6-luna implementation correctness is 74/88 for table and 62/88 for graph; gpt-4.1-mini bounded task correctness is 49/88 for table and 55/88 for graph. These point comparisons must be read with family-level exploratory intervals and the negative-label coverage limits above. Only 10 of 24 three-response repetition groups are identical, despite all responses being protocol-valid.

The prospective description's "oracle upper bound" wording is not mathematically valid for the implemented gate. It permits only aggregate multi-world authorization `yes`, then executes only world zero. A model can permit an aggregate-unknown site that is trusted in world zero. Under transient faults, the conservative gold gate completes 28/36 cases per strategy, while model views complete 30–33/36 and the all-candidate reference completes 34/36. These must be named reference gates, not guaranteed upper bounds. Under normal execution all these groups complete 34/36. Checkpoint and search also tie in each integrated group.

After adding the stage-summary witness, the independent review suite passed **10 tests in 13.47 seconds**. Full historical regression, final release integrity, CI, and remote publication are the parent's remaining release checks; no result for those checks is asserted here.

## Separate targeted supplement

The parent registered `docs/phase6_challenge_design.md` after observing the main coverage gaps and recovery ties. This is a targeted exploratory mechanism study, not a replacement holdout or an independent population test. Its fixture remains sealed to the reviewer until its separate freeze.

The reviewer inspected the new `selection_v6.py` before that freeze. Both modes invoke the same frozen `_estimate` on all remaining routes, apply the same goal/error/remaining-quota feasibility predicate, and share the same VM, receipts, grants, and attempt limits. They differ only in catalog-order versus minimum-call selection. No private truth, reference AST, fixture identifier, or injected-fault-state dependency was found. The recorded `initial_feasible_catalog_count` refers to the first planning decision after original execution and its retry, not to the untouched initial world. Planning capability is equal per decision; total work may differ after actions cause different states or numbers of later decisions.

Before the supplemental freeze, the reviewer found that cached supplemental job rows were reused without comparing their request hashes. A local synthetic regression witness failed because a wrong cached hash was accepted. The parent added the same hash guard as the main runner, and the witness passed. The parent also made supplemental launch checks verify the linked main freeze and all current main frozen bytes. No frozen main code was changed.

After the separate freeze, all seven supplemental hashes matched. Independently recomputing every route/world/site-intervention comparison produced **134/134 full semantic matches**, with no reference execution errors. The 12 fixtures form six pairs whose source structures, routes, goals, and starting files agree after erasing opaque site IDs; exactly one grant differs within each pair. Three families place the cheaper route first and three place it second. There are 32 original static effect sites. Independent truth yields authorization yes 26/no 6, implementation necessity yes 20/no 12, and bounded task necessity yes 20/no 12. The supplement supplies the intended negative controls but contains no unknown labels and remains purposefully constructed.

The 1,152 supplemental recovery rows have zero runner errors, and the successful container batch exactly reproduces them. The equal-planning comparison exposes a genuine tradeoff under supplied grants and quota 16:

| Fault | Search-equal completions | First-feasible completions | Search-equal calls | First-feasible calls |
| --- | ---: | ---: | ---: | ---: |
| None | 12/12 | 12/12 | 39 | 47 |
| Transient before commit | 12/12 | 12/12 | 69 | 61 |
| Known after commit | 12/12 | 11/12 | 63 | 53 |
| Ambiguous after commit | 0/12 | 0/12 | 30 | 30 |

These are unconditional call totals. Costs conditioned on joint success must exclude the unmatched known-after success and retain the smaller denominator. Under transient and known-after faults, choices induce different later planning states: search-equal uses 98 planner steps versus 84 for first-feasible. The comparison therefore shares planning capabilities, but aggregate planning effort is not always identical. Tight-quota and undergrant cells tie. The evidence supports neither universal completion superiority nor universal cost savings.

The supplemental collection contains 96 distinct completed, protocol-valid requests. Each saved parsed observation exactly reproduces from its raw response. Its conservative reservation upper bound was USD 0.6125535, below USD 2. The latest ledger preserves the completed main ledger as an exact prefix, which itself preserves Phase 5. Latest cumulative upper exposure is **USD 16.39469075**, leaving USD 13.156884375 below the fixed cap. The full Phase 6 increment is USD 0.239239825. Main and supplement together contain 432 model conditions from 428 distinct requests; the cohorts must still be analyzed separately.

All 480 supplemental integrated conditions complete, with exact VM/container agreement and no runner errors. Among the 96 model-gated cases per mode/fault, normal execution costs 338 calls for search-equal versus 426 for first-feasible; transient faults reverse the direction to 587 versus 541. Thus the integrated data preserve the same cost tradeoff. Supplemental authorization recognizes the six negative controls well, but necessity reasoning remains weak: gpt-6-luna bounded task correctness is 0–2 of 32 sites across views. Accurate denial recognition and successful guarded execution must not be presented as accurate task-necessity reasoning.

Final focused verification after the supplemental runner repair: `.venv/Scripts/python.exe -m pytest tests/test_runtime_v6.py tests/test_truth_v6.py tests/test_protocol_v6.py tests/test_analysis_v6.py tests/test_selection_v6.py tests/test_phase6_review.py --basetemp work/p6review -q` — **95 passed in 20.13 seconds**. No unresolved implementation blocker was found in the reviewed study paths. The retained limitations and adverse results above are part of the audit, not defects to hide through retrospective fixture or prompt changes.

The reviewer also executed the read-only `verify(False)` release audit before creation of the final release hash manifest. It passed: **24,393 baseline files unchanged**, all main frozen bytes and the linked supplemental freeze valid, 432 model conditions reproduced from raw evidence, and all **5,376 runtime conditions** reproduced with exact VM/container equality and quota/authorization invariants. The audit reports the latest cumulative ledger upper bound above. `release_files=0` in this pre-manifest invocation is intentional; final release-hash validation, historical full-suite regression, remote SHA, and CI remain separate parent-owned publication checks.

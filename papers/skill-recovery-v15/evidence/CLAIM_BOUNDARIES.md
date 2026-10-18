# Claim boundaries for the v15 manuscript

Frozen evidence commit: `37e33664ab0626446e8ed1cfcd0304368d041aaa`.
This file records implementation-grounded limits on manuscript claims. The new paper does not replace the old paper or any experimental outcome. `prepare_evidence.py` regenerates the adjacent numeric extract and input-hash manifest without API calls or study writes.

## What the evidence supports

- A mechanism study of conditional recovery in an authored, bounded simulator: whether useful computation remains, which evidence about prior effects is available, and which work the trusted executor performs determine the observed outcomes.
- A causal explanation for seven selected, previously accepted v14 failures. Neutralizing task-irrelevant dependency/conflict lookups repairs 6/7 and 5/7 separately, and 7/7 together. All seven remain failures with an 80,000-step cap; adding analogous constraints to correct reference code induces seven failures. These are interventions on selected failures, not an estimate of error prevalence.
- With intact computation under the tested gate, Full completes 16/16 templates in each model condition with zero API requests. Source damage removes any general advantage over repair. The source-free replan control is measured once per model on 16 templates, not five independent times.
- State evidence, a remaining-operation plan, and automatic execution have different observed effects. The corrected A–D comparison does not establish monotonic improvement from richer information. D's reliable execution has a large advantage over model-written execution in this restricted interface.
- Finite random and generic surface-transformation tests miss some permitted semantic boundaries. The exploratory semantic supplement demonstrates this for co-designed mutants and test cases, with explicit final-input overlap and no general superiority claim.

## Trusted runtime is stronger than an offline scorer

`rm15/recovery.py:support()` calls `oracle_value(task, current_input)` at runtime, compares the saved result to that expected result, and classifies each existing artifact using expected artifact content. `rm15/runtime.py:Machine.call('valid')` also compares its argument to the native task oracle at runtime. `saved()` invokes the oracle to collect cache-reading diagnostics. The oracle is therefore not used only as hidden offline ground truth.

The fixed `compute()` implementation executes the authored bounded solver. It is distinct from the native oracle implementation, but both are authored by the benchmark team. Native oracle work is not counted as interpreter logical steps. Some checker time is separately accumulated, but not all native support/diagnostic work is fully isolated in those counters. Do not claim complete end-to-end computational cost accounting or a deployment-ready state verifier for arbitrary tasks. Model waiting time is not total system elapsed time.

The trusted task, grants, history, cache labels, receipt/status model, runtime gateway, task oracle and fixed solver are assumptions of the simulation. The oracle may need the entire current input to judge whether a cache can be reused. Thus avoiding a bounded `compute()` invocation does not establish that no equivalent computation occurs anywhere in the trusted system.

## D is executor delegation, not improved model computation

In both campaign evaluators, only a parsed `status='candidate'` invokes `run_program()`. A model's stop, clarification, invalid result or API/protocol failure remains a recorded outcome. Once a state-D candidate is admitted, `automatic()` governs cache reuse, computing if needed, artifact writing, receipt resolution, remaining events and cleanup. With the fixed computation installed, candidate compute/effects text is not executed in D. D therefore tests reliable delegated execution after a protocol-valid candidate; it does not demonstrate that generated effects code is correct or that the model learned stronger state reasoning.

All source-comparison methods also use the same automatic effect executor; their generated/transformed computation remains relevant because no fixed compute implementation is installed for source conditions. The source comparison isolates a narrower computation-recovery question under strong common effect support, not unconstrained end-to-end agent repair.

## Operation uniqueness includes repeated writes

`Machine.call()` counts a write to an already existing path as a duplicate, even if the value is identical. It also counts repeated named send/service events. These attempts are normally stopped by the common gateway. Do not describe every `DUPLICATE_EFFECT` as a duplicate email, payment or external service commit. `duplicates_executed` counts repeated named events in the final world, whereas duplicate-attempt counts also include writes.

The corrected Luna-B final-failed-candidate decomposition contains ten duplicate failures: nine writes and one service preparation. Mini-B has 47 failed episodes, including 23 missing-variable and ten unsupported-call-target failures. Interface/code execution errors are an important part of the observed differences. A separate metric in the compact episode tables flags whether any candidate validation or final execution exhibited a problem; it is not the same denominator as the last failed candidate's cause.

The old field `wrong_stop_feasible` includes all interpreter halts on feasible tasks. It is not a count of the model deliberately refusing to proceed. Use the explicit failure decomposition for declared stop, interface/execution failure, and API/output-protocol failure. `disclosure_executed` in some diagnostic contexts also reflects retained historical harm; do not infer that every such flag is a new disclosure caused by recovery.

## Source comparison and its remaining confound

Intact and partially damaged source use one private-token read followed by an `if secret == 'A'` gate with no `else`. The deterministic transformation removes the read and unwraps the body. Destroyed, absent and unrelated source conditions are controlled missing-computation conditions. The study does not cover general malicious branching, arbitrary control-flow repair or the diversity of real Skill attacks.

Every episode has at most two candidate positions. Full always spends its first position on deterministic transformation, leaving at most one model request; repair and replan can use both positions for model requests. Under damaged or absent computation, Full can consume a position on a predictably unhelpful candidate. Equal candidate positions are not equal opportunities for model generation. Do not attribute all source-condition differences to source information alone or claim that Full generally beats ordinary repair/replanning.

The specialist solver is 16/16 on final and scale tests. Its development/maintenance cost is not in online API cost. It remains an important strong control; excluding that cost does not justify removing the control.

## Original versus corrected state experiment

The original 512 state episodes offered one fixed computation tool but did not prevent effects code from reading the current input and recomputing. The preserved disclosure reports eight accepted programs and 35 saved attempts with direct input reads. These results stay visible and separate.

The separately frozen strict supplement forbids current-input reads from effects code, hides fixed-solver locals, and requires a fixed-compute invocation for feasible completion when no valid initial cache exists. Valid-cache reuse is permitted. The supplied computation algorithm is common across A–D; the tests do not claim equal quantities of executed bounded computation because reuse is deliberately allowed.

The environment-recovered strict dataset contains 512 episodes. Exactly 372 episodes were selected for reacquisition because their first acquisition had transport errors; 140 unaffected episodes were preserved, including model errors and API refusals. The 744 original transport-error requests and their reservations were retained. The recovery-selection rule was frozen before obtaining replacement answers. Do not pool original and corrected interfaces or initial/recovered acquisition as independent repeated trials. Changes between original and strict results combine the interface intervention and new model draws, so the change is not a pure paired estimate of the interface effect.

A separately frozen adapter catches one candidate-induced uncaught type-error class and records the existing `MALFORMED_PROGRAM` outcome. The original frozen runtime remains unchanged. This is an implementation repair disclosed in provenance, not a successful candidate repair.

## Counts and denominators

- Original main grid: 864 episodes = 352 source + 512 original state. Its 562 accepted, final-correct outcomes comprise 483 feasible safe completions and 79 correct boundary stops. Do not call all 562 completed tasks.
- Strict state grid: 512 episodes = two models × four support levels × 16 templates × four histories. Per model/support cell, 48 histories are feasible and 16 are unknown-effect/no-query boundaries. Strict totals are 265 feasible completions + 82 correct stops = 347 correct outcomes.
- Source cells contain 16 templates. Replan is one shared source-free set per model. Reporting that same result alongside five source levels does not create 80 replan observations.
- A failed recovery attempt and an unsafe event actually executed are different outcomes. The common gateway can block an erroneous attempt. The protection module can reduce attempts while the gateway supplies execution prevention.
- Protection ablations contain 224 history/physical-state cases per setting, not 224 independent templates. Full yields 160 safe completions and 64 correct stops; no cache check yields 128 and 64; no receipt handling yields 88 and zero. The latter has 112 cases with duplicate attempts and zero executed duplicate events.
- No-cache-check selects an invalid cache in 32 cases. Those cases halt as `MALFORMED_PROGRAM`; they are not 32 completed wrong-content results. Wrong-cache reads, invalid-cache selection and wrong final content are separate measures.
- Boundary interventions contain 128 cases: 32 ordinary completions and 96 correct stops for missing permission, inconsistent artifact-count requirements or retained prior harm. Unknown/no-query stopping is evaluated in the state/protection designs, not an additional intervention hidden inside this 128-case table.
- The fault grid has 176 schedule/input cases per retry setting, including 32 no-fault reference cases. At zero retries those 32 complete; with at most three retries all 176 complete. It is inaccurate to call all 176 fault-injected cases. Thirty-two additional insufficient-call-budget cases stop with `CALL_BUDGET`; these are resource failures, not successful boundary-stop proofs of task unsatisfiability.

## Validation scope

The main computation-validation study has 96 constructed variants: 77 with observed counterexamples, nine structurally inapplicable identity transformations, and ten with no observed counterexample in the finite corpus. “No observed counterexample” does not prove equivalence. Retain all 96 in the primary denominator. The 77-member denominator is defined using the union of validation and final tests and is therefore a conditional diagnostic, not an independently known defect population.

Each strategy uses four tests. Random, larger-input and generic transformation tests detect 67/96, 66/96 and 58/96 respectively, leaving 8/29, 11/30 and 17/38 accepted variants that fail on the independent final inputs. Generic transformations address order, labels and decoys and share a base input; random uses four separately generated inputs. Equal count does not equal input diversity or logical work. Zero false rejections applies only to 16 authored correct references on these tests.

The later semantic supplement is exploratory and co-designed after the main comparison. Its 48 constructed mutants have observed counterexamples. Semantic challenges detect 48/48 versus random 23/48. All differential benefit is in anticipated assumptions (32/32 versus 7/32); the semantic-relation stratum ties at 16/16. It is not blinded, independently authored or a natural-model-error population.

Among the 25 random-accepted semantic mutants, one fails on fresh random/scale finals and 25 fail on parameterized semantic finals. Ten parameterized final input cases exactly repeat validation inputs (often empty cases). The 10 are input-case overlaps, not necessarily ten overlapping mutant observations. Do not call all semantic final tests independent. Semantic cases are smaller, and native oracle computation is not charged in logical-step counters.

All 562 accepted original-main outcomes pass ordinary fresh-input evaluation; two Luna triangle-counting repairs fail the scale phase by exceeding the step budget. Treat these as resource failures on different scale inputs, not as evidence of semantic mismatch or broad program correctness. API refusals, incomplete outputs, transport failures and uncertain billing are acquisition/protocol/accounting categories, not semantic-program counterexamples.

## Cost and saved verification

The inherited ledger is not reset. New settled-usage upper estimates are $1.483756725; unresolved reservations total $4.853928375. Their sum is $6.337685100 of new conservative exposure, with $9.430934925 remaining under the inherited cap. There are 746 unsettled new reservations; the 744 transport-error reservations remain reserved. This is a conservative ledger, not a provider invoice or a statement of actual charges. The earlier main-replay report has an earlier ledger snapshot and must not override the final integrity totals.

The saved verification reports document 24,042 original-main and 20,512 strict worlds, totaling 44,554, with zero replay network requests. The saved test log records 55 passed tests and 1,072 passed subtests. The manuscript evidence script checks these reports and hashes but does not itself rerun the interpreter or tests. It reaggregates 864/512 compact episode rows, detailed causal and diagnostic records, 5,120 individual validation trials, and the cost ledger. It verifies frozen inputs/source hashes and the Git baseline for all studies and pre-existing paper directories, without rereading every raw API response.

## Statistical and external-validity limits

The analysis unit is 16 related author-constructed templates across four structures. Secrets, parameter changes, physical committed/uncommitted worlds and repeated validation inputs are not independent task samples. The paired bootstrap uses 10,000 resamples of the 16 template differences with seed 20261018; it reports conditional descriptive intervals, not a population guarantee for real Skills. State contrasts combine feasible completion and correct boundary stopping; they are not feasible-only rates. Sign-flip values are descriptive and not multiplicity-adjusted confirmatory tests.

There is one recovery episode per condition, with up to two candidate positions; that is not necessarily one API request. Two pilot templates also occur in the primary set. The 14-template exclusion is exploratory. The original/strict interfaces and two models differ in restricted-language adherence as well as possible reasoning behavior. No representative real Skills, independent human annotations, independent task authorship, real service deployment, arbitrary network faults or formal correctness/security proof are supplied. The work does not establish component novelty merely by composing established techniques.

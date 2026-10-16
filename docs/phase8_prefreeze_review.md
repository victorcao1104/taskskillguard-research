# Phase 8 independent pre-acquisition review

Date: 2026-10-16. Scope: prospective design, protocol, recovery adapter, acquisition, all-world job construction and restricted-container harness. No Phase 8 held-out fixture, fixture generator or model outcome was read. No provider request, network operation or Git operation was performed. The reviewer changed only this review document; test outputs used temporary locations under `work/`.

**Disposition:** no open blocking defect was found in the reviewed implementation after the corrections below. This supports proceeding to the declared production freeze and subsequent independent fixture/differential checks. It does not certify unseen data, an uncomputed campaign reservation total, actual Docker execution or model outcomes.

## Findings and corrections

| Finding | Why it mattered | Verified disposition |
| --- | --- | --- |
| F originally inherited “Return one judgment per candidate ID” while requesting facts only. | Conflicting output instructions would confound D/F comparison. | `protocol_v8.system` removes that output instruction for F, retains the semantic rules, and appends the facts-only instruction. |
| T originally inherited “Public source, grants and goal are the only evidence.” | This conflicted with the trusted execution facts supplied to T. | The T system prompt explicitly permits trusted execution facts. |
| F originally accepted `world: 0.0`. | JSON Schema accepts numerically integral floats as integers, and Python equates `0.0` and `0`; exact world-index types were not enforced. | The parser explicitly requires `type(index) is int`. A regression test covers `0.0`; booleans are also rejected. |
| F required ordered worlds without explicitly requesting that ordering. | A complete, correct but reordered response could fail an unstated protocol condition. | The F prompt now requires ascending world-index order. |
| The original freeze pattern omitted inherited production dependencies. | A changed runtime, solver, client, budget or shared dispatch helper could evade the pre-request freeze check. | The freeze now includes all existing `src/tsg/*.py` and production `scripts/*.py`, alongside Phase 8 tests/design, the prospective analysis plan and requirements. The designated analysis implementation/test are explicitly deferred to the final release freeze. |
| `exact_facts` assumes at least one candidate. | A legal no-effect toy program raises `IndexError` at `rows[0]`. | This remains an explicit campaign boundary: acquisition now rejects an empty candidate set with `CAMPAIGN_REQUIRES_CANDIDATES` before requests. General empty-candidate support is outside this campaign. |

## Protocol and comparison assessment

The shared validator rejects duplicate JSON keys, nonfinite numbers, non-object roots, missing/extra schema fields, invalid response envelopes and incomplete responses. F adds exact world and candidate coverage, unique candidates, sorted unique route arrays, integer-only indices and route bounds. Invalid records expose an empty `by_id`, allowing downstream code to block the original route without salvaging a partial model response. D and T use the same typed direct-label schema and exact candidate coverage.

The D and F public payloads were equal byte for byte on a hand-authored toy. Both use the same source-derived candidates and public source/routes/worlds/goal/catalog status. D retains the Phase 7 B1 instructions; F changes the requested representation and uses deterministic aggregation. All arms receive a 4,000-token output cap in acquisition. This is a comparison of output representations and aggregation responsibilities, not a claim of identical output tasks. T additionally receives exact execution facts and must remain an attribution control; its tool execution count is recorded.

The reducer preserves inactive versus failed-baseline behavior, open-catalog unknown, and mixed-world unknown. Global facts are compared once per world; site facts are compared per site/world. Wrong facts are never corrected before aggregation or scoring.

**Semantic error is distinct from protocol failure.** A structurally valid response may claim an inactive site is unauthorized, give an inactive site avoiding routes, or name an in-range avoiding route absent from its claimed legal set. These are contradictory or false executable facts, not malformed JSON/coverage. Independent probes confirmed that they remain protocol-valid; exact fact scoring records their errors, and aggregation uses the submitted facts. This preserves the intended distinction rather than improving apparent accuracy through rejection or repair.

## Recovery assessment

`recovery_v8._estimate` creates a fault-free VM from copied observed files/grants, emits, receipts and signatures. It applies the original-route model gate. It does not receive the schedule, future dispatch count or fault name. The toy state-isolation test verifies that probing leaves the actual machine unchanged.

At a shared observed state, both policies enumerate the same remaining alternatives and include the current route only after `transient_before` or `known_after`. They use identical feasibility, remaining-quota and gate checks. The only selection difference is feasible-current-route priority versus minimum remaining charged calls, with route-index ties. The implementation records every simulated route and its planning work; total planning work need not match after policies reach different states.

The original is attempted first; at most four actual attempts run. Permanent failures retire routes. Unknown-commit and actual quota-exhaustion errors stop without planning. Receipts and exact grants remain shared across attempts, including alternatives. Tests cover denied grants, receipt-signature conflicts, zero-cost known-commit retry at exhausted quota, alternative comparison, repeated transient faults, gate-blocked retry simulation and a toy future-fault schedule under which cost selection loses. Cost savings must therefore be reported alongside success and both-success denominators.

## Acquisition and isolation assessment

The acquisition code copies and verifies the complete Phase 7 ledger prefix, uses the inherited locked durable budget, preserves unknown reservations, fixes four workers and zero automatic retries, and checks the sum of exact request reservations against both USD 4 and the cumulative remaining allowance. Request hashes include schema/system/payload/replicate; the complete 480-job manifest and job bytes are immutable. Request intent precedes dispatch; an orphan intent does not authorize another provider call. Pricing constants were inspected as inherited code, not independently revalidated over the network.

The all-world harness constructs the stated three-policy, two-quota, eight-fault recovery grid. Integration uses six model/view pipelines plus solver/all-allow/all-block, two new policies, four faults and quota 16. A two-world toy produced 96 recovery and 144 integration conditions with unique IDs and all nine pipelines. Invalid F observations produced empty original gates. Public execution inputs excluded private reference programs and labels.

The container command pins its image, disables networking, makes the root filesystem read-only, drops all capabilities, enables no-new-privileges, runs as UID/GID 65534, and limits processes, memory, CPU and temporary storage. It has no host mounts. Modules load in dependency order; 48 toy conditions produced exact agreement between direct execution and the isolated Python worker. This tested worker packaging, not the Docker isolation boundary itself. A mocked timeout preserved partial stdout/stderr and failure status; rerunning refused to launch the failed batch again. Actual container runs and full VM/container equality remain required campaign evidence.

The prospective analysis plan explicitly retains invalid responses in denominators, separates held-out and regression results, uses paired family bootstrap rather than treating candidate/world observations as independent, reports recovery success losses and both-success cost, and defines integration sensitivity using paired all-allow/all-block outcomes. It distinguishes aggregate authorization gates from per-world execution-success ceilings. These specifications are appropriate; the later analysis implementation and reported values still require verification against them.

## Verification evidence

Final fresh test invocation:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_protocol_v8.py tests/test_recovery_v8.py tests/test_budget_v4.py tests/test_phase7_budget_locked.py tests/test_phase7_review.py --basetemp work/phase8-review-tests -p no:cacheprovider
89 passed in 0.95s
```

Additional independent in-memory/toy probes verified seven strict index/type rejections, D/F payload equality, corrected prompt instructions, semantic-error preservation, all-world/pipeline counts, original-gate handling, private-metadata exclusion, 48 worker/VM result matches, restriction flags and no-relaunch timeout behavior. All provider tests used mocks.

Reviewed source SHA-256 values at the final pass:

| File | SHA-256 |
| --- | --- |
| `src/tsg/protocol_v8.py` | `a0d02544323d4d3c09d5a9c330bbfcca110160fbaeaadc3b846ab7cf954fcedd` |
| `src/tsg/recovery_v8.py` | `3cbde81a0406a2e26fd53e9220e59ea3b51bb1031ae895bef1c53ee07465c9b4` |
| `scripts/phase8_common.py` | `e3c156278cecfa16629d35ea416d784a4e4c54359cd14fa05da5e68e432f29e6` |
| `scripts/run_phase8.py` | `dce56802fd4372c8f08fdcf26e6d2ce677354df21c333281b4349e87733201d9` |
| `scripts/experiment_phase8.py` | `240640e96582172521b4781585228cee82d907b1a54661f807e2f46ac70e0aaa` |
| `scripts/container_phase8.py` | `6153d3983605b79d24e889013c44bfcf734d7b3b07bb952ceefa9093f1a6fcf3` |

The production/data freezes must occur after relevant authors stop writing. Fixture coverage/novelty, full differential truth, the actual reservation bound, observed billing, full container equality, missing-response denominators and final statistical/reporting claims require the subsequent campaign checks and are not inferred from this review.

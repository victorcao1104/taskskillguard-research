# Phase 9 independent prefreeze review

Date: 2026-10-16. Disposition: ready for production freeze within the reviewed scope. No important findings remain open. This review does not establish heldout performance or replace the final independent replay and release verification.

## Boundary and scope

Reviewed the prospective design, implementation plan, analysis contract, protocol/recovery descriptions, `protocol_v9.py`, `query_v9.py`, `observation_v9.py`, `recovery_v9.py`, acquisition/experiment/container helpers, and their production toy tests. Relevant frozen Phase 6–8 runtime, reducer, API and budget implementations were read to check inherited semantics. Existing tracked files were not edited by this reviewer; this document is the reviewer's only repository edit.

The reviewer did not open `build_phase9_heldout.py`, `test_reference_v9.py`, `work/p9ref`, `data/phase9`, or reference/model/runtime outcome artifacts. No API, network, Git or container execution was performed. Additional executions used hand-written toy workflows, a temporary freeze directory, or in-memory replacements for experiment inputs and artifact writes.

## Findings resolved before freeze

### 1. Incomplete query traces crossed the runtime authorization boundary

Severity: P2. Original location: `src/tsg/query_v9.py:224-229`; corrected boundary: `src/tsg/query_v9.py:224-232`.

The paid original query exported positive authorization and inactivity facts even when its interpreter result contained an execution error. This disagreed with the conservative incomplete-audit handling in `src/tsg/recovery_v9.py:140-142`. A toy original containing an authorized write followed by 101 assignments produced `step_limit` but exported a positive authorization row. With preflight disabled, passing that row allowed the write; the runtime's own audit kept the site unresolved and prevented the write. Gateway grants still prevented unauthorized commits, and the registered integrated grid's preflight masked this particular side effect, but the handoff was an unsound completeness assertion.

Resolution: query handoff now includes a world only when its paid original query completed without an execution error. Diagnostic causal labels retain the frozen committed-trace semantics. Error details remain in the paid query observations and trace. The new incomplete-baseline test and the reviewer's reproduction confirm an empty handoff, unresolved runtime gate, no committed write, and zero free audit calls.

### 2. Data freeze did not enforce the existing production freeze

Severity: P2. Corrected location: `scripts/phase9_common.py:28-30`.

The initial implementation could create a data freeze from changed production files without first checking the production freeze, while acquisition verified only the resulting data freeze. That left the intended production-before-heldout chronology dependent on an external manual check.

Resolution: `freeze('data')` now verifies the production freeze first. A temporary-directory reproduction froze a toy module, changed it, and confirmed `FROZEN_CHANGED:src/tsg/toy.py` before any data-freeze artifact was created. Protocol and recovery descriptions were also added to the frozen inventory.

### 3. Experiment proof checks omitted proved unknowns and acquired orders

Severity: P2 verification gap; no incorrect reducer output was demonstrated. Corrected locations: `scripts/experiment_phase9.py:60-77` and `scripts/experiment_phase9.py:81-87`.

The initial prefix check skipped every displayed `unknown`, including a claim that intrinsic unknown was already proved. It checked only catalog-order prefixes and used the production solver as its comparison. Acquired, heuristic and random order results were stored without the same proof assertion.

Resolution: every evaluated pipeline, repeat and budget now checks every proved label, including unknown, against the independent reference interpreter. Catalog-prefix checks use the same distinction. The reviewer ran the updated experiment entirely on a toy case with in-memory outputs, then injected a falsely proved unknown and confirmed rejection by `UNSOUND_QUERY_PROOF`.

## Reviewed properties

- Factorial records preserve the model's labels and reduce the same proposed facts offline. Wrong but well-formed facts are retained; inconsistent duplicate globals and malformed coverage fail explicitly. Exact-tool arms are documented as additional computation rather than equal-capability controls.
- Q0/Q1 expose identical public source information; Q1's extra edges are a deterministic representation. Ranking receives no execution answers. Model, heuristic and seeded-random orders use the same catalog and paid prefix budgets. Invalid rankings receive neither queries nor a heuristic fallback. The incremental possibility sets conservatively preserve budget uncertainty and distinguish proved intrinsic unknown.
- The controller's initial decisions use public hypotheses and charged observations. Actual world selection is confined to environment initialization. Hidden-world and future-fault tests cover the relevant decision boundary. Conditional safe authorized/inactive mixtures preserve global typed unknown rather than rewriting it to yes.
- Planning audits and route probes share the counted budget. Structural admission bounds match the frozen 100-entered-step limit; no extra full solve was found outside the recorded interpreter accounting. Cache keys include changed state, grants, receipts, signatures, gate, goal and remaining quota. Receipt reuse and read returns remain consistent with the frozen gateway.
- Preflight checks receipt/signature behavior before the first effect. All recovery policies see the same eligible candidates and budget before applying their ranking rule. Ambiguous commits stop before further planning or belief updates; the four-attempt limit and quota/grant invariants are retained.
- Acquisition inherits the prior ledger and conservative prices, uses durable dispatch markers, fixes request identity and replicate identity, and rejects a campaign exceeding its reservation ceiling before dispatch. No retry path was introduced. The inherited ledger's one-process ownership assumption remains applicable.
- The container command is pinned, unprivileged, read-only and disconnected, with no host mounts. Launch intents and output artifacts support deterministic replay. Actual container replay belongs to the later verification stage.

## Verification evidence and limits

The focused command `pytest tests/test_protocol_v9.py tests/test_query_v9.py tests/test_recovery_v9.py tests/test_acquisition_v9.py tests/test_experiment_v9.py -q` passed 129 tests after the incomplete-query repair. Subsequent experiment proof-check changes were exercised directly on the independent-truth toy workflow: 12 evaluated conditions and three catalog prefixes passed, and an injected false proved unknown failed as intended. The freeze continuity and incomplete-query boundary were additionally reproduced independently without study data.

Planning units count VM simulations and entered steps, not all host CPU work; parsing, cache-key construction and observation-separation search are excluded as documented. Observability, finite hypothesis coverage, trusted local-query provenance, modeled latency and risk weights remain synthetic assumptions. The review found no basis for claims beyond those bounds. Final analysis must retain invalid responses, losses and null outcomes, and final release verification must establish artifact integrity, independent heldout agreement, container agreement and budget reconciliation. Current provider prices were not independently checked in this no-network review.

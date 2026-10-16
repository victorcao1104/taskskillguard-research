# Phase 10 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the root orchestration and dispatching-parallel-agents for independent versioned modules and reference authorship. User has explicitly authorized direct execution of the four proposed priorities.

**Goal:** Measure goal-relevant observations, short query protocols, realized adaptive stopping and legal recovery under shifted faults.

**Architecture:** New v10 modules compose the frozen v6-v9 semantic and receipt engines. Separate reference authorship, acquisition, execution and analysis; preserve all old artifacts.

**Tech Stack:** Existing Python 3.12 environment, pytest, locked API client/budget, Docker, GitHub Actions.

**Spec:** docs/phase10_design.md

## Global Constraints
- All 30,435 baseline tracked files remain byte-identical; verify the actual inventory count.
- Only synthetic fixtures and previously authorized GPT-6 Luna / GPT-4.1 mini APIs.
- Cumulative cap $29.551575125; Phase 10 additional cap $6, inherited remaining $12.168282575.
- Never read or expose credential text. No automatic API retries or outcome-based repair.
- New result files are immutable. All production changes precede formal heldout exposure.

## Review Focus
- Goal observations must not access actual-world identity or future faults.
- Failed/incomplete base queries must not produce positive authorization evidence.
- Adaptive stop checks must be free of hidden interpreter calls; consumed queries run once.
- Dynamic request restart must not duplicate paid dispatch, reservation or evidence.
- Same-budget comparisons must preserve alternative planner capabilities and all invalid responses.

## Task 1: archive and prospective specification
- [x] Verify clean Phase 9 HEAD and private origin; create and verify remote archive tag.
- [x] Record architecture, interface signatures, arms, budgets and outcomes in the spec.
- [ ] Save immutable baseline inventory and archive evidence; record locked-budget inheritance.

## Task 2: goal-aware runtime
Files: src/tsg/observation_v10.py, src/tsg/recovery_v10.py, tests/test_recovery_v10.py, docs/phase10_recovery.md.
Consumes frozen v6/v7/v9 engine interfaces; produces `execute(case, ..., observation_mode, risk_weights)` as specified.
- [ ] Failing tests: goal-only uncertainty, unavailable observations, multi-observation separation, no actual-world dependence, shared planning budget, unknown commit, weighted policies and operation faults.
- [ ] Implement and run focused tests including old compatibility; document exact new semantics.

## Task 3: short protocol and incremental queries
Files: src/tsg/query_v10.py, tests/test_query_v10.py, docs/phase10_protocol.md.
Produces QuerySession, selection payload/schema/parser, evidence-only stopping; signatures in spec.
- [ ] Failing tests: duplicate/outside/empty/over-limit IDs, no prefix reruns, failed baseline handoff, intrinsic unknown, all stop modes, representation equality.
- [ ] Implement and verify independently against frozen full-query results on toy inputs.

## Task 4: independent new reference
Files: scripts/build_phase10_heldout.py, tests/test_reference_v10.py, docs/phase10_reference.md, results/phase10/reference/first-pass/*.
- [ ] Author 24 cases/12 families without reading v10 production modules; test reference truth and typed distribution.
- [ ] Save first-pass generator/data hashes; materialize data/phase10/heldout.jsonl only after production freeze.

## Task 5: orchestration and freeze
Files: scripts/phase10_common.py, run_phase10.py, experiment_phase10.py, container_phase10.py, tests/test_acquisition_v10.py, test_experiment_v10.py.
- [ ] Test inherited ledger cap/prefix, duplicate dispatch safety, requested protocol limits and matched runtime grids.
- [ ] Review complete production interfaces; freeze production, materialize reference, freeze data.
- [ ] Acquire every registered stream within the campaign bound; retain every raw response and failure.
- [ ] Compute all proof/control grids and interface/integrated/recovery conditions, then container replay.

## Task 6: analysis, independent review, publication
Files: scripts/analyze_phase10.py, plot_phase10.py, verify_phase10.py; tests/test_analysis_v10.py; docs/phase10_report.md, phase10_reproduction.md, PHASE10.md; .github/workflows/phase10-tests.yml.
- [ ] Family-paired estimates, proof/validity/error attribution, actual stop savings and recovery tradeoffs; preserve negatives.
- [ ] Independent review of traces, frozen chronology, API accounting and conclusions.
- [ ] Run full tests, reproduce results and analysis, verify baseline hashes, save release manifest.
- [ ] Publish study-v10 and main to private origin, verify exact-head CI and report costs/results.

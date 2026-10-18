# v15 Recovery Mechanisms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run the user-specified synthetic mechanism-isolation experiments without changing old evidence.
**Architecture:** Preserve gr14 as a read-only interpreter/reference for exact old-case diagnosis. New rm15 modules separate task truth, bounded execution, support, acquisition and analysis.
**Tech Stack:** Python 3.12, pytest, jsonschema, inherited budgeted provider, local simulated operations.
**Spec:** design.md.

## Global constraints

Synthetic only; original two models; inherited $15.768620025 maximum remaining exposure; no old files changed; fixed grants; all raw errors retained. Native execution continues under the user's explicit instruction. Design and protocol freeze before main results, not after.

## Tasks

- [x] 1. Exact v14 diagnostic replay and source-span constraint intervention. Files causal_v14.py, tests/test_causal.py. Test preservation of non-target text, inactive-only edits, replay and budget-factor independence. Save original, treatment and inverse-injection outcomes, full traces and hashes.
- [x] 2. New task suite and execution adapter. Files rm15/tasks.py, solvers.py, runtime.py, tests/test_tasks.py. Sixteen templates with independent oracle versus candidate code; four structures, scale separated; unsafe code never host-executed. Test valid and invalid examples, mutable aliases, partial state and disclosure/permission boundaries.
- [x] 3. Source-integrity and state-support protocols. Files rm15/support.py, protocol.py, campaign.py. Test source-only treatment changes, identical source-blind baseline, B informational/C decision/D execution distinction, identical computation in A–D, fault locations and paired unknown observation.
- [x] 4. Validation study and stopping grid. Files validation_study.py, boundaries.py. Freeze new mutant families and inputs, run equal count/cost tests and individual transformations. Test incorrect stops separately from API/syntax errors and actual infeasibility.
- [x] 5. Budget inheritance and pilot. File rm15/provider.py. Verify ledger prefix, whole-grid worst-case admission, exact caching, no duplicate dispatch and authorized model list. Pilot separate from final.
- [x] 6. Freeze, acquire and replay formal campaigns. Save source/input hashes and exact jobs before live work. Run strong controls and both model grids, retain all failures, cached replay all selected programs. Never use final counterexamples to repair main results.
- [ ] 7. Analyze, review and publish. Files analyze.py, REPORT_ZH.md, README.md, provenance/review.md. Compare paired strata; include cost curves and power limits; fresh final review; verify old evidence unchanged; publish new private version.

## Review focus

1. Source variants accidentally change history or final input: hash the non-source fields and test equality.
2. B/C quietly execute effects: assert before/after world unchanged when generating support.
3. Hidden committed state leaks into prompts: strip internal service state; only authorized query observes it.
4. Interventions remove active task constraints: reject edits when the trusted goal enables the relation.
5. Final inputs influence repair: freeze final data and ensure payloads use construction inputs only.


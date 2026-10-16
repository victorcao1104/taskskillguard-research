# Phase 8 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or scoped parallel tasks. Implement and verify each owned component; do not edit prior files.

**Goal:** Isolate fact inference from aggregation and safe retry eligibility from economic selection.

**Architecture:** Independent reference fixtures and a new recovery adapter over frozen v6/v7; a factorized evidence protocol with deterministic aggregation; immutable acquisition and paired all-world evaluation.

**Tech Stack:** Python 3.12, pytest, existing API client and locked budget ledger, no-network Docker, GitHub Actions.

**Spec:** docs/phase8_design.md

## Global Constraints

- New files only; baseline commit 0f1aefcd6ed7986b0c4035be36f60967efab4a1c.
- Pure synthetic; no human annotation; gpt-6-luna/gpt-4.1-mini only.
- Campaign reservations <=$4; cumulative upper <=$29.551575125.
- No API retries, no outcome-based tuning, preserve all failed evidence.

## Review Focus

- Candidate/world coverage, duplicated indices and integer/bool confusion must fail strictly.
- Aggregation must distinguish inactive, baseline failure, open catalog and mixed worlds.
- Retry simulations must honor original model gate and preserved receipts, without future faults.
- Both recovery comparisons must expose simulated route counts/planning steps and both-success costs.
- No-alternative, missing-grant, all-block and all-world cases must reveal integration masking.

## Tasks

- [ ] Record baseline hashes; create Phase8 branch and prospective design.
- [ ] Independent author creates build_phase8_heldout.py, data/phase8, reference coverage/distance audit. Do not read production/new outcomes.
- [ ] Implement recovery_v8.execute(case, policy, fault='none', allowed_ids=None, world_index=0, quota=16), policies priority_equal/cost_equal. Meaningful tests first, then code, no heldout reads before freeze.
- [ ] Implement protocol_v8 factorized facts, strict parser and deterministic aggregation. Test toy edge cases before implementation. D reuses typed direct; F emits facts; T receives exact facts.
- [ ] Independently review components before freeze; correct issues, freeze code and data; validate differential semantics.
- [ ] Prepare fixed 480 jobs and budget reservation manifest; acquire once; run full recovery and integration VM/container grids.
- [ ] Analyze typed confusion, per-fact errors, repeat agreement, recovery cost/success and all-world gate sensitivity, family bootstrap.
- [ ] Write Chinese findings with limitations and prospective next changes; independent outcome review.
- [ ] Run tests and reproducibility verifier, freeze final release after all writing ends, commit/push private repo, verify remote refs and CI.

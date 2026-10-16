# Phase 9 implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task. User has authorized implementing all four priorities without further stage approvals.

**Goal:** Complete all four Phase 8 priorities with archived baseline, synthetic experiments, auditable comparisons and private publication.

**Architecture:** Independently authored reference fixtures, production-only protocols/query service and observation/recovery controller. Root integrates immutable acquisition, execution, analysis and verification; an independent reviewer checks prefreeze and final evidence.

**Tech Stack:** Python 3.12, existing DSL/interpreters, pytest, existing durable API client, pinned no-network Linux container, private GitHub CI.

**Spec:** `docs/phase9_design.md`.

## Global constraints

Only new Phase 9 files. No real corpus access, no human labeling. Frozen legacy code remains unchanged. Inherit all budget reservations, cap $29.551575125; campaign <= $4. Trusted observations never reveal private world index. Preserve ambiguous-stop safety.

## Review focus

Hidden or absent observation versus empty file; stale receipt/cache under changed state; query-prefix soundness with open catalog and partial applicability; duplicate global facts inconsistencies and missing world coverage; genuine planning limits and future fault blindness.

## Tasks

- [x] Archive: annotate and push verified Phase 8 tag, create study-v9, list baseline files before edits.
- [ ] Production protocol (`protocol_v9.py`, `query_v9.py`): red tests for strict factorial schemas, malformed duplicates, prefix soundness, early witnesses; implement fixed interfaces and run tests.
- [ ] Runtime (`recovery_v9.py`, optional `observation_v9.py`): red tests for hidden-world ambiguity, preflight poisoning, budget and cache integrity, shifted faults; implement and test all policies with same capabilities.
- [ ] Independent reference (`build_phase9_heldout.py`): 24 cases/12 mechanisms, exact independent truth, coverage and novelty. Do not materialize heldout before production freeze.
- [ ] Integration (`phase9_common.py`, `run_phase9.py`, `experiment_phase9.py`, `container_phase9.py`): immutable inputs/jobs, inherited budget, dry run capacity check, 336 one-shot calls, all-world operational grid and isolated replay.
- [ ] Analysis (`analyze_phase9.py`, plots, report): factorial effects, query proof efficiency/unknown reasons, observation/preflight/cost tradeoffs, exact old-case comparison; clustered uncertainty.
- [ ] Verification (`verify_phase9.py`, workflow): replay truth, requests, parsing, query budgets, runtime and analysis offline; test suite; old file hashes; release hash manifest.
- [ ] Independent review and publication: resolve important findings, preserve failure evidence, push study-v9 and main only after verification, check private status and exact-head CI.

# Goal-checked Skill recovery implementation plan

> For agentic workers: use superpowers:executing-plans, task by task. The user authorized direct completion. Preserve the design and progress ledger through compaction.

**Goal:** Test the independent value of state-aware recovery when goals contain postconditions but no supplied computation pipeline.

**Architecture:** Independent declarative truth checker, bounded AST runtime, certified state module, independently authored original helpers and source-free compiler, paired model acquisition and frozen replay.

**Tech stack:** Python 3.12 and existing project dependencies; inherited audited OpenAI client and budget ledger.

**Spec:** `studies/goal-recovery-v14/design.md`.

## Global constraints

- Synthetic data only; no real Skills, human annotation, native script execution or new credentials.
- Models exactly gpt-6-luna and gpt-4.1-mini; remaining allowance $16.8239037 under the inherited cumulative cap.
- All pre-v14 tracked bytes and tags remain unchanged.
- New files only under this study plus additive PHASE14.md; no source files under synced sources/ are modified.
- Main methods share goal, state, tools, validation and resource ceilings.

## Review focus

- False reuse caused by equal values on one input; new data/goal/order must invalidate the decision.
- Secret-dependent empty branches, malformed code and forged certificates must not bypass enforcement.
- Unknown sends must preserve physical history without leaking hidden commit status to the planner.
- Infeasible goals, missing permissions and exhausted budgets must not be reclassified as success.
- Shared generator/compiler logic or hidden template dispatch must not create an unexplained advantage.

## Tasks

1. [ ] Implement goal predicates and independent truth evaluation. Tests first: nonunique witnesses; wrong order; boundary totals; empty/missing/duplicate IDs; differential checks across generated candidates.
2. [ ] Implement bounded in-memory AST runtime and state certificates. Tests first: no imports/attributes/native access, implicit-flow disclosure, exactly-once effects, unknown status, per-input reuse and forged metadata. Run the full unit suite before committing.
3. [ ] Implement independent synthetic Skill helpers, source transformer and strong compiler. Tests first: no direct query or clean replacement in case payload, compiler solves development cases, counterexample defeats point-value reuse, strong validation rejects weak-fit candidates. Freeze source and selection manifests before held-out acquisition.
4. [ ] Implement common paired protocol and budgeted provider, using existing client internals. Tests first: input/output limits, unique identities, immutable outputs, inherited budget cap, cached-only replay. Conduct balanced development runs; preserve all diagnostics; acquire admitted complete grids only.
5. [ ] Recompute comparisons, ablations, challenge/final-input outcomes and all costs. Freshly replay saved responses, verify old-file inventory, independent review, address evidenced defects with preserved amendments, publish report/data/code and a new release.

Each task follows a failing regression, minimal implementation, green tests and a commit. Record deviations and exact commands in progress.md. A final read-only reviewer is required by the execution workflow; it does not authorize extra implementer agents or paid research calls.

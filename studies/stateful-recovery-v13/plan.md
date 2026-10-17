# Stateful Skill Recovery Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement this plan inline. A fresh whole-branch review follows implementation.

**Goal:** Construct and evaluate legal continuations without supplied replacement scripts.
**Architecture:** Finite data/effect interpreter, independent declarative goal evaluator, residual-contract compiler, common candidate verifier, equal-budget proposal methods, frozen experiment runner and replay.
**Tech Stack:** Python 3.12, existing pinned libraries and OpenAI response client, IEEE LaTeX.
**Spec:** `design.md`.

## Global constraints

- Synthetic only; no native execution of Skill packages.
- New campaign <= USD20; models exactly gpt-6-luna and gpt-4.1-mini.
- Preserve old evidence; do not change a frozen method after viewing test outcomes without an additive amendment and new evaluation label.
- Inputs, grants, receipts and task predicates are trusted; source and proposals are data.
- No default safe-script catalogue in main experiments.

## Review focus

- Lost acknowledgement: distinguish two worlds and avoid an assumed failure.
- Secret-controlled absence: retain labels on a missing file and observable branch effects.
- Old violation: safe completion stays false after irreversible prefix damage.
- Constant-output patch: different final input rows must expose memorization.
- Baseline fairness: same state, primitives, validator, caps and all attempt costs.

## Tasks

- [x] 1. Write failing tests for `engine.execute(program, world, task)` and `goals.expected(task, inputs)`. Implement finite primitives, labels, receipts, faults and explicit traces; hand-check table outputs and failure states. Preserve red/green outputs.
- [x] 2. Write tests for `verify.check(candidate, case, inputs)` and `contracts.build(case)`. Implement full-prefix evaluation, twin-world checks, residual predicates, dependency cuts and absence regression. Require literal expected counterexamples.
- [ ] 3. Test and implement `methods.propose`, deterministic construction, common model protocol, strict budget/resume behavior and all ablations. Run development cases only; document method choices and freeze source hashes.
- [ ] 4. Generate held-out families after freeze, validation/final inputs, faults and fixed-budget adaptive mutations. Save the finite grid and caps before acquisition. Verify no catalogue leakage or duplicated request replicates.
- [ ] 5. Run deterministic controls, then balanced two-model repeated experiments under the cap. Retain errors and every candidate/counterexample. Analyze clustered paired differences and complete cost ledgers.
- [ ] 6. Reproduce zero-API, audit controls and counterexamples with a fresh reviewer, write the simple IEEE paper and Chinese findings. Render and inspect the PDF. Verify old file hashes and publish new private branch/tag/release.

## Execution ledger

- 2026-10-18: User supplied detailed design and authorized autonomous execution; no repeated design/key approval requested.
- Native worktree tool reported “Not a git repository” for the parent project mirror. Used git worktree fallback for the actual nested repository. Old v12 archived remotely before checkout.
- Baseline: 70 v12 tests and 22 subtests pass. Existing previously authorized key presence checked without exposing it.
- Budget interpretation: USD20 newly authorized for v13; prior cumulative upper $22.781273975 retained separately. Total historical plus this campaign cannot exceed $42.781273975.
- First core implementation commit: bda827fb4e6de881322fb78c96a551adf2e00e16. Development v1 evidence is retained, not overwritten after audit fixes.
- Independent read-only core review found missing final two-world checks, omitted duplicate write/delete metrics, coincidental-cache weakness in the strong comparator, incorrect else-branch resumption and observer absence leakage. All were reproduced as failing tests and repaired before held-out generation or any API call. A separate liveness test exposed overwritten variables surviving retry slicing; repaired.
- 51 tests pass after these repairs. Both full-prefix and continuation effects contribute to security/duplicate scores. Model-visible state merges the two declared secret worlds. Strong goal construction has a budgeted fresh-query fallback when cached reuse fails validation.
- Cost accounting includes every interpreter call in observation/contract construction and validation, not only the final simulated continuation; final evaluation cost is separate. A bounded retry primitive only retries confirmed no-effect failures, never uncertain sends.
- Prospective model grid: 24 held-out task/state cases, eight methods, two models, three independent replicates, at most three validation candidates per run. Contract methods spend their first candidate on source construction, leaving at most two model calls. Input reservation bound 18,000 bytes including client headroom; output cap 1,600 tokens. Main worst-case request bound is $17.52408 (1,368 calls per model), below new USD20 cap. No API calls made at this ledger entry.

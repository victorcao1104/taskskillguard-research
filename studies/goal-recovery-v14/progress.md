# SDD ledger — plan: studies/goal-recovery-v14/plan.md

- User brief: directly complete a new synthetic round, preserve strong controls, fix reuse/generalization, retain negatives, publish within remaining budget.
- Archive: archive-before-goal-recovery-v14-20261018 pushed at v13 commit 4b24fd40ab3e625a23b6eb04b8665a6c57a92c19.
- Workspace: reused existing isolated worktree; new branch study-v14-goal-recovery. Existing untracked provenance/final_review.md belongs to the previous review and remains untouched.
- Pre-flight: goals feed runtime valid() and independent truth checks; runtime feeds certificate/state module; these interfaces will be tested before acquisition.
- Ruling: use a study-local persistent ledger rather than the shell-specific skill helper, to keep research decisions and corrections in the published artifact.
- Ruling: user already authorized design implementation and publication; no repeated permission gate. Existing API credential reuse remains authorized; do not reveal or copy credentials into the study.
- Task 1: complete. Missing-module regression observed, then four goal tests passed, including nonunique answers and independent checker differential tests.
- Task 2: core complete. Runtime and certificate tests were written and observed failing before implementation. Full suite: 13 passed. Certificates bind input/goal/value; the state module rechecks rather than trusting saved metadata.
- Baseline: all 66 v13 tests passed before new implementation. v13 files remain unchanged.
- Task 3: data, controls and shared verifier implemented after red tests. 20 tests pass. Original helper generation does not import the compiler; independent truth checks feasibility. Validation includes six random inputs plus reversal, ID renaming, ties/boundary values and decoy records (18 inputs); final 16 seeds and 32 larger stress inputs are separate.
- Ruling: main deterministic grid includes a prior-leak condition in addition to the twelve conditions in the design, so historical safety accounting remains directly testable. Main 24-case selection is unchanged. Runtime certificates validate values on each current input, not global equivalence of an arbitrary saved computation.

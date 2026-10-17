# SDD ledger — plan: studies/goal-recovery-v14/plan.md

- User brief: directly complete a new synthetic round, preserve strong controls, fix reuse/generalization, retain negatives, publish within remaining budget.
- Archive: archive-before-goal-recovery-v14-20261018 pushed at v13 commit 4b24fd40ab3e625a23b6eb04b8665a6c57a92c19.
- Workspace: reused existing isolated worktree; new branch study-v14-goal-recovery. Existing untracked provenance/final_review.md belongs to the previous review and remains untouched.
- Pre-flight: goals feed runtime valid() and independent truth checks; runtime feeds certificate/state module; these interfaces will be tested before acquisition.
- Ruling: use a study-local persistent ledger rather than the shell-specific skill helper, to keep research decisions and corrections in the published artifact.
- Ruling: user already authorized design implementation and publication; no repeated permission gate. Existing API credential reuse remains authorized; do not reveal or copy credentials into the study.

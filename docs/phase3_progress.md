# Phase 3 execution ledger — plan: docs/phase3_plan.md

- User authorization: implement prior six-step recommendation, redesign/run next round, upload existing private repo, cumulative USD20, human annotation deferred.
- Baseline: branch study-v3 from 91d3688; clean working tree; pytest 158 passed / 4 Docker-gated skipped (6.11 s).
- Budget read-only reconciliation: 5974 reservations; USD5.858965400000001 upper exposure.
- Scope decision: use dedicated existing research checkout on new branch; preserve old artifacts and tags. No duplicate repository/worktree or new credential approval needed for the already authorized continuation.
- Pre-flight: protocol produces planner dict consumed by execution; real-context jobs consumed by main single-writer API driver; transform callback consumed by new executor. Interfaces specified in plan.
- In progress: freeze design and assign independent code domains; implementation not yet complete.

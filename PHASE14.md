# Phase 14 — Goal-checked recovery without a supplied computation recipe

All new files live in [studies/goal-recovery-v14](studies/goal-recovery-v14/README.md). Earlier versions and papers are unchanged. The archive tag `archive-before-goal-recovery-v14-20261018` preserves the v13 starting point; `v14-development-pilot-20261018` preserves the complete pilot.

Read [REPORT_ZH.md](studies/goal-recovery-v14/REPORT_ZH.md) for the full findings and limitations, [VERSION_COMPARISON.md](studies/goal-recovery-v14/VERSION_COMPARISON.md) for the design changes, and [analysis.json](studies/goal-recovery-v14/reports/analysis.json) for every grouped result and cost field.

The new task gives independently checked output constraints, not a computation pipeline. State recovery certifies current values and preserves completed effects. Strong source-free compilation, ordinary repair and source-free replanning remain controls, including versions with the same automatic state module. All execution uses a bounded synthetic interpreter.

Blocked main episodes: full recovery safely completes 45/54 with Luna and 42/54 with GPT-4.1 mini; ordinary repair with the same state module completes 42/54 and 40/54. Only 45/54 are designed feasible. The compiler solves all 15 feasible cases among 18 blocked cases without model calls. Full recovery uses 20/27 model requests versus 60/80 for state-assisted repair; local verification costs are separately counted and are not uniformly lower.

Combined conditions: full recovery completes 23/24 Luna episodes and 21/24 mini episodes; state-assisted repair completes 24/24 and 18/24. The one Luna full noncompletion is a preserved HTTP 400 `invalid_prompt` provider rejection, not evidence that its generated program failed. The compiler solves 12/12 combined cases. No selective replacement runs were made.

Seven mini programs passed construction validation but failed final inputs, largely because they added constraints the task did not require; one stopped at the step budget. All seven pass the larger-input sample, demonstrating why larger random inputs do not replace targeted checks. The report preserves both sets and requires their intersection for robust success. No real-Skill, universal-safety or first-of-its-kind claim is made.

Evidence: 864 main episodes, 144 combined episodes, 72 pilot episodes, 312 broad deterministic controls, 36 combined controls, 1,008 larger-input evaluations, and 1,008 fresh cached replays. The reproduction audit found no semantic replay mismatch and checked 2,436 summary/evidence pairs. New tests: 32 passed; unchanged v13 tests: 66 passed.

Budget: $1.055283675 new conservative exposure; $15.768620025 remains. The old cumulative cap and ledger prefix are unchanged. Release tag: `v14-goal-checked-recovery`.

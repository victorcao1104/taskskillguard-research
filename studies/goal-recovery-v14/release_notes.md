# Goal-checked synthetic Skill recovery (v14)

This version replaces recipe-like task specifications with independently checkable output constraints, checks reused values against the current input and goal, and expands held-out input validation. It retains strong source-free compilation, ordinary model repair and replanning, including controls sharing the same state module.

Main blocked episodes: full recovery safely completes 45/54 with gpt-6-luna and 42/54 with gpt-4.1-mini; state-assisted ordinary repair completes 42/54 and 40/54. The compiler solves all 15 feasible cases among 18 blocked cases. Full recovery reduces model requests but does not uniformly reduce verification work or establish a general advantage over strong controls.

Combined conditions preserve an unfavorable observed Luna comparison: 23/24 full versus 24/24 state-assisted repair/replanning. The full noncompletion is an HTTP 400 invalid_prompt API rejection, so it is not an algorithmic failure finding. Seven accepted mini programs fail nominal new inputs after adding unnecessary constraints, yet pass the larger-input sample. Both findings remain in the report.

Read [the full Chinese report](https://github.com/victorcao1104/taskskillguard-research/blob/v14-goal-checked-recovery/studies/goal-recovery-v14/REPORT_ZH.md), [the version comparison](https://github.com/victorcao1104/taskskillguard-research/blob/v14-goal-checked-recovery/studies/goal-recovery-v14/VERSION_COMPARISON.md), and [reproduction instructions](https://github.com/victorcao1104/taskskillguard-research/blob/v14-goal-checked-recovery/studies/goal-recovery-v14/README.md). Exact requests, responses, candidates, failures, frozen inputs, summaries and compressed traces are included. All 1,008 main/combined episodes freshly replay without API calls and match excluding timing. Old versions are unchanged.

Models: gpt-6-luna and gpt-4.1-mini. Synthetic data only. This round adds $1.055283675 conservative exposure, leaving $15.768620025 under the inherited budget. No universal-safety or novelty claim.

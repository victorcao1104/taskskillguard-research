# v14 paper: safe recovery after a blocked Skill

This release adds a new English IEEE-style paper based on the frozen v14 synthetic experiment. The central question is what state management and program repair contribute after an untrusted Skill is blocked, under fixed permissions and independently checkable goals.

## Included

- Final PDF: 10 body pages plus one reference page; 180-word abstract; 17 cited references.
- Editable standalone LaTeX, build instructions and citation audit.
- Claim-to-result map, checked result extract and SHA-256 manifest for 8,666 frozen experiment files.
- The complete corresponding study under studies/goal-recovery-v14 in the tagged repository.
- All older papers, experiments, raw responses and failure evidence remain preserved.

## Findings retained

State support helps several model baselines, and preserving useful computation reduces model requests. Full recovery has only small, uncertain completion gains over repair with the same state support. The strong source-free compiler solves all feasible cases in the matched main and combined grids. Seven accepted Mini programs fail on unseen inputs after imposing extra constraints; all seven pass larger-input tests. The Luna combined 23/24 result retains a provider rejection and does not misclassify it as an algorithmic failure.

This is an empirical contribution, not a claim of universal recovery, real-Skill effectiveness or a novel general synthesis algorithm.

## Access and reproduction

The repository remains private. Collaborators need repository access to inspect history and the full experiment.

The manuscript package contains the paper sources and evidence index. For full cached experiment replay, clone the tagged repository and follow studies/goal-recovery-v14/README.md. No paid model calls are required for cached replay.

Experiment baseline: ea7bb8ce9e8495a03566e1d5b91a1e3698237b50 / v14-goal-checked-recovery.
Pre-rewrite archive: archive-before-paper-v14-20261018.

No new experiment API spending, real Skill data or human annotations were added for this paper rewrite.

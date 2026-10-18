# v15 design: mechanisms and alternative explanations

Baseline: 74a06d2f3345ed8e2eb7768d36ba66d2e9ae7688 (v14 paper and frozen study).
User-supplied paper5.pdf is byte-identical to the v14 paper (SHA-256 36f5b0432c372ff2b09fc5bee667db12276861c35af84c474ba6e2aa5b9c4181).
The user explicitly requests these experiments and confirms synthetic-only scope with simulated service faults. Existing API configuration and the two models remain authorized; no new key or budget increase.

## Questions and primary comparisons

RQ1: Which part of state support prevents which error?
A raw state / B certified structured state / C trusted residual-action list / D automatic residual execution.
Hold computation fixed to the same valid candidate, with identical goals, grants, histories and model limits.
Primary paired contrasts: B-A (information), C-B (decision support), D-C (execution delegation).
Report wrong-cache attempts and accepted writes, attempted/executed duplicates, missing obligations, erroneous stops, protocol errors and safe completion. Gateway remains common. Protection ablations run only in the simulator.

RQ2: When is preserving source computation useful?
For the same task/input/history, vary source: intact plus dangerous action; local arithmetic/condition damage; destroyed algorithm; absent; irrelevant code.
Compare Full, ordinary repair with common state support, source-free replanning with common state support, and task-appropriate deterministic solvers.
Replanning requests are shared across source levels because replanning must not see source. Do not count reused results as independent model samples.
Full's deterministic transformation occupies the first of two candidate slots; all other model methods have two model slots.
Primary interaction: Full-minus-repair by source integrity, completion and request savings. No prior requirement that Full wins.

RQ3: Which tests detect which faults, at what cost?
Existing seven v14 failures are development/causal diagnostics, never the held-out validation population.
A source-span intervention replaces only inactive requires/conflicts lookups with empty relations; all other text remains identical. Evaluate each relation separately and together, under original and increased step budgets. Reinsert analogous restrictions in correct solver programs.
Compare equal-count random, larger-input and targeted tests; also compare under a common logical step cap. Report false rejection of correct programs, defect detection, first failure work and accepted-candidate independent-final failure.
Frozen novel mutants include ordering, stale IDs, boundary conditions, wrong arithmetic, dropped records, extra constraints and effect mistakes. Report in-distribution and held-out defect families separately.

## Task structure and sampling

Four structures, four semantic templates each: transformation/aggregation, graph computation, linked report artifacts, simulated service workflows. These are 16 authored templates, clustered into four related structures; do not describe parameter instances as independent tasks.
Goals describe independently checkable outputs, not a supplied imperative route. Deterministic reference solvers remain strong controls. Reference solvers and candidate implementations are separate; both belong to this benchmark team.
New inputs: development seeds 101â€“104; construction validation 201â€“204; final 1001â€“1008; scale 2001â€“2004. Formal main inputs and all source variants freeze before acquisition.
Source campaign: 16 templates Ã— five source levels Ã— Full/repair plus source-free replan once per template Ã— two models. One run per task/model, prioritizing templates over repeated deterministic successes.
State campaign: 16 templates Ã— four paired histories Ã— four support levels Ã— two models. Fixed correct computation, effects generation only. Histories: invalid cache / confirmed delivery / unknown with query / same unknown without query. Additional offline paired boundaries and multiple service faults.
No real Skills or human annotations.

## Budget and stopping rules

Inherited upper exposure $27.01265395, cumulative cap $42.781273975; available $15.768620025. This is the existing conservative ledger, not an invoice.
Use GPT-6 Luna and GPT-4.1 mini only. Max input bound 14,000 bytes including conservative output headroom; max output 2,000 tokens; max two slots per episode. All simulations, checks, rejected candidates and prefix logical work counted.
Whole-grid maximum-reservation admission precedes live acquisition. Pilot may adjust shared protocol, then source/protocol/data hashes freeze. No selective retries after final evaluation.
Maintain a durable inherited ledger, exact requests and raw responses; cached-only is the default. Leave unused budget rather than add unplanned confirmatory experiments.

## Analysis and exclusions

Prospective primary comparisons above are frozen before formal acquisition. No outcome-based exclusions. API, schema, syntax, resource, permission, task-semantic and explicit-stop outcomes remain separate.
Feasible completion, correct boundary stop, wrong stop, and subsequent completion after historical harm are distinct.
Use paired template-level differences, bootstrap intervals and sign flips with 16 clusters; also display the four structure-level aggregates. Single run does not estimate model sampling variance.
Sensitivity: at 16 templates, a sign test with all nonzero differences aligned requires six discordant templates for two-sided p<.05. With 30% discordance, rough 80%-power normal approximation needs about 59 clusters for a 20-point difference; this study is not powered to rule out small effects. Report precision and directional patterns, not significance hunting.
Budget curves at one/two candidate slots and zero/one/two model requests use saved attempts; time/cost curves are descriptive reanalyses, not new acquisition.

## Preservation and deliverables

Create only studies/recovery-mechanisms-v15. Preserve all v14 files and old papers. Archive tag before edits. Report all results and limitations in English machine-readable tables and a readable Chinese report; upload a new tag/release in the same private repository after review.
No paper rewrite is implied before new results are known. Final conclusions must answer conditional mechanism value rather than advertise Full.


## Pre-formal protocol amendment after two pilot batches

The reservation input bound is 24,000 bytes (including the inherited 4,096-byte headroom), not the initial 14,000. Full feedback and candidate source must fit without truncation. The admitted full grid maximum is $13.1712, within the verified remaining allowance; this is a ceiling, not planned expenditure. Two 44-episode pilots are excluded from formal results and retained. Shared schema wording now distinguishes executable effects from prose and makes the fixed-computation invocation explicit. Exact runtime error detail is returned uniformly. No task-specific answer is added. JSON type equality rejects booleans in place of required integers. A concurrent progress-display ledger read was guarded by its existing lock; reservations were already guarded.

Source attacks use one explicit private-read conditional without an else. This is a controlled source-integrity experiment, not evidence of broad attack-family coverage. The unchanged v14 transformation is retained; complex branch reconstruction is outside this primary test.

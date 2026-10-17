# Stateful construction after a blocked Skill: prospective study v13

Date: 2026-10-18 (Pacific/Auckland). Base: `2ee03bf7f6761784a41fb98b96086b78e85e0126`.
User authority: continue autonomously, synthetic data only, GPT-6 Luna and GPT-4.1 mini, new campaign capped at USD20. Prior costs remain preserved and do not reset historically.

## Question and falsifiable contribution

Can a system construct a legal continuation after a Skill is blocked, without a supplied replacement script, while preserving completed work and avoiding repeated effects? The proposed mechanism is a **residual effect contract**: trusted task predicates, the execution receipt state, and a cut through tainted source dependencies jointly constrain candidate programs. The method is not claimed to invent synthesis, CEGIS, information-flow repair, or transaction recovery.

Hypotheses: (H1) contract guidance improves safe completion or reduces total generation/verification cost relative to equally budgeted repair and fresh replanning; (H2) each contract component changes its predicted failure class; (H3) improvement survives task/attack structural holdouts and partial states. Ties and reversals refute the corresponding claims. Outcomes are never a stopping criterion for experimentation.

## Alternatives and selection

1. LLM-only repair is simple and is a required baseline, but its repeated instructions do not produce an explicit state contract.
2. Full symbolic synthesis can provide a strong bounded-language comparator, but an unrestricted tool search is expensive. Include a goal-directed deterministic constructor as a strong reference; do not weaken it to favor the LLM.
3. Selected: a small trusted contract compiler plus untrusted model proposals, checked by the same executable validator used by all competitors. Preserve original source as a possible hint, never as the goal definition.

## Trust boundary and language

Tasks supply input schema, declarative relational/aggregate output requirements, immutable permissions, preserved inputs, delivery identifiers and a remaining call budget. They do NOT supply a replacement program. Skills contain SKILL.md and JSON programs in a documented finite language. Primitive operations are read, filter, project, sort, aggregate, join, arithmetic map, object construction, write, send, delete, status query and conditional execution. No primitive accepts a task identifier or directly solves a benchmark task. No native Skill code is executed; resources and messages are in-memory synthetic objects.

Untrusted candidates cannot modify grants, task goals, receipts, truth functions or budgets. Resource operations require exact grants. Values carry source labels, including control influence and file absence labels. Successful previous operations remain in the full trace. Previous unauthorized or disclosed effects make safe completion false forever. An uncertain send represents two possible worlds; continuation must work in both or stop/ask for confirmation. A permitted status query may distinguish those worlds. This is finite testing of confidentiality, not a sound proof for general programs or distributed systems.

## Mechanism

1. Compute pending goals from task predicates and trusted confirmed receipts, distinguishing success, failure, unattempted and uncertain effects. Expose unknowns, never convert them to not-sent.
2. Analyze explicit variable and control dependencies. Mark outputs transitively dependent on blocked or secret operations as unusable hints. Dependencies do not become task obligations.
3. Emit a residual contract: pending predicates, reusable verified artifacts, forbidden dependencies, effect counts, required status checks and unchanged permissions. This is a constraint representation, not an ordered replacement program.
4. Propose bounded programs. Every method receives the same primitive documentation and validator budget. Check syntax, privileges, full-history integrity, variable data correctness, effect multiplicity, and paired secret worlds. Return a concrete counterexample. Contract-guided retries retain learned constraints; ordinary CEGIS also receives the same underlying counterexamples.

The full method is not only an annotated prompt. A deterministic continuation constructor removes completed effect obligations, inserts status-conditioned sends for uncertain receipts, retains bounded retries only for confirmed no-effect faults, and backward-slices unused data computations. It can sever a source condition whose predicate depends on a forbidden read, treating branch bodies as candidate hints; it never declares that transformation correct before common validation. It first tries this construction from the original Skill, charging one validation slot. If rejected, it uses model candidates and the same constructor for the remaining slots. Models do not gain extra calls or validation slots. The four ablations disable the corresponding constructor pass as well as its prompt annotation. This mechanism is separately compared with direct goal-directed construction to reveal whether the finite task specification already makes repair unnecessary.

## Controls and ablations

Deterministic: stop, remove the blocked statement and resume, retry the original Skill, goal-directed construction, and an explicitly advantaged prewritten-catalogue reference.
Model: ordinary error-guided repair; discard-source replanning with the same task/state; ordinary candidate generation plus the same validator; full contract guidance. Four full-method ablations remove residual-goal derivation, dependency-cut annotation, history-derived constraints, or structured counterexample retention. Raw task/state remains available to all main competitors. Ablations are information-processing ablations, not changes to the safety gateway.
All model methods use identical per-run caps for calls, output tokens, verifier calls and input size; the same model and sampling settings are paired. All preprocessing, validation steps, execution steps, model tokens and elapsed time are recorded. Early acceptance saves cost. Duplicate or unsafe proposals remain in attempt records even when the common gateway prevents real effects.

## Data and freeze order

Develop on a small, named set of task and attack mechanisms. Freeze semantics, methods, prompts and generator rules before generating held-out cases. Use held-out relational task structures, held-out attack transformations and their compositions. Distinguish developer-authored structural holdouts from independently authored tests: this study is not independently human-designed.
Generate varying rows and values, plus separate validation and final evaluation inputs. A candidate that memorizes one output must fail. Include deletion-only repair, lost variables, malicious conditions, mixed payloads, completed writes/sends/deletes, missing acknowledgements, insufficient grants/budgets, unreachable tasks, previous irreversible disclosure, and repeated transient faults. Faults must actually occur at multiple reachable effect positions; record reachability.
Add a fixed-budget adaptive mutation search after the method freeze. It may inspect the public method and query the same validator, but cannot modify trusted tasks. Retain every mutation and query; no claim of unrestricted attacker robustness.

The frozen offline grid contains six task templates and 21 states (benign plus 20 attack/fault settings), or 126 cases. Four supplemental states exercise faults after a completed write, a failed receipt query, a new lost acknowledgement during recovery, and two consecutive delete failures. The last-but-one has runtime uncertainty: this finite interpreter cannot resume inside an uncertain operation, so a verified single continuation may be impossible. This is reported separately from missing permission and budget infeasibility. The paid main grid is the prospectively balanced 24-case selection recorded in `run.py`; eight methods, two models and three replicates yield 1,152 episodes. Each has at most three candidate validations. Full and ablated constructors spend one slot on a source-derived proposal and can call a model at most twice; the three ordinary methods can call it three times. Actual spend, CPU, simulated calls and validation executions are reported, not treated as equal realized cost.

The catalogue reference is a separately stored task-specific answer prepared by the strong goal compiler and its validation fallback. Its preparation evidence and cost are retained under `reference_catalogue/`; only this advantaged reference may read those answers. This is a synthetic prepared-answer reference, not a claim to execute the old v5 catalogue implementation unchanged. The source-free compiler remains the main non-LLM competitor and receives no prepared answers.

The fixed adaptive budget is eight mutations for each of six families. The adversary queries the source-derived constructor and common validator, not the complete paid recovery loop. It selects the rejected feasible mutation with the largest measured interpreter step count, with a deterministic index tie-break. A separate legal-plan witness excludes trivially impossible histories. Only validation inputs participate in selection. Four defenders then run with both models and two replicates on the six selected mutations (96 episodes). All 48 attack queries, witnesses, costs and failures are retained. This limited search does not establish robustness against an unrestricted adaptive attacker.

## Metrics and analysis

Report ordinary completion, unauthorized effects, forbidden disclosure, full-history safe completion, duplicate effects, benign interference, infeasible/uncertain stop behavior, and total cost/time. Separate proposal violations from executed violations. A no-solution search timeout is unknown, not an impossibility proof. Irreversible prefix damage is separate from an unsafe recovery.
Pair comparisons by task/state/model/run. Repeat model requests with independent replicate identifiers; never reuse one response as multiple independent runs. Cluster by task/attack structural families, not wording or input rows. Report absolute counts, paired differences, cluster-bootstrap uncertainty and repeated-run variability. Main claims use held-out tests; development/adaptive results are separate. No selective removal of provider failures or difficult tasks.

## Delivery and limits

New code/data/results/paper live only in `studies/stateful-recovery-v13/`, plus an additive root phase index. Existing 47,056 tracked files and tags stay byte-identical. Publish a new branch/tag/release in the same private repository. Preserve prospective freezes, failed tests, counterexamples, raw model responses and budget ledger. Portable zero-API reproduction is required.
The revised paper remains a finite synthetic Skill recovery study. Follow the previous IEEE rubric and simple language. Do not promise positive results, priority, broad confidentiality or real-market generalization.

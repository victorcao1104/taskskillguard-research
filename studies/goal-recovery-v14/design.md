# v14: goal-checked continuation construction

## Authorized objective

Continue the user's synthetic Skill-security research. Goals must be independently checkable without a supplied computation pipeline. Fix point-value reuse and weak new-input verification. Preserve strong source-free compilation, model replanning and ordinary repair, and test the independent value of the state mechanism. Preserve all old results and negative findings; publish on the existing private repository. Models remain gpt-6-luna and gpt-4.1-mini. There is no new $20 allowance: the remaining v13 allowance is $16.8239037, subject to the inherited ledger and unchanged cumulative cap.

## Chosen design and alternatives

This is an architectural extension in an existing isolated worktree. The user explicitly authorized implementation, experiments and publication; existing credential reuse remains authorized. The design/planning workflow records concrete decisions without inserting another approval round.

Simply hiding v13's query behind prose would preserve its direct compilation recipe. Unrestricted Python would introduce an unnecessary sandbox problem. Instead, use declarative constraints over selected public records and a small interpreted Python subset. Valid outputs can be nonunique. A trusted task supplies output properties (coverage, cardinality, totals, uniqueness, incompatibility, dependencies and ordering), not a sequence of filters, joins or aggregations. An independent evaluator checks these properties. General combinations enumeration is permitted as a primitive; it supplies no solution and every examined candidate is charged.

## Threat model and separation

Synthetic Skill packages contain instructions and two untrusted code blocks: compute a variable named `result`, then perform effects. Both blocks use the same restricted language and tools. Execution is an AST interpreter over in-memory values, with no eval/exec, imports, arbitrary attributes, native files or network. Secret labels propagate through data and control flow. Permission checks apply equally to original and recovered code. A checked current state records artifacts, sent/unknown receipts, cleanup and prior violations. Prior violations cannot be erased.

The planning code and the final truth checker are separate implementations. Tasks expose all constraint semantics to every method. `valid(candidate)` is a shared Boolean goal check, not an answer-producing tool; its work is counted. The benchmark generator does not call the strong compiler to create original helpers. Candidate programs are tested on changed record identities, values and order, not just the one recovery input.

## Recovery mechanism

The state module computes unfinished obligations and can certify a saved selection only for the exact current input, goal and value. It does not infer program equivalence from point equality. A reuse decision is rechecked for every execution input; changes invalidate the certificate. The certificate is created by trusted code, never accepted from Skill-provided metadata. A candidate without a usable cached result must compute a new result. Final effects remain under the same grants. Confirmed effects are preserved; unknown sends require an already authorized status query, otherwise execution stops.

The full method starts with a bounded source transformation: track secret/forbidden-read dependencies, remove contaminated assignments and unwrap attacker-dependent branches, then try the resulting compute block with the state module. The common verifier must still accept it. At most two model proposals follow that first candidate. The transformation is a heuristic, not a proof or a complete synthesizer.

## Strong controls and attribution

Six model methods: repair_raw, repair_state, replan_raw, replan_state, full, full_no_reuse. The first four get up to three model proposals; full methods spend the first of three candidate slots on their source bootstrap. Raw methods receive the same state, task, grammar, valid() and validation evidence; the state methods additionally apply the automatic state module. Replanning never receives original Skill code. All methods use the same output schema, parser, input cap, output cap, validation inputs and final evaluator.

The strong compiler emits source-free bounded combinatorial search plus explicit state/receipt handling, including independently checked reuse. It is not weakened into blind replay. A fresh-computation compiler remains as a secondary efficiency control. Stop and source construction controls are also retained. Exact finite search is a legitimate strongest control; if it wins again, report that. Controlled reuse and validation probes compare old point-value acceptance with runtime certification, and three nominal validation inputs with structured challenge inputs, on the same candidate bank. Those probes are not extra independent task families.

## Dataset and freeze

Two development goal families and six held-out families combine public predicates: coverage under budget, exact quota with quality bounds, compatible panels, dependency-closed packages, matching selections and ranked selections. Six task structures are not six unrelated real applications. Public goal constraints can still be expressive enough for a general solver; that is a declared control, not a claimed absence of all formal specification.

Full deterministic grid crosses six held-out families with benign, forbidden dependency, destroyed computation, mixed secret payload, partial artifact, confirmed send, queryable unknown, unqueryable unknown, stale saved selection, forged certificate, missing grant and infeasible goal conditions. Freeze a 24-case model subset by family and condition before acquisition, with three runs per model/method. Additional fixed combined mutations are evaluated after method freeze, with no selective reruns. Candidate programs are checked on nominal inputs plus permutations, ties, boundary values, decoy records and changed identifiers; final seeds and a larger-input stress set are not fed back to recovery.

## Metrics and limits

Report complete, safe complete, permission/disclosure/duplicate violations, benign losses, stopping on designed nonfeasibility, accepted-but-wrong programs, request counts, tokens, conservative exposure, candidate checks, interpreted steps, tool calls and time. Include the original prefix. Cluster comparisons by six task families; three repeated model runs are not independent tasks. Report raw and state-assisted controls separately; do not compare the best full protocol with a weaker control protocol.

Finite input checking is not a proof for every input. Runtime certificates validate current values, not future programs. The interpreter is a synthetic model rather than a production sandbox. A strong solver's advantage may reveal that automatic repair is unnecessary in this domain. No novelty or real-Skill claim follows merely from adding components.

## Budget and reproducibility

Pre-acquisition review amendments: secret use conservatively taints the rest of an interpreted continuation, including expression effects and exception-dependent control. A new recovery boundary resets this control context; caches from a secret-using prefix are unavailable through the common public cache view to every method. This trades precision for an auditable bounded model and is not a production information-flow proof. Expanded nested values are bounded before copying; string formatting is excluded. Hidden secret/physical-commit fields in counterexamples are never passed to a model. On retries, the last full candidate replaces original source, and the failing input replaces the first example to avoid duplicating large data under the shared context cap. This is uniform across methods. Invalid protocol output consumes a candidate slot; an infrastructure failure ends that episode without a silent request retry.

Append a new ledger with the exact old ledger prefix; keep the original cumulative cap. Price every request before dispatch, unique campaign identities, no silent retries of uncertain requests. Proposed caps: 12,000 input bytes and 2,000 output tokens; admit whole grids only when their worst reservation fits. Main maximum is 1,152 requests per model, bounded at $12.096 for the two models at checked conservative rates. Reserve the rest for development and a small prespecified combined-condition grid; reduce a not-yet-started grid uniformly if admission fails, never select by observed success.

Save raw responses, failures, all candidate programs, challenge counterexamples, input seeds, execution traces, source/data hashes and revisions. Fresh replay executes saved programs into a new output directory with no API calls. Publish a new tag without moving any old tag.

Development-only amendment before main freeze: the complete 72-episode pilot used $0.063605225 conservative exposure and is archived at v14-development-pilot-20261018. Import/function-definition mistakes, wrong send arity and two retry input-cap failures were observed. All main and combined methods therefore receive the same explicit system-level reminder that builtins are preinstalled, imports/functions are unsupported, and send has three arguments. The shared input ceiling becomes 14,000 bytes including headroom; output stays 2,000 tokens. Main maximum reservation is $13.3056 and combined maximum is $2.2176, totaling $15.5232 against $16.760298475 remaining after the pilot. No task solution or computation sequence is added. Pilot results are never replaced or pooled as main results.

# Phase 11 independent finite reference

The authoring script uses only frozen `truth_v6` validation and its diagnostic
interpreter. It neither imports nor reads the Phase 11 production runtime,
controller, protocol, experiment results, or model outcomes. The independent
guarded interpreter was implemented from an explicitly supplied semantic
contract. This is implementation independence, not an independently invented
language specification. The original unrestricted `truth_v6.run` results are
retained beside the guarded results and are not used to certify execution.

The planned main sample has 48 cases: two lexical variants of each of 24
structural templates. Names, paths, and literal erasure identify the actual
number of original AST skeletons. An exact-match comparison also checks old
Phase 6–10 originals and alternatives. Any discovered shortcomings are retained
in the first-pass coverage record, not repaired after outcomes are observed.
Two variants do not count as independent structural families, and syntax novelty
does not establish independent mechanisms or real-world generalization.

## Public case and independent result schemas

Each case contains `case_id`, `family`, `split`, `generation.variant`, `program`,
`routes`, `worlds`, `goal`, `observable_files`, `observable_grants`,
`catalog_closed`, and a source Markdown rendering. The public original is route
0; `routes` holds alternatives indexed from 1. Worlds contain initial string
files and operation/resource grants. The main schema permits 2–8 worlds and
1–5 alternate routes. Every authored catalog is closed.

Each reference record has `executions[world_index][route_index]` with final
files, emissions, full attempted-effect trace, completion/error, goal,
`safe_success`, charged calls, receipt reuses, and entered steps. It separately
retains `diagnostic_unrestricted_executions`. `observation_classes` lists world
indices, universally safe routes, intrinsic certificate feasibility, and the
minimum number of fresh run receipts conditional on the class. No model or
controller output participates in this truth.

## Guarded execution contract

Every route starts from a fresh supplied world with quota 32 and at most 100
entered AST steps. Reads, writes, emissions, and deletion require grants.
An implicit receipt key is the site identity and occurrence number. Explicit
keys are scoped to one fresh run. Exact receipt reuse costs no call and returns
the saved result, including the original read snapshot. A conflicting signature
or denied grant charges one call and stops unless quota exhaustion is reached
first. Reused emissions do not emit again. Every attempted effect is recorded.
Goal satisfaction requires completed execution, exact specified emission counts,
specified file contents, and specified absence; all attempted trace effects must
be authorized. A partial state matching the goal before an error is a failure.

Fresh audit queries do not share state with one another or with actual recovery.
Cross-route key collisions are included because stateful recovery may retain
receipts even when fresh route certificates are valid. A fresh certificate does
not by itself prove recoverability from an arbitrary partially mutated state.

## Observation and certificate meaning

A run query buys one fresh audit at a public `(world, route)` coordinate. It
does not reveal which world is actual. Charged initial observations reveal only
allowlisted file presence/value or grant membership and refine the compatible
world set. Missing files are distinct from present empty strings. Hidden worlds
are precisely worlds with equal answers to every allowed initial observation.

The independent finite checker uses only cached audit coordinates and already
obtained initial observations. `verified` requires a single route with cached
safe success for every compatible world. `infeasible` requires one cached
counterexample for every route and a terminal observation class: all remaining
allowed observations are constant within it. Otherwise the answer is `unknown`.
An empty compatible set is inconsistent evidence and returns unknown; it never
creates a vacuous certificate. A negative result before potentially refining
observations is not intrinsic infeasibility. Full audit suffices for either
positive or negative entailment in a terminal class but need not be minimal.

The checker trusts independently generated reference records and cache
coordinates; it checks finite entailment, not cryptographic authenticity.
Production is separately responsible for binding receipts to paid queries.
The checker never executes an unqueried program when deciding a certificate.

## Cost oracles and scaling limits

For a fully observed class with a common successful route, the minimum fresh
atomic run receipts is its cardinality. Without a common route it is null.
A minimal negative certificate has one failed run per route. These facts concern
this atomic receipt system, not the difficulty of static program reasoning.

For every actual world the authoring oracle exhaustively enumerates allowed
observation subsets. For each subset it computes the compatible worlds and
common successful routes. `hindsight_certificate_cost` minimizes the number of
observations plus compatible worlds over feasible subsets. It is an exact
hindsight lower bound on paid positive evidence, excluding search for the right
route and observations. It is not an online query selector. All current cases
have at most two observation atoms, so no subset truncation is necessary.

Twelve separate scaling siblings cross worlds 2/4/8/16 and total routes 2/4/8.
They declare a parent family, `split=scaling`, and a limitation: alternate routes
repeat equivalent programs while hidden markers distinguish world structures.
They measure certificate/cache width, not novel semantic route diversity, and
must not be pooled into the 24 main structural families.

## Preservation and verification

The script's default is ignored `work/phase11-reference-firstpass/`. It writes
all evidence exactly once and refuses to replace any first-pass artifact.
`provenance.json` records UTC authoring time, generator and hand-test hashes,
frozen reference hash, artifact hashes, and isolation declarations. The parent
must freeze production before copying these bytes into `data/phase11`.

Tests first demonstrated missing-implementation failure, then cover receipt
deduplication, read snapshots, partial goals before errors, grant denial, quota,
step limits, signature conflicts, every cache subset of a hand-derived tiny
case, compatibility refinement, empty compatibility, hindsight evidence cost,
case schema counts, and frozen output hash integrity. No test imports production.

The preserved first pass passed all declared coverage checks: 48 cases, 24
distinct original skeletons, two variants per family, and no exact prior
skeleton matches. Fourteen hand tests pass. An additional exhaustive check of
8,672 allowed observation/cache states across the 48 cases agrees with the
finite witness definition. There are 222 main world/route cells, including 150
guarded successes and 22 cells with receipt reuse. Error cells comprise 16 grant
denials, 8 signature conflicts, and 2 unbound-variable failures.

A material retained limitation is that the 86 feasible terminal observation
classes in the main sample are singletons; its 10 infeasible classes include
the hidden nonseparable examples. Feasible terminal classes requiring multiple
world receipts occur in the separately identified scaling siblings. The main
sample therefore does not independently test diverse multiworld feasible
terminal classes, even though certificates before observing can cover multiple
compatible worlds. Do not conceal this by pooling scaling siblings into main
family counts.

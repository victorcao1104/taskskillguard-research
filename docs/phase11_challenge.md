# Prospective Phase 11 multiworld challenge supplement

This is an explicitly disclosed addition, not a replacement of the original
first pass. Aggregate-only structural coverage of that first pass showed that
all feasible main terminal observation classes were singletons. The coordinator
requested this supplement to address that gap before any production outcome
access. The independent author has not read production Phase 11 code, model
outputs, controller results, or experiments. Every original first-pass artifact
remains byte-for-byte unchanged, and its hashes are embedded in this supplement's
provenance. The coordinator separately records when production was frozen.

The challenge contains 24 cases from 12 authored structural templates, with two
lexical variants each. Each case has 4–8 public worlds, 3–5 total routes including
the original, a closed catalog, an explicit goal, and explicit observation
allowlists. Full observation classes have cardinality 2–4. Main, challenge, and
scaling results must remain distinguishable; adding challenge cases does not
retroactively change the original 48-case sample or its limitations.

The supplement tests common routes that work across multiple hidden worlds,
world-specific alternatives, partial goals followed by branch joins, receipt
dependency forks and joins, shared read snapshots, branch-dependent overwrites,
exact emission counts, hidden aliases, and receipt signature conflicts. Fork/join
dependencies are represented by sequential finite DSL programs; there is no
concurrent scheduler or claim to test actual parallel execution.

At least six templates have a feasible multiworld terminal class. At least
three have an intrinsically infeasible terminal class even though each individual
world has a successful route: `forall world, exists route` does not establish
the certificate condition `exists route, forall compatible worlds`. These cases
test inability to select a common route from the permitted evidence, not an
inability to accomplish the task in a perfectly revealed world.

Some observation fields are duplicated aliases or constant; some distinguish
nuisance state without changing which route can accomplish the goal. The paid
atomic certificate system can still reward nuisance-world separation by reducing
the number of required run receipts, even when route feasibility does not change.
The supplement therefore separates decision information from world entropy and
does not assume information gain always measures useful decision progress.
Wholly hidden feasible cases and constant observation aliases include cases in
which initial observations cannot reduce positive-certificate cost.

The independent reference imports only the original reference author's frozen
helpers. Each public world/route cell has both an independently implemented
guarded execution and a frozen `truth_v6.run` diagnostic execution. Certificates
use guarded completion, exact goal satisfaction, and authorization of every
attempted trace effect. Quota, receipts, read snapshots, and the finite step limit
retain the original reference semantics. Case and result payloads otherwise
match the original schemas, with `split=challenge`, family prefix `p11c_`, and
case IDs `p11c-<family>-0` and `p11c-<family>-1`.

The same exact hindsight oracle enumerates every allowed initial-observation
subset, finds the compatible worlds, and minimizes observation count plus
required successful run receipts whenever a common route exists. This is a lower
bound on positive evidence with hindsight, not a deployable query selector or a
claim of computational optimality. The largest observation allowlist in this
supplement has three atoms; no subset is truncated.

Certificate validation enumerates all cached-run subsets when at most 16
compatible world/route cells remain. Cache cells outside compatibility are
irrelevant to the entailment checker, and duplicate observation histories with
the same compatible set are represented once. Broader pre-observation states
receive explicit empty/full/minimal-route and missing-one-witness boundary
checks. Their powersets are not called exhaustive. `checker_validation.json`
records both exhaustive and boundary-only counts and the cell limit.

Coarse AST normalization erases names, paths, and literal values but preserves
operation and expression types, order, branches, loops, and expanded call
boundaries. Novelty checks compare originals against all old original and
alternate programs plus the preserved Phase 11 first pass. Syntactic uniqueness
does not establish semantic independence, new real-world mechanisms, or external
generalization. The 24 cases represent 12 structural templates, not 24 unrelated
mechanisms; every template still uses the same bounded synthetic language.

Tests were authored first and initially failed because the implementation did
not exist. The completed tests cover counts and schema, multiworld positive and
negative family coverage, syntax nonduplication, original first-pass byte
preservation, per-class oracle relationships, no-savings cases, and frozen
challenge hashes. The generator seals `challenge.jsonl`,
`reference_challenge.jsonl`, `coverage.json`, `checker_validation.json`, and
`provenance.json` in ignored `work/phase11-challenge-firstpass/`. It refuses to
replace any existing artifact. The parent materializes these exact bytes only
after recording production freeze. The reference author does not materialize
release data or inspect production performance.

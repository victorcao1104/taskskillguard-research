# Phase 11 certificate theory and pre-freeze review

Prospective review, 2026-10-17. This document concerns `certificate_v11.py` and the finite fault-free route contract in `phase11_design.md`. It does not assert optimal route choice, arbitrary-program safety, or fault-tolerant completion. No heldout generator/data or model outputs were consulted. The associated independent tiny-model checks are in `tests/test_certificate_theorems_v11.py`.

## Model and trust assumptions

Let W be a finite nonempty declared world set, R a finite nonempty route set, and Q a finite set of permitted immutable initial observation functions `q: W -> A_q`. Let `h in W` be the actual initial world, unknown to the selector. For fixed VM semantics, goal, quota, grants, and initially empty execution receipts, define `S(w,r)` as a Boolean: the guarded fault-free execution of route r in world w terminates within its bounds, has no unauthorized effect, and satisfies the exact goal. A run query supplies one trusted Boolean S(w,r), plus its execution record; it does not identify h. Failed execution is a false S, not a successful authorization proof.

An evidence state E contains a partial table K of paid run receipts and paid observations. Available truthful observations leave the nonempty compatible set `C(E) = {w in W: every available observation agrees with w}`. Unavailable observations supply no value and remove no world. Invalid/out-of-catalog observations lead to mismatch/abstention, not an empty-set positive proof. No truth claim is made if h is omitted from W or evidence is unsound.

Assumptions: (A1) W covers the actual world and the route catalog is closed for the stated contract; (A2) the VM, grants, quota, program, goal, and receipt semantics are fixed and correctly modeled; (A3) run receipts and initial observations are truthful, snapshot-bound, and cannot be modified by the selector; (A4) before actual execution there is no external state drift; (A5) acquisition does not mutate the execution state or consume its effect quota; (A6) all executions pass through the guarded gateway; (A7) the contract selects one fixed route for the current class. A route itself may branch using its legal runtime reads. A controller that performs extra unmodeled observations, synthesizes a new route, or splices routes is outside A7.

The certificate binding must identify all inputs in A2 and all evidence references used to derive C and the witness. A content hash is an identity check, not authentication. The revised implementation constructs certificates from a trusted local cache and separately checks supplied certificates with `verify_certificate(case, trusted_store, certificate, quota)`. That checker recomputes binding, compatible worlds from named observation references, and exact positive witness coverage or negative failure coverage, without invoking the VM. It requires a genuinely trusted store; it cannot authenticate arbitrary forged execution records by checking their self-supplied hashes. Python-private attributes and a public digest do not provide isolation. An untrusted model must receive serialized public snapshots, with no reference to mutable session state. Unsafe direct object/cache mutation is outside the threat model.

## Proposition 1: positive witness soundness and extension validity

A positive witness for route r is one authentic successful paid run receipt `(w,r)` for **every** `w in C(E)`. Then executing r in the actual world is safe and goal-completing under A1–A7 in the fault-free model.

Proof. A1 and truthful filtering imply `h in C(E)`. The receipt for `(h,r)` establishes S(h,r). A2, A4–A6 identify this simulated execution with the guarded actual execution. Therefore it has the claimed properties.

If E' adds only consistent truthful observations and additional authentic run receipts, without changing A2–A5, the same r remains a valid witness. Proof: `nonempty C(E') subseteq C(E)` and existing true S entries remain true. Restrict the original receipts to C(E'). New run receipts cannot contradict authentic old ones under deterministic fixed semantics.

This establishes **witness validity**, not equality of the route returned by `check()`. The implementation selects the first fully covered route; new receipts may enable an earlier route while the old witness remains valid. Nor does it establish optimal cost, unchanged complete traces, or completion after faults. A subsequent commit/status protocol needs its own invariant and may safely abstain.

## Proposition 2: terminal negative stability under allowed refinement

Let Q_rem be the observations that are still legally available for future acquisition. Suppose each q in Q_rem is constant on C(E), and each route r has at least one authentic failure receipt `(w_r,r)` with `w_r in C(E)`. Then no future sequence of run queries and truthful Q_rem observations can produce a positive witness for a fixed route in this class. The negative verdict remains valid under those refinements.

Proof. Run queries reveal table entries but do not narrow C. A constant observation returns the common value and also does not narrow C. Induction over any finite sequence leaves C unchanged. Every route's failure witness remains a member of C and its false value is immutable; hence no route can have all-true receipts over C. Unavailable observations likewise do not narrow C. Contradictory observations violate the assumptions and require mismatch, not continued negative certification.

This is a robust-contract negative, **not** the assertion that no route can succeed in h. For example, with two observationally identical worlds and `S=[[true,false],[false,true]]`, each world has a successful route, but no single route works throughout the class.

### Unavailable-observation qualification found in review

The initial implementation's `_separable()` excluded every consumed observation ID, including unavailable ones. Its negative result was consequently stable only relative to the **remaining one-shot query catalog**. A two-world diagonal S table and one distinguishing unavailable observation form a counterexample to intrinsic irreducibility: a later available answer could split the class. The pre-freeze revision resolves this by keeping consumed unavailable observations potentially separating; both `check()` and `verify_certificate()` consequently refuse the intrinsic negative while such a separator remains. A regression test covers this behavior. If the one-shot catalog exhausts in this state, the result remains unknown rather than becoming intrinsic infeasibility.

## Proposition 3: no-opportunity bound for an observational class

Define the full observational equivalence class of h by `B(h)={w: for all q in Q, q(w)=q(h)}`. Assume all Q answers can eventually be obtained truthfully. If `for every r in R, there exists w in B(h) with S(w,r)=false`, then no sound acquisition policy restricted to Q and paid run queries can issue a positive fixed-route certificate in the actual world h, regardless of acquisition budget.

Proof. Every possible truthful observation transcript leaves every w in B(h) compatible. Run queries do not identify h. A positive certificate for r would therefore need S(w,r)=true for all w in B(h), contradicting the premise. This argument applies to adaptive and randomized policies: any concrete transcript on which a sound positive certificate is issued yields the same contradiction. It bounds **certifiable robust completion**, not actual-world completion by a guessing policy or a richer controller.

If unavailable observations prevent distinguishing classes that would otherwise separate, the effective compatible set may be larger than B(h). The same argument can apply to that larger reachable class for a fixed capability model, but this is an availability limitation, not an intrinsic property of the full permitted observation functions.

## Proposition 4: minimum positive run-receipt count

For a fixed compatible class C and the explicit-receipt proof language, any positive certificate needs at least |C| distinct run receipts; |C| suffice if some route is successful on all C. Necessity follows because each receipt covers exactly one `(world,route)` pair and every world needs coverage for the same route. Sufficiency follows by querying that route once per world.

This lower bound belongs to the declared certificate interface. Public programs may permit a different sound static analyzer to infer several cells without buying separate receipts, and duplicate semantically equivalent worlds could be compressed by a richer proof language. We do not claim an information-theoretic bound for arbitrary program analysis.

With unit costs, always-available observations, and a known actual h used **only by an offline oracle**, let `C_T(h)={w: for all q in T, q(w)=q(h)}` for each subset `T subseteq Q`. Then the minimum number of queries for a positive witness along this particular transcript is

`L(h) = min_T { |T| + |C_T(h)| : exists r, forall w in C_T(h), S(w,r)=true }`,

with infinity if no such T exists. Lower bound: any successful transcript uses some observation subset T and at least |C_T(h)| receipts; wasted queries cannot improve it. Attainability with oracle knowledge: acquire T, then audit a successful route over exactly C_T(h). This is a hindsight/omniscient per-instance ceiling on efficiency, not an implementable adaptive policy or a bound on expected cost without a prior. Nonuniform costs, unavailable observations, or sharing execution budgets require a different expression.

## Counterexamples and review findings

- All-authorized does not imply goal success; the success predicate must include the exact goal and error-free bounded termination.
- A successful route for each world (`forall w exists r`) does not imply a common successful route (`exists r forall w`).
- A positive witness may survive additional evidence while the checker's selected route changes. The design's revised witness language is appropriate.
- A missing receipt is not false; a negative certificate needs actual failures for every route and an appropriate no-further-refinement condition.
- Omitting the actual world or changing initial files after certification can invalidate positive execution despite all hashes being internally consistent. These violate the trust model; no synthetic success rate repairs them.
- Fresh absence of a commit record does not prove terminal noncommit. A delayed original may commit after a retry. Fencing or same-ID deduplication is necessary in a concurrent status model.
- The initial review found no separate imported-certificate checker. The pre-freeze revision adds one and checks changed binding, missing witness and quota mismatches. This resolves the interface gap; adversarial trusted-store replacement remains excluded, and hashes still do not supply authenticity.
- `_separable()` and query-policy partition scoring inspect public hypothesis answers. This does not reveal the actual world, but is real checker/selector work. The checker counts comparisons; selector partition scoring and structural cost computations also deserve measurement or an explicit exclusion from the abstract work metric.

## Prior art and bounded contribution

The positive/negative class arguments are elementary finite-set results. Stopping once hypotheses fit a decision class is established by [Golovin, Krause and Ray, ECD](https://arxiv.org/abs/1010.3091); overlapping acceptable route regions closely match [Choudhury et al., decision-region determination for active edge evaluation](https://arxiv.org/abs/1711.07329). External safety guards under uncertainty have direct precedents in [Alshiekh et al.](https://arxiv.org/abs/1708.08611) and [Carr et al.](https://arxiv.org/abs/2204.00755). Trusted checking of supplied evidence has the broader precedent of [Necula's proof-carrying code](https://doi.org/10.1145/263699.263712). Durable operation IDs, completion records, pending/stale states, and retry requirements are established distributed-systems mechanisms, explicitly discussed in [RIFL §§3–4](https://web.stanford.edu/~ouster/cgi-bin/papers/rifl.pdf).

The proposed contribution is therefore a particular executable contract, independent finite reference checks, informative counterexamples, and measured tradeoffs in a synthetic agent-workflow setting. These propositions do not establish publication novelty, real-world security, optimal acquisition, model superiority, or general recovery guarantees.

## Pre-freeze validation and acquisition review

The seven independent theorem tests quantify over complete Boolean tables compatible with partial evidence, all nonempty refinements on three worlds, all pairs of binary observation functions on three worlds, and receipt/query subsets. The receipt lower bound is checked using universal Boolean completions, not by mirroring `decide()`. The hindsight formula is compared against a brute-force search over observation and receipt subsets. These finite checks are supporting tests, not replacements for the proofs or validation of arbitrary Python implementation behavior.

Focused run on 2026-10-17: `tests/test_certificate_theorems_v11.py` plus `tests/test_certificate_v11.py`: **20 passed in 0.58s**. The seven theorem tests and thirteen production certificate tests were included. Output was saved at `work/p11-theory-review.xml`; it is a local test record, not an independent heldout result.

Read-only inspection of `scripts/run_phase11.py` and `scripts/phase11_common.py` confirmed that online stopping precedes request creation/reservation/provider I/O, fresh streams use disjoint deterministic replicate IDs, and finalization checks request-hash uniqueness. Graph/padding counts are explicitly local `o200k_base` counts with an unverified model-tokenizer mapping caveat. No runner execution or heldout data read was performed by this reviewer. Fresh online/fixed source streams can differ because the model makes independent stochastic choices: empirical completion equality is not implied by Proposition 1. Matched-prefix replay isolates surviving-witness validity, while the fresh stream comparison measures the full policy's cost/outcome difference. The freeze manifest should include the independent theorem-test file.

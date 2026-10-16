# Phase 10: decision-relevant observation and adaptive queries

The user approved this next round and direct execution on 2026-10-16. Only synthetic experiments are authorized. Preserve every file tracked at 738c1dbe60a42c941662878e849a9432d4543c86 byte-for-byte. Archive tag archive-phase9-20261016 is verified on the original private repository. The cumulative monetary cap remains $29.551575125; inherited conservative cost is $17.383292550, leaving $12.168282575. This campaign additionally caps new API reservations/settlements at $6. No real Skill or human labeling is involved.

## Questions and alternatives

RQ1: Can goal-relevant trusted observations recover robust-preflight refusals without relaxing grants, receipts, or unknown-commit stopping? Compare Phase 9, Phase 10 authorization-only observation, and Phase 10 authorization-plus-goal observation under identical budgets. Merely disabling preflight is retained as a diagnostic control, not the proposed fix.

RQ2: Does a bounded next-query or small-batch protocol improve validity over a full permutation, and does an execution-directed objective improve decision evidence? Compare both validity and unconditional proof/decision coverage; never repair answers using truth or silently replace an invalid answer.

RQ3: Does actual early stopping preserve completion while reducing paid interpreter work and total accounted workflow cost? Distinguish diagnostic completion from complete original authorization evidence. Compare fixed, diagnostic-stop, and authorization-stop prefixes of the same acquired stream. The authorization stop is a sufficient evidence contract, not a claim of globally optimal stopping.

RQ4: How robust are legal recovery choices under position-based versus operation-based faults and different predeclared risk weights? Retain calls, priority, risk policies and alternative planning; do not weaken a control to manufacture model gains.

## Architecture and interfaces

New versioned modules only. `recovery_v10.execute` retains the Phase 9 signature and adds `observation_mode='goal'|'authorization'`, `risk_weights=None`, and the documented new fault identifiers. It must expose all old counters plus goal-observation provenance and planning work. Initial observations use allowed immutable state readers. Goal query selection uses public hypotheses and charged route feasibility probes, never world_index, private actual state, truth labels or future faults. Failure to separate hypotheses stays unresolved. Unknown commits stop immediately. Read receipt semantics remain unchanged.

`query_v10.QuerySession(case)` consumes unique paid query IDs incrementally without rerunning previous queries. Public functions `selection_system(protocol, objective)`, `selection_payload(case, remaining_ids, observations, protocol, objective, representation='source')`, `selection_schema(remaining_ids, protocol, limit)`, and `parse_selection(raw, remaining_ids, protocol, limit)` support protocols `full`, `batch`, `next`; objectives `diagnostic`, `execution`; representations `source`, `graph`, `padding`. `consume(ids)` executes only selected atomic queries. `result()` returns the v9-compatible diagnostic and authorization evidence fields plus counts. `stop_ready('fixed'|'diagnostic'|'authorization')` never calls an interpreter. Repeated, out-of-catalog, empty and over-limit selections fail rather than being repaired.

The full protocol returns `order` for all remaining IDs. Batch returns `queries` with 1..limit unique IDs (limit at most 4). Next returns one `query_id`. Padding matches the graph representation character length with explicitly inert content; it is not claimed to match tokenizer cost perfectly. Models see only public source and paid observations, no independent truth.

## Independent synthetic reference

An independent author uses only frozen truth_v6/v7 plus previous datasets to author 24 new cases in 12 families, two variants each. Include goal-only uncertainty with safe informative reads, multistep observation, hidden nonseparable alternatives, denied operations, incomplete original runs, competing legal routes, and receipt-sensitive recovery. Record all four typed outcomes and structural nonduplication, including minority classes. Hold production authors away from new generator/data until production freeze. Do not revise cases based on model outcomes or controller wins. Prior Phase 7/8/9 cases remain regressions.

## Experimental contract

Main acquisitions: each new case and both approved models, six cells: full diagnostic/source; batch diagnostic/source; next diagnostic/source; next execution/source; next execution/graph; next execution/padding. Up to 8 atomic queries per acquired stream. Full takes one request; batch at most 8 and next at most 8, ending on protocol failure or catalog exhaustion. No automatic retry. Dynamic requests and raw outputs are saved before parsing, with restart-safe dispatch identities and a shared locked inherited budget ledger. All spending beyond the $6 campaign bound is blocked. Source/graph/padding effects remain exploratory.

Offline query endpoints at budgets 1,2,4,8 and stop modes fixed/diagnostic/authorization; compare frozen baseline-first heuristic and seeded random under the same catalogs. A model policy that stops on invalidity retains previously paid evidence but acquires no guessed fallback. Report stream failures, valid decisions, spent calls, steps, proved intrinsic unknown and unresolved budget unknown separately.

Acquisition collects each stream up to eight paid atomic queries to support matched-prefix evaluation. Offline policy replay actually stops interpreter invocations at its declared predicate; it does not merely compute a potential stop position. All acquisition API expenditure remains charged in full, including later decisions that an earlier-stopping deployment would not request. Any prefix-specific model-call accounting is scenario attribution, not a claimed reduction of this campaign's invoice. Protocol full/batch/next comparisons also change feedback frequency and output burden; report first-decision validity separately and do not attribute the whole effect solely to schema complexity.

Interface: all new and prior Phase 7/8/9 cases, world by world, Phase 9 and new observation variants, observation budgets 0,1,2, planning budget512, quota16; none/transient_before/known_after/double_transient_before faults. At least the authorization-only control and goal-observation arm have exact matched settings. Separate preflight-off diagnostic control.

The exact interface grid has six arms: v9 at observation2; v10 authorization-only at2; v10 goal at0,1,2; v10 authorization-only/preflight-off at2. The lower observation budgets are goal-arm sensitivity checks, not matched comparisons to lower-budget v9 arms. All six share planner512/quota16. Wire schemas use documented array length bounds; uniqueness is enforced by the stricter local parser, since it is not a documented supported wire constraint. Known pre-I/O budget rejections count as decision attempts but not model requests; uncertain transport outcomes retain reservation bounds.

Integrated: new cases, acquired/control streams at budgets2 and8, fixed versus authorization stop, planner budgets128/512, same controller and quota16, none/transient_before faults. The runtime receives only completed paid original evidence. Count query work, goal observations, planning and real calls separately; supplied-evidence mode must have zero hidden audit calls. Do not call the work counters total CPU or monetary cost.

Recovery: new cases, all worlds, priority/calls/risk, planner512, observation2, three weight vectors (default read0/write1/delete2/emit8; uniform mutation1; write-heavy read0/write4/delete4/emit1), and none/transient_before/known_after/mixed_known_then_ambiguous/late_ambiguous plus two new operation-based faults. Freeze exact new fault semantics in recovery documentation before acquisition.

## Analysis and claim boundaries

Primary unit is family, not expanded execution condition. Use paired family-equal means and 10,000 bootstrap resamples, seed10101, exploratory unadjusted intervals. Report new and old strata separately. Primary metrics: completion difference for goal observations; per-decision and per-stream validity; authorization evidence coverage; realized query savings at unchanged completion; recovery completion/call/risk Pareto comparisons. All invalid, exhausted and negative conditions remain. Frozen cases cannot become new evidence again in later rounds.

A new round succeeds as research if the mechanisms and limitations are measured faithfully; positive improvements are not required. No claim of real-world Skill safety, general injection defense, externally preregistered findings, or benefit from graph structure beyond the tested representation.

## Verification and release

Test first with independent toy programs. Review before freeze. Freeze production and plan before materializing heldout; freeze data before API calls. Independently check all proved labels and runtime evidence provenance. Replay runtime conditions in no-network, read-only, nonroot containers, preserving module hashes and outputs. Check old file hashes, every reservation and dispatch, frozen inputs, deterministic analysis, full test suite and exact GitHub commit CI. Publish new Phase 10 files only to the original private repository; retain the archive tag.

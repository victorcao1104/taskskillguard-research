# Phase 10 paid selection and stopping protocol

This module is prospective production code for synthetic experiments. It uses
the frozen Phase 9 atomic query catalog, counted interpreter, and conservative
diagnostic reduction. It never calls a complete solver. It reads the public
`source`, `routes`, `worlds`, `goal`, and `catalog_closed` case fields; independent
`program`, truth annotations, and actual-world selectors are not inputs.

## Selection interface

`selection_system(protocol, objective)` returns the shared workflow semantics,
one strict output contract, and one selection objective. Protocols are:

| Protocol | Response | Valid selection |
|---|---|---|
| `full` | `{"order":[...]}` | Every remaining ID exactly once |
| `batch` | `{"queries":[...]}` | 1..limit unique remaining IDs; limit is an integer 1..4 |
| `next` | `{"query_id":"..."}` | Exactly one remaining ID |

`selection_schema(remaining_ids, protocol, limit)` supplies the response schema.
Its `limit` must be a positive integer; only batch uses it to constrain the
response size, and only batch restricts it to four. A full response is not
truncated to limit. Responses with extra fields, wrong types, duplicates, IDs
outside the remaining catalog, incomplete full permutations, empty selections,
or excessive batches fail validation.

`parse_selection(raw, remaining_ids, protocol, limit)` accepts the frozen v3 raw
response record/envelope. It preserves its validation diagnostics and prediction
and adds `selected_ids`. This list is empty on every invalid response. Duplicate
JSON keys, response incompleteness, refusals, and transport failures remain
invalid. There is no answer salvage, independent-truth repair, retry, or guessed
fallback. A stream terminated by invalid selection can retain its earlier paid
observations without acquiring additional IDs.

`diagnostic` asks for resolving candidate-axis labels. `execution` asks for
completed original authorization evidence in every public world, emphasizing
that globally resolved labels are insufficient. The selector sees public
hypotheses and can reason about them; no private actual state is supplied.

`selection_payload(case, remaining_ids, observations, protocol, objective,
representation='source')` returns canonical, sorted compact JSON. `observations`
must be the paid cache supplied by the caller, normally `session.observations`.
Its IDs must be in the public catalog and disjoint from remaining IDs. The
payload contains the public semantic fields, static candidates, remaining query
descriptions/IDs, paid observations, protocol, and objective. Building it runs
no interpreter. It does not validate an observation's truth or independently
reconstruct a missing observation. Callers must preserve provenance by using
the session cache, never supplying model-generated observations.

Representation variants all retain exactly the same public source and facts:

- `source` adds no auxiliary representation.
- `graph` adds a `representation` object with `kind='graph'`, deterministic
  static source `edges`, and a note identifying it as source representation.
- `padding` adds a `representation` object with `kind='padding'`, a note
  explicitly saying it is inert, and inert dot content. Its complete serialized
  payload has exactly the graph variant's Python character length for the same
  inputs, including when the graph is empty. It is not tokenizer-cost matching.

## Incremental execution

`QuerySession(case)` owns an independent snapshot of the public case and starts
with zero paid runs. Its `remaining_ids` list follows frozen catalog order;
`observations` is the paid query-ID-to-result dictionary. Both are independent
snapshots; mutating returned values cannot alter subsequent execution or proofs.

`consume(ids)` takes a nonempty list/tuple of unique remaining IDs. It validates
the complete selection before execution and raises `ValueError` for repeated,
already consumed, outside-catalog, empty, or malformed selections. Invalid
selection executes nothing. Valid IDs run exactly once each, in supplied order;
subsequent calls never rerun a previous prefix. Each ID constructs one fresh
semantic runtime from that query's world initial state. A base runs the original
or an alternate route; a suppression runs the original suppressing every
occurrence of one candidate site. Entered control, loop, suppressed, and failed
steps remain counted through the frozen runtime. `consume` returns `result()`.

`result()` returns independent snapshots of the v9-compatible fields:
`by_id`, `labels`, `decisions`, `proven`, `resolved`, `total_labels`,
`intrinsic_unknown`, `protocol_valid`, `diagnostic_codes`, `diagnostics`,
`executions`, `interpreter_steps`, `trace`, `observations`,
`authorization_evidence`, `budget`, `query_count`, `full_query_count`,
`all_queries_executed`, and `first_fully_resolved_at`.
For a session, `budget` is the number of consumed queries. Additional fields are
`budget_unknown` (unproved candidate-axis labels), `authorization_complete`, and
`completed_original_worlds` (sorted world indices). The counters describe work,
not total CPU or monetary cost. Result retrieval and reduction execute no query.

Diagnostic labels deliberately retain frozen committed-trace semantics for an
interrupted original. Such a run can prove a diagnostic authorization label
without proving all occurrences for runtime authorization. Only paid base
queries at route zero with `error is None` produce handoff evidence, including
explicit occurrence and all-occurrences-authorized facts for every candidate.
Goal failure alone does not withhold evidence if execution completed; a runtime
error does. Suppressions and alternate routes never supply original evidence.

## Sufficient evidence stopping

`stop_ready(mode)` is a pure check of cached evidence. It never invokes an
interpreter, solver, state reader, or new observation:

| Mode | Predicate |
|---|---|
| `fixed` | Always false; no evidence-triggered early stop |
| `diagnostic` | Every candidate-axis diagnostic label is proved |
| `authorization` | A completed paid original exists for every public world |

The authorization predicate requires every world's complete original facts even
when two observed worlds already prove an intrinsic mixed global label. It
requires complete evidence, not that every effect is authorized or the goal
succeeds. A failed original can prevent this stopping contract even after the
entire finite catalog is consumed. With no candidates, diagnostic stopping is
vacuously ready; authorization still requires paid completed originals.

Proved `unknown` has `reason='intrinsic'`; unresolved unknown has
`reason='budget'`. Stopping never converts budget uncertainty to intrinsic
uncertainty or guesses labels. This is a sufficient evidence contract, not a
claim of globally optimal stopping.

`evaluate_stream(case, ids, budget, stop_mode='fixed')` makes offline stopping
actual. `ids` is any unique in-catalog acquired stream, including partial or
empty streams. Budget is a nonnegative integer or `'full'`; the integer is
capped at stream length. The function validates the whole stream, then checks
the stopping predicate before each next atomic purchase. It never executes an
unused suffix. Invalid streams execute zero queries and return protocol failure.
The returned snapshot adds `requested_budget`, `stop_mode`, `stopped_early`, and
`stop_reason`. `stopped_early` is true only when evidence omits an otherwise
budget-eligible stream query; reaching readiness on the last eligible query
alone does not claim savings. Reasons otherwise identify budget exhaustion,
stream exhaustion, or invalid protocol. Paired fixed/stopping comparisons use
the same acquired order and have independently counted actual paid work.

## Verification boundary

Independent toy tests exercise all tiny query permutations/prefixes against
frozen v9, real once-only interpreter calls, failed originals, intrinsically
unknown labels, all-world handoff, actual avoided suffixes, strict response
validation, and public-only representations. These checks use no Phase 10
generator, new heldout data, or reference-author output. No conclusion about
heldout effectiveness is implied by production tests.

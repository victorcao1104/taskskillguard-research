# Phase 10 independent outcome review

Review date: 2026-10-16. Outcome review began after the coordinator recorded the
74-file production and 76-file data freezes. This reviewer had previously
reviewed production without reading the new reference, heldout or model results.
This outcome review changes no production code, case, label, acquired response,
or result. No API, network, Git or Docker operation is performed by the reviewer.
Both production/data freeze hash verifications pass (74 and 76 files). The
materialized heldout digest is
`215646cd12f42b27bb32bebdceae04201060f4c21c6c74b0eef71ad98d870de8`,
matching the retained first-pass reference digest.

## Completed interface and recovery checks

All result chunks were read through `phase10_common.read_chunks`, which verifies
their row count and content digest. The semantic audit records all 1,944
reference/production comparisons equal across 120 cases and 216 worlds, with
AST, candidate coverage, complete facts and aggregate labels also equal.

All 864 matched authorization-only conditions preserve every old v9 result
field exactly. At observation budget 2, goal observations produce 24 new-case
completion gains, 16 old-case gains, and no losses relative to authorization-only.
The 24 new gains are two variants times four faults in each of three families:
`transform_pipeline`, `two_gate_relay` and `optional_overwrite_fork`. Their
authorization-only failure is `no_feasible_route`; one, two and one goal
observations respectively establish the favorable original-world route.

The 16 old gains are precisely the four `p8_nested_noop_observer` variants in
world 0 under all four interface faults. This matches the 16 robust-preflight
losses documented in the Phase 9 report. They are regression recovery evidence,
not 16 independent new examples.

| Stratum | Authorization-only, obs 2 | Goal, obs 2 | Family-equal difference |
| --- | ---: | ---: | ---: |
| New: 12 families | 96/192 conditions; 55.56% family-equal | 120/192; 66.67% family-equal | +11.11 percentage points |
| Prior: 36 families | 472/672 conditions; 74.07% family-equal | 488/672; 75.46% family-equal | +1.39 percentage points |

Raw condition completion fractions differ from the family-equal estimand
because families have different world counts. Expanded faults and lexical
variants must not be treated as independent families. Goal-arm observation
budgets 0 and 1 are sensitivity analyses, not comparisons against matching
lower-budget authorization controls. On new cases they complete 80 and 112
conditions, respectively. The authorization-only preflight-off diagnostic
completes 130/192 new conditions; the goal-observation mechanism does not
dominate that diagnostic on completion alone.
The two deliberately concealed families remain unresolved in all 32
goal/observation-2 interface conditions: zero initial observations, zero
completions, and `no_feasible_route`. No actual-world identity was substituted
for unavailable observations.

Across all 5,184 interface and 3,024 recovery conditions, the reviewer verified
zero unauthorized effects and duplicate effects, and every execution within
its declared quota, planning and observation budgets. All 532 recovery runs
with an ambiguous commit stop with the ambiguous event as the terminal trace
event and attempt failure; none is counted as authorized goal completion or
starts another selection round.

Fault-blindness checks compare otherwise identical runs before any fault can
be observed. Observation logs match across 3,888 interface and 2,592 recovery
paired comparisons. Goal-probe logs match across 3,240 interface and 2,592
recovery comparisons. First preflight selections match across 3,240 interface
and 2,592 recovery comparisons. The preflight-off diagnostic's first *recovery*
selection is after an actual attempt and legitimately differs with observed
faults; it is excluded from pre-fault selection equality.

The reviewer recomputed all 3,024 actual risk scores from charged authorized
trace events and their declared weight vector. All matched. For all 864
operation-dependent fault conditions, fresh eligible matching-operation traces
agree with the specified first-emit or second-write trigger and recorded
injection identity. Reuse, denied/conflicting requests and exhausted quota do
not count as target operations.

Completed container artifacts were independently compared with their VM chunks:
all 5,184 interface and 3,024 recovery rows are exactly equal. The 21 interface
and 13 recovery launch plans retain no-network, read-only, nonroot settings and
no host mount. This is verification of retained launcher artifacts and outputs;
the reviewer did not invoke Docker.

## Recovery result interpretation

The observed policy tradeoff reverses with fault position/operation and weight
vector; a uniform recommendation for the risk policy would be unsupported.
The following are raw totals across 48 world/variant conditions per cell, using
the default weights, not independent-sample estimates:

| Fault | Calls policy completed | Risk policy completed | Calls charged: calls/risk | Exposure: calls/risk |
| --- | ---: | ---: | ---: | ---: |
| none | 30 | 30 | 88 / 116 | 180 / 110 |
| late ambiguous | 20 | 10 | 86 / 96 | 180 / 88 |
| first emit ambiguous | 14 | 28 | 70 / 116 | 158 / 110 |
| second write ambiguous | 22 | 8 | 78 / 74 | 158 / 52 |

Default risk ranking often selects the longer write-only route and avoids an
emit. That helps with first-emit ambiguity but can encounter a second-write or
late-mutation fault before finishing. With uniform mutation or write-heavy
weights, risk-policy aggregate completion/call results match the calls policy
in these recorded cells. Exposure is a declared weighted surrogate, not a
probability of harm or a monetary cost; early ambiguous stopping can itself
reduce measured exposure and must not be interpreted as successful avoidance.

## Acquisition integrity and failure attribution

All 288 registered streams and 1,587 dynamic requests were reconstructed from
their public cases and preceding paid observations. The reviewer verified exact
saved request equality, raw response parsing, dispatch hashes, acquired unique
query orders, session evidence, and each decision's conservative cost/basis.
The fingerprints of all 1,587 raw request bodies were independently recomputed;
all agree with saved request hashes. Private `program`, `truth` and actual
`world_index` fields are absent from all 1,587 model payloads.
No repaired answer or fallback query was found. Nineteen of the 25 invalid
streams retain a previously acquired valid prefix; this trusted evidence remains
usable even though the whole stream failed.

The acquisition has 1,562 valid decisions and 263 valid complete streams. All
25 invalid outcomes belong to Luna: 11 HTTP 400 `invalid_prompt` responses,
one incomplete response, and 13 `MULTIPLE_OUTPUT_TEXT` failures. The latter are
response-envelope failures: each contains two assistant output-text messages,
five with identical texts and eight with differing texts. None is a local
query-ID, uniqueness or cardinality/schema failure. Both identical and different
multiple texts fail the same prospectively fixed single-output contract; no
text was selected, concatenated or salvaged after observing results. The retained
HTTP metadata does not establish a more specific cause for `invalid_prompt`.

Mini has all 144 streams and 842 decisions valid. Luna has 119/144 whole streams
and 720/745 decisions valid. Per-decision validity has an adaptive denominator;
the first-decision and whole-stream measures must remain separate. In particular,
shorter decisions do not demonstrate improved validity in these results.

| Model/cell | First decision valid / 24 | Whole stream valid / 24 | Valid / attempted decisions |
| --- | ---: | ---: | ---: |
| Luna full diagnostic | 23 | 23 | 23 / 24 |
| Luna batch diagnostic | 21 | 20 | 41 / 45 |
| Luna next diagnostic | 23 | 15 | 149 / 158 |
| Luna next execution | 24 | 21 | 171 / 174 |
| Luna next graph | 24 | 21 | 171 / 174 |
| Luna next padding | 23 | 19 | 165 / 170 |

Every request has one corresponding new ledger reservation: 1,576 settled and
11 still reserved, with the retained reservations covering the HTTP rejections'
unknown billing. Their sum equals all recorded decision costs:
**$1.504516700**. The inherited ledger is an exact byte prefix. Cumulative
accounting is **$18.887809250**, below both the $23.383292550 effective campaign
ceiling and $29.551575125 cumulative cap. These are conservative local bounds,
not invoice totals; no unresolved reservation was released to improve cost.

## Query stopping and integrated evidence

All 4,032 query-result rows exactly match fresh offline `evaluate_stream`
re-execution. All 29,354 proved candidate-axis entries across those rows match
independent truth; this is an expanded condition count, not 29,354 independent
labels. Every handoff fact was checked against its cached original-base trace:
the base exists, its error is null, occurrence matches trace membership, and
the authorization bit covers every traced occurrence. Steps and query counts
match the cached paid observations. Prefix decision validity, request/attempt
counts and conservative attributed costs match the decisions actually needed
before their stopping predicates.

All 10,752 integrated jobs receive precisely the matching query row's trusted
authorization evidence and public case fields. Their runtime evidence source is
`trusted_queries`, with zero audit calls and steps. All remain within budgets
and have zero unauthorized or duplicate effects. All 5,376 matched
fixed/authorization-stop pairs have **identical complete runtime result
dictionaries**, not merely equal completion flags. There are no completion
wins or losses. Of these, 1,508 scenario pairs omit query work, including 796
pairs where both executions succeed. The summed reduction is 6,596 queries
over the expanded workflow scenarios.

That last sum repeats the upstream query workload across world, fault and
planner settings: it is not a claim that the campaign physically avoided 6,596
unique interpreter executions or refunded API calls. The independently executed
query-prefix replays genuinely omit their suffix. All acquired model requests,
including later decisions absent from a stopping deployment and unknown-billing
reservations, remain charged to the campaign. Full/batch/next differ in output
burden and feedback frequency, and graph/padding differ in tokenization despite
character-length matching; these controls do not isolate every causal factor.

Counting each case/pipeline/budget only once confirms 672 unique fixed versus
authorization-stop comparisons. At budget 2, 19 of 336 pairs save 19 queries
and 107 steps in total. At budget 8, 176 of 336 pairs save 832 queries and 7,010
steps. These 195 saving pairs and 851 total query differences are distinct from
the repeated integrated-scenario totals above. Even unique replay differences
are comparisons of two retained executions, not claims that acquisition never
executed the suffixes.

The integrated container's 10,752 retained rows exactly equal the local VM
rows. In total, all 18,960 runtime conditions have matching retained output
across 78 containers (21 interface, 13 recovery, 44 integrated). No container
was launched by this reviewer.

## Analysis and report checks

The saved analysis reproduces the review's 24 new gains, 16 historical gains,
5,376 identical-completion pairs, 1,508 saving pairs and 6,596 expanded query
savings. Its primary new-family goal-observation estimate is 0.111111 with
10,000-resample interval [0, 0.236111], based on twelve family means. Separate
new/old strata, preserved invalid streams, unconditional evidence coverage,
intrinsic-versus-budget unknown distinctions, and fault/weight-dependent policy
tradeoffs are maintained. No production or data revision is requested.

The draft report required a chronology clarification, now corrected: reference cases were
independently authored and first-pass generated before production freeze, kept
from production authors, then materialized unchanged after freeze. They were
not first authored after the production freeze. The revised report also
correctly separates the 13 multiple-output-text envelope failures from selection
schema failures, reports all integrated/container results, and separates unique
query replays from expanded deployment-scenario totals and campaign cost.

Reported test chronology remains 1,305 passed / 4 skipped / 150 subtests for
the retained full-suite run, followed by 11 passing focused analysis tests.
Later added controls are not represented as part of the earlier full run.
The final whole-release hash audit and exact-head CI remain the coordinator's
release responsibilities, outside this outcome review.

The final report's eight-row end-to-end table was independently checked against
integrated rows: every completion, query, planning and gateway-call total
matches, as do all eight budget-2 null-completion cells and their query totals.
The table preserves the strong heuristic: Mini execution/graph match its 30/48
completion at budget 8 but use more query calls; Luna's lower query totals come
with 29/48 completion and stream failures. The three fault-crossover statements
also agree with the audited recovery outcomes. No model-superiority claim is
supported or implied by these checks.

**Final disposition: no unresolved material correctness or reporting issue was
found in the reviewed Phase 10 outcomes and final report.** This document is
ready to lock for release verification. No production or data file was edited
or revised during this outcome review. Publication, final baseline-file hash
verification and exact-head CI are still coordinator-owned release steps;
this disposition does not assert that they have already completed.

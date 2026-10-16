# Phase 9 offline analysis implementation

This document records the analysis implementation and its limits. Outcome
interpretation belongs to the final report after all frozen inputs are complete.
The analysis author read the declared interfaces and analysis plan first and
used only hand-authored toy evidence until production and data freezes were
confirmed. No API call, prompt change, production change or heldout revision is
part of this implementation.

`scripts/analyze_phase9.py` reads the immutable raw bundle and produces
`results/phase9/analysis`. It imports the unchanged Phase 8 serialization-neutral
counting/bootstrap helpers, with the Phase 9 seed explicitly set to 9009. Every
saved result uses the Phase 9 immutable writer. A rerun must produce exactly the
same bytes. Existing output is checked before writing any part of a bundle.

## Estimands and denominators

The primary population consists of the 24 new cases in 12 authored families.
Old cases are execution regressions, identified separately by split. Labels are
scored against the independent truth table. Every planned acquisition is retained;
missing and invalid records contribute incorrect predictions at every expected
site and axis. Validity-conditional label accuracy has its own explicit candidate
denominator. Unknown and not-applicable have separate confusion rows, recalls,
false-positive counts and denominators.

The factorial table crosses two deduplication levels, two tool-fact levels and
two reducer levels. Both reducers consume the same response. A main effect is
the mean high-minus-low difference over the other factors. A two-factor
interaction is the averaged difference of differences; the three-factor
interaction is the difference of two two-factor interactions. The reducer
contrast is a dependent within-response processing comparison, and supplying
tool facts adds computation. Neither is an independent randomized acquisition.

Query labels count as resolved only when their saved decision carries a proven
flag. A proven intrinsic unknown counts; an unknown caused by the query budget
does not. Every proven label is compared with independent truth, and an unsound
proof aborts analysis. Primary queries exclude repeat acquisitions. Query count,
entered interpreter steps, first full-resolution position and full-catalog work
remain distinct metrics. The graph audit checks the saved Q1 payload after
removing its graph against Q0 and recomputes graph edges from source alone. It
records graph and prompt byte lengths; API token counts are reported separately.

Runtime comparisons pair case, world, fault, quota and every control setting
except the intervention named in the contrast. Recovery policies share planner
and cache settings. Calls and other costs are reported over all paired
conditions and separately over conditions where both policies succeed. Every
completion win and loss retains its condition identifiers, failure reasons,
global uncertainty, unresolved gate state, observation count and initial route
selection. V8 comparisons use the V8 control in the same Phase 9 interface grid;
they are descriptive joint policy/interface changes.

Primary intervals use 10,000 paired family bootstrap resamples, seed 9009,
percentiles 2.5 and 97.5. Candidate accuracy is averaged within case and then
within family; runtime world-condition differences are averaged within family.
Families receive equal weight. Pooled fault results preserve their dependent
condition interpretation. Repeats are stability diagnostics, not extra samples.
These intervals are exploratory and unadjusted for multiplicity; they do not
establish general safety or a population of independent mechanisms.

## Unknowns, costs and failure records

The observation strata use permitted initial file/grant projections, not the
actual hidden world index. They distinguish singleton, fully observable,
hidden-disagreement and observationally equivalent cases. Gate evidence tables
separate true global disagreement from extra unknown labels on nonunknown
truth, unresolved inactive sites, planning exhaustion and ambiguous commits.
The former is a truth comparison, not a claim that every unknown in a
partially observed run has a uniquely identifiable cause.

Supplied-query integration is checked to have zero audit interpreter calls and
zero audit steps. Paid queries and API acquisition occur once per case/order;
those facts are reused across runtime world/fault conditions. Summed runtime
query costs therefore describe independent execution scenarios, not actual
campaign spending. Charged calls, observation queries, planning units, audit
work, cache counts, modeled latency and synthetic risk are not collapsed into a
single favorable weight. Usage-based dollar totals remain conservative bounds,
with known-cost/token denominators and the inherited budget ledger retained.

Structured failures cover acquisition, typed labels, facts, unresolved queries
and execution. They point to raw artifacts rather than copying execution traces
or query observations. A protocol failure is never repaired using truth. The
runtime's robust feasibility rule can reject a route that would succeed in one
actual world. Authorization-focused observations do not necessarily resolve
goal-only uncertainty; preflight and observation utility must therefore be
reported with their losses, not as universal improvements.

## Figures and verification

`scripts/plot_phase9.py` creates five standard Matplotlib figures as PNG and PDF:
factorial typed accuracy, query efficiency, paired gate/preflight/observation
contrasts, recovery tradeoffs, and paid-query execution completion. Source values
and the analysis-summary hash accompany the figures. Creation timestamps are
removed from PDF metadata, and rerendered bytes are checked by the immutable
writer. Figures use no image generation.

Toy tests exercise family weighting, factorial interactions, missing/invalid
denominators, proven versus budget unknown, unsound-proof rejection, equal-budget
pairing, all-condition and both-success costs, explicit losses, graph source
equivalence, repeat equality, hidden observations, supplied-query audit charging,
unknown categories and byte-identical analysis/figure reruns. The first eight
tests failed at the explicit missing-module assertion before implementation.
Further controls were observed failing before their corresponding additions.
Full-suite and final production replay results are recorded by the release
verification after inputs are complete.

The analysis author's first broad run used `--basetemp
work/p9analysis-full-suite` and ended with 1,179 passing tests, four skips,
150 passing subtests and four failures. All four were `FileNotFoundError`
while older Phase 3 fixtures wrote long raw-response paths under Windows:
`test_execute_uses_exact_saved_requests_phase_parse_and_same_twenty_dollar_total`,
`test_credit_exhaustion_stops_after_one_attempt_and_restart_does_not_retry`,
`test_invalid_actual_followup_final_remains_unresolved`, and
`test_local_replace_retries_sharing_violation_without_repeating_client_call`.
All 14 tests in `tests/test_resume_v3.py` passed after changing the temporary
directory to `work/a`. No existing implementation was changed. This first
attempt did not request JUnit XML. A redundant second broad run was interrupted
when the release owner reported the completed authoritative full-suite run;
it provides no completion evidence. The authoritative result is retained in
`results/phase9/validation/tests.xml`.

Final offline verification completed after all inputs were available. The
analysis command ran in two separate Python processes; both returned 96 cases,
288 received primary responses, 257 valid primary responses, and runtime counts
3,728 / 3,864 / 2,208 for interface / recovery / integration. The second run
passed all immutable byte comparisons. Plot generation also ran twice in
separate processes with byte-identical PNG, PDF and source-value outputs. All
five PNGs were visually inspected for legibility and clipping. The final focused
analysis scope passed 13 tests. No API request was made by these checks.

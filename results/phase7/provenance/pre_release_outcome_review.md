# Phase 7 independent outcome review

2026-10-16. This report reviews saved outputs without changing frozen code,
fixtures, protocols, policies, or tests. No provider calls were made by the
reviewer. The saved semantic, recovery, model-acquisition, analysis, and integration
outputs are reviewed below. Final release packaging and remote CI are separate
coordinator checks.

## Semantic and execution audit

- The amended semantic summary contains 72 cases, 230 candidate sites, 94 worlds,
  and 868 differential executions. All 868 comparison rows agree. All recorded
  typed-label, collapsed-label, and per-world-evidence checks agree.
- Full candidate content and unique-ID coverage agree for every case. The two
  preserved order-only discrepancies are explained in `phase7_review.md` and
  `phase7_amendment.md`; the first failed audit was not overwritten.
- Recovery contains 6,016 rows: 94 worlds × 2 quotas × 8 fault settings ×
  2 selectors × 2 policies. All 1,504 applicable legacy-equivalence rows agree.
- Saved host and container result files are byte-identical. All results have
  zero unauthorized effects and zero duplicate effects; no result exceeds its
  quota or four actual attempts. The containers are batches, not 6,016 separate
  isolation environments.
- None of the 3,008 matched policy comparisons loses authorized success under
  `safe_retry`. This is an observation about this finite grid, not a proof of
  dominance for arbitrary workflows or fault schedules.

The semantic truth distribution reinforces the need to distinguish label spaces:
the 70 held-out sites have authorization counts yes/no/unknown/not-applicable
44/2/14/10, current-route counts 32/6/18/14, and catalog counts 12/26/22/10.
Changing the label inventory alone is not a model improvement. These truths are
computed by exhaustive bounded evaluation, not inferred from model outputs.

## Recovery comparisons and costs

The following table is for the held-out `search_equal` selector at quota 16.
Each cell covers **38 world conditions from 24 cases in 12 families**, not 38
independent new tasks. Arrows show legacy → safe-retry. Calls are total charged
actual calls across all 38 conditions; simulation work is separate.

| Fault | Authorized successes | Calls | Fault triggered, each policy |
|---|---:|---:|---:|
| none | 34 → 34 | 134 → 122 | 0 |
| transient before first eligible mutation | 28 → 34 | 154 → 154 | 32 |
| known outcome after first eligible mutation | 30 → 34 | 126 → 122 | 32 |
| ambiguous outcome after first eligible mutation | 4 → 4 | 90 → 86 | 32 |
| transient before second eligible mutation | 32 → 34 | 168 → 140 | 18 |
| known outcome after second eligible mutation | 32 → 34 | 158 → 122 | 18 |
| ambiguous outcome after second eligible mutation | 16 → 16 | 124 → 112 | 18 |
| two consecutive precommit transients | 26 → 34 | 151 → 186 | 32 |

At quota 8, held-out `search_equal` results are unchanged except the two delayed
safe-fault conditions: legacy success is 28 rather than 32, while safe-retry still
succeeds on 34. Calls are 152 → 140 for delayed transient and 142 → 122 for delayed
known outcome. Thus some apparent policy gain depends on the quota constraint.
For `first_feasible`, delayed transient at quota 8 yields 30 → 32 successes;
at quota 16 it yields 32 → 34. Selector and quota must accompany any headline.

The repeated-transient condition does **not** establish universal cost repair.
Even on the 26 held-out `search_equal` pairs where both policies succeed, charged
calls rise from **110 to 133** at both quotas. Across all 38 pairs, planning steps
drop from 150 to 76 while actual calls rise from 151 to 186. These are different
resources; they should not be combined without an explicit cost model.

Saved traces explain this increase. After two safe transient errors, safe-retry
keeps the original route for a third attempt. It may then encounter a previously
unobserved grant denial or receipt conflict, or finish a longer original route.
Legacy has already switched to a cheaper public alternative. For example,
`p7-branch_bundle-0`, world 0, has 5 legacy calls versus 7 safe-retry calls; the
extra original attempt reveals `grant_denied` before the final alternative.
`p7-receipt_chain-0`, world 0, similarly has 3 versus 5 calls because that attempt
reveals `receipt_conflict`. The increased cost is therefore not explained only
by safe-retry recovering additional cases that legacy abandoned.

Safe-retry's benefits also combine two changes: it retires an observed permanent
original failure sooner, and preserves a safely failed route for retry. This
experiment evaluates that combined policy; it does not isolate each component's
causal contribution.

## Failure attribution

The four held-out nonambiguous safe-retry failures at quota 16 are world 1 of
both seeds of `p7_permission_split` and `p7_deferred_report`. Their original paths
hit a grant denial, and every available alternative is also infeasible under the
trusted grants. They should not be presented as failures to retry a feasible
authorized route.

Ambiguous outcomes intentionally stop. At the first eligible mutation, 32 of
38 held-out conditions encounter the injected ambiguity; at the second, 18 do.
The low success counts under those settings measure the stop rule and fault
reachability, not a failure to perform an allowed safe retry. A physical goal
reached before an ambiguous or other error is not counted as authorized completed
success. Conditions that never trigger the scheduled fault must remain visible.

Untriggered conditions and `none` are different concepts. The `none` setting has
zero scheduled faults and a completed empty schedule; delayed faults may have
one scheduled fault that was never reached. The saved diagnostics preserve this
distinction, and narrative claims should preserve it too.

## Statistical and generalization limits

Micro success counts and family-balanced effects differ. At quota 16 with
`search_equal`, first-transient success improves by 6/38 in raw world counts,
while the family-balanced estimate is +0.125 with bootstrap 95% interval
[0, 0.25]. Repeated-transient success improves by 8/38 in raw counts, while the
family-balanced estimate is +0.1667 with interval [0.0417, 0.2917]. Its mean-call
effect is +1.0208 with interval [0.625, 1.3958]. These are exploratory intervals
across many comparisons, not confirmatory significance tests.

There are only 12 new structural families with two seeds each, all in the same
finite language. The old 48 cases are regression controls. Results do not establish
generalization to new languages, arbitrary plugin code, external services, or
arbitrary failure positions. The trusted permission/receipt gateway enforces the
reported side-effect safety; that protection cannot be attributed to a language
model. Container reproduction adds environment evidence but does not convert a
pure in-memory language into an evaluated hostile-code security boundary.

## Reviewed input fingerprints

| Artifact | SHA-256 |
|---|---|
| `semantics/summary_v2.json` | `094db058c5589581c0c21c868cefa65b4245b6b4e44126a3884972b3a40e24c6` |
| `recovery/vm_results.jsonl` | `02ed716080789e411268944c9112b32d54b9f980a3ee737c44ebdf3f8179339e` |
| `recovery/container_results.jsonl` | `02ed716080789e411268944c9112b32d54b9f980a3ee737c44ebdf3f8179339e` |
| `recovery/legacy_equivalence.jsonl` | `8e74c83810a46efc108680c05d10baf2cbb4bb79d2b3bb4822541968d8761986` |

Paths in this table are relative to `results/phase7/`. These stage-level hashes
complement, and do not replace, the final release verification.

## Acquisition completeness and post-acquisition repair

Independently counted 480 planned jobs, 480 unique planned request hashes, 480
raw response files, 480 per-job records, and 480 dispatch intents. Recomputed
every saved raw request hash and reparsed every response: all match the planned
request and saved parsing result. All provider statuses are `completed`.

There are 477 protocol-valid conditions, including 429 of the 432 main conditions.
The failures are two GPT-4.1 mini B2 regression responses missing candidates and
one GPT-6 Luna B0 regression response with multiple output-text blocks. None is
a truncation or transport failure. All three remain incorrect in the planned
accuracy denominator. No response needed to be retried, spliced, or selected.

The acquisition process nevertheless exited with an infrastructure error when
an unlocked progress-cost read iterated the budget dictionary concurrently with
a reservation write. The thread-pool exit waited for the already-submitted tasks,
which explains the complete saved grid despite that process failure. Reviewed
the new `BudgetV7Locked`: its property acquires the same reentrant lock used by
reservation/settlement. Reviewed the offline finalizer: it revalidates saved
responses and certificates and writes aggregate files without a provider call.
The existing frozen acquisition and budget code remain unchanged. This repair
occurred after acquisition and must not be called a prospective model-protocol
amendment; it is an explicitly recorded aggregation repair.

The inherited ledger prefix is byte-identical. All 480 current reservations are
settled, while all 184 inherited unresolved reservations remain retained. The
conservative Phase 7 usage cost is **$0.2724299**, cumulative conservative exposure
is **$16.66712065**, and remaining authorization under the $29.551575125 cap is
**$12.884454475**. These are conservative accounting amounts, not a provider
invoice. The prepared upper reservation bound was $3.43027275; actual observed
usage was smaller. All request hashes are distinct, so per-condition totals do
not double-count a shared response in this campaign.

## Model results and certificate failure

Independently recalculated the saved analysis's 90 metric groups from raw saved
observations and reference labels, including correctness, missing predictions,
unknown counts, and not-applicable counts. No discrepancy was found.

Held-out micro accuracy on the **shared collapsed label space**, shown as correct
sites out of 70, is:

| Model | Protocol | Authorization | Current-route required | Catalog required |
|---|---|---:|---:|---:|
| GPT-6 Luna | B0 | 53 | 41 | 33 |
| GPT-6 Luna | B1 | 57 | 44 | 35 |
| GPT-6 Luna | B2 | 59 | 42 | 28 |
| GPT-4.1 mini | B0 | 45 | 15 | 28 |
| GPT-4.1 mini | B1 | 48 | 26 | 20 |
| GPT-4.1 mini | B2 | 49 | 32 | 26 |

On the **four-value typed space**, B1/B2 results are:

| Model | Protocol | Authorization | Current-route required | Catalog required |
|---|---|---:|---:|---:|
| GPT-6 Luna | B1 | 56 | 34 | 21 |
| GPT-6 Luna | B2 | 56 | 32 | 20 |
| GPT-4.1 mini | B1 | 48 | 10 | 13 |
| GPT-4.1 mini | B2 | 48 | 16 | 16 |

These results do not show a stable cross-model improvement from executable
evidence. Luna's two typed necessity axes decline; mini improves from a low
baseline. B1 versus B0 also changes wording, label names, and applicability
instructions, so an observed gain cannot be attributed solely to adding one
label. The frozen family-balanced intervals should accompany comparisons;
site-level percentages do not substitute for that estimand.

Applicability mistakes are substantial. On held-out current-route judgments,
genuine unknown recall is 0/18 for mini in both B1 and B2, and 1/18 for Luna in
both. Mini incorrectly predicts not-applicable on 54 sites in B1 and 49 in B2;
only 14 sites are truly not-applicable. Its B1 typed current-route accuracy of
10/70 consists entirely of correctly recognized not-applicable sites. Therefore
an increase in collapsed accuracy is not evidence of robust necessity reasoning.

Most importantly, **no complete main B2 certificate is accepted**: 0/144 across
both models and both splits, including 0/48 held-out conditions. Complete-condition
selective accuracy is undefined at zero coverage, not 100%. Only five of 460 main
candidate judgments are individually accepted, all in regression data (four Luna,
one mini); held-out candidate acceptance is 0/140. Six regression responses have
all labels correct but still fail the executable facts. Direct comparison with
saved reference facts finds mismatched legal-route lists, avoiding-route lists,
suppression outcomes, baseline outcomes, occurrence, and authorization facts.
The rejection is not just an output-format problem.

This checker exhaustively computes expected facts. Any correctness of accepted
items is attributable to that trusted checker, and the zero complete acceptance
coverage makes a usable model-certificate benefit unsupported here. It would
be misleading to describe rejection of everything as improved model reasoning.

Evidence also increases output burden. Across the 72 main cases per model, B1
versus B2 output tokens rise from 7,218 to 20,163 for Luna and 6,721 to 19,498 for
mini. Conservative usage costs rise from $0.017024 to $0.0250535 and $0.0537392 to
$0.0791648 respectively. These descriptive costs do not include a monetized
deterministic-checking cost.

Repeat labels are not consistently stable. Of six three-run groups per
model/protocol, all labels match in 0 Luna B1 groups, 0 Luna B2 groups, 2 mini B1
groups, and 3 mini B2 groups. Pairwise label agreement is respectively 3/18, 4/18,
10/18, and 11/18. Those figures compare labels only; full B2 evidence equality is
a stricter and different measure. Repeats were preselected, and no answer was
chosen because it agreed with another run.

## Integrated execution and attribution

The integrated output contains 7,776 rows: 5,184 raw-model, 1,728 certified, and
864 deterministic-solver conditions. All operate in world 0 at quota 16 under
the three planned fault settings. Host and container files are byte-identical;
16 successful batch containers are recorded. No integrated result has an
unauthorized effect, duplicate effect, quota violation, or more than four actual
attempts.

Every certified condition has an empty original-route gate, because every main
B2 certificate was rejected. For held-out cases under `search_equal` and
`safe_retry`, all pipelines succeed on 24/24 cases under all three fault settings.
That saturated endpoint cannot establish model-quality or certificate-quality
improvement. Public catalog execution and trusted grants can recover despite
poor model judgments or a completely blocked original route.

For example, with no fault, certified safe-retry uses 55 calls across 24 held-out
cases, versus 84 for the deterministic-solver gate and 80–83 for raw-model gates.
This is not evidence-generation efficiency: blocking every original route sends
execution to inexpensive public alternatives. The certification stage has itself
already run the finite checker. For the certified pipeline, legacy → safe-retry
success is 24 → 24 without faults, 18 → 24 for transient-before, and 14 → 24 for
known-after; the recovery-policy change explains these gains without any accepted
model certificate.

All 24 certified held-out cases select an alternative route. The saved
`route_bypass` flag reports 20 because it specifically requires a committed
alternative effect. The other four cases—both seeds of `deferred_cleanup` and
`preexisting_bundle`—already satisfy the goal, and an empty alternative completes
without committing an effect. A report must not interpret the flag's remaining
four as successful model-gated original execution.

The model labels aggregate all public worlds, whereas integrated execution uses
world 0 only. The recovery grid uses all 94 worlds. Thus 24/24 integrated held-out
success and 34/38 recovery-world success have different denominators and are not
contradictory. All routes remain subject to trusted grants; this zero-violation
result is not attributable to model refusal or certificate acceptance.

## Additional reviewed fingerprints and decision

| Artifact, relative to `results/phase7/` | SHA-256 |
|---|---|
| `api/observations.jsonl` | `3d4f59e65bb8571b542aded89b683bc68664c57baab325d82bda5388a5035d29` |
| `api/budget.jsonl` | `1f373a5700f91ee42a190935daa53ccfda658eae02ef9fb79d3faf12491ba0f6` |
| `integrated/vm_results.jsonl` | `6eda57be34c38a64cc8841f22ba6d89e13e49875e508b7a22893e6d5541f164e` |
| `integrated/container_results.jsonl` | `6eda57be34c38a64cc8841f22ba6d89e13e49875e508b7a22893e6d5541f164e` |
| `analysis/summary.json` | `352343401ed2ac3041a33d95ea2bceda1826d9e14746120e6d22d0c290e040b7` |

No blocking integrity defect remains in the saved outputs reviewed here. The
evidence supports a bounded semantics/recovery study with meaningful negative
model-evidence findings. It does not support general LLM evidence superiority,
universal recovery-cost improvement, or real-world Skill security effectiveness.
The final narrative should retain the zero certificate coverage, applicability
confusions, retry cost counterexample, trusted-catalog attribution, and explicit
post-freeze/post-acquisition repair history. Final release hashes and remote CI
remain separate release requirements.

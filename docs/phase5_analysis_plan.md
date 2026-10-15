# Prospective Phase5 offline analysis plan

This plan was written before the analyst read any Phase5 model outcome. It defines the analysis of the frozen active `reasoning_cases_v2.jsonl` and the 588-job acquisition grid. The analyzer makes no API calls and never executes sample programs. Output is deterministic and create-only. Existing analysis files are never overwritten.

## Planned denominators

The main comparison uses replicate 0 only: 18 construction families × three authorization contexts × five views × two models = 540 jobs. The other 48 jobs are two additional replicates of six digest-selected families, balanced across authorization contexts, for table/oracle and both models. Their corresponding 24 replicate-0 jobs form a 72-run reliability panel. Repeats are not extra independent families or main accuracy observations.

The job file supplies the complete denominator. Duplicate/unplanned observations or job IDs, unknown cases/contexts, source truth ID mismatch, and metadata/hash mismatches are rejected or explicitly marked protocol invalid. Missing saved observations stay in every planned denominator with null predictions. A result is valid only if saved protocol validity, completed status, exact candidate coverage, label domains, unknown-axis coverage, nonempty unknown evidence fields, and expected request hash all agree. Invalid responses receive no partial label credit.

## Four-axis metrics

Report action validity, authorization, implementation finite-intervention necessity, and finite task-route necessity separately. Reuse the arithmetic in `tsg.analysis_v4.metrics`; do not reuse that module's old eight-family warning or its old case mapping. Each metric table records planned eligible labels, available predictions, missing/invalid predictions, and numerator/denominator counts.

- Exact accuracy: exact yes/no/unknown matches divided by all planned eligible labels.
- Known-truth accuracy: correct yes/no predictions divided by planned gold yes/no labels, including missing/invalid responses as failures.
- Avoidable unknown: predicted unknown on gold yes/no, divided by planned known truth. Missing/invalid is a separate category.
- Correct unknown: predicted unknown on gold unknown, divided by planned gold unknown.
- Unsupported decision: predicted yes/no on gold unknown, divided by planned gold unknown; do not count missing as a decision.
- Decided coverage and selective accuracy retain the Phase4 definitions; deciding a gold-unknown label incorrectly counts against selective accuracy.
- Unknown reason agreement: an exact reason-code match when a gold-unknown dimension is predicted unknown. Report both gold-unknown planned and correct-unknown denominators. Missing evidence/next-action text is checked for presence only, never credited as semantically correct merely because it is nonempty.

Report overall, by model/view/axis, by model/view/context/axis, by model/view/split/axis, and by model/view/context/split/axis. Report protocol coverage for the same job-level groups. Unknown counts must also be broken down by gold reason, so the deliberately frequent missing-scope condition cannot hide dynamic-binding or incomplete-route failures.

## Paired graph comparisons

For each model and axis, compare auto, oracle, shuffled, and length_control against table, and compare oracle against length_control and auto. Pair the exact case, context, and canonical candidate. Report all-split and per-split results for exact, known-truth, and unknown-truth accuracy. Missing/invalid outputs remain in the planned pair and contribute no exact matches.

Use 2,000 deterministic paired cluster bootstrap resamples, drawing construction families with replacement and retaining every candidate/context in each drawn family. Give the pooled ratio difference, equal-family macro difference, percentile 95% interval, actual family count, labels per family, seed, and number of undefined resamples. A split has six families; all data has eighteen. When a metric has no relevant gold labels, report null instead of zero. There is no multiplicity correction and no confirmatory superiority claim across these comparisons. Intervals describe this small finite-family panel, not all real skills or programs.

The graph audit independently compares canonical auto/oracle triples in `acquisition/edge_audit.jsonl`: true positives, extras, missed edges, precision/recall, type counts, and per-case counts. Recompute rather than trust stored summary counts. Where saved raw reasoning graphs exist, distinguish raw extractor dependency edges/nodes from projected canonical edges; a projection count is not raw extractor recall. The audit does not inspect model responses to define graph correctness.

The token-control audit pairs oracle and length_control jobs. Report local recorded token counts, exact local matching, actual API input-token availability and counts, and actual paired differences. API usage is an observed token quantity, not an invoice; output tokens and request/schema overhead are not controlled by local prompt matching. Do not assume local o200k_base equality proves identical billed tokens for every model.

## Reliability and reference baseline

For each planned three-replicate family/context/view/model group, report all-valid groups and exact label-vector consistency, plus per-axis candidate consistency and all three pairwise comparisons. Keep invalid/missing repetitions in planned denominators and report their counts. Also report agreement conditional on available valid pairs. Repetition only estimates observed response stability; no label or replicate is treated as an independent additional task.

The symbolic authorization comparator reads public canonical claims and public grants only. Within a rule all selectors must match; rules are alternatives. Unmatched static claims under closed_deny are no, absent scope is unknown, and unbound dynamic resource claims remain unknown. No private truth or source parsing determines its predictions. Score those predictions against private truth afterward. Label it a structured-candidate baseline conditional on provided claims and grants, not a raw-source competitor, extractor, semantic necessity solver, or independent source-truth validator.

## Phase4 context and publication

If saved Phase4 synthetic metric tables exist, include their original values with their exact source and provenance. The new families, precise denial variants, new views, private/public separation, and finite intervention semantics change the estimand and difficulty. Such numbers are historical context, not causal before/after accuracy estimates. No automatic subtraction or significance comparison across phases is planned.

The analyzer may publish a complete-grid accounting report while some observations are missing, but must prominently mark it incomplete and show the missing count. The parent will run the final publication after acquisition completes. Preserve input SHA-256 hashes and analyzer/plan hashes. Inputs are read-only; final files are created only in a fresh output directory. Refuse a pre-existing output directory before writing anything, avoiding partially updated evidence packages.

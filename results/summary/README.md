# Saved-result analysis snapshot

Created: 2026-10-14T22:24:57.750660+00:00

Synthetic benchmark: 132 cases, 6 families.
Formal detection responses observed: 1056.

| Phase | Status | Detection observed / expected |
|---|---|---:|
| development | complete_counts | 528 / 528 |
| validation | complete_counts | 176 / 176 |
| held_out | complete_counts | 352 / 352 |

P/R/F1 are selective (decided predictions); coverage and abstention-inclusive recall accompany every row.
Security-positive rows use positive_label=no; yes-label rows are also exported. Pooled replicate rows are descriptive, not independent samples.
CI is a family cluster percentile bootstrap. Read cluster_warning before interpreting it.

Budget exposure upper estimate: USD 1.365067, including outstanding reserves of USD 0.009080.

## Interpretation limits

- Formal prediction metrics exclude pilot/pre_review/pre_cache_review; budget includes all incurred or reserved API expenses, even when historical raw responses are unavailable.
- Synthetic labels are generator-authored specifications plus executable output checks, not human annotations.
- V1 uses researcher-authored synthetic graphs; V2/V5 are post-processing with saved VM evidence.
- Reference exclusions apply only to supported fixture workflows; inclusion or replay failure never proves necessity.
- Two replicates are repeated observations; bootstrap resamples whole families with all their observations.
- With one family CI is null; two/three-family intervals are extremely weak. Six total families do not establish broad generalization.
- Mechanistic templates were inspected during development; only designated model-response holdout is unobserved before its run.
- VM timings exclude model latency. Fixed oracle policies and trusted labels are not an end-to-end generated-policy evaluation.
- In post_task_reuse runtime_step=3 and expires_at=3; the present lease ablation primarily tests use-count limits, not an isolated temporal-expiry effect.
- The post_task_reuse/a_late authorization label assumes max_uses=1 absent from the natural-language task; a separate post hoc exclusion sensitivity is not a preregistered primary result.
- Real corpus statistics measure extraction coverage and syntactic localization; no human accuracy or arbitrary-script execution claims.
- Metamorphic experiment is one formatting-comment perturbation, not a general prompt-injection robustness proof.

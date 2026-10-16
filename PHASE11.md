# Phase 11 — checkable evidence contracts

Pure synthetic research release. All previous tracked evidence is preserved; baseline commit `caf5ee5430e011044c478ec8fed7013545978922`, archive tag `archive-phase10-20261017`.

- [English paper draft](paper/phase11/manuscript.md)
- [中文研究报告](docs/phase11_report.md)
- [Claim–evidence matrix](paper/phase11/claims.md)
- [Reproduction guide](docs/phase11_reproduction.md)
- [Prospective analysis plan](docs/phase11_analysis_plan.md)
- [Theory and trust assumptions](docs/phase11_theory.md)
- [Independent final review](docs/phase11_final_review.md)
- [Machine-readable analysis](results/phase11/analysis/summary.json)
- [Release verification](results/phase11/provenance/release_verification.json)

36 structural families (24 main,12 challenge),72 lexical cases,12 dependent scaling cases. 288 model streams,1,605 provider responses,2 retained API errors. All1,006 reference executions match after separately documented normalization of two diagnostic error strings. 12,320 acquisition conditions,15,696 recovery conditions,13,824 integrated conditions. Restricted-container replay matches all43,064 recorded conditions (8,664top-level null results; wrappers may also contain null executions; dependent rows).

At matched budget12, observe-cover completes30/36 API-world tasks; GPT-6 Luna29/36; GPT-4.1 mini28/36. No model or graph superiority claim. Certificate stopping reduces acquired work; terminal-status recovery succeeds only under explicit trusted backend assumptions. This supports a bounded, reproducible mechanism study, not real-world Skill security or guaranteed publication novelty.

Additional upper estimated cost:$3.765178875. Cumulative:$22.652988125. Remaining authorized margin:$6.898587. No further model calls are needed for ordinary replay.

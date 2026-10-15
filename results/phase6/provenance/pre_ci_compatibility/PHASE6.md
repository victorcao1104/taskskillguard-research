# Phase 6 — executable synthetic workflow research

Pure synthetic scope. No real Skill experiment or human annotation in this phase. Baseline commit `efd19d5e8704bdaec24fd183b81026d1d7fffccd` is preserved byte-for-byte.

- [中文研究报告：发现、比较、反例与边界](docs/phase6_report.md)
- [Prospective main design](docs/phase6_design.md) and [separate targeted supplement](docs/phase6_challenge_design.md)
- [Independent audit](docs/phase6_review.md), [truth validation](docs/phase6_truth_validation.md), [runtime](docs/phase6_runtime.md), [equal-planning controls](docs/phase6_selection.md)
- [Reproduction and artifact map](docs/phase6_reproduction.md)
- [Main analysis](results/phase6/analysis/summary.json) and [targeted analysis](results/phase6/challenge/analysis/summary.json)
- [Machine-readable overview](results/phase6/publication/overview.json), [release verification](results/phase6/provenance/release_verification.json)

Main: 36 workflows / 18 families, 336 model conditions. Targeted supplement: 12 workflows / 6 families, 96 model conditions. Four successful no-network batch containers reproduce 5,376 distinct finite execution conditions. A separate first launch failure is preserved. Cost accounting inherits every earlier ledger entry.

These are bounded mechanism tests. Static graph effects are not consistently beneficial; stronger recovery controls expose cost/success tradeoffs rather than universal search superiority. Read the report's claim limits before using the figures.

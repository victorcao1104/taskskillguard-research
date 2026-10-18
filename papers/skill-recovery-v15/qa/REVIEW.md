# Manuscript delivery review

Reviewed on 18 October 2026. This is an AI-assisted artifact review, not independent human annotation or external replication.

## Format and visual review

- Exported with Tectonic 0.17.0; the desktop standalone compiler also returned success for the final source.
- 12 PDF pages: 11 body pages and one bibliography page.
- Single-paragraph abstract: 189 words. All 19 references are cited; 13 are published peer-reviewed works, with preprint/acceptance status distinguished in the citation audit.
- Introduction spans approximately 1–1.5 pages of column space. Related work fits within page 2. Conclusion/future work occupies most of page 11, followed by contributions/artifacts.
- Methodology and experimental design span pages 3–7; results and limitations span pages 7–11.
- All 12 final pages rendered at 1,600 pixels and visually inspected. Equations, diagram, algorithm, seven tables, footnote and two-column bibliography are legible. No clipping or overlapping text remains.
- No overfull boxes, undefined citations/references or PDF replacement glyphs. The compiler emits nonfatal underfull-box notices, a dependency encoding warning in `algorithm.sty` and a Fontconfig configuration notice; the exported equations and text render correctly.
- `text_checks.json` records the final PDF hash and page inventory. `table_checks.json` records manuscript/evidence hashes and checks 33 rows / 89 numeric table cells.

## Substantive checks and revisions

A fresh read-only review checked the manuscript against evidence and relevant implementation. Core numerical and causal conclusions passed. Three clarifications were incorporated:

1. Cost counters omit some native oracle, state-preparation and diagnostic computation; model bills are not complete system cost.
2. The seven old failed programs comprise five matching-family and two quota-quality programs. The inverse intervention repeats two task/input suites across seven program cases.
3. Repair's first request sees original source; Full's model request sees its transformed candidate and feedback. Later feedback requests use the preceding candidate and omit original source.

The manuscript distinguishes automatic executor work from model reasoning, attempts from executed effects, invalid-cache selection from wrong completed output, and feasible completion from correct boundary stopping. It retains the source-method failures, non-monotonic state results, strong specialist solver, transport incidents, finite validation gaps and semantic-input overlap. It credits prior continuation mechanisms in CaMeL, Progent and SkillScope.

## Evidence and preservation

`prepare_evidence.py --check` rederived the manuscript evidence and verified 62 input hashes, six paired comparisons, 5,120 individual saved validation trials, the budget ledger and unchanged old studies/papers against experiment commit `37e33664ab0626446e8ed1cfcd0304368d041aaa`.

`check_table_values.py --check` passed for Tables II–VII and the embedded bibliography. No paid API call or new experiment was made. The 44,554 replay worlds and 55 tests / 1,072 subtests quoted by the paper are the preserved experiment's verification records, not newly executed tests during manuscript preparation.

All new tracked files belong to `papers/skill-recovery-v15`. The preexisting untracked top-level `provenance/` directory is excluded. The archive tag preserves the starting point, and the manuscript release identifies the new version without changing old papers or experiment outcomes.

# Phase 4 Implementation Plan

> **For agentic workers:** Use the design as the contract, test-driven implementation for correctness changes, and independent review before acquisition. Parallel independent file ownership is used under dispatching-parallel-agents; parent integrates and owns experiment execution.

**Goal:** Repair the study object and produce falsifiable extraction, reasoning, Replay and enforcement evidence.
**Architecture:** Segmented source evidence feeds a bounded semantic extractor and explicit uncertainty ledger. Independent fixture truth and the real descriptive corpus remain separate. All new outputs are additive.
**Tech Stack:** Existing Python3.12 environment, standard-library parsing, frozen v2/v3 components as read-only dependencies, existing pinned Docker image, two authorized OpenAI models.
**Spec:** `docs/phase4_design.md`.

## Global constraints

- Preserve all files tracked by a666de55206ece2dcdbb669d083aa175a50dea5a and original corpus.
- Cumulative API cap USD20; inherit full USD13.9757919 ledger, retain all unknown billing reservations.
- Use only existing180 bounded/redacted source bundles for any real-source API transmission; no human labels invented.
- No Skill source imports or execution on host. Only isolated controlled fixtures execute.
- Separate frozen primary observations from development and posthoc corrections.

## Review focus

1. Shell expansions/unknown flags cannot turn attacker strings into resolved resources.
2. Markdown source mapping, unclosed blocks and multiple effects on one line cannot silently lose or duplicate effects.
3. A clean candidate count can conceal recall loss, uninvoked examples or missing dependencies.
4. Reference failure or invalid neutralization cannot establish task necessity.
5. Different candidate populations, graph token counts and missing outputs cannot masquerade as model improvements.

### Task1 — shared evidence and immutable baseline

Files: create `src/tsg/evidence_v4.py`, `tests/test_evidence_v4.py`, `results/phase4/provenance/baseline_manifest.json`.
Interface: `make_node` and `select_graph` exactly as design; stable IDs and validated spans; selection reports closure loss.
- [ ] Write failing tests: input-order stable IDs, distinct compound effects, invalid span, deterministic cross-role selection, mandatory dependency closure and explicit capped closure.
- [ ] Run focused tests, implement, rerun; preserve baseline SHA256 inventory and budget prefix evidence.

### Task2 — shell semantics

Files: create `src/tsg/shell_v4.py`, `tests/test_shell_v4.py`.
Consumes `make_node`; produces `analyze_shell` interface from design.
- [ ] Fail then implement tests for GET/POST, --url, multiline quoted data, output/input file effects, assignments/rebinding, pipe dependencies, unsupported flags/substitutions/control and line mapping.
- [ ] Independently review ambiguity/false certainty; report unsupported grammar explicitly.

### Task3 — Markdown/Python integration and real corpus census

Files: create `src/tsg/extraction_v4.py`, `tests/test_extraction_v4.py`, `scripts/prepare_phase4.py`.
Consumes shared evidence and shell module; reuses immutable `graph_v2` Python interpreter with source mapping.
- [ ] Fail then implement metadata/fence/prohibition/OAuth non-actions, fenced code parsing, original-line evidence, isolated snippet bindings, unsupported/unclosed regions, stable cross-file IDs and conservative call links.
- [ ] Extract all180 existing prepared bundles, retain uncapped graph and rejected legacy matches, select12 with closure and explicit omissions; produce source-hashed corpus census and before/after matching.

### Task4 — independent fixture benchmark

Files: create `src/tsg/fixtures_v4.py`, `data/phase4/fixtures_*.jsonl`, `tests/test_fixtures_v4.py`, `scripts/evaluate_extraction_phase4.py`.
- [ ] Separate author supplies literal expected effects/non-actions/uncertainties and family splits, without deriving expected labels from either extractor.
- [ ] Validate source spans and independent known targets; freeze fixture version before model calls; run old/new extraction with precision, recall, target errors and abstention reported separately by family/split.

### Task5 — task reasoning and matched graph controls

Files: new `src/tsg/reasoning_v4.py`, `tests/test_reasoning_v4.py`, `scripts/run_phase4.py`, versioned data/results.
- [ ] Define independently authored finite task contracts and authorization/necessity truth; separate optional permission, prohibition and missing scope.
- [ ] Match candidate IDs and source across raw/node-table/graph; validate all response IDs/statuses with phase-aware parser. Preserve input token counts and all failures.
- [ ] Freeze exact affordable synthetic and real-subset job grid, price assumptions and budget before paid calls; single cumulative writer, no outcome-based resampling.

### Task6 — actual Replay and faulty-contract controls

Files: new `src/tsg/replay_v4.py`, `tests/test_replay_v4.py`, `scripts/run_replay_phase4.py`.
- [ ] Test Original/neutralized/independent-reference with triggered, valid_ablation, CorePres, GoalSat and two necessity fields.
- [ ] Test explicit contract overgrant/undergrant, missing reference, tool error and partial lease consumption; execute isolated fixtures, save exact grid and raw effect evidence.

### Task7 — synthesis, release and completion audit

Files: new phase4 analysis/report/verifier/workflow and root PHASE4 entry.
- [ ] Compute paired results by independent families, coverage/selective risk and all-plan utility; no human real accuracy.
- [ ] Independent review, appropriate full tests, baseline/corpus/budget/grids/provenance checks.
- [ ] Upload original private repository with versioned artifacts and confirm remote/CI; requirement-by-requirement goal audit remains mandatory.

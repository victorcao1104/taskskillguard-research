# v15: when can a blocked Skill be recovered safely?

This study separates three questions: which state support reduces which failure; when retained source computation is useful; and which finite validation tests miss which defects. It is a synthetic mechanism study, not an audit of real Skills or a claim of universal secure recovery.

The previous paper and every earlier experiment remain unchanged. Baseline: `74a06d2f3345ed8e2eb7768d36ba66d2e9ae7688`; archive tag: `archive-before-mechanisms-v15-20261018`. The main protocol and inputs were frozen at `333d55cca` before formal model acquisition.

## Read the evidence

- `design.md`: prospective questions, comparisons, budget, power and limitations.
- `reports/REPORT_ZH.md`: readable findings and comparison with v14.
- `reports/main_summary.json`, `episode_table.csv`: all formal outcomes, paired template contrasts and resource curves.
- `reports/causal_v14.json`, `causal_summary.json`: exact interventions on seven old failures; no old score is replaced.
- `reports/validation_summary.json`: 96 authored mutants and equal-count/logical-budget comparisons.
- `results/episodes/`: immutable per-episode candidates, validation, fresh-input and scale evaluations. `pilot*` files are development only; `formal--*` files are the 864 original formal episodes. The enforced state supplement is stored separately under `results/strict_state/episodes/`.
- `results/diagnostics.json`: cache/receipt interventions, paired stop conditions, reachable service faults and call-budget exhaustion.
- `results/strong_controls.json.gz`: specialist deterministic solvers, stop and literal-deletion references.
- `api/requests/`, `api/raw/`, `api/dispatch/`, `api/budget.jsonl`: exact model requests, raw answers, durable dispatch records and inherited conservative cost ledger. No API key is included.
- `provenance/`: frozen code/input hashes, archive evidence, environment, budget admission and pilot changes.
- `semantic_validation_followup.py` and `results/semantic_validation/`: explicitly exploratory semantic boundary tests added after the primary validation design. They do not replace its negative results.

## What is controlled

Source experiment: 16 authored templates in four structures, five source-integrity levels, Full and ordinary repair, plus one source-blind replan per template/model. Replan results are shared references across source levels, never five independent samples. All use the same automatic state executor and verifier. Full's source transformation uses the first of two candidate slots; other methods may use two model calls. The request/cost curves expose this difference. A task-specific deterministic solver remains an explicit strong reference, with its specialized implementation cost outside the online budget.

Original state experiment: the same correct computation is supplied through `compute()`, but A–C could bypass it and recompute inside generated effects. Eight accepted programs did so. These results remain available; they do not enforce identical executed computation. The separate `strict_state.py` supplement blocks effects from reading current input directly and requires the fixed computation when no valid cache is available. A receives raw state; B also receives certified state; C also receives remaining operations; D executes the operations automatically after a candidate decision. Models still control stop/clarify decisions. The enforced supplement isolates support levels more tightly; neither experiment establishes that D improves the computation algorithm. Raw cache reads and actually selecting a stale result are separate diagnostics.

The gateway, permissions and result checker are common. Rejected duplicate attempts and actual duplicated effects are distinct. Unknown send state is evaluated in both hidden physical worlds with identical visible information. Prior harm remains in the record. No candidate can execute host Python, read real private files, send messages or contact a real service.

## Reproduce without paid calls

Use a complete checkout of this repository, not a copy of this folder alone: the bounded interpreter and durable provider utilities are imported from preserved earlier versions. Python 3.12 was used.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r studies/recovery-mechanisms-v15/requirements-replay.txt
cd studies/recovery-mechanisms-v15
../../.venv/Scripts/python -m pytest tests -q --basetemp ../../work/v15-tests
../../.venv/Scripts/python verify_replay.py
```

`verify_replay.py` executes every saved formal candidate locally, checks the recorded validation/final outcomes and traces, verifies frozen hashes and the inherited ledger prefix, and makes **zero API requests**. It writes a verification report only. The strict supplement has its own cached replay command documented in `strict_state.py --help`. Wall-clock timings are not expected to reproduce exactly; logical steps and outcomes are checked. Dataset generation and bounded execution use no external data.

`python analyze.py` regenerates derived tables and figures from saved results. `python -m rm15.validation_study --output-root ../../work/v15-validation-replay` reproduces the primary mutant study in a separate output folder. Do not modify frozen input definitions or old experiment records in place.

Live acquisition is deliberately separate (`python -m rm15.campaign --live`). It reuses durable requests, never automatically retries an unknown dispatch, and requires the original authorized local credential configuration. It is unnecessary for checking the published evidence. A collaborator using their own key/data should create a new study version, ledger and declared budget rather than reset this experiment's ledger.

## Boundaries of the conclusions

The 16 templates are related, not 864 independent tasks. There is one model draw per condition; intervals resample authored templates and do not establish population-wide confidence. Both oracle and solver are benchmark-team authored. The main source attack is a removable private-read gate with no `else`, and output goals can describe relatively simple mathematics. Specialist solvers can remain the best choice. Engineered validation mutants are not representative of natural model errors. The study neither estimates real Skill risk nor establishes novelty over all prior repair methods.

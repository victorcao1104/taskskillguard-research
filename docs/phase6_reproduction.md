# Phase 6 artifact map and reproduction

All commands run from repository root with Python 3.12. Install `configs/requirements-lock.txt` and `configs/phase5-requirements.txt` in an isolated environment. No real corpus or credentials are needed for offline verification. Do not overwrite preserved data or results; experiments use immutable writes.

## Offline release check

```powershell
python -m pytest -q --basetemp work/phase6-repro-tests
python scripts/verify_phase6_release.py
```

Verifier checks all 24,393 baseline byte hashes, both prospective freezes, exact model requests and parsed responses, both inherited ledger prefixes and latest cumulative cap, independently recomputed truth, and all 5,376 VM results against saved container results. It does not call model APIs or Docker. CI uses this route on Linux. The four skipped baseline tests remain optional historical tests; skips are not relabeled as passing.

## Immutable experimental records

| Material | Main | Targeted supplement |
|---|---|---|
| Fixtures | `data/phase6/dev.jsonl`, `heldout.jsonl` | `data/phase6/challenge.jsonl` |
| Code/input freeze | `results/phase6/provenance/freeze.json` | `results/phase6/challenge/freeze.json` |
| Truth/intervention traces | `results/phase6/first/` | `results/phase6/challenge/first/` |
| Exact requests and representation controls | `results/phase6/acquisition/` | `results/phase6/challenge/acquisition/` |
| Responses, intents, observations, ledger | `results/phase6/api/` | `results/phase6/challenge/api/` |
| Factorial jobs and VM/container outcomes | `results/phase6/recovery/` | `results/phase6/challenge/recovery/` |
| Model-gated and reference execution | `results/phase6/integrated/` | `results/phase6/challenge/integrated/` |
| Candidate scores, unknowns, family intervals | `results/phase6/analysis/` | `results/phase6/challenge/analysis/` |

Frozen main pipeline: `scripts/experiment_phase6.py`, `scripts/run_phase6.py`, `scripts/analyze_phase6.py`. Supplement pipeline: `scripts/run_phase6_challenge.py`, `scripts/analyze_phase6_challenge.py`. Source semantics: independent `truth_v6.py` and `runtime_v6.py`; equal-planning selectors: `selection_v6.py`. Publication-only script creates the report and PNG/PDF scientific figures; its hard-coded descriptive counts are checked against structured evidence during review.

The development/heldout/challenge builders use no model or production VM imports. Runtime/truth authors did not read initial heldout fixtures before freeze; supplemental selector author did not read challenge fixtures before its freeze. The coordinating author sees all files after freezes. This is local process isolation, not a claim of externally controlled blind preregistration.

## Model collection and cost

The existing authorized configuration stays outside this repository. Commands `run_phase6.py --execute --env-file <local-path>` and `run_phase6_challenge.py collect --env-file <local-path>` can reuse preserved records, but do not invoke them just to verify results. For a new campaign use separately frozen new output paths and obtain an applicable budget. Never delete raw/intents to cause a retry. The latest ledger is `results/phase6/challenge/api/budget.jsonl`; cumulative cap is $29.551575125 and latest exposure is $16.394690750. This is conservative model-price accounting, not an invoice.

## Container amendment and isolation

The first recovery container launch failed because the pinned image's original ENTRYPOINT expected an old job file. Original `container_plan.json`, `container_intent.json`, `container_stdout.json`, `container_stderr.txt`, and `container_exit.json` remain unchanged. `scripts/container_phase6_v2.py` explicitly selects `python3` as entrypoint and retains the image digest, frozen runtime bytes, job grid, no network, UID65534, read-only root, dropped capabilities, process/memory limits, and no host mounts. Each successful launch stores its plan/stdout/stderr/exit under `container_v2/`. The failed launch performed no study VM conditions.

One successful container processes each batch with fresh state per condition. Four successful batches cover main recovery2304, main integrated1440, supplement recovery1152, supplement integrated480. Container results match host VM outputs exactly. There are no real files/messages/tools accessed by the DSL. Container isolation is additional containment of a trusted bounded VM, not evidence against arbitrary hostile Python.

## Terminology corrections

`oracle` is the preserved raw condition name for a conservative aggregate-label gate. It is not a theoretical completion upper bound because labels aggregate possible worlds while execution uses world0. `route_bypass` means any committed alternate-route effect, not necessarily evasion of a model decision. `initial_feasible_catalog_count` in the supplemental selector means the first *selection* state after original plus retry, not the initial world's feasibility. `container_count:2` in each analysis summary counts successful batches for its own track; overall successful count is4 plus1 preserved failed launch.

The main source prompt omits prose descriptions of step-limit/key-conflict rules. Every planned reference route and intervention in both sets is error-free, so these clauses do not change labels in this campaign; their model understanding was not tested. Raw frozen artifacts and names are retained; this explanation records their limits rather than rewriting evidence.

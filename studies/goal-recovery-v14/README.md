# Goal-checked recovery of synthetic Skills (v14)

This study asks whether explicit state handling helps recover a blocked Skill when the trusted task specifies output properties, but supplies no computation pipeline or replacement program. It tests independent value against model repair, model replanning and a strong source-free constraint compiler. It makes no real-Skill or production sandbox claim.

The preserved predecessor is `../stateful-recovery-v13/`. The archive tag is `archive-before-goal-recovery-v14-20261018`. All previous tracked files remain unchanged. The complete development pilot is additionally preserved at `v14-development-pilot-20261018`.

Start with [the Chinese report](REPORT_ZH.md), [the v13 comparison](VERSION_COMPARISON.md), and [the machine-readable results](reports/analysis.json). The release is `v14-goal-checked-recovery`. Figures are in `figures/`; raw acquisition incidents and accepted-program failures have separate reports.

## Study layout

- `design.md`, `plan.md`, `progress.md`: decisions, corrections and execution history.
- `gr14/`: independent goal checker, bounded interpreter, state certificates, source transformation, compiler, dataset, shared validation and acquisition.
- `data/`: frozen cases and validation/final/stress inputs. Six main families are combinations of declarative selection properties, not six unrelated application domains.
- `api/`: inherited budget, exact requests, durable dispatch records and raw provider responses. No credential file is included.
- `provenance/`: source hashes, grid selection, budget inheritance and review evidence.
- `results/`: complete development/main/combined/control outcomes. JSON summaries are accompanied by compressed execution traces.
- `reports/`: analyses, mechanism probes, reproduction evidence and claim boundaries.

## Environment

Python 3.12 or later, `pytest` and `jsonschema` are required for the study and inherited client. Install the repository's existing dependencies if using the original environment. The scientific plotting script additionally uses matplotlib. All synthetic execution is interpreted in memory; candidate code is never passed to Python `exec` or the operating system.

The observed runtime is Python 3.12.14, pytest 9.1.1, jsonschema 4.26.0, and matplotlib 3.11.2; see `provenance/environment.json`. Clone the whole repository, not this directory alone: the budgeted provider imports the preserved common client under root `src/` and `scripts/`.

From this study directory, run:

```text
python -m pytest tests -q --basetemp ../../work/v14-tests-fresh
python -m gr14.campaign controls --out ../../work/v14-controls-fresh
python -m gr14.campaign main --out ../../work/v14-main-fresh
python -m gr14.campaign combined --out ../../work/v14-combined-fresh
python probes.py
```

The default campaign mode is **cached-only**: it refuses a missing API response. Use a new output directory for an actual recomputation; pointing at an existing result directory skips completed rows. Main and combined source hashes must match their freeze manifests. The development pilot used an older shared system instruction and a 12,000-byte cap; replay it from its preserved tag with the matching saved artifacts. Main/combined use 14,000 bytes including conservative token headroom, and 2,000 output tokens.

`--live` makes paid requests and requires an explicitly configured key and the inherited ledger. It is not needed to inspect or replay this release. Original acquisition reused an authorized local configuration outside the repository. Do not copy a private key into any artifact.

## Experimental units and costs

Main: 24 case conditions × 6 methods × 2 models × 3 repeated runs = 864 episodes. Model requests are issued separately when needed; deterministic-first successes use no API call. Six of the 24 are benign reconstruction probes. Three conditions cannot safely complete under the given permissions/observations. Combined mutations: 12 conditions × 3 methods × 2 models × 2 runs = 144 episodes. Two development families contribute 72 separate pilot episodes and are not pooled with the main result.

Methods are `repair_raw`, `repair_state`, `replan_raw`, `replan_state`, `full`, and `full_no_reuse`. Every method has three candidate slots. Full methods spend their first slot on a deterministic source transformation and can use at most two model requests; other methods can use three. All candidates use the same validator and runtime. This is a matched maximum candidate budget, not equal realized spending. The compiler uses no model and has the same bounded execution tools, goal checker and permissions.

Report validation and final-execution work separately, with original-prefix work included. Cached prefix simulation is counted logically even when computation is shared. Times include machine-dependent local execution and API latency; they are not universal deployment latency estimates. GPT-4.1 mini uses temperature 0; Luna uses reasoning effort none. Repetitions use the same configuration and are not independent task families; some full-method episodes are entirely deterministic. Uncertainty is clustered by the six designed families.

## Completed verification

All 1,008 main/combined episodes were freshly replayed from saved responses. Selected programs, validation/final outcomes and full traces match after excluding timing. The evidence audit checks 2,436 summary/gzip pairs, 36 frozen cases, 1,231 raw requests, source hashes and old-ledger preservation. No API call is required for this check. Detailed commands:

```text
python replay_parallel.py main --out ../../work/v14-main-fresh
python replay_parallel.py combined --out ../../work/v14-combined-fresh
python audit_release.py
python failure_analysis.py
python acquisition_diagnostics.py
python audit_benign.py
python figures.py
```

Use empty replay directories to recompute; interrupted replay resumes completed rows. The audit expects the shown paths. `python stress_parallel.py` computes missing larger-input rows and verifies existing summary/evidence pairs. To rerun all stress evaluations without altering the release, use a separate fresh clone and move its `results/stress` into a separate local archive first. Do not overwrite the published source evidence.

The cost ledger added $1.055283675 this round, leaving $15.768620025 under the unchanged inherited cap. This is conservative research exposure, not an invoice. One HTTP 400 `invalid_prompt` rejection remains in the combined Luna full completion rate; it must not be interpreted as a generated-program failure. The 13 incomplete responses and all 74 uniform last-completed-text normalizations remain inspectable.

## Important limitations

`valid(ids)` checks a proposed selection and returns only a Boolean; it supplies no witness. Nevertheless, a small finite search with a precise formal goal can be easy for a generic compiler. That is an intentionally retained strong control. Many damaged original Skills still contain useful computation; destroyed-computation cases test the narrower situation in which they do not.

Certificates bind current input, goal and value. They establish validity of this current value, not equivalence of the saved computation on every possible input. Eighteen challenge inputs, sixteen final inputs and thirty-two larger stress inputs remain finite tests. The public-cache and secret-use policy is deliberately conservative and may discard reusable work. A safe current completion cannot erase a prior disclosure.

The original benign source is not initially executed in reconstruction probes. Their failures measure reconstruction overhead, not a deployed gateway's normal-task false-block rate. The report separates these probes from blocked cases and audits normal pass-through explicitly. Historical versions and the new task distribution are not numerically interchangeable benchmarks.

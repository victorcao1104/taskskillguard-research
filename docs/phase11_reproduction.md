# Phase 11 reproduction guide

This release provides a deterministic replay of the recorded synthetic experiment. It also preserves the original provider responses and restricted-container records. Replaying recorded responses does not reproduce a new draw from a hosted model. Checking a recorded container transcript does not launch a new container. These distinctions are reflected in the verifier output.

The archive point before Phase 11 is `archive-phase10-20261017`, targeting commit `caf5ee5430e011044c478ec8fed7013545978922`. The baseline manifest records 37,907 tracked files. No earlier experiment is replaced. The authoritative Phase 11 evidence is under `data/phase11/` and `results/phase11/`; the manuscript is under `paper/phase11/`.

## Setup

Use Python 3.12 and a clean checkout of this private repository. Installing dependencies and downloading the tokenizer cache require network access. Neither step uses a model API or reads a credential file. Run these commands from the repository root:

```text
python -m venv .venv
```

Activate the environment using the normal command for your shell, or replace `python` below with `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on Linux/macOS.

```text
python -m pip install -r configs/requirements-lock.txt -r configs/phase5-requirements.txt
python -c "import os,tiktoken; os.environ['TIKTOKEN_CACHE_DIR']='work/tiktoken'; tiktoken.get_encoding('o200k_base')"
python scripts/hydrate_phase11.py
```

The tokenizer dependency is `tiktoken==0.12.0`. Its `o200k_base` cache file is named `fb374d419588a4632f3f557e76b4b70aebbca790`; its SHA-256 is `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`. The verifier rejects missing or changed cache bytes before replay. `o200k_base` is a length-control surrogate: this release does not establish that it is the tokenizer used by GPT-6 Luna. The graph/padding control matches local surrogate counts, while provider usage is recorded separately.

`hydrate_phase11.py` copies committed first-pass archives into ignored `work/` locations required by the frozen independent generator and tests. It checks hashes and refuses to overwrite any different existing bytes. It does not regenerate labels, alter cases, or modify the archived results. The new `tests/conftest.py` performs the same restoration for the full suite on a clean checkout, including older CI workflows.

## Offline verification

After setup, these commands require no OpenAI key and make no provider requests:

```text
python -m pytest -q --basetemp work/p11-reproduction-tests
python scripts/verify_phase11.py
```

The verifier explicitly blocks socket connections during evidence replay. It restores only ignored first-pass working copies. Experiment writers are replaced in memory with comparison-only functions: missing or changed result files cause failure rather than being silently generated. The default command checks the committed release manifests; it does not repair them. Successful verification establishes the following finite, recorded claims:

| Evidence | Reproduction check |
| --- | --- |
| Old results | Every one of the 37,907 baseline file hashes is unchanged. |
| Prospective freezes | All 78 production and 86 data-freeze file hashes match. These are local freezes, not external preregistration. |
| Independent data | Rebuild 48 main cases, 24 challenge cases and 12 scaling siblings; reproduce all six case/reference JSONL files byte for byte. Rebuild coverage and reference checker evidence. |
| Reference semantics | Retain both original error-name disagreements; separately reproduce the declared normalization and all 1,006 normalized world/route comparisons. |
| Certificate enumeration | Reproduce 8,672 main cache/history states and the separately defined challenge enumeration, retaining its boundary-only partitions. |
| Model acquisition | Reconstruct all 288 adaptive/fixed streams from 1,605 unique saved requests and raw responses with `invoke=None`; check prompt fingerprints, dispatch intents, selected queries and stop conditions. No missing continuation is inferred. |
| Budget | Check the exact inherited Phase 10 ledger prefix, every new reservation and settlement, the conservative usage arithmetic, and the cap at every appended ledger state. The two provider errors retain their reserved exposure. |
| Local experiment | Recompute 1,006 semantic pairs, 12,320 deterministic policy conditions, 15,696 recovery conditions, 218 old-contract comparisons and 13,824 integrated conditions, plus the matched-prefix subset. |
| Isolation record | Rebuild the exact job list and source payload; verify the pinned image, command, intent, exit, UID and stdout for all 173 recorded Docker batches. Compare these results with fresh local semantic replay. No fresh container is launched by this verifier. |
| Analysis | Recompute all tables, bootstrap summaries and figure source CSV files from retained rows. Validate all PNG/SVG/PDF hashes. |
| Independent trace measurement | Independently reconstruct authorization, effect identity, receipt binding, quota accounting and final files/emits from the recorded traces, without importing production code or trusting its summary counters. Preserve the 42,846-slot denominator: 28,482 executions and 14,364 null abstentions. |
| Physical-goal clarification | Recompute a separate posthoc sidecar from all 15,696 recovery rows, retaining 2,880 null executions. Recheck the final-state goal independently; reproduce 1,512 condition summaries and 24 paired contrasts without rewriting the frozen primary endpoint. |
| Diagnostic evidence | Recompute four assumption counterexamples and the posthoc Phase 10 parser diagnostic without changing Phase 10 metrics. |

The first-pass main cohort is preserved even though all of its feasible fully observed classes were singletons. The challenge supplement was commissioned after aggregate coverage review and is reported separately; it is not an untouched random holdout from an external population. Scaling cases are dependent siblings and are not additional independent families.

The primary runtime field `authorized_goal` denotes error-free acknowledged completion. An operation with an uncertain response can already have achieved the physical goal while the controller cannot acknowledge completion. The separate `physical_goal/` sidecar evaluates the goal predicate on saved final files and emissions and keeps this distinction visible. It was introduced after outcome review and is explicitly exploratory; it is not a retrospectively declared primary endpoint. Neither physical success nor a posthoc state inspection licenses the controller to continue without trusted runtime evidence.

One frozen challenge generator writes a descriptive provenance path using platform-native separators. The verifier checks that exact path after separator canonicalization, then reconstructs the archived Windows spelling for the metadata byte comparison. Case and reference JSONL receive no platform normalization. This reporting-only portability treatment is explicit in the verification result.

## Figure reproduction

Analysis uses the locked NumPy version, 10,000 equal-family bootstrap resamples and seed 11101. It averages dependent worlds, lexical variants and conditions within each authored family before computing cross-family summaries. Intervals describe these finite templates; they are not population confidence guarantees or confirmatory significance tests.

The portable verifier reproduces the numerical tables and the exact CSV rows selected for each figure, and verifies stored image hashes. Font rasterization and PDF internals can differ across operating systems even with locked Python packages. In the original rendering environment, additionally run:

```text
python scripts/verify_phase11.py --render-figures
```

This requires exact PNG, SVG and PDF rerender bytes. A render mismatch is not silently accepted as an image replacement. In a different environment, produce a separate comparison artifact rather than overwriting the archived figures.

## Independent checks and fresh isolation

The independent generator modules contain pure `build_cases()` and `reference_record()` functions, and the default verifier uses them without importing the production engine into the author interpreter. Running a generator with a new `--output-dir` also produces a new timestamped provenance file, so that provenance timestamp is not expected to match the historical first pass. Existing first-pass output paths are write-once.

To rerun restricted execution, Docker must already have the exact image `sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`. `scripts/container_phase11.py` sets no network, read-only filesystem, unprivileged UID 65534, no capabilities, no new privileges, resource limits and no host mounts. It interprets the finite synthetic DSL; it does not execute downloaded Skill code. Each condition gets fresh semantic state, while up to 250 conditions share one batch container.

On the archival checkout, `container_phase11.py deterministic` and `container_phase11.py integrated` validate and reuse already recorded successful batches; they do not constitute new launches. To obtain fresh container evidence, prepare a separate disposable copy containing the released source, `data/`, and recorded non-isolation results, but leave `results/phase11/isolation/` absent in that new copy. Preserve the original checkout and capsules. After dependency setup in the copy, run:

```text
python scripts/container_phase11.py deterministic
python scripts/container_phase11.py integrated
```

Those commands create 117 and 56 new batch containers respectively because their intent/exit records do not yet exist in the copy. Archive the copy as a separate replication, recording its source commit, environment and run time. If a launch fails, retain that replication's failure evidence; the current runner intentionally refuses to retry failed or orphaned intents automatically. The offline verifier's container claim is limited to the archived command/input/output evidence and exact agreement with local replay, not an independent attestation from the Docker daemon.

## API evidence and costs

The released acquisition has 288 streams, 1,605 provider attempts, 1,603 valid decisions and two retained API errors. There are no automatic retries. Raw response objects retain the original parser annotations; the Phase 11 phase-aware parser is replayed explicitly and its decision records are authoritative for this experiment. A valid paid prefix can still provide a certificate even if a later fixed-stream call fails; full-stream protocol validity and task completion are reported separately.

The Phase 11 conservative additional cost is $3.765178875, cumulative upper exposure is $22.652988125, and the cumulative cap is $29.551575125. The Phase 11 campaign also had its own $8.00 additional cap. These values use the recorded token-rate upper-bound method and retained unknown-usage reservations; they are not provider invoice amounts. The default verifier never reads `.env` files or sends synthetic content to a provider. A new API run would require a new prospective campaign, unique request identifiers and its own budget ledger; it would not be a byte-exact reproduction of the released model outputs.

## Release maintenance

Only the release author should use `python scripts/verify_phase11.py --release`, and only after all evidence and review artifacts are finalized. This option performs the same full replay, then writes `release_hashes.json` and `release_verification.json` once. All Phase 11 source, tests, reports, data, raw results, paper files and the shared clean-checkout fixture helper are covered. The two release manifests themselves are excluded to avoid recursive hashing. A subsequent changed file causes verification failure; the proper response is an append-only amendment or a new experiment version, not replacing the old manifest.

The frozen finite-world contract assumes complete world and route catalogs, truthful initial observations, a trusted receipt store and gateway, and the specified status/fencing backend. The executable counterexamples show why omitted worlds, external state drift, forged trusted-store data and unfenced absence cannot inherit the certificate guarantee. Reproduction verifies behavior within the supplied model; it does not establish real-Skill coverage, resistance to host-process compromise, or unrestricted distributed exactly-once execution.

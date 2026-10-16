# Phase 8 reproduction and evidence map

This round is entirely synthetic. Prior phases and original corpora are immutable. The baseline inventory contains 27,489 tracked files at commit `0f1aefcd6ed7986b0c4035be36f60967efab4a1c`.

## Offline verification

Python 3.12 with `configs/requirements-lock.txt` and `configs/phase5-requirements.txt` is sufficient. From the repository root:

```text
python -m pytest -q --basetemp work/p8
python scripts/verify_phase8.py
```

The verifier checks every old file hash, both prospective freezes, all saved request hashes and strict parsing, exact budget inheritance, reference/production truth and intervention agreement, all recovery/integration conditions, saved container evidence, recomputed analysis and final release hashes. It uses no model API and launches no container. The saved API evidence is replayed, not regenerated.

Use the short `work/p8` test temporary path on this Windows checkout. A validation attempt with `work/phase8-release-tests` reached an absolute path length of 260 in four legacy mocked-client tests and failed to create the response file despite an existing parent directory. The same 14-test module passed with a short path. The failed attempt is retained in `results/phase8/validation/long_path_attempt.xml`; this changed no code or experiment results.

## Experiment construction

The exact protocol and analysis questions are in `docs/phase8_design.md` and `docs/phase8_analysis_plan.md`. The independent generator's procedure and limitations are in `docs/phase8_reference.md`; the recovery policies are in `docs/phase8_recovery.md`.

```text
python scripts/experiment_phase8.py semantics
python scripts/experiment_phase8.py recovery
python scripts/experiment_phase8.py integrated
python scripts/analyze_phase8.py
```

These commands reproduce saved artifacts byte-for-byte or fail on a mismatch. They do not silently overwrite outcomes. The integrated stage requires saved API observations. Reference generator tests reproduce frozen inputs; no generation is conditioned on model outcomes.

`scripts/run_phase8.py` prepares the fixed 480-job manifest without making API requests. Live acquisition requires the explicit `--execute --env-file <authorized-ignored-config>` flags. Existing raw responses are reused; an unresolved dispatch marker cannot authorize a second request. The ledger retains the full Phase 7 byte prefix and unresolved historical reservations. Its conservative upper bound is not a provider invoice.

## Container replay

`scripts/container_phase8.py recovery` and `scripts/container_phase8.py integrated` use the pinned image digest recorded in each batch plan. Successful saved batch evidence is verified and reused. To independently relaunch, use a separate clone/output campaign with a separately recorded plan; do not erase saved intents or results.

The original container execution uses no network, no host mounts, a read-only root filesystem, UID 65534, all capabilities dropped, no-new-privileges, and CPU/memory/PID limits. Each condition has fresh in-memory state; up to 400 conditions share one container launch. A condition is not a separate container. Only the trusted finite interpreter and synthetic JSON programs execute; there are no real skill scripts.

## Provenance boundaries

- Production author did not read new fixtures before `production_freeze.json`; fixture author did not inspect production modules or model outcomes.
- `data_freeze.json`, acquisition manifest and all request bytes were fixed before provider dispatch. This is a local prospective freeze, not an external preregistration.
- Analysis estimands were fixed before dispatch; analysis implementation was allowed to finish during acquisition and is included in the final release hashes. It is not misrepresented as pre-acquisition frozen code.
- Published plots and summaries are derived views. Raw responses, parsed observations, complete effects, independent reference audits and preserved failure evidence remain available.
- Schemas and safety gateway operations are deterministic; claims are limited to this finite DSL. This is not evidence of real-skill safety, adversarial robustness or formal correctness for arbitrary programs.

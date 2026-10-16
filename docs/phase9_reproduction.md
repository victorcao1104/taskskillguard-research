# Phase 9 reproduction

Use Python 3.12 and the existing pinned requirements in `configs/requirements-lock.txt` and `configs/phase5-requirements.txt`. All commands run from the repository root. On Windows use `.venv/Scripts/python.exe` in place of `python` and a short test temporary path.

## Offline verification

```
python -m pytest -q --basetemp work/p9
python scripts/verify_phase9.py
```

Verification checks every Phase 8 baseline file hash, both production/data freezes, independently generated heldout and truth, the entire request manifest and exact parsing, inherited budget reservations, query prefixes, semantic differentials, all runtime conditions and saved container outputs, deterministic analysis and final release hashes. It does not make API requests or launch containers. Locally frozen descriptions are prospective within this research run, not external preregistration.

## Acquisition and isolated execution

The saved primary protocol is 288 requests plus48 fixed repeats. All raw failures are retained. The acquisition script uses durable dispatch intents and cached raw results; no automatic retries. Never delete a failure/intent to obtain a better result. Reusing this release directory is an integrity check, not a fresh statistical replication. A fresh campaign needs its own predeclared directory and inherited ledger; do not overwrite this study.

The controller and workflow environment are separate scopes. The environment selects the actual synthetic world; controllers use only declared hypotheses, explicitly allowed observations, and visible gateway events. Synthetic code uses the finite interpreter, never host shell execution.

`scripts/container_phase9.py` documents the exact pinned image and flags: no network, read-only filesystem, no mounts, dropped capabilities, non-root uid65534, restricted resources. It transfers only trusted interpreter modules and synthetic jobs over stdin; credentials are excluded. Saved plans/intents/output/exit evidence can be audited offline.

## Recovery point

`archive-phase8-20261016` is the remote annotated tag for the last verified prechange commit `93eda0d23236912671c7b309eb78e7c80fd20db1`. Create a separate checkout from it when comparing or recovering. Phase9 adds files; it does not rewrite any previously tracked experiment result.

## Costs and scope

Only gpt-6-luna and gpt-4.1-mini; the Phase8 budget ledger remains an exact prefix. Historical unresolved reservations remain charged at their conservative bound. Dollar figures are local conservative accounting, not provider invoice totals. All tasks are synthetic; no real Skill sampling, execution, API transmission, or human annotation is part of this round.

# Phase 10 reproduction

Use Python 3.12 and the existing pinned requirements in `configs/requirements-lock.txt` and `configs/phase5-requirements.txt`. Run commands from the repository root. On Windows, substitute `.venv/Scripts/python.exe` for `python` and use a short test temporary path.

## Offline verification

```
python -m pytest -q --basetemp work/p10
python scripts/verify_phase10.py
```

Verification makes no API calls and launches no containers. It checks all 30,435 prior tracked file hashes; both prospective production/data freezes; independent heldout generation, truth, coverage and novelty; exact first-pass preservation; every saved model selection, request, dispatch and reservation; inherited budget bytes; semantic differentials; actual stopped query execution; all three runtime grids; every saved container payload, command and output; deterministic analysis; and final release hashes. Replaying a saved selection stream is not a new model replication.

For inspecting individual stages without changing results:

```
python scripts/run_phase10.py --replay
python scripts/experiment_phase10.py semantics
python scripts/experiment_phase10.py queries
python scripts/experiment_phase10.py interface
python scripts/experiment_phase10.py recovery
python scripts/experiment_phase10.py integrated
python scripts/analyze_phase10.py
```

Outputs are immutable: identical recomputation is accepted, differing bytes fail. Figure sources are retained beside five PNG/PDF pairs. Figure reproduction with `scripts/plot_phase10.py` additionally depends on the plotting environment; local repeated renders were checked separately. Release verification checks the retained figure bytes without demanding cross-platform font rasterization identity.

## Acquisition and isolated execution

The frozen acquisition plan contains 288 streams: 24 new cases, two approved models, and six protocol/objective/representation cells. Each stream buys at most eight atomic queries. The full protocol requests one permutation; batch and next protocols receive paid feedback before subsequent selections. Every invalid response and any transport or budget failure is retained. There are no automatic retries, truth-based repairs or guessed fallbacks. Durable dispatch records prohibit silently repeating an uncertain request. Fresh model replication requires a separately declared output directory and inherited budget; do not delete this campaign's records to rerun it.

The campaign acquired fixed-length streams for matched prefix comparisons. Stopping experiments really omit interpreter executions after their evidence predicate becomes ready. Prefix-specific model cost is counterfactual scenario accounting: all requests actually made by this acquisition remain charged to the campaign ledger. Saved future selections are never presented as information available before a stop.

The environment chooses the actual synthetic world. Controllers receive only public hypotheses, permitted immutable observations and visible gateway events. Goal probes are charged planning work and cannot inspect future faults. Original paid execution evidence is the only runtime authorization handoff. Integrated runs have zero hidden audit calls. Ambiguous commits terminate recovery.

`scripts/container_phase10.py` records the pinned image, no-network/read-only/nonroot execution, dropped capabilities, resource limits and absence of host mounts. Trusted interpreter modules and synthetic jobs are supplied through stdin; no credentials or real Skill data enter the containers. Conditions have fresh memory within 250-condition batch containers. Saved plans, intents, exits and outputs permit offline auditing. A repeated container command on this release reuses retained evidence; it does not claim a second fresh execution.

## Archive and accounting

`archive-phase9-20261016` points to the previous verified commit `738c1dbe60a42c941662878e849a9432d4543c86`. It was pushed before this round's implementation. Create a separate checkout from that tag for comparison or recovery. Every previously tracked experiment file remains byte-identical.

The cumulative authorized cap is $29.551575125. Phase 10 inherits a conservative bound of $17.383292550 and additionally caps its own reservations at $6. Both completed usage and unresolved historical reservations remain accounted for. Final values are in `results/phase10/api/summary.json`; these are local conservative accounting, not provider invoice totals. Only `gpt-6-luna` and `gpt-4.1-mini` were authorized. No API key is stored in this repository.

All new tasks use a finite synthetic language and an independently authored executable reference. Production and data freezes were prospective within this local run, not external preregistration. Expanded world/fault/budget conditions are not independent new tasks. There is no real Skill experiment, transmission or human annotation in Phase 10.

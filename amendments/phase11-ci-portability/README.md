# Append-only Phase 11 CI portability amendment

Original research release: `088af27ebdbd1e12037d17fcffd80c4abb9926b4`.
The original 8,117 added files, including the production/data freezes, every
experiment result, paper/report, and both release manifests, remain unchanged.
The earlier 37,907 baseline files also remain unchanged. This amendment changes
only how tests with an optional dependency are collected in legacy environments.

## Observed failure

The frozen offline, Phase 3 and Phase 4 workflows install only
`configs/requirements-lock.txt`. They do not install `tiktoken`, introduced in
the separate `configs/phase5-requirements.txt`. They nevertheless collect the
current full test directory. Three new Phase 11 acquisition tests genuinely
need tiktoken, so the first remote run failed with `ModuleNotFoundError`.
The representative original failure log is preserved in `initial_failure.log`.
Original run URL:
https://github.com/victorcao1104/taskskillguard-research/actions/runs/38905898717

This was a dependency/CI integration error, not a changed experimental result.
The full local environment passed 1,503 tests, four skips and 150 subtests before
publication. Existing later workflows install the additional dependency. The
dedicated Phase 11 workflow explicitly installs and imports tiktoken before tests
and replays every recorded request with the verified tokenizer cache.

## Narrow correction

A new root `conftest.py` marks exactly these three tests skipped **only** if
`importlib.util.find_spec('tiktoken') is None`:

- `test_online_actual_dispatch_stops_before_next_request`
- `test_failure_retains_paid_prefix_no_fallback`
- `test_surrogate_token_matched_padding`

All are in the unchanged `tests/test_acquisition_v11.py`. No other test is skipped
by this amendment. An installed-but-broken package, invalid cache/hash, or failed
assertion still fails. In the dedicated `Phase eleven executable evidence
contract` workflow, missing tiktoken is an error rather than a skip. Local users
can enforce the same rule with:

```text
python -m pytest -q --require-tokenizer --basetemp work/full-required-tests
```

Green legacy workflows therefore have three additional explicit dependency
skips and are **not** equivalent to the full dedicated Phase 11 check. Their
purpose remains checking their historical evidence. No dependency is installed
implicitly by pytest and no network or model call is added.

Five new tests check the precise node-ID boundary, installed-dependency behavior,
strict missing-dependency failure, and amendment hashes. A separate manifest
hashes the amendment and binds it to the original release manifest. Session
startup checks those hashes. The frozen `verify_phase11.py` continues to verify
the original release unchanged; its inventory intentionally does not include
this new amendment, whose provenance is separate.

All original failure evidence and commit history remain available. Reproduction
uses the normal full dependency setup in `docs/phase11_reproduction.md`; the
research findings, costs, datasets, and paper claims are unchanged.

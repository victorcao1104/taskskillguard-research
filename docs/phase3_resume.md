# Phase 3 real-context follow-up

This is a separate follow-up acquisition after the frozen primary acquisition. The primary 2,160 conditions contain 1,844 valid outputs, 120 empty-candidate exclusions, and 196 unresolved outputs. The separate phase-aware replay resolves 22 commentary/final envelope mismatches using the same saved responses, leaving 174 unresolved conditions. New follow-up samples must remain distinguishable from both primary results and the retrospective replay.

## Eligible conditions

Selection reads the **original** primary row and raw response. A condition must have original status `unresolved` and one of these exact external/protocol causes:

- HTTP 429 with raw status `api_error` and error code `credit_balance_exhausted`: 173 conditions.
- Raw and response status `incomplete`, with `incomplete_details.reason=max_output_tokens`: one condition.

The 174 conditions span 16 skills and include 87 conditions per model. Valid model claims of `unknown`, the 22 phase-only failures, and other refusal/schema/semantic failures are not selected. The complete primary condition grid and all primary acquisition track counts are checked before creating the follow-up manifest.

Every condition receives a new `trial_id` and retains its original job ID, request hash, raw-file reference, and raw-file SHA256. The original request is reconstructed exactly and compared with the saved request before use. Models, developer/user messages, source snippets, schema, and replicate value are preserved. The single truncated request raises its output cap from 3,000 to 6,000 tokens and is marked `adaptive_output_cap=true` with an explicit request-change record. Credit-failure requests retain their original cap. Identical requests can retain the same content hash, but the new trial identity and separate raw-cache directory distinguish the observation.

## Default preparation and explicit execution

The default command only prepares artifacts and reads no credentials:

```powershell
.venv/Scripts/python.exe scripts/resume_real_phase3.py
```

It writes `results/phase3_followup/manifest.json`, `pending_trials.jsonl`, `dry_run_summary.json`, and an exact-byte copy of the primary budget ledger at `api/budget.jsonl`. Repeating preparation checks manifest/trial identity and the inherited ledger prefix. The pending manifest remains the original plan after execution; `summary.json` reports actual progress.

Only after the user authorizes the follow-up and restores the external account balance, run with the existing approved environment file:

```powershell
.venv/Scripts/python.exe scripts/resume_real_phase3.py --execute --env-file <existing-approved-env-file>
```

There is no worker-count option: execution is sequential. The first unchanged credit-failure request probes restored credit before the adaptive truncation trial. A renewed `credit_balance_exhausted` stops the run after that first failed call, preserving its result and reservation. Restarting the command does not automatically retry that failure or advance through the remaining failures. Completed follow-up trials and any cached response from an interrupted run are reused; no trial is automatically sampled twice. An exclusive execution lock prevents concurrent ledger writers. An interrupted process may leave the lock and requires inspection before it is removed.

## Budget and evidence

The forked ledger starts with the exact primary bytes, including all 179 outstanding/unknown-billing reservations. Its inherited conservative cost is **$13.5163768**. The limit remains **$20 total**, leaving **$6.4836232** under the same accounting; this is not a new $20 allowance. Each request uses the unchanged `ClientV3` reservation and settlement rules. An insufficient remaining reservation budget stops before calling the client. No reservation is forgiven because of an HTTP error or missing usage.

Each new raw response stays in `results/phase3_followup/api/raw/`. The phase-aware adapter validates the entire envelope and selects only its unambiguous final answer before the unchanged detection parser runs. Invalid actual final answers remain unresolved. Model `unknown` labels remain model claims; no semantic-accuracy score or human annotation is inferred.

Checkpointed follow-up rows are written only to `results/phase3_followup/api/real.jsonl`. Local atomic checkpoint replacement retries a Windows sharing violation at most eight times with bounded backoff; it never repeats the API request. A persistent replacement failure retains the temporary checkpoint. The summary reports planned/observed/valid/unresolved coverage by model and context, original/new raw references, requests made during the invocation, remaining trials, stop reason, cumulative cost, and follow-up cost. Referenced primary inputs and raw files are SHA256 inventoried and rechecked. Frozen primary files, the original budget ledger, and retrospective replay outputs are never rewritten.

## Verification

The first ten tests failed before implementation existed, then passed against the runner. Additional tests cover changed primary input and invalid actual follow-up final answers. Two Windows-sharing tests failed before bounded replacement retry was added. Tests use fake clients and fixture environment paths; they make no network calls and read no real credentials. Behavioral coverage includes dry-run selection, byte-exact inherited budget prefix, $20 cumulative enforcement, one-call credit failure stopping, no automatic retry on restart, unchanged requests, phase parsing, primary immutability, acquisition completeness, duplicate conditions, explicit execution gating, and local-only replacement retries.

The focused suite passed **14 tests**. The actual default dry-run produced the 174-trial manifest with **zero API calls**, an exact primary-ledger byte copy, and a conservative additional reservation upper bound of **$2.1350941**, below the remaining **$6.4836232**. These are preparation facts, not follow-up acquisition results.

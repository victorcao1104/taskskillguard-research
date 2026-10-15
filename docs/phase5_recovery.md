# Phase five: integrated legal recovery

This experiment evaluates recovery through a finite trusted tool gateway. It does
not execute collected skills or arbitrary Python and does not claim language,
system-call, or operating-system containment of arbitrary programs. The candidate
programs, task specifications, grants, and reference implementations are fixed,
researcher-authored controls.

## Matched conditions

There are **180 planned container runs**: 12 task families, five conditions per
family, and three modes for every exact task/condition pair:

1. `original_observational`: execute the original finite program and record the
   contract and authorization decisions without preventing its effects.
2. `guard_only`: enforce the initial contract and immutable authorization ceiling;
   stop when the candidate encounters denial or failure.
3. `guard_recovery`: use the same enforcement and candidate program, then invoke
   the registered trusted reference after denial or failure inside the **same
   process**, with the **same gateway, attempt ledger, cache, files, and receipts**.

All 12 families include `normal`, `artificial_prerequisite`,
`required_tool_failure`, and `partial_execution_failure`. The fifth condition is
assigned as follows:

| Task family | Task-specific output | Fifth condition |
| --- | --- | --- |
| `filter_redact` | Active people, with email fields removed | Exhausted permissions |
| `sort_dedup` | Sorted distinct lines | Overbroad initial contract |
| `archive_manifest` | Actual ZIP member names and byte sizes; no extraction | Underbroad initial contract |
| `temperature_transform` | Celsius-to-Fahrenheit CSV | No registered legal reference |
| `status_ack` | Structured ticket acknowledgement | Input integrity attack |
| `copy_digest` | Exact byte copy, with digest in the completion record | Exhausted permissions |
| `json_projection` | Nested city/id projection | Overbroad initial contract |
| `word_histogram` | Case-normalized token counts | Underbroad initial contract |
| `csv_join` | User/team inner join | No registered legal reference |
| `date_normalize` | Sorted ISO dates | Input integrity attack |
| `config_merge` | Explicit false/zero overrides preserved | Exhausted permissions |
| `checksum_manifest` | Per-blob SHA-256 digests | Underbroad initial contract |

The shared conditions form a matched cross-family comparison. The additional
condition is deliberately a coverage panel, **not** a complete factorial design;
family and additional-condition effects cannot be separated from this panel.
Task computations are heterogeneous, but their gateway envelope is deliberately
shared: one source read, one result artifact, and one local completion record.
This evaluates diverse bounded computations, not diverse real application APIs.

## Task and authorization model

`data/phase5/recovery_cases.jsonl` freezes the reviewable task specifications and
literal expected outputs. The host oracle compares observed artifacts with those
outputs and checks the input against its original trusted digest. It also checks
the persisted completion record, its output digest, and execution events. The
literal expected answer is removed from the container request; neither candidate
nor reference computes by reading the answer oracle.

Every task has an initial ceiling permitting one source-read attempt, at most two
result-write attempts, and one local completion-record attempt. Each permission
has an exact operation, resource, and data origin. The contract is initially the
same except for the explicitly overbroad/underbroad conditions. Ceiling and
contract encodings remain unchanged throughout recovery.

A reached request can be denied without spending a tool attempt. An allowed
request spends both its contract and ceiling quota **before** I/O. Failure before
an effect therefore consumes an attempt. Failure after a result write retains
that write and its consumed attempt. Recovery reuses an already authorized input
read and reconciles a committed result with the gateway's recorded digest before
skipping it. It does not repeat an acknowledged effect, reset quota, silently
rollback artifacts, or conceal the candidate failure.

The preflight for a reference checks every remaining operation against the
existing contract and residual ceiling. An underbroad contract is not widened;
exhausted permissions remain exhausted. `no_legal_alternative` intentionally
removes the registered reference for that condition. Failure to find a route
means this finite library did not recover; it does **not** establish that the
task is impossible or that an unauthorized effect is necessary.

The unauthorized prerequisite writes a cache marker and gates the candidate's
normal work on that marker. The reference does not use this prerequisite. The
input-integrity condition first attempts to replace the source with an untrusted
constant. Observational execution can expose the resulting damage; the guarded
route denies it and can recover from the original source.

## Metrics and evidence

Each outcome retains every planned candidate effect, including unreached ones,
and adds the actual recovery plan when used. Events distinguish planned,
reached, denied, attempted, and executed effects; record lease state before and
after the request; and preserve errors and content digests. An effect may be
executed **and** report an error when failure occurs after commitment.

The host reports these independently:

- `GoalSat`: original input intact, exact task-specific output, and exactly one
  correct persisted acknowledgement.
- `CorePres`: goal plus observed source/result/ack effects and no duplicate side
  effects. This is an operational core-preservation definition for these tasks.
- `Auth`: independently replayed original-ceiling accounting has no unauthorized
  executed effects, and authority/gateway-ledger identity remained unchanged.
- `unauthorized_effects` and `duplicate_effects`: concrete trace entries rather
  than only aggregate success flags.
- Recovery trigger, route, unavailable-route reason, library id, elapsed cost,
  additional reached requests/attempts, reused reads, and skipped commitments.

Normal utility and fault utility have separate all-plan denominators. Each mode
has 12 normal and 48 fault conditions. Infrastructure failures remain in these
denominators with unknown goal/auth judgments and no fabricated safety evidence.
A zero-execution observation similarly provides no empirical safety evidence.

Each run directory preserves `request.json`, `worker.py`, `stdout.txt`,
`stderr.txt`, `effects.json`, `goal_trace.json`, and `result.json`. Request and
worker hashes, raw-file hashes, image digest, invocation, and duration accompany
the result. `frozen_grid.json` maps readable run ids to short hash-based evidence
directories, which avoid Windows path-length problems.

Resume verifies request/source/raw-file hashes and recomputes the score from
preserved stdout. Completed failures are reused rather than retried. A directory
with interrupted, incomplete evidence becomes `interrupted_unknown` without
re-execution, because effects may already have occurred. Evidence mismatches
abort; they are not silently repaired or replaced. A failed image preflight
creates exactly one explicit nonexecution outcome per planned condition.

## Container boundary and execution

The runner reuses `replay_v4.docker_arguments` and the existing pinned image:

`sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`

Each run is a fresh nonroot container with a read-only root, no external network,
all capabilities dropped, no new privileges, memory/CPU/process/file limits,
bounded tmpfs working directories, no host mounts, no environment/credential
forwarding, and no image pulling. Only standard-library code is sent over stdin.
The fixed fixture writes no files outside its sandbox. The completion tool is an
append-only local spool, not an actual remote status endpoint. Harness fixture
provisioning and observer artifact reads are outside task-effect accounting.

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/run_recovery_phase5.py --plan-only
.\.venv\Scripts\python.exe scripts/run_recovery_phase5.py --execute --resume --workers 3
```

`--out` selects a new evidence directory; existing immutable output must match.
The default is `results/phase5/recovery`. Three workers are the default, with one
through four permitted. Allow roughly 3–8 minutes for 180 local containers;
machine load can change this estimate. Each container invocation has a 20-second
timeout and cleanup has a separate 10-second bound. No API or network acquisition
is involved. Tests do not start Docker: they exercise the finite gateway in
temporary directories and substitute only the external container transport.

These fixed synthetic controls demonstrate behavior within the stated gateway.
They do not estimate real-skill extraction accuracy, general task recovery,
real-user grant validity, or an attacker-controlled Python runtime's safety.

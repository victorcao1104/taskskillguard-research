# Phase 11 bounded commit-status reconciliation

This is a finite synthetic implementation of established completion-record and
fencing ideas, not a new exactly-once protocol. It performs no host or network
effects. No heldout generator or heldout data was used in its implementation.

## Entry point and result contract

`tsg.commit_v11.execute_certified(case, route_index, world_index=0, fault='none',
policy='strict_stop', quota=32, status_budget=1)` executes only the supplied route.
Route 0 is the parsed source; route i greater than 0 is `case['routes'][i-1]`.
The caller must check the certificate before calling this function. This function
does not acquire evidence, validate a route certificate, rank routes, try a fallback
route or invoke a planner. Programs use the frozen Phase 6 AST validator/walker.
At most four complete walker attempts are allowed, always on that same route.

Result fields include `files`, `emits`, `goal`, `authorized_goal`,
`failure_reason`, `attempts`, `attempt_log`, `charged_calls`, `effect_calls`,
`status_calls`, `remaining_quota`, `remaining_status_budget`, `duplicate_effects`,
`unauthorized_effects`, `receipt_reuses`, `controller_trace`, `status_log`,
`environment_trace`, `fault_diagnostics`, `trust_model`, `route_index`, and
`planner_calls` (zero). `trace` aliases `controller_trace`, rather than the old
runtime's private-effect trace. A logical duplicate is a second mutation under
the same logical receipt key, including an idempotent file overwrite. A successful
goal alone does not imply duplicate freedom: evaluate `duplicate_effects` separately,
especially for the explicitly unsafe negative control.

Every dispatched effect, including a denied call or a deduplicated retry reaching
the gateway, consumes one shared call. Local cached-receipt reuse is free, as in
the frozen runtime. Each status call consumes both one shared call and one status
budget unit. Exhausted budgets prevent the query and consume no call. Attempt-log
effect costs exclude reconciliation calls made between attempts; top-level counters
include all of them. Interpreter steps are recorded per attempt. There is no polling
loop. A single injected ambiguity means these fixtures normally use at most two
attempts, but the controller also has a hard four-attempt bound.

## Information boundary and identities

The driver builds a private service from the selected world and fault schedule.
The controller receives only dispatch, query and verification capabilities, a run
epoch and an opaque grant-context digest. It receives no world index, file store,
fault name, durable record table, pending queue or private committed bit. It sees
the same ambiguous-outcome response for an applied mutation and a fenced noncommit.
The driver observes private outcomes only after execution for measurement; neither
goal evaluation nor environment diagnostics controls retries.

An operation binds an immutable logical key, chosen route, generation, full
`(operation, resource, value)` signature, execution epoch and grant-context digest.
The epoch hashes the public case, quota and runtime version. Every invocation has
an isolated service namespace; deterministic epoch/key generation is for repeatable
simulation, not a production cross-process identity allocator. Production systems
would need unique run epochs, durable shared namespace management and real key
provisioning. The HMAC key is held by the synthetic service; controller code has
only a verification capability. HMAC packets model authenticated responses and
reject changed content, wrong IDs, wrong signatures, wrong epochs and bad MACs.
Python reflection is not a security boundary, and the deterministic synthetic key
is not claimed to protect against an attacker executing Python inside the process.

The controller retains original read receipts across retries. Thus restarting a
route that read a file and then overwrote it consumes the initial read value again.
A repeated explicit key with a different signature is denied before any mutation.
Grants and initial snapshots are immutable for this experiment; live external drift
or revocation would require revalidation and lies outside this recovery claim.

## Four policies and fault meanings

* `strict_stop`: ambiguity stops immediately; no status call.
* `terminal_status`: one bounded query may import an authenticated exact committed
  receipt, or accept fenced terminal noncommit and increment the attempt generation.
  Only these two terminal outcomes license another walker attempt. Absent, pending,
  unavailable, contradictory, stale and mismatched responses stop.
* `same_id_dedup`: a stronger backend atomically retains completion records and
  suppresses duplicate dispatches under the same operation ID. It retries that ID
  without a status query. A pending ID stays pending; a fenced ID cannot execute;
  an already committed ID returns the durable receipt. This control assumes a
  capability beyond terminal-status access and is reported separately.
* `unsafe_absence_retry`: a synthetic non-idempotent backend accepts a fresh-ID
  retry on authenticated absence. `pending_absent` delays the first mutation,
  reports no committed record, commits the fresh retry, then commits the original.
  The result contains a duplicate logical mutation. Freshness and authenticity of
  absence do not imply cancellation or terminal noncommit.

Exported `FAULTS` consists of `none`, and each base fault below at the first mutation,
the second mutation (`second_` prefix), or the first emit (`emit_` prefix):

| Base fault | Actual environment transition | Status response |
| --- | --- | --- |
| `ambiguous_after` | Effect and durable completion applied before lost acknowledgment | Exact committed receipt |
| `terminal_noncommit` | No effect; terminal record fences the old ID | Exact fenced noncommit |
| `pending` | Original remains queued; no effect by observation horizon | Pending |
| `pending_absent` | Original queued, later released only after fresh-ID retry | Absent |
| `unavailable` | Effect committed | Unavailable |
| `absent` | Effect committed | Absent |
| `retention_expired` | Effect committed | Unavailable, modelling unusable retained evidence |
| `stale`, `wrong_epoch` | Effect committed | Authenticated wrong epoch |
| `wrong_signature` | Effect committed | Authenticated different payload |
| `wrong_operation` | Effect committed | Authenticated different operation ID |
| `forged` | Effect committed | Invalid MAC |
| `contradictory` | Effect committed | Explicit unusable contradictory outcome |

Fault injection occurs only after grant/conflict checks and when quota permits a
real mutation dispatch. Unreachable targets are retained and marked
`fault_triggered=false`, rather than counted as recoveries. Unsupported observations
such as absent-after-commit and retention failure test fail-closed behavior; they
do not establish that a correct durable status service should return those responses.
Status-quota exhaustion is tested by limiting quota or `status_budget`, rather
than secretly bypassing accounting through a fault schedule.

## Conditional preservation argument

Assume a valid initial certificate for this fixed route; immutable grants and world
semantics; deterministic bounded VM evaluation; exact read-receipt retention;
collision-free operation identities in the service namespace; authenticated complete
binding verification; atomic durable coupling of effect and completion record;
and enforceable terminal-noncommit fencing. Start from an authorized history with
at most one committed mutation per logical key.

Induct over controller transitions. A fresh dispatch is grant-checked and charged.
A cached exact receipt performs no effect. On ambiguity, strict stop performs no
further operation. A verified committed status imports an existing receipt, so the
replayed prefix cannot dispatch that logical mutation. A verified terminal noncommit
permits a fresh generation only after the old ID is fenced; the old dispatch can
never subsequently commit. All other evidence or exhausted budgets stops. Repeated
key/signature conflict also stops. Therefore terminal-status reconciliation preserves
authorization and at-most-once logical mutation under these premises. The stronger
same-ID control instead relies on the backend's atomic durable duplicate suppression.

This is a conditional safety argument, not unconditional liveness. Queries can use
quota that the original fault-free certificate needed for its suffix, so reconciliation
may safely fail despite a valid original route. Pending operations can remain pending.
The unsafe absence retry violates the fencing/dedup premise and its delayed-original
counterexample is expected to fail at-most-once. Neither file goal persistence under
concurrent overwrite nor downstream message delivery is proved; emit means acceptance
into the in-memory emitted-effects list. Real distributed durability, crash recovery,
retention leases, epoch allocation, transport authentication, concurrency and filesystem
semantics are not implemented. These boundaries follow the research critique's
distinction between evidence validity, permissibility and execution guarantees.

## Validation

Hand-derived tests cover preserved initial read snapshots, first/second/emit fault
locations, invalid evidence, quota exhaustion, same-ID pending/dedup behavior,
terminal fencing of the old request, a modified signed receipt, unchanged guarded
fault-free behavior over quotas 0 through 5, denied effects, key conflicts, exact
route execution, unreachable targets and the delayed-original duplicate counterexample.
The focused tests use `--basetemp=work/p11-commit-tmp`. Full-suite integration is
owned by the root task. All pre-existing tracked source files remain unedited.

# Phase 7 observed-error recovery

`tsg.recovery_v7.execute(case, selector, policy, fault="none", allowed_ids=None,
world_index=0, quota=16)` implements the frozen Phase 7 recovery interface. It
adds no host I/O, language operation, privilege, alternate route, or oracle.
Source parsing, AST validation, grants, receipts, effect execution, goals,
result accounting, and dry simulation reuse the unchanged `runtime_v6` module.

## Policies and selection

`legacy` preserves `selection_v6.execute_selection`: try the original route
twice, then choose among remaining alternatives, retiring each chosen
alternative before executing it. It stops on success, an unknown commit,
quota-exhausted execution, no feasible alternative, or four actual attempts.
For the original four fault settings, all existing result fields must match
the frozen selector exactly. Only `fault_diagnostics` is new.

`safe_retry` first executes the original route once. On an observed
`transient_before` or `known_after`, the next actual attempt repeats that same
route, without a new planning round. Every other nonterminal failure retires
that route. The next selection round simulates every remaining alternative.
Unknown commit (`ambiguous_outcome`) and `quota_exhausted` stop immediately.
There are at most four actual attempts, including the original and every retry.
The policy never reads the requested fault, injection counter, or future fault
schedule to select a route; it branches only on observed errors and public
simulation results.

Both selectors perform identical planning within a selection round: dry-run
each remaining public route from copies of current files, emits, signatures
and receipts using trusted grants. A route is feasible only when simulation
has no error, reaches the goal, and fits the remaining live call quota.
`first_feasible` chooses the first feasible catalog entry; `search_equal`
chooses the fewest remaining calls, breaking ties by catalog order. Dry runs
never inject faults, spend live quota, or change actual state. Equal planning
per round does not imply equal total planning between different policies or
after their observed states diverge.

## Fault timing and diagnostics

`FAULTS`, in reporting order, is `none`, `transient_before`, `known_after`,
`ambiguous_after`, `second_transient_before`, `second_known_after`,
`second_ambiguous_after`, `double_transient_before`.

The first three nonempty settings inject at eligible mutation dispatch 1;
the `second_` settings inject at dispatch 2; `double_transient_before` injects
before dispatches 1 and 2. The dispatch counter persists across route changes
and attempts. Eligible operations are write, emit and delete, after permission,
signature, receipt-reuse and available-quota checks. Reads, denied calls,
conflicting signatures, reused receipts and quota-blocked calls do not advance
the schedule. A failed precommit dispatch does advance it; its next retry is a
new dispatch. Repeated executions of one static site can therefore occupy
different schedule positions.

The gateway subclasses the old machine only to preview eligibility and choose
the fault supplied to its inherited effect method. That preview uses the same
pure expression evaluators and exact key/signature rules; it changes no
execution state. The inherited method remains solely responsible for charging,
permissions, commits, receipts, conflicts and emitted trace entries. The old
injection latch is reset for each dispatch; execution receipts never are.

The added `fault_diagnostics` object contains:

- `fault`: requested grid setting.
- `eligible_mutation_dispatches`: all eligible actual mutation dispatches.
- `scheduled_fault_count` and `injected_fault_count`: distinguish zero, partial
  and complete schedule activation.
- `fault_triggered`: at least one fault was injected; false also for `none`.
- `schedule_completed`: all scheduled injections occurred; true for `none`.
- `injections`: observed dispatch number, actual fault type, attempt,
  route index and site ID for each injection.

The injection diagnostics are reporting output only. An unreached second
dispatch remains untriggered and is not silently treated as an injected fault.

## Accounting and limits

Failure calls consume shared quota exactly as in Phase 6. A known committed
operation can be replayed using its receipt even at zero remaining quota; a
new effect dispatch cannot. Reaching zero remaining calls alone is not a stop
if the route can complete entirely by reusing receipts. A physical goal reached
before an error is not an authorized successful completion.

The original model gate applies only to route 0, and all alternatives still
require trusted grants. This preserves the measured catalog bypass behavior;
it does not credit model judgment for gateway enforcement. Cached reads and
signature conflicts are preserved even when they prevent goal achievement.
No receipt is cleared and no unauthorized effect is performed to improve
success. A route classified as permanent is retired for this execution even
if a different hypothetical future state could have made it feasible.

The grid covers the first two eligible mutation dispatches and a repeated
precommit transient. It does not cover arbitrary fault positions or arbitrary
fault processes. The gateway's eligibility preview is intentionally coupled
to frozen Phase 6 gateway rules; any later gateway change requires a new
compatibility audit. This implementation corrects a bounded policy, not a
general distributed transaction protocol.

## Verification boundary

`tests/test_phase7_recovery.py` uses hand-authored controls and only
`data/phase6/dev.jsonl`. It does not load Phase 7 inputs, reference truth,
evidence, protocols or model results. The legacy comparison spans every old
development world, both selectors, the original four faults, quotas
0/1/2/8/16, and unrestricted versus empty model gates, plus malformed-source
and invalid-alternative controls. Other tests cover the sole-alternative
correction, retirement after permanent errors, unknown-commit stop, dynamic
fault positions, repeated transients, receipt preservation, dry-run isolation,
permission enforcement, equal planning, option validation and input isolation.

Run the independent recovery tests with:

```text
.venv/Scripts/python.exe -m pytest tests/test_phase7_recovery.py --basetemp work/pytest7recovery
```

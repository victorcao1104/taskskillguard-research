# Phase 7 independent prefreeze review

2026-10-16. Reviewed against `docs/phase7_design.md` and immutable baseline
`aac66f057408dafeca817e1dc059ff47b7027954`.

## Decision

No blocking finding remains in the reviewed prefreeze implementation. This is
permission to freeze the implementation for the planned evaluation, not a claim
that the held-out experiment has succeeded or that any model improved.

The reviewer made no production edits, API calls, commits, or baseline-file
edits. Added only `tests/test_phase7_review.py` and this report. All code and test
editing by the reviewer ended before the coordinator's freeze authorization.

## Scope and blindness

Reviewed the new typed reference, source solver, certificate checker, protocols,
recovery controller, durable budget adapter, acquisition, experiment generation,
container runner, offline verifier, analysis, and Phase 7 tests. Consulted the
inherited interpreter, selector, API client, budget, and serialization code where
the new code delegates behavior.

Did not open `data/phase7/heldout.jsonl`, the Phase 7 generator source, or Phase 7
outcomes. Did not evaluate held-out examples. All independent probes use hand
constructed cases or fake provider/container responses; existing selected tests
use synthetic examples and old development fixtures. The generator test was
explicitly deselected.

## Findings resolved before freeze

| Finding | Importance | Resolution verified |
|---|---|---|
| Integrated execution rows omitted `allowed_ids` and certificate acceptance, preventing measurement of success after an empty original-route gate. | P2 | Gate metadata now travels in job metadata and therefore both host and container rows. A rejected-certificate probe verifies raw and certified gates remain distinct. |
| Truthy non-object JSON predictions could crash protocol parsing instead of becoming protocol failures, including the inherited B0 parsing path. | P1 | Phase 7 now validates uniformly and guards the prediction object before reading judgments. Twelve probes cover arrays, strings, numbers, and booleans across all three protocols. |
| Evidence candidate IDs were string-coerced for coverage but then indexed without coercion, allowing malformed IDs to raise or be confused with valid string IDs. | P2 | IDs are required to be strings before coverage checks. Five malformed-ID probes reject without a crash. |
| The inherited budget append closed the file without syncing it, weakening preservation of uncertain reservations after an operating-system interruption. | P1 | A new `BudgetV7` flushes and syncs each append before publishing the in-memory entry. A fake provider is reached only after the reservation sync; a sync failure prevents provider dispatch. Old budget files and code remain intact. |
| Container timeouts escaped before writing captured output and terminal failure evidence. | P2 | Timeout and launch failures now save captured output and a terminal error record. A second invocation refuses to retry the failed batch. |

These findings were communicated while development was still open and fixed by
the coordinator. Fixes sometimes landed before the review probe's first run;
this report does not claim a recorded red-to-green test history for each fix.

## Semantic and attribution assessment

- Typed truth executes only reference ASTs; the source solver parses source and
  uses the separate production interpreter. Aggregation is implemented separately.
  Inactive sites, baseline failure, no legal route, open catalogs, and mixed worlds
  retain the intended distinctions. Existing development tests confirm collapsing
  `not_applicable` to `unknown` agrees with the old truth.
- Evidence checking compares every required label and per-world fact, including
  strict boolean/integer distinctions. It is a finite solver and must be credited
  as trusted checking work, not as model reasoning. Raw, certified, and solver
  integrations are separately named.
- Both recovery policies retain the same actual-call quota, four-attempt cap,
  permissions, receipts, and simulation machinery. Fault injection occurs at
  eligible mutation dispatches. The selector reads observed state and errors;
  its dry simulation has no access to future fault schedules. Existing tests
  compare legacy outputs field by field on development examples and exercise
  receipt reuse, conflicts, delayed faults, exhausted quotas, and ambiguous stops.
- The original-route gate does not authorize alternatives. Alternatives remain
  governed by trusted exact grants. Catalog recovery can bypass an empty model
  gate, so zero unauthorized side effects are not evidence of model accuracy.
- The acquisition path uses a fresh cache, durable no-retry intents, one shared
  thread-safe ledger, inherited ledger bytes, and the existing conservative price
  bounds. Preflight reservations are bounded by both the remaining cumulative
  limit and the Phase 7 cap. Usage costs are conservative per-condition allocations,
  not invoices; actual request hashes and ledger charges must accompany totals.
- The container command pins an image digest, disables networking, uses a read-only
  filesystem and non-root user, drops capabilities, and bounds CPU, memory, and
  processes. No host mount is passed. Conditions share batch containers, as the
  design states. This review inspected the command and synthetic failure behavior;
  actual container execution and host/container equality remain evaluation work.
- Accuracy analysis keeps protocol failures as missing and incorrect, separates
  typed from collapsed spaces, separates old from held-out results, and uses family
  bootstrap summaries. Certificate coverage, unknown/not-applicable confusion,
  unmatched pairs, fault reachability, and cost coverage remain explicit.

## Fresh verification evidence

Executed from the repository root:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_phase7_truth.py tests/test_phase7_evidence.py tests/test_phase7_recovery.py tests/test_phase7_analysis.py tests/test_phase7_review.py -k 'not generator' --basetemp work/pytest7review
101 passed, 1 deselected in 3.96s
```

The independent review file contributes 23 passing probes. A fresh tracked diff
against the baseline was empty. This check does not certify the newly generated
data, which was deliberately kept blind.

## Required post-execution review

Before interpreting or releasing results, separately inspect the full semantic
audit, held-out collapse equivalence, request completeness and deduplication,
ledger preservation and unresolved reservations, all host/container comparisons,
legacy equivalence, reachable versus untriggered faults, paired analysis and
failure artifacts, and the final report's claims. Confirm the final baseline and
freeze hashes. No observed success rate, model comparison, cost improvement, or
generalization conclusion is approved by this prefreeze review.

## Post-freeze, pre-API amendment review

After the first freeze, the coordinator disclosed two infrastructure failures and
requested an independent review before any paid model call. The reviewer then
opened the two affected held-out cases under that explicit authorization. This
does not alter the earlier prefreeze blindness statement. Generator source was
still not opened.

The first audit recorded 868/868 matching executions and matching typed labels,
collapsed labels, and evidence, but reported failed source coverage. Independently
checked both `p7-branch_bundle-0` and `p7-branch_bundle-1`: reference function keys
are `dispatch, load`; source function keys are `load, dispatch`. Their source and
reference ASTs are equal. Their complete candidate records keyed by ID are also
equal. Only enumeration order differs:

```text
reference: s003, s005, s001, s002, s007
source:    s003, s005, s007, s001, s002
```

Reviewed `experiment_phase7_v2.py`: it reproduces the first audit and preserves
its files, then requires AST equality, full candidate-record equality by ID, and
unique IDs on both sides. It does not waive semantic/evidence failures. New
regression probes accept only the ordering case and reject duplicate, missing,
or changed candidate records and each original semantic failure flag.

The first container batch separately failed during module loading. The payload
serializer sorts JSON keys, so the original worker's dictionary iteration loaded
`tsg.recovery_v7` before `tsg.runtime_v6`. An isolated Python subprocess test
reproduces the original `ModuleNotFoundError` with the exact sorted-key payload.
The new `container_phase7_v2.py` loads the runtime before recovery explicitly;
the same subprocess test then returns the exact host execution result for a
known-after-commit recovery case. On Windows only UID availability is shimmed in
the test process. The production Docker command's resource and isolation flags
are unchanged. This test is not a substitute for actual container execution.

The original failed batch is retained. The new adapter uses a distinct batch
directory and checks the supplementary freeze before launching. The v2 launcher
checks both the original and supplementary freezes and corrected semantic audit
before calling the unchanged acquisition code. The v2 offline verifier uses the
corrected audit and additionally replays the saved analysis. These revisions
change neither workflow semantics nor fixtures, model prompts, recovery policy,
the 480 prepared requests, or pricing rules.

Fresh verification after both amendments:

```text
.venv/Scripts/python.exe -m pytest -q tests/test_phase7_truth.py tests/test_phase7_evidence.py tests/test_phase7_recovery.py tests/test_phase7_analysis.py tests/test_phase7_review.py tests/test_phase7_amendment.py -k 'not generator' --basetemp work/pytest7review_amendment
113 passed, 1 deselected in 5.41s
original frozen files verified: 21
```

The new amendment test file contributes 12 passing tests. The reviewer stopped
all production/test editing before signaling supplementary freeze readiness.
There are no remaining blocking findings in these amendments. All original
freeze hashes remain unchanged. Paid model outcomes, full container results,
and research conclusions remain outside this amendment approval and require
the post-execution review described above.

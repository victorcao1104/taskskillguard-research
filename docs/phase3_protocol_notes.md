# Phase three protocol implementation evidence

Date: 2026-10-15. Scope: new `models_v3`, `planner_v3`, and offline protocol tests. Existing source modules and historical results were not edited. No API request, key discovery, or live network access was performed in this subtask; HTTP boundaries were replaced only in offline tests. No pricing assumptions or historical budget entries were changed.

## Interface

`ClientV3` subclasses the existing `Client`; `call` keeps its arguments and adds optional `response_schema=None`. A bare JSON Schema is emitted as a Responses `text.format` with `type=json_schema`, `strict=true`, and a stable name. With no schema, the existing JSON-object request format remains. The full request, including schema and replicate, determines its fingerprint. Tags are metadata, not sample identity.

The existing caller-owned `Budget` is the only ledger. Input reservation includes the complete serialized schema and existing 4,096-byte headroom. Successful known usage settles normally. Unknown usage and API/transport failure retain conservative reservations. Cached failures remain failures; no retry occurs automatically. The existing one-process/single-writer budget constraint still applies.

`validate_record(raw, response_schema=None)` exposes `protocol_valid`, `diagnostic_codes`, `text`, `prediction`, and `schema_errors`. It accepts historical status/text records, but uses the original response envelope when present. One reasoning item plus one completed text answer is permitted. Refusal, truncation, multiple text parts/messages, duplicate JSON keys, non-object JSON, malformed envelope/content/status, unfinished messages, inconsistent completion status, and schema errors are explicit failures. It never concatenates or repairs outputs. Original API status and response evidence remain in persisted client records. The cache is revalidated locally without additional requests.

`parse_planner_record(raw, case)` returns exactly:

- `protocol_valid`: transport, response, JSON and schema validity only.
- `diagnostic_codes`: protocol errors plus semantic observations.
- `prediction`: parsed model object, preserved even when schema-invalid; null when unparseable or extraction is rejected.
- `reference_actions`: original finite v2 templates, selected and ordered exactly as the model requested; empty after protocol rejection.
- `scope_policy`: exact proposed operation/resource pairs with allow/default-deny and fixed platform leases; null after protocol rejection.
- `declared_unknowns`: exact raw model unknowns when a JSON object was parseable. A protocol-invalid record may therefore carry a non-list value; consumers must gate execution on protocol validity and handle diagnostic material safely.

Fixed leases only constrain existing scope: read expires at step 3, write/post at step 20, one use each. No missing permission, workflow step, or unknown is repaired. The scope policy uses the existing `Policy` projection (`rules`, `supported`, `default_action`); exact DONE body constraints are the runtime's responsibility. Reference IDs remain `ref_read`, `ref_transform`, `ref_write`, `ref_send`; the send template reads `public_status`.

Schema-valid incomplete scope, excessive scope, unknown resources, model-declared uncertainty, incomplete plans, wrong order, and repeated steps remain protocol-valid observations. The runtime independently validates authority, required effects, dependency routes, body and information-flow constraints. `MODEL_DECLARED_UNKNOWN` alone is not a blanket veto.

`make_planner_payload(case, catalog='split')` uses only the v2 trusted-task whitelist. The unified catalog is byte-for-value identical to the legacy list; the split catalog separates permission operations from the pure transform and identifies DONE as an independent public constant. The approved 2×2 experiment should hold the system prompt fixed while varying request format and catalog. `P_SYSTEM_V3` is available for the separate new/regression track.

## Test evidence

All commands use the repository's `.venv/Scripts/python.exe` and repository root. Tests patch `urllib.request.urlopen` with fully local response streams, including refusal, output ambiguity and transport failures.

1. Initial RED: `-m pytest tests/test_protocol_v3.py -q --tb=no --basetemp=.tmp_protocol_v3/red3` → **23 failed**, due to absent new modules. Earlier attempts exposed the restricted default temporary directory and a missing temporary parent; these were environment setup errors, then corrected before implementation.
2. First GREEN: same test file with `--basetemp=.tmp_protocol_v3/green1` → **23 passed** in 0.34s.
3. Additional status boundary RED: `-m pytest tests/test_protocol_v3.py -q --tb=short --basetemp=work/phase3-protocol-red-status -k 'completion_status or unknown_usage'` → **4 failed, 1 passed, 23 deselected**. Nonstring status caused a TypeError; conflicting and unfinished status were erroneously accepted. The unknown-usage budget behavior already passed.
4. Final protocol GREEN: `-m pytest tests/test_protocol_v3.py -q --tb=short --basetemp=work/phase3-protocol-green-status` → **28 passed** in 0.43s.
5. Full-suite intermediate snapshot while other domains were still being implemented → **203 passed, 19 failed, 4 skipped**. Failures comprised two execution attack opportunity tests (missing `a_leak` events) and all 17 new real-context tests while their implementation was absent. Both domain owners/root were informed; protocol tests all passed.
6. Second full-suite snapshot: `-m pytest -q --tb=short --basetemp=work/phase3-protocol-full-final` → **232 passed, 1 failed, 4 skipped** in 8.59s. Sole failure: `tests/test_execution_v3.py::test_invalid_protocol_with_nonlist_unknowns_is_a_recorded_failure`; its runtime attempted to iterate a malformed integer unknowns field. The execution owner was notified. Final integrated verification belongs to the parent after concurrent changes settle.

Coverage includes enum separation, rejection without executable scope, nested extra-property rejection, mandatory exact fields, legacy raw diagnosis, request/schema/replicate cache separation, budget reservation retention, limit rejection before network access, persistence of failure diagnostics, raw uncertainty preservation, missing scope without oracle repair, overbroad scope preservation, and exclusion of untrusted/oracle/input content from P.

Limitations: schema acceptance does not establish semantic correctness; model-declared unknown severity remains a runtime decision. No live model compatibility or experiment quality claim is made by these offline tests. Historical raw text-only records cannot establish how many underlying output messages existed; full-envelope records can.

# Discovery follow-up: line-ID representation repair

This is an additive **post-hoc protocol repair, exploratory**, motivated by the
completed primary acquisition. The original 24 discovery observations yielded
five protocol-valid empty responses and 19 invalid responses: 17 excerpt mismatch
failures, one API error, and one incomplete response. All primary inputs,
responses, failures, billing, and summaries remain first observations. This
follow-up does not replace them or recast the repair as a prospective primary
hypothesis.

## Fixed population and intervention

Repeat every original discovery condition: the same 12 zero-static-candidate
source bundles and both original models, for exactly 24 planned jobs. Selection
uses the original frozen acquisition jobs, without looking up response outcomes.
The sources must match the original prompts exactly and remain within 12 files
and 24,000 source characters per bundle. A zero static candidate count is a
bounded-grammar coverage gap, never a finding of safety.

The changed representation gives each sorted file an opaque local file ID and
every supplied physical line an explicit ID such as `F0:L0001`. Models return
start/end line IDs, operation, resource, execution role, and a short reason.
The structured schema enumerates real line IDs for both endpoints. Models do
not copy excerpts. The parser constructs the exact original contiguous source
substring, preserving intermediate line endings and omitting the final physical
line terminator. It rejects cross-file/reversed spans, spans over 1,800
characters, unknown IDs, duplicate span/operation/resource proposals, schema or
phase failures. Any invalid member invalidates the whole response. At most 12
proposals are allowed; empty proposals remain allowed. The output cap is 4,000.

## Freeze and acquisition

Before any paid follow-up request, freeze exact requests, source strings and
hashes, schemas, request fingerprints, opaque source/job mappings to original
conditions, per-job conservative reservation bounds, and a shared-ledger prefix
snapshot under `results/phase4_discovery_followup/acquisition/`. Fingerprints use
the same request and replicate serialization as the unchanged `ClientV3`.

Use the existing corrected `BudgetV4` campaign and ledger at
`results/phase4/api/budget.jsonl`. The follow-up's total upper reservation must
not exceed USD1.50, and the campaign remainder must cover it. No additional
allowance is created. The parent serializes ledger writers. Preparation reads
no credentials and sends no requests. Paid acquisition requires explicit
`--execute` and an existing explicit environment-file path. Raw responses,
including API errors and incomplete responses, are cached separately; first
responses are preserved and never automatically retried. A resumed run reuses
cached failures rather than requesting replacements.

## Estimands and limits

Report planned/completed responses, protocol validity, raw error categories,
source-anchored proposal counts, model strata, input/output tokens, and spend.
Keep all 24 planned conditions in denominators and preserve distinct failures.
Compare only these response/anchoring measures with their matched primary
conditions. Anchoring is constructed by the new representation, so improved
anchoring is not evidence of improved semantic extraction or human accuracy.
The prompt, input tokens, schema and response fields also change: this is a
protocol repair, not an isolated scientific estimate of one formatting token.

Source semantics, invocation, execution, authorization, necessity and complete
coverage remain unverified. No Skill source is executed. Real-source semantic
accuracy still requires independent human annotation; model agreement alone
cannot supply it. All follow-up results must retain their exploratory,
post-hoc-repair registration and appear alongside the original negative results.

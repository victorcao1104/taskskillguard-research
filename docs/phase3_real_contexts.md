# Phase 3 real-corpus context preparation

This track uses the same 180 completed sources from `data/manifests/skills_manifest.jsonl`. It is static, read-only preparation: no source code is imported or executed and the preparation script makes no API calls. All contexts are **researcher-authored hypothetical contexts, not actual user grants**. Human annotation and real-corpus semantic accuracy remain pending.

## Contexts and interpretation

Each source has three actual context rows drawn from four named context types:

| Context | Scope | Prepared sources |
|---|---|---:|
| `review_only` | Review already supplied snippets and return an answer with source references; no effects of source actions are requested | 180 |
| `explicit_effect` | One selected candidate has an eligible, directly grounded operation and exact literal resource; the hypothetical task explicitly requests that scope with public synthetic input restrictions | 3 |
| `missing_scope` | No eligible focus in the selected bounded candidates; the hypothetical task asks for missing operation/resource/data parameters | 177 |
| `edge` | Workflow request deliberately withholds resource, destination, data and effect scope | 180 |

`explicit_effect` and `missing_scope` are mutually exclusive within a source. The total is 540 context rows, not 720. Scope availability is independent of response validity and the model's `unknown` judgments. In particular, `missing_scope` is never included in explicit-effect positive-context denominators. Even an explicit-effect context is not a positive authorization label: an actual source action may use another payload, require credentials, be merely an example, or be unnecessary.

The three eligible focuses are a directly declared POST endpoint, a curl command with explicit `-X POST`, and an instruction directly requesting a read of `scripts/cli-commands.sh`. Eligibility permits only `file.read`, `file.write`, `file.delete`, `network.get` and `network.post`, with a non-placeholder literal appearing in the candidate's source span. Python candidates need AST grounding; lexical candidates also need an immediately associated operation verb or explicit curl POST. Credential access, command execution, dynamic/reconstructed-only resources, ellipsis/placeholder resources, unrelated keyword/URL pairs, OAuth scope identifiers, and a link merely titled “Post Inspector” do not qualify. The broad graph extractor's candidate operation is never silently repaired to create a focus.

The prior report's 116/180 `high` rows without exact operation/resource and this version's 177/180 `missing_scope` rows are **not comparable error rates**. This version uses graph_v2, a narrower eligible-operation set, literal association validation, and the first 12 action candidates. Its count describes scope-construction coverage under these rules. It does not prove that the full source lacks a usable task, nor that a source or model became less accurate. Only 3 selected sources enter the explicit-effect subset, so subset comparison is small and selected.

## Bounded evidence and fixed denominator

The existing `read_bundle` helper supplies at most 24,000 redacted characters and 12 files per source, with the primary SKILL first. Credential-shaped pattern redaction remains unchanged. Source content outside this evidence envelope is not saved or sent in a detection payload. All 3,414 manifest files are independently hash-checked before and after each source preparation; this verification reads bytes only. The original manifest paths and original file hashes remain verbatim in the prepared provenance. Bounded, redacted text has separate hashes and is not confused with original-file hashes.

The unmodified graph_v2 extractor finds 4,097 privilege-relevant candidates in the bounded evidence. Preparation retains the first 12 such candidates per source, yielding 1,711 selected action IDs. It then retains the first available non-action support nodes up to 96 total graph nodes, and the existing induced edges up to 192. Unresolved records are capped at 96. Omitted counts are recorded. These limits can omit relevant dependencies; the graph remains partial evidence, not an execution or safety proof.

The `raw` and `graph_v2` presentations receive identical line-numbered snippets, candidate IDs and candidate source spans. Only `graph_v2` receives the bounded graph. No candidate from the omitted set is added to either condition, and no candidate is removed because a scope context is unavailable. Across all sources, 430 files are embedded, 74 files are truncated, and 2,447 eligible file entries are omitted. The existing redaction helper matched zero patterns in this particular bounded sample; that is not evidence that arbitrary credentials cannot exist.

Ten sources have no selected candidates. The driver must make no API call for them. `parse_detection_record(None, prepared, context, variant, model)` returns `status="not_applicable"`, `model_evaluated=false`, `empty_candidate_set=true`, `request_hash=null`, `prediction={"actions":[]}`, and `diagnostic_codes=["EMPTY_CANDIDATE_SET"]`. These 120 nominal two-model/two-presentation rows are not protocol successes. The nominal maximum is 2,160 rows, with 2,040 actual API jobs after these skips. A budget-driven reduction to fewer contexts must preserve and report omitted conditions explicitly.

## Interfaces and artifacts

`src/tsg/real_v3.py` exposes:

- `prepare_row(row)`: serializable bounded files, graph, action IDs, context objects, coverage, provenance and source verification.
- `build_detection_payload(prepared, context_name, variant)`: a dictionary for `raw` or `graph_v2`; the parent serializes it for the shared API client.
- `DETECTION_SYSTEM_V3`: the common classifier instruction.
- `detection_schema(action_ids)`: strict object schema with fixed action count and required fields `action_id`, `authorized`, `necessary`, `reason`; duplicate/missing IDs are additionally rejected by the parser. An empty set has an empty actions array schema, but is skipped by the driver.
- `parse_detection_record(raw, prepared, context_name, variant, model=None)`: preserves protocol diagnostics, validates the common strict protocol via `models_v3.validate_record`, and independently rejects action-coverage mismatches. Hypothetical scope metadata and model predictions remain separate from unavailable human labels.

Preparation is reproduced with `.venv/Scripts/python.exe scripts/prepare_real_phase3.py`. The default input requires exactly 180 distinct completed source IDs. Fixture tests can supply `--manifest`, `--expected-count`, `--data-out`, and `--out`.

The new artifacts are `data/phase3/real_prepared.jsonl` (one row per source with bounded/redacted source), `data/phase3/real_contexts.jsonl` (one row per actual context), and `data/phase3/real_annotation_handoff.jsonl` (5,133 selected action-in-context rows). `results/phase3/real_preparation/summary.json`, `manifest.json`, and `verification.json` record counts, input/code/artifact hashes and paired-input checks. Existing data/results are not overwritten.

## Human annotation handoff

The existing independent priority packets remain at `data/annotation_v2/priority/rater_a/` and `rater_b/`, with their existing empty labels. They retain their previous candidate definitions. The new handoff adds v3 context text, source IDs, exact source spans, original source-file hashes and bounded-evidence references. Its `rater_a`, `rater_b` and `adjudication` label objects are all empty. It contains no model predictions, model accuracy, fabricated human identities, or filled labels.

The handoff is a coordinator input for creating new independent review packets; it is not silently interchangeable with the previous packet importer. v1 and v2 node IDs have different meanings. Join evidence by source identity, original file hash and source span, then recheck the candidate and context. Do not copy old action labels by node ID alone. Distinguish action existence, permission relevance, hypothetical authorization, task necessity and observed execution; execution remains unobserved in this track. Human reviewers must assess omitted source material before making any whole-skill claim.

## Verification and rulings

Tests were written first and observed failing, then made green. They cover missing scope exclusion, literal/operation association, secret and command exclusion, fixed presentation denominators, evidence caps and redaction, original hash preservation, path containment, Windows manifest separator preservation, strict response schemas, duplicated JSON keys, authoritative response envelopes, missing/duplicate action IDs, and empty-candidate skips. Full-corpus verification checks all 180 IDs, all bounds and all 540 paired presentation inputs. Whole-suite results are recorded in `results/phase3/real_preparation/test-suite.log`.

Rulings: candidate selection is fixed before context construction, so failure to find an eligible focus among those candidates is reported as selected-scope coverage, not a search of the entire source. The operation/resource association rule is deliberately conservative; its cost is false-negative focus eligibility, visible in the explicit/missing counts. Source-file hash lookup normalizes separators only for matching evidence spans; stored manifest paths and hashes are unchanged. Empty candidate sets preserve study rows but never count as model successes.

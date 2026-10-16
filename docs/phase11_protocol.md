# Phase 11 Responses protocol

`tsg.protocol_v11` is a new, offline parser. Frozen `models_v3.validate_record`
and `query_v10.parse_selection` remain the Phase 10 parsers. Nothing in this
module calls an API, retries a response, consumes a query, changes the budget,
or writes raw evidence.

The Responses message `phase` distinguishes `commentary` from `final_answer`.
See the [official reasoning guide](https://developers.openai.com/api/docs/guides/reasoning#phase-parameter).
This distinction supplies an explicit selection rule for envelopes containing
commentary and final output. A unique final message can be selected even when
it is not last; message position alone never selects an answer.

## Interfaces

```python
validate_record_v11(raw, schema=None)
parse_selection_v11(raw, remaining_ids, protocol, limit)
```

Both return `protocol_valid`, `diagnostic_codes`, `prediction`, `text`, and
`schema_errors`. The selection parser additionally returns `selected_ids` and
the v10-compatible `diagnostics` alias. Failed selections always return an
empty `selected_ids` list. As in v3, `prediction` may retain an object rejected
by the schema; callers must gate its use on `protocol_valid`. Validated `text`
is exposed only on success.

Additional fields are `official_source`, `phase_selection`, and
`reliability_level`. The latter describes the accepted evidence structure;
it is not a calibrated confidence score or a semantic accuracy measure:

| Value | Evidence |
| --- | --- |
| `phased_envelope` | One explicit completed final answer, with zero or more completed commentary messages |
| `unphased_envelope` | One legacy unphased assistant message in a completed envelope |
| `legacy_text_only` | Completed historical record with a string `text` and no response envelope |
| `invalid` | Any extraction, JSON, schema, or empty-selection failure |

`phase_selection` reports the mode, selected output index, total assistant
message count, final-answer count, and commentary count. An index identifies
the final candidate even if some other envelope defect causes rejection; it
does not imply acceptance.

## Acceptance boundaries

When `response` exists, it is authoritative. Cached `text`, `prediction`,
`protocol_valid`, or diagnostic convenience fields cannot override it. The
envelope must contain an output list and an explicit completed response
status. A present wrapper status must agree with it. The complete envelope
is checked before parsing the selected JSON.

Phased messages must all be completed assistant messages and must use only
`commentary` or `final_answer`. Exactly one final answer is required. Multiple
finals, commentary alone, unknown phase values, or a mix of phased and
unphased messages fail. A single unphased legacy message is accepted; as in
the historical parser, its message status may be omitted or null when the
enclosing response is completed. A present non-completed status fails.

Every message, including commentary that is not selected, must contain exactly
one nonempty string `output_text` part. Commentary is not required to be JSON.
Reasoning output items may accompany messages. Refusal types, tool-call types,
errors, incomplete details, malformed statuses, and non-completed statuses
anywhere in the envelope fail. Unexpected output items, roles, or message
content types also fail. The parser never concatenates text, chooses the last
message as a fallback, strips fences, repairs JSON, normalizes the envelope,
or mutates the input.

Selected text must be a JSON object with no duplicate keys at any nesting
level and no nonfinite numeric values, including floating-point overflow.
Trailing prose and fenced JSON fail. Optional JSON Schema validation uses
Draft 2020-12 and retains path, validator, and message for each error.
Duplicate keys in the selected text are detectable; duplicate envelope keys
already lost by a caller's JSON decoder cannot be reconstructed from a dict.

Selection validation reuses the frozen v10 `selection_schema`:

- `full` requires an exact permutation of all remaining IDs.
- `batch` requires 1 through the requested limit unique remaining IDs, with
  the configured limit restricted to 1 through 4.
- `next` requires exactly one remaining ID.
- All shapes forbid extra fields and invented IDs. Empty full selections are
  rejected at the selection boundary, as in v10.

Configuration errors retain the frozen v10 exceptions. No fallback selection,
oracle repair, interpreter call, or runtime authorization is provided.

## Historical interpretation

Applying this parser to saved Phase 10 responses is a posthoc extraction
diagnostic. A newly accepted final JSON object is not a recovered acquired
query stream: an adaptive continuation that did not happen remains absent.
The parser does not revise frozen protocol-validity metrics or historical
execution results. Prospective phase-aware use must be identified separately.

## Verification

`tests/test_protocol_v11.py` exercises whole-envelope rejection, explicit final
selection, evidence levels, cached-field independence, strict JSON and schemas,
and all three v10 selection protocols. Tests use synthetic offline records;
they do not spend API budget or alter historical raw evidence.

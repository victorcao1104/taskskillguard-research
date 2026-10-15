# Exploratory phase-aware response replay

This is a **post-hoc integration correction**, developed after the primary new-family results exposed completed Responses envelopes containing an intermediate assistant message and an explicit final answer. The frozen `models_v3.py` parser and every primary raw/API/runtime artifact remain unchanged. These replayed responses are the same model samples, not new independent observations or prospective validation.

## Protocol basis and bounded change

The [official OpenAI reasoning guide, phase parameter](https://developers.openai.com/api/docs/guides/reasoning#phase-parameter), checked on 2026-10-15, distinguishes intermediate assistant commentary from the completed final answer. The primary parser counted both messages' text parts as multiple outputs. The new `phase_protocol_v3.py` adapter recognizes that documented distinction without selecting by JSON plausibility, expected task output, or success.

Selection rules are deliberately narrow:

- A response with explicit phases must contain exactly one `final_answer` message. Every other assistant message must explicitly be `commentary`.
- All phased messages must be completed. Refusals, errors, incomplete statuses/details, unexpected tool calls, malformed content, and response-status mismatches anywhere in the envelope remain rejecting conditions.
- Multiple finals, an unknown phase, commentary without a final, and an unphased message mixed with another message are rejected. One unphased message retains the primary parser's existing unambiguous compatibility; text-only legacy records retain the primary validation rules.
- After selection, the unchanged primary validator parses the selected final as one complete JSON object and applies the same schema. Multiple text parts, duplicate JSON keys, nonfinite constants, non-JSON prefixes, and invalid final schemas remain invalid. There is no regex recovery, concatenation, or search for a plausible JSON fragment.

The adapter deep-copies the envelope before removing validated commentary. Selection metadata records the original output index, total message count, explicit-final and commentary counts, discarded commentary indices, adapter version, and source URL. The original protocol verdict/diagnostics are kept beside the exploratory verdict. Neither the raw cache nor its recorded primary verdict is rewritten.

## Offline replay and outputs

After the primary input tracks are complete, run:

```powershell
.venv/Scripts/python.exe scripts/replay_phase_protocol_phase3.py --include-real
```

The default destination is the new `results/phase3/phase_protocol/` directory. Existing output directories are rejected, and destinations outside that dedicated tree are rejected. A deliberate partial run requires `--allow-partial` and should use a distinct child destination with `--output`; it is labeled `complete=false` and `analysis_status=partial`. Normal operation checks the expected primary counts before creating outputs: 528 regression API/runtime conditions, 1,024 new-family API/runtime conditions, 384 factorial conditions, and 48 OS contracts; `--include-real` additionally requires all 2,160 real-context rows and 180 prepared skills.

All saved regression and new-family P and Q responses are reparsed, using the same planner semantics and the original saved Q schema. Full-guard VM execution is replayed on the same frozen cases and transformations. Invalid actual final answers retain invalid protocol status; a trace cannot receive confirmed-completion credit when P or Q is unresolved. The comparison reports primary and exploratory counts by model/split, changed runtime conditions, and changed **unique** request hashes so a shared P response is not misrepresented as several independent model errors or repairs.

The factorial receives planner diagnostics only. OS contracts receive schema diagnostics only; no container or OS experiment is rerun. When included, the real-context records are reparsed against their original schema and bounded action IDs, with original empty-candidate exclusions preserved. Real-corpus labels remain model claims and human annotation remains pending.

Input files and every referenced raw response are SHA256 inventoried and checked for changes before any exploratory output is written. Outputs include separate `api/`, `runtime/`, and `diagnostics/` records plus `summary.json`. The summary retains source hashes, complete/partial coverage, primary-versus-exploratory outcomes, selection metadata for changed requests, and explicit `additional_api_requests=0`, `additional_api_cost_usd=0`, and `os_execution_replayed=false` fields. Source request hashes must match the raw-file records. The replay never creates a client or accesses credentials.

## Verification and interpretation

The initial 23 tests failed before the adapter and replay existed. The adapter then passed 21 phase/error boundary tests, and the replay passed its completeness/partial-output checks. Two further behavioral tests verify that primary destinations are refused and that an offline fixture replay repairs the commentary/final distinction while preserving every primary byte. The targeted suite has **25 passing tests**, and independent read-only review found no blocking parser issue. Later full-suite results are recorded separately in the release provenance.

The complete replay was executed after primary acquisition finished. New-family held-out confirmed completion changed from 249/256 to 256/256 for Luna and remained 256/256 for mini; no unauthorized effect or leak was observed in either replayed group. Three unique Luna responses account for seven repaired runtime conditions. Real-corpus protocol-valid conditions changed from 1,844 to 1,866 of 2,040 applicable conditions. The remaining 174 unresolved conditions comprised 173 credit-balance errors and one truncated response; they were not repaired by parsing. The replay made zero additional API requests and did not rerun OS containers.

The primary analysis remains the main frozen result. Any improvement from this adapter must be reported alongside it as exploratory same-response replay, with no new model sampling. The correction addresses a response-integration mismatch; it does not demonstrate that the models learned, that an invalid final answer became valid, or that execution policy became more permissive.

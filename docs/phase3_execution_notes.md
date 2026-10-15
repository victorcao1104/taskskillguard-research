# Phase 3 execution contract and verification

`tsg.pipeline_v3.run_pipeline_v3(case, planner, q_plan=None, variant='full', transform_fn=None)` is the new finite capability VM. Existing `pipeline_v2.py`, `sandbox.py`, and historical results remain unchanged. This implementation performs no host filesystem or network actions and makes no API calls.

## Inputs and output

`planner` is the result of `planner_v3.parse_planner_record`: `protocol_valid`, `diagnostic_codes`, `prediction`, `scope_policy`, `reference_actions`, and `declared_unknowns`. A schema-valid model response may still have incomplete or excessive scope. Protocol failure never executes, including in the raw-model comparison arm. Malformed rejected predictions and unknown declarations remain diagnosable without crashing execution.

`q_plan` contains original action IDs. `None` means the full original action list; `[]` is an explicitly empty proposal. Unknown IDs become unsupported action attempts. The original graph is preserved as `original_actions`, including producers omitted by Q. `transform_fn(kind, text)` must return text; the default is the existing finite legacy transformer. Transform failures are recorded and cannot restart the task.

The result has the legacy nested `run` with events, sink events, outputs, goal, unauthorized-execution, leak, and recovery metrics. It additionally records `protocol`, `semantic_diagnostics`, `preflight`, `recovery_provenance`, `raw_scope_policy`, initial/effective contracts, the independent trusted ceiling, and `attack_opportunities`. The three principal outcome booleans also appear at the top level. `status='valid'` describes admission, not task completion; completion must be read from `run.goal_satisfied`.

## Authority and exact parameters

The independent ceiling comes only from `trusted_planner_v2.task_spec(case)`. Required effects are the exact task input read, task transformation, exact output write, and independent public `DONE` notification when requested. Optional cache permission is permitted but not required. Read/write leases come from the trusted specification; status and optional-cache effects have one use through runtime step 20. Execution uses monotonically increasing actual plan positions rather than Skill-supplied step labels.

Raw scope is checked for valid syntax, exact resources, containment within that ceiling, and required permission coverage. Overbroad or incomplete model scope blocks full-arm effects; it is retained for diagnosis and is never silently narrowed or expanded. The compiler arm explicitly sources effective scope from the trusted specification. It does not invent a reference plan or repair protocol failures.

Body constraints and labels are independent. An admitted status action must carry exactly `DONE` when that status is requested. A confidential value whose bytes happen to equal `DONE` retains its input provenance and is still blocked by the taint guard. The VM initializes the legitimate public constant separately from all input values. Successful effects consume leases; denied body or taint attempts do not consume the legitimate send quota.

## Plan validation and recovery

Q plan coverage is structural. It does not speculate that an unexecuted malicious action has already consumed a quota, because that would replace the plan and erase the attack before its guard checkpoint. Unauthorized side effects remain in complete fixed attack plans.

Missing required effects or unsatisfied dependencies can select the **entire P-supplied reference workflow before any execution**. That workflow must pass both the trusted ceiling and effective model policy, ordered value provenance, required effects, exact public-status source, and lease checks. Invalid reference routes, duplicate reads beyond quota, output writes with the wrong source, and replacements of the public constant cannot recover a task.

Dependency evidence retains the dependent action, required value, and producer IDs from the full original graph. No dependency is blindly deleted. There is one execution state, no runtime recovery loop, and no quota reset. Empty-plan recovery is consequently preexecution only. Removing recovery leaves missing-plan failures visible. Removing obligations leaves missing coverage unrepaired, while explicit dependency recovery remains available.

Unknown strings are preserved. A conservative finite classifier treats explicitly optional telemetry/cache/future matters as warnings when they do not reference required effects; unspecified external synchronization can warn for a task with no required send. Required input/output/transformation/status uncertainties and unclassified uncertainties block. This is a bounded heuristic, not open-ended semantic understanding.

## Exact variants

The independent feature keys are `authority`, `obligations`, `recovery`, `scope`, `body`, `taint`, and `lease`.

| Variant | Difference from full |
| --- | --- |
| `full` | All seven components enabled; effective scope remains the validated model scope. |
| `model_raw` | Initial ceiling/completeness admission disabled; model syntax, protocol, and remaining guards retained. Controlled mock diagnostic comparison only. |
| `trusted_compile` | All components enabled; effective scope comes from the independent task compiler and `scope_source='trusted_task_compiler'`. Raw model diagnostics remain. |
| `no_authority` | Same initial admission switch as `model_raw`, named as a mechanism ablation. |
| `no_obligations` | Missing-effect coverage does not trigger reference selection; dependencies can still do so. |
| `no_recovery` | No reference selection. |
| `no_scope` | Runtime exact operation/resource membership disabled; body, taint, and applicable leases retained. |
| `no_body` | Exact network body comparison disabled; taint retained. |
| `no_taint` | Information-flow comparison disabled; exact body retained. |
| `no_lease` | Runtime use limits and windows disabled; other guards retained. |

All variants retain strict validation of any recovery reference. A disabled component can have no measurable effect when another component stops the same attack. `attack_opportunities` therefore reports planned attacks, attempts reached, actual guard reach, per-checkpoint reach, and executed attacks separately. An attack removed by preexecution recovery has a planned opportunity but no reached runtime check.

## Post-run scoring and verification

`case.policy`, `ground_truth`, and `expected_output` are used only after execution by scoring helpers. They never select, authorize, or repair a plan. Tests change all three scoring fields and confirm identical decisions and preflight evidence. Successful references receive credit for equivalent required effects: `required_effect_evidence` maps original required action IDs to the executed reference IDs, with operation/resource, provenance, and output/body checks. Required-effect completion is not inferred from ID equality.

Observed test sequence: 18 initial execution tests failed before the module existed; implementation exposed two attack-erasure failures; structural coverage corrected those. Further failing tests covered malformed rejected unknowns/predictions and incorrect required-effect credit after reference recovery. The final targeted execution run passed **28 tests**. A full-suite snapshot passed **240 tests, 4 skipped**. The initial full-suite runs hit sandbox temporary-directory permissions and then Windows long-path limits; using a short unique temporary directory in the writable project root resolved those environmental failures. Tests use mock/in-memory execution; these results do not establish an OS security boundary or arbitrary-code containment.

### Review amendment: independent public notification scoring

The subsequent independent review reproduced a post-run scoring defect with the frozen `component_probes_v3` confidential-same-literal probe. Under `no_taint`, confidential input containing the bytes `DONE` reached the sink, consumed the send quota, and caused the actual independent public notification to be denied. The initial goal scorer accepted any `DONE` sink body and incorrectly reported completion, although required-effect evidence correctly showed the missing public send.

A new regression first failed on `goal_satisfied=True`. The scorer now requires the expected destination, exact `DONE` body, `sources=['trusted-literal']`, public readers, and an authorized executed send event. It is consistent with the required-effect evidence: this probe still records the leak and now records goal failure with `a_send` missing. This changes only post-run scoring; execution decisions, model requests, prompts, protocol code, and preserved historical results are unchanged. The parent experiment driver records a freeze amendment and retains the original freeze and raw evidence. Verification after this amendment: **29 execution tests**, **30 execution-plus-probe tests**, and a full-suite snapshot of **268 passed, 4 skipped**.

### Review amendment: verbs within optional topics

A later review reproduced two false blocking classifications: `Optional telemetry send target is unspecified.` and `Optional cache write format is unspecified.` Both newly added tests first failed because generic `send`/`write` words overrode the explicitly optional topic. The finite classifier now recognizes those verbs within an explicitly optional telemetry/cache clause. Required-effect names, exact required resources, and separate unresolved read/write/send clauses still block, including declarations that prepend `optional` to the required output or status. Original unknown strings remain intact. This is deliberately conservative for unrecognized language and does not grant any new scope. Verification: **40 execution tests** and a full-suite snapshot of **283 passed, 4 skipped**. Only execution classification, its tests, and these notes changed; no model or API request code changed.

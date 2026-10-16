# Phase 11 claim–evidence matrix

Every empirical claim describes this finite synthetic campaign. No result from earlier phases is overwritten. This matrix separates proved conditional properties, measurements, posthoc diagnostics, and unsupported extrapolations.

| Claim | Type | Evidence / precise selection | Boundary |
|---|---|---|---|
| A fixed positive witness survives truthful refinement | Conditional proposition | `docs/phase11_theory.md`, `tests/test_certificate_theorems_v11.py` | Actual world covered; static semantics/state; trusted evidence. Selected route/trace can change. |
| No common route in a full observation class prevents a positive certificate | Conditional proposition | Theory Proposition 3, challenge reference observation classes | Fixed-route interface; does not imply each actual world is impossible. |
| At least one receipt per compatible world is needed | Interface lower bound | Theory Proposition 4, independent exhaustive tiny checks | Not a lower bound on general static analysis or compressed proofs. |
| 1,006 semantic comparisons agree after typed-error normalization | Reproduced measurement | `results/phase11/reference/normalized/agreement_summary.json` | Original two raw error-string mismatches retained separately. |
| Observe-cover budget12 online saves4.736 queries with equal completion | Primary descriptive contrast | `analysis/contrasts.jsonl`: cohort=combined, contrast=observe_cover_online_minus_fixed, budget=12; details in `policy_conditions` | Family mean over36templates/218worldrows. Not total CPU or measured wall time. |
| Models do not exceed strong heuristic completion | Primary descriptive comparison | `model_comparator_conditions`, `contrasts`: source_online_minus_matched_heuristic, baseline=observe_cover,budget12 | 36 selected actual worlds; one provider draw per cell. |
| Graph lacks stable benefit over padding | Secondary descriptive comparison | `contrasts`: graph_minus_padding, budget12 | Exact local surrogate-token match, not verified provider-token match. |
| Fresh source-online acquisition costs less | Secondary measured contrast | `stream_conditions`, `contrasts`: source_online_minus_fresh_fixed_actual_cost for cost; source_online_minus_fresh_fixed for query/completion; API raw usage/reservations | Independent draws; aggregate completion equality does not imply identical family outcomes. |
| All670 matched positive prefixes retain successful witnesses | Conditional replay result | `results/phase11/matched_prefix`, `analysis/matched_prefix_detail` | Offline counterfactual work;621full-result matches; no invoice-savings claim. |
| Terminal status recovers178triggered executions for each terminal fault | Primary recovery contrast | `recovery_detail/conditions/triggered_conditions`: status_budget1, ambiguous_after or terminal_noncommit | Trusted atomic durable status/fencing; missing certificates retained in all-row denominator. |
| Acknowledged recovery and physical progress have different gains | Posthoc outcome disaggregation | `results/phase11/physical_goal/`: ambiguous_after/status1 physical43.056pp versus acknowledged81.944pp | Strict-stop already has physicalgoal84/218; physical goal is not error-free termination. |
| Absence is insufficient to license a fresh-ID retry | Constructive counterexample | `results/phase11/counterexamples/results.json` | Synthetic delayed-original schedule; one counterexample refutes universal retry safety. |
| Earlier13parser rejections are extraction errors under phase-aware semantics | Posthoc diagnostic | `results/phase11/protocol_reaudit/summary.json` | No absent continuation is reconstructed; no Phase10 metric is revised. |
| New full contract does not improve old full completion | Descriptive unequal-interface comparison | `analysis/previous_contract_detail/conditions`:178/218both | Not an isolated causal ablation. |
| Measured authorization counters alone do not establish security | Measurement limitation | `src/tsg/commit_v11.py` return field; separate posthoc `trace_audit` | Gateway enforces policy and counter is constructed0; no real attack distribution. |
| Independently checked recorded commits respect grants/logical identity | Posthoc trace consistency | `results/phase11/trace_audit`:63,622commits,0unauthorized;50,608mutations,0duplicates | Assumes complete truthful simulator traces;42,846slots include14,364nulls. |
| All43,064 container conditions agree | Replay evidence | `results/phase11/isolation/{deterministic,integrated}/audit.json` | Includes8,664top-level null results; wrappers may contain additional null executions; dependent conditions; offline verifier checks retained capsules, not fresh container launches. |

Paths beginning `analysis/` are under `results/phase11/analysis/`. No claim is made for model/graph superiority, new active-learning theory, real-world Skill coverage, production security, arbitrary distributed recovery, or guaranteed publication acceptance.

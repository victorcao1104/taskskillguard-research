# Report claim-to-evidence map

All paths below are relative to the repository root. The underlying experiment is frozen. This map is reporting provenance, not a replacement for the original release's claims file.

| Report claim | Authoritative evidence | Interpretation boundary |
|---|---|---|
| Main: 48 cases, 24 families, 102 world rows; challenge: 24, 12, 116; scaling: 12 cases, 90 world rows | `data/phase11/heldout.jsonl`, `challenge.jsonl`, `scaling.jsonl`; `results/phase11/analysis/summary.json` | 36 independent aggregation units are authored families; scaling remains dependent. |
| 1,006 reference comparisons, two original error-string differences | `results/phase11/reference/normalized/agreement_summary.json`; `results/phase11/analysis/semantics_detail.csv` | Typed-error normalization is separate and disclosed; original mismatches retained. |
| Certificate soundness, fixed-route impossibility, receipt bound | `docs/phase11_theory.md`; `src/tsg/certificate_v11.py`; theorem tests | Finite covered worlds and truthful fixed-snapshot evidence; no new general optimality theorem. |
| 7.750 to 3.014 queries; completion stays at 81.94% | `results/phase11/analysis/policy_conditions.csv`, `contrasts.csv`; filter combined / observe_cover / budget 12 | Equal-family mean, not the raw percentage 178/218. Fixed control deliberately continues. |
| observe-cover reaches its ceiling at eight queries | same policy table, budgets 8/12 | 178 positive and 40 negative world rows; zero unknown. |
| Models: 29/36 and 28/36; heuristic: 30/36 | `results/phase11/analysis/model_comparator_conditions.csv`; source online / budget 12 / baseline observe_cover | One selected actual world per family; no repeated provider draws. |
| Graph does not improve completion over padding; uncertain query effects | `results/phase11/analysis/contrasts.csv`; graph_minus_padding and graph_minus_source | Local tokenizer control, not verified provider-token equivalence; not an IPIGuard baseline. |
| 230 positive, 43 negative, 15 unknown; unknowns split into 10 certifiable and 5 infeasible | `results/phase11/api/summary.json`; `results/phase11/analysis/stream_detail.csv` | Unknown category and provider validity are separate axes. |
| 1,603/1,605 valid decisions; 286/288 valid streams | API summary and retained response/decision records | Two HTTP 400 errors; no speculative error cause. |
| Fresh online/fixed calls and cost estimates | `results/phase11/analysis/stream_conditions.csv`, `contrasts.csv`; source_online_minus_fresh_fixed_actual_cost | Conservative estimate, not invoice; aggregate completion equality is not per-family identity. |
| 670 successful prefix comparisons; 621 identical full results | `results/phase11/analysis/matched_prefix_detail.csv` and `matched_prefix_conditions.csv` | Conditional witness preservation; offline counterfactuals are not extra invoice savings. |
| Recovery: 178/218; +81.94 percentage points acknowledged completion | `results/phase11/analysis/recovery_conditions.csv`, `contrasts.csv`; terminal_status_minus_strict_stop, status budget 1 | Two primary first-mutation terminal faults; conditional triggered denominator 178/178. |
| Strict-stop physical goals: 84/218, family mean 38.89%; physical gain 43.06 points | `results/phase11/physical_goal/conditions.csv`, `contrasts.csv`, `summary.json` | Explicitly posthoc; physical goals differ from error-free acknowledged completion. |
| No unauthorized/duplicate committed effects in trace audit | `results/phase11/trace_audit/summary.json` and detail records | 42,846 slots / 28,482 executions / 14,364 nulls; trusts traces; not an attack rate. |
| 43,064 container conditions / 173 batches | `results/phase11/isolation/` records and release verification | 8,664 top-level nulls plus wrapper nulls; recorded replay is not a new container launch. |
| Scaling: 4 to 128 queries | `results/phase11/figures/dependent_scaling.csv` | Full fixed observe_cover, dependent construction; not online stopping or arbitrary-program scaling. |
| Prior contract also completes 178/218 | `results/phase11/analysis/previous_contract_conditions.csv` and detail | Unequal acquisition/planning interfaces, not an isolated causal ablation. |
| Parser accepts 13 older responses | `results/phase11/` diagnostic evidence and `docs/phase11_protocol.md` | Posthoc extraction only; no adaptive continuation invented or old metric rewritten. |
| Incremental API cost $3.765178875; remaining $6.898587 | `results/phase11/api/summary.json` and budget ledger | No API calls for paper writing; original cumulative cap unchanged. |

The paper checker mechanically validates a subset of these quantities and all archived file hashes. Independent read-only editorial review additionally checked the prose, methods, intervals, citation support, and scope. Neither process substitutes for a new independent research replication.

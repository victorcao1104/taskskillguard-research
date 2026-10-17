# Claim-to-evidence map

All paths below are relative to this study. Derived outputs are reproducible from preserved inputs; they are not independent observations.

| Claim | Evidence | Boundary |
|---|---|---|
| 48 supported packages, 12 mechanisms, 6 unsupported probes | `data/cases.json`, `data/unsupported.json`, `data/specification.json` | Constructed, dependent variants; no population prevalence |
| 180 exact source effect sites, no adapter omissions within cases | `results/coverage.json`, `results/aligned/truth.json` | Accepted grammar only; does not imply arbitrary Skill coverage |
| Phase 5 locator 134/180 and operation match 128/180 | `results/coverage_corrected.json` | Corrects top-level versus nested provenance scoring; old mock emit support differs |
| First 292/324 mismatches; amended 324/324 agreement | `results/first_differential.json`, `results/aligned/differential.json`, `amendments_reference.json` | 288 trace conventions plus 4 missing-file behavior differences; post-holdout amendment |
| Two original-necessity labels changed yes to no | `results/truth.json` versus `results/aligned/truth.json` | Intermediate-file attacks, stage-write site, both lexical variants |
| Unchanged Phase 6 interpreter/reference agree on 228 lowered executions | `results/phase6_bridge.json` | Legacy semantics do not validate new flow, limits or preservation predicates |
| No-fault attack scope/flow/completion counts | `analysis/deterministic_summary.json`, `results/deterministic.json` | Ordinary quota, attack stratum, 24 cases per mode |
| Identical completion on 1,344 recovery pairs | `analysis/paired_recovery.json` | 48 packages × 7 scenario grids × 4 assigned fault profiles; not independent tasks |
| Ordinary recovery 140/192 each, calls 822 versus 680 | `analysis/deterministic_summary.json` | Expensive staging route deliberately listed first; same simulation capability |
| Recovery success alone does not establish model contribution | `analysis/gate_summary.json`, `results/gate_controls.json` | Both recovery controls complete 48/48 no-fault cases after all-block |
| 288 model conditions, 264 distinct requests, 286 valid conditions | `api/manifest.json`, `api/observations.json`, `api/raw/`, `analysis/model_summary.json` | 24 reused conditions; two retained HTTP 400 invalid_prompt failures |
| Model label accuracy and unknown categories | `analysis/model_accuracy.json`, `analysis/model_scores.json`, `analysis/model_truth.json` | Flow-detection accuracy excludes 128 ordinary non-emit `na` sites |
| Graph changes are mixed | `analysis/paired_graph.json`, `analysis/model_scores.json` | Added graph also adds tokens; no new padding control/repeated samples |
| Model filters do not improve no-fault completion | `analysis/model_replay_summary.json`, `results/model_replay.json` | Filters apply only to original sites; trusted recovery remains available |
| 7 containers match 6,720 host conditions | `results/container_replay.json` | Compiled-program replay, not native package execution |
| Zero-API reproduction matches all saved traces | `reproduction/post-review/reproduction.json` | Fixed saved models; future model outputs need not reproduce bit-for-bit |
| Cost within remaining budget | `api/summary.json`, `provenance/budget_inheritance.json`, `api/budget.jsonl` | Conservative exposure, not invoice |
| Prior work preserved | `provenance/baseline.json`, `provenance/preservation_check.json` | File-byte check against 46,059 old tracked files |
| Known absence-flow security gap | `results/post_review_absence_flow.json`, `review_probe.py` | Two worlds, post-review negative probe outside main counts; flow guard permits different outputs derived from secret-controlled deletion |

The paper retains Phase 5 and Phase 6 historical findings with separate denominators. Their original sources remain under `results/phase5`, `results/phase6`, and the respective repository phase reports. They are not pooled with this study. SkillScope, Progent and CaMeL are related methods and inspirations, not newly benchmarked upstream implementations.

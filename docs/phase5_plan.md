# Phase5 execution plan

Approved scope: execute the ordered Phase4 follow-up recommendations. Preserve all previously tracked files. No API work by child agents, no corpus execution, no edits under project sources/.

| Work package | Owned files | Validation |
| --- | --- | --- |
| Independent truth | data/phase5/fixtures_*.jsonl, reasoning_cases.jsonl; build_fixtures_phase5.py; test_truth_v5.py | literal source spans, disjoint families, no label leakage, frozen hashes before outcomes |
| Coverage implementation | extraction_v5.py, shell_v5.py, census_phase5.py, test_extraction_v5.py | failing regression first; alias/mutation/dynamic/options; frozen implementation before hidden evaluation |
| Legal recovery | recovery_v5.py, run_recovery_phase5.py, test_recovery_v5.py, recovery_cases.jsonl | no quota reset/scope expansion/duplicate effects; real 180-container grid; independent goals |
| Parent integration | reasoning_v5.py, run_phase5.py, analyze_phase5.py, prepare_phase5.py, report/release checks | immutable job hashes, no truth in model payload, family uncertainty, budget prefix, full-grid failures |

Use independent agents for the three disjoint implementation/truth packages, as prescribed by the dispatching-parallel-agents skill. They cannot edit each other's files; parent integrates shared contracts. Public reasoning schema and metric definitions must be agreed before paid results are seen.

1. Freeze baseline tracked-file hashes and budget. Run existing regression suite.
2. Author independent fixtures and fix supported coverage from dev evidence only. Freeze source before parent runs validation/heldout.
3. Build new reasoning contract: four dimensions, explicit unknown evidence/action, identical node IDs and source across five views. Unit-test mismatched/duplicate IDs, invalid protocol, gold leakage and graph transformations.
4. Freeze paid main grid and any repeat subgrid with exact request hashes and all-request reservation bound. Run first attempts once; cache failures; analyze with planned denominators.
5. Run offline all180 census, new omission/candidate human packs. Run integrated container grid with full traces. Test normal/fault results separately.
6. Independent methodological/code review, meaningful fixes/tests, Chinese comparison report, structured summaries and reproducibility checks. Preserve any first-observation errors as an amendment chain.
7. Stage only new Phase5 artifacts, verify all inherited hashes, push study-v5 and main to the original private repository after verification, inspect remote SHA and CI outcomes. No merge/commit claim before corresponding evidence.

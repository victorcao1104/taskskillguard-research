# v13: Stateful Skill recovery without prepared replacements

This synthetic study constructs and verifies continuations under unchanged permissions, trusted remaining goals and side-effect history. It includes two models, strong source-free controls, ablations, held-out query structures, bounded adaptive mutations, partial execution and fault cases. All old versions and superseded or failed runs remain available.

## Main findings

- Under the common normalized protocol, safe completion is 55/72 for the full method and 55/72 for ordinary repair with GPT-6 Luna; GPT-4.1 mini obtains 51/72 and 35/72 respectively.
- The full method uses fewer model requests in both comparisons, but more interpreter executions. It is not a universal cost or completion winner.
- Shared operand-role guidance strengthens replanning. In that paired sensitivity, full/replan scores are 56/72 versus 38/72 (Luna), and 54/72 versus 21/72 (mini).
- The deterministic source-free goal compiler remains strongest: 20/20 feasible matched cases, or 20/24 including nonfeasible cases. The trusted formal query specification and shared task-generator primitives limit generalization claims.
- Of 768 accepted normalized candidates, 43 fail fresh-input correctness. A further 64-input stress test finds no additional failures among the 725 that passed. These are bounded tests, not a proof.
- Unknown delivery status without a permitted status query requires stopping. Prior disclosure remains unsafe; a later successful continuation cannot erase it.

## Reproducibility and budget

All 66 tests pass. Fresh offline replay checks 5,312 distinct saved records, with 5,408 comparisons because 96 adaptive records are checked in two contexts. All comparisons agree. The replay checks 3,340 raw request identities, makes no API calls, and leaves the ledger unchanged. All 47,056 pre-v13 Git objects are preserved.

New v13 conservative API exposure is **$3.1760963 of $20**, leaving **$16.8239037**. This includes uncertain reservations and is not a provider invoice. Earlier project expenditure is tracked separately.

The IEEE report contains 12 body pages plus one reference page, with 15 references. `paper.pdf` is the report; `ieee-source.zip` contains only editable paper sources and figures. Clone the repository at this release tag for the complete experiment, raw responses, failures, analysis and reproduction scripts. Read `studies/stateful-recovery-v13/README.md` and `REPORT_ZH.md` before reproducing or modifying it.

This release supports a bounded empirical result about state-aware recovery and its limitations. It does not establish first-of-its-kind novelty, superiority over strong programmatic planning, or security for real unrestricted Skills.

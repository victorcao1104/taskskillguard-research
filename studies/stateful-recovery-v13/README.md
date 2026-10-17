# Stateful Skill recovery without prepared replacements (v13)

This synthetic study asks whether a blocked Skill can be continued under unchanged permissions, using the remaining task and trusted effect history. It does not run downloaded Skills, native scripts, real email, or a real filesystem service. No human annotation is required.

Read `REPORT_ZH.md` for the findings in Chinese, `paper.pdf` for the English IEEE report, and `analysis/summary.json` for machine-readable results. The strongest source-free goal compiler is retained, including results that limit the proposed method's value. Model-generated programs are never trusted merely because they are generated during recovery.

## Reproduce without API spending

Clone this private repository with access granted by its owner, and check out the `study-v13-stateful-recovery` branch or its final release tag. Run from the repository root. Python 3.12 is the tested interpreter.

```text
python -m venv .venv
```

Activate the environment (`.venv\Scripts\Activate.ps1` on PowerShell, or `source .venv/bin/activate` on Linux/macOS), then:

```text
python -m pip install -r studies/stateful-recovery-v13/requirements.txt
python -m pytest studies/stateful-recovery-v13 -q
python studies/stateful-recovery-v13/reproduce.py --output work/v13-independent-replay
```

The output directory must not exist. On Windows with a long checkout path, use a short output location, for example `--output "$env:TEMP/tsg-v13-replay"` in PowerShell, to avoid the host path-length limit. The replay uses saved raw model responses, validates request identities, reruns the simulator and checker, compares semantic records and compressed trace hashes, and verifies that the budget ledger did not change. It does not contact a model provider. Deleting only a summary file and reading saved episode files is not considered reproduction.

The original development pilot is retained but not replayed using the later clarified protocol. Repeated API acquisition cannot guarantee identical responses from a changing hosted model. The exact saved-response experiment can be reproduced locally.

## Evidence layout

| Path | Contents |
|---|---|
| `design.md`, `plan.md` | Research questions, planned controls and implementation order |
| `sr13/`, `run.py` | Frozen interpreter, independent goals, construction, checker and initial campaign |
| `data/cases.json`, `data/packages/` | 126 synthetic cases and matching Skill packages |
| `data/adaptive_search.json` | All 48 bounded mutation queries and six selected cases |
| `reference_catalogue/` | Prepared-answer control, never supplied to main methods |
| `results/main/` | Original strict-protocol 1,152 episodes, unchanged |
| `results/state_amendment/` | Entire unknown-receipt stratum: 144 corrected reruns |
| `results/offline_corrected/` | 756 deterministic trials with corrected state and benign pass-through |
| `results/adaptive/` | 96 strict-protocol trials on selected mutations |
| `results/robust_protocol/`, `results/adaptive_net/` | Common transport normalization: 1,152 + 96 new episodes |
| `results/robust_adaptive/` | Preserved 96-episode network-failed launch; no model answers |
| `results/typed_roles/` | 288 paired full/replan episodes with shared generic operand-role guidance |
| `results/stress_inputs/` | 64 additional input seeds for every accepted normalized main program |
| `api/` | Raw responses, request/dispatch identities and append-only budget ledger |
| `analysis/` | Recomputed tables, per-episode CSV, fault and artifact audits |
| `provenance/` | Freeze hashes, old-version inventory and disclosed amendments |
| `reproduction/verification.json` | Fresh local replay and preservation checks |
| `*.tex`, `figures/` | Editable paper and generated scientific figures |

Each episode keeps proposals, counterexamples, acceptance, fresh-input outcomes, search costs, final scoring costs and a SHA-256 reference to its compressed traces. A stopped or invalid episode remains in the denominator. Prior leakage remains unsafe even if later work succeeds.

## Making a new experiment

Create a new branch and study directory; preserve this study's frozen files and evidence. Define a new trusted goal evaluator, explicit permissions, held-out task families and uncertainty model before acquiring results. A new natural-language task parser or unrestricted Python executor changes the threat model and needs separate evaluation. Do not treat the finite checker here as a production sandbox.

Use separate output paths and a new campaign identity. Changing a frozen source or reusing an old output path deliberately raises an error. Fresh paid acquisition needs a separately authorized local API configuration and budget. No API key is included in this repository. This study's existing ledger includes inherited expenditure; the new v13 allowance is $20 on top of the recorded inherited amount, not a claim that the entire multi-version project cost $20.

## Interpretation limits

The trusted task supplies a formal query specification. That is substantially stronger than a vague user request and makes a generic deterministic compiler competitive. The six held-out query structures share primitives and authors with development cases. The adaptive attacker searches a small mutation library against the source constructor, not an unrestricted model-in-the-loop attacker. Security checks cover bounded input/secret worlds; they are not a proof for arbitrary Skills. Repeated successful writes and deletes are prohibited by this study's explicit once-only policy.

All earlier project versions remain in Git history and their original paths. The archive tag before this work is `archive-before-stateful-recovery-20261018`.

The final study tag is `v13-stateful-recovery`. The release includes the PDF, paper-only source archive, Chinese report, summary and replay verification. `provenance/release_manifest.json` inventories the published study files by SHA-256. `package_release.py` performs an offline packaging audit, including frozen-source checks, the inherited ledger prefix and a credential-format scan; that scan is not a proof that every possible sensitive string is detectable.

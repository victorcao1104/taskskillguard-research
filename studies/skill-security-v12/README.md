# TaskSkillGuard: return to Skill security

This additive study takes the **Phase 5 final revision** (`efd19d5e8704bdaec24fd183b81026d1d7fffccd`) as its research direction and adopts **Phase 6 executable truth and equal-capability controls**. It does not replace previous experiments or papers. The implementation starts from preserved commit `7296da08bea968151dac7fab1b4c7edfc813ed27` so all later historical evidence remains available.

The question is concrete: **can a Skill complete the user's task without performing effects that the task does not permit?** The study connects `SKILL.md`, selected helper source, source-located effects, task scope, outbound data restrictions and trusted recovery. It is a bounded synthetic mechanism study, not a marketplace audit or autonomous policy generator.

## Read first

- [Chinese findings and interpretation](REPORT_ZH.md)
- [IEEE paper](output/paper.pdf) and [editable source archive](output/ieee-source.zip)
- [Claim-to-evidence map](EVIDENCE.md)
- [Design](design.md), [protocol](protocol.py), [case specification](data/specification.json)
- [Preserved first failures](results/first_differential.json) and [reference amendment](amendments_reference.json)

## Results at a glance

The new set has 48 supported packages from 12 constructed mechanisms, with two dependent lexical variants per benign/attack pair, and six unsupported probes. The original independent comparison had 292 differences in 324 checks; after a documented trace-contract and missing-file amendment, all 324 agree. This is not a claim of first-run perfection.

For the 24 no-fault attacks, scope checks prevent 14 scope violations but leave 10 forbidden outbound flows. Scope plus flow checks prevent both and stop the original attacked routes. Trusted recovery completes all 24. The 24 benign packages complete under all five controls in the same no-fault setting.

Minimum-call and first-feasible recovery have identical completion on all 1,344 paired conditions. Under the ordinary quota they complete 140/192 conditions each; minimum-call selection uses 680 versus 822 charged calls. This supports limited cost savings under the deliberately expensive-first catalogue, not a general completion advantage.

The model study has 288 conditions, 264 distinct requests and 286 protocol-valid conditions. Two retained GPT-6 Luna responses report HTTP 400 `invalid_prompt`; they were not retried. Adding model prechecks does not beat the deterministic gateway in the no-fault ordinary setting. Added graph information gives mixed label changes and no consistent execution improvement. All-block followed by trusted recovery also completes 48/48 no-fault cases: recovery success cannot establish model contribution.

## Reproduce without paying for models

From the repository root, use Python 3.12 and an isolated environment. Install the pinned study dependencies:

```text
python -m pip install -r studies/skill-security-v12/requirements.txt
python -m pytest studies/skill-security-v12/test_adapter.py studies/skill-security-v12/test_runtime.py studies/skill-security-v12/test_protocol.py studies/skill-security-v12/test_reference.py studies/skill-security-v12/test_review_regressions.py -q
python studies/skill-security-v12/reproduce.py --output work/skill-security-v12-reproduction
```

The last command regenerates cases, recomputes amended truth, runs all 6,720 deterministic conditions, reparses retained model responses and replays all 3,456 model conditions. It checks complete records against committed results and makes **zero API calls**. The original and amended reference files remain separate. `freeze.py`, `experiment.py prepare`, and `acquire.py prepare` document the historical acquisition process; they are not the recommended replay entry point after the recorded reference amendment.

`analyze.py offline`, `analyze.py models`, and `figures.py` derive the published summaries and figures. Their immutable outputs reject unexpected changes. The figure generator writes the generated figures in this new study only. For a modified experiment, use a new study/output version rather than replacing retained evidence.

The acquisition runner will reuse retained responses and dispatch markers, with no automatic retries. Do not remove the saved response/dispatch directories to force new calls. New paid acquisition would require a separately frozen campaign and budget review; it is unnecessary to reproduce the reported results.

## Isolation and container verification

No package Python is executed natively. A bounded AST adapter lowers the selected helper into an in-memory interpreter. Unsupported source is rejected as unsupported, not certified safe. The interpreter has no real file or network tool.

Seven restricted containers replayed all 6,720 compiled-program conditions and matched the host result hashes. The saved [container record](results/container_replay.json) includes the pinned image digest, disabled network, read-only root, no host mounts, dropped capabilities, unprivileged user and resource limits. This verifies the finite gateway across environments; it is not execution of unrestricted Skills or real services. The earlier entrypoint timeout is retained in provenance. The image is a local prior-study image and is not distributed by this private release; portable offline reproduction above does not require Docker.

## Layout

| Path | Content |
|---|---|
| `data/` | Generated packages, trusted tasks, quotas, model contexts |
| `adapter.py`, `runtime.py` | Source lowering and scope/flow/recovery gateway |
| `reference.py`, `fixtures.py` | Separately authored reference and fixed generator |
| `reference_before_amendment.py` | Exact original reference bytes |
| `api/` | Frozen requests, raw responses, dispatch markers, inherited budget |
| `results/` | First comparisons, amended truth, traces and container results |
| `analysis/` | Accuracy, unknown, graph and recovery summaries |
| `provenance/` | Archive baseline, pre-evaluation freeze, corrections and checks |
| `reproduction/` | Recorded zero-API replay verification |
| `paper.tex`, `*.tex`, `figures/`, `output/` | IEEE source, figures and final artifacts |

## Limits and budget

Trusted grants, source-reader restrictions, goals and alternative routes are supplied. Their creation is not solved. The source subset excludes most Python; mock resources use exact strings, missing reads return empty strings, and missing deletes are no-ops. **A retained post-review probe leaks a bit through secret-controlled deletion and a later missing read, even within accepted syntax.** The current flow monitor loses absence provenance; it is not a sound noninterference system. Reproduce this negative result with `python studies/skill-security-v12/review_probe.py`; see `results/post_review_absence_flow.json`. It is separate from the frozen 48 packages and is not repaired in this release. Receipt identity is a finite convention, not a distributed exactly-once guarantee. Denied attempts consume quota by design. Package variants share structure, some benign prompts repeat across families, and graph views are not length-matched. There is no adaptive attacker or independent human ground truth.

The prior cumulative conservative exposure is $22.652988125. This campaign adds **$0.128285850**, leaving **$6.770301150** under the authorized cumulative cap of $29.551575125. These are conservative ledger amounts including unresolved reservations, not a provider invoice. No real Skill experiment or human annotation was performed.

The pre-study remote archive is `archive-before-skill-return-20261017`. All 46,059 previously tracked file hashes are retained for preservation checking.

# Phase 2 human annotation handoff and retrospective statistics

The user requested that automated work continue first and that human annotation be left for them to arrange. Accordingly, all annotation cells remain blank. No human ground truth, Cohen's kappa, or human agreement result is claimed. The packets and strict import/adjudication workflow are ready; the substantive two-person review and any third-person adjudication remain pending.

## Exact workload

| Scope | Skill-version units | Action units | Action-in-task units | Total units per person | Label fields per person |
|---|---:|---:|---:|---:|---:|
| Full | 312 | 2,233 | 5,643 | 8,188 | 19,474 |
| Priority subset | 25 | 144 | 288 | 457 | 1,033 |

Two independent raters therefore require 16,376 full unit reviews, or 914 priority unit reviews. Action-in-task units each contain three separate labels. Evidence references, rationales, and any additional missed actions are extra review work, not included in the label-field count. Adjudication workload cannot be known until both reviews are received.

The full package covers 180 real source bundles (three hypothetical trusted task contexts; 5,115 candidate action-in-task rows) and 132 synthetic concrete source variants from 12 parent skills and six template families (528 action-in-task rows, including local transformation actions). Each synthetic variant gets a distinct skill-level review because its source text differs. These 132 variants are not 132 independent skill families.

The priority subset is a convenience triage selection: one real source from each of seven observed heuristic categories, and one synthetic instance from each of six families for authorized network sending, optional cache creation, and the ambiguous implicit lease case. It is neither representative nor a substitute for full ground truth. Its independently randomized IDs differ from the full packets; do not combine the two as independent observations or duplicate label credit. Start with either scope and retain that scope in every report.

## Distribute separate packets

For the full review, give person A only `data/annotation_v2/full/rater_a/` and person B only `data/annotation_v2/full/rater_b/`. For triage, use the corresponding `priority/` folders. Each contains:

- `review.html`: a local form with source evidence, task references, source line numbers, relevant neutral traces, label selectors, notes, progress and JSON export.
- `packet.json`: the exact evidence and row definitions.
- `labels.csv`: an alternative blank spreadsheet-compatible response template.

Keep `coordinator_private/key.json`, saved model predictions, generated truth, policy output, and the other person's answers away from each rater until their independent review is complete. The separate packets use different opaque row IDs and row order. Their evidence is identical. Source semantics are visible by design; the packet cannot conceal that a source instruction itself says something suspicious. Candidate operation/resource classifications, candidate risk status, scenario names, gold labels, model outputs, and trace authorization reason codes are excluded.

Candidate-bearing real source files are embedded, with frozen SHA256 checks. The full frozen bundle file inventory and original local paths are supplied separately in each evidence document. Reviewers must inspect relevant unembedded source before assigning a skill-level “no”; otherwise they should select “unknown”. A remote reviewer needs read-only access to those original sources or an approved copy. This package does not claim complete real-source extraction recall: missed actions reported by humans must become new units for independent review.

The HTML displays untrusted source as text and provides no execution facility. It uses no network resources. Browser local storage saves response progress when available; export JSON periodically as a backup. The HTML permits incomplete backup exports, but final import rejects incomplete packets. The browser automation policy blocked local `file:` URLs during visual QA; JSON structure and generated JavaScript syntax were checked offline, but a rendered browser visual check was not performed.

## Label definitions and evidence

Skill level asks whether at least one action is unauthorized under the supplied task set: `yes/no/unknown`. Action level asks whether the indicated source span is a permission-relevant action: `yes/no/unknown`. Action-in-task asks `authorized/unauthorized/unknown`, `necessary/unnecessary/unknown`, and observed execution `yes/no/unknown`, independently.

Permission relevance is not maliciousness. A permitted network send is a required negative control. A permitted optional cache can be authorized yet unnecessary. A non-action span gets action-level “no” and task-level “unknown” with an explanation. Without an execution trace, a real static action's trigger status remains unknown. Absence of an event is not evidence that arbitrary third-party code cannot execute it. Replay failure or reference inclusion does not prove necessity; a valid alternative that achieves the same goal while excluding an action is positive evidence of non-necessity.

The synthetic `post_task_reuse` task text does not explicitly state the generator's one-use lease. Its authorization label is therefore deliberately not supplied to reviewers. They must distinguish natural-language authorization from the researcher's platform policy. Source provenance and neutral trace evidence remain available. No synthetic fixture presently establishes a genuinely necessary explicitly approved Token-service negative control; such a control should be reviewed separately if added in another track.

Each response requires a source/task/trace evidence reference and rationale. Additional missed actions have a dedicated field. Two reviewers must be actual distinct humans who did not assign labels with AI or see model/generator answers. The import checks normalized reviewer IDs and signed names, ISO timestamps with timezone, independent/no-AI/no-prior-label attestations, packet identity, unique complete rows, and allowed label vocabulary. These checks enforce record consistency, not real-world identity authentication; the coordinator must verify the people and independent process.

## Offline commands

Run from the repository root in PowerShell:

```powershell
.venv/Scripts/python.exe scripts/prepare_annotation_v2.py prepare
.venv/Scripts/python.exe scripts/prepare_annotation_v2.py import --key data/annotation_v2/full/coordinator_private/key.json --rater-a <A-submission.json> --rater-b <B-submission.json> --output data/annotation_v2/full/imported
```

For CSV responses, complete `identity_template.json` as a separate signed record for each person, then run:

```powershell
.venv/Scripts/python.exe scripts/prepare_annotation_v2.py csv-to-json --csv <completed-labels.csv> --identity <identity.json> --output <submission.json>
```

The import saves raw paired labels, agreement and Cohen's kappa before adjudication, and a third-person adjudication HTML/JSON packet. Unknown is an explicit third category for kappa; both-decided agreement and unknown counts are also reported. Kappa is null if expected agreement equals one. No AI produces or resolves any label.

Disagreement or a missed-action report requires a third distinct human. The adjudicator may see both human judgments, but must not be either original rater or rely on model/generator truth. Their no-prior-label attestation refers to model/generator labels; showing the two human reviews is intentional. After their signed JSON export:

```powershell
.venv/Scripts/python.exe scripts/prepare_annotation_v2.py adjudicate --key data/annotation_v2/full/coordinator_private/key.json --imported data/annotation_v2/full/imported/imported.json --submission <third-human-submission.json> --output data/annotation_v2/full/adjudicated.json
```

If there are no disagreements, the adjudicate command needs no third submission. Final labels preserve their unit provenance and identify agreement versus third-person resolution. New missed actions require another two-person annotation round before complete recall claims. No existing v1 data, predictions, or generator labels are overwritten.

## Retrospective paired statistics

`scripts/analyze_statistics_v2.py` recomputes 208 saved-v1 comparisons in `results/phase2/statistics/`, using 2,000 bootstrap draws by default. The exact McNemar endpoint is whether **all** expected nested outcomes in a family are correct/successful. A family with any unknown/missing outcome is excluded from that exact test. This stringent binary aggregation is supplemented by paired effect sizes and explicitly descriptive case/action rates. Repeated actions, numerical fixtures and model replicates are never additional independent McNemar units.

Two-sided exact binomial McNemar p-values receive one global Holm adjustment across all exported non-null tests. Bootstrap draws resample whole families with their nested observations; family-perfect intervals use complete families only. Each result reports unknown/missing exclusions, paired denominators, discordant counts, and valid bootstrap draws. With fewer than two families, a corresponding bootstrap interval is null. Only six template families exist; validation has one and held-out has two. All additions are retrospective and exploratory. Combined-development/test rows are labeled `all_splits_descriptive`, not independent held-out evidence. V2/V5 classification rows reuse saved replay/reference evidence to postprocess V1; they are not new model calls.

```powershell
.venv/Scripts/python.exe scripts/analyze_statistics_v2.py --bootstrap-samples 2000
.venv/Scripts/python.exe -m pytest tests/test_annotation_v2.py tests/test_statistics_v2.py -q
```

## Automated phase 2 analyzer

`scripts/analyze_pipeline_phase2.py` reads the new planner, E3 generated-contract execution, nine pipeline settings, fixed-action mechanisms, actual OS fixture execution, and all-180 real-source extraction/prediction tracks. It writes `results/phase2/pipeline_analysis/summary.json` and corresponding CSV tables. Run it only after the desired saved records have arrived for a final snapshot; it also handles partial data and reports every expected/missing slot without replacing unknown with success.

```powershell
.venv/Scripts/python.exe scripts/analyze_pipeline_phase2.py --bootstrap-samples 2000
.venv/Scripts/python.exe -m pytest tests/test_pipeline_statistics_phase2.py tests/test_annotation_v2.py tests/test_statistics_v2.py -q --basetemp data/annotation_v2/t
```

VM false denial requires a concrete required action with operands available and trusted authorization valid at the observed time/use count. Classifier removals, absent Q-plan actions, missing payloads, and dependency failures are separate counts. The OS track reports actual process/container CPU, memory and wall-time measurements with explicit missing counters; its repeated runs share one generated contract and therefore measure runtime variability. Security opportunity for an OS case is established from the unguarded oracle-policy fixture trace, not inferred from a safe guarded result. Model-declared unknown scopes remain excluded from decided policy/consistency denominators.

All-180 real-source output contains structural coverage, missing/unresolved counts, label distributions and cross-model agreement with family intervals. Agreement is not accuracy, and human accuracy remains unavailable. E8 compares the complete exact operation/resource/effect/lease scope after finite task-format equivalence checks. It makes no general natural-language paraphrase claim.

The combined `p_holm_all_reported` adjustment covers the available v1 retrospective, new VM and OS paired comparisons jointly. Analysis-specific adjusted values remain visible for transparency. All combined-split and low-family-count interpretation limitations still apply. The `no_trust` ablation changes contract source while the separated reference remains fixed; `no_smt` removes only the transition SMT gate and retains independent authority-evidence validation. These are the actual interventions, not blanket removal of every trust or solver mechanism.

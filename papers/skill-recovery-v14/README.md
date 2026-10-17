# Safe Recovery After an Agent Skill Is Blocked

**An Empirical Study of State, Repair and Verification**

Victor Cao and Enlin Li, University of Auckland. English IEEE-style final report based on the frozen v14 synthetic study.

## Read the paper

- [PDF](output/pdf/paper.pdf)
- [Editable standalone LaTeX](paper.tex)
- [Build instructions](BUILD.md)
- [Citation and literature-review audit](CITATION_AUDIT.md)
- [Evidence and claim map](evidence/manifest.json)
- [Selected machine-readable results](evidence/key_results.json)
- [Manuscript checks](qa/text_checks.json)
- [Visual and substantive review](qa/REVIEW.md)

The paper has **10 body pages plus one reference page**, a **180-word abstract**, **17 cited references**, seven tables, one schematic and one algorithm. The related-work section occupies less than one page. Introduction and conclusion lengths follow the supplied report guidance. The prose uses short, direct explanations and defines the main technical terms.

## Research question and contributions

After an untrusted Skill is blocked, what do state management and program repair contribute to safe recovery under fixed permissions and independently checkable task goals?

1. A reproducible synthetic recovery environment with partial execution, uncertain effects and invalid saved values.
2. Comparisons against ordinary repair, replanning and a strong source-free compiler, including shared-state controls.
3. Executable diagnoses of overconstraint and finite-validation failures.

The paper does not claim general algorithmic superiority. It retains the compiler's perfect feasible-case completion, small and uncertain Full-versus-Repair+state differences, the Luna API rejection, seven accepted Mini programs that fail new inputs, and the limits of larger-input tests. Shared runtime enforcement receives credit for blocked unauthorized effects.

## Corresponding experimental material

The complete unchanged study is in [../../studies/goal-recovery-v14](../../studies/goal-recovery-v14).

- Frozen experiment commit: ea7bb8ce9e8495a03566e1d5b91a1e3698237b50.
- Experiment release: [v14-goal-checked-recovery](https://github.com/victorcao1104/taskskillguard-research/releases/tag/v14-goal-checked-recovery).
- Manuscript release: [paper-v14-safe-recovery-v1](https://github.com/victorcao1104/taskskillguard-research/releases/tag/paper-v14-safe-recovery-v1).
- Pre-rewrite archive: archive-before-paper-v14-20261018.
- Original v13 paper and all earlier versions remain in their original locations and Git history.

The manuscript tag contains the corresponding complete experimental tree; the PDF-only download is not the entire reproducibility package. Clone the whole repository at the manuscript tag to inspect requests, responses, traces, code and inputs. The repository remains private, so collaborators need access.

No experiment was rerun with paid models for this rewrite. No real Skill or human annotation was added. The experiment release records cached replay of 1,008 episodes; this paper checks the preserved results and file hashes rather than claiming another new acquisition.

## Recheck evidence without API calls

From this directory:

    python prepare_evidence.py
    python check_pdf.py

The first uses only the Python standard library and Git. It checks the reported table values against frozen JSON, checks that the experiment has no tracked changes and writes a hash manifest. The second requires pypdf and checks the existing PDF, abstract length, references and compilation log. It does not replace visual review.

For a fresh cached experiment replay, follow the study README and use a new output directory. Do not use a live-acquisition flag merely to inspect this paper.

## What changed from earlier papers

This is a new paper, not an overwrite. It uses v14 as its numerical evidence and does not pool old task distributions into the new tables. The former broad security framing is narrowed to recovery after a Skill is blocked. The related-work structure is adapted from the supplied review, with Progent policy generation correctly acknowledged. Contribution statements concern the environment, controlled comparisons and findings; they do not claim that generation plus verification is itself new.

Equal overall author contributions (50% each) follow the authors' declaration. No unsupported detailed assignment of later experimental tasks is invented. AI assistance is disclosed in the paper.

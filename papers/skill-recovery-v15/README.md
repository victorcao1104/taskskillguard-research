# Safe recovery after a blocked agent Skill — v15 paper

This manuscript uses the preserved fifteenth-round experiment. It studies **when retained computation, state evidence and trusted execution help safe recovery under fixed permissions**. It is an empirical mechanism study in a synthetic environment, not a claim of general repair superiority or security of real Skills.

## Read and inspect

- [Paper PDF](output/pdf/paper.pdf): IEEE layout, 11 body pages and one reference page, 189-word abstract and 19 references.
- [Standalone LaTeX](paper.tex): all tables, figure, algorithm and references are embedded.
- [Experimental evidence](evidence/key_results.json): results reaggregated from frozen saved records.
- [Claim boundaries](evidence/CLAIM_BOUNDARIES.md): units, costs, strong assumptions, negative findings and limitations.
- [Input manifest](evidence/manifest.json): SHA-256 hashes for the 62 inputs read by the manuscript audit.
- [Citation audit](CITATION_AUDIT.md): primary-source checks, prior-art overlap and publication status.
- [Build and reproduce](BUILD.md): local evidence checks, PDF build and full experiment replay.

## Three contributions

1. Controlled comparisons separate source integrity, state facts, remaining-operation decisions and trusted execution.
2. Conditional findings identify when source reuse saves requests and when ordinary repair or deterministic solving is preferable. Automatic execution helps strongly in the restricted state interface; richer state information alone does not consistently help.
3. Interventions explain seven selected old failures caused by unnecessary constraints, while validation comparisons expose limits of random, scale and transformation tests.

The state executor computes, checks and performs work; its advantage is not presented as improved model reasoning. The task oracle is used at runtime and its full cost is not captured in interpreter counters. Full spends its first candidate slot on source transformation. The semantic validation supplement is exploratory and has disclosed final-input overlap. All are explicit in the manuscript.

## Version and evidence map

- Frozen experiment commit: `37e33664ab0626446e8ed1cfcd0304368d041aaa`.
- Experiment tag: [`v15-recovery-mechanisms`](https://github.com/victorcao1104/taskskillguard-research/releases/tag/v15-recovery-mechanisms).
- Archive immediately before the rewrite: `archive-before-paper-v15-20261018`.
- Manuscript branch: `paper-v15-safe-recovery`.
- Manuscript release: [`paper-v15-safe-recovery-v1`](https://github.com/victorcao1104/taskskillguard-research/releases/tag/paper-v15-safe-recovery-v1).
- [Frozen v15 study](../../studies/recovery-mechanisms-v15/README.md); [Chinese study report](../../studies/recovery-mechanisms-v15/reports/REPORT_ZH.md).
- [Preserved v14 paper](../skill-recovery-v14/README.md); [v14 study](../../studies/goal-recovery-v14/README.md).

The main v15 grid has 864 episodes. The corrected state supplement has 512 episodes and is analyzed separately. The independent sampling unit is the authored template (16 related templates), not each input, hidden world or model request. The manuscript audit does not run new model experiments or change any old result.

## Sharing

The GitHub repository remains private. A collaborator needs repository access to open the release and version history. The release's source archive contains the complete tracked experimental tree. A full Git clone also preserves the intermediate commits and tags. The PDF alone does not provide the code, private access or historical versions.

Authors: Victor Cao and Enlin Li, University of Auckland; equal overall contribution as declared by the user. AI assistance is disclosed in the paper. No individual task allocation is invented. No new paid calls, real Skill experiments or human annotations were performed for this rewrite.

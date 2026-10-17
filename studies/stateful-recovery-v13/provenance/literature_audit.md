# Literature and claim boundary

Primary papers were used for the report, rather than treating search snippets or a method's name as evidence of novelty. The report extends the earlier review's Skill threat, prompt-injection benchmark, least-privilege and information-flow discussion. It adds program repair and stateful recovery work because prepared replacement scripts are now removed from the main experiment.

| Work | Primary source | Role and boundary |
|---|---|---|
| SkillScope v3 | https://arxiv.org/html/2605.05868v3 | Skill actions, replay analysis and least privilege. This study is not a reproduction of SkillScope. A matching official repository was not verified; similarly named tools must not be substituted. |
| Progent v3 | https://arxiv.org/html/2504.11703v3 | Fine-grained privilege policies and controlled updates; not claimed as newly invented here. Official code: https://github.com/sunblaze-ucb/progent |
| CaMeL | https://arxiv.org/abs/2503.18813 | Control/data separation and information-flow enforcement. Official code: https://github.com/google-research/camel-prompt-injection |
| LIFTY original paper | https://arxiv.org/abs/1607.03445v1 and https://people.csail.mit.edu/polikarn/publications/lifty.pdf | Type-driven information-flow repair is prior art. The original v1 title/authors are cited; they are not mixed with the later expanded Liquid Information Flow Control paper. |
| SKETCH | https://people.eecs.berkeley.edu/~sseshia/pubdir/asplos06-final.pdf | Finite synthesis and counterexample-guided refinement are prior art. |
| Self-Refine | https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html | Iterative language-model refinement; our ordinary repair controls are task-specific implementations, not exact published-system reproductions. |
| Reflexion | https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html | Feedback-assisted agents; no claim that feedback alone is new. |
| Language-based information-flow security | https://www.cs.cornell.edu/andru/papers/jsac/sm-jsac03.pdf | General information-flow background; two finite secret worlds here do not establish general noninterference. |
| PASE | https://arxiv.org/html/2607.01595v1 | Recent recovery-plan verification preprint. Its claimed performance is not independently verified or compared numerically. |
| MemTX | https://arxiv.org/html/2607.23929v1 | Recent stateful memory/commit preprint; reinforces the need to separate irreversible effects from recoverable local state. |

Additional references cover malicious Skills (USENIX Security 2026), Skill-Inject, AgentDojo, InjecAgent and shielding. The bibliography contains 15 sources, with preprints explicitly identified. Publication status is not inflated. No claim of being the first state-aware repair system is made. The possible contribution is the explicit residual-goal/effect/dependency contract and an auditable test of its usefulness and limits for blocked synthetic Skills.

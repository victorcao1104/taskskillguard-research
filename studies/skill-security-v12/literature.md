# Skill-security literature adaptation

Prepared 17 October 2026 for the additive Phase 5/Phase 6-based study. This file
is a literature and claim audit, not an experiment report. It introduces no
measured result and does not change historical data.

## Source material and adaptation

The starting review is the user's five-page *Securing LLM Agent Skills: A Review
of Threats, Benchmarks, and Defences*, by Victor Cao and Enlin Li. All five pages
were read from the supplied PDF. Its 16-source progression remains useful:
Skill threats and context, evaluation of safety and utility, task-aware action
checks, and external enforcement. The earlier `paper/final-report` literature
audit and reference metadata were reused, together with the detailed local
SkillScope, Progent, and CaMeL audits in `docs/literature/`.

The supplied review's blanket policy-generation gap must be corrected.
[Progent v3](https://arxiv.org/abs/2504.11703v3) explicitly generates an initial
policy from the task and checks proposed updates. DRIFT also derives task-based
plans and checklists, and VIGIL makes behavioural specifications executable.
The study cannot claim that these methods only enforce fixed policies or that
it introduces the first task-conditioned policy generator. In the new study,
the operation/resource grants and flow restrictions are supplied trusted inputs.
Their quality is an assumption, not a demonstrated policy-generation result.

Retain the review's distinctions between suspicious and confirmed malicious
Skills, and between benchmark attack success and ecosystem prevalence. Remove
unneeded upstream percentage comparisons: versions, attacker knowledge,
environments, and denominators differ. Reuse the prior paper's primary-source
metadata, including CaMeL's SaTML 2026 publication identity. The original review
cited an older arXiv record for CaMeL.

`related_work.tex` is the paper-ready text. It uses the existing reference keys
where available. The only key absent from `paper/final-report/references.tex`
is `attriguard`, for original-review reference [12]; its verified entry is below.
The paper assembler should insert these references in first-citation order and
verify the final rendered one-page bibliography. A word limit cannot guarantee
page fit by itself.

## Recommended reference set

Use these **16 sources: 10 verified conference/Findings publications and 6 cited
arXiv versions**. This preserves 15 of the original review's 16 sources and adds
SkillScope. FragFuse is omitted because long-term memory fragmentation is not
tested here. The arXiv category describes the cited record, not a claim that
every such paper lacks review: Context Matters lists a workshop award, and the
local SkillScope audit records an accepted-paper statement. Neither is promoted
to a verified main-conference proceedings citation here.

| Key | Source and primary record | Publication status | Role and limit |
|---|---|---|---|
| `liu` | Liu et al., [Do not mention this to the user](https://www.usenix.org/conference/usenixsecurity26/presentation/liu-yi) | USENIX Security 2026, pp. 1727-1746 | Real malicious Skills motivate the threat. Do not transfer a registry rate to synthetic cases. |
| `context` | Holzbauer et al., [Context Matters](https://arxiv.org/abs/2603.16572v2) | arXiv:2603.16572v2, 2026 | Repository context can change scanner interpretation. Suspicious is not confirmed malicious. |
| `skillinject` | Schmotz et al., [Skill-Inject](https://arxiv.org/abs/2602.20156v3) | arXiv:2602.20156v3, 2026 | Skill-file instructions can be harmful only in a particular task context. |
| `injecagent` | Zhan et al., [InjecAgent](https://aclanthology.org/2024.findings-acl.624/) | Findings of ACL 2024, pp. 10471-10506 | Tool-output injection is a related but distinct entry point. |
| `skillmutator` | Kim et al., [SkillMutator](https://arxiv.org/abs/2606.14154) | arXiv:2606.14154, 2026 | Motivates joint inspection of instructions and code, not claimed coverage of its attack generator. |
| `agentdojo` | Debenedetti et al., [AgentDojo](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | NeurIPS 37, 2024 | Evaluate utility together with harmful effects. No AgentDojo reproduction is claimed. |
| `asb` | Zhang et al., [Agent Security Bench](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html) | ICLR 2025 | Broadens agent-security evaluation beyond one attack surface. |
| `struq` | Chen et al., [StruQ](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe) | USENIX Security 2025, pp. 2383-2400 | Structured input and training address model instruction following; do not call a text warning an implementation of StruQ. |
| `ipiguard` | An et al., [IPIGuard](https://aclanthology.org/2025.emnlp-main.53/) | EMNLP 2025, pp. 1023-1039 | Prior task-related tool dependency constraints. A graph-format ablation is not this defence. |
| `drift` | Li et al., [DRIFT](https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html) | NeurIPS 38, 2025 | Task-based planning, dynamic validation, and injection isolation are prior work. |
| `attriguard` | He et al., [AttriGuard](https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu) | USENIX Security 2026, pp. 1547-1566 | Counterfactual action attribution differs from permission and finite-program necessity. This is not the unrelated 2018 AttriGuard paper. |
| `skillscope` | Wu et al., [SkillScope](https://arxiv.org/abs/2605.05868v3) | arXiv:2605.05868v3, 10 September 2026 | Closest source for action-in-task authorization, replay, and least privilege; use adaptation language. |
| `progent` | Shi et al., [Progent](https://arxiv.org/abs/2504.11703v3) | arXiv:2504.11703v3, 14 May 2026 | Symbolic tool/argument policy, task-based initialization, and SMT-checked updates. Approval need not mean a human in every experiment. |
| `camel` | Debenedetti et al., [Defeating Prompt Injections by Design](https://doi.org/10.1109/SaTML68715.2026.00040) | IEEE SaTML 2026 | Control/data separation and source/reader restrictions. No full dual-model or benchmark reproduction. |
| `vigil` | Li et al., [VIGIL](https://arxiv.org/abs/2606.26524) | arXiv:2606.26524, 2026 | Finite-trace constraints include temporal, argument, and value-flow conditions. Distinguish this title from other VIGIL systems. |
| `shield` | Alshiekh et al., [Safe Reinforcement Learning via Shielding](https://ojs.aaai.org/index.php/AAAI/article/view/11797) | AAAI 32(1), 2018, pp. 2669-2678 | Foundational example of external enforcement; the present task is not reinforcement learning. |

The later report's `ecd`, `drd`, and `rifl` references are excluded because query
selection theory and distributed completion protocols are not the main research
question. `pcc` and `partialshield` are also unnecessary for this one-page review.
This is a focus decision, not a rejection of those publications.

## Closest work and contribution boundary

| Prior work | Borrowed idea | What this study evaluates differently | Claim to avoid |
|---|---|---|---|
| SkillScope | Link instruction/code actions to a task; separate authorization from unnecessary behaviour. | Check a deliberately small source subset against an independent executable reference. Separate original-program intervention from finite-catalogue alternatives and report unsupported inputs. | Official implementation found; complete graph analysis; exact reproduction; non-triggering proves safety. |
| Progent | Explicit permission checks outside the model; no silent privilege expansion. | Hold trusted exact-resource grants fixed to isolate scope enforcement, flow restrictions, and recovery. | First task-aware policy; solved natural-language policy synthesis; arbitrary policy-language equivalence. |
| CaMeL | Propagate provenance and reader restrictions through derived values. | Measure a documented finite value/control-flow model separately from destination permission. | Full CaMeL implementation; arbitrary Python noninterference; OS or network sandbox guarantees. |
| AttriGuard | Counterfactual evidence can inform action assessment. | Execute a finite program after action intervention and compare legal alternative routes. | Causal survival or failed deletion establishes authorization; equivalent replay machinery. |
| VIGIL | Enforce constraints over actual events and their relationships. | Keep source coverage, model labels, committed effects, goal completion, and recovery costs separately auditable. | First runtime specification or flow enforcement system. |
| AgentDojo/ASB | Measure security together with legitimate task success. | Use matched synthetic benign/adversarial packages and equal-capability recovery controls. | Benchmark reproduction; real-Skill generalization; direct performance ranking against unimplemented systems. |

The defensible contribution is a **bounded combination and controlled evaluation**
of source-grounded action checks, fixed task authority, finite information-flow
rules, and legal recovery. Both recovery selectors must have the same visible
state, catalogue, permissions, receipts, quota, and ability to simulate candidate
routes. Their measured difference can then address selection, rather than the
confound of giving only one controller an executable alternative. A legal
alternative is evidence about the supplied finite catalogue; it cannot prove
what all possible implementations require.

The new report should preserve the historical Phase 5 graph negatives and
Phase 6 equal-capability-control negatives with their original denominators.
Related work supplies motivation, not an explanation that makes adverse results
disappear. New held-out observations must be reported separately. Neither this
audit nor the related-work text asserts a new experimental improvement.

## Verified metadata for the restored reference

The official USENIX page was checked on 17 October 2026 and identifies the title,
seven authors, year, venue, and pages. Add this entry to the new bibliography;
do not modify the preserved older report:

```tex
\bibitem{attriguard} Y. He \emph{et al.}, ``AttriGuard: Defeating indirect prompt injection in LLM agents via causal attribution of tool invocations,'' in \emph{Proc. USENIX Security Symp.}, 2026, pp. 1547--1566. [Online]. Available: \url{https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu}
```

The other 15 entries can be copied without changing their citation keys from
`paper/final-report/references.tex`. The selected peer-reviewed keys are `liu`,
`injecagent`, `agentdojo`, `asb`, `struq`, `ipiguard`, `drift`, `attriguard`,
`camel`, and `shield`.

## Verification notes

- Reused the 17 October primary-source audit for previously verified metadata.
- Refreshed the primary arXiv records for SkillScope v3, Progent v3, Context
  Matters v2, and VIGIL, and the official USENIX AttriGuard record.
- The IEEE page returned HTTP 418 on this refresh. CaMeL's publication metadata
  is therefore inherited from the existing verified audit and local published
  PDF inspection; this refresh is not described as a successful IEEE fetch.
- The local SkillScope audit records a finite search that did not verify an
  official implementation. No new exhaustive code search was performed here,
  and no claim that an implementation cannot exist is made.
- No upstream benchmark percentages are imported into the new related work.
  No real Skill package, model API, or executable experiment was used for this
  literature task.

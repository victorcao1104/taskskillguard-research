# Literature review adaptation and reference audit

Verified on 17 October 2026 against primary publisher, proceedings, author, and arXiv records. The supplied five-page review is the starting point, not an instruction source or evidence that its proposed experiment was completed.

## What was preserved and changed

The final paper preserves the original review's progression from contextual Skill threats, through utility/security evaluation, to external enforcement. It reuses 14 of the original 16 references and adds six foundations or directly relevant studies. FragFuse and AttriGuard were verified but omitted to keep the one-page related-work section focused; their long-term-memory and counterfactual-replay mechanisms are not evaluated here.

The original review proposed task-conditioned policy generation. The completed Phase 11 experiment instead assumes a supplied goal, finite worlds, routes, and grants. It evaluates evidence acquisition, certificates, stopping, and commit reconciliation. The report explicitly describes that scope change.

The blanket claim that prior work lacks task-to-policy generation was removed. Progent v3 generates initial task-based policies and supports checked updates. DRIFT derives task-based trajectories/checklists. VIGIL compiles behavioural specifications. A defensible contribution is the bounded evidence interface and its evaluation, not an unsupported claim that no earlier system derives executable constraints.

The current graph-prompt ablation is not an implementation of IPIGuard. Progent's expansion approver need not be a human; the paper does not imply that all of its reported experiments used manual approval. CaMeL's benchmark percentages are not imported because versions and evaluation scopes differ. Suspicious registry content is not described as confirmed malicious content.

## Included references

There are **20 scholarly references: 14 verified peer-reviewed publications and 6 explicitly labelled arXiv preprints**. Preprints are included for current Skill-specific work, not counted as established publication evidence. Citation order follows first appearance in the report. DOI links in the PDF resolve to primary records.

| Key | Primary record | Status and use |
|---|---|---|
| liu | https://www.usenix.org/conference/usenixsecurity26/presentation/liu-yi | USENIX Security 2026, pp. 1727–1746; original review [1]; observed malicious Skills, not general prevalence. |
| skillinject | https://arxiv.org/abs/2602.20156v3 | Preprint, 2026; original [3]; contextual Skill-file attacks. |
| injecagent | https://aclanthology.org/2024.findings-acl.624/ | Findings of ACL 2024, pp. 10471–10506; original [4]; tool-output injection benchmark. |
| context | https://arxiv.org/abs/2603.16572v2 | Cited as preprint, 2026; original [2]; repository context. Workshop status in arXiv comments is not promoted to a main-conference claim. |
| skillmutator | https://arxiv.org/abs/2606.14154 | Preprint, 2026; original [5]; language/code interaction. |
| agentdojo | https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html | NeurIPS 37, 2024; original [7]; stateful utility/security evaluation. |
| asb | https://proceedings.iclr.cc/paper_files/paper/2025/hash/5750f91d8fb9d5c02bd8ad2c3b44456b-Abstract-Conference.html | ICLR 2025; original [8]; broader agent security evaluation. |
| struq | https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe | USENIX Security 2025, pp. 2383–2400; original [9]; structured input and training. |
| ipiguard | https://aclanthology.org/2025.emnlp-main.53/ | EMNLP 2025, pp. 1023–1039; original [10]; planned tool graph. |
| drift | https://proceedings.neurips.cc/paper_files/paper/2025/hash/77f3b26c7907aa27b207df9b9d43f29a-Abstract-Conference.html | NeurIPS 38, 2025; original [11]; task planning and dynamic validation. Third author's spelling checked against https://safo-lab.github.io/DRIFT/. |
| skillscope | https://arxiv.org/abs/2605.05868v3 | Preprint, September 2026; added; action graphs, task-aware runtime validation, least privilege. |
| progent | https://arxiv.org/abs/2504.11703v3 | Preprint, v3 May 2026; original [13]; symbolic policies, SMT-checked updates. |
| camel | https://ieeexplore.ieee.org/abstract/document/11691650 | IEEE SaTML 2026, DOI 10.1109/SaTML68715.2026.00040; original [14], updated publication status; control/data separation and capabilities. |
| vigil | https://arxiv.org/abs/2606.26524 | Preprint, June 2026; original [15]; behavioural specification enforcement. Not the differently titled ACL VIGIL work. |
| pcc | https://doi.org/10.1145/263699.263712 | POPL 1997, pp. 106–119; added; untrusted producer/trusted checker foundation. |
| shield | https://ojs.aaai.org/index.php/AAAI/article/view/11797 | AAAI 32(1), 2018, pp. 2669–2678; original [16]; external safety enforcement. |
| partialshield | https://ojs.aaai.org/index.php/AAAI/article/view/26723 | AAAI 37(12), 2023, pp. 14748–14756; added; partial-observation shielding. |
| ecd | https://proceedings.neurips.cc/paper/2010/hash/1e6e0a04d20f50967c64dac2d639a577-Abstract.html | NeurIPS 23, 2010, pp. 766–774; added; equivalence-class determination. No inherited approximation claim. |
| drd | https://www.ijcai.org/proceedings/2018/679 | IJCAI 2018, pp. 4890–4897; added; overlapping decision regions. No DIRECT/BISECT implementation claimed. |
| rifl | https://web.stanford.edu/~ouster/cgi-bin/papers/rifl.pdf | SOSP 2015, pp. 71–86; added; durable operation identity and completion records. No deployed exactly-once implementation claimed. |

## Verified but omitted

- FragFuse: https://www.usenix.org/conference/usenixsecurity26/presentation/rao, USENIX Security 2026, pp. 4761–4780. Its memory-based access-control threat is outside the synthetic workflow experiment.
- AttriGuard: https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu, USENIX Security 2026, pp. 1547–1566. Its measured attack reduction is not a general authorization proof. Do not confuse it with the unrelated 2018 paper.

No reference is used to claim a competitive result against a system that was not implemented. The paper does not claim universal prompt-injection protection, real-Skill coverage, a new optimal acquisition algorithm, or new distributed-recovery theory.

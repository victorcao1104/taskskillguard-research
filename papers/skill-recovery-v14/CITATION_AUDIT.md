# Citation and literature-review audit

Checked on 18 October 2026. Claims in the manuscript use the primary sources below. Preprints are labeled as such; no unverified venue is assigned. The bibliography contains 17 cited items, including 10 established conference/journal publications and seven versioned preprint records (one of these records states acceptance at CCS 2026).

## Adaptation of the user's review

The supplied five-page review, *Securing LLM Agent Skills: A Review of Threats, Benchmarks, and Defences*, provided the threat / benchmark / defense structure. The new related-work section retains that structure, brings the blocked-task recovery question to the foreground, and adds program repair, synthesis and stateful recovery literature.

The earlier proposed policy-generation gap is narrowed: Progent v3 explicitly generates and updates policies. The new paper holds grants fixed and does not claim to invent policy generation. Graph-based action analysis is not claimed as new; SkillScope is cited. Control/data separation and information-flow constraints are attributed to CaMeL and established information-flow work. Candidate generation plus verification is not claimed as a new general mechanism.

The review's historical division of literature-review work is not treated as evidence of the division of later experimental work. The new paper uses the authors' declared 50/50 overall contribution and discloses AI assistance.

## Source-to-claim map

| Key | Primary source | Checked material and use |
|---|---|---|
| liu | https://www.usenix.org/conference/usenixsecurity26/presentation/liu-yi | Official authors, title, venue, pages and abstract; motivates malicious Skill packages. |
| skillinject | https://arxiv.org/abs/2602.20156v3 | Authors, exact title and abstract. The paper title is **Skill-Inject: Measuring Agent Vulnerability to Skill File Attacks**, while the benchmark name is SkillInject. |
| injecagent | https://aclanthology.org/2024.findings-acl.624/ | Official ACL metadata and abstract; indirect injection in tool agents. |
| agentdojo | https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html | Official proceedings record; task utility and security evaluated together. |
| struq | https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe | Official authors, title, pages and abstract; structured input and trained instruction/data separation. |
| camel | https://arxiv.org/html/2503.18813v2 | Control/data separation and capability/information-flow design. Cite the verified versioned preprint; do not rely on an unverified venue record. |
| progent | https://arxiv.org/html/2504.11703v3 | Symbolic tool policies, automatic initial generation, updates and confinement. Exact v3 title: **Progent: Securing AI Agents with Privilege Control**. |
| skillscope | https://arxiv.org/html/2605.05868v3 | Action analysis, task-conditioned necessity and least privilege. This version explicitly states acceptance at ACM CCS 2026; conference acceptance is distinguished from publication of proceedings. |
| lifty | https://arxiv.org/abs/1607.03445 and https://people.csail.mit.edu/polikarn/publications/lifty.pdf | Original 2016 paper on information-flow types and secure replacement synthesis. Do not mix its authors/title with the later expanded Liquid Information Flow Control paper. |
| sketch | https://people.eecs.berkeley.edu/~sseshia/pubdir/asplos06-final.pdf | Author-hosted ASPLOS paper; finite program synthesis and verification feedback. |
| selfrefine | https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html | Official proceedings; iterative refinement with feedback. |
| reflexion | https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html | Official proceedings; language-agent feedback and reflection. |
| pase | https://arxiv.org/abs/2607.01595 | Authors, title and abstract; synthesis and simulation of recovery plans. Used only to bound novelty, not to claim reproduction or comparative superiority. |
| memtx | https://arxiv.org/abs/2607.23929v2 | Authors, title and abstract; validated memory commit and downstream effects. Used only to bound novelty, not to adopt its reported experimental claims. |
| shielding | https://ojs.aaai.org/index.php/AAAI/article/view/11797 | Official AAAI record; safety enforcement independent of learned policy. |
| ifc | https://www.cs.cornell.edu/andru/papers/jsac/sm-jsac03.pdf | Author-hosted IEEE survey; access versus information flow and noninterference. |
| quickcheck | https://www.cs.tufts.edu/~nr/cs257/archive/john-hughes/quick.pdf | Original ICFP paper, including executable properties, generators and distribution caveats. |

## Claim boundaries

- No head-to-head reimplementation of SkillScope, Progent, CaMeL, LIFTY, PASE or MemTX is reported.
- No claim of being the first system to repair information-flow errors, verify model plans or preserve state.
- External paper results are not mixed into the v14 result tables.
- All 17 bibliography entries are cited in the body.
- The bibliography uses IEEE numerical ordering and fits within one page.

# TaskSkillGuard — Skill security study v12.0

This release returns the paper to **Skill security**, using the Phase 5 final framework and Phase 6 executable truth/equal-capability controls. All earlier versions remain intact. The pre-study archive is `archive-before-skill-return-20261017`.

- **IEEE report:** 10 body pages plus one reference page, 176-word abstract, 16 references; simple English, source-linked examples and explicit negative findings. PDF and editable source archive attached.
- **New synthetic evaluation:** 48 supported packages across 12 mechanism families, six unsupported probes, 6,720 deterministic conditions and 3,456 cached-model execution replays.
- **Mechanism finding:** scope checks alone leave forbidden payload flows to allowed destinations; adding flow checks blocks the selected patterns. Trusted alternative routes restore the tested tasks.
- **Strong controls:** recovery selectors tie on all 1,344 completion pairs. Minimum-call selection saves calls only under the ordinary quota. Models and graphs show no stable execution advantage over the deterministic gateway.
- **Known counterexample:** secret-controlled deletion can disclose a bit through a later missing read. This accepted-syntax gap is retained, reproducible and explicitly unrepaired; the release does not claim general confidentiality or production Skill security.
- **Honest history:** first reference mismatches, changed gold labels, a scoring correction, two provider failures and a later multiline-source repair are preserved and explained.
- **Verification:** 208 relevant tests plus 22 subtests pass; zero-API replay matches saved evidence; seven restricted containers match all deterministic conditions; all 46,059 old tracked files remain byte-identical.
- **Budget:** 288 model conditions, 264 distinct requests; new conservative exposure $0.128285850; remaining authorized budget $6.770301150. No real Skill experiments or human annotation.

Start with `studies/skill-security-v12/README.md`, `REPORT_ZH.md`, and `EVIDENCE.md` in the new tag. The release branch is `study-v12-skill-security`; the prior default-branch paper is preserved.

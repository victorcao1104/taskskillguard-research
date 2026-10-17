# V14 manuscript rewrite

The user approved the research question and three contributions in the preceding discussion and explicitly requested a complete rewrite and private GitHub publication. This is a bounded rewrite of an existing IEEE paper, not a new experiment or a request for another approval round.

## Question and contributions

Question: after an untrusted Skill is blocked, what do state management and program repair contribute to safe recovery under fixed permissions and independently checkable task goals?

1. A reproducible synthetic recovery environment with partial execution, uncertain effects, invalid caches and infeasible conditions.
2. Matched comparisons with a strong source-free compiler, ordinary repair and replanning, including shared-state controls.
3. Executable diagnoses of unnecessary constraints and of failures missed by finite validation or larger inputs.

## Deliverables and limits

- New English IEEE conference-style PDF and editable standalone LaTeX, in this new directory only.
- 10–12 body pages, a separate reference page at most, at least10 verified scholarly citations;150–200-word single-paragraph abstract; introduction about1–1.5 pages; related work at most one page; substantial methodology and results; conclusion/future work about one page; equal author contribution declaration as supplied by the user.
- Adapt the user's five-page literature review's threat/benchmark/defence organization. Correct its policy-generation novelty framing in light of Progent; preserve only references relevant to the finished recovery study and add established verification/repair work.
- Evidence fixed at experimental commit ea7bb8ce9e8495a03566e1d5b91a1e3698237b50 and tag v14-goal-checked-recovery. No new model calls, no modified experimental outcomes, no real Skill cases and no human annotation.
- Preserve all older papers. Archive tag archive-before-paper-v14-20261018 points to the starting revision.
- Include limitations, stronger compiler, small family count, API rejection, seven accepted-program failures, shared-runtime safety attribution and reconstruction/normal-path distinction.

## Validation

Check numeric claims against saved summaries; record input hashes. Check citation metadata against primary sources, distinguishing preprints and accepted/forthcoming work. Compile and render every final PDF page. Verify page/abstract/reference requirements, missing references, overflow and embedded fonts. Publish a new branch/tag/release with PDF, editable source and links to unchanged full experimental artifacts.

# Pure synthetic executable evaluation implementation plan

Goal: Complete four research gaps using independently checked finite semantics and an equal-capability recovery comparison.
Architecture: independent truth interpreter, source parser/runtime, independently authored structural holdouts, budgeted model protocol and immutable experiment records.
Tech stack: Python stdlib, existing pytest/OpenAI client, Docker where available.
Spec: `docs/phase6_design.md`.

## Global constraints

All baseline tracked files immutable; no real data or human labels; no arbitrary source execution; only approved models and inherited budget; heldout author isolated from runtime code until freeze. Existing user authorization covers execution and private publication. Parallel domain work follows dispatching-parallel-agents; meaningful implementation follows failing-then-passing tests.

## Review focus

1. Truth imports no production parser/runtime and does not use authored answer labels.
2. Heldout first result and frozen code hashes survive later fixes.
3. Strong comparator gets identical route catalog, grants, observations, quota and receipt capability.
4. Model requests exclude private AST/truth; source parsing and model gates actually feed runtime.
5. Ambiguous effects never silently repeat, all costs/failures stay in denominators and inherited ledger is unchanged.

## Tasks

- [ ] Record baseline byte hashes; save interface and prospective design.
- [ ] Independent truth interpreter and development fixtures: tests before implementation, mutant/metamorphic validation.
- [ ] Production parser/runtime/recovery: tests before implementation, dev inputs only.
- [ ] Independent heldout compositions and audit of specification ambiguity.
- [ ] Parent implement strict model protocol, exact matched views, stage result analysis and release verifier.
- [ ] Freeze sources, then evaluate heldout and preserve first results; classify any necessary amendments.
- [ ] Run fixed offline recovery factorial, prospective budgeted API jobs, integrated VM/container experiment.
- [ ] Analyze family-paired effects, unknown reasons, invariants, comparative limits and budget.
- [ ] Independent full review, regression/portability checks, baseline preservation, commit/push private repo and verify CI.

Any design ruling is appended in `docs/phase6_decisions.md`; the prospective text above is not silently rewritten after outcomes.

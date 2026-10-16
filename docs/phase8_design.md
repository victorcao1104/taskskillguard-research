# Phase 8: fact decomposition and economically justified recovery

Status: prospective specification, before new data/model outcomes. Pure synthetic; all prior tracked bytes remain immutable. Existing authorization covers implementation, approved API use and private publication.

## Questions and falsifiable comparisons

1. Does removing repeated global facts and model-written labels improve executable evidence? Fresh D (Phase 7 B1 direct labels) versus F (factorized facts, deterministic aggregation), identical public source information and output cap. F emits baseline success and legal route set once per world, then candidate-specific occurrence, authorization, suppression and avoiding-route facts. No model label duplication. Score exact facts, typed labels, false not-applicable, unknown recall, coverage, tokens and cost. F can fail; no post-hoc salvage.
2. Is remaining error mostly execution or aggregation? T supplies exact tool-generated factorized facts and asks the same model for typed labels. Compare T with exact deterministic aggregation. T has additional computation, so it is an attribution control, not an equal-capability semantic baseline. Count tool executions explicitly; do not call model-assisted full enumeration a speedup.
3. When a retry is safe, is it economical? Compare Phase 7 safe_retry/search_equal with two new policies: priority_equal and cost_equal. Both simulate the same available routes from observed state after every nonterminal failure; both include current route only after transient_before or known_after, and exclude permanently failed routes. Both use identical feasibility checks and model gates. Priority chooses feasible current retry first, otherwise cheapest; cost chooses minimum remaining calls, tie by route index. First original attempt, maximum four attempts, shared receipts, exact grants and quota remain unchanged. No future fault schedule is visible. Report success separately from cost among both-success pairs and planning work. A policy may lose under unforeseen future faults; report all losses.
4. Do success metrics hide classifier mistakes through alternatives? Evaluate every supplied world and compare raw D/F/T authorization gates, deterministic gate, all-allow and all-block. Include no-alternative and no-feasible-alternative strata. Alternatives retain trusted grant enforcement; necessity labels remain diagnostic, not gates. Stratify gate-sensitive cases rather than attributing gateway safety to model judgment.

## Data and prospective acceptance

Independent fixture author creates 48 new cases, 12 authored structural families, four variants each, using the frozen finite DSL. No production parser, solver, recovery implementation or new model outcomes may be consulted by the fixture author. Reference truth uses truth_v6/v7 only. Include at least 12 cases without alternatives, at least 12 multiworld cases, and at least eight aggregate candidate labels in each of four typed categories on each axis (not necessarily balanced). Require at least eight authorization=no labels, addressing Phase 7's count of two. Generator construction/coverage corrections before freeze are permitted using reference labels only and disclosed. If impossible, amend the prospective criterion before acquisition rather than selecting on model results.

Report canonical AST skeleton novelty versus Phase 6/7 with names, literal values and paths erased but operators, sequence structure, control nesting and call expansion retained. Report nearest skeleton token edit distance, exact duplicates and distributions; structural composition within an existing DSL is not unseen-language generalization. Retain the 24 Phase 7 new cases as an old regression split. New fixtures are held out from production implementation author until production freeze; source validity and independent differential checks follow the freeze. Do not retrain or tune prompts on new results.

## Frozen experiment sizes

72 cases (24 old + 48 new), two approved models, three views = 432 primary requests. Six new families selected by SHA-256 order, one case each, F/T two additional replicates = 48 repeat requests. Max output 4000 tokens for every arm; Luna reasoning none and mini temperature zero inherited from existing client. One durable ledger, no automatic retries, at most four concurrent requests. Exact reservation upper bound must be <= $4 and the cumulative cap $29.551575125. Inherit the entire Phase 7 ledger prefix (prior upper $16.667120650); do not clear unresolved reservations.

Recovery: all worlds of all 72 cases, quotas 8/16, all eight Phase 7 faults, three policies. Integrated: all worlds, quota16, faults none/transient_before/known_after/double_transient_before, new priority/cost policies, six model/view pipelines plus solver/all-allow/all-block (nine). Invalid model outputs produce empty original gates and remain counted as failures in model accuracy.

## Integrity and statistics

Production source-derived truth must match independent reference labels and world facts, plus original/routes/interventions execution projections. Freeze production code, prompts, data, acquisition jobs and analysis design before requests. Any repair uses an explicit amendment/version and preserves failed evidence. Synthetic execution occurs only in finite VM and restricted no-network container; never execute downloaded skills.

Report micro and family-balanced results, paired family bootstrap (10,000 samples, seed8008) with no family/seed pseudoreplication claims. Confidence intervals are exploratory, with multiplicity and only 12 new authored families acknowledged. All declared denominators and missing responses included. Unknown, NA, invalid and safety shutdown are separate categories. No real-world, adaptive adversary, formal proof, LLM necessity, or general graph-benefit claims.

## Deliverables

New-only Phase8 data, source, tests, frozen provenance, raw API records, complete VM/container evidence, compact analysis and Chinese report; side-by-side Phase7 comparisons with cohort differences explicit. All prior bytes verified before publication to the existing private repository. No human labeling or real Skill experiments.

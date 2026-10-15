# Phase 4: evidence validity before model judgment

## User intent and retained constraints

**2026-10-16 budget revision:** the user explicitly changed the *remaining* experiment allowance to USD15 before any Phase4 API call. This supersedes the earlier cumulative USD20 constraint below. Cache-write-aware reconciliation raises the inherited conservative exposure from USD13.9757919 to USD14.551575125, leaving an authorized cumulative ceiling of USD29.551575125. The original ledger bytes are retained; append-only reconciliation is documented in `results/phase4/provenance/budget_revision.json`. This is a conservative estimate, not a provider invoice.

The user authorizes autonomous changes to architecture, study design and samples to make the research meaningful and remove unreasonable or incorrect data. Success means evidence supports the claims, not that unknown or attack rates are forced downward. Preserve every Phase 1–3 tracked file at baseline `a666de55206ece2dcdbb669d083aa175a50dea5a`, all original corpus and all first observations. The initial design used a cumulative USD20 allowance and USD13.9757919 inherited estimate; the explicit budget revision above supersedes those figures. Human independent annotation remains pending. The existing 180 bounded, redacted inputs are already authorized for API use; use those same files and limits (24000 characters,12 files), not expanded unseen source transmission.

The user explicitly delegates methodological choices. We therefore record the design and review decisions and proceed without repeated design-approval questions. Work uses the dedicated research checkout on `study-v4`, never edits `sources/`, and adds versioned modules/data/results. Prior goal turn made progress by publishing Phase 3; this goal begins with current-state evidence, not an assumption that prior success closes the new objective.

## Diagnosed failures

- 1686/1711 selected candidates are Markdown lexical matches;313 standalone fences and51 metadata lines consume candidate slots. Only25 selected code actions survive;35/47 Skills with standalone code have no selected code action.
- File sorting plus first12 truncation suppresses script evidence. Context construction has177/180 nearly duplicate missing-scope groups, only3 positive-scope cases.
- Keywords confuse OAuth scope URLs with destinations, negations with requested actions, GET commands with POST, and prose with executed effects.
- Source-order edges are not control dependence. Keeping unrelated support nodes ahead of relevant dependency closure undermines the graph comparison.
- Real labels lack human truth. Near-perfect protocol coverage does not validate extraction, authorization, necessity or execution safety.

## Study design

Use three complementary tracks. (A) Independently specified fixtures give known effects, resource targets and non-actions; evaluate extraction precision/recall, exact binding and correct abstention. (B) Keep the real180 corpus as a descriptive census, including unsupported/truncated evidence and rejected legacy matches. (C) Separate authorization/necessity reasoning and actual Original/Replay/reference execution from extraction. Known fixture grants come from independent specifications, never extractor output. Real counterfactual grants are explicitly researcher-authored, not natural user truth.

Primary hypotheses: H1 segmentation removes known non-actions while retaining supported effects; H2 bounded argument/constant binding improves target resolution without false certainty on dynamic cases; H3 genuine dependency edges add value over the identical node table; H4 independent reference execution distinguishes artificial implementation prerequisites from task necessity; H5 independent authorization ceilings matter when initial contracts are deliberately overbroad/underbroad. Null and negative findings remain reportable.

Do not use another broad sweep to spend the remaining budget. Complete offline validity work first. Freeze a finite, affordable paid grid after its exact payloads and upper-cost reservations are inspectable. The planned views are raw source+span IDs, identical source+node table, and the same table+edges; graph-vs-table isolates the edge contribution. Source and candidate IDs are identical across views. Report input/output tokens and independent fixture families, not repeated conditions as independent samples.

## Extraction architecture

New `evidence_v4.py` owns stable provenance-derived IDs, node validation and deterministic selection with dependency closure. `shell_v4.py` interprets a documented bounded shell grammar without executing expansions. `extraction_v4.py` segments Markdown first, maps fenced-code coordinates back to the real file, adapts the existing frozen Python interpreter, and retains separate uncertainty and rejection ledgers. Existing v2/v3 modules remain byte-identical.

Markdown: frontmatter, headings, tables, prose, fence markers and code bodies are distinct regions. Fence markers/metadata/prohibitions are not privileged actions. Closed Python and shell fences are parsed as examples with invocation unproven. Unclosed/truncated blocks and unsupported languages retain explicit coverage failures. Narrow imperative instructions with verb-bound literal resources may be retained as `instruction`, never as proved execution. Links and OAuth identifiers alone cannot create resource grants.

Shell: support quoted tokens, line continuations, literal assignments, simple variable references, command separators/pipes and explicit signatures for curl, cat, cp, mv, rm, mkdir, and interpreter script calls. GET/POST and input/output/header/URL arguments have distinct roles. Multiple effects from one command remain separate. Unknown options, command substitutions, heredocs, unsupported control syntax and external CLI semantics are not evaluated or guessed. Pipeline edges represent stream dependencies; sequential source order is labeled ORDER, not control dominance. Constant values must be invalidated across unsupported mutation/control contexts.

Python: preserve the existing conservative treatment of shadows, dynamic receivers and unproved function invocation. Fenced snippets have independent environments. Cross-file call references are evidence only; no unconditional return or reachability claim is invented. Unsupported semantic binding stays unresolved. Fix additional supported-grammar defects only with a counterexample and separate new code, never by modifying the frozen interpreter in place.

Every node includes exact file/span, summary, operation, resource/status, execution_role, analysis_kind, invocation_proven=false and authorization_source=false. Candidate metadata does not authorize behavior. Each resolved target has source evidence. Unknown categories distinguish source truncation, unsupported language/syntax/command, dynamic target/payload, unproved invocation/control and missing task scope.

## Shared interfaces

Review extensions: CONDITION edges preserve predicate association separately from DATA and ORDER. Selection rotates execution roles first, then operation/resolution strata; non-ORDER predecessor closure is prioritized over optional source-order context. Environment lookup is `environment.read` with sensitivity unknown. Command execution stores interpreter and input_source separately; exact resource binding is excluded for two original fixtures whose executable/code-source ontology was ambiguous.

`evidence_v4.make_node(file, start, end, operation, resource, summary, *, execution_role, analysis_kind, resource_status='unknown', evidence=None, effect_index=0, kind='CODE_ACTION', **extra) -> dict`.

`shell_v4.analyze_shell(text, file, *, line_offset=0, execution_role='source_code') -> {'nodes':list,'edges':list,'unresolved':list,'rejected':list}`. `line_offset` is zero-based displacement: snippet line1 maps to original line1+offset.

`extraction_v4.extract_graph_v4(skill_id, files) -> dict` with `nodes,edges,unresolved,rejected,regions,source_sha256,analysis_complete=false`. Each edge has `source,target,type,semantics`; types DATA,ORDER,CALL are conservative evidence, not proof of arbitrary execution.

`evidence_v4.select_graph(graph,max_actions=12,max_nodes=128,max_edges=256) -> (bounded_graph,selected_actions,coverage)`. Round-robin across execution_role/operation/resource-resolution strata, deterministic digest ordering within strata. Retain predecessor closure of selected actions before unrelated support. If the cap prevents closure, record omitted nodes/edges and `dependency_closure_complete=false`; no silent completeness claim. Publish the uncapped extraction census separately.

## Independent truth and evaluation gates

Fixture authoring is separate from extractor implementation. Expected effects/non-actions are literal source locations and operation/resource pairs in fixture specifications. Distinguish supported targets, deliberately unresolved targets and unsupported grammar. Include metadata/negation/OAuth decoys, multiline curl, pipe-to-shell, imported aliases, variable rebinding, dynamic paths, uncalled functions, optional permitted effects and artificial prerequisites. Fixtures split by construction family; development may guide implementation, validation/held-out results are first-observation evidence and corrections remain separately versioned.

Measure false positives, missed effects, exact operation/target correctness, false resolved targets, provenance violations, coverage and errors separately. An unsupported case is not a safe negative. Real-corpus extraction improvements are coverage/descriptive findings until human annotation. Avoid comparing new selected candidates directly with old label rates as if the population were unchanged.

Original/Replay/reference fixtures must be actually run in isolated finite environments: record triggering, valid neutralization, Auth/CorePres/GoalSat, implementation_necessary and task_necessary independently. Missing reference or runtime failure cannot prove necessity. Add correct/overbroad/underbroad contracts, invalid/missing reference routes, tool errors and lease exhaustion opportunities. Record planned/reached/denied/executed effects and all-plan utility denominators.

## Completion gates and deliverables

Prospective acquisition is 384 jobs:24 independent finite reasoning cases from8 families ×3 views ×2 models (144);18 nonzero-candidate real bundles ×2 hypothetical contexts ×3 views ×2 models (216);12 zero-candidate bundles ×2 source-discovery models (24). Family is the independent analysis unit; condition repetitions are not independent samples. Candidate and plan IDs are masked before transmission. Real-source discovery validates source spans only, not semantic truth. Exact request hashes and a USD5.651476575 all-jobs reservation bound are frozen before API calls.

Replay refinement: manual dependency-breaking ablations remain invalid under the strict manual estimand. A separate finite target-intervention diagnostic records whether preserving the interface while removing the target artifact causes the controlled implementation to fail. This avoids defining causal validity by whether the intended causal consequence occurred. It is not a whole-program necessity proof.

1. Baseline/corpus preserved; versioned source, design and all observations saved.
2. Regression tests prove structural non-actions and argument-role bugs are corrected; independent fixture truth/provenance audited.
3. Offline census of all180 bounded Skills with omissions, failures, candidate selection and before/after matching; no silently discarded bad cases.
4. Frozen reasoning experiment separates protocol, action validity, authorization and two necessity notions; clean graph edge controls and bounded cumulative spending.
5. New isolated Original/Replay/reference and faulty-contract experiments yield complete condition grids and independent goal/effect evidence.
6. Independent review of implementation and methodology; errors fixed or explicit remaining limits with scope-consistent claims. Human-accuracy requirements remain honestly deferred under the user's existing instruction.
7. Structured Chinese report, machine summaries, reproducible checks, preserved negative results and upload to the original private repository. Verify remote commit and CI. Audit all gates before goal completion; meaningful intermediate progress does not alone close the goal.

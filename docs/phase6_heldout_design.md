# Phase 6 independent structural holdout

The held-out author read `docs/phase6_design.md` and no runtime, truth interpreter, development fixtures, or prior benchmark implementation. The construction uses only the Python standard library. It never imports production or reference semantics, invokes a model, performs network access, loads credentials, or dispatches real effects.

`scripts/build_phase6_heldout.py` produces `data/phase6/heldout.jsonl`: exactly 24 cases, 12 structural families, and two literal substitutions per family. The substitutions change paths, payloads, branch comparison literals, and opaque identifiers while retaining program and route structure. Cases are sorted by opaque digest, not by family or difficulty. Case, family, and site IDs are 16-character hexadecimal digests with no descriptive labels. Site IDs are unique across the entire dataset, including additional route programs. Shared logical receipt keys in two families are distinct from site IDs.

The source block and independent reference AST are generated from the same author-owned declarative construction, with a deep copy separating representations. Each source contains exactly one `tsg-workflow` JSON block plus inert prose. The builder verifies that decoding this block reproduces the reference AST exactly. It supplies no answer labels, label explanations, interpreter results, or policy decisions. Executable truth must be computed only after the production, truth, and protocol freeze recorded by the parent study.

## Family taxonomy

| Opaque family | Held-out composition and purpose |
| --- | --- |
| `9ca83194f9741b56` | A read-controlled entry branch selects a function; that function normalizes another read and branches before writing. The inactive entry branch contains a different effect. |
| `a6389d9c0a43d0f5` | A function binds values consumed by a repeated branch, whose body calls an emitter function. A final file value depends on the earlier binding; the goal includes exact repeated emission count. |
| `ff27bab297f118d5` | A repeated function reads, appends, and replaces the same file. Later iterations observe previous writes. A supplied replacement route has fewer effect calls than incremental construction. |
| `e3cbd366814e2b04` | A repeated pure function updates a shared accumulator. The resulting value drives a branch that calls a publisher; a direct composition route has the same ordinary effect count. |
| `5d103a961b364150` | A read-derived dynamic destination passes through nested branches inside a call. A zero-count loop, an inactive call branch, and an uncalled function supply three forms of dead code. |
| `58a1b3c3c386c6bd` | A read-controlled call performs repeated deletion, another deletion, and manifest creation. The goal requires both absence and exact file content. |
| `197444f718235848` | Nested functions bind a dynamic destination and transformed value before an entry-level branch invokes a publishing function. Source and alternate route use matching explicit logical keys while ordering write and emit differently. |
| `6101258f4cf540f5` | A function stages transformed data; a subsequent read controls cleanup and final publication. The catalog presents a more costly materialization route before a shorter route. Shared logical keys identify matching committed writes and deletion. |
| `fb9e12bed4601030` | Nested repetitions surround function calls and conditional emission. A supplied route decomposes four emissions differently. Exact multiplicity makes partial progress and duplicate effects consequential. |
| `226e614bc9ca4a96` | Two sequential functions stage and consume cached data. Possible worlds differ in initial cache contents and the cache-write grant; the alternative bypasses the cache while preserving the goal. |
| `aace5909ae504e85` | Two read-dependent guards occur across call boundaries. The alternate route reorders the reads and guards. One possible world cannot reach the output under any supplied route. |
| `aa7031812fb1dcb2` | An initializing function binds a loop-carried value, a repeated conditional function updates it, and a later branch emits and writes. The supplied alternatives have different ordinary effect costs; the route catalog is explicitly open. |

These are authored compositions within the specified DSL, not evidence of generalization to new operators or real Skills. Whether each is structurally absent from development should be checked after the production freeze; the author did not inspect development fixtures to engineer that result.

## Feasibility and fairness caveats

There are 28 possible worlds across the 24 cases. Every initial world has a false goal, as checked without execution. All 24 first worlds are designed to reach the goal through the original source with the supplied grants and the normal 16-call condition. The second world in each `aace5909ae504e85` case is intentionally infeasible relative to the closed supplied catalog: its entry condition prevents publication, and the alternative preserves that condition. This is an explicit eligibility/unknown scenario, not a successful refusal. The two cache-family second worlds alter both initial state and one grant; they test mixed-world reasoning, while the separate recovery factorial still removes grants independently as specified.

Two cases have open catalogs. Every case supplies at least one additional route, and four cases supply two. Catalog order is fixed before any execution result is available. The study must not alter it after observing recovery performance.

The construction includes natural opportunities for checkpoint and search to tie: pure accumulator work costs no external calls, equal-cost publication routes exist, and ordinary no-fault execution can already complete. Incremental replacement and materialization routes also provide cost differences. They do not guarantee a search advantage under every fault, budget, grant condition, or planner implementation. Tight quotas can make all strategies fail. Repeated emits require exact counts; previously emitted values cannot be undone, so a different route after partial progress can legitimately fail its goal. Receipt-compatible keys are included only where the corresponding effect signatures agree.

Repeated reads/writes, nested repeated calls, dead branches, zero repetitions, uncalled functions, exact emit multiplicity, absent-file goals, and explicit logical receipt keys are intentional tests of the published semantics. In particular, nested repeats require occurrence identities that distinguish different logical executions of the same site. No benchmark-specific repair or favorable relabeling is authorized by this document.

## Construction checks and sealed handoff

The builder checks exact case schema (therefore excluding answer fields), opaque and globally unique site IDs, supported AST/expressions, required and optional node fields, defined function names, acyclic calls including unreachable functions, conservative variable scope, repeat bounds, and a maximum structural execution bound of 100 steps. It checks all branch bodies, including inactive ones. It also verifies that both seeds in each family have identical program-and-route structural fingerprints and that the 12 family fingerprints are distinct.

The conservative bound observed during construction is 14 executed steps, including control and call nodes; there are 290 distinct static site IDs across original and alternative programs. The checks are construction assertions, not an independent execution oracle. Baseline feasibility descriptions above are authoring intent and directly inspectable structure, not authored labels or claims of interpreter agreement.

Rebuild with `python scripts/build_phase6_heldout.py`. The output is deterministic UTF-8 JSONL with LF newlines. The builder prints counts and its SHA-256 digest. The initial sealed output digest is `4dce7c3eecf9595833292ee691c5cac197f182c74bf6168072b11b375b9f19a6`. The parent should freeze production, truth, and protocol artifacts before opening the fixture, preserve the first evaluation unchanged, and separately identify any subsequent repair.

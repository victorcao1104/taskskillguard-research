# Phase 6 targeted challenge fixtures

This supplemental dataset was authored after the preserved first offline evaluation and the prospective amendment `docs/phase6_challenge_design.md`. It targets the coverage and route-selection mechanism described by that amendment. It is not an unbiased second holdout, a replacement for the main dataset, or evidence of the prevalence of these opportunities.

The author read the original DSL specification and the supplemental design. The supplemental design disclosed the coverage finding; no production code, reference interpreter, model outputs, or result files were read. The author changed only the new builder, fixture, and this document. No old fixture, prior result, API, credential, real Skill, or remote resource was used.

## Pairing and construction

`scripts/build_phase6_challenge.py` creates 12 cases from six structural families. Each family has a pair with identical literals, starting files, goals, program structure, and route catalog order. Exactly one optional-effect grant is present in one member and absent in the other. Opaque site IDs are renamed between members to remain unique across the complete supplement; this renaming has no semantic role. Case and family IDs are opaque as well. There are no descriptive variant fields or authored answer labels.

Every original places the optional effect before any task-essential effect. Pure bindings, branches, repetitions, and calls may precede it. Its resource or emission is irrelevant to the stated goal, and its return value is not consumed by the goal-producing computation. The original physically reaches the goal when effects execute normally without grant enforcement, by the construction of its literals and data flow. Alternatives avoid the optional resource and have grants for every effect in both variants. The goal is initially unmet in every case.

The optional operation varies across write, emit, delete, and read. One original repeats the optional emit twice; a denied grant stops at the first occurrence. Another optional read binds a deliberately unused value. This keeps optionality separate from whether an operation mutates state.

## Family taxonomy and catalog order

The call counts below are structural counts on the supplied ordinary paths, not measured interpreter or planner results. For each family they apply to both grant variants.

| Family | Composition | Original calls | Catalog calls in supplied order |
| --- | --- | ---: | --- |
| `e2f8da905fde0134` | A call branches on a pure-bound prefix and performs an optional dynamic write. The original then reads and normalizes input. Alternatives compare direct publication with staged read-after-write publication. | 3 | 2, 4 |
| `2a7986b26aa3785f` | A function repeats the optional emit before another function reads input. Alternatives compare direct doubled publication with a repeated staging write and later readback. | 4 | 5, 2 |
| `72202a736ef1e736` | A branch calls an optional deletion function; a separate repeated pure function builds an accumulator. Alternatives compare direct literal composition with staged input for another accumulator. | 2 | 1, 3 |
| `03bef0f7964549d0` | A repeated call makes an optional dynamic write, followed by a guarded dynamic publisher. Alternatives use paired read/write calls or staged publication with deletion. The goal also requires the staging path absent. | 3 | 5, 2 |
| `97bd2f14fced52a0` | A nested call/branch performs an optional emit before a triple accumulator. Alternatives compare pure repeated calls with staged data readback controlling publication. | 2 | 1, 3 |
| `b6df6b1d39cb1990` | A repetition and branch call an optional reader whose result is unused. Separate input data drive a publisher call. Alternatives compare guarded direct publication with a repeated staging call and readback branch. | 3 | 4, 2 |

Exactly three families put the cheaper route first and three put the more expensive route first. Fixture records are sorted by opaque case digest. Catalog order is fixed before supplemental execution and must not be rearranged after results are observed.

Under the specified charging rule, a denied first effect followed by the original retry consumes two calls. Quota 4 then leaves two calls: every cheap route fits its ordinary path and every expensive route exceeds the remainder. Quota 16 can accommodate either alternative after these two denials. This creates the intended finite selection problem without asserting a strategy outcome. Equal-planning strategies may tie on success while differing on calls when multiple routes are feasible. Fault timing, gating, receipts, and the separate mutating-grant-removal condition can change outcomes and must remain in their denominators.

## Safety of syntax and interventions

All expressions are string-valued. Every binding used by either branch is established conservatively before use; function calls are acyclic; repeat counts are within 0–3. No explicit receipt key appears anywhere, so explicit-key reuse conflicts cannot arise. Repeated effects use the specified per-occurrence default identity. All functions are reached in the constructed ordinary programs, and the checks traverse both sides of every conditional.

A site intervention returns an empty string for a suppressed read. Consumers use only string concatenation, uppercase, and equality, so suppression can change a goal result or a branch but cannot cause a type error or an undefined variable. The same conservative all-branches bound applies to these intervention paths. The maximum bound is 10 executed nodes, well below 100, across originals and alternatives. No planned original, alternative, or single-site reference intervention needs an omitted source-prompt rule about long routes or conflicting explicit keys.

The builder checks schema, grammar, variable scope, call cycles, bounds, unique opaque site IDs, paired identity after ID removal, one-grant pair differences, initially unmet goals, counterbalanced order, structural family uniqueness, and the intended route-call bounds. It also checks that every static effect in every alternative has a supplied grant in both members. These are construction assertions; the builder contains no interpreter, calls no production/reference implementation, and emits no truth labels.

## Sealed handoff

Outputs are `scripts/build_phase6_challenge.py`, `data/phase6/challenge.jsonl`, and this document. The fixture has 12 cases, 12 worlds, six paired families, 202 unique static site IDs, a maximum structural bound of 10 nodes, and a maximum ordinary effect bound of five calls. Source/reference AST equality is verified by decoding the source's sole fenced JSON block. The deterministic output uses UTF-8 and LF newlines.

Rebuild with `python scripts/build_phase6_challenge.py`. Initial fixture SHA-256: `5ead001c780b2f8422bb92a0b8a83b61448077ffaef74585f8e5cf7dc4a1e335`.

Freeze the supplemental fixture and equal-planning implementation before inspecting or executing the challenge. Derive all labels with the frozen reference interpreter, preserve the first supplemental results, and report targeted results separately from the unchanged original campaign. Any later repair must be separately named and must not overwrite this initial evidence.

# TaskSkillGuard: return to Skill security

User-approved direction, 17 October 2026: use Phase 5 final revision
`efd19d5e8704bdaec24fd183b81026d1d7fffccd`, strengthen it with Phase 6 executable
truth and equal-capability controls, retain all old versions, use synthetic
data only, and rewrite the IEEE report in clear English. Implementation is
additive on `7296da08bea968151dac7fab1b4c7edfc813ed27` so no later evidence is lost.
The user has already authorized design, implementation, experiments and private
publication together. Routine design choices do not require a new approval.

## Main questions

1. Can a source-grounded, task-conditioned check distinguish permitted Skill
   actions from excess actions, including actions that an unsafe implementation
   makes a prerequisite?
2. Which protection comes from task permission enforcement and which additionally
   requires data-flow restrictions? Does a malicious Skill statement grant authority?
3. After a Skill is blocked or a tool fails, can a legal alternative complete the
   task under the same permissions, state and quota? Does cost-based selection
   improve on a recovery controller with the same information and simulation ability?

Graph representation is a secondary ablation. Query optimisation, stopping
theorems and distributed commit protocols are outside the paper's main scope.

## Source-to-effect boundary

New synthetic packages contain actual `SKILL.md` text and Python-like script
files. One fenced shell command `python scripts/main.py` selects the entry file.
The adapter accepts only this invocation form, a relative traversal-free path,
and a deliberately small Python AST subset. No Python source is executed with
`exec`, `eval`, subprocess or a host filesystem tool. Unsupported syntax and
ambiguous entry points produce an explicit unsupported result, not a safe label.

Supported syntax: `from pathlib import Path`, `from mock_tools import emit`;
string/int/bool constants, variables, string `+`, `.upper()`; assignments;
`Path(expr).read_text()`, `.write_text(expr)`, `.unlink()`; `emit(destination,
value)`; `if left == right` with else; `for name in range(N)` for literal N 0..3;
zero-argument acyclic functions and calls. Loop indices cannot be read. Helpers
use hygienically renamed locals and require definite assignment before local
reads; reserved built-in/imported names and the internal `__tsg_` prefix cannot
be rebound. Methods have no extra arguments or
keywords. Return statements, dynamic imports, arbitrary calls, shell execution,
and other operators are unsupported. Logical resource paths are exact strings;
no real path, symlink or network semantics are claimed.

Each lowered effect has ID `file:line`, exact source location and file SHA-256.
Phase 5's unmodified extractor is measured separately on the same source; its
partial graph cannot establish execution order. A stricter new adapter lowers
the selected script into the unchanged Phase 6 language. A separate interpreter
evaluates the Python AST directly, without using production lowering, to check
effects, goals and action interventions. Phase 6 reference/runtime agreement is
also checked for the lowered finite programs.

## Security and recovery semantics

Trusted task input supplies exact operation/resource grants, optional per-resource
attempt limits (`world.limits`, keys `op|resource`), initial files,
outbound reader restrictions, desired outputs, preserved inputs and a finite
catalogue of trusted alternative scripts. Skill instructions and model outputs
cannot change any of these. Source provenance is propagated through variables,
concatenation, uppercase, file writes and branch control. Outbound emits require
both an operation/resource grant and permission from every contributing source.
This is a finite flow model, not arbitrary Python noninterference or complete
CaMeL reproduction. Initial readers are destination lists; absent restrictions
mean public, an empty list forbids outbound disclosure.

Controls: observe-only original execution; scope guard only; scope+flow guard;
scope+flow with first-feasible recovery; scope+flow with minimum-call recovery.
Both recovery selectors simulate all eligible alternatives from the identical
visible state, receipts, permissions and remaining quota. Both have four actual
attempts, the same trusted catalogue, and no future fault knowledge. The original
route is tried first. Safe known failures may retry; unknown committed outcomes
stop. Every dispatched call, including a denial, consumes the shared quota.
Known receipts prevent duplicate logical effects. No rollback, permission
expansion or quota reset is permitted. Simulation work is reported separately.

Primary outcomes: any unauthorized committed effect, forbidden outbound flow,
authorized goal completion (including input preservation), duplicate mutation,
actual calls, and simulated work. A post-hoc goal alone cannot erase an earlier
violation. Actions that never execute are not counted as confirmed safe actions.
Necessary-in-original and necessary-in-catalogue are separate executable tests;
open catalogues and unexecuted sites remain unknown/not-applicable as appropriate.

## Experiments and evidence policy

Use matched benign/adversarial synthetic packages, including legitimate outbound
communication and deletion, so blanket blocking cannot win. Include authority
spoofing, excess collection, unauthorized destinations, allowed destination with
forbidden payload, derived and file-mediated data flow, artificial prerequisites,
source tampering, repeated effects and benign-looking helper functions. Explicit
unsupported packages test the coverage boundary. These are constructed mechanism
families, not a random sample of Skill ecosystems or adaptive attack campaigns.

Freeze production and protocol before the independent evaluation author releases
new cases. Preserve first mismatches/failures and record repairs as amendments.
Use a separate small development set for implementation. Report source coverage,
model errors, enforcement and recovery separately. New model audits, if used,
read the complete synthetic package and trusted task and are replayed through
the same gateway. The model proposes action labels only, never new authority.
Source/table versus graph is secondary; raw invalid answers stay in denominators.
No real Skill package is read, transmitted or executed.

All new files stay in this study directory except the additive PHASE12 entry.
Paid acquisition may use the already authorized models and existing configuration,
with the complete Phase 11 ledger inherited. Cumulative cap $29.551575125;
starting upper exposure $22.652988125; remaining $6.898587. New campaign reservation
must be at most $3 and below the remaining cap. No automatic retries.

## Paper and publication

10--12 pages of IEEE body, one paragraph 150--200 word abstract, introduction
about 1--1.5 pages, updated literature review at most one page, clear methods and
results, conclusion/future work about one page, at least 10 verified references
within one IEEE page. Preserve confirmed authors and equal overall contributions.
Retain the prior review's Skill-security framing and accurate citations. Preserve
Phase 5 graph negatives and Phase 6 strong-control negatives explicitly; do not
merge their denominators with new data. Produce PDF and editable source package,
trace every numeric claim, inspect every final page, publish a new branch/tag and
GitHub release in the existing private repository. Do not replace the old paper.

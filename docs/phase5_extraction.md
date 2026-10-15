# Phase 5 bounded extraction extension

`extract_graph_v5(skill_id, files)` accepts only supplied text and returns the
v4 graph schema with an additional `coverage` object. It never reads paths named
by source examples, imports corpus modules, evaluates corpus expressions, runs
shell commands, accesses credentials, or makes network requests. Every node
retains `invocation_proven: false` and `authorization_source: false`.

## Evidence for choosing the extension

The input is the existing, bounded, approved set of 180 bundles in
`data/phase3/real_prepared.jsonl`. Its exact text hashes are checked against the
immutable v4 graphs. Existing omission/truncation coverage is retained in each
census observation. The census is descriptive and has no human accuracy labels.

The v4 graph ledger contains 3,041 `unmodeled_call` records and 873
`unsupported_command` records. Its most frequent unsupported shell heads are
`uvx` (139), `npx` (116), and `belt` (68). Those commands remain unsupported;
guessing the effects of arbitrary package runners or application CLIs would
require a much broader semantic model.

Counting call/command heads in closed, supported-language regions finds:

| Proposed head | Occurrences |
| --- | ---: |
| `os.makedirs` | 2 |
| `shutil.copyfile`, `shutil.copy`, `shutil.move`, `shutil.rmtree` | 0 each |
| `os.remove`, `os.unlink`, `os.rename`, `os.mkdir` | 0 each |
| `echo` | 21 |
| `printf` | 4 |
| `tee` | 2 |
| `wget` | 0 |

These syntax counts do not establish supported argument structure, identity,
effects or invocation. Eleven Python regions fail parsing and 57 shell regions
fail lexical analysis; they are not silently counted as zero-operation code.
Most `echo` occurrences have no file sink; the `printf` examples occur in
unsupported compound shell blocks, and the two `tee` examples use unresolved
variables. Only one `echo` example has a supported direct file redirect.

The final census adds **two candidates**, from **250 to 252**, in two bundles,
and removes zero candidates: one literal example-role write to
`.sfdx/last-validation.json`, and one source-code directory write whose target
remains unknown. One of the two `os.makedirs` sites lacks a proven imported
symbol identity and remains unsupported. The result is a small coverage proxy,
**not evidence of accuracy, execution, authorization, or broad real-world recall**.
The other new signatures are a bounded synthetic capability exercise, not a
prevalence-driven improvement claim.

## Exact supported extension

Python support requires a statically retained `os.name` or `shutil.name`
callable identity. Canonical calls, imported module/function aliases, and simple
assignment aliases use the inherited flow environment. Unknown alias identities,
wildcard imports, rebinding that loses a known identity, detected attribute
mutation, `setattr`/`delattr` mutation, and direct
namespace escape or dynamic evaluation through `globals`, `locals`, `exec`, or
`eval` cause abstention for the new signatures. This intentionally over-abstains
and is not whole-program alias analysis. Imported modules may themselves be
shadowed at runtime; the static import spelling is not a runtime identity proof.

| Signature | Candidate effects |
| --- | --- |
| `shutil.copyfile(source, destination)` | read source; write destination; source-to-destination DATA evidence |
| `shutil.copy(source, destination)` | read source; write unknown destination |
| `shutil.move(source, destination)` | delete source namespace; write unknown destination |
| `os.rename(source, destination)` | delete source namespace; write destination namespace |
| `shutil.rmtree(path)` | delete tree-root capability, without enumerating descendants |
| `os.remove(path)`, `os.unlink(path)` | delete path |
| `os.mkdir(path)`, `os.makedirs(path)` | directory write |
| `os.makedirs(path, exist_ok=True/False)` | directory write; only a literal Boolean is accepted |

No byte-read effect is invented for move/rename. `shutil.copy` and `shutil.move`
accept existing directory destinations, so a supplied destination string cannot
establish the resulting filename. These writes remain `resource: "unknown"`,
with `destination_may_be_directory` uncertainty and original argument evidence.
Literal/resolved paths denote supplied path expressions, not canonical filesystem
identities. Successful return values, symlink resolution, execution success,
interprocedural dataflow and arbitrary mutations remain unproved.

Exact `src`/`dst`, `path`, and `makedirs(name=...)` keyword roles are accepted,
including unambiguous mixed positional/keyword forms. Duplicate roles, duplicate
keywords, unknown keywords, extra positional arguments, starred arguments,
keyword unpacking, empty/reserved paths and statically invalid path types are
unsupported. Module, callable and open-handle identities cannot be reused as
path literals merely because the abstract interpreter records their names as
strings. Unresolved path values retain an operation candidate with an explicit
unknown resource, never a guessed pathname. Optional mode flags are outside the
bounded contract. Existing v4 keyword deletion effects remain supported.

Shell support reuses the immutable v4 lexer, constant expansion, existing
signatures and source mapping. Its new signatures are:

- `wget`: exactly one HTTP(S) URL; only `-O`, `--output-document`,
  `--output-document=...` and `--` are accepted. A GET candidate is emitted;
  only an explicit non-`-` output creates a write candidate and DATA edge.
  Without explicit output, the default filename stays in the uncertainty ledger.
- `tee`: literal/resolved output paths, optional `-a`/`--append`, and `--`.
  Each path yields a write; supported upstream stream evidence is retained.
- `echo`/`printf`: one terminal stdout `>` or `>>` followed by one
  literal/resolved target. `echo` flags and implementation-dependent escapes
  abstain. `printf` accepts only `%s`, `%%`, simple `\n`, `\r`, `\t`, `\\`
  escapes and an exact argument count.

Unknown expansion in any extension argument, unknown options, multiple or
descriptor redirections, heredocs, substitutions, compound control syntax,
shell functions and visible command rebinding remain unsupported. This is a
finite signature grammar, not a general shell parser or sound semantics proof.
Ordinary terminal output produces no file candidate. Shell stdout content from
the new `echo`/`printf` signatures is not modeled as an inferred value.

## Compatibility and provenance

The new Python interpreter subclasses `_PythonV4`; the shell dispatcher composes
the v4 helpers. Normalization and segmentation orchestration are copied into
the versioned adapter solely to select the new interpreter and dispatcher.
No shared globals are monkeypatched and no frozen file is changed.

Unchanged v4 evidence retains its original analysis kind and stable node IDs.
New effects carry `extension_version: 5`. Markdown code examples remain examples;
fence offsets apply to action, resource and uncertainty spans. Fresh environments
per snippet and existing ORDER, CONDITION and literal-reference CALL semantics
are retained. `coverage.unknown_reasons` aggregates the explicit uncertainty
ledger; `coverage.analysis_complete` is always false.

## Development verification and artifacts

The hand-authored targeted suite initially failed all 65 cases before the new
modules existed. It then passed. Four additional tests exposed dynamic namespace
identity leakage, failed before its conservative invalidation fix, and passed
afterward. The parent then approved proven aliases and exact argument keywords;
11 positive tests failed before that support and passed afterward, with 14
mutation/duplicate-keyword guard tests. Four further red-to-green tests prevent
module, callable and handle names from being treated as path literals. Four
superseded alias/keyword abstention cases were removed to reflect the approved
contract. The final targeted suite contains 94 passing tests.

The first complete workspace-temporary-directory run recorded 682 passes,
4 skips and 150 passed subtests, with one missing sibling documentation file
(`docs/phase5_truth.md`) while the truth agent was still writing it. A later
run passed 713 tests, 4 skips and 150 subtests. The final run against the frozen
extractor recorded **717 passes, 4 skips, 150 passed subtests and one failure**:
`test_reasoning_v5.py::test_project_data_through_unscored_bind_but_not_through_order`.
That sibling test was deliberately introduced during the parent's concurrent
red-to-green cycle. The parent reported its fix and 18 passing reasoning tests,
and reserved the final integrated suite for release. No extraction test failed
in that run. These concurrent integration observations are recorded rather than
being presented as a clean final repository-wide result. The initial default
temporary-directory attempt was interrupted after sandbox permission errors;
the completed runs use fresh temporary directories in the workspace.

Only the independently released **development** fixture file was inspected or
evaluated here. On its 16 fixtures / 24 effect sites, v4 matched 4 and frozen v5
matched 22. Both produced zero extra candidates and zero falsely resolved
resources. V5's descriptive precision is 22/22 and recall is 22/24; the small
development set does not establish general accuracy. The two remaining expected
effects are optional `mkdir` mode forms outside the bounded contract. The initial
stricter implementation matched only 9/24 and lost two inherited keyword effects;
that observation remains available. The approved alias/keyword extension restores
those sites and is evaluated separately, before any hidden fixture evaluation.
Validation, heldout and separate reasoning-gold evaluation belong to the parent
agent after implementation freeze.

- `results/phase5/extraction_development/independent_dev/`: preserved initial
  development-only observations and aggregate metrics (9/24 matched).
- `results/phase5/extraction_development/independent_dev_alias_keyword_final/`:
  intermediate alias/keyword snapshot (22/24), preceding path-type hardening.
- `results/phase5/extraction_development/independent_dev_frozen/`: authoritative
  development result for the frozen implementation (22/24).
- `results/phase5/extraction_development/census/`: preserved initial census
  before dynamic namespace hardening.
- `results/phase5/extraction_development/census_final/` and
  `census_alias_keyword_final/`: preserved intermediate census snapshots.
- `results/phase5/extraction_development/census_frozen/`: authoritative approved180
  census with input and frozen implementation hashes.
- `results/phase5/extraction_development/freeze.json`: implementation hashes and
  final verification record, produced only after the final suite completes.

Reproduce the census with:

```powershell
.venv/Scripts/python.exe scripts/census_phase5.py --out results/phase5/extraction_development/census_frozen
```

Outputs are create-only and accept an identical replay, but reject different
bytes at an existing path. Use a fresh output directory after any code change.
Run tests with a fresh workspace temporary directory to avoid the sandbox's
default temporary-folder permission issue:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_extraction_v5.py -q
.venv/Scripts/python.exe -m pytest -q --basetemp=work/p5extractfreeze
```

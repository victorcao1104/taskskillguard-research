# Build, verify and reproduce

## Manuscript evidence

Use a complete clone of the private repository, including its history. The paper audit uses Python's standard library and Git. From `papers/skill-recovery-v15`:

```text
python prepare_evidence.py --check
python check_table_values.py
```

The first command reaggregates saved records, verifies 62 input hashes, six paired bootstrap comparisons and 5,120 individual saved validation trials, reconciles the ledger, and checks that earlier studies and papers match the frozen commit. It does not call a model, execute candidate programs or rewrite study results. Omitting `--check` regenerates only this paper's two evidence JSON files.

The second command compares manuscript table cells with that derived evidence. Saved experiment replay and test counts are explicitly distinguished from these new manuscript checks.

## PDF

The standalone source uses IEEEtran, T1 font encoding, amsmath, amssymb, booktabs, array, algorithm, algpseudocode, TikZ, hyperref, url and cite. No external figure, table or bibliography file is needed by the compiler. `references.tex` is the audited bibliography companion; the same entries are embedded in `paper.tex`.

Create `output/pdf`, then run Tectonic 0.17.0 or a compatible standard LaTeX distribution:

```text
tectonic -X compile paper.tex --outdir output/pdf --keep-logs
```

The first build may download public TeX fonts/packages. With a complete local bundle cache, append `--only-cached`. Where needed, `TECTONIC_CACHE_DIR` can identify the existing cache. Do not include local credentials or machine-specific cache contents in the repository.

The built-in Codex standalone compiler can also check this source. It supplies diagnostics and an editor preview; the released PDF is the exported Tectonic build.

Install `pypdf` in the Python environment used for PDF checks, then run:

```text
python check_pdf.py
```

This checks 10–12 body pages, exactly one bibliography page, abstract length, cited reference keys, missing glyphs, overfull boxes and undefined references. The generated `qa/text_checks.json` records the delivered PDF hash. A different engine/font bundle can produce different PDF bytes; the source and experiment hashes are the scientific record.

## Visual inspection

Create `qa/pages`, then render with Poppler:

```text
pdftoppm -scale-to 1600 -png output/pdf/paper.pdf qa/pages/page
```

Inspect every page, including table notes, the two-line equation, the algorithm and the bibliography. Rendered review images and compiler auxiliary files are ignored build products. The PDF is tracked. See `qa/REVIEW.md` for the delivery review.

## Full experiment replay

Follow [the frozen study instructions](../../studies/recovery-mechanisms-v15/README.md). Python 3.12 and the study's `requirements-replay.txt` were used. A complete checkout is required because earlier preserved interpreter/provider utilities are imported. Saved responses allow replay without an API key or paid requests.

The study's `verify_replay.py` and `verify_strict.py` execute saved candidates; the manuscript's `prepare_evidence.py` only audits and reaggregates records. They are different checks. On deeply nested Windows paths, use the study's `windows_long_paths.py` launcher. Replay reports and regenerated analyses should be kept as new local output or in a separate checkout; do not overwrite the release's frozen evidence when conducting new experiments.

A collaborator's new data, prompts, provider calls or improved method form a new study. Preserve this version, declare the changed protocol and budget, and keep new results separate. No live acquisition is required to reproduce the saved scores.

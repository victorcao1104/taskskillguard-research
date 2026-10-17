# Build and inspect

The manuscript is a standalone IEEEtran LaTeX source. Figures, tables and references are embedded in paper.tex. No paid API or experimental data generation is needed to compile it.

## PDF build

Use Tectonic 0.17.0 or a standard LaTeX installation providing IEEEtran, fontenc, amsmath, amssymb, booktabs, array, algorithm, algpseudocode, TikZ, hyperref, url and cite.

From this directory, create output/pdf and run:

    tectonic -X compile paper.tex --outdir output/pdf --keep-logs

The first compilation may download the public TeX bundle. An existing cache can be used with:

    tectonic -X compile paper.tex --outdir output/pdf --keep-logs --only-cached

The delivered PDF was compiled with Tectonic 0.17.0 using the existing bundle cache. The Codex editor's standalone compiler also successfully compiled the source before a final numeric rounding correction in Table V; the exported deliverable is built and checked with Tectonic. The correction changes 7,769 to 7,770, rounding the machine-readable mean to the nearest integer.

Tectonic reported an encoding warning inside the bundled algorithm.sty and nonfatal underfull-box warnings. The manuscript has no undefined references, overfull boxes or replacement glyphs. These dependency warnings do not indicate a source compilation failure. See the saved QA report.

A byte-identical PDF is not required from a different TeX engine or font bundle. The source, experiment hashes and table values are the reproducible scientific record.

## Evidence checks

Python 3.12+ and Git:

    python prepare_evidence.py

Install pypdf in your chosen environment, then:

    python check_pdf.py

The paper check requires the compilation log next to the generated PDF. A fresh build creates it. The final saved QA report can be inspected without rebuilding.

## Visual review

Use Poppler:

    pdftoppm -scale-to 1600 -png output/pdf/paper.pdf qa/pages/page

Create qa/pages first. Inspect every page, including equations, long table headers and bibliography. Rendered review pages are local build products and are not needed to rebuild the paper.

## Experiment replay

Follow ../../studies/goal-recovery-v14/README.md in a full repository clone. Saved responses are sufficient for cached replay. Use a new output directory and preserve the existing results. Live model acquisition is a separate experiment, costs money, and may not reproduce provider outputs exactly.

## Private sharing

The paper tag and release preserve the complete experiment tree and prior history. Grant a collaborator repository access, then send the manuscript release link. Sharing the PDF alone gives them the text, not the ability to inspect private Git history or rerun the full study.

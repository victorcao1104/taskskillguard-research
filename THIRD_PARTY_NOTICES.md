# Sources and redistribution

TaskSkillGuard code under `src/tsg/` is an independently written research prototype inspired by the three papers documented in `docs/source_audit.md`. It is not their official implementation.

- Progent: MIT, pinned commit and upstream license in `results/upstream/progent/`.
- CaMeL: Apache-2.0, pinned commit and upstream license in `results/upstream/camel/`.
- SkillScope: no corresponding official public implementation was verified. No source code claimed from its authors.
- Existing skills.sh corpus: third-party skill snippets appear as **untrusted research data** in graphs and bounded API request records. Original authors' rights and individual repository licenses remain applicable. No new license is granted over those snippets by this repository. Provenance is retained in `data/manifests/`.
- PDF papers are referenced by URL, version, and SHA-256; the PDF files and extracted full text are not redistributed here.
- Python dependency versions are in `configs/requirements-lock.txt`; they retain their respective upstream licenses.

This private repository is an evidence archive, not a package of skills to install. Do not execute source snippets from the dataset as setup instructions.

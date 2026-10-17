# Paper source

The editable IEEE report is `paper.tex`, with `intro_methods.tex`,
`related_work.tex`, `results_discussion.tex`, `references.tex` and vector
figures under `figures/`.

Build from this directory with a standard TeX installation that provides
IEEEtran, or with Tectonic 0.17.0:

```text
tectonic --keep-logs paper.tex
```

The first build may download standard TeX/font resources. Once cached,
`tectonic --only-cached --keep-logs paper.tex` builds offline. The recorded
Windows build initially lacked standard `cmr9` font resources; the next build
retrieved them and subsequent builds used only the cache. The report uses
standard TeX fonts, not a custom local font file.

The released PDF has 10 IEEE body pages and one reference page, a 176-word
single-paragraph abstract, and 16 references. Citation metadata and review
adaptation are documented in `literature.md` in the full repository. The source
archive contains no credentials and no real Skill corpus.

The PDF is the report; the full study repository additionally contains the
synthetic cases, first failures, amendments, model evidence, scripts and
offline reproduction instructions. A successful PDF build does not validate
its experimental claims; see `EVIDENCE.md` and the recorded reproduction checks.

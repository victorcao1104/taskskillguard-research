# Build the paper

The report uses IEEEtran, standard TeX fonts and three vector figures generated from `analysis/summary.json`. Run `python studies/stateful-recovery-v13/figures.py` from the repository root to regenerate figures.

From this study directory, compile with a TeX distribution providing IEEEtran and the listed packages, or Tectonic 0.17.0:

```text
tectonic -X compile paper.tex --outdir output --keep-logs
```

The first build may require downloads of standard TeX resources. The recorded build required access to Tectonic's bundle cache; later builds succeeded with `--only-cached` in that same host context. No experimental data is sent to the TeX resource server.

The final PDF has 12 body pages plus one reference page, a 179-word single-paragraph abstract, and 15 references. `check_paper.py` requires the optional `pypdf` package and checks those structural properties, citation keys, and overflow warnings. Scientific figure labels and tables were inspected in rendered pages. The algorithm package emits an encoding warning from its own source; the output has no replacement characters. The host also prints a fontconfig configuration warning, but compilation succeeds with standard TeX fonts. Neither warning is silently presented as a clean build log.

The source archive contains the `.tex` files, vector figures and this guide. It is a paper source archive, not the complete experiment. Clone the repository branch/tag for raw model records, generated Skill cases, all failures and zero-API reproduction. A successful PDF build does not validate the experimental claims.

# Final IEEE report

**When Is Evidence Enough? Checkable Contracts for Bounded Agent Workflows**

Authors: Victor Cao and Enlin Li, University of Auckland. Equal overall contributions (50% each), as confirmed by the project owner. The earlier literature-review responsibilities are taken from the supplied review; no new individual experimental roles are invented.

## Read or edit

- [PDF report](output/paper.pdf)
- [Editable LaTeX](paper.tex) and [IEEE references](references.tex)
- [Portable LaTeX source package](output/ieee-source.zip) for Overleaf or a local editor
- [Reference audit and adaptation notes](literature-audit.md)
- [Claim-to-evidence map](claim-evidence.md)
- [Report checks](verification/report_checks.json)
- [Figure input rows and hashes](verification/figure_inputs.json)

The report follows the supplied rubric: IEEE two-column format, 12 body pages, a single 182-word abstract (whitespace count), about 1–1.5 pages of introduction, no more than one page of related work, substantial methodology and results, about one page of conclusion/future work, and one page of IEEE references. The final measured counts are in `verification/report_checks.json`. The bibliography contains 20 sources: 14 peer-reviewed publications and six labelled preprints.

## 中文说明

正文使用较简单的学术英语：每段先讲重点，再提供依据和解释。世界、路线、证书、确认完成、物理目标等必要术语均在正文中定义。

文献综述沿用原稿的“威胁与上下文 → 安全和可用性评价 → 外部执行控制”脉络。原稿提出的任务到权限策略生成，并不是最新实验已经完成的内容。论文明确把研究范围收窄到有限合成环境中的证据采集、证书检查、停止和恢复。相关文献也已具备部分策略生成能力，因此删除了过宽的研究空白表述。

实验数字均取自冻结的 Phase 11 结果。正文明确保留模型未超过强启发式、图未稳定超过 padding、unknown 的两类原因，以及确认完成与实际新增进展的区别。没有补造实验、人工标注或真实 Skill 结果，也没有新增实验 API 开销。

## Research versions and preservation

- Original Phase 11 research release: `088af27ebdbd1e12037d17fcffd80c4abb9926b4`.
- Append-only CI portability amendment / report input commit: `b994ef8b6bd3b9e29250d8fd557d05f6082ac2a6`.
- Earlier archive: `archive-phase10-20261017`, commit `caf5ee5430e011044c478ec8fed7013545978922`.
- Pre-paper archive: `archive-before-final-paper-20261017`, pointing to the input checkout above.
- Private repository: https://github.com/victorcao1104/taskskillguard-research

This directory is separate from the frozen `paper/phase11` release. Nothing in the old research release is edited. The report checker reads and verifies all 8,115 Phase 11 release hashes and all 37,907 earlier baseline hashes. A new report is not a new experiment.

## Rebuild this paper

Use Python 3.12 and the repository's locked figure dependencies. Install the additional paper dependency from `paper/final-report/requirements.txt` if PDF checks are needed. From the repository root:

```text
python paper/final-report/build_figures.py
```

Install Tectonic 0.17.0 from its official release or use a complete LaTeX distribution with IEEEtran. From this directory:

```text
tectonic paper.tex --outdir output --keep-logs --keep-intermediates
```

The original build used the standard Tectonic bundle v33 and the genuine IEEEtran conference class, with a 10-point, two-column body. Package download is needed on the first build. After the cache is present, `--only-cached` avoids package downloads. This is a multi-file LaTeX project: include `references.tex` and `figures/*.pdf` when copying it to another editor or Overleaf. Compiling sends no manuscript content to a model service.

Run the paper checks from the repository root:

```text
python paper/final-report/verify_report.py
```

The checker validates selected published numbers against the frozen tables, citation coverage/order, abstract length, PDF page bounds, missing glyphs/references, and preservation of old evidence. It writes only this directory's verification result. It does not call model APIs or rerun the research experiment. Publication-quality layout also requires visual review; the final review record is in `verification/editorial_review.md`.

PDF rendering and fonts can differ across TeX environments. The released PDF is the authoritative reviewed layout; the scripts reproduce numerical figure inputs. Do not confuse byte identity of a PDF with reproducibility of an experiment.

## Reproduce the research

Follow [the frozen Phase 11 reproduction guide](../../docs/phase11_reproduction.md). It separates offline evidence replay, new restricted-container execution, and fresh model acquisition. Offline replay uses retained responses and does not spend API budget. A fresh container run needs the pinned image already available; this repository retains its identifier and batch records, not an image archive. A fresh hosted-model run is stochastic and is not part of rebuilding the paper.

The report cannot promise a grade, acceptance, or general protection for real Skills. It supports a bounded, reproducible mechanism study with disclosed assumptions and negative findings. Reviewers need access to the private artifact; no public release or external preregistration is claimed.

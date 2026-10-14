# 论文与源码核验入口

三篇用户 PDF 均全文阅读，包含附录，并对关键公式、表格和源码分别核对。详细证据、页码、路径、版本差异和未复现项见下列审计：

| 论文 | 本次实际版本 | 官方源码结论 | 本地核验 |
|---|---|---|---|
| [SkillScope](https://arxiv.org/abs/2605.05868v3) | v3，2026-09-10，21 页 | 在作者主页、arXiv 和对应作者 GitHub 的有限检索中未找到可验证官方实现 | [全文与代码检索审计](literature/skillscope.md) |
| [Progent](https://arxiv.org/abs/2504.11703v3) | 用户 v3，17 页 | [sunblaze-ucb/progent](https://github.com/sunblaze-ucb/progent)，MIT；commit `5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565` | [策略、SMT、适配器与探针](literature/progent.md) |
| [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813) | 用户文件为 SaTML 2026 发表版本，32 页，与手册写的 arXiv v2 不同 | [google-research/camel-prompt-injection](https://github.com/google-research/camel-prompt-injection)，Apache-2.0；commit `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` | [解释器、P/Q、标签与测试审计](literature/camel.md) |

上游具体复现步骤与原始探针结果见 [upstream_reproduction.md](literature/upstream_reproduction.md)。本地实现不导入上游生产代码；上游 clone 的最小测试与 TaskSkillGuard 合成实验分开记账。

## 本项目文件级来源

| 本地文件 | 关系与范围 |
|---|---|
| `src/tsg/graph.py` | 独立重写，SkillScope 启发的说明/Python AST 候选图；非完整跨过程 CFG |
| `src/tsg/sandbox.py` | 独立重写，SkillScope 启发的中和重放、有限 reference；无任意脚本执行 |
| `src/tsg/policy.py` | 独立重写，Progent 启发的精确规则与 Z3 比较，CaMeL 启发的 sources/readers |
| `src/tsg/prompts.py` | 本项目自行编写提示；未冒充论文缺失的原始提示 |
| `src/tsg/models.py` | 本项目 API、缓存、预算记录；不是论文执行器 |
| `src/tsg/benchmark.py` | 本项目合成 fixture 与规格标签，不是原论文 benchmark |
| `src/tsg/corpus.py` | 用户既有下载库只读适配；保留来源 ID、路径与哈希 |
| `results/upstream/` | 上游测试的观测输出、研究探针和许可证；不声称完整 benchmark 复现 |

公开 URL 用于复查论文与上游归属。本仓库不重新分发三篇 PDF，也不重新抓取整个 skill 语料库。

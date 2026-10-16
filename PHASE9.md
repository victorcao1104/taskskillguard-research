# Phase 9 — 可信观测、查询预算与合法恢复

本轮落实并检验 Phase 8 提出的四个优先级，仅使用合成任务。阅读 [完整分析](docs/phase9_report.md)，或先查看 [实验方案](docs/phase9_design.md) 与 [预设分析口径](docs/phase9_analysis_plan.md)。

| 优先级 | 实现与证据 |
|---|---|
| 审计到执行接口 | 条件授权、受限可信观测、保留全局 unknown、回执语义预检；[实现说明](docs/phase9_recovery.md) |
| 固定类型汇总与等预算查询 | 同一响应的模型标签/程序汇总，模型/启发式/随机查询顺序，图表示对照；[协议](docs/phase9_protocol.md) |
| 多目标恢复 | 相同规划预算的调用优先/重试优先/风险优先策略，缓存对照与新故障时序；[执行证据](results/phase9/recovery/summary.json) |
| 拆分消融与新结构 | 去重 × 工具事实 × 汇总器，门控 × 预检，12 个新结构家族；[独立参考](docs/phase9_reference.md) |

规模：24 个新任务、46 个新世界、144 个新候选点；另保留72个旧任务作为执行回归。336次模型请求均返回，302次满足协议；9,800个执行条件完成26个隔离容器重放。无自动补答、无结果择优。费用上界增量 $0.391094500，累计 $17.383292550，剩余 $12.168282575。

**结果不是全面支配：** 可信观测能改善特定家族的完成率；预检仍会因目标相关信息不足而损失可用性；图和模型查询需要面对同预算启发式的对照；较低风险分数不保证在改变后的故障时序中更成功。完整效应、负面结果和区间见报告。

存档点：[archive-phase8-20261016](https://github.com/victorcao1104/taskskillguard-research/tree/archive-phase8-20261016)，对应提交 `93eda0d23236912671c7b309eb78e7c80fd20db1`。可从该标签创建单独分支/检出比较。全部旧文件的校验值保留在 [baseline.json](results/phase9/provenance/baseline.json)。

- [复现方式](docs/phase9_reproduction.md)
- [冻结前独立审查](docs/phase9_prefreeze_review.md)
- [结果独立审查](docs/phase9_outcome_review.md)
- [结构化分析](results/phase9/analysis/summary.json)
- [最终完整性验证](results/phase9/provenance/release_verification.json)

本研究覆盖有限 DSL、声明的世界集合和可信本地工具。它不提供真实 Skill 的安全结论，也不需要人工标注。旧真实样本实验作为历史材料保留，本轮没有新增此类实验。

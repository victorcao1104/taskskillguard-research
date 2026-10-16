# Phase 8 — 纯合成改进轮

本轮将事实预测与标签汇总分离，并在合法恢复中比较重试优先与最少调用。新增 48 个结构覆盖样本，保留 24 个旧样本回归；完成 480 个模型请求和 14,640 个执行条件。

主要发现：必要性标签改善，完整事实仍不可靠；节省调用伴随更多规划；更准确的跨世界 unknown 不一定改善当前世界的执行成功。

- [中文报告与修复前后对比](docs/phase8_report.md)
- [实验方案](docs/phase8_design.md) · [分析计划](docs/phase8_analysis_plan.md)
- [完整统计](results/phase8/analysis/summary.json) · [门控原因诊断](results/phase8/diagnostics_v2/summary.json)
- [复现与数据索引](docs/phase8_reproduction.md)
- [结果独立审查](docs/phase8_outcome_review.md)
- [最终验证](results/phase8/provenance/release_verification.json)

本轮 API 保守费用增量 $0.325077400；累计上界 $16.992198050，剩余 $12.559377075。全部旧结果保留。仅使用合成样本；无真实 Skill 实验、无人工标注。

前轮入口：[Phase 7](PHASE7.md)。

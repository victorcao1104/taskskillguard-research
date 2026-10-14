# TaskSkillGuard Research

依据用户研究手册，结合 SkillScope、Progent、CaMeL 的研究原型与实际实验。两轮自动化工作完成，原始预测、真实容器轨迹、失败、不确定结果、统计与费用均保留。**真人双标注由用户后续安排，不能将当前结果称为完整人工验证。**

入口：[中文最终报告](docs/final_report.md) · [逐项验收矩阵](docs/phase2_requirements_matrix.md) · [复现指南](docs/reproduction_phase2.md) · [人工接续说明](docs/phase2_annotation.md)。

## 实际完成的工作

| 轨道 | 保存的证据 |
|---|---|
| 三篇论文 | 全文/附录阅读；Progent、CaMeL 官方代码固定 commit 与最小实测；SkillScope 官方实现未核实，明确标为 paper-inspired |
| 真实来源 | skills.sh completed 中抽取 180 包、123 家族；3,414 文件前后哈希一致；保留原始 ID、来源、路径和 split |
| 全样本模型检测 | GPT-6 Luna / GPT-4.1 mini；360 条 Q 提取、2,160 条 V0/V1 三任务分类；未知与失败单列 |
| P/Q 与合同执行 | 1,644 条新规划记录（1,188 个不同请求 hash）；3,168 条 E3 闭环；九配置各 528 条运行 |
| 真正 OS 执行 | 240 次正式工具适配器容器执行；另有 31 份原始来源脚本检查，其中四个功能任务成功、27 个接口探针、九个运行错误 |
| Replay / 机制 | 三类动作九次类型保持回放、六条双模型 Judge；33 合同探针、10 信息流探针、96 次期限/额度控制；1,188 条固定动作机制运行 |
| 统计与交付 | family bootstrap、配对比较、联合 Holm、实际 CPU/RAM、PNG/PDF 图表、五个以上可复核错误案例；两份独立盲审包 |
| 累计费用 | usage 估计 USD5.8498859；含六笔历史未结算预留的保守上界 **USD5.8589654 / 20**，不是平台账单 |

## 结果怎么解读

- 正确合同的 OS 守卫组达成目标 **24/24**，越权 **0/16** 个攻击机会；未守卫组越权 **16/16**。这是六类可信工具 fixture 的结果，不是任意第三方脚本的安全证明。
- 模型闭环暴露了明显可用性问题。Luna 的 held-out 完整配置完成 **50/69** 个已决定任务，另有 **19** 个不确定；mini 同条件 **88/88** 个不确定，不能填成“零攻击、全安全”。去掉共享守卫后 Luna 完成54/69，但两组均无观测越权，因此此对比不能证明守卫带来安全增益。
- 新静态图已知资源比例由 **6.64% → 7.32%**，加入1,609条 DATA 边，仍有大量未解析结构。该指标不是语义准确率。
- 三类可比回放中，两例支持动作不必要，一例保持 unknown。Judge 与这三对确定性输出检查一致，不构成人工 GT。
- 家族样本量小、重复嵌套；联合多重比较校正后没有显著优势证据。模型或机制没有改善的结果均保留。

![OS安全与任务完成](results/phase2/figures/os_security_utility.png)

## 目录

| 路径 | 内容 |
|---|---|
| [docs/literature](docs/literature/) | 三论文阅读、公式、页码、官方来源、版本及许可 |
| [docs/source_audit.md](docs/source_audit.md) | 方法归属与上游代码可验证边界 |
| [data/manifests](data/manifests/) | completed 抽样、来源、原始路径、内容哈希与家族切分 |
| [data/annotation_v2](data/annotation_v2/) | 双人独立盲审包、协调者映射、三层标签、导入与仲裁 |
| [src/tsg](src/tsg/) / [containers](containers/) | 图、合同、SMT、双账本、P/Q、VM、真实 OS 隔离 |
| [results/api](results/api/) | 内容寻址请求/响应、usage、单写入者累计预算 |
| [results/phase2](results/phase2/) | 全部新实验、容器输出/syscall、汇总、图、失败与验证 |
| [results/upstream](results/upstream/) | Progent/CaMeL 最小实测原始日志及许可证 |

## 快速离线核验

安装 Python 3.12 与 `configs/requirements-lock.txt` 后：

```text
python -m pytest -q --basetemp work/check
python scripts/verify_release.py
python scripts/verify_phase2_release.py
```

统计不需要密钥；新的 Docker 复跑可复用已保存合同，详见复现指南。发布证据与新工作目录分离，禁止覆盖原数据、清空预算或在宿主执行 Skill 指令。

原始整库、密钥、虚拟环境和 PDF 全文不上传。有限第三方片段只作待分析数据；许可证与归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。第一轮原始结论保留于 [study_v1_report.md](docs/study_v1_report.md) 和 tag `study-v1`，新结果不改写旧观察。

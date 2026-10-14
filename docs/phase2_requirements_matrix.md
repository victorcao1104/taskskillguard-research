# 第二轮手册要求与证据矩阵

本表是自动化验收的可复核清单，依据手册 §12–18。人工双标注及仲裁已由用户明确延期，交付为可导入、可仲裁、可重算的一对独立人工包；未收到真人结果前，不计算真实语料检测准确率或伪称人工 GT。手册的 180 Skills/720 场景是建议规模，不将有限动态支持外推到全部样本。WP-01 要求官方来源核验、安装尝试和最小实测，不要求把三个上游完整论文基准都跑完。

最终自动化网格已完整落盘并通过逐键/回链检查，统计状态为 `complete_saved_counts`，没有缺失网格项。**已执行**不表示每次结果成功；unknown、协议失败和源脚本不兼容都保留。**人工待提供**是用户指定后续步骤。第一轮 `docs/requirements_matrix.md` 保留为历史，第二轮不改写旧实验。

| 工作包 | 第二轮状态与证据 | 适用边界/最终核验 |
|---|---|---|
| WP-01 环境与来源 | 已执行。`docs/source_audit.md`、`docs/literature/`、`results/upstream/` 保留来源、commit、license、最小复现；新增 `results/phase2/os/image_dependency_inventory.json`、runtime diagnostics。 | SkillScope 仍按核实结果标记 paper-inspired；Progent/CaMeL 不冒充完整 benchmark。依赖版本锁与 image digest 均说明可复建边界。 |
| WP-02 只读 corpus 与 split | 已执行。180 条现有 manifest/family split 未重采集；原始 3,414 文件不可变记录保留；新增 OS 执行过的 31 bundle/529 文件哈希变化 0。 | 分组证据为既有 repo/publisher/selected exact hashes；不是全库近似重复完备证明。 |
| WP-03 任务、fixture、GT | 自动化部分已执行/已生成。132 合成例；`data/tasks/phase2_real_task_triples.jsonl` 三任务；六类真实 OS fixture；四个 source 功能任务；双人盲审包在 `data/annotation_v2/`。 | 540 真实三任务是研究者设定的上下文，不等于 540 真实动态成功。人工标签、κ 与仲裁结果待真人提供。 |
| WP-04 V0 baseline | 已执行。第二轮全 180 包，360 条 Q 提取、2,160 条 V0/V1 三任务记录，共 2,520 条；保留原始请求响应。 | JSON 解析通过≠正确；unknown/格式失败保留。真实 F1 待人工 GT。 |
| WP-05 Graph/Task Ceiling | v2 常量路径、作用域、分支合流、DATA/CALL/RETURN 与 unresolved 的有界提取已实现；`src/tsg/graph_v2.py`、`scripts/build_graphs_v2.py`、`results/phase2/graphs_v2/`。可信 P 仅见任务，Q 证据无授权权。 | coverage、已知资源比例是结构指标，不是语义准确率。所有截断、遗漏及非 Python lexical-only 单列。 |
| WP-06 Clean Replay/Necessity | 已执行真实 OS 原始/中和/独立参考；六 fixture 18 次初始记录，另有类型保持的 write/read/send 三动作九次运行与六条双模型 Judge。原始 source 31 个，四个明确任务成功，其中一个冻结 held-out 首次成功。 | 27 个接口探针不算任务成功；九个 source runtime_error 保留。无效 HTTP-low 对照剔除；CSV read 中和丢失目标且 reference 仍读→necessity unknown。Judge 不是人工 GT。 |
| WP-07 DSL/Schema/SMT/Guard | 已执行 33/33 合同探针：5 UNSAT、8 SAT、3 UNSUPPORTED；SAT witness 回放、双账本、无授权扩权拒绝。`contracts_v2.py` 与 `results/phase2/contracts/`。真实 OS 精确 scope guard 另有实际输出拒绝测试。 | 受限 DSL，不是一般 Schema→SMT。OS 有限 guard 与 VM 的完整 DSL 是不同适配层；任意源脚本仅 OS containment。 |
| WP-08 P/Q 与数据流 | 已执行：1,644 条 P 记录对应 1,188 个不同请求 hash；工具不可用的 Q、可信任务 P、无授权证据通道；10 个 flow 探针，未授权流 3→0，公开/授权 token 两个合法发送保留。 | Q 建议复用第一轮冻结输出；P 参考是有限动作目录。数据流是 VM 机制，原始任意脚本没有通用 taint。OS HTTP high 另实测 fake token authentication。 |
| WP-09 I1–I4 与消融 | 已执行：九配置各 528 条，共 4,752 条闭环；另有 1,188 条固定动作机制控制、96 条 lifecycle；有限结构等价 E8 模型比较。 | `no_smt` 只关闭 transition subset check；`no_guard` 移除共享 scope/taint/lease 执行点。许多去组件没有可测提升；mini 的大量 unknown 单列，不作安全通过。 |
| WP-10 冻结、统计、报告 | 已执行统计：第一轮 208、VM 696、OS 78 个配对对照，2,000 次 family bootstrap、联合 Holm；真实资源、错误案例、图表和最终报告均保存。held-out source 冻结 commit ed42057。 | 测试/发布核验见 `results/phase2/tests_final.xml` 和 `results/verification/`；六模板家族限制推断，报告不声称有显著泛化优势。人工待提供。 |

| 实验 | 可核验实现与已存在证据 | 计分限制或待主运行确认 |
|---|---|---|
| E0 工具链 | `os/compatibility_report.csv` 全 180、`unsupported_reasons.csv`、`smoke_test.json`、真实 PDF/CSV/Git/HTTP/SMTP/SQLite、root/source RO/外网拒绝/审计不可写、31 source 原文件不变。 | 已有文件、代码及网络合法路径；安全拒绝来自实际 errno/守卫事件。外网关闭属于 containment，不能当作语义权限模型分数。 |
| E1 V0/V1 | 第一轮两模型固定合成预测；第二轮 180 真实 Q/V0/V1 三任务共 2,520 记录；`graphs_v2/summary.json` 是另外的静态结构轨道。 | Action/Skill F1、定位准确率待人工标签；graph_v2 没有回填原模型输入。 |
| E2 Replay | OS fixture 与 typed replay；VM 396 组旧记录；source 功能 oracle；独立原始/中和/参考 traces。 | 同时报告 replay_valid 与 GoalSat/necessity；original_failed、invalid_ablation、runtime_error、not_triggered、unknown 不并入 TN。 |
| E3 Enforcement | 已执行 240 次真实 OS exact scope（oracle/两个模型、混合/分离、guard off/on、两次重复）及 3,168 条 VM 合同执行。 | 固定 c2 image，准确外层任务判定与 raw 同存。29 个旧合同槽位的 declared-unknown 对应116运行，只保留观察，不计入决定性安全率；OS unknown 同样单列。 |
| E4 Flow | `results/phase2/flow/e4_flow_probes.jsonl` 显式秘密/派生/公开/opaque/授权 token，taint off/on；OS 认证 HTTP 与合法 SMTP。 | opaque 来源明确标记不跟踪；有限 VM flow 不等于任意 OS 程序追踪。 |
| E5 授权污染 | 全部三任务、混合/分离模型合同及执行已落盘；DualLedger 独立批准、受限 evidence scope、不可复用 approval、扩权拒绝探针。 | 调用者身份来自受信嵌入 API，非真人认证 UI；审批次数是机制事件，非真实用户负担。 |
| E6 三角必要性 | 独立 reference、reference-exclusion gate、P 参考计划与任务 oracle；文件读 reference 包含候选时不推不必要。 | “参考含有动作”不能证明全局必要；类型保持替身也只证明该预设干预的结果。 |
| E7 收缩/租约 | `results/phase2/lifecycle/` 96 次已记录：expiry/quota 独立，static/shrink/lease/shrink+lease 同任务；33 合同探针含阶段/时钟/额度边界。 | 不再把次数耗尽叫时间到期；两种限制的贡献分别报告。 |
| E8 元变形 | 已执行有限 task spec round-trip；JSON/fields/indented JSON 与保持动作顺序的注释版；V0/V1/V5 保存请求及 `pipeline_analysis/metamorphic.csv`。 | 有限结构等价自动验证，不声称任意自然语言同义改写已获人工确认。unknown 不强行计为一致。 |
| E9 消融/迁移/成本 | 九配置、两模型、两次重复全部完成；family 统计/Holm、容器 CPU/RAM、完整 API usage 与账本。累计保守费用上界 USD5.8589654/20。 | CI 不足返回 null；模板重复不扩大独立 n；无 API 服务端资源指标不编造。费用不是平台账单。 |

最终自动化交付须从原始结果重算，明确标出人工待提供，保留失败、unknown、unsupported、开发修订和已冻结轨道。既不能把组件实现当成实验执行，也不能把手册允许的工程适配误写成必须逐行复现三个上游全基准。

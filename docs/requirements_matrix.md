# 手册要求与实际证据矩阵

对照来源：用户的 `TaskSkillGuard_Research_Experiment_Manual_ZH.md`，§15 的 E0–E9、§18 的 WP-01–10，连同 §12–13、§16–17 的数据、隔离和统计要求。此表记录完成程度，不把实现了一个组件等同于完成整项实验。

核心实现冻结提交：`195620a2d11fbb4b833254d8a5f5b19102b417e3`。补充评估、统计和交付文档可晚于核心冻结；各次运行以 `results/run_manifests/` 中的代码/配置哈希和提交为准。最终核验：2026-10-15（新西兰）。held_out、transfer、judge及提示消融均已结束；本表以下按最终落盘记录更新。冻结后边界修补的零差异回归见 results/verification/runtime_stability.json。

状态含义：**已执行**指有对应代码和实际输出；**有限替代**指做了可复核的缩小实验，但未满足原要求的全部范围；**未完成**指缺少要求的执行或证据；**运行中**仅表示已启动，不能据此给出结论。

## 工作包逐项核对

| 工作包 | 状态 | 现有实现和证据 | 尚缺少或限定的范围 |
|---|---|---|---|
| WP-01 环境与来源校验 | 已执行；上游复现为有限范围 | `docs/source_audit.md`、`docs/literature/{skillscope,progent,camel}.md`；上游 commit、许可证、探针、锁定环境和原始输出在 `results/upstream/`；本项目依赖在 `configs/requirements-lock.txt` | SkillScope 官方代码在已记录的有限检索中未核实；Progent/CaMeL 只运行最小机制测试，未跑完整 benchmark。用户 CaMeL PDF 实为 SaTML 2026 版本，已记录与手册 arXiv v2 的区别。依赖锁不是手册所建议的同名 `dependency_lock.md`。 |
| WP-02 现有库只读接入 | 已执行，分组覆盖有限 | `src/tsg/corpus.py` 的只读 SQLite、抽样、分组；`data/manifests/skills_manifest.jsonl` 和 `corpus_report.json` 保留来源 ID、去重记录、脚本、语言、哈希与 split。实读 9,547 个 completed，4 个缺 SKILL.md，候选 9,543；抽样 180、含脚本 90、pilot 30。`immutability_after.json`：180 包、3,414 文件、变化 0 | 实际 split 为 development 99 / validation 46 / held_out_test 35，123 家族（67/31/25），不是手册示例的 100/40/40。家族仅覆盖选中样本的发布者、仓库与完全相同文本连接，未证明全库近似重复无泄漏。split 嵌入 manifest，未另造同名 CSV/JSONL。 |
| WP-03 Benchmark 与 GT | 有限替代；人工 GT 未完成 | `src/tsg/benchmark.py`、`data/benchmark/synthetic_cases.jsonl`：132 个合成案例、6 模板、2 数值 fixture、11 场景、396 条动作规格标签；所有动态例有明确输入、预期字符串输出、固定 task policy 和 mock 副作用。真实样本的三种假设任务由 `scripts/run_supplement.py::task_triples` 生成 | 132 合成案例不是 180 个真实 Skill 的可执行重放。所有 `human_annotated=false`；未完成双人标注、仲裁或一致性。真实 high/low/edge 权限上下文是研究者合成假设，不是实际用户授权或人工 GT。标注包的空列不算完成标注。 |
| WP-04 V0 Direct LLM | 已执行合成开发/验证/测试 | `prompts.DETECTION`、`models.parse_prediction`、`run_experiment.py::detection`；两模型、结构化动作覆盖校验、原始响应哈希及失败状态保留。`results/{pilot,development,validation,held_out}/detection.jsonl` | pilot 提示修订前结果不进入正式指标。真实语料缺人工 GT，不能给真实检测准确率。模型别名不等于永久不可变的服务端模型版本；seed 未发送 API。 |
| WP-05 V1 Graph 与 Task Ceiling | 有限替代，已执行 | `graph.extract_graph/validate_model_graph`；180 个真实静态图在 `data/graphs/`，说明行/Python AST、显式 CALL/RETURN、来源 span 和 unresolved；`policy.py` 精确 action/resource；60 个模型图审计响应在 `results/real/real.jsonl` | 真实图是有界、不完整静态图；source-order 边不是可达性证明。合成 V1 图由生成器编写，不测自动抽取精度。真实模型图 59 valid、1 unresolved；valid 只指结构/定位校验，不能称语义正确率。 |
| WP-06 V2 Replay 与 Necessity | 有限替代，已执行 | `sandbox.run_case/replay_case/reference_run`；每次空内存状态，原始/单点中和/可信参考三份独立轨迹；`results/mechanistic/replays.jsonl` 396 组，384 comparable、12 dependency_blocked；`run_supplement.py::judge` 不给 Judge oracle 判定布尔值 | 没有 OS 容器或第三方脚本重放。document/git/database/email 是字符串变换，未生成真正 PDF、Git 仓库、SQLite 或 SMTP 服务。有限 VM 的状态不是任意脚本 `invalid_ablation/runtime_error` 覆盖证明；未触发这些失败不表示不存在。Judge已完成72条响应，含实际误判与null；见补充统计。 |
| WP-07 V3 Compiler/Guard | 有限替代，已执行 | `policy.Rule/Policy/compare_policies/Ledger/Guard`：精确资源、默认拒绝、Z3 独立 context、SAT witness、UNSAT/UNKNOWN 分开、可信扩权来源；396 条 update 记录与工具事件在 `results/mechanistic/`；`tests/test_policy.py` | schema 由手写类型/字段/枚举校验执行，虽然安装了 jsonschema，运行代码未调用该库。不是一般 JSON Schema→SMT 编译器。审批是受信调用参数及账本模拟，没有人机审批界面或身份系统。运行实验固定 oracle policy；生成合同未接入完整执行闭环。 |
| WP-08 V4 P/Q 与数据流 | 有限替代，已执行 | `Client` 的请求不提供工具；`EXTRACT` 读取不可信材料；分离合同输入只含可信任务。`LabeledValue/combine/Guard` 保留显式 sources/readers，检查 mock 网络和本地写入；`tests/test_models.py`、`tests/test_sandbox.py` 与 V3/V4 同动作轨迹 | 这是 P/Q 职责的组件隔离，非完整 CaMeL 受限解释器或多轮自主代理。检测器本身会读取不可信文本，不能宣称所有 P 路径完全不接触原文。未覆盖隐式控制流、异常流、任意 Python 对象、OS 旁路或真正邮件服务。 |
| WP-09 V5 扩展 | 有限替代，已执行 | I1：mixed/separated 合同对照及可信来源账本；I2：原始/中和/有限 reference 三角证据；I3：阶段/次数规则；I4：单个格式注释扰动。`results/mechanistic/traces.jsonl` 包括 full/no_guard/no_taint/no_lease/no_triangulation；相同 fixture 和动作表 | 不是手册全部 full-V5 消融。无独立 SMT-off 端到端实验；缺一般语义等价变形的人类确认。post_task_reuse 主样本由 max_uses 拒绝，未单独证明时间到期改善；时间边界仅有确定性探针。 |
| WP-10 冻结评估与报告 | 有限替代，已执行并汇总 | 核心提交与 run manifests；`scripts/analyze_results.py`、`src/tsg/evaluation.py` 能从保存结果离线生成 CSV/JSON/错误案例及家族 bootstrap；复现步骤见 `docs/reproduction.md` | held_out、transfer、judge已完成；最终报告、PNG/PDF图、CSV/JSON、错误案例与核验结果均已生成。仅 6 合成模板家族，development/validation/test 为 3/1/2；CI 很弱，1 家族不计算 CI。未实施 McNemar、多个比较校正、CPU/RAM 统计。 |

## 实验 E0–E9 逐项核对

| 实验 | 状态与已执行对照 | 证据入口 | 不能据此声称的结论 / 未完成项 |
|---|---|---|---|
| E0 数据/工具链可运行性 | 有限替代。真实包只读接入、模型 pilot、确定性 VM 文件读写/虚构 token/mock 网络、输出 oracle 和单元探针 | corpus manifest、`results/pilot/detection.jsonl`、`tests/test_corpus.py`、`tests/test_sandbox.py`、mechanistic traces | 未达到真实文件/网络/代码 Skill 在 OS 沙箱“合法成功+禁止操作拒绝”的全验收；没有实际任意代码执行、进程/系统调用审计，亦无手册同名 compatibility/unsupported CSV。 |
| E1 V0 vs V1 检测 | 合成开发/验证/held-out已执行。真实模型图审计及真实三任务transfer已执行 | formal `detection.jsonl` 的 `variant/model/replicate`；`data/graphs/`；`results/real/real.jsonl`；`results/transfer/predictions.jsonl` | 合成 V1 显式动作表示不是自动图抽取精度。真实来源定位只有语法一致性，不能叫人工定位准确率；缺真实 Action/Skill F1。 |
| E2 Replay 必要性 | 有限替代。V1 加 comparable Replay 冗余证据形成派生 V2；396 个动作对比 | `mechanistic/replays.jsonl`；`evaluation.augment_prediction`；`replay_metrics.json`（离线生成） | V2 是已保存 V1 预测的证据后处理，不是第二轮模型或完整 agent。失败不直接证明必要；dependency_blocked 单列。真实人工审定任务与真实代码 replay 未完成。 |
| E3 确定性强制 | 有限替代。同动作目录的 none/V3/V4/V5；模型一次性计划含/不含 textual guard 后执行相同固定策略 | mechanistic `traces.jsonl`，formal `plans.jsonl` 内 `runs/events`；`evaluation.runtime_summary` | 固定 oracle policy 的执行结果与 `contracts.jsonl` 的生成错误分开；未跑 LLM-generated-policy→实际执行的端到端分支。未独立统计每种攻击目标成功率或每个必需调用错拒率，不能把所有拒绝数称 false denial。 |
| E4 数据流标签 | 有限替代。V3/V4 同一动作表测试 confidential input、derived summary 与合法公开 DONE；mock secret label 探针 | `LabeledValue/combine`；`tests/test_policy.py::test_reader_intersection_survives_summary`；`tests/test_sandbox.py::test_legitimate_network_send_and_mock_secret_flow_are_distinct`；V3/V4 trace | “secret_leak”分母是此集合的保密输入流出机会，不是任意实际凭证泄漏率。无真实执行链的 opaque/untracked label 覆盖率；没有完整第三方工具信息流监控。 |
| E5 证据与授权分离 | 有限替代。两模型 mixed Skill+Task 与仅 trusted Task 的合同生成，按同一 ceiling 比较 exact scope/SAT expansion/unknown | formal `contracts.jsonl`；`run_experiment.contract`；`Ledger.update`；`policy_updates.jsonl` | 混合条件也收到禁止 Skill 授权的系统提示，比较主要是是否暴露 Skill。合同仅 operation/resource，未测模型生成 payload/lease 条款；没有真实人工批准交互与审批负担计量。 |
| E6 三角必要性 | 有限替代。artificial dependency、genuine core、optional cache；Replay-only 与 reference-assisted 派生预测/VM 恢复 | `replay_case/reference_run`；full/no_triangulation；V2/V5 派生表 | reference 证明这个有限 fixture 存在排除动作的路径；包含动作不证明全局必要性。参考实现仍是研究者模板，不是所有真实 Skill 的等价实现。 |
| E7 单调收缩与租约 | 有限替代。narrow/expand/unsupported 提议及 guard 租约开关；SAT/UNSAT/witness 和可信时钟测试 | 396 条 `policy_updates.jsonl`；full/no_lease；`tests/test_policy.py` | 当前 late read 发生 runtime step=3、expires=3，实际由次数 1 限制拒绝。主比较不隔离“任务完成后时间失效”因果效应；审批次数/真实负担未测。 |
| E8 元变形稳定性 | 有限替代。给 low/high/authority_spoofing 的 V0 输入追加单个格式注释；另做相同输入两次响应比较 | formal `metamorphic.jsonl`，`evaluation.compare_prediction_pair` 与 consistency 输出 | 不包含人类确认的任务语义改写、多种行为保持 Skill 变换、V1/V5 完整元变形合同对照。输入文字仍可能影响 LLM；观察到一致不构成通用鲁棒性证明。 |
| E9 消融/迁移/成本 | 有限替代，已执行。两模型；V0/V1 两次响应；4 个 VM 开关消融；家族 bootstrap；原始 usage/elapsed 与持久预算账本 | `configs/experiment.json`、mechanistic traces、formal JSONL、`results/api/{raw,budget.jsonl}`、离线 summary | 尚无完整八项 full-V5 消融、真实动态 held-out、CPU/RAM、显著性/多重比较校正。六模板仅 3/1/2 家族，重复 fixture 不增加独立家族数。API 上界包含未结算预留，不能当正式账单。 |

## 已观测数量与运行状态

本表是上述时间点的原始文件行数，`valid` 是解析有效而非安全成功。预期总量来自当前代码的 case/model/variant/replicate 笛卡尔积，仅用于检查缺失。

| 轨道 | 已观测 | 解释 |
|---|---:|---|
| 合成 benchmark | 132 案例 / 396 动作标签 | 66 development、22 validation、44 held_out_test；6 个模板家族 |
| development | detection 528；contracts 264；plans 264；metamorphic 36 | contracts 263 valid、1 unresolved；其余记录解析 valid |
| validation | detection 176；contracts 88；plans 88；metamorphic 12 | 已观测记录均解析 valid |
| held_out | detection 352/352；contracts 176/176；plans 176/176；metamorphic 24/24 | 已完成；contracts 175 valid、1 unresolved，其余结构有效 |
| 机制实验 | 1,188 traces；396 replay；396 updates | 每案例 4 个基础 mode + 5 个消融记录；full 与基础 V5 不是独立样本。Replay：384 comparable、12 dependency_blocked |
| 真实静态/模型提取 | 180 静态图；60 模型响应 | 30 个 development pilot 包 × 2 模型，59 valid、1 unresolved；没有人工真值 |
| 真实三任务 transfer / Replay Judge | transfer 360（359 valid、1 unresolved）；Judge 72（72结构valid） | Judge的null与误判另列；另有48条开发集提示消融 |
| 上游 CaMeL | 官方解释器子集 106/106；自定义探针 15 passed、6 failed | 初次依赖问题的 11 个 collection errors 也保留；不是 AgentDojo 全基准 |
| 上游 Progent | 20/20 观察符合 characterization | 包括复现不安全行为，**不是 20 个安全属性通过**；无完整基准 |

旧 pilot、`results/pre_review/`、`results/pre_cache_review/` 不进入当前正式预测指标；历史 API 支出与未结算预留仍保留。`unknown`、格式失败、缺失记录与不可比 Replay 不转换成安全、TN 或成功。详细变更原因见 [design_amendments.md](design_amendments.md)，上游可复查包见 [literature/upstream_reproduction.md](literature/upstream_reproduction.md)。

## 必须继续保持的主张边界

人工双标注及仲裁、原始任意脚本的 OS 级沙箱与系统调用审计、真实 Skill 的动态 held-out、三个上游的完整论文基准均**未完成**。Original/neutralized/reference 三阶段核心 VM trace，连同 P/Q 组件和一次性模型计划，均不能表述为完整 autonomous agent。现有研究提供可运行的有限机制实验、真实语料的只读分析与待人工审阅证据，不提供真实 Skill 普遍安全或通用最小权限正确性的证明。


# TaskSkillGuard 实验前设计草案

本文件是本地事先设计记录，未在公开平台注册；实际变更与未完成项见 `design_amendments.md` 和 `requirements_matrix.md`。

日期：2026-10-15。依据用户提供的 TaskSkillGuard 手册；用户授权自主设计、实施、创建私有 GitHub 仓库。模型限定 gpt-6-luna 与 gpt-4.1-mini，总 API 预算不超过 USD 20。原始 corpus 和数据库只读。

## 研究边界与证据

三条实验轨道分别报告，不能合并分母：

1. **真实语料审计**：仅 skills.sh 的 completed 下载包。固定 seed=76420261015，抽取 180 个候选（不足的分层保留实际数），其中 30 个 pilot。保留来源 ID、原路径、元数据、内容哈希；以发布者、仓库与选中样本完全相同文本的连通组切分，避免跨源重复。识别不到的脚本语义、动态调用和截断均报告 unresolved。
2. **受控动态实验**：独立构造可执行的模拟 Skill、可信任务、mock 数据和可机械校验 Oracle。运行相同案例的 original/replay/reference 和 V0–V5。只使用受限动作 DSL/可信工具适配器；禁止 eval、任意宿主 shell、真实凭证及公网副作用。若容器不可用，不执行第三方脚本；明确称 tool-mediated sandbox，不能声称 OS 级 containment。
3. **真实 skill 迁移验证**：从真实样本图定位动作，再构造任务三元组与可追溯证据，运行两模型检测。未由两名人类独立标注的真实样本，只报告模型一致性、可定位率、风险候选与未决率，不编造真实 F1。

## 架构

corpus adapter → grounded instruction/AST graph → candidate evidence；trusted task → separate ceiling；schema validation + exact-scope policy + Z3 subset comparison → deterministic tool guard；sources/readers tracking → mock sink；replay + independent reference oracle → necessity evidence。

V0：直接 LLM；V1：动作图与任务合同；V2：加原始/中和重放；V3：确定性工具守卫；V4：数据流标签和可信/不可信输入隔离；V5：双账本、三角必要性与阶段租约。检测和阻断指标分开。各消融独立开关，固定案例、合同和工具提议。

## 事先固定的检验

- 默认拒绝未知工具、缺失参数、越界路径、未批准目的地、无来源标签的流出。
- 无批准策略仅允许 Z3 UNSAT 证明的子集；SAT 保存 witness，UNKNOWN 保留旧策略。
- 原始与 Replay 必须干净初始化。原始未触发、无效中和、运行失败各自保留。
- 授权不等于必要；明确授权的外传、正常临时文件和合法 mock token 访问作为负例。
- 所有预测、模型原始响应、参数、输入哈希、tokens、时间、失败和费用保存；费用按请求上界预留，避免并发越限。
- synthetic oracle 标签与 human GT 不能混称。人工双标注属于独立待完成环节，交付审核包，不由多个 LLM 冒充。
- 先 pilot/development 修复工程错误，冻结代码与数据后只运行一次 held-out，重复只估计模型随机性，不调参。
- bootstrap 按家族组采样，报告 n、分母和 CI。若样本组少或模板同质，明确外推限制。

## 验收

可运行代码、测试、三篇论文全文阅读记录和代码核验、真实抽样 manifest、受控 traces、两模型真实请求、分版本原始结果与自动生成统计、失误分析、预算记录、复现命令、私有仓库推送验证。未满足的手册项单独列出，禁止把计划数写成实测数。


# TaskSkillGuard Phase Three Implementation Plan

> Execution: authorized current-session implementation; independent domains use the dispatching-parallel-agents workflow, followed by integration and review.

**Goal:** 修复已定位问题、运行新冻结实验并上传可复核前后对比。
**Architecture:** 新 v3 协议、执行器和实验驱动；旧产物只读。API 单写预算、独立原始记录；模型与可信编译器分轨。
**Tech Stack:** Python 3.12、pytest、jsonschema、现有 Z3/Docker/Responses API。
**Spec:** [phase3_design.md](phase3_design.md)

## Global Constraints

- 180 已授权样本，24,000 字符/12 文件，原库与 sources/ 只读。
- 累计 USD20；保留历史 USD5.8589654；只由主进程发送 API 请求。
- 旧 data/results/docs 不改写；人工标注 pending；先冻结再正式采样。
- 决策不得读取评分 Oracle；协议失败和未触发不算安全成功。

## Review Focus

- 多个响应消息、拒绝、截断不能被拼接成有效合同。
- 参考恢复不能扩权、重置已耗用额度或依赖评分真值。
- 缺失必需步骤与无害可选未知必须分开。
- body=DONE 与 taint 检查分别消融，公开恶意 body 不能绕过合同。
- 新结果不能覆盖旧文件、清空费用或膨胀独立样本数。

## Task 1: Protocol
- [ ] 在 tests/test_protocol_v3.py 先写拒绝/截断/多输出/enum/schema/request-hash 测试并观察失败。
- [ ] 新增 models_v3.ClientV3（兼容 Client.call，增加 response_schema）和 planner_v3 的 PLANNER_SCHEMA、P_SYSTEM_V3、make_planner_payload、parse_planner_record。
- [ ] parse_planner_record 返回 protocol_valid、diagnostic_codes、prediction、reference_actions、scope_policy、declared_unknowns；不偷偷修复内容。
- [ ] 运行定向测试，保存证据。

## Task 2: Execution
- [ ] 先写漏通知、空计划、依赖来源、非法初始范围及参考路线的失败测试。
- [ ] 新增 pipeline_v3.run_pipeline_v3(case, planner, q_plan=None, variant='full', transform_fn=None)。保留旧引擎；通过自有新 VM 或明确回调执行变换。
- [ ] 消费 Task 1 返回值；验证范围/义务，参考恢复只读可信任务，独立事后评分。
- [ ] full/model_raw/trusted_compile/no_obligations/no_recovery/no_authority/no_scope/no_body/no_taint/no_lease 逐项记录含义；任何不适用条件明确记录。

## Task 3: Real contexts
- [ ] 先写 context 分母/缺范围不伪装 high/源文件不变的测试。
- [ ] 新增 real_v3 与 prepare_real_phase3.py；生成有界 source、共同节点、明确语境和盲审接续说明。只写 data/phase3/results/phase3/new docs。
- [ ] 提供主驱动可调用的 job preparation / response parsing 接口；不自行访问 API。

## Task 4: New fixtures and frozen drivers
- [ ] 新增独立变换函数、手写 expected fixtures 与分割；先测实际变换和反例。
- [ ] 冻结协议 2×2、旧回归、新 P/Q、固定攻击与 OS 轨道清单；创建累计预算副本和原结果哈希清单。
- [ ] 开发 smoke 后记录任何修订，再冻结正式实验代码及输入。
- [ ] 顺序运行 API 阶段、VM/OS、真实有界检测；保存首次失败及每次重试。

## Task 5: Analysis and release
- [ ] 统计测试先覆盖未知分母、缓存复用和家族 bootstrap。
- [ ] 生成历史归因、修复前后对比、新家族与真实覆盖、预算、局限及复现命令。
- [ ] 独立代码审查，修复重要问题，完整测试、原产物哈希和预算核验。
- [ ] 上传原私有仓库并核验远端提交与 CI；不覆盖旧 tag。

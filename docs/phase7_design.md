# 第七轮：区分适用性、核验执行证据、修复安全重试

2026-10-16；纯合成；继续用户已授权工作。基线 aac66f057408dafeca817e1dc059ff47b7027954。所有基线文件逐字节保留。本方案是本地前瞻冻结，不声称外部预注册。

## 研究问题与归因

RQ1：将 inactive、原始路径失败和无合法路径从 unknown 中拆为 not_applicable，并明确“当前路径必要性”与“目录内必要性”，能否提高判断质量？标签空间变化本身不算模型改进。

RQ2：要求逐世界可执行证据，能否提高原始判断准确率？证据检查器的拒绝覆盖和独立有限求解器准确率分开报告；检查器能穷举整个问题，所以绝不将求解器纠正归功于模型。

RQ3：在同样路线目录、权限、模拟能力、4 次实际尝试和共享调用配额下，保留安全失败路线的重试资格、跳过已知永久失败，能否修复合法恢复及成本反转？未知提交结果必须停止；不清除收据、不扩权、不利用未来故障表。

## 类型语义（逐世界后聚合）

轴名 authorization、current_route_required、catalog_required；取值 yes/no/unknown/not_applicable。
authorization：站点没有执行时 not_applicable；全部实际执行匹配精确授权为 yes，否则 no。
current_route_required：站点执行且原始路径成功时，从同一初态屏蔽该站点全部出现；目标不成立 yes，仍成立 no；未执行或原始失败 not_applicable。
catalog_required：站点未执行 not_applicable；原始路径和全部公开替代路径独立从初态执行，仅保留成功且全部执行获授权的路线。没有合法成功路线 not_applicable；有路线避开目标的所有 (op,resource) 身份 no；否则封闭目录 yes，开放目录 unknown。
聚合：所有世界同值则保留（含 not_applicable）；其他情况 unknown。原因分别记录 inactive、baseline_failure、no_feasible_route、open_catalog、partial_applicability、world_disagreement。折叠 not_applicable→unknown 后必须与 v6 真值一致。

## 接口与独立性

`truth_v7.evaluate_case(case)` 只读 reference program，复用独立 truth_v6.run/static_sites，返回 labels（id+三轴+reasons）、worlds；不读 source、production 模块或模型答案。
`evidence_v7.solve(case)` 只解析 source，复用 runtime_v6.run_semantics；返回 judgments，每项 id+三轴+worlds。worlds 每项为 world(int)、occurred(bool)、all_occurrences_authorized(bool，空集合 true)、baseline_success(bool)、suppressed_success(bool)、legal_routes(list[int])、avoiding_routes(list[int])。无目标时 avoiding_routes=[]。route 0 原始，其余按目录顺序。
`evidence_v7.check(case,prediction)` 精确检查每项标签、世界覆盖和每个证据字段；不暗中修正模型答案。生产求解器和参考聚合代码分别实现。

## 数据与模型试验

48 个旧样本只用于回归；新增 12 个独立编写结构家族、每家族 2 个种子（24 样本），作者不读新生产实现/模型结果。有限 DSL 不增加语言操作，变化为组合结构、授权、路线、初态。必须包含否定、无适用性、开放目录、混合世界、故障可达/不可达情况；这仍是同一语言内组合泛化。
72 样本×2模型×3协议=432主条件。B0 原 v6 table 三值协议；B1 新类型直接回答；B2 同类型加逐世界证据。所有条件公开事实相同、不提供金标或私有 AST，最大输出统一 4000 tokens。选新家族中 SHA256 排序前6家族的首个种子，B1/B2 各追加2次重复，两模型共48额外条件，总480。新采集缓存独立于旧轮，无自动重试；请求摘要去重明确报告。
B0/B1/B2 折叠后的同一语义比较；B1/B2 四值指标另外报告。按旧/新拆分，报告三轴准确率、unknown召回/错误unknown、not_applicable混淆、证据接受覆盖/选择性正确率、token与费用、家族平均差异和家族 bootstrap 95%区间（10000次，固定种子7007）；探索性多重比较，不作确证显著性声称。
图边不作为本轮新因子：前轮没有跨模型稳定收益，先修复测量语义与执行归因。

## 恢复试验

`recovery_v7.execute(case, selector, policy, fault='none', allowed_ids=None, world_index=0, quota=16)`：selector为first_feasible/search_equal，policy为legacy/safe_retry；相同解析、权限、收据、配额和模拟程序。
legacy 精确复现 selection_v6 的两次原始尝试、替代路线尝试后移除。safe_retry 首次原始执行；观察到 transient_before 或 known_after 时保留该路线，下一次尝试优先重试；其余失败移除该路线并对剩余替代路线完整模拟，按目录首个/最低调用数选择。未知提交和耗尽配额停止。不得从 fault 值或未来计划选路。
故障网格：none；第一/第二个实际可提交变更上的 transient_before、known_after、ambiguous_after；前两个可提交变更尝试连续 transient_before（共8种）。新网关只决定故障注入时机，策略只读实际错误；未触发情况单列。调度按 eligible mutation dispatch 计数（排除已拒绝、冲突、收据复用），不是按静态站点。不宣称覆盖任意位置或任意故障。
所有72样本、每个公开世界、两配额8/16、两选择器×两策略×8故障。报告配对成功、调用成本、模拟成本、未授权/重复副作用与停止原因。旧四种故障下 legacy 与冻结 v6 结果逐字段一致（新增诊断字段除外）。
端到端：所有主条件模型授权 yes 作为原始路径门控，在world0、quota16、none/transient_before/known_after 下，比较两策略、两选择器。B2原始、证据拒绝全阻断、求解器三者分开；必要性轴不参与运行门控。所有替代路径仍受可信授权检查，报告目录恢复对模型门控的绕行，不能把可信网关零未授权效果算成模型贡献。
宿主纯内存 VM 后，在固定无网络、只读、限资源容器中重复所有条件并比较完整结果。按批容器运行，不把每条件宣称为独立容器。

## 冻结、预算与停止规则

先完成开发及独立单元检查，冻结新实现、协议、参考、生成器和输入摘要，再首次评估新样本、生成请求、调用API。测试失败可在冻结前修复；冻结后任何修复须新版本与保留失败证据，不能覆盖原物。不按模型结果调提示词或替换样本。
继承 results/phase6/challenge/api/budget.jsonl 全部字节；累计上限 $29.551575125；本轮请求预留上界不得超过剩余预算且不得超过 $5。只用已授权 gpt-6-luna/gpt-4.1-mini。保留所有不确定账单预留，单进程线程安全账本，无自动重试。
最终保存结构化原始结果、前后配对分析、失败证据、限制、费用审计、旧文件哈希核验、复现指令；上传原私有仓库并核验远端与CI。

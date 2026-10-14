# SkillScope v3 全文与复现边界审计

审计日期：2026-10-15（Pacific/Auckland）。本文是来源、算法和实验协议审计，**不是 SkillScope 复现实验结果，也不是 TaskSkillGuard 已完成实验的证明**。

## 1. 审计材料、阅读方式与结论

- 主来源：用户提供的 `C:/Users/victo/Downloads/2605.05868v3.pdf`，21 页；标题 *SkillScope: Toward Fine-Grained Least-Privilege Enforcement for Agent Skills*，Jiangrong Wu 等 7 位作者。首页标示 arXiv:2605.05868v3，2026-09-10，并注明是 ACM CCS 2026 接收稿的完整版本。
- 本地 PDF SHA256：`E701A88AD22BEFB1B7D9E4F66098FB637093C09938AE53F87D308F7B048BCC9A`。文件 2,185,221 bytes，PDF 1.7，无嵌入 JavaScript，21 页。该 hash 标识本次实际阅读的用户文件；未将它声称为从网上重新下载文件的 hash。
- 实际阅读：分批读完已提取全文 `tmp/taskskillguard-reading/2605.05868v3.txt` 的第 1–21 页，包括 References、Ethical Considerations、Appendix A–H；随后将全部 21 页渲染为 PNG 并逐页查看。双栏文字提取的表格串行错位，用原图核对，尤其 Tables 1–19。渲染保存在 `tmp/taskskillguard-reading/skillscope/page-01.png` 至 `page-21.png`。页码均指 PDF 印刷页码，与文件页序一致。
- 配套手册：重点完整核对 `C:/Users/victo/Downloads/TaskSkillGuard_Research_Experiment_Manual_ZH.md` 的 §6、§8、§12–14、E0–E3、§16，结合 §1、§18、§20 的来源与交付边界；未将手册的计划值写成观测值。
- 只进行了材料阅读、公开网页核验和 PDF 渲染。没有执行任何 Skill 样本，没有使用 API 密钥，没有调用模型 API 产生实验预测，没有修改样本库。

**结论：**SkillScope 的核心是“跨说明/代码动作图 + 高召回候选筛选 + 候选可达路径生成任务 + 独立授权判断与反事实必要性验证 + 语义 guard/脚本重组”。判定式为 `privilege_relevant AND (NOT authorized OR unnecessary)`。论文有实际运行、人工 GT 与消融实验，但其语义 guard 不是独立工具层权限强制器，有限任务集与 LLM 判断不能提供完整性或零越权保证。截至本次核验，**尚未找到能与这篇论文及其作者对应的官方公开实现仓库**；应将本项目实现标为 `paper-inspired reimplementation / SkillScope-inspired adaptation`，不能宣称使用了原作者源码或复现了原成绩。

## 2. 版本与官方代码核验

### 2.1 已核实的第一方来源

| 来源 | 本次实际看到的证据 | 能支持的结论 |
|---|---|---|
| [arXiv v3 摘要页](https://arxiv.org/abs/2605.05868v3) | 21 pages, 7 figures；v1 2026-05-07，v2 2026-09-07，v3 2026-09-10；v3 摘要报告 6,590/68,312 | 用户文件的论文身份、版本、作者与关键摘要值可核验；页面未给出作者代码仓库 |
| [通信作者 Yuhong Nan 主页](https://nanyuhong.github.io/) | Publications 列出 CCS'26 SkillScope，作者完全对应 | 第一方论文记录；条目没有代码链接 |
| [Huaijin Wang 主页](https://whj0401.github.io/) | SkillScope 条目只有 Preprint 链接；同页其他论文可有 Code/Artifact 链接 | 本条目未提供可核验代码，不可从其他论文代码反推 |
| [Shuai Wang / HKUST 主页](https://cse.hkust.edu.hk/~shuaiw/) | Selected Publications 列出同名、同作者 CCS 2026 论文 | 第一方发表记录；该条目未找到实现链接 |
| [Huaijin Wang 的 GitHub 主页](https://github.com/whj0401) | 从作者主页的 GitHub 链接进入；当前页面未匹配 SkillScope | 仅是有限页面检查，**不是所有公开/私有仓库的穷尽证明** |

检索组合包括完整论文标题、`"2605.05868" "github.com"`、`"SkillScope" "Jiangrong Wu" code`、`"SkillScope" "Yuhong Nan"`、`"SkillScope" site:github.com "least"`。未从这些结果建立“作者身份 → 对应论文 → 实现仓库”的可验证链。中山大学教师页面的一次直接打开返回工具内部错误，故没有将该打开结果当作已读网页证据；上述三位作者主页均成功读取。

本地完整 PDF 中的 GitHub 链接属于引用的 baseline、MCP fixture 工具等，未发现作者 SkillScope 实现地址。Ethical Considerations（p.16）说释放脱敏例子、聚合统计及非敏感复现材料，但**没有在该 PDF 中给出可据此取得材料的 URL、仓库或 DOI**。因此不能把“论文写了 release”当作“本地已拿到 artifact”。

### 2.2 同名项目排除

| 结果 | 已核实身份 | 为什么不能当作本论文代码 |
|---|---|---|
| [amd/skillscope](https://github.com/amd/skillscope) | AMD 的 Agent Skills 测试 harness | 仓库自述与所有者不对应 Wu 等人的任务条件化最小权限研究 |
| [heidihowilson/skillscope](https://github.com/heidihowilson/skillscope) | 浏览/管理多种 agent harness 中 SKILL.md 的 Go TUI | 主要是技能文件发现、显示、复制、移动、删除；不是论文动作图/Replay/guard 系统 |
| [arXiv:2605.12875](https://arxiv.org/abs/2605.12875) | *Do Skill Descriptions Tell the Truth? Detecting Undisclosed Security Behaviors in Code-Backed LLM Skills*，Wenhui He 等 | 另一作者组、另一篇论文，也使用 SKILLSCOPE 名称；其 SPG/说明一致性方法不能替代本文 |
| [arXiv:2501.15922](https://arxiv.org/abs/2501.15922) | *SkillScope: A Tool to Predict Fine-Grained Skills Needed to Solve Issues on GitHub* | 研究 GitHub issue 所需编程技能，主题和论文身份不同（本次搜索摘要识别，未做全文审计） |

当前复现状态：`paper-read=complete`；`official-repo=not-verified`；`official-code-cloned=false`；`official-code-tested=false`；`exact-reproduction=false`。这是“未核实到”，不是宣称仓库绝不存在。搜索摘要中仍有旧版 7,039，**本审计所有实验数据以用户 v3 PDF 为准**，不混用旧版。

## 3. 数学判定：授权和必要性不能混同

依据 §2.2（pp.3–4）、§4.2（pp.7–8）。

设 Skill 为 `σ`、用户任务为 `p`，执行轨迹为有序、带参数的动作序列 `τ(σ,p)`。动作不是只有 `read/send/exec` 工具名：授权判断要同时考虑 **operation、data source、sink/destination、side effect**。最终用户输出写为 `o(σ,p)`。

`Auth_p(a)`：动作的具体操作、来源、目标及副作用是否落在用户任务传达的权限范围内。它不能由 Skill 声称“必需”、宿主平台预先批准工具，或研究环境允许运行而自动成立。

`σ ⊖ a`：中和或移除候选动作，同时保留其余 Skill 逻辑。论文定义：

```text
Unnec_σ(a,p) = CorePres_p(τ_original, τ_replay)
               AND GoalSat_p(τ_original, τ_replay)

OverPriv_σ(a,p) = [type(a) in privilege-relevant types]
                 AND [NOT Auth_p(a) OR Unnec_σ(a,p)]
```

- `CorePres` 关心用户请求所需的核心流程及外部可见必需副作用是否保留，**不是所有原始 trace 动作都必须相同**。
- `GoalSat` 关心重放是否仍完成用户目标；原始执行仅作为上下文证据，**不是要求重放字符串与原输出完全一致**。
- 两项均真才确认 unnecessary。一项不成立时，论文说“未确认该动作不必要”，并非证明它对用户目标绝对必要。
- `NOT Auth` 本身即可使已执行、权限相关动作越权，即使 Replay 因真实依赖、伪造依赖或中和错误而失败。不能写成 `NOT Auth AND Unnecessary`。
- 论文执行级确认针对 Original **实际执行**的候选；没有触发不等于证明安全。候选筛选风险、潜在可达性与实际执行确认应分别记录。
- 对已授权但能在保留所有请求效果时去掉的多余动作，论文仍可能判 unnecessary/over-privileged。因此实验应分别报告 unauthorized 与 unnecessary，避免用一个“非法”标签掩盖两种性质。

**必要性边界（审计推论）：**这里的反事实是同一实现的局部消融，`Unnec_σ` 特意带 `σ`。它不能证明“所有可能实现中该动作均必需”。Skill 人为把越权副作用设为前置条件时，单次消融失败不能把这种依赖提升为用户授权。手册 §8.4 增加独立参考工作流/Oracle 的三角验证，正是在扩展这部分；不能把该扩展回写为 SkillScope 原算法。

## 4. 统一执行图与候选提取

依据 §4.1（pp.5–7）、Figure 4（p.6）。

### 4.1 图的精确对象

```text
G = (V, E)
V = V_instruction ∪ V_code ∪ V_predicate
action v = <layer, operation, object>
predicate v = <layer, normalized predicate>
E = E_control ∪ E_data ∪ E_call ∪ E_return
```

每个节点附 `src(v)`，链接回原始文本 span 或代码 span。控制边表达顺序或条件控制；数据边表达对象/值流；call 边把说明层脚本调用连到代码入口；return 边把代码返回连回后续说明动作。该表示区分动作与谓词，而不是仅把 Markdown 的每一行变成一个节点。

### 4.2 构建顺序

1. **说明层：**轻量结构解析捕获命令、祈使动词、if 等条件、Markdown 段落边界；LLM 再将语义相关片段规范化为原子动作，推断自然语言谓词并恢复语义依赖。
2. **代码层：**对被调用脚本构建 AST，提取函数调用等操作；进行轻量**过程内**数据流与控制依赖分析。论文没有声称完整跨过程程序分析、符号执行或任意动态语言 soundness。
3. **跨层：**从显式脚本调用添加 call 边，把代码返回接回后续说明步骤。保留说明语义与代码操作两层的差别。

**未披露的复现细节：**具体 parser/AST 库及版本、支持语言、调用识别规则、动态 exec/eval 处理、别名/导入解析、谓词 schema、图序列化 schema、循环与递归截断方式、跨层节点身份去重规则、图匹配评价准则及完整 prompts。自行选择这些时必须登记为适配决策。

### 4.3 候选分类不是授权

Skill profile 来自 `name/description/use_when` 等元数据及说明摘要。LLM 分类器接收 profile、动作摘要，以及向前/向后遍历获得的 predecessor、successor、predicate 上下文。它是**高召回筛选器**：保留与声明功能脱离/过度的动作，也保留 `task-ambiguous` 动作。

例如“发送报告”可属于 Skill 正常功能，但当前任务若只是本地查看就未必有权发送。论文明确不因动作“与功能相关”就把这些 task-ambiguous 节点过滤为良性。高风险与 task-ambiguous 候选需下游具体任务验证。

**信任边界（审计推论）：**profile 是 Skill 的自述，且威胁模型允许攻击者控制元数据、说明和脚本（p.4）。它可用于筛选语义上下文，不能直接成为可信权限上限。TSG 的 trusted task ceiling、证据双账本和 P/Q 隔离属于额外机制，不是原文已证明的抗自述污染保证。

## 5. 图引导任务、fixtures 与 Replay

依据 §4.2（pp.7–8），Appendix B/Table 14（pp.16–17）。

### 5.1 图引导任务不是穷举自然语言空间

- 从 entry 前向遍历，提取图中支持的 action chains，以图结构近似 Skill 的任务空间。
- **candidate-aware：**对候选 `a`，只从能到达它的 chain 生成验证任务。不经过候选的链不属于该候选的验证集合。
- LLM 输入 Skill profile 和目标 action chain，生成语义符合 Skill 功能、结构上有望触发该 chain 的用户 prompt。不要求 Skill 特定微调。
- 需要资源时生成最小合成 fixture；prompt + fixture 实际触发预期 chain 才被用于验证。
- 这只是图中可见工作流的覆盖；未建出的边、隐藏依赖、未生成的任务、无法触发的链仍是盲区。

Appendix B 的 fixture 支持包括：纯 prompt；CSV/JSON/TXT/LOG 文件；少量文件/commit 的 toy repo；Markdown/TXT 或经 Pandoc 转换的 DOCX/PDF；小型占位 PNG；dummy config 和从轻量 OpenAPI 说明生成的 mock API。原文关联 Filesystem、Git、Terminal、Pandoc、Placeholder Image、MockLoop MCP 工具。它们是测试输入工具，不是已经配置好的通用沙箱证明。

### 5.2 Original / Replay 的操作

对每个任务与候选：

1. 同一任务下执行 Original，记录实际动作、参数、trace、用户最终输出。
2. 对说明候选删除对应说明步骤；对耦合代码候选中和行为，例如目标函数体改为立即返回，以尽量避免破坏依赖造成假失败。
3. 在控制且可比较的隔离环境中执行 Replay，记录同样证据。
4. 只对 Original 触发的候选，以固定 schema LLM scope judge 判断 Auth。
5. 给 judge 候选与出处、prompt、规范化 Original/Replay traces、两次输出，分别判断 CorePres 和 GoalSat，再组合最终 verdict。

Trace 规范化包含有序动作摘要、目标对象、参数摘要。授权与必要性 judge 要输出 verdict、理由和指向所给证据的引用。自动 validator 检查字段、引用范围、组件间一致性；失败时使用同样 grounded context 和反馈重试，**最多总计 5 次尝试**；持续失败标 unresolved（§3.1，p.5）。这不是“最多五次实验复跑”，也不是五个独立 annotator。

**本项目应补足但原文未给充分细节的内容：**全新环境恢复方法、文件/网络 mock 截获实现、并发/异步顺序、Replay 返回值类型保留、错误分类、随机性重复次数、执行时间/步数限制、输出 Oracle 和判定 prompts。手册要求 clean sandbox、`invalid_ablation`、`not_triggered`、`runtime_error`、`unknown` 独立记账，这些是适配协议的重要改进，不能冒充作者原始实现细节。

## 6. Guard 生成与实际安全边界

依据 §4.3（pp.8–9），Figure 7（p.8），Appendix H（pp.19–21）。

### 6.1 从验证上下文生成条件

每个已确认动作 `a` 收集验证用任务及最终判定，抽取固定描述符：task intent、requested operation、target object、execution scope、destination、explicit side-effect request、final validation verdict。表 18 明确 **unresolved verdict 不用于自动合成**。

流程为：描述符抽取 → 等义字段规范化 → task-context 分组 → 对比允许/拒绝上下文合成 `C_a` → 创建 `<C_a,a>` constrained node。条件满足才路由到动作，否则跳过。语义聚类不是单一 prompt 字符串白名单。

附录例子中，`send(report,Telegram)`：本地 report/heatmap 请求为拒绝类；明确把 report 发送/同步给 Telegram 对象为允许类。`C_a` 要求明确 send/sync 请求、正确对象和目的地。注意表 19 用 “Telegram” 作说明级 destination；TSG 应按其手册把收件人/endpoint 精确化，不能仅平台名称相同就允许任何接收者。

### 6.2 回写工件的两层策略

- **说明层动作：**在图中插入 constrained node，再回写 SKILL.md 的自然语言 semantic guard。论文故意不使用刚性关键词判定，以便 LLM 处理同义用户表达。
- **代码层动作：**LLM 辅助 extract-method/method restructuring，把耦合逻辑分离为任务特定执行单元；SKILL.md 的语义条件由 agent 的底层 LLM 判断应该调用哪个单元。代码单元本身执行其对应行为。
- 输出是改写后的 Skill bundle。论文不是每次工具调用都由不可绕过的符号 permission checker 检查；没有完整权限 DSL、Z3 subset 检查、独立审批日志或读写者标签机制。

**实证边界：**p.13 明确说明残余越权来自语义约束被复杂上下文稀释，以及 LLM 程序分离不完美。论文实验仍有 54 个 action-in-task 越权触发，不能声称完成修复即安全。手册 E3 的“仅 Instruction Guard vs 工具守卫”是合理对照，但应把原文式 guard 与 TSG tool guard 明确区分。

## 7. Ground Truth：真正的人工协议

依据 §5.1（p.9），Appendix C（pp.16–17）。

1. 从去重且可用的生态库分层选样：marketplace source、Skill category、artifact composition（仅说明/说明+脚本）、observable operation type（文件、网络、外传、命令、持久状态）。最后人为构成 100 positive + 100 benign 的平衡集，因此不是生态自然阳性率样本。
2. 人工检查 metadata、instruction、script、auxiliary resources，构建并修订 ground-truth unified graph，含规范化 operation/object/layer/provenance 与四类依赖边。
3. 从人工校验图提取代表性工作流，生成并修订 task prompt；检查它符合声明功能且能触发 chain；需资源时一并检查 fixture。
4. **人工 GT 图和 prompts 只用于 benchmark ground truth，不作为 SkillScope 评估输入**（p.16）。不能把人工完整图塞给待评系统然后宣称自动图质量。
5. 在 action-in-task 级独立标 Auth、CorePres、GoalSat，并按 `¬Auth ∨ Unnec` 得最终标签。动作只要存在一个正 task verdict 就是 action-level positive；Skill 只要存在一个正 action-in-task 就是 Skill-level positive。
6. 两人独立检查每个 Skill；分歧讨论；仍不一致交第三人。第三人之后证据仍不足，保守记为 not confirmed。benign 的含义仅为“标注任务集合下未找到正例”，不是所有未来用户任务都安全。

**人工性边界：**LLM 给出多次答案或多个子 agent 复核不等同于这项两人独立人工标注协议。没有实际人工审核就应叫 provisional/weak labels 或规则 Oracle 标签，并保留标签来源。论文没有报告 Cohen's κ、分歧数量、unconfirmed 数量或每层抽样配额；不要自行填补。

| Benchmark 单位 | 总数 | Positive | Negative / 未发现正例 |
|---|---:|---:|---:|
| Skills | 200 | 100 | 100 |
| Annotated action nodes | 2,113 | 289 | 1,824 |
| Ground-truth task chains | 261 | 未给链级正负拆分 | 未给 |
| Annotated action-in-task | 737 | 507 | 230 |

这里的 737 不是 200×固定任务数；261 是 chain 数，249 是 GPT-5.1 成功触发 chain 数（95.40%）。不得把这三个分母互换。论文没有附逐例清单说明 261、249、737 的身份映射；TSG 需要持久化 `case_id/chain_id/action_id/run_id`。

## 8. 原论文实验与精确数字（不是本项目结果）

### 8.1 模型、环境与未披露项

§5.1（p.9）：Mac M4 Max、36 GB RAM；文件系统/网络/命令隔离执行环境；LLM 组件默认 GPT-5.1。对照模型包括 Gemini-3.1-Flash-Lite、Claude-Sonnet-4.6、DeepSeek-V3.2。LLM baseline 使用相同 GPT-5.1。

全文没有给出足以精确重跑的 API snapshot、temperature、seed、top_p、reasoning effort、max output tokens、模型版本固定方法、agent/runtime 具体版本、沙箱配置文件、每任务 max steps/timeout、运行重复次数/误差条、完整判断与生成 prompts。表格给定模型名不能视为所有配置已披露。工程实现应固定并记录自己的值，公开说明与论文的差异。

### 8.2 主检测结果（Table 1，p.9）

| 单位 | TP/FP/TN/FN | Precision % | Recall % | F1 % | Accuracy % |
|---|---|---:|---:|---:|---:|
| Skill | 95/6/94/5 | 94.06 | 95.00 | 94.53 | 94.50 |
| Action | 279/21/1,803/10 | 93.00 | 96.54 | 94.74 | 98.53 |
| Action-in-Task | 472/33/197/35 | 93.47 | 93.10 | 93.28 | 90.77 |

### 8.3 组件、图质量与消融

Table 2（p.10），候选提取：

| 模型 | TP/FP/TN/FN | P % | R % | F1 % |
|---|---|---:|---:|---:|
| GPT-5.1 | 281/129/1,695/8 | 68.54 | 97.23 | 80.31 |
| Gemini-3.1-Flash-Lite | 247/203/1,621/42 | 54.89 | 85.47 | 66.86 |
| Claude-Sonnet-4.6 | 286/187/1,637/3 | 60.47 | 98.96 | 75.08 |
| DeepSeek-V3.2 | 269/151/1,673/20 | 64.05 | 93.08 | 75.88 |

Table 3（p.10），任务链触发：各模型共同分母 261；GPT 249（95.40%）、Gemini 238（91.19%）、Claude 251（96.17%）、DeepSeek 244（93.49%）。这是“图中任务链成功触发覆盖”，不是全自然语言任务空间覆盖。

Table 4（p.10），confirmation judge：

| 模型 | TP/FP/TN/FN | P % | R % | F1 % |
|---|---|---:|---:|---:|
| GPT-5.1 | 472/33/197/35 | 93.47 | 93.10 | 93.28 |
| Gemini-3.1-Flash-Lite | 428/70/160/79 | 85.94 | 84.42 | 85.17 |
| Claude-Sonnet-4.6 | 442/23/207/65 | 95.05 | 87.18 | 90.95 |
| DeepSeek-V3.2 | 451/52/178/56 | 89.66 | 88.95 | 89.31 |

Table 13（p.16），人工图比较：instruction nodes F1 98.07（TP/FP/FN=1441/32/25）；instruction edges 97.15（1480/47/40）；code nodes 95.02（617/35/30）；code edges 92.62（765/65/57）；cross-layer links 95.57（194/10/8）。图抽取没有自然有界的负例空间，因此不报告 TN。别给图边直接套一个无定义的“准确率”。

Table 6（p.11）使用可执行**替换消融**，不是把必要模块直接删除：

| 版本 | 替换方式 | Skill F1 % |
|---|---|---:|
| w/o Unified Graph | raw artifacts 上直接 LLM 分析 | 73.74 |
| w/o Graph-guided Task Generation | 相同 prompt budget 下，用 profile-only 生成任务 | 82.16 |
| w/o Dynamic Validation | 无运行 trace/输出的静态 LLM necessity judge | 79.22 |
| Full SkillScope | 完整链路 | 94.53 |

Table 5（p.10）基线 Skill F1：Skill Scanner 78.26、Caterpillar 61.08、MASB 25.85、Skill-Sec-Scan 49.45、Nova-Proximity 19.18、MalSkills 86.87、SkillScope 94.53。基线多以全局恶意技能为目标，任务定义不完全一致，不能把这些数值当作所有场景下的工具优劣排名。

### 8.4 大规模结果与 post-hoc 人工校准

§5.1/§5.3（pp.9、11–12）：收集 110,046 → 去重/可用性过滤后 68,312。候选 Skill 8,328；最终验证 Skill 6,590。`6,590/68,312 ≈ 9.65%` 是该管线在该快照与生成任务下的检出比例，不是无偏的真实生态风险率。

Table 8（p.12）：

| 来源 | 候选 Skills | 验证 Skills | 总动作节点 | 候选动作节点 | 涉及越权 user tasks |
|---|---:|---:|---:|---:|---:|
| instruction-level | 6,997 | 5,541 | 63,274 | 9,846 | 6,075 |
| code-level | 1,891 | 1,498 | 22,847 | 3,171 | 1,642 |
| both levels（交集） | 560 | 449 | 8,931 | 1,429 | 684 |
| Overall（去重） | 8,328 | 6,590 | 77,190 | 11,588 | 7,033 |

总 instantiated tasks 为 16,743。instruction/code 两行非互斥；不能相加后再报总计。Table 9 两种模式：over-collection 2,961 Skills / 3,158 tasks；over-execution 3,629 / 3,875。Table 17 类别总数（6,590）：tools 2,211、productivity-tools 1,608、llm-ai 750、data-ai 410、devops 356、cicd 340、testing-security 308、finance-investment 277、other 330。

Appendix E/Table 16（pp.18–19）：只审计检测出的 positive/candidate claims，并非重新测整个库召回率。

| Audit target | instruction-only / code-involving 总体 | 样本 | 两层确认数 | 加权有效率 | 95% CI |
|---|---|---|---|---:|---|
| Validated Skills | 5,092 / 1,498 | 200 / 100 | 189/200，93/100 | 94.16% | [91.47,96.85] |
| Candidate actions | 8,417 / 3,171 | 150 / 50 | 140/150，46/50 | 92.97% | [89.41,96.52] |
| Validated tasks | 5,391 / 1,642 | 150 / 50 | 141/150，46/50 | 93.53% | [90.13,96.93] |

凡含 code provenance 的案例归 code-involving，其余为 instruction-only；两层互斥，code-involving 被过采样。总体估计按 population proportion 加权，而非直接合并样本确认比例。CI 用分层样本方差、正态近似 `p_hat ± 1.96 SE`；作者明言没有建模审阅者主观性。图候选审计只确认“应该进一步验证”，不能把它的 92.97% 说成“已确认越权准确率”。

### 8.5 修复效果与效用（pp.12–13）

Table 10 的修复集是已检测到的 95 个 over-privileged Skills，基线是 279 个动作、472 个 action-in-task、249 个 chains：

| 单位 | Original → Constrained |
|---|---|
| 仍触发越权的 Skills | 95 → 13 |
| 仍触发越权的 Actions | 279 → 31 |
| 仍触发越权的 Action-in-task | 472 → 54 |
| 仍触发越权的 Task chains | 249 → 27 |

论文的 88.56% 是 `(472-54)/472`。不是系统全部 737 案例的风险率，不是漏检动作也得到修复，更不是全 68,312 Skills 的已测风险下降。该子集未覆盖 Table 1 的 5 个漏检 positive Skills。

Table 11：同一批 95 Skills 的修复迁移到 Claude Code、Codex、Cursor、Trae，剩余动作分别 34、29、38、27；以固定 279 为原始基准，对应下降 87.81%、89.61%、86.38%、90.32%。Appendix G（p.19）明确**279 是同一个原始修复集合基线**，每个 agent 测修复后其中哪些仍可触发；不是分别报告每个 runtime 自身 Original 的重跑数量。因此应解读为同一修复跨运行时的可迁移性，不能解释为四个 runtime 独立的完整安全效果比较。

测试统一采用隔离 workspace、受控网络/命令与一致非交互平台权限；这些平台权限不建立 `Auth_p(a)`。不能把系统弹窗帮忙拦住的结果混入论文 semantic guard 的功劳。

Table 12，249 个 legitimate tasks 的效用：

| 策略 | Task completion | Output equivalence | Core trace equivalence |
|---|---|---|---|
| Direct removal | 144/249 (57.83%) | 130/249 (52.21%) | 112/249 (44.98%) |
| SkillScope constraining | 249/249 (100%) | 236/249 (94.78%) | 232/249 (93.17%) |

100% 任务完成只适用于这批有限任务和该评价协议。输出/核心 trace 仍有变化；“任务完成”不等同于所有行为完全保真，更不是所有未见任务都成功。

### 8.6 成本（Tables 7、15；pp.11、18）

| 阶段 | 单位数 | LLM calls | Input M | Output M | Total M |
|---|---:|---:|---:|---:|---:|
| Graph construction | 200 Skills | 200 | 0.358 | 0.111 | 0.469 |
| Consistency screening | 2,113 nodes | 2,113 | 2.217 | 0.170 | 2.387 |
| Task instantiation | 261 chains | 261 | 0.208 | 0.021 | 0.229 |
| Over-privilege validation | 737 cases | 2,211 | 4.205 | 0.184 | 4.389 |
| Constraining | 279 repaired actions | 666 | 1.304 | 0.558 | 1.862 |
| Overall | 200 Skills | 5,451 | 8.292 | 1.045 | 9.337 |

总平均 46.69K tokens/Skill；validation 5.96K/case；repair 6.67K/repaired action。分项显示数字四舍五入，分项和可能与 overall 差 0.001M，不宜据此断言原始账本错误。成本表没有充分说明所有被测 agent 动态执行自身 tokens 是否完整计入；不能把 9.337M 当成本项目模型预算保证，也不能在没有价格及 snapshot 时换算确定费用。

## 9. 关键限制与对 TaskSkillGuard 的诚实适配

### 9.1 原文明示限制

- LLM/agent 执行非确定性会影响 Replay 可比性和最终 verdict（p.14）。
- 高耦合代码的 LLM 辅助分离可能不完美（pp.13–14）。
- fixture 生成是若干工具的 ad hoc 组合，对复杂领域输入、需认证服务不易扩展（p.14）。
- 不在所检查工件或 Replay 中可观察的行为、例如依赖零日漏洞，不在其范围内；需要沙箱、依赖验证、runtime policy/egress 辅助（p.4）。
- 语义 guard 可能被上下文稀释，确有残余风险（p.13）。

### 9.2 审计推论与本项目处理方式

| 风险/缺口 | 应怎样实现与报告 |
|---|---|
| 不可信 metadata/profile 引导候选与任务，可能有漏筛或“自造授权” | profile 仅作行为证据；trusted task ceiling 来源独立。合成 P_high 可以作为研究者审定对照，但永不当真实用户授权 |
| 图只近似工件可见路径；动态调用和缺资源不可确认 | 标 `unresolved_dynamic_call/unsupported`，统计覆盖率；不得把没有运行的样本计为 TN |
| Replay 是实现内干预；中和可能破坏接口/返回值/状态 | 两个全新环境，相同 fixture；保留接口；`invalid_ablation` 单列。参考 Oracle 与独立 workflow 属 TSG 扩展 |
| 以原输出作唯一正确答案可能保留恶意副作用 | Oracle 从可信任务独立定义；CorePres 仅要求请求需要的动作/副作用 |
| 人工 not confirmed 与 confirmed benign 区别不足 | TSG 保持 unknown/abstain 独立桶，报告总分母、有效分母与 unresolved；不能悄悄提升准确率 |
| 有限图任务不代表真实用户任务分布 | 保存 task provenance、chain coverage、触发率；固定可信 low/high/edge 对照；家族分组 holdout |
| 文字 guard 不能强制所有工具调用 | E3 分离 sandbox-only、textual guard、deterministic tool policy；在正确 Oracle policy 和 LLM policy 两种条件下分别测 |
| tool adapter 未必覆盖脚本子进程、原生网络与文件访问 | 将 tool-mediated enforcement 和 OS containment 分开；不能执行真实未知脚本时使用安全 mock/转译并准确标注，不宣称真实原生执行 |
| 论文缺完整 code、prompts、snapshots 和 harness 参数 | 持久化本项目参数、代码 commit、hash、raw trace、ground-truth provenance；称 paper-inspired，不称 exact reproduction |
| 原论文分数不可移植到自有库 | 原文数据只作为 Related Work；本项目所有 P/R/F1/安全/utility 来自实际自己的 JSONL 与独立标签 |
| 正例审计不能估计漏检 | 除候选/正例，还抽审负例；报告检出率与 recall 的不同适用分母 |

### 9.3 最小可审计实验协议

以下是针对手册的实施建议，不是新增已完成工作：

1. 固定只读现有库 snapshot 和 family split；先 pilot 24–30（手册计划），动态子集按可运行性说明，**不为了匹配论文规模重新爬取**。
2. 每条 case 保存可信 task、允许/禁止具体资源、fixture hash、独立 Oracle、source span、人工/规则/模型标签来源。若尚无人类双人标注，清楚标为 preliminary。
3. V0 真正运行 direct LLM 才叫 Raw LLM baseline；若只能规则推断，称 rule baseline，不使用虚构 LLM 响应。
4. V1 保存说明动作、谓词、代码动作、四类边及不可解析项；静态授权和候选筛选分开。若只用正则或简化 AST，报告为 simplification。
5. V2 在相同人工审定任务上比较静态 judge 与 Original/Replay，记录 Auth/CorePres/GoalSat 三值、触发率、重放有效率。每个消融要可运行且保持相同输入预算/任务集合。
6. 论文式 guard 作为单独 baseline；Progent 风格符号控制、CaMeL 风格标签、双账本、lease、metamorphic testing 分开开关。不要将 V3/V4 阻断力误写成检测 F1 必然更高。
7. 记录每次实际尝试、决定、执行与 mock sink 到达；拒绝尝试不等于越权已执行，允许工具不等于允许数据流。只有 mock sink 真的收到指定假秘密才记泄漏成功。
8. 固定完整版本后再评 held-out；重复动态实验反映随机性；按 Skill/family 聚类置信区间。至少保留失败、unknown、unsupported，而不是仅保存漂亮成功例子。

## 10. 全页覆盖账本

下表的“文本+原图”均为本次实际完成。全文初读按 1–2、3–4、5–6、7–8、9–10、11–12、13–14、15–16、17–18、19–21 的分批完整输出读取；图表取值以随后查看的原图校正。

| PDF 页 | 已读章节/关键内容 | 核验方式与审计重点 |
|---:|---|---|
| 1 | 标题、全部作者、版本边栏、Abstract、§1 开头 | 文本+原图；v3、21页身份、三项摘要数字 |
| 2 | §1 例子、挑战、方法概览、贡献 | 文本+原图；任务条件化与检测/修复范围 |
| 3 | §2.1、§2.2 开头，Figures 1–2 | 文本+原图；progressive disclosure、参数化 Auth |
| 4 | §2.2 公式、§3 threat/deployment、挑战 | 文本+原图；OR 判定、CorePres/GoalSat、威胁范围 |
| 5 | Figure 3、§3.1、LLM/幻觉处理、§4.1 开头 | 文本+原图；三组件、证据验证、最多5次总尝试 |
| 6 | §4.1、Figure 4 | 文本+原图；三类节点、四类边、过程内分析、task-ambiguous |
| 7 | §4.1 末、§4.2、Figures 5–6 | 文本+原图；candidate-aware chains、fixture、Original/Replay |
| 8 | §4.2 判定、§4.3 开头、Figure 7 | 文本+原图；trace-grounded Auth、judge、constraint node |
| 9 | §4.3 末、§5.1、§5.2 开头、Table 1 | 文本+原图；语义guard、脚本拆分、样本/环境/主结果 |
| 10 | §5.2、Tables 2–5 | 文本+原图；四模型、261分母、baseline与judge数值 |
| 11 | §5.2 消融/成本、§5.3 开头、Tables 6–7 | 文本+原图；可执行替换消融、5,451调用、生态校准 |
| 12 | §5.3、§5.4 开头、Tables 8–10 | 文本+原图；交集与去重、两模式、472→54 |
| 13 | §5.4、§6 开头、Tables 11–12 | 文本+原图；残余失败、四runtime、249 utility分母 |
| 14 | §6 限制、§7 related work、§8、References [1]–[21] | 文本+原图；非确定性/重构/fixture限制、引用边界 |
| 15 | References [22]–[67]、Ethical Considerations 开头 | 文本+原图；所有参考条目、Progent引用、公开来源伦理 |
| 16 | Ethics 续、Appendix A–C 开头、Table 13 | 文本+原图；脱敏材料声明、图质量、人工图/任务构造 |
| 17 | Table 14、Appendix C 续、D 开头 | 文本+原图；fixtures、完整GT数量、两人+第三人协议 |
| 18 | Table 15、Appendix D 末、E | 文本+原图；cost精确单位、分层抽审与权重 |
| 19 | Table 16、Appendix E 末、F、G、H 开头、Table 17 | 文本+原图；CI、类别、固定279跨runtime基线、平台授权区别 |
| 20 | Appendix H 步骤与工作例 | 文本+原图；normalize/group/synthesize、允许条件 |
| 21 | Tables 18–19 | 文本+原图；descriptor全部字段、unresolved排除、四个任务例 |

**可交付措辞：**“我们完整阅读并核对 SkillScope v3 的正文与附录，依据其公开算法描述实现受限适配；截至 2026-10-15 未核实到对应作者公开实现。我们的图抽取、任务合同、沙箱、Oracle 和工具层控制均按实际实现分别标注来源与差异。原论文成绩仅用于背景比较，本项目成绩由独立保存的实验记录计算。”

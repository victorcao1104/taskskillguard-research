# TaskSkillGuard 冻结前独立代码复核

此页保留第一轮审阅。第二轮结果与修复见 [phase2_code_review.md](phase2_code_review.md)。

**最终状态更新：本报告下方“最终定向复核补充”已独立确认三个 P2 全部修复；全套 49 项测试通过，3,300 次保存执行离线复跑零差异。下列“仍待处理”是前一快照的历史状态，不代表最终实现仍有这些问题。**

审查时间：2026-10-15（Pacific/Auckland）；最后缓存只读快照为 2026-10-14T22:17:11Z。审查对象尚无冻结 commit，以下使用文件 SHA-256 定位。按 requesting-code-review 的独立审查要求执行；未修改实现、数据、真实 API 缓存或账本，未调用 API，所有 HTTP 探针均使用本地 mock。测试临时目录和审查证据仅位于 `tmp/taskskillguard-reading/progent/`。

## 结论

本轮发现的三项冻结阻断已修复并由独立探针确认：相同请求并发覆盖 raw 响应；合同生成结果绕过严格 schema；图节点接受未知 operation／无证据资源。Judge 缺失必需判定键的问题亦已修复。`compare_policies` 每次创建独立 Z3 context 的实现和 90 次并发测试通过。

剩余三个实际边界 bug 已向实现者报告，当前固定 benchmark 未触发后两个，真实 completed 缓存未触发第一个。它们不构成“现有结果已错”的证据，但应在扩大动作目录或通用接口声明前修复。完整测试集正在并行开发 evaluation 模块，本报告不声称全项目最终测试全部通过。

## 仍待处理的问题（本快照）

### P2 — usage 缺失会将成本预留归零

位置：`src/tsg/models.py:51–56`，`Budget.settle`。`usage.get('input_tokens',0)` 和 output 默认 0，故 `{}` 会将正常预留转为 `settled` 且 `cost_usd=0`，释放预算。非负整数／bool 类型也未检查。代码声称保守预算上界，这一失败路径不符合该声称。

独立复现：预留 gpt-4.1-mini 的 100 input tokens，成本 0.00004；`settle(rid,{})` 后成本为 0，并能继续预留。证据：`final_recheck.json` 的 `missing_usage_budget`。不涉及真实调用。

最小修复：只有 input_tokens/output_tokens 均为非负的严格整数时结算；否则保留完整预留并记录 usage_unknown（允许保存返回原文）。若返回成本超过预留，仍按真实成本入账并报告上界估计失效，不能截断成本。

当前数据影响：只读清点的 1,618 条 completed raw 全部拥有非负整数 usage，未发现本问题已导致费用少记。

### P2 — 删除输出后仍能得到 goal_satisfied=true

位置：`src/tsg/sandbox.py:93–95,116`。file.write 同时写 `files` 和 `outputs`，file.delete 仅删除 `files`，utility 却读取 `outputs` 中的历史写入值。

独立复现：取现成 low case，在合法 read/transform/write 后追加删除该 `output_path` 的动作，mode=none。删除事件 executed=true，但返回 outputs 仍含 TOTAL=5，goal_satisfied=true。证据：`final_recheck.json` 的 `deleted_output_goal`。

最小修复：`outputs` 明确定义为最终可见输出，并在删除时同步删除；或从最终 `files` 状态计算 utility，另设 write_log 保留历史事件。此问题会抬高允许“先写后删”动作的 utility、replay/Judge 输入，但当前固定目录的删除攻击针对 unrelated 文件，不能据此断言已跑指标错误。

### P2 — 独立执行评分忽略 forbid

位置：`src/tsg/sandbox.py:106–109`。`authorized_by_gt` 只检查是否存在匹配 allow，不排除同一 operation/resource 上有效的 forbid，与 Policy 的拒绝优先语义不同。

独立复现：给现成 low case 的 policy 加同资源 file.read forbid，mode=none 读取仍被 `authorized_by_gt=true`，unauthorized_executed=false。证据：`final_recheck.json` 的 `forbid_oracle`。

最小修复：在独立评分器内实现相同的 allow/forbid、时间窗和实际次数语义；保持独立于被测 Guard 的 verdict，避免直接把 Guard verdict 当真值。当前生成的 task policy 没有 forbid，故影响通用正确性和未来扩展，不是现有固定 case 的已证实分数变化。

## 已修复并复核的问题

| 问题 | 修补位置 | 独立复核结果 |
|---|---|---|
| 同 fingerprint 并发请求可发两次、只留下最后一份 raw，结果 request_hash 无法唯一对应返回响应 | `models.py:97–111,137–139` 每个 fingerprint lock、临时文件原子替换 | 8 workers、16 次同请求调用：1 次 mock HTTP、1 reservation、1 raw、全部返回 mock-1、0 个残留 tmp |
| contract 接受 supported:false、default_action:allow、同资源全 forbid，仍 valid/exact_scope=true | `run_experiment.py:66–78` 顶层和每条规则严格 schema | 原反例现在 status=unresolved，不再有 exact_scope |
| graph 接受任意 operation 和凭空资源，只要行号存在 | `graph.py:84–105` 操作枚举、精确整数行号、资源字面量存在于引用行 | 未知 operation 和不存在的 resource 两节点均 invalid；已出现资源和显式 unknown 保留 |
| Judge 用 obj.get 令缺失键等价于 null | `run_supplement.py:69–71` 必须包含三键 | 仅 reason 的 JSON 现在 status=unresolved |
| 默认 Z3 context 在线程间共享 | `policy.py:87–100` 每 call context、所有 AST／空 disjunction／solver 使用该 context | 项目中 90 次并发比较测试通过 |

这些锁只保证当前使用方式（一个进程、一个共享 Client），与 Budget 的“一进程 writer”约束一致。没有证明多进程或多 Client 同目录安全；报告应保留这一运行约束。

graph 新验证证明节点 schema 和 literal/span 定位成立，不证明 operation、summary 或 DATA/CONTROL 边的语义真实。当前图被明确命名为 partial static graph；不要把通过校验等同于完整 CFG 或可执行性证明。

## 现有缓存／审计记录

在修补前，离线 barrier mock 曾明确复现两个调用、两个 reservation、一份 raw、两个不同返回 response ID。原证据保留在 `final_probes.json`。修补后的证据保留在 `final_recheck.json`，不能混用两份结果。

最后一次只读快照为：1,632 个 reservation、1,618 份 raw；14 个 reservation_id 暂无 raw，其中 2 settled、12 reserved，账面累计成本／预留 0.0198129 美元。并行实验仍在运行，reserved 项可能只是进行中的请求；这个快照不能证明 14 份响应丢失，也不能单凭它确定 settled 两项的原因。所有旧账本项必须继续计费，不应为使数量一致而删除。应保留历史执行结果归档、说明正式结果从最终 raw 重建，并记录无法映射到 raw 的历史请求。

快照只输出数量和状态，未输出请求内容或凭证；文件为 `cache_ledger_readonly_audit.json`。

## 真正的研究限制，而非新安全漏洞

- 这是有限 DSL 的 capability VM：内存文件、固定 transform、mock sink，无宿主文件／进程／网络。未知操作不会调用真实系统。不能声称 OS sandbox、第三方脚本动态执行，或完整复现上游 Progent。
- `post_task_reuse` 的 actions 中声明 step=21 已不控制时钟；真实 enumerate 的 late step=3，expires=3 为包含边界。现有拒绝由 max_uses=1 导致。只把 max_uses 改成 2，即可看到 late read 获准。这是次数耗尽证据，不是独立的时间到期证据。应分别做 quota 与 expiry 探针，不能改称已跑场景证明二者。
- named family 不是完全独立实现：csv（development）与 database（held-out）共用 CSV 输入、expected_output、transform 分支。家族切分可以称命名任务族切分，不能声称全新计算模板上的泛化。组数少、模板同质应限制 CI 和外推解读。
- 实际原始、neutralized、reference 均现在执行 VM；reference 是研究者固定可信任务模板，仍不是独立人类 ground truth 或通用 necessity 证明。
- transfer 为真实 source bundle 上的研究者假设任务，`human_annotated=false` 明确。不能据此报告真实用户授权 F1。只选择前 12 个静态节点，且 high context 若选中 secret.read，可能与“Never access credentials”形成歧义；应保留 unknown／歧义统计，不称统一正例。

## 验证与范围

完整阅读并复核：`src/tsg/policy.py`、`sandbox.py`、`models.py`、`graph.py`、`scripts/run_experiment.py`、`scripts/run_supplement.py`、相关 tests／prompts／design。

离线项目测试：显式使用本审查 scratch 作为 basetemp、关闭 pytest cache、排除仍开发的 `tests/test_evaluation.py`，结果 **34 passed in 0.91s**。此前不排除 evaluation 的运行在收集阶段出现 `No module named tsg.evaluation`，不是 34 项失败。没有执行依赖 API 的实验，也没有篡改 cache 后重跑。

重现独立探针：在 `taskskillguard-research` 工作目录运行 `.venv/Scripts/python.exe ../tmp/taskskillguard-reading/progent/final_recheck.py`。全部写入自身 scratch，HTTP 全部 mock。

复核快照 SHA-256：

| 文件 | SHA-256 |
|---|---|
| src/tsg/policy.py | BE65CD836F9DA8330170959FCC9A6AC42F8DDBA57A24C057F4A1EA484A3EF788 |
| src/tsg/sandbox.py | 424EC018646426E1222663DBEBD02298C827002D8AF988D1E50C51D697173573 |
| src/tsg/models.py | 1DBF7E0EE64029C9C3D4CECEE0C79098EE642D108D1A11ADF89E6584E1E6272E |
| src/tsg/graph.py | 29636B5DF8913F46D768DB80AE8650DC85DFFC812BB74A451094266883CDCC13 |
| scripts/run_experiment.py | C125B0706EFA86959F9A9B962DCE7B1385FD374398C67E34B653BA19B86B209E |
| scripts/run_supplement.py | 82D9AFAA04AD424383844C788C9AD253D93F9A16DC479034BA377BFD89DDB71B |

审查过程中实现者可并行继续改动；上述结论只对应所列 hash。后续修补需要更新验证记录，不能仅以本文替代最终冻结检查。

## 最终定向复核补充（2026-10-15）

结论：前述三个 P2 均已关闭。没有发现阻断当前有限合成实验交付的新问题。此次仍未调用 API，也未修改项目实现、报告、结果、真实缓存或账本；仅更新本审查 scratch。

### 三项修补的独立反例复跑

| 原问题 | 当前实现 | 独立实测 |
|---|---|---|
| 缺失 usage 将费用预留归零 | `models.py:54–58` 要求完整、非负严格整数用量；不满足则 `unknown_usage` 并保留预留 | 0.00004 美元预留经 `{}` 结算后仍为 0.00004，状态 unknown_usage；项目测试亦覆盖负 usage |
| 删除产物仍算目标成功 | `sandbox.py:95` 同步移除最终 outputs | 追加实际删除事件后 outputs={}、goal_satisfied=false |
| oracle 忽略 forbid | `sandbox.py:109–112` 独立检查匹配 forbid，覆盖 allow | read_authorized=false、unauthorized_executed=true |

此前的同 hash 单进程并发、contract／graph schema、Judge 必需字段探针也再次通过。`final_recheck.json` 已更新为最终修补后的结果；前述历史失败应参阅 `final_probes.json`，不可将旧失败误当成当前状态。

### 完整测试、原始运行稳定性与费用

本次不排除 evaluation：使用独立 scratch basetemp、关闭 pytest cache，完整项目测试 **49 passed in 1.04s**。没有声称亲自观察开发者的先红后绿历史；本审查直接观察的是最终完整通过及独立反例结果。

独立逐字段重跑了 1,188 条 mechanistic 和 2,112 条 model-plan，共 3,300 次。对 mechanistic 的新返回值只补回旧记录的 `ablation` 非执行标签，执行配置仍直接取原保存 `settings`；之后仅剔除 `state_id`／`elapsed_seconds`。所有其余字段（含嵌套 events、outputs、settings、reference）比较，**差异为 0**。未改写项目 `results/verification/runtime_stability.json`。独立证据另存本目录 `final_stability_recheck.json`。

只读费用复算与报告一致：

- reservation 2,632；raw 2,624；settled 合计 USD 1.3559874；加保留预留后的上界 USD 1.3650669。
- 无 raw 的历史记录为 2 settled（USD 0.0005304）及 6 reserved；全部仍在账本中。
- 这些数值是所列代码价格表上的保守估算，不是独立平台账单核验。

### final_report.md 主张核对

报告明确说明：V0 在此数据优于 V1；模型图验证不等于语义精度；不是 OS sandbox；不执行第三方原始脚本；运行时使用固定 oracle policy，非端到端自主 Agent 成绩；合成标签非 human GT；named family 与计算模板重叠；quota 与纯时间 expiry 证据不同；真实样本无人工准确率；保留两条 settled 缺 raw。未发现会推翻当前结论的明显主张错误。

向实现者提出两处小修辞修正，不要求新增 API 或改变实验：

1. 报告开头“完成三篇论文全文/附录及官方源码核验”容易暗示 SkillScope 官方源码也已核实，与其后表格“未核实官方实现”相矛盾。建议明确为三篇审读、Progent／CaMeL 可取得源码核验、SkillScope 官方实现未核实。
2. `check_runtime_stability.py` 原实现的 normalized 还剔除 `ablation`，而 JSON 描述称仅剔除 UUID/耗时。该字段只是记录标签、settings 已完整比较，故不是成绩差异；建议修正措辞或像本独立复跑一样带回标签再比较。独立零差异结果不依赖忽略此字段。

本轮快照 SHA-256：

| 文件 | SHA-256 |
|---|---|
| src/tsg/models.py | 65AC0B18836CE35C384B879D58AF3502C318F02D0C2283AF07E7B9D7888ADF8D |
| src/tsg/sandbox.py | C2DBFBF68A45AF6C8BB68C5070C80565B00A048E18DB2E8C81B1B3CDF9BBDA85 |
| scripts/check_runtime_stability.py | AF91D669F107F83DDD4142AEAAA5E657C2BCF26DD6513B3E64436B8F20ECC166 |
| docs/final_report.md | 1827C729B180DEC3866BA557D41CB88551B3E8031DA7F6DD854BFEDC5BBE47BC |

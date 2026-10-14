# CaMeL 全文与官方代码独立核验

核验日期：2026-10-15（Pacific/Auckland）。本文件仅报告实际阅读、静态检查与本地纯测试；没有调用任何模型 API，没有读取真实凭证，没有运行完整 AgentDojo，也没有修改上游受版本控制的文件。

## 1. 结论与可声明范围

**状态：official-code-available + code-tested（解释器子集）；尚非完整 benchmark reproduction。**

- 已逐页阅读用户 PDF 的全部 32 页，包括参考文献和附录 A–H；另渲染并核对第 2、5、7、17、18、22 页的关键图表。逐页账本见末节。
- 官方仓库成功克隆；固定 commit 为 `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`。许可证为 Apache-2.0。
- 上游 `tests/test_camel_lang`：**106 passed**。这是解释器语法、表达式等单元测试，不能推导整套防御安全或模型评测复现。
- 本审计新增 21 个无模型探针：**15 passed，6 failed**。失败包括容器/模拟 Q 调用的标签保留反例，以及 3 处实现语义不符。保留全部失败，不以跳过或修复上游代码掩盖结果。
- 建议 TaskSkillGuard 借鉴 P/Q 隔离和信息流设计，但现阶段不得把该仓库直接视作经过安全验证的执行基础；应逐项建立回归测试后再适配。

## 2. 论文版本与数据边界

输入文件：`C:/Users/victo/Downloads/Defeating_Prompt_Injections_by_Design.pdf`。

- SHA-256：`b2839e0a00862b86f06552531d1291cc083a51a6c3276bb0c8b1304ada68d53e`。
- 首页是 **2026 IEEE Conference on Secure and Trustworthy Machine Learning (SaTML)** 正式发表稿；DOI：`10.1109/SaTML68715.2026.00040`；印刷页码 587–618，对应 PDF 页 1–32。
- 手册把 CaMeL 来源标为 arXiv v2（2025-06-24）。本次实际阅读的对象应改记为这份 SaTML 2026 文件。没有逐字符对比 arXiv v2，不能假设二者完全相同。
- 正文主要术语为 **flow tags**；图 3 仍有 capabilities 字样，代码类名为 `Capabilities`，这不意味着能力令牌、租约或 OS 权限沙箱。
- 本文以下页码均指 **PDF 页码**，必要时同时标出论文节号。

### 2.1 论文机制的准确概括

1. **可信规划与不可信数据处理分离**（§V-A，页 4–5）：P-LLM 接收用户任务、受信工具/类型说明，输出受限 Python 程序；不读取工具原文与 Q-LLM 返回内容。Q-LLM 仅把非结构化数据解析为指定 schema，无外部工具调用权限。
2. **Q-LLM 不是事实或授权 oracle**：其结果仍可能被攻击者操纵。`have_enough_information=false` 触发 `NotEnoughInformationError`，Q 不可用自然语言向 P 传递“缺什么信息”，以免重新打开注入通道。
3. **来源与读者标签**（§V-C，页 6）：来源可为 User、CaMeL 或工具及内部来源；readers 可为 Public 或读者集合。依赖图让派生值继承输入限制。只有双模型隔离仍会被参数操纵绕过（§II，页 2–3）。
4. **解释器与策略**（§V-B/D，页 5–6）：使用 Python AST 自行解释一个受限语言；工具执行前检查策略。策略是 Python 函数，不是 Progent 风格可比较的符号 DSL。
5. **修复循环**（页 6、附录 H 页 31–32）：P 最多尝试 10 次；仅可信异常内容可反馈，不可信异常文本须删除。已定义变量和标签保留，之前有副作用的调用不回滚；提示模型不要重复调用并不构成事务原子性。
6. **NORMAL 与 STRICT**（页 6–7、18、20–21）：STRICT 对控制依赖及 Q 调用之后的语句进行更保守传播，用于缓解异常引起的终止侧信道；并不证明消除所有侧信道。

### 2.2 不能省略的限制

- 威胁模型信任用户提示，并假定用户未把不可信提示粘贴进来、记忆未受攻击（§IV，页 4）。将 Skill 原文送入 P 的可信提示将改变这个前提。
- 不防止不改变受保护流向的错误摘要、答案污染或面向用户的钓鱼内容（§IV-A，页 4）。来源 UI 可帮助识别，并非内容正确性保证。
- “按邮件里的指令做事”属于 P 无法直接规划的任务；把工具分派循环写入计划会让数据选择控制流（§VI-A，页 7；附录 D，页 19–20）。
- 异常终止、工具直接操纵、共享资源与可能的时序侧信道仍是限制。time 模块未开放，只排除了附录中的那个特定示例（附录 E，页 20–21）。
- 策略制定、解密/降级授权和用户疲劳仍需解决；安全性依赖标签和策略质量（§VII，页 11）。
- 形式化验证解释器属于未来工作（§VIII，页 12）；附录 F 给出安全游戏，不等于已经机械化证明实现无漏洞。`Ω_prompt` 是安全定义中的允许动作集合，脚注明确它不是 CaMeL 的实际设计组件；图 17 的全局策略也不等于 TSG 的任务权限合同（页 21–22）。

### 2.3 原论文结果与内部差异

这些数字全部是**论文报告值**，不是本项目实测：

- 摘要 77% 对 84% 对应表 I 的 o3 High：CaMeL 77.3% ±8.3、原生调用 84.5% ±7.2（页 1、16）。不同模型下降幅度差异较大，不能把最佳模型结果当全模型平均。
- 图 6 的攻击总量为 949（页 9）。表 III 中，o3 High + CaMeL 为 0，Gemini 2.5 Pro + CaMeL 为 0；Claude 4 Sonnet + CaMeL 仍有 travel 非零项；**o4 Mini High + CaMeL 的 banking 也列 1±0.0**（页 17，已核对渲染图）。正文 §VI-B2 把剩余成功解释为 travel 展示评论的非注入目标，并不完全解释这条 banking 记录。应保留差异、标为待作者/原始轨迹核对，不能写成“所有模型所有任务 ASR 都为零”。
- 正文 §VI-D 与图 9 称输入中位数 2.82×、输出 2.73×（页 11–12）；表 VII 列 Input 2.73、Output 2.82（页 18）；表 X 标为 under attack，又列 Input 2.02、Output 2.64（页 19）。此外图 9 与图 13 的有无攻击说明也需结合原始统计确认。保留表号和场景，不自行选一个数字统一覆盖。
- 表 VI（Claude 3.5 Sonnet 对照）的 Spotlighting 成功攻击数为 5，Tool Filter 为 8（页 17）；正文页 9 称下一最佳为 Tool Filter/8。不能根据正文一句话重写表格排名。
- 页 13 说明作者复用轨迹评估有/无策略，降低模型调用数；代码也确实提供 replay-with-policies 路径。这不等价于重新让模型在每次策略拒绝后自主重新规划。

## 3. 仓库固定信息、许可证与依赖

官方地址：[google-research/camel-prompt-injection](https://github.com/google-research/camel-prompt-injection)。在线 README 与本地仓库均已核对。

| 项目 | 核验结果 |
|---|---|
| 本地位置 | `tmp/taskskillguard-reading/upstream-camel` |
| HEAD | `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` |
| commit 时间 | `2025-06-20T15:59:27+02:00` |
| commit 标题 | `Update README.md, add .env template` |
| 许可证 | Apache License, Version 2.0，`LICENSE` |
| 项目声明 | `camel` 1.0.0，`pyproject.toml` |
| Python 声明 | `requires-python >=3.10`；`.python-version` 为 3.10.12 |
| 本次运行时 | CPython 3.12.14 / Windows，隔离目录 `.audit/.venv` |
| 论文链接的代码版本 | 页 18 链接指向 `45b656a0aaf688626955b12823ec0bd6af9f7df7` |

HEAD 与论文所链 commit **并非只有 README 不同**：`main.py`、`models.py`、`privileged_llm.py`、`custom_yaml.py` 等也有差异。P-LLM 文件差异包括移除两个旧 Google 模型的 Q fallback。核心 interpreter/capabilities/security policies 文件在两 commit 间未显示变更。本次证据全部以 HEAD 为准。

README 明确称其为研究 artifact，解释器可能有 bug，也可能并非完全安全；不属于受支持的 Google 产品且不计划维护。本次发现与这一限定一致。

### 3.1 顶层依赖与 lock 中版本

| 依赖 | pyproject 下界 | uv.lock 版本 |
|---|---:|---:|
| agentdojo | 0.1.34 | 0.1.34 |
| anthropic | 0.51.0 | 0.52.2 |
| cyclopts | 3.16.1 | 3.16.2 |
| pydantic-ai | 0.2.4 | 0.2.12 |
| pydantic | 2.11.4 | 2.11.5 |
| tiktoken | 0.9.0 | 0.9.0 |
| google-genai | 1.15.0 | 1.18.0 |
| openai | 1.78.1 | 1.82.1 |
| vertexai | 1.71.1 | 1.71.1 |
| jsonref | 1.1.0 | 1.1.0 |
| openapi-pydantic | 0.5.1 | 0.5.1 |

本次只安装纯解释器测试所需子集：pytest 8.3.5、pydantic 2.11.5、pydantic-ai-slim 0.2.12、typing-extensions 4.14.0 及其依赖。未完整安装 agentdojo 和模型 provider extras。精确实际安装包在 `.audit/installed.txt`；不是“完整 uv sync --frozen 环境”，也未声称所有间接依赖都与 lock 一致。

## 4. 代码入口与论文映射

以下位置均在固定 HEAD。可通过 [固定版本源码树](https://github.com/google-research/camel-prompt-injection/tree/f083b6b396399d3b3c7f2ddaf613a5945eaf32d8) 核对。除 `main.py` 和已写出 `src/camel/` 的路径外，本节源文件路径默认相对于 `src/camel/`。

| 要核验的机制 | 真实代码路径、函数与行号 | 结论 |
|---|---|---|
| 实验入口 | `main.py:27 main`；`src/camel/models.py:88 make_tools_pipeline` | AgentDojo v1.2、important_instructions 攻击、模型和 replay 参数；本次未执行 |
| P-LLM | `pipeline_elements/privileged_llm.py:200 PrivilegedLLM`；`:286 _generate_and_interpret_code`；`:402 query` | 独立 `privileged_llm_messages`，初始仅系统提示/用户查询；工具结果进入记录消息，而不加入 P 的上下文 |
| Q-LLM | `quarantined_llm.py:37 query_quarantined_llm`；P 的 `query` 内注册 `query_ai_assistant` | 构造 Pydantic 输出模型及 have_enough_information；`pydantic_ai.Agent` 未注册外部工具；`run_sync` 是真正模型调用点，本次没有执行 |
| 异常隔离 | `privileged_llm.py:86 format_camel_exception`；`:114 make_error_messages` | 通过 is_trusted 判断异常文本是否删除；类型与代码位置仍反馈；状态保留 |
| 执行入口 | `interpreter/interpreter.py:2689 parse_and_interpret_code`；`:2403 camel_eval` | 代码块提取→ast.parse→按节点解释；不是直接 exec 整段模型代码 |
| 能力结构 | `capabilities/capabilities.py:24 Capabilities` | sources_set、readers_set、other_metadata；default() 为 User/Public，camel() 为 CaMeL/Public |
| 来源/读者类型 | `capabilities/sources.py:22 SourceEnum`、`:30 Tool`；`capabilities/readers.py:22 Public` | 包括 User、CaMeL、Assistant、TrustedToolSource；工具可有 inner_sources；Public 与集合交操作返回集合 |
| 传播查询 | `capabilities/utils.py:14 get_all_readers`、`:40 get_all_sources`、`:71 is_trusted` | 递归查询：读者交集、来源并集；必须注意本审计发现的容器反例 |
| 值与依赖 | `interpreter/value.py:50 CaMeLValue`；`:95 new_with_dependencies`；`:186 CaMeLCallable`；`:207 wrap_output`；`:1343 value_from_raw` | 原始 Python 值包装为 CaMeLValue；返回值依赖 self/args/kwargs；具体成员保留仍需测试 |
| 工具返回初始标签 | `pipeline_elements/agentdojo_function.py:121 _get_metadata_for_ad`；`:209 AgentDojoFunction`、`:240 wrap_output` | 使用 AgentDojo 数据类型/工具名确定初始标签；不是由 LLM 自行证明可信 |
| 邮件/云盘等标签 | 同文件 `:40 _get_calendar_event_metadata`、`:51 _get_cloud_drive_file_metadata`、`:61 _get_email_metadata`、`:74 _get_transaction_metadata` | 邮件来源为发送者，读者为 sender/recipients/cc/bcc；云盘来源为 owner+rw编辑者，读者来自 shared_with；银行 me 映射 User |
| 工具前策略调用 | `interpreter/interpreter.py:1991 _eval_call`，尤其 2050、2060 | 先 check_policy，再调用工具；拒绝抛 SecurityPolicyDeniedError；内建/类/特定函数类型有豁免 |
| 策略引擎 | `security_policy.py:73 SecurityPolicyEngine`、`:77 check_policy` | no-side-effect 白名单直接允许；检查非公开控制依赖；**首个匹配规则**直接返回；无匹配默认拒绝 |
| 无策略模式 | `security_policy.py:99 NoSecurityPolicyEngine`；`pipeline_elements/security_policies/agentdojo_security_policies.py:38 ADNoSecurityPolicyEngine` | 始终允许，不能据此宣称权限防御开启 |
| 具体策略 | `pipeline_elements/security_policies/{workspace,banking,slack,travel}.py` | 本次深入阅读 workspace 的发送/删除/日历入口和 banking；其余并未逐行全审 |
| STRICT | `interpreter.py:637 _assign_name`、`:1665 _eval_if`、`:1753 _eval_for`、`:2067 _eval_call` | 严格模式给赋值附加上下文依赖；Q 调用输入进入后续依赖；不是“关闭所有隐式流”开关 |
| replay | `pipeline_elements/replay_privileged_llm.py:129 replay_task`；`:273 PrivilegedLLMReplayer` | 读取保存的 Q 返回/计划，重新过策略；与完整新生成执行应区分 |

代码审阅范围是这些入口、核心传播/解释路径与相关测试；**没有声称每个源文件逐行审计**。

### 4.1 语言限制与默认配置的实际含义

附录 G（页 31）禁用 import、eval/exec、while、generator、break/continue、def/lambda 和有副作用的列表/字典方法。解释器在 `camel_eval` 中拒绝相关节点；有限的内建函数与类从 namespace/library 提供。内建 `print` 面向用户，不能自动当成对外 sink。

运行 `main.py` 的通常非 replay 路径（`models.py:191–203`）构造 `PrivilegedLLM(llm, ADNoSecurityPolicyEngine, q_llm or model)`。因此默认采集轨迹**没有策略限制**。`--replay-with-policies` 才走 suite policy engine 的重放路径。普通路径也没有把传入的 `eval_mode` 继续传给 `PrivilegedLLM`，其构造默认是 NORMAL；不能以为只给 CLI 设置 STRICT 就已在首次执行中生效。

## 5. 已运行的本地验证

### 5.1 环境建立与失败记录

1. 初次默认权限 clone 失败，错误为 `getaddrinfo() thread failed to start`；经允许的网络升级成功获取公开仓库。
2. 在仓库 `.audit/.venv` 创建 CPython 3.12.14 隔离环境。先固定核心四个包，间接依赖选到了新版本，导致 `opentelemetry._events` 导入失败，pytest **11 个收集错误**。
3. 对照官方 `uv.lock`，将已装且在 lock 中的包按该版本对齐（关键包括 opentelemetry-api 1.33.1、logfire-api 3.16.1、griffe 1.7.3）；不改上游源码。随后同一上游测试目录通过。
4. 另一次 `uv pip freeze` 因默认缓存目录不可写失败；改用隔离 Python 的 `importlib.metadata` 读取包清单成功。该失败不涉及测试或模型访问。

证据目录：`tmp/taskskillguard-reading/upstream-camel/.audit/`。

| 文件 | 证据 |
|---|---|
| `upstream-pytest-initial-failure.txt` / `upstream-junit-initial-failure.xml` | 11 个收集错误的原始输出 |
| `upstream-pytest.txt` / `upstream-junit.xml` | 106 passed；pytest 控制台 1.80s；JUnit suite time 1.537s |
| `test_capability_probes.py` | 16 个机制探针，包括参数化实例；其中 15 通过、1 失败 |
| `test_known_discrepancies.py` | 5 个预期语义探针；5 失败，未修饰为 xfail |
| `probes-pytest.txt` / `probes-junit.xml` | 合计 21 tests，15 passed，6 failed；控制台 1.13s |
| `minimal-locked-requirements.txt` | 对齐时使用的最小依赖约束 |
| `installed.txt` | 实际最终安装包清单 |
| `evidence.json` | Python 版本、PDF hash、JUnit 计数摘要 |

### 5.2 通过的机制探针

- 整数派生值来源取并集、readers 取交集。
- 受检字符串 `.lower()` 仍保留私有来源与读者限制。
- if 分支给常量赋值：NORMAL 中结果可公开；STRICT 中受私有条件约束。
- STRICT 下模拟 Q 调用输入影响后续常量赋值；仅使用本地 lambda，没有真正调用 Q。
- 自定义本地 sink：允许读者可调用、未授权读者被阻止，拒绝发生在 mock 副作用之前。
- 未知外部工具默认拒绝；私有控制依赖阻止公开参数的副作用；内建 len 不要求外部工具策略。
- import、while、lambda、eval 被拒绝；策略规则以首个匹配规则为准。

### 5.3 失败与风险的准确分层

**A. 容器元素自身标签未被完整纳入查询——本地直接反例。**

`CaMeLIterable.get_dependencies`（`value.py:262`）与 `CaMeLMapping.get_dependencies`（`:345`）追加的是成员的依赖，而不是成员对象本身。直接以私有标签且无上游依赖包装的 `MOCK_SECRET`，放进解释器表达式 `[secret]` 后，容器 `get_all_readers` 返回 Public；NORMAL、STRICT 两个参数化例子均失败。STRICT 没有私有控制上下文时不能弥补这个问题。通过继承上游 `CaMeLCallable` 的 mock Q 调用，在 NORMAL 中也观察到返回值没有保留该输入的私有标签（第三个失败）。

这是**可运行的局部标签保留反例**；没有执行真实网络外传，也没有运行真实 AgentDojo/Q-LLM，不能将其描述为已复现完整攻击。其根因证据足以要求适配前补足容器、参数打包、模型摘要与重新包装的传播回归测试。

**B. `base_security_policy` 对公开参数错误拒绝——直接调用反例。**

`security_policy.py:64–66` 没有解包 `get_all_readers` 的 `(readers, visited)` 二元组，而将整个二元组与 Public 比较。只传一个公开参数也返回 `Denied('Data is not public.')`。这是保守误拒绝；该函数与具体 suite policies 是否共同使用要按调用路径判断，不应扩大成所有默认策略都存在该问题。

**C. `is_trusted(..., trusted_set=...)` 参数没有实际参与判定——直接调用反例。**

`capabilities/utils.py:71–73` 设置了局部 trusted_set，但 `_source_is_trusted` 只使用模块 `_TRUSTED_SET`。显式将允许集合缩至 `{CaMeL}` 后，User 值仍被判可信。本次验证的是接口语义；现有多数调用未传自定义集合，不能据此断言所有 suite 已受同样影响。

**D. 邮件删除策略条件反向——精确函数体探针。**

`workspace.py:121–131 delete_email_policy` 的注释要求用户直接提供 email_id，但代码在 `is_trusted(email_id)` 为真时返回 Denied，反而在其他情况返回 Allowed。为避免安装完整 AgentDojo，测试从原文件 AST 提取并执行该方法体，仅移除类型注解，未改逻辑。用户标签的模拟 ID 得到 Denied，测试失败。此项是**方法体级验证**，不是完整 adapter 集成测试；也未实际删除邮件。

**E. 另有静态核对点，尚未做完整运行验证。**

- `_get_metadata_for_ad` 将 `_UNTRUSTED_TRAVEL_TOOLS` 的 dict 返回值标成 `Tool(... inner_sources={User})`（`agentdojo_function.py:156–160`），与集合名称/评论语义存在冲突，需结合实际返回结构检查。
- `WorkspaceSecurityPolicyEngine.send_email_policy` 在收件人 `is_trusted` 时直接 Allowed（`:78–79`），不会继续检查正文/附件读者；这相当于一种明确的可信目的地放行规则。附录 B 的简短“收件人来自用户且内容可读”文字不足以替代真实分支逻辑。TSG 应明确自己是否允许这种降级授权。
- `SecurityPolicyEngine.check_policy` 的说明提到任意规则 Allowed，而实际为第一个匹配即返回；本次探针确认了后者。不能把多条策略理解为逻辑 OR 合并。

### 5.4 复查命令

在 `upstream-camel` 内使用现成隔离环境，可无模型运行：

```powershell
$env:PYTHONPATH = (Resolve-Path 'src').Path
& '.audit/.venv/Scripts/python.exe' -m pytest tests/test_camel_lang -q
& '.audit/.venv/Scripts/python.exe' -m pytest .audit/test_capability_probes.py .audit/test_known_discrepancies.py -q
```

第二条预期保留 6 个失败；它不是“全部通过”的发布验收。原始 `.audit/installed.txt` 应随复现材料保存。未执行模型配置、完整 main.py、外网工具任务或任何真实 side effect。

## 6. 对 TaskSkillGuard 手册的直接修订建议

1. 将资料状态改为“SaTML 2026 PDF 全文已读；官方源码固定 HEAD；解释器子集已测试并发现失败反例”，替换笼统的“尚未 clone/test”。
2. 在 WP-08 中把 P 的输入限制到可信任务和工具目录；Skill Action Graph 与 Skill 自称权限均作为不可信证据，不能因被抽成 JSON 就标成 User。P 生成的字面量被上游默认标为 User，是依赖隔离前提的设计，并非证明内容来自人类。
3. TSG 自有来源标签必须覆盖容器成员、字符串拼接、格式化、解析、模型摘要、参数打包、错误/重试和所有外发字段。先加入本次反例作为必须通过的回归测试。
4. 只在真实 side-effect adapter 外层拦截，明确默认拒绝、首条规则/组合语义和批准后的降级范围；避免误用 `NoSecurityPolicyEngine`，并验证实际运行的模式参数已传到解释器。
5. 把“Q 无工具”“P 不见原文”“标签保留”“sink 校验”分别做隔离测试；仅在 prompt 中宣称数据不可信并不满足 CaMeL 机制。
6. TSG 的任务合同、必要性证据、SMT 扩权检查、租约与元变形验证属于组合/新增机制。CaMeL 本身不提供这些模块，不能把附录 F 的 `Ω_prompt` 当成已经实现的 task ceiling。
7. 保留原论文的受限保证与未解决项，不声称代码已形式化验证、不声称系统没有提示注入、不把论文表格当成本次 TSG 数值。

## 7. 逐页实际阅读账本

T = 已阅读该页全部提取文本，含正文、脚注、图表标题与可提取表格；V = 另渲染查看整页。未声称逐像素审查所有页面。提取源为 `tmp/taskskillguard-reading/Defeating_Prompt_Injections_by_Design.txt`，按显式 PAGE 标记分块顺序阅读，截断块另行补读。

| PDF页 / 印刷页 | 覆盖内容与核对要点 | 状态 |
|---|---|---|
| 1 / 587 | 封面作者、摘要、DOI、§I、§II开头；77%/84% | T |
| 2 / 588 | 图1–2；Dual LLM 的数据流不足、Bob 文档示例 | T+V |
| 3 / 589 | 标签/依赖图解决数据流；批准脚注；§III相关工作 | T |
| 4 / 590 | §III续、§IV威胁模型/非目标、§V组件、Q不足信息机制 | T |
| 5 / 591 | 图3、P/Q隔离、P提示、隐私、Python策略函数 | T+V |
| 6 / 592 | §V-C flow tags、来源/readers；解释器、NORMAL/STRICT、异常/状态、§VI | T |
| 7 / 593 | 图4严格依赖图；模型列表；utility三种失败模式 | T+V |
| 8 / 594 | 图5；低成本Q；§VI-B无策略/有策略安全评估 | T |
| 9 / 595 | 图6与949攻击；余下成功解释；触发率；baseline比较 | T |
| 10 / 596 | 图7–8；触发率仅统计成功任务；RTBAS/PFI对照 | T |
| 11 / 597 | §VI-D开销；§VII疲劳、侧信道、ROP类比与未解决项；§VIII开头 | T |
| 12 / 598 | 图9；替代语言、形式化验证未来工作、上下文策略/Progent、结论 | T |
| 13 / 599 | LLM使用与复用轨迹说明、致谢、参考文献[1]–[25] | T |
| 14 / 600 | 参考文献[25]续–[59]，含Progent/IFC/安全基础 | T |
| 15 / 601 | 参考文献[60]–[61]；附录A安全概念；图10；附录B银行策略 | T |
| 16 / 602 | 表I–II所有模型/套件结果；银行续、Slack、Travel策略 | T |
| 17 / 603 | 表III攻击数、IV–V utility、VI baseline攻击数；非零项/排名差异 | T+V |
| 18 / 604 | 图11 NORMAL图；Workspace策略；代码固定commit；表VII–IX | T+V |
| 19 / 605 | 图12策略例子、图13开销、表X；附录D开头 | T |
| 20 / 606 | 附录D数据变控制；附录E异常终止侧信道、图14、STRICT缓解 | T |
| 21 / 607 | 图15时序侧信道/未开放time；附录F安全游戏/Ω脚注 | T |
| 22 / 608 | 图16 PI-SEC/Verify、图17 CaMeL伪代码与全局策略说明 | T+V |
| 23 / 609 | 附录G P系统提示、内建类型/函数、type返回字符串 | T |
| 24 / 610 | 支持方法白名单、datetime等类与方法 | T |
| 25 / 611 | datetime类续、Pydantic方法、EmailStr；send_email签名 | T |
| 26 / 612 | 邮件参数/附件、删除/收发/搜索函数、联系人查询开头 | T |
| 27 / 613 | 联系人、日期、日历搜索/创建/取消函数 | T |
| 28 / 614 | 日历更新/参与者、云盘追加/查找/创建/删除 | T |
| 29 / 615 | 云盘读取/共享/搜索、Q解析函数schema说明、Email类型开头 | T |
| 30 / 616 | Email/Calendar/CloudDrive枚举schema、P代码注意事项 | T |
| 31 / 617 | 语言约束、banking提示补充、附录H错误示例与状态保留 | T |
| 32 / 618 | 附录H不可信异常文本删除提示收尾 | T |

本审计中论文给出的攻击文本、系统提示和代码样例均作为研究材料处理，没有当成执行指令。上游代码的研究警告、依赖失败、子集通过与新探针失败同时保留，供后续整合报告复核。

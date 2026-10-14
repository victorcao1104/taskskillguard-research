# Progent 全文与官方代码核验记录

核验日期：2026-10-15（Pacific/Auckland）。本记录服务于 TaskSkillGuard 手册 WP-01；不代表三篇论文或 TaskSkillGuard 全部实验复现。仅对本地模拟值做确定性验证，未调用任何 LLM、未访问真实邮箱/密钥/敏感数据，未运行攻击实验。

## 1. 来源、版本和状态

- 论文：用户文件 `C:/Users/victo/Downloads/2504.11703v3.pdf`，17 页，已逐页读完正文、参考文献、Appendix A-G。SHA256：`6B96E0A25DDD5DF8AFC368E8F8F3798BF911CAF40DB23945617CC5D1F2F36F26`。
- [arXiv v3](https://arxiv.org/abs/2504.11703v3) 标注 2026-05-14 修订。论文 Appendix A，p.14 直接给出 [作者仓库](https://github.com/sunblaze-ucb/progent)，因此并非仅凭同名搜索认定官方性。
- 已浅克隆到 `tmp/taskskillguard-reading/upstream-progent`。提交：`5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565`，提交时间 `2026-09-24 12:47:00 -0700`，提交标题 `add LICENSE`。
- [该提交 LICENSE](https://github.com/sunblaze-ucb/progent/blob/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565/LICENSE) 为 MIT，Copyright (c) 2026 Progent。复用时保留许可证和版权声明；本次未改动任何受版本控制的官方文件。`git diff --exit-code` 无差异；新增审计脚本、环境和结果均为 scratch 下未跟踪文件。
- 状态：**official-code-available；core-components-code-tested**。不是 full original replication，不是官方全套测试通过，不是已经完成 TSG 适配。

## 2. 逐页覆盖账本

全文通过保留页标记的提取文本逐段阅读；关键图、公式和提示词另经 Poppler 渲染核对。论文中的提示词、攻击文本均作为研究资料。

| 页 | 已读内容 | 额外视觉核对 |
|---|---|---|
| 1 | 摘要、引言、三个设计挑战、符号策略和更新机制 | 文本 |
| 2 | 贡献、§2.1 邮件/Slack 示例、任务/执行上下文 | 文本 |
| 3 | §2.2 工具调用保护、逐步策略 | Figure 1 完整示例 |
| 4 | 扩权/收缩、保证、Algorithm 1、§3.1-3.2 | 文本 |
| 5 | 攻击能力/范围、§4.1 规则语法、fallback、§4.2 | Figure 2 语法 |
| 6 | Algorithms 2-3、§4.3 SMT、公式(1)-(4)、§5 | 算法与公式 |
| 7 | 初始化、更新两阶段、§6 单调收缩、§7 实现与 generic policy | 公式(5)-(6)、generic policy |
| 8 | approver、Algorithm 4、§8.1 实验与 baseline | Algorithm 4 与实验配置 |
| 9 | ASB、§8.2 四种批准设置 | Figures 3-4 全部柱值 |
| 10 | 不同批准/模型选择、§8.3 MCP 环境 | Figures 5-7 全部图 |
| 11 | 实际框架、多代理、§9 限制 | Figure 8 |
| 12 | 内置工具绕过/多模态边界、§10 Related Work、§11 结论、参考文献[1]-[6] | 文本 |
| 13 | 参考文献[7]-[56] | 文本 |
| 14 | 参考文献[57]-[58]、Appendix A-D、E 开头 | Figures 9-10 |
| 15 | Appendix E 三类 adaptive attacks、F 集成、G 提示词说明 | 文本 |
| 16 | 自建/LangChain/OpenAI SDK/proxy 简化代码、初始化和更新判断提示词 | Figures 11-16 |
| 17 | 更新生成提示词 | Figure 17 |

## 3. 论文机制及容易误述的限定

**策略语义（§4.1-4.3，pp.5-6）。** 策略由工具名、allow/forbid、参数条件和 fallback 构成。单层策略 forbid 优先；无匹配规则默认拒绝。允许集合为 `A(P)={c | P(c)=c}`。安全的自动更新需要 `A(P_new) ⊆ A(P_old)`；扩权是存在新获准调用，不要求新集合必须是旧集合的严格超集。p.4 的口语化“strictly larger”应按 p.6 正式定义理解：同时删除一些权限、增加另一些权限仍是 expansion。

**更新（§5，pp.6-7）。** 初始化只利用可信用户任务和工具定义。第一阶段判断需不需要更新时只看任务、工具和调用参数，明确排除工具结果；第二阶段才把工具结果放入候选生成。随后用确定性的集合关系检查决定是否可以自动应用。§6 的 monotonic confinement 是“在获批扩权之间，行动空间不增大”，不保证初始策略一定最小、批准一定正确、所有注入一定失败。

**generic policies（§7，pp.7-8，Algorithm 4）。** 这是带优先级的先匹配决策：高优先级规则已明确 allow 或 forbid 时，低优先级策略不再决定该调用；高层无匹配才转下一层。不能将其直接描述成所有规则一律求交。特别是高优先级全局 allow 会遮蔽低优先级任务限制。p.7 的 `A(P_generic,P) ⊆ A(P_generic)` 需要结合“无匹配”的组合语义解释；若对单独 generic 仍用 Algorithm 2 的默认拒绝，低层允许的高层未匹配调用会让该集合式产生解释张力。TSG 的固定任务上限应明确采用独立约束求交，不能直接以优先级 allow 代替权限上限。

**实验数字（§8，Figures 3-8，pp.8-11）：以下全部为论文结果。** AgentDojo ASR 39.9%→1.0%；无攻击 utility 79.4%→76.3%，受攻击 utility 54.0%→61.3%。ASB ASR 70.3%→3.9%；无攻击 utility 78.2%→78.2%，受攻击 utility 71.1%→69.7%。因此“维持高 utility”不能改写成所有指标均不下降。默认比较采用 Auto-Approve；Auto-Deny 的 ASR 为0.7%，Manual Approval为0.0%，Disable Update为2.5%（Figure 5）。6% 是需批准的扩权更新占比，不是全部工具调用比例。

**评估范围（Appendix D-E，pp.14-15）。** AgentDojo 排除 travel 中两个偏好操纵攻击；一个 Slack 攻击判定原本只看 trace 中是否出现调用，作者人工纠正“被阻断但仍在 trace”导致的误判。手动批准假设操作者有较强安全意识。Adaptive Figure 10 的 normal/if-then-else/allow-attack-tool/AgentVigil ASR 分别为1.0/0.5/4.2/0.9%，不能将通常攻击的1%套用所有自适应攻击。

**边界（§3.2，p.5；§9，pp.11-12）。** 不覆盖最小权限内的偏好操纵或纯文本输出攻击；错误批准、含糊用户任务仍可能授予过多权限；proxy 无法覆盖绕开外部 MCP 的内置工具；多模态屏幕点击不是当前覆盖范围。

## 4. 真实代码对象和入口

下表所有路径基于固定提交 `5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565`；链接固定在该提交。

| 组件 | 代码与函数 | 实际语义 |
|---|---|---|
| 策略对象 | [secagent/tool.py](https://github.com/sunblaze-ucb/progent/blob/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565/secagent/tool.py#L29) 的全局 `security_policy`；`Tool`；`update_security_policy` | `dict[tool, list[tuple(priority,effect,conditions,fallback)]]`；effect 0=allow,1=forbid；fallback 0=error,1=terminate,2=confirm。还有第五项后续策略更新。不是论文 Figure 9 中的命名字段对象。 |
| 排序 | `tool.py:64 sort_policy` | `(priority,-effect)` 排序，小优先级数值先执行；仅同优先级 forbid 先于 allow。 |
| 参数和调用 | `tool.py:508 check_arg`、`:521 _check_tool_call`、`:573 check_tool_call` | dict限制交给 `jsonschema.validate`；字符串限制用 `re.match`；也接受 Python callable。 |
| 策略生成 | `tool.py:375 generate_security_policy`、`:415 decide_whether_to_update`、`:435 generate_update_security_policy` | 生成规则 priority=100、effect=allow；读取 `SECAGENT_ONLY_ALLOW_NARROW` 时默认 False；只有 True 才调用 subset checker。 |
| SMT | [secagent/policy_analysis.py](https://github.com/sunblaze-ucb/progent/blob/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565/secagent/policy_analysis.py#L83) `build_constraints`、`:233 solve_schema`、`:357 security_policy_subset_check` | 构造 `not(old_restriction) and new_restriction` 寻找反例；5秒 timeout；不等价于实现任意完整 JSON Schema / 任意策略列表的证明器。 |
| 正则转换 | [secagent/role_analyzer.py](https://github.com/sunblaze-ucb/progent/blob/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565/secagent/role_analyzer.py#L382) `AnyChar`、`regex_construct_to_z3_expr`、`regex_to_z3_expr` | 有限正则子集；AnyChar/字符类别按ASCII；`^`/`$` 等位置断言抛 NotImplementedError。文件首行注明源自 gravitational/rbac-linter。 |
| 类型检查 | [secagent/policy_type_check.py](https://github.com/sunblaze-ucb/progent/blob/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565/secagent/policy_type_check.py) `security_policy_type_check` | 存在独立校验函数；但 `tool.py:121` 同名函数目前仅构造工具字典，`:130 # check()` 是注释，不可声称运行时强制完成该静态校验。 |

论文 Appendix F 的 `from progent import *`、`initialize_policy` 等是明确标记的简化展示；实际安装包名为 `secagent`，不能原样复制论文图中的 API 并声称已验证。

## 5. Tool Adapter 核验

| Adapter | 代码位置/实际校验 | 本次状态 |
|---|---|---|
| 普通 Python 函数 | `tool.py:718 secure_tool_wrapper` 使用 `inspect.signature.bind`，再 `apply_defaults()`，把绑定后参数传给 `check_tool_call`；`apply_secure_tool_wrapper` 处理列表 | 已执行无副作用示例：默认 recipient=bob、策略只准 alice，省略参数时被拒绝。直接调用核心校验传 `{}` 却被允许，显示适配器差异。 |
| AgentDojo | `agentdojo/src/agentdojo/default_suites/v1/banking/task_suite.py` 按 `SECAGENT_SUITE` 包装工具；`agent_pipeline/tool_execution.py:ToolsExecutor.query` 在执行后调用更新（manual_check=False） | 静态追踪；未安装/运行完整 AgentDojo。其 runtime、任务 fixture 与被包装函数共同决定参数行为，不能拿核心例子代替端到端结果。 |
| LangChain | `tool.py:SecAgentLangchainMiddleware.awrap_tool_call` 在 handler 前检查 `request.tool_call['args']`；更新时 manual_check=False；`add_langchain_tools` 从模型可见参数中删除 `$ref` 字段 | 静态审查，未运行此 SDK。核心前置检查本身没有像 Python wrapper 那样补默认值；实际 SDK 是否提前规范化另需集成测试。 |
| OpenAI Agents SDK | `tool.py:635 openai_tool_wrapper` 解析 JSON 后检查；`:656 openai_agent_wrapper` 包装 FunctionTool/MCP工具；模型可见参数中删除 `$ref` 字段 | 静态审查，未运行 SDK；未把“包装存在”当成端到端通过。 |
| MCP proxy | `secagent/progent_proxy.py:294 ToolCallFilterMiddleware.on_call_tool` 在 call_next 前检查 `context.message.arguments`；`:126 convert_mcp_tool_to_progent` 转换工具元数据。另有 `mcp_proxy.py:32` 示例 | 静态审查，未启动服务器或连接任何外部 MCP。 |
| ASB | `asb/pyopenagi/agents/react_agent_attack.py` 的执行路径在 `.run(function_params)` 前调用 `check_tool_call(function_name,{})`，此处 function_params=None | 静态证据说明这条适配路径没有传入实际参数对象；本次不推广为所有 ASB 模块结论。 |

## 6. 安装、运行记录和依赖

官方 `pyproject.toml` 声明 Python>=3.9、hatchling，以及 `docstring_parser`、`jsonschema`、`pydantic>2.0`、`openai`、`anthropic`、`z3-solver`。除 Pydantic 下界外未锁版本。AgentDojo 声明 Python>=3.10，另带 LangChain/VertexAI/Cohere 等依赖；`real-world-agents/requirements.txt` 固定 langchain==1.0.2、autogen-core==0.7.5、openai-agents==0.4.2。`tool.py` 注释还注明 langchain-core==1.0.1、langchain-mcp-adapters==0.1.12。不能推定当前包组合与论文环境一致。

实际步骤与结果：

1. 普通权限 clone 遇到 DNS/getaddrinfo 错误；经工具授权后的网络重试成功。未遇到自动审核拒绝。
2. 在 `upstream-progent/.audit-venv` 创建隔离 venv；自动 ensurepip 失败，随后使用 bundled Python 的 `pip --python <venv-python>` 给已创建的 venv 安装最小依赖。普通网络安装同样 DNS 失败，获准联网重试后成功。
3. 只安装并固定 core smoke test 所需四个直接依赖：z3-solver==5.3.0.0、jsonschema==4.26.0、pydantic==2.14.1、docstring_parser==0.18.0；Python 3.12.14，Windows amd64。完整传递依赖锁在 `.audit_requirements_lock.txt`。
4. 以源码导入官方 core，没有执行完整 `pip install -e .`，没有安装 openai/anthropic/整个 benchmark。没有寻找或读取凭证。
5. 执行新增 `.audit_probe.py`：20/20 个**行为刻画观察**与预期一致，进程退出0。此数字包含成功复现的不安全行为；不是“20项安全性质通过”。无官方 secagent 专用 tests 目录；仓库里有 AgentDojo/agentdojo-mcp 的基准测试，本次未跑。
6. 补充 mock 更新路径时第一次试验出现样例间状态污染：上游 `update_security_policy` 持有传入 dict 引用，更新修改了测试用初始策略。根据日志定位后仅给审计脚本的 fixture 增加 deep copy，重新运行20项一致；未更改上游代码。保留最终原始结果，不将首次失败误判为上游扩权绕过。

本地重跑（从 workspace 根目录；现有环境已就绪）：

```powershell
& 'tmp/taskskillguard-reading/upstream-progent/.audit-venv/Scripts/python.exe' 'tmp/taskskillguard-reading/upstream-progent/.audit_probe.py'
```

证据文件：`upstream-progent/.audit_probe.py`、`.audit_results.json`、`.audit_stderr.txt`、`.audit_requirements_lock.txt`。这些都是本次审计产物，不是原作者测试或数据。

## 7. 已验证的行为与缺口

| 行为 | 本机观察 | 意义 |
|---|---|---|
| 字符串 enum 允许/拒绝，已初始化策略的未知工具拒绝 | 符合预期；空字典策略也拒绝 | 基础策略校验已运行。 |
| enum 从 `{alice,bob}` 缩到 `{alice}` / 逆向扩权 | subset 分别 True / False | 受支持的简单场景可用。 |
| `security_policy=None` | `check_tool_call` 警告后返回，允许 | 未初始化状态不是 fail-closed；TSG必须初始化到明确拒绝态。 |
| 核心校验缺失受限参数 | `{}` 省略 recipient 仍允许；Python wrapper 补默认值后正确拒绝 | 不能只检查存在的参数；统一参数规范化是安全边界。 |
| `const` 旧约束移除 | subset返回True；运行时 JSON Schema 的const本来有效 | 编译器忽略未支持关键字，比较与执行不一致。 |
| 旧 `pattern='^alice$'` 放宽为任意 string | subset返回True | 正则转换不支持锚点，异常被 `solve_schema` 吞掉，最终被当成没有扩权反例。 |
| `pattern='alice'` 与值 `xalicex` | jsonschema接受；Z3约束拒绝 | JSON Schema pattern 是搜索匹配，而 Z3 InRe 是全串匹配；这是实测语义差异。 |
| Solver 返回 unknown | 测试中仅注入 `check()->unknown`，subset返回True | 未实际触发超时；但验证了 unknown 路径与 unsat 混同，不能视为证明安全。 |
| allow/forbid改变与多条规则 | checker只保留priority100，再看首条规则参数；effect变化不影响结果 | 它不是论文完整任意策略语义比较器。生成器常规输出为allow，因此effect反例针对通用API边界，不能冒称正常生成输出必然出现。 |
| 优先级 | 同优先级 forbid优先；priority1 allow可遮蔽priority100 forbid | 与高优先级短路一致，但不等同所有deny全局优先；固定上限不宜这样表达。 |
| 更新模式 | mock掉模型：manual_check=False、ONLY_ALLOW_NARROW=False 接受enum扩权；True 拒绝该简单扩权 | 证明实际默认可走 Auto-Approve；调用方必须明确选择批准策略。 |

关键原因：`policy_analysis.py:320-329` 仅在 `s.check()==sat` 时返回模型，unknown 和转换异常最终同样返回 None；`:357-424` 只比较 priority100 首条规则的逐参数条件，并不构建全部工具规则/forbid/优先级的完整允许集合。`tool.py:464` 仅在显式环境开关下启用该检查。运行时支持的 JSON Schema 范围大于 SMT 编译器实现的范围，因此“用了 Z3”不等于论文安全证明已在当前代码/全部输入上成立。

## 8. 对 TaskSkillGuard 的可执行结论

当前合适的来源标记是“**参考 Progent v3 机制；已核验官方 core；TSG 的受限策略运行时仍需单独实现/适配和验证**”。不要把该提交未经修补直接当成安全证明完备的执行核心。

TSG 最少应：固定受限DSL并拒绝未知关键字；统一运行时与SMT语义；保留 sat/unsat/unknown/error 四种结果，仅 unsat 证明无扩权；比较完整规则集合及 forbid/优先级；补齐缺省/必需参数校验；策略初始化失败时拒绝；把任务上限/全局限制作为每次调用都要满足的交集；批准账本绑定候选策略哈希与任务，而非依赖一个默认 False 的环境开关。

后续才能开展独立适配器测试、工具调用与真实副作用的对应检查、policy fuzz/property tests，以及论文 AgentDojo/ASB 重跑。本次没有产生任何新 ASR/utility 研究成绩；论文数值不能迁移到本课程 Skill 语料。

# Phase 2：可校验合同、SMT 与证据双账本

## 实现与证据范围

`src/tsg/contracts_v2.py` 是独立编写的受限实现，对应实施手册 §5.3、§9、§11.1、§11.3 和 WP-07。它使用实际的 `jsonschema.Draft202012Validator` 校验合同及工具参数，使用实际的 Z3 查询比较权限；不是一般 JSON Schema 到 SMT 的完整编译器，也不是 Progent 原仓库的复现结果。旧 `policy.py` 和旧实验记录保持不变。

本模块不执行任何工具、脚本、模型或网络请求。所有资源都是 capability VM 中的逻辑名称；不解决主机符号链接、Windows 路径别名、真实 HTTP 重定向或操作系统沙箱逃逸。真实主机资源必须另由执行层处理。信息流 `sources/readers` 检查由调用层实施，不包含在本模块的权限包含性证明中。

实际运行 `scripts/run_contract_probes_v2.py` 得到 **33/33 个探针通过**：5 个 UNSAT 收缩/等价证明，8 个 SAT 扩权见证，3 个 UNSUPPORTED/unknown；其余 17 个覆盖授权账本与执行边界。每个 SAT 见证再次调用新旧合同的确定性运行时，证实新合同允许且旧合同拒绝，才记为 expansion。

原始输入、预期、实际结果、见证及时间保存在 `results/phase2/contracts/probes.jsonl`；另有 `probes.csv`、`summary.json`、`approval_traces.jsonl`、`approval_arms.json`、`approval_arms.csv` 和 `manifest.json`。Manifest 记录依赖版本、基线 Git commit、四个实际文件的 SHA-256，不把未提交文件声称为已有 commit。

## 精确支持的语言

合同必须通过 `configs/contract_v2.schema.json`，顶层必需字段为：

```json
{
  "contract_id": "task_1_contract",
  "task_id": "task_1",
  "skill_id": "skill_1",
  "policy_version": 1,
  "authority_source": "trusted_user_request",
  "rules": [],
  "default_action": "deny",
  "review_on_unknown": true
}
```

`authority_source` 也可为 `trusted_administrator` 或 `proposed`。该字段仅是元数据，不能把输入变为可信授权。信任来自独立调用的 Authority Ledger API。

| 字段 | 语义与边界 |
|---|---|
| `rule_id` | 每份合同唯一的非空字符串 |
| `effect` | `allow` 或 `forbid`；匹配的 forbid 优先 |
| `operation` | 12 个有限工具名：file.read/write/delete、secret.read、network.get/post、email.read/send、db.read/write、command.exec、process.spawn。枚举工具名不表示执行器已经实现该工具 |
| `resource` | 精确字符串，或 `{"path_prefix":"/sandbox/input"}`，或 `{"domains":["mock.invalid"]}` |
| `parameters` | 下述扁平闭合对象 schema；缺省表示仅允许空对象 `{}` |
| `starts_at_step` | 含起点的非负步骤，缺省为 0 |
| `expires_after_step` | 含终点的非负步骤；缺省不设终点 |
| `allowed_stages` | 非空、无重复字符串列表；缺省不限阶段 |
| `max_uses` | allow 的非负使用额度；缺省不限。forbid 禁止携带此字段，避免禁止规则被使用次数耗尽 |
| `approval_id` / `evidence_ids` | 每个 allow 必需，引用可信账本中的批准记录与证据 |
| `purpose` | 可选审计文本；不参与权限判断 |

资源路径限定为 `/sandbox` 及其子路径，区分大小写。路径段可用 ASCII 字母、数字和 `._~-`，不允许 `.`、`..`、空段、反斜杠、百分号编码、控制字符或其他 Unicode 字符。`path_prefix` 匹配目录本身与 `prefix + '/'` 开始的后代，不匹配 `/sandbox/input-evil`。这是逻辑路径语法，不是任意 POSIX 文件名支持。

URL 只支持 HTTPS、有限字面域名与受限路径；运行时小写化主机并规范化默认 443 端口和空路径。合同必须已规范化。域名 allowlist 精确匹配整个主机名，不隐含子域名；禁止用户信息、非默认端口、查询、片段、百分号编码和非法路径段。所有对比都在同一规范化资源语法中进行。

参数示例：

```json
{
  "type": "object",
  "properties": {
    "body": {"type": "string", "const": "DONE"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
    "preview": {"type": "boolean", "enum": [true, false]}
  },
  "required": ["body"],
  "additionalProperties": false
}
```

参数仅支持 `string`、`integer`、`boolean` 三种标量类型，`const`、同类型 `enum`、整数 `minimum/maximum/exclusiveMinimum/exclusiveMaximum`、`required` 和固定 `additionalProperties:false`。可选字段的缺失与存在分别建模；改变字段类型也可产生扩权见证。JSON Schema 的 integer 语义允许数值上为整数的 JSON 数字；布尔值不是整数。

不支持嵌套对象、数组、number、null、正则 pattern、format、oneOf/anyOf/allOf、条件 schema、外部 `$ref`、任意 Python 表达式、shell 语义、动态数据依赖和通配符。出现任何未支持键或无效类型，整份合同为 unsupported：对比返回 unknown，调用拒绝，显式批准也不能让不支持的合同生效。这里的配置 schema 自身使用本地 `$defs`/`if` 是校验器的实现；这不意味着用户参数语言支持这些构造。

额外边界：合同最多 256 KiB、256 条规则；每条参数 schema 最多 16 字段；枚举最多 64 项。Solver 默认每次查询 2 秒；TIMEOUT/UNKNOWN 保留旧策略。证据作用域检查中的 UNKNOWN 也拒绝更新。

## 证明语义与运行时状态

比较器查询：`Allow(new,c) AND NOT Allow(old,c)`。符号调用含工具、规范资源、阶段、步骤、使用次数，以及参数的存在位、类型和值。

- UNSAT → 支持语言内的 subset；可自动收缩或等价替换。
- SAT → expansion；保存并重放具体见证。
- 不支持、超时或求解不确定 → unknown；保留旧策略。

每次比较使用独立 Z3 context；并发测试覆盖了相同与不同合同的混合查询。元数据顺序及规则顺序不改变权限语义。

`ContractGuard` 的 `step` 必须由可信执行器给定，不能回退。阶段字符串同样应来自可信执行器。阶段名本身没有内建顺序；只有匹配阶段和步骤窗口的 allow 才有效。额度以 **`(operation, canonical_resource)`** 计数，跨参数和阶段共享；这不是整个目录或域名的全局总额度。更新合同应保留同一个 Guard 的计数器与时钟。重新构造 Guard 表示一个新运行，不能用于绕过当前运行的额度。

错误码分别为 `LEASE_NOT_STARTED`、`LEASE_EXPIRED`、`STAGE_DENY`、`QUOTA_EXHAUSTED` 和 `CLOCK_ROLLBACK`。`max_uses=1` 的第二次有效窗口内调用会返回 QUOTA_EXHAUSTED；即使从未使用，超过步骤终点也会返回 LEASE_EXPIRED。探针把二者分别测量，不再把额度耗尽报告成过期。多个规则均不匹配当前窗口且无法归为单一原因时返回 `LEASE_INACTIVE`。

`lease=False` 是显式实验开关，关闭步骤、阶段和额度限制；forbid 匹配仍优先，但其时窗也被忽略。正常运行应保持默认 `lease=True`。

## 证据双账本与批准边界

`DualLedger` 分别保存：

1. Authority Ledger：可信 actor、task、时间、批准 ID、证据 ID、完整授权 scope、合同摘要及是否已消费。
2. Skill Evidence Ledger：Skill/Q 模型/观察内容，仅作审计事实，固定 `authority:false`。

`record_skill_evidence()` 永远不签发权限，即使 claim 伪称来自用户或使用与可信证据相同的字符串 ID。每个 allow 必须引用 Authority Ledger 内的批准与证据，且其真实有效作用域（考虑 forbid 后）必须被该条批准记录涵盖。仅存在一个名字相同的证据不够。

更新必须属于同一 task。未批准的收缩只改变 effective，保留 task_ceiling；恢复已撤销权限依然属于相对当前 effective 的扩权。扩权需要：可信 user/administrator 经独立通道显式批准，`approved is True`，批准绑定精确合同 SHA-256，而且尚未消费。`task_initial` 在初始化时已消费，不能反复复用；一次成功扩权消费批准。重新开放需要新的批准记录。修改一个 allow 的资源、期限、阶段或参数范围时，应引用相应的新批准，不能继续伪引旧来源。

这些是 **可信嵌入式 API 的能力边界**，不提供用户身份认证或密码学签名。任何进程内 Python 调用者都能调用方法；执行器必须保证 Skill/Q 模型不能接触 `register_approval()`、Guard 状态或 `effective` 赋值。不能把模型输出中的 `actor:"user"`、`approved:true` 直接传入批准入口。

## 稳定集成 API

```python
from tsg.contracts_v2 import Contract, ContractGuard, DualLedger, compare_contracts

initial = Contract.from_dict(trusted_contract_json)
assert initial.valid(), initial.errors
ledger = DualLedger(initial, trusted_initial_evidence=('task_initial',))
guard = ContractGuard(ledger.effective)

ledger.record_skill_evidence('claim_1', 'skill', untrusted_claim)
proposal = Contract.from_dict(proposal_json)
comparison = compare_contracts(ledger.effective, proposal)
accepted = ledger.update(proposal)  # Only supported, evidence-bound subsets.

# Only an independently authenticated trusted adapter may take this branch.
ledger.register_approval('approval_2', proposal, actor='user', approved=True,
                         evidence_ids=['trusted_message_2'])
accepted = ledger.update(proposal, approval_id='approval_2')
if accepted:
    guard.contract = ledger.effective  # Preserve this run's clock and counters.

allowed, reason = guard.check('network.post', 'https://mock.invalid/status',
                              step=4, args={'body': 'DONE'}, stage='send')
```

`Contract.to_dict()`、`authority_ledger`、`skill_evidence_ledger` 和 `events` 返回防御性快照。`Contract.allows(operation,resource,step,args=None,stage='default',uses=0,temporal=True)` 可重放见证，不改变计数；实际有状态调用应使用 `ContractGuard.check()`。

## 已测批准对照

固定四个合成场景：用户要求的报告输出、用户要求的公开状态发送、Skill 自称必要的假秘密读取、未请求的其他目的地发送。`trusted_authorized` 在脚本中预先固定，独立于 Skill 内容；这里没有模拟为真实人工审批数据。

| 方案 | 审批请求 | 批准 | 错误放行 | 合法动作放行 | 未授权动作拒绝 |
|---|---:|---:|---:|---:|---:|
| deny_all_expansions | 4 | 0 | 0 | 0 / 2 | 2 / 2 |
| oracle_approver | 4 | 2 | 0 | 2 / 2 | 2 / 2 |

两组使用相同四个场景，模型 token 与 API 成本均为 0；本地运行时间保存于 JSON/CSV。这只证明固定探针下的策略和批准控制行为，不是开放世界安全率、真人审批准确率、真实 Skill 语义准确率或总体 utility 提升。

## 重跑

在仓库根目录：

```powershell
.venv/Scripts/python.exe scripts/run_contract_probes_v2.py
.venv/Scripts/python.exe -m pytest tests/test_contracts_v2.py -q --basetemp=work/contracts-pytest
.venv/Scripts/python.exe -m pytest -q --basetemp=work/all-pytest
```

受限 Windows 环境中系统临时目录曾不可写，因此测试将临时文件放在仓库 `work/` 内。`--basetemp` 指向 pytest 专用目录，因为 pytest 可清理该目录。正式探针输出只写 `results/phase2/contracts/`，不修改原始 corpus 或 v1 结果。时间戳和耗时可变化；是否通过、求解关系和批准计数应一致；SAT 的具体等价见证可随 Z3 版本变化。

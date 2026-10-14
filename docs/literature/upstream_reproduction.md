# 上游核验材料归档与复查说明

归档日期：2026-10-15。范围是此前 CaMeL、Progent 本地核验材料的逐字节归档，以及 SkillScope 官方实现的核实边界。**本次归档没有重跑测试、调用模型、访问网络或重新开展论文实验。** 研究代码、上游仓库文件及 `sources/` 均未修改。

已核对两份源码审计、Progent 探针与原始 JSON/文本输出、CaMeL 的原始 pytest/JUnit/JSON 及依赖清单。复制后重新计算 SHA-256，20 份复制文件全部与来源相同。每个仓库的 `archive_manifest.json` 记录源相对路径、归档路径、大小和 SHA-256；`results/upstream/summary.json` 为本次从原始结果重新计算的汇总，不是新实验结果。

## 1. 固定来源、许可证和运行范围

| 来源 | 仓库与固定 commit | 许可证 | 此前实际验证 |
|---|---|---|---|
| CaMeL | [google-research/camel-prompt-injection](https://github.com/google-research/camel-prompt-injection/tree/f083b6b396399d3b3c7f2ddaf613a5945eaf32d8)；`f083b6b396399d3b3c7f2ddaf613a5945eaf32d8` | Apache-2.0；完整 LICENSE 已归档 | 上游解释器测试目录及自建纯机制探针；没有完整 AgentDojo、模型 API 或真实外部副作用 |
| Progent | [sunblaze-ucb/progent](https://github.com/sunblaze-ucb/progent/tree/5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565)；`5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565` | MIT；完整 LICENSE 已归档 | 官方 core 源码的自建确定性行为刻画；没有官方完整测试、AgentDojo/ASB、模型 API 或外部适配器端到端测试 |

两份测试均使用 Windows amd64、CPython 3.12.14。CaMeL 上游声明 Python >=3.10、`.python-version=3.10.12`；Progent 顶层声明 Python >=3.9。因此本次运行环境并非自动等同于原论文环境。

CaMeL 用户 PDF 为 SaTML 2026 正式发表稿，32 页，DOI `10.1109/SaTML68715.2026.00040`。论文附录链接的代码 commit 是 `45b656a0aaf688626955b12823ec0bd6af9f7df7`，与本次 HEAD 有少量实现差异；不能把二者混为同一个固定版本。详细差异和页码见 `docs/literature/camel.md`。

## 2. 原始计数与正确解释

| 证据集 | 原始计数 | 可以声称 | 不可以声称 |
|---|---|---|---|
| CaMeL 首次 pytest 收集 | 11 个 collection errors；JUnit 的 tests=11、errors=11 | 当时由于间接依赖不兼容无法收集；不是 11 项正常测试已执行 | 不得把收集失败删掉后称安装一次即成功 |
| CaMeL 上游 `tests/test_camel_lang` | 106 tests，106 passed，0 failures/errors/skips | 固定环境下这个目录通过 | 不是整个上游测试集通过，不是防御安全证明或论文复现 |
| CaMeL 自建探针 | 21 tests，15 passed，6 failed | 确认若干正常行为，同时留下具体反例 | 不得将预期会暴露缺陷的 6 个失败包装成安全通过 |
| Progent `.audit_probe.py` | 20 条 records，20 个 characterized=true，0 mismatch，退出码0 | 全部观察与刻画脚本的 expected 一致 | **不是 20 项安全性质通过**，不是官方单元测试通过 |

### 2.1 CaMeL 失败的含义

21 个探针由两个文件组成：`test_capability_probes.py` 的 16 个实例中有 15 个通过、1 个失败；`test_known_discrepancies.py` 的 5 个实例均失败。这里的失败都是保留的断言失败，没有标成 xfail 或跳过。

- NORMAL 下模拟 Q 返回值没有保留直接私有输入标签：1 个失败。
- `[secret]` 容器没有把直接私有成员的 readers 纳入查询：NORMAL/STRICT 各 1 个失败，共 2 个。
- `base_security_policy` 对公开参数误拒：1 个失败。
- `is_trusted` 的自定义 `trusted_set` 不生效：1 个失败。
- `delete_email_policy` 对可信用户 ID 的条件反向：1 个失败。此项仅抽取并执行原方法 AST 的逻辑体；不是完整 AgentDojo 适配器测试，也未真正删除邮件。

这些是局部反例，不是对真实邮箱或网络的攻击执行。STRICT 模式也未修复已测容器成员案例。详见原始失败日志和 `docs/literature/camel.md`。

### 2.2 Progent 的 characterization 不能转换成安全通过率

脚本按“是否重现已观察的行为”判断 `characterized`。例如 `uninitialized_policy_allows`、`missing_restricted_argument_is_skipped`、`jsonschema_const_expansion_misclassified`、`unsupported_regex_anchor_expansion_misclassified`、`injected_unknown_treated_as_subset` 都在观察不安全或不完整的边界行为；这些 record 的 `expected=true` 并不是研究者期望防御这样工作。

此外 `actual` 的含义依探针而异：有时表示调用获准，有时表示“正确拒绝已发生”，有时是 solver 字符串 `unsat`。因此不能统计 `actual=true` 得出安全通过数，也不能与 CaMeL 的 pytest passed 相加计算统一安全通过率。汇总 JSON 将 Progent 的 `security_property_pass_count` 明确设为 null。

`injected_unknown_treated_as_subset` 使用 fake solver 令 `check()` 返回 unknown；它验证的是错误分支处理，不代表实际制造了 solver 超时。两个更新流程探针将模型请求替换成本地 lambda。原始结果中没有 Progent JUnit 文件，本次没有伪造或将 characterization 转成零失败 JUnit。

### 2.3 数字核对与保留差异

- 与既有 `camel.md`、`progent.md` 的最终测试计数**没有差异**。
- CaMeL 上游控制台 elapsed 为 1.80s，JUnit suite time 为 1.537s；新增探针分别为 1.13s、0.885s。这是记录范围不同的时间字段，保留两者，不统一改写。
- CaMeL 首次 11 errors 是 collection errors，不参与“106 项通过”的分母。
- Progent 前期曾修正审计 fixture 的共享 dict 状态污染，再得到最终 20/20；归档的是现存最终脚本/结果，未找到并编造首次运行原始输出。上游源码未因该修正而改动。
- 论文自身的攻击数、token 倍数等正文/表格差异属于文献审计内容，不是本次本地测试计数，已在对应审计中保留。

## 3. 文件清单

以下路径相对于 `taskskillguard-research/results/upstream/`。不含 venv、整个上游源码、图片或 PDF。

### `camel/`：14 份原样复制文件，另加 manifest

| 文件 | 用途 |
|---|---|
| `LICENSE` | 上游 Apache-2.0 全文 |
| `upstream-pyproject.toml` | 上游依赖声明，原文件 `pyproject.toml` 原样改名归档 |
| `upstream-uv.lock` | 上游完整锁文件，原文件 `uv.lock` 原样改名归档 |
| `installed.txt` | 实际最小测试环境的最终完整包清单 |
| `minimal-locked-requirements.txt` | 对齐已装依赖时使用的约束；不是完整最终环境 |
| `evidence.json` | 此前记录的 Python 版本、PDF hash、JUnit 摘要 |
| `upstream-pytest-initial-failure.txt` | 首次 collection 失败的控制台输出 |
| `upstream-junit-initial-failure.xml` | 首次 collection 失败的 JUnit |
| `upstream-pytest.txt` | 106 项上游子集通过的控制台输出 |
| `upstream-junit.xml` | 同一上游子集的 JUnit |
| `test_capability_probes.py` | 自建机制探针源码 |
| `test_known_discrepancies.py` | 自建预期语义反例探针源码 |
| `probes-pytest.txt` | 15 passed / 6 failed 的原始输出 |
| `probes-junit.xml` | 同一组自建探针的 JUnit |
| `archive_manifest.json` | 本次生成：来源、commit、逐文件 hash/大小 |

### `progent/`：6 份原样复制文件，另加 manifest

| 文件 | 用途 |
|---|---|
| `LICENSE` | 上游 MIT 全文 |
| `upstream-pyproject.toml` | 上游依赖声明 |
| `.audit_probe.py` | 20 条行为刻画的原始脚本 |
| `.audit_results.json` | 原始 records、实际版本与 20/20 刻画计数 |
| `.audit_stderr.txt` | 策略、solver、mock 更新输出；均为模拟值 |
| `.audit_requirements_lock.txt` | 实际最小环境的直接及传递依赖版本 |
| `archive_manifest.json` | 本次生成：来源、commit、逐文件 hash/大小 |

`summary.json` 是本次新增的跨来源机器可读摘要。加上两个 manifest，共 **23 个归档目录文件**；本文是另一个文档文件。

## 4. 依赖与离线复查步骤

归档没有携带解释器、venv 或 wheel。当前工作区已有两个隔离环境，可用下列命令复查；**这些是供后续执行的步骤，本次归档未执行**。在新的离线机器上，没有相应 Python 与本地包缓存/wheel 时，仅凭锁文件不能完成安装，应记录阻碍，不得声称已复现。

CaMeL 最小环境包含 pytest 8.3.5、pydantic 2.11.5、pydantic-ai-slim 0.2.12、typing-extensions 4.14.0 等。首次导入失败来自间接依赖漂移；对齐 opentelemetry-api/logfire-api/griffe 等后子集通过。完整实际版本以 `installed.txt` 为准；其中保留一些首次安装遗留包，不能把它称为完整 `uv sync --frozen` 环境，也不能用上游 `uv.lock` 覆盖实际环境事实。

Progent 最小环境直接依赖为 z3-solver 5.3.0.0、jsonschema 4.26.0、pydantic 2.14.1、docstring_parser 0.18.0；全部版本见 `.audit_requirements_lock.txt`。两种依赖环境应隔离，不要混装。

以下从本 ChatGPT project 工作区根目录执行；先用 `git -C <repo> rev-parse HEAD` 核对上表 commit。若不一致，应停止将新结果归到本组证据。每次复查写入新目录，避免覆盖已归档原始结果。

### 4.1 CaMeL 当前环境

```powershell
$archive = (Resolve-Path 'taskskillguard-research/results/upstream/camel').Path
$camelRepo = (Resolve-Path 'tmp/taskskillguard-reading/upstream-camel').Path
$camelPython = Join-Path $camelRepo '.audit/.venv/Scripts/python.exe'
$camelRun = Join-Path $archive ('rerun-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $camelRun | Out-Null
$env:PYTHONPATH = Join-Path $camelRepo 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location $camelRepo
try {
    & $camelPython -m pytest tests/test_camel_lang -q -p no:cacheprovider --junitxml="$camelRun/upstream-junit.xml" *> "$camelRun/upstream-pytest.txt"
    $upstreamExit = $LASTEXITCODE
    & $camelPython -m pytest "$archive/test_capability_probes.py" "$archive/test_known_discrepancies.py" -q -p no:cacheprovider --junitxml="$camelRun/probes-junit.xml" *> "$camelRun/probes-pytest.txt"
    $probesExit = $LASTEXITCODE
    [pscustomobject]@{ UpstreamExit = $upstreamExit; ProbesExit = $probesExit }
} finally {
    Pop-Location
}
```

预期参考结果：上游退出0，自建探针退出1且保留上述6个失败。测试 `delete_email_policy` 的方法体提取依赖工作目录为固定 CaMeL 根目录，所以不能直接在归档目录执行全部探针。此脚本使用本地 mock，不需要 API key。

### 4.2 Progent 当前环境

```powershell
$archive = (Resolve-Path 'taskskillguard-research/results/upstream/progent').Path
$progentRepo = (Resolve-Path 'tmp/taskskillguard-reading/upstream-progent').Path
$progentPython = Join-Path $progentRepo '.audit-venv/Scripts/python.exe'
$progentRun = Join-Path $archive ('rerun-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $progentRun | Out-Null
Copy-Item -LiteralPath "$archive/.audit_probe.py" -Destination "$progentRun/.audit_probe.py"
$env:PYTHONPATH = $progentRepo
$env:PYTHONDONTWRITEBYTECODE = '1'
& $progentPython "$progentRun/.audit_probe.py" 1> "$progentRun/stdout.txt" 2> "$progentRun/stderr.txt"
$LASTEXITCODE
```

脚本会把新 JSON 写在其自身所在目录的 `.audit_results.json`，因此先复制到独立 rerun 目录，不能直接运行归档原脚本而覆盖旧结果。预期参考是退出0及20条刻画一致；仍不得转述成20条安全通过。

## 5. SkillScope 官方仓库的核实边界

截至 **2026-10-15 的前期有限检索**，没有建立“作者身份 → 本项目指定论文 → 官方实现仓库”的可核验链。本次归档未再次联网检索。

前期来源包括 arXiv:2605.05868v3、通信作者 Yuhong Nan、Huaijin Wang、Shuai Wang 的第一方论文主页，以及由作者主页进入的 GitHub 页面；完整标题、arXiv ID、作者名与 GitHub 组合检索也未找到匹配实现。PDF 虽描述释放材料，但没有给出可取得作者 artifact 的 URL/DOI。AMD 的同名项目、管理 SKILL.md 的同名 TUI 和其他同名论文已被排除，理由见 `docs/literature/skillscope.md`。

这应表述为 **official-repo not verified**，不是证明仓库绝不存在。没有官方 clone、commit、license、依赖或测试可归档，因此不创建虚构的 SkillScope 上游测试目录。TSG 对此方法的实现应保留 `paper-inspired reimplementation / SkillScope-inspired adaptation` 标签，不声称作者代码复用或原成绩复现。

本归档与已有三份来源审计共同构成 WP-01 的有限可核验材料；它们不替代课程项目自身数据集、GT、端到端对照实验或正式研究结果。

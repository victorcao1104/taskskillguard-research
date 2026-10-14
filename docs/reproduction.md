# 复现指南

默认先从仓库保存的输入与预测离线重算，不需要 API key，也不需要作者机器上的 `.env`、原始语料路径或上游 clone。安装依赖可能访问包索引；安装后统计和测试不调用模型。所有新输出放到被忽略的 `work/` 子目录，避免覆盖发布证据。

核心实验代码冻结在 `195620a2d11fbb4b833254d8a5f5b19102b417e3`。请使用包含 `scripts/analyze_results.py`、`src/tsg/evaluation.py` 和原始结果的交付版本；不要假设较早核心提交已经包含后续统计、补充评估和文档。`results/run_manifests/` 保存每次运行的提交、Python 版本及文件 SHA256；`configs/requirements-lock.txt` 是本项目实际环境包版本清单，不是带下载哈希的跨平台制品锁。

交付版通过 `.gitattributes` 禁止自动换行转换，保留实际研究输入和归档证据的原始字节。早期核心提交使用了本机 Git 默认换行规则，因此比较该提交与运行时文件哈希时须区分换行差异；复算请使用交付版的实际输入、raw和逐次运行清单。

## 1. 安装与离线统计：Windows PowerShell

在本仓库根目录执行。要求 Python 3.12（原运行版本 3.12.14）；不要使用原始 corpus 所在目录作为工作目录。

```powershell
py -3.12 -m venv .venv
$tsgPy = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $tsgPy -m pip install -r configs/requirements-lock.txt
& $tsgPy -m pip install --no-deps -e .

$tsgRun = Join-Path (Get-Location) ('work/reproduce-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $tsgRun | Out-Null
foreach ($name in @('configs', 'data', 'src', 'scripts')) {
    Copy-Item -LiteralPath $name -Destination $tsgRun -Recurse
}
New-Item -ItemType Directory -Path (Join-Path $tsgRun 'results') | Out-Null
foreach ($name in @('api', 'development', 'validation', 'held_out', 'mechanistic', 'real', 'transfer', 'judge', 'prompt_ablation', 'run_manifests')) {
    $source = Join-Path 'results' $name
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $tsgRun 'results') -Recurse
    }
}

& $tsgPy -m pytest -q --junitxml "$tsgRun/pytest.xml" --basetemp "$tsgRun/pytest-tmp"
& $tsgPy "$tsgRun/scripts/analyze_results.py" --root $tsgRun --bootstrap-samples 1000 --seed 76420261015
```

测试使用 mock 请求与临时 fixture；不执行下载的 Skill 脚本，也不读取 API key。JUnit 和 pytest 临时目录都在新建副本下。若已有 `.venv`，先确认其 Python 版本与依赖，不要把上游 CaMeL/Progent 的环境混装进本项目。

## 2. 安装与离线统计：Linux / macOS shell

```bash
python3.12 -m venv .venv
TSG_PY="$PWD/.venv/bin/python"
"$TSG_PY" -m pip install -r configs/requirements-lock.txt
"$TSG_PY" -m pip install --no-deps -e .

mkdir -p work
TSG_RUN="$(mktemp -d "$PWD/work/reproduce-XXXXXXXX")"
cp -R configs data src scripts "$TSG_RUN/"
mkdir "$TSG_RUN/results"
for name in api development validation held_out mechanistic real transfer judge prompt_ablation run_manifests; do
  if [ -d "results/$name" ]; then cp -R "results/$name" "$TSG_RUN/results/"; fi
done

"$TSG_PY" -m pytest -q --junitxml "$TSG_RUN/pytest.xml" --basetemp "$TSG_RUN/pytest-tmp"
"$TSG_PY" "$TSG_RUN/scripts/analyze_results.py" --root "$TSG_RUN" --bootstrap-samples 1000 --seed 76420261015
```

非原平台安装可能因 wheel 可用性不同失败，应保留安装错误和实际版本；不要默默替换版本后称完全同环境复现。纯离线机器需预先准备这些版本的 wheel，再以 pip 的 `--no-index --find-links <wheel目录>` 安装。

## 3. 离线结果应该如何核对

分析器从副本读取 benchmark、正式 development/validation/held_out 的解析预测、机制轨迹、真实静态图/模型图及预算账本；写入该副本的 `results/summary/`。核心输出包括：

- `coverage.json`：每轨道已观测/预期、缺失记录和运行完整程度。
- `detection_metrics.{json,csv}`：动作授权/必要性，正标签 `no` 和 `yes` 分列；unknown 另列、覆盖率与包含 abstention 的 recall 同报。
- `runtime_metrics.{json,csv}`、`replay_metrics.json`、`policy_update_metrics.json`：执行、泄漏、任务输出、Replay 状态和 Z3 结果。
- `contract_metrics.{json,csv}`、`consistency_metrics.{json,csv}`、`error_cases.{jsonl,csv}`：合同、重复/格式扰动和错误证据。
- `real_graph_metrics.json`、`budget.json`、`input_inventory.json`、`summary.json`：真实提取覆盖、预算上界、输入指纹及聚合结果。

API 的原始缓存已在 `results/api/raw/<request_hash>.json`；解析预测的 `request_hash` 回链到其中的请求、响应和 usage。离线统计使用已保存解析记录，**不需要加载 key，也不会补发缺失请求**。缓存可以供逐条审计，但当前 runner 不是“严格离线从 raw 全重建”的命令：它先执行 `load_key`，缓存缺失时还会发请求。因此不要用 `run_experiment.py` 代替无 key 的离线统计。

缺失、截断、未完成结果应保留在 coverage 中，不能补成负例。现有派生 V2/V5 是 V1 预测加已保存的 VM redundancy/reference 证据后处理，不是新增模型响应。transfer/judge 的原始结果由补充脚本产生；若交付时统计器尚未整合某补充指标，不能因复制了这些文件就称该指标已自动重算。

重复运行时间戳、state UUID、耗时和输入目录绝对路径可能不同；应对照固定输入哈希、case/model/variant/replicate、预测/判定与指标，不能要求整个 JSON 文件字节完全一致。bootstrap 固定 seed 为 76420261015，默认 1,000 次；只有 3/1/2 个合成模板家族，单家族区间为空，其他区间也不能支持强泛化结论。旧 pilot/pre_review/pre_cache_review 不进入正式预测指标，预算仍包含历史已发生/预留支出。

如要重跑不调用模型的机制实验，请重新建立另一份上述 `work/` 副本，再运行：

```powershell
# PowerShell，变量指向新副本
& $tsgPy "$tsgRun/scripts/run_experiment.py" --phase mechanistic
& $tsgPy "$tsgRun/scripts/analyze_results.py" --root $tsgRun
```

```bash
# Linux，变量指向新副本
"$TSG_PY" "$TSG_RUN/scripts/run_experiment.py" --phase mechanistic
"$TSG_PY" "$TSG_RUN/scripts/analyze_results.py" --root "$TSG_RUN"
```

该命令仅执行可信内存 capability VM。它会重写副本中的机制记录；Original、中和 Replay、参考执行均从新状态开始。它不会启动 Docker、运行真实 Python/Shell Skill、产生真实网络请求或访问模拟路径对应的宿主文件。不要运行 `build_benchmark.py` 来重建离线统计输入：它还读取真实 corpus，且会写新的 benchmark/graphs；离线重算使用交付的冻结输入即可。

## 4. 可选：重新连接自己的只读语料

原始第三方语料和上游完整代码**没有全部上传**。仓库保留 180 条来源/哈希映射、静态图、获准分析的有界文本证据和 API 记录；这不等于完整 source bundle。没有原库也能重算现有统计；重新抽取真实图或调用真实 transfer 则必须有对应原始文件。

适配器固定针对已有 skills.sh 目录结构：`state.sqlite` 的 `materializations(source_native_id, raw_directory, status)`，以及 `raw/`、可选 metadata/occurrences/dedup_decisions。SQLite 用 `mode=ro` 和 `PRAGMA query_only=ON` 打开，文件只读。其他索引 schema 需要显式编写/修改适配配置与实现，不能把任意目录当成相同数据源。

先在新工作副本的 `configs/corpus.local.json` 写本机设置（自行替换 root，不是作者的绝对路径）：

```json
{"root": "/your/existing/skills-sh-run", "adapter": "skills.sh.materializations.v1"}
```

这是本地记录配置；当前 CLI 不自动读取它，下列命令显式取 `root` 并传入适配器。不要修改原始 corpus 或提交个人绝对路径。

```powershell
$tsgCorpus = Get-Content -Raw "$tsgRun/configs/corpus.local.json" | ConvertFrom-Json
& $tsgPy "$tsgRun/scripts/validate_corpus.py" --root $tsgCorpus.root --out "$tsgRun/data/manifests" --sample-size 180
& $tsgPy "$tsgRun/scripts/validate_corpus.py" --verify --out "$tsgRun/data/manifests"
```

```bash
TSG_CORPUS_ROOT="$("$TSG_PY" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["root"])' "$TSG_RUN/configs/corpus.local.json")"
"$TSG_PY" "$TSG_RUN/scripts/validate_corpus.py" --root "$TSG_CORPUS_ROOT" --out "$TSG_RUN/data/manifests" --sample-size 180
"$TSG_PY" "$TSG_RUN/scripts/validate_corpus.py" --verify --out "$TSG_RUN/data/manifests"
```

重新生成 manifest 会把路径映射到本机且只写工作副本。保留其 source_native_id、sample membership、family、split 和内容哈希与发布 manifest 的比较；若原库变化导致样本或哈希不同，这是新数据版本，不可冒充原实验。`--verify` 校验 manifest 引用的现存文件，不会自动重定位旧的绝对路径。完成映射后才能在副本中执行 `scripts/build_benchmark.py` 或真实分析；不要覆盖交付原件。

### 原始来源 ID 的映射

完整映射在 `data/manifests/skills_manifest.jsonl`，以 `skill_id` 连接 `data/graphs/<skill_id>.json`、真实模型结果与人工标注包。`skill_id = "real-" + SHA256(source_native_id)[:16]`；它是本项目键，不是原站 ID。

| 本项目 skill_id | 原始 source_native_id | raw_directory |
|---|---|---|
| `real-73a972f23c7db629` | `caffeinelabs/skills/connector-googlemail` | `9130924e20c5bab427ab90d6` |
| `real-42d5dda6270a7968` | `nomadamas/k-skill/kstartup-search` | `c64178754a105c1e762713bb` |
| `real-086ce64dc89f0932` | `useosint/osint-skills/x-ray-a-company` | `19e207afc48a4d15ddd12744` |

manifest 同时保存 `source_url`、`repo_id`、`publisher_id`、`corpus_relative_path`、`skill_sha256`、逐文件 `file_sha256`、`bundle_sha256`、既有 dedup 记录和 family/split。将 `raw_directory` 接到本机 corpus 的 `raw/` 下定位包，再用 `corpus_relative_path` 定位 SKILL.md；跨 Windows/Linux 需正规化目录分隔符，不能原样使用作者的 `bundle_path/skill_md_path`。上述名称只是样本标识，不是对其恶意性或安全性的判断。

## 5. 可选：有预算的 live API 复跑

只有主动选择重新请求模型时才需要这一节。创建新的 `work/` 副本，保留同一个 `results/api/budget.jsonl` 和缓存，不在多个进程同时写此账本。当前 runner 使用两模型 `gpt-6-luna`、`gpt-4.1-mini`，代码中的累计上限为 **USD 20**；它依据固定单价做本地保守预留，不等于服务商强制额度或最终账单。`configs/experiment.json` 记录设计参数，但部分值也写在 runner/models 中，改配置文件不会自动改变硬编码模型、预算和所有行为。

由运行者指定已有 env 文件的位置，文件只需含 `OPENAI_API_KEY=...`。不要把 key 放在命令行或仓库内；`load_key` 优先读取当前进程 `OPENAI_API_KEY`，仅不存在时读取所传文件。以下只询问文件路径，不显示内容：

```powershell
$tsgEnvFile = Read-Host 'Existing API env-file path'
& $tsgPy "$tsgRun/scripts/run_experiment.py" --phase development --env-file $tsgEnvFile --workers 6
# 前一步结束后才开始下一步；不要同时启动多个 phase
& $tsgPy "$tsgRun/scripts/run_experiment.py" --phase validation --env-file $tsgEnvFile --workers 6
& $tsgPy "$tsgRun/scripts/run_experiment.py" --phase held_out --env-file $tsgEnvFile --workers 6
```

```bash
read -r -p 'Existing API env-file path: ' TSG_ENV_FILE
"$TSG_PY" "$TSG_RUN/scripts/run_experiment.py" --phase development --env-file "$TSG_ENV_FILE" --workers 6
"$TSG_PY" "$TSG_RUN/scripts/run_experiment.py" --phase validation --env-file "$TSG_ENV_FILE" --workers 6
"$TSG_PY" "$TSG_RUN/scripts/run_experiment.py" --phase held_out --env-file "$TSG_ENV_FILE" --workers 6
```

同请求/replicate 哈希命中会复用已有响应；这属于缓存复现，不是独立新样本。要进行独立新采样需要明确新实验设计、独立记录其成本与随机性，不能删除旧账本以绕过总预算。当前每哈希锁与预算锁只保护单进程，不能跨进程保证 USD 20 上限。API 不接收 seed；gpt-4.1-mini 请求 temperature=0，gpt-6-luna 请求 reasoning effort=none；响应/usage/参数以 raw 记录为准。将 held-out 重新请求后用于调参会改变原实验的冻结含义。

真实包模型提取使用 `--phase real`；真实三任务和 Replay Judge 使用 `scripts/run_supplement.py --phase transfer` / `--phase judge`，同样要求 `--env-file <运行者指定路径>`。real/transfer 必须先完成只读本机映射，并确认允许将所选 30 个 pilot 包的有界文本提交模型；本次记录的上限是每包 24,000 字符、12 文件，transfer 使用更小的 20,000 字符窗口。Judge 只发送合成轨迹。真实任务仍是研究者假设上下文；补充结果和空白双标注表不得转换为人工 GT。

## 6. 上游复查与交付边界

上游复现使用各自环境，步骤和许可证见 [literature/upstream_reproduction.md](literature/upstream_reproduction.md)。CaMeL pinned `f083b6b396399d3b3c7f2ddaf613a5945eaf32d8`：解释器子集 106 passed，自定义 21 探针中 15 passed/6 failed；Progent pinned `5be7b63fa96f70bc19b72fbcee81f1c0bcc1a565`：20 个 characterization 观察相符，含不安全行为，不能叫 20 个安全通过。SkillScope 在记录的有限检索中未核实官方仓库，因此本地模块保持 paper-inspired 标识。没有在本指南的离线统计命令中导入或下载这三个上游的生产代码。

要求/完成度逐项对照见 [requirements_matrix.md](requirements_matrix.md)；数据、冻结与解释边界见 [design_amendments.md](design_amendments.md)。人工双标注、真实脚本 OS 沙箱、真实动态 held-out 和上游完整基准仍未完成。现有三阶段 VM trace、P/Q 组件和一次性计划是有限机制实验，不是完整自主 agent。

## 补充表与报告重算

在同一个独立副本中依次运行 scripts/analyze_supplement.py、scripts/analyze_combined.py、scripts/plot_results.py、scripts/write_report.py。它们均从本地结果读取，不调用API；输出写到脚本所在副本。scripts/verify_release.py核对2,724条结果回链，scripts/check_runtime_stability.py复跑固定机制和模型计划。

合成输入、提示在核心冻结后未按held-out调整；三个后续健壮性修补经3,300次运行对比确认不改变已报告结果。新增的提示消融与a_late敏感性检查均明确为事后开发集/统计分析。


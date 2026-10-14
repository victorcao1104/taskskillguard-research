# 第二轮复现指南

第一轮的独立指南和历史结论保留在 [reproduction_v1.md](reproduction_v1.md)、[study_v1_report.md](study_v1_report.md) 和 Git tag `study-v1`。以下所有命令在仓库根目录执行，`python` 指 Python 3.12 虚拟环境解释器；Windows 可替换为 `.venv/Scripts/python.exe`。

## 1. 核验发布证据

```text
python -m pip install -r configs/requirements-lock.txt
python -m pytest -q --basetemp work/check
python scripts/verify_release.py
python scripts/verify_phase2_release.py
```

不需要 API 密钥、Docker 或原始语料。测试默认跳过 Docker 集成；后两项只读核验文件哈希、旧 2,724 条结果回链、第二轮完整网格、重复键、请求指纹、真实样本覆盖、P 输入边界、OS 逐次证据、预算与盲审包。GitHub Actions 执行相同检查。

`results/verification/artifact_manifest.json` 记录发布文件 SHA256。改动派生文件后，该核验应失败；研究者重新发行时才从暂存区生成新 manifest，不应为了隐藏改动而覆盖发布证据。

## 2. 重算表格和图表

先复制一份工作 checkout，保留 `data/`、`results/`、`src/`、`scripts/`、`configs/`、`containers/`。下面会覆盖副本中的派生汇总，但不访问模型或执行第三方脚本：

```text
python scripts/analyze_statistics_v2.py --bootstrap-samples 2000
python scripts/analyze_pipeline_phase2.py --bootstrap-samples 2000
python scripts/run_os_judge_phase2.py
python scripts/plot_phase2.py
python scripts/write_phase2_report.py
```

主要输出为 `results/phase2/pipeline_analysis/`、`results/phase2/figures/` 的 PNG/PDF 和 `docs/phase2_report.md`。按 family 聚类 bootstrap，保存配对效应、区间、精确 family endpoint McNemar、联合 Holm 以及重复的描述性方差。六个合成模板家族不能由数千条嵌套记录扩充成数千个独立样本。

可在副本中运行 `python scripts/run_pipeline_phase2.py` 重新执行保存策略与建议的 capability VM：3,168 条 E3、4,752 条九配置、1,188 条固定动作。它只执行可信有限动作目录，不启动任意脚本。UUID、耗时可不同，应比较动作、判定和指标。新代码拒绝不匹配的冻结输入；历史执行文件和 code hash 均保留。

## 3. 真正的隔离容器复跑

Docker 必须支持 Linux 容器。无需用户目录或 Docker socket 挂载；所有网络正例只访问容器内部 Mock 服务。

```text
docker build -t taskskillguard-os:replication containers
python scripts/replay_os_release.py --image taskskillguard-os:replication --out work/os-replication
```

此命令复用保存的 48 个模型合同，产生 240 次新的容器观察，**不调用 API**。输出必须是尚不存在的仓库 `work/` 子目录，拒绝覆盖发布结果。可先做四次运行的小检查：

```text
python scripts/replay_os_release.py --image taskskillguard-os:replication --out work/os-csv-check --case os-csv-low --oracle-only
```

每次保留 image ID、代码/合同哈希、任务、系统调用、实际输出和资源。新镜像采用修正后的 Oracle；历史正式 E3 固定 `sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`，保存旧 embedded oracle，再由独立外层任务判定重计分。不得把新观察混进原 240 条分母。

基础镜像固定 digest、直接 pip 依赖固定版本；apt snapshot 与全部转依赖未锁定，未来 build 不保证同一个 image ID。历史环境清单在 `results/phase2/os/image_dependency_inventory.json`；精确镜像复放需要保留该 image。本指南提供新的可运行复现实验，不声称逐字节恢复未来联网环境。

原始来源脚本的四个功能任务、27 个接口探针及九个运行失败另列。任意源脚本只有 OS containment；工具适配器的逐调用授权、数据标签不能推广到它们。详见 [phase2_os_sandbox.md](phase2_os_sandbox.md)。

## 4. 只读来源与模型输入

180 包均来自 skills.sh 的 `completed` 索引；`data/manifests/skills_manifest.jsonl` 保留来源、原始 ID、路径、逐文件哈希、family 和 split。SQLite 只读打开。另一机器要把 bundle 路径映射到本机并核对内容，不可将不同文件当同一实验样本。完整原库没有上传；没有原库也能重算现存统计，但不能重新提取或执行来源包。映射方法见历史指南第 4 节。

模型全样本检测采用冻结的 legacy bounded graph；`graph_v2` 是相同窗口的独立离线结构实验，未回填正式模型输入。`python scripts/build_graphs_v2.py` 需要原库，应在工作副本执行。DATA 边增加是结构覆盖指标，不是语义准确率或完整信息流证明。

## 5. 可选的模型 API 复跑

累计预算账本 `results/api/budget.jsonl` 包含两轮与历史失败预留，**不得清空，且只能有一个进程写入**。上限 USD20；单价保守估算不是账单或平台硬配额。使用运行者指定的已有 env 文件，不把 key 放命令行或仓库。

```text
python scripts/run_real_phase2.py --env-file <existing-env-file> --workers 8
python scripts/run_pipeline_phase2.py --api --env-file <existing-env-file> --workers 8
python scripts/run_os_e2e_phase2.py --api --env-file <existing-env-file>
python scripts/run_os_judge_phase2.py --api --env-file <existing-env-file>
```

必须依次完成。真实样本步骤需要已映射原库。本次用户已批准 180 包、每包最多 24,000 字符/12 文件并遮盖可识别凭证格式；分类使用较小的 20,000 字符窗口。其他运行者需要确认自己资料可以提交 API。实际模型为 `gpt-6-luna`、`gpt-4.1-mini`。

同一请求/replicate 的 hash 会命中缓存；缓存复用不是新调用。重新采样、修改提示或使用新模型属于新实验，须另存观察、记录费用，不能据此重新声称原 held-out 未见。Skill 与模型文本始终作为分析数据，无执行权或授权权。

## 6. 人工接续

分别给两位真人 `data/annotation_v2/full/rater_a/` 和 `rater_b/`。coordinator key、模型预测、其他人的答案不应一并发送。项目未代发任何消息。

全量为 8,188 单位/人，可先做 priority 的 457 单位/人，但小包不是完整或代表性 GT。导入、独立性声明、三层标签、第三人复核及 κ 重算见 [phase2_annotation.md](phase2_annotation.md)。目前真人标签均空；真实检测准确率、F1、人工一致率保持 pending。

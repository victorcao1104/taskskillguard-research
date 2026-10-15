# 第四轮复现与证据核验

第四轮全部新增在 `study-v4`，旧基线为 `a666de55206ece2dcdbb669d083aa175a50dea5a`。基线清单的18,444个文件必须保持原始字节；所有已有目录中的旧结果都不是待重算覆盖的缓存。

## 无网络核验

需要 Python3.12 和 `configs/requirements-lock.txt`。仓库内的命令不依赖模型密钥，也不执行真实 Skill。

```console
python -m pytest -q --basetemp work/phase4-tests
python scripts/verify_phase4_release.py --hash-manifest results/phase4/provenance/release_hashes.json
```

核验包括旧文件、批准的有界源文本、冻结请求哈希、响应与解析一致性、完整条件网格、历史费用前缀、预留与结算、Replay 原始回执和评分、独立家族统计，以及未提供真人真值的限制。哈希验证的是保存文件之间的一致性，不是供应商签名、账单或对历史容器隔离的密码学证明。

有原始180样本路径的机器还可只读核验原始语料：

```console
python scripts/verify_phase4_release.py --verify-corpus
```

默认核验不依赖 `C:` 下的原始下载库，因此可以在 GitHub Linux CI 运行。原始 `state.sqlite` 没有被新一轮流程写入；本轮沿用已按 completed 状态抽取并保存来源的180份清单。`sources/` 是只读同步材料。

## 重新计算分析

先复制工作区或确认自己只是在生成相同结果，再运行：

```console
python scripts/analyze_phase4.py
python scripts/report_phase4.py
```

第一个命令从384个冻结任务及逐请求记录计算完整分母统计，拒绝缺项、额外项或重复项。第二个生成 CSV、科学图和费用汇总，并生成空白人工包；发现已有标签、笔记、状态变化或候选总体变化时会拒绝覆盖。已填标注仍应放入独立版本目录。两者不发起 API。输入/响应哈希保存在分析汇总中；主分析使用2,000次固定种子的家族配对 bootstrap。

`extraction_primary` 保留首次观察；`extraction_rescored` 只修评分；`extraction_revised` 是实现修复后在同一已见样例上的回归。重新运行最新提取器不能声称重新生成了历史首版代码的观察。首次保存图可用于同图评分复查，修订脚本快照也已存档。

## 付费重现的限制

主采集冻结文件在 `results/phase4/acquisition/`；384个首答及API错误在 `results/phase4/api/`。来源协议修订的24个任务独立冻结在 `results/phase4_discovery_followup/acquisition/`。默认准备命令不读密钥、不联网，实际采集必须明确提供 `--execute` 和已授权配置路径。不要把密钥正文写入命令、文档、结果或提交。

主流程和修订流程共用 `results/phase4/api/budget.jsonl`，同一时刻只运行一个采集进程。账本继承旧历史和未结算预留，缓存写入采用保守高价。用户新增15美元授权记录在 `budget_revision.json`。如需新的独立复制实验，应建立新目录、固定新的复制编号和预算授权，不能删除响应或账本来迫使重跑。

实际模型或供应商版本可能变化，新的首答不能保证与历史逐字相同。已保存的请求与响应能够离线重算评分，不能消除模型非确定性。

## 容器证据

`results/phase4/replay/` 保存冻结174条件、每次 worker、容器参数、stdout/stderr、产物、效果和独立评分。镜像固定为 `sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`。

默认发布核验只重新评分保存的回执，不启动 Docker，不执行 worker。若重新运行容器，应另建复制输出目录保留本轮结果。这里的 worker 是项目生成的有限受控程序，没有把原 Skill 源码导入执行。无外网容器内的回环HTTP只用于验证工具效果。

## 人工标注

`data/phase4/human_review/rater_A.jsonl` 和 `rater_B.jsonl` 各217项，只有候选ID/来源跨度、来源哈希和空白标签；提取器的操作、资源、风险状态、敏感性与摘要不作为答案展示。两人独立核对同目录 `sources.jsonl` 中的源码，该文件只含180份有界源码和哈希，不含图或模型预测；第三人复核分歧。应另抽零候选、被截断和不支持区域以评估漏检，不能仅根据候选包计算全语料召回。

当前包没有填入模型判断，§12.4仍由用户安排。保存结果后，先冻结人工版本，再设计后续测试，避免人工标签泄漏到同一个测试集的调参过程。

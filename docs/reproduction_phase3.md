# 第三轮复现与证据索引

本轮在原私有仓库的 `study-v3` 分支实施。原始基线为 `study-v2` / `91d368833b298a558ea70778100a27ba038c3527`；前两轮文件逐一保留，第三轮结果位于 `results/phase3/`。请在独立克隆中重算，避免改写已发布的第三轮证据。

## 无 API 的验证

安装 `configs/requirements-lock.txt` 中的依赖，使用 Python 3.12。Windows 可将 `python` 换成 `.venv/Scripts/python.exe`。

```text
python -m pytest -q --basetemp work/phase3-check
python scripts/verify_release.py
python scripts/verify_phase2_release.py
python scripts/verify_phase3_release.py
```

第三个验证器检查前两轮全部 10,650 个基线文件、正式冻结及两次修订链、精确实验条件集合、原始响应指纹、累计预算和空白人工标签。第二次修订发生在主采集后，只改变本地路径查找，三份预处理数据逐字节等价。最终 release manifest 包含本轮代码及证据，清单自身不自引用。普通 CI 不需要 API 密钥、Docker 或本机原语料。

## 从已保存原始响应重新分析

```text
python scripts/analyze_phase3.py
python scripts/report_phase3.py
```

这些命令不调用模型，也不执行 Skill。首次分析生成时间不同，不能把整个 JSON 的逐字节变化解释为统计变化。所有比例均同时保留计划分母与已判定分母。家族 bootstrap 固定 seed=20261015、2,000 次；区间为描述性边际区间，不报告多重检验后的显著性。

在独立克隆中执行 `python scripts/run_phase3.py --stage runtime` 可重跑有限内存 VM。它读取已保存 P/Q 结果；新任务转换使用受信适配器，不执行任意 Skill 源码。随机审计标识、墙钟时间等字段不要求逐字节相同，核心决策、效果和计数应相同。

阶段解析重放使用 `scripts/replay_phase_protocol_phase3.py --include-real`，输出位于独立 `results/phase3/phase_protocol/`，不调用 API；它拒绝覆盖已经存在的输出目录。完整发布中该目录已包含结果，重新生成应在独立副本中进行，并保留原件。

余额恢复后的 174 条请求是独立补跑，计划、代码冻结、原始响应和累计账本均在 `results/phase3_followup/`。见 [补跑规则](phase3_resume.md)。`scripts/report_followup_phase3.py` 仅作离线分析：保留原始、阶段重放和补跑汇总三个层次，所有预选补跑均按固定规则使用，不按成功与否挑选。该命令也拒绝覆盖已存在的分析目录。配对分歧基于双方协议有效的同一动作，仅衡量一致性，不是准确率；句法围栏诊断为事后分析，不更改正式候选。

## 重新取得模型与 OS 观察

历史结果已经包含原始模型响应，因此复核不需额外付费。若确需重新采样，必须建立独立新轮次并记录新冻结；不要删除缓存把重试伪装成首次观察。本轮原驱动的恢复命令如下，已完成的 job/hash 会复用：

```text
python scripts/run_phase3.py --stage factorial --env-file <已授权配置文件>
python scripts/run_phase3.py --stage regression --env-file <已授权配置文件>
python scripts/run_phase3.py --stage new --split development --env-file <已授权配置文件>
python scripts/run_phase3.py --stage new --split validation --env-file <已授权配置文件>
python scripts/run_phase3.py --stage new --split held_out_test --env-file <已授权配置文件>
python scripts/run_phase3.py --stage os-api --env-file <已授权配置文件>
python scripts/run_phase3.py --stage real --env-file <已授权配置文件>
python scripts/run_os_phase3.py --workers 3
```

不要同时运行多个 API 驱动。每次调用都进入同一个累计 20 美元账本，前两轮账本字节必须保持完整前缀；未知账单保留预留金额。仓库中不保存配置文件或密钥。

OS 复现实验要求原固定镜像 `sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`，运行 12 个原有任务、两次容器重复、正确合同与四种模型合同、guard 开关，共 240 条。它验证有限工具适配器的实际效果；不等于任意源码均有逐工具权限保护。没有该镜像时只能复核已保存轨迹，不能声称完成 OS 复跑。

## 证据目录

| 路径 | 内容 |
| --- | --- |
| `docs/phase3_design.md`、`phase3_plan.md` | 最初设计与实现计划，原文冻结保留 |
| `results/phase3/provenance/` | 旧文件哈希、首次/修订冻结、检查点中断证据、测试及发布清单 |
| `data/phase3/synthetic_cases.jsonl` | 16 家族、256 个新任务与手写预期输出 |
| `results/phase3/api/` | 条件记录、首次原始响应、累计账本 |
| `results/phase3/runtime/` | 同一旧 P/Q 回归、新 P/Q 运行、消融与正交探针 |
| `results/phase3/os/` | 实际容器输出、工具事件、独立任务评分 |
| `data/phase3/real_prepared.jsonl` | 180 个已完成下载样本的有界证据及固定动作候选 |
| `results/phase3/analysis/` | 完整 JSON、CSV 对照表、可导出图 |
| `results/phase3/phase_protocol/` | 同一响应的阶段解析重放，零新增模型请求 |
| `results/phase3_followup/` | 174 条独立补跑、继承的预算账本、补跑前冻结与前后对照 |
| `data/phase3/real_annotation_handoff.jsonl` | 新语境对应的空白人工标注交接数据 |

原语料保持只读，来源、原始标识、源文件路径和哈希可从 `data/manifests/skills_manifest.jsonl` 追溯。新人工交接数据有 5,133 个 action-context 单元，双人标签与复核标签均空白。旧优先标注包仍保留，但新旧节点不能直接按 ID 互换，需按来源、文件哈希与文本范围核对。

主实验累计账本停在 $13.5163768，后续费用只记入继承它的补跑账本；不要把两个累计数字相加。历史未知账单的预留不会因为补跑成功而自动释放。补跑后的最新累计值以 `results/phase3_followup/summary.json` 为准。

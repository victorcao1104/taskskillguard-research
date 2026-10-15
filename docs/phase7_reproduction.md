# 第七轮复现

旧轮文件保持原样；本轮新增评估只使用合成数据和已保存回答，不新增真实 Skill 语料或人工标注。

## 无费用核验

Python 3.12，安装 `configs/requirements-lock.txt`；如运行全部历史测试另装 `configs/phase5-requirements.txt`。运行：

```
python -m pytest -q --basetemp work/phase7-tests
python scripts/publish_phase7.py
python scripts/analyze_phase7.py
```

核验器检查 25812 个基线文件字节、研究冻结摘要、全部请求摘要与严格响应解析、可执行证据、真值、原地恢复回放、容器结果一致性、预算继承和发布文件摘要。核验只重建纯内存计算，不调用 API 或外部工具；已有输出不同即报错，不覆盖旧记录。

最终发布清单为 `release_hashes_v2.json`。初版清单生成期间，独立审查补入了最终核验段落；初版清单及当时审查文件的精确前缀另存保留。只更新发布摘要与核验入口，实验数据和分析不变。

## 重建计算

```
python scripts/experiment_phase7_v2.py
python scripts/experiment_phase7.py recovery
python scripts/experiment_phase7.py integrated
```

容器重放入口为 `python scripts/container_phase7_v2.py recovery` 和 `integrated`。已保存成功批次只读复用；有失败或遗留发送意图则停止，不自动重试。镜像、隔离参数、载荷与代码摘要见各 `container_batches_v2/*/plan.json`。初版载入顺序失败保存在 `container_batches/001`，见修正记录。容器没有网络、主机挂载、密钥或真实工具；每个条件为新建内存状态，多条件共享一个批容器。

## 模型采集与预算

`scripts/run_phase7_v3.py` 默认核验补充冻结、覆盖修正和请求清单，不发送，并使用修正后的费用读取锁。`--execute --env-file <已授权本地配置>` 才调用供应商；密钥不入仓库。仓库已有结果会复用，不自动二次发送。当前轮最终汇总由 `scripts/finalize_phase7.py` 完全离线重建，原因见 [采集后修复](phase7_postacquisition_repair.md)。新采集须使用新版本输出与追加预算，不能删除记录来规避无重试设计。

三协议同公开输入、两模型、统一4000输出上限。480个预定条件含48次额外重复。旧缓存不计入本轮新回答。预算是保守使用量上界，不是供应商发票；以账本最新预留/结算状态为准。

## 文件导航

- `docs/phase7_design.md`：先于新留出评估冻结的研究问题与方案。
- `src/tsg/truth_v7.py`：独立参考聚合；`evidence_v7.py`：生产有限求解器和证据核验。
- `src/tsg/recovery_v7.py`：相同权限、状态与调用额度下的选路/重试对照。
- `results/phase7/semantics/`：参考真值、解析覆盖和独立执行差分。
- `results/phase7/api/`：原始请求与回答、逐条件解析、账本。
- `results/phase7/recovery/`、`integrated/`：实际执行轨迹和容器批证据。
- `results/phase7/analysis/`：逐候选、逐案例、家族配对与汇总。

所有结论限于有限 DSL、公开世界与路线目录。not_applicable 是适用性分类；unknown 仍可能来自开放目录、世界分歧或混合适用性。求解器枚举收益不能写成模型能力收益，可信授权网关的安全性也不能归功于模型。

# TaskSkillGuard Implementation Plan

> 本文件保留初始计划。最终执行状态、有限替代和未完成项以 `requirements_matrix.md`、`final_report.md` 为准；下列原始清单不是完成声明。

**Goal:** 完成可复现的论文启发实验，保留可审查证据。
**Architecture:** 独立 corpus、graph、policy、sandbox、benchmark、models、evaluation 模块。
**Tech Stack:** Python 3.12、SQLite只读、AST、Z3、JSON Schema、pytest、OpenAI Responses API。
**Spec:** [design.md](design.md) 与用户提供的实验手册。

## Global constraints

只读原始语料；只在独立目录写输出；API 总预算 USD 20；仅两指定模型；无真实恶意副作用；私有 GitHub；未知不算安全；不冒充人工标注。

## Review focus

路径/符号链接越界；权限比较 UNKNOWN；不可信文本扩权；模型输出丢失/错位标签；统计分母及样本家族泄漏。

## Tasks

- [ ] 1. 来源审计：论文全页覆盖，官方仓库 commit/license/function，最小可运行测试。输出 docs/literature/ 与 source_audit.md。
- [ ] 2. corpus.py：readonly_connection、build_manifest、group_split。先测试 completed 筛选、原始哈希不变、家族不跨 split，再实现。输出 180 条候选与30条 pilot、抽样审计。
- [ ] 3. policy.py 与 sandbox.py：exact match、canonical path/URL、SMT subset、ledger、labels、lease、mock tool execution。先写允许/拒绝/未知及副作用测试，再实现；任何无效中和不当必要证据。
- [ ] 4. graph.py 与 benchmark.py：指令/AST节点及跨层边，受控 fixtures/Oracle/低高边界任务与攻击。验证 provenance、跨文件调用、无效重放和 ground truth 独立性。
- [ ] 5. models.py：两模型结构化解析、可信 ceiling 与隔离 Q、原始 V0、Judge。预算预留、失败分类、请求缓存及原始响应。先测预算/格式失败，再 smoke test。
- [ ] 6. run_experiment.py：pilot 后冻结；E0–E9、消融和 held-out。记录实际运行模式和所有不支持项。
- [ ] 7. evaluate.py：按家族 bootstrap、精确分母、自动生成 CSV/图/报告、成本、五个可复核错误案例。
- [ ] 8. 全项目测试与独立 review；敏感内容检查；创建并推送私有 repo；验证远端文件/commit。


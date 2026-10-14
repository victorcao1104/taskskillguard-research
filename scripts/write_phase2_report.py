"""Generate an auditable Chinese phase-2 report from saved results, without API calls."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tsg.evaluation import budget_summary

INPUTS = (
    'results/phase2/pipeline_analysis/summary.json', 'results/phase2/graphs_v2/summary.json',
    'results/phase2/contracts/summary.json', 'results/phase2/contracts/approval_arms.json',
    'results/phase2/lifecycle/summary.json', 'results/phase2/flow/summary.json',
    'results/phase2/os/source_summary_final.json', 'results/phase2/os/source_runs.json',
    'results/phase2/os/resource_summary.json', 'results/phase2/os/replay_results.json',
    'results/phase2/os/typed_replay/comparisons.json', 'results/phase2/os/replay_multiaction/comparisons.json',
    'results/api/budget.jsonl', 'docs/phase2_oracle_amendments.md',
    'results/phase2/os/replay_summary_final.json', 'results/phase2/pipeline/planner.jsonl',
    'results/summary/detection_metrics.json',
    'results/phase2/figures/manifest.json', 'scripts/write_phase2_report.py', 'scripts/plot_phase2.py',
    'results/phase2/os_judge/summary.json',
    'docs/study_v1_report.md',
)


def read(root, path, default=None):
    target = root / path
    return json.loads(target.read_text(encoding='utf-8')) if target.exists() else default


def ratio(n, d):
    return f'{n}/{d} ({100*n/d:.1f}%)' if isinstance(n, (int, float)) and isinstance(d, (int, float)) and d else f'{n}/{d} (NA)'


def fmt(value, digits=3):
    if value is None:
        return 'NA'
    return f'{value:.{digits}f}' if isinstance(value, float) else str(value)


def measured(row, metric, scale=1):
    value = row.get('resources', {}).get(metric, {})
    mean = value.get('mean')
    return f"{fmt(mean / scale) if mean is not None else 'NA'} (n={value.get('n_measured', 0)})"


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]) + '\n'


def _goal_count(row):
    if 'n_goal_success' in row:
        return row['n_goal_success']
    if row.get('goal_success_rate') is None:
        return None
    value = row['goal_success_rate'] * row['n_valid_runs']
    if abs(value - round(value)) > 1e-7:
        raise ValueError('Invalid saved goal rate: integer numerator cannot be recovered')
    return round(value)


def _budget(root):
    path = root / 'results/api/budget.jsonl'
    return budget_summary(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()) if path.exists() else None


def planner_provenance(root):
    path = root / 'results/phase2/pipeline/planner.jsonl'
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
    result = []
    for model in sorted({r['model'] for r in rows}):
        selected = [r for r in rows if r['model'] == model]
        hashes = {r['request_hash'] for r in selected if r.get('request_hash')}
        result.append((model, len(selected), len(hashes), len(selected)-len(hashes)))
    return result


def build_report(root=ROOT, *, allow_partial=False):
    root = Path(root)
    analysis = read(root, INPUTS[0], {})
    os_judge = read(root, 'results/phase2/os_judge/summary.json', {})
    complete = analysis.get('analysis_status') == 'complete_saved_counts' and all(
        analysis.get('track_count_completion', {}).get(track) is True for track in ('pipeline', 'real_180', 'os_e2e')) and (
        not os_judge or os_judge.get('complete') is True)
    if not complete and not allow_partial:
        raise ValueError('ANALYSIS_INCOMPLETE: regenerate the analyzer after every planned track is saved; use --allow-partial only for an explicitly interim report')
    completion = analysis.get('track_count_completion', {})
    graph = read(root, INPUTS[1], {})
    contracts = read(root, INPUTS[2], {})
    approvals = read(root, INPUTS[3], {})
    lifecycle = read(root, INPUTS[4], [])
    flow = read(root, INPUTS[5], {})
    source = read(root, INPUTS[6], {})
    resources = read(root, INPUTS[8], {})
    runtime = analysis.get('runtime', [])
    lines = ['# TaskSkillGuard 第二轮自动化研究报告', '',
             f"生成时间：{datetime.now(timezone.utc).isoformat(timespec='seconds')}。状态：{'自动化计划记录齐全；真人标注仍 pending' if complete else '中间快照；模型实验 pending，不得当作最终比较'}。", '',
             '本报告依据已保存的原始记录与聚合结果生成。比例均附分子和分母；未知、协议失败、缺失运行不记为安全成功。真实语料的授权与必要性尚无真人真值，因此不报告其准确率、F1 或 Cohen’s κ。', '',
             '## 研究设计与证据边界', '',
             '分离条件中的可信任务规划器 P 仅接收任务及有限工具说明；不可信分析器 Q 可读取 Skill、动作图与 Replay，但其声明只能作为证据。混合对照故意向合同生成器提供不可信 Skill。运行时实际使用生成的合同，而不是用 Oracle 上限替换错误授权。正确合同、模型分离合同与模型混合合同分别报告。任务完成还要求必需效果出现；安全成功要求未出现固定任务真值中的未授权执行。', '',
             table(['轨道', '能支持的结论', '不能支持的结论'], [
                 ('真实语料静态分析 / 模型分类', '结构接受率、覆盖与模型分歧', '没有真人标注的语义准确率'),
                 ('真实源码隔离试跑', '指定入口的兼容性与少量功能任务', '所有语料可执行或任意源码逐工具拦截'),
                 ('Docker 工具适配器', '实际文件、进程、HTTP/SMTP/SQLite/Git 的有限任务效果', '绕过适配器的任意程序都受合同保护'),
                 ('能力 VM 闭环 P/Q', '合同生成、证据接收、Replay、守卫、参考恢复的有限接口闭环', 'OS 资源消耗或开放世界端到端成功率'),
                 ('SMT / 生命周期 / flow 探针', '明确支持子集内的规则性质与构造反例', '不受限 JSON Schema 或自然语言语义证明'),
             ]),
             '源码与任务按家族划分；重复模型调用和重复容器运行不是新的独立家族。保留第一次失败、重试、未知和 Oracle 修订。预算包含第一轮与试运行，不能只呈现本轮成功调用的成本。', '',
             '动作图、确定性权限与来源标签分别借鉴 SkillScope、Progent、CaMeL 的思路；本实现与上游复现范围不等同。论文版本、官方仓库确认状态及已有局部复现见 [来源审计](source_audit.md) 和 [上游复现说明](literature/upstream_reproduction.md)。', '',
             '## RQ 与 E0–E9 结果索引', '',
             table(['实验 / 研究问题', '本轮证据', '解释边界'], [
                 ('E0 兼容性', '源码运行与 unsupported 报告、Docker 资源记录', '入口 smoke 与完整功能分开'),
                 ('E1 / RQ1 检测', '180 语料的两模型、三任务语境、原文/图条件；合成任务另有冻结标签', '真实语料真人标签 pending'),
                 ('E2 / RQ1,RQ5 Replay', '类型保持 neutralization 与原始/Replay/参考三条轨迹', '未触发、协议错误、目标失败均不能断言冗余'),
                 ('E3 / RQ2 执行', '正确/模型合同 × guard 条件；能力 VM 与 OS 分开', '仅有限可信适配器保证'),
                 ('E4 / RQ3 信息流', '10 个显式 secret/derived/public/opaque 探针与 no_taint', '构造机制，不是语料泄漏率估计'),
                 ('E5 / RQ4 信任分离', '分离/混合合同、双账本、未授权扩权、错误 grant', '未把模型输出修成 Oracle 合同'),
                 ('E6 / RQ6 三角必要性', 'original / comparable replay / trusted reference 与 no_triangulate', '参考轨迹证明存在可行替代，不证明所有动作必要性'),
                 ('E7 / RQ2,RQ6 租约', '独立 expiry 与 quota 目标；静态/收缩/租约四条件', 'stage 在合同探针中验证，主 VM 不是 stage 效果实验'),
                 ('E8 / RQ6 差分', '有限任务格式变形与精确 scope 一致性', '不是一般自然语言同义改写证明'),
                 ('E9 / RQ5,RQ6 泛化成本', '两模型九消融、家族统计、Token/API、CPU/RAM', '小家族统计仅探索性'),
             ]), '',
             '## E0：实际源码兼容性与资源', '']
    if source:
        lines += [f"执行了 {source.get('distinct_sources_executed')} 个不同源码入口，共 {source.get('source_runs_including_development_retry')} 次运行（保留开发重试）；最终入口状态为 {source.get('status_by_distinct_source_latest')}。功能任务成功 {source.get('functional_task_successes')}/{source.get('functional_task_sources')}，其中 held-out 首次运行成功 {source.get('heldout_first_run_task_successes')}；另有 {source.get('interface_smoke_sources')} 个仅接口探针。不能把接口正常退出计作任务成功。", '']
    else:
        lines += ['源码运行结果 pending。', '']
    if resources:
        rows = []
        for name, r in resources.get('groups', {}).items():
            rows.append((name, r['runs'], fmt(r.get('cpu_seconds_tracer_and_payload', {}).get('mean')),
                         fmt(r.get('memory_peak_bytes_whole_container', {}).get('mean', 0) / 1048576),
                         fmt(r.get('container_wall_seconds', {}).get('mean'))))
        lines += [table(['来源', '实际运行数', '均值 CPU 秒', '均值容器峰值 MiB', '均值容器墙钟秒'], rows),
                  'CPU 包含 tracer/payload，峰值内存包含容器监督器与 fixture，早期 payload 计时还包含 Oracle；均不是模型推理资源。来源：[资源原始汇总](../results/phase2/os/resource_summary.json)。', '']
    lines += ['## E1：图提取与真实语料模型覆盖', '']
    if graph:
        rows = []
        for key in ('v1_same_input', 'v2'):
            r = graph[key]
            rows.append((key, r['candidate_actions'], ratio(r['known_resource_actions'], r['candidate_actions']),
                         ratio(r['code_known_resource_actions'], r['code_candidate_actions']), r['edge_counts'].get('DATA', 0),
                         r.get('candidate_source_sink_data_pairs', 0), r['unresolved_records']))
        lines += [table(['提取器', '候选动作', '已知资源', '代码已知资源', 'DATA 边', 'source→sink 对', '未解析记录'], rows),
                  f"两版均读取同一 {graph['skills']} 个 Skill、{graph['files_analyzed']} 个文件，单 bundle 上限 {graph['limits']['max_chars_per_bundle']} 字符与 {graph['limits']['max_files_per_bundle']} 文件；{graph['truncated_files']} 个文件截断、{graph['omitted_files']} 个文件因边界省略，源文件变化 {len(graph['source_changes'])}。", '',
                  'v2 增加 Python AST 的常量绑定、简单路径与候选 DATA 传播，但所有图均声明 analysis_complete=false。当前语料的代码资源状态只包含 literal/lexical_literal/unknown，resolved_constant 为零；变量解析能力仅由针对性测试证明。更多 DATA 边与更少 CALL/RETURN 不等于语义更准确。未建模调用、跨函数全局状态、循环固定点与解析失败均显式记录。新增 AST graph_v2 是独立离线覆盖对比，没有追溯替换冻结的模型实验输入，不能把其覆盖变化归因于 P/Q 消融效果。', '',
                  '[图协议与限制](phase2_graphs.md)；[覆盖原始计数](../results/phase2/graphs_v2/summary.json)。', '']
    real = analysis.get('real_180', {})
    if completion.get('real_180') is True:
        lines += [table(['划分', 'Skill / 家族', '提取保存/计划', '分类保存/计划'], [
            (split, f"{r['n_skills']} / {r['n_families']}", f"{r['n_extractions']}/{r['n_expected_extractions']}",
             f"{r['n_predictions']}/{r['n_expected_predictions']}") for split, r in real.get('inventory', {}).items()]),
            table(['held-out 模型', '提取状态', '接受/拒绝节点', '含 unresolved 的记录'], [
                (r['model'], r['status_counts'], f"{r['n_accepted_nodes']}/{r['n_rejected_nodes']}", r['n_records_with_unresolved_graph'])
                for r in real.get('coverage', []) if r.get('track') == 'source_graph_extraction' and r['split'] == 'held_out_test']),
            table(['held-out 语境/条件/属性', '两模型均确定的一致', '未知或缺失 / 全部动作对'], [
                (f"{r['context']}/{r['variant']}/{r['attribute']}", ratio(r['n_agree_decided'], r['n_both_decided']),
                 f"{r['n_unknown_or_missing_pairs']}/{r['n_expected_action_pairs']}")
                for r in real.get('cross_model_agreement', []) if r['split'] == 'held_out_test']),
            '模型间一致性只是分歧指标：两者可以同时错误；不能替代真人准确率。全部 development/validation/held-out 覆盖和 unknown 分布见聚合 JSON。', '']
    else:
        lines += ['真实语料模型轨道尚未全部写入最终分析快照（pending），暂不生成模型比较表。', '']
    historical = read(root, 'results/summary/detection_metrics.json', [])
    historical = [r for r in historical if r.get('split') == 'held_out_test' and r.get('replicate') == 'pooled'
                  and r.get('positive_label') == 'no' and r.get('variant') in ('v0', 'v1', 'v2', 'v5')]
    if historical:
        lines += ['合成任务的已冻结第一轮检测结果沿用原始记录，正类为 no（未授权/不必要）；这里不重新调用模型或用新增图覆盖旧输入。该真值来自研究者构造任务，与真实语料真人真值不同。', '',
                  table(['历史 held-out 模型 / 版本 / 属性', 'TP / FP / FN', 'Precision / Recall / F1', '可判定 / 计划观察'], [
                      (f"{r['model']} / {r['variant']} / {r['attribute']}", f"{r['tp']} / {r['fp']} / {r['fn']}",
                       f"{fmt(r['precision'])} / {fmt(r['recall'])} / {fmt(r['f1'])}", f"{r['n_decided']}/{r['n_expected_observations']}") for r in historical]),
                  'v2/v5 的历史检测标签还包含 Replay/参考轨迹的有限证据后处理，并非新增独立模型调用。历史统计与误例详见 [第一轮报告](study_v1_report.md)。', '']
    lines += ['## E3、E5、E9：P/Q 闭环与九项消融', '',
              '以下主表只使用 held_out_test；all_splits_descriptive 不用于声称泛化。未执行的必需动作包括分类器移除、Replay 移除和其它缺失，不能仅用守卫 deny 次数衡量任务损害。no_smt 只移除合同迁移比较，保留独立的证据 scope 验证与同任务约束；其空效果不能解释为所有 SMT 均无价值。no_guard 旁路整个共享守卫，因此同时移除 scope、taint 与 lease 检查，不是 scope 的孤立消融；no_taint 和 no_lease 才是在守卫仍开启时分别移除该项。', '',
              '旧 E3 合同即使通过 JSON 解析，也可能在原始响应中声明 unknowns。分析器按 request_hash 回查这些声明，将关联运行排除在可判定成功率之外；合同、执行轨迹与原始状态均保留，不把 fail-closed 或解析成功当作已知安全。', '']
    lines += ['分离 P 的可信任务在多个攻击变体中相同，客户端会复用同一 replicate 的相同请求 hash。两次 replicate 使用不同 hash；记录条数不等于独立模型调用数。Q 建议复用第一轮已冻结的实际模型计划（textual_guard=false），本轮未重新独立采样 Q。P 参考计划来自受限动作目录，只执行可信适配器，不解释任意生成程序。no_trust 改变合同来源，但参考路线仍来自分离的可信规划器。', '']
    uncertainty = analysis.get('e3_contract_uncertainty_recovery', {})
    if uncertainty:
        lines += [f"E3 原响应审核：{uncertainty['generated_contract_slots']} 个生成合同条件中，{uncertainty['declared_unknown_contract_slots']} 个条件声明不确定，关联 {uncertainty['declared_unknown_raw_responses']} 个不同原响应；{uncertainty['uncertainty_affected_rows']} 条运行从可判定率排除。已核对 {uncertainty['checked_raw_responses']} 个原响应，未验证运行 {uncertainty['unverified_rows']}。这些是条件/响应/运行三种不同计数，原始执行文件不变。", '']
    provenance = planner_provenance(root)
    if provenance:
        lines += [table(['P 模型', '已保存条件记录', '唯一请求 hash', '重复 hash 记录'], provenance),
                  '唯一 hash 也不能直接代替收费调用次数：传输失败/重试与历史缓存需由 reservation 账本和原始响应核对。', '']
    if completion.get('pipeline') is True:
        selected = [r for r in runtime if r.get('track') == 'P_Q_pipeline_ablation' and r['split'] == 'held_out_test']
        for row in (r for r in selected if r['variant'] == 'full'):
            lines += [f"主条件 {row['model']}：可判定 {row['n_valid_runs']}/{row['n_runs']}，未知 {row['n_unresolved_runs']}，任务完成 {ratio(row['n_goal_success'], row['n_valid_runs'])}。" +
                      ('无可判定主条件，不能报告其成功率或从该消融推断守卫效果。' if not row['n_valid_runs'] else
                       '百分比仅针对可判定条件；未知覆盖损失必须同时报告。'), '']
        lines += ['如果 full 与 no_guard 的已知轨迹都没有越权，主闭环结果没有提供该比较的安全增益证据；需要与固定攻击轨道及 OS 实际效果分别解释。不同条件的 unknown 数量不同，不能把选择后的成功率直接当作相同分母的改进。', '']
        lines += [table(['模型 / 消融', '任务成功', '越权 / 固定机会', '泄漏 / 机密机会', '漏掉必需动作 / 必需总数', '未知运行'], [
            (f"{r['model']} / {r['variant']}", ratio(r['n_goal_success'], r['n_valid_runs']),
             ratio(r['n_unauthorized_execution'], r['n_attack_opportunities']), ratio(r['n_secret_leak'], r['n_flow_opportunities']),
             f"{r['n_required_actions_omitted']}/{r['n_required_actions']}", r['n_unresolved_runs']) for r in selected]),
            table(['E3 模型 / 合同 / guard', '任务成功', '越权 / 机会', '合法就绪请求误拒绝'], [
                (f"{r.get('model', 'oracle')} / {r['policy_origin']} / {r['mode']}", ratio(r['n_goal_success'], r['n_valid_runs']),
                 ratio(r['n_unauthorized_execution'], r['n_attack_opportunities']), ratio(r['n_false_guard_denials'], r['n_legitimate_ready_attempts']))
                for r in runtime if r.get('track') == 'E3_closed_loop' and r['split'] == 'held_out_test']),
            '固定动作回放轨道单独保存于 runtime 的 fixed_actions_mechanistic；它用于定位机制，不能充当模型从零完成任务的证据。安全分母是预先固定的未授权机会，不能因模型未生成危险动作而缩小分母。', '']
    else:
        lines += ['闭环 P/Q 及九项消融尚未完整保存（pending），本节不填零值或预期结果。', '']
    lines += ['## 实际 OS 工具执行：正确合同与模型合同', '',
              'OS 外层任务 Oracle 使用 task_text_and_required_effects_v2：HTTP-low 必须保存 READY，SMTP-high 必须同时有合法草稿和发送；全部任务均核对必需工具效果。保留镜像原 goal 布尔值，修订独立计分且发生于 OS 模型合同生成前。见 [Oracle 修订说明](phase2_oracle_amendments.md)。', '']
    os = analysis.get('os_e2e', {})
    if completion.get('os_e2e') is True:
        lines += [f"已保存运行 {os['n_saved_runs']}/{os['n_expected_runs']}、模型合同 {os['n_saved_contracts']}/{os['n_expected_contracts']}；{os['n_fixture_cases']} 个任务属于 {os['n_fixture_families']} 个 fixture 家族。", '',
                  f"研究容器记录共 {resources.get('runs', 0) + os['n_saved_runs']} 次：源码/Replay 研究 {resources.get('runs', 0)} 次，加正式 OS 条件 {os['n_saved_runs']} 次；已复用的正确合同基线只计一次。单独的安装验证、集成测试和可移植 CLI 自检不加入研究分母。", '',
                  table(['合同 / 模型 / guard / 语境', '任务成功', '越权 / 机会', '缺失必需调用', '未知运行'], [
                      (f"{r['origin']} / {r.get('model') or 'oracle'} / {r['guard_enabled']} / {r['context']}",
                       ratio(_goal_count(r), r['n_valid_runs']), ratio(r['n_unauthorized_execution'], r['n_attack_opportunities']),
                       r['n_required_calls_missing'], r['n_unresolved_runs']) for r in os['runtime'] if r['context'] != 'all_contexts']),
                  table(['模型 / 混合 / 语境', 'scope 精确 / 可判定', '错误扩权', '缺必需 scope', '未知/缺失'], [
                      (f"{r['model']} / {r['mixed']} / {r['context']}", ratio(r['n_exact_scope'], r['n_decided']),
                       r['n_overgrant'], r['n_missing_required_scope'], r['n_unknown_missing']) for r in os['contracts'] if r['context'] != 'all_contexts']),
                  table(['OS 合同 / 模型 / guard / 语境', '均值 CPU 秒', '均值峰值 MiB', '均值墙钟秒'], [
                      (f"{r['origin']} / {r.get('model') or 'oracle'} / {r['guard_enabled']} / {r['context']}",
                       measured(r, 'child_cpu_seconds'), measured(r, 'cgroup_memory_peak_bytes', 1048576),
                       measured(r, 'wall_seconds_including_container')) for r in os['runtime'] if r['context'] != 'all_contexts']),
                  '这里直接使用模型生成的 scope，不以正确合同过滤后再报告。真实执行审计包含工具事件、文件结果、系统调用、隔离元数据和原始输出。所有容器资源分布、两次重复的差异与 CI 位于 os_e2e.runtime。', '']
    else:
        lines += ['OS 模型合同 / 执行尚未完整保存（pending）。保留正确合同基线，但不混入未完成模型条件构成最终图。', '']
    lines += ['## E2、E6：Replay 与三角必要性', '',
              '可比较 Replay 必须确实触发目标、保持规定类型/协议、保留核心输入依赖，并满足精确任务 Oracle。Replay 失败只给 unknown；独立可信参考完成任务且不包含目标，才支持该目标可省略。参考执行若发生未授权动作也无效。', '']
    replay_final = read(root, 'results/phase2/os/replay_summary_final.json', {})
    if replay_final:
        lines += [f"最终类型保持轨道保存 {replay_final['typed_run_count']} 次真实执行，其中进程成功 {replay_final['typed_process_success_count']}；{replay_final['valid_replay_pairs']} 个有效 Replay 对覆盖 {', '.join(replay_final['valid_action_classes'])}。保持目标 {replay_final['goal_preserving_pairs']} 对，失去目标 {replay_final['goal_losing_pairs']} 对；可省略证据 {replay_final['unnecessary_evidence_pairs']} 对，必要性 unknown {replay_final['necessity_unknown_pairs']} 对。", '',
                  '[权威 Replay 汇总与排除记录](../results/phase2/os/replay_summary_final.json)。旧 HTTP 无效对与被替代的 SMTP 探索不重复计数。', '']
    for path, title in [('results/phase2/os/replay_results.json', '可选 cache 探针'),
                        ('results/phase2/os/typed_replay/comparisons.json', '类型保持扩展')]:
        rows = read(root, path, [])
        if rows:
            lines += [table([title, '保存状态', '必要性（原记录）', '证据解释'], [
                (r.get('case_id', r.get('fixture')), r.get('status'), r.get('task_necessary'),
                 '失败保留 unknown；以下 Oracle 修订优先' if r.get('status') != 'comparable' else '仅该冻结 fixture') for r in rows]), '']
    lines += ['HTTP-send 的初次多动作 Replay 使用了偏宽的旧输出判定；其原 comparisons.json 中的 comparable 保留供审计，但本报告不将它计为“冗余动作成功”的证据。原始输出 OK 不满足 HTTP-low 要求的 READY。SMTP 类型保持探针返回成功确认却移除真正发送效果，只有任务确实无需发送时才可断言可省略。', '',
              ]
    if os_judge.get('complete') is True:
        lines += [f"两模型对实际 OS 轨迹的补充 Judge 已保存 {os_judge['n_records']}/{os_judge['n_expected_records']} 条响应，复用 {os_judge['n_actual_runs_reused']} 次执行；{os_judge['n_pairs']} 个干预对只属于 {os_judge['n_fixture_families']} 个家族。", '',
                  table(['模型 / 字段', '与 fixture 判定一致 / 可比较', '分歧', '预测 unknown', '评价目标 unknown'], [
                      (f'{model} / {field}', ratio(r['n_agree'], r['n_compared']), r['n_disagree'],
                       r['n_unknown_predictions'], r['n_unknown_evaluation_targets'])
                      for model, data in os_judge['by_model'].items() for field, r in data['field_agreement'].items()]),
                  'Judge 仅看观察输出、执行事件与有限 syscall 摘录，不接收 Oracle 标签/守卫决定。core_preserved 与确定性请求输出相等性比较，goal 字段与权威 Replay 汇总比较；这不是真人准确率或必要性分类准确率，不进行总体 CI/显著性推断。来源：[Judge 汇总](../results/phase2/os_judge/summary.json)。', '']
    elif os_judge:
        lines += ['实际 OS Replay 的两模型 Judge 补充轨道 pending，尚不生成一致性数值表。', '']
    lines += ['## E4：来源与 reader 标签', '']
    if flow:
        lines += [f"已保存 {flow['probes']} 个构造探针：关闭 taint 出现未授权 flow {flow['unauthorized_flow_without_taint']} 次；开启后 {flow['unauthorized_flow_with_taint']} 次，仍允许合法发送 {flow['legitimate_sends_with_taint']} 次。覆盖直接 secret、派生摘要、公开输入和 opaque 变换；范围为五种构造机制，不能解释为真实语料泄漏率。", '',
                  '[flow 原始结果](../results/phase2/flow/e4_flow_probes.jsonl)。', '']
    lines += ['## E5、E7：双账本、受限 SMT 与租约', '']
    if contracts:
        lines += [f"合同探针通过 {contracts.get('passed')}/{contracts.get('probes')}；solver 结果为 {contracts.get('solver_counts')}。SAT 给出具体扩权见证并由运行时重放；UNSAT 只证明已文档化的受限语法；UNSUPPORTED/UNKNOWN 均关闭权限，不能当作子集证明。", '']
    lines += ['支持闭合的平面参数对象、有限 string/integer/boolean 常量与枚举、整数界、精确资源、受限路径前缀/HTTPS 主机、step/stage/每资源 quota。真实 jsonschema 验证与 SMT 均执行。forbid 优先；不可信证据不能创建授权；扩权须可信入口签发的任务绑定、精确 digest、一次性批准。Python 宿主 API 本身不是用户身份认证。', '']
    if approvals:
        lines += [table(['批准策略', '请求 / 批准', '错误 grant', '合法调用允许', '非法调用拒绝'], [
            (name, f"{r['approval_requests']} / {r['approvals_granted']}", r['wrong_grants'],
             ratio(r['authorized_calls_allowed'], r['authorized_cases']), f"{r['denied_unauthorized_cases']}/{r['cases']-r['authorized_cases']}")
            for name, r in approvals.items()]),
            '这四个构造用例使用冻结研究者标签，批准行为是模拟器实验，不是真人审核数据；本地零模型调用、零 Token、零 API 成本。deny-all 的安全性必须与阻止合法任务的代价一起读。', '']
    if lifecycle:
        lines += [table(['目标 / 条件', '任务完成', '期限/额度后执行'], [
            (f"{r['target']} / {r['configuration']}", f"{r['task_completions']}/{r['n']}", f"{r['late_executions']}/{r['n']}") for r in lifecycle]),
            f"共 {sum(r['n'] for r in lifecycle)} 次保存的运行。expiry_only 不靠 quota 用尽触发，quota_only 不靠时间过期触发；主 VM 使用 step/quota，stage 独立在合同探针中验证。收缩能在已知更新时间阻断晚到动作，租约能在无额外收缩时独立阻断；这些构造用例不能推断开放任务的最优期限。", '']
    lines += ['[合同语法、API 与信任边界](phase2_contracts.md)；[探针原始记录](../results/phase2/contracts/probes.jsonl)。', '',
              '## E8：合同格式元变形', '']
    if completion.get('pipeline') is True:
        lines += [table(['held-out 模型 / 版本 / 格式', 'scope 一致 / 可判定等价对', '未知/缺失/未确认'], [
            (f"{r['model']} / {r['variant']} / {r['form']}", ratio(r['n_exact_scope_match'], r['n_decided_confirmed_pairs']),
             r['n_unknown_missing_or_unconfirmed']) for r in analysis.get('metamorphic', []) if r['split'] == 'held_out_test']),
            '等价条件由有限任务规格往返校验与相同动作序列确认，仅改变 fields/缩进 JSON 等格式。缺失或 unknown 对不计作一致；不能扩展为一般自然语言语义等价。', '']
    else:
        lines += ['格式元变形模型调用尚未全部写入最终分析（pending）。', '']
    lines += ['## 统计、成本与可复现性', '',
              f"置信区间对完整家族重采样 {analysis.get('bootstrap_samples', 'pending')} 次；保留同一家族的攻击变体、任务语境和重复调用。配对精确 McNemar 的分析单位为家族，所有预期嵌套观察均成功才算家族成功；未知导致整对不完整，不伪装为否定标签。Holm 同时覆盖本轮 VM、OS 与历史已报告比较。", '',
              '这是事后探索性分析，不是预注册验证。合成任务 held-out 只有两个家族、validation 一个家族；统计区间和 p 值无法弥补该独立样本量。两个模型的多次调用不增加家族数。', '']
    if complete:
        comparisons = [r for r in analysis.get('paired_comparisons', []) if r.get('split') == 'held_out_test' and r.get('track') == 'P_Q_pipeline_ablation']
        lines += [table(['模型 / 比较 / 终点', '完整家族', '原始 p', '全报告 Holm p'], [
            (f"{r.get('model')} / {r['left']} vs {r['right']} / {r['endpoint']}", r['n_families_complete'],
             fmt(r.get('family_mcnemar', {}).get('p_exact'), 4), fmt(r.get('family_mcnemar', {}).get('p_holm_all_reported'), 4)) for r in comparisons]),
            f"全报告多重比较族大小：{analysis.get('multiplicity', {}).get('all_reported_test_family_size', 'NA')}。完整家族 CI、重复间差异、所有开发/验证结果见 [分析 JSON](../results/phase2/pipeline_analysis/summary.json)。", '']
        lines += [table(['held-out VM 模型 / 条件', '有效运行', '平均运行时秒'], [
            (f"{r['model']} / {r['variant']}", r['n_valid_runs'], fmt(r.get('mean_vm_seconds'), 6))
            for r in runtime if r.get('track') == 'P_Q_pipeline_ablation' and r['split'] == 'held_out_test' and r['variant'] in ('full', 'no_guard')]),
            'VM 计时不含 API 延迟与 OS 执行；不同条件也可能运行不同动作，因此这些是观察耗时，不能直接视为等工作量下的纯守卫开销。', '']
    budget = _budget(root)
    if budget:
        lines += [f"完整 API 账本：{budget['n_settled']}/{budget['n_reservations']} 个 reservation 已结算，估计支出 ${budget['settled_estimated_usd']:.6f}；未结算保留上限 ${budget['unsettled_reserved_upper_usd']:.6f}，总暴露上限 ${budget['total_exposure_upper_usd']:.6f}。已结算 input/output Token 为 {budget['input_tokens_settled']}/{budget['output_tokens_settled']}。", '',
                  table(['模型', '已结算 / 未结算', 'input / output Token', '估计 USD'], [
                      (r['model'], f"{r['n_settled']} / {r['n_unsettled']}", f"{r['input_tokens_settled']} / {r['output_tokens_settled']}", f"{r['settled_estimated_usd']:.6f}") for r in budget['by_model']]),
                  '账本按 reservation 的最后状态去重，包含 pilot、第一轮与审阅前费用。数值为标准价格保守估计，不是供应商发票；不因缺少原始响应或失败重试而删除费用。报告 manifest 保存本次所读完整账本 hash。', '']
    else:
        lines += ['API 账本 pending；本地探针不能用于推断总项目成本。', '']
    lines += ['## 有证据的失败与限制', '']
    errors = []
    if source:
        errors += [('真实源码兼容性', f"{source.get('status_by_distinct_source_latest', {}).get('runtime_error', 'NA')} 个不同入口为 runtime_error", 'source_summary_final.json 与每个 stderr/系统调用轨迹；保留失败分母'),
                   ('开发图表功能失败', '首次脚本正常退出，但精确任务 Oracle 为 false；后续开发重试另记', 'source_runs.json / supplemental_source_runs.json；正常退出不等于完成任务')]
    if (root / 'docs/phase2_oracle_amendments.md').exists():
        errors += [('HTTP-low Oracle 偏宽', '旧容器接受 POST 后 OK，可信请求要求 READY', 'phase2_oracle_amendments.md；外层 v2 计分保留旧输出'),
                   ('SMTP-high Oracle 缺项', '旧检查只确认发送，遗漏必需草稿', '同一修订记录；新增必需效果检查')]
    if graph:
        errors += [('Python 图解析/覆盖', f"{graph['v2']['unresolved_reasons'].get('python_parse_error', 0)} 个解析失败记录；{graph['v2']['unknown_resource_actions']}/{graph['v2']['candidate_actions']} 候选资源未知", 'graphs_v2/coverage.jsonl；解析失败不当作无风险')]
    if (root / 'docs/study_v1_report.md').exists():
        errors += [('第一轮权威伪装错误', 'csv-0-authority_spoofing / mini / v1 / r0 对 a_secret 错误授权', '历史 study_v1_report.md；raw a63af34bea4c8663e83504185de05c0a4b7238a8dbd152b053d38675d9dafce3 保留，不据此回调 held-out')]
    if flow:
        errors += [('允许读取后的信息流', f"未加标签时实际构造出 {flow['unauthorized_flow_without_taint']} 次不被普通工具权限阻止的 flow", 'flow/e4_flow_probes.jsonl；工具允许不代表所有 reader 合法')]
    if uncertainty:
        errors += [('parse-valid 不等于确定合同', f"{uncertainty['declared_unknown_contract_slots']}/{uncertainty['generated_contract_slots']} 个旧 E3 合同条件在原响应声明不确定", 'e3_contract_uncertainty_recovery 保存请求 hash 与原文件 hash；仅修订分析副本')]
    lines += [table(['现象', '实际观察', '证据 / 处理'], errors), '',
              '## 真人工作包与研究结论边界', '',
              '真人标注状态：pending。已准备随机化、盲化的双人标注包；完整包每人 8,188 个审阅单元、19,474 个字段，优先包每人 457 个单元、1,033 个字段。两人独立完成后才能计算一致性、裁决分歧并报告真实语料 Precision/Recall/F1。模型产出、研究者构造标签、Oracle 和未填写模板均不是真人标注。详见 [标注协议](phase2_annotation.md)。', '',
              '本轮可验证的是：有限 DSL 的 fail-closed 约束、可信授权与不可信证据的隔离、可比较 Replay 的证据规则，以及保存轨迹中适配器层的安全性与效用。尚不能主张普适技能理解、真实语料检测准确率、任意源码强制隔离、完整信息流分析或大样本跨家族泛化。', '',
              '## 结果文件与重现', '',
              '原始模型记录、请求 hash、冻结输入、完整错误与执行日志均由各实验驱动保存；汇总不会修改原始记录。报告与图表是纯离线读取，可在已有数据上重建：', '',
              '```powershell', '.venv/Scripts/python.exe scripts/analyze_pipeline_phase2.py',
              '.venv/Scripts/python.exe scripts/plot_phase2.py', '.venv/Scripts/python.exe scripts/write_phase2_report.py', '```', '',
              '最终报告生成器拒绝缺失轨道；仅检查中间进度时显式使用 --allow-partial。图表不把缺失或 unknown 填成零。', '']
    for name, title in [('graph_coverage', '图资源与 DATA 候选覆盖'), ('lifecycle', '期限与额度的独立探针'),
                        ('pipeline_ablations', 'held-out 九项 P/Q 消融'), ('os_security_utility', '实际 OS 安全性与效用')]:
        if (root / f'results/phase2/figures/{name}.png').exists():
            lines += [f'![{title}](../results/phase2/figures/{name}.png)', '']
    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, default=Path('docs/phase2_report.md'))
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    body = build_report(args.root, allow_partial=args.allow_partial)
    out = args.out if args.out.is_absolute() else args.root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding='utf-8')
    manifest = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'partial_allowed': args.allow_partial,
                'inputs': {path: hashlib.sha256((args.root / path).read_bytes()).hexdigest() for path in INPUTS if (args.root / path).exists()},
                'report_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'model_calls': 0}
    target = args.root / 'results/phase2/report_manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()

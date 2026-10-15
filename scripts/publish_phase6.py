"""Create an evidence-linked report and standard scientific figures."""
import json
from pathlib import Path
import sys
from phase6_common import ROOT,jb,immutable


def main():
    s=json.loads((ROOT/'results/phase6/analysis/summary.json').read_text())
    c=json.loads((ROOT/'results/phase6/challenge/analysis/summary.json').read_text())
    budget=json.loads((ROOT/'results/phase6/challenge/api/summary.json').read_text())
    inherited=json.loads((ROOT/'results/phase6/provenance/budget_inheritance.json').read_text())['inherited_upper_usd']
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(11,4),sharey=True)
    models=['gpt-4.1-mini','gpt-6-luna'];axes=['authorization','implementation','task']
    labels=['Authorization','Current-route\nnecessity','Catalog-relative\nnecessity']
    for ax,model in zip(axs,models):
        for v,shift,color in [('table',-.18,'#306caa'),('graph',.18,'#da8052')]:
            rs=[next(r for r in s['metrics'] if r['split']=='all' and r['model']==model and r['view']==v and r['axis']==a) for a in axes]
            bars=ax.bar([i+shift for i in range(3)],[100*r['correct']/r['total'] for r in rs],width=.34,label=v,color=color)
            ax.bar_label(bars,labels=[f"{r['correct']}/{r['total']}" for r in rs],fontsize=8,padding=3)
        ax.set_xticks(range(3),labels);ax.set_title(model);ax.set_ylim(0,110);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axs[0].set_ylabel('Correct labels (%)');axs[1].legend(loc='upper right')
    fig.suptitle('Phase 6 main study: 36 authored workflows / 18 families')
    fig.tight_layout();out=ROOT/'results/phase6/figures';out.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf'):fig.savefig(out/f'accuracy.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4))
    faults=['none','transient_before','known_after']
    for mode,shift,color in [('first_feasible',-.18,'#306caa'),('search_equal',.18,'#da8052')]:
        rs=[next(r for r in c['recovery'] if r['mode']==mode and r['fault']==f and r['quota']==16 and r['grant_condition']=='supplied') for f in faults]
        bars=ax.bar([i+shift for i in range(3)],[r['charged_calls'] for r in rs],width=.34,label=mode,color=color)
        ax.bar_label(bars,labels=[f"{r['charged_calls']} calls\n{r['authorized_goal']}/{r['n']} success" for r in rs],fontsize=9,padding=3)
    ax.set_xticks(range(3),['No fault','Transient before effect','Known committed effect'])
    ax.set_ylim(0,100);ax.set_ylabel('Total charged calls (12 cases)');ax.legend();ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    ax.set_title('Targeted supplement: equal planning capabilities, quota 16')
    fig.tight_layout()
    for ext in ('png','pdf'):fig.savefig(out/f'recovery_tradeoff.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
    table=['| 模型 | 轴 | 表格 | 图边 |','|---|---|---:|---:|']
    cn={'authorization':'授权','implementation':'当前实现必要性','task':'有限目录任务必要性'}
    for model in models:
        for axis in axes:
            vals=[next(r for r in s['metrics'] if r['split']=='all' and r['model']==model and r['view']==v and r['axis']==axis) for v in ('table','graph')]
            table.append(f"| {model} | {cn[axis]} | {vals[0]['correct']}/128 | {vals[1]['correct']}/128 |")
    supp_table=['| 故障（quota=16，12案例） | 首个可行：成功/调用 | 最低成本：成功/调用 |','|---|---:|---:|']
    for f in faults:
        vals=[next(r for r in c['recovery'] if r['mode']==m and r['fault']==f and r['quota']==16 and r['grant_condition']=='supplied') for m in ('first_feasible','search_equal')]
        supp_table.append(f"| {f} | {vals[0]['authorized_goal']}/12；{vals[0]['charged_calls']} | {vals[1]['authorized_goal']}/12；{vals[1]['charged_calls']} |")
    report=f'''# 第六轮：可执行合成工作流中的必要性、未知与合法恢复

本轮完成了限定工作流语言中的四项补强。主要进展是证据链可独立复算、公平对照更强；没有得到“图边普遍改善判断”或“复杂搜索普遍优于强基线”的结论。所有历史结果保留，新增研究不使用真实 Skill 或人工标注。

## 研究问题与实验规模

研究对象是 JSON 形式的有限工具工作流，包含读写、发出模拟消息、删除、变量、分支、有限循环和无环函数调用。工具只改变内存状态，不访问宿主文件或真实网络。授权来自独立授予的操作/资源对；必要性来自站点干预及明确给定的有限路线目录。它不是任意 Python、真实 Skill 或开放世界代理的完整安全模型。

主实验先冻结实现，再评估独立作者构造的24个留出案例（12个组合结构家族），加12个开发案例（6家族）。首次发现留出负例不足和恢复对照全部打平后，另行预登记12个有针对性的成对挑战案例（6家族），冻结新选路模块后评估。补充集单独报告，不用于替换首次结果，不是未见过所有研究决策的确认性测试。

| 轨道 | 主实验 | 定向补充 |
|---|---:|---:|
| 工作流/家族 | 36/18 | 12/6 |
| 独立语义比较（路线×世界×干预） | 374/374一致 | 134/134一致 |
| 静态效果提取 | 128/128，无额外站点 | 32/32，无额外站点 |
| 模型条件 | 288主条件+48重复 | 96 |
| 不同API请求 | 332 | 96 |
| 恢复执行条件 | 2304 | 1152 |
| 集成执行条件（含参考门控） | 1440 | 480 |

共5376个不同执行条件，逐项完成本地有限VM与隔离容器一致性核验。成功容器批次4个；另有1次入口配置失败，其原始日志完整保留。**条件数不是独立家族数，批量条件也不是5376个独立容器。** 所有432个模型条件取得完整且协议有效的结果。主实验两例图为空，使graph/shuffled共享4个请求，故实际不同请求共428个。

## 可执行真值与结构泛化

真值解释器只读参考AST，生产执行器只解析合成Markdown中的工作流；二者由不同实现者编写。真值不读取模型答案或生产提取结果。比较包括最终状态、完整效果轨迹、授权标记、目标与错误状态，以及全部备选路线的站点干预。九个故意破坏大小写、拼接、分支、循环、删除、授权、干预、目录闭包及必要性方向的语义变异均被手工推导的见证测试拒绝。

508次一致性比较说明两个实现对这些有限样本一致；它不能排除共同规格错误，也不是形式化证明。留出集删除标识和字面值后的结构指纹与开发集无粗粒度重合，但仍只覆盖已有算子的组合，不能称为新语言或任意程序泛化。

首次留出集授权真值只有yes70/unknown18，实现必要性只有yes68/unknown20，**没有no负例**。因此首次留出结果不能单独测量显式拒绝或非必要动作的识别。补充集提供授权yes26/no6、实现必要性yes20/no12、任务必要性yes20/no12；它不含unknown，不能用来宣称未知处理改善。

## 判断结果：接口修复没有解决语义推理

下表使用主实验128个站点的完整分母。协议失效为零；正确率低不能再归因于格式丢失。

{chr(10).join(table)}

![主实验判断准确率](../results/phase6/figures/accuracy.png)

mini在表格条件下未对任何实现必要性给出yes：当前路线中关键读取/写入也常判为no。具体见dev-transform-0：去掉任何链上效果都会改变输出，但四个站点均被判为非必要。它与把“存在别的实现”误当“当前实现干预不必要”相容；由于短协议没有保存解释链，不能断言模型内部究竟用了什么理由。

Luna在表格条件下的实现必要性为102/128，但任务必要性只有47/128。问题不是保守性本身：任务轴真值只有40个unknown，它却输出109个unknown，其中71个属于真值已经可判定时的过度弃答。相反，mini对40个任务unknown仅正确保留13个，作出27个无充分依据的yes/no。

## unknown需要分开解释

主实验授权/实现/任务轴分别有27/33/40个unknown。这里混合了三种情况：多种可能世界给出不同结论；目录未闭合或不存在成功合法路线；站点未触发或原流程未成功、导致估计量不适用。最后一类是预先定义的资格条件，并非模型“不知道事实”。报告保留原三值标签，同时按inactive、baseline_failure、mixed_worlds、open_catalog、no_legal_route列原因；原因可重叠，不能直接相加当作站点总数。

下一步应采用“可判定yes/no、证据不足、估计量不适用、接口失败”的分层统计，而不是只追求unknown下降。本轮没有在看到结果后重新标注unknown或补发同一请求刷掉错误。

## 图边贡献仍不稳定

图、打乱图和长度匹配的填充条件保留相同源码、候选、世界和路线。图与填充的本地token数精确相同；这不保证相同注意力或输出长度。静态边表达语法数据/控制/调用关系，未宣称是完整因果图。

按18个家族等权配对，mini任务轴graph-table为+5.83个百分点，探索性95%区间[+2.31,+9.68]；Luna实现轴为−11.94个百分点，区间[−25.97,−0.14]。其余方向也不统一。多项对照未经确认性多重检验，这些区间不应包装成稳定的总体提升。24个三次重复组中仅10组预测向量完全一致。

关键含义是：结构表达可以改变结果，但“改变”不等于“增益”，也不等于模型正确使用了边。应优先保证有限执行和证据校验，再决定是否需要图表示；目前不宜把图的普遍优势写成论文中心结论。

## 同等能力强对照与合法恢复

主实验576对search/checkpoint在成功、调用、重复副作用和尝试次数上逐项打平；search额外耗费774个模拟步骤。原始故障通常在重试原路线后即可处理，另一些权限条件使整个目录不可行，所以这个零增益也暴露了实验对选路需求的覆盖不足。

补充集中，first_feasible与search_equal获得相同路线、状态、回执、授予权限、目标、剩余额度，并在每次选路时模拟全部剩余路线。两者均先过滤目标与额度可行性，唯一选择差异是目录顺序或最低调用数。第一次共同选路状态的计算能力相同；选择改变后续状态后，整轮计算量可以不同，已经单独记录。

{chr(10).join(supp_table)}

![恢复中的收益与代价](../results/phase6/figures/recovery_tradeoff.png)

无故障时最低成本策略少8次调用；提交前瞬时故障下反而多8次；已提交且有回执的故障下多完成1例，但多10次调用。低成本贪心根据当前可见状态选路，不知道未来故障；某条路线先失败后，剩余尝试与目录状态改变，会反转成本优势。这里不把失败路线节省的调用算成质量改善，分析同时提供全条件和共同成功条件的代价。

所有策略都受同一可信权限网关约束，因此零越权效果首先证明网关在这些有限测试中执行了规则，**不是模型或搜索额外提供的安全收益**。不确定是否已提交的效果会安全停止；它不能被计入成功，也不能靠回滚、重置额度或盲目重发隐藏问题。

## 端到端证据与剩余可用性损失

流水线确实从源码解析候选，经真实API判断、原路线授权门控，到共享状态的执行与恢复。模型没有执行工具，不产生新的程序；实现/任务必要性作为独立评价轴，不控制许可。故这里是“源码到门控执行的端到端研究”，不是自由规划的通用LLM代理评测。

主实验checkpoint、全部候选交给可信网关时，无故障和瞬时故障均完成34/36。表格模型门控在瞬时故障下mini完成31/36、Luna32/36；模型阻断原路线后，恢复额外消耗尝试，部分后续故障无法再重试。另有目录不可行与回执签名冲突，是不同类型的可用性损失。

原计划称作oracle的门控按“所有可能世界聚合后为yes”放行，但实际执行只用world0。它在瞬时故障下仅28/36，因此是**保守真值参考门控，不是理论完成率上界**。模型误把聚合unknown判为yes，有时仍被world0的可信网关允许而提高完成率；这不说明错误的语义判断优于真值。

补充集480个集成条件均完成。模型门控子集无故障时，最低成本策略调用338次，首个可行426次；瞬时故障下反转为587对541次。这再次说明调用节省取决于故障与恢复过程，不能只报告正常条件。

## 与第五轮相比，改善与不可比较之处

| 旧证据的限制 | 本轮补强 | 仍不能主张 |
|---|---|---|
| 部分真值靠作者判断、语义歧义 | 独立解释器、可执行干预、完整轨迹差分与变异见证 | 任意程序正确性或无共同规格错误 |
| 少数家族、提取与后续判断分离 | 冻结后组合结构留出，真实解析结果进入模型与执行 | 真实Skill分布或新算子泛化 |
| 固定参考恢复与弱对照 | 同权限/目录/状态的检查点，再加同模拟能力的可行性基线 | 搜索普遍更安全、更省钱或更成功 |
| 格式失效混入语义失败 | 432/432协议有效，原始答案与阶段结果可追溯 | 语义准确率因此改善 |
| 图收益不稳定 | 表格/图/打乱/长度控制与家族配对 | 图的稳健因果收益 |

第五轮的程序、标签、任务与分母不同；不能把旧提取6/10与本轮88/88直接作因果改善比例，也不能把第五轮恢复40/48与本轮完成率直接比较。旧结果未重算或覆盖。

## 研究价值与论文边界

当前有价值的成果是可复现的有限语义评测框架、unknown资格条件与证据不足的区分、以及公平恢复对照揭示的代价反转。适合写成机制研究/评测方法与反例分析。这里的有限状态与封闭目录已经允许确定性枚举；不能声称LLM是解决这些有限判断的必要技术，也不能以与自身定义一致的真值冒充新检测算法优越性。

本轮也没有运行自适应提示注入攻击者或真实恶意工具基准。合成源码被视为数据、效果被可信网关约束，是实验边界；不能把这些结果写成已经证明抵抗通用提示注入攻击。

明显局限包括：人工设计的24个家族，补充集目的性选择，公开目标/备选路线和部分直接构造目标的路线，单次主要采集与有限重复，两种模型，固定故障位置和额度，只有授权轴进入执行，以及有限VM而非外部真实工具。模型提示遗漏了100步上限和显式key冲突的文字说明，但主/补充全部基线、路线与干预均未触发这两条规则；不能据此评价模型掌握了它们。

建议下一步优先做独立冻结生成器与更丰富的状态/故障组合；把“未触发”从unknown中拆出；让模型输出可被执行器验证的中间证据而不直接相信标签；比较确定性枚举及受预算约束的规划；最后才扩大图结构或模型规模。任何新真实Skill或人工轨道均不在当前范围内。

## 预算、完整性与复现

本轮新增保守计费上界 **${budget['cumulative_upper_usd']-inherited:.9f}**；累计 **${budget['cumulative_upper_usd']:.9f}**；既有授权余量 **${budget['remaining_usd']:.9f}**。账本继承Phase5→主实验→补充实验的完整字节前缀，不是供应商发票，不把预留减少误称为退款。无自动重试。

基线24393个已跟踪文件逐字节保留。完整测试835 passed、4 skipped、150 subtests passed；另有发布验证复算真值、模型解析、执行记录、预算和散列。最终发布验证见[机器可读验证](../results/phase6/provenance/release_verification_v2.json)。独立审查见[review](phase6_review.md)，复现入口见[reproduction](phase6_reproduction.md)。

主结果：[逐候选结果](../results/phase6/analysis/candidate_scores.jsonl)、[统计与区间](../results/phase6/analysis/summary.json)、[首次独立语义比较](../results/phase6/first/differential.jsonl)。补充结果：[独立目录](../results/phase6/challenge/analysis/summary.json)。所有原始请求、回答、失败与预算在相邻api/、recovery/、integrated/目录中。
'''
    immutable(ROOT/'docs/phase6_report.md',report.encode('utf-8'))
    summary={'phase':6,'scope':'synthetic_only','main_cases':36,'main_families':18,'targeted_cases':12,'targeted_families':6,
             'semantic_comparisons':508,'model_conditions':432,'unique_requests':428,'execution_conditions':5376,
             'successful_containers':4,'preserved_failed_container_launches':1,'baseline_files_preserved':24393,
             'phase6_upper_usd':budget['cumulative_upper_usd']-inherited,
             'cumulative_upper_usd':budget['cumulative_upper_usd'],'remaining_usd':budget['remaining_usd'],
             'all_model_conditions_valid':432,'supplemental_collection':budget}
    immutable(ROOT/'results/phase6/publication/overview.json',jb(summary))
    print(json.dumps(summary))


if __name__=='__main__':main()

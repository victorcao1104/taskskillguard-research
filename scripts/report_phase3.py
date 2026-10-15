"""Build descriptive tables/figures from saved evidence, with no model calls."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/phase3/analysis'


def export(name, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / (name + '.csv')).open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])


def fraction(n, d):
    return f'{n}/{d} ({n/d:.1%})' if d else f'{n}/{d} (NA)'


def historical_os_rows(rows):
    # The prior summary contains both subgroup rows AND their all-context total.
    # Select one level; summing all three levels would double every observation.
    return [{'round':'v2', **{k:r[k] for k in ('origin','model','guard_enabled')},
             **{dst:r[src] for dst,src in [('conditions','n_expected_runs'),
                 ('decided','n_valid_runs'),('confirmed_completion','n_goal_success'),
                 ('unauthorized_conditions','n_unauthorized_execution')]}}
            for r in rows if r['context']=='all_contexts']


def main():
    summary = json.loads((OUT / 'summary.json').read_text(encoding='utf-8'))
    if not summary['complete']:
        raise ValueError('FINAL_SUMMARY_REQUIRED')
    sections = ['# 第三轮数据表\n\n从已保存的主实验分析生成；完整指条件记录齐全，不表示每个模型请求均成功。条件数不等于独立家族数或 API 调用数。阶段重放与余额恢复后的补跑另见 phase3_followup_results.md。']
    factorial = [{k: r[k] for k in ('model','protocol_mode','catalog','conditions',
                  'protocol_valid','scope_complete_no_excess','declared_unknown',
                  'unique_request_hashes')} for r in summary['factorial']['groups']]
    export('protocol_factorial', factorial)
    sections += ['## 协议 2×2', table(['模型','格式','目录','协议有效','范围完整且无越界','声明未知'],
        [[r['model'],r['protocol_mode'],r['catalog'],fraction(r['protocol_valid'],r['conditions']),
          fraction(r['scope_complete_no_excess'],r['conditions']),r['declared_unknown']] for r in factorial])]

    stages = [('v2_saved',summary['historical_same_inputs']['before']),
              ('v3_same_PQ',summary['historical_same_inputs']['after']),
              ('v3_fresh_PQ_regression',summary['runtime']['regression']['full']),
              ('v3_new_families',summary['runtime']['new']['full'])]
    comparison=[]
    for stage, metrics in stages:
        for r in metrics['subgroups']:
            if set(('model','split')) <= r.keys():
                comparison.append({'stage':stage,**{k:r[k] for k in (
                    'model','split','planned_conditions','decided_conditions',
                    'confirmed_completion','completion_rate_all_planned','completion_rate_decided',
                    'confirmed_clean_completion','independent_families','attack_conditions_planned',
                    'attack_conditions_decided','unauthorized_attack_conditions','leak_attack_conditions')}})
    export('before_after',comparison)
    sections += ['## 历史留出组（现在仅作已见回归）与新家族留出组',
        table(['轨道','模型','家族','可判定/计划','完成/全部计划','完成/可判定','越权/已判定攻击条件'],
        [[r['stage'],r['model'],r['independent_families'],
          fraction(r['decided_conditions'],r['planned_conditions']),
          fraction(r['confirmed_completion'],r['planned_conditions']),
          fraction(r['confirmed_completion'],r['decided_conditions']),
          fraction(r['unauthorized_attack_conditions'],r['attack_conditions_decided'])]
         for r in comparison if r['split']=='held_out_test'])]

    variants=[]
    for variant, metrics in summary['runtime']['new'].items():
        for r in metrics['subgroups']:
            if r.get('split')=='held_out_test':
                variants.append({'variant':variant,**{k:r[k] for k in (
                    'model','planned_conditions','decided_conditions','confirmed_completion',
                    'undecided_conditions','recovery_conditions','required_effect_missing_conditions')}})
    export('new_heldout_variants',variants)
    sections += ['## 新家族留出组执行变体',table(['模型','变体','可判定','完成/计划','参考恢复','必需效果未完成'],
        [[r['model'],r['variant'],r['decided_conditions'],fraction(r['confirmed_completion'],r['planned_conditions']),
          r['recovery_conditions'],r['required_effect_missing_conditions']] for r in variants])]

    mechanisms=[]
    for r in summary['mechanisms']:
        mechanisms.append({k:r[k] for k in ('variant','planned_conditions','decided_conditions',
            'confirmed_completion','attack_conditions_planned','attack_conditions_decided',
            'unauthorized_attack_conditions','leak_attack_conditions')} |
            {f'attack_{k}':r['attack_reach'][k] for k in ('planned','reached','guard_reached','executed')})
    export('mechanism_controls',mechanisms)
    sections += ['## 固定合同、固定攻击计划（全部新家族）',table(
        ['变体','完成/计划','越权/攻击条件','泄漏/攻击条件','计划攻击动作','到达/实际执行攻击动作'],
        [[r['variant'],fraction(r['confirmed_completion'],r['planned_conditions']),
          fraction(r['unauthorized_attack_conditions'],r['attack_conditions_decided']),
          fraction(r['leak_attack_conditions'],r['attack_conditions_decided']),r['attack_planned'],
          f"{r['attack_reached']}/{r['attack_executed']}"] for r in mechanisms]),
        '注意：该轨道的初始合同均正确，因此 no_authority 没有非法初始合同机会；body 与 taint 的独立作用还需查看 component_probes.jsonl。']

    old = json.loads((ROOT/'results/phase2/pipeline_analysis/summary.json').read_text(encoding='utf-8'))
    os_rows=historical_os_rows(old['os_e2e']['runtime'])
    os_rows += [{'round':'v3',**{k:r[k] for k in ('origin','model','guard_enabled','conditions',
                   'decided','confirmed_completion','unauthorized_conditions')}} for r in summary['os']['groups']]
    export('os_before_after',os_rows)
    sections += ['## 实际 OS 有限适配器（越权分母为全部已判定运行，不是攻击成功率）',
        table(['轮次','合同来源','模型','guard','可判定/计划','完成/计划','越权条件'],
        [[r['round'],r['origin'],r['model'],r['guard_enabled'],fraction(r['decided'],r['conditions']),
          fraction(r['confirmed_completion'],r['conditions']),r['unauthorized_conditions']] for r in os_rows])]

    real=[]
    for r in summary['real']['groups']:
        real.append({k:r[k] for k in ('model','context','variant','conditions','model_evaluated_conditions',
            'not_applicable_conditions','protocol_valid_conditions','classified_action_observations')} |
            {f'{attribute}_{label}':r[attribute+'_counts'].get(label,0)
             for attribute in ('authorized','necessary') for label in ('yes','no','unknown')})
    export('real_coverage',real)
    sections += ['## 真实样本条件覆盖（准确率待人工标注）',table(
        ['模型','语境','表示','协议有效/实际评估','授权unknown/动作','必要性unknown/动作'],
        [[r['model'],r['context'],r['variant'],fraction(r['protocol_valid_conditions'],r['model_evaluated_conditions']),
          fraction(r['authorized_unknown'],r['classified_action_observations']),
          fraction(r['necessary_unknown'],r['classified_action_observations'])] for r in real])]
    (ROOT/'docs/phase3_results_tables.md').write_text('\n\n'.join(sections)+'\n',encoding='utf-8')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for axis,model in zip(axes,('gpt-4.1-mini','gpt-6-luna')):
        selected=[r for r in factorial if r['model']==model]
        labels=[r['protocol_mode']+'\n'+r['catalog'] for r in selected]
        values=[r['protocol_valid']/r['conditions']*100 for r in selected]
        axis.bar(labels,values,color='#276e87')
        axis.set(ylim=(0,112),title=model,ylabel='Protocol-valid conditions (%)')
        for i,r in enumerate(selected): axis.text(i,values[i]+2,f"{r['protocol_valid']}/{r['conditions']}",ha='center')
    fig.suptitle('Protocol 2 × 2: original planner semantics held fixed')
    for ext in ('png','pdf'): fig.savefig(OUT/f'protocol_factorial.{ext}',dpi=180)
    plt.close(fig)
    print(json.dumps({'tables':'docs/phase3_results_tables.md','csv_tables':6,'figure':'protocol_factorial.png'}))


if __name__=='__main__':
    main()

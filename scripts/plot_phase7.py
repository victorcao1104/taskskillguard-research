"""Publication-sized descriptive figures; raw data and tests remain authoritative."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from phase7_common import ROOT,read_rows

def main():
    summary=json.loads((ROOT/'results/phase7/analysis/summary.json').read_text())
    out=ROOT/'results/phase7/figures';out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(11,4),sharey=True,layout='constrained')
    names=('authorization','current_route_required','catalog_required')
    for ax,model in zip(axes,('gpt-4.1-mini','gpt-6-luna')):
        for i,(view,color) in enumerate(zip(('B0','B1','B2'),('#7b8794','#2374ab','#d98324'))):
            rows={r['axis']:r for r in summary['metrics'] if r['split']=='heldout' and r['model']==model and r['view']==view and r['label_space']=='collapsed'}
            vals=[100*rows[a]['accuracy'] for a in names]
            bars=ax.bar(np.arange(3)+(i-1)*.25,vals,.24,label=view,color=color)
            ax.bar_label(bars,fmt='%.0f',fontsize=8,padding=2)
        ax.set_xticks(range(3),['Authorization','Current route','Catalog']);ax.set_title(model);ax.set_ylim(0,110)
        ax.legend(frameon=False,ncol=3,loc='upper right')
    axes[0].set_ylabel('Correct candidate judgments (%)')
    fig.suptitle('New families: same collapsed label space (not_applicable → unknown)',fontsize=12)
    for ext in ('png','pdf'):fig.savefig(out/f'model_comparison.{ext}',dpi=200)
    plt.close(fig)
    rows=read_rows(ROOT/'results/phase7/recovery/vm_results.jsonl')
    faults=('none','transient_before','known_after','double_transient_before')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for i,(policy,color) in enumerate((('legacy','#7b8794'),('safe_retry','#2374ab'))):
        groups=[[r for r in rows if r['split']=='heldout' and r['quota']==16 and r['selector']=='search_equal' and r['fault']==f and r['policy']==policy] for f in faults]
        values=([100*sum(r['result']['authorized_goal'] for r in g)/len(g) for g in groups],
                [sum(r['result']['charged_calls'] for r in g) for g in groups])
        for ax,ys in zip(axes,values):
            bars=ax.bar(np.arange(4)+(i-.5)*.35,ys,.34,label=policy,color=color)
            ax.bar_label(bars,fmt='%.1f' if ax is axes[0] else '%.0f',fontsize=8,padding=2)
            ax.set_xticks(range(4),['None','Before','Known after','Two before']);ax.legend(frameon=False)
    axes[0].set_ylim(0,115);axes[0].set_ylabel('Authorized completion (%)')
    axes[1].set_ylim(0,max(v for v in values[1])*1.2);axes[1].set_ylabel('Total charged effect calls')
    fig.suptitle('New families: 38 worlds, quota 16, lowest-call feasible-route selector',fontsize=12)
    for ext in ('png','pdf'):fig.savefig(out/f'recovery_comparison.{ext}',dpi=200)
    plt.close(fig)

if __name__=='__main__':main()

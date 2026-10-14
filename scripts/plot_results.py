"""Static research figures, with explicit denominators and study boundaries."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]


def main():
    rows=[json.loads(s) for s in (ROOT/'results/mechanistic/traces.jsonl').read_text(encoding='utf-8').splitlines()]
    names=['Unguarded','V3: scope','V4: + flow','V5: full']
    colors=['#8c98a5','#3878a8','#2b9a92','#236542']
    modes=['none','v3','v4','v5']
    groups=[[r for r in rows if r['mode']==m and 'ablation' not in r] for m in modes]
    fig,axes=plt.subplots(1,3,figsize=(13,4.7))
    for ax,field,title,subset in zip(axes,['unauthorized_executed','secret_leaked','goal_satisfied'],
            ['Unauthorized execution (lower is better)','Confidential-flow leaks (lower is better)','Task completion (higher is better)'],[None,{'data_flow_misuse','derived_summary'},None]):
        counts=[];denoms=[]
        for group in groups:
            chosen=[r for r in group if subset is None or r['scenario'] in subset]
            counts.append(sum(r[field] for r in chosen));denoms.append(len(chosen))
        values=[100*n/d for n,d in zip(counts,denoms)]
        bars=ax.bar(names,values,color=colors,width=.64)
        for bar,n,d,v in zip(bars,counts,denoms,values):
            ax.text(bar.get_x()+bar.get_width()/2,v+2.2,f'{n}/{d}',ha='center',fontsize=10)
        ax.set_ylim(0,115);ax.set_yticks([0,25,50,75,100],labels=['0%','25%','50%','75%','100%'])
        ax.set_title(title,fontsize=10,pad=14);ax.tick_params(axis='x',rotation=20)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('TaskSkillGuard: controlled capability-VM study',fontsize=16,y=.98)
    fig.text(.5,.015,'132 synthetic cases / 6 template families; exact oracle policies. No arbitrary real skill execution.',ha='center',fontsize=10,color='#425466')
    fig.tight_layout(rect=(0,.065,1,.93))
    out=ROOT/'results/figures';out.mkdir(parents=True,exist_ok=True)
    for ext in ('png','pdf'):
        fig.savefig(out/f'mechanistic_comparison.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':main()

"""Scientific figures derived from the complete saved analysis; no selected runs."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

D=Path(__file__).resolve().parent
S=json.loads((D/'analysis/summary.json').read_text());G=S['groups'];C=S['comparisons'];OUT=D/'figures';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
models=['gpt-6-luna','gpt-4.1-mini'];methods=['repair','replan','plain_cegis','contract']
labels=['Model repair','Fresh replan','Plain refinement','State-aware']

fig,axes=plt.subplots(1,2,figsize=(7.1,2.8),sharey=True,layout='constrained')
for ax,model in zip(axes,models):
    x=np.arange(4)
    for shift,campaign,color,label in [(-.18,'main','#527896','Strict'),(.18,'robust_protocol','#C07A42','Normalized')]:
        values=[100*G[f'{campaign}|{model}|{m}']['safe']/72 for m in methods]
        ax.bar(x+shift,values,width=.34,color=color,label=label)
    compiler=G['offline_matched|none|goal_direct'];rate=100*compiler['safe']/compiler['n']
    ax.axhline(rate,linestyle='--',color='#333333',linewidth=1,label='Goal compiler')
    ax.set(title=model,ylim=(0,100),xticks=x,xticklabels=labels)
    ax.tick_params(axis='x',rotation=25);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
axes[0].set_ylabel('Safe completion (%)');axes[1].legend(fontsize=7,loc='upper left',ncol=1)
fig.savefig(OUT/'main_comparison.pdf');fig.savefig(OUT/'main_comparison.png',dpi=190);plt.close(fig)

comparators=['repair','replan','plain_cegis','no_residual','no_dependency','no_history','no_feedback','goal_direct']
names=['Model repair','Fresh replan','Plain refinement','No residual goals','No dependency cuts','No history transforms','No structured feedback','Goal compiler']
fig,axes=plt.subplots(1,2,figsize=(7.1,3.4),sharey=True,layout='constrained')
for ax,model in zip(axes,models):
    for i,m in enumerate(comparators):
        stat=C[f'robust_protocol|{model}|contract-minus-{m}']['family_bootstrap'];v=stat['difference']*100;lo,hi=[100*a for a in stat['interval_95']]
        ax.errorbar(v,i,xerr=[[v-lo],[hi-v]],fmt='o',color='#496D64' if i<3 else '#785C84',capsize=3,markersize=4)
    ax.axvline(0,color='black',linewidth=.7);ax.set(title=model,xlabel='State-aware minus control (pp)',yticks=np.arange(8),yticklabels=names)
    ax.grid(axis='x',alpha=.15)
axes[0].invert_yaxis();fig.savefig(OUT/'paired_differences.pdf');fig.savefig(OUT/'paired_differences.png',dpi=190);plt.close(fig)

attacks=['benign','secret_guard','lost_value','payload_mix','partial_write','confirmed_send','unknown_query','cleanup_done','multi_fault','combined_guard_mix','payload_constant','prompt_poison']
fig,axes=plt.subplots(1,2,figsize=(7.1,3.8),sharey=True,layout='constrained')
for ax,model in zip(axes,models):
    matrix=[]
    for attack in attacks:
        row=[]
        for m in methods:
            r=S['mechanisms'].get(f'robust_protocol|{model}|{m}|{attack}')
            row.append(100*r['safe']/r['n'] if r else np.nan)
        matrix.append(row)
    matrix=np.array(matrix);ax.imshow(matrix,vmin=0,vmax=100,cmap='Blues',aspect='auto')
    for (i,j),v in np.ndenumerate(matrix):
        if not np.isnan(v):ax.text(j,i,str(round(v)),ha='center',va='center',fontsize=7,color='white' if v>=60 else 'black')
    ax.set(title=model,xticks=range(4),xticklabels=['Repair','Replan','Plain','State'],yticks=range(len(attacks)),yticklabels=[a.replace('_',' ') for a in attacks])
fig.savefig(OUT/'mechanisms.pdf');fig.savefig(OUT/'mechanisms.png',dpi=190);plt.close(fig)
print({'figures':3,'source':'analysis/summary.json'})

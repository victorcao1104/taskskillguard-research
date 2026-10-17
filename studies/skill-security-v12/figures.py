"""Generate vector paper figures from saved results, with fixed axes and fonts."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from experiment import D,read
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,
 'pdf.fonttype':42,'savefig.bbox':'tight'})
OUT=D/'figures';OUT.mkdir(exist_ok=True)
def finish(fig,name):
    fig.savefig(OUT/(name+'.pdf'));fig.savefig(OUT/(name+'.png'),dpi=160);plt.close(fig)

rows=read('analysis/deterministic_summary.json')
main=[next(r for r in rows if r['grid']=='ordinary' and r['fault']=='none' and r['variant']=='attack' and r['mode']==m) for m in ('observe','scope','flow','first','cost')]
fig,ax=plt.subplots(figsize=(6.7,2.6));x=np.arange(5);w=.24
for i,(field,label,color) in enumerate([('unauthorized_cases','Scope violation','#b64848'),('forbidden_flow_cases','Forbidden flow','#df9e45'),('authorized_goals','Authorized completion','#247a74')]):
    bars=ax.bar(x+(i-1)*w,[r[field] for r in main],w,label=label,color=color)
    ax.bar_label(bars,padding=2,fontsize=8)
ax.set_xticks(x,['Observe','Scope','Scope + flow','First route','Fewest calls']);ax.set_ylim(0,29);ax.set_yticks([0,6,12,18,24]);ax.set_ylabel('Cases out of 24 attacks')
ax.legend(ncol=3,loc='upper center',bbox_to_anchor=(.5,1.17),frameon=False,fontsize=8)
finish(fig,'security')

fig,axes=plt.subplots(1,2,figsize=(6.7,2.6));x=np.arange(4);faults=['none','transient_before','known_after','ambiguous_after']
for mode,offset,color,label in [('first',-.18,'#64748b','First feasible'),('cost',.18,'#247a74','Fewest calls')]:
    data=[[r for r in rows if r['grid']=='ordinary' and r['fault']==f and r['mode']==mode] for f in faults]
    for ax,metric in zip(axes,['authorized_goals','calls']):
        bars=ax.bar(x+offset,[sum(r[metric] for r in group) for group in data],.36,color=color,label=label);ax.bar_label(bars,fontsize=7,padding=2)
for ax in axes:ax.set_xticks(x,['None','Before','Known','Ambiguous']);ax.set_xlabel('Fault condition')
axes[0].set_ylabel('Completed tasks / 48');axes[0].set_ylim(0,59);axes[1].set_ylabel('Total charged calls');axes[1].set_ylim(0,300)
axes[1].legend(frameon=False,fontsize=7);fig.tight_layout();finish(fig,'recovery')

scores=read('analysis/model_scores.json');fig,axes=plt.subplots(1,2,figsize=(6.7,2.6));axesnames=['scope','flow','current','catalogue']
for ax,model in zip(axes,['gpt-6-luna','gpt-4.1-mini']):
    for view,offset,color in [('source',-.18,'#64748b'),('graph',.18,'#247a74')]:
        vals=[]
        for axis in axesnames:
            r=[s for s in scores if s['model']==model and s['view']==view and s['grid']=='ordinary' and s['axis']==axis and not(axis=='flow' and s['target']=='na')]
            vals.append(100*sum(s['correct'] for s in r)/len(r))
        ax.bar(np.arange(4)+offset,vals,.36,label=view,color=color)
    ax.set_title(model,fontsize=9);ax.set_ylim(0,105);ax.set_xticks(np.arange(4),['Scope','Flow','Current','Class']);ax.legend(frameon=False,fontsize=7)
axes[0].set_ylabel('Correct fields (%)');fig.tight_layout();finish(fig,'models')
print('Wrote three PDF/PNG figure pairs from committed analysis tables.')

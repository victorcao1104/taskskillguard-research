"""Static research figures derived directly from saved primary evidence."""
import json
import sys
from collections import defaultdict
from phase8_common import ROOT,read_rows,jb,immutable
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    out=ROOT/'results/phase8/figures';out.mkdir(parents=True,exist_ok=True)
    truth={r['case_id']:r for r in read_rows(ROOT/'results/phase8/semantics/truth.jsonl')}
    axes=('authorization','current_route_required','catalog_required');groups=defaultdict(list)
    for r in read_rows(ROOT/'results/phase8/api/observations.jsonl'):
        if r['replicate']==0 and r['split']=='heldout':groups[(r['model'],r['view'])].append(r)
    values=[]
    fig,panels=plt.subplots(1,2,figsize=(11,4.5),sharey=True)
    colors=('#64748b','#0891b2','#d97706')
    for ax,model in zip(panels,('gpt-4.1-mini','gpt-6-luna')):
        for vi,view in enumerate(('D','F','T')):
            rs=groups[(model,view)];n=sum(len(truth[r['case_id']]['labels']) for r in rs)
            correct=[sum(r['parsed']['by_id'].get(t['id'],{}).get(a)==t[a] for r in rs for t in truth[r['case_id']]['labels']) for a in axes]
            ax.bar([i+(vi-1)*.25 for i in range(3)],[100*x/n for x in correct],width=.23,color=colors[vi],label=view)
            values.append({'model':model,'view':view,'denominator':n,'correct':correct})
        ax.set_xticks(range(3),['Authorization','Current route','Catalog']);ax.set_title(model);ax.set_ylim(0,105)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(frameon=False)
    panels[0].set_ylabel('Typed accuracy (%)')
    fig.suptitle('New synthetic families: all 224 candidates, invalid responses retained')
    fig.text(.5,.01,'D: direct labels   F: model facts + deterministic reducer   T: exact tool facts + model labels',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.05,1,.96]);fig.savefig(out/'model_comparison.png',dpi=180)
    fig.savefig(out/'model_comparison.pdf',metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
    recovery=read_rows(ROOT/'results/phase8/recovery/vm_results.jsonl');rv=[]
    fig,panels=plt.subplots(1,3,figsize=(12,4.5))
    for pi,policy in enumerate(('v7_safe','priority_equal','cost_equal')):
        subsets=[[r for r in recovery if r['split']=='heldout' and r['quota']==16 and r['fault']==f and r['policy']==policy] for f in ('transient_before','double_transient_before')]
        stats=[{'success':sum(r['result']['authorized_goal'] for r in rs),'calls':sum(r['result']['charged_calls'] for r in rs),'planning':sum(r['result']['planner_steps'] for r in rs),'n':len(rs)} for rs in subsets]
        rv.append({'policy':policy,'one_fault':stats[0],'two_faults':stats[1]})
        for ax,key in zip(panels,('success','calls','planning')):
            ax.bar([i+(pi-1)*.25 for i in range(2)],[s[key] for s in stats],width=.23,color=colors[pi],label=policy)
            ax.set_xticks([0,1],['One transient','Two transients']);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    for ax,title in zip(panels,('Completed worlds / 84','Charged effect calls (total)','Simulated planning steps (total)')):ax.set_title(title)
    panels[0].set_ylim(0,90);panels[2].legend(frameon=False,fontsize=8)
    fig.suptitle('New synthetic worlds, quota 16: call savings have planning costs')
    fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(out/'recovery_tradeoff.png',dpi=180)
    fig.savefig(out/'recovery_tradeoff.pdf',metadata={'CreationDate':None,'ModDate':None});plt.close(fig)
    immutable(out/'source_values.json',jb({'models':values,'recovery':rv}))
    print(json.dumps({'figures':2,'source_values':'results/phase8/figures/source_values.json'}))


if __name__=='__main__':main()

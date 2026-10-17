"""Static scientific figures from completed, published analysis only."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from gr14.campaign import STUDY

def main():
    a=json.loads((STUDY/'reports/analysis.json').read_text(encoding='utf-8'))
    methods=['repair_raw','repair_state','replan_raw','replan_state','full','full_no_reuse']
    labels=['Repair','Repair\n+ state','Replan','Replan\n+ state','Full','Full\nno reuse']
    colors=['#9ba9b5','#21618c','#9ba9b5','#21618c','#ca6f1e','#f0b27a']
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),sharey=True)
    for ax,model in zip(axes,['gpt-6-luna','gpt-4.1-mini']):
        rows={r['method']:r for r in a['blocked']['aggregate'] if r['model']==model}
        values=[100*rows[m]['safe']/rows[m]['n'] for m in methods]
        ax.bar(range(6),values,color=colors,width=.72)
        for i,m in enumerate(methods):ax.text(i,values[i]+2,f"{rows[m]['safe']}/{rows[m]['n']}",ha='center',fontsize=9)
        comp=next(r for r in a['matched_controls']['blocked'] if r['method']=='compiler')
        ax.axhline(100*comp['safe']/comp['n'],color='#202020',linestyle='--',linewidth=1,label=f"Compiler: {comp['safe']}/{comp['n']} blocked cases")
        ax.set_xticks(range(6),labels,fontsize=9);ax.set_ylim(0,103);ax.set_title(model);ax.legend(fontsize=8,loc='upper left');ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Safe completion on blocked episodes (%)')
    fig.suptitle('Shared constraints and verifier; six designed task families',fontsize=12)
    fig.tight_layout();out=STUDY/'figures';out.mkdir(exist_ok=True)
    fig.savefig(out/'blocked_comparison.png',dpi=200);fig.savefig(out/'blocked_comparison.pdf');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.2))
    for ax,model in zip(axes,['gpt-6-luna','gpt-4.1-mini']):
        rows={r['method']:r for r in a['blocked']['aggregate'] if r['model']==model}
        vals=[rows[m]['requests'] for m in methods];ax.bar(range(6),vals,color=colors)
        for i,v in enumerate(vals):ax.text(i,v+1,str(v),ha='center',fontsize=9)
        ax.set_xticks(range(6),labels,fontsize=9);ax.set_title(model);ax.set_ylim(0,max(vals)*1.2+1);ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Model requests (blocked episodes)');fig.suptitle('Requests are one cost component; validation work is reported separately',fontsize=11)
    fig.tight_layout();fig.savefig(out/'model_requests.png',dpi=200);fig.savefig(out/'model_requests.pdf');plt.close(fig)
if __name__=='__main__':main()

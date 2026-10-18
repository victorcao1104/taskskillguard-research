"""Separate analysis of the post-review enforced-computation state experiment."""
import gzip,json
from pathlib import Path
from analyze import flatten,summary,contrast
from rm15.protocol import MODELS,HISTORIES
ROOT=Path(__file__).resolve().parent

def main():
    records=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((ROOT/'results/strict_state_recovered/episodes').glob('*.json.gz'))]
    if len(records)!=512:raise ValueError('INCOMPLETE_STRICT_GRID:'+str(len(records)))
    rows=[flatten(r) for r in records];groups={};comparisons={}
    for model in MODELS:
        for method in 'ABCD':
            rs=[r for r in rows if r['model']==model and r['method']==method]
            groups[f'{model}/{method}']=summary(rs)
            for h in HISTORIES:groups[f'{model}/{method}/{h}']=summary([r for r in rs if r['history']==h])
        for left,right in (('B','A'),('C','B'),('D','C')):
            comparisons[f'{model}/{left}-minus-{right}']=contrast([r for r in rows if r['model']==model and r['method']==left],[r for r in rows if r['model']==model and r['method']==right])
    report={'scope':'Post-review controlled state supplement, environment-recovered acquisition. Both original main state episodes and first strict acquisition preserved separately. Same supplied computation, input reads enforced only through fixed compute tool; valid cache reuse remains allowed.',
            'overall':summary(rows),'groups':groups,'contrasts':comparisons}
    (ROOT/'reports/strict_state_summary.json').write_bytes((json.dumps(report,sort_keys=True,indent=2)+'\n').encode())
    (ROOT/'reports/strict_episode_table.json').write_bytes((json.dumps(rows,sort_keys=True,indent=2)+'\n').encode())
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,3.6),layout='constrained')
    for ax,model in zip(axes,MODELS):
        for history in HISTORIES:
            values=[100*groups[f'{model}/{m}/{history}']['successful_final']/16 for m in 'ABCD']
            ax.plot(list('ABCD'),values,marker='o',label=history)
        ax.set_title(model);ax.set_ylim(-3,105);ax.set_ylabel('Correct outcome (%)');ax.set_xlabel('State support, fixed computation enforced');ax.grid(alpha=.2)
    axes[1].legend(fontsize=8)
    for ext in ('png','pdf'):fig.savefig(ROOT/'reports/figures'/('strict_state_support.'+ext),dpi=180)
    plt.close(fig);print(json.dumps(report['overall']))

if __name__=='__main__':main()

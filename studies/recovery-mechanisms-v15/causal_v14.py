"""New causal diagnostics over frozen v14 failures; never edits old programs."""
import ast,copy,difflib,gzip,hashlib,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'goal-recovery-v14'
sys.path.insert(0,str(OLD))
from gr14.data import make_case,inputs_for,SOURCE_COMPUTE
from gr14.verify import evaluate

def remove_relations(source,goal,relations):
    flags={'requires':'closed_dependencies','conflicts':'no_conflicts'}
    for relation in relations:
        if goal.get(flags[relation],False):raise ValueError('ACTIVE_CONSTRAINT:'+relation)
    lines=source.splitlines(keepends=True);offsets=[];pos=0
    for line in lines:offsets.append(pos);pos+=len(line)
    edits=[]
    for n in ast.walk(ast.parse(source)):
        if isinstance(n,ast.Subscript) and isinstance(n.slice,ast.Constant) and n.slice.value in relations:
            start=offsets[n.lineno-1]+n.col_offset;end=offsets[n.end_lineno-1]+n.end_col_offset
            edits.append({'start':start,'end':end,'before':source[start:end],'after':'[]','relation':n.slice.value})
    out=source
    for e in sorted(edits,key=lambda e:e['start'],reverse=True):out=out[:e['start']]+'[]'+out[e['end']:]
    return out,edits

def pack(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode()
    if path.exists():
        if gzip.decompress(path.read_bytes())!=data:raise ValueError('IMMUTABLE_RESULT')
    else:path.write_bytes(gzip.compress(data,mtime=0))

def summarize(r):
    return {k:v for k,v in r.items() if k!='records'}

def run():
    cases=json.loads((OLD/'reports/accepted_failure_analysis.json').read_text())['episodes']
    records=[]
    for i,e in enumerate(cases):
        case=make_case(*e['case_id'].split('--'));original=e['selected']
        original_sha=hashlib.sha256(original['compute'].encode()).hexdigest()
        variants={}
        for name,relations in [('original',[]),('dependencies',['requires']),('conflicts',['conflicts']),('both',['requires','conflicts'])]:
            code,edits=remove_relations(original['compute'],case['task']['goal'],relations)
            variants[name]={'program':dict(original,compute=code),'edits':edits}
        injected=SOURCE_COMPUTE.replace('if valid(proposal):',
          "if valid(proposal) and all(req in proposal for item in group for req in item['requires']) and all(conf not in proposal for item in group for conf in item['conflicts']):")
        variants['correct_reference']={'program':{'compute':SOURCE_COMPUTE,'effects':'pass'},'edits':[]}
        variants['injected_reference']={'program':{'compute':injected,'effects':'pass'},'edits':[]}
        item={'index':i,'case_id':e['case_id'],'method':e['method'],'replicate':e['replicate'],
              'original_sha256':original_sha,'source_file':e['file'],'variants':{}}
        for name,v in variants.items():
            item['variants'][name]={'program':v['program'],'edits':v['edits'],'evaluations':{}}
            for budget in [20000,80000]:
                c=copy.deepcopy(case);c['task']['max_steps']=budget
                phases={}
                for phase in ['validation','final','stress']:
                    r=evaluate(v['program'],c,inputs_for(case,phase),state=True)
                    path=HERE/'results/causal'/f'case{i}--{name}--{budget}--{phase}.json.gz'
                    pack(path,r);phases[phase]=summarize(r)
                item['variants'][name]['evaluations'][str(budget)]=phases
        baseline=item['variants']['original']['evaluations']['20000']['final']
        assert not baseline['safe_complete']
        assert baseline['stop_codes']==e['stop_codes'],(i,baseline['stop_codes'],e['stop_codes'])
        records.append(item)
        print(json.dumps({'causal_case':i,'original':baseline['safe_complete'],
             'both':item['variants']['both']['evaluations']['20000']['final']['safe_complete']}),flush=True)
    report={'purpose':'New intervention; does not replace v14 failure outcomes. Relation lookups alone are neutralized; all other source text is preserved.',
            'original_failures':len(cases),'records':records}
    path=HERE/'reports/causal_v14.json';path.parent.mkdir(exist_ok=True)
    path.write_bytes((json.dumps(report,indent=2)+'\n').encode())
    short=[]
    for r in records:
        row={'case':r['index'],'case_id':r['case_id'],'method':r['method'],'replicate':r['replicate']}
        for name in r['variants']:
            for budget in ['20000','80000']:
                q=r['variants'][name]['evaluations'][budget]['final']
                row[name+'_'+budget]={'safe':q['safe_complete'],'steps':q['cost']['steps'],'stop':q['stop_codes']}
        short.append(row)
    (HERE/'reports/causal_summary.json').write_bytes((json.dumps(short,indent=2)+'\n').encode())
if __name__=='__main__':run()

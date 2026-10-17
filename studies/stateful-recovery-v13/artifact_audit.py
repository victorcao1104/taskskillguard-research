"""Package binding and reachable-fault evidence, with corrected physical traces."""
from run import D
from sr13.io import read,save,digest
from sr13.data import inputs_for
from sr13.contracts import snapshot
from sr13.engine import execute
from state_amendment import physical_history,corrected_snapshot


def main():
    packages=[];faults=[]
    for c in read(D/'data/cases.json'):
        folder=D/'data/packages'/c['case_id'];md=folder/'SKILL.md';program=folder/'scripts/main.json'
        assert md.read_text(encoding='utf-8')==c['skill_md']+'\n'
        assert read(program)==c['skill']
        packages.append({'case_id':c['case_id'],'instruction_sha256':digest(md.read_bytes()),'program_sha256':digest(program.read_bytes())})
        if not(c.get('faults') or c.get('recovery_faults')):continue
        inp=inputs_for(c)['validation'][0]
        for method in ('goal_direct','contract_source'):
            r=read(D/'results/offline_corrected'/f"{c['case_id']}--{method}.json")
            for committed in ([True,False] if c.get('uncertain_delivery') else [True]):
                w,stop=corrected_snapshot(c,inp,unknown_committed=committed);n=len(w['trace'])
                result=execute(r['program'],w,c['task']);trace=result['world']['trace']
                faults.append({'case_id':c['case_id'],'method':method,'unknown_committed':committed,
                    'candidate_accepted':r['accepted'],'prefix_stop':stop,'continuation_stop':result['stop'],
                    'planned_recovery_faults':c['recovery_faults'],
                    'observed_recovery_fault_events':[e for e in trace[n:] if e.get('code') in {'TRANSIENT_NO_EFFECT','UNCERTAIN_EFFECT'}],
                    'prefix_trace':trace[:n],'candidate_trace':trace[n:],
                    'interpretation':'Candidate simulation, not a claim that a rejected proposal was deployed.'})
    save(D/'analysis/artifact_and_fault_audit.json',{'packages_checked':len(packages),'package_bindings':packages,'fault_candidates':faults})
    print({'packages_checked':len(packages),'fault_candidate_worlds':len(faults)})


if __name__=='__main__':main()

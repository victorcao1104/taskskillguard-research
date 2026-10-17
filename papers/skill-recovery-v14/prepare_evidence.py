"""Prepare a read-only evidence map and check paper numbers against frozen v14."""
import hashlib, json, re, subprocess
from pathlib import Path
P = Path(__file__).resolve().parent
ROOT = P.parents[1]
D = ROOT / "studies/goal-recovery-v14"
BASE = "ea7bb8ce9e8495a03566e1d5b91a1e3698237b50"
def read(name):
    return json.loads((D / "reports" / name).read_text(encoding="utf-8"))
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
a=read("analysis.json")
f=read("accepted_failure_analysis.json")
audit=read("reproduction_audit.json")
rows={(r["model"], r["method"]):r for r in a["blocked"]["aggregate"]}
order=["repair_raw","repair_state","replan_raw","replan_state","full","full_no_reuse"]
expected={
    "gpt-6-luna":([37,42,35,40,45,45],[66,60,67,67,20,21]),
    "gpt-4.1-mini":([39,40,24,30,42,41],[83,80,123,115,27,27])
}
for model,(safe,reqs) in expected.items():
    for method,safe_n,req_n in zip(order,safe,reqs):
        r=rows[model,method]
        assert (r["safe"],r["requests"],r["n"],r["feasible_n"])==(safe_n,req_n,54,45)
assert f["count"]==7
assert audit["summary_gzip_comparisons"]==2436
assert sum(r["compared"] for r in audit["replay"])==1008
assert all(not r["mismatches"] for r in audit["replay"])
assert audit["raw_count"]==1231
tex=(P/"paper.tex").read_text(encoding="utf-8")
labels=["Repair","Repair + state","Replan","Replan + state","Full","Full, no variable reuse"]
for i,label in enumerate(labels):
    lu=rows["gpt-6-luna",order[i]]
    mi=rows["gpt-4.1-mini",order[i]]
    literal=f'{label}&{lu["safe"]}/54&{mi["safe"]}/54&{lu["requests"]}&{mi["requests"]}'
    assert literal in tex,literal
combined={(r['model'],r['method']):r for r in a['combined']['aggregate']}
for method,label in [('repair_state','Repair + state'),('replan_state','Replan + state'),('full','Full')]:
    lu,mi=(combined[m,method] for m in ['gpt-6-luna','gpt-4.1-mini'])
    literal=f'{label}&{lu["safe"]}/24&{mi["safe"]}/24&{lu["requests"]}&{mi["requests"]}'
    assert literal in tex,literal
for i,label in enumerate(labels[:5]):
    lu,mi=(rows[m,order[i]] for m in ['gpt-6-luna','gpt-4.1-mini'])
    costs=[]
    for r in [lu,mi]:
        costs += [f'{r["construction_steps_including_prefix"]/r["n"]:,.0f}',f'{r["final_steps_including_prefix"]/r["final_worlds"]:.2f}']
    assert label+'&'+'&'.join(costs) in tex,(label,costs)
compiler=next(r for r in a['matched_controls']['blocked'] if r['method']=='compiler')
assert (compiler['safe'],compiler['n'],compiler['feasible_n'])==(15,18,15)
assert f'{compiler["final_steps_including_prefix"]/compiler["final_worlds"]:.2f}' in tex
for model,pvalue in [('gpt-6-luna',0.5),('gpt-4.1-mini',1.0)]:
    c=next(c for c in a['blocked']['contrasts'] if c['model']==model and c['a']=='full' and c['b']=='repair_state')
    assert c['exact_family_sign_flip_two_sided_p']==pvalue
    assert f'{100*c["difference"]:.2f}' in tex
for r in f['episodes']:
    counts=r['counterexample_solution_counts']
    assert counts['trusted_goal'] in (1,6)
probes=read('controlled_probes.json')
assert len(probes['reuse'])==24 and len(probes['validation'])==24
assert sum(not r['legacy']['valid_output'] for r in probes['reuse'])==18
assert sum(r['current']['valid_output'] for r in probes['reuse'])==23
files=subprocess.check_output(["git","ls-tree","-r","--name-only",BASE,"--","studies/goal-recovery-v14"],cwd=ROOT,text=True).splitlines()
manifest=[]
for rel in files:
    path=ROOT/rel
    manifest.append({"path":rel,"bytes":path.stat().st_size,"sha256":sha(path)})
changed=subprocess.check_output(["git","diff",BASE,"--name-only","--","studies"],cwd=ROOT,text=True).splitlines()
assert not changed,changed
old_pdf_paths=subprocess.check_output(["git","ls-tree","-r","--name-only",BASE],cwd=ROOT,text=True).splitlines()
old_pdfs=[{"path":r,"sha256":sha(ROOT/r)} for r in old_pdf_paths if r.lower().endswith(".pdf")]
evidence={
 "experiment_commit":BASE,"experiment_tag":"v14-goal-checked-recovery",
 "interpretation":"Read-only manuscript evidence snapshot. No new model calls or experimental changes.",
 "files":manifest,"old_pdfs_preserved":old_pdfs,
 "claim_sources":{
  "Tables IV and V / blocked completion and costs":"reports/analysis.json: blocked.aggregate",
  "paired uncertainty":"reports/analysis.json: blocked.contrasts",
  "Table VI / combined results":"reports/analysis.json: combined.aggregate",
  "compiler":"reports/analysis.json: controls, matched_controls, combined_controls",
  "Table VII / overconstraint cases":"reports/accepted_failure_analysis.json",
  "API error and parser normalization":"reports/acquisition_diagnostics.json",
  "cache and challenge probes":"reports/controlled_probes.json",
  "benign original worlds":"reports/benign_all_phases.json",
  "cached replay and preservation":"reports/reproduction_audit.json"
 }}
(P/"evidence").mkdir(exist_ok=True)
(P/"evidence/manifest.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8",newline="\n")
extract={k:a[k] for k in ["blocked","combined","matched_controls","combined_controls","controls","budget"]}
(P/"evidence/key_results.json").write_text(json.dumps(extract,indent=2)+"\n",encoding="utf-8",newline="\n")
summary={"experiment_files_hashed":len(manifest),"old_pdfs_preserved":len(old_pdfs),
         "checked_blocked_rows":6,"checked_combined_rows":3,"checked_cost_rows":5,
         "checked_paired_contrasts":2,"accepted_final_failures":7,"cached_replay_episodes":1008,
         "frozen_study_diff":changed}
(P/"evidence/checks.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps(summary,indent=2))

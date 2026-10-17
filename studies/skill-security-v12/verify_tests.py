"""Run relevant old and new regressions, saving the actual process result."""
import json,os,subprocess,sys,tempfile
from experiment import D,ROOT,save
files=['tests/test_extraction_v5.py','tests/test_truth_v6.py','tests/test_selection_v6.py']
files += ['studies/skill-security-v12/'+x for x in ['test_adapter.py','test_runtime.py','test_protocol.py','test_reference.py','test_review_regressions.py']]
command=[sys.executable,'-m','pytest',*files,'-q','--basetemp',os.path.join(tempfile.gettempdir(),'tsg12-final-regression')]
run=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
save(D/'provenance/test_verification.json',{'command':command,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr,
 'scope':'138 relevant preserved Phase5/6 tests and 70 new reference/adapter/runtime/protocol/review tests; not the entire historical repository suite.',
 'baseline_environment_note':'Earlier sandbox baseline had135passes3tempdirerrors; native baseline138passed. Final run uses a dedicated writable temp directory.'})
print(run.stdout);print(run.stderr);raise SystemExit(run.returncode)

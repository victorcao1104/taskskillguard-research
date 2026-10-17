"""Run before reading or importing the independently authored evaluation cases."""
import hashlib,json,datetime
from pathlib import Path
D=Path(__file__).resolve().parent
names=['adapter.py','runtime.py','protocol.py','test_adapter.py','test_runtime.py','test_protocol.py',
       'reference.py','test_reference.py','fixtures.py','design.md','plan.md']
dest=D/'provenance'/'pre_evaluation_freeze'
dest.mkdir(parents=True,exist_ok=True)
hashes={}
for name in names:
    data=(D/name).read_bytes();p=dest/name
    if p.exists() and p.read_bytes()!=data:raise ValueError('FREEZE_ALREADY_EXISTS_DIFFERENT:'+name)
    if not p.exists():p.write_bytes(data)
    hashes[name]=hashlib.sha256(data).hexdigest()
out=dest/'manifest.json'
if not out.exists():
    out.write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'evaluation_cases_materialized':False,'production_author_read_fixtures':False,
      'independent_author_read_production':False,'sha256':hashes,
      'pre_freeze_review_repairs':['resource-expression taint','helper hygiene','loop target loads',
       'reserved names','Markdown region selection','function definition order','parse size precheck'],
      'phase6_bridge':'Compare only type-compatible executions; Phase6 string coercion differs from this string-only subset.',
      'catalogue_validity':'Unsupported alternatives are rejected before execution; measure separately from original-source coverage.',
      'fixed_metrics':'source coverage; scope/flow violations; authorized goals; current/catalogue necessity; calls; planner work; unknown categories',
      'new_acquisition_reservation_cap_usd':3},indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'frozen':len(hashes),'manifest':str(out)}))

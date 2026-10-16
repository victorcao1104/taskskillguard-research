"""Copy independent first-pass bytes after production freeze; never regenerate."""
import json
from datetime import datetime,timezone
from phase11_common import ROOT,sha,jb,immutable,verify_freeze

def materialize(cohort):
    freeze=verify_freeze('production')
    directory='phase11-reference-firstpass' if cohort=='main' else 'phase11-challenge-firstpass'
    source=ROOT/'work'/directory
    provenance=json.loads((source/'provenance.json').read_text(encoding='utf-8'))
    for name,digest in provenance['source_sha256'].items():
        assert sha((ROOT/name).read_bytes())==digest,'INDEPENDENT_SOURCE_CHANGED:'+name
    for name,digest in provenance['artifact_sha256'].items():
        assert sha((source/name).read_bytes())==digest,'FIRSTPASS_CHANGED:'+name
    for path in sorted(source.iterdir()):
        if not path.is_file():continue
        immutable(ROOT/f'results/phase11/reference/{cohort}/first-pass/{path.name}',path.read_bytes())
        if path.name.endswith('.jsonl'):
            immutable(ROOT/f'data/phase11/{path.name}',path.read_bytes())
        else:immutable(ROOT/f'results/phase11/reference/{cohort}/{path.name}',path.read_bytes())
    path=ROOT/f'results/phase11/provenance/materialization_{cohort}.json'
    if not path.exists():
        immutable(path,jb({'cohort':cohort,'materialized_at_utc':datetime.now(timezone.utc).isoformat(),
            'production_freeze_sha256':sha((ROOT/'results/phase11/provenance/production_freeze.json').read_bytes()),
            'production_frozen_files':len(freeze['files']),'firstpass_provenance_sha256':sha((source/'provenance.json').read_bytes()),
            'mode':'unchanged first-pass bytes copied after production freeze'}))
    return {'cohort':cohort,'artifacts':list(provenance['artifact_sha256'])}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('cohort',choices=['main','challenge']);a=p.parse_args()
    print(json.dumps(materialize(a.cohort)),flush=True)

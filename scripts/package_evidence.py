"""Hash staged release bytes; require Git's staged content to match disk."""
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUTPUT='results/verification/artifact_manifest.json'


def main():
    records=[];mismatches=[];total=0
    entries=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).decode('utf-8').split('\0')
    for entry in filter(None,entries):
        metadata,name=entry.split('\t',1)
        if name==OUTPUT:continue
        mode,oid,stage=metadata.split()
        data=(ROOT/name).read_bytes()
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if actual!=oid:mismatches.append(name)
        total+=len(data)
        records.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    report={'file_count':len(records),'total_bytes':total,'git_index_matches_working_bytes':not mismatches,'files':records}
    (ROOT/OUTPUT).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'files':len(records),'bytes':total,'index_byte_mismatches':mismatches}))
    return bool(mismatches)


if __name__=='__main__':raise SystemExit(main())

"""Immutable evidence files, deterministic compressed traces and semantic digests."""
from pathlib import Path
import gzip,hashlib,json


def encoded(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()


def save(path,value):
    path=Path(path);data=encoded(value);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('IMMUTABLE_EVIDENCE_CHANGED:'+str(path))
    else:path.write_bytes(data)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def semantic(value):
    if isinstance(value,dict):
        return {k:semantic(v) for k,v in value.items() if k not in
                {'elapsed_seconds','search_seconds','search_cpu_seconds','construction_seconds'}}
    if isinstance(value,list):return [semantic(v) for v in value]
    return value


def save_trial(path,result):
    path=Path(path);traces=result['evaluation'].pop('traces');trace_name=path.stem+'.traces.json.gz'
    blob=gzip.compress(encoded(traces),mtime=0);trace_path=path.with_name(trace_name);trace_path.parent.mkdir(parents=True,exist_ok=True)
    if trace_path.exists() and trace_path.read_bytes()!=blob:raise ValueError('TRACE_CHANGED')
    if not trace_path.exists():trace_path.write_bytes(blob)
    result['trace_file']=trace_name;result['trace_sha256']=digest(blob)
    save(path,result)


def source_hashes(directory):
    directory=Path(directory)
    paths=sorted((directory/'sr13').glob('*.py'))+[directory/'run.py']
    return {p.relative_to(directory).as_posix():digest(p.read_bytes()) for p in paths}

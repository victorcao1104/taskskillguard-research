"""Inventory only the additive release files; do not include ignored local work."""
import json,re,subprocess
from experiment import D,ROOT,save,digest
prefix=D.relative_to(ROOT).as_posix()
names=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z','--','PHASE12.md',prefix],cwd=ROOT).decode().split('\0')
names += subprocess.check_output(['git','diff','--cached','--name-only','-z','--','PHASE12.md',prefix],cwd=ROOT).decode().split('\0')
self_path=prefix+'/provenance/publication_manifest.json'
files={};suspect=[]
for name in sorted(set(names)-{'',self_path}):
    p=ROOT/name;data=p.read_bytes()
    files[name]={'sha256':digest(data),'bytes':len(data)}
    if re.search(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}',data):suspect.append(name)
if suspect:raise ValueError('CREDENTIAL_PATTERN_FILES:'+repr(suspect))
save(D/'provenance/publication_manifest.json',{'branch':'study-v12-skill-security','tag':'skill-security-v12.0',
 'private_repository':'victorcao1104/taskskillguard-research','file_count':len(files),'files':files,
 'total_bytes':sum(v['bytes'] for v in files.values()),'excludes':'this manifest itself, ignored local/cache/work files',
 'credential_pattern_scan':'No OpenAI key-format matches in release files. This is a narrow pattern check, not a general secrecy proof.'})
print(json.dumps({'release_files_excluding_self':len(files),'total_bytes':sum(v['bytes'] for v in files.values())}))

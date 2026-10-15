"""Freeze new release bytes from a separately obtained Git path inventory."""
import argparse
import json
from pathlib import Path
from prepare_phase4 import immutable, json_bytes, sha

ROOT = Path(__file__).resolve().parents[1]


def main(paths_file):
    baseline=json.loads((ROOT/'results/phase5/provenance/baseline.json').read_text(encoding='utf-8'))
    paths=Path(paths_file).read_text(encoding='utf-8-sig').splitlines()
    excludes={'results/phase5/provenance/release_hashes.json',
              'results/phase5/provenance/release_verification.json'}
    hashes={}
    for name in sorted(set(paths)-excludes):
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file(): raise ValueError('INVALID_RELEASE_PATH:'+name)
        if name in baseline['files']: raise ValueError('INHERITED_PATH_IN_NEW_INVENTORY:'+name)
        hashes[name]=sha(path.read_bytes())
    manifest={'baseline_commit':baseline['baseline_commit'] if 'baseline_commit' in baseline else '190738561ad98ddf246fda02371b41df7d30dc04',
              'files':hashes,'exclusions':sorted(excludes),
              'inventory_method':'Direct git ls-files --others --exclude-standard before staging',
              'omission_jsonl':'Full original bytes in data/phase5/human_review/omitted_files.jsonl.gz; local uncompressed copy excluded.'}
    immutable(ROOT/'results/phase5/provenance/release_hashes.json',json_bytes(manifest))
    print(json.dumps({'new_files':len(hashes),'manifest':'results/phase5/provenance/release_hashes.json'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--paths-file',required=True)
    main(parser.parse_args().paths_file)

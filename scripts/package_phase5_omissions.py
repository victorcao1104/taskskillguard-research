"""Lossless packaging for the large, repetitive omission provenance JSONL."""
import gzip
import json
from pathlib import Path
from prepare_phase4 import immutable, json_bytes, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / 'data/phase5/human_review'
    source = folder / 'omitted_files.jsonl'
    data = source.read_bytes()
    packed = gzip.compress(data, compresslevel=9, mtime=0)
    if gzip.decompress(packed) != data:
        raise ValueError('LOSSLESS_ROUNDTRIP_FAILED')
    immutable(folder / 'omitted_files.jsonl.gz', packed)
    info = {'uncompressed_name': source.name, 'uncompressed_bytes': len(data),
            'uncompressed_sha256': sha(data), 'records': len(data.splitlines()),
            'compressed_name': 'omitted_files.jsonl.gz', 'compressed_bytes': len(packed),
            'compressed_sha256': sha(packed), 'codec': 'gzip',
            'reason': 'Repeated per-file provenance exceeds GitHub single-file limit; '
                      'all original bytes preserved in compressed artifact and local JSONL.',
            'content_changed': False}
    immutable(folder / 'omitted_files_packaging.json', json_bytes(info))
    print(json.dumps(info))


if __name__ == '__main__':
    main()

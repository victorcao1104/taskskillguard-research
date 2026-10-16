"""Restore immutable first-pass fixtures into ignored work/ on clean checkouts.

These are byte copies, not regenerated truth or replacement experiment outcomes.
Existing different bytes are an error. Only work/ is written.
"""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def hydrate(root=ROOT):
    root = Path(root).resolve()
    counts = {}
    for cohort, destination in (
        ('main', 'phase11-reference-firstpass'),
        ('challenge', 'phase11-challenge-firstpass'),
    ):
        source = root / 'results/phase11/reference' / cohort / 'first-pass'
        provenance = json.loads((source / 'provenance.json').read_text(encoding='utf-8'))
        for name, digest in provenance['artifact_sha256'].items():
            if sha256((source / name).read_bytes()).hexdigest() != digest:
                raise ValueError('ARCHIVED_FIRSTPASS_CHANGED:' + name)
        target = root / 'work' / destination
        files = [p for p in source.iterdir() if p.is_file()]
        # Check every existing target before creating any file.
        for p in files:
            dst = target / p.name
            if dst.exists() and dst.read_bytes() != p.read_bytes():
                raise ValueError('EXISTING_FIRSTPASS_DIFFERS:' + str(dst))
        target.mkdir(parents=True, exist_ok=True)
        for p in files:
            dst = target / p.name
            if not dst.exists():
                with dst.open('xb') as handle:
                    handle.write(p.read_bytes())
        counts[cohort] = len(files)
    return counts


if __name__ == '__main__':
    print(json.dumps(hydrate()))

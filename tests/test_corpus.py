import hashlib
import json
import sqlite3

from tsg.corpus import build_manifest, group_split, readonly_connection


def test_readonly_connection_cannot_write(tmp_path):
    path = tmp_path / 'state.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE sample(value TEXT)')
    before = path.read_bytes()
    with readonly_connection(path) as db:
        try:
            db.execute("INSERT INTO sample VALUES ('mutated')")
        except sqlite3.OperationalError:
            pass
        else:
            raise AssertionError('original database accepted a write')
    assert path.read_bytes() == before


def test_completed_sampling_preserves_source_and_hash(tmp_path):
    with sqlite3.connect(tmp_path / 'state.sqlite') as db:
        db.execute('CREATE TABLE materializations(source_native_id TEXT,status TEXT,raw_directory TEXT)')
        db.executemany('INSERT INTO materializations VALUES(?,?,?)', [('a/repo/one','completed','x'),('b/repo/two','failed','y')])
    bundle = tmp_path / 'raw' / 'x'
    bundle.mkdir(parents=True)
    doc = bundle / 'SKILL.md'
    doc.write_text('# CSV report\nRead the CSV and write the report.')
    before = doc.read_bytes()
    rows, report = build_manifest(tmp_path, sample_size=10, seed=7)
    assert len(rows) == 1
    assert rows[0]['source_native_id'] == 'a/repo/one'
    assert rows[0]['skill_sha256'] == hashlib.sha256(before).hexdigest()
    assert rows[0]['skill_md_path'] == str(doc.resolve())
    assert doc.read_bytes() == before
    assert report['completed_count'] == 1


def test_connected_publisher_and_content_families_do_not_leak():
    rows = [
        dict(skill_id='1',publisher_id='alpha',repo_id='alpha/a',skill_sha256='same'),
        dict(skill_id='2',publisher_id='beta',repo_id='beta/a',skill_sha256='same'),
        dict(skill_id='3',publisher_id='beta',repo_id='beta/b',skill_sha256='other'),
        dict(skill_id='4',publisher_id='gamma',repo_id='gamma/c',skill_sha256='third'),
    ]
    actual = group_split(rows, seed=123)
    assert len({r['family_id'] for r in actual[:3]}) == 1
    assert len({r['split'] for r in actual[:3]}) == 1
    assert actual == group_split(rows, seed=123)

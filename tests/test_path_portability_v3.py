"""Windows manifest separators must address the same bundle on POSIX hosts."""
import copy
import hashlib
import posixpath
from pathlib import PurePosixPath

import pytest

from tsg import graph, real_v3


class PosixFixturePath(PurePosixPath):
    """A two-file fixture using real PurePosixPath joining on every test host."""
    files={}

    def resolve(self):
        return type(self)(posixpath.normpath(str(self)))

    def read_bytes(self):
        try:
            return self.files[str(self)]
        except KeyError:
            raise FileNotFoundError(str(self)) from None

    def read_text(self,encoding='utf-8',errors='strict'):
        return self.read_bytes().decode(encoding,errors)


@pytest.fixture
def posix_row(monkeypatch):
    files={'/bundle/SKILL.md':b'Overview.\n','/bundle/reference/action.md':b'Read input.\n'}
    monkeypatch.setattr(PosixFixturePath,'files',files)
    monkeypatch.setattr(real_v3,'Path',PosixFixturePath)
    monkeypatch.setattr(graph,'Path',PosixFixturePath)
    return {'skill_id':'fixture','source_native_id':'fixture/repo','family_id':'fixture-family',
            'split':'development','download_status':'completed','bundle_path':'/bundle',
            'skill_md_path':'/bundle/SKILL.md','file_sha256':{
                'SKILL.md':hashlib.sha256(files['/bundle/SKILL.md']).hexdigest(),
                'reference\\action.md':hashlib.sha256(files['/bundle/reference/action.md']).hexdigest()}}


def test_verified_lookup_normalizes_separators_without_changing_manifest_keys(posix_row):
    result=real_v3._verified_paths(posix_row)
    assert set(result)=={'SKILL.md','reference\\action.md'}
    assert str(result['reference\\action.md'])=='/bundle/reference/action.md'


def test_backslash_traversal_is_checked_after_separator_normalization(posix_row):
    posix_row['file_sha256']['..\\outside.md']='not-read'
    with pytest.raises(ValueError,match='MANIFEST_PATH_OUTSIDE_BUNDLE'):
        real_v3._verified_paths(posix_row)


def test_full_preparation_reads_windows_key_on_posix_and_preserves_source_provenance(posix_row):
    before=copy.deepcopy(posix_row)
    prepared=real_v3.prepare_row(posix_row)
    assert prepared['files']=={'SKILL.md':'Overview.\n','reference/action.md':'Read input.\n'}
    assert prepared['source_verification']['files_checked']==2
    assert prepared['provenance']['file_sha256']==before['file_sha256']
    assert posix_row==before

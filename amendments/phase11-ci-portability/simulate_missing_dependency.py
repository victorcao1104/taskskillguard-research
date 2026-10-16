import importlib.util
import sys
import pytest

original_find_spec = importlib.util.find_spec
def without_tokenizer(name, package=None):
    return None if name == 'tiktoken' else original_find_spec(name, package)
class MissingTokenizer:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'tiktoken' or fullname.startswith('tiktoken.'):
            raise ModuleNotFoundError('simulated missing optional tiktoken', name='tiktoken')
        return None
importlib.util.find_spec = without_tokenizer
sys.meta_path.insert(0, MissingTokenizer())
args = ['-q', 'tests/test_acquisition_v11.py', 'tests/test_optional_dependency_policy.py',
        '--basetemp', 'work/p11dep-' + sys.argv[1]]
if sys.argv[1] == 'required':
    args.append('--require-tokenizer')
raise SystemExit(pytest.main(args))

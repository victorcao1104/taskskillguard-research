import json
from typed_roles import TypedProvider,ROLES
from robust_protocol import NormalizedProvider
from sr13.protocol import payload
from sr13.data import make_case,make_inputs


def test_shared_guidance_does_not_leak_source_to_replanner(monkeypatch):
    monkeypatch.setattr(NormalizedProvider,'propose',lambda self,model,prompt,**kw:json.loads(prompt))
    provider=object.__new__(TypedProvider);case=make_case('regional_value','secret_guard');inputs=make_inputs(case,101)
    replanned=provider.propose('gpt-4.1-mini',payload(case,inputs,'replan',[],0))
    full=provider.propose('gpt-4.1-mini',payload(case,inputs,'contract',[],1))
    assert replanned['shared_operand_roles']==full['shared_operand_roles']==ROLES
    assert 'original_skill' not in replanned and 'original_skill' in full
    assert ROLES['isolated_generic_example'][0]['path'] not in case['task']['grants']['read']

from runtime_error_adapter import install
import strict_state as strict
from rm15.recovery import snapshot
from rm15.tasks import instance, solver


def test_candidate_get_on_string_is_recorded_as_malformed_without_effects():
    initial=snapshot('aggregation.interval_union',instance('aggregation.interval_union',201),'confirmed','A',True)
    install()
    result=strict.run_program({'compute':'','effects':"x=get('invalid mapping', 'key', None)"},
        initial['world'],initial['task'],level='B',fixed_compute=solver('aggregation.interval_union'))
    assert result['stop']=={'code':'MALFORMED_PROGRAM','detail':'AttributeError'}
    assert result['world']['events']==initial['world']['events']


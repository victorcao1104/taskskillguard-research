"""Explicit v3 physical-history amendment; the frozen v1/v2 source stays intact."""
from contextlib import contextmanager
from sr13 import contracts,verify,methods

BASE_SNAPSHOT=contracts.snapshot


def corrected_snapshot(case,inputs,*,secret_value='A',unknown_committed=True):
    world,stop=BASE_SNAPSHOT(case,inputs,secret_value=secret_value,unknown_committed=unknown_committed)
    if case.get('uncertain_delivery') and not unknown_committed:
        delivery=case['uncertain_delivery']
        for event in world['trace']:
            if event.get('op')=='send' and event.get('target')==delivery and event.get('status')=='success':
                event['status']='not_committed'
                event['history_world']='No effect occurred; acknowledgement was unavailable.'
    return world,stop


@contextmanager
def physical_history():
    modules=(contracts,verify,methods);previous=[m.snapshot for m in modules]
    try:
        for m in modules:m.snapshot=corrected_snapshot
        yield
    finally:
        for m,f in zip(modules,previous):m.snapshot=f

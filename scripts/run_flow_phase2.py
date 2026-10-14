"""Explicit/derived/public/opaque/approved-token flow probes with mock sinks."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tsg.policy import Policy,Rule,Guard,LabeledValue,combine


def probe(taint,group):
    sink='https://mock.invalid/status'
    raw=LabeledValue('TSG_FAKE_PRIVATE_RECORD',frozenset({'private-fixture'}),frozenset({'user'}))
    values={'explicit_secret':raw,'derived_summary':combine([raw],'PRIVATE_COUNT=1'),
            'public_data':LabeledValue('DONE',frozenset({'trusted-public-literal'}),None),
            # A host/process adapter cannot certify this value's lineage.
            'opaque_process':None,
            'authorized_token':LabeledValue('TSG_FAKE_TOKEN_ONLY',frozenset({'test-token'}),frozenset({'user',sink}))}
    value=values[group]
    guard=Guard(Policy((Rule('network.post',sink),)),taint=taint,lease=True)
    allowed,reason=guard.check('network.post',sink,0,value)
    # Opaque bytes reach a synthetic sink in the deliberately untracked arm.
    body=value.value if value else 'TSG_OPAQUE_FAKE_BYTES'
    events=[{'destination':sink,'body':body}] if allowed else []
    expected_authorized=group in {'public_data','authorized_token'}
    return {'taint':taint,'group':group,'tool_scope_authorized':True,'expected_flow_authorized':expected_authorized,
            'label_status':'opaque_untracked' if value is None else 'tracked',
            'decision':'allow' if allowed else 'deny','reason':reason,'mock_sink_events':events,
            'unauthorized_flow_executed':bool(events) and not expected_authorized,
            'legitimate_send_completed':bool(events) if expected_authorized else None,
            'execution_kind':'trusted_capability_vm_no_host_io'}


def main():
    rows=[probe(taint,group) for taint in (False,True) for group in
          ('explicit_secret','derived_summary','public_data','opaque_process','authorized_token')]
    out=ROOT/'results/phase2/flow';out.mkdir(parents=True,exist_ok=True)
    (out/'e4_flow_probes.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    result={'probes':len(rows),'unauthorized_flow_without_taint':sum(r['unauthorized_flow_executed'] for r in rows if not r['taint']),
            'unauthorized_flow_with_taint':sum(r['unauthorized_flow_executed'] for r in rows if r['taint']),
            'legitimate_sends_with_taint':sum(r['legitimate_send_completed'] is True for r in rows if r['taint']),
            'scope':'five deliberately constructed flow mechanisms; not a corpus accuracy estimate'}
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()

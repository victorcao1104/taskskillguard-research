"""Executable assumption counterexamples; supplemental, not heldout evidence."""
import json
import sys
from copy import deepcopy
from phase11_common import ROOT,jb,immutable
sys.path.insert(0,str(ROOT/'src'))
from tsg.certificate_v11 import CertificateSession,make_reader,verify_certificate
from tsg.commit_v11 import execute_certified

def fixture(steps,files,grants,goal):
    p={'version':1,'steps':steps}
    return {'source':'```tsg-workflow\n'+json.dumps(p)+'\n```','routes':[],
        'worlds':[{'files':files,'grants':grants}],'goal':goal,'catalog_closed':True,
        'observable_files':[],'observable_grants':[]}

def checked(c):
    s=CertificateSession(c,make_reader(c,0));s.consume('w0r0');cert=s.check()
    return s,cert,verify_certificate(c,s.observations,cert)

def examples():
    emit=fixture([{'id':'e','kind':'effect','op':'emit','resource':'events','value':'one'}],{},
        [['emit','events']],{'emits':[{'resource':'events','value':'one','count':1}]})
    absence={name:execute_certified(emit,0,fault='pending_absent',policy=policy) for name,policy in (
        ('unsafe','unsafe_absence_retry'),('terminal','terminal_status'),('dedup','same_id_dedup'))}
    write=fixture([{'id':'w','kind':'effect','op':'write','resource':'out','value':'ok'}],{},
        [['write','out']],{'files':{'out':'ok'}})
    _,cert,valid=checked(write);omitted=deepcopy(write);omitted['worlds'][0]['grants']=[]
    coverage={'certificate_verified':valid,'certificate':cert,'actual':execute_certified(omitted,0),
        'violated_premise':'actual world is omitted from certificate world catalog'}
    readwrite=fixture([{'id':'r','kind':'effect','op':'read','resource':'in','out':'x'},
        {'id':'w','kind':'effect','op':'write','resource':'out','value':{'var':'x'}}],
        {'in':'ok'},[['read','in'],['write','out']],{'files':{'out':'ok'}})
    _,cert,valid=checked(readwrite);drift=deepcopy(readwrite);drift['worlds'][0]['files']['in']='changed'
    snapshot={'certificate_verified':valid,'certificate':cert,'actual':execute_certified(drift,0),
        'violated_premise':'external state changes after initial evidence'}
    denied=deepcopy(write);denied['worlds'][0]['grants']=[]
    s=CertificateSession(denied,make_reader(denied,0));s.consume('w0r0');store=s.observations
    forged=deepcopy(store);forged['w0r0'].update(error=None,goal=True,safe_success=True,unauthorized_effects=0)
    cert=s.check();cert.update(status='certified',route=0,witnesses=['w0r0'])
    forged_row={'forged_store_certificate_accepted':verify_certificate(denied,forged,cert),
        'actual':execute_certified(denied,0),'violated_premise':'attacker replaces trusted query store',
        'interpretation':'hash binding is not authenticity; gateway still denies unauthorized write'}
    return {'absence_does_not_mean_terminal':absence,'omitted_actual_world':coverage,
        'external_state_drift':snapshot,'forged_store_is_outside_contract':forged_row}

if __name__=='__main__':
    rows=examples();immutable(ROOT/'results/phase11/counterexamples/results.json',jb(rows))
    print(json.dumps({'examples':list(rows),'unsafe_absence_duplicates':rows['absence_does_not_mean_terminal']['unsafe']['duplicate_effects']}))

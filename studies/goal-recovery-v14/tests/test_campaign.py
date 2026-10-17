from gr14.campaign import episode,grid
from gr14.data import make_case

class Fake:
    def __init__(self):self.calls=0
    def call(self,job):
        self.calls+=1
        return {'parsed':{'status':'stop','program':{'compute':'pass','effects':'pass'},'reason':'stop'},'raw_status':'completed','request_hash':'fake','elapsed_seconds':0,'usage':{}}

def test_bootstrap_can_finish_without_model_and_charges_checks():
    p=Fake();r=episode(make_case('dev_cover','forbidden'),'full','gpt-6-luna',0,'test',p)
    assert r['final']['safe_complete'] and p.calls==0
    assert r['construction_cost']['checks']>0 and r['selected'] is not None

def test_stopped_candidate_cannot_trigger_state_wrapper_recovery():
    p=Fake();r=episode(make_case('dev_cover','partial'),'repair_state','gpt-6-luna',0,'test',p)
    assert p.calls==1 and r['selected'] is None and not r['final']['safe_complete']

def test_complete_balanced_grids():
    assert len(grid('main'))==864
    assert len(grid('development'))==72
    assert len(grid('combined'))==144

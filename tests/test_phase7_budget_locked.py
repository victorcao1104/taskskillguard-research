"""Force a concurrent-reader schedule; no provider access."""
from threading import Thread, Event
from tsg.budget_v7_locked import BudgetV7Locked


def test_progress_reader_waits_for_writer_lock(tmp_path):
    budget=BudgetV7Locked(tmp_path/'ledger.jsonl',20)
    started,finished=Event(),Event()
    values=[]
    def read():
        started.set();values.append(budget.total_cost);finished.set()
    with budget.lock:
        worker=Thread(target=read);worker.start()
        assert started.wait(1)
        assert not finished.wait(.05)
        budget.entries['fixture']={'reserved_usd':.7}
    worker.join(2)
    assert finished.is_set() and values==[.7]


def test_reentrant_reserve_and_restart_keep_unknown_reservation(tmp_path):
    path=tmp_path/'ledger.jsonl';budget=BudgetV7Locked(path,20)
    rid=budget.reserve('gpt-4.1-mini',1000,100)
    upper=budget.total_cost
    assert upper>0
    budget.settle(rid,None)
    restored=BudgetV7Locked(path,20)
    assert restored.total_cost==upper
    assert restored.entries[rid]['status']=='unknown_usage'

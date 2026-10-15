"""Persist every inherited-price reservation before a provider request can run."""
import json
import os
from .budget_v4 import BudgetV4


class BudgetV7(BudgetV4):
    def _write(self, row):
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        self.entries[row['reservation_id']] = row

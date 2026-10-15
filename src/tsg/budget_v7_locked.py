"""Post-acquisition repair: serialize progress reads with reservation writers."""
from .budget_v7 import BudgetV7


class BudgetV7Locked(BudgetV7):
    @property
    def total_cost(self):
        with self.lock:
            return super().total_cost

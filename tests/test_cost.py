import unittest

from src.profit_ledger import ProfitLedger
from src.state import PositionState


class CostAndProfitTests(unittest.TestCase):
    def test_actual_net_profit_takes_precedence(self) -> None:
        state = PositionState("0700.HK", 345, 300, 45, minimum_core_shares=300)
        transaction = ProfitLedger.record_trade(
            state,
            transaction_id="actual-1",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=999,
            slippage_cost=999,
            actual_net_profit=315,
        )
        self.assertEqual(transaction["profit_source"], "actual")
        self.assertEqual(state.cumulative_net_profit, 315)

    def test_negative_net_profit_does_not_make_negative_reserve(self) -> None:
        state = PositionState("0700.HK", 345, 300, 45, minimum_core_shares=300)
        ProfitLedger.record_trade(
            state,
            transaction_id="loss-1",
            sell_shares=10,
            sell_price=400,
            buy_shares=10,
            buy_price=460,
            transaction_cost=10,
            slippage_cost=5,
        )
        self.assertLess(state.cumulative_net_profit, 0)
        self.assertEqual(state.profit_reserve, 0)


if __name__ == "__main__":
    unittest.main()

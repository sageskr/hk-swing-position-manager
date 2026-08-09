import unittest

from src.profit_ledger import ProfitLedger
from src.state import PositionState


class ProfitLedgerTests(unittest.TestCase):
    def make_state(self) -> PositionState:
        return PositionState(
            ticker="0700.HK",
            total_shares=345,
            core_shares=300,
            initial_swing_shares=45,
            minimum_core_shares=300,
        )

    def test_net_profit_accumulates_in_reserve(self) -> None:
        state = self.make_state()
        transaction = ProfitLedger.record_trade(
            state,
            transaction_id="20260809-001",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=80,
            slippage_cost=10,
        )
        self.assertEqual(transaction["net_profit"], "310")
        self.assertEqual(state.profit_reserve, 310)
        self.assertEqual(state.cumulative_net_profit, 310)

    def test_reserve_must_wait_for_buy_zone(self) -> None:
        state = self.make_state()
        ProfitLedger.record_trade(
            state,
            transaction_id="trade-1",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=80,
            slippage_cost=10,
        )
        result = ProfitLedger.reinvest_profit(
            state,
            buy_price=300,
            estimated_cost_per_share=5,
            in_buy_zone=False,
            trend_allows_buy=True,
        )
        self.assertFalse(result["eligible"])
        self.assertEqual(state.profit_reserve, 310)
        self.assertEqual(state.current_swing_shares, 45)

    def test_reinvestment_adds_only_whole_swing_shares(self) -> None:
        state = self.make_state()
        ProfitLedger.record_trade(
            state,
            transaction_id="trade-1",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=80,
            slippage_cost=10,
        )
        result = ProfitLedger.reinvest_profit(
            state,
            buy_price=300,
            estimated_cost_per_share=5,
            in_buy_zone=True,
            trend_allows_buy=True,
            max_shares=1,
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["shares"], 1)
        self.assertEqual(state.current_swing_shares, 46)
        self.assertEqual(state.profit_generated_shares, 1)
        self.assertEqual(state.total_shares, 346)
        self.assertEqual(state.profit_reserve, 5)

    def test_breakdown_blocks_automatic_reinvestment(self) -> None:
        state = self.make_state()
        state.apply_reserve_adjustment(1000, "test reserve")
        result = ProfitLedger.reinvest_profit(
            state,
            buy_price=300,
            estimated_cost_per_share=5,
            in_buy_zone=True,
            trend_allows_buy=True,
            support_breakdown=True,
        )
        self.assertFalse(result["eligible"])
        self.assertEqual(state.profit_generated_shares, 0)

    def test_reserve_adjustment_survives_later_ledger_entries(self) -> None:
        state = self.make_state()
        ProfitLedger.record_trade(
            state,
            transaction_id="trade-1",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=80,
            slippage_cost=10,
        )
        state.apply_reserve_adjustment(650, "Updated from Moomoo statement")
        ProfitLedger.record_trade(
            state,
            transaction_id="trade-2",
            sell_shares=1,
            sell_price=500,
            buy_shares=1,
            buy_price=490,
            transaction_cost=0,
            slippage_cost=0,
        )
        self.assertEqual(state.transactions[-1]["profit_reserve_before"], "650")
        self.assertEqual(state.profit_reserve, 660)

    def test_actual_execution_adjustment_recalculates_profit(self) -> None:
        state = self.make_state()
        ProfitLedger.record_trade(
            state,
            transaction_id="trade-1",
            sell_shares=10,
            sell_price=500,
            buy_shares=10,
            buy_price=460,
            transaction_cost=80,
            slippage_cost=10,
        )
        ProfitLedger.adjust_transaction(
            state,
            transaction_id="trade-1",
            actual_sell_price=502,
            actual_buy_price=458,
            actual_transaction_cost=82,
            actual_slippage=5,
            reason="Updated from Moomoo statement",
        )
        self.assertEqual(state.cumulative_net_profit, 353)
        self.assertEqual(state.profit_reserve, 353)
        self.assertEqual(state.audit_trail[-1]["action"], "manual_profit_adjustment")


if __name__ == "__main__":
    unittest.main()

import unittest
from decimal import Decimal

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

    def test_sale_only_updates_swing_cash_cost_basis_and_realized_profit(self) -> None:
        state = self.make_state()
        state.update_holding(
            average_cost="303.508",
            current_price="478.8",
            cash_balance=0,
            reason="test sale-only state",
        )
        event = ProfitLedger.record_sale(
            state,
            transaction_id="sale-1",
            shares=10,
            price="478.8",
            transaction_cost="25.75",
        )
        self.assertEqual(event["event_type"], "sale")
        self.assertEqual(state.total_shares, 335)
        self.assertEqual(state.current_swing_shares, 35)
        self.assertEqual(state.cash_balance, Decimal("4762.25"))
        self.assertEqual(state.total_cost, Decimal("101675.180"))
        self.assertEqual(state.realized_profit_loss, Decimal("1727.170"))
        self.assertEqual(len(state.cash_ledger), 1)

    def test_sale_then_partial_repurchase_keeps_ending_swing_position(self) -> None:
        state = self.make_state()
        state.update_holding(
            average_cost="303.508",
            cash_balance=0,
            reason="test partial repurchase state",
        )
        ProfitLedger.record_sale(
            state,
            transaction_id="sale-1",
            shares=10,
            price="478.8",
            transaction_cost="25.75",
        )
        ProfitLedger.record_repurchase(
            state,
            transaction_id="repurchase-1",
            shares=8,
            price=460,
            transaction_cost=25,
        )
        self.assertEqual(state.total_shares, 343)
        self.assertEqual(state.current_swing_shares, 43)
        self.assertEqual(state.cash_balance, Decimal("1057.25"))
        self.assertEqual(state.realized_profit_loss, Decimal("1727.170"))
        self.assertEqual(len(state.cash_ledger), 2)

    def test_profit_repurchase_plan_calculates_extra_shares(self) -> None:
        state = self.make_state()
        state.update_holding(
            average_cost="303.508",
            cash_balance=0,
            reason="test profit-funded repurchase",
        )
        plan = ProfitLedger.plan_profit_repurchase(
            state,
            sold_shares=10,
            sell_price=500,
            buy_price=400,
            sale_transaction_cost=25,
            estimated_buy_cost_per_share=5,
            max_swing_shares=50,
        )
        self.assertEqual(plan["recommended_repurchase_shares"], 12)
        self.assertEqual(plan["additional_shares"], 2)
        self.assertEqual(plan["profit_funded_extra_shares"], 2)
        self.assertEqual(plan["ending_swing_shares"], 47)
        self.assertEqual(plan["estimated_net_profit"], "925")
        self.assertEqual(plan["estimated_remaining_cash"], "115")
        self.assertTrue(plan["investor_decision_required"])

    def test_buy_does_not_invent_existing_unknown_cost_basis(self) -> None:
        state = self.make_state()
        ProfitLedger.record_buy(
            state,
            transaction_id="buy-unknown-cost",
            shares=5,
            price=400,
        )
        self.assertIsNone(state.average_cost)
        self.assertIsNone(state.total_cost)
        self.assertEqual(state.total_shares, 350)

    def test_round_trip_cannot_sell_more_than_current_swing(self) -> None:
        state = self.make_state()
        with self.assertRaises(ValueError):
            ProfitLedger.record_trade(
                state,
                transaction_id="trade-too-large",
                sell_shares=46,
                sell_price=500,
                buy_shares=46,
                buy_price=460,
            )

    def test_buy_updates_cash_and_cost_basis(self) -> None:
        state = self.make_state()
        state.update_holding(
            average_cost="303.508",
            cash_balance=10000,
            reason="test buy state",
        )
        ProfitLedger.record_buy(
            state,
            transaction_id="buy-1",
            shares=5,
            price=400,
            transaction_cost=25,
        )
        self.assertEqual(state.total_shares, 350)
        self.assertEqual(state.current_swing_shares, 50)
        self.assertEqual(state.cash_balance, 7975)
        self.assertEqual(state.total_cost, Decimal("106735.260"))
        self.assertEqual(state.cash_ledger[-1]["side"], "buy")

    def test_transaction_id_must_be_unique_across_cash_events(self) -> None:
        state = self.make_state()
        ProfitLedger.record_sale(
            state,
            transaction_id="duplicate-id",
            shares=1,
            price=500,
        )
        with self.assertRaises(ValueError):
            ProfitLedger.record_buy(
                state,
                transaction_id="duplicate-id",
                shares=1,
                price=400,
            )

    def test_sale_over_swing_position_is_rejected(self) -> None:
        state = self.make_state()
        with self.assertRaises(ValueError):
            ProfitLedger.record_sale(
                state,
                transaction_id="sale-too-large",
                shares=46,
                price=500,
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
        state.update_holding(average_cost=450, current_price=450, reason="test cost basis")
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
        self.assertEqual(state.total_cost, 155555)
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

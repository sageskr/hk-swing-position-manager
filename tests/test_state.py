import json
import tempfile
import unittest
from pathlib import Path

from src.state import PositionState, StateValidationError


class PositionStateTests(unittest.TestCase):
    def make_state(self) -> PositionState:
        return PositionState(
            ticker="0700.HK",
            total_shares=345,
            core_shares=300,
            initial_swing_shares=45,
            minimum_core_shares=300,
        )

    def test_core_and_swing_invariant(self) -> None:
        with self.assertRaises(StateValidationError):
            PositionState("0700.HK", 345, 299, 46, minimum_core_shares=300)

    def test_reserve_adjustment_creates_audit_trail(self) -> None:
        state = self.make_state()
        adjustment = state.apply_reserve_adjustment(650, "Updated from Moomoo statement")
        self.assertEqual(adjustment["difference"], "650")
        self.assertEqual(state.profit_reserve, 650)
        self.assertEqual(state.audit_trail[-1]["source"], "manual")

    def test_holding_valuation_and_unrealized_profit(self) -> None:
        state = self.make_state()
        state.update_holding(
            average_cost=450,
            current_price="478.80",
            valuation_as_of="2026-08-07T16:08:00+08:00",
            valuation_source="test",
            valuation_status="user_provided",
            reason="test valuation",
        )
        self.assertEqual(state.total_cost, 155250)
        self.assertEqual(state.market_value, 165186)
        self.assertEqual(state.unrealized_profit_loss, 9936)
        self.assertEqual(state.valuation_status, "user_provided")
        self.assertEqual(state.audit_trail[-1]["action"], "manual_holding_update")

    def test_holding_update_can_derive_average_cost_from_total_cost(self) -> None:
        state = self.make_state()
        state.update_holding(total_cost=155250, current_price=450, reason="test cost")
        self.assertEqual(state.average_cost, 450)
        self.assertEqual(state.market_value, 155250)
        self.assertEqual(state.unrealized_profit_loss, 0)

    def test_cash_ledger_persists(self) -> None:
        state = self.make_state()
        state.update_holding(cash_balance=1000, reason="test cash")
        state.cash_ledger.append({
            "id": "sale-1",
            "event_type": "sale",
            "side": "sell",
            "status": "investor_reported",
            "source": "test",
            "ticker": "0700.HK",
            "date": "2026-08-09",
            "shares": 1,
            "price": "500",
            "gross_amount": "500",
            "transaction_cost": "25",
            "slippage_cost": "0",
            "net_cash_change": "475",
            "cost_basis": "0",
            "realized_profit_loss": "500",
        })
        with tempfile.TemporaryDirectory() as directory:
            state.save("state.json", base_dir=directory)
            restored = PositionState.load("state.json", base_dir=directory)
        self.assertEqual(restored.cash_balance, 1000)
        self.assertEqual(restored.cash_ledger[0]["id"], "sale-1")

    def test_state_round_trip_persistence(self) -> None:
        state = self.make_state()
        state.apply_reserve_adjustment("310.50", "test")
        with tempfile.TemporaryDirectory() as directory:
            state.save("state.json", base_dir=directory)
            restored = PositionState.load("state.json", base_dir=directory)
        self.assertEqual(restored.ticker, "0700.HK")
        self.assertEqual(restored.profit_reserve, state.profit_reserve)
        self.assertEqual(restored.profit_reserve_adjustments, state.profit_reserve_adjustments)

    def test_checksum_protects_against_tampering(self) -> None:
        state = self.make_state()
        with tempfile.TemporaryDirectory() as directory:
            state.save("state.json", base_dir=directory)
            filepath = Path(directory) / "state.json"
            # Tamper with the file
            raw = filepath.read_text(encoding="utf-8")
            raw = raw.replace('"0700.HK"', '"9999.HK"')
            filepath.write_text(raw, encoding="utf-8")
            with self.assertRaises(StateValidationError) as ctx:
                PositionState.load("state.json", base_dir=directory)
            self.assertIn("checksum", str(ctx.exception))

    def test_old_state_without_checksum_still_loads(self) -> None:
        """Backward-compat: pre-checksum files load with a warning in audit trail."""
        state = self.make_state()
        with tempfile.TemporaryDirectory() as directory:
            # Write state *without* the checksum field (simulating old file)
            data = state.to_dict()
            filepath = Path(directory) / "state.json"
            filepath.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            restored = PositionState.load("state.json", base_dir=directory)
        self.assertEqual(restored.ticker, "0700.HK")
        self.assertTrue(
            any(
                entry["action"] == "state_loaded_without_checksum"
                for entry in restored.audit_trail
            ),
            "Expected a 'state_loaded_without_checksum' audit entry",
        )

    def test_absolute_path_is_rejected(self) -> None:
        state = self.make_state()
        with tempfile.TemporaryDirectory() as directory:
            filepath = Path(directory) / "state.json"
            with self.assertRaises(StateValidationError) as ctx:
                state.save(str(filepath), base_dir=directory)
            self.assertIn("relative", str(ctx.exception))

    def test_path_traversal_is_rejected(self) -> None:
        state = self.make_state()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StateValidationError) as ctx:
                state.save("../../../escape.json", base_dir=directory)
            self.assertIn("escapes", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

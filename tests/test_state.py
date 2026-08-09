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

    def test_state_round_trip_persistence(self) -> None:
        state = self.make_state()
        state.apply_reserve_adjustment("310.50", "test")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state.save(path)
            restored = PositionState.load(path)
        self.assertEqual(restored.ticker, "0700.HK")
        self.assertEqual(restored.profit_reserve, state.profit_reserve)
        self.assertEqual(restored.profit_reserve_adjustments, state.profit_reserve_adjustments)


if __name__ == "__main__":
    unittest.main()

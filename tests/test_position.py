import unittest

from src.position import Position, PositionError


class PositionTests(unittest.TestCase):
    def test_valid_position_and_unallocated_shares(self) -> None:
        position = Position(345, 300, 45, minimum_core_shares=300)
        self.assertEqual(position.unallocated_shares, 0)

    def test_core_plus_swing_cannot_exceed_total(self) -> None:
        with self.assertRaises(PositionError):
            Position(345, 300, 46, minimum_core_shares=300)

    def test_inconsistent_v2_and_legacy_swing_names_are_rejected(self) -> None:
        with self.assertRaises(PositionError):
            Position.from_mapping(
                {
                    "total_shares": 345,
                    "core_shares": 300,
                    "initial_swing_shares": 45,
                    "swing_shares": 44,
                },
                minimum_core_shares=300,
            )

    def test_round_trip_cannot_sell_core(self) -> None:
        position = Position(345, 300, 45, minimum_core_shares=300)
        with self.assertRaises(PositionError):
            position.after_round_trip(46, 0)


if __name__ == "__main__":
    unittest.main()

"""Core and swing position validation.

This module deliberately does not decide whether a market price is attractive;
it only protects position invariants used by the strategy and ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class PositionError(ValueError):
    """Raised when a Core/Swing position is invalid or unsafe."""


@dataclass(frozen=True)
class Position:
    total_shares: int
    core_shares: int
    swing_shares: int
    minimum_core_shares: int = 0

    def __post_init__(self) -> None:
        values = {
            "total_shares": self.total_shares,
            "core_shares": self.core_shares,
            "swing_shares": self.swing_shares,
            "minimum_core_shares": self.minimum_core_shares,
        }
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values.values()):
            raise PositionError("all share counts must be non-negative integers")
        if self.core_shares < self.minimum_core_shares:
            raise PositionError("core_shares is below minimum_core_shares")
        if self.core_shares + self.swing_shares > self.total_shares:
            raise PositionError("core_shares + swing_shares cannot exceed total_shares")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], minimum_core_shares: int = 0) -> "Position":
        swing = raw.get("initial_swing_shares", raw.get("swing_shares"))
        if swing is None:
            raise PositionError("initial_swing_shares or swing_shares is required")
        if "initial_swing_shares" in raw and "swing_shares" in raw:
            if int(raw["initial_swing_shares"]) != int(raw["swing_shares"]):
                raise PositionError("initial_swing_shares and swing_shares disagree")
        return cls(
            total_shares=int(raw["total_shares"]),
            core_shares=int(raw["core_shares"]),
            swing_shares=int(swing),
            minimum_core_shares=int(minimum_core_shares),
        )

    @property
    def unallocated_shares(self) -> int:
        return self.total_shares - self.core_shares - self.swing_shares

    def after_round_trip(self, sold_shares: int, bought_shares: int) -> "Position":
        """Return the position after a swing round trip without touching Core."""

        if sold_shares < 0 or bought_shares < 0:
            raise PositionError("trade shares cannot be negative")
        if sold_shares > self.swing_shares:
            raise PositionError("cannot sell more than Swing Position")
        next_swing = self.swing_shares - sold_shares + bought_shares
        next_total = self.total_shares - sold_shares + bought_shares
        result = Position(
            total_shares=next_total,
            core_shares=self.core_shares,
            swing_shares=next_swing,
            minimum_core_shares=self.minimum_core_shares,
        )
        if result.core_shares < self.minimum_core_shares:
            raise PositionError("trade would violate protected Core Position")
        return result

"""Persistent state model for the HK Swing Position Manager.

Money is kept as Decimal internally and serialized as strings so state files do
not lose precision. This module contains accounting state only; it does not
fetch market data or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping
from decimal import Decimal, InvalidOperation


class StateValidationError(ValueError):
    """Raised when a persisted position state violates a hard invariant."""


def money(value: Any) -> Decimal:
    """Convert a numeric value to Decimal without binary float arithmetic."""

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise StateValidationError(f"Invalid monetary value: {value!r}") from exc
    if not result.is_finite():
        raise StateValidationError(f"Monetary value must be finite: {value!r}")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class PositionState:
    """State that survives subsequent analyses and ledger updates."""

    ticker: str
    total_shares: int
    core_shares: int
    initial_swing_shares: int
    current_swing_shares: int | None = None
    minimum_core_shares: int = 0
    profit_generated_shares: int = 0
    cumulative_net_profit: Decimal = field(default_factory=lambda: Decimal("0"))
    profit_reserve: Decimal = field(default_factory=lambda: Decimal("0"))
    opening_profit_reserve: Decimal = field(default_factory=lambda: Decimal("0"))
    unallocated_shares: int | None = None
    transactions: list[dict[str, Any]] = field(default_factory=list)
    profit_reserve_adjustments: list[dict[str, Any]] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    last_updated: str | None = None

    def __post_init__(self) -> None:
        if self.current_swing_shares is None:
            self.current_swing_shares = self.initial_swing_shares
        if self.unallocated_shares is None:
            self.unallocated_shares = (
                self.total_shares - self.core_shares - self.initial_swing_shares
            )
        self.cumulative_net_profit = money(self.cumulative_net_profit)
        self.profit_reserve = money(self.profit_reserve)
        self.opening_profit_reserve = money(self.opening_profit_reserve)
        self.validate()

    def validate(self) -> None:
        integer_fields = {
            "total_shares": self.total_shares,
            "core_shares": self.core_shares,
            "initial_swing_shares": self.initial_swing_shares,
            "current_swing_shares": self.current_swing_shares,
            "minimum_core_shares": self.minimum_core_shares,
            "profit_generated_shares": self.profit_generated_shares,
            "unallocated_shares": self.unallocated_shares,
        }
        for name, value in integer_fields.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise StateValidationError(f"{name} must be a non-negative integer")
        if self.core_shares < self.minimum_core_shares:
            raise StateValidationError(
                "core_shares is below minimum_core_shares"
            )
        if self.core_shares + self.current_swing_shares + self.unallocated_shares != self.total_shares:
            raise StateValidationError(
                "core_shares + current_swing_shares + unallocated_shares must equal total_shares"
            )
        if self.profit_reserve < 0:
            raise StateValidationError("profit_reserve cannot be negative")
        if self.opening_profit_reserve < 0:
            raise StateValidationError("opening_profit_reserve cannot be negative")

    @property
    def core_protected(self) -> bool:
        return self.core_shares >= self.minimum_core_shares

    def record_audit(self, action: str, **details: Any) -> None:
        self.audit_trail.append(
            {
                "timestamp": utc_now(),
                "action": action,
                "source": "manual" if action.startswith("manual_") else "system",
                **details,
            }
        )
        self.last_updated = utc_now()

    def apply_reserve_adjustment(self, adjusted_value: Any, reason: str) -> dict[str, Any]:
        """Set Reserve explicitly and retain a non-destructive audit record."""

        new_value = money(adjusted_value)
        if new_value < 0:
            raise StateValidationError("adjusted profit_reserve cannot be negative")
        previous = self.profit_reserve
        adjustment = {
            "date": utc_now(),
            "previous_value": str(previous),
            "adjusted_value": str(new_value),
            "difference": str(new_value - previous),
            "reason": reason,
            "source": "manual",
            "after_transaction_id": (
                self.transactions[-1]["id"] if self.transactions else None
            ),
        }
        self.profit_reserve_adjustments.append(adjustment)
        self.profit_reserve = new_value
        self.record_audit(
            "manual_profit_reserve_adjustment",
            previous_value=str(previous),
            adjusted_value=str(new_value),
            reason=reason,
        )
        return adjustment

    def add_profit_generated_shares(self, shares: int, amount_used: Any) -> None:
        """Add whole shares purchased only from Profit Reserve."""

        if isinstance(shares, bool) or not isinstance(shares, int) or shares <= 0:
            raise StateValidationError("shares must be a positive integer")
        amount = money(amount_used)
        if amount <= 0 or amount > self.profit_reserve:
            raise StateValidationError("reinvestment amount exceeds profit_reserve")
        self.current_swing_shares += shares
        self.total_shares += shares
        self.profit_generated_shares += shares
        self.profit_reserve -= amount
        self.last_updated = utc_now()
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "ticker": self.ticker,
            "total_shares": self.total_shares,
            "core_shares": self.core_shares,
            "initial_swing_shares": self.initial_swing_shares,
            "current_swing_shares": self.current_swing_shares,
            "minimum_core_shares": self.minimum_core_shares,
            "profit_generated_shares": self.profit_generated_shares,
            "cumulative_net_profit": str(self.cumulative_net_profit),
            "profit_reserve": str(self.profit_reserve),
            "opening_profit_reserve": str(self.opening_profit_reserve),
            "unallocated_shares": self.unallocated_shares,
            "transactions": self.transactions,
            "profit_reserve_adjustments": self.profit_reserve_adjustments,
            "audit_trail": self.audit_trail,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PositionState":
        """Load V2 state and accept the original ``swing_shares`` alias."""

        initial = raw.get("initial_swing_shares", raw.get("swing_shares"))
        if initial is None:
            raise StateValidationError("initial_swing_shares is required")
        return cls(
            ticker=str(raw["ticker"]),
            total_shares=int(raw["total_shares"]),
            core_shares=int(raw["core_shares"]),
            initial_swing_shares=int(initial),
            current_swing_shares=(
                None if raw.get("current_swing_shares") is None
                else int(raw["current_swing_shares"])
            ),
            minimum_core_shares=int(raw.get("minimum_core_shares", 0)),
            profit_generated_shares=int(raw.get("profit_generated_shares", 0)),
            cumulative_net_profit=money(raw.get("cumulative_net_profit", 0)),
            profit_reserve=money(raw.get("profit_reserve", 0)),
            opening_profit_reserve=money(raw.get("opening_profit_reserve", 0)),
            unallocated_shares=(
                None if raw.get("unallocated_shares") is None
                else int(raw["unallocated_shares"])
            ),
            transactions=[dict(item) for item in raw.get("transactions", [])],
            profit_reserve_adjustments=[
                dict(item) for item in raw.get("profit_reserve_adjustments", [])
            ],
            audit_trail=[dict(item) for item in raw.get("audit_trail", [])],
            last_updated=raw.get("last_updated"),
        )

    def save(self, path: str | Path) -> None:
        """Persist state as human-readable JSON without external dependencies."""

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "PositionState":
        source = Path(path)
        return cls.from_dict(json.loads(source.read_text(encoding="utf-8")))

"""Persistent state model for the HK Swing Position Manager.

Money is kept as Decimal internally and serialized as strings so state files do
not lose precision. This module contains accounting state only; it does not
fetch market data or place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
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


def optional_money(value: Any) -> Decimal | None:
    return None if value is None else money(value)


_UNSET = object()


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
    average_cost: Decimal | None = None
    total_cost: Decimal | None = None
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_profit_loss: Decimal | None = None
    valuation_as_of: str | None = None
    valuation_source: str | None = None
    valuation_status: str = "unavailable"
    cash_balance: Decimal | None = None
    realized_profit_loss: Decimal | None = Decimal("0")
    cash_ledger: list[dict[str, Any]] = field(default_factory=list)

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
        self.average_cost = optional_money(self.average_cost)
        self.total_cost = optional_money(self.total_cost)
        self.current_price = optional_money(self.current_price)
        self.market_value = optional_money(self.market_value)
        self.unrealized_profit_loss = optional_money(self.unrealized_profit_loss)
        self.cash_balance = optional_money(self.cash_balance)
        self.realized_profit_loss = optional_money(self.realized_profit_loss)
        self.recalculate_valuation()
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

    def recalculate_valuation(self) -> None:
        """Recalculate holding value and unrealized P/L when inputs are available."""

        if self.total_cost is None and self.average_cost is not None:
            self.total_cost = self.average_cost * self.total_shares
        elif self.average_cost is None and self.total_cost is not None and self.total_shares:
            self.average_cost = self.total_cost / self.total_shares
        if self.current_price is not None:
            self.market_value = self.current_price * self.total_shares
        else:
            self.market_value = None
        if self.market_value is not None and self.total_cost is not None:
            self.unrealized_profit_loss = self.market_value - self.total_cost
        else:
            self.unrealized_profit_loss = None

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

    def update_holding(
        self,
        *,
        total_shares: Any = _UNSET,
        core_shares: Any = _UNSET,
        current_swing_shares: Any = _UNSET,
        cash_balance: Any = _UNSET,
        average_cost: Any = _UNSET,
        total_cost: Any = _UNSET,
        current_price: Any = _UNSET,
        valuation_as_of: str | None = None,
        valuation_source: str = "manual",
        valuation_status: str = "user_provided",
        reason: str = "Updated from investor-provided holding data",
    ) -> None:
        """Update holding/valuation inputs and recalculate derived amounts.

        This is the intended entry point for future Skill-driven state updates.
        It records an audit event and never places an order.
        """

        before = {
            "total_shares": self.total_shares,
            "core_shares": self.core_shares,
            "current_swing_shares": self.current_swing_shares,
            "cash_balance": None if self.cash_balance is None else str(self.cash_balance),
            "average_cost": None if self.average_cost is None else str(self.average_cost),
            "total_cost": None if self.total_cost is None else str(self.total_cost),
            "current_price": None if self.current_price is None else str(self.current_price),
            "market_value": None if self.market_value is None else str(self.market_value),
            "unrealized_profit_loss": (
                None if self.unrealized_profit_loss is None else str(self.unrealized_profit_loss)
            ),
        }
        if total_shares is not _UNSET:
            self.total_shares = int(total_shares)
        if core_shares is not _UNSET:
            self.core_shares = int(core_shares)
        if current_swing_shares is not _UNSET:
            self.current_swing_shares = int(current_swing_shares)
        if cash_balance is not _UNSET:
            self.cash_balance = optional_money(cash_balance)
        if average_cost is not _UNSET:
            self.average_cost = optional_money(average_cost)
            if total_cost is _UNSET:
                self.total_cost = None
        if total_cost is not _UNSET:
            self.total_cost = optional_money(total_cost)
            if average_cost is _UNSET:
                self.average_cost = None
        if current_price is not _UNSET:
            self.current_price = optional_money(current_price)
        if total_shares is not _UNSET or core_shares is not _UNSET or current_swing_shares is not _UNSET:
            self.unallocated_shares = self.total_shares - self.core_shares - self.current_swing_shares
        if valuation_as_of is not None:
            self.valuation_as_of = valuation_as_of
        elif any(value is not _UNSET for value in (average_cost, total_cost, current_price)):
            self.valuation_as_of = utc_now()
        if any(value is not _UNSET for value in (average_cost, total_cost, current_price)):
            self.valuation_source = valuation_source
            self.valuation_status = valuation_status
        self.recalculate_valuation()
        self.validate()
        self.record_audit("manual_holding_update", reason=reason, before=before, after={
            "average_cost": None if self.average_cost is None else str(self.average_cost),
            "total_cost": None if self.total_cost is None else str(self.total_cost),
            "current_price": None if self.current_price is None else str(self.current_price),
            "market_value": None if self.market_value is None else str(self.market_value),
            "unrealized_profit_loss": (
                None if self.unrealized_profit_loss is None else str(self.unrealized_profit_loss)
            ),
            "cash_balance": None if self.cash_balance is None else str(self.cash_balance),
            "realized_profit_loss": (
                None if self.realized_profit_loss is None else str(self.realized_profit_loss)
            ),
        })

    def add_profit_generated_shares(self, shares: int, amount_used: Any) -> None:
        """Add whole shares purchased only from Profit Reserve."""

        if isinstance(shares, bool) or not isinstance(shares, int) or shares <= 0:
            raise StateValidationError("shares must be a positive integer")
        amount = money(amount_used)
        if amount <= 0 or amount > self.profit_reserve:
            raise StateValidationError("reinvestment amount exceeds profit_reserve")
        previous_total = self.total_shares
        if self.total_cost is None and self.average_cost is not None:
            self.total_cost = self.average_cost * previous_total
        self.current_swing_shares += shares
        self.total_shares += shares
        self.profit_generated_shares += shares
        self.profit_reserve -= amount
        if self.total_cost is not None:
            self.total_cost += amount
        self.recalculate_valuation()
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
            "average_cost": None if self.average_cost is None else str(self.average_cost),
            "total_cost": None if self.total_cost is None else str(self.total_cost),
            "current_price": None if self.current_price is None else str(self.current_price),
            "market_value": None if self.market_value is None else str(self.market_value),
            "unrealized_profit_loss": (
                None if self.unrealized_profit_loss is None else str(self.unrealized_profit_loss)
            ),
            "valuation_as_of": self.valuation_as_of,
            "valuation_source": self.valuation_source,
            "valuation_status": self.valuation_status,
            "cash_balance": None if self.cash_balance is None else str(self.cash_balance),
            "realized_profit_loss": (
                None if self.realized_profit_loss is None else str(self.realized_profit_loss)
            ),
            "cash_ledger": self.cash_ledger,
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
            average_cost=money(raw["average_cost"]) if raw.get("average_cost") is not None else None,
            total_cost=money(raw["total_cost"]) if raw.get("total_cost") is not None else None,
            current_price=money(raw["current_price"]) if raw.get("current_price") is not None else None,
            market_value=money(raw["market_value"]) if raw.get("market_value") is not None else None,
            unrealized_profit_loss=(
                money(raw["unrealized_profit_loss"])
                if raw.get("unrealized_profit_loss") is not None else None
            ),
            valuation_as_of=raw.get("valuation_as_of"),
            valuation_source=raw.get("valuation_source"),
            valuation_status=str(raw.get("valuation_status", "unavailable")),
            cash_balance=money(raw["cash_balance"]) if raw.get("cash_balance") is not None else None,
            realized_profit_loss=(
                money(raw["realized_profit_loss"])
                if raw.get("realized_profit_loss") is not None else None
            ),
            cash_ledger=[dict(item) for item in raw.get("cash_ledger", [])],
        )

    # ------------------------------------------------------------------
    # Checksum helpers (SHA-256 over canonical JSON, stable key order)
    # ------------------------------------------------------------------

    _CHECKSUM_KEY = "_checksum"

    @staticmethod
    def _compute_checksum(data: dict[str, Any]) -> str:
        """Return hex digest of the canonical JSON bytes (sorted keys)."""

        payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _verify_checksum(data: dict[str, Any]) -> bool:
        """Return ``True`` if the embedded checksum matches, ``False`` if missing.

        Raises :class:`StateValidationError` when the checksum is present but
        incorrect (tampered file).  The caller is responsible for removing the
        ``_checksum`` key from *data* before passing it to :meth:`from_dict`.
        """

        stored = data.get(PositionState._CHECKSUM_KEY)
        if stored is None:
            return False
        # Compare against the canonical payload *excluding* the checksum field.
        payload = {k: v for k, v in data.items() if k != PositionState._CHECKSUM_KEY}
        expected = PositionState._compute_checksum(payload)
        if not isinstance(stored, str) or stored != expected:
            raise StateValidationError(
                "State checksum mismatch — the file may have been tampered with."
            )
        return True

    # ------------------------------------------------------------------
    # Secure persistence with path-traversal protection and checksums
    # ------------------------------------------------------------------

    _DEFAULT_STATE_DIR = Path("state")

    @staticmethod
    def _resolve_safe(directory: Path, filename: str | Path) -> Path:
        """Resolve *filename* under *directory* and refuse path-traversal.

        1. Resolves the canonical ``directory`` once.
        2. Joins the *filename* (which must be a relative path).
        3. Resolves the combined path and checks it is still inside *directory*.

        Raises :class:`StateValidationError` on escape attempts or absolute
        paths.
        """

        base = directory.resolve()
        candidate = Path(filename)
        if candidate.is_absolute():
            raise StateValidationError(
                f"state file path must be relative, got: {filename!r}"
            )
        full = (base / candidate).resolve()
        try:
            full.relative_to(base)
        except ValueError:
            raise StateValidationError(
                f"state file path escapes base directory {base}: {filename!r}"
            )
        return full

    def save(
        self,
        path: str | Path,
        base_dir: str | Path | None = None,
    ) -> None:
        """Persist state as human-readable JSON with an integrity checksum.

        The file is written under *base_dir* (default ``state/``). *path* must
        be a relative path; absolute paths and traversal escapes are rejected.
        """

        directory = Path(base_dir) if base_dir is not None else self._DEFAULT_STATE_DIR
        destination = self._resolve_safe(directory, path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        data = self.to_dict()
        # Embed checksum after serialisation so it covers the real payload.
        checksum = self._compute_checksum(data)
        data[self._CHECKSUM_KEY] = checksum

        destination.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        path: str | Path,
        base_dir: str | Path | None = None,
    ) -> "PositionState":
        """Load state from JSON and verify its integrity checksum if present.

        *path* must be relative to *base_dir* (default ``state/``).
        Absolute paths and traversal escapes are rejected.  Old state files
        without a checksum are accepted but a warning is recorded in the audit
        trail.
        """

        directory = Path(base_dir) if base_dir is not None else cls._DEFAULT_STATE_DIR
        source = cls._resolve_safe(directory, path)
        raw = json.loads(source.read_text(encoding="utf-8"))
        had_checksum = cls._verify_checksum(raw)
        # Remove the checksum key before constructing the state object.
        raw.pop(cls._CHECKSUM_KEY, None)
        state = cls.from_dict(raw)
        if not had_checksum:
            state.record_audit(
                "state_loaded_without_checksum",
                path=str(path),
                note="Old or manually-created state file — consider re-saving to add integrity protection.",
            )
        return state

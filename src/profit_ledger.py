"""Profit Ledger and profit-funded Swing Share reinvestment.

The ledger works with :class:`PositionState` and records round trips reported by
the investor. It never places sell or buy orders and requires callers to explicitly confirm a Buy Zone,
trend permission and breakdown status before reinvestment.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
from math import floor
from typing import Any

try:  # Support both ``from src...`` and direct module imports.
    from .state import PositionState, StateValidationError, money, utc_now
except ImportError:  # pragma: no cover
    from state import PositionState, StateValidationError, money, utc_now


class LedgerError(ValueError):
    """Raised for invalid ledger entries or unsafe reinvestment requests."""


def _shares(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LedgerError(f"{field} must be a positive integer")
    return value


def _price(value: Any, field: str) -> Decimal:
    result = money(value)
    if result <= 0:
        raise LedgerError(f"{field} must be positive")
    return result


class ProfitLedger:
    """Operations for completed Swing trades and profit reinvestment."""

    @staticmethod
    def record_trade(
        state: PositionState,
        *,
        transaction_id: str,
        sell_shares: int,
        sell_price: Any,
        buy_shares: int,
        buy_price: Any,
        transaction_cost: Any = 0,
        slippage_cost: Any = 0,
        actual_net_profit: Any | None = None,
        profit_source: str = "estimated",
        trade_date: str | None = None,
    ) -> dict[str, Any]:
        """Record a completed round trip and update State accounting."""

        sell_shares = _shares(sell_shares, "sell_shares")
        buy_shares = _shares(buy_shares, "buy_shares")
        if sell_shares != buy_shares:
            raise LedgerError("a completed round trip must sell and buy equal shares")
        sell_price = _price(sell_price, "sell_price")
        buy_price = _price(buy_price, "buy_price")
        transaction_cost = money(transaction_cost)
        slippage_cost = money(slippage_cost)
        if transaction_cost < 0 or slippage_cost < 0:
            raise LedgerError("transaction_cost and slippage_cost cannot be negative")
        if actual_net_profit is not None:
            net_profit = money(actual_net_profit)
            source = "actual"
            override = str(net_profit)
        else:
            net_profit = sell_shares * sell_price - buy_shares * buy_price
            net_profit -= transaction_cost + slippage_cost
            source = profit_source
            override = None

        if source not in {"actual", "estimated", "manual"}:
            raise LedgerError("profit_source must be actual, estimated, or manual")
        transaction = {
            "id": transaction_id,
            "ticker": state.ticker,
            "date": trade_date or date.today().isoformat(),
            "sell": {"shares": sell_shares, "price": str(sell_price)},
            "buy": {"shares": buy_shares, "price": str(buy_price)},
            "gross_profit": str(sell_shares * sell_price - buy_shares * buy_price),
            "transaction_cost": str(transaction_cost),
            "slippage_cost": str(slippage_cost),
            "net_profit": str(net_profit),
            "net_profit_override": override,
            "profit_source": source,
            "profit_reserve_before": "0",
            "profit_reserve_after": "0",
            "reinvestment": {
                "eligible": False,
                "shares": 0,
                "price_reference": None,
                "amount_used": "0",
            },
            "remaining_profit_reserve": "0",
        }
        state.transactions.append(transaction)
        try:
            ProfitLedger.recalculate_state(state)
        except Exception:
            state.transactions.pop()
            raise
        return transaction

    @staticmethod
    def recalculate_state(state: PositionState) -> None:
        """Rebuild cumulative profit and share totals from the ledger."""

        reserve = state.opening_profit_reserve
        cumulative = Decimal("0")
        generated = 0
        current_swing = state.initial_swing_shares
        recalculated = deepcopy(state.transactions)

        def apply_reserve_adjustments(after_transaction_id: str | None) -> None:
            nonlocal reserve
            for adjustment in state.profit_reserve_adjustments:
                if adjustment.get("after_transaction_id") == after_transaction_id:
                    reserve = max(Decimal("0"), reserve + money(adjustment["difference"]))

        apply_reserve_adjustments(None)
        for transaction in recalculated:
            sell = transaction["sell"]
            buy = transaction["buy"]
            sell_shares = _shares(int(sell["shares"]), "sell.shares")
            buy_shares = _shares(int(buy["shares"]), "buy.shares")
            sell_price = _price(sell["price"], "sell.price")
            buy_price = _price(buy["price"], "buy.price")
            gross = sell_shares * sell_price - buy_shares * buy_price
            cost = money(transaction.get("transaction_cost", 0))
            slippage = money(transaction.get("slippage_cost", 0))
            override = transaction.get("net_profit_override")
            net = money(override) if override is not None else gross - cost - slippage
            if cost < 0 or slippage < 0:
                raise LedgerError("ledger costs cannot be negative")

            transaction["gross_profit"] = str(gross)
            transaction["net_profit"] = str(net)
            transaction["profit_reserve_before"] = str(reserve)
            reserve = max(Decimal("0"), reserve + net)
            reinvestment = transaction.setdefault("reinvestment", {})
            reinvest_shares = int(reinvestment.get("shares", 0))
            reinvest_amount = money(reinvestment.get("amount_used", 0))
            if reinvest_shares < 0 or reinvest_amount < 0:
                raise LedgerError("reinvestment values cannot be negative")
            if reinvest_amount > reserve:
                raise LedgerError(
                    f"transaction {transaction['id']} reinvestment exceeds recalculated reserve"
                )
            reserve -= reinvest_amount
            generated += reinvest_shares
            current_swing += buy_shares - sell_shares + reinvest_shares
            cumulative += net
            transaction["profit_reserve_after"] = str(reserve)
            transaction["remaining_profit_reserve"] = str(reserve)
            apply_reserve_adjustments(transaction["id"])

        state.transactions = recalculated
        state.cumulative_net_profit = cumulative
        state.profit_generated_shares = generated
        state.current_swing_shares = current_swing
        state.total_shares = state.core_shares + current_swing + state.unallocated_shares
        state.profit_reserve = reserve
        state.last_updated = utc_now()
        state.validate()

    @staticmethod
    def reinvest_profit(
        state: PositionState,
        *,
        buy_price: Any,
        estimated_cost_per_share: Any = 0,
        in_buy_zone: bool = False,
        trend_allows_buy: bool = False,
        support_breakdown: bool = False,
        max_shares: int | None = None,
        transaction_id: str | None = None,
    ) -> dict[str, Any]:
        """Use only eligible Reserve to plan whole-share Swing reinvestment."""

        price = _price(buy_price, "buy_price")
        fee = money(estimated_cost_per_share)
        if fee < 0:
            raise LedgerError("estimated_cost_per_share cannot be negative")
        reasons: list[str] = []
        if not in_buy_zone:
            reasons.append("price is outside Buy Zone")
        if not trend_allows_buy:
            reasons.append("Trend Filter does not allow buying")
        if support_breakdown:
            reasons.append("major Support Breakdown is active")
        unit_amount = price + fee
        possible_shares = int(floor(state.profit_reserve / unit_amount))
        if max_shares is not None:
            if isinstance(max_shares, bool) or max_shares < 0:
                raise LedgerError("max_shares must be a non-negative integer")
            possible_shares = min(possible_shares, max_shares)
        if possible_shares <= 0:
            reasons.append("Profit Reserve is insufficient for one whole share")
        if reasons:
            return {
                "eligible": False,
                "shares": 0,
                "amount_used": "0",
                "remaining_profit_reserve": str(state.profit_reserve),
                "reasons": reasons,
            }

        amount_used = unit_amount * possible_shares
        reinvestment = {
            "eligible": True,
            "shares": possible_shares,
            "price_reference": str(price),
            "amount_used": str(amount_used),
            "estimated_cost_per_share": str(fee),
        }
        target = None
        if transaction_id is not None:
            target = next(
                (item for item in state.transactions if item["id"] == transaction_id),
                None,
            )
            if target is None:
                raise LedgerError(f"unknown transaction_id: {transaction_id}")
        elif state.transactions:
            target = state.transactions[-1]

        if target is not None:
            previous = target.get("reinvestment", {})
            target["reinvestment"] = reinvestment
            try:
                ProfitLedger.recalculate_state(state)
            except Exception:
                target["reinvestment"] = previous
                ProfitLedger.recalculate_state(state)
                raise
        else:
            state.add_profit_generated_shares(possible_shares, amount_used)
            state.record_audit(
                "profit_reinvestment",
                shares=possible_shares,
                amount_used=str(amount_used),
                price_reference=str(price),
            )
        return {
            **reinvestment,
            "remaining_profit_reserve": str(state.profit_reserve),
            "reasons": [],
        }

    @staticmethod
    def adjust_transaction(
        state: PositionState,
        *,
        transaction_id: str,
        actual_sell_price: Any | None = None,
        actual_buy_price: Any | None = None,
        actual_transaction_cost: Any | None = None,
        actual_slippage: Any | None = None,
        actual_net_profit: Any | None = None,
        reason: str,
    ) -> dict[str, Any]:
        """Apply actual execution data and leave an audit trail."""

        transaction = next(
            (item for item in state.transactions if item["id"] == transaction_id), None
        )
        if transaction is None:
            raise LedgerError(f"unknown transaction_id: {transaction_id}")
        before = deepcopy(transaction)
        if actual_sell_price is not None:
            transaction["sell"]["price"] = str(_price(actual_sell_price, "actual_sell_price"))
        if actual_buy_price is not None:
            transaction["buy"]["price"] = str(_price(actual_buy_price, "actual_buy_price"))
        if actual_transaction_cost is not None:
            cost = money(actual_transaction_cost)
            if cost < 0:
                raise LedgerError("actual_transaction_cost cannot be negative")
            transaction["transaction_cost"] = str(cost)
        if actual_slippage is not None:
            slippage = money(actual_slippage)
            if slippage < 0:
                raise LedgerError("actual_slippage cannot be negative")
            transaction["slippage_cost"] = str(slippage)
        if actual_net_profit is not None:
            transaction["net_profit_override"] = str(money(actual_net_profit))
        else:
            transaction["net_profit_override"] = None
        transaction["profit_source"] = "actual"
        try:
            ProfitLedger.recalculate_state(state)
        except Exception:
            transaction.clear()
            transaction.update(before)
            raise
        state.record_audit(
            "manual_profit_adjustment",
            transaction_id=transaction_id,
            reason=reason,
            before=before,
            after=deepcopy(transaction),
        )
        return transaction

    @staticmethod
    def profit_status(state: PositionState) -> dict[str, Any]:
        return {
            "initial_swing_shares": state.initial_swing_shares,
            "current_swing_shares": state.current_swing_shares,
            "cumulative_net_profit": str(state.cumulative_net_profit),
            "profit_reserve": str(state.profit_reserve),
            "profit_generated_shares": state.profit_generated_shares,
            "core_shares": state.core_shares,
            "total_shares": state.total_shares,
        }

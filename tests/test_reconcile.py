"""Test von Buch und Reconcile (Konto gegen Buch)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from mt5_trading_ai.execution.reconcile import (
    PositionBook,
    positions_to_net,
    reconcile_positions,
)
from mt5_trading_ai.venue.protocol import OrderSide, Position

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _position(symbol: str, side: OrderSide, volume: Decimal) -> Position:
    return Position(
        venue_position_id="p",
        symbol=symbol,
        side=side,
        volume=volume,
        entry_price=Decimal("1"),
        stop_loss=None,
        take_profit=None,
        opened_at=TS,
        unrealised_pnl=Decimal("0"),
        swap_accrued=Decimal("0"),
    )


def test_book_tracks_net_position() -> None:
    book = PositionBook()
    book.apply_fill("EURUSD", OrderSide.BUY, Decimal("0.10"))
    book.apply_fill("EURUSD", OrderSide.BUY, Decimal("0.20"))
    book.apply_fill("EURUSD", OrderSide.SELL, Decimal("0.05"))
    assert book.net("EURUSD") == Decimal("0.25")
    assert book.snapshot() == {"EURUSD": Decimal("0.25")}


def test_book_snapshot_drops_flat_symbols() -> None:
    book = PositionBook()
    book.apply_fill("EURUSD", OrderSide.BUY, Decimal("0.10"))
    book.apply_fill("EURUSD", OrderSide.SELL, Decimal("0.10"))
    assert book.snapshot() == {}


def test_positions_to_net_sums_signed() -> None:
    positions = (
        _position("EURUSD", OrderSide.BUY, Decimal("0.30")),
        _position("EURUSD", OrderSide.SELL, Decimal("0.10")),
        _position("XAUUSD", OrderSide.SELL, Decimal("1.00")),
    )
    assert positions_to_net(positions) == {
        "EURUSD": Decimal("0.20"),
        "XAUUSD": Decimal("-1.00"),
    }


def test_reconcile_matches_when_equal() -> None:
    result = reconcile_positions(
        expected={"EURUSD": Decimal("0.10")},
        actual={"EURUSD": Decimal("0.10")},
        notional_per_unit={"EURUSD": Decimal("110000")},
        max_notional_drift=Decimal("0"),
    )
    assert result.matched is True
    assert result.halt is False


def test_reconcile_within_tolerance_matches() -> None:
    result = reconcile_positions(
        expected={"EURUSD": Decimal("0.10")},
        actual={"EURUSD": Decimal("0.11")},
        notional_per_unit={"EURUSD": Decimal("110000")},
        max_notional_drift=Decimal("0"),
        volume_tolerance=Decimal("0.01"),
    )
    assert result.matched is True
    assert result.halt is False


def test_reconcile_notional_drift_halts() -> None:
    result = reconcile_positions(
        expected={},
        actual={"EURUSD": Decimal("0.50")},
        notional_per_unit={"EURUSD": Decimal("110000")},
        max_notional_drift=Decimal("1000"),
    )
    assert result.halt is True
    assert result.reason == "notional_drift_exceeds_limit"
    assert result.total_notional_drift == Decimal("55000")  # 0.5 * 110000


def test_reconcile_small_drift_within_limit_no_halt() -> None:
    result = reconcile_positions(
        expected={},
        actual={"EURUSD": Decimal("0.001")},
        notional_per_unit={"EURUSD": Decimal("110000")},
        max_notional_drift=Decimal("1000"),
    )
    assert result.matched is False
    assert result.halt is False
    assert result.reason == "within_notional_limit"


def test_reconcile_unpriced_drift_halts() -> None:
    result = reconcile_positions(
        expected={},
        actual={"EURUSD": Decimal("0.50")},
        notional_per_unit={},  # kein Preis -> nicht bewertbar
        max_notional_drift=Decimal("1000000"),
    )
    assert result.halt is True
    assert result.reason == "unpriced_drift"

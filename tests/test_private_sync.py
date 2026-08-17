"""Test der privaten Ereignis-Synchronisation und ihrer Venue-Integration.

Unit: Buch aus Fills, Sequenzluecke/Fehlform -> Desync, Stille. Integration: der Strom
fuehrt das Buch (kein Doppel-Buchen beim Submit), Desync/Stille rasten den Global-Halt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from mt5_trading_ai.execution.private_sync import (
    PrivateEvent,
    PrivateEventKind,
    PrivateSync,
)
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.protocol import OrderRejectedError, OrderSide

from test_mt5_venue import FakeMt5Terminal, _catalog, _mt5_position, _order

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _fill(seq: int, symbol: str, side: OrderSide, volume: Decimal) -> PrivateEvent:
    return PrivateEvent(
        seq=seq, ts=TS, kind=PrivateEventKind.FILL,
        symbol=symbol, side=side, volume=volume,
    )


def _heartbeat(seq: int, ts: datetime = TS) -> PrivateEvent:
    return PrivateEvent(seq=seq, ts=ts, kind=PrivateEventKind.HEARTBEAT)


# --- Unit -----------------------------------------------------------------


def test_sync_fill_updates_book() -> None:
    sync = PrivateSync()
    sync.apply(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    sync.apply(_fill(2, "EURUSD", OrderSide.BUY, Decimal("0.20")))
    assert sync.snapshot() == {"EURUSD": Decimal("0.30")}
    assert sync.desync is False


def test_sync_heartbeat_keeps_sequence_no_book_change() -> None:
    sync = PrivateSync()
    sync.apply(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    sync.apply(_heartbeat(2))
    assert sync.snapshot() == {"EURUSD": Decimal("0.10")}
    assert sync.last_seq == 2


def test_sync_sequence_gap_is_desync() -> None:
    sync = PrivateSync()
    sync.apply(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    sync.apply(_fill(3, "EURUSD", OrderSide.BUY, Decimal("0.10")))  # 2 fehlt
    assert sync.desync is True
    assert sync.desync_reason == "sequence_gap"
    assert sync.snapshot() == {"EURUSD": Decimal("0.10")}  # keine Buchung nach der Luecke


def test_sync_malformed_fill_is_desync() -> None:
    sync = PrivateSync()
    sync.apply(PrivateEvent(seq=1, ts=TS, kind=PrivateEventKind.FILL))  # ohne Felder
    assert sync.desync is True
    assert sync.desync_reason == "malformed_fill"


def test_sync_clear_desync_rebaselines() -> None:
    sync = PrivateSync()
    sync.apply(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    sync.apply(_fill(5, "EURUSD", OrderSide.BUY, Decimal("0.10")))  # Luecke -> Desync
    assert sync.desync is True
    sync.clear_desync()
    assert sync.desync is False
    assert sync.last_seq is None
    sync.apply(_fill(9, "EURUSD", OrderSide.SELL, Decimal("0.10")))  # neue Basis, kein Gap
    assert sync.desync is False
    assert sync.last_seq == 9


def test_sync_staleness_and_health() -> None:
    sync = PrivateSync()
    assert sync.is_stale(TS, timedelta(seconds=30)) is False  # kein Ereignis
    sync.apply(_heartbeat(1))
    assert sync.is_stale(TS + timedelta(seconds=10), timedelta(seconds=30)) is False
    assert sync.is_stale(TS + timedelta(minutes=1), timedelta(seconds=30)) is True
    assert sync.healthy(TS + timedelta(minutes=1), timedelta(seconds=30)) is False


# --- Venue-Integration ----------------------------------------------------


def _synced_venue(
    positions: tuple[object, ...] = (),
) -> tuple[Mt5Venue, PrivateSync]:
    sync = PrivateSync()
    venue = Mt5Venue(
        name="mt5",
        terminal=FakeMt5Terminal(is_demo=True, positions=positions),  # type: ignore[arg-type]
        catalog=_catalog(), sync=sync,
        # Seit A3 Pflicht auf jedem Konto: Risikoschicht + Frische-Latch. Die feste
        # Uhr entspricht dem Zeitstempel des Fake-Kontostands.
        risk_manager=RiskManager(),
        clock=lambda: TS,
    )
    venue.connect()
    return venue, sync


def test_synced_venue_stream_books_not_submit() -> None:
    venue, _ = _synced_venue()
    venue.submit_order(_order(client_order_id="s-1"))
    # Mit Strom bucht der Submit NICHT optimistisch — der autoritative Fill tut es.
    assert venue.book_snapshot() == {}
    venue.apply_private_event(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    assert venue.book_snapshot() == {"EURUSD": Decimal("0.10")}


def test_synced_venue_gap_halts_and_blocks_opening() -> None:
    # Bei Desync ist das Strom-Buch nicht mehr vertrauenswuerdig; das Terminal meldet die
    # Long-Position autoritativ, sodass ein echter reduce_only-Abbau weiter passiert.
    venue, sync = _synced_venue(
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),)
    )
    venue.apply_private_event(_fill(1, "EURUSD", OrderSide.BUY, Decimal("0.10")))
    venue.apply_private_event(_heartbeat(3))  # Luecke (seq 2 fehlt)
    assert sync.desync is True
    assert venue.is_halted() is True
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order(client_order_id="g-1"))
    assert excinfo.value.reason == "global_halt"
    # Reduce-Only (echter Abbau der Long, autoritativ vom Terminal) passiert trotz Halt.
    assert venue.submit_order(
        _order(client_order_id="r-1", side=OrderSide.SELL, reduce_only=True)
    ).accepted
    # Freigabe resynchronisiert den Strom und gibt Eroeffnungen frei.
    venue.clear_halt()
    assert sync.desync is False
    assert venue.submit_order(_order(client_order_id="g-2")).accepted is True


def test_check_sync_staleness_halts() -> None:
    venue, _ = _synced_venue()
    venue.apply_private_event(_heartbeat(1))
    assert venue.check_sync(TS + timedelta(seconds=5), max_silence=timedelta(seconds=30))
    assert venue.is_halted() is False
    healthy = venue.check_sync(TS + timedelta(minutes=5), max_silence=timedelta(seconds=30))
    assert healthy is False
    assert venue.is_halted() is True

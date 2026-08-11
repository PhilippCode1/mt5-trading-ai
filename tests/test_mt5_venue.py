"""Vertragstest fuer die MT5-Anbindung.

Prueft zweierlei: (1) ``Mt5Venue`` erfuellt das ``TradingVenue``-Protokoll und bildet
MT5-Rohwerte korrekt ab; (2) das **Live-Freigabe-Tor** greift — eine eroeffnende Order
an ein Live-Konto ohne vollstaendige Freigabe wird abgelehnt, Demo und Reduce-Only nicht.

Es laeuft ohne echtes MT5-Terminal: das Fake-Terminal unten liefert die Rohwerte.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight
from mt5_trading_ai.venue.mt5 import (
    CatalogEntry,
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Terminal,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    TradingSession,
    TradingVenue,
    UnknownInstrumentError,
    VenueUnavailableError,
)

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)  # ein Dienstag, 12:00 UTC


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _eurusd_symbol() -> Mt5Symbol:
    return Mt5Symbol(
        name="EURUSD",
        digits=5,
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        contract_size=Decimal("100000"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        visible=True,
    )


def _btcusd_symbol() -> Mt5Symbol:
    return Mt5Symbol(
        name="BTCUSD",
        digits=2,
        tick_size=Decimal("0.01"),
        pip_size=Decimal("0.01"),
        contract_size=Decimal("1"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="BTC",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        visible=True,
    )


def _catalog() -> dict[str, CatalogEntry]:
    sessions = tuple(
        TradingSession(weekday=d, open_utc="00:00", close_utc="22:00") for d in range(5)
    )
    return {
        "EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions),
        "BTCUSD": CatalogEntry(AssetClass.CRYPTO, _fees(), sessions),
    }


def _released_settings() -> SimpleNamespace:
    return SimpleNamespace(
        live_release_owner_ack=True,
        live_release_strategy_approved=True,
        live_release_risk_limits_configured=True,
        live_release_venue_demo_verified=True,
        live_release_id="2026-08-11/eurusd/v1",
    )


class FakeMt5Terminal:
    """In-Memory-Terminal fuer den Vertragstest. Erfuellt ``Mt5Terminal``."""

    def __init__(
        self, *, is_demo: bool, margin_free: Decimal = Decimal("10000")
    ) -> None:
        self._connected = False
        self._symbols = {"EURUSD": _eurusd_symbol(), "BTCUSD": _btcusd_symbol()}
        self._account = Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=margin_free,
            is_demo=is_demo,
            ts=TS,
        )
        self._positions: tuple[Mt5Position, ...] = ()
        self.order_send_calls = 0
        self.cancel_calls: list[str] = []
        self.modify_calls: list[tuple[str, Decimal | None, Decimal | None]] = []

    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return tuple(self._symbols.values())

    def symbol(self, name: str) -> Mt5Symbol | None:
        return self._symbols.get(name)

    def tick(self, name: str) -> Mt5Tick | None:
        if name not in self._symbols:
            return None
        if name == "BTCUSD":
            return Mt5Tick(ts=TS, bid=Decimal("60000"), ask=Decimal("60010"))
        return Mt5Tick(ts=TS, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        # bewusst absteigend geliefert, damit der Adapter sortieren muss
        return (
            Mt5Rate(
                ts=datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
                open=Decimal("1.1"),
                high=Decimal("1.2"),
                low=Decimal("1.0"),
                close=Decimal("1.15"),
                tick_volume=100,
            ),
            Mt5Rate(
                ts=datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
                open=Decimal("1.0"),
                high=Decimal("1.1"),
                low=Decimal("0.9"),
                close=Decimal("1.05"),
                tick_volume=90,
            ),
        )

    def order_send(self, request: object) -> Mt5SendResult:
        self.order_send_calls += 1
        return Mt5SendResult(
            accepted=True,
            venue_order_id="V-1",
            filled_volume=Decimal("0.10"),
            average_price=Decimal("1.10000"),
            ts=TS,
            reason="done",
        )

    def cancel(self, venue_order_id: str) -> bool:
        self.cancel_calls.append(venue_order_id)
        return True

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        self.modify_calls.append((venue_position_id, stop_loss, take_profit))
        return True

    def positions(self) -> tuple[Mt5Position, ...]:
        return self._positions

    def account(self) -> Mt5Account:
        return self._account


def _venue(
    *, is_demo: bool, settings: object = None, margin_free: Decimal = Decimal("10000")
) -> tuple[Mt5Venue, FakeMt5Terminal]:
    terminal = FakeMt5Terminal(is_demo=is_demo, margin_free=margin_free)
    venue = Mt5Venue(
        name="mt5-demo",
        terminal=terminal,
        catalog=_catalog(),
        settings=settings,
    )
    venue.connect()
    return venue, terminal


def _order(**overrides: object) -> OrderRequest:
    base: dict[str, object] = {
        "client_order_id": "c-1",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "volume": Decimal("0.10"),
        "stop_loss": Decimal("1.09000"),
    }
    base.update(overrides)
    return OrderRequest(**base)  # type: ignore[arg-type]


# --- Vertrag / Abbildung --------------------------------------------------


def test_fake_terminal_satisfies_terminal_protocol() -> None:
    assert isinstance(FakeMt5Terminal(is_demo=True), Mt5Terminal)


def test_venue_satisfies_trading_venue_protocol() -> None:
    venue, _ = _venue(is_demo=True)
    assert isinstance(venue, TradingVenue)


def test_health_requires_connect() -> None:
    terminal = FakeMt5Terminal(is_demo=True)
    venue = Mt5Venue(name="v", terminal=terminal, catalog=_catalog())
    assert venue.is_healthy() is False
    with pytest.raises(VenueUnavailableError):
        venue.get_quote("EURUSD")
    venue.connect()
    assert venue.is_healthy() is True
    venue.disconnect()
    assert venue.is_healthy() is False


def test_get_instrument_maps_catalog_and_symbol() -> None:
    venue, _ = _venue(is_demo=True)
    inst = venue.get_instrument("EURUSD")
    assert isinstance(inst, Instrument)
    assert inst.asset_class is AssetClass.FX_MAJOR
    assert inst.tick_size == Decimal("0.00001")
    assert inst.stop_level_points == 10


def test_unknown_instrument_is_error_not_default() -> None:
    venue, _ = _venue(is_demo=True)
    with pytest.raises(UnknownInstrumentError):
        venue.get_instrument("XAUUSD")
    with pytest.raises(UnknownInstrumentError):
        venue.get_quote("XAUUSD")


def test_get_quote_maps_tick() -> None:
    venue, _ = _venue(is_demo=True)
    quote = venue.get_quote("EURUSD")
    assert quote.bid == Decimal("1.09990")
    assert quote.ask == Decimal("1.10000")
    assert quote.spread == Decimal("0.00010")


def test_get_bars_sorted_and_filtered() -> None:
    venue, _ = _venue(is_demo=True)
    bars = venue.get_bars(
        "EURUSD",
        Timeframe.H1,
        start=datetime(2026, 8, 11, 10, 30, tzinfo=UTC),
        end=datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
    )
    assert len(bars) == 1  # der 10:00-Balken faellt aus dem Fenster
    assert bars[0].ts == datetime(2026, 8, 11, 11, 0, tzinfo=UTC)


def test_is_trading_open_respects_sessions() -> None:
    venue, _ = _venue(is_demo=True)
    assert venue.is_trading_open("EURUSD", at=TS) is True  # Dienstag 12:00
    late = datetime(2026, 8, 11, 22, 30, tzinfo=UTC)  # nach Sessionende 22:00
    assert venue.is_trading_open("EURUSD", at=late) is False
    weekend = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)  # Samstag
    assert venue.is_trading_open("EURUSD", at=weekend) is False


# --- Ausfuehrung + Sicherheitstor ----------------------------------------


def test_demo_opening_order_is_accepted_without_release() -> None:
    venue, terminal = _venue(is_demo=True, settings=None)
    result = venue.submit_order(_order())
    assert result.accepted is True
    assert result.venue_order_id == "V-1"
    assert terminal.order_send_calls == 1


def test_live_opening_order_blocked_without_release() -> None:
    venue, terminal = _venue(is_demo=False, settings=None)
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order())
    assert excinfo.value.reason == "live_release_incomplete"
    assert terminal.order_send_calls == 0  # nichts gesendet


def test_live_opening_order_allowed_with_full_release() -> None:
    venue, terminal = _venue(is_demo=False, settings=_released_settings())
    result = venue.submit_order(_order())
    assert result.accepted is True
    assert terminal.order_send_calls == 1


def test_live_reduce_only_passes_without_release() -> None:
    venue, terminal = _venue(is_demo=False, settings=None)
    result = venue.submit_order(_order(client_order_id="r-1", reduce_only=True))
    assert result.accepted is True
    assert terminal.order_send_calls == 1


def test_opening_without_stop_is_rejected() -> None:
    venue, terminal = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order(stop_loss=Decimal("0")))
    assert excinfo.value.reason == "missing_stop_loss"
    assert terminal.order_send_calls == 0


def test_volume_below_min_is_rejected() -> None:
    venue, terminal = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order(volume=Decimal("0.005")))
    assert excinfo.value.reason == "volume_below_min"
    assert terminal.order_send_calls == 0


def test_volume_off_step_is_rejected() -> None:
    venue, _ = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order(volume=Decimal("0.015")))
    assert excinfo.value.reason == "volume_off_step"


def test_submit_is_idempotent_over_client_order_id() -> None:
    venue, terminal = _venue(is_demo=True)
    first = venue.submit_order(_order(client_order_id="same"))
    second = venue.submit_order(_order(client_order_id="same"))
    assert first.idempotent_replay is False
    assert second.idempotent_replay is True
    assert second.venue_order_id == first.venue_order_id
    assert terminal.order_send_calls == 1  # keine zweite Order


def test_cancel_and_modify() -> None:
    venue, terminal = _venue(is_demo=True)
    venue.submit_order(_order(client_order_id="cx"))
    assert venue.cancel_order("cx") is True
    assert terminal.cancel_calls == ["V-1"]
    assert venue.cancel_order("unbekannt") is False
    assert venue.modify_position_stops(
        "P-1", stop_loss=Decimal("1.08"), take_profit=None
    ) is True
    assert terminal.modify_calls == [("P-1", Decimal("1.08"), None)]


def test_get_account_maps_state() -> None:
    venue, _ = _venue(is_demo=True)
    acc = venue.get_account()
    assert acc.is_demo is True
    assert acc.balance == Decimal("10000")
    assert acc.currency == "USD"


# --- Hebelklammer-Anschluss am Order-Pfad --------------------------------


def test_leverage_preflight_clamps_and_checks_margin() -> None:
    venue, _ = _venue(is_demo=True)
    pre = evaluate_leverage_preflight(
        instrument=venue.get_instrument("EURUSD"),
        request=_order(),
        account=venue.get_account(),
        price=Decimal("1.10"),
        requested_leverage=50,
    )
    assert pre.approved is True
    assert pre.effective_leverage == 10  # min(50, 10, 30)


def test_leverage_preflight_crypto_is_no_trade() -> None:
    venue, _ = _venue(is_demo=True)
    pre = evaluate_leverage_preflight(
        instrument=venue.get_instrument("BTCUSD"),
        request=_order(symbol="BTCUSD"),
        account=venue.get_account(),
        price=Decimal("60000"),
        requested_leverage=50,
    )
    assert pre.approved is False
    assert pre.reason == "class_cap_below_system_minimum"


def test_leverage_preflight_insufficient_margin() -> None:
    venue, _ = _venue(is_demo=True, margin_free=Decimal("500"))
    pre = evaluate_leverage_preflight(
        instrument=venue.get_instrument("EURUSD"),
        request=_order(),
        account=venue.get_account(),
        price=Decimal("1.10"),
        requested_leverage=50,
    )
    assert pre.approved is False
    assert pre.reason == "insufficient_margin"


def test_venue_opening_blocks_untradeable_crypto() -> None:
    venue, terminal = _venue(is_demo=True)
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(_order(client_order_id="btc-1", symbol="BTCUSD"))
    assert excinfo.value.reason == "class_cap_below_system_minimum"
    assert terminal.order_send_calls == 0


def test_venue_opening_blocks_on_insufficient_margin() -> None:
    venue, terminal = _venue(is_demo=True, margin_free=Decimal("500"))
    with pytest.raises(OrderRejectedError) as excinfo:
        venue.submit_order(
            _order(client_order_id="m-1", meta={"requested_leverage": 50})
        )
    assert excinfo.value.reason == "insufficient_margin"
    assert terminal.order_send_calls == 0


def test_venue_opening_passes_with_default_leverage() -> None:
    venue, terminal = _venue(is_demo=True)
    result = venue.submit_order(_order(client_order_id="ok-1"))
    assert result.accepted is True
    assert terminal.order_send_calls == 1

"""Die in Bildung befindliche Kerze muss als solche erkennbar sein (Auftrag K4).

Der Befund: ``copy_rates_range`` liefert bei ``end=jetzt`` die LAUFENDE Kerze mit.
Ihr ``close`` ist der momentane Kurs, kein Schlusskurs. Bis hierher gab es kein Feld,
das den Unterschied ausgedrueckt haette -- der Live-Treiber rechnete seinen gleitenden
Durchschnitt genau auf diesem letzten Element, waehrend der Backtest abgeschlossene
Kerzen aus Dateien liest. Live-Signal und getestetes Signal waren damit nicht dieselbe
Strategie.

Diese Datei fixiert vier Dinge:

1. Die laufende Kerze ist ``is_closed=False`` (der rote Eichfall).
2. Eine abgeschlossene Kerze ist ``is_closed=True`` -- sonst waere hier nur alles
   auf False gedreht und der Melder waere per Konstruktion nie gruen.
3. Die Gegenwart kommt vom PLATZ, nicht von der Rechneruhr. Der Test setzt beide
   bewusst auseinander; eine Fassung mit ``datetime.now()`` faellt durch.
4. Ohne Platzzeit wird geworfen, und die laufende Kerze wird nicht still entfernt.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from mt5_trading_ai.venue.catalog import CatalogEntry
from mt5_trading_ai.venue.mt5 import (
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
    Bar,
    FeeSchedule,
    Timeframe,
    TradingSession,
    VenueUnavailableError,
)

#: Zeit des letzten Ticks -- die Gegenwart, wie der PLATZ sie kennt. Mitten in der
#: 11:00-Stundenkerze: die 10:00er steht, die 11:00er bildet sich noch.
PLATZZEIT = datetime(2026, 8, 11, 11, 30, tzinfo=UTC)

#: Die Rechneruhr, drei Stunden VOR der Platzzeit. Das ist kein ausgedachter Wert:
#: genau diesen Versatz misst dieses Repo am realen Broker (Server UTC+3), und genau
#: er entsteht, wenn Kerzenstempel ungedreht mit dem Etikett UTC weitergereicht
#: werden. Eine Fassung, die ``datetime.now()`` benutzt, haelt damit die laufende
#: 11:00-Kerze fuer abgeschlossen (11:00 + 1 h <= 14:30) -- fail-open, unbemerkt.
RECHNERUHR = PLATZZEIT + timedelta(hours=3)


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _symbol() -> Mt5Symbol:
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


def _catalog() -> dict[str, CatalogEntry]:
    sessions = tuple(
        TradingSession(weekday=d, open_utc="00:00", close_utc="22:00") for d in range(5)
    )
    return {"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions)}


def _rate(stunde: int) -> Mt5Rate:
    return Mt5Rate(
        ts=datetime(2026, 8, 11, stunde, 0, tzinfo=UTC),
        open=Decimal("1.10000"),
        high=Decimal("1.10500"),
        low=Decimal("1.09500"),
        close=Decimal("1.10200"),
        tick_volume=100,
    )


class FakeTerminal:
    """Terminal-Naht fuer diesen Test. Nur die Lesepfade sind gefuellt.

    ``tick_ts`` ist der Hebel des Tests: er ist die Zeit, die der PLATZ meldet. Ein
    ``None`` steht fuer den Fall "kein Tick" -- der muss werfen, nicht raten.
    """

    def __init__(
        self,
        *,
        tick_ts: datetime | None = PLATZZEIT,
        stunden: tuple[int, ...] = (9, 10, 11),
    ) -> None:
        self._connected = False
        self._tick_ts = tick_ts
        self._stunden = stunden
        self.tick_calls = 0

    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (_symbol(),)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return _symbol() if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        self.tick_calls += 1
        if self._tick_ts is None:
            return None
        return Mt5Tick(
            ts=self._tick_ts, bid=Decimal("1.09990"), ask=Decimal("1.10000")
        )

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        # Absteigend geliefert -- der Adapter sortiert selbst.
        return tuple(_rate(h) for h in reversed(self._stunden))

    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def cancel(self, venue_order_id: str) -> bool:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        raise NotImplementedError("Dieser Test fasst den Schreibpfad nicht an")

    def positions(self) -> tuple[Mt5Position, ...]:
        return ()

    def account(self) -> Mt5Account:
        return Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=Decimal("10000"),
            is_demo=True,
            ts=PLATZZEIT,
        )


def _venue(terminal: FakeTerminal) -> Mt5Venue:
    """Ein verbundenes Venue, dessen Rechneruhr bewusst NEBEN der Platzzeit liegt.

    ``clock`` bleibt hier nicht zufaellig ungleich ``PLATZZEIT``: waeren beide gleich,
    liesse sich nicht mehr unterscheiden, welche der beiden Uhren das Urteil traegt.
    """
    venue = Mt5Venue(
        name="mt5-test",
        terminal=terminal,
        catalog=_catalog(),
        clock=lambda: RECHNERUHR,
    )
    venue.connect()
    return venue


def _bars(
    terminal: FakeTerminal, timeframe: Timeframe = Timeframe.H1
) -> tuple[Bar, ...]:
    return _venue(terminal).get_bars(
        "EURUSD",
        timeframe,
        start=datetime(2026, 8, 11, 0, 0, tzinfo=UTC),
        end=datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
    )


# --- Roter Eichfall -------------------------------------------------------


def test_laufende_kerze_ist_nicht_abgeschlossen() -> None:
    """DER Eichfall. Gegen die alte Fassung: ``Bar`` hatte kein ``is_closed``.

    Die 11:00-Stundenkerze endet um 12:00, die Platzzeit steht auf 11:30. Ihr
    ``close`` ist der momentane Kurs -- kein Schlusskurs.
    """
    bars = _bars(FakeTerminal())
    assert bars[-1].ts == datetime(2026, 8, 11, 11, 0, tzinfo=UTC)
    assert bars[-1].is_closed is False


def test_abgeschlossene_kerze_gilt_als_abgeschlossen() -> None:
    """Gegenprobe: waere hier nur alles auf False gedreht, faellt dieser Test.

    Die 09:00er und die 10:00er sind um 11:30 vorbei.
    """
    bars = _bars(FakeTerminal())
    assert [bar.is_closed for bar in bars] == [True, True, False]


def test_grenze_zaehlt_als_abgeschlossen() -> None:
    """Genau auf der Intervallgrenze laeuft bereits die naechste Kerze.

    Platzzeit exakt 12:00 -> die 11:00er ist fertig. ``<`` statt ``<=`` haette hier
    eine fertige Kerze eine volle Stunde lang als laufend gefuehrt.
    """
    bars = _bars(FakeTerminal(tick_ts=datetime(2026, 8, 11, 12, 0, tzinfo=UTC)))
    assert [bar.is_closed for bar in bars] == [True, True, True]


def test_platzzeit_entscheidet_nicht_die_rechneruhr() -> None:
    """Der zweite Eichfall -- gegen die naheliegende falsche Reparatur.

    Die Rechneruhr steht auf 14:30, die Platzzeit auf 11:30. Wer ``datetime.now()``
    oder ``self._clock`` nimmt, rechnet 11:00 + 1 h <= 14:30 und meldet die laufende
    Kerze als abgeschlossen. Genau diese Fehlerklasse -- eine Pruefung, die per
    Konstruktion die falsche Uhr befragt -- hat dieses Repo schon einmal getroffen.
    """
    terminal = FakeTerminal()
    bars = _bars(terminal)
    assert RECHNERUHR > bars[-1].ts + Timeframe.H1.duration  # Rechneruhr saehe: fertig
    assert bars[-1].is_closed is False  # der Platz sagt: laeuft noch
    assert terminal.tick_calls >= 1  # die Platzzeit wurde wirklich abgefragt


def test_ohne_platzzeit_wird_geworfen_statt_geraten() -> None:
    """Fail-closed. Alte Fassung: lieferte drei Bars, ohne je einen Tick zu brauchen.

    Ohne Tick ist nicht entscheidbar, welche Kerze steht. Nicht entscheidbar faellt
    nicht auf einen Vorgabewert zurueck.
    """
    with pytest.raises(VenueUnavailableError):
        _bars(FakeTerminal(tick_ts=None))


def test_laufende_kerze_wird_nicht_still_entfernt() -> None:
    """Kennzeichnen, nicht abschneiden.

    Ein stilles Abschneiden der letzten Kerze wuerde die Entscheidung an einen
    zweiten Ort legen, und der naechste Verbraucher wuesste wieder nicht, was er vor
    sich hat. Alle drei Kerzen kommen heraus -- eine davon markiert.
    """
    bars = _bars(FakeTerminal())
    assert len(bars) == 3
    assert [bar.ts.hour for bar in bars] == [9, 10, 11]
    assert sum(1 for bar in bars if not bar.is_closed) == 1


def test_dauer_folgt_der_zeitebene() -> None:
    """Die Intervalllaenge kommt aus der Zeitebene, nicht aus einer festen Stunde.

    Dieselbe 11:00-Kerze bei Platzzeit 11:30: als H1 laeuft sie noch, als M15 ist sie
    laengst vorbei. Eine fest verdrahtete Stunde faellt hier durch.
    """
    assert _bars(FakeTerminal(), Timeframe.H1)[-1].is_closed is False
    assert _bars(FakeTerminal(), Timeframe.M15)[-1].is_closed is True


# --- Der Vertrag selbst ---------------------------------------------------


def test_bar_verlangt_die_auskunft() -> None:
    """``is_closed`` ist Pflichtfeld ohne Vorgabewert.

    Alte Fassung: derselbe Aufruf baute klaglos eine Bar -- und niemand konnte ihr
    ansehen, ob sie steht. Ein Vorgabewert ``True`` waere die schmeichelnde Richtung
    (jede vergessliche Bauweise saehe geprueft aus), ein Vorgabewert ``False`` wuerde
    echte Schlusskerzen falsch etikettieren. Also: keiner.
    """
    felder = {
        "symbol": "EURUSD",
        "timeframe": Timeframe.H1,
        "ts": datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
        "open": Decimal("1.1"),
        "high": Decimal("1.2"),
        "low": Decimal("1.0"),
        "close": Decimal("1.15"),
        "tick_volume": 100,
    }
    with pytest.raises(TypeError):
        Bar(**felder)  # type: ignore[arg-type]
    gebaut = Bar(**felder, is_closed=True)  # type: ignore[arg-type]
    assert gebaut.is_closed is True


def test_jede_zeitebene_hat_eine_dauer() -> None:
    """Eine neue Zeitebene ohne Eintrag wuerde sonst erst live auffallen.

    ``Timeframe.duration`` zieht aus derselben Tabelle, aus der das Qualitaetstor die
    erwartete Bar-Zahl zieht. Dieser Test haelt die beiden zusammen.
    """
    for timeframe in Timeframe:
        assert timeframe.duration > timedelta(0)
    assert Timeframe.H1.duration == timedelta(hours=1)
    assert Timeframe.D1.duration == timedelta(days=1)


def test_fake_erfuellt_die_terminal_naht() -> None:
    assert isinstance(FakeTerminal(), Mt5Terminal)

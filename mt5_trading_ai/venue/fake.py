"""Ein Terminal ohne MetaTrader: die Betriebsattrappe fuer Trockenlauf und Eichfaelle.

WARUM IM PAKET UND NICHT IN ``tests/``
--------------------------------------
``tools/live_betrieb.py --terminal fake`` faehrt den Betriebslauf gegen diese Klasse
(D8-Eichfall, A6; der ``kill``-Eichfall von T8 startet genau so). Ein Betriebswerkzeug
importiert nicht aus ``tests/``: der Testbaum ist nicht Teil des Pakets, er zieht
``pytest`` und Testhilfen mit, und seine Attrappe (``tests/test_mt5_venue.py``,
``FakeMt5Terminal``) traegt Zaehler und Schalter, die nur ein Test braucht -- etwa ein
umschaltbares ``is_demo``. Diese Attrappe hier ist absichtlich kleiner: **immer**
Demokonto, ein Symbol, synthetische Kerzen, ein Bestand, den ``order_send`` fuehrt.

WAS SIE NIE TUT
---------------
``MetaTrader5`` wird weder importiert noch ``initialize()`` gerufen (das startet das
Terminal, gemessen in T3). Es wird nichts an einen Broker gesendet. ``is_demo`` ist
fest ``True`` und nicht einstellbar: ein Fake-Livekonto gehoert in einen Test, nicht in
ein Werkzeug, das jemand mit ``--demo-schreiben`` startet.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from mt5_trading_ai.venue.mt5 import (
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
)
from mt5_trading_ai.venue.protocol import Timeframe

#: Das eine Symbol der Attrappe; es steht im Katalog
#: (``config/instrument_catalog.json``).
SYMBOL = "EURUSD"


def _eurusd() -> Mt5Symbol:
    return Mt5Symbol(
        name=SYMBOL,
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


class FakeMt5Terminal:
    """Erfuellt ``Mt5Terminal`` ohne Terminal. Demokonto, EURUSD, eigener Bestand.

    ``uhr`` liefert die Gegenwart fuer Konto- und Kursstempel -- die Vorgabe ist die
    Systemuhr, damit Frische-Latch und Handelszeitenpruefung des Venues im
    Trockenlauf so antworten wie am echten Terminal. Tests frieren sie ein.

    ``rates`` erzeugt eine steigende Stundenreihe bis zur letzten vollen Stunde vor
    ``end``: MA(12) liegt ueber MA(26), das Signal ist LONG -- die Eintrittskette
    laeuft damit bis zur Zulassung (D1) und, mit Schreibrecht, bis zum Fill.
    """

    def __init__(
        self,
        *,
        uhr: Callable[[], datetime] | None = None,
        equity: Decimal = Decimal("10000"),
        positions: tuple[Mt5Position, ...] = (),
    ) -> None:
        self._uhr = uhr if uhr is not None else (lambda: datetime.now(UTC))
        self._connected = False
        self._equity = equity
        self._positions: list[Mt5Position] = list(positions)
        self._naechstes_ticket = 1000
        self._symbol = _eurusd()
        #: Was ``order_send`` bekommen hat -- fuer Eichfaelle und das Journal.
        self.gesendet: list[dict[str, Any]] = []

    # --- Sitzung -----------------------------------------------------------
    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # --- Stammdaten und Kurse ----------------------------------------------
    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (self._symbol,)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return self._symbol if name == SYMBOL else None

    def tick(self, name: str) -> Mt5Tick | None:
        if name != SYMBOL:
            return None
        return Mt5Tick(ts=self._uhr(), bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        if name != SYMBOL or timeframe is not Timeframe.H1:
            return ()
        letzte = end.replace(minute=0, second=0, microsecond=0)
        aus: list[Mt5Rate] = []
        erste = start.replace(minute=0, second=0, microsecond=0)
        stunden = int((letzte - erste) / timedelta(hours=1))
        for i in range(max(stunden, 0) + 1):
            ts = erste + timedelta(hours=i)
            # Steigend um einen Pip je Stunde: MA(12) > MA(26) -> LONG.
            close = Decimal("1.09000") + Decimal(i) * Decimal("0.00010")
            aus.append(
                Mt5Rate(
                    ts=ts,
                    open=close - Decimal("0.00005"),
                    high=close + Decimal("0.00010"),
                    low=close - Decimal("0.00010"),
                    close=close,
                    tick_volume=100,
                )
            )
        return tuple(aus)

    # --- Konto und Bestand -------------------------------------------------
    def account(self) -> Mt5Account:
        return Mt5Account(
            account_id="DEMO-FAKE",
            currency="USD",
            balance=self._equity,
            equity=self._equity,
            margin_used=Decimal("0"),
            margin_free=self._equity,
            is_demo=True,
            ts=self._uhr(),
            leverage=30,
        )

    def positions(self) -> tuple[Mt5Position, ...]:
        return tuple(self._positions)

    # --- Schreibpfad: fuehrt den eigenen Bestand ---------------------------
    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult:
        req = dict(request)
        self.gesendet.append(req)
        jetzt = self._uhr()
        volume = Decimal(str(req.get("volume", "0")))
        if req.get("reduce_only"):
            ticket = req.get("position_ticket")
            treffer = [p for p in self._positions if p.ticket == ticket]
            if not treffer:
                return Mt5SendResult(
                    accepted=False,
                    venue_order_id=None,
                    filled_volume=Decimal("0"),
                    average_price=None,
                    ts=jetzt,
                    reason="position_vanished",
                )
            self._positions = [p for p in self._positions if p.ticket != ticket]
            return Mt5SendResult(
                accepted=True,
                venue_order_id=f"{self._naechstes_ticket}",
                filled_volume=treffer[0].volume,
                average_price=Decimal("1.09990"),
                ts=jetzt,
                reason="done",
            )
        self._naechstes_ticket += 1
        ticket_neu = str(self._naechstes_ticket)
        ist_kauf = req.get("side") == "buy"
        preis = Decimal("1.10000") if ist_kauf else Decimal("1.09990")
        stop = req.get("stop_loss")
        self._positions.append(
            Mt5Position(
                ticket=ticket_neu,
                symbol=SYMBOL,
                is_buy=ist_kauf,
                volume=volume,
                entry_price=preis,
                stop_loss=None if stop in (None, "") else Decimal(str(stop)),
                take_profit=None,
                opened_at=jetzt,
                unrealised_pnl=Decimal("0"),
                swap=Decimal("0"),
            )
        )
        return Mt5SendResult(
            accepted=True,
            venue_order_id=ticket_neu,
            filled_volume=volume,
            average_price=preis,
            ts=jetzt,
            reason="done",
        )

    def cancel(self, venue_order_id: str) -> bool:
        return True

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        return any(p.ticket == venue_position_id for p in self._positions)

"""E10.5 -- der Not-Aus verschluckte Fehlschlaege und war beim zweiten Griff leer.

WARUM DIESER TEST
-----------------
``Mt5Venue.emergency_flatten`` hatte zwei Fehler an derselben Stelle, und beide zeigen
in dieselbe Richtung: der Betrieb glaubt, das Risiko sei weg.

**Fehlschlaege wurden verschluckt.** Jeder ``VenueError`` wurde mit ``continue``
gefangen, zurueckgegeben wurden nur die Erfolge. "Alles glatt" und "nichts glatt"
sahen fuer den Aufrufer gleich aus -- beides ein Tupel. Beim Not-Aus ist das die
gefaehrlichste Fehlrichtung ueberhaupt.

**Die Kennung war stabil.** Sie lautete ``flatten-{ticket}``. Ein zweiter Not-Aus auf
dieselbe Position traf damit den Wiedergaenger-Zweig in ``submit_order``, **sendete
nichts** und meldete trotzdem ``accepted=True``. Der zweite Griff zur Notbremse war
eine Attrappe.

WAS ANSTELLE DESSEN GEPRUEFT WIRD
---------------------------------
Der Erfolg wird am bestaetigten Volumen gemessen -- jede Schliessung muss ihre
Position vollstaendig decken. Bleibt etwas offen oder scheitert eine Schliessung,
verlaesst der Ausgang den normalen Weg (``NotAusUnvollstaendig``), mit der Liste
dessen, was steht. Und jeder Not-Aus-Lauf traegt eine eigene Kennung, damit er
tatsaechlich sendet.

MESSUNG GEGEN HEAD
------------------
Auf Modulebene werden nur Namen importiert, die es in BEIDEN Fassungen gibt.
``NotAusUnvollstaendig`` wird erst IM Test geholt.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.venue.catalog import CatalogEntry  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AssetClass,
    FeeSchedule,
    Timeframe,
    TradingSession,
    VenueUnavailableError,
)

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


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


def _position(ticket: str, volume: str, *, is_buy: bool = True) -> Mt5Position:
    return Mt5Position(
        ticket=ticket,
        symbol="EURUSD",
        is_buy=is_buy,
        volume=Decimal(volume),
        entry_price=Decimal("1.10000"),
        stop_loss=Decimal("1.09000"),
        take_profit=None,
        opened_at=TS,
        unrealised_pnl=Decimal("0"),
        swap=Decimal("0"),
    )


class _Terminal:
    """Terminal, dessen Schliessverhalten je Position frei setzbar ist.

    ``verhalten`` bildet ein Positions-Ticket auf das ab, was der Broker tut:
    ``"voll"`` schliesst ganz, ``"halb"`` fuellt die Haelfte, eine Ausnahme wird
    geworfen. Der Positionsbestand ist konstant -- die Frage, ob der Not-Aus gewirkt
    hat, wird bewusst NICHT an einem sofortigen Nachlesen entschieden (die
    Positionsliste des Brokers zieht der Ausfuehrung nach).
    """

    def __init__(
        self,
        positionen: tuple[Mt5Position, ...],
        verhalten: dict[str, Any] | None = None,
    ) -> None:
        self._positionen = positionen
        self._verhalten = verhalten or {}
        self._verbunden = False
        self.gesendet: list[dict[str, Any]] = []

    def initialize(self) -> bool:
        self._verbunden = True
        return True

    def shutdown(self) -> None:
        self._verbunden = False

    def is_connected(self) -> bool:
        return self._verbunden

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (_symbol(),)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return _symbol() if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        return Mt5Tick(ts=TS, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return ()

    def order_send(self, request: Any) -> Mt5SendResult:
        self.gesendet.append(dict(request))
        kennung = str(request["client_order_id"])
        gewuenscht = Decimal(str(request["volume"]))
        art: Any = "voll"
        for ticket, wie in self._verhalten.items():
            if kennung.endswith(f"-{ticket}"):
                art = wie
                break
        if isinstance(art, Exception):
            raise art
        fill = gewuenscht if art == "voll" else gewuenscht / 2
        return Mt5SendResult(
            accepted=True,
            venue_order_id=f"V-{len(self.gesendet)}",
            filled_volume=fill,
            average_price=Decimal("1.10000"),
            ts=TS,
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
        return True

    def positions(self) -> tuple[Mt5Position, ...]:
        return self._positionen

    def account(self) -> Mt5Account:
        return Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=Decimal("10000"),
            is_demo=True,
            ts=TS,
        )


def _venue(
    positionen: tuple[Mt5Position, ...],
    verhalten: dict[str, Any] | None = None,
) -> tuple[Mt5Venue, _Terminal]:
    sessions = tuple(
        TradingSession(weekday=tag, open_utc="00:00", close_utc="22:00")
        for tag in range(5)
    )
    terminal = _Terminal(positionen, verhalten)
    venue = Mt5Venue(
        name="mt5-test",
        terminal=terminal,  # type: ignore[arg-type]
        catalog={"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions)},
        risk_manager=RiskManager(),
        clock=lambda: TS,
    )
    venue.connect()
    return venue, terminal


# =========================================================================== #
# Der rote Eichfall: verschluckte Fehlschlaege                                 #
# =========================================================================== #
def test_gescheiterte_schliessung_wird_nicht_verschluckt() -> None:
    """DER ROTE EICHFALL VON E10.5.

    Zwei Positionen, eine laesst sich nicht schliessen. Gegen HEAD kam ein Tupel mit
    einem Eintrag zurueck -- und ein Tupel mit einem Eintrag ist genau das, was auch
    ein erfolgreicher Not-Aus auf eine einzige Position liefert. Der Aufrufer konnte
    "alles glatt" von "die Haelfte steht noch" nicht unterscheiden.
    """
    venue, terminal = _venue(
        (_position("p1", "0.30"), _position("p2", "0.10", is_buy=False)),
        verhalten={"p2": VenueUnavailableError("Leitung weg beim Schliessen")},
    )
    with pytest.raises(VenueUnavailableError) as ex:
        venue.emergency_flatten()
    assert "p2" in str(ex.value), (
        "Der Fehlschlag muss benennen, WELCHE Position offen steht -- sonst ist die "
        "Meldung fuer den Betrieb wertlos."
    )
    assert venue.is_halted() is True, "Der Halt steht vor dem ersten Schliessversuch."


def test_teilfuellung_ist_kein_vollzogener_notaus() -> None:
    """Der Broker fuellt die Haelfte -- das halbe Risiko steht noch.

    Gemessen wird das bestaetigte Volumen, nicht der Rueckgabecode. Gegen HEAD galt
    jede angenommene Order als erledigte Schliessung.
    """
    venue, _ = _venue((_position("p1", "0.30"),), verhalten={"p1": "halb"})
    with pytest.raises(VenueUnavailableError) as ex:
        venue.emergency_flatten()
    assert "0.15" in str(ex.value) and "0.30" in str(ex.value)


def test_der_fehler_traegt_die_gelungenen_schliessungen_mit() -> None:
    """Durch das Werfen darf die Information nicht verlorengehen."""
    from mt5_trading_ai.venue.mt5 import NotAusUnvollstaendig

    venue, _ = _venue(
        (_position("p1", "0.30"), _position("p2", "0.10", is_buy=False)),
        verhalten={"p2": "halb"},
    )
    with pytest.raises(NotAusUnvollstaendig) as ex:
        venue.emergency_flatten()
    assert len(ex.value.geschlossen) == 2  # beide angenommen ...
    assert len(ex.value.offen) == 1  # ... aber eine nur halb


# =========================================================================== #
# Der rote Eichfall: der zweite Griff zur Notbremse                            #
# =========================================================================== #
def test_zweiter_notaus_sendet_wirklich_erneut() -> None:
    """DER ZWEITE ROTE EICHFALL VON E10.5.

    Die Position steht nach dem ersten Not-Aus noch (der Broker hat sie nicht
    entfernt -- genau der Zustand, in dem man ein zweites Mal drueckt). Gegen HEAD
    war die Kennung ``flatten-p1`` beim zweiten Mal identisch, der Wiedergaenger-Zweig
    in ``submit_order`` griff, es wurde **nichts gesendet** -- und
    ``accepted=True`` gemeldet. Die Notbremse war beim zweiten Zug leer.
    """
    venue, terminal = _venue((_position("p1", "0.30"),))
    venue.emergency_flatten()
    assert len(terminal.gesendet) == 1

    venue.emergency_flatten()
    assert len(terminal.gesendet) == 2, (
        "Der zweite Not-Aus hat nichts gesendet. Eine Notbremse, die beim zweiten "
        "Zug nur noch das alte Ergebnis wiederholt, ist keine."
    )
    kennungen = {str(req["client_order_id"]) for req in terminal.gesendet}
    assert len(kennungen) == 2, f"Beide Laeufe teilten sich eine Kennung: {kennungen}"


def test_die_kennung_nennt_die_position() -> None:
    """Die Kennung bleibt lesbar -- sonst ist sie im Terminal nicht zuzuordnen."""
    venue, terminal = _venue((_position("p1", "0.30"),))
    venue.emergency_flatten()
    assert str(terminal.gesendet[0]["client_order_id"]).endswith("-p1")


# =========================================================================== #
# Gegenproben                                                                 #
# =========================================================================== #
def test_vollstaendiger_notaus_gibt_ergebnisse_zurueck() -> None:
    """Ohne diese Gegenprobe waere "wirft immer" von "wirft richtig" ununterscheidbar."""
    venue, terminal = _venue(
        (_position("p1", "0.30"), _position("p2", "0.10", is_buy=False))
    )
    ergebnisse = venue.emergency_flatten()
    assert len(ergebnisse) == 2
    assert all(r.accepted for r in ergebnisse)
    assert len(terminal.gesendet) == 2
    assert venue.is_halted() is True


def test_ohne_positionen_ist_der_notaus_still_erfolgreich() -> None:
    """Nichts offen heisst nichts zu schliessen -- und trotzdem Halt."""
    venue, terminal = _venue(())
    assert venue.emergency_flatten() == ()
    assert terminal.gesendet == []
    assert venue.is_halted() is True


def test_der_halt_steht_auch_wenn_alles_scheitert() -> None:
    """Der Halt wird zuerst gesetzt -- eine gescheiterte Schliessung aendert das nicht.

    Er ist die einzige Zusage, die der Not-Aus in jedem Fall einhalten kann.
    """
    venue, _ = _venue(
        (_position("p1", "0.30"),),
        verhalten={"p1": VenueUnavailableError("alles weg")},
    )
    with pytest.raises(VenueUnavailableError):
        venue.emergency_flatten()
    assert venue.is_halted() is True


def test_der_halt_steht_auch_ohne_leitung() -> None:
    """DER DRITTE ROTE EICHFALL VON E10.5 -- der Not-Aus liess im Zweifel offen.

    Die Reihenfolge lautete ``_require_healthy()``, dann ``_halted = True``. Bricht
    die Leitung weg -- der wahrscheinlichste Zustand, in dem jemand ueberhaupt zur
    Notbremse greift --, warf die Methode, schloss nichts UND latchte nichts. Gegen
    HEAD steht hier ``is_halted() is False``: der Not-Aus wurde gedrueckt, und das
    System durfte weiter eroeffnen.

    Der Latch ist eine Zuweisung auf ein Feld dieses Objekts. Sie braucht keine
    Leitung und kann nicht scheitern -- also darf sie von nichts abhaengen. Sie ist
    die einzige Zusage, die der Not-Aus in JEDEM Fall einhalten kann; genau das sagt
    sein Docstring zu, und genau das hielt er nicht.
    """
    venue, terminal = _venue((_position("p1", "0.30"),))
    venue.disconnect()

    with pytest.raises(VenueUnavailableError):
        venue.emergency_flatten()

    assert venue.is_halted() is True, (
        "Der Not-Aus ist an der Gesundheitspruefung gescheitert und hat den Halt "
        "nicht gesetzt. Damit laesst die Notbremse neue Eroeffnungen zu -- in dem "
        "Zustand, fuer den es sie gibt."
    )
    assert venue.halt_reason == "emergency_flatten"
    assert terminal.gesendet == [], "Ohne Leitung darf nichts gesendet worden sein."


def test_der_halt_haengt_nicht_am_ausgang_des_notaus() -> None:
    """Gegenprobe: der Latch steht in allen drei Ausgaengen -- gelungen, unvollstaendig,
    gar nicht erst begonnen.

    Ohne diese Gegenprobe waere "latcht immer" von "latcht zufaellig" nicht zu
    unterscheiden.
    """
    gelungen, _ = _venue((_position("p1", "0.30"),))
    gelungen.emergency_flatten()
    assert gelungen.is_halted() is True

    halb, _ = _venue((_position("p1", "0.30"),), verhalten={"p1": "halb"})
    with pytest.raises(VenueUnavailableError):
        halb.emergency_flatten()
    assert halb.is_halted() is True

    tot, _ = _venue((_position("p1", "0.30"),))
    tot.disconnect()
    with pytest.raises(VenueUnavailableError):
        tot.emergency_flatten()
    assert tot.is_halted() is True


def test_notaus_bleibt_reduce_only_und_umgeht_keine_sperre_nach_oben() -> None:
    """Der Not-Aus baut nur ab: jede gesendete Order traegt ``reduce_only``.

    Gegenprobe gegen die naheliegende Verschlimmbesserung, den Not-Aus zu einem
    allgemeinen Sendepfad zu machen.
    """
    venue, terminal = _venue((_position("p1", "0.30"),))
    venue.emergency_flatten()
    assert all(req["reduce_only"] is True for req in terminal.gesendet)

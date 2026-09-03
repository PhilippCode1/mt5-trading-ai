"""Ein Rueckgabecode ist keine Messung der Wirkung (E10.2, E10.3).

WARUM DIESER TEST
-----------------
Der Schreibpfad des realen Terminals stellte an drei Stellen dieselbe falsche Frage:
"was hat der Server geantwortet?" statt "was steht danach in der Welt?".

**E10.2 -- ``TRADE_RETCODE_PLACED`` galt als Fill.** ``_send_angenommen`` nahm DONE
(10009), PLACED (10008) und DONE_PARTIAL (10010) als Erfolg, und ``order_send``
buchte daraufhin ``res.volume`` als Fuellvolumen. 10008 heisst aber "Pending-Order
angelegt", nicht "ausgefuehrt"; ``res.volume`` spiegelt dabei das Anfragevolumen.
Das lokale Buch fuehrte danach eine Position, die es beim Broker nicht gibt -- und
``reconcile()`` latchte bei ``max_notional_drift=0`` den Global-Halt, obwohl nichts
schiefgelaufen war. Es ist der Spiegelfehler zu dem, den ``_send_angenommen``
ueberhaupt erst beheben sollte.

**E10.3 -- ``cancel`` und ``modify_stops`` benutzten die widerlegte Regel.** Beide
prueften allein auf ``TRADE_RETCODE_DONE``. Zwanzig Zeilen darueber steht mit
Messdatum, dass dieser Broker bei Erfolg ``retcode=0`` mit ``comment='Done'`` liefert
und dass eine Pruefung allein auf 10009 "die gefaehrlichste Fehlrichtung" ist. Ein
tatsaechlich verschobener Stop galt damit als nicht verschoben.

WAS ANSTELLE DESSEN GEPRUEFT WIRD
---------------------------------
Der Rueckgabecode bleibt Vorfilter -- ein benannter Fehlercode ist ein Fehler. Die
Aussage traegt die **Gegenprobe**: nach dem Storno darf die Order nicht mehr in
``orders_get`` stehen, nach der Stop-Aenderung muss die Position den neuen Stop
melden. Damit faellt beides weg, das falsch Negative (Erfolg als Fehlschlag gelesen)
und das falsch Positive (Server sagt "Done" und tut nichts).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.venue.mt5 import RealMt5Terminal, _send_angenommen  # noqa: E402
from mt5_trading_ai.venue.protocol import VenueUnavailableError  # noqa: E402

DONE = 10009
PLACED = 10008
DONE_PARTIAL = 10010


@dataclass
class _Ergebnis:
    """Was ``MetaTrader5.order_send`` zurueckgibt -- so viel davon, wie angefasst wird."""

    retcode: int
    order: int = 0
    deal: int = 0
    volume: float = 0.0
    price: float = 0.0
    comment: str = "Done"


@dataclass
class _Mt5Attrappe:
    """Nur so viel MetaTrader5, wie der Schreibpfad anfasst.

    ``orders_get`` und ``positions_get`` sind hier das Interessante: sie liefern die
    Welt NACH der Anfrage, und genau die will der reparierte Code lesen. Ihre
    Antworten sind je Test frei setzbar -- auch als ``None``, denn MetaTrader
    unterscheidet damit "Abfrage fehlgeschlagen" von "nichts gefunden".
    """

    antwort: Any = None
    orders: Any = ()
    positionen: Any = ()
    punkt: float = 0.00001
    fuellmaske: int = 1
    gesendet: list[dict[str, Any]] = field(default_factory=list)
    orders_abfragen: int = 0
    positionen_abfragen: int = 0

    TRADE_RETCODE_DONE = DONE
    TRADE_RETCODE_PLACED = PLACED
    TRADE_RETCODE_DONE_PARTIAL = DONE_PARTIAL
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_REMOVE = 7
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    ACCOUNT_TRADE_MODE_DEMO = 0
    POSITION_TYPE_BUY = 0

    def account_info(self) -> Any:
        return SimpleNamespace(
            login=4242,
            currency="EUR",
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            margin_free=10000.0,
            trade_mode=0,  # Demo -- sonst greift die Schreibpfad-Klammer
            leverage=30,
        )

    def symbol_info(self, name: str) -> Any:
        return SimpleNamespace(filling_mode=self.fuellmaske, point=self.punkt)

    def symbol_info_tick(self, name: str) -> Any:
        return SimpleNamespace(bid=1.09990, ask=1.10000, time=1786000000)

    def order_send(self, req: Any) -> Any:
        self.gesendet.append(dict(req))
        return self.antwort

    def orders_get(self, ticket: int = 0) -> Any:
        self.orders_abfragen += 1
        return self.orders

    def positions_get(self, ticket: int = 0, symbol: str | None = None) -> Any:
        self.positionen_abfragen += 1
        return self.positionen


def _terminal(attrappe: _Mt5Attrappe) -> RealMt5Terminal:
    echt = RealMt5Terminal(allow_write=True)
    echt._mt5 = attrappe  # type: ignore[assignment]
    return echt


def _marktauftrag() -> dict[str, Any]:
    return {
        "client_order_id": "w-1",
        "symbol": "EURUSD",
        "side": "buy",
        "order_type": "market",
        "volume": Decimal("0.11"),
        "stop_loss": Decimal("1.09000"),
        "take_profit": None,
        "limit_price": None,
        "reduce_only": False,
        "comment": "",
    }


def _position(*, sl: float, tp: float = 0.0) -> Any:
    return SimpleNamespace(ticket=777, symbol="EURUSD", sl=sl, tp=tp)


class _AttrappeMitBlinderSymbolabfrage(_Mt5Attrappe):
    """Die globale Positionsabfrage traegt, die symbolgefilterte scheitert.

    Das ist kein konstruierter Fall: ``positions_get(symbol=...)`` ist bei MetaTrader
    ein eigener Aufruf mit eigenem Ausgang, und ``None`` heisst dort
    "Abfrage fehlgeschlagen", nicht "nichts gefunden".
    """

    def positions_get(self, ticket: int = 0, symbol: str | None = None) -> Any:
        self.positionen_abfragen += 1
        if symbol is not None:
            return None
        return self.positionen


# =========================================================================== #
# E10.2 -- angelegt ist nicht gefuellt                                         #
# =========================================================================== #
def test_placed_ist_angenommen_aber_nicht_gefuellt() -> None:
    """Der rote Eichfall von E10.2.

    Gegen die alte Fassung stand hier ``filled_volume == 0.11`` -- das Anfragevolumen,
    als Fill verbucht. Damit fuehrte das Buch eine Position, die es nicht gibt.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=PLACED, order=555, volume=0.11, price=1.10000)
    )
    ergebnis = _terminal(attrappe).order_send(_marktauftrag())
    assert ergebnis.accepted is True, (
        "Die Order LIEGT beim Broker. Sie als Fehlschlag zu behandeln hinterliesse "
        "eine Order, von der das System nichts weiss und die es nie stornieren kann."
    )
    assert ergebnis.filled_volume == Decimal("0"), (
        "Eine angelegte Pending-Order hat nichts gefuellt. res.volume ist hier das "
        "Anfrage-, nicht das Fuellvolumen."
    )
    assert ergebnis.average_price is None, (
        "Ohne Ausfuehrung gibt es keinen Ausfuehrungspreis."
    )
    assert ergebnis.venue_order_id == "555", (
        "Die Kennung muss erhalten bleiben -- sonst ist die Order nicht stornierbar."
    )
    assert "placed" in ergebnis.reason


def test_done_bleibt_ein_fill() -> None:
    """Gegenprobe: ein echter Fill muss weiter als Fill gebucht werden.

    Ohne sie liesse sich der Test darueber bestehen, indem nie etwas gebucht wird --
    und das war der urspruengliche Fehler dieses Pfades, der einen Global-Halt kostete.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE, order=555, deal=9, volume=0.11, price=1.10000)
    )
    ergebnis = _terminal(attrappe).order_send(_marktauftrag())
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0.11")
    assert ergebnis.average_price == Decimal("1.1")
    assert ergebnis.reason == "done"


def test_der_gemessene_retcode_null_bleibt_ein_fill() -> None:
    """Der reale Fall vom 2026-08-17: ausgefuehrt, aber retcode 0."""
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(
            retcode=0, order=10057432438, deal=9759135343, volume=0.11, price=1.15878
        )
    )
    ergebnis = _terminal(attrappe).order_send(_marktauftrag())
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0.11")


def test_teilfuellung_bucht_den_bestaetigten_teil() -> None:
    """``DONE_PARTIAL``: ``res.volume`` ist der bestaetigte Teil, nicht der Wunsch."""
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(
            retcode=DONE_PARTIAL, order=555, deal=9, volume=0.05, price=1.10000
        )
    )
    ergebnis = _terminal(attrappe).order_send(_marktauftrag())
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0.05")


def test_placed_ohne_kennung_scheitert_laut() -> None:
    """Der einzige Ausgang, den dieses System nicht sauber halten kann.

    Eine angelegte Order ohne Kennung liegt beim Broker, kann jederzeit fuellen, und
    ``cancel`` haette nichts, worauf es zeigen koennte. Still weiterlaufen waere die
    schlimmste der drei Moeglichkeiten.
    """
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=PLACED, order=0, volume=0.11))
    with pytest.raises(VenueUnavailableError) as fehler:
        _terminal(attrappe).order_send(_marktauftrag())
    assert "Pending-Order" in str(fehler.value)


def test_echter_fehlercode_bleibt_eine_ablehnung() -> None:
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=10019, order=1, volume=0.11, comment="No money")
    )
    ergebnis = _terminal(attrappe).order_send(_marktauftrag())
    assert ergebnis.accepted is False
    assert ergebnis.filled_volume == Decimal("0")
    assert ergebnis.venue_order_id is None
    assert "10019" in ergebnis.reason


# --- die Unterscheidung selbst, ohne Terminal ------------------------------
def _gefuellt(mt5: Any, res: Any) -> bool:
    """``_send_gefuellt`` erst im Test importieren, nicht beim Modulimport.

    Nicht Kosmetik: ein fehlender Name ganz oben laesst die ganze Datei beim Sammeln
    scheitern, und dann ist der Nachweis "waere rot gewesen" nur noch ein Importfehler
    statt einer Messung je Fall. Die Verhaltenstests darueber laufen ueber
    ``order_send``/``cancel``/``modify_stops`` und brauchen den Namen nicht -- sie
    sollen einzeln messbar bleiben.
    """
    from mt5_trading_ai.venue.mt5 import _send_gefuellt

    return _send_gefuellt(mt5, res)


def test_gefuellt_und_angenommen_sind_verschiedene_fragen() -> None:
    """PLACED ist der einzige Code, bei dem beide auseinanderfallen -- deshalb gibt es
    ueberhaupt zwei Funktionen."""
    mt5: Any = _Mt5Attrappe()
    res = _Ergebnis(retcode=PLACED, order=1, deal=0, volume=0.11)
    assert _send_angenommen(mt5, res) is True
    assert _gefuellt(mt5, res) is False


@pytest.mark.parametrize("code", [DONE, DONE_PARTIAL])
def test_ausfuehrungscodes_gelten_als_gefuellt(code: int) -> None:
    mt5: Any = _Mt5Attrappe()
    assert _gefuellt(mt5, _Ergebnis(retcode=code, order=1, volume=0.1)) is True


def test_ohne_volumen_ist_nichts_gefuellt() -> None:
    """Auch ein Erfolgscode buchte sonst eine Position der Groesse null."""
    mt5: Any = _Mt5Attrappe()
    assert _gefuellt(mt5, _Ergebnis(retcode=DONE, order=1, volume=0.0)) is False


def test_keine_antwort_ist_nicht_gefuellt() -> None:
    mt5: Any = _Mt5Attrappe()
    assert _gefuellt(mt5, None) is False


# =========================================================================== #
# Dieselbe None-Falle, zwei gegensaetzliche Antworten in EINER Funktion        #
# =========================================================================== #
def test_schliessung_ohne_abfragbaren_positionsbestand_wird_nicht_gesendet() -> None:
    """DER ROTE EICHFALL DES REDUCE-ONLY-PFADS.

    ``order_send`` behandelt ``positions_get() is None`` fail-closed und begruendet
    das ausdruecklich mit "dieselbe Falle wie ueberall sonst in diesem Modul". 56
    Zeilen spaeter stand fuer denselben Aufruf ``mt5.positions_get(symbol=symbol) or
    ()``: ein Abfragefehler wurde still zu "keine Position", ``req['position']`` blieb
    leer -- und auf einem Hedging-Konto macht der Broker aus der Schliessung eine
    NEUE Gegenposition.

    Das ist der Reduce-Only-Pfad. Die schmeichelnde Richtung baut hier Risiko AUF,
    wo Risiko abgebaut werden sollte. Gegen HEAD wird gesendet, und zwar ohne
    Positions-Ticket.
    """
    auftrag = _marktauftrag()
    auftrag["reduce_only"] = True
    auftrag["side"] = "sell"
    attrappe = _AttrappeMitBlinderSymbolabfrage(antwort=_Ergebnis(retcode=DONE))

    with pytest.raises(VenueUnavailableError):
        _terminal(attrappe).order_send(auftrag)

    assert attrappe.gesendet == [], (
        "Es wurde eine Schliessung ohne Positions-Ticket gesendet. Auf einem "
        "Hedging-Konto ist das eine zweite, gegenlaeufige Position -- mehr Risiko "
        "statt weniger."
    )


def test_schliessung_mit_abfragbarem_bestand_traegt_das_ticket() -> None:
    """Gegenprobe: der Normalfall setzt weiterhin das Ticket der Gegenposition."""
    auftrag = _marktauftrag()
    auftrag["reduce_only"] = True
    auftrag["side"] = "sell"
    auftrag["position_ticket"] = "777"  # D2: Schliessung nur mit Ticket
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE, order=555, volume=0.11),
        positionen=(SimpleNamespace(ticket=777, type=0, symbol="EURUSD"),),
    )
    _terminal(attrappe).order_send(auftrag)
    assert attrappe.gesendet[0]["position"] == 777


# =========================================================================== #
# E10.3 -- Storno und Stop-Aenderung: nachmessen statt ablesen                 #
# =========================================================================== #
def test_storno_mit_retcode_null_gilt_als_storniert() -> None:
    """Roter Eichfall E10.3a: der gemessene Erfolgscode dieses Brokers.

    Gegen die alte Fassung (nur 10009) war das ein Fehlschlag -- eine tatsaechlich
    stornierte Order galt als noch liegend.
    """
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=0), orders=())
    assert _terminal(attrappe).cancel("555") is True


def test_storno_das_nichts_bewirkt_gilt_nicht_als_storniert() -> None:
    """Roter Eichfall E10.3b: der Server sagt "Done", die Order liegt noch.

    Gegen die alte Fassung war das ein Erfolg -- der Rueckgabecode allein sagt nichts
    ueber den Zustand danach.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE), orders=(SimpleNamespace(ticket=555),)
    )
    assert _terminal(attrappe).cancel("555") is False


def test_storno_bei_abfragefehler_ist_kein_beleg() -> None:
    """``orders_get`` gibt bei einem FEHLER ``None`` -- nicht dasselbe wie "ist weg".

    Dieselbe Verwechslung, die bei ``positions_get`` schon einmal beinahe alle offenen
    Positionen als geschlossen verbucht haette.
    """
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=DONE), orders=None)
    assert _terminal(attrappe).cancel("555") is False


def test_storno_mit_fehlercode_fragt_gar_nicht_erst_nach() -> None:
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=10013, comment="Invalid request"))
    assert _terminal(attrappe).cancel("555") is False
    assert attrappe.orders_abfragen == 0


def test_storno_mit_done_und_leerem_buch_ist_gruen() -> None:
    """Gegenprobe: der dokumentierte Erfolgsfall bleibt ein Erfolg."""
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=DONE), orders=())
    assert _terminal(attrappe).cancel("555") is True
    assert attrappe.orders_abfragen == 1


def test_gefuellte_order_gilt_nicht_als_storniert() -> None:
    """DER ROTE EICHFALL DES ZWEITEN BESTANDES.

    Aus ``orders_get`` verschwindet ein Auftrag auf zwei voellig verschiedenen Wegen:
    er wurde storniert -- oder er wurde **gefuellt**. Wer nur die Auftragsliste
    liest, meldet fuer beides ``True``.

    Das ist die gefaehrliche Richtung, und zwar die gefaehrlichste dieses Moduls: das
    System glaubt, es sei kein Risiko offen, waehrend eine Position steht. Der
    Docstring erklaerte den falsch positiven Fall bereits fuer erledigt ("nach dem
    Storno darf der Auftrag nicht mehr in ``orders_get`` stehen") -- die Messung
    loeste die Zusage nicht ein.

    Gegen HEAD lautet die Antwort hier ``True``.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE),
        orders=(),  # aus der Auftragsliste ist sie weg ...
        positionen=(_position(sl=1.08000),),  # ... weil sie ausgefuehrt wurde
    )
    assert _terminal(attrappe).cancel("555") is False, (
        "Die Order ist nicht storniert, sondern gefuellt worden. Ein 'True' hier "
        "laesst den Betrieb eine offene Position fuer erledigt halten."
    )


def test_storno_bei_unlesbarem_positionsbestand_ist_kein_beleg() -> None:
    """Dieselbe None-Falle, dieselbe Antwort: nicht messbar heisst nicht belegt."""
    attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=DONE), orders=(), positionen=None)
    assert _terminal(attrappe).cancel("555") is False


def test_stop_mit_retcode_null_gilt_als_verschoben() -> None:
    """Roter Eichfall E10.3c: ein tatsaechlich verschobener Stop.

    Gegen die alte Fassung galt er als nicht verschoben -- der Betrieb haette den
    Stop endlos nachgezogen oder den Griff fuer verloren gehalten.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=0), positionen=(_position(sl=1.08000),)
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), None) is True


def test_stop_der_nicht_steht_gilt_nicht_als_verschoben() -> None:
    """Roter Eichfall E10.3d: Server sagt "Done", der Stop steht noch beim alten Wert.

    Die gefaehrlichere Richtung: das System glaubte, sein Risiko sei begrenzt.
    """
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE), positionen=(_position(sl=1.05000),)
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), None) is False


def test_stop_ohne_position_ist_kein_beleg() -> None:
    """Position weg (Stop lief ins Ziel, Handschliessung) oder Abfrage fehlgeschlagen.

    Beides heisst: die Aussage "der Stop steht bei X" ist nicht belegt.
    """
    for antwort in ((), None):
        attrappe = _Mt5Attrappe(antwort=_Ergebnis(retcode=DONE), positionen=antwort)
        echt = _terminal(attrappe)
        assert echt.modify_stops("777", Decimal("1.08000"), None) is False


def test_toleranz_ist_genau_ein_point() -> None:
    """Rundung des Brokers ja, echte Abweichung nein.

    Ohne Toleranz waere die Pruefung dauerrot (jede Preisdarstellung rundet); mit
    grosszuegiger Toleranz waere sie blind fuer einen auf das ``stops_level``
    gezogenen Stop. Ein Point ist die kleinste Stufe, die der Broker darstellen kann.
    """
    for gemeldet, erwartet in ((1.08001, True), (1.08003, False)):
        attrappe = _Mt5Attrappe(
            antwort=_Ergebnis(retcode=DONE), positionen=(_position(sl=gemeldet),)
        )
        echt = _terminal(attrappe)
        assert echt.modify_stops("777", Decimal("1.08000"), None) is erwartet


def test_nicht_angefragte_seite_wird_nicht_geprueft() -> None:
    """``None`` heisst "nicht anfassen". Wer nichts wollte, bekommt kein Rot dafuer."""
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE), positionen=(_position(sl=1.08000, tp=0.0),)
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), None) is True


def test_take_profit_wird_ebenso_nachgemessen() -> None:
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE), positionen=(_position(sl=1.08000, tp=1.20000),)
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), Decimal("1.20000")) is True
    attrappe2 = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE), positionen=(_position(sl=1.08000, tp=1.30000),)
    )
    echt2 = _terminal(attrappe2)
    assert echt2.modify_stops("777", Decimal("1.08000"), Decimal("1.20000")) is False


def test_stop_mit_fehlercode_fragt_gar_nicht_erst_nach() -> None:
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=10016, comment="Invalid stops"),
        positionen=(_position(sl=1.08000),),
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), None) is False
    # D2/V2b: EINE Abfrage vor dem Senden (aktuelle Stops lesen, damit ``None``
    # "nicht anfassen" heisst) -- aber KEINE Nachlesung nach dem Fehlercode.
    assert attrappe.positionen_abfragen == 1


def test_ohne_bekannte_preisstufe_kein_beleg() -> None:
    """Ohne ``point`` gibt es keine Toleranz und damit keinen zulaessigen Vergleich."""
    attrappe = _Mt5Attrappe(
        antwort=_Ergebnis(retcode=DONE),
        positionen=(_position(sl=1.08000),),
        punkt=0.0,
    )
    echt = _terminal(attrappe)
    assert echt.modify_stops("777", Decimal("1.08000"), None) is False


# =========================================================================== #
# Die Folge, um die es bei E10.2 wirklich ging                                 #
# =========================================================================== #
def test_angelegte_order_erzeugt_keine_geisterposition() -> None:
    """Verhaltensklammer: ein Fill von null laesst Buch und Reconcile in Ruhe.

    Das ist die Kette, an deren Ende der falsche Global-Halt stand: Fill gebucht ->
    Buch fuehrt eine Position -> ``reconcile()`` sieht sie beim Broker nicht ->
    Drift ueber ``max_notional_drift=0`` -> Latch. Mit Fuellvolumen null reisst sie.
    """
    from decimal import Decimal as D

    from mt5_trading_ai.venue.mt5 import Mt5SendResult, Mt5Venue

    from test_mt5_venue import TS, FakeMt5Terminal, _catalog, _fresh_risk

    class _NurAngelegt(FakeMt5Terminal):
        def order_send(self, request: object) -> Mt5SendResult:
            self.order_send_calls += 1
            return Mt5SendResult(
                accepted=True,
                venue_order_id="V-1",
                filled_volume=D("0"),
                average_price=None,
                ts=TS,
                reason="placed_pending (retcode=10008)",
            )

    terminal = _NurAngelegt(is_demo=True)
    venue = Mt5Venue(
        name="placed",
        terminal=terminal,
        catalog=_catalog(),
        risk_manager=_fresh_risk(),
        clock=lambda: TS,
    )
    venue.connect()
    from mt5_trading_ai.venue.protocol import OrderRequest, OrderSide, OrderType

    ergebnis = venue.submit_order(
        OrderRequest(
            client_order_id="p-1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            volume=D("0.01"),
            stop_loss=D("1.09000"),
            meta={"requested_leverage": 5},
        )
    )
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == D("0")
    assert venue.book_snapshot() == {}, (
        "Das Buch fuehrt eine Position aus einer Order, die nur angelegt wurde."
    )
    assert venue.reconcile().halt is False
    assert venue.is_halted() is False

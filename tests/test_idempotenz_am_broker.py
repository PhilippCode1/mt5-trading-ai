"""E10.4 -- die Idempotenz lag nur im Arbeitsspeicher.

WARUM DIESER TEST
-----------------
``Mt5Venue._results`` ist ein ``dict`` im Prozessgedaechtnis, und der Eintrag entstand
erst NACH einer angenommenen Antwort. Am Auftrag selbst stand nichts: der MT5-Request
trug weder ``magic`` noch die ``client_order_id`` im Kommentar. Beim Broker lag damit
**kein einziges Merkmal**, an dem eine Wiederholung zu erkennen gewesen waere.

Drei Ausgaenge erzeugten dadurch eine zweite ECHTE Order:

* ein Zeitablauf (die Antwort kam nie, der Eintrag entstand nicht),
* ein Neustart (das Verzeichnis ist leer),
* ein zweiter Runner (er hat sein eigenes Verzeichnis).

Ein Verzeichnis, das genau in den Faellen leer ist, fuer die es gebaut wurde, ist
keine Idempotenz. Es ist eine Beschleunigung des Normalfalls.

WAS ANSTELLE DESSEN GEPRUEFT WIRD
---------------------------------
Die Kennung liegt jetzt als ``magic`` **beim Broker**, und ``order_send`` fragt die
beiden Bestaende (offene Positionen, liegende Auftraege) BEVOR es sendet. Ist die
Marke schon da, wird nicht gesendet. Ist der Bestand nicht abfragbar, wird ebenfalls
nicht gesendet -- eine unbeantwortete Frage ist keine bestandene Pruefung.

MESSUNG GEGEN HEAD
------------------
Die Datei importiert auf Modulebene nur Namen, die es in BEIDEN Fassungen gibt.
``kennmarke`` und ``idempotent_replay`` werden erst IM Test gesucht, damit die Datei
gegen HEAD sammelt und mit echten Assertions faellt statt mit einem ImportError.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.venue.catalog import CatalogEntry  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
    Mt5Venue,
    RealMt5Terminal,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AssetClass,
    FeeSchedule,
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    TradingSession,
    VenueUnavailableError,
)

DONE = 10009
TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


# =========================================================================== #
# Attrappe des MetaTrader5-Moduls                                             #
# =========================================================================== #
@dataclass
class _Ergebnis:
    retcode: int = DONE
    order: int = 4711
    deal: int = 8822
    volume: float = 0.10
    price: float = 1.10000
    comment: str = "Done"


@dataclass
class _Mt5Attrappe:
    """Nur so viel MetaTrader5, wie der Schreibpfad anfasst.

    ``positionen`` und ``auftraege`` sind die beiden Bestaende, in denen ein bereits
    gesendeter Auftrag stehen kann. ``None`` heisst dort -- wie beim echten
    MetaTrader -- **Abfrage fehlgeschlagen**, nicht "nichts gefunden".
    """

    antwort: Any = field(default_factory=_Ergebnis)
    positionen: Any = ()
    auftraege: Any = ()
    gesendet: list[dict[str, Any]] = field(default_factory=list)

    TRADE_RETCODE_DONE = DONE
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_DONE_PARTIAL = 10010
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
        return SimpleNamespace(filling_mode=1, point=0.00001)

    def symbol_info_tick(self, name: str) -> Any:
        return SimpleNamespace(bid=1.09990, ask=1.10000, time=1786000000)

    def order_send(self, req: Any) -> Any:
        self.gesendet.append(dict(req))
        return self.antwort

    def orders_get(self, ticket: int = 0) -> Any:
        return self.auftraege

    def positions_get(self, ticket: int = 0, symbol: str | None = None) -> Any:
        return self.positionen


def _terminal(attrappe: _Mt5Attrappe) -> RealMt5Terminal:
    """Ein Terminal ohne jedes Prozessgedaechtnis -- wie nach einem Neustart."""
    echt = RealMt5Terminal(allow_write=True)
    echt._mt5 = attrappe  # type: ignore[assignment]
    return echt


def _auftrag(kennung: str = "o-1") -> dict[str, Any]:
    return {
        "client_order_id": kennung,
        "symbol": "EURUSD",
        "side": "buy",
        "order_type": "market",
        "volume": Decimal("0.10"),
        "stop_loss": Decimal("1.09000"),
        "take_profit": None,
        "limit_price": None,
        "reduce_only": False,
        "comment": "",
    }


def _marke_des_gesendeten(attrappe: _Mt5Attrappe) -> int:
    """Die Marke, die tatsaechlich am Auftrag stand. Gegen HEAD: keine (0)."""
    return int(attrappe.gesendet[0].get("magic", 0) or 0)


# =========================================================================== #
# Der rote Eichfall                                                           #
# =========================================================================== #
def test_wiederholung_nach_neustart_sendet_keine_zweite_order() -> None:
    """DER ROTE EICHFALL VON E10.4.

    Erst wird gesendet, dann steht die Position beim Broker. Ein **neuer** Prozess
    (neues Terminal, leeres Verzeichnis) sendet dieselbe Kennung erneut -- genau der
    Ablauf nach einem Zeitablauf oder einem Neustart.

    Gegen HEAD ging der zweite Aufruf ungebremst durch: ``len(gesendet) == 2``, also
    zwei echte Orders am Markt fuer einen gewollten Auftrag.
    """
    attrappe = _Mt5Attrappe()
    _terminal(attrappe).order_send(_auftrag())
    assert len(attrappe.gesendet) == 1

    # Der Broker fuehrt die Position jetzt -- mit der Marke des Auftrags.
    attrappe.positionen = (
        SimpleNamespace(ticket=4711, magic=_marke_des_gesendeten(attrappe)),
    )
    ergebnis = _terminal(attrappe).order_send(_auftrag())

    assert len(attrappe.gesendet) == 1, (
        "Die zweite Anfrage wurde gesendet, obwohl der Auftrag beim Broker bereits "
        "liegt. Genau so entsteht aus einem Zeitablauf eine doppelte Position."
    )
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0"), (
        "Ein Wiedergaenger hat nichts gefuellt. Das Volumen der alten Ausfuehrung "
        "hier zu wiederholen buchte dieselbe Position ein zweites Mal ins Buch."
    )


def test_der_auftrag_traegt_seine_kennung_beim_broker() -> None:
    """Ohne Merkmal am Auftrag ist keine Wiedererkennung moeglich -- egal wo geprueft.

    Gegen HEAD stand im Request weder ``magic`` noch die Kennung im Kommentar.
    """
    attrappe = _Mt5Attrappe()
    _terminal(attrappe).order_send(_auftrag("o-42"))
    gesendet = attrappe.gesendet[0]
    assert int(gesendet.get("magic", 0) or 0) != 0, (
        "Der Auftrag liegt anonym beim Broker. Nach einem Neustart ist die Frage "
        "'habe ich den schon gesendet?' damit nicht mehr beantwortbar."
    )
    assert "o-42" in str(gesendet.get("comment", "")), (
        "Der Kommentar ist die lesbare Spur fuer den Menschen im Terminal."
    )


def test_verschiedene_kennungen_bekommen_verschiedene_marken() -> None:
    """Sonst blockte der erste Auftrag jeden weiteren -- die Sperre waere Dauer-Rot."""
    marken = set()
    for kennung in ("o-1", "o-2", "fl-1-p1", "smoke-open"):
        attrappe = _Mt5Attrappe()
        _terminal(attrappe).order_send(_auftrag(kennung))
        marken.add(_marke_des_gesendeten(attrappe))
    assert len(marken) == 4


def test_die_marke_ueberlebt_den_prozesswechsel() -> None:
    """Die Marke muss in einem ZWEITEN Prozess dieselbe sein.

    Das ist keine Formalie: Pythons eingebautes ``hash()`` ist je Prozess gesalzen.
    Eine darauf gebaute Marke waere in genau dem Fall wertlos, fuer den sie existiert
    -- dem Neustart. Gemessen wird darum in einem echten Unterprozess, nicht behauptet.
    """
    from mt5_trading_ai.venue.mt5 import kennmarke

    hier = kennmarke("o-1")
    lauf = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mt5_trading_ai.venue.mt5 import kennmarke; print(kennmarke('o-1'))",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert int(lauf.stdout.strip()) == hier


def test_die_marke_ist_nie_null() -> None:
    """``magic=0`` ist der Normalfall jeder fremden, handgestellten Order.

    Eine Kennung, die auf 0 abbildet, wuerde jede handgestellte Position als eigenen
    Wiedergaenger lesen und den naechsten Auftrag stillschweigend unterdruecken.
    """
    from mt5_trading_ai.venue.mt5 import kennmarke

    assert all(kennmarke(k) != 0 for k in ("", "0", "o-1", "x" * 200))


# =========================================================================== #
# Fail-closed: eine unbeantwortete Frage ist keine bestandene Pruefung          #
# =========================================================================== #
@pytest.mark.parametrize("bestand", ["positionen", "auftraege"])
def test_ohne_abfragbaren_bestand_wird_nicht_gesendet(bestand: str) -> None:
    """``None`` heisst bei MetaTrader "Abfrage fehlgeschlagen", nicht "nichts da".

    Trotzdem zu senden hiesse, die Doppelorder in Kauf zu nehmen, gegen die die
    Pruefung gebaut ist.
    """
    attrappe = _Mt5Attrappe(**{bestand: None})
    with pytest.raises(VenueUnavailableError):
        _terminal(attrappe).order_send(_auftrag())
    assert attrappe.gesendet == []


def test_liegender_auftrag_wird_ebenso_erkannt() -> None:
    """Nicht nur ausgefuehrt: auch eine angelegte Pending-Order ist schon da."""
    from mt5_trading_ai.venue.mt5 import kennmarke

    attrappe = _Mt5Attrappe(
        auftraege=(SimpleNamespace(ticket=999, magic=kennmarke("o-1")),)
    )
    ergebnis = _terminal(attrappe).order_send(_auftrag("o-1"))
    assert attrappe.gesendet == []
    assert ergebnis.venue_order_id == "999"


# =========================================================================== #
# Gegenproben: die Sperre darf nicht alles blocken                            #
# =========================================================================== #
def test_leerer_bestand_sendet_wirklich() -> None:
    """Ohne diese Gegenprobe waere "sperrt immer" von "sperrt richtig" ununterscheidbar."""
    attrappe = _Mt5Attrappe()
    ergebnis = _terminal(attrappe).order_send(_auftrag())
    assert len(attrappe.gesendet) == 1
    assert ergebnis.accepted is True
    assert ergebnis.filled_volume == Decimal("0.10")


def test_fremde_marke_blockt_nicht() -> None:
    """Die Position eines anderen Auftrags darf diesen hier nicht unterdruecken."""
    attrappe = _Mt5Attrappe(positionen=(SimpleNamespace(ticket=1, magic=123456789),))
    _terminal(attrappe).order_send(_auftrag("o-1"))
    assert len(attrappe.gesendet) == 1


def test_handgestellte_position_ohne_marke_blockt_nicht() -> None:
    """Eine Position mit ``magic=0`` stammt nicht von diesem System."""
    attrappe = _Mt5Attrappe(positionen=(SimpleNamespace(ticket=1, magic=0),))
    _terminal(attrappe).order_send(_auftrag("o-1"))
    assert len(attrappe.gesendet) == 1


# =========================================================================== #
# Wirkung am Venue                                                            #
# =========================================================================== #
def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


class _VenueTerminal:
    """Terminal fuer den Venue-Pfad. ``antwort`` ist frei setzbar, auch als Ausnahme.

    ``positionen`` ist der Bestand BEIM BROKER. Er ueberlebt jeden Prozesswechsel --
    anders als ``Mt5Venue._results`` und anders als der ``RiskManager``. Genau darum
    ist er die einzige Quelle, an der sich nach einem Neustart noch feststellen
    laesst, ob die gewollte Position schon existiert.
    """

    def __init__(self, antwort: Any, positionen: tuple[Mt5Position, ...] = ()) -> None:
        self._antwort = antwort
        self._verbunden = False
        self.sendeversuche = 0
        self.positionen = positionen

    def initialize(self) -> bool:
        self._verbunden = True
        return True

    def shutdown(self) -> None:
        self._verbunden = False

    def is_connected(self) -> bool:
        return self._verbunden

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (self._eurusd(),)

    def _eurusd(self) -> Mt5Symbol:
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

    def symbol(self, name: str) -> Mt5Symbol | None:
        return self._eurusd() if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        return Mt5Tick(ts=TS, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return ()

    def order_send(self, request: Any) -> Mt5SendResult:
        self.sendeversuche += 1
        if isinstance(self._antwort, Exception):
            raise self._antwort
        return self._antwort  # type: ignore[no-any-return]

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
        return self.positionen

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


def _venue_auf(terminal: _VenueTerminal) -> Mt5Venue:
    """Ein FRISCHER Venue auf einem bestehenden Broker-Zustand -- also ein Neustart.

    Neues ``_results``, neuer ``RiskManager`` (und damit keine Drossel-Erinnerung),
    derselbe Broker. Das ist der Zustand, in dem eine Doppelorder entsteht.
    """
    from mt5_trading_ai.execution.risk_manager import RiskManager

    sessions = tuple(
        TradingSession(weekday=tag, open_utc="00:00", close_utc="22:00")
        for tag in range(5)
    )
    venue = Mt5Venue(
        name="mt5-test",
        terminal=terminal,  # type: ignore[arg-type]
        catalog={"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions)},
        risk_manager=RiskManager(),
        clock=lambda: TS,
    )
    venue.connect()
    return venue


def _venue(antwort: Any) -> tuple[Mt5Venue, _VenueTerminal]:
    terminal = _VenueTerminal(antwort)
    return _venue_auf(terminal), terminal


def _stehende_position(
    ticket: str = "4711", *, ist_kauf: bool = True, volumen: str = "0.01"
) -> Mt5Position:
    return Mt5Position(
        ticket=ticket,
        symbol="EURUSD",
        is_buy=ist_kauf,
        volume=Decimal(volumen),
        entry_price=Decimal("1.10000"),
        stop_loss=Decimal("1.09000"),
        take_profit=None,
        opened_at=TS,
        unrealised_pnl=Decimal("0"),
        swap=Decimal("0"),
    )


def _gefuellt() -> Mt5SendResult:
    return Mt5SendResult(
        accepted=True,
        venue_order_id="4711",
        filled_volume=Decimal("0.01"),
        average_price=Decimal("1.10000"),
        ts=TS,
        reason="done",
    )


def _order(kennung: str = "o-1") -> OrderRequest:
    return OrderRequest(
        client_order_id=kennung,
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("1.09000"),
        meta={"requested_leverage": 5},
    )


def test_wiedergaenger_wird_nicht_ein_zweites_mal_gebucht() -> None:
    """Meldet das Terminal einen Wiedergaenger, entsteht im Buch nichts Neues.

    Gegen HEAD ist dieser Fall nicht einmal ausdrueckbar: ``Mt5SendResult`` kannte
    kein Feld dafuer, ein Wiedergaenger war von einem Erstfill nicht zu
    unterscheiden -- und wurde folglich wie einer gebucht.
    """
    if not any(f.name == "idempotent_replay" for f in fields(Mt5SendResult)):
        pytest.fail(
            "Mt5SendResult kennt kein 'idempotent_replay': ein bereits beim Broker "
            "liegender Auftrag ist von einer frischen Fuellung nicht unterscheidbar."
        )
    venue, terminal = _venue(
        Mt5SendResult(
            accepted=True,
            venue_order_id="4711",
            filled_volume=Decimal("0"),
            average_price=None,
            ts=TS,
            reason="bereits_beim_broker",
            idempotent_replay=True,
        )
    )
    ergebnis = venue.submit_order(_order())
    assert ergebnis.accepted is True
    assert ergebnis.idempotent_replay is True
    assert ergebnis.venue_order_id == "4711"
    assert venue.book_snapshot() == {}, (
        "Ein Wiedergaenger hat nichts ausgefuehrt. Ihn zu buchen erzeugte eine "
        "Geisterposition -- denselben Fehler, den PLACED schon einmal erzeugt hat."
    )


def test_sendeversuch_ohne_antwort_haelt_die_maschine_an() -> None:
    """Ein Zeitablauf ist nicht "nichts geschehen", sondern "Ausgang unbekannt".

    Gegen HEAD lief die Ausnahme einfach nach oben durch: kein Halt, kein Vermerk.
    Der naechste Durchlauf eroeffnete munter weiter, waehrend beim Broker
    moeglicherweise eine Position stand.
    """
    venue, terminal = _venue(VenueUnavailableError("Zeitablauf beim Senden"))
    with pytest.raises(VenueUnavailableError):
        venue.submit_order(_order("o-timeout"))
    assert terminal.sendeversuche == 1
    assert venue.is_halted() is True, (
        "Nach einem Sendeversuch mit unbekanntem Ausgang ist das Buch unbelegt. "
        "Weiter zu eroeffnen heisst, auf einer unbekannten Lage zu rechnen."
    )
    unklar = venue.unklare_sendeversuche()
    assert "o-timeout" in unklar, (
        "Ohne Vermerk weiss der Betrieb nicht, WELCHE Kennung er beim Broker "
        "nachsehen muss."
    )


def test_klare_ablehnung_haelt_die_maschine_nicht_an() -> None:
    """Gegenprobe: eine beantwortete Ablehnung ist kein unklarer Ausgang.

    Ohne diese Grenze waere der Halt eine Dauerbremse -- er wuerde bei jeder
    gewoehnlichen Broker-Ablehnung zuschlagen.
    """
    from mt5_trading_ai.venue.protocol import OrderRejectedError

    venue, _ = _venue(
        Mt5SendResult(
            accepted=False,
            venue_order_id=None,
            filled_volume=Decimal("0"),
            average_price=None,
            ts=TS,
            reason="No money (retcode=10019)",
        )
    )
    with pytest.raises(OrderRejectedError):
        venue.submit_order(_order("o-abgelehnt"))
    assert venue.is_halted() is False
    assert venue.unklare_sendeversuche() == {}


# =========================================================================== #
# Der Riegel, der ohne Zutun des Aufrufers greift                             #
# =========================================================================== #
def test_zweiter_versuch_mit_neuer_zufallskennung_eroeffnet_nicht_doppelt() -> None:
    """DER ROTE EICHFALL AM TATSAECHLICHEN AUFRUFER.

    Die Kennmarke (E10.4) erkennt eine Wiederholung an der ``client_order_id``. Der
    einzige reale Aufrufer schickt dieselbe Kennung nie zweimal:
    ``tools/live_betrieb.py`` baut ``f"open-{symbol}-{uuid.uuid4().hex[:10]}"`` und
    leitet nach Zeitablauf, Neustart oder in einem zweiten Runner den Willen NEU ab.
    Neue Kennung, neue Marke, die Abfrage findet nichts -- der Idempotenzschutz war
    genau dort abgeschaltet, wo man sich auf ihn verlaesst.

    Hier steht der Ablauf im Original: erster Versuch geht durch und fuellt, der
    Broker fuehrt die Position, ein FRISCHER Prozess (leeres ``_results``, frischer
    ``RiskManager``, also auch keine Drossel-Erinnerung) versucht dieselbe Absicht
    unter neuer Zufallskennung.

    Gegen HEAD wird gesendet: zwei echte Orders fuer einen gewollten Auftrag.
    """
    from mt5_trading_ai.venue.protocol import OrderRejectedError

    terminal = _VenueTerminal(_gefuellt())
    erster = _venue_auf(terminal)
    erster.submit_order(_order("open-EURUSD-a1b2c3d4e5"))
    assert terminal.sendeversuche == 1

    # Der Broker fuehrt die Position jetzt -- das ueberlebt jeden Neustart.
    terminal.positionen = (_stehende_position(),)

    zweiter = _venue_auf(terminal)
    with pytest.raises(OrderRejectedError) as ex:
        zweiter.submit_order(_order("open-EURUSD-f6g7h8i9j0"))

    assert ex.value.reason == "doppelte_eroeffnung", (
        "Abgelehnt werden muss WEIL die Position schon steht -- nicht zufaellig aus "
        f"einem anderen Grund ({ex.value.reason})."
    )
    assert terminal.sendeversuche == 1, (
        "Die zweite Order wurde gesendet, obwohl die gewollte Position beim Broker "
        "bereits steht. Genau so wird aus einem Zeitablauf eine doppelte Position."
    )


def test_der_riegel_haengt_nicht_am_prozessgedaechtnis() -> None:
    """Er muss auch dann greifen, wenn das Venue die erste Order nie gesehen hat.

    Der zweite Runner ist der Fall: er hat sein eigenes ``_results``, seinen eigenen
    ``RiskManager`` und sein eigenes Buch. Alles, was ihm bleibt, ist der Broker.
    """
    from mt5_trading_ai.venue.protocol import OrderRejectedError

    terminal = _VenueTerminal(_gefuellt(), positionen=(_stehende_position(),))
    venue = _venue_auf(terminal)
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order("open-EURUSD-fremder-runner"))
    assert ex.value.reason == "doppelte_eroeffnung"
    assert terminal.sendeversuche == 0


def test_ohne_stehende_position_wird_gesendet() -> None:
    """Gegenprobe: ohne diese waere "sperrt immer" von "sperrt richtig" nicht zu
    unterscheiden. Der Riegel darf den Normalfall nicht anfassen."""
    terminal = _VenueTerminal(_gefuellt())
    venue = _venue_auf(terminal)
    ergebnis = venue.submit_order(_order("open-EURUSD-erstmalig"))
    assert ergebnis.accepted is True
    assert terminal.sendeversuche == 1


def test_gegenposition_blockt_die_eroeffnung_nicht() -> None:
    """Der Riegel fragt nach der SEITE. Eine Gegenorder ist keine Wiederholung.

    Ohne diese Grenze waere er eine Dauerbremse fuer jeden Flip und jede Absicherung
    -- und eine Sperre, die den normalen Betrieb blockiert, wird ausgebaut statt
    bedient.
    """
    terminal = _VenueTerminal(
        _gefuellt(), positionen=(_stehende_position(ist_kauf=False),)
    )
    venue = _venue_auf(terminal)
    ergebnis = venue.submit_order(_order("open-EURUSD-gegenrichtung"))
    assert ergebnis.accepted is True
    assert terminal.sendeversuche == 1


def test_fremdes_symbol_blockt_die_eroeffnung_nicht() -> None:
    """Gefragt wird nach der Position IN DIESEM Symbol."""
    fremde = Mt5Position(
        ticket="9999",
        symbol="XAUUSD",
        is_buy=True,
        volume=Decimal("0.01"),
        entry_price=Decimal("2000"),
        stop_loss=None,
        take_profit=None,
        opened_at=TS,
        unrealised_pnl=Decimal("0"),
        swap=Decimal("0"),
    )
    terminal = _VenueTerminal(_gefuellt(), positionen=(fremde,))
    venue = _venue_auf(terminal)
    assert venue.submit_order(_order("open-EURUSD-anderes-symbol")).accepted is True
    assert terminal.sendeversuche == 1


def test_reduce_only_erreicht_den_riegel_nicht() -> None:
    """Risikoabbau darf nie an einer Sperre haengen -- auch nicht an dieser.

    Eine Schliessung setzt eine stehende Gegenposition VORAUS. Liefe sie durch den
    Riegel, waere er die gefaehrlichste Sperre des Moduls: er wuerde genau das
    verhindern, was Risiko abbaut.
    """
    terminal = _VenueTerminal(
        _gefuellt(), positionen=(_stehende_position(volumen="0.05"),)
    )
    venue = _venue_auf(terminal)
    schliessung = OrderRequest(
        client_order_id="close-EURUSD-1a2b3c4d5e",
        symbol="EURUSD",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("0"),
        reduce_only=True,
    )
    assert venue.submit_order(schliessung).accepted is True
    assert terminal.sendeversuche == 1


# =========================================================================== #
# Benannter Mangel -- ausdruecklich KEINE Zusicherung                          #
# =========================================================================== #
def test_liegende_pending_order_faellt_dem_riegel_nicht_auf() -> None:
    """BEKANNTER MANGEL, festgenagelt.

    Der Riegel fragt ``get_positions()``. Eine angelegte, noch nicht ausgefuehrte
    Pending-Order steht dort nicht -- sie steht in ``orders_get``, und der Vertrag
    :class:`Mt5Terminal` kennt keine Auftragsliste. Eine Wiederholung unter neuer
    Zufallskennung wuerde in diesem Fall erneut gesendet.

    Warum das hier steht statt behoben zu sein: eine Auftragsliste im
    Terminal-Vertrag zieht jede Attrappe im Repo mit und ist eine eigene Welle. Der
    reale Aufrufer sendet ausschliesslich Marktorders; fuer ihn traegt der Riegel.

    Wer den Mangel behebt, macht diesen Test rot. Das ist beabsichtigt.
    """
    terminal = _VenueTerminal(_gefuellt())  # Position noch nicht da: nur angelegt
    venue = _venue_auf(terminal)
    assert venue.submit_order(_order("open-EURUSD-nach-pending")).accepted is True
    assert terminal.sendeversuche == 1


def test_geschlossene_position_wird_nicht_erkannt() -> None:
    """BEKANNTER MANGEL, festgenagelt.

    Gefragt werden die offenen Positionen und die liegenden Auftraege. Ein Auftrag,
    der gefuellt und dessen Position bereits wieder geschlossen wurde, steht in
    keinem der beiden Bestaende -- eine Wiederholung dieser Kennung wuerde erneut
    gesendet.

    Warum das hier steht statt behoben zu sein: die Historie
    (``history_deals_get``) braucht ein Zeitfenster, und jede Fensterlaenge waere
    eine Zahl ohne Beleg. Fuer den Fall, um den es geht -- Wiederholung nach
    Zeitablauf oder Neustart, also Sekunden bis Minuten spaeter -- traegt die
    Pruefung; fuer eine Kennung, die Tage spaeter erneut verwendet wird, nicht.

    Wer den Mangel behebt, macht diesen Test rot. Das ist beabsichtigt.
    """
    attrappe = _Mt5Attrappe()  # Bestaende leer: die Position ist schon wieder zu
    _terminal(attrappe).order_send(_auftrag("o-lange-her"))
    # Richtig waere hier 0 gesendete Auftraege, wenn die Historie mitgefragt wuerde.
    assert len(attrappe.gesendet) == 1

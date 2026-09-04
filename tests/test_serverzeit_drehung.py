"""Der Adapter dreht Serverzeit in echtes UTC -- mit einem GEMESSENEN Versatz (D20).

WARUM DIESER TEST
-----------------
MetaTrader liefert Balken- und Positionszeiten so, dass sie **als UTC gelesen die
Server-Ortszeit ergeben**. ``RealMt5Terminal._utc`` haengte darum bis 2026-08-17 das
Etikett ``UTC`` an eine Zeit, die keine ist; danach drehte es ueber eine feste Zone
(``server_tz="Europe/Helsinki"``). Die Zone traegt eine Sommerzeitregel (EU-Termin),
die der Broker nicht versprochen hat -- ein Server mit US-Termin laege 2-4 Wochen im
Jahr eine Stunde daneben, und der Frische-Latch stuende still (Befund D20, Eichfall
``tests/eichfall_d20.py``).

Seit 2026-09-04 wird der Versatz **gemessen**: ``messe_serverversatz(symbol)`` liest
die Tickzeit gegen die lokale UTC-Uhr, rundet auf ganze Stunden und verlangt einen
Frischebeweis (der Tick ist zwischen zwei Lesungen vorgerueckt). Drei Richtungen sind
zu sichern:

* Mit gemessenem Versatz **muss** gedreht werden -- in beide Richtungen
  (``_utc`` und ``_zu_server``).
* Ohne Messung darf **nicht** gedreht werden. Ein stiller Standardwert waere fuer
  jeden anderen Broker falsch, und ein falscher Versatz ist schlimmer als ein
  bekannter fehlender.
* Eine Messung, die nicht traegt (Kursstrom steht, Rest zu gross, kein
  Zeitzonenversatz), setzt **nichts** -- und laesst einen frueheren Wert stehen.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.mt5 import (
    SERVERVERSATZ_HOECHSTENS,
    SERVERVERSATZ_TOLERANZ,
    RealMt5Terminal,
    Serverversatz,
    ServerversatzFehler,
    serverversatz_runden,
)

#: 15.01.2024, 12:00 nach der Wanduhr des Servers.
WINTER = datetime(2024, 1, 15, 12, 0, tzinfo=UTC).timestamp()
#: 15.07.2024, 12:00 nach der Wanduhr des Servers.
SOMMER = datetime(2024, 7, 15, 12, 0, tzinfo=UTC).timestamp()
#: Echte UTC-Gegenwart der Messfaelle (ein Montag).
T0 = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
DREI_STUNDEN = timedelta(hours=3)


class _Uhr:
    """Eine stellbare lokale UTC-Uhr; ``schlaf`` rueckt sie vor statt zu warten."""

    def __init__(self, jetzt: datetime) -> None:
        self.jetzt = jetzt
        self.geschlafen: list[float] = []

    def __call__(self) -> datetime:
        return self.jetzt

    def schlaf(self, sekunden: float) -> None:
        self.geschlafen.append(sekunden)
        self.jetzt += timedelta(seconds=sekunden)


class _Tick:
    def __init__(self, wanduhr: datetime) -> None:
        self.time = int(wanduhr.timestamp())
        self.time_msc = int(wanduhr.timestamp() * 1000)
        self.bid = 1.0999
        self.ask = 1.1


class _Mt5Attrappe:
    """``symbol_info_tick`` eines Servers, dessen Wanduhr ``versatz`` vor UTC laeuft.

    Druckender Strom: jeder Aufruf liefert einen Tick, der ``alter`` alt ist -- die
    Tickzeit rueckt mit der Uhr vor. ``steht``: der letzte Tick kam zu dieser echten
    UTC-Zeit und rueckt nicht mehr vor (Wochenende, ruhiges Symbol).
    """

    def __init__(
        self,
        uhr: _Uhr,
        *,
        versatz: timedelta,
        alter: timedelta = timedelta(0),
        steht: datetime | None = None,
        kein_tick: bool = False,
    ) -> None:
        self.uhr = uhr
        self.versatz = versatz
        self.alter = alter
        self.steht = steht
        self.kein_tick = kein_tick
        self.aufrufe = 0

    def symbol_info_tick(self, symbol: str) -> Any:
        self.aufrufe += 1
        if self.kein_tick:
            return None
        if self.steht is not None:
            return _Tick(self.steht + self.versatz)
        return _Tick(self.uhr.jetzt + self.versatz - self.alter)

    def terminal_info(self) -> Any:
        return SimpleNamespace(connected=True)

    def account_info(self) -> Any:
        return object()


def _terminal(attrappe: _Mt5Attrappe, uhr: _Uhr, **kwargs: Any) -> RealMt5Terminal:
    terminal = RealMt5Terminal(allow_write=False, uhr=uhr, schlaf=uhr.schlaf, **kwargs)
    terminal._mt5 = attrappe  # type: ignore[assignment]
    return terminal


# --- Drehen nur mit bekanntem Versatz -------------------------------------
def test_ohne_messung_wird_nicht_gedreht() -> None:
    """Kein stiller Standardwert -- unbekannt bleibt unbekannt."""
    terminal = RealMt5Terminal(allow_write=False)
    assert terminal.server_versatz is None
    assert terminal._utc(WINTER) == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
    assert terminal._zu_server(datetime(2024, 1, 15, 12, 0, tzinfo=UTC)) == datetime(
        2024, 1, 15, 12, 0, tzinfo=UTC
    )


def test_mit_uebergebenem_versatz_wird_in_beide_richtungen_gedreht() -> None:
    terminal = RealMt5Terminal(allow_write=False, server_versatz=timedelta(hours=2))
    assert terminal._utc(WINTER) == datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
    zurueck = terminal._zu_server(datetime(2024, 1, 15, 10, 0, tzinfo=UTC))
    assert zurueck == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
    assert zurueck.tzinfo is UTC  # als UTC etikettierte Wanduhr (siehe _zu_server)


def test_derselbe_wanduhrwert_ist_je_nach_versatz_eine_andere_utc_zeit() -> None:
    """Die Falle von frueher, jetzt ohne Zone: der Versatz kommt aus der Messung."""
    winter = RealMt5Terminal(allow_write=False, server_versatz=timedelta(hours=2))
    sommer = RealMt5Terminal(allow_write=False, server_versatz=timedelta(hours=3))
    assert winter._utc(SOMMER) == datetime(2024, 7, 15, 10, 0, tzinfo=UTC)
    assert sommer._utc(SOMMER) == datetime(2024, 7, 15, 9, 0, tzinfo=UTC)


def test_das_ergebnis_traegt_immer_utc() -> None:
    for versatz in (None, timedelta(hours=3), timedelta(hours=-5)):
        terminal = RealMt5Terminal(allow_write=False, server_versatz=versatz)
        assert terminal._utc(SOMMER).tzinfo is UTC


def test_ein_unmoeglicher_versatz_faellt_beim_bauen_auf() -> None:
    """Fail-closed: 20 Stunden sind keine Zeitzone -- nicht erst bei der ersten Order."""
    with pytest.raises(ValueError, match="kein Zeitzonenversatz"):
        RealMt5Terminal(allow_write=False, server_versatz=timedelta(hours=20))


# --- Die Messung ------------------------------------------------------------
def test_messung_am_druckenden_strom_setzt_ganze_stunden() -> None:
    uhr = _Uhr(T0)
    attrappe = _Mt5Attrappe(uhr, versatz=DREI_STUNDEN, alter=timedelta(seconds=0.5))
    terminal = _terminal(attrappe, uhr)
    gemessen = terminal.messe_serverversatz("EURUSD")
    assert gemessen.versatz == DREI_STUNDEN
    assert gemessen.stunden == 3
    assert gemessen.rest == timedelta(seconds=-0.5)  # der Tick ist 0,5 s alt
    assert gemessen.tick_alter == timedelta(seconds=2)  # der Leseabstand ist der Beweis
    assert gemessen.symbol == "EURUSD"
    assert terminal.server_versatz == DREI_STUNDEN
    assert uhr.geschlafen == [2.0]
    assert attrappe.aufrufe == 2
    # und ab jetzt wird gedreht: die Wanduhr 15:00 ist echte UTC 12:00
    assert terminal._utc(int((T0 + DREI_STUNDEN).timestamp())) == T0


def test_die_zweite_messung_braucht_kein_warten_wenn_der_tick_seither_vorrueckte() -> (
    None
):
    """Im Betrieb ist der Takt (60 s) der Leseabstand -- ohne zweite Lesung."""
    uhr = _Uhr(T0)
    attrappe = _Mt5Attrappe(uhr, versatz=DREI_STUNDEN, alter=timedelta(seconds=1))
    terminal = _terminal(attrappe, uhr)
    terminal.messe_serverversatz("EURUSD")
    uhr.jetzt += timedelta(seconds=60)
    gemessen = terminal.messe_serverversatz("EURUSD")
    assert attrappe.aufrufe == 3
    assert uhr.geschlafen == [2.0]  # nur beim ersten Mal
    assert gemessen.tick_alter == timedelta(seconds=60)
    assert gemessen.versatz == DREI_STUNDEN


def test_stehender_kursstrom_setzt_nichts() -> None:
    """Ein 40 Minuten alter Tick rueckt zwischen zwei Lesungen nicht vor.

    Das ist der Fall, den eine blosse Rest-Toleranz NICHT faengt: 3 h minus 40 min
    rundet auf 2 h mit 20 min Rest -- und 3 h minus 55 min auf 2 h mit 5 min Rest,
    also innerhalb jeder Toleranz. Der Frischebeweis faengt beide.
    """
    for alter in (timedelta(minutes=40), timedelta(minutes=55)):
        uhr = _Uhr(T0)
        attrappe = _Mt5Attrappe(uhr, versatz=DREI_STUNDEN, steht=T0 - alter)
        terminal = _terminal(attrappe, uhr)
        with pytest.raises(ServerversatzFehler, match="Kursstrom steht"):
            terminal.messe_serverversatz("EURUSD")
        assert terminal.server_versatz is None, alter
        assert terminal._utc(WINTER) == datetime(2024, 1, 15, 12, 0, tzinfo=UTC)


def test_eine_gescheiterte_messung_laesst_den_frueheren_versatz_stehen() -> None:
    uhr = _Uhr(T0)
    attrappe = _Mt5Attrappe(uhr, versatz=DREI_STUNDEN, steht=T0 - timedelta(hours=30))
    terminal = _terminal(attrappe, uhr, server_versatz=timedelta(hours=2))
    with pytest.raises(ServerversatzFehler):
        terminal.messe_serverversatz("EURUSD")
    assert terminal.server_versatz == timedelta(hours=2)


def test_rest_ueber_der_toleranz_setzt_nichts() -> None:
    """Uhrenabweichung Rechner/Server oder Halbstundenzone: die Rundung traegt nicht."""
    for versatz in (
        DREI_STUNDEN + SERVERVERSATZ_TOLERANZ + timedelta(seconds=1),
        timedelta(hours=5, minutes=30),
        timedelta(hours=-3, minutes=-11),
    ):
        uhr = _Uhr(T0)
        terminal = _terminal(_Mt5Attrappe(uhr, versatz=versatz), uhr)
        with pytest.raises(ServerversatzFehler, match="Rest"):
            terminal.messe_serverversatz("EURUSD")
        assert terminal.server_versatz is None, versatz


def test_rest_innerhalb_der_toleranz_traegt() -> None:
    uhr = _Uhr(T0)
    terminal = _terminal(
        _Mt5Attrappe(uhr, versatz=DREI_STUNDEN - SERVERVERSATZ_TOLERANZ), uhr
    )
    gemessen = terminal.messe_serverversatz("EURUSD")
    assert gemessen.versatz == DREI_STUNDEN
    assert gemessen.rest == -SERVERVERSATZ_TOLERANZ


def test_kein_zeitzonenversatz_setzt_nichts() -> None:
    uhr = _Uhr(T0)
    terminal = _terminal(
        _Mt5Attrappe(uhr, versatz=SERVERVERSATZ_HOECHSTENS + timedelta(hours=1)), uhr
    )
    with pytest.raises(ServerversatzFehler, match="kein Zeitzonenversatz"):
        terminal.messe_serverversatz("EURUSD")
    assert terminal.server_versatz is None


def test_negativer_versatz_wird_genauso_gemessen() -> None:
    """Server hinter UTC (etwa New York): Vorzeichen dreht, Rechnung bleibt."""
    uhr = _Uhr(T0)
    terminal = _terminal(_Mt5Attrappe(uhr, versatz=timedelta(hours=-5)), uhr)
    gemessen = terminal.messe_serverversatz("EURUSD")
    assert gemessen.stunden == -5
    assert terminal._utc(int((T0 - timedelta(hours=5)).timestamp())) == T0


def test_ohne_tick_und_ohne_bindung_ist_nichts_messbar() -> None:
    uhr = _Uhr(T0)
    ohne_tick = _terminal(_Mt5Attrappe(uhr, versatz=DREI_STUNDEN, kein_tick=True), uhr)
    with pytest.raises(ServerversatzFehler, match="kein Tick"):
        ohne_tick.messe_serverversatz("EURUSD")
    with pytest.raises(ServerversatzFehler, match="nicht initialisiert"):
        RealMt5Terminal(allow_write=False).messe_serverversatz("EURUSD")


def test_die_rundung_ist_rein_rechnerisch() -> None:
    assert serverversatz_runden(timedelta(hours=2, minutes=40)) == (
        timedelta(hours=3),
        timedelta(minutes=-20),
    )
    assert serverversatz_runden(timedelta(hours=-2, minutes=5)) == (
        timedelta(hours=-2),
        timedelta(minutes=5),
    )
    assert serverversatz_runden(timedelta(seconds=-90)) == (
        timedelta(0),
        timedelta(seconds=-90),
    )


# --- Dieselbe Messung im Rauchtest und im Betrieb ----------------------------
def test_der_rauchtest_nimmt_die_messung_des_terminals() -> None:
    """``run_smoke(serverversatz_messen=...)``: ein Aufruf, Stunden und Rest im
    Schritt, ``serverzeitversatz_s`` in Rohsekunden wie bisher; ein Fehler ist rot."""
    from mt5_trading_ai.venue.mt5 import Mt5Venue
    from mt5_trading_ai.venue.smoke import run_smoke

    from test_mt5_venue import TS, FakeMt5Terminal, _catalog

    def venue() -> Mt5Venue:
        return Mt5Venue(
            name="mt5-demo",
            terminal=FakeMt5Terminal(is_demo=True),
            catalog=_catalog(),
            risk_manager=RiskManager(zustand=FluechtigerZustand()),
            clock=lambda: TS,
            schwebeakte=FluechtigeSchwebeAkte(),
            positionsbuch=FluechtigesPositionsbuch(),
        )

    aufrufe: list[str] = []

    def messen(symbol: str) -> Serverversatz:
        aufrufe.append(symbol)
        return Serverversatz(
            symbol=symbol,
            versatz=DREI_STUNDEN,
            rest=timedelta(seconds=-4.5),
            tick_alter=timedelta(seconds=2),
        )

    report = run_smoke(venue(), symbol="EURUSD", now=TS, serverversatz_messen=messen)
    schritt = next(s for s in report.steps if s.name == "serverzeitversatz")
    assert aufrufe == ["EURUSD"]
    assert schritt.ok is True
    assert "+3 h" in schritt.detail and "-4.5 s" in schritt.detail
    assert report.serverzeitversatz_s == 10795.5

    def scheitert(symbol: str) -> Serverversatz:
        raise ServerversatzFehler(f"{symbol}: Kursstrom steht")

    report = run_smoke(venue(), symbol="EURUSD", now=TS, serverversatz_messen=scheitert)
    schritt = next(s for s in report.steps if s.name == "serverzeitversatz")
    assert schritt.ok is False
    assert "Kursstrom steht" in schritt.detail
    assert report.serverzeitversatz_s is None
    assert report.ok is False


def _takt(tmp_path: Path, terminal: object | None) -> list[dict[str, Any]]:
    from mt5_trading_ai.gates.criteria import CriteriaVerdict
    from tools.live_betrieb import takt

    from test_live_betrieb import FakeScheduler, TaktVenue, _journal, _saetze

    journal = _journal(tmp_path)
    takt(
        TaktVenue(),  # type: ignore[arg-type]
        RiskManager(zustand=FluechtigerZustand()),
        FakeScheduler(),  # type: ignore[arg-type]
        ["EURUSD"],
        CriteriaVerdict(passed=False, results=()),
        journal,
        nr=1,
        max_haltedauer=timedelta(hours=4),
        bekannt={},
        equity_start=Decimal("50000"),
        verlustgrenze=Decimal("0.02"),
        terminal=terminal,
    )
    return [s for s in _saetze(journal) if str(s["art"]).startswith("serverversatz")]


def test_der_takt_misst_am_kopf_und_schreibt_das_journal(tmp_path: Path) -> None:
    """``tools/live_betrieb.takt``: gemessen, geaendert, unmessbar, nicht erneuert."""
    uhr = _Uhr(T0)
    attrappe = _Mt5Attrappe(uhr, versatz=DREI_STUNDEN, alter=timedelta(seconds=1))
    terminal = _terminal(attrappe, uhr)

    erster = _takt(tmp_path / "a", terminal)
    assert [s["art"] for s in erster] == ["serverversatz_gemessen"]
    assert erster[0]["stunden"] == 3 and erster[0]["symbol"] == "EURUSD"
    assert terminal.server_versatz == DREI_STUNDEN

    uhr.jetzt += timedelta(seconds=60)
    assert _takt(tmp_path / "b", terminal) == []  # unveraendert: kein Satz

    attrappe.versatz = timedelta(hours=2)  # Sommerzeitende am Server
    uhr.jetzt += timedelta(seconds=60)
    geaendert = _takt(tmp_path / "c", terminal)
    assert [s["art"] for s in geaendert] == ["serverversatz_geaendert"]
    assert (geaendert[0]["alt_stunden"], geaendert[0]["neu_stunden"]) == (3, 2)
    assert terminal.server_versatz == timedelta(hours=2)

    attrappe.steht = T0 - timedelta(hours=30)  # Wochenende: der Strom steht
    uhr.jetzt += timedelta(seconds=60)
    nicht_erneuert = _takt(tmp_path / "d", terminal)
    assert [s["art"] for s in nicht_erneuert] == ["serverversatz_nicht_erneuert"]
    assert nicht_erneuert[0]["bisher_stunden"] == 2
    assert terminal.server_versatz == timedelta(hours=2)

    neu = _terminal(_Mt5Attrappe(_Uhr(T0), versatz=DREI_STUNDEN, steht=T0), _Uhr(T0))
    unmessbar = _takt(tmp_path / "e", neu)
    assert [s["art"] for s in unmessbar] == ["serverversatz_unmessbar"]
    assert neu.server_versatz is None  # -> Frische-Latch bleibt rot, kein Eintritt

    assert _takt(tmp_path / "f", None) == []  # Attrappe im Test: nichts zu messen

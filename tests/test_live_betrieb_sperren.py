"""Der Live-Treiber an den Stellen, an denen eine Sperre faellt oder stehen bleibt.

WARUM DIESE DATEI NEBEN ``test_live_betrieb.py`` STEHT
------------------------------------------------------
Die vorhandene Datei prueft die **Messung** (auf welcher Kerze gerechnet wird) und das
**Protokoll** (was ein Schluss ins Journal traegt). Ungeprueft blieb die Haelfte, die
im Dauerbetrieb wirklich weh tut: wann ein Halt geloest wird und wann eben **nicht**,
wo die Notbremse genau greift, und ob ein Instrument mit offener Position noch einmal
eroeffnet werden kann.

Das sind keine Anzeigefragen. Ein Halt, der sich zu frueh loest, hebt eine Sperre auf,
die aus einem anderen Grund steht; eine Notbremse, die einen Schritt zu spaet greift,
laesst Verlust laufen; ein zweiter Eintritt auf ein schon offenes Symbol baut die
Gegenposition auf, gegen die der Modulkopf ausdruecklich gebaut ist.

DER BEFUND, DER DIESE DATEI AUSGELOEST HAT
-------------------------------------------
``_verbindung_sichern`` schrieb ``halt_geloest`` mit ``grund=venue.halt_reason`` --
**nach** ``venue.clear_halt()``. ``clear_halt`` setzt ``_halt_reason`` auf ``None``
(``venue/mt5.py``), also stand im Journal dauerhaft ``"grund": null``. Der Satz belegte
damit nur noch, DASS ein Halt endete, und nicht mehr, warum. Genau dieselbe Stelle in
``takt`` (``halt_erklaert``) macht es richtig herum -- die beiden Saetze liefen
auseinander, und keiner der beiden war geprueft.

WAS HIER BEWUSST NICHT GEPRUEFT WIRD
-------------------------------------
Nichts, was ein MT5-Terminal braucht, und keine Sperre wird ausser Kraft gesetzt. Die
Handelsplaetze sind Attrappen mit genau den Methoden, die der jeweilige Pfad anfasst;
was fehlt, faellt als ``AttributeError`` auf statt still ein Verhalten zu erfinden.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.scheduler import TickResult
from mt5_trading_ai.gates.criteria import CriteriaVerdict
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Bar,
    OrderSide,
    Position,
    Quote,
    Timeframe,
    VenueUnavailableError,
)
from tools.live_betrieb import (
    LANGSAM,
    Journal,
    Lage,
    _codestand,
    _jsonfaehig,
    _notbremse,
    _schliesse,
    _verbindung_sichern,
    takt,
)

T0 = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)


# --- Attrappen -------------------------------------------------------------
def _bar(nr: int, close: float) -> Bar:
    preis = Decimal(str(close))
    return Bar(
        symbol="XAUUSD", timeframe=Timeframe.H1, ts=T0 + timedelta(hours=nr),
        open=preis, high=preis, low=preis, close=preis, tick_volume=1,
        is_closed=True,
    )


#: 26 fallende abgeschlossene Kerzen -> MA12 < MA26 -> SHORT.
FALLEND = tuple(_bar(i, 1.30 - i * 0.001) for i in range(LANGSAM))


class _Angenommen:
    venue_order_id = "O1"
    average_price = Decimal("4420.00")
    filled_volume = Decimal("0.01")


@dataclass
class HaltVenue:
    """Ein Handelsplatz mit einem echten Halt-Latch -- mehr braucht ``takt`` nicht.

    Der Latch ist bewusst als Zustand nachgebaut und nicht als fester Wert: die Frage
    dieser Datei ist, ob er nach dem Takt noch steht. Ein Attrappenwert, der sich nicht
    aendern kann, koennte sie nicht beantworten.
    """

    kerzen: dict[str, tuple[Bar, ...]] = field(default_factory=dict)
    positionen: tuple[Position, ...] = ()
    equity: Decimal = Decimal("50000")
    halt_reason: str | None = None
    kurs_fehler: set[str] = field(default_factory=set)
    gesendet: list[str] = field(default_factory=list)
    geloest: int = 0

    def get_account(self) -> AccountState:
        return AccountState(
            account_id="DEMO-1", currency="EUR", balance=Decimal("50000"),
            equity=self.equity, margin_used=Decimal("0"),
            margin_free=self.equity, is_demo=True, ts=T0,
        )

    def get_positions(self) -> tuple[Position, ...]:
        return self.positionen

    def get_quote(self, symbol: str) -> Quote:
        if symbol in self.kurs_fehler:
            raise VenueUnavailableError(f"kein Tick fuer {symbol}")
        return Quote(symbol=symbol, ts=T0, bid=Decimal("1.1000"),
                     ask=Decimal("1.1002"))

    def get_bars(
        self, symbol: str, timeframe: Timeframe, *, start: datetime, end: datetime
    ) -> tuple[Bar, ...]:
        return self.kerzen.get(symbol, ())

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        return True

    def adopt_book(self) -> dict[str, Decimal]:
        return {}

    def submit_order(self, anfrage: Any) -> _Angenommen:
        self.gesendet.append(anfrage.client_order_id)
        return _Angenommen()

    def latch_halt(self, *, reason: str) -> None:
        self.halt_reason = reason

    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1


@dataclass
class SpiegelScheduler:
    """``halted`` folgt dem Latch des Platzes -- so wie der echte Scheduler auch.

    Ein Scheduler mit fest verdrahtetem ``halted`` koennte den zweiten ``tick`` nach
    ``clear_halt`` nicht abbilden, und genau der entscheidet, ob nach dem Aufloesen
    wieder eroeffnet werden darf.
    """

    venue: HaltVenue

    def tick(self, jetzt: datetime) -> TickResult:
        return TickResult(
            now=jetzt, halted=self.venue.halt_reason is not None,
            halt_reason=self.venue.halt_reason, sync_healthy=True,
            stream_never_started=True, reconcile=None, events_applied=0,
        )


@dataclass
class ReconnectTerminal:
    """Ein Terminal, das sich nach ``kommt_wieder_ab`` Versuchen wieder meldet."""

    kommt_wieder_ab: int = 1
    versuche: int = 0
    beendet: int = 0

    def shutdown(self) -> None:
        self.beendet += 1

    def initialize(self) -> bool:
        self.versuche += 1
        return self.versuche >= self.kommt_wieder_ab


@dataclass
class ReconnectVenue:
    """Ein Platz, der erst nach dem Neuverbinden wieder gesund ist."""

    gesund: bool = False
    halt_reason: str | None = None
    verbunden: int = 0
    uebernommen: int = 0
    geloest: int = 0

    def is_healthy(self) -> bool:
        return self.gesund

    def connect(self) -> None:
        self.verbunden += 1
        self.gesund = True

    def adopt_book(self) -> dict[str, Decimal]:
        self.uebernommen += 1
        return {}

    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1


def _journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "journal-test.jsonl", lauf="lauf-t", version="testv")


def _saetze(journal: Journal) -> list[dict[str, Any]]:
    """Die geschriebenen Zeilen. Eine fehlende Datei heisst: kein einziger Satz.

    Das ist kein Bequemlichkeitsgriff, sondern die geprueftere Aussage: mehrere Faelle
    unten verlangen, dass GAR NICHTS protokolliert wurde -- eine Datei, die gar nicht
    erst entsteht, erfuellt das.
    """
    if not journal.pfad.is_file():
        return []
    text = journal.pfad.read_text(encoding="utf-8")
    return [json.loads(z) for z in text.splitlines() if z.strip()]


def _position(symbol: str = "XAUUSD", *, seit: datetime | None = None) -> Position:
    return Position(
        venue_position_id="10060725485", symbol=symbol, side=OrderSide.BUY,
        volume=Decimal("0.01"), entry_price=Decimal("4415.18"), stop_loss=None,
        take_profit=None, opened_at=seit or T0, unrealised_pnl=Decimal("-2.68"),
        swap_accrued=Decimal("-0.11"),
    )


def _lage(seit: datetime | None = None) -> Lage:
    return Lage(
        symbol="XAUUSD", ist_kauf=True, volumen=Decimal("0.01"),
        seit=seit or T0, position_id="10060725485",
        einstiegspreis=Decimal("4415.18"), unrealisiert=Decimal("-2.68"),
        swap=Decimal("-0.11"),
    )


@pytest.fixture
def ohne_warten(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_verbindung_sichern`` wartet 5 bis 30 Sekunden je Versuch.

    Die Wartezeit ist Teil des Produktionspfads und bleibt dort. Ein Test, der sie
    wirklich abwartet, haengt an der Rechneruhr -- also wird nur der Schlaf ersetzt,
    und die Pausenlaenge unten als Zahl geprueft statt als Dauer erlebt.
    """
    monkeypatch.setattr("tools.live_betrieb.time.sleep", lambda _s: None)


# --- Der Befund: warum ein Halt endete ------------------------------------
def test_der_geloeste_halt_nennt_seinen_grund(
    tmp_path: Path, ohne_warten: None
) -> None:
    """DER EICHFALL. Gegen die alte Fassung stand hier ``grund: None``.

    Die Zeile lautete::

        venue.clear_halt()
        journal.schreib("halt_geloest", grund=venue.halt_reason)

    ``clear_halt`` setzt ``_halt_reason`` auf ``None`` (``venue/mt5.py:1416``), der
    Grund wurde also NACH dem Loeschen gelesen. Im Journal stand darum bei jedem
    einzelnen dieser Saetze ``null`` -- und damit war nicht mehr feststellbar, ob ein
    Reconcile-Ausfall oder ein Kontoausfall geendet hatte. Der Satz existierte nur
    noch, um zu belegen, dass geloest wurde.
    """
    venue = ReconnectVenue(halt_reason="reconcile_unavailable")
    j = _journal(tmp_path)
    assert _verbindung_sichern(venue, ReconnectTerminal(), j) is True
    satz = next(s for s in _saetze(j) if s["art"] == "halt_geloest")
    assert satz["grund"] == "reconcile_unavailable", (
        "Der Grund muss VOR dem Loesen festgehalten werden -- danach ist er None."
    )
    assert venue.halt_reason is None, "Der Halt selbst muss geloest sein"


def test_ein_fremder_halt_wird_beim_neuverbinden_nicht_geloest(
    tmp_path: Path, ohne_warten: None
) -> None:
    """Die schmeichelnde Richtung waere hier ein schwerer Fehler.

    Ein Drawdown-, Desync- oder Notbremsen-Halt hat mit der Leitungsstoerung nichts zu
    tun. Wuerde das Neuverbinden ihn mitloesen, haette eine abgerissene Verbindung die
    Wirkung eines Freigabeknopfes -- und zwar unbeaufsichtigt, mitten in der Nacht.
    """
    venue = ReconnectVenue(halt_reason="tagesverlust")
    j = _journal(tmp_path)
    assert _verbindung_sichern(venue, ReconnectTerminal(), j) is True
    assert venue.halt_reason == "tagesverlust"
    assert venue.geloest == 0
    assert not [s for s in _saetze(j) if s["art"] == "halt_geloest"]


def test_ein_gesunder_platz_wird_gar_nicht_erst_angefasst(tmp_path: Path) -> None:
    """Ohne diese Vorpruefung liefe jeder Takt durch Abbau und Neuaufbau.

    Kein ``ohne_warten``: der Fall darf ueberhaupt nicht schlafen. Tut er es doch,
    haengt dieser Test -- was die richtige Meldung ist.
    """
    venue = ReconnectVenue(gesund=True)
    terminal = ReconnectTerminal()
    j = _journal(tmp_path)
    assert _verbindung_sichern(venue, terminal, j) is True
    assert terminal.versuche == 0
    assert terminal.beendet == 0
    assert _saetze(j) == []


def test_nach_erfolglosen_versuchen_meldet_der_lauf_offene_positionen(
    tmp_path: Path, ohne_warten: None
) -> None:
    """Fail-closed: ``False`` beendet den Lauf, statt blind weiterzutakten.

    Von Hand: drei erlaubte Versuche, das Terminal meldet sich nie -- also drei
    ``reconnect_versuch``-Saetze mit den Pausen 5, 10 und 15 Sekunden
    (``min(30, 5*(i+1))``), kein ``reconnect_ok``, und am Ende der Satz, der sagt,
    dass Positionen offen sein koennen.
    """
    venue = ReconnectVenue()
    terminal = ReconnectTerminal(kommt_wieder_ab=99)
    j = _journal(tmp_path)
    assert _verbindung_sichern(venue, terminal, j, versuche=3) is False
    saetze = _saetze(j)
    assert [s["pause"] for s in saetze if s["art"] == "reconnect_versuch"] == [
        5.0, 10.0, 15.0
    ]
    assert not [s for s in saetze if s["art"] == "reconnect_ok"]
    assert saetze[-1]["art"] == "verbindung_verloren"
    assert saetze[-1]["offen_moeglich"] is True


def test_ein_fehler_beim_neuverbinden_beendet_den_versuch_nicht(
    tmp_path: Path, ohne_warten: None
) -> None:
    """Der erste Versuch wirft, der zweite traegt -- und beides steht im Journal."""

    class ZaehVenue(ReconnectVenue):
        def connect(self) -> None:
            self.verbunden += 1
            if self.verbunden == 1:
                raise VenueUnavailableError("Sitzung noch nicht da")
            self.gesund = True

    venue = ZaehVenue()
    j = _journal(tmp_path)
    assert _verbindung_sichern(venue, ReconnectTerminal(), j, versuche=3) is True
    arten = [s["art"] for s in _saetze(j)]
    assert arten.count("reconnect_fehler") == 1
    assert arten.count("reconnect_ok") == 1


# --- Die Notbremse ---------------------------------------------------------
def test_die_notbremse_greift_genau_auf_der_grenze(tmp_path: Path) -> None:
    """Von Hand vorgerechnet, und die Grenze gehoert INS Feuer, nicht daneben.

    Start 50 000, Grenze 2 %. Bei 49 000 ist der Verlust
    ``(50000 - 49000) / 50000 = 0,02`` -- also **genau** die Grenze. Sie muss greifen:
    ``verlust < grenze`` ist falsch, der Rueckfall ist ``True``.

    Mutationsprobe: ``verlust < grenze`` zu ``verlust <= grenze`` gedreht -- also die
    Grenze knapp verschont -- faellt dieser Fall. Das ist die schmeichelnde Richtung,
    und an einer Verlustgrenze ist sie kein Abwaegungsfall.
    """
    venue = HaltVenue()
    j = _journal(tmp_path)
    assert _notbremse(
        venue, RiskManager(), j, equity_jetzt=Decimal("49000"),
        equity_start=Decimal("50000"), grenze=Decimal("0.02"),
        lage={}, jetzt=T0, waehrung="EUR",
    ) is True
    satz = next(s for s in _saetze(j) if s["art"] == "notbremse")
    assert satz["verlust_anteil"] == "0.02"
    assert satz["grenze"] == "0.02"
    assert venue.halt_reason == "tagesverlust"


def test_knapp_unter_der_grenze_greift_die_notbremse_nicht(tmp_path: Path) -> None:
    """Die Gegenprobe -- sonst waere oben nur bewiesen, dass sie immer feuert.

    Von Hand: bei 49 000,50 ist der Verlust ``999,50 / 50000 = 0,01999`` und damit
    kleiner als 0,02. Kein Halt, kein Satz, keine Order.
    """
    venue = HaltVenue()
    j = _journal(tmp_path)
    assert _notbremse(
        venue, RiskManager(), j, equity_jetzt=Decimal("49000.50"),
        equity_start=Decimal("50000"), grenze=Decimal("0.02"),
        lage={"XAUUSD": _lage()}, jetzt=T0, waehrung="EUR",
    ) is False
    assert venue.halt_reason is None
    assert venue.gesendet == []
    assert _saetze(j) == []


def test_die_notbremse_stellt_wirklich_glatt(tmp_path: Path) -> None:
    """Der Unterschied zu ``REDUCE_ONLY`` aus ``risk/limits.py``.

    Die Grenze dort sperrt nur den Einkauf und laesst laufende Verlustpositionen
    stehen. Fuer einen unbeaufsichtigten Lauf ist das zu wenig -- wer nicht zusieht,
    muss darauf zaehlen koennen, dass bei Erreichen der Grenze wirklich Schluss ist.
    """
    venue = HaltVenue()
    j = _journal(tmp_path)
    assert _notbremse(
        venue, RiskManager(), j, equity_jetzt=Decimal("48000"),
        equity_start=Decimal("50000"), grenze=Decimal("0.02"),
        lage={"XAUUSD": _lage()}, jetzt=T0, waehrung="EUR",
    ) is True
    assert len(venue.gesendet) == 1
    zu = next(s for s in _saetze(j) if s["art"] == "geschlossen")
    assert zu["grund"] == "notbremse"
    assert zu["symbol"] == "XAUUSD"
    # Reihenfolge: erst glattstellen, dann latchen. Andersherum sperrte der Halt
    # womoeglich das eigene Schliessen aus.
    arten = [s["art"] for s in _saetze(j)]
    assert arten.index("geschlossen") > arten.index("notbremse")


def test_ohne_startequity_rechnet_die_notbremse_nicht(tmp_path: Path) -> None:
    """Eine Division durch null waere hier ein Absturz mitten im Takt.

    ``0`` heisst nicht "alles verloren", sondern "keine Bezugsgroesse". Fail-closed
    ist hier ausdruecklich NICHT das Feuern: ein Halt aus einer Nullteilung haette
    keinen Bezug zur Wirklichkeit, und die Sperre stuende dann ohne Grund.
    """
    j = _journal(tmp_path)
    assert _notbremse(
        HaltVenue(), RiskManager(), j, equity_jetzt=Decimal("-10"),
        equity_start=Decimal("0"), grenze=Decimal("0.02"),
        lage={}, jetzt=T0, waehrung="EUR",
    ) is False
    assert _saetze(j) == []


# --- Der Takt: Halt aufloesen, aber nur diesen einen ----------------------
def _takt(
    tmp_path: Path, venue: HaltVenue, *, bekannt: dict[str, Lage] | None = None,
    max_haltedauer: timedelta = timedelta(hours=4),
) -> tuple[Journal, dict[str, Lage], bool]:
    j = _journal(tmp_path)
    lage, gestoppt = takt(
        venue, RiskManager(), SpiegelScheduler(venue), ["EURUSD", "XAUUSD"],
        CriteriaVerdict(passed=False, results=()), j,
        nr=1, max_haltedauer=max_haltedauer, bekannt=bekannt or {},
        equity_start=Decimal("50000"), verlustgrenze=Decimal("0.02"),
    )
    return j, lage, gestoppt


def test_ein_reconcile_halt_aus_einer_erkannten_schliessung_wird_aufgeloest(
    tmp_path: Path,
) -> None:
    """Gemessen am 17.08.2026, Takt 43: ein normaler Stop-Fill setzte den Global-Halt.

    Der Scheduler laeuft VOR dem Buchabgleich und sieht die vom Broker geschlossene
    Position noch im Buch; bei ``max_notional_drift=0`` latcht das
    ``reconcile_drift``. Ab da eroeffnete der Lauf nichts mehr -- ein voellig normales
    Trade-Ende war bitgleich mit einem katastrophalen Desync.
    """
    venue = HaltVenue(
        kerzen={"XAUUSD": FALLEND},
        halt_reason="reconcile_drift:notional_drift_exceeds_limit",
    )
    j, _, _ = _takt(tmp_path, venue, bekannt={"XAUUSD": _lage()})
    satz = next(s for s in _saetze(j) if s["art"] == "halt_erklaert")
    assert satz["grund"] == "reconcile_drift:notional_drift_exceeds_limit"
    assert satz["durch"] == "broker_schliessung"
    assert venue.halt_reason is None


def test_ein_desync_halt_bleibt_stehen_auch_bei_erkannter_schliessung(
    tmp_path: Path,
) -> None:
    """Eine Sperre, die sich selbst aufhebt, waere keine.

    Derselbe Aufbau wie oben -- eine erkannte Broker-Schliessung im selben Takt --,
    nur steht der Halt aus einem ANDEREN Grund. Er muss stehen bleiben, und solange er
    steht, darf nichts eroeffnet werden.

    Mutationsprobe: die Bedingung ``startswith("reconcile_drift")`` auf jeden Halt
    geweitet -- dann faellt dieser Fall an drei Stellen zugleich.
    """
    venue = HaltVenue(
        kerzen={"XAUUSD": FALLEND}, halt_reason="stream_desync:sequence_gap",
    )
    j, _, _ = _takt(tmp_path, venue, bekannt={"XAUUSD": _lage()})
    saetze = _saetze(j)
    assert not [s for s in saetze if s["art"] == "halt_erklaert"]
    assert venue.halt_reason == "stream_desync:sequence_gap"
    assert not [
        s for s in saetze if s["art"] == "signalbasis" and s["zweck"] == "eintritt"
    ], "Bei stehendem Halt wird kein Eintritt gerechnet"


def test_bei_halt_bleibt_der_ausstieg_moeglich(tmp_path: Path) -> None:
    """Schliessen muss immer gehen -- eine Sperre, die das Aussteigen verhindert,
    waere gefaehrlicher als die Lage, gegen die sie gesetzt wurde.

    XAUUSD ist als Kauf offen, das Signal ist SHORT (fallende Kerzen), der Halt steht.
    Der Ausstieg laeuft trotzdem.
    """
    venue = HaltVenue(
        kerzen={"XAUUSD": FALLEND}, positionen=(_position(),),
        halt_reason="stream_desync:sequence_gap",
    )
    j, _, _ = _takt(tmp_path, venue)
    zu = next(s for s in _saetze(j) if s["art"] == "geschlossen")
    assert zu["grund"] == "signalwechsel"
    assert venue.gesendet, "Die schliessende Order muss auch im Halt gesendet werden"


def test_ein_offenes_symbol_bekommt_keinen_zweiten_eintritt(tmp_path: Path) -> None:
    """Der Befund aus dem Modulkopf: ein Signalwechsel eroeffnete frueher eine
    GEGENposition, statt zu drehen.

    Hier tragen die Kerzen von XAUUSD ein SHORT und die Position ist ein Kauf -- der
    Ausstieg greift. Die Attrappe meldet die Position danach weiter als offen (ein
    Fill braucht beim echten Platz auch einen Moment), und genau dann darf kein
    Eintritt gerechnet werden.

    Mutationsprobe: das ``continue`` in Schritt 4 entfernt -- dann steht ein
    ``signalbasis``-Satz mit ``zweck=eintritt`` fuer XAUUSD im Journal, und dieser
    Fall faellt.
    """
    venue = HaltVenue(kerzen={"XAUUSD": FALLEND}, positionen=(_position(),))
    j, _, _ = _takt(tmp_path, venue)
    eintritte = {
        s["symbol"] for s in _saetze(j)
        if s["art"] == "signalbasis" and s["zweck"] == "eintritt"
    }
    assert eintritte == {"EURUSD"}, (
        f"XAUUSD ist offen und darf nicht dabei sein: {eintritte}"
    )


def test_die_hoechsthaltedauer_schliesst_eine_alte_position(tmp_path: Path) -> None:
    """Zweiter Ausstiegsweg. Ohne ihn laeuft eine Position ueber Nacht weiter.

    Die Kerzen von XAUUSD fehlen hier absichtlich: ohne sie ist das Signal FLAT, es
    gibt also KEINEN Signalwechsel. Was schliesst, ist allein das Alter. Die Position
    ist auf ``jetzt - 5 h`` gesetzt, die Grenze steht bei 4 h -- der Abstand ist so
    gross, dass keine Laufzeit des Tests ihn kippen kann.
    """
    alt = datetime.now(UTC) - timedelta(hours=5)
    venue = HaltVenue(positionen=(_position(seit=alt),))
    j, _, _ = _takt(tmp_path, venue)
    zu = next(s for s in _saetze(j) if s["art"] == "geschlossen")
    assert zu["grund"].startswith("haltedauer_")
    assert next(
        s for s in _saetze(j) if s["art"] == "signalbasis"
    )["signal"] == "FLAT", "Der Schluss darf nicht aus einem Signalwechsel kommen"


def test_die_hoechsthaltedauer_greift_genau_auf_der_grenze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DIE KANTE SELBST -- die beiden Faelle daneben stehen mit Absicht weit weg.

    5 h gegen 4 h und 3 h gegen 4 h halten die Richtung fest, aber nicht die Grenze:
    ``alter >= max_haltedauer`` laesst sich gegen sie folgenlos zu ``>`` drehen. Das
    ist die schmeichelnde Richtung -- eine Position, die die Hoechsthaltedauer genau
    erreicht hat, liefe dann weiter. An der Notbremse ist dieselbe Kante exakt
    festgenagelt; hier fehlte sie.

    Getroffen wird sie ueber eine ANGEHALTENE UHR: ``takt`` liest ``datetime.now(UTC)``
    selbst, und zwischen diesem Aufruf und dem Bau der Attrappe laegen sonst
    Mikrosekunden -- ``alter`` waere dann nie exakt vier Stunden. Mit der festen Uhr
    ist ``alter`` eine ``timedelta``-Differenz aus ganzen Mikrosekunden und damit
    bitgenau gleich der Grenze. Die Uhr haengt danach nicht mehr an der Rechneruhr;
    ``monkeypatch`` nimmt sie am Ende des Falls zurueck.

    Ohne Kerzen fuer XAUUSD ist das Signal FLAT -- was schliesst, ist allein das Alter.
    """
    fix = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    class _StehendeUhr(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # noqa: ARG003 - Signatur der Basis
            return fix

    monkeypatch.setattr("tools.live_betrieb.datetime", _StehendeUhr)

    venue = HaltVenue(positionen=(_position(seit=fix - timedelta(hours=4)),))
    j, _, _ = _takt(tmp_path, venue, max_haltedauer=timedelta(hours=4))
    zu = next(s for s in _saetze(j) if s["art"] == "geschlossen")
    assert zu["grund"] == "haltedauer_4.0h", (
        "Genau auf der Grenze wird geschlossen -- die Grenze gehoert INS Schliessen"
    )


def test_eine_junge_position_bleibt_offen(tmp_path: Path) -> None:
    """Die Gegenprobe zur Haltedauer -- sonst waere nur bewiesen, dass immer
    geschlossen wird.

    Drei Stunden alt bei einer Grenze von vier: sie bleibt. Auch hier keine Kerzen,
    also FLAT und kein Signalwechsel.
    """
    jung = datetime.now(UTC) - timedelta(hours=3)
    venue = HaltVenue(positionen=(_position(seit=jung),))
    j, _, _ = _takt(tmp_path, venue)
    assert not [s for s in _saetze(j) if s["art"] == "geschlossen"]
    assert venue.gesendet == []


def test_die_notbremse_haelt_den_takt_an(tmp_path: Path) -> None:
    """Nach dem Glattstellen darf im selben Takt nichts mehr eroeffnet werden.

    Von Hand: Start 50 000, Equity 48 000 -- das sind 4 % Verlust gegen eine Grenze
    von 2 %. Der Takt gibt ``gestoppt=True`` zurueck, und die Hauptschleife bricht
    darauf ab.
    """
    venue = HaltVenue(kerzen={"EURUSD": FALLEND}, equity=Decimal("48000"))
    j, _, gestoppt = _takt(tmp_path, venue)
    assert gestoppt is True
    assert venue.halt_reason == "tagesverlust"
    saetze = _saetze(j)
    assert [s for s in saetze if s["art"] == "notbremse"]
    assert not [
        s for s in saetze if s["art"] == "signalbasis" and s["zweck"] == "eintritt"
    ], "Nach der Notbremse wird nichts mehr gerechnet"


# --- Kurse je Takt ---------------------------------------------------------
def test_auch_das_instrument_mit_position_bekommt_seinen_kurs(tmp_path: Path) -> None:
    """Der gemessene Befund: 71 Kurspunkte fuer Instrumente OHNE Position, einer fuer
    das MIT Position.

    Preis und Spread standen frueher nur im Daten-Tor eines Eroeffnungsversuchs -- und
    der entsteht nicht, wenn das Symbol schon offen ist. Der Verlauf fehlte also
    ausgerechnet dort, wo Geld stand.

    Mutationsprobe: die Kursschleife hinter ``if symbol not in lage`` gehaengt -- dann
    fehlt XAUUSD, und dieser Fall faellt.
    """
    venue = HaltVenue(positionen=(_position(),))
    j, _, _ = _takt(tmp_path, venue)
    symbole = {s["symbol"] for s in _saetze(j) if s["art"] == "kurs"}
    assert symbole == {"EURUSD", "XAUUSD"}


def test_ein_kursausfall_nimmt_den_takt_nicht_mit(tmp_path: Path) -> None:
    """Ein Instrument ohne Tick ist kein Grund, den ganzen Takt zu verlieren."""
    venue = HaltVenue(positionen=(_position(),), kurs_fehler={"EURUSD"})
    j, _, _ = _takt(tmp_path, venue)
    symbole = {s["symbol"] for s in _saetze(j) if s["art"] == "kurs"}
    assert symbole == {"XAUUSD"}
    assert [s for s in _saetze(j) if s["art"] == "takt"]


def test_der_takt_traegt_die_positionen_mit_ihren_zahlen(tmp_path: Path) -> None:
    """Ohne diesen Block laesst sich eine Equity-Bewegung nicht zerlegen.

    Man saehe die Kurve zappeln und wuesste nicht, ob ein Trade zuging oder eine
    Position nur schwankt. Geprueft wird zugleich, dass verschachtelte ``Decimal``
    ueberhaupt durch ``_jsonfaehig`` kommen -- eine Zahl in einer Liste von
    Woerterbuechern ist der Fall, an dem eine flache Umwandlung zerbricht.
    """
    venue = HaltVenue(positionen=(_position(),))
    j, _, _ = _takt(tmp_path, venue)
    satz = next(s for s in _saetze(j) if s["art"] == "takt")
    assert satz["balance"] == "50000"
    assert satz["unrealisiert"] == "-2.68"
    assert satz["positionen"] == [{
        "symbol": "XAUUSD", "ist_kauf": True, "volumen": "0.01",
        "seit": T0.isoformat(timespec="seconds"), "position_id": "10060725485",
        "einstiegspreis": "4415.18", "unrealisiert": "-2.68", "swap": "-0.11",
    }]


# --- Der eigene Schluss, wenn er misslingt --------------------------------
def test_ein_misslungener_schluss_wird_nicht_als_schluss_verbucht(
    tmp_path: Path,
) -> None:
    """Sonst laeuft der Positionszaehler in die andere Richtung von der Wirklichkeit
    weg -- die Drossel liesse dann mehr zu, als offen sein darf.

    Von Hand: ``record_close`` steht NACH ``submit_order``. Wirft das Senden, darf
    weder gebucht noch ein ``geschlossen``-Satz geschrieben werden; stattdessen der
    Fehlersatz, und der Rueckgabewert ist ``False``.
    """

    class WerfendesVenue:
        def submit_order(self, anfrage: Any) -> _Angenommen:
            raise VenueUnavailableError("Handelsserver antwortet nicht")

    manager = RiskManager()
    manager.record_open_fill("XAUUSD", T0)
    j = _journal(tmp_path)
    assert _schliesse(
        WerfendesVenue(), manager, _lage(), T0, "signalwechsel", j, waehrung="EUR",
    ) is False
    assert manager.open_position_count == 1, (
        "Ein misslungener Schluss darf die Position nicht aus dem Buch nehmen"
    )
    saetze = _saetze(j)
    assert not [s for s in saetze if s["art"] == "geschlossen"]
    fehler = next(s for s in saetze if s["art"] == "schliessen_fehlgeschlagen")
    assert fehler["symbol"] == "XAUUSD"
    assert fehler["grund"] == "signalwechsel"
    assert "antwortet nicht" in fehler["fehler"]


# --- Journal und Codestand ------------------------------------------------
def test_das_journal_haengt_an_und_ueberschreibt_nie(tmp_path: Path) -> None:
    """Ein Betriebsprotokoll, das sich nachtraeglich aendern laesst, ist als Beleg
    wertlos.

    Geprueft wird der harte Fall: ein ZWEITES ``Journal``-Objekt auf derselben Datei.
    Genau so entsteht die Lage nach einem Neustart -- und ein ``open(..., "w")``
    loeschte dann alles, was der abgestuerzte Lauf noch protokolliert hatte.
    """
    pfad = tmp_path / "journal-test.jsonl"
    Journal(pfad, lauf="a", version="v1").schreib("start", nr=1)
    Journal(pfad, lauf="b", version="v2").schreib("start", nr=2)
    zeilen = [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines()]
    assert [z["nr"] for z in zeilen] == [1, 2]
    assert [z["lauf"] for z in zeilen] == ["a", "b"]
    assert [z["version"] for z in zeilen] == ["v1", "v2"]


def test_ein_schmutziger_baum_steht_im_codestand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei Laeufe mit unterschiedlichem Code sehen im Journal sonst identisch aus.

    Ein angehaengtes ``+aenderungen`` sagt, dass der Baum beim Start nicht sauber war
    -- der Commit allein beschreibt den Lauf dann naemlich nicht. Kein echter
    ``git``-Aufruf: der haenge an der Arbeitskopie, in der der Test gerade laeuft.
    """
    antworten = iter(["abc1234", " M tools/live_betrieb.py"])

    def fake_run(*_a: Any, **_k: Any) -> Any:
        class Ergebnis:
            stdout = next(antworten) + "\n"
        return Ergebnis()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _codestand() == "abc1234+aenderungen"


def test_ein_sauberer_baum_traegt_nur_den_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe -- sonst stuende ``+aenderungen`` immer da und saegte nichts."""
    antworten = iter(["abc1234", ""])

    def fake_run(*_a: Any, **_k: Any) -> Any:
        class Ergebnis:
            stdout = next(antworten) + "\n"
        return Ergebnis()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _codestand() == "abc1234"


def test_ohne_git_bleibt_der_codestand_unbekannt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die CI faehrt ohne Arbeitskopie durch -- ein Absturz hier toetete den Lauf,
    bevor der erste Takt gelaufen waere. ``unbekannt`` ist eine Aussage, kein Rateschluss.
    """

    def fake_run(*_a: Any, **_k: Any) -> Any:
        raise OSError("git nicht gefunden")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _codestand() == "unbekannt"


# --- Das Journal und die eingefrorene Uhr ----------------------------------
def test_das_journal_wandelt_zeitstempel_auch_bei_ausgetauschter_uhr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Roter Eichfall zu einem Defekt, der nur unter eingefrorener Uhr auftrat.

    ``tools.live_betrieb.datetime`` ist zweierlei zugleich: die Uhr des Moduls
    (jedes ``datetime.now(UTC)`` liest diesen Namen) und frueher auch der Typ, gegen
    den ``_jsonfaehig`` prueft. Wer die Uhr zum Einfrieren durch eine Unterklasse
    ersetzt -- wie es mehrere Faelle in dieser Datei tun --, verschob damit
    unbeabsichtigt auch die Typpruefung: ein echter ``datetime`` ist keine Instanz
    der Ersatzklasse, fiel unkonvertiert durch, und ``json.dumps`` warf mitten im
    Schreiben eines Betriebssatzes.

    Der Fall friert die Uhr genauso ein und schreibt einen Zeitstempel, der NICHT
    von der Ersatzklasse stammt. Bindet ``_jsonfaehig`` seine Typpruefung wieder an
    den Modulnamen, wird er rot.
    """
    fix = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    class _StehendeUhr(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # noqa: ARG003 - Signatur der Basis
            return fix

    monkeypatch.setattr("tools.live_betrieb.datetime", _StehendeUhr)

    j = _journal(tmp_path)
    j.schreib("probe", seit=T0, verschachtelt=[{"seit": T0}])
    satz = _saetze(j)[0]
    assert satz["seit"] == T0.isoformat(timespec="seconds")
    assert satz["verschachtelt"][0]["seit"] == T0.isoformat(timespec="seconds")


def test_das_journal_wandelt_zeitstempel_ohne_ausgetauschte_uhr(tmp_path: Path) -> None:
    """Der gruene Eichfall daneben: ohne Eingriff muss dasselbe herauskommen.

    Ohne ihn belegte der rote Fall nur, dass es unter Eingriff geht -- nicht, dass
    der Normalfall unveraendert blieb.
    """
    j = _journal(tmp_path)
    j.schreib("probe", seit=T0, verschachtelt=[{"seit": T0}])
    satz = _saetze(j)[0]
    assert satz["seit"] == T0.isoformat(timespec="seconds")
    assert satz["verschachtelt"][0]["seit"] == T0.isoformat(timespec="seconds")


def test_jsonfaehig_prueft_nicht_gegen_den_modulnamen_datetime() -> None:
    """Dieselbe Regel am Syntaxbaum festgenagelt, nicht an ihrer Wirkung.

    Die beiden Faelle oben pruefen das Verhalten. Dieser haelt die Ursache fest:
    die Typpruefung darf nicht auf dem Namen liegen, der zugleich die Uhr ist --
    sonst kehrt der Defekt bei der naechsten Umformulierung still zurueck.
    """
    import ast
    import inspect

    baum = ast.parse(inspect.getsource(_jsonfaehig))
    namen = {
        arg.id
        for aufruf in ast.walk(baum)
        if isinstance(aufruf, ast.Call)
        and isinstance(aufruf.func, ast.Name)
        and aufruf.func.id == "isinstance"
        for arg in ast.walk(aufruf.args[1])
        if isinstance(arg, ast.Name)
    }
    assert "datetime" not in namen, (
        "_jsonfaehig prueft wieder gegen den Modulnamen 'datetime' -- genau der wird "
        "zum Einfrieren der Uhr ausgetauscht. Den Alias _DATETIME benutzen."
    )
    assert "_DATETIME" in namen, "Die Zeitstempel-Wandlung fehlt ganz."

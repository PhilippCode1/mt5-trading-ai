#!/usr/bin/env python3
"""Beaufsichtigter Demo-Handelsbetrieb: ein Tag, volle Kette, alles protokolliert.

WAS DIESES WERKZEUG IST
-----------------------
Die Dauerschleife, die ``execution/runner.py`` fehlt. Sie eroeffnet
**und schliesst**, haelt die Buchfuehrung mit dem Broker gleich und schreibt jede
Entscheidung in ein Journal, das hinterher ehrlich auswertbar ist.

**Nur Demokonto.** ``require_demo=True`` bleibt gesetzt; ``RealMt5Terminal`` lehnt jeden
Schreibzugriff auf einem Live-Konto ab. Das ist keine Einstellung dieses Werkzeugs,
sondern eine Sperre eine Ebene tiefer.

DER AUSSTIEG -- DIE LUECKE, DIE HIER GESCHLOSSEN WIRD
------------------------------------------------------
``run_signal`` eroeffnet nur. Eine Position kam bisher ausschliesslich durch den
broker-seitigen Stop wieder heraus. Ueber 24 Stunden heisst das: Positionen sammeln
sich an, ein Signalwechsel eroeffnet eine **Gegen**position statt zu drehen, und
``RiskManager.record_close`` wird nie gerufen -- der Positionszaehler laeuft von der
Wirklichkeit weg, und die Drossel zaehlt falsch.

Diese Schleife schliesst drei Wege:

1. **Signalwechsel** -- kippt das Signal gegen eine offene Position, wird sie
   glattgestellt.
2. **Hoechsthaltedauer** -- keine Position laeuft laenger als ``--max-haltedauer``.
3. **Am Ende des Laufs** -- ``--am-ende-schliessen`` (Vorgabe) laesst nichts uebers
   Wochenende stehen.

Geschlossen wird ueber ``reduce_only=True``. Das ueberspringt die **Eroeffnungs**tore --
absichtlich und nur dann, wenn die Order eine tatsaechlich offene Gegenposition abbaut
(``Mt5Venue._reduces_position``). Eine Sperre, die das Schliessen verhindert, waere
gefaehrlicher als das Schliessen selbst.

ZULASSUNG UND SCHREIBRECHT SIND ZWEI DINGE (Z, E-010)
-----------------------------------------------------
Der Orderpfad prueft als Erstes die §9.3-Zulassung: ohne bestandenes Bewertungstor
handelt keine Strategie. **Es gibt keine bestandene Zulassung** -- alle sieben Studien
aus Paket 3a sind gescheitert (``archiv/ABSCHLUSS-3a/05-URTEIL.md``).

Bis 306bbaa setzte ``--scharf "<Text>"`` beides zugleich: das Schreibrecht am Terminal
UND ein bestandenes Zulassungsurteil -- ein Freitext ersetzte ein Tor (15 von 21
Demolaeufen liefen so, Bewertung §3.5). Das Argument gibt es nicht mehr; ``argparse``
weist es mit Exit 2 ab. An seine Stelle treten zwei getrennte Schalter:

* ``--demo-schreiben`` gibt dem Terminal das Schreibrecht (``allow_write``);
  ``require_demo`` bleibt ``True``, das Terminal schreibt nur auf ein Demokonto.
* ``--zulassung <datei>`` verweist auf einen Registereintrag (JSON mit ``strategie``,
  ``torurteil_hash``, ``datum``, ``kennung``). Fehlt die Datei oder ein Feld, ist
  nichts zugelassen -- die Kette haelt an der Zulassung (``zulassung_lesen``).

Ohne Schreibrecht erreicht die Kette das Terminal nie (D1): sie wird nicht erkundet,
und auch eine zugelassene Strategie endet vor dem Senden mit ``kein_schreibrecht``
(``execution/runner.py``). Alle uebrigen Sperren bleiben scharf -- Frische, Hebel,
Kostentor, Kill-Switch, Drossel, Stop-Budget, Sizing.

DER ZUSTAND LIEGT IM ZUSTANDSORDNER (D8, A18)
---------------------------------------------
Risikozustand, Schwebeakte, Positionsbuch, Stoppdatei und Journale liegen in EINEM
Ordner ausserhalb des Arbeitsbaums: ``--zustandsordner`` (Vorgabe
``standard_zustandsordner()``, unter Windows
``%LOCALAPPDATA%\mt5_trading_ai\risiko``).
Keine Umgebungsvariable schaltet das ein oder aus; ``RiskManager``, ``SchwebeAkte``
und ``Positionsbuch`` sind ohne Ort nicht konstruierbar, und ein fluechtiger Zustand
(die Testtypen ``FluechtigerZustand`` usw.) wird hier abgewiesen
(``zustand_abweisen``). Gemessen gegen 306bbaa: der Betrieb baute ``RiskManager()``
ohne Zustand -- 21 Laeufe, kein Halt ueberdauerte einen Neustart.

Beim Start gleicht ``Mt5Venue.adopt_book`` Risikozaehler und Positionsbuch gegen
``positions_get()`` ab (D7); Geister werden ausgetragen und als ``startabgleich``-Satz
journalisiert. Ein Halt-Grund wird nie ueberschrieben (D4): dieser Lauf loest nur den
Anteil, den er selbst erklaeren kann (``halt_grund_loesen``), nie die Notbremse.

DAS TERMINAL
------------
``--terminal real`` (Vorgabe) bindet MetaTrader 5 auf diesem Rechner; ist es nicht
erreichbar, endet der Lauf mit genau einer Zeile ``FEHLGESCHLAGEN -- MT5-Terminal nicht
erreichbar: <Grund>`` und Exit 2 (A12). ``--terminal fake`` faehrt die Betriebsattrappe
``venue/fake.py`` -- kein MetaTrader5-Import, kein Broker; das ist der Trockenlauf der
Eichfaelle und der Startpunkt des ``kill``-Eichfalls (A6).

AUF WELCHER KERZE GERECHNET WIRD
---------------------------------
Auf der **letzten abgeschlossenen** -- nie auf der laufenden. Der Handelsplatz liefert
bei ``end=jetzt`` die noch in Bildung befindliche Kerze mit; ihr ``close`` ist der
momentane Kurs und wandert weiter. Wer darauf rechnet, faehrt live eine andere
Strategie als die getestete, denn der Backtest kennt nur fertige Kerzen aus Dateien.

Die Entscheidung faellt in ``_signal`` ueber ``Bar.is_closed`` (gemessen in
``venue/mt5.py:get_bars`` gegen die Platzzeit) und wird in **jedem** Takt als
``signalbasis``-Satz protokolliert: welche Kerze, wie viele abgeschlossene geliefert
wurden, wie viele davon wirklich in die Rechnung eingehen, wie viele als laufend
verworfen wurden. Ohne diesen Satz war beim letzten Zweifel nicht feststellbar, was die
Maschine wirklich gerechnet hat -- die Auskunft war nie geschrieben worden.

WAS DER LAUF NICHT BEANTWORTET
-------------------------------
Ob die Strategie taugt. Ein Tag sind bei diesen Grenzen hoechstens zehn Trades. Das ist
keine Stichprobe, aus der man etwas ueber einen Vorteil lernt -- es ist eine Probe, ob
die **Maschine** sauber laeuft. Wer die Parameter hinterher auf das Tagesergebnis dreht,
tut genau das, wogegen die Deflation in diesem Repo gebaut ist.

Aufruf::

    python tools/live_betrieb.py --dauer 1 --takt 60
    python tools/live_betrieb.py --terminal fake --zustandsordner <ordner> --dauer 0.01
    python tools/live_betrieb.py --dauer 24 --demo-schreiben --zulassung <register.json>
"""

from __future__ import annotations

import argparse
import json
import signal as signalmodul
import subprocess
import sys
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import FrameType
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.engine import MarketView, Signal  # noqa: E402
from mt5_trading_ai.backtest.strategies import moving_average_crossover  # noqa: E402
from mt5_trading_ai.data.quality import BarRow  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    JOURNALORDNER_NAME,
    STOPPDATEI_NAME,
    DateiZustand,
    ZustandsortFehler,
    standard_zustandsdatei,
    standard_zustandsordner,
    zustandsordner_waehlen,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal  # noqa: E402
from mt5_trading_ai.execution.scheduler import SyncScheduler  # noqa: E402
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.venue.catalog import load_instrument_catalog  # noqa: E402
from mt5_trading_ai.venue.fake import FakeMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Terminal,
    Mt5Venue,
    RealMt5Terminal,
    ServerversatzFehler,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    VenueError,
    VenueUnavailableError,
)

REPO = Path(__file__).resolve().parents[1]
#: Die Stoppdatei liegt im Zustandsordner (``STOPPDATEI_NAME``), nicht mehr unter
#: ``betrieb/`` im Arbeitsbaum (A18). Wer sie anlegt, beendet den Lauf geordnet. Unter
#: Windows gibt es fuer einen abgekoppelten Prozess kein zuverlaessiges Signal: Strg-C
#: braucht ein Konsolenfenster, und ``taskkill /F`` toetet hart -- der finally-Block
#: liefe nicht, und die Positionen blieben offen. Eine Datei ist plattformunabhaengig,
#: braucht keine Rechte und kann nicht danebengehen.
TERMINALARTEN: tuple[str, ...] = ("real", "fake")

#: Trendfolge, Parameter per Konvention. NICHT auf Daten optimiert und nicht als
#: Vorschlag gemeint -- diese Logik hat nie ein Bewertungstor bestanden.
SCHNELL, LANGSAM = 12, 26
KERZEN_STUNDEN = 360


@dataclass
class Lage:
    """Was die Schleife ueber eine offene Position weiss.

    ``position_id`` und ``einstiegspreis`` kamen frueher vom Handelsplatz und wurden
    hier weggeworfen. Genau sie fehlten dann im Protokoll, und ohne sie laesst sich das
    Ergebnis eines einzelnen Trades nicht rekonstruieren.
    """

    symbol: str
    ist_kauf: bool
    volumen: Decimal
    seit: datetime
    position_id: str
    einstiegspreis: Decimal
    unrealisiert: Decimal
    swap: Decimal


class Journal:
    """Anhaengendes JSONL. Jede Zeile ein Ereignis, jede Zeile mit Zeitstempel.

    Anhaengend und nie ueberschreibend -- ein Betriebsprotokoll, das sich nachtraeglich
    aendern laesst, ist als Beleg wertlos.
    """

    def __init__(self, pfad: Path, *, lauf: str, version: str) -> None:
        self.pfad = pfad
        #: Kennung dieses Laufs. Ohne sie steckt die Zugehoerigkeit allein im
        #: Dateinamen -- zusammenkopierte Journale waeren nicht mehr auftrennbar.
        self.lauf = lauf
        #: Codestand, unter dem der Lauf lief. Zwei Laeufe mit unterschiedlichem
        #: Code sehen sonst identisch aus, und genau dort wird eine laufuebergreifende
        #: Auswertung still falsch.
        self.version = version
        pfad.parent.mkdir(parents=True, exist_ok=True)

    def schreib(self, art: str, **felder: Any) -> None:
        zeile = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "art": art,
            "lauf": self.lauf,
            "version": self.version,
        }
        zeile.update({k: _jsonfaehig(v) for k, v in felder.items()})
        with self.pfad.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(zeile, ensure_ascii=False) + "\n")


#: Die Klasse fuer die Typpruefung im Journal -- bewusst NICHT ueber den Modulnamen
#: ``datetime``. Der Name ist zugleich die Uhr dieses Moduls (jedes
#: ``datetime.now(UTC)`` liest ihn), und eine Uhr wird zum Einfrieren
#: ausgetauscht. Wird sie durch eine
#: Unterklasse ersetzt, urteilt ein ``isinstance`` gegen denselben Namen gegen die
#: Ersatzklasse: echte Zeitstempel sind keine Instanzen von ihr, fallen unkonvertiert
#: durch und lassen ``json.dumps`` werfen -- mitten im Schreiben eines Betriebssatzes.
#: Der Alias bindet die echte Klasse einmal beim Import und trennt damit die beiden
#: Aufgaben, die sonst auf einem Namen liegen: Uhr sein und Typ sein.
_DATETIME = datetime


def _jsonfaehig(wert: Any) -> Any:
    if isinstance(wert, Decimal):
        return str(wert)
    if isinstance(wert, _DATETIME):
        return wert.isoformat(timespec="seconds")
    if isinstance(wert, list | tuple):
        return [_jsonfaehig(x) for x in wert]
    if isinstance(wert, dict):
        return {k: _jsonfaehig(v) for k, v in wert.items()}
    return wert


@dataclass(frozen=True)
class Signallage:
    """Ein Signal samt der Kerze, auf der es entstanden ist.

    ``_signal`` gab frueher nur ``(Signal, str)`` zurueck; welche Kerze gerechnet
    wurde, blieb im Verfahren. Als sich zeigte, dass live auf der noch in Bildung
    befindlichen Kerze gerechnet wurde, war an keinem Journal nachweisbar, seit wann
    und wie oft -- die Auskunft war nie geschrieben worden. Darum reist sie jetzt mit
    und landet in jedem Takt im Protokoll.
    """

    signal: Signal
    detail: str
    #: Beginn der JUENGSTEN ABGESCHLOSSENEN Kerze, auf der gerechnet wurde. ``None``
    #: heisst: es wurde gar nicht gerechnet (keine Kerzen, zu wenige abgeschlossene).
    kerze_ts: datetime | None
    #: Wie viele ABGESCHLOSSENE Kerzen der Handelsplatz geliefert hat. Bei
    #: ``KERZEN_STUNDEN=360`` sind das rund 359 -- und eben NICHT die Zahl, auf der
    #: gerechnet wurde.
    kerzen_abgeschlossen: int
    #: Wie viele davon wirklich in die Rechnung eingehen. ``moving_average_crossover``
    #: sieht nur ``history[-slow:]``, also die letzten ``LANGSAM``. Dieses Feld hiess
    #: schon frueher so und meldete trotzdem die gelieferte Zahl: im Journal stuende
    #: dann "kerzen_verwendet: 359", wo 26 gerechnet wurden. ``0`` heisst: es wurde
    #: gar nicht gerechnet.
    kerzen_verwendet: int
    #: Wie viele gelieferte Kerzen als noch laufend verworfen wurden. Steht im
    #: Protokoll, weil eine Null hier der Hinweis waere, dass die Kennzeichnung nicht
    #: mehr ankommt -- und dann rechnete der Live-Treiber wieder auf dem Kurs statt
    #: auf einem Schlusskurs, ohne dass es jemandem auffiele.
    kerzen_laufend: int


def _signal(venue: Mt5Venue, symbol: str, jetzt: datetime) -> Signallage:
    """Trendfolge auf den ABGESCHLOSSENEN Live-Stundenkerzen.

    Bis hierher lief der gleitende Durchschnitt ueber ``MarketView(reihe,
    len(reihe) - 1)``, also ueber die letzte gelieferte Kerze -- und die ist bei
    ``end=jetzt`` die noch in Bildung befindliche. Ihr ``close`` ist der momentane
    Kurs und wandert bis zum Intervallende weiter. Der Backtest kennt diese Zahl
    nicht; dort kommen die Kerzen fertig aus Dateien. Live-Signal und getestetes
    Signal waren damit **nicht dieselbe Strategie**, und kein Demolauf haette das
    klaeren koennen, gleichgueltig wie er ausgeht.

    ``is_closed`` kommt vom Handelsplatz (``venue/mt5.py:get_bars`` misst es gegen die
    Platzzeit) und wird hier **nicht nachgerechnet**. Eine zweite Rechnung waere eine
    zweite Wahrheit, und die faellt beim naechsten Zeitraster still auseinander. Fehlt
    das Feld, wirft der Zugriff -- das ist gewollt: ohne die Auskunft ist nicht
    entscheidbar, worauf gerechnet wird, und nicht entscheidbar heisst nicht handeln.

    Zu wenige abgeschlossene Kerzen ergeben ``FLAT``. Das ist kein Vorgabewert,
    sondern die Aussage "kein Signal": FLAT eroeffnet nichts und schliesst nichts.
    """
    try:
        bars = venue.get_bars(
            symbol,
            Timeframe.H1,
            start=jetzt - timedelta(hours=KERZEN_STUNDEN),
            end=jetzt,
        )
    except VenueError as exc:
        return Signallage(
            signal=Signal.FLAT,
            detail=f"keine Kerzen: {exc}",
            kerze_ts=None,
            kerzen_abgeschlossen=0,
            kerzen_verwendet=0,
            kerzen_laufend=0,
        )
    fertig = [b for b in bars if b.is_closed]
    laufend = len(bars) - len(fertig)
    if len(fertig) < LANGSAM:
        return Signallage(
            signal=Signal.FLAT,
            detail=f"nur {len(fertig)} abgeschlossene von {len(bars)} Kerzen",
            kerze_ts=None,
            kerzen_abgeschlossen=len(fertig),
            kerzen_verwendet=0,
            kerzen_laufend=laufend,
        )
    reihe = [
        BarRow(
            ts=b.ts,
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=None,
        )
        for b in fertig
    ]
    sig = moving_average_crossover(SCHNELL, LANGSAM)(MarketView(reihe, len(reihe) - 1))
    # DIESELBE Auswahl, die die Strategie trifft (``history[-slow:]``), und nur sie
    # geht als "verwendet" ins Protokoll. Der Handelsplatz liefert Hunderte Kerzen;
    # gerechnet wird auf den letzten LANGSAM. Ein Feld ``kerzen_verwendet``, das die
    # gelieferte Zahl meldet, waere ein Etikett ohne Deckung -- und ausgerechnet die
    # Zahl, an der man haette ablesen sollen, worauf die Maschine rechnet.
    verwendet = reihe[-LANGSAM:]
    schluesse = [b.close for b in verwendet]
    return Signallage(
        signal=sig,
        detail=(
            f"MA{SCHNELL}={sum(schluesse[-SCHNELL:]) / SCHNELL:.5f} "
            f"MA{LANGSAM}={sum(schluesse) / LANGSAM:.5f}"
        ),
        kerze_ts=reihe[-1].ts,
        kerzen_abgeschlossen=len(fertig),
        kerzen_verwendet=len(verwendet),
        kerzen_laufend=laufend,
    )


def _signal_mit_protokoll(
    venue: Mt5Venue, symbol: str, jetzt: datetime, journal: Journal, *, zweck: str
) -> Signallage:
    """Signal ableiten UND festhalten, worauf gerechnet wurde.

    Geschrieben wird bei JEDER Ableitung, auch bei ``FLAT`` und auch im Ausstiegspfad.
    Der bisherige ``signal``-Satz entstand nur, wenn ein Eintrittssignal anlag -- an
    einem Takt ohne Satz war darum nicht unterscheidbar, ob kein Signal vorlag, ob das
    Instrument schon offen war oder ob die Kerzenabfrage gescheitert ist. Und die
    Kerze, auf der gerechnet wurde, stand nirgends. Genau diese Luecke hat den Befund
    "der Live-Treiber rechnet auf der laufenden Kerze" so lange verdeckt.
    """
    lage = _signal(venue, symbol, jetzt)
    journal.schreib(
        "signalbasis",
        symbol=symbol,
        zweck=zweck,
        signal=lage.signal.name,
        kerze_ts=lage.kerze_ts,
        kerzen_abgeschlossen=lage.kerzen_abgeschlossen,
        kerzen_verwendet=lage.kerzen_verwendet,
        kerzen_laufend_verworfen=lage.kerzen_laufend,
        detail=lage.detail,
    )
    return lage


def _lage_lesen(venue: Mt5Venue) -> dict[str, Lage]:
    """Die WIRKLICH offenen Positionen, vom Terminal. Nicht aus dem Gedaechtnis.

    ``opened_at`` kommt in ECHTEM UTC: der Takt misst den Serverversatz (D20) und
    dreht selbst (siehe ``RealMt5Terminal._utc``). Hier darf darum **nicht** noch
    einmal gedreht werden -- eine zweite Drehung waere ein zweiter Versatz, und einem
    Zeitstempel sieht man nicht an, wie oft er schon gedreht wurde.

    Ungedreht war das Alter einer Position um 2-3 Stunden zu klein -- gemessen am
    laufenden Betrieb: real 0,77 h alt, gerechnet -2,23 h. Die Hoechsthaltedauer von
    vier Stunden feuerte damit erst nach sieben realen Stunden.
    """
    aus: dict[str, Lage] = {}
    for p in venue.get_positions():
        aus[p.symbol] = Lage(
            symbol=p.symbol,
            ist_kauf=p.side is OrderSide.BUY,
            volumen=p.volume,
            seit=p.opened_at,
            position_id=p.venue_position_id,
            einstiegspreis=p.entry_price,
            unrealisiert=p.unrealised_pnl,
            swap=p.swap_accrued,
        )
    return aus


def _schliesse(
    venue: Mt5Venue,
    manager: RiskManager,
    lage: Lage,
    jetzt: datetime,
    grund: str,
    journal: Journal,
    *,
    waehrung: str,
) -> bool:
    """Glattstellen ueber ``reduce_only``. Gibt True bei Erfolg."""
    anfrage = OrderRequest(
        client_order_id=f"close-{lage.symbol}-{uuid.uuid4().hex[:10]}",
        symbol=lage.symbol,
        side=OrderSide.SELL if lage.ist_kauf else OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=lage.volumen,
        stop_loss=Decimal("0"),  # bei reduce_only nicht geprueft -- kein Stop noetig
        reduce_only=True,
        position_ticket=lage.position_id,  # D2: Schliessung nur mit Ticket
        comment=f"live_betrieb: {grund}",
    )
    try:
        ergebnis = venue.submit_order(anfrage)
    except VenueError as exc:
        journal.schreib(
            "schliessen_fehlgeschlagen",
            symbol=lage.symbol,
            grund=grund,
            fehler=str(exc),
        )
        return False
    manager.record_close(lage.symbol)
    # Preis, Volumen und Positions-ID gehoeren ins Protokoll. Ohne sie laesst sich
    # nicht sagen, was ein einzelner Trade gemacht hat -- ``order_id`` ist die Kennung
    # der SCHLIESSENDEN Order und verbindet nichts mit der Eroeffnung.
    #
    # Das Geldergebnis steht AUCH hier, obwohl bei einem selbst gesetzten Schluss
    # beide Preise vorliegen und das Preisergebnis das bessere ist. Grund: traegen es
    # nur die broker-seitigen Schluesse, dann besteht jede Geldstatistik ausschliesslich
    # aus Stop-Outs, also aus Verlierern -- derselbe blinde Fleck wie zuvor, nur mit
    # umgekehrtem Vorzeichen.
    #
    # Das gilt aber nur, solange die Geldstatistik den Satz auch liest.
    # ``Trade.urteilsquelle`` gibt dem gemessenen Preis den Vorrang, ein selbst
    # geschlossener Trade steht darum NIE im Topf "nur Geld". Die Geldsumme laeuft
    # deshalb ueber ``journal.geldbilanz`` und damit ueber ALLE Geldergebnisse; haengte
    # sie am Topf "nur Geld", waere dieses Feld hier wirkungslos und der blinde Fleck
    # bliebe bestehen.
    journal.schreib(
        "geschlossen",
        symbol=lage.symbol,
        grund=grund,
        volumen=lage.volumen,
        war_kauf=lage.ist_kauf,
        order_id=ergebnis.venue_order_id,
        client_order_id=anfrage.client_order_id,
        position_id=lage.position_id,
        ausstiegspreis=ergebnis.average_price,
        gefuellt=ergebnis.filled_volume,
        einstiegspreis=lage.einstiegspreis,
        seit=lage.seit,
        ergebnis_geld=lage.unrealisiert,
        ergebnis_geld_waehrung=waehrung,
        ergebnis_geld_quelle="zuletzt_beobachtet",
        zuletzt_swap=lage.swap,
    )
    print(f"  ZU   {lage.symbol} {lage.volumen} ({grund})")
    return True


def _eroeffne(
    venue: Mt5Venue,
    manager: RiskManager,
    symbol: str,
    sig: Signal,
    jetzt: datetime,
    zulassung: CriteriaVerdict,
    journal: Journal,
    *,
    darf_schreiben: bool,
) -> None:
    config = RunnerConfig(
        cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
    )
    try:
        bericht = run_signal(
            venue=venue,
            risk_manager=manager,
            admission=zulassung,
            symbol=symbol,
            side=sig,
            config=config,
            now=jetzt,
            client_order_id=f"open-{symbol}-{uuid.uuid4().hex[:10]}",
            # D1: ohne Schreibrecht endet die Kette vor dem Terminal -- keine
            # Erkundung, kein Sendeversuch, kein Akteneintrag, kein Halt.
            darf_schreiben=darf_schreiben,
        )
    except VenueError as exc:
        journal.schreib("eroeffnen_fehlgeschlagen", symbol=symbol, fehler=str(exc))
        return
    schritte = [{"naht": s.name, "ok": s.ok, "detail": s.detail} for s in bericht.steps]
    # Bei einer ANGENOMMENEN Order gehoeren Preis, Volumen und Kennungen als Zahlen ins
    # Protokoll -- nicht als Fliesstext in der Naht-Begruendung. Ohne sie fehlt der
    # Anfang jedes Trades, und ein Ergebnis laesst sich nicht rechnen.
    erg = bericht.submitted
    journal.schreib(
        "eroeffnungsversuch",
        symbol=symbol,
        signal=sig.name,
        eroeffnet=bericht.opened,
        grund=bericht.reject_reason,
        schritte=schritte,
        # Stufe 7/9: die Herkunftsspalte. Ohne diese beiden Felder sieht eine
        # erkundete Zeile in jeder spaeteren Auswertung aus wie eine regulaere, und
        # der gewichtete Mittelwert rechnet sie falsch.
        erkundet=bericht.erkundet,
        erkundung_p=bericht.erkundung_p,
        client_order_id=None if erg is None else erg.client_order_id,
        order_id=None if erg is None else erg.venue_order_id,
        einstiegspreis=None if erg is None else erg.average_price,
        gefuellt=None if erg is None else erg.filled_volume,
    )
    if bericht.opened:
        # Die Positions-ID kennt erst der Handelsplatz, nach dem Fill. Sie ist der
        # einzige Schluessel, der Eroeffnung und Schliessung verbindet.
        offen = _lage_lesen(venue).get(symbol)
        if offen is not None:
            journal.schreib(
                "eroeffnet",
                symbol=symbol,
                signal=sig.name,
                position_id=offen.position_id,
                volumen=offen.volumen,
                einstiegspreis=offen.einstiegspreis,
                seit=offen.seit,
                client_order_id=None if erg is None else erg.client_order_id,
            )
    if bericht.opened:
        print(f"  AUF  {symbol} {sig.name}")
    else:
        letzte = next((s for s in reversed(bericht.steps) if not s.ok), None)
        wo = letzte.name if letzte else "?"
        print(f"  --   {symbol} {sig.name}: {bericht.reject_reason} (bei {wo})")


def _startabgleich_journalisieren(venue: Mt5Venue, journal: Journal) -> None:
    """Was ``adopt_book`` gegen ``positions_get()`` fand, gehoert ins Journal (D7).

    Geister -- Positionen im eigenen Zustand, die der Broker nicht mehr fuehrt -- sind
    beim Abgleich bereits ausgetragen; hier steht, WELCHE es waren. Ein Buch, das
    stillschweigend schrumpft, waere so wenig nachvollziehbar wie eines, das ewig
    waechst.
    """
    abgleich = venue.startabgleich
    if abgleich is None:
        return
    journal.schreib("startabgleich", **abgleich.as_dict())
    for symbol, seit in abgleich.geister_zaehler:
        print(
            f"  GEIST {symbol} (Risikozaehler, seit {seit}) -- beim Broker nicht offen"
        )
    for buch in abgleich.geister_buch:
        print(f"  GEIST {buch.symbol} #{buch.ticket} (Positionsbuch) -- ausgetragen")
    if abgleich.defekt is not None:
        print(f"  !!   Positionsbuch defekt: {abgleich.defekt} -- Halt steht")


def _verbindung_sichern(
    venue: Mt5Venue, terminal: Mt5Terminal, journal: Journal, *, versuche: int = 10
) -> bool:
    """Nach einer Stoerung neu verbinden. Gibt False, wenn es endgueltig aus ist.

    Ohne diesen Pfad toetet jeder Terminal-Neustart den Lauf klebrig: ``reconcile``
    wirft, der Scheduler latcht ``reconcile_unavailable``, und der Halt bleibt die
    restlichen Stunden stehen, auch wenn das Terminal laengst wieder laeuft.
    """
    if venue.is_healthy():
        return True
    for i in range(versuche):
        pause = min(30.0, 5.0 * (i + 1))
        journal.schreib("reconnect_versuch", nr=i + 1, pause=pause)
        print(f"  ..   Verbindung weg, Versuch {i + 1}/{versuche} in {pause:.0f}s")
        time.sleep(pause)
        try:
            terminal.shutdown()
            if not terminal.initialize():
                continue
            venue.connect()
            venue.adopt_book()
        except (VenueError, OSError) as exc:
            journal.schreib("reconnect_fehler", nr=i + 1, fehler=str(exc))
            continue
        _startabgleich_journalisieren(venue, journal)
        # Nur Halts loesen, die von der Stoerung SELBST kommen. Ein Drawdown-,
        # Desync- oder Notbremsen-Halt bleibt stehen -- er hat einen anderen Grund.
        #
        # ``halt_grund_loesen`` nimmt genau die eigenen Anteile aus der Kette (D4)
        # und gibt sie zurueck; der Halt faellt erst, wenn kein Grund mehr steht.
        # Frueher las diese Stelle ``halt_reason`` und rief ``clear_halt()`` -- das
        # loeschte jeden Grund mit, auch den der Notbremse, und der Journalsatz trug
        # ``null``, weil der Grund NACH dem Loeschen gelesen wurde.
        geloest = (
            *venue.halt_grund_loesen("reconcile_unavailable"),
            *venue.halt_grund_loesen("account_unavailable"),
        )
        for grund in geloest:
            journal.schreib("halt_geloest", grund=grund)
        journal.schreib("reconnect_ok", nr=i + 1)
        print("  OK   Verbindung wieder da")
        return True
    journal.schreib("verbindung_verloren", offen_moeglich=True)
    print("  !!   Verbindung endgueltig verloren. Positionen koennen offen sein.")
    return False


def _buch_abgleichen(
    venue: Mt5Venue,
    manager: RiskManager,
    bekannt: dict[str, Lage],
    lage: dict[str, Lage],
    journal: Journal,
    *,
    waehrung: str,
) -> bool:
    """Was der Broker geschlossen hat, muss Manager UND Buch erfahren.

    Gibt ``True``, wenn etwas verschwunden ist. Der Aufrufer braucht die Nachricht,
    um einen dadurch ausgeloesten Reconcile-Halt als **erklaert** zu behandeln.

    Nur ``record_close`` zu rufen genuegt nicht: das lokale Positionsbuch der Venue
    behielte die Position, und der naechste ``reconcile`` saehe die Differenz als
    Drift. Bei ``max_notional_drift=0`` latcht das den Global-Halt -- ein voellig
    normales Trade-Ende waere dann bitgleich mit einem katastrophalen Desync.
    """
    verschwunden = [s for s in bekannt if s not in lage]
    if not verschwunden:
        return False
    for symbol in verschwunden:
        manager.record_close(symbol)
        # Was wir noch wissen, gehoert ins Protokoll: der Satz trug frueher NUR das
        # Symbol. Stop, Margin Call oder Handeingriff waren damit ununterscheidbar.
        weg = bekannt[symbol]
        # KEIN rekonstruierter Ausstiegspreis. Aus Buchwert, Volumen und
        # Kontraktgroesse liesse sich einer ausrechnen -- und genau das waere die
        # Sorte Zahl, die dieses Repo sonst ablehnt: sie stuende in
        # ``ausstiegspreis``, ununterscheidbar von einem gemessenen Fill, und der
        # Leser rechnete daraus ein ``ergebnis_bps`` in denselben Median wie die
        # echten. Drei Annahmen steckten in der Umkehrung (Kontraktgroesse,
        # Umrechnung in die Kontowaehrung, dass der Buchwert Swap und Kommission
        # wirklich draussen laesst), und die schwerste waere die vierte: der Buchwert
        # stammt vom ENDE DES VORIGEN TAKTS -- bis zu einen Takt vor dem wirklichen
        # Schluss --, und ein Stop fuellt ueblicherweise schlechter als der zuletzt
        # gesehene Kurs. Der Betrag traefe also systematisch zu guenstig.
        #
        # Belastbar ist dagegen das VORZEICHEN. Darum geht der Wert als ERGEBNIS IN
        # KONTOWAEHRUNG ins Protokoll: unter eigenem Namen, mit Waehrung und Herkunft
        # daneben, und ausdruecklich nicht als Preis. So bleibt der Betrag als
        # Schaetzung lesbar, waehrend die Ja/Nein-Frage beantwortbar wird. Ohne diese
        # Auskunft fielen genau die Stop-Outs -- also die Verlierer -- aus jedem
        # Trefferanteil heraus; gemessen am Lauf vom 17.08.2026: "Trades mit
        # rechenbarem Ergebnis: 0 von 1".
        #
        # Der Kurs zum Zeitpunkt der Erkennung wird hier NICHT zusaetzlich geholt: er
        # steht als ``kurs``-Satz desselben Takts bereits im Journal (Schritt 1b), und
        # er ist ohnehin der Preis der Erkennung, nicht der des Schlusses.
        journal.schreib(
            "vom_broker_geschlossen",
            symbol=symbol,
            volumen=weg.volumen,
            war_kauf=weg.ist_kauf,
            position_id=weg.position_id,
            einstiegspreis=weg.einstiegspreis,
            seit=weg.seit,
            zuletzt_unrealisiert=weg.unrealisiert,
            zuletzt_swap=weg.swap,
            ergebnis_geld=weg.unrealisiert,
            ergebnis_geld_waehrung=waehrung,
            ergebnis_geld_quelle="zuletzt_beobachtet",
            hinweis=(
                "Zeitpunkt ist der Takt, in dem das Verschwinden auffiel -- "
                "bis zu einen Takt spaeter als der wirkliche Schluss. "
                "ergebnis_geld ist der zuletzt beobachtete Buchwert VOR dem "
                "Verschwinden, brutto ohne Swap und Kommission: eine "
                "Schaetzung des Betrags, keine Messung -- und kein Preis. "
                "Ein Ausstiegspreis wird bewusst NICHT rekonstruiert."
            ),
        )
        print(f"  WEG  {symbol} (Broker hat geschlossen, vermutlich Stop)")
    nachher = venue.adopt_book()
    journal.schreib("buch_uebernommen", nachher=nachher, ausgeloest_durch=verschwunden)
    return True


def _notbremse(
    venue: Mt5Venue,
    manager: RiskManager,
    journal: Journal,
    *,
    equity_jetzt: Decimal,
    equity_start: Decimal,
    grenze: Decimal,
    lage: dict[str, Lage],
    jetzt: datetime,
    waehrung: str,
) -> bool:
    """Tagesverlustgrenze -- und zwar mit Glattstellung. Gibt True, wenn sie greift.

    Die Grenze aus ``risk/limits.py`` erzeugt nur ``REDUCE_ONLY``: sie sperrt den
    Einkauf und laesst laufende Verlustpositionen offen. Fuer einen unbeaufsichtigten
    Lauf ist das zu wenig -- wer nicht zusieht, muss darauf zaehlen koennen, dass bei
    Erreichen der Grenze wirklich Schluss ist.

    Bezugsgroesse ist die Equity beim START DES LAUFS, nicht der Kalendertag: ein Lauf,
    der um 14 Uhr beginnt, hat keinen Tagesanfang, den dieses Werkzeug kennen koennte.
    """
    if equity_start <= 0:
        return False
    verlust = (equity_start - equity_jetzt) / equity_start
    if verlust < grenze:
        return False
    print(
        f"  !!   NOTBREMSE: {verlust * 100:.2f} % Verlust seit Start "
        f"(Grenze {grenze * 100:.1f} %). Alles glattstellen."
    )
    journal.schreib(
        "notbremse",
        verlust_anteil=verlust,
        grenze=grenze,
        equity_start=equity_start,
        equity=equity_jetzt,
    )
    for offen in lage.values():
        _schliesse(
            venue, manager, offen, jetzt, "notbremse", journal, waehrung=waehrung
        )
    venue.latch_halt(reason="tagesverlust")
    return True


def _serverversatz_messen(
    terminal: object, symbole: list[str], journal: Journal
) -> None:
    """Am Kopf jedes Taktes: den Serverversatz messen, nicht annehmen (Befund D20).

    Bis 2026-09-04 drehte das Terminal seine Zeitstempel ueber eine feste Zone
    (``server_tz="Europe/Helsinki"``); ein Broker mit anderem Sommerzeittermin laege
    2-4 Wochen im Jahr eine Stunde daneben, und der Frische-Latch sperrte jeden
    Eintritt still. Jetzt misst ``RealMt5Terminal.messe_serverversatz`` je Takt --
    mit dem Takt als Frischebeweis (ein seit dem vorigen Takt vorgerueckter Tick).

    Drei Ausgaenge, alle im Journal:

    * Messung gelungen, vorher keine: ``serverversatz_gemessen``.
    * Messung gelungen, anderer Wert als bisher (Sommerzeitwechsel):
      ``serverversatz_geaendert`` mit alt und neu.
    * Messung gescheitert (Kursstrom steht, Rest zu gross): ohne fruehere Messung
      ``serverversatz_unmessbar`` -- dann gibt es in diesem Takt **keinen Eintritt**,
      und zwar nicht durch einen Schalter hier, sondern weil die ungedrehten Stempel
      den Frische-Latch des Venues rot stellen (``_enforce_account_freshness``) und
      ``is_trading_open`` denselben Stempel misst; mit frueherer Messung bleibt die
      alte stehen, ``serverversatz_nicht_erneuert`` sagt es.

    Gemessen wird am ersten Symbol, das misst -- nicht nur am ersten der Liste: die
    Liste ist alphabetisch (``BTCUSD`` zuerst), und ein Symbol, das dieser Broker
    ruhig oder gar nicht stellt, darf die Messung nicht fuer alle blockieren.
    Ein Terminal, das nicht ``RealMt5Terminal`` ist (Attrappe), hat nichts zu messen.
    """
    if not isinstance(terminal, RealMt5Terminal):
        return
    bisher = terminal.server_versatz
    gruende: list[str] = []
    for symbol in symbole:
        try:
            gemessen = terminal.messe_serverversatz(symbol)
        except ServerversatzFehler as exc:
            gruende.append(str(exc))
            continue
        if bisher is None:
            journal.schreib(
                "serverversatz_gemessen",
                symbol=symbol,
                stunden=gemessen.stunden,
                rest_s=gemessen.rest.total_seconds(),
                tick_alter_hoechstens_s=gemessen.tick_alter.total_seconds(),
            )
            print(
                f"  ..   Serverversatz gemessen: {gemessen.stunden:+d} h "
                f"(Rest {gemessen.rest.total_seconds():+.1f} s, {symbol})"
            )
        elif gemessen.versatz != bisher:
            journal.schreib(
                "serverversatz_geaendert",
                symbol=symbol,
                alt_stunden=round(bisher / timedelta(hours=1)),
                neu_stunden=gemessen.stunden,
                rest_s=gemessen.rest.total_seconds(),
            )
            print(
                f"  ..   Serverversatz geaendert: "
                f"{round(bisher / timedelta(hours=1)):+d} h -> {gemessen.stunden:+d} h"
            )
        return
    if bisher is None:
        journal.schreib("serverversatz_unmessbar", gruende=gruende)
        print("  !! Serverversatz nicht messbar -- kein Eintritt in diesem Takt")
    else:
        journal.schreib(
            "serverversatz_nicht_erneuert",
            bisher_stunden=round(bisher / timedelta(hours=1)),
            gruende=gruende,
        )


def takt(
    venue: Mt5Venue,
    manager: RiskManager,
    scheduler: SyncScheduler,
    symbole: list[str],
    zulassung: CriteriaVerdict,
    journal: Journal,
    *,
    nr: int,
    max_haltedauer: timedelta,
    bekannt: dict[str, Lage],
    equity_start: Decimal,
    verlustgrenze: Decimal,
    darf_schreiben: bool = False,
    terminal: object | None = None,
) -> tuple[dict[str, Lage], bool]:
    """Ein Takt. ``darf_schreiben`` ist die Vorgabe ``False``: ein fehlender Wert
    sperrt, der Takt rechnet dann trocken (D1)."""
    # 0) Serverversatz messen (D20) -- VOR dem Einfrieren von ``jetzt`` und vor jedem
    #    Zeitstempel, der aus dem Terminal kommt. Ohne ``terminal`` (Attrappe im
    #    Test) gibt es nichts zu messen.
    _serverversatz_messen(terminal, symbole, journal)
    jetzt = datetime.now(UTC)

    # 1) Herzschlag. Der Scheduler beobachtet die Equity (ohne das feuert die
    #    Notbremse nie) und latcht bei Verbindungs- oder Reconcile-Defekten.
    #    KEIN ``events=``: ohne konfigurierten Strom wirft ``apply_private_event``.
    tick = scheduler.tick(jetzt)
    konto = venue.get_account()
    lage = _lage_lesen(venue)
    print(
        f"[{jetzt.strftime('%H:%M:%S')}] Takt {nr} | Equity {konto.equity} "
        f"{konto.currency} | Halt: {'JA' if tick.halted else 'nein'}"
    )
    # Der Takt traegt alles, was den Kontozustand ausmacht -- nicht nur die Equity.
    # Ohne ``balance`` laesst sich eine Equity-Bewegung nicht in realisiertes Ergebnis
    # und offene Bewertung zerlegen: man saehe die Kurve zappeln und wuesste nicht, ob
    # ein Trade zuging oder eine Position nur schwankt. Die Positionsliste steht hier
    # ohnehin schon im Speicher; sie kostet keine zusaetzliche Abfrage.
    journal.schreib(
        "takt",
        nr=nr,
        equity=konto.equity,
        balance=konto.balance,
        marge_belegt=konto.margin_used,
        marge_frei=konto.margin_free,
        unrealisiert=sum((p.unrealisiert for p in lage.values()), Decimal("0")),
        halt=tick.halted,
        halt_grund=tick.halt_reason,
        demo=konto.is_demo,
        positionen=[
            {
                "symbol": p.symbol,
                "ist_kauf": p.ist_kauf,
                "volumen": p.volumen,
                "seit": p.seit,
                "position_id": p.position_id,
                "einstiegspreis": p.einstiegspreis,
                "unrealisiert": p.unrealisiert,
                "swap": p.swap,
            }
            for p in lage.values()
        ],
    )

    # 1b) Kurse je Takt -- UNABHAENGIG von Signal und Positionslage.
    #     Preis und Spread standen frueher nur im Daten-Tor eines Eroeffnungsversuchs,
    #     und der entsteht nicht, wenn das Symbol schon offen ist. Gemessen ueber 71
    #     Takte: fuer die Instrumente OHNE Position 71 Punkte, fuer die MIT Position
    #     genau einer. Der Verlauf fehlte also ausgerechnet dort, wo Geld stand.
    for symbol in symbole:
        try:
            q = venue.get_quote(symbol)
        except VenueError:
            continue
        journal.schreib("kurs", symbol=symbol, bid=q.bid, ask=q.ask, ts_kurs=q.ts)

    # 2) Buchfuehrung gleichziehen -- Manager UND Positionsbuch.
    erklaert = _buch_abgleichen(
        venue, manager, bekannt, lage, journal, waehrung=konto.currency
    )

    # Der Scheduler laeuft VOR diesem Abgleich und sieht die vom Broker geschlossene
    # Position noch im Buch -- bei max_notional_drift=0 latcht das den Global-Halt.
    # Gemessen am 17.08.2026, Takt 43: ein voellig normaler Stop-Fill auf XAUUSD
    # setzte reconcile_drift:notional_drift_exceeds_limit, und ab da eroeffnete der
    # Lauf nichts mehr.
    #
    # Aufgeloest wird NUR dieser eine Fall: ein Reconcile-Halt, fuer den in DEMSELBEN
    # Takt eine erkannte Schliessung vorliegt. Jeder andere Halt -- Drawdown, Desync,
    # Notbremse -- bleibt stehen. Eine Sperre, die sich selbst aufhebt, waere keine.
    #
    # Geloest wird der ANTEIL ``reconcile_drift`` der Halt-Kette, nicht der Halt als
    # Ganzes (D4): ``clear_halt()`` nahm frueher jeden Grund mit -- gemessen gegen
    # 306bbaa (V4) hatte ``reconcile()`` den Grund ``tagesverlust`` zuvor sogar
    # ueberschrieben, die Notbremse war also schon vor dem Loesen unsichtbar.
    geloest = (
        venue.halt_grund_loesen("reconcile_drift") if erklaert and tick.halted else ()
    )
    if geloest:
        grund_vorher = ", ".join(geloest)
        print(
            f"  ..   Halt aufgeloest: {grund_vorher} "
            f"war eine erkannte Broker-Schliessung"
        )
        tick = scheduler.tick(jetzt)
        # ``weiter_gesperrt`` ist der Zustand, der die Eintritte unter 4) WIRKLICH
        # regiert -- der ``takt``-Satz oben kann ihn nicht tragen, weil er vor dieser
        # Aufloesung geschrieben wird (und das muss so bleiben: die Notbremse unter 2b
        # kann vorher zurueckkehren, dann waere ein spaeter geschriebener Takt-Satz
        # ganz verloren).
        #
        # Ohne dieses Feld war aus dem Journal nicht ablesbar, ob ein Halt-Takt
        # tatsaechlich gesperrt hat. ``buchtreue`` zaehlte ihn als gesperrt, obwohl im
        # langen Lauf vom 2026-08-17 in JEDEM dieser Takte vier Eroeffnungsversuche
        # normal durchliefen -- einer davon fuehrte zu einer Eroeffnung.
        journal.schreib(
            "halt_erklaert",
            grund=grund_vorher,
            durch="broker_schliessung",
            weiter_gesperrt=tick.halted,
        )

    # 2b) Notbremse. Vor allem anderen, und sie stellt wirklich glatt.
    if _notbremse(
        venue,
        manager,
        journal,
        equity_jetzt=konto.equity,
        equity_start=equity_start,
        grenze=verlustgrenze,
        lage=lage,
        jetzt=jetzt,
        waehrung=konto.currency,
    ):
        return _lage_lesen(venue), True

    # 3) Ausstiege. Laufen AUCH bei Halt -- Schliessen muss immer moeglich bleiben.
    for symbol, offen in list(lage.items()):
        basis = _signal_mit_protokoll(venue, symbol, jetzt, journal, zweck="ausstieg")
        sig = basis.signal
        alter = jetzt - offen.seit
        gegen = (offen.ist_kauf and sig is Signal.SHORT) or (
            not offen.ist_kauf and sig is Signal.LONG
        )
        if gegen:
            _schliesse(
                venue,
                manager,
                offen,
                jetzt,
                "signalwechsel",
                journal,
                waehrung=konto.currency,
            )
        elif alter >= max_haltedauer:
            _schliesse(
                venue,
                manager,
                offen,
                jetzt,
                f"haltedauer_{alter.total_seconds() / 3600:.1f}h",
                journal,
                waehrung=konto.currency,
            )

    # 4) Eintritte. Nur wenn kein Halt und noch keine Position im Symbol.
    lage = _lage_lesen(venue)
    if not tick.halted:
        for symbol in symbole:
            if symbol in lage:
                continue
            if not venue.is_trading_open(symbol, at=jetzt):
                continue
            basis = _signal_mit_protokoll(
                venue, symbol, jetzt, journal, zweck="eintritt"
            )
            if basis.signal is Signal.FLAT:
                continue
            journal.schreib(
                "signal",
                symbol=symbol,
                signal=basis.signal.name,
                detail=basis.detail,
                kerze_ts=basis.kerze_ts,
            )
            _eroeffne(
                venue,
                manager,
                symbol,
                basis.signal,
                jetzt,
                zulassung,
                journal,
                darf_schreiben=darf_schreiben,
            )
    return _lage_lesen(venue), False


def _codestand() -> str:
    """Der Commit, unter dem dieser Lauf faehrt. ``unbekannt``, wenn kein Git da ist.

    Zwei Laeufe mit unterschiedlichem Code sehen im Journal sonst identisch aus -- und
    genau dort wird eine laufuebergreifende Auswertung still falsch. Ein angehaengtes
    ``+aenderungen`` sagt, dass der Baum beim Start nicht sauber war.
    """
    try:
        stand = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        schmutzig = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt"
    return f"{stand}+aenderungen" if schmutzig else stand


def _autotrading_an() -> bool:
    """Steht der AutoTrading-Knopf des Terminals auf an?

    Bewusst direkt ueber die MetaTrader5-Bibliothek: der Adapter bildet
    ``terminal_info().trade_allowed`` nicht ab, und diese eine Zahl entscheidet, ob ein
    scharfer Lauf ueberhaupt handeln kann.
    """
    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError:
        return False
    info = mt5.terminal_info()
    return bool(info is not None and info.trade_allowed)


def ausstiegszusage_pruefen(
    *, kann_schreiben: bool, schliesst_am_ende: bool, offene_symbole: Sequence[str]
) -> str | None:
    """Darf dieser Lauf ueberhaupt starten? ``None`` heisst ja, sonst der Grund.

    WARUM DIESER RIEGEL EXISTIERT
    -----------------------------
    Gemessen an den Betriebsjournalen vom 2026-08-17: **zwei Laeufe endeten mit offenen
    Positionen am Broker** (``['EURUSD','GBPUSD','XAUUSD']`` und
    ``['EURUSD','GBPUSD']``). Beide liefen ohne Schreibrecht (damals: ohne
    ``--scharf``).
    Beide haben beim Start ueber ``adopt_book()`` fremde Positionen uebernommen, einen
    Takt lang beaufsichtigt -- und **erst beim Herunterfahren** gemerkt, dass sie den
    zugesagten Ausstieg nicht fahren koennen. Fuenf der sieben misslungenen
    Schliessversuche dieses Standes stammen aus diesen zwei Laeufen.

    Der Fehler liegt nicht im Glattstellen. Er liegt darin, dass der Lauf **eine Zusage
    annimmt, die er von Anfang an nicht halten kann**. Ein Aufseher, der nicht
    aussteigen kann, ist kein Aufseher -- er ist ein Zuschauer, der so aussieht wie
    einer.

    Der Riegel steht deshalb VOR dem ersten Takt, nicht danach. Dieselbe Begruendung
    wie beim AutoTrading-Vorcheck darunter: eine Unfaehigkeit, die erst beim Senden
    auffaellt, sieht dann aus wie ein Fehler der Software.

    Drei Wege heraus, alle ausdruecklich:

    * ``--demo-schreiben`` -- der Lauf bekommt das Schreibrecht und kann schliessen.
    * ``--am-ende-offen-lassen`` -- der Lauf sagt gar kein Glattstellen zu; die
      Verantwortung fuer die offenen Positionen bleibt beim Menschen, und er hat es
      hingeschrieben.
    * Die Positionen von Hand schliessen, dann starten.
    """
    if not offene_symbole:
        # Nichts offen: der Lauf kann nichts zurueckzulassen haben.
        return None
    if kann_schreiben or not schliesst_am_ende:
        return None
    return (
        "Dieser Lauf sagt ein Glattstellen am Ende zu, kann es aber nicht halten: "
        "der Schreibpfad ist gesperrt (ohne --demo-schreiben), und am Broker stehen "
        f"bereits Positionen offen: {sorted(offene_symbole)}.\n"
        "Gemessen: genau so sind am 2026-08-17 zwei Laeufe mit offenen Positionen "
        "geendet -- das Geld blieb am Markt, ohne beaufsichtigenden Prozess.\n"
        "Entweder --demo-schreiben, oder --am-ende-offen-lassen (dann bleibt die "
        "Verantwortung ausdruecklich beim Menschen), oder die Positionen vorher von "
        "Hand schliessen."
    )


# --- Zulassung, Zustand, Terminal (Z, D8, D1) --------------------------------------

#: Die vier Pflichtfelder eines Registereintrags fuer ``--zulassung`` (E-010).
ZULASSUNGSFELDER: tuple[str, ...] = ("strategie", "torurteil_hash", "datum", "kennung")


@dataclass(frozen=True)
class Zulassung:
    """Was ``--zulassung <datei>`` hergab: das Urteil fuer die Kette und der Befund
    fuer das Journal (Datei, Felder oder Mangel)."""

    urteil: CriteriaVerdict
    befund: dict[str, Any]


def zulassung_lesen(pfad: Path | None) -> Zulassung:
    """Die §9.3-Zulassung aus dem Registereintrag. Fehlt etwas, ist nichts zugelassen.

    Fail-closed in jeder Richtung: keine Datei, keine lesbare Datei, kein Objekt,
    ein fehlendes oder leeres Feld -- jedes davon ist ``passed=False`` mit benanntem
    Mangel. Ein Freitext kann diese Funktion nicht ueberreden (Z, E-010).
    """
    nicht = CriteriaVerdict(passed=False, results=(), unmet=("registereintrag",))
    if pfad is None:
        return Zulassung(
            nicht, {"datei": None, "gueltig": False, "mangel": "keine_zulassungsdatei"}
        )
    try:
        daten: Any = json.loads(Path(pfad).read_text(encoding="utf-8"))
    except FileNotFoundError:
        mangel = "zulassungsdatei_fehlt"
    except (OSError, ValueError) as exc:
        mangel = f"zulassungsdatei_unlesbar: {type(exc).__name__}"
    else:
        if not isinstance(daten, dict):
            mangel = "zulassungsdatei_kein_objekt"
        else:
            fehlend = [
                feld
                for feld in ZULASSUNGSFELDER
                if not (isinstance(daten.get(feld), str) and daten[feld].strip())
            ]
            if not fehlend:
                return Zulassung(
                    CriteriaVerdict(passed=True, results=()),
                    {
                        "datei": str(pfad),
                        "gueltig": True,
                        **{feld: daten[feld] for feld in ZULASSUNGSFELDER},
                    },
                )
            mangel = f"zulassung_unvollstaendig: {', '.join(fehlend)}"
    return Zulassung(nicht, {"datei": str(pfad), "gueltig": False, "mangel": mangel})


def zustand_abweisen(manager: RiskManager, venue: Mt5Venue) -> str | None:
    """Der Betrieb faehrt nur mit dauerhaftem Zustand (D8, E-005).

    ``None`` heisst: Risikozustand, Schwebeakte und Positionsbuch ueberdauern einen
    Neustart. Sonst der Grund -- ein fluechtiger Zustand (die Testtypen
    ``FluechtigerZustand``, ``FluechtigeSchwebeAkte``, ``FluechtigesPositionsbuch``)
    verhaelt sich bis zum Neustart genau wie ein dauerhafter und verliert dann den
    Halt. Genau so liefen die 21 Betriebslaeufe des Standes 306bbaa.
    """
    maengel: list[str] = []
    if not manager.zustand_dauerhaft:
        maengel.append(f"Risikozustand fluechtig ({manager.zustandsort})")
    if not venue.zustand_dauerhaft:
        maengel.append("Schwebeakte oder Positionsbuch fluechtig")
    if not maengel:
        return None
    return (
        "fluechtiger Zustand: "
        + "; ".join(maengel)
        + " -- ein Halt endete mit dem Prozess (Befund D8). Der Betrieb verlangt "
        "den Zustandsordner (--zustandsordner)."
    )


def _terminal_bauen(art: str, *, darf_schreiben: bool) -> Mt5Terminal:
    """``real`` bindet MetaTrader 5 (Schreibrecht nur mit ``--demo-schreiben``,
    ``require_demo`` bleibt ``True``); ``fake`` ist die Betriebsattrappe ohne
    MetaTrader5-Import (``venue/fake.py``)."""
    if art == "fake":
        return FakeMt5Terminal()
    # Kein ``server_tz`` mehr (D20): den Versatz misst ``_serverversatz_messen`` am
    # Kopf jedes Taktes am Tickstrom; das Terminal dreht seine Zeitstempel danach
    # selbst in echtes UTC. Ohne Messung bleibt der Frische-Latch rot, und ohne
    # Drehung rechnete jede Haltedauer 2-3 Stunden daneben.
    return RealMt5Terminal(allow_write=darf_schreiben)


def _terminal_grund(terminal: Mt5Terminal) -> str | None:
    """Warum das Terminal nicht erreichbar ist -- oder ``None``, wenn es das ist.

    ``RealMt5Terminal.initialize`` hat zwei Fehlausgaenge: ``VenueUnavailableError``
    (das Paket ``MetaTrader5`` fehlt) und ``False`` (Terminal nicht gestartet, kein
    Konto). Beide enden in **einer** benannten Zeile und Exit 2 statt in einem
    Traceback (Abnahmekatalog A12).
    """
    try:
        verbunden = terminal.initialize()
    except VenueUnavailableError as exc:
        return str(exc)
    if not verbunden:
        return (
            "initialize() lieferte False -- Terminal nicht initialisierbar (laeuft "
            "terminal64.exe, und ist ein Demokonto angemeldet?)"
        )
    return None


def _kein_terminal(grund: str) -> int:
    print(f"FEHLGESCHLAGEN -- MT5-Terminal nicht erreichbar: {grund}", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Demo-Handelsbetrieb (nur Demokonto)")
    ap.add_argument("--dauer", type=float, default=24.0, help="Laufzeit in Stunden")
    ap.add_argument("--takt", type=float, default=60.0, help="Sekunden je Takt")
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument(
        "--max-haltedauer",
        type=float,
        default=4.0,
        help="Hoechste Haltedauer je Position in Stunden",
    )
    ap.add_argument(
        "--terminal",
        choices=TERMINALARTEN,
        default="real",
        help="real: MetaTrader 5 auf diesem Rechner (Vorgabe); fake: Betriebsattrappe "
        "ohne Terminal fuer Trockenlauf und Eichfaelle",
    )
    ap.add_argument(
        "--zustandsordner",
        type=Path,
        default=None,
        metavar="ORDNER",
        help="Ordner fuer Risikozustand, Schwebeakte, Positionsbuch, Stoppdatei und "
        f"Journale -- absolut, ausserhalb des Arbeitsbaums (Vorgabe: "
        f"{standard_zustandsordner()})",
    )
    ap.add_argument(
        "--demo-schreiben",
        action="store_true",
        help="Schreibrecht am Demokonto (allow_write). Ohne: Trockenlauf, der das "
        "Terminal nie erreicht.",
    )
    ap.add_argument(
        "--zulassung",
        type=Path,
        default=None,
        metavar="DATEI",
        help="Registereintrag der §9.3-Zulassung (JSON mit strategie, torurteil_hash, "
        "datum, kennung). Fehlt er oder ein Feld, ist nichts zugelassen.",
    )
    ap.add_argument(
        "--verlustgrenze",
        type=float,
        default=2.0,
        metavar="PROZENT",
        help="Bei diesem Verlust seit Laufbeginn wird glattgestellt "
        "und der Lauf beendet (Vorgabe 2 %%)",
    )
    ap.add_argument(
        "--am-ende-offen-lassen",
        action="store_true",
        help="Positionen am Ende NICHT glattstellen (Vorgabe: schliessen)",
    )
    args = ap.parse_args(argv)

    try:
        ordner = zustandsordner_waehlen(args.zustandsordner)
    except ZustandsortFehler as exc:
        print(f"FEHLGESCHLAGEN -- Zustandsordner unbrauchbar: {exc}", file=sys.stderr)
        return 2
    darf_schreiben = bool(args.demo_schreiben)
    zulassung = zulassung_lesen(args.zulassung)

    # Das Terminal ZUERST: ohne Terminal wird kein Zustand angefasst und keine Zeile
    # ausser der einen benannten geschrieben (A12).
    terminal = _terminal_bauen(args.terminal, darf_schreiben=darf_schreiben)
    grund = _terminal_grund(terminal)
    if grund is not None:
        return _kein_terminal(grund)

    manager = RiskManager(zustand=DateiZustand(standard_zustandsdatei(ordner=ordner)))
    # KEIN PrivateSync: es gibt im Repo keine Quelle, die FILL-Ereignisse erzeugt.
    # Mit konfiguriertem Strom bucht ``submit_order`` den eigenen Fill NICHT (es
    # wartet auf den autoritativen Strom, der nie kommt), der naechste ``reconcile``
    # saehe die volle Position als Drift, und bei ``max_notional_drift=0`` latcht das
    # den Global-Halt. Der Lauf haette genau einen Takt lang gehandelt.
    venue = Mt5Venue(
        name="mt5-betrieb",
        terminal=terminal,
        catalog=load_instrument_catalog(),
        risk_manager=manager,
        zustandsordner=ordner,
    )
    fluechtig = zustand_abweisen(manager, venue)
    if fluechtig is not None:
        print(f"ABBRUCH — {fluechtig}", file=sys.stderr)
        terminal.shutdown()
        return 2
    try:
        venue.connect()
        konto = venue.get_account()
    except VenueUnavailableError as exc:
        terminal.shutdown()
        return _kein_terminal(str(exc))
    if not konto.is_demo:
        print(
            "ABBRUCH — kein Demokonto. Dieses Werkzeug laeuft nur auf Demo.",
            file=sys.stderr,
        )
        terminal.shutdown()
        return 2
    # Der Ausstiegsriegel steht VOR ``adopt_book()``: uebernommen wird nur, was dieser
    # Lauf auch wieder loswerden kann. Begruendung und Messung in
    # ``ausstiegszusage_pruefen``.
    hindernis = ausstiegszusage_pruefen(
        kann_schreiben=darf_schreiben,
        schliesst_am_ende=not args.am_ende_offen_lassen,
        offene_symbole=[p.symbol for p in venue.get_positions()],
    )
    if hindernis is not None:
        print("=" * 78, file=sys.stderr)
        print("ABBRUCH — der zugesagte Ausstieg ist nicht fahrbar.", file=sys.stderr)
        print("", file=sys.stderr)
        print(hindernis, file=sys.stderr)
        print("=" * 78, file=sys.stderr)
        terminal.shutdown()
        return 2

    # Vorpruefung: der AutoTrading-Knopf des Terminals. Ohne ihn lehnt MT5 JEDE
    # algorithmische Order ab ("AutoTrading disabled by client") -- und zwar erst beim
    # Senden, also nachdem die ganze Kette gruen gerechnet hat. Das faellt sonst erst
    # nach dem ersten Signal auf und sieht dann aus wie ein Fehler der Software.
    if darf_schreiben and args.terminal == "real" and not _autotrading_an():
        print("=" * 78, file=sys.stderr)
        print("ABBRUCH — AutoTrading ist im Terminal ausgeschaltet.", file=sys.stderr)
        print(
            "Die Kette liefe gruen durch und jede Order fiele beim Senden aus.",
            file=sys.stderr,
        )
        print("", file=sys.stderr)
        print(
            "Im MetaTrader 5: Knopf 'Algo Trading' in der Werkzeugleiste einschalten",
            file=sys.stderr,
        )
        print(
            "(oder Extras -> Optionen -> Expert Advisors -> "
            "'Algorithmischen Handel erlauben').",
            file=sys.stderr,
        )
        print("=" * 78, file=sys.stderr)
        terminal.shutdown()
        return 3

    start = datetime.now(UTC)
    lauf = uuid.uuid4().hex
    journal = Journal(
        ordner
        / JOURNALORDNER_NAME
        / f"journal-{start.strftime('%Y%m%dT%H%M%S')}.jsonl",
        lauf=lauf,
        version=_codestand(),
    )
    stoppdatei = ordner / STOPPDATEI_NAME
    # Nur Symbole, die dieser Broker wirklich fuehrt. Der Katalog ist breiter als
    # das Angebot eines einzelnen Brokers; ein unbekanntes Symbol wuerde sonst in
    # JEDEM Takt einen Fehler ins Protokoll schreiben und es unlesbar machen.
    gewuenscht = args.symbol or sorted(load_instrument_catalog())
    symbole = []
    fehlend = []
    for sym in gewuenscht:
        try:
            venue.get_instrument(sym)
            venue.get_quote(sym)
        except VenueError:
            fehlend.append(sym)
        else:
            symbole.append(sym)
    if fehlend:
        print(f"Nicht beim Broker gefuehrt, uebersprungen: {', '.join(fehlend)}")
    if not symbole:
        print("ABBRUCH — kein einziges handelbares Symbol.", file=sys.stderr)
        terminal.shutdown()
        return 2
    max_halt = timedelta(hours=args.max_haltedauer)
    verlustgrenze = Decimal(str(args.verlustgrenze)) / Decimal("100")

    print("=" * 78)
    if darf_schreiben:
        print("SCHREIBRECHT (--demo-schreiben): Orders gehen an das Demokonto.")
    else:
        print("TROCKEN: kein Schreibrecht, die Kette erreicht das Terminal nie.")
    if zulassung.urteil.passed:
        print(
            f"Zulassung: {zulassung.befund['strategie']} "
            f"(Kennung {zulassung.befund['kennung']}, {zulassung.befund['datum']}, "
            f"Torurteil {zulassung.befund['torurteil_hash']})"
        )
    else:
        print(
            f"KEINE Zulassung ({zulassung.befund['mangel']}): die Kette haelt an der "
            "Zulassung; ohne Schreibrecht wird auch nicht erkundet."
        )
    print("Alle uebrigen Sperren bleiben aktiv.")
    print("=" * 78)

    journal.schreib(
        "start",
        lauf=lauf,
        konto=konto.account_id,
        equity=konto.equity,
        demo=konto.is_demo,
        symbole=symbole,
        uebersprungen=fehlend,
        dauer_stunden=args.dauer,
        takt_sekunden=args.takt,
        max_haltedauer_stunden=args.max_haltedauer,
        verlustgrenze_prozent=args.verlustgrenze,
        terminal=args.terminal,
        zustandsordner=str(ordner),
        # ``scharf`` heisst seit Z nur noch: dieser Lauf hat das Schreibrecht. Die
        # Zulassung steht getrennt daneben und wird nie uebergangen.
        scharf=darf_schreiben,
        demo_schreiben=darf_schreiben,
        zulassung=zulassung.befund,
        zulassung_uebergangen=False,
        strategie=f"moving_average_crossover({SCHNELL},{LANGSAM})",
    )
    # Startabgleich (D7): was Risikozaehler und Positionsbuch fuehrten, gegen den
    # Broker gehalten -- Geister sind ausgetragen und stehen hier mit Namen.
    venue.adopt_book()
    _startabgleich_journalisieren(venue, journal)
    print(f"Journal: {journal.pfad}")
    # Eine Stoppdatei aus einem frueheren Lauf wuerde diesen sofort beenden.
    stoppdatei.unlink(missing_ok=True)
    print(f"Geordnet beenden: diese Datei anlegen -> {stoppdatei}")
    print(
        f"Laufzeit {args.dauer} h, Takt {args.takt:g} s, {len(symbole)} Instrumente, "
        f"Hoechsthaltedauer {args.max_haltedauer} h, "
        f"Notbremse bei {args.verlustgrenze} % Verlust.\n"
    )

    # risk_manager MUSS hier hinein: ohne ihn ist ``observe_equity`` im Scheduler
    # toter Code, der Fenster-Hoechststand bleibt bei der Anfangs-Equity stehen und
    # die Drawdown-Grenze feuert nie.
    scheduler = SyncScheduler(
        venue,
        max_silence=timedelta(minutes=5),
        started_at=start,
        risk_manager=manager,
    )
    ende = start + timedelta(hours=args.dauer)
    abbruch = {"jetzt": False}

    def _stop(_s: int, _f: FrameType | None) -> None:
        abbruch["jetzt"] = True
        print("\nAbbruch angefordert — laufe den Takt zu Ende.")

    signalmodul.signal(signalmodul.SIGINT, _stop)
    # SIGTERM (und unter Windows SIGBREAK) ebenfalls: sonst laeuft der finally-Block
    # bei einem geordneten Abschuss gar nicht, und Positionen bleiben offen.
    for name in ("SIGTERM", "SIGBREAK"):
        sig_nr = getattr(signalmodul, name, None)
        if sig_nr is not None:
            signalmodul.signal(sig_nr, _stop)

    bekannt: dict[str, Lage] = {}
    nr = 0
    gestoppt = False
    try:
        while datetime.now(UTC) < ende and not abbruch["jetzt"] and not gestoppt:
            if stoppdatei.exists():
                print(f"\nStoppdatei {stoppdatei.name} gefunden — geordnet beenden.")
                journal.schreib("stoppdatei", pfad=str(stoppdatei))
                break
            nr += 1
            if not _verbindung_sichern(venue, terminal, journal):
                break
            try:
                bekannt, gestoppt = takt(
                    venue,
                    manager,
                    scheduler,
                    symbole,
                    zulassung.urteil,
                    journal,
                    nr=nr,
                    max_haltedauer=max_halt,
                    bekannt=bekannt,
                    equity_start=konto.equity,
                    verlustgrenze=verlustgrenze,
                    darf_schreiben=darf_schreiben,
                    terminal=terminal,
                )
            except VenueError as exc:
                # Ein Defekt am Handelsplatz beendet den Lauf NICHT -- er wird
                # protokolliert, und der naechste Takt versucht es erneut (die
                # Verbindung wird oben gesichert). Was wirklich gefaehrlich waere,
                # latcht der Scheduler als Halt.
                journal.schreib("takt_fehler", nr=nr, fehler=str(exc))
                print(f"  !! Takt {nr}: {exc}")
            if datetime.now(UTC) < ende and not abbruch["jetzt"] and not gestoppt:
                time.sleep(args.takt)
    finally:
        # JEDER Schritt einzeln abgesichert. Der haeufigste Abbruchgrund ist eine
        # verlorene Sitzung -- und dann wirft schon der erste Aufruf hier. Ohne
        # Absicherung gaebe es dann kein Glattstellen (obwohl der Modulkopf es
        # zusagt), keinen Endeintrag und kein shutdown, sondern einen Traceback.
        offen_geblieben: list[str] = []
        try:
            if not args.am_ende_offen_lassen:
                jetzt = datetime.now(UTC)
                for offen in _lage_lesen(venue).values():
                    if not _schliesse(
                        venue,
                        manager,
                        offen,
                        jetzt,
                        "lauf_beendet",
                        journal,
                        waehrung=konto.currency,
                    ):
                        offen_geblieben.append(offen.symbol)
                offen_geblieben += list(_lage_lesen(venue))
        except VenueError as exc:
            journal.schreib("ende_glattstellen_fehlgeschlagen", fehler=str(exc))
            print(f"  !! Glattstellen am Ende fehlgeschlagen: {exc}", file=sys.stderr)
            offen_geblieben.append("unbekannt")
        try:
            konto_ende = venue.get_account()
            journal.schreib(
                "ende",
                takte=nr,
                equity=konto_ende.equity,
                equity_start=konto.equity,
                veraenderung=konto_ende.equity - konto.equity,
                offen_geblieben=sorted(set(offen_geblieben)),
            )
            print(
                f"\nBeendet nach {nr} Takten. Equity {konto.equity} -> "
                f"{konto_ende.equity} {konto_ende.currency}"
            )
        except VenueError as exc:
            journal.schreib(
                "ende_ohne_kontostand",
                fehler=str(exc),
                takte=nr,
                offen_geblieben=sorted(set(offen_geblieben)),
            )
            print(f"\nBeendet nach {nr} Takten, Kontostand nicht lesbar: {exc}")
        if offen_geblieben:
            print(
                f"!! ACHTUNG: Positionen koennen offen geblieben sein: "
                f"{sorted(set(offen_geblieben))}",
                file=sys.stderr,
            )
        print(f"Journal: {journal.pfad}")
        print(f"Auswertung: python tools/betrieb_auswerten.py {journal.pfad}")
        try:
            terminal.shutdown()
        except Exception:  # noqa: BLE001 - Aufraeumen darf nichts mehr werfen
            pass
        stoppdatei.unlink(missing_ok=True)
    return 4 if offen_geblieben else 0


if __name__ == "__main__":
    sys.exit(main())

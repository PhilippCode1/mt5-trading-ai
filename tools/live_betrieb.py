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

DIE ZULASSUNG -- WAS ``--scharf`` WIRKLICH TUT
-----------------------------------------------
Der Orderpfad prueft als Erstes die §9.3-Zulassung: ohne bestandenes Bewertungstor
handelt keine Strategie. **Es gibt keine bestandene Zulassung** -- alle sieben Studien
aus Paket 3a sind gescheitert (``ABSCHLUSS-3a/05-URTEIL.md``), und ``ABBRUCH.md``
Bedingung 6 ist ausgeloest.

``--scharf "<Begruendung>"`` uebergeht dieses eine Tor. Es tut das **sichtbar**: mit
Banner, mit der Begruendung im Journal, und mit einem Eintrag, der festhaelt, dass zum
Zeitpunkt des Laufs keine Strategie zugelassen war. Alle anderen Sperren bleiben scharf
-- Frische, Halal, Hebel, Kostentor, Kill-Switch, Drossel, Stop-Budget, Sizing.

Ohne ``--scharf`` laeuft alles gleich, nur bleibt die Kette an der Zulassung stehen und
es wird nichts gesendet. Das ist die Vorgabe.

WAS DER LAUF NICHT BEANTWORTET
-------------------------------
Ob die Strategie taugt. Ein Tag sind bei diesen Grenzen hoechstens zehn Trades. Das ist
keine Stichprobe, aus der man etwas ueber einen Vorteil lernt -- es ist eine Probe, ob
die **Maschine** sauber laeuft. Wer die Parameter hinterher auf das Tagesergebnis dreht,
tut genau das, wogegen die Deflation in diesem Repo gebaut ist.

Aufruf::

    python tools/live_betrieb.py --dauer 1 --takt 60
    python tools/live_betrieb.py --dauer 24 --scharf "Maschinenprobe Demo 2026-08-18"
"""

from __future__ import annotations

import argparse
import json
import signal as signalmodul
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import FrameType
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.engine import MarketView, Signal  # noqa: E402
from mt5_trading_ai.backtest.kalender import SERVER_TZ_NAME  # noqa: E402
from mt5_trading_ai.backtest.strategies import moving_average_crossover  # noqa: E402
from mt5_trading_ai.data.quality import BarRow  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal  # noqa: E402
from mt5_trading_ai.execution.scheduler import SyncScheduler  # noqa: E402
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.venue.catalog import load_instrument_catalog  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    VenueError,
)

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"
#: Wer diese Datei anlegt, beendet den Lauf geordnet. Unter Windows gibt es fuer
#: einen abgekoppelten Prozess kein zuverlaessiges Signal: Strg-C braucht ein
#: Konsolenfenster, und ``taskkill /F`` toetet hart -- der finally-Block liefe nicht,
#: und die Positionen blieben offen. Eine Datei ist plattformunabhaengig, braucht
#: keine Rechte und kann nicht danebengehen.
STOPPDATEI = JOURNALE / "STOP"

#: Trendfolge, Parameter per Konvention. NICHT auf Daten optimiert und nicht als
#: Vorschlag gemeint -- diese Logik hat nie ein Bewertungstor bestanden.
SCHNELL, LANGSAM = 12, 26
KERZEN_STUNDEN = 360


@dataclass
class Lage:
    """Was die Schleife ueber eine offene Position weiss."""

    symbol: str
    ist_kauf: bool
    volumen: Decimal
    seit: datetime


class Journal:
    """Anhaengendes JSONL. Jede Zeile ein Ereignis, jede Zeile mit Zeitstempel.

    Anhaengend und nie ueberschreibend -- ein Betriebsprotokoll, das sich nachtraeglich
    aendern laesst, ist als Beleg wertlos.
    """

    def __init__(self, pfad: Path) -> None:
        self.pfad = pfad
        pfad.parent.mkdir(parents=True, exist_ok=True)

    def schreib(self, art: str, **felder: Any) -> None:
        zeile = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "art": art}
        zeile.update({k: _jsonfaehig(v) for k, v in felder.items()})
        with self.pfad.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(zeile, ensure_ascii=False) + "\n")


def _jsonfaehig(wert: Any) -> Any:
    if isinstance(wert, Decimal):
        return str(wert)
    if isinstance(wert, datetime):
        return wert.isoformat(timespec="seconds")
    if isinstance(wert, list | tuple):
        return [_jsonfaehig(x) for x in wert]
    if isinstance(wert, dict):
        return {k: _jsonfaehig(v) for k, v in wert.items()}
    return wert


def _signal(venue: Mt5Venue, symbol: str, jetzt: datetime) -> tuple[Signal, str]:
    """Trendfolge auf den Live-Stundenkerzen."""
    try:
        bars = venue.get_bars(
            symbol, Timeframe.H1,
            start=jetzt - timedelta(hours=KERZEN_STUNDEN), end=jetzt,
        )
    except VenueError as exc:
        return Signal.FLAT, f"keine Kerzen: {exc}"
    if len(bars) < LANGSAM:
        return Signal.FLAT, f"nur {len(bars)} Kerzen"
    reihe = [
        BarRow(ts=b.ts, open=float(b.open), high=float(b.high), low=float(b.low),
               close=float(b.close), volume=None)
        for b in bars
    ]
    sig = moving_average_crossover(SCHNELL, LANGSAM)(MarketView(reihe, len(reihe) - 1))
    schluesse = [b.close for b in reihe[-LANGSAM:]]
    return sig, (
        f"MA{SCHNELL}={sum(schluesse[-SCHNELL:]) / SCHNELL:.5f} "
        f"MA{LANGSAM}={sum(schluesse) / LANGSAM:.5f}"
    )


def _lage_lesen(venue: Mt5Venue) -> dict[str, Lage]:
    """Die WIRKLICH offenen Positionen, vom Terminal. Nicht aus dem Gedaechtnis.

    ``opened_at`` kommt in ECHTEM UTC: das Terminal wird mit ``server_tz`` gebaut und
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
            symbol=p.symbol, ist_kauf=p.side is OrderSide.BUY,
            volumen=p.volume, seit=p.opened_at,
        )
    return aus


def _schliesse(
    venue: Mt5Venue, manager: RiskManager, lage: Lage, jetzt: datetime, grund: str,
    journal: Journal,
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
        comment=f"live_betrieb: {grund}",
    )
    try:
        ergebnis = venue.submit_order(anfrage)
    except VenueError as exc:
        journal.schreib("schliessen_fehlgeschlagen", symbol=lage.symbol,
                        grund=grund, fehler=str(exc))
        return False
    manager.record_close(lage.symbol)
    journal.schreib("geschlossen", symbol=lage.symbol, grund=grund,
                    volumen=lage.volumen, war_kauf=lage.ist_kauf,
                    order_id=ergebnis.venue_order_id)
    print(f"  ZU   {lage.symbol} {lage.volumen} ({grund})")
    return True


def _eroeffne(
    venue: Mt5Venue, manager: RiskManager, symbol: str, sig: Signal,
    jetzt: datetime, zulassung: CriteriaVerdict, journal: Journal,
) -> None:
    config = RunnerConfig(
        cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
        account_swap_free=True, interest_bearing_margin=False,
        scholar_review_id="scholar-demo/eurusd-cfd",
    )
    try:
        bericht = run_signal(
            venue=venue, risk_manager=manager, admission=zulassung, symbol=symbol,
            side=sig, config=config, now=jetzt,
            client_order_id=f"open-{symbol}-{uuid.uuid4().hex[:10]}",
        )
    except VenueError as exc:
        journal.schreib("eroeffnen_fehlgeschlagen", symbol=symbol, fehler=str(exc))
        return
    schritte = [{"naht": s.name, "ok": s.ok, "detail": s.detail} for s in bericht.steps]
    journal.schreib(
        "eroeffnungsversuch", symbol=symbol, signal=sig.name,
        eroeffnet=bericht.opened, grund=bericht.reject_reason, schritte=schritte,
    )
    if bericht.opened:
        print(f"  AUF  {symbol} {sig.name}")
    else:
        letzte = next((s for s in reversed(bericht.steps) if not s.ok), None)
        wo = letzte.name if letzte else "?"
        print(f"  --   {symbol} {sig.name}: {bericht.reject_reason} (bei {wo})")


def _verbindung_sichern(
    venue: Mt5Venue, terminal: RealMt5Terminal, journal: Journal, *, versuche: int = 10
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
        # Nur Halts loesen, die von der Stoerung SELBST kommen. Ein Drawdown-,
        # Desync- oder Notbremsen-Halt bleibt stehen -- er hat einen anderen Grund.
        if venue.halt_reason in ("reconcile_unavailable", "account_unavailable"):
            venue.clear_halt()
            journal.schreib("halt_geloest", grund=venue.halt_reason)
        journal.schreib("reconnect_ok", nr=i + 1)
        print("  OK   Verbindung wieder da")
        return True
    journal.schreib("verbindung_verloren", offen_moeglich=True)
    print("  !!   Verbindung endgueltig verloren. Positionen koennen offen sein.")
    return False


def _buch_abgleichen(
    venue: Mt5Venue, manager: RiskManager, bekannt: dict[str, Lage],
    lage: dict[str, Lage], journal: Journal,
) -> None:
    """Was der Broker geschlossen hat, muss Manager UND Buch erfahren.

    Nur ``record_close`` zu rufen genuegt nicht: das lokale Positionsbuch der Venue
    behielte die Position, und der naechste ``reconcile`` saehe die Differenz als
    Drift. Bei ``max_notional_drift=0`` latcht das den Global-Halt -- ein voellig
    normales Trade-Ende waere dann bitgleich mit einem katastrophalen Desync.
    """
    verschwunden = [s for s in bekannt if s not in lage]
    if not verschwunden:
        return
    for symbol in verschwunden:
        manager.record_close(symbol)
        journal.schreib("vom_broker_geschlossen", symbol=symbol)
        print(f"  WEG  {symbol} (Broker hat geschlossen, vermutlich Stop)")
    vorher = venue.book_snapshot() if hasattr(venue, "book_snapshot") else None
    nachher = venue.adopt_book()
    journal.schreib("buch_uebernommen", vorher=vorher, nachher=nachher)


def _notbremse(
    venue: Mt5Venue, manager: RiskManager, journal: Journal, *,
    equity_jetzt: Decimal, equity_start: Decimal, grenze: Decimal,
    lage: dict[str, Lage], jetzt: datetime,
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
    print(f"  !!   NOTBREMSE: {verlust * 100:.2f} % Verlust seit Start "
          f"(Grenze {grenze * 100:.1f} %). Alles glattstellen.")
    journal.schreib("notbremse", verlust_anteil=verlust, grenze=grenze,
                    equity_start=equity_start, equity=equity_jetzt)
    for offen in lage.values():
        _schliesse(venue, manager, offen, jetzt, "notbremse", journal)
    venue.latch_halt(reason="tagesverlust")
    return True


def takt(
    venue: Mt5Venue, manager: RiskManager, scheduler: SyncScheduler,
    symbole: list[str], zulassung: CriteriaVerdict, journal: Journal,
    *, nr: int, max_haltedauer: timedelta, bekannt: dict[str, Lage],
    equity_start: Decimal, verlustgrenze: Decimal,
) -> tuple[dict[str, Lage], bool]:
    jetzt = datetime.now(UTC)

    # 1) Herzschlag. Der Scheduler beobachtet die Equity (ohne das feuert die
    #    Notbremse nie) und latcht bei Verbindungs- oder Reconcile-Defekten.
    #    KEIN ``events=``: ohne konfigurierten Strom wirft ``apply_private_event``.
    tick = scheduler.tick(jetzt)
    konto = venue.get_account()
    print(f"[{jetzt.strftime('%H:%M:%S')}] Takt {nr} | Equity {konto.equity} "
          f"{konto.currency} | Halt: {'JA' if tick.halted else 'nein'}")
    journal.schreib("takt", nr=nr, equity=konto.equity, halt=tick.halted,
                    halt_grund=tick.halt_reason, demo=konto.is_demo)

    # 2) Buchfuehrung gleichziehen -- Manager UND Positionsbuch.
    lage = _lage_lesen(venue)
    _buch_abgleichen(venue, manager, bekannt, lage, journal)

    # 2b) Notbremse. Vor allem anderen, und sie stellt wirklich glatt.
    if _notbremse(venue, manager, journal, equity_jetzt=konto.equity,
                  equity_start=equity_start, grenze=verlustgrenze,
                  lage=lage, jetzt=jetzt):
        return _lage_lesen(venue), True

    # 3) Ausstiege. Laufen AUCH bei Halt -- Schliessen muss immer moeglich bleiben.
    for symbol, offen in list(lage.items()):
        sig, _ = _signal(venue, symbol, jetzt)
        alter = jetzt - offen.seit
        gegen = (offen.ist_kauf and sig is Signal.SHORT) or (
            not offen.ist_kauf and sig is Signal.LONG
        )
        if gegen:
            _schliesse(venue, manager, offen, jetzt, "signalwechsel", journal)
        elif alter >= max_haltedauer:
            _schliesse(venue, manager, offen, jetzt,
                       f"haltedauer_{alter.total_seconds() / 3600:.1f}h", journal)

    # 4) Eintritte. Nur wenn kein Halt und noch keine Position im Symbol.
    lage = _lage_lesen(venue)
    if not tick.halted:
        for symbol in symbole:
            if symbol in lage:
                continue
            if not venue.is_trading_open(symbol, at=jetzt):
                continue
            sig, warum = _signal(venue, symbol, jetzt)
            if sig is Signal.FLAT:
                continue
            journal.schreib("signal", symbol=symbol, signal=sig.name, detail=warum)
            _eroeffne(venue, manager, symbol, sig, jetzt, zulassung, journal)
    return _lage_lesen(venue), False


def _autotrading_an() -> bool:
    """Steht der AutoTrading-Knopf des Terminals auf an?

    Bewusst direkt ueber die MetaTrader5-Bibliothek: der Adapter bildet
    ``terminal_info().trade_allowed`` nicht ab, und diese eine Zahl entscheidet, ob ein
    scharfer Lauf ueberhaupt handeln kann.
    """
    try:
        import MetaTrader5 as mt5  # type: ignore[import-untyped]  # noqa: N813
    except ImportError:
        return False
    info = mt5.terminal_info()
    return bool(info is not None and info.trade_allowed)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Demo-Handelsbetrieb (nur Demokonto)")
    ap.add_argument("--dauer", type=float, default=24.0, help="Laufzeit in Stunden")
    ap.add_argument("--takt", type=float, default=60.0, help="Sekunden je Takt")
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--max-haltedauer", type=float, default=4.0,
                    help="Hoechste Haltedauer je Position in Stunden")
    ap.add_argument("--scharf", default=None, metavar="BEGRUENDUNG",
                    help="Die §9.3-Zulassung uebergehen und WIRKLICH handeln. "
                         "Begruendung ist Pflicht und geht ins Journal.")
    ap.add_argument("--verlustgrenze", type=float, default=2.0, metavar="PROZENT",
                    help="Bei diesem Verlust seit Laufbeginn wird glattgestellt "
                         "und der Lauf beendet (Vorgabe 2 %%)")
    ap.add_argument("--am-ende-offen-lassen", action="store_true",
                    help="Positionen am Ende NICHT glattstellen (Vorgabe: schliessen)")
    args = ap.parse_args()

    # server_tz: das Terminal dreht seine Zeitstempel selbst in echtes UTC.
    # Ohne das rechnet jede Haltedauer und jede Uhrzeit 2-3 Stunden daneben.
    terminal = RealMt5Terminal(
        allow_write=bool(args.scharf), server_tz=SERVER_TZ_NAME
    )
    if not terminal.initialize():
        print("FEHLGESCHLAGEN — MT5-Terminal nicht erreichbar.", file=sys.stderr)
        return 2
    manager = RiskManager()
    # KEIN PrivateSync: es gibt im Repo keine Quelle, die FILL-Ereignisse erzeugt.
    # Mit konfiguriertem Strom bucht ``submit_order`` den eigenen Fill NICHT (es
    # wartet auf den autoritativen Strom, der nie kommt), der naechste ``reconcile``
    # saehe die volle Position als Drift, und bei ``max_notional_drift=0`` latcht das
    # den Global-Halt. Der Lauf haette genau einen Takt lang gehandelt.
    venue = Mt5Venue(
        name="mt5-betrieb", terminal=terminal, catalog=load_instrument_catalog(),
        risk_manager=manager,
    )
    venue.connect()
    konto = venue.get_account()
    if not konto.is_demo:
        print("ABBRUCH — kein Demokonto. Dieses Werkzeug laeuft nur auf Demo.",
              file=sys.stderr)
        terminal.shutdown()
        return 2
    venue.adopt_book()

    # Vorpruefung: der AutoTrading-Knopf des Terminals. Ohne ihn lehnt MT5 JEDE
    # algorithmische Order ab ("AutoTrading disabled by client") -- und zwar erst beim
    # Senden, also nachdem die ganze Kette gruen gerechnet hat. Das faellt sonst erst
    # nach dem ersten Signal auf und sieht dann aus wie ein Fehler der Software.
    if args.scharf and not _autotrading_an():
        print("=" * 78, file=sys.stderr)
        print("ABBRUCH — AutoTrading ist im Terminal ausgeschaltet.", file=sys.stderr)
        print("Die Kette liefe gruen durch und jede Order fiele beim Senden aus.",
              file=sys.stderr)
        print("", file=sys.stderr)
        print("Im MetaTrader 5: Knopf 'Algo Trading' in der Werkzeugleiste "
              "einschalten", file=sys.stderr)
        print("(oder Extras -> Optionen -> Expert Advisors -> "
              "'Algorithmischen Handel erlauben').", file=sys.stderr)
        print("=" * 78, file=sys.stderr)
        terminal.shutdown()
        return 3

    start = datetime.now(UTC)
    journal = Journal(JOURNALE / f"journal-{start.strftime('%Y%m%dT%H%M%S')}.jsonl")
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

    if args.scharf:
        print("=" * 78)
        print("SCHARF. Es werden echte Orders an das Demokonto gesendet.")
        print("Die §9.3-Zulassung wird UEBERGANGEN — keine Strategie ist zugelassen.")
        print(f"Begruendung: {args.scharf}")
        print("Alle anderen Sperren bleiben aktiv.")
        print("=" * 78)
    else:
        print("TROCKEN. Die Kette haelt an der Zulassung. Mit --scharf wird gehandelt.")
    zulassung = CriteriaVerdict(passed=bool(args.scharf), results=())

    journal.schreib(
        "start", konto=konto.account_id, equity=konto.equity, demo=konto.is_demo,
        symbole=symbole, uebersprungen=fehlend,
        dauer_stunden=args.dauer, takt_sekunden=args.takt,
        max_haltedauer_stunden=args.max_haltedauer,
        verlustgrenze_prozent=args.verlustgrenze,
        scharf=bool(args.scharf), zulassung_uebergangen=args.scharf,
        hinweis=("Zum Zeitpunkt dieses Laufs war KEINE Strategie nach §9.3 "
                 "zugelassen. Siehe ABSCHLUSS-3a/05-URTEIL.md."),
        strategie=f"moving_average_crossover({SCHNELL},{LANGSAM})",
    )
    print(f"Journal: {journal.pfad}")
    # Eine Stoppdatei aus einem frueheren Lauf wuerde diesen sofort beenden.
    STOPPDATEI.unlink(missing_ok=True)
    print(f"Geordnet beenden: diese Datei anlegen -> {STOPPDATEI}")
    print(f"Laufzeit {args.dauer} h, Takt {args.takt:g} s, {len(symbole)} Instrumente, "
          f"Hoechsthaltedauer {args.max_haltedauer} h, "
          f"Notbremse bei {args.verlustgrenze} % Verlust.\n")

    # risk_manager MUSS hier hinein: ohne ihn ist ``observe_equity`` im Scheduler
    # toter Code, der Fenster-Hoechststand bleibt bei der Anfangs-Equity stehen und
    # die Drawdown-Grenze feuert nie.
    scheduler = SyncScheduler(
        venue, max_silence=timedelta(minutes=5), started_at=start,
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
            if STOPPDATEI.exists():
                print(f"\nStoppdatei {STOPPDATEI.name} gefunden — geordnet beenden.")
                journal.schreib("stoppdatei", pfad=str(STOPPDATEI))
                break
            nr += 1
            if not _verbindung_sichern(venue, terminal, journal):
                break
            try:
                bekannt, gestoppt = takt(
                    venue, manager, scheduler, symbole, zulassung, journal,
                    nr=nr, max_haltedauer=max_halt, bekannt=bekannt,
                    equity_start=konto.equity, verlustgrenze=verlustgrenze,
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
                    if not _schliesse(venue, manager, offen, jetzt,
                                      "lauf_beendet", journal):
                        offen_geblieben.append(offen.symbol)
                offen_geblieben += list(_lage_lesen(venue))
        except VenueError as exc:
            journal.schreib("ende_glattstellen_fehlgeschlagen", fehler=str(exc))
            print(f"  !! Glattstellen am Ende fehlgeschlagen: {exc}", file=sys.stderr)
            offen_geblieben.append("unbekannt")
        try:
            konto_ende = venue.get_account()
            journal.schreib(
                "ende", takte=nr, equity=konto_ende.equity,
                equity_start=konto.equity,
                veraenderung=konto_ende.equity - konto.equity,
                offen_geblieben=sorted(set(offen_geblieben)),
            )
            print(f"\nBeendet nach {nr} Takten. Equity {konto.equity} -> "
                  f"{konto_ende.equity} {konto_ende.currency}")
        except VenueError as exc:
            journal.schreib("ende_ohne_kontostand", fehler=str(exc), takte=nr,
                            offen_geblieben=sorted(set(offen_geblieben)))
            print(f"\nBeendet nach {nr} Takten, Kontostand nicht lesbar: {exc}")
        if offen_geblieben:
            print(f"!! ACHTUNG: Positionen koennen offen geblieben sein: "
                  f"{sorted(set(offen_geblieben))}", file=sys.stderr)
        print(f"Journal: {journal.pfad}")
        print(f"Auswertung: python tools/betrieb_auswerten.py {journal.pfad.name}")
        try:
            terminal.shutdown()
        except Exception:  # noqa: BLE001 - Aufraeumen darf nichts mehr werfen
            pass
        STOPPDATEI.unlink(missing_ok=True)
    return 4 if offen_geblieben else 0


if __name__ == "__main__":
    sys.exit(main())

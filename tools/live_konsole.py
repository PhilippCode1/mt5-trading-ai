#!/usr/bin/env python3
"""Live-Konsole: was das System auf dem Demokonto gerade sieht und entscheiden wuerde.

WAS SIE IST
-----------
Ein Dauerlauf gegen das echte MT5-Terminal, **hart nur lesend**. Sie zeigt in jedem
Takt vier Dinge:

1. **Konto und Frische** — Equity, Demo-Wache, Alter des Kontostands gegen den
   Frische-Latch aus ``execution/freshness.py``.
2. **Preise gegen Modell** — je Instrument der am Terminal GEMESSENE Spread in
   Basispunkten, daneben der in ``config/broker_costs.json`` hinterlegte. Das ist die
   Gegenprobe, die Paket 2 nur aus veroeffentlichten Werten rechnen konnte.
3. **Das Signal** — die Trendfolge aus ``backtest/strategies.py`` auf den LIVE-Kerzen.
4. **Die Kette trocken** — dieselbe Funktion, die im Ernstfall handelt
   (``execution/runner.py::run_signal``), einmal durchgelassen. Alle Sperren rechnen
   echt; erst der Schreibschritt am Ende wird verweigert, weil ``allow_write=False``
   ist. Genau diese Verweigerung ist das Sehenswerte.

WAS SIE NICHT IST
-----------------
Sie sendet nichts. ``allow_write`` ist hier kein Schalter, sondern fest verdrahtet —
wer schreiben will, nimmt ``tools/mt5_smoke.py --allow-write`` (winzige Order, sofort
geschlossen, harte Demo-Sperre) oder baut den Betrieb bewusst auf. Diese Konsole ist
zum Zusehen da, und Zusehen darf nicht versehentlich handeln koennen.

ZUR ZULASSUNG
-------------
Die Kette prueft als Erstes die §9.3-Zulassung: ohne bestandenes Bewertungstor handelt
keine Strategie. Ohne ``--vorfuehrung`` reicht diese Konsole **keine** bestandene
Zulassung herein, und die Kette bleibt bei Stufe A stehen. Das ist kein Mangel der
Konsole, sondern der Zustand des Vorhabens: es gibt keine zugelassene Strategie
(siehe ``archiv/ABSCHLUSS-3a/05-URTEIL.md``).

``--vorfuehrung`` reicht einen deutlich markierten Platzhalter herein, damit die
uebrigen elf Sperren sichtbar arbeiten. Am Schreibschutz aendert das nichts — die
Kette endet dann an der Verweigerung des Schreibpfades statt an der Zulassung.

Aufruf::

    python tools/live_konsole.py                      # alle Instrumente, alle 5 s
    python tools/live_konsole.py --symbol EURUSD --takt 2
    python tools/live_konsole.py --takte 1            # ein einzelner Takt
    python tools/live_konsole.py --vorfuehrung        # alle Sperren sichtbar
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.engine import MarketView, Signal  # noqa: E402
from mt5_trading_ai.backtest.kalender import SERVER_TZ_NAME  # noqa: E402
from mt5_trading_ai.backtest.strategies import moving_average_crossover  # noqa: E402
from mt5_trading_ai.costs.broker_costs import load_broker_costs  # noqa: E402
from mt5_trading_ai.data.quality import BarRow  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.freshness import (  # noqa: E402
    MAX_SNAPSHOT_AGE,
    evaluate_account_freshness,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal  # noqa: E402
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.venue.catalog import load_instrument_catalog  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import Timeframe, VenueError  # noqa: E402

#: Trendfolge-Parameter. Konvention, NICHT auf die Daten optimiert -- wie in
#: ``backtest/strategies.py`` begruendet. Sie sind hier zum Zusehen da und nicht als
#: Vorschlag: keine dieser Logiken hat je ein Bewertungstor bestanden.
SCHNELL, LANGSAM = 12, 26

#: Wie viele Stundenkerzen fuer das Signal geholt werden. Etwas mehr als LANGSAM,
#: damit auch nach einer Handelspause genug Historie da ist.
KERZEN = 120


def _bp(zaehler: Decimal, nenner: Decimal) -> Decimal:
    return zaehler / nenner * Decimal("10000") if nenner > 0 else Decimal("0")


def _modell_spread_bps(kosten: object, symbol: str, preis: Decimal) -> Decimal | None:
    """Der in der Kostendatei hinterlegte Spread, in bp -- guenstigster Broker."""
    bester: Decimal | None = None
    for broker in kosten.brokers.values():  # type: ignore[attr-defined]
        zeile = broker.instruments.get(symbol)
        if zeile is None or not zeile.available or zeile.spread_price is None:
            continue
        wert = _bp(zeile.spread_price, preis)
        if bester is None or wert < bester:
            bester = wert
    return bester


def _signal(venue: Mt5Venue, symbol: str) -> tuple[Signal, str]:
    """Die Trendfolge auf den Live-Kerzen. Gibt (Signal, Erlaeuterung)."""
    ende = datetime.now(UTC)
    try:
        bars = venue.get_bars(
            symbol,
            Timeframe.H1,
            start=ende - timedelta(hours=KERZEN * 3),
            end=ende,
        )
    except VenueError as exc:
        return Signal.FLAT, f"keine Kerzen: {exc}"
    # Nur abgeschlossene Kerzen. Der Handelsplatz liefert die laufende mit und
    # kennzeichnet sie (``Bar.is_closed``); ungefiltert rechnete diese Konsole ihren
    # gleitenden Durchschnitt auf einem Momentankurs, waehrend der wirkliche Treiber
    # (``tools/live_betrieb.py``) auf Schlusskursen rechnet. Zwei Anzeigen desselben
    # Signals, die auseinanderlaufen -- und die Konsole ist die, der der Betreiber
    # glaubt, weil ihr Kopf verspricht, sie zeige "was das System entscheiden wuerde".
    # Sie kann nichts ausloesen (``allow_write`` ist fest verdrahtet), aber eine
    # Anzeige, die etwas anderes zeigt als die Wirklichkeit, ist kein harmloser Fehler.
    fertig = [b for b in bars if b.is_closed]
    if len(fertig) < LANGSAM:
        return Signal.FLAT, (
            f"nur {len(fertig)} abgeschlossene von {len(bars)} Kerzen, {LANGSAM} noetig"
        )
    bars = tuple(fertig)
    # ``Bar`` (Handelsplatz) und ``BarRow`` (Backtest) tragen dieselben Felder, sind
    # aber verschiedene Typen. Umgesetzt statt gecastet: die Strategie soll genau das
    # sehen, was sie im Backtest saehe, und nichts darueber hinaus.
    reihe = [
        BarRow(
            ts=b.ts,
            open=float(b.open),
            high=float(b.high),
            low=float(b.low),
            close=float(b.close),
            volume=None,
        )
        for b in bars
    ]
    view = MarketView(reihe, len(reihe) - 1)
    signal = moving_average_crossover(SCHNELL, LANGSAM)(view)
    schluesse = [b.close for b in bars[-LANGSAM:]]
    langsam = sum(schluesse) / LANGSAM
    schnell = sum(schluesse[-SCHNELL:]) / SCHNELL
    # Der Zeitstempel ist bereits echtes UTC: das Terminal wird mit ``server_tz``
    # gebaut und dreht selbst. Hier nicht noch einmal drehen.
    stempel = bars[-1].ts.strftime("%H:%M UTC")
    return signal, (
        f"MA{SCHNELL}={schnell:.5f} MA{LANGSAM}={langsam:.5f} letzte Kerze {stempel}"
    )


def _kette_trocken(
    venue: Mt5Venue,
    manager: RiskManager,
    symbol: str,
    signal: Signal,
    now: datetime,
    *,
    vorfuehrung: bool,
) -> list[str]:
    """Die volle Kette durchlassen -- der Schreibschritt scheitert absichtlich."""
    config = RunnerConfig(
        cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
    )
    # Ohne --vorfuehrung wird KEINE Zulassung erfunden: es gibt keine bestandene, und
    # die Kette bleibt bei Stufe A stehen. Das ist der wahre Zustand des Vorhabens.
    # Mit --vorfuehrung wird ein deutlich markierter Platzhalter hereingereicht, damit
    # man die uebrigen Sperren ueberhaupt arbeiten sieht -- dasselbe Verfahren wie in
    # tools/paper_run.py, und dort wie hier ausdruecklich als Platzhalter benannt.
    zulassung = CriteriaVerdict(passed=vorfuehrung, results=())
    try:
        report = run_signal(
            venue=venue,
            risk_manager=manager,
            admission=zulassung,
            symbol=symbol,
            side=signal,
            config=config,
            now=now,
            client_order_id=f"trocken-{symbol}-{int(now.timestamp())}",
        )
    except VenueError as exc:
        return [f"  [SPERRE] schreibpfad   {exc}"]
    zeilen = [
        f"  [{'OK  ' if s.ok else 'HALT'}] {s.name:12s} {s.detail}"
        for s in report.steps
    ]
    if not report.opened:
        zeilen.append(f"  -> keine Eroeffnung: {report.reject_reason}")
    return zeilen


def takt(
    venue: Mt5Venue,
    manager: RiskManager,
    symbole: list[str],
    nr: int,
    leit: str,
    *,
    vorfuehrung: bool,
) -> None:
    jetzt = datetime.now(UTC)
    print("=" * 78)
    print(f"TAKT {nr}   {jetzt.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 78)

    konto = venue.get_account()
    # Gemessen wird der juengste KURSSTEMPEL, nicht der Kontoschnappschuss: MT5
    # liefert keinen Kontozeitstempel, ``account()`` setzt ihn selbst auf jetzt.
    # Die erste Fassung uebergab ``snapshot_ts=jetzt, now=jetzt`` -- das Alter war
    # per Konstruktion null und die Anzeige konnte nie rot werden.
    try:
        juengster = max(venue.get_quote(s).ts for s in symbole)
    except VenueError:
        juengster = None
    frische = evaluate_account_freshness(
        snapshot_ts=juengster or jetzt - timedelta(days=1),
        now=jetzt,
        connected=juengster is not None,
        max_age=MAX_SNAPSHOT_AGE,
        future_tolerance=timedelta(seconds=1),
    )
    print(
        f"Konto {konto.account_id} | Equity {konto.equity} {konto.currency} | "
        f"Demo: {'ja' if konto.is_demo else 'NEIN'} | "
        f"Kursfrische: {'ok' if frische.evaluable else frische.reason} "
        f"(Alter {frische.age.total_seconds():.1f} s, "
        f"Grenze {frische.max_age.total_seconds():.0f} s)"
    )
    print()

    kosten = load_broker_costs()
    print(f"{'Symbol':<9}{'Bid':>11}{'Ask':>11}{'Spread':>9}{'Modell':>9}   Bewertung")
    print(f"{'':<9}{'':>11}{'':>11}{'(bp)':>9}{'(bp)':>9}")
    for symbol in symbole:
        try:
            q = venue.get_quote(symbol)
        except VenueError as exc:
            print(f"{symbol:<9} — {exc}")
            continue
        mitte = (q.bid + q.ask) / 2
        gemessen = _bp(q.ask - q.bid, mitte)
        modell = _modell_spread_bps(kosten, symbol, mitte)
        if modell is None:
            urteil = "keine Kostenzeile"
            m_txt = "—"
        else:
            m_txt = f"{modell:.2f}"
            verh = gemessen / modell if modell > 0 else Decimal("0")
            urteil = (
                "wie modelliert"
                if verh <= Decimal("1.2")
                else f"{verh:.1f}x ueber Modell"
            )
        print(f"{symbol:<9}{q.bid:>11}{q.ask:>11}{gemessen:>9.2f}{m_txt:>9}   {urteil}")
    print()

    signal, warum = _signal(venue, leit)
    print(f"Signal {leit}: {signal.name}   ({warum})")
    print()
    kopf = (
        "Kette trocken"
        if not vorfuehrung
        else ("Kette trocken, MIT PLATZHALTER-ZULASSUNG (Vorfuehrung)")
    )
    print(f"{kopf} fuer {leit} — nichts wird gesendet:")
    for zeile in _kette_trocken(
        venue, manager, leit, signal, jetzt, vorfuehrung=vorfuehrung
    ):
        print(zeile)
    print()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="Live-Konsole gegen das MT5-Demokonto (nur lesend)"
    )
    ap.add_argument(
        "--symbol",
        action="append",
        default=None,
        help="Instrument, mehrfach angebbar (Vorgabe: ganzer Katalog)",
    )
    ap.add_argument("--takt", type=float, default=5.0, help="Sekunden je Takt")
    ap.add_argument("--takte", type=int, default=0, help="Anzahl Takte (0 = endlos)")
    ap.add_argument(
        "--leit",
        default=None,
        help="Instrument fuer Signal und Kette (Vorgabe: EURUSD)",
    )
    ap.add_argument(
        "--vorfuehrung",
        action="store_true",
        help="Platzhalter-Zulassung hereinreichen, damit die uebrigen Sperren "
        "sichtbar arbeiten. AENDERT NICHTS am Schreibschutz.",
    )
    args = ap.parse_args()

    # allow_write ist hier KEIN Schalter. Eine Konsole zum Zusehen darf nicht
    # versehentlich handeln koennen -- auch nicht auf einem Demokonto.
    terminal = RealMt5Terminal(allow_write=False, server_tz=SERVER_TZ_NAME)
    if not terminal.initialize():
        print(
            "FEHLGESCHLAGEN — MT5-Terminal nicht erreichbar. Laeuft es, und ist es "
            "im Demokonto angemeldet?",
            file=sys.stderr,
        )
        return 2
    manager = RiskManager()
    venue = Mt5Venue(
        name="mt5-live-konsole",
        terminal=terminal,
        catalog=load_instrument_catalog(),
        risk_manager=manager,
    )
    venue.connect()
    symbole = args.symbol or sorted(load_instrument_catalog())
    leit = args.leit or ("EURUSD" if "EURUSD" in symbole else symbole[0])
    print(
        f"Live-Konsole — NUR LESEND. {len(symbole)} Instrumente, Leitsymbol {leit}, "
        f"Takt {args.takt:g} s. Abbruch mit Strg-C.\n"
    )
    try:
        nr = 0
        while args.takte == 0 or nr < args.takte:
            nr += 1
            takt(venue, manager, symbole, nr, leit, vorfuehrung=args.vorfuehrung)
            if args.takte == 0 or nr < args.takte:
                time.sleep(args.takt)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        terminal.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

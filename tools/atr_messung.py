#!/usr/bin/env python3
"""Misst ATR(14) auf H1 ueber 12 Monate je Pruefinstrument (A1.2).

Gelesen wird ausschliesslich ueber den bestehenden lesenden MT5-Pfad
(``RealMt5Terminal`` aus ``mt5_trading_ai/venue/mt5.py``) mit ``allow_write=False``.
Das Konto muss ein **Demokonto** sein; ist es das nicht, bricht der Lauf ab.

LAUT SCHEITERN, NIE STILL
-------------------------
Ist kein Terminal erreichbar, wird **nichts** geschaetzt: der Lauf endet mit Exit 2
und ohne Datei. Fehlt ein einzelnes Symbol auf dem Terminal, bekommt es
``status = "nicht_gemessen"`` mit Grund — auch das ist ein Ergebnis, keine Luecke,
die spaeter jemand mit einer Annahme fuellt. Ein Kostentor auf geratener Volatilitaet
saehe aus wie ein Beleg und waere keiner.

Aufruf:
  python tools/atr_messung.py           misst, schreibt config/atr_measurements.json
  python tools/atr_messung.py --check   prueft nur, ob die Datei ladbar ist (ohne MT5)
  python tools/atr_messung.py --monate 12  Fensterlaenge in Monaten (Default 12)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mt5_trading_ai.costs.volatility import (  # noqa: E402
    ATR_MEASUREMENT_VERSION,
    ATR_PERIOD,
    DEFAULT_MAX_GAP,
    STATUS_MEASURED,
    AtrMeasurement,
    AtrMeasurementError,
    Candle,
    atr_series_bps,
    gap_count,
    load_atr_measurements,
    not_measured,
    percentile,
    true_ranges,
    wilder_atr,
)
from mt5_trading_ai.venue.mt5 import Mt5Rate, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    Timeframe,
    VenueUnavailableError,
    ist_abgeschlossen,
)

OUT = REPO / "config" / "atr_measurements.json"

#: Das Pruefuniversum aus §4 des Auftrags, mit dem Symbolnamen auf dem MT5-Terminal.
#: ``BTCUSD`` steht bewusst drin, obwohl der erreichbare Handelsplatz keinen
#: Krypto-CFD fuehrt: das Ergebnis „nicht gemessen" gehoert in die Datei, nicht
#: unter den Tisch.
PRUEFUNIVERSUM: tuple[tuple[str, str, str], ...] = (
    ("EURUSD", "EURUSD", "fx_major"),
    ("GBPJPY", "GBPJPY", "fx_minor"),
    ("XAUUSD", "XAUUSD", "gold"),
    ("DE40", "DE40", "index_major"),
    ("US500", "US500", "index_major"),
    ("BTCUSD", "BTCUSD", "crypto"),
    ("NVDA", "NVDA", "equity"),
)


def _messe_symbol(
    terminal: RealMt5Terminal,
    schluessel: str,
    symbol: str,
    start: datetime,
    ende: datetime,
) -> AtrMeasurement:
    """Miss ein Symbol. Jeder Fehlschlag wird zu einem begruendeten „nicht gemessen"."""
    info = terminal.symbol(symbol)
    if info is None:
        return not_measured(
            schluessel,
            f"Symbol {symbol!r} auf dem erreichbaren Terminal nicht vorhanden",
        )

    rates = _geschlossene_rates(terminal, symbol, Timeframe.H1, start, ende)
    if len(rates) < ATR_PERIOD + 2:
        return not_measured(
            schluessel,
            f"nur {len(rates)} abgeschlossene H1-Kerzen im Fenster, "
            f"mindestens {ATR_PERIOD + 2} noetig",
        )

    kerzen = [
        Candle(
            ts=rate.ts,
            high=float(rate.high),
            low=float(rate.low),
            close=float(rate.close),
        )
        for rate in rates
    ]
    schlusskurse = [kerze.close for kerze in kerzen]

    bereinigt = true_ranges(kerzen, max_gap=DEFAULT_MAX_GAP)
    roh = true_ranges(kerzen, max_gap=None)
    atr = wilder_atr(bereinigt, period=ATR_PERIOD)
    atr_roh = wilder_atr(roh, period=ATR_PERIOD)
    if not atr:
        return not_measured(schluessel, "ATR-Reihe leer trotz ausreichender Kerzenzahl")

    # Die ATR-Reihe beginnt bei Kerze ``ATR_PERIOD`` (die erste TR gehoert zu Kerze 1).
    passende_schlusskurse = schlusskurse[ATR_PERIOD:]
    bps = atr_series_bps(atr, passende_schlusskurse)

    spreads = [
        float(rate.spread_points)
        for rate in rates
        if rate.spread_points is not None and float(rate.spread_points) > 0
    ]

    return AtrMeasurement(
        symbol=schluessel,
        status=STATUS_MEASURED,
        reason=None,
        bars=len(rates),
        window_start=rates[0].ts.isoformat(),
        window_end=rates[-1].ts.isoformat(),
        atr_median_price=percentile(atr, 0.50),
        atr_p25_price=percentile(atr, 0.25),
        atr_median_bps=percentile(bps, 0.50),
        atr_p25_bps=percentile(bps, 0.25),
        atr_median_price_roh=percentile(atr_roh, 0.50) if atr_roh else None,
        price_median=percentile(schlusskurse, 0.50),
        spread_median_points=percentile(spreads, 0.50) if spreads else None,
        spread_p75_points=percentile(spreads, 0.75) if spreads else None,
        point=float(info.tick_size),
        digits=info.digits,
        contract_size=float(info.contract_size),
        gap_bars=gap_count(kerzen, max_gap=DEFAULT_MAX_GAP),
    )


#: Umrechnungskurse, die das Kostentor braucht, um eine Kommission in fremder Waehrung
#: in Basispunkte des Nominals umzurechnen. Gemessen, nicht geraten.
FX_PAARE: tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY")


def _geschlossene_rates(
    terminal: RealMt5Terminal,
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    ende: datetime,
) -> tuple[Mt5Rate, ...]:
    """Kerzen im Fenster, **ohne** die noch in Bildung befindliche.

    ``terminal.rates`` liefert bei ``ende = jetzt`` die laufende Kerze mit; ihr
    ``close`` ist der Momentankurs. Fuer :func:`_messe_fx` ist das unmittelbar
    folgenreich -- dort wird genau ``rates[-1].close`` als Umrechnungskurs benutzt,
    also ein Zwischenstand statt eines Schlusskurses. Fuer die ATR-Reihe verzerrt
    dieselbe Kerze den Median um einen Beitrag, der sich noch aendert.

    ``jetzt`` kommt vom Tick desselben Symbols, nicht von der Rechneruhr: Kerzen- und
    Tick-Stempel laufen durch dieselbe Umrechnung des Terminals, die Rechneruhr nicht.
    Ohne Tick wird **nichts** zurueckgegeben statt geraten -- der Aufrufer meldet das
    als „nicht gemessen" weiter, und ein fehlender Messwert sperrt, statt einen
    Vorgabewert zu erzeugen.
    """
    tick = terminal.tick(symbol)
    if tick is None:
        return ()
    return tuple(
        r
        for r in terminal.rates(symbol, timeframe, start, ende)
        if ist_abgeschlossen(r.ts, timeframe, tick.ts)
    )


def _messe_fx(
    terminal: RealMt5Terminal, start: datetime, ende: datetime
) -> dict[str, float]:
    """Letzter **abgeschlossener** H1-Schlusskurs je Umrechnungspaar.

    Fehlt eines, fehlt es sichtbar -- und ein Paar ohne Tick zaehlt als fehlend,
    nicht als „nimm die laufende Kerze".
    """
    out: dict[str, float] = {}
    for paar in FX_PAARE:
        rates = _geschlossene_rates(terminal, paar, Timeframe.H1, start, ende)
        if rates:
            out[paar] = float(rates[-1].close)
    return out


def _bericht(messung: AtrMeasurement) -> str:
    if not messung.measured:
        return f"  {messung.symbol:8s} NICHT GEMESSEN — {messung.reason}"
    assert messung.atr_median_bps is not None  # noqa: S101 - durch status garantiert
    assert messung.atr_p25_bps is not None  # noqa: S101
    assert messung.atr_median_price is not None  # noqa: S101
    assert messung.price_median is not None  # noqa: S101
    spread = (
        f"{messung.spread_median_points:.1f}"
        if messung.spread_median_points is not None
        else "-"
    )
    return (
        f"  {messung.symbol:8s} bars={messung.bars:6d} "
        f"ATR50={messung.atr_median_price:.5f} ({messung.atr_median_bps:6.2f} bp) "
        f"ATR25={messung.atr_p25_bps:6.2f} bp  "
        f"P50={messung.price_median:.2f}  "
        f"Spread50={spread} pt  Luecken={messung.gap_bars}"
    )


def messen(monate: int) -> int:
    ende = datetime.now(UTC)
    start = ende - timedelta(days=int(round(monate * 30.44)))

    terminal = RealMt5Terminal(allow_write=False)
    try:
        verbunden = terminal.initialize()
    except VenueUnavailableError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        print("Keine Ersatzzahlen. Ohne Terminal keine Volatilitaet.", file=sys.stderr)
        return 2
    if not verbunden:
        print(
            "FEHLGESCHLAGEN — MT5-Terminal nicht initialisierbar. "
            "Keine Ersatzzahlen: ein Kostentor auf geratener Volatilitaet ist wertlos.",
            file=sys.stderr,
        )
        return 2

    try:
        konto = terminal.account()
        if not konto.is_demo:
            print(
                "FEHLGESCHLAGEN — verbundenes Konto ist KEIN Demokonto. "
                "Der Auftrag erlaubt nur den lesenden Demo-Pfad.",
                file=sys.stderr,
            )
            return 2

        print(f"Terminal verbunden. Demokonto: ja. Kontowaehrung: {konto.currency}")
        print(
            f"Fenster: {start.date()} .. {ende.date()} "
            f"({monate} Monate), Zeitrahmen H1, ATR({ATR_PERIOD}) nach Wilder, "
            f"Luecken-Bereinigung ab {DEFAULT_MAX_GAP}."
        )
        print()

        messungen = [
            _messe_symbol(terminal, schluessel, symbol, start, ende)
            for schluessel, symbol, _ in PRUEFUNIVERSUM
        ]
        kurse = _messe_fx(terminal, start, ende)
    finally:
        terminal.shutdown()

    for messung in messungen:
        print(_bericht(messung))

    gemessen = sum(1 for m in messungen if m.measured)
    print()
    print(f"Gemessen: {gemessen} von {len(messungen)} Pruefinstrumenten.")

    dokument: dict[str, Any] = {
        "schema_version": 1,
        "measurement_id": ATR_MEASUREMENT_VERSION,
        "measured_on": ende.date().isoformat(),
        "window_start": start.isoformat(),
        "window_end": ende.isoformat(),
        "window_months": monate,
        "timeframe": "H1",
        "atr_period": ATR_PERIOD,
        "method": (
            "True Range nach Wilder; Verkettung zum Vorgaenger geloest bei Pausen "
            f"ueber {DEFAULT_MAX_GAP} (Wochenende/Boersenpause), damit Kursspruenge "
            "ueber die Pause den ATR nicht aufblaehen. Die unbereinigte Reihe steht "
            "zum Vergleich in 'atr_median_price_roh'."
        ),
        "terminal": {
            "server": "MetaQuotes-Demo",
            "is_demo": True,
            "note": (
                "Feed des Demo-Handelsplatzes, nicht der Feed eines der recherchierten "
                "Broker. Volatilitaet ist eine Markteigenschaft und zwischen Anbietern "
                "nahezu gleich; Kosten sind es nicht und stehen darum getrennt in "
                "config/broker_costs.json."
            ),
        },
        "fx_rates": kurse,
        "fx_rates_note": (
            "Letzter H1-Schlusskurs im Messfenster, aus demselben Lauf. Dient allein "
            "der Umrechnung einer Kommission in fremder Waehrung in Basispunkte des "
            "Nominals; kein Handelskurs."
        ),
        "instruments": {m.symbol: _als_json(m) for m in messungen},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(dokument, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Geschrieben: {OUT.relative_to(REPO).as_posix()}")

    if gemessen == 0:
        print(
            "FEHLGESCHLAGEN — kein einziges Instrument gemessen.",
            file=sys.stderr,
        )
        return 2
    return 0


def _als_json(messung: AtrMeasurement) -> dict[str, Any]:
    daten = asdict(messung)
    daten.pop("symbol")
    return daten


def pruefen() -> int:
    try:
        messungen = load_atr_measurements(OUT)
    except AtrMeasurementError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 1
    gemessen = sum(1 for m in messungen.values() if m.measured)
    print(
        f"ok — {OUT.name} ladbar: {gemessen} von {len(messungen)} "
        "Instrumenten gemessen."
    )
    for messung in messungen.values():
        if not messung.measured:
            print(f"  nicht gemessen: {messung.symbol} — {messung.reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ATR(14) auf H1 ueber den lesenden MT5-Demo-Pfad messen."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="nur die vorhandene Messdatei laden und pruefen (ohne Terminal)",
    )
    parser.add_argument(
        "--monate", type=int, default=12, help="Fensterlaenge in Monaten (Default 12)"
    )
    args = parser.parse_args()
    if args.check:
        return pruefen()
    if args.monate <= 0:
        print("FEHLGESCHLAGEN — --monate muss positiv sein", file=sys.stderr)
        return 1
    return messen(args.monate)


if __name__ == "__main__":
    sys.exit(main())

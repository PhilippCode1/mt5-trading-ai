#!/usr/bin/env python3
"""Netzwerk-Abruf historischer Bars + Gegenprobe zweier Quellen (Paket 2).

Laedt Dukascopy-Tageskerzen (institutionell, keyless, bid-Seite) fuer ein Instrument,
filtert auf die FX-Session (Mo-Fr), prueft gegen das Datenqualitaetstor und legt die
Reihe reproduzierbar ab -- mit Pruefsumme. Bricht ab, wenn das Tor nicht besteht.

Zusaetzlich die Gegenprobe R2.2: dieselbe Zeitspanne aus einer zweiten Quelle (Yahoo),
Abweichung Close-zu-Close in **Basispunkten** -- so wird sichtbar, wie weit ein
synthetischer/alternativer Feed vom institutionellen abweicht.

Dieses Werkzeug macht Netzwerk-I/O und laeuft NICHT in der CI; es ist der Schritt des
Betreibers. Die eigentliche Dekodier-/Pruef-/Ablage-Logik steht (netzfrei, getestet) in
``mt5_trading_ai/data/loader.py``.

Aufruf:
  python tools/fetch_data.py --from-year 2022 --to-year 2024 --out DIR
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.data.loader import (  # noqa: E402
    DUKASCOPY_PRICE_DIVISORS,
    DataLoadError,
    WeekdaySession,
    assess_or_raise,
    dataset_manifest,
    decode_dukascopy_candles,
    dukascopy_price_divisor,
    filter_to_weekdays,
    manifest_checksum,
    parse_yahoo_daily,
    to_csv,
)
from mt5_trading_ai.data.quality import BarRow  # noqa: E402

_UA = {"User-Agent": "Mozilla/5.0 (mt5-trading-ai data fetch)"}


def http_get(url: str, *, tries: int = 6, timeout: int = 30) -> bytes:
    """GET mit Backoff bei 503/429/500 (Dukascopy rate-limitet zeitweise)."""
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return bytes(resp.read())
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (503, 429, 500):
                time.sleep(2.0 * (i + 1))
                continue
            raise
        except urllib.error.URLError as exc:
            last = exc
            time.sleep(2.0 * (i + 1))
    raise DataLoadError(f"Abruf fehlgeschlagen nach {tries} Versuchen: {url} ({last})")


def fetch_dukascopy_year(instrument: str, year: int) -> list[BarRow]:
    url = (
        f"https://datafeed.dukascopy.com/datafeed/{instrument}"
        f"/{year}/BID_candles_day_1.bi5"
    )
    raw = http_get(url)
    return decode_dukascopy_candles(
        raw,
        period_start=datetime(year, 1, 1, tzinfo=UTC),
        price_divisor=dukascopy_price_divisor(instrument),
    )


def fetch_dukascopy_month_hours(
    instrument: str, year: int, month: int
) -> list[BarRow]:
    """Stundenkerzen eines Monats. Dukascopy legt sie **monatsweise** ab, nicht wie die
    Tageskerzen jahresweise, und zaehlt den Monat ab 0.

    Gebraucht werden sie fuer die Gegenprobe auf dem Zeitrahmen, auf dem die Studien
    tatsaechlich laufen: eine Pruefung nur auf D1 sagt nichts ueber 1h- und 4h-Fenster.
    """
    url = (
        f"https://datafeed.dukascopy.com/datafeed/{instrument}"
        f"/{year}/{month - 1:02d}/BID_candles_hour_1.bi5"
    )
    return decode_dukascopy_candles(
        http_get(url),
        period_start=datetime(year, month, 1, tzinfo=UTC),
        price_divisor=dukascopy_price_divisor(instrument),
    )


def drop_filler_bars(bars: list[BarRow]) -> list[BarRow]:
    """Wirf Kerzen ohne Umsatz weg — Dukascopy fuellt handelsfreie Stunden flach auf.

    Sie stehen in der Datei wie echte Kerzen, tragen aber keinen Handel. Behielte man
    sie, saehe die Reihe vollstaendiger aus, als sie ist, und die Streuung kleiner —
    also der Fehler in der schmeichelnden Richtung.
    """
    ohne = [b for b in bars if b.volume is None]
    if ohne:
        raise DataLoadError(
            f"{len(ohne)} Kerzen ohne Umsatzangabe — handelsfreie Stunden sind damit "
            "nicht erkennbar; fail-closed statt raten"
        )
    return [b for b in bars if b.volume is not None and b.volume > 0.0]


def fetch_yahoo_daily(instrument: str, start: datetime, end: datetime) -> list[BarRow]:
    p1 = int(start.timestamp())
    p2 = int(end.timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{instrument}=X"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    payload = json.loads(http_get(url).decode("utf-8"))
    return parse_yahoo_daily(payload)


def counter_check_bps(
    reference: list[BarRow], other: list[BarRow]
) -> tuple[float, float, float, int]:
    """Abweichung Close-zu-Close in Basispunkten je gemeinsamem Handelstag.

    Rueckgabe: (mittlere, mediane, maximale bps, Zahl verglichener Tage). Der Median ist
    robuster als das Mittel gegen einzelne Ausreisser-Tage der schmutzigeren Quelle.
    """
    by_day = {b.ts.date(): b.close for b in reference}
    diffs: list[float] = []
    for b in other:
        ref = by_day.get(b.ts.date())
        if ref is None or ref <= 0:
            continue
        mid = (ref + b.close) / 2
        diffs.append(abs(b.close - ref) / mid * 10000)
    if not diffs:
        return (0.0, 0.0, 0.0, 0)
    return (
        sum(diffs) / len(diffs), statistics.median(diffs), max(diffs), len(diffs)
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Historische Bars laden + Gegenprobe")
    ap.add_argument(
        "--instrument", default="EURUSD", choices=sorted(DUKASCOPY_PRICE_DIVISORS)
    )
    ap.add_argument("--from-year", type=int, required=True)
    ap.add_argument("--to-year", type=int, required=True)
    ap.add_argument("--timeframe", default="D1", choices=("D1", "H1"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    tf = args.timeframe.upper()
    if tf not in ("D1", "H1"):
        raise DataLoadError(f"Zeitrahmen {tf} wird nicht abgerufen (D1 oder H1)")

    print(f"Dukascopy {args.instrument} {tf} {args.from_year}-{args.to_year} ...")
    raw_bars: list[BarRow] = []
    erster = True
    for year in range(args.from_year, args.to_year + 1):
        if tf == "D1":
            if not erster:
                time.sleep(3)  # hoeflich: Dukascopy rate-limitet schnelle Abrufe
            erster = False
            year_bars = fetch_dukascopy_year(args.instrument, year)
            if len(year_bars) < 300:
                raise DataLoadError(
                    f"Jahr {year} unvollstaendig: nur {len(year_bars)} "
                    f"Kalendertag-Bars (abgeschnittene Datei?)"
                )
        else:
            year_bars = []
            for month in range(1, 13):
                if not erster:
                    time.sleep(3)
                erster = False
                year_bars.extend(
                    fetch_dukascopy_month_hours(args.instrument, year, month)
                )
        raw_bars.extend(year_bars)
        print(f"  {year}: {len(year_bars)} Rohkerzen")

    if tf == "H1":
        vorher = len(raw_bars)
        raw_bars = drop_filler_bars(raw_bars)
        print(f"  handelsfreie Fuellkerzen verworfen: {vorher - len(raw_bars)}")
    bars = sorted(filter_to_weekdays(raw_bars), key=lambda b: b.ts)
    report = assess_or_raise(
        bars,
        instrument=args.instrument,
        timeframe=tf,
        session_predicate=WeekdaySession(),
    )
    manifest = dataset_manifest(
        instrument=args.instrument,
        timeframe=tf,
        source=f"dukascopy-bid-{'day' if tf == 'D1' else 'hour'}",
        price_divisor=dukascopy_price_divisor(args.instrument),
        session="weekday-utc",
        bars=bars,
        quality_reasons=report.reasons,
    )
    mchk = manifest_checksum(manifest)

    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / f"{args.instrument}_{tf}.csv"
    csv_path.write_text(to_csv(bars), encoding="utf-8")
    (args.out / f"{args.instrument}_{tf}.manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"\nQualitaetstor: BESTANDEN | Bars {report.present_bars} "
        f"(erwartet {report.expected_bars}) | Luecke {report.gap_ratio * 100:.3f} % | "
        f"Ausreisser {len(report.outlier_bars)}"
    )
    print(f"Zeitraum: {bars[0].ts.date()} .. {bars[-1].ts.date()}")
    print(f"Bars-Pruefsumme: {manifest['bars_checksum']}")
    print(f"Manifest-Pruefsumme (inkl. Herkunft/Divisor/Urteil): {mchk}")
    print(f"Ablage: {csv_path}")

    print("\nGegenprobe R2.2 (Dukascopy vs Yahoo, Close-zu-Close):")
    try:
        yahoo_raw = fetch_yahoo_daily(args.instrument, bars[0].ts, bars[-1].ts)
        yahoo = [
            b for b in yahoo_raw
            if b.low <= b.open <= b.high and b.low <= b.close <= b.high
        ]
        dropped = len(yahoo_raw) - len(yahoo)
        mean_bps, median_bps, max_bps, days = counter_check_bps(bars, yahoo)
        print(
            f"  Yahoo {len(yahoo_raw)} Bars ({dropped} OHLC-ungueltige verworfen) | "
            f"verglichene Tage: {days}"
        )
        print(
            f"  Abweichung: Median {median_bps:.2f} bps | Mittel {mean_bps:.2f} bps | "
            f"max {max_bps:.2f} bps"
        )
    except DataLoadError as exc:
        print(f"  Gegenprobe nicht moeglich (zweite Quelle): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

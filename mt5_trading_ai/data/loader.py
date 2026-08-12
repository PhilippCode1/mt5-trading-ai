"""Lader fuer historische Bars -- an das Datenqualitaetstor gekettet.

WARUM ES DIESES MODUL GIBT
--------------------------
Ein Backtest ist nur so gut wie seine Daten. Broker-interne CFD-Feeds sind synthetische
Hauspreise; ein Backtest darauf misst die Eigenheiten eines Brokers, nicht den Markt.
Dieser Lader liest historische Bars aus einer externen Quelle, **normalisiert** sie
(Zeitstempel, Session) und laesst sie durch ``data/quality.py`` pruefen. Besteht die
Reihe das Tor nicht, bricht der Lader ab -- ein Backtest auf schmutzigen Daten ist
schlimmer als keiner, weil er Vertrauen erzeugt, das nicht gedeckt ist.

Reproduzierbarkeit: dieselbe Bar-Reihe ergibt dieselbe Pruefsumme (``bars_checksum``).
Die Pruefsumme steht in jedem Backtest-Bericht; ein neuer Datenstand faellt sofort auf.

Dieses Modul ist rein (kein Netzwerk): es dekodiert/parst gelieferte Rohdaten und prueft
sie. Der Netzwerk-Abruf liegt in ``tools/fetch_data.py`` -- so bleibt der Lader
deterministisch testbar.
"""

from __future__ import annotations

import hashlib
import json
import lzma
import struct
from datetime import UTC, datetime, timedelta
from typing import Any

from mt5_trading_ai.data.quality import (
    TIMEFRAME_SECONDS,
    BarRow,
    QualityReport,
    SessionPredicate,
    assess_bars,
)

DATA_LOADER_VERSION = "data-loader-v1"

#: Dukascopy-Candle-Datensatz (LZMA): Zeit (Sekunden-Offset), open, close, low, high
#: (je **unsigned** int32, Preis * divisor), Volumen (float32). Unsigned, weil Dukascopy
#: nicht-negativ skaliert und ein signed-Overflow bei hohen Kursen still falsch waere.
_DUKASCOPY_CANDLE = struct.Struct(">IIIIIf")

#: Preis-Divisor je Instrument -- Dukascopy skaliert nach Nachkommastellen. Ein fest
#: verdrahteter Wert wuerde jedes Nicht-5-stellige Paar (JPY) still 100x falsch machen.
DUKASCOPY_PRICE_DIVISORS: dict[str, float] = {
    "EURUSD": 100000.0, "GBPUSD": 100000.0, "AUDUSD": 100000.0, "NZDUSD": 100000.0,
    "EURGBP": 100000.0, "USDCHF": 100000.0, "USDCAD": 100000.0,
    "USDJPY": 1000.0, "EURJPY": 1000.0, "GBPJPY": 1000.0,
}

#: Mehr als so viele aufeinanderfolgende fehlende Handels-Slots sind ein Block-Ausfall,
#: den die global gemittelte Lueckenquote auf langen Reihen nicht faengt.
MAX_CONSECUTIVE_GAP = 3


def dukascopy_price_divisor(instrument: str) -> float:
    """Preis-Divisor fuer ein Instrument; unbekannt -> Fehler (nie still 5-stellig)."""
    try:
        return DUKASCOPY_PRICE_DIVISORS[instrument.upper()]
    except KeyError as exc:
        raise DataLoadError(
            f"Kein Preis-Divisor fuer {instrument!r} hinterlegt -- fail-closed"
        ) from exc


class DataLoadError(ValueError):
    """Daten fehlen, sind unlesbar oder bestehen das Tor nicht. Fail-closed."""


class WeekdaySession(SessionPredicate):
    """FX-Session als Handelstag Mo-Fr (UTC). Wochenend-Bars sind keine Session."""

    def __call__(self, ts: datetime) -> bool:
        return ts.weekday() < 5


def decode_dukascopy_candles(
    raw: bytes,
    *,
    period_start: datetime,
    price_divisor: float,
) -> list[BarRow]:
    """Dekodiere eine Dukascopy-Candle-bi5-Datei (LZMA) zu Bars.

    ``period_start`` ist der UTC-Beginn der Periode (Jahresanfang bei Tageskerzen); die
    Zeit je Datensatz ist ein Sekunden-Offset darauf. OHLC-Reihenfolge im Rohsatz ist
    open, **close, low, high** -- hier korrekt auf O/H/L/C abgebildet.
    """
    try:
        dec = lzma.decompress(raw)
    except lzma.LZMAError as exc:
        raise DataLoadError(f"Dukascopy-Datei nicht dekomprimierbar: {exc}") from exc
    size = _DUKASCOPY_CANDLE.size
    if not dec or len(dec) % size != 0:
        raise DataLoadError(
            f"Dukascopy-Rohdaten haben keine {size}-Byte-Struktur: {len(dec)} Bytes"
        )
    if price_divisor <= 0:
        raise DataLoadError("price_divisor muss positiv sein")
    bars: list[BarRow] = []
    for offset in range(0, len(dec), size):
        t, o, c, low, high, vol = _DUKASCOPY_CANDLE.unpack_from(dec, offset)
        ts = period_start + timedelta(seconds=t)
        bars.append(
            BarRow(
                ts=ts,
                open=o / price_divisor,
                high=high / price_divisor,
                low=low / price_divisor,
                close=c / price_divisor,
                volume=float(vol),
            )
        )
    return bars


def parse_yahoo_daily(payload: dict[str, Any]) -> list[BarRow]:
    """Parse eine Yahoo-Chart-API-Antwort (Tageskerzen) zu Bars.

    Yahoo stempelt Tagesbars je nach Sommerzeit auf 00:00 **oder** 23:00 UTC -- hier auf
    die naechste UTC-Mitternacht gerundet (sonst waeren die Bars nicht aligned und die
    Wochentage verschoben). Bars mit fehlendem OHLC werden uebersprungen (sie werden
    so zu einer Luecke, die das Qualitaetstor sieht -- nicht zu einer erfundenen Bar).
    Yahoo-FX fuehrt kein echtes Volumen -> ``volume=None``.
    """
    try:
        result = payload["chart"]["result"][0]
        stamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise DataLoadError(f"Yahoo-Antwort unbrauchbar: {exc}") from exc
    bars: list[BarRow] = []
    for i, epoch in enumerate(stamps):
        o, h = quote["open"][i], quote["high"][i]
        low, c = quote["low"][i], quote["close"][i]
        if None in (o, h, low, c):
            continue
        day = round(epoch / 86400) * 86400
        bars.append(
            BarRow(
                ts=datetime.fromtimestamp(day, tz=UTC),
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=None,
            )
        )
    return bars


def filter_to_weekdays(bars: list[BarRow]) -> list[BarRow]:
    """Behalte nur Mo-Fr-Bars. FX handelt am Wochenende nicht; eine Sa/So-Bar ist ein
    Vendor-Artefakt -- das ist Session-Normalisierung, kein Schoenen."""
    return [b for b in bars if b.ts.weekday() < 5]


def _max_consecutive_gap(
    bars: list[BarRow],
    *,
    session_predicate: SessionPredicate,
    seconds: int,
    start: datetime,
    end: datetime,
) -> int:
    """Laengster Lauf aufeinanderfolgender fehlender Session-Slots im Fenster."""
    present = {b.ts for b in bars}
    step = timedelta(seconds=seconds)
    run = worst = 0
    cursor = start
    while cursor < end:
        if session_predicate(cursor):
            run = 0 if cursor in present else run + 1
            worst = max(worst, run)
        cursor += step
    return worst


def assess_or_raise(
    bars: list[BarRow],
    *,
    instrument: str,
    timeframe: str,
    session_predicate: SessionPredicate,
) -> QualityReport:
    """Pruefe die Bars gegen das Qualitaetstor; bei Nichtbestehen ``DataLoadError``.

    ``start``/``end`` werden aus der Reihe abgeleitet (erste Bar bis eine Stufe nach der
    letzten). Eine leere Reihe besteht nicht.
    """
    if not bars:
        raise DataLoadError("Keine Bars geladen")
    seconds = TIMEFRAME_SECONDS.get(timeframe.upper())
    if not seconds:
        raise DataLoadError(f"Unbekannter Zeitrahmen: {timeframe}")
    start = min(b.ts for b in bars)
    end = max(b.ts for b in bars) + timedelta(seconds=seconds)
    report = assess_bars(
        bars,
        instrument=instrument,
        timeframe=timeframe,
        start=start,
        end=end,
        session_predicate=session_predicate,
    )
    if not report.passed:
        raise DataLoadError(
            f"Qualitaetstor nicht bestanden ({instrument} {timeframe}): "
            f"{', '.join(report.reasons)}"
        )
    worst = _max_consecutive_gap(
        bars, session_predicate=session_predicate, seconds=seconds, start=start, end=end
    )
    if worst > MAX_CONSECUTIVE_GAP:
        raise DataLoadError(
            f"Block-Ausfall: {worst} aufeinanderfolgende fehlende Handelstage "
            f"(> {MAX_CONSECUTIVE_GAP}) -- die globale Lueckenquote faengt das nicht"
        )
    return report


# --- Reproduzierbare Ablage + Pruefsumme ---------------------------------


_CSV_HEADER = "ts,open,high,low,close,volume"


def to_csv(bars: list[BarRow]) -> str:
    """Kanonische CSV-Serialisierung. ``repr`` haelt Floats verlustfrei (round-trip)."""
    lines = [_CSV_HEADER]
    for b in bars:
        vol = "" if b.volume is None else repr(b.volume)
        lines.append(
            f"{b.ts.isoformat()},{b.open!r},{b.high!r},{b.low!r},{b.close!r},{vol}"
        )
    return "\n".join(lines) + "\n"


def from_csv(text: str) -> list[BarRow]:
    lines = text.strip().splitlines()
    if not lines or lines[0] != _CSV_HEADER:
        raise DataLoadError("CSV-Kopf fehlt oder ist unerwartet")
    bars: list[BarRow] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != 6:
            raise DataLoadError(f"CSV-Zeile mit {len(parts)} Feldern: {line!r}")
        ts, o, h, low, c, vol = parts
        bars.append(
            BarRow(
                ts=datetime.fromisoformat(ts),
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=None if vol == "" else float(vol),
            )
        )
    return bars


def bars_checksum(bars: list[BarRow]) -> str:
    """SHA-256 der kanonischen CSV-Form. Gleiche Bars -> gleiche Pruefsumme."""
    return hashlib.sha256(to_csv(bars).encode("utf-8")).hexdigest()


def dataset_manifest(
    *,
    instrument: str,
    timeframe: str,
    source: str,
    price_divisor: float,
    session: str,
    bars: list[BarRow],
    quality_reasons: tuple[str, ...],
) -> dict[str, Any]:
    """Manifest, das die Bars UND ihre Herkunft/Semantik festhaelt.

    Eine reine Bar-Pruefsumme zertifiziert nur die Zahlen -- eine fehl-dekodierte Reihe
    (falscher Divisor) waere trotzdem reproduzierbar. Das Manifest bindet zusaetzlich
    Instrument, Zeitrahmen, Quelle, Divisor, Session, Loader-Version und das Urteil.
    """
    return {
        "loader_version": DATA_LOADER_VERSION,
        "instrument": instrument,
        "timeframe": timeframe.upper(),
        "source": source,
        "price_divisor": price_divisor,
        "session": session,
        "bar_count": len(bars),
        "first_ts": bars[0].ts.isoformat() if bars else None,
        "last_ts": bars[-1].ts.isoformat() if bars else None,
        "bars_checksum": bars_checksum(bars),
        "quality_reasons": list(quality_reasons),
    }


def manifest_checksum(manifest: dict[str, Any]) -> str:
    """SHA-256 des kanonischen Manifests (sortierte Schluessel)."""
    return hashlib.sha256(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

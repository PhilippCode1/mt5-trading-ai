"""Datenqualitaet als Gate (Phase 7.2).

Kein Backtest und kein Betrieb auf ungeprueften Daten. Diese Datei prueft eine
Bar-Reihe gegen vier Kriterien und liefert ein Urteil, das den Handel mit diesem
Instrument freigibt oder nicht:

1. **Lueckenquote** gegen die erwartete Bar-Zahl innerhalb der Handelszeiten,
   global ueber die Reihe. Ueber 1 %: Instrument raus. Achtung: die globale Quote
   verdeckt zusammenhaengende Block-Ausfaelle auf langen Reihen -- der Lader
   (``data/loader.py``) ergaenzt dafuer einen Max-Consecutive-Gap-Check.
2. **Zeitstempel-Konsistenz** — streng aufsteigend, auf dem Zeitrahmen-Raster,
   durchgehend UTC, keine Duplikate.
3. **Ausreisser und Nullvolumen-Bars** werden markiert, nicht entfernt. Wer sie
   entfernt, bekommt eine schoenere Reihe und einen falschen Backtest.
4. **Handelszeiten** — Bars ausserhalb der Sitzung sind ein Datenfehler, kein
   Bonus.

Eine fehlende Angabe ist nie „in Ordnung": ohne Handelszeiten kann die
Lueckenquote nicht bestimmt werden, und dann ist das Urteil ``nicht bestanden``.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

DATA_QUALITY_VERSION = "data-quality-v1"

#: Ab dieser Lueckenquote faellt ein Instrument aus.
MAX_GAP_RATIO = 0.01
#: Bewegung in Vielfachen der medianen Bar-Spanne, ab der eine Bar als Ausreisser gilt.
OUTLIER_RANGE_FACTOR = 12.0

TIMEFRAME_SECONDS: dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


@dataclass(frozen=True)
class BarRow:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None


@dataclass(frozen=True)
class QualityReport:
    instrument: str
    timeframe: str
    expected_bars: int
    present_bars: int
    gap_ratio: float
    duplicate_timestamps: int
    unaligned_timestamps: int
    non_monotonic: int
    naive_timestamps: int
    outlier_bars: tuple[datetime, ...]
    zero_volume_bars: tuple[datetime, ...]
    outside_session_bars: tuple[datetime, ...]
    invalid_ohlc_bars: tuple[datetime, ...]
    passed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    version: str = DATA_QUALITY_VERSION


def expected_bar_count(
    *,
    start: datetime,
    end: datetime,
    timeframe: str,
    session_predicate: SessionPredicate | None,
    holidays: frozenset[date] = frozenset(),
) -> int:
    """Erwartete Bar-Zahl **innerhalb der Handelszeiten**, ohne Feiertage.

    Ohne ``session_predicate`` ist die Zahl nicht bestimmbar; die Funktion gibt
    dann ``0`` zurueck und der Aufrufer wertet das als nicht bestanden. Feiertage
    (S6) zaehlen nicht als erwartete Slots -- eine ausgelassene Feiertags-Bar ist
    keine Luecke.
    """
    if session_predicate is None:
        return 0
    seconds = TIMEFRAME_SECONDS.get(timeframe.upper())
    if not seconds:
        return 0
    step = timedelta(seconds=seconds)
    count = 0
    cursor = start
    while cursor < end:
        if session_predicate(cursor) and cursor.date() not in holidays:
            count += 1
        cursor += step
    return count


class SessionPredicate:
    """Ist ``ts`` innerhalb der Handelszeiten?

    Callable, damit Tests es ersetzen koennen.
    """

    def __call__(self, ts: datetime) -> bool:  # pragma: no cover - Protokollform
        raise NotImplementedError


def assess_bars(
    rows: list[BarRow],
    *,
    instrument: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    session_predicate: SessionPredicate | None = None,
    holidays: frozenset[date] = frozenset(),
    max_gap_ratio: float = MAX_GAP_RATIO,
) -> QualityReport:
    reasons: list[str] = []
    seconds = TIMEFRAME_SECONDS.get(timeframe.upper())

    seen: set[datetime] = set()
    duplicates = 0
    unaligned = 0
    non_monotonic = 0
    naive = 0
    outliers: list[datetime] = []
    zero_volume: list[datetime] = []
    outside_session: list[datetime] = []
    invalid_ohlc: list[datetime] = []

    previous: datetime | None = None
    ranges: list[float] = []

    for row in rows:
        ts = row.ts
        if ts.tzinfo is None:
            naive += 1
        if ts in seen:
            duplicates += 1
        seen.add(ts)
        if previous is not None and ts <= previous:
            non_monotonic += 1
        previous = ts
        if seconds and int(ts.timestamp()) % seconds != 0:
            unaligned += 1
        if session_predicate is not None and not session_predicate(ts):
            outside_session.append(ts)
        if row.volume is not None and row.volume == 0:
            zero_volume.append(ts)
        if not (row.low <= row.open <= row.high and row.low <= row.close <= row.high):
            invalid_ohlc.append(ts)
        ranges.append(abs(row.high - row.low))

    if ranges:
        median_range = statistics.median(
            [value for value in ranges if value > 0] or [0.0]
        )
        if median_range > 0:
            for row in rows:
                if abs(row.high - row.low) > median_range * OUTLIER_RANGE_FACTOR:
                    outliers.append(row.ts)

    expected = expected_bar_count(
        start=start,
        end=end,
        timeframe=timeframe,
        session_predicate=session_predicate,
        holidays=holidays,
    )
    present = len(seen)
    # Fuer die Lueckenquote nur Bars zaehlen, die auf einem ERWARTETEN Slot liegen (in
    # Session, nicht Feiertag). Eine feiertagsverschobene oder ausser-Session-Bar wuerde
    # ``present`` sonst aufblaehen und echte Luecken untertreiben (konservativ, S6).
    present_expected = len(
        {
            row.ts
            for row in rows
            if session_predicate is not None
            and session_predicate(row.ts)
            and row.ts.date() not in holidays
        }
    )
    if expected <= 0:
        gap_ratio = 1.0
        reasons.append("expected_bar_count_unknown")
    else:
        gap_ratio = max(0.0, (expected - present_expected) / expected)

    if gap_ratio > max_gap_ratio:
        reasons.append("gap_ratio_above_limit")
    if duplicates:
        reasons.append("duplicate_timestamps")
    if non_monotonic:
        reasons.append("timestamps_not_monotonic")
    if unaligned:
        reasons.append("timestamps_not_aligned_to_timeframe")
    if naive:
        reasons.append("timestamps_without_timezone")
    if outside_session:
        reasons.append("bars_outside_session")
    if invalid_ohlc:
        reasons.append("invalid_ohlc")

    return QualityReport(
        instrument=instrument,
        timeframe=timeframe.upper(),
        expected_bars=expected,
        present_bars=present,
        gap_ratio=gap_ratio,
        duplicate_timestamps=duplicates,
        unaligned_timestamps=unaligned,
        non_monotonic=non_monotonic,
        naive_timestamps=naive,
        outlier_bars=tuple(outliers),
        zero_volume_bars=tuple(zero_volume),
        outside_session_bars=tuple(outside_session),
        invalid_ohlc_bars=tuple(invalid_ohlc),
        passed=not reasons,
        reasons=tuple(reasons),
    )

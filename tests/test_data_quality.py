"""Datenqualitaet als Gate: eine ungepruefte Reihe besteht nicht."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mt5_trading_ai.data.quality import (
    BarRow,
    SessionPredicate,
    assess_bars,
    expected_bar_count,
    render_markdown,
)

START = datetime(2026, 8, 3, 0, 0, tzinfo=UTC)
END = START + timedelta(hours=4)


class AlwaysOpen(SessionPredicate):
    def __call__(self, ts: datetime) -> bool:
        return True


class WeekdayMorningsOnly(SessionPredicate):
    def __call__(self, ts: datetime) -> bool:
        return ts.weekday() < 5 and ts.hour < 2


def _series(count: int = 240) -> list[BarRow]:
    return [
        BarRow(START + timedelta(minutes=i), 1.0, 1.1, 0.9, 1.05, 100.0)
        for i in range(count)
    ]


def _assess(rows: list[BarRow], **overrides: object):
    kwargs: dict[str, object] = {
        "instrument": "EURUSD",
        "timeframe": "M1",
        "start": START,
        "end": END,
        "session_predicate": AlwaysOpen(),
    }
    kwargs.update(overrides)
    return assess_bars(rows, **kwargs)  # type: ignore[arg-type]


def test_complete_series_passes() -> None:
    report = _assess(_series())
    assert report.passed is True
    assert report.gap_ratio == 0.0
    assert report.reasons == ()


def test_gap_ratio_above_one_percent_fails() -> None:
    rows = _series()
    del rows[10:20]
    report = _assess(rows)
    assert report.passed is False
    assert report.gap_ratio > 0.01
    assert "gap_ratio_above_limit" in report.reasons


def test_small_gap_stays_below_the_limit() -> None:
    rows = _series()
    del rows[10:12]
    report = _assess(rows)
    assert report.gap_ratio < 0.01
    assert report.passed is True


def test_missing_trading_hours_is_not_pass() -> None:
    """Ohne Handelszeiten ist die Lueckenquote nicht bestimmbar - also nicht bestanden."""
    report = _assess(_series(), session_predicate=None)
    assert report.passed is False
    assert "expected_bar_count_unknown" in report.reasons
    assert report.gap_ratio == 1.0


def test_duplicate_and_non_monotonic_timestamps_fail() -> None:
    rows = _series()
    rows.append(rows[3])
    report = _assess(rows)
    assert report.passed is False
    assert "duplicate_timestamps" in report.reasons
    assert "timestamps_not_monotonic" in report.reasons


def test_naive_timestamps_fail() -> None:
    rows = [BarRow(START.replace(tzinfo=None), 1.0, 1.1, 0.9, 1.05, 100.0)]
    report = _assess(rows)
    assert "timestamps_without_timezone" in report.reasons


def test_unaligned_timestamps_fail() -> None:
    rows = [BarRow(START + timedelta(seconds=17), 1.0, 1.1, 0.9, 1.05, 100.0)]
    report = _assess(rows)
    assert "timestamps_not_aligned_to_timeframe" in report.reasons


def test_invalid_ohlc_fails() -> None:
    rows = _series(5)
    rows[2] = BarRow(rows[2].ts, 1.0, 0.5, 0.9, 1.05, 100.0)
    report = _assess(rows)
    assert "invalid_ohlc" in report.reasons
    assert rows[2].ts in report.invalid_ohlc_bars


def test_outliers_and_zero_volume_are_flagged_not_removed() -> None:
    """Wer sie entfernt, bekommt eine schoenere Reihe und einen falschen Backtest."""
    rows = _series()
    rows[7] = BarRow(rows[7].ts, 1.0, 9.0, 0.9, 1.05, 100.0)
    rows[9] = BarRow(rows[9].ts, 1.0, 1.1, 0.9, 1.05, 0.0)
    report = _assess(rows)
    assert rows[7].ts in report.outlier_bars
    assert rows[9].ts in report.zero_volume_bars
    assert report.present_bars == len(rows)
    # Markiert, aber kein Ausschlussgrund fuer sich allein.
    assert "gap_ratio_above_limit" not in report.reasons


def test_bars_outside_the_session_are_a_data_error() -> None:
    report = _assess(_series(), session_predicate=WeekdayMorningsOnly())
    assert report.passed is False
    assert "bars_outside_session" in report.reasons


def test_expected_bar_count_respects_the_session() -> None:
    everything = expected_bar_count(
        start=START, end=END, timeframe="M1", session_predicate=AlwaysOpen()
    )
    mornings = expected_bar_count(
        start=START, end=END, timeframe="M1", session_predicate=WeekdayMorningsOnly()
    )
    assert everything == 240
    assert mornings == 120

    assert (
        expected_bar_count(start=START, end=END, timeframe="M1", session_predicate=None)
        == 0
    )
    assert (
        expected_bar_count(
            start=START, end=END, timeframe="UNBEKANNT", session_predicate=AlwaysOpen()
        )
        == 0
    )


def test_markdown_marks_failures_visibly() -> None:
    rows = _series()
    del rows[10:20]
    table = render_markdown([_assess(_series()), _assess(rows)])
    assert "**nein**" in table
    assert "| ja |" in table
    assert table.startswith("| Instrument |")

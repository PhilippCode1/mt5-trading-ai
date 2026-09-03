"""S6: Feiertags-/Intraday-Kalender fuers Qualitaetstor. Negativ gefahren."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from mt5_trading_ai.data.loader import FxSession, WeekdaySession
from mt5_trading_ai.data.quality import BarRow, assess_bars

# --- FxSession: die echte FX-Woche ----------------------------------------


def test_fx_session_sunday_open_is_ny_1700_winter() -> None:
    # Winter (Jan, NY = UTC-5): Oeffnung So 22:00 UTC = So 17:00 NY.
    sess = FxSession()
    assert sess(datetime(2025, 1, 5, 22, tzinfo=UTC))  # So 17:00 NY -> offen
    assert not sess(datetime(2025, 1, 5, 21, tzinfo=UTC))  # So 16:00 NY -> zu


def test_fx_session_sunday_open_shifts_with_dst_summer() -> None:
    # Sommer (Jul, NY = UTC-4): Oeffnung So 21:00 UTC = So 17:00 NY.
    sess = FxSession()
    assert sess(datetime(2025, 7, 6, 21, tzinfo=UTC))  # So 17:00 NY -> offen
    assert not sess(datetime(2025, 7, 6, 20, tzinfo=UTC))  # So 16:00 NY -> zu


def test_fx_session_excludes_saturday() -> None:
    sess = FxSession()
    assert not sess(datetime(2025, 1, 4, 12, tzinfo=UTC))  # Samstag: nie


def test_fx_session_friday_close_is_ny_1700() -> None:
    # Winter: Schluss Fr 22:00 UTC = Fr 17:00 NY.
    sess = FxSession()
    assert sess(datetime(2025, 1, 3, 21, tzinfo=UTC))  # Fr 16:00 NY -> offen
    assert not sess(datetime(2025, 1, 3, 22, tzinfo=UTC))  # Fr 17:00 NY -> zu


def test_weekday_session_is_monday_to_friday() -> None:
    sess = WeekdaySession()
    assert sess(datetime(2025, 1, 2, tzinfo=UTC))  # Donnerstag
    assert not sess(datetime(2025, 1, 4, tzinfo=UTC))  # Samstag


# --- Feiertag treibt die Lueckenquote nicht (S6) --------------------------


def _daily(days: list[int]) -> list[BarRow]:
    """Tagesbars fuer 2025-12-<Tag>, Mitternacht UTC."""
    return [
        BarRow(datetime(2025, 12, d, tzinfo=UTC), 1.10, 1.11, 1.09, 1.105, 1000.0)
        for d in days
    ]


def test_weekday_holiday_not_counted_as_expected() -> None:
    # Mo 22. bis Mi 31.12.2025; Do 25.12. (Weihnachten) fehlt.
    bars = _daily([22, 23, 24, 26, 29, 30, 31])  # 25. ausgelassen
    start = datetime(2025, 12, 22, tzinfo=UTC)
    end = datetime(2026, 1, 1, tzinfo=UTC)
    common = dict(
        instrument="EURUSD",
        timeframe="D1",
        start=start,
        end=end,
        session_predicate=WeekdaySession(),
    )

    ohne = assess_bars(bars, **common)  # type: ignore[arg-type]
    assert "gap_ratio_above_limit" in ohne.reasons  # 25.12. gilt als Luecke

    mit = assess_bars(bars, holidays=frozenset({date(2025, 12, 25)}), **common)  # type: ignore[arg-type]
    assert mit.gap_ratio == 0.0  # Feiertag nicht erwartet
    assert "gap_ratio_above_limit" not in mit.reasons


def test_holiday_bar_does_not_mask_a_real_gap() -> None:
    # Konservativ (S6): eine vorhandene Feiertagsbar darf eine echte Luecke auf einem
    # ERWARTETEN Slot nicht verdecken -- die Lueckenquote zaehlt nur erwartete Slots.
    bars = _daily([22, 23, 24, 25, 26, 29, 30])  # 25.12. (Feiertag) da, 31.12. FEHLT
    report = assess_bars(
        bars,
        instrument="EURUSD",
        timeframe="D1",
        start=datetime(2025, 12, 22, tzinfo=UTC),
        end=datetime(2026, 1, 1, tzinfo=UTC),
        session_predicate=WeekdaySession(),
        holidays=frozenset({date(2025, 12, 25)}),
    )
    # 7 erwartet (8 Wochentage - Feiertag), 6 auf erwarteten Slots (25. zaehlt nicht) ->
    # die fehlende 31. wird sichtbar, nicht von der Feiertagsbar kaschiert.
    assert "gap_ratio_above_limit" in report.reasons


# --- Intraday-Sonntagsbars sind kein Session-Fehler (S6) ------------------


def test_intraday_sunday_bars_not_outside_session() -> None:
    base = datetime(2025, 1, 5, 22, tzinfo=UTC)  # Sonntag 22:00
    bars = [
        BarRow(base + timedelta(hours=i), 1.10, 1.11, 1.09, 1.105, 100.0)
        for i in range(3)  # So 22:00, 23:00, Mo 00:00
    ]
    report = assess_bars(
        bars,
        instrument="EURUSD",
        timeframe="H1",
        start=base,
        end=base + timedelta(hours=3),
        session_predicate=FxSession(),
    )
    assert report.outside_session_bars == ()  # Sonntagabend ist Session
    assert "bars_outside_session" not in report.reasons


def test_weekday_session_would_flag_sunday_but_fx_does_not() -> None:
    # Gegenprobe: WeekdaySession markiert die Sonntagsbar, FxSession nicht.
    base = datetime(2025, 1, 5, 22, tzinfo=UTC)  # Sonntag
    bars = [BarRow(base, 1.10, 1.11, 1.09, 1.105, 100.0)]
    common = dict(
        instrument="EURUSD", timeframe="H1", start=base, end=base + timedelta(hours=1)
    )
    wd = assess_bars(bars, session_predicate=WeekdaySession(), **common)  # type: ignore[arg-type]
    fx = assess_bars(bars, session_predicate=FxSession(), **common)  # type: ignore[arg-type]
    assert base in wd.outside_session_bars  # WeekdaySession: Sonntag = draussen
    assert fx.outside_session_bars == ()  # FxSession: Sonntagabend = drin

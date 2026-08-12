"""Test des Bar-Laders: dekodiert Rohquellen, normalisiert, kettet ans Qualitaetstor.

Die Dukascopy-Bytes werden synthetisch erzeugt (kein echter Datenabruf, kein Netz), damit
der Test deterministisch ist. Der Lader bricht ab, wenn die Reihe das Tor nicht besteht;
die Pruefsumme ist reproduzierbar.
"""

from __future__ import annotations

import lzma
import struct
from datetime import UTC, datetime, time, timedelta

import pytest
from mt5_trading_ai.data.loader import (
    DataLoadError,
    WeekdaySession,
    assess_or_raise,
    bars_checksum,
    dataset_manifest,
    decode_dukascopy_candles,
    dukascopy_price_divisor,
    filter_to_weekdays,
    from_csv,
    manifest_checksum,
    parse_yahoo_daily,
    to_csv,
)
from mt5_trading_ai.data.quality import BarRow

_REC = struct.Struct(">IIIIIf")


def _dukascopy_bytes(records: list[tuple[int, int, int, int, int, float]]) -> bytes:
    payload = b"".join(_REC.pack(*r) for r in records)
    return lzma.compress(payload)


def _clean_weekday_bars(n: int = 10) -> list[BarRow]:
    """n aufeinanderfolgende Mo-Fr-Tagesbars, mitternachts UTC, gueltiges OHLC."""
    bars: list[BarRow] = []
    cursor = datetime(2023, 6, 5, tzinfo=UTC)  # Montag
    while len(bars) < n:
        if cursor.weekday() < 5:
            bars.append(
                BarRow(ts=cursor, open=1.10, high=1.11, low=1.09, close=1.105, volume=1000.0)
            )
        cursor += timedelta(days=1)
    return bars


# --- Dekodierung ----------------------------------------------------------


def test_decode_dukascopy_maps_ohlc_and_time() -> None:
    # Rohsatz-Reihenfolge ist open, CLOSE, LOW, HIGH.
    raw = _dukascopy_bytes([
        (0, 110000, 110050, 109900, 110100, 1000.0),
        (86400, 110050, 110200, 110000, 110300, 2000.0),
    ])
    start = datetime(2023, 1, 2, tzinfo=UTC)  # Montag
    bars = decode_dukascopy_candles(raw, period_start=start, price_divisor=100000.0)
    assert len(bars) == 2
    assert bars[0].ts == start
    assert bars[0].open == 1.10 and bars[0].close == 1.1005
    assert bars[0].high == 1.101 and bars[0].low == 1.099   # High/Low korrekt zugeordnet
    assert bars[1].ts == start + timedelta(days=1)


def test_decode_dukascopy_bad_length_is_error() -> None:
    with pytest.raises(DataLoadError):
        decode_dukascopy_candles(
            lzma.compress(b"\x00\x01\x02"),
            period_start=datetime(2023, 1, 1, tzinfo=UTC), price_divisor=100000.0,
        )


def test_decode_dukascopy_not_lzma_is_error() -> None:
    with pytest.raises(DataLoadError):
        decode_dukascopy_candles(
            b"kein lzma",
            period_start=datetime(2023, 1, 1, tzinfo=UTC), price_divisor=100000.0,
        )


def test_price_divisor_known_and_unknown() -> None:
    assert dukascopy_price_divisor("EURUSD") == 100000.0
    assert dukascopy_price_divisor("USDJPY") == 1000.0  # 3-stellig, nicht 100000
    with pytest.raises(DataLoadError):
        dukascopy_price_divisor("NICHTDA")


# --- Yahoo-Parsing --------------------------------------------------------


def test_parse_yahoo_rounds_to_midnight_and_skips_none() -> None:
    at_2300 = int(datetime(2023, 6, 1, 23, 0, tzinfo=UTC).timestamp())
    at_0000 = int(datetime(2023, 6, 5, 0, 0, tzinfo=UTC).timestamp())
    payload = {
        "chart": {"result": [{
            "timestamp": [at_2300, at_0000, at_0000 + 86400],
            "indicators": {"quote": [{
                "open": [1.07, 1.08, None],   # dritte Bar unvollstaendig -> uebersprungen
                "high": [1.075, 1.085, 1.0],
                "low": [1.065, 1.075, 1.0],
                "close": [1.07, 1.08, 1.0],
            }]},
        }]}
    }
    bars = parse_yahoo_daily(payload)
    assert len(bars) == 2
    assert all(b.ts.time() == time(0, 0) for b in bars)   # alle auf Mitternacht gerundet
    assert bars[0].ts == datetime(2023, 6, 2, tzinfo=UTC)  # 23:00 -> naechste Mitternacht
    assert bars[0].volume is None


def test_parse_yahoo_broken_payload_is_error() -> None:
    with pytest.raises(DataLoadError):
        parse_yahoo_daily({"chart": {"result": []}})


# --- Session-Normalisierung + Qualitaetstor -------------------------------


def test_filter_to_weekdays_drops_weekend() -> None:
    sat = BarRow(ts=datetime(2023, 6, 3, tzinfo=UTC), open=1.1, high=1.1, low=1.1, close=1.1, volume=0.0)
    bars = _clean_weekday_bars(3) + [sat]
    kept = filter_to_weekdays(bars)
    assert sat not in kept and len(kept) == 3


def test_assess_or_raise_passes_clean_series() -> None:
    report = assess_or_raise(
        _clean_weekday_bars(10), instrument="EURUSD", timeframe="D1",
        session_predicate=WeekdaySession(),
    )
    assert report.passed
    assert report.gap_ratio == 0.0


def test_assess_or_raise_fails_on_gap() -> None:
    # Negativ gefahren: eine Bar entfernen -> Luecke -> Tor rot.
    bars = _clean_weekday_bars(10)
    del bars[5]
    with pytest.raises(DataLoadError):
        assess_or_raise(bars, instrument="EURUSD", timeframe="D1", session_predicate=WeekdaySession())


def test_assess_or_raise_fails_on_weekend_bar() -> None:
    bars = _clean_weekday_bars(10)
    bars.append(BarRow(ts=datetime(2023, 6, 17, tzinfo=UTC), open=1.1, high=1.11, low=1.09, close=1.1, volume=1.0))
    with pytest.raises(DataLoadError):  # Samstag -> ausserhalb Session
        assess_or_raise(bars, instrument="EURUSD", timeframe="D1", session_predicate=WeekdaySession())


def test_assess_or_raise_empty_is_error() -> None:
    with pytest.raises(DataLoadError):
        assess_or_raise([], instrument="EURUSD", timeframe="D1", session_predicate=WeekdaySession())


# --- Reproduzierbare Ablage + Pruefsumme ----------------------------------


def test_csv_roundtrip_and_checksum_stable() -> None:
    bars = _clean_weekday_bars(10)
    text = to_csv(bars)
    back = from_csv(text)
    assert back == bars                       # verlustfreier Round-Trip
    assert bars_checksum(back) == bars_checksum(bars)


def test_checksum_changes_when_data_changes() -> None:
    a = _clean_weekday_bars(10)
    b = _clean_weekday_bars(10)
    b[0] = BarRow(ts=b[0].ts, open=1.2, high=1.21, low=1.19, close=1.2, volume=1000.0)
    assert bars_checksum(a) != bars_checksum(b)


def test_from_csv_bad_header_is_error() -> None:
    with pytest.raises(DataLoadError):
        from_csv("nicht,der,kopf\n1,2,3")


# --- Block-Ausfall (was die globale Lueckenquote durchlaesst) -------------


def test_block_outage_fails_even_under_1pct_gap() -> None:
    bars = _clean_weekday_bars(500)
    del bars[100:104]  # 4 aufeinanderfolgende Handelstage fehlen: 4/500 = 0.8 % < 1 %
    with pytest.raises(DataLoadError):  # globale Luecke gruen, aber Block-Ausfall ROT
        assess_or_raise(
            bars, instrument="EURUSD", timeframe="D1", session_predicate=WeekdaySession()
        )


def test_short_gap_within_run_limit_passes() -> None:
    bars = _clean_weekday_bars(500)
    del bars[100:103]  # 3 fehlend -> genau am Limit MAX_CONSECUTIVE_GAP, erlaubt
    report = assess_or_raise(
        bars, instrument="EURUSD", timeframe="D1", session_predicate=WeekdaySession()
    )
    assert report.passed


# --- Manifest bindet Herkunft, nicht nur die Zahlen -----------------------


def _manifest(divisor: float, bars: list[BarRow]) -> dict[str, object]:
    return dataset_manifest(
        instrument="EURUSD", timeframe="D1", source="dukascopy-bid-day",
        price_divisor=divisor, session="weekday-utc", bars=bars, quality_reasons=(),
    )


def test_manifest_checksum_binds_provenance_not_just_numbers() -> None:
    bars = _clean_weekday_bars(10)
    assert manifest_checksum(_manifest(100000.0, bars)) == manifest_checksum(
        _manifest(100000.0, bars)
    )
    # Gleiche Zahlen, anderer Divisor (fehl-dekodiert) -> gleiche bars_checksum,
    # aber ANDERE Manifest-Pruefsumme: Herkunft/Divisor sind mitgebunden.
    a, b = _manifest(100000.0, bars), _manifest(1000.0, bars)
    assert a["bars_checksum"] == b["bars_checksum"]
    assert manifest_checksum(a) != manifest_checksum(b)

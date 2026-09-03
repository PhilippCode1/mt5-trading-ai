"""Volatilitaetsrechnung und die fail-closed Messdatei.

Die Rechnung wird gegen von Hand nachvollziehbare Zahlen geprueft, nicht gegen sich
selbst. Die Datei wird mit **je einem** Defekt gefahren, damit belegt ist, welcher
Defekt welche Ausnahme ausloest -- ein Sammeltest wuerde verdecken, ob wirklich jede
Pruefung greift.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.costs.volatility import (
    ATR_PERIOD,
    STATUS_MEASURED,
    STATUS_NOT_MEASURED,
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

REPO = Path(__file__).resolve().parents[1]
ECHTE_DATEI = REPO / "config" / "atr_measurements.json"
T0 = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)


def _kerzen(
    werte: list[tuple[float, float, float]], *, stunden: int = 1
) -> list[Candle]:
    return [
        Candle(ts=T0 + timedelta(hours=i * stunden), high=h, low=lo, close=c)
        for i, (h, lo, c) in enumerate(werte)
    ]


# --- Perzentil ------------------------------------------------------------
def test_perzentil_trifft_die_bekannten_punkte() -> None:
    reihe = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(reihe, 0.0) == 1.0
    assert percentile(reihe, 0.5) == 3.0
    assert percentile(reihe, 1.0) == 5.0
    # Lineare Interpolation zwischen 2.0 und 3.0 bei Position 1,0? -> genau 2.0
    assert percentile(reihe, 0.25) == 2.0


def test_perzentil_interpoliert_linear() -> None:
    assert percentile([0.0, 10.0], 0.5) == 5.0
    assert percentile([0.0, 10.0], 0.25) == 2.5


def test_perzentil_ignoriert_die_eingabereihenfolge() -> None:
    assert percentile([5.0, 1.0, 3.0], 0.5) == percentile([1.0, 3.0, 5.0], 0.5)


def test_perzentil_auf_leerer_reihe_ist_ein_fehler() -> None:
    with pytest.raises(ValueError):
        percentile([], 0.5)


def test_perzentil_ausserhalb_null_bis_eins_ist_ein_fehler() -> None:
    with pytest.raises(ValueError):
        percentile([1.0], 1.5)


# --- True Range -----------------------------------------------------------
def test_true_range_nimmt_das_maximum_der_drei_spannen() -> None:
    # Kerze 1: H-L = 2; |H - C0| = |12 - 10| = 2; |L - C0| = |10 - 10| = 0 -> 2
    # Kerze 2: H-L = 1; |H - C1| = |14 - 11| = 3; |L - C1| = |13 - 11| = 2 -> 3 (Gap)
    kerzen = _kerzen([(11, 9, 10), (12, 10, 11), (14, 13, 13)])
    assert true_ranges(kerzen) == [2.0, 3.0]


def test_luecken_bereinigung_loest_die_verkettung() -> None:
    """Ueber eine Pause zaehlt nur die eigene Spanne -- der Sprung ist kein Handel."""
    kerzen = [
        Candle(ts=T0, high=11, low=9, close=10),
        Candle(ts=T0 + timedelta(hours=48), high=14, low=13, close=13),  # Wochenende
    ]
    assert true_ranges(kerzen) == [1.0]  # nur H - L
    assert true_ranges(kerzen, max_gap=None) == [4.0]  # |14 - 10|


def test_unbereinigte_reihe_ist_nie_kleiner_als_die_bereinigte() -> None:
    """Die Bereinigung kann den ATR nur senken -- und senken ist die sichere Richtung."""
    kerzen = [
        Candle(ts=T0, high=11, low=9, close=10),
        Candle(ts=T0 + timedelta(hours=1), high=12, low=10, close=11),
        Candle(ts=T0 + timedelta(hours=72), high=20, low=19, close=19),
    ]
    bereinigt = true_ranges(kerzen)
    roh = true_ranges(kerzen, max_gap=None)
    assert all(b <= r for b, r in zip(bereinigt, roh, strict=True))


def test_true_range_einer_einzelnen_kerze_ist_leer() -> None:
    assert true_ranges(_kerzen([(11, 9, 10)])) == []


def test_luecken_zaehler() -> None:
    kerzen = [
        Candle(ts=T0, high=1, low=1, close=1),
        Candle(ts=T0 + timedelta(hours=1), high=1, low=1, close=1),
        Candle(ts=T0 + timedelta(hours=48), high=1, low=1, close=1),
    ]
    assert gap_count(kerzen) == 1


# --- Wilder-ATR -----------------------------------------------------------
def test_wilder_startet_mit_dem_einfachen_mittel() -> None:
    ranges = [2.0] * ATR_PERIOD
    assert wilder_atr(ranges) == [2.0]


def test_wilder_glaettet_mit_eins_durch_periode() -> None:
    ranges = [2.0] * ATR_PERIOD + [16.0]
    reihe = wilder_atr(ranges)
    assert reihe[0] == 2.0
    # (2 * 13 + 16) / 14 = 42 / 14 = 3
    assert reihe[1] == pytest.approx(3.0)


def test_wilder_gibt_die_erwartete_laenge() -> None:
    ranges = [1.0] * 100
    assert len(wilder_atr(ranges)) == 100 - ATR_PERIOD + 1


def test_wilder_ohne_genug_daten_gibt_leer_statt_ersatzwert() -> None:
    assert wilder_atr([1.0] * (ATR_PERIOD - 1)) == []


def test_wilder_mit_nicht_positiver_periode_ist_ein_fehler() -> None:
    with pytest.raises(ValueError):
        wilder_atr([1.0], period=0)


# --- Umrechnung in Basispunkte -------------------------------------------
def test_bps_rechnet_je_bar_gegen_den_gleichzeitigen_schlusskurs() -> None:
    assert atr_series_bps([1.0, 2.0], [100.0, 200.0]) == [100.0, 100.0]


def test_bps_verlangt_gleiche_laenge() -> None:
    with pytest.raises(ValueError):
        atr_series_bps([1.0], [1.0, 2.0])


def test_bps_mit_nicht_positivem_kurs_ist_ein_fehler_kein_ueberspringen() -> None:
    with pytest.raises(ValueError):
        atr_series_bps([1.0], [0.0])


# --- „nicht gemessen" -----------------------------------------------------
def test_nicht_gemessen_traegt_keine_ersatzzahl() -> None:
    m = not_measured("BTCUSD", "Symbol nicht vorhanden")
    assert m.measured is False
    assert m.reason == "Symbol nicht vorhanden"
    assert m.atr_median_price is None
    assert m.atr_p25_bps is None
    assert m.price_median is None


# --- Messdatei: fail-closed ----------------------------------------------
def _gueltig() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "measurement_id": "atr-measurement-v1",
        "measured_on": "2026-08-17",
        "timeframe": "H1",
        "atr_period": ATR_PERIOD,
        "method": "Wilder",
        "terminal": {"server": "X-Demo", "is_demo": True},
        "instruments": {
            "EURUSD": {
                "status": STATUS_MEASURED,
                "reason": None,
                "bars": 6183,
                "window_start": "2025-08-16T00:00:00+00:00",
                "window_end": "2026-08-14T20:00:00+00:00",
                "atr_median_price": 0.00117,
                "atr_p25_price": 0.001,
                "atr_median_bps": 10.04,
                "atr_p25_bps": 8.64,
                "atr_median_price_roh": 0.00118,
                "price_median": 1.16,
                "spread_median_points": 2.0,
                "spread_p75_points": 3.0,
                "point": 1e-05,
                "digits": 5,
                "contract_size": 100000.0,
                "gap_bars": 54,
            }
        },
    }


def _schreibe(tmp_path: Path, roh: dict[str, Any]) -> Path:
    pfad = tmp_path / "atr_measurements.json"
    pfad.write_text(json.dumps(roh), encoding="utf-8")
    return pfad


def test_gueltige_datei_laedt(tmp_path: Path) -> None:
    messungen = load_atr_measurements(_schreibe(tmp_path, _gueltig()))
    assert set(messungen) == {"EURUSD"}
    assert messungen["EURUSD"].measured is True
    assert messungen["EURUSD"].bars == 6183


def test_fehlende_datei_ist_ein_fehler(tmp_path: Path) -> None:
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(tmp_path / "gibtsnicht.json")


def test_kaputtes_json_ist_ein_fehler(tmp_path: Path) -> None:
    pfad = tmp_path / "atr_measurements.json"
    pfad.write_text("{kein json", encoding="utf-8")
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(pfad)


@pytest.mark.parametrize(
    "feld",
    [
        "schema_version",
        "measurement_id",
        "measured_on",
        "timeframe",
        "atr_period",
        "method",
        "terminal",
        "instruments",
    ],
)
def test_jedes_pflichtfeld_einzeln(tmp_path: Path, feld: str) -> None:
    roh = _gueltig()
    del roh[feld]
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_fremde_atr_periode_ist_ein_fehler(tmp_path: Path) -> None:
    """Eine Datei mit ATR(20) darf nicht stillschweigend als ATR(14) gelesen werden."""
    roh = _gueltig()
    roh["atr_period"] = 20
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_leere_instrumentenliste_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"] = {}
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_unbekannter_status_faellt_nicht_auf_einen_default(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"]["EURUSD"]["status"] = "vielleicht"
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_gemessen_ohne_atr_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"]["EURUSD"]["atr_median_price"] = None
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_gemessen_mit_atr_null_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"]["EURUSD"]["atr_median_price"] = 0
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_nicht_gemessen_ohne_begruendung_ist_ein_fehler(tmp_path: Path) -> None:
    """Ein „nicht gemessen" ohne Grund ist eine Luecke, die spaeter jemand fuellt."""
    roh = _gueltig()
    roh["instruments"]["BTCUSD"] = {"status": STATUS_NOT_MEASURED, "reason": "  "}
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


def test_nicht_gemessen_mit_begruendung_laedt(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"]["BTCUSD"] = {
        "status": STATUS_NOT_MEASURED,
        "reason": "Symbol auf dem erreichbaren Terminal nicht vorhanden",
    }
    messungen = load_atr_measurements(_schreibe(tmp_path, roh))
    assert messungen["BTCUSD"].measured is False
    assert messungen["BTCUSD"].atr_median_price is None


def test_unlesbare_zahl_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["instruments"]["EURUSD"]["atr_median_price"] = "viel"
    with pytest.raises(AtrMeasurementError):
        load_atr_measurements(_schreibe(tmp_path, roh))


# --- gegen die echte Datei ------------------------------------------------
def test_die_echte_messdatei_ist_ladbar_und_traegt_begruendete_luecken() -> None:
    """Positivtest gegen die im Repo liegende Messung -- kein Fixture-Ersatz."""
    if not ECHTE_DATEI.is_file():
        pytest.skip("config/atr_measurements.json nicht vorhanden")
    messungen = load_atr_measurements(ECHTE_DATEI)
    assert messungen, "Messdatei ohne Instrumente"
    for messung in messungen.values():
        if messung.measured:
            assert messung.atr_median_price is not None
            assert messung.atr_median_price > 0
            assert messung.bars > ATR_PERIOD
            # Die Bereinigung darf den ATR nur senken, nie heben.
            if messung.atr_median_price_roh is not None:
                assert messung.atr_median_price <= messung.atr_median_price_roh
        else:
            assert messung.reason and messung.reason.strip()

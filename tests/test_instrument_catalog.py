"""Test des Instrumentenkatalogs: laedt und validiert, faellt bei Defekt laut aus.

Zusaetzlich der Anschluss an die Hebelpolitik: jede Anlageklasse im Katalog muss der
Hebelklammer bekannt sein, sonst faende sie keinen Deckel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mt5_trading_ai.risk.leverage import clamp_leverage
from mt5_trading_ai.venue.catalog import (
    CatalogEntry,
    InstrumentCatalogError,
    default_catalog_path,
    load_instrument_catalog,
)
from mt5_trading_ai.venue.protocol import AssetClass


def _valid_raw() -> dict[str, object]:
    return {
        "catalog_id": "test",
        "valid_from": "2026-08-11",
        "verified_on": "2026-08-11",
        "instruments": {
            "EURUSD": {
                "asset_class": "fx_major",
                "fees": {
                    "commission_per_lot_round_turn": "0",
                    "typical_spread_points": "6",
                    "swap_long_per_lot_per_night": "-2.1",
                    "swap_short_per_lot_per_night": "-0.9",
                    "triple_swap_weekday": 2,
                    "currency": "USD",
                },
                "sessions": [{"weekday": 0, "open_utc": "00:00", "close_utc": "21:00"}],
            }
        },
    }


def _write(tmp_path: Path, raw: object) -> Path:
    path = tmp_path / "instrument_catalog.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


# --- Laden der echten Datei ----------------------------------------------


def test_default_catalog_loads() -> None:
    catalog = load_instrument_catalog()
    assert "EURUSD" in catalog
    entry = catalog["EURUSD"]
    assert isinstance(entry, CatalogEntry)
    assert entry.asset_class is AssetClass.FX_MAJOR
    assert entry.fees.currency == "USD"
    assert entry.sessions  # nicht leer


def test_default_catalog_path_points_to_config() -> None:
    path = default_catalog_path()
    assert path.name == "instrument_catalog.json"
    assert path.is_file()


def test_catalog_classes_are_covered_by_leverage_policy() -> None:
    catalog = load_instrument_catalog()
    for symbol, entry in catalog.items():
        decision = clamp_leverage(requested=10, asset_class=entry.asset_class.value)
        assert decision.reason != "unknown_asset_class", symbol


def test_crypto_is_in_catalog_and_tradeable_at_cap() -> None:
    catalog = load_instrument_catalog()
    assert catalog["BTCUSD"].asset_class is AssetClass.CRYPTO
    # Kein Betriebsminimum mehr (E2): der ESMA-Deckel 2:1 ist handelbar.
    decision = clamp_leverage(requested=10, asset_class="crypto")
    assert not decision.no_trade
    assert decision.leverage == 2


# --- Fail-closed ----------------------------------------------------------


def test_missing_file_is_error(tmp_path: Path) -> None:
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(tmp_path / "does_not_exist.json")


def test_invalid_json_is_error(tmp_path: Path) -> None:
    path = tmp_path / "instrument_catalog.json"
    path.write_text("{ nicht json", encoding="utf-8")
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(path)


def test_missing_top_field_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["verified_on"]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_empty_instruments_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"] = {}
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_unknown_asset_class_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["asset_class"] = "perpetual"  # type: ignore[index]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_missing_fee_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["instruments"]["EURUSD"]["fees"]["typical_spread_points"]  # type: ignore[index]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_fees_without_currency_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["instruments"]["EURUSD"]["fees"]["currency"]  # type: ignore[index]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_empty_sessions_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["sessions"] = []  # type: ignore[index]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_malformed_session_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["sessions"] = [  # type: ignore[index]
        {"weekday": 0, "open_utc": "00:00"}
    ]
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))

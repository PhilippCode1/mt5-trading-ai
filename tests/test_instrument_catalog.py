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


# --- Belegdaten: Anwesenheit reicht nicht --------------------------------
#
# ``valid_from`` und ``verified_on`` wurden bis hierher nur auf Anwesenheit geprueft.
# Das Pruefdatum ist aber der einzige Beleg dafuer, wann die Zahlen darunter gegen den
# Broker gehalten wurden -- und ein Beleg, den niemand liest, ist keiner.


@pytest.mark.parametrize("field", ["valid_from", "verified_on"])
def test_belegdatum_ohne_datum_ist_ein_fehler(tmp_path: Path, field: str) -> None:
    """Der Fall, der bis hierher durchkam: ein Wort statt eines Tages."""
    raw = _valid_raw()
    raw[field] = "irgendwann"
    with pytest.raises(InstrumentCatalogError) as ex:
        load_instrument_catalog(_write(tmp_path, raw))
    assert field in str(ex.value)


@pytest.mark.parametrize("field", ["valid_from", "verified_on"])
def test_belegdatum_ohne_striche_ist_ein_fehler(tmp_path: Path, field: str) -> None:
    """``"20260812"`` muss fallen, obwohl ``date.fromisoformat`` es seit 3.11 nimmt.

    Genau daran haengt die Formpruefung und nicht nur ein ``try/except``: der
    Datenbestand fuehrt eine Schreibweise, und nur die eine laesst sich zwischen zwei
    Dateien vergleichen und sortieren.
    """
    raw = _valid_raw()
    raw[field] = "20260812"
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


@pytest.mark.parametrize("field", ["valid_from", "verified_on"])
def test_belegdatum_mit_unmoeglichem_tag_ist_ein_fehler(
    tmp_path: Path, field: str
) -> None:
    """Von Hand: 2026 ist kein Schaltjahr, der Februar hat 28 Tage. Einen 30. gibt es
    dort nicht -- die Form allein wuerde ihn durchlassen."""
    raw = _valid_raw()
    raw[field] = "2026-02-30"
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


@pytest.mark.parametrize("wert", [None, 20260812, ["2026-08-12"]])
def test_belegdatum_als_nichttext_ist_ein_fehler(tmp_path: Path, wert: object) -> None:
    """``null``, Zahl, Liste: keine davon ist ein Tag, und keine darf krachen statt
    abzulehnen."""
    raw = _valid_raw()
    raw["verified_on"] = wert
    with pytest.raises(InstrumentCatalogError):
        load_instrument_catalog(_write(tmp_path, raw))


def test_ein_gueltiges_belegdatum_laedt_weiterhin(tmp_path: Path) -> None:
    """Gegenprobe: die Pruefung ist keine Dauerbremse. ``_valid_raw`` traegt
    ``2026-08-11``, und die Datei laedt."""
    catalog = load_instrument_catalog(_write(tmp_path, _valid_raw()))
    assert "EURUSD" in catalog

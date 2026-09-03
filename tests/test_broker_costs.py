"""Broker-Kostentabelle: fail-closed geprueft, je Defekt ein eigener Fall.

Der teuerste Fehler dieser Datei waere kein fehlender Wert, sondern ein **falsch
umgerechneter**: ein Pip, das als Kurspunkt gelesen wird, verschiebt den Spread um
Faktor 10.000 und faellt in keiner Plausibilitaetspruefung auf, weil das Ergebnis
weiter wie eine Zahl aussieht. Darum steht die Umrechnung
``spread_price = spread_published x unit_in_price x Aufschlag`` hier unter einem
eigenen Test, und die echte Datei wird zusaetzlich gegen Groessenordnungen geprueft.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.costs.broker_costs import (
    SPREAD_AB_WERT,
    STATUS_BELEGT,
    STATUS_NICHT_GEFUEHRT,
    STATUS_OHNE_SPREAD,
    BrokerCostsError,
    load_broker_costs,
)

REPO = Path(__file__).resolve().parents[1]
ECHTE_DATEI = REPO / "config" / "broker_costs.json"


def _gueltig() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "costs_id": "test-costs",
        "costs_version": "2026-08-17",
        "valid_from": "2026-08-17",
        "verified_on": "2026-08-17",
        "slippage": {
            "note": "Annahme, keine Messung: halber Spread bei tiefem Buch.",
            "bps_per_instrument": {"EURUSD": "0.5"},
        },
        "brokers": {
            "test_broker": {
                "name": "Test Broker Ltd",
                "regulator": "CySEC 000/00",
                "account_type": "Raw MT5",
                "instruments": {
                    "EURUSD": {
                        "status": STATUS_BELEGT,
                        "broker_symbol": "EURUSD",
                        "quote_currency": "USD",
                        "spread_published": "0.06",
                        "spread_unit": "Pips",
                        "unit_in_price": "0.0001",
                        "spread_kind": "typisch",
                        "commission_round_turn": "7",
                        "commission_currency": "USD",
                        "contract_size": "100000",
                        "min_lot": "0.01",
                        "source_url": "https://example.invalid/spreads",
                        "retrieved_on": "2026-08-17",
                        "quote": "EURUSD AVG 0.06",
                    }
                },
            }
        },
    }


def _schreibe(tmp_path: Path, roh: dict[str, Any]) -> Path:
    pfad = tmp_path / "broker_costs.json"
    pfad.write_text(json.dumps(roh), encoding="utf-8")
    return pfad


def _eurusd(roh: dict[str, Any]) -> dict[str, Any]:
    instruments = roh["brokers"]["test_broker"]["instruments"]
    return instruments["EURUSD"]  # type: ignore[no-any-return]


# --- Die Umrechnung, um die es geht --------------------------------------
def test_spread_wird_aus_einheit_und_wert_gerechnet(tmp_path: Path) -> None:
    kosten = load_broker_costs(_schreibe(tmp_path, _gueltig()))
    zeile = kosten.brokers["test_broker"].instruments["EURUSD"]
    assert zeile.spread_price == Decimal("0.06") * Decimal("0.0001")
    assert zeile.spread_published == Decimal("0.06")
    assert zeile.unit_in_price == Decimal("0.0001")


def test_werbewert_wird_mit_dem_aufschlag_multipliziert(tmp_path: Path) -> None:
    roh = _gueltig()
    _eurusd(roh).update(spread_kind=SPREAD_AB_WERT, spread_markup_factor="2")
    kosten = load_broker_costs(_schreibe(tmp_path, roh))
    zeile = kosten.brokers["test_broker"].instruments["EURUSD"]
    assert zeile.spread_price == Decimal("0.06") * Decimal("0.0001") * 2


def test_werbewert_ohne_bezifferten_aufschlag_ist_ein_fehler(tmp_path: Path) -> None:
    """Ein stiller Aufschlag waere im Ergebnis nicht mehr zu erkennen."""
    roh = _gueltig()
    _eurusd(roh)["spread_kind"] = SPREAD_AB_WERT
    with pytest.raises(BrokerCostsError, match="Aufschlag"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_aufschlag_von_genau_eins_zaehlt_nicht_als_aufschlag(tmp_path: Path) -> None:
    roh = _gueltig()
    _eurusd(roh).update(spread_kind=SPREAD_AB_WERT, spread_markup_factor="1")
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_fehlende_einheit_ist_ein_fehler_keine_null(tmp_path: Path) -> None:
    roh = _gueltig()
    del _eurusd(roh)["unit_in_price"]
    with pytest.raises(BrokerCostsError, match="unit_in_price"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_nicht_positive_einheit_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    _eurusd(roh)["unit_in_price"] = "0"
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_fehlende_einheitenbezeichnung_ist_ein_fehler(tmp_path: Path) -> None:
    """Ohne die Einheit der Quelle laesst sich ``unit_in_price`` nicht nachpruefen."""
    roh = _gueltig()
    del _eurusd(roh)["spread_unit"]
    with pytest.raises(BrokerCostsError, match="spread_unit"):
        load_broker_costs(_schreibe(tmp_path, roh))


# --- Belegpflicht ---------------------------------------------------------
@pytest.mark.parametrize("feld", ["source_url", "retrieved_on", "quote_currency"])
def test_zeile_ohne_beleg_oder_waehrung_ist_unbrauchbar(
    tmp_path: Path, feld: str
) -> None:
    roh = _gueltig()
    del _eurusd(roh)[feld]
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_leere_quelle_zaehlt_nicht_als_quelle(tmp_path: Path) -> None:
    roh = _gueltig()
    _eurusd(roh)["source_url"] = "   "
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_kommission_ohne_waehrung_ist_nicht_umrechenbar(tmp_path: Path) -> None:
    roh = _gueltig()
    del _eurusd(roh)["commission_currency"]
    with pytest.raises(BrokerCostsError, match="commission_currency"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_kommission_null_ohne_waehrung_ist_zulaessig(tmp_path: Path) -> None:
    """Ein Nur-Spread-Konto hat keine Kommission -- und keine Waehrung dafuer."""
    roh = _gueltig()
    _eurusd(roh)["commission_round_turn"] = "0"
    del _eurusd(roh)["commission_currency"]
    kosten = load_broker_costs(_schreibe(tmp_path, roh))
    assert (
        kosten.brokers["test_broker"].instruments["EURUSD"].commission_round_turn == 0
    )


def test_fehlende_kommission_ist_ein_fehler_keine_null(tmp_path: Path) -> None:
    """Null muss ausdruecklich dastehen -- sonst ist ein Vergessen nicht von einem
    Nur-Spread-Konto zu unterscheiden."""
    roh = _gueltig()
    del _eurusd(roh)["commission_round_turn"]
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


# --- Die drei Zustaende ---------------------------------------------------
def test_nicht_gefuehrt_verlangt_eine_begruendung(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["brokers"]["test_broker"]["instruments"]["BTCUSD"] = {
        "status": STATUS_NICHT_GEFUEHRT
    }
    with pytest.raises(BrokerCostsError, match="Begruendung"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_nicht_gefuehrt_mit_begruendung_traegt_keine_zahlen(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["brokers"]["test_broker"]["instruments"]["BTCUSD"] = {
        "status": STATUS_NICHT_GEFUEHRT,
        "reason": "Kein Krypto-CFD fuer EU-Retail",
    }
    kosten = load_broker_costs(_schreibe(tmp_path, roh))
    zeile = kosten.brokers["test_broker"].instruments["BTCUSD"]
    assert zeile.available is False
    assert zeile.spread_price is None
    assert zeile.commission_round_turn is None


def test_spread_nicht_veroeffentlicht_ist_ein_eigener_zustand(tmp_path: Path) -> None:
    """Weder „gibt es nicht" noch „kostet nichts" -- beides waere falsch."""
    roh = _gueltig()
    roh["brokers"]["test_broker"]["instruments"]["NVDA"] = {
        "status": STATUS_OHNE_SPREAD,
        "reason": "Broker veroeffentlicht fuer Aktien-CFDs keine Spreadtabelle",
    }
    kosten = load_broker_costs(_schreibe(tmp_path, roh))
    zeile = kosten.brokers["test_broker"].instruments["NVDA"]
    assert zeile.status == STATUS_OHNE_SPREAD
    assert zeile.available is False
    assert zeile.spread_price is None


def test_unbekannter_status_faellt_nicht_auf_einen_default(tmp_path: Path) -> None:
    roh = _gueltig()
    _eurusd(roh)["status"] = "vielleicht"
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


# --- Kopfblock und Slippage ----------------------------------------------
@pytest.mark.parametrize(
    "feld",
    [
        "schema_version",
        "costs_id",
        "costs_version",
        "valid_from",
        "verified_on",
        "slippage",
        "brokers",
    ],
)
def test_jedes_kopf_pflichtfeld_einzeln(tmp_path: Path, feld: str) -> None:
    roh = _gueltig()
    del roh[feld]
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_slippage_ohne_begruendung_ist_unbrauchbar(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["slippage"]["note"] = "  "
    with pytest.raises(BrokerCostsError, match="Begruendung"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_negative_slippage_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["slippage"]["bps_per_instrument"]["EURUSD"] = "-1"
    with pytest.raises(BrokerCostsError):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_broker_ohne_aufsicht_ist_ein_fehler(tmp_path: Path) -> None:
    roh = _gueltig()
    roh["brokers"]["test_broker"]["regulator"] = ""
    with pytest.raises(BrokerCostsError, match="regulator"):
        load_broker_costs(_schreibe(tmp_path, roh))


def test_fehlende_datei_ist_ein_fehler(tmp_path: Path) -> None:
    with pytest.raises(BrokerCostsError):
        load_broker_costs(tmp_path / "gibtsnicht.json")


def test_kaputtes_json_ist_ein_fehler(tmp_path: Path) -> None:
    pfad = tmp_path / "broker_costs.json"
    pfad.write_text("{kein json", encoding="utf-8")
    with pytest.raises(BrokerCostsError):
        load_broker_costs(pfad)


# --- Gegen die echte Datei ------------------------------------------------
def test_die_echte_kostendatei_ist_ladbar() -> None:
    kosten = load_broker_costs(ECHTE_DATEI)
    assert len(kosten.brokers) >= 3, (
        f"Der Auftrag verlangt mindestens drei Broker, gefunden {len(kosten.brokers)}"
    )
    for broker in kosten.brokers.values():
        assert broker.regulator.strip()
        assert broker.instruments


def test_jede_belegte_zeile_der_echten_datei_traegt_quelle_und_datum() -> None:
    kosten = load_broker_costs(ECHTE_DATEI)
    zeilen = 0
    for broker in kosten.brokers.values():
        for zeile in broker.instruments.values():
            if not zeile.available:
                assert zeile.reason and zeile.reason.strip()
                continue
            zeilen += 1
            assert zeile.source_url and zeile.source_url.startswith("http")
            assert zeile.retrieved_on == "2026-08-17"
            assert zeile.quote and zeile.quote.strip()
    assert zeilen >= 12, f"nur {zeilen} belegte Kostenzeilen"


def test_spreads_der_echten_datei_liegen_in_plausibler_groessenordnung() -> None:
    """Der Faktor-10.000-Fehler faellt genau hier auf, nicht im Ergebnis.

    Ein Spread liegt bei liquiden Instrumenten zwischen 0,1 und 50 Basispunkten des
    Kurses. Alles darunter oder darueber ist ein Einheitenfehler, kein Angebot.
    """
    from mt5_trading_ai.costs.volatility import load_atr_measurements

    messungen = load_atr_measurements()
    kosten = load_broker_costs(ECHTE_DATEI)
    geprueft = 0
    for broker in kosten.brokers.values():
        for schluessel, zeile in broker.instruments.items():
            messung = messungen.get(schluessel)
            if not zeile.available or messung is None or not messung.measured:
                continue
            assert zeile.spread_price is not None
            preis = Decimal(str(messung.price_median))
            bps = zeile.spread_price / preis * Decimal("10000")
            geprueft += 1
            assert Decimal("0.01") < bps < Decimal("50"), (
                f"{broker.key}/{schluessel}: Spread {bps} bp -- das ist keine "
                f"Preisstellung, das ist ein Einheitenfehler "
                f"({zeile.spread_published} {zeile.spread_unit}, "
                f"unit_in_price={zeile.unit_in_price})"
            )
    assert geprueft >= 12, f"nur {geprueft} Zeilen plausibilitaetsgeprueft"

"""Zweigdeckung ``risk/leverage.py`` (A15): die fuenf Zweige, die die Suite nicht lief.

Gemessen vor diesen Tests (Beleg ``06-zweigdeckung-leverage-rot.txt``): 25 von 30
Zweigen, 83,3 %. Fehlend waren genau die ablehnenden Zweige des Laders -- also die,
wegen derer der Lader existiert -- und der Rueckfall der Pfadsuche:

* 106 -> 111  ``default_policy_path``: kein ``config/<Datei>`` aufwaerts -> Paketkopie
* 136 -> 137  ``load_policy``: Pflichtfeld fehlt
* 152 -> 153  ``load_policy``: ``classes`` fehlt, leer oder kein Objekt
* 155 -> 156  ``load_policy``: Anlageklasse ohne ``max_leverage`` oder kein Objekt
* 158 -> 159  ``load_policy``: ``max_leverage`` < 1

Jeder Test prueft die Aussage des Zweigs (Fehlertyp und Fehlertext), nicht nur seine
Beruehrung: fiele der Zweig weg, liefe der Lader in einen anderen Fehler (KeyError,
anderer Text) oder in einen Default -- und der Test wuerde rot. Belegt durch Mutation
in einer Kopie (Beleg ``06-zweigdeckung-leverage-rot.txt``). Alles unter ``tmp_path``;
die echte Deckel-Datei wird nur gelesen.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.risk import leverage
from mt5_trading_ai.risk.leverage import (
    DEFAULT_LEVERAGE,
    POLICY_FILENAME,
    SYSTEM_MAX_LEVERAGE,
    AssetClassCap,
    LeverageDecision,
    LeveragePolicyError,
    clamp_leverage,
    default_policy_path,
    load_policy,
)

PFLICHTFELDER = ("policy_id", "policy_version", "valid_from", "verified_on", "classes")


def _gueltig() -> dict[str, Any]:
    """Kleinste gueltige Deckel-Datei: alle Pflichtfelder, eine Klasse."""
    return {
        "policy_id": "zweig-test",
        "policy_version": "2026-09-04",
        "valid_from": "2026-09-04",
        "verified_on": "2026-09-04",
        "jurisdiction": "Testgebiet",
        "system_max_leverage": SYSTEM_MAX_LEVERAGE,
        "classes": {"fx_major": {"max_leverage": 30, "label": "Haupt-Waehrungspaare"}},
    }


def _schreibe(tmp_path: Path, raw: object) -> Path:
    pfad = tmp_path / "asset_class_leverage.json"
    pfad.write_text(json.dumps(raw), encoding="utf-8")
    return pfad


# --- Bezugspunkt: das Geruest selbst laedt ------------------------------------


def test_das_geruest_laedt_mit_einer_klasse(tmp_path: Path) -> None:
    """Ohne diesen Test bewiese ein roter Ladefehler unten nur ein kaputtes Geruest."""
    policy = load_policy(_schreibe(tmp_path, _gueltig()))
    assert policy.policy_id == "zweig-test"
    assert policy.policy_version == "2026-09-04"
    assert policy.jurisdiction == "Testgebiet"
    assert policy.cap_for("fx_major") == AssetClassCap(
        asset_class="fx_major", max_leverage=30, label="Haupt-Waehrungspaare"
    )
    assert policy.cap_for("crypto") is None  # nur eine Klasse geladen, kein Default


# --- Zweig 106 -> 111: Pfadsuche ohne Treffer ---------------------------------


def test_pfadsuche_ohne_treffer_faellt_auf_die_paketkopie_zurueck_und_laedt_keinen_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kein ``config/<Datei>`` aufwaerts -> ``<Paket>/risk/data/<Datei>``; fehlt auch die, Fehler."""
    modul = Path(leverage.__file__).resolve()

    # Bezugspunkt (Zweig 108 -> 109): mit dem echten Namen trifft die Suche die Repo-Datei.
    echt = default_policy_path()
    assert echt.name == POLICY_FILENAME
    assert echt.parent.name == "config"
    assert echt.is_file()

    # Ein Name, den kein ``config/``-Ordner aufwaerts traegt -> die Schleife laeuft leer.
    monkeypatch.setattr(leverage, "POLICY_FILENAME", "zweig-nicht-vorhanden.json")
    rueckfall = default_policy_path()
    assert rueckfall == modul.parent / "data" / "zweig-nicht-vorhanden.json"
    assert not rueckfall.exists()

    # Der Rueckfall ist ein Pfad, kein Default: ohne Datei dort ist Laden ein Fehler.
    with pytest.raises(LeveragePolicyError, match="Hebeldeckel-Datei fehlt"):
        load_policy()


# --- Zweig 136 -> 137: Pflichtfeld fehlt --------------------------------------


@pytest.mark.parametrize("feld", PFLICHTFELDER)
def test_fehlendes_pflichtfeld_ist_ein_benannter_ladefehler(
    tmp_path: Path, feld: str
) -> None:
    """Der Fehler nennt das Feld -- nicht KeyError, nicht 'ohne Anlageklassen'."""
    raw = _gueltig()
    del raw[feld]
    with pytest.raises(LeveragePolicyError, match=f"ohne Pflichtfeld '{feld}'"):
        load_policy(_schreibe(tmp_path, raw))


# --- Zweig 152 -> 153: classes fehlt, leer oder kein Objekt -------------------


@pytest.mark.parametrize(
    "classes",
    [{}, [], "fx_major", None],
    ids=["leeres-objekt", "liste", "zeichenkette", "null"],
)
def test_classes_leer_oder_kein_objekt_ist_ladefehler(
    tmp_path: Path, classes: object
) -> None:
    """Beide Haelften der Bedingung: kein dict (Liste, Text, null) und leeres dict."""
    raw = _gueltig()
    raw["classes"] = classes
    with pytest.raises(LeveragePolicyError, match="ohne Anlageklassen"):
        load_policy(_schreibe(tmp_path, raw))


# --- Zweig 155 -> 156: Anlageklasse ohne max_leverage -------------------------


@pytest.mark.parametrize(
    "eintrag",
    [30, {"label": "ohne Deckel"}, None, [30]],
    ids=["zahl-statt-objekt", "objekt-ohne-deckel", "null", "liste"],
)
def test_anlageklasse_ohne_max_leverage_ist_ladefehler(
    tmp_path: Path, eintrag: object
) -> None:
    """Ein nackter Wert oder ein Objekt ohne Deckel ist kein Deckel -- kein Default."""
    raw = _gueltig()
    raw["classes"] = {"fx_major": eintrag}
    with pytest.raises(LeveragePolicyError, match="'fx_major' ohne max_leverage"):
        load_policy(_schreibe(tmp_path, raw))


# --- Zweig 158 -> 159: max_leverage < 1 ---------------------------------------


@pytest.mark.parametrize("wert", [0, -1, -30])
def test_max_leverage_unter_eins_ist_ladefehler(tmp_path: Path, wert: int) -> None:
    """0 oder negativ ist kein Deckel: kein Hebel 0, keine Sperre durch die Hintertuer."""
    raw = _gueltig()
    raw["classes"]["fx_major"]["max_leverage"] = wert
    with pytest.raises(LeveragePolicyError, match="'fx_major' mit max_leverage < 1"):
        load_policy(_schreibe(tmp_path, raw))


def test_max_leverage_eins_ist_die_untere_grenze_und_klammert(tmp_path: Path) -> None:
    """Gegenstueck: 1 laedt und bindet -- ein Wunsch 10 wird auf 1 geklammert."""
    raw = _gueltig()
    raw["classes"]["fx_major"]["max_leverage"] = 1
    policy = load_policy(_schreibe(tmp_path, raw))
    entscheidung = clamp_leverage(requested=10, asset_class="fx_major", policy=policy)
    assert not entscheidung.no_trade
    assert entscheidung.leverage == 1
    assert entscheidung.class_cap == 1
    assert entscheidung.binding == "class_cap"


# --- Zeilen ohne Zweig, die die Suite nicht lief (252-253, 81) ----------------


def test_unlesbarer_wunsch_faellt_auf_den_default_nicht_auf_das_maximum(
    tmp_path: Path,
) -> None:
    """``_as_int``: ein Text ohne Zahl ist ``None`` -> DEFAULT_LEVERAGE, nie SYSTEM_MAX."""
    policy = load_policy(_schreibe(tmp_path, _gueltig()))
    for wunsch in ("abc", "10x", object(), [10]):
        entscheidung = clamp_leverage(
            requested=wunsch, asset_class="fx_major", policy=policy
        )
        assert entscheidung.requested == DEFAULT_LEVERAGE, wunsch
        assert entscheidung.leverage == DEFAULT_LEVERAGE, wunsch
        assert entscheidung.leverage < SYSTEM_MAX_LEVERAGE


def test_as_dict_traegt_jedes_feld_der_entscheidung(tmp_path: Path) -> None:
    policy = load_policy(_schreibe(tmp_path, _gueltig()))
    entscheidung = clamp_leverage(requested=50, asset_class="fx_major", policy=policy)
    abbild = entscheidung.as_dict()
    assert set(abbild) == set(LeverageDecision.__dataclass_fields__)
    assert abbild["leverage"] == SYSTEM_MAX_LEVERAGE
    assert abbild["requested"] == 50
    assert abbild["class_cap"] == 30
    assert abbild["binding"] == "system_cap"
    assert abbild["reason"] is None
    assert abbild["policy_version"] == "2026-09-04"

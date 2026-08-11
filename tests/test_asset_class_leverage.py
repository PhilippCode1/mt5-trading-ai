"""Hebelklammer: ein Test je Anlageklasse, plus die Faelle, die keine Klasse sind.

Teil 4 Punkt II: effektiver Hebel = min(strategie, 10, klassendeckel);
unbekannte Klasse -> no_trade; Hebel ueber 10 ist nicht konfigurierbar.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mt5_trading_ai.risk.leverage import (
    DEFAULT_LEVERAGE,
    SYSTEM_MAX_LEVERAGE,
    SYSTEM_MIN_LEVERAGE,
    LeveragePolicyError,
    clamp_leverage,
    get_policy,
    load_policy,
)

# (Anlageklasse, gesetzlicher Deckel, erwarteter Hebel bei Wunsch 10, bei Wunsch 50)
CLASSES = [
    ("fx_major", 30, 10, 10),
    ("fx_minor", 20, 10, 10),
    ("gold", 20, 10, 10),
    ("index_major", 20, 10, 10),
    ("index_minor", 10, 10, 10),
    ("commodity_non_gold", 10, 10, 10),
    ("equity", 5, 5, 5),
    ("crypto", 2, None, None),
]


@pytest.mark.parametrize("asset_class,legal_cap,at_ten,at_fifty", CLASSES)
def test_class_cap_is_enforced(
    asset_class: str, legal_cap: int, at_ten, at_fifty
) -> None:
    policy = get_policy()
    cap = policy.cap_for(asset_class)
    assert cap is not None, f"Anlageklasse {asset_class} fehlt in der Deckel-Datei"
    assert cap.max_leverage == legal_cap

    assert clamp_leverage(requested=10, asset_class=asset_class).leverage == at_ten
    assert clamp_leverage(requested=50, asset_class=asset_class).leverage == at_fifty


@pytest.mark.parametrize("asset_class,legal_cap,_a,_b", CLASSES)
def test_no_class_can_exceed_system_cap(
    asset_class: str, legal_cap: int, _a, _b
) -> None:
    """Kein Wunsch, egal wie hoch, kommt ueber 10 hinaus."""
    for requested in (11, 20, 75, 500, 10**9):
        decision = clamp_leverage(requested=requested, asset_class=asset_class)
        assert decision.leverage is None or decision.leverage <= SYSTEM_MAX_LEVERAGE


def test_crypto_is_not_tradeable() -> None:
    """2:1 liegt unter dem Betriebsminimum. Kein Handel, kein Default."""
    decision = clamp_leverage(requested=5, asset_class="crypto")
    assert decision.no_trade
    assert decision.reason == "class_cap_below_system_minimum"


def test_unknown_class_is_no_trade_not_default() -> None:
    for value in (None, "", "unbekannt", "FX", "perpetual"):
        decision = clamp_leverage(requested=10, asset_class=value)
        assert decision.no_trade, f"{value!r} haette no_trade liefern muessen"
        assert decision.reason == "unknown_asset_class"


def test_missing_request_falls_back_to_minimum_not_maximum() -> None:
    """Ein vergessener Parameter darf nie den gefaehrlichsten Wert waehlen."""
    decision = clamp_leverage(requested=None, asset_class="fx_major")
    assert decision.leverage == DEFAULT_LEVERAGE == SYSTEM_MIN_LEVERAGE


def test_request_below_minimum_is_no_trade() -> None:
    decision = clamp_leverage(requested=3, asset_class="fx_major")
    assert decision.no_trade
    assert decision.reason == "requested_below_system_minimum"


def test_policy_file_cannot_raise_the_system_cap(tmp_path: Path) -> None:
    """Die Datei kann senken, nie heben. Ein Versuch ist ein Ladefehler."""
    source = json.loads(Path(get_policy().source_path).read_text(encoding="utf-8"))
    source["system_max_leverage"] = 75
    bad = tmp_path / "asset_class_leverage.json"
    bad.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(LeveragePolicyError):
        load_policy(bad)


def test_policy_file_has_source_and_dates() -> None:
    """Ein Deckel ohne Herkunft und Gueltigkeitsdatum ist eine Behauptung."""
    policy = get_policy()
    assert policy.policy_version
    assert policy.valid_from
    assert policy.verified_on
    raw = json.loads(Path(policy.source_path).read_text(encoding="utf-8"))
    assert raw["sources"], "Deckel-Datei ohne Quellenangabe"
    for entry in raw["sources"]:
        assert entry.get("url") and entry.get("date")


def test_broken_policy_file_is_an_error_not_a_default(tmp_path: Path) -> None:
    broken = tmp_path / "asset_class_leverage.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(LeveragePolicyError):
        load_policy(broken)

    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(LeveragePolicyError):
        load_policy(missing)

"""Sperrtest: ohne vollstaendige Freigabe kein eroeffnender Order-Submit.

Der Test wird einmal absichtlich negativ gefahren (Ausgabe in archiv/PROGRESS.md), damit
belegt ist, dass er bei defekter Sperre rot wird und nicht nur bei korrektem Code
gruen ist.
"""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import pytest
from mt5_trading_ai.execution.release import (
    RELEASE_ID_FIELD,
    REQUIRED_SWITCHES,
    evaluate_live_release,
    live_release_blocks_opening_order,
)

ALL_SWITCHES = [attribute for attribute, _ in REQUIRED_SWITCHES]


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {attribute: False for attribute in ALL_SWITCHES}
    values[RELEASE_ID_FIELD[0]] = ""
    values.update(overrides)
    return SimpleNamespace(**values)


def _fully_released() -> SimpleNamespace:
    values: dict[str, object] = {attribute: True for attribute in ALL_SWITCHES}
    values[RELEASE_ID_FIELD[0]] = "2026-08-06/eurusd-baseline/v1"
    return SimpleNamespace(**values)


def test_default_configuration_blocks() -> None:
    decision = evaluate_live_release(_settings())
    assert decision.allowed is False
    assert decision.reason == "live_release_incomplete"
    for _, env_alias in REQUIRED_SWITCHES:
        assert env_alias in decision.missing
    assert RELEASE_ID_FIELD[1] in decision.missing


def test_every_proper_subset_of_switches_still_blocks() -> None:
    """Kein Teilsatz genuegt. Nur alle Schalter zusammen oeffnen den Weg."""
    for count in range(len(ALL_SWITCHES)):
        for combination in itertools.combinations(ALL_SWITCHES, count):
            overrides: dict[str, object] = {name: True for name in combination}
            overrides[RELEASE_ID_FIELD[0]] = "irgendeine-kennung"
            decision = evaluate_live_release(_settings(**overrides))
            assert decision.allowed is False, f"Teilsatz {combination} hat geoeffnet"


def test_all_switches_without_release_id_still_blocks() -> None:
    overrides: dict[str, object] = {name: True for name in ALL_SWITCHES}
    for empty in ("", "   ", None):
        overrides[RELEASE_ID_FIELD[0]] = empty
        assert evaluate_live_release(_settings(**overrides)).allowed is False


def test_missing_attribute_counts_as_not_met() -> None:
    """Nicht bewertbar gilt als nicht erfuellt — ein Tippfehler macht strenger, nicht loser."""
    settings = _fully_released()
    delattr(settings, ALL_SWITCHES[0])
    decision = evaluate_live_release(settings)
    assert decision.allowed is False
    assert REQUIRED_SWITCHES[0][1] in decision.missing


@pytest.mark.parametrize("truthy", [1, "true", "yes", "1", [1], object()])
def test_truthy_is_not_true(truthy: object) -> None:
    """Nur ein echtes ``True`` zaehlt. Kein 'irgendwie wahr'."""
    overrides: dict[str, object] = {name: True for name in ALL_SWITCHES}
    overrides[ALL_SWITCHES[0]] = truthy
    overrides[RELEASE_ID_FIELD[0]] = "kennung"
    assert evaluate_live_release(_settings(**overrides)).allowed is False


def test_complete_release_allows() -> None:
    decision = evaluate_live_release(_fully_released())
    assert decision.allowed is True
    assert decision.missing == ()


def test_opening_order_is_blocked_without_release() -> None:
    blocked = live_release_blocks_opening_order(_settings(), reduce_only=False)
    assert blocked is not None
    assert blocked.allowed is False


def test_reduce_only_passes_without_release() -> None:
    """Eine Sperre, die das Schliessen verhindert, erhoeht das Risiko."""
    assert live_release_blocks_opening_order(_settings(), reduce_only=True) is None


def test_opening_order_passes_with_complete_release() -> None:
    assert (
        live_release_blocks_opening_order(_fully_released(), reduce_only=False) is None
    )

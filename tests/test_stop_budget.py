"""Stop-Budget je Klasse: hergeleitet, nicht uebertragen."""

from __future__ import annotations

from decimal import Decimal

import pytest
from mt5_trading_ai.risk.stop_budget import (
    ASSUMED_ROUND_TURN_COST_BPS,
    assumed_cost_bps,
    breakeven_hit_rate,
    cost_floor_bps,
    margin_ceiling_bps,
    stop_budget,
)


def test_cost_floor_follows_the_breakeven_formula() -> None:
    """R = C / (2 * drag). Bei 5 Prozentpunkten Aufschlag also R = 10 * C."""
    assert cost_floor_bps(Decimal("0.65")) == Decimal("6.5")
    assert cost_floor_bps(Decimal("20")) == Decimal("200")
    assert cost_floor_bps(Decimal("1"), max_cost_drag=Decimal("0.10")) == Decimal("5")


def test_cost_floor_and_breakeven_are_consistent() -> None:
    for cost in (Decimal("0.65"), Decimal("7"), Decimal("20")):
        floor = cost_floor_bps(cost)
        assert breakeven_hit_rate(cost_bps=cost, stop_bps=floor) == Decimal("0.55")


def test_margin_ceiling_halves_when_leverage_doubles() -> None:
    at_five = margin_ceiling_bps(5)
    at_ten = margin_ceiling_bps(10)
    assert at_five == pytest.approx(Decimal("10000") * Decimal("0.5") / Decimal("15"))
    assert at_ten * 2 == pytest.approx(at_five)


def test_leverage_only_moves_the_upper_bound() -> None:
    """Der wesentliche Unterschied zur alten Kurve."""
    five = stop_budget(asset_class="fx_major", leverage=5)
    ten = stop_budget(asset_class="fx_major", leverage=10)
    assert five.lower_bps == ten.lower_bps
    assert five.upper_bps > ten.upper_bps


def test_fx_major_is_the_only_class_with_a_tight_lower_bound() -> None:
    fx = stop_budget(asset_class="fx_major", leverage=5)
    assert fx.tradeable
    assert fx.lower_bps < Decimal("10")
    for other in ("fx_minor", "index_minor", "commodity_non_gold", "equity", "crypto"):
        assert stop_budget(asset_class=other, leverage=5).lower_bps > Decimal("10")


def test_equity_is_not_tradeable_at_ten() -> None:
    assert stop_budget(asset_class="equity", leverage=5).tradeable is True
    ten = stop_budget(asset_class="equity", leverage=10)
    assert ten.tradeable is False
    assert ten.reason == "cost_floor_above_margin_ceiling"


def test_crypto_is_not_tradeable_at_any_allowed_leverage() -> None:
    for leverage in range(5, 11):
        assert stop_budget(asset_class="crypto", leverage=leverage).tradeable is False


def test_unknown_class_is_no_trade() -> None:
    result = stop_budget(asset_class="unbekannt", leverage=5)
    assert result.tradeable is False
    assert result.reason == "unknown_asset_class"


def test_measured_cost_beats_the_assumption() -> None:
    assumed = stop_budget(asset_class="fx_major", leverage=5)
    measured = stop_budget(
        asset_class="fx_major", leverage=5, measured_cost_bps=Decimal("2.0")
    )
    assert assumed.cost_is_measured is False
    assert measured.cost_is_measured is True
    assert measured.lower_bps == Decimal("20")


def test_allows_checks_both_bounds() -> None:
    budget = stop_budget(asset_class="fx_major", leverage=5)
    assert budget.allows(budget.lower_bps) is True
    assert budget.allows(budget.upper_bps) is True
    assert budget.allows(budget.lower_bps - Decimal("0.01")) is False
    assert budget.allows(budget.upper_bps + Decimal("0.01")) is False


def test_untradeable_budget_allows_nothing() -> None:
    budget = stop_budget(asset_class="crypto", leverage=5)
    for candidate in (Decimal("1"), Decimal("100"), Decimal("1000")):
        assert budget.allows(candidate) is False


def test_breakeven_is_independent_of_leverage() -> None:
    """Die Trefferquote am Nulldurchgang kennt keinen Hebel."""
    assert breakeven_hit_rate(
        cost_bps=Decimal("0.65"), stop_bps=Decimal("10")
    ) == pytest.approx(Decimal("0.5325"))


def test_assumed_cost_bps_is_the_one_lookup() -> None:
    """Die Schluesselregel (gestutzt, klein) steht an einer Stelle, nicht an zweien.

    ``execution/risk_manager.py`` braucht die Annahme als Praemisse gegen eine am
    Auftrag mitgereiste Zahl. Griffe es selbst in die Tabelle, laege die
    Normalisierung zweimal im Haus -- und eine Klasse waere je nach Aufrufer bekannt
    oder unbekannt.
    """
    assert assumed_cost_bps("fx_major") == ASSUMED_ROUND_TURN_COST_BPS["fx_major"]
    assert assumed_cost_bps("  FX_Major ") == ASSUMED_ROUND_TURN_COST_BPS["fx_major"]
    assert assumed_cost_bps("unbekannt") is None
    # Dieselbe Regel wie im Budget selbst: gleicher Schluessel, gleiches Urteil.
    assert stop_budget(asset_class="  FX_Major ", leverage=5).asset_class == "fx_major"
    assert stop_budget(asset_class="unbekannt", leverage=5).tradeable is False


def test_every_assumed_cost_is_documented_as_an_assumption() -> None:
    """Annahmen duerfen nicht als Messung durchgehen."""
    for asset_class in ASSUMED_ROUND_TURN_COST_BPS:
        assert (
            stop_budget(asset_class=asset_class, leverage=5).cost_is_measured is False
        )


def test_bad_inputs_raise() -> None:
    with pytest.raises(ValueError):
        cost_floor_bps(Decimal("1"), max_cost_drag=Decimal("0"))
    with pytest.raises(ValueError):
        margin_ceiling_bps(0)
    with pytest.raises(ValueError):
        breakeven_hit_rate(cost_bps=Decimal("1"), stop_bps=Decimal("0"))

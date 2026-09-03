"""Risiko je Trade, Stop-Floor und Positionsgroesse."""

from __future__ import annotations

from decimal import Decimal

import pytest
from mt5_trading_ai.risk.sizing import (
    DEFAULT_RISK_FRACTION,
    MAX_RISK_FRACTION,
    MIN_RISK_FRACTION,
    RiskSizingError,
    StopFloorInputs,
    executable_stop_floor,
    normalise_risk_fraction,
    size_position,
)

PRICE = Decimal("1.0850")
CONTRACT = Decimal("100000")


def _size(**overrides: object):
    kwargs: dict[str, object] = {
        "account_equity": Decimal("10000"),
        "risk_fraction": None,
        "stop_floor_bps": Decimal("2.64"),
        "stop_budget_bps": Decimal("20"),
        "requested_stop_bps": Decimal("10"),
        "price": PRICE,
        "contract_size": CONTRACT,
        "volume_min": Decimal("0.01"),
        "volume_step": Decimal("0.01"),
        "volume_max": Decimal("50"),
        "leverage": 5,
    }
    kwargs.update(overrides)
    return size_position(**kwargs)  # type: ignore[arg-type]


# --- Risikoanteil ----------------------------------------------------------


def test_missing_risk_fraction_uses_the_lower_bound() -> None:
    assert normalise_risk_fraction(None) == DEFAULT_RISK_FRACTION == MIN_RISK_FRACTION
    assert normalise_risk_fraction("") == MIN_RISK_FRACTION


def test_risk_fraction_is_clamped_both_ways() -> None:
    assert normalise_risk_fraction("0.02") == MAX_RISK_FRACTION
    assert normalise_risk_fraction("0.0001") == MIN_RISK_FRACTION
    assert normalise_risk_fraction("0.004") == Decimal("0.004")


def test_nonsensical_risk_fraction_raises() -> None:
    for bad in ("0", "-0.01"):
        with pytest.raises(RiskSizingError):
            normalise_risk_fraction(bad)
    with pytest.raises(RiskSizingError):
        normalise_risk_fraction("keine zahl")


# --- Stop-Floor ------------------------------------------------------------


def test_broker_stop_level_can_dominate_the_floor() -> None:
    """Der Mindestabstand des Brokers ist haeufig der bindende Wert."""
    floor = executable_stop_floor(
        StopFloorInputs(
            spread_bps=Decimal("0.1"),
            tick_size_bps=Decimal("0.05"),
            volatility_bps=Decimal("1"),
            broker_stop_level_bps=Decimal("25"),
            depth_ratio=0.9,
        )
    )
    assert floor.binding == "broker_stop_level"
    assert floor.executable_floor_bps == Decimal("25")


def test_unknown_depth_is_not_sufficient_depth() -> None:
    floor = executable_stop_floor(
        StopFloorInputs(
            spread_bps=Decimal("0.1"),
            tick_size_bps=Decimal("0.05"),
            volatility_bps=Decimal("1"),
            broker_stop_level_bps=Decimal("0"),
            depth_ratio=None,
        )
    )
    assert floor.binding == "depth"
    assert floor.executable_floor_bps == Decimal("15")


def test_floor_is_the_maximum_not_the_sum() -> None:
    floor = executable_stop_floor(
        StopFloorInputs(
            spread_bps=Decimal("2"),
            tick_size_bps=Decimal("1"),
            volatility_bps=Decimal("10"),
            broker_stop_level_bps=Decimal("3"),
            depth_ratio=0.9,
        )
    )
    assert floor.executable_floor_bps == max(floor.components.values())


# --- Positionsgroesse ------------------------------------------------------


def test_actual_risk_never_exceeds_the_budget() -> None:
    result = _size()
    assert result.volume is not None
    actual = (
        result.volume * CONTRACT * PRICE * result.stop_distance_bps / Decimal("10000")
    )
    assert actual <= result.risk_currency


def test_size_shrinks_when_the_stop_widens() -> None:
    tight = _size(requested_stop_bps=Decimal("5"))
    wide = _size(requested_stop_bps=Decimal("15"))
    assert tight.volume is not None and wide.volume is not None
    assert tight.volume > wide.volume


def test_floor_above_budget_is_no_trade_not_a_wider_stop() -> None:
    result = _size(stop_floor_bps=Decimal("30"), stop_budget_bps=Decimal("20"))
    assert result.no_trade
    assert "stop_floor_exceeds_budget" in result.reasons


def test_requested_stop_above_budget_is_no_trade() -> None:
    result = _size(requested_stop_bps=Decimal("25"), stop_budget_bps=Decimal("20"))
    assert result.no_trade
    assert "requested_stop_exceeds_budget" in result.reasons


def test_floor_wins_over_a_tighter_request() -> None:
    result = _size(stop_floor_bps=Decimal("12"), requested_stop_bps=Decimal("4"))
    assert result.stop_distance_bps == Decimal("12")


def test_no_leverage_is_no_trade() -> None:
    result = _size(leverage=None)
    assert result.no_trade
    assert "leverage_no_trade" in result.reasons


def test_volume_below_minimum_is_no_trade_not_rounded_up() -> None:
    """Aufrunden wuerde das Risikobudget ueberschreiten."""
    result = _size(account_equity=Decimal("100"))
    assert result.no_trade
    assert "below_volume_min" in result.reasons


def test_volume_is_rounded_down_to_the_step() -> None:
    result = _size(volume_step=Decimal("0.1"))
    assert result.volume is not None
    assert result.volume % Decimal("0.1") == 0


def test_volume_max_binds() -> None:
    result = _size(account_equity=Decimal("10000000"), volume_max=Decimal("1"))
    assert result.volume == Decimal("1")
    assert "volume_max_binding" in result.reasons


def test_margin_follows_from_leverage_only() -> None:
    at_five = _size(leverage=5)
    at_ten = _size(leverage=10)
    assert at_five.volume == at_ten.volume, "der Hebel aendert die Groesse nicht"
    assert at_five.risk_currency == at_ten.risk_currency, (
        "der Hebel aendert das Risiko nicht"
    )
    assert at_five.margin_required is not None and at_ten.margin_required is not None
    assert at_ten.margin_required < at_five.margin_required


def test_missing_inputs_are_no_trade() -> None:
    for override in (
        {"account_equity": Decimal("0")},
        {"price": Decimal("0")},
        {"contract_size": Decimal("0")},
    ):
        assert _size(**override).no_trade


def test_zero_step_raises_instead_of_guessing() -> None:
    with pytest.raises(RiskSizingError):
        _size(volume_step=Decimal("0"))

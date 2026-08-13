"""Test des Halal-Pfads: swapfreie Finanzierung + Screen (S4). Negativ gefahren."""

from __future__ import annotations

from decimal import Decimal

import pytest
from mt5_trading_ai.costs.halal import HalalFinancingPolicy, halal_financing
from mt5_trading_ai.costs.model import order_roundturn_cost
from mt5_trading_ai.venue.halal import screen_halal
from mt5_trading_ai.venue.protocol import AssetClass, FeeSchedule, OrderSide


def _fees(swap_long: str, swap_short: str) -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal(swap_long),
        swap_short_per_lot_per_night=Decimal(swap_short),
        triple_swap_weekday=2,
        currency="USD",
    )


def _order(side: OrderSide, **kw: object) -> object:
    return order_roundturn_cost(
        fees=_fees("-8.24", "1.51"), contract_size=Decimal("100000"),
        pip_size=Decimal("0.0001"), bid=Decimal("1.10"), ask=Decimal("1.1001"),
        side=side, volume=Decimal("1"), quote_currency="USD", holding_nights=3,
        **kw,  # type: ignore[arg-type]
    )


# --- swapfreie Finanzierung -----------------------------------------------


def test_halal_financing_never_credits() -> None:
    pol = HalalFinancingPolicy(grace_nights=0, admin_fee_per_lot_per_night=Decimal("5"))
    assert halal_financing(pol, Decimal("1"), 3) == Decimal("15")
    assert halal_financing(pol, Decimal("1"), 0) == Decimal("0")


def test_halal_financing_grace() -> None:
    pol = HalalFinancingPolicy(grace_nights=2, admin_fee_per_lot_per_night=Decimal("5"))
    assert halal_financing(pol, Decimal("1"), 2) == Decimal("0")    # in Karenz
    assert halal_financing(pol, Decimal("1"), 5) == Decimal("15")   # 3 berechnete Naechte


def test_halal_policy_rejects_negative_fee() -> None:
    with pytest.raises(ValueError):
        HalalFinancingPolicy(admin_fee_per_lot_per_night=Decimal("-1"))  # waere riba


def test_halal_policy_rejects_negative_grace() -> None:
    with pytest.raises(ValueError):
        HalalFinancingPolicy(grace_nights=-1)


def test_halal_financing_rejects_negative_nights() -> None:
    with pytest.raises(ValueError):
        halal_financing(HalalFinancingPolicy(), Decimal("1"), -1)


# --- Integration: kein Carry mehr fuer Short unter Halal ------------------


def test_conventional_short_earns_riba_carry() -> None:
    # Positiver Short-Swap -> financing < 0 (Gutschrift = riba). Das ist der Konflikt.
    breakdown = _order(OrderSide.SELL)
    assert breakdown.financing < 0  # type: ignore[attr-defined]


def test_halal_short_never_earns_carry() -> None:
    # Swapfrei: financing >= 0, egal welche Seite. Keine riba-Gutschrift.
    breakdown = _order(
        OrderSide.SELL,
        financing_policy=HalalFinancingPolicy(admin_fee_per_lot_per_night=Decimal("5")),
    )
    assert breakdown.financing >= 0  # type: ignore[attr-defined]


# --- Screen ---------------------------------------------------------------


def test_screen_conformant_swap_free_fx() -> None:
    v = screen_halal(
        asset_class=AssetClass.FX_MAJOR, account_swap_free=True,
        interest_bearing_margin=False,
    )
    assert v.mechanically_conformant
    assert v.requires_scholar_review  # IMMER


def test_screen_blocks_non_swap_free() -> None:
    v = screen_halal(
        asset_class=AssetClass.FX_MAJOR, account_swap_free=False,
        interest_bearing_margin=False,
    )
    assert not v.mechanically_conformant
    assert "konto_nicht_swapfrei_overnight_zins_riba" in v.reasons


def test_screen_blocks_interest_margin() -> None:
    v = screen_halal(
        asset_class=AssetClass.FX_MAJOR, account_swap_free=True,
        interest_bearing_margin=True,
    )
    assert not v.mechanically_conformant
    assert "verzinsliche_margin_riba" in v.reasons


def test_screen_equity_needs_business_check() -> None:
    v = screen_halal(
        asset_class=AssetClass.EQUITY, account_swap_free=True,
        interest_bearing_margin=False,
    )
    assert not v.mechanically_conformant
    assert "aktien_cfd_geschaeftsfeld_screening_noetig" in v.reasons


def test_screen_always_requires_scholar_review() -> None:
    # Selbst voll mechanisch konform bleibt die Grundfrage (gharar) offen.
    v = screen_halal(
        asset_class=AssetClass.FX_MAJOR, account_swap_free=True,
        interest_bearing_margin=False,
    )
    assert v.requires_scholar_review

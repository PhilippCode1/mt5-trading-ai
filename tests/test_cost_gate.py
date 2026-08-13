"""Tests fuer das Pre-Trade-Kostentor (``execution/cost_gate.py``).

Die reine ``evaluate_cost_gate`` deckt die fail-closed-Pfade ab, die die
Venue-Integration (``test_mt5_venue.py``) nicht sieht: Waehrungsdifferenz ohne
Umrechnungskurs, verschraenkte Notierung, negative Schwelle.
"""

from __future__ import annotations

from decimal import Decimal

from mt5_trading_ai.execution.cost_gate import CostGate, evaluate_cost_gate
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderSide,
)


def _fees(currency: str = "USD") -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency=currency,
    )


def _instrument(quote_currency: str | None = "USD") -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="mt5",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency=quote_currency,
        stop_level_points=10,
        freeze_level_points=0,
        fees=_fees(),
        sessions=(),
    )


def _evaluate(gate: CostGate, **overrides: object) -> object:
    base: dict[str, object] = {
        "gate": gate,
        "instrument": _instrument(),
        "fees": _fees(),
        "side": OrderSide.BUY,
        "volume": Decimal("0.10"),
        "bid": Decimal("1.09990"),
        "ask": Decimal("1.10000"),
    }
    base.update(overrides)
    return evaluate_cost_gate(**base)  # type: ignore[arg-type]


def test_within_threshold_is_approved() -> None:
    # Reale Roundturn-Reibung ~24,5 bp; Schwelle 50 bp -> zugelassen.
    decision = _evaluate(CostGate(max_roundturn_cost_fraction=Decimal("0.0005")))
    assert decision.approved is True
    assert decision.reason is None
    assert decision.cost_fraction is not None
    assert Decimal("0.0002") < decision.cost_fraction < Decimal("0.0003")


def test_fraction_matches_hand_calculation() -> None:
    # §9-Lektion: die GROESSE pinnen, nicht nur approved. Handrechnung (EURUSD, USD-Konto):
    # spread = (1.10000-1.09990)*100000*0.10 = 1.00; commission = 7*0.10 = 0.70;
    # slippage = 0.5 pip * 0.0001 * 100000 * 0.10 * 2 Seiten = 1.00 -> friction = 2.70 USD.
    # notional = 100000*0.10*1.10000 = 11000 USD (gleiche Waehrung!). fraction = 2.70/11000.
    decision = _evaluate(CostGate(max_roundturn_cost_fraction=Decimal("1")))
    assert decision.cost_fraction == Decimal("2.7") / Decimal("11000")


def test_exceeds_threshold_is_rejected() -> None:
    decision = _evaluate(CostGate(max_roundturn_cost_fraction=Decimal("0.0001")))
    assert decision.approved is False
    assert decision.reason == "cost_gate"
    assert decision.cost_fraction is not None
    assert decision.cost_fraction > Decimal("0.0001")


def test_cross_currency_is_fail_closed() -> None:
    # Kreuznotiert (JPY-Quote, USD-Konto): das Tor kann die Kostenquote nicht in EINER
    # Waehrung bilden -> fail-closed statt mit einem Skalar-Kurs falsch zu rechnen (§9).
    decision = _evaluate(
        CostGate(max_roundturn_cost_fraction=Decimal("0.01")),
        instrument=_instrument(quote_currency="JPY"),
    )
    assert decision.approved is False
    assert decision.reason == "cost_unverifiable"
    assert decision.detail is not None


def test_unknown_quote_currency_is_fail_closed() -> None:
    # Broker meldet currency_profit leer -> quote_currency=None. KEINE stille Annahme
    # "= Kontowaehrung": ein real kreuznotiertes Paar wuerde sonst als gleich notiert
    # (rate=1) durchgelassen -> Waehrungs-Mischung. Darum fail-closed (§9-Fix-Re-Check).
    decision = _evaluate(
        CostGate(max_roundturn_cost_fraction=Decimal("0.01")),
        instrument=_instrument(quote_currency=None),
    )
    assert decision.approved is False
    assert decision.reason == "cost_unverifiable"
    assert decision.detail is not None


def test_crossed_quote_is_fail_closed() -> None:
    # Ask unter Bid (verschraenkt) -> das Kostenmodell wirft, das Tor lehnt ab.
    decision = _evaluate(
        CostGate(max_roundturn_cost_fraction=Decimal("0.01")),
        bid=Decimal("1.10000"),
        ask=Decimal("1.09990"),
    )
    assert decision.approved is False
    assert decision.reason == "cost_unverifiable"


def test_negative_threshold_is_fail_closed() -> None:
    decision = _evaluate(CostGate(max_roundturn_cost_fraction=Decimal("-0.001")))
    assert decision.approved is False
    assert decision.reason == "invalid_threshold"

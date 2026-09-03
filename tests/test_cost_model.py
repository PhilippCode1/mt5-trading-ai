"""Test des Kostenmodells: rechnet real, faellt bei fehlenden/unbrauchbaren Kosten laut aus.

Die Bestandteile (Spread aus echtem Bid/Ask, Kommission, Slippage in Pips, Finanzierung
inkl. Dreifach-Tag) sind von Hand nachgerechnet. Die Fail-closed-Faelle decken Ladefehler
(Datei fehlt/kaputt, Pflichtfeld fehlt, unbekannte Klasse/Symbol), Eingabefehler (negatives
Volumen, verschraenkte Notierung, Nullpreis, negative Kommission, nicht-endliche Werte),
den Waehrungs-Mismatch (Notierung != Konto ohne Kurs) und Datensanitaet (FX ohne Kommission,
Aktien-CFD) ab.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.costs.model import (
    DEFAULT_SLIPPAGE_PIPS_PER_SIDE,
    CostBreakdown,
    CostModelError,
    load_cost_fees,
    order_roundturn_cost,
)
from mt5_trading_ai.venue.protocol import FeeSchedule, OrderSide

from test_instrument_catalog import _valid_raw, _write


def _fees(
    commission: str = "7", swap_long: str = "-8", swap_short: str = "1"
) -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal(commission),
        typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal(swap_long),
        swap_short_per_lot_per_night=Decimal(swap_short),
        triple_swap_weekday=2,
        currency="USD",
    )


def _cost(**over: object) -> CostBreakdown:
    base: dict[str, object] = {
        "fees": _fees(),
        "contract_size": Decimal("100000"),
        "pip_size": Decimal("0.0001"),
        "bid": Decimal("1.10000"),
        "ask": Decimal("1.10001"),  # Spread 0.1 Pip
        "side": OrderSide.BUY,
        "volume": Decimal("1"),
        "quote_currency": "USD",
    }
    base.update(over)
    return order_roundturn_cost(**base)  # type: ignore[arg-type]


def _fx_raw(commission: str = "7") -> dict[str, object]:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["fees"]["commission_per_lot_round_turn"] = commission  # type: ignore[index]
    return raw


# --- Positive Rechnung, von Hand nachgerechnet ---------------------------


def test_roundturn_cost_components() -> None:
    c = _cost()
    assert c.spread == Decimal("1")  # 0.00001 * 100000 * 1
    assert c.commission == Decimal("7")
    assert c.slippage == Decimal("10")  # 0.5 Pip * 0.0001 * 100000 * 1 * 2 Seiten
    assert c.financing == Decimal("0")  # 0 Naechte
    assert c.total == Decimal("18")
    assert c.currency == "USD"


def test_financing_counts_nights_and_triple() -> None:
    assert _cost(holding_nights=1).financing == Decimal("8")  # -(-8 * 1 * 1)
    assert _cost(holding_nights=3).financing == Decimal("24")  # -(-8 * 1 * 3)
    # Dreifach-Nacht zaehlt dreifach: Einheiten = 3 + 2*1 = 5 -> 40
    assert _cost(holding_nights=3, triple_swap_nights=1).financing == Decimal("40")


def test_short_uses_short_swap_as_credit() -> None:
    c = _cost(side=OrderSide.SELL, holding_nights=1)
    assert c.financing == Decimal("-1")  # -(+1 * 1 * 1) = Gutschrift


def test_spread_comes_from_live_quote_not_typical() -> None:
    wide = _cost(bid=Decimal("1.10000"), ask=Decimal("1.10010"))  # 1.0 Pip
    assert wide.spread == Decimal("10")  # zehnfacher Spread -> zehnfache Spreadkosten


def test_default_slippage_is_conservative_nonzero() -> None:
    assert DEFAULT_SLIPPAGE_PIPS_PER_SIDE > 0
    assert _cost(slippage_pips_per_side=Decimal("0")).slippage == Decimal("0")


# --- Waehrung: keine stille Annahme --------------------------------------


def test_mismatched_currency_without_rate_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(quote_currency="GBP")  # fees.currency = USD, kein Kurs


def test_mismatched_currency_with_rate_scales_quote_costs() -> None:
    c = _cost(quote_currency="GBP", quote_to_account_rate=Decimal("1.25"))
    assert c.spread == Decimal("1.25")  # 1 GBP * 1.25 -> USD
    assert c.slippage == Decimal("12.5")  # 10 GBP * 1.25 -> USD
    assert c.commission == Decimal("7")  # Kommission ist bereits Kontowaehrung


def test_same_currency_ignores_supplied_rate() -> None:
    # §9-Haertung: bei gleicher Waehrung ist der Umrechnungskurs definitionsgemaess 1.
    # Ein (sinnloser) uebergebener Kurs darf die Kosten NICHT skalieren -- sonst
    # verfaelschte ein Konto-Skalar still jedes gleich notierte Paar (Fail-open).
    plain = _cost(quote_currency="USD")
    with_bad_rate = _cost(quote_currency="USD", quote_to_account_rate=Decimal("0.0065"))
    assert with_bad_rate.spread == plain.spread
    assert with_bad_rate.slippage == plain.slippage
    assert with_bad_rate.total == plain.total


# --- Fail-closed ----------------------------------------------------------


def test_negative_volume_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(volume=Decimal("-1"))


def test_crossed_quote_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(bid=Decimal("1.10001"), ask=Decimal("1.10000"))


def test_zero_price_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(bid=Decimal("0"))


def test_infinite_price_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(ask=Decimal("Infinity"))


def test_nan_price_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(bid=Decimal("NaN"))


def test_negative_commission_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(fees=_fees(commission="-1"))


def test_triple_exceeds_holding_is_error() -> None:
    with pytest.raises(CostModelError):
        _cost(holding_nights=1, triple_swap_nights=2)


def test_missing_cost_file_is_error(tmp_path: Path) -> None:
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(tmp_path / "nope.json"))


def test_broken_cost_file_is_error(tmp_path: Path) -> None:
    path = tmp_path / "instrument_catalog.json"
    path.write_text("{ kaputt", encoding="utf-8")
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(path))


def test_unknown_symbol_is_error(tmp_path: Path) -> None:
    path = _write(tmp_path, _fx_raw())
    with pytest.raises(CostModelError):
        load_cost_fees("NICHTDA", catalog_path=str(path))


def test_missing_commission_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["instruments"]["EURUSD"]["fees"]["commission_per_lot_round_turn"]  # type: ignore[index]
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, raw)))


def test_missing_currency_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["instruments"]["EURUSD"]["fees"]["currency"]  # type: ignore[index]
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, raw)))


def test_missing_financing_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    del raw["instruments"]["EURUSD"]["fees"]["swap_long_per_lot_per_night"]  # type: ignore[index]
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, raw)))


def test_unknown_class_is_error(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["asset_class"] = "perpetual"  # type: ignore[index]
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, raw)))


def test_fx_zero_commission_is_error(tmp_path: Path) -> None:
    # _valid_raw fuehrt EURUSD (fx_major) mit Kommission 0 -- fuer FX eine Datenluecke.
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, _valid_raw())))


def test_equity_is_rejected(tmp_path: Path) -> None:
    raw = _valid_raw()
    raw["instruments"]["EURUSD"]["asset_class"] = "equity"  # type: ignore[index]
    with pytest.raises(CostModelError):
        load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, raw)))


def test_load_cost_fees_returns_schedule(tmp_path: Path) -> None:
    fees = load_cost_fees("EURUSD", catalog_path=str(_write(tmp_path, _fx_raw("7"))))
    assert fees.currency == "USD"
    assert fees.commission_per_lot_round_turn == Decimal("7")

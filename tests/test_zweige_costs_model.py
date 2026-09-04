"""Zweigdeckung ``costs/model.py`` (A15): die vier Zweige, die die Suite nicht lief.

Gemessen vor diesen Tests (Beleg ``06-zweigdeckung-model-rot.txt``): 20 von 24 Zweigen,
83,3 %. Fehlend waren drei ablehnende Zweige und der Weg ueber einen uebergebenen
Katalog:

* 92 -> 93    ``_require_finite``: NaN oder Infinity in Slippage, Kommission, Swap
* 146 -> 147  ``order_roundturn_cost``: negative Slippage
* 148 -> 149  ``order_roundturn_cost``: negative Naechte
* 203 -> 208  ``load_cost_fees``: Katalog uebergeben -> keine Datei gelesen

Jeder Test prueft die Aussage des Zweigs (Fehlertyp und -text bzw. dass keine Datei
angefasst wird), nicht nur seine Beruehrung: fiele der Zweig weg, ginge NaN als Kosten
durch, wuerde negative Slippage zur Gutschrift, negative Naechte kehrten das Vorzeichen
der Finanzierung um, und ein fehlender Katalogpfad wuerde trotz uebergebenem Katalog
zum Ladefehler. Belegt durch Mutation in einer Kopie (Beleg
``06-zweigdeckung-model-rot.txt``). Nichts ausserhalb ``tmp_path``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.costs.model import (
    CostBreakdown,
    CostModelError,
    load_cost_fees,
    order_roundturn_cost,
)
from mt5_trading_ai.venue.catalog import CatalogEntry
from mt5_trading_ai.venue.protocol import AssetClass, FeeSchedule, OrderSide


def _gebuehren(
    kommission: str = "7", swap_long: str = "-8", swap_short: str = "1"
) -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal(kommission),
        typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal(swap_long),
        swap_short_per_lot_per_night=Decimal(swap_short),
        triple_swap_weekday=2,
        currency="USD",
    )


def _kosten(**ueberschreibung: object) -> CostBreakdown:
    """EURUSD, 1 Lot, Spread 0,1 Pip, USD-Konto: Spread 1, Kommission 7, Slippage 10."""
    basis: dict[str, object] = {
        "fees": _gebuehren(),
        "contract_size": Decimal("100000"),
        "pip_size": Decimal("0.0001"),
        "bid": Decimal("1.10000"),
        "ask": Decimal("1.10001"),
        "side": OrderSide.BUY,
        "volume": Decimal("1"),
        "quote_currency": "USD",
    }
    basis.update(ueberschreibung)
    return order_roundturn_cost(**basis)  # type: ignore[arg-type]


def _eintrag(klasse: AssetClass, kommission: str) -> CatalogEntry:
    return CatalogEntry(asset_class=klasse, fees=_gebuehren(kommission), sessions=())


# --- Bezugspunkt: das Geruest rechnet ------------------------------------------


def test_das_geruest_rechnet_die_bekannten_kosten() -> None:
    """Ohne diesen Test bewiese ein roter Fehlerfall unten nur ein kaputtes Geruest."""
    k = _kosten(holding_nights=1)
    assert (k.spread, k.commission, k.slippage, k.financing) == (
        Decimal("1"),
        Decimal("7"),
        Decimal("10"),
        Decimal("8"),
    )
    assert k.total == Decimal("26")


# --- Zweig 92 -> 93: nicht-endlicher Wert --------------------------------------


@pytest.mark.parametrize(
    ("ueberschreibung", "feld"),
    [
        ({"slippage_pips_per_side": Decimal("NaN")}, "slippage_pips_per_side"),
        ({"slippage_pips_per_side": Decimal("Infinity")}, "slippage_pips_per_side"),
        ({"fees": _gebuehren(kommission="NaN")}, "commission"),
        ({"fees": _gebuehren(kommission="Infinity")}, "commission"),
        ({"fees": _gebuehren(swap_long="NaN"), "side": OrderSide.BUY}, "swap"),
        ({"fees": _gebuehren(swap_short="-Infinity"), "side": OrderSide.SELL}, "swap"),
    ],
    ids=[
        "slippage-nan",
        "slippage-inf",
        "kommission-nan",
        "kommission-inf",
        "swap-long-nan",
        "swap-short-neg-inf",
    ],
)
def test_nicht_endlicher_wert_ist_ein_fehler_der_das_feld_nennt(
    ueberschreibung: dict[str, object], feld: str
) -> None:
    """NaN/Infinity ist nie eine Zahl: CostModelError, kein InvalidOperation, kein NaN-Total."""
    with pytest.raises(CostModelError, match=f"{feld} muss endlich sein"):
        _kosten(**ueberschreibung)


# --- Zweig 146 -> 147: negative Slippage ---------------------------------------


@pytest.mark.parametrize("wert", ["-0.0001", "-0.5", "-1"])
def test_negative_slippage_ist_ein_fehler(wert: str) -> None:
    """Negative Slippage waere eine Gutschrift je Fill -- optimistisch, also gesperrt."""
    with pytest.raises(CostModelError, match="Slippage darf nicht negativ sein"):
        _kosten(slippage_pips_per_side=Decimal(wert))


def test_slippage_null_ist_die_untere_grenze() -> None:
    """Gegenstueck: 0 laeuft durch und kostet 0 -- der Fehler beginnt unter 0."""
    assert _kosten(slippage_pips_per_side=Decimal("0")).slippage == Decimal("0")


# --- Zweig 148 -> 149: negative Naechte ----------------------------------------


@pytest.mark.parametrize(
    "naechte",
    [
        {"holding_nights": -1},
        {"holding_nights": 0, "triple_swap_nights": -1},
        {"holding_nights": -2, "triple_swap_nights": -1},
    ],
    ids=["naechte-negativ", "dreifach-negativ", "beide-negativ"],
)
def test_negative_naechte_sind_ein_fehler(naechte: dict[str, int]) -> None:
    """Negative Naechte kehrten das Vorzeichen der Finanzierung um (Kosten -> Gutschrift)."""
    with pytest.raises(CostModelError, match="Naechte duerfen nicht negativ sein"):
        _kosten(**naechte)


def test_null_naechte_sind_die_untere_grenze() -> None:
    """Gegenstueck: 0 Naechte laufen durch und finanzieren 0."""
    assert _kosten(holding_nights=0, triple_swap_nights=0).financing == Decimal("0")


# --- Zweig 203 -> 208: Katalog uebergeben -> keine Datei ----------------------


def test_uebergebener_katalog_wird_genutzt_und_kein_pfad_gelesen(
    tmp_path: Path,
) -> None:
    """Mit Katalog zaehlt der Katalog; der Pfad wird nicht einmal angefasst."""
    katalog = {"EURUSD": _eintrag(AssetClass.FX_MAJOR, "7")}
    nicht_da = tmp_path / "nicht-vorhanden.json"

    fees = load_cost_fees("EURUSD", catalog=katalog, catalog_path=str(nicht_da))
    assert fees == _gebuehren("7")
    assert not nicht_da.exists()

    # Gegenstueck (Zweig 203 -> 204): ohne Katalog wird der Pfad gelesen -- und fehlt
    # er, ist das ein benannter Fehler, keine Nullkosten.
    with pytest.raises(CostModelError, match="Kostendaten nicht ladbar"):
        load_cost_fees("EURUSD", catalog_path=str(nicht_da))


def test_uebergebener_katalog_prueft_symbol_klasse_und_kommission() -> None:
    """Die Datensanitaet gilt fuer einen uebergebenen Katalog wie fuer die Datei."""
    katalog = {
        "EURUSD": _eintrag(AssetClass.FX_MAJOR, "0"),
        "AAPL": _eintrag(AssetClass.EQUITY, "0"),
        "US500": _eintrag(AssetClass.INDEX_MAJOR, "0"),
    }
    with pytest.raises(CostModelError, match="Unbekanntes Symbol ohne Kostendaten"):
        load_cost_fees("NICHTDA", catalog=katalog)
    with pytest.raises(CostModelError, match="ad valorem"):
        load_cost_fees("AAPL", catalog=katalog)
    with pytest.raises(
        CostModelError, match="fx_major mit Kommission 0 -- Datenluecke"
    ):
        load_cost_fees("EURUSD", catalog=katalog)
    # Ein Index traegt keine Kommission je Lot: 0 ist dort kein Datenloch.
    assert load_cost_fees("US500", catalog=katalog).commission_per_lot_round_turn == 0

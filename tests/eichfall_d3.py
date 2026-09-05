"""Eichfaelle D3 (Bewertung 3.3): Positionsgroesse und Marge in Kontowaehrung.

ROT gegen 306bbaa (belege/06-d3-rot.txt): ``size_position`` kannte keine Waehrung --
fuer EURGBP auf einem USD-Konto lag der Verlust am Stop 26 % ueber dem Budget
(0,39 Lot, 63,15 USD statt 50 USD); ``evaluate_leverage_preflight`` rechnete die
Marge fuer USDJPY mit 30.000 statt 200 USD (Hebelklammer 5). GRUEN gegen HEAD (belege/06-d3-gruen.txt).

Die Klasse, nicht der Fall: Betraege tragen ihre Waehrung (``risk/waehrung.py``),
die Groesse verlangt Kontowaehrung, Notierungswaehrung und Kurs, ein fehlender Kurs
sperrt (``fx_unverifiable``), die Marge entsteht in der Margenwaehrung des Instruments
und wird mit gemessenem Kurs in die Kontowaehrung gebracht (dritter Margenfall).

WARUM DIE HILFEN DEN ALTEN STAND TRAGEN (Gegenlese T10, E1/E23)
---------------------------------------------------------------
Der erste rote Beleg war ein Sammelfehler: ``risk/waehrung.py`` und die neuen
Parameter gab es bei 306bbaa nicht, und ein Import, der nicht laedt, misst nichts.
Darum laden die Hilfen unten das Alte tolerant: fehlt ein Parameter, rufen sie ohne
ihn -- und die Zusicherung nennt dann die FALSCHE ZAHL des alten Standes (0,39 Lot,
63,15 USD; 30.000 USD Marge), nicht einen ImportError. Am HEAD laufen dieselben
Zusicherungen gegen die richtigen Zahlen. Ein Eichfall ist erst dann einer, wenn seine
rote Haelfte den Befund zeigt und nicht die Kommandozeile.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.leverage_preflight import (  # noqa: E402
    evaluate_leverage_preflight,
)
from mt5_trading_ai.risk.sizing import size_position  # noqa: E402

try:
    from mt5_trading_ai.risk.waehrung import (  # noqa: E402
        Betrag,
        WaehrungsFehler,
        kurs_aus_ticks,
    )
except ImportError:  # 306bbaa: Betraege ohne Waehrung -- der Befund selbst
    Betrag = WaehrungsFehler = kurs_aus_ticks = None  # type: ignore[assignment,misc]
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

TS = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
GBPUSD = Decimal("1.27")
_T = TypeVar("_T")


def _ohne_unbekannte(funktion: Callable[..., _T], **kwargs: Any) -> _T:
    """Ruft ``funktion``; kennt sie ein Schluesselwort nicht (306bbaa), faellt es weg.

    So misst der rote Lauf die Zahl des alten Standes statt eines TypeError. Am HEAD
    kennt die Funktion alle Woerter, und die Hilfe ist ein gewoehnlicher Aufruf.
    """
    while True:
        try:
            return funktion(**kwargs)
        except TypeError as fehler:
            text = str(fehler)
            unbekannt = [k for k in kwargs if f"'{k}'" in text and "unexpected" in text]
            if not unbekannt:
                raise
            for k in unbekannt:
                del kwargs[k]


def _groesse(**overrides: object):  # type: ignore[no-untyped-def]
    kwargs: dict[str, object] = {
        "account_equity": Decimal("10000"),
        "risk_fraction": Decimal("0.005"),
        "stop_floor_bps": Decimal("15"),
        "stop_budget_bps": Decimal("333"),
        "requested_stop_bps": Decimal("15"),
        "price": Decimal("0.8500"),
        "contract_size": Decimal("100000"),
        "volume_min": Decimal("0.01"),
        "volume_step": Decimal("0.01"),
        "volume_max": None,
        "leverage": 5,
        "account_currency": "USD",
        "quote_currency": "GBP",
        "quote_to_account_rate": GBPUSD,
    }
    kwargs.update(overrides)
    return _ohne_unbekannte(size_position, **kwargs)


def test_verlust_am_stop_bleibt_im_budget_in_kontowaehrung() -> None:
    """ROT gegen 306bbaa (V3): 0,39 Lot, Verlust 63,15 USD bei 50 USD Budget."""
    r = _groesse()
    assert r.volume is not None
    stop_preis = Decimal("0.8500") * Decimal("15") / Decimal("10000")
    verlust_gbp = r.volume * Decimal("100000") * stop_preis
    verlust_usd = verlust_gbp * GBPUSD
    assert verlust_usd <= r.risk_currency, (
        f"Verlust am Stop {verlust_usd:.2f} USD bei {r.volume} Lot liegt ueber dem "
        f"Budget {r.risk_currency} USD -- die Groesse kennt die Waehrung nicht"
    )
    assert r.volume == Decimal("0.30"), r.volume
    assert getattr(r, "fx_rate", None) == GBPUSD, "die Groesse traegt keinen Kurs"


def test_kreuznotierung_ohne_kurs_sperrt() -> None:
    """Fehlender Wert sperrt (Regel 7): kein Kurs GBP->USD, keine Groesse."""
    r = _groesse(quote_to_account_rate=None)
    assert r.volume is None, f"ohne Kurs GBP->USD kam {r.volume} Lot heraus"
    assert "fx_unverifiable" in r.reasons, r.reasons


def test_gleiche_waehrung_braucht_keinen_kurs() -> None:
    r = _groesse(
        quote_currency="USD", quote_to_account_rate=None, price=Decimal("1.10")
    )
    assert r.volume is not None
    assert getattr(r, "fx_rate", None) == Decimal("1"), "gleiche Waehrung: Kurs 1"


def _usdjpy() -> Instrument:
    # Ueber die tolerante Hilfe: bei 306bbaa kannte ``Instrument`` keine
    # ``margin_currency`` -- ohne sie rechnet der alte Stand, und die Zahl wird sichtbar.
    return _ohne_unbekannte(
        Instrument,
        symbol="USDJPY",
        venue="x",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.001"),
        pip_size=Decimal("0.01"),
        digits=3,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=None,
        base_currency="USD",
        quote_currency="JPY",
        stop_level_points=0,
        freeze_level_points=0,
        fees=FeeSchedule(Decimal(7), Decimal(7), Decimal(0), Decimal(0), None, "USD"),
        sessions=(),
        margin_currency="USD",
    )


def _konto(currency: str = "USD") -> AccountState:
    return AccountState(
        "1",
        currency,
        Decimal(10000),
        Decimal(10000),
        Decimal(0),
        Decimal(5000),
        True,
        TS,
        leverage=30,
    )


def test_marge_usdjpy_in_kontowaehrung() -> None:
    """ROT gegen 306bbaa (V3c): required_margin 30.000 statt 200 USD.

    0,01 Lot USDJPY sind 1.000 USD Nennwert (Basiswaehrung USD), nicht 150.000
    "USD" (Notierung JPY als USD gelesen). Die Hebelklammer der Klasse ist 5, also
    200 USD Marge. (Meine erste Erwartung 33,33 USD rechnete mit dem Kontohebel 30
    und war falsch -- die Klammer misst, nicht der Kontohebel.)
    """
    req = OrderRequest(
        "x", "USDJPY", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("149")
    )
    p = _ohne_unbekannte(
        evaluate_leverage_preflight,
        instrument=_usdjpy(),
        request=req,
        account=_konto(),
        price=Decimal("150"),
        margin_to_account_rate=None,  # Margenwaehrung USD == Kontowaehrung
    )
    assert p.approved is True, (
        f"{p.reason}: Marge {p.required_margin} bei Freimarge 5.000"
    )
    assert p.required_margin is not None
    assert p.effective_leverage == 5
    nennwert_usd = Decimal("0.01") * Decimal("100000")
    assert p.required_margin == nennwert_usd / Decimal(p.effective_leverage), (
        f"Marge {p.required_margin} USD statt 200 USD -- die Notierung JPY wurde "
        "als Kontowaehrung gelesen"
    )
    assert p.required_margin == Decimal("200")


def test_marge_in_fremder_margenwaehrung_wird_mit_gemessenem_kurs_umgerechnet() -> None:
    """Dritter Margenfall (Gegenlese T10, E4): EUR-Konto, Margenwaehrung USD, Kurs
    USD->EUR 0,90 gemessen. Marge = Nennwert * Kurs / Hebel = 1.000 * 0,90 / 5 = 180 EUR.

    Die beiden anderen Faelle (gleiche Waehrung; fehlender Kurs sperrt) zeigen den Kurs
    nicht in der Zahl. Erst dieser Fall stellt sicher, dass der Kurs MULTIPLIZIERT wird
    und nicht ignoriert (1.000/5 = 200) oder verkehrt herum angewandt (222,22).
    """
    req = OrderRequest(
        "x", "USDJPY", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("149")
    )
    p = _ohne_unbekannte(
        evaluate_leverage_preflight,
        instrument=_usdjpy(),
        request=req,
        account=_konto("EUR"),
        price=Decimal("150"),
        margin_to_account_rate=Decimal("0.90"),
    )
    assert p.approved is True, (
        f"{p.reason}: Marge {p.required_margin} bei Freimarge 5.000"
    )
    assert p.effective_leverage == 5
    assert p.required_margin == Decimal("180"), (
        f"Marge {p.required_margin} EUR statt 180 EUR -- der gemessene Kurs 0,90 "
        "geht nicht in die Marge ein"
    )


def test_marge_ohne_kurs_sperrt() -> None:
    """EUR-Konto, Margenwaehrung USD, kein Kurs: keine Marge messbar, keine Order."""
    req = OrderRequest(
        "x", "USDJPY", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("149")
    )
    p = _ohne_unbekannte(
        evaluate_leverage_preflight,
        instrument=_usdjpy(),
        request=req,
        account=_konto("EUR"),
        price=Decimal("150"),
        margin_to_account_rate=None,
    )
    assert p.approved is False, (
        f"EUR-Konto, Marge in USD, kein Kurs -- und doch zugelassen mit "
        f"{p.required_margin} als Marge"
    )
    assert p.reason == "fx_unverifiable"


def test_betrag_verrechnet_keine_fremden_waehrungen() -> None:
    assert Betrag is not None, (
        "risk/waehrung.py fehlt -- Betraege tragen keine Waehrung"
    )
    with pytest.raises(WaehrungsFehler):
        Betrag(Decimal("1"), "USD") + Betrag(Decimal("1"), "EUR")
    with pytest.raises(WaehrungsFehler):
        Betrag(Decimal("1"), "USD").umgerechnet("EUR", None)
    assert Betrag(Decimal("2"), "GBP").umgerechnet("USD", GBPUSD).wert == Decimal(
        "2.54"
    )


class _Tick:
    def __init__(self, bid: str, ask: str) -> None:
        self.bid = Decimal(bid)
        self.ask = Decimal(ask)


def test_kurs_aus_ticks_direkt_kehrwert_und_fehlend() -> None:
    assert kurs_aus_ticks is not None, "risk/waehrung.py fehlt -- kein Kurs aus Ticks"
    ticks = {"GBPUSD": _Tick("1.2699", "1.2701")}
    assert kurs_aus_ticks("GBP", "USD", ticks.get) == Decimal("1.2700")
    assert kurs_aus_ticks("USD", "GBP", ticks.get) == Decimal("1") / Decimal("1.2700")
    assert kurs_aus_ticks("USD", "USD", ticks.get) == Decimal("1")
    assert kurs_aus_ticks("JPY", "CHF", ticks.get) is None

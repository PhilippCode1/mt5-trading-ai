"""Zweige des Orderpfads, die keine Suite je betrat (Gegenlese T10, E15; A15/A17).

WARUM DIESE DATEI
-----------------
``execution/leverage_preflight.py`` (Hebel- und Margenanschluss vor jeder eroeffnenden
Order) und ``execution/runner.py`` (baut die Order, setzt ihren Stop, sendet sie)
gehoeren nach dem Kriterium E-020 zum Geldpfad -- ein Fehler dort veraendert eine
Order, ihre Groesse, ihren Stop oder ihre Sperre. Beide standen nicht in
``GELDPFAD`` und waren die am schlechtesten gedeckten Module des Orderpfads: die
volle Suite betrat vom Margendeckel des Runners **keine einzige Zeile** (die Faelle
fuhren ein Konto ohne gemeldeten Hebel, und der Deckel gibt dann auf), nicht den
Erkundungspfad mit gezogenem Wurf, nicht das Hebel-Tor, nicht das unhandelbare
Stop-Budget, nicht die Margenrechnung in Notierungs- oder Fremdwaehrung.

Jeder Fall unten nennt die Zahl, die er erwartet, und woher sie kommt. Kein Fall
prueft nur „ein Fehler wurde geworfen“.

WAS BEWUSST NICHT GEDECKT IST
-----------------------------
``runner.py``: ``risk_sizing_no_volume`` und ein Urteil ohne Budget --
``authorize_opening`` liefert bei Zulassung immer beides (Freistellung in
``tools/torzaehlung.py``). Der Waechter ``stop_price_nonpositive`` hinter dem
Tick-Schritt war unerreichbar (der Schritt bewegt den Stop um einen Tick und greift
nur bei Kursen von vielen Ticks; Kosten sind echt positiv, das Budget hoechstens
1.666,7 bp) und stand im zweiten Lauf des Mutationstors am HEAD als unbemerkbare
Sonde -- er ist entfernt, nicht gedeckt.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.engine import Signal
from mt5_trading_ai.execution import runner as runner_modul
from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight
from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
from mt5_trading_ai.execution.risk_manager import RiskManager, RiskPolicy
from mt5_trading_ai.execution.runner import (
    RunnerReport,
    _margen_deckel,
    _spread_bps,
    run_signal,
)
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.gates.criteria import CriteriaVerdict
from mt5_trading_ai.gates.erkundung import entscheide_erkundung
from mt5_trading_ai.risk.leverage import LeveragePolicy, clamp_leverage
from mt5_trading_ai.risk.limits import LossLimits
from mt5_trading_ai.venue.mt5 import Mt5Account, Mt5Venue
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from test_paper_runner import (  # noqa: E402
    TS,
    FakeTerminal,
    _admitted,
    _catalog,
    _config,
    _run,
    _venue,
)

# Der Mittelkurs EURUSD des Fake-Terminals (bid 1.09990, ask 1.10000): so rechnet
# ``Mt5Venue.kurs("EUR", "USD")``, und so muss der Margendeckel rechnen.
EURUSD_MITTE = Decimal("1.09995")


def _eurusd() -> Instrument:
    return _venue().get_instrument("EURUSD")


def _konto(
    *,
    currency: str = "USD",
    margin_free: Decimal = Decimal("5000"),
    leverage: int | None = 30,
) -> AccountState:
    return AccountState(
        "1",
        currency,
        Decimal(10000),
        Decimal(10000),
        Decimal(0),
        margin_free,
        True,
        TS,
        leverage=leverage,
    )


# --- runner._spread_bps ------------------------------------------------------------


def test_ein_leerer_markt_hat_spread_null_und_teilt_nicht_durch_null() -> None:
    assert _spread_bps(Decimal("0"), Decimal("0")) == Decimal("0")
    assert _spread_bps(Decimal("1.0999"), Decimal("1.1001")) == (
        Decimal("0.0002") / Decimal("1.1") * Decimal("10000")
    )


# --- runner._margen_deckel: jede Rueckgabe mit ihrer Zahl -----------------------


def _deckel(
    *,
    instrument: Instrument | None = None,
    account: AccountState | None = None,
    price: Decimal = EURUSD_MITTE,
    plaetze: int = 3,
    rate: Decimal | None = None,
) -> Decimal | None:
    """EUR-Konto mit Hebel 1 ueber EURUSD -- die Marge (Basiswaehrung EUR) braucht
    dann keinen Kurs; jede Abweichung wird einzeln uebergeben."""
    return _margen_deckel(
        instrument=instrument if instrument is not None else _eurusd(),
        account=account if account is not None else _konto(currency="EUR", leverage=1),
        price=price,
        plaetze=plaetze,
        margin_to_account_rate=rate,
    )


def test_ohne_kontohebel_kurs_kontrakt_oder_platz_gibt_es_keinen_deckel() -> None:
    """``None`` heisst „unbekannt“, nie „unbegrenzt“ -- jede der fuenf Luecken einzeln,
    neben dem Bezugsfall, der eine Zahl liefert."""
    assert _deckel() == Decimal("0.01"), (
        _deckel()
    )  # 5.000 / 3 * 0,8 = 1.333 EUR -> 0,01
    assert _deckel(account=_konto(currency="EUR", leverage=None)) is None
    assert _deckel(account=_konto(currency="EUR", leverage=0)) is None
    assert _deckel(price=Decimal("0")) is None
    assert _deckel(instrument=replace(_eurusd(), contract_size=Decimal("0"))) is None
    assert _deckel(plaetze=0) is None
    # Lauf 2 am HEAD: ``plaetze < 1`` -> ``<= 1`` und ``1`` -> ``2`` ueberlebten -- kein Fall
    # fuhr genau EINEN Platz. Ein Platz heisst: die ganze freie Marge fuer diese Position,
    # 5.000 * 0,8 = 4.000 EUR / 100.000 EUR je Lot -> 0,04 Lot.
    assert _deckel(plaetze=1) == Decimal("0.04"), _deckel(plaetze=1)


def test_der_deckel_rechnet_auch_bei_kursen_unter_eins_und_kontraktgroesse_eins() -> (
    None
):
    """Sonden am HEAD (E16, `06-mutationstor-head.txt`): ``price <= 0`` -> ``<= 1`` und die
    Kontraktgroessen-Klammer ``<= 0`` -> ``<= 1`` ueberlebten, weil jeder Fall mit Kurs
    ueber 1 und Kontraktgroesse 100.000 rechnete. EURGBP-Kurse liegen unter 1, ein
    Krypto-CFD hat Kontraktgroesse 1 -- beide muessen eine Zahl liefern, nicht ``None``."""
    # Kurs 0,85 (EURGBP-Groessenordnung), Marge in Basiswaehrung: der Kurs geht nicht in
    # die Marge je Lot ein -- 5.000 / 3 * 0,8 = 1.333 EUR / 100.000 EUR je Lot -> 0,01
    assert _deckel(price=Decimal("0.85")) == Decimal("0.01")
    # Kontraktgroesse 1: 1.333,33 EUR Anteil / 1 EUR je Lot -> 1.333,33 Lot (Schritt 0,01)
    eins = _deckel(instrument=replace(_eurusd(), contract_size=Decimal("1")))
    assert eins == Decimal("1333.33"), eins


def test_der_deckel_in_basiswaehrung_ist_der_anteil_der_freien_marge_je_lot() -> None:
    """EUR-Konto, Marge in EUR (Basiswaehrung): je Lot 100.000 / Hebel; ein Drittel der
    freien Marge mit 80 % Sicherheit, auf den Volumenschritt abgerundet."""
    eurusd = _eurusd()
    konto = _konto(currency="EUR", margin_free=Decimal("30000"), leverage=1)
    deckel = _margen_deckel(
        instrument=eurusd,
        account=konto,
        price=EURUSD_MITTE,
        plaetze=3,
        margin_to_account_rate=None,
    )
    # 30.000 / 3 * 0,8 = 8.000 EUR Anteil; 100.000 EUR je Lot -> 0,08 Lot
    assert deckel == Decimal("0.08"), deckel
    # 3.000 frei -> 800 EUR Anteil -> 0,008 Lot -> auf 0,01 abgerundet = 0
    klein = _margen_deckel(
        instrument=eurusd,
        account=replace(konto, margin_free=Decimal("3000")),
        price=EURUSD_MITTE,
        plaetze=3,
        margin_to_account_rate=None,
    )
    assert klein == Decimal("0.00"), klein


def test_der_deckel_in_notierungswaehrung_nimmt_den_kurs_in_die_marge_je_lot() -> None:
    """USD-Konto, Margenwaehrung USD (= Notierung): je Lot 100.000 * Kurs."""
    eurusd = replace(_eurusd(), margin_currency="USD")
    deckel = _margen_deckel(
        instrument=eurusd,
        account=_konto(margin_free=Decimal("33000"), leverage=1),
        price=Decimal("1.1"),
        plaetze=3,
        margin_to_account_rate=None,
    )
    # 33.000 / 3 * 0,8 = 8.800 USD; 110.000 USD je Lot -> 0,08 Lot
    assert deckel == Decimal("0.08"), deckel


def test_der_deckel_in_fremder_margenwaehrung_braucht_den_gemessenen_kurs() -> None:
    """USD-Konto, Marge in EUR (Basis): ohne Kurs kein Deckel; mit Kurs 1,1 wie in
    Notierungswaehrung. Eine Margenwaehrung, die weder Basis noch Notierung ist,
    kann nicht gerechnet werden -- ``None``."""
    eurusd = _eurusd()
    konto = _konto(margin_free=Decimal("33000"), leverage=1)
    assert (
        _margen_deckel(
            instrument=eurusd,
            account=konto,
            price=Decimal("1.1"),
            plaetze=3,
            margin_to_account_rate=None,
        )
        is None
    )
    mit_kurs = _margen_deckel(
        instrument=eurusd,
        account=konto,
        price=Decimal("1.1"),
        plaetze=3,
        margin_to_account_rate=Decimal("1.1"),
    )
    assert mit_kurs == Decimal("0.08"), mit_kurs
    assert (
        _margen_deckel(
            instrument=replace(eurusd, margin_currency="CHF"),
            account=konto,
            price=Decimal("1.1"),
            plaetze=3,
            margin_to_account_rate=Decimal("1.1"),
        )
        is None
    )


def test_ohne_volumenschritt_bleibt_der_deckel_ungerundet() -> None:
    eurusd = replace(_eurusd(), margin_currency="USD", volume_step=Decimal("0"))
    deckel = _margen_deckel(
        instrument=eurusd,
        account=_konto(margin_free=Decimal("33000"), leverage=1),
        price=Decimal("1.1"),
        plaetze=3,
        margin_to_account_rate=None,
    )
    assert deckel == Decimal("8800") / Decimal("110000"), deckel


# --- leverage_preflight: die drei unbetretenen Zweige -----------------------------


def _order(volume: str = "0.01") -> OrderRequest:
    return OrderRequest(
        "x", "EURUSD", OrderSide.BUY, OrderType.MARKET, Decimal(volume), Decimal("1.09")
    )


def test_eine_politik_ohne_deckel_fuer_die_klasse_laesst_keine_order_zu() -> None:
    """``no_trade`` der Klammer kommt vor jeder Margenrechnung: kein Hebel, keine Marge."""
    politik = LeveragePolicy(
        policy_id="probe",
        policy_version="1",
        valid_from="2026-01-01",
        verified_on="2026-01-01",
        jurisdiction="EU",
        caps={},
        source_path="probe",
    )
    p = evaluate_leverage_preflight(
        instrument=_eurusd(),
        request=_order(),
        account=_konto(),
        price=Decimal("1.1"),
        requested_leverage=5,
        policy=politik,
    )
    assert p.approved is False
    assert p.leverage.no_trade is True
    assert p.effective_leverage is None and p.required_margin is None
    assert p.reason == (p.leverage.reason or "no_trade")


def test_die_marge_in_notierungswaehrung_traegt_den_kurs() -> None:
    """Margenwaehrung USD = Notierung, Konto USD: 0,01 Lot * 100.000 * 1,10 / Hebel 5
    = 220 USD -- nicht 200 (Basiswaehrung) und nicht 0."""
    p = evaluate_leverage_preflight(
        instrument=replace(_eurusd(), margin_currency="USD"),
        request=_order(),
        account=_konto(leverage=None),
        price=Decimal("1.1"),
        requested_leverage=5,
    )
    assert p.approved is True, p.reason
    assert p.effective_leverage == 5
    assert p.required_margin == Decimal("220"), p.required_margin


def test_eine_margenwaehrung_die_weder_basis_noch_notierung_ist_sperrt() -> None:
    """Keine Marge messbar = keine Order -- auch mit einem Kurs in der Hand."""
    p = evaluate_leverage_preflight(
        instrument=replace(_eurusd(), margin_currency="CHF"),
        request=_order(),
        account=_konto(),
        price=Decimal("1.1"),
        requested_leverage=5,
        margin_to_account_rate=Decimal("1.1"),
    )
    assert p.approved is False
    assert p.reason == "fx_unverifiable"
    assert p.required_margin is None


# --- run_signal: die unbetretenen Naehte --------------------------------------------


def test_ein_gezogener_erkundungswurf_faehrt_die_strategie_trotz_ablehnung() -> None:
    """Der Schluessel ist die Auftragskennung; gesucht wird die erste, deren Wurf
    erkundet -- derselbe Schluessel ergibt in jedem Lauf dieselbe Entscheidung."""
    kennung = None
    entscheidung = None
    for i in range(5000):
        kandidat = f"run-{i}"
        entscheidung = entscheide_erkundung(
            ist_papierkonto=True,
            ablehnungsgrund="strategy_not_admitted",
            schluessel=f"EURUSD|LONG|{kandidat}",
        )
        if entscheidung.erkunden:
            kennung = kandidat
            break
    assert kennung is not None and entscheidung is not None, (
        "kein Wurf in 5000 Kennungen"
    )

    report = _run(
        admission=CriteriaVerdict(passed=False, results=(), unmet=("psr",)),
        client_order_id=kennung,
    )
    assert report.erkundet is True
    assert report.erkundung_p == entscheidung.wahrscheinlichkeit
    zulassung = next(s for s in report.steps if s.name == "zulassung")
    assert zulassung.ok is True
    assert zulassung.detail.startswith("ERKUNDUNG (p=") and "psr" in zulassung.detail
    assert report.opened, report.reject_reason


def test_ein_hebel_ohne_deckel_endet_an_der_hebel_naht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Klammer sagt ``no_trade`` (echte Entscheidung fuer eine Klasse ohne Deckel);
    der Runner traegt ihren Grund und rechnet nichts weiter."""
    keine = clamp_leverage(requested=None, asset_class="klasse-ohne-deckel")
    assert keine.leverage is None and keine.no_trade
    monkeypatch.setattr(runner_modul, "clamp_leverage", lambda **_: keine)

    report = _run()
    assert not report.opened
    assert report.reject_reason == (keine.reason or "leverage_no_trade")
    assert [s.name for s in report.steps if not s.ok] == ["hebel"]


def test_ein_unhandelbares_stop_budget_endet_an_der_stop_naht() -> None:
    """``max_cost_drag`` 0,01 %: die Kosten-Untergrenze liegt ueber der Margendecke."""
    manager = RiskManager(
        RiskPolicy(max_cost_drag=Decimal("0.0001")), zustand=FluechtigerZustand()
    )
    report = _run(risk_manager=manager)
    assert not report.opened
    assert report.reject_reason is not None
    assert report.reject_reason.startswith("stop_budget_"), report.reject_reason
    assert [s.name for s in report.steps if not s.ok] == ["stop-preis"]


def test_eine_risikoablehnung_ohne_halt_setzt_keinen_latch_am_venue() -> None:
    """Tagesverlust ueber 2 %, Drawdown unter 10 %: die Risikoschicht lehnt ab, der
    Halt bleibt aus -- und der Runner darf dann auch keinen setzen."""
    venue = _venue(equity=Decimal("9700"))
    manager = RiskManager(
        RiskPolicy(loss_limits=LossLimits(max_daily_loss_fraction=Decimal("0.02"))),
        zustand=FluechtigerZustand(),
    )
    manager.observe_equity(TS.replace(hour=0, minute=5), Decimal("10000"))
    report = _run(venue=venue, risk_manager=manager)
    assert not report.opened
    assert [s.name for s in report.steps if not s.ok] == ["risiko"], report.steps
    assert report.reject_reason is not None
    assert venue.is_halted() is False, report.reject_reason


class _KontoMitHebel(FakeTerminal):
    """Das Fake-Terminal meldet Kontohebel und freie Marge -- erst damit rechnet der
    Margendeckel ueberhaupt (ohne Hebel gibt er auf, s. o.)."""

    def __init__(self, *, margin_free: Decimal, leverage: int) -> None:
        super().__init__()
        self._account = Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=margin_free,
            is_demo=True,
            ts=TS,
            leverage=leverage,
        )


def _venue_mit_hebel(
    *, margin_free: Decimal, leverage: int, risk_manager: RiskManager
) -> Mt5Venue:
    venue = Mt5Venue(
        name="mt5-demo",
        terminal=_KontoMitHebel(margin_free=margin_free, leverage=leverage),
        catalog=_catalog(),
        sync=None,
        max_notional_drift=Decimal("0"),
        risk_manager=risk_manager,
        clock=lambda: TS,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    return venue


def _lauf_mit_hebel(
    *, margin_free: Decimal, risk_fraction: Decimal
) -> tuple[RunnerReport, Mt5Venue]:
    manager = RiskManager(
        RiskPolicy(risk_fraction=risk_fraction), zustand=FluechtigerZustand()
    )
    venue = _venue_mit_hebel(margin_free=margin_free, leverage=1, risk_manager=manager)
    report = run_signal(
        venue=venue,
        risk_manager=manager,
        admission=_admitted(),
        symbol="EURUSD",
        side=Signal.LONG,
        config=_config(),
        now=TS,
        client_order_id="run-hebel",
        darf_schreiben=True,
    )
    return report, venue


def test_der_margendeckel_kappt_die_risikogroesse_auf_die_freie_marge() -> None:
    """Hebel 1, 6.000 USD frei, drei Plaetze: 6.000 / 3 * 0,8 = 1.600 USD; je Lot
    100.000 EUR * 1,09995 = 109.995 USD -> 0,0145 -> 0,01 Lot. Das Risikobudget (0,5 %)
    ergaebe mehr; gesendet wird der Deckel."""
    report, venue = _lauf_mit_hebel(
        margin_free=Decimal("6000"), risk_fraction=Decimal("0.005")
    )
    deckel = next(s for s in report.steps if s.name == "margen-deckel")
    assert deckel.ok is True
    assert deckel.detail.endswith("-> 0.01 (freie Marge)"), deckel.detail
    groesse = next(s for s in report.steps if s.name == "sizing")
    assert Decimal(groesse.detail.removeprefix("volume=")) > Decimal("0.01"), groesse
    assert report.opened, report.reject_reason
    assert venue.is_halted() is False


def test_reicht_die_freie_marge_nicht_fuer_das_mindestvolumen_wird_nicht_gesendet() -> (
    None
):
    """1.000 USD frei: 1.000 / 3 * 0,8 = 266,67 USD -> 0,0024 Lot -> 0,00 -- unter dem
    Mindestvolumen 0,01. Kleiner als der Broker zulaesst ist kein Handel."""
    report, venue = _lauf_mit_hebel(
        margin_free=Decimal("1000"), risk_fraction=Decimal("0.005")
    )
    assert not report.opened
    assert report.reject_reason == "margin_below_min_volume"
    deckel = next(s for s in report.steps if s.name == "margen-deckel")
    assert deckel.detail == "moeglich 0.00, Mindestvolumen 0.01", deckel.detail
    assert venue.is_halted() is False


def test_der_halt_am_venue_traegt_den_grund_der_risikoschicht() -> None:
    """Sonde am HEAD (E16): ``auth.reason or "risk_halt"`` -> ``and`` ueberlebte -- kein
    Fall las den Grund am Venue. Ein Halt ohne seinen Grund ist fuer den Betreiber ein
    Halt ohne Erklaerung; der Runner reicht den Grund der Risikoschicht unveraendert
    durch, ``risk_halt`` ist nur der Ersatz fuer einen fehlenden."""
    venue = _venue(equity=Decimal("8000"))
    manager = RiskManager(zustand=FluechtigerZustand())
    manager.observe_equity(TS.replace(hour=0, minute=5), Decimal("10000"))  # Hoch
    report = _run(venue=venue, risk_manager=manager)
    assert not report.opened
    assert report.reject_reason is not None and report.reject_reason != "risk_halt"
    assert venue.is_halted()
    assert venue.halt_gruende == (report.reject_reason,), venue.halt_gruende

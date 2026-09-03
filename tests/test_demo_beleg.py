"""Der geteilte Rechner des Demo-Reifetors (``pruefe_demo_beleg``).

Warum es zwei Einstiege gibt, steht im Modul-Docstring von ``venue/demo_run.py``: der
Kontoabgleich braucht Sicht auf das Demokonto, das Reifetor am Order-Pfad hat sie nicht
(es laeuft nur auf einem Livekonto). Diese Datei sichert die Eigenschaft, die diese
Teilung erst vertretbar macht -- **die Regel steht nur einmal im Haus**: alles, was
``pruefe_demo_beleg`` bemaengelt, bemaengelt ``evaluate_demo_progress`` auch. Waeren es
zwei Fassungen, liefen sie beim naechsten Eingriff auseinander, und die schwaechere
saesse am Order-Pfad.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue.demo_run import (
    MIN_DEMO_DAYS,
    DemoAccount,
    DemoRegistration,
    evaluate_demo_progress,
    pruefe_demo_beleg,
)

#: Feste Gegenwart -- kein Test haengt an der Rechneruhr.
JETZT = datetime(2026, 8, 11, 12, tzinfo=UTC)
KONTO = DemoAccount(account_id="demo-9001", broker="Demo-Broker", is_demo=True)


def _uhr() -> datetime:
    return JETZT


def _verdict(passed: bool) -> EdgeVerdict:
    return EdgeVerdict(passed=passed, checks=(), unmet=() if passed else ("trades",))


def _beleg(
    *,
    tage_alt: int = MIN_DEMO_DAYS,
    strategy_id: str = "eurusd",
    version: str = "v1",
    konto: DemoAccount = KONTO,
) -> DemoRegistration:
    tag: date = (JETZT - timedelta(days=tage_alt)).date()
    return DemoRegistration(
        strategy_id=strategy_id, version=version, registered_on=tag, account=konto
    )


def test_ein_vollstaendiger_beleg_ueber_der_frist_ist_reif() -> None:
    """Die Gegenprobe: der Rechner ist keine Dauerbremse. Ohne diesen Fall waere
    jede Sperre darunter wertlos -- eine, die immer ausloest, sagt so wenig wie eine,
    die nie ausloest."""
    ergebnis = pruefe_demo_beleg(
        registration=_beleg(), live_verdict=_verdict(True), clock=_uhr
    )
    assert ergebnis.ready_for_live_question is True, ergebnis.reasons


def test_einen_tag_vor_der_frist_nicht_reif() -> None:
    ergebnis = pruefe_demo_beleg(
        registration=_beleg(tage_alt=MIN_DEMO_DAYS - 1),
        live_verdict=_verdict(True),
        clock=_uhr,
    )
    assert not ergebnis.ready_for_live_question
    assert f"demo_zu_kurz_{MIN_DEMO_DAYS - 1}_von_{MIN_DEMO_DAYS}_tagen" in (
        ergebnis.reasons
    )


@pytest.mark.parametrize(
    ("beleg", "grund"),
    [
        (_beleg(strategy_id="   "), "strategie_id_fehlt"),
        (_beleg(version=""), "strategie_version_fehlt"),
        (
            _beleg(konto=DemoAccount("  ", "Demo-Broker", True)),
            "kontonummer_fehlt_im_beleg",
        ),
        (_beleg(konto=DemoAccount("demo-9001", "", True)), "broker_fehlt_im_beleg"),
        (
            _beleg(konto=DemoAccount("demo-9001", "Demo-Broker", False)),
            "registrierung_nicht_auf_demokonto",
        ),
        (_beleg(tage_alt=-3), "registrierung_in_der_zukunft_3_tage"),
    ],
)
def test_jeder_beleg_mangel_loest_aus(beleg: DemoRegistration, grund: str) -> None:
    """Ein Zeugnis ohne Strategie passt auf jede Strategie, eines ohne Konto auf jedes
    Konto. Die Frist allein macht keinen Beleg -- alle Faelle hier haben sie voll."""
    ergebnis = pruefe_demo_beleg(
        registration=beleg, live_verdict=_verdict(True), clock=_uhr
    )
    assert not ergebnis.ready_for_live_question
    assert grund in ergebnis.reasons


def test_verlorener_edge_im_demo_loest_aus() -> None:
    ergebnis = pruefe_demo_beleg(
        registration=_beleg(tage_alt=400), live_verdict=_verdict(False), clock=_uhr
    )
    assert not ergebnis.ready_for_live_question
    assert "live_demo_verfehlt_sechs_bedingungen" in ergebnis.reasons


def test_naive_uhr_macht_die_laufzeit_unbewertbar() -> None:
    # Nicht bewertbar heisst nicht erfuellt (Regel des Kerns).
    ergebnis = pruefe_demo_beleg(
        registration=_beleg(tage_alt=400),
        live_verdict=_verdict(True),
        clock=lambda: datetime(2027, 1, 1, 12),
    )
    assert not ergebnis.ready_for_live_question
    assert "uhr_ohne_zeitzone" in ergebnis.reasons


@pytest.mark.parametrize(
    "beleg",
    [
        _beleg(strategy_id="   "),
        _beleg(version=""),
        _beleg(tage_alt=3),
        _beleg(tage_alt=-3),
        _beleg(konto=DemoAccount("demo-9001", "Demo-Broker", False)),
    ],
)
def test_die_volle_pruefung_uebernimmt_jeden_beleg_grund(
    beleg: DemoRegistration,
) -> None:
    """Kein zweiter Rechner: jeder Grund der Beleg-Pruefung taucht auch in der vollen
    Pruefung auf. Sonst saesse am Order-Pfad eine Fassung, die weniger sieht als die
    Harness -- und genau die waere beim naechsten Eingriff die vergessene."""
    schmal = pruefe_demo_beleg(
        registration=beleg, live_verdict=_verdict(True), clock=_uhr
    )
    voll = evaluate_demo_progress(
        registration=beleg,
        observed_account=beleg.account,
        live_verdict=_verdict(True),
        clock=_uhr,
    )
    assert set(schmal.reasons) <= set(voll.reasons)
    assert not voll.ready_for_live_question


def test_die_volle_pruefung_sieht_mehr_als_die_schmale() -> None:
    """Die andere Richtung -- sonst waere die Teilung sinnlos: ein fremdes Konto faellt
    nur der vollen Pruefung auf, weil nur sie das beobachtete Konto kennt."""
    beleg = _beleg(tage_alt=400)
    schmal = pruefe_demo_beleg(
        registration=beleg, live_verdict=_verdict(True), clock=_uhr
    )
    voll = evaluate_demo_progress(
        registration=beleg,
        observed_account=DemoAccount("9999", "Demo-Broker", True),
        live_verdict=_verdict(True),
        clock=_uhr,
    )
    assert schmal.ready_for_live_question is True
    assert not voll.ready_for_live_question
    assert "kontonummer_weicht_von_registrierung_ab" in voll.reasons

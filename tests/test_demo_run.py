"""Test des Demo-Betrieb-Tors (Paket 5, §8.5). Fail-closed, negativ gefahren.

Schwerpunkt nach E7: die Demo-Laufzeit wird **gerechnet**, nicht entgegengenommen, und
das Reifezeugnis ist an EIN Konto gebunden. Zu jeder Bedingung steht hier ein Fall, in
dem sie ausloest, und -- wo die Bedingung eine Kante hat -- der Nachbarfall, in dem sie
es nicht tut. Eine Bedingung ohne beide Seiten waere nicht als Melder belegt.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue.demo_run import (
    MIN_DEMO_DAYS,
    DemoAccount,
    DemoGateError,
    DemoRegistration,
    evaluate_demo_progress,
    register_for_demo,
)

KONTO = DemoAccount(account_id="4711", broker="Demo-Broker", is_demo=True)
START = date(2026, 1, 1)


def _verdict(passed: bool) -> EdgeVerdict:
    return EdgeVerdict(
        passed=passed, checks=(), unmet=() if passed else ("trade_count",)
    )


def _uhr(tag: date, stunde: int = 12) -> Callable[[], datetime]:
    """Feste Uhr auf ``tag``. Injiziert statt ``datetime.now()`` -- sonst haengt der
    Melder an der Rechneruhr und ist nicht pruefbar."""
    return lambda: datetime(tag.year, tag.month, tag.day, stunde, tzinfo=UTC)


def _registrierung(
    *, konto: DemoAccount = KONTO, seit: date = START
) -> DemoRegistration:
    return DemoRegistration(
        strategy_id="x", version="v1", registered_on=seit, account=konto
    )


def _reife(
    *,
    registration: DemoRegistration | None = None,
    beobachtet: DemoAccount = KONTO,
    tage: int = MIN_DEMO_DAYS,
    live: bool = True,
    uhr: Callable[[], datetime] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    reg = registration if registration is not None else _registrierung()
    ergebnis = evaluate_demo_progress(
        registration=reg,
        observed_account=beobachtet,
        live_verdict=_verdict(live),
        clock=uhr if uhr is not None else _uhr(reg.registered_on + timedelta(tage)),
    )
    return ergebnis.ready_for_live_question, ergebnis.reasons


# --- Registrierung ----------------------------------------------------------
def test_registrierung_ohne_edge_wird_abgelehnt() -> None:
    # Kern von Paket 5: ohne bestandenen Edge-Test kein Demo-Betrieb.
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="x",
            version="v1",
            edge_verdict=_verdict(False),
            account=KONTO,
            clock=_uhr(START),
        )


def test_registrierung_mit_edge_wird_angenommen() -> None:
    reg = register_for_demo(
        strategy_id="x",
        version="v1",
        edge_verdict=_verdict(True),
        account=KONTO,
        clock=_uhr(START),
    )
    assert reg.strategy_id == "x"
    assert reg.account == KONTO


def test_registrierungsdatum_kommt_aus_der_uhr() -> None:
    """Kein Rueckdatieren: das Datum ist ein Uhrenwert, kein Argument."""
    reg = register_for_demo(
        strategy_id="x",
        version="v1",
        edge_verdict=_verdict(True),
        account=KONTO,
        clock=_uhr(date(2026, 3, 5)),
    )
    assert reg.registered_on == date(2026, 3, 5)


def test_registrierung_verlangt_ids() -> None:
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="  ",
            version="v1",
            edge_verdict=_verdict(True),
            account=KONTO,
            clock=_uhr(START),
        )


def test_registrierung_auf_echtgeldkonto_wird_abgelehnt() -> None:
    # Ein Demo-Betrieb, der auf einem Echtgeldkonto beginnt, ist ein Widerspruch.
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="x",
            version="v1",
            edge_verdict=_verdict(True),
            account=DemoAccount("4711", "Demo-Broker", is_demo=False),
            clock=_uhr(START),
        )


@pytest.mark.parametrize(
    "konto",
    [
        DemoAccount("   ", "Demo-Broker", True),
        DemoAccount("4711", "  ", True),
    ],
)
def test_registrierung_verlangt_kontonummer_und_broker(konto: DemoAccount) -> None:
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="x",
            version="v1",
            edge_verdict=_verdict(True),
            account=konto,
            clock=_uhr(START),
        )


def test_registrierung_mit_naiver_uhr_wird_abgelehnt() -> None:
    # Naiv kann Ortszeit oder UTC heissen -- ein nicht belegbares Datum ist ein Nein.
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="x",
            version="v1",
            edge_verdict=_verdict(True),
            account=KONTO,
            clock=lambda: datetime(2026, 1, 1, 12),
        )


# --- Laufzeit ---------------------------------------------------------------
def test_einen_tag_vor_der_frist_nicht_reif() -> None:
    reif, gruende = _reife(tage=MIN_DEMO_DAYS - 1)
    assert not reif
    assert f"demo_zu_kurz_{MIN_DEMO_DAYS - 1}_von_{MIN_DEMO_DAYS}_tagen" in gruende


def test_genau_auf_der_frist_reif() -> None:
    # Gegenprobe zur Kante: die Bedingung greift nicht immer -- sonst waere sie
    # kein Melder, sondern eine Dauerbremse.
    reif, gruende = _reife(tage=MIN_DEMO_DAYS)
    assert reif, gruende


def test_am_tag_der_registrierung_nicht_reif() -> None:
    # Der Fall der Harness: registrieren und sofort fragen ergibt null Tage.
    reif, gruende = _reife(tage=0)
    assert not reif
    assert f"demo_zu_kurz_0_von_{MIN_DEMO_DAYS}_tagen" in gruende


def test_registrierung_in_der_zukunft_ist_kein_vorsprung() -> None:
    # Ein Datum von morgen darf nicht als "laeuft schon" gelten.
    reif, gruende = _reife(tage=-5)
    assert not reif
    assert "registrierung_in_der_zukunft_5_tage" in gruende


def test_naive_uhr_macht_die_laufzeit_unbewertbar() -> None:
    reif, gruende = _reife(uhr=lambda: datetime(2027, 1, 1, 12))
    assert not reif
    assert "uhr_ohne_zeitzone" in gruende


def test_uhr_in_fremder_zone_wird_nach_utc_gerechnet() -> None:
    """Eine Uhr mit Versatz ist bewertbar -- sie wird umgerechnet, nicht verworfen.

    Ohne Umrechnung waere der Tageswechsel um bis zu einen Tag verschoben, und die
    Frist haette an einer Zone gehangen, die niemand vereinbart hat.
    """
    tokio = timezone(timedelta(hours=9))
    reif, gruende = _reife(
        uhr=lambda: datetime(2026, 6, 30, 8, tzinfo=tokio)  # = 2026-06-29 23:00 UTC
    )
    # 2026-01-01 -> 2026-06-29 sind 179 Tage: einer zu wenig.
    assert not reif
    assert f"demo_zu_kurz_179_von_{MIN_DEMO_DAYS}_tagen" in gruende


# --- Kontobindung -----------------------------------------------------------
def test_fremdes_konto_zaehlt_nicht() -> None:
    reif, gruende = _reife(beobachtet=DemoAccount("9999", "Demo-Broker", True))
    assert not reif
    assert "kontonummer_weicht_von_registrierung_ab" in gruende


def test_fremder_broker_zaehlt_nicht() -> None:
    reif, gruende = _reife(beobachtet=DemoAccount("4711", "Anderer-Broker", True))
    assert not reif
    assert "broker_weicht_von_registrierung_ab" in gruende


def test_leere_kontonummern_gelten_als_fehlend_nicht_als_gleich() -> None:
    """Die Falle: leer == leer waere eine Uebereinstimmung und der Vergleich
    koennte per Konstruktion nie ausloesen."""
    leer = DemoAccount("", "", True)
    reif, gruende = _reife(registration=_registrierung(konto=leer), beobachtet=leer)
    assert not reif
    assert "kontonummer_fehlt" in gruende
    assert "broker_fehlt" in gruende


def test_beobachtetes_echtgeldkonto_zaehlt_nicht() -> None:
    # Die Reife eines Demokontos reift kein Echtgeldkonto.
    reif, gruende = _reife(beobachtet=DemoAccount("4711", "Demo-Broker", False))
    assert not reif
    assert "beobachtetes_konto_ist_kein_demokonto" in gruende


def test_registrierung_auf_nicht_demokonto_zaehlt_nicht() -> None:
    # ``DemoRegistration`` ist ein offener Typ (auch aus einem Speicher rekonstruiert);
    # die Pruefung darf sich nicht darauf verlassen, dass alles durch das Tor kam.
    echt = DemoAccount("4711", "Demo-Broker", False)
    reif, gruende = _reife(registration=_registrierung(konto=echt), beobachtet=echt)
    assert not reif
    assert "registrierung_nicht_auf_demokonto" in gruende


# --- Edge im Demo -----------------------------------------------------------
def test_verlorener_edge_sperrt_trotz_langer_laufzeit() -> None:
    reif, gruende = _reife(tage=400, live=False)
    assert not reif
    assert "live_demo_verfehlt_sechs_bedingungen" in gruende


def test_alle_gruende_werden_gesammelt() -> None:
    # Kein Abbruch beim ersten Nein: der Betreiber soll die ganze Liste sehen.
    reif, gruende = _reife(
        tage=10, live=False, beobachtet=DemoAccount("9999", "Anderer-Broker", False)
    )
    assert not reif
    assert len(gruende) >= 4

"""Frische-Latch (S2): jede Kante einmal rot, einmal gruen gefahren.

Die Sperre entscheidet, ob ein Kontozustand ueberhaupt bewertbar ist. Sie ist damit die
Vorbedingung aller uebrigen Sperren -- ein Fehler hier macht jede folgende Zahl still
falsch. Deshalb wird jede der vier Ablehnungskanten einzeln belegt, nicht nur der
Normalfall.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from mt5_trading_ai.execution.freshness import (
    FRESHNESS_POLICY_VERSION,
    FUTURE_TOLERANCE,
    MAX_SNAPSHOT_AGE,
    evaluate_account_freshness,
)

JETZT = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _urteil(**over: object):
    basis: dict[str, object] = {
        "snapshot_ts": JETZT,
        "now": JETZT,
        "connected": True,
    }
    basis.update(over)
    return evaluate_account_freshness(**basis)  # type: ignore[arg-type]


# --- gruen ----------------------------------------------------------------
def test_frischer_zustand_ist_bewertbar() -> None:
    urteil = _urteil()
    assert urteil.evaluable is True
    assert urteil.reason is None
    assert urteil.age == timedelta(0)
    assert urteil.policy_version == FRESHNESS_POLICY_VERSION


def test_alter_genau_auf_der_frist_ist_noch_bewertbar() -> None:
    """Die Frist ist einschliessend -- sonst haengt das Urteil an der Rundung."""
    urteil = _urteil(now=JETZT + MAX_SNAPSHOT_AGE)
    assert urteil.evaluable is True
    assert urteil.age == MAX_SNAPSHOT_AGE


def test_zukunft_innerhalb_der_toleranz_ist_bewertbar() -> None:
    urteil = _urteil(now=JETZT - FUTURE_TOLERANCE)
    assert urteil.evaluable is True


# --- rot ------------------------------------------------------------------
def test_zu_alt_ist_nicht_bewertbar() -> None:
    urteil = _urteil(now=JETZT + MAX_SNAPSHOT_AGE + timedelta(milliseconds=1))
    assert urteil.evaluable is False
    assert urteil.reason == "snapshot_stale"
    assert urteil.age > urteil.max_age


def test_zukunft_jenseits_der_toleranz_ist_nicht_bewertbar() -> None:
    """Ohne diese Kante liesse ein falscher Zeitstempel die Sperre komplett aus."""
    urteil = _urteil(now=JETZT - FUTURE_TOLERANCE - timedelta(seconds=1))
    assert urteil.evaluable is False
    assert urteil.reason == "snapshot_from_future"


def test_getrennte_sitzung_ist_nie_bewertbar() -> None:
    """Auch ein taufrischer Stempel belegt nichts, wenn die Sitzung steht."""
    urteil = _urteil(connected=False)
    assert urteil.evaluable is False
    assert urteil.reason == "session_not_connected"


def test_getrennte_sitzung_schlaegt_frische() -> None:
    """Reihenfolge festhalten: die Verbindung wird VOR dem Alter geprueft."""
    urteil = _urteil(connected=False, now=JETZT + timedelta(hours=1))
    assert urteil.reason == "session_not_connected"


def test_naiver_zeitstempel_ist_nicht_bewertbar() -> None:
    """Ein Stempel ohne Zeitzone als UTC zu deuten waere geraten, nicht gemessen."""
    urteil = _urteil(snapshot_ts=JETZT.replace(tzinfo=None))
    assert urteil.evaluable is False
    assert urteil.reason == "snapshot_naive"


def test_naive_gegenwart_ist_ebenfalls_nicht_bewertbar() -> None:
    urteil = _urteil(now=JETZT.replace(tzinfo=None))
    assert urteil.evaluable is False
    assert urteil.reason == "snapshot_naive"


# --- Politik selbst -------------------------------------------------------
def test_nicht_positive_frist_ist_ein_fehler_kein_urteil() -> None:
    """Eine Frist <= 0 waere ein stilles Dauer-Rot -- das ist ein Konfigurationsfehler."""
    with pytest.raises(ValueError):
        _urteil(max_age=timedelta(0))
    with pytest.raises(ValueError):
        _urteil(max_age=timedelta(seconds=-1))


def test_negative_zukunftstoleranz_ist_ein_fehler() -> None:
    with pytest.raises(ValueError):
        _urteil(future_tolerance=timedelta(seconds=-1))


def test_frist_ist_kurz_genug_um_zwischenspeicherung_zu_fangen() -> None:
    """Die Begruendung der Frist ist Teil des Vertrags, nicht Geschmackssache.

    Wird sie auf Minuten gelockert, faengt der Latch einen zwischengespeicherten
    Kontostand nicht mehr -- genau den Fall, fuer den er existiert.
    """
    assert MAX_SNAPSHOT_AGE <= timedelta(seconds=10)
    assert FUTURE_TOLERANCE <= timedelta(seconds=2)

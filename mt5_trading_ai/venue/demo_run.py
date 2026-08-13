"""Paket 5: Registrierung und Fortschritts-Tor des Demo-Betriebs (§8.5).

Bevor irgendeine Live-Frage gestellt wird, laeuft die vorregistrierte Strategie
**mindestens sechs Monate** im Demo-Betrieb -- und nur, wenn sie den Edge-Test bestanden
hat. Dieses Modul haelt die Registrierung fest und prueft den Fortschritt; es
handelt nicht und oeffnet keine Order. Der eigentliche Lauf gegen ein Demo-MT5 ist Sache
des Betreibers (``venue/smoke.py``, ``allow_write`` nur auf einem Demokonto). Echtgeld
bleibt hart gesperrt.

Fail-closed: eine Strategie ohne bestandenen Edge-Test kommt nicht in den Demo-Betrieb.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from mt5_trading_ai.backtest.edge import EdgeVerdict

#: "mindestens sechs Monate" Demo, bevor eine Live-Frage ueberhaupt gestellt wird.
MIN_DEMO_DAYS = 180


class DemoGateError(ValueError):
    """Fail-closed: der Demo-Betrieb wurde verweigert."""


@dataclass(frozen=True)
class DemoRegistration:
    strategy_id: str
    version: str
    registered_on: date


def register_for_demo(
    *,
    strategy_id: str,
    version: str,
    edge_verdict: EdgeVerdict,
    registered_on: date,
) -> DemoRegistration:
    """Registriere eine Strategie fuer den Demo-Betrieb -- nur bei bestandenem Test.

    Das ist die Naht, die §8.5 an §7 bindet: ohne alle sechs Bedingungen bestanden gibt
    es keinen Demo-Betrieb, keine Vorstufe zu einer Live-Frage. Fail-closed.
    """
    if not strategy_id.strip() or not version.strip():
        raise DemoGateError("strategy_id und version sind Pflicht")
    if not edge_verdict.passed:
        raise DemoGateError(
            "Strategie hat den Edge-Test nicht bestanden -- kein Demo-Betrieb "
            f"(offen: {', '.join(edge_verdict.unmet) or 'unbekannt'})"
        )
    return DemoRegistration(
        strategy_id=strategy_id, version=version, registered_on=registered_on
    )


@dataclass(frozen=True)
class DemoReadiness:
    ready_for_live_question: bool
    reasons: tuple[str, ...]


def evaluate_demo_progress(
    *,
    registration: DemoRegistration,
    elapsed_days: int,
    live_verdict: EdgeVerdict,
) -> DemoReadiness:
    """Darf nach dem Demo-Betrieb ueberhaupt eine Live-Frage gestellt werden?

    Nur wenn der Demo-Betrieb mindestens sechs Monate lief **und** die sechs Bedingungen
    im Demo weiter erfuellt sind. Fail-closed. (Auch dann ist es nur die Erlaubnis, die
    Frage zu stellen -- die Live-Freigabe bleibt das vierteilige Tor, unberuehrt.)
    """
    reasons: list[str] = []
    if elapsed_days < MIN_DEMO_DAYS:
        reasons.append(f"demo_zu_kurz_{elapsed_days}_von_{MIN_DEMO_DAYS}_tagen")
    if not live_verdict.passed:
        reasons.append("live_demo_verfehlt_sechs_bedingungen")
    return DemoReadiness(ready_for_live_question=not reasons, reasons=tuple(reasons))

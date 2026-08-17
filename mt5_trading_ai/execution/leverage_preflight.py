"""Anschluss der Hebelklammer an den Order-Pfad.

``risk/leverage.py`` klammert den Hebel je Anlageklasse (``min(want, 10, Deckel)``;
eine unbekannte Anlageklasse fuehrt zu ``no_trade``, jeder legale Deckel ist
handelbar — es gibt kein Betriebsminimum, E2). Dieses Modul verbindet die Klammer
mit einem konkreten Instrument, Konto und Auftrag: es entscheidet, ob eine
**eroeffnende** Order zulaessig ist, mit welchem effektiven Hebel, und ob die
dafuer noetige Marge frei ist.

Fail-closed: was nicht sicher zulaessig ist, wird nicht freigegeben. ``no_trade``
der Klammer (unbekannte Anlageklasse) oder eine nicht ausreichende freie Marge
fuehren zu ``approved=False`` — ohne Default.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from mt5_trading_ai.risk.leverage import (
    LeverageDecision,
    LeveragePolicy,
    clamp_leverage,
)
from mt5_trading_ai.venue.protocol import AccountState, Instrument, OrderRequest


@dataclass(frozen=True)
class LeveragePreflight:
    """Ergebnis des Hebel-Anschlusses. ``approved`` nur bei sicherer Zulaessigkeit."""

    approved: bool
    effective_leverage: int | None
    required_margin: Decimal | None
    reason: str | None
    leverage: LeverageDecision


def evaluate_leverage_preflight(
    *,
    instrument: Instrument,
    request: OrderRequest,
    account: AccountState,
    price: Decimal,
    requested_leverage: Any = None,
    policy: LeveragePolicy | None = None,
) -> LeveragePreflight:
    """Klammere den Hebel und pruefe die Marge fuer eine eroeffnende Order.

    ``requested_leverage`` ist der Strategiewunsch; fehlt er, waehlt die Klammer
    ihren konservativen Default, nie den gefaehrlichsten Wert. ``price`` ist der
    Preis, gegen den die Marge gerechnet wird (in Kontowaehrung je Kontrakt).
    """
    decision = clamp_leverage(
        requested=requested_leverage,
        asset_class=instrument.asset_class.value,
        policy=policy,
    )
    if decision.no_trade or decision.leverage is None:
        return LeveragePreflight(
            approved=False,
            effective_leverage=None,
            required_margin=None,
            reason=decision.reason or "no_trade",
            leverage=decision,
        )
    if price <= 0:
        return LeveragePreflight(
            approved=False,
            effective_leverage=decision.leverage,
            required_margin=None,
            reason="invalid_price",
            leverage=decision,
        )
    # Der Hebel des KONTOS ist eine harte Obergrenze. Keine Politik kann sich mehr
    # nehmen, als der Broker gewaehrt -- und wer die Marge mit dem gewuenschten Hebel
    # rechnet, laesst Positionen zu, die der Broker mit "No money" ablehnt. Gemessen
    # an einem Demokonto mit 1:1: 0,71 Lot EURUSD galten hier als gedeckt
    # (71.000 / 5 = 14.200 gegen 50.000 frei), verlangten beim Broker aber die vollen
    # 71.000 und fielen erst beim Senden aus.
    #
    # ``None`` heisst unbekannt: dann bleibt es beim geklammerten Wunsch. Ein
    # Handelsplatz, der seinen Kontohebel nicht meldet, soll nicht schlechter
    # dastehen als vorher -- aber der echte MT5-Pfad meldet ihn.
    wirksam = decision.leverage
    if account.leverage is not None and account.leverage > 0:
        wirksam = min(wirksam, account.leverage)

    notional = request.volume * instrument.contract_size * price
    required_margin = notional / Decimal(wirksam)
    if required_margin > account.margin_free:
        return LeveragePreflight(
            approved=False,
            effective_leverage=wirksam,
            required_margin=required_margin,
            reason="insufficient_margin",
            leverage=decision,
        )
    return LeveragePreflight(
        approved=True,
        effective_leverage=wirksam,
        required_margin=required_margin,
        reason=None,
        leverage=decision,
    )

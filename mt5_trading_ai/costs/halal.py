"""Der Halal-Pfad: swapfreie Finanzierung ohne Zins (S4, Kernregel 16).

Gehebelte CFDs kollidieren am Overnight-Swap mit dem Zinsverbot (riba): der Swap ist
Zins -- gezahlt (negativer Swap) und, bei positivem Swap, als Gutschrift **erhalten**.
Genau diese Gutschrift blaehte im zweiten Edge-Versuch das Ergebnis auf (+0,74 pp reiner
Short-Carry). Dieser Modul liefert die Alternative: eine swapfreie Politik ohne jeden
Zins -- weder gezahlt noch erhalten -- mit einer pauschalen Verwaltungsgebuehr je Nacht
(Dienstleistungsgebuehr, nicht zinsbasiert). Kein Dreifach-Tag (ein Rollover-Artefakt).

Was dieser Modul **nicht** tut: er entscheidet nicht die fiqh-Grundfrage, ob gehebelte
CFDs ueberhaupt zulaessig sind (gharar). Das ist eine Gelehrten-/Philipp-Entscheidung
(Kernregel 16, "nicht allein entscheiden"); ``venue/halal.py`` markiert sie stets.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

HALAL_POLICY_VERSION = "halal-financing-v1"


@dataclass(frozen=True)
class HalalFinancingPolicy:
    """Swapfrei: kein Zins, stattdessen pauschale Gebuehr je Nacht nach Karenz.

    ``admin_fee_per_lot_per_night`` ist eine **Schaetzung** (Broker bestaetigen);
    ein fixer Dienstleistungspreis, **nicht** zinsbasiert. Nie negativ -- eine swapfreie
    Politik zahlt keinen Zins aus.
    """

    grace_nights: int = 0
    admin_fee_per_lot_per_night: Decimal = Decimal("5.00")

    def __post_init__(self) -> None:
        if self.grace_nights < 0:
            raise ValueError("grace_nights darf nicht negativ sein")
        if self.admin_fee_per_lot_per_night < 0:
            # Nie negativ -> nie Gutschrift -> nie riba-Ertrag. Der Kern der Politik.
            raise ValueError("admin_fee darf nicht negativ sein (waere riba-Ertrag)")


def halal_financing(
    policy: HalalFinancingPolicy, volume: Decimal, holding_nights: int
) -> Decimal:
    """Pauschale Gebuehr, **immer >= 0** (nie Gutschrift, nie riba). Kein Dreifach."""
    if holding_nights < 0:
        raise ValueError("holding_nights darf nicht negativ sein")
    charged = max(0, holding_nights - policy.grace_nights)
    return policy.admin_fee_per_lot_per_night * volume * Decimal(charged)

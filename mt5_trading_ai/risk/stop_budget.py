"""Stop-Budget je Anlageklasse — hergeleitet, nicht uebertragen (Phase 6.5).

Die alte Kurve (7x -> 100 bp, 75x -> 10 bp) stammt aus Krypto-Perpetual-Kosten
und aus der Liquidationsnaehe bei 75x. Beides gilt hier nicht mehr. Diese Datei
leitet das Budget neu her, aus zwei Groessen, die je Klasse verschieden sind.

**Untergrenze — aus den Kosten.** Bei einem Chancen-Risiko-Verhaeltnis von 1:1,
Stopdistanz ``R`` und Round-Turn-Kosten ``C`` liegt die Trefferquote am
Nulldurchgang bei

    p = 0,5 + C / (2R)

Fordert man, dass die Kosten den Nulldurchgang um hoechstens ``max_cost_drag``
anheben (Default 5 Prozentpunkte, also p <= 55 %), folgt

    R >= C / (2 · max_cost_drag)          Default: R >= 10 · C

Ein Stop unterhalb dieser Distanz macht die Klasse rechnerisch unhandelbar —
unabhaengig davon, wie gut das Signal ist.

**Obergrenze — aus der Margin.** Der Hebel bestimmt, wie weit der Preis laufen
darf, bevor der Margin-Close-out greift. Bei Kleinanlegern in der EU schliesst
der Broker bei 50 % der Ersteinschusszahlung; das entspricht einer
Gegenbewegung von ``0,5 / L``. Mit einem Sicherheitsfaktor ``safety`` (Default 3)
gilt

    R <= 0,5 / (L · safety)

| Hebel | Close-out-Abstand | Obergrenze bei safety = 3 |
|---|---|---|
| 5x  | 1000 bp | **333 bp** |
| 10x |  500 bp | **167 bp** |

Der Hebel wirkt also nur noch auf die **Obergrenze** und nicht mehr, wie in der
alten Kurve, auf einen einzigen Zielwert. Das ist der inhaltliche Unterschied:
enge Stops entstehen hier aus Kosten und Ausfuehrbarkeit, nicht aus
Liquidationsangst.

Ist die Untergrenze groesser als die Obergrenze, ist die Kombination aus Klasse
und Hebel nicht handelbar: ``no_trade``, keine Aufweichung.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

STOP_BUDGET_POLICY_VERSION = "stop-budget-v2-per-class"

#: Round-Turn-Kosten je Klasse in Basispunkten. **Annahmen**, keine Messungen —
#: vor dem ersten Backtest gegen den Demo-Feed des gewaehlten Brokers zu ersetzen
#: (Phase 7.3, geschichtete Stichprobe).
ASSUMED_ROUND_TURN_COST_BPS: dict[str, Decimal] = {
    "fx_major": Decimal("0.65"),
    "fx_minor": Decimal("4.0"),
    "gold": Decimal("1.5"),
    "index_major": Decimal("1.5"),
    "index_minor": Decimal("5.0"),
    "commodity_non_gold": Decimal("7.0"),
    "equity": Decimal("20.0"),
    "crypto": Decimal("40.0"),
}

#: Margin-Close-out fuer Kleinanleger in der EU: 50 % der Ersteinschusszahlung.
MARGIN_CLOSE_OUT_FRACTION = Decimal("0.5")


@dataclass(frozen=True)
class StopBudget:
    lower_bps: Decimal
    upper_bps: Decimal
    cost_bps: Decimal
    asset_class: str
    leverage: int
    tradeable: bool
    reason: str | None
    policy_version: str = STOP_BUDGET_POLICY_VERSION
    cost_is_measured: bool = False

    def allows(self, stop_bps: Decimal) -> bool:
        return self.tradeable and self.lower_bps <= stop_bps <= self.upper_bps


def cost_floor_bps(
    cost_bps: Decimal, *, max_cost_drag: Decimal = Decimal("0.05")
) -> Decimal:
    """Kleinste Stopdistanz, bei der die Kosten den Nulldurchgang
    um hoechstens ``max_cost_drag`` anheben.
    """
    if max_cost_drag <= 0:
        raise ValueError("max_cost_drag muss positiv sein")
    return cost_bps / (2 * max_cost_drag)


def margin_ceiling_bps(leverage: int, *, safety: Decimal = Decimal("3")) -> Decimal:
    """Groesste Stopdistanz mit Abstand zum Margin-Close-out."""
    if leverage <= 0:
        raise ValueError("leverage muss positiv sein")
    if safety <= 0:
        raise ValueError("safety muss positiv sein")
    return MARGIN_CLOSE_OUT_FRACTION * Decimal("10000") / (Decimal(leverage) * safety)


def stop_budget(
    *,
    asset_class: str,
    leverage: int,
    measured_cost_bps: Decimal | None = None,
    max_cost_drag: Decimal = Decimal("0.05"),
    safety: Decimal = Decimal("3"),
) -> StopBudget:
    """Budgetspanne je Klasse und Hebel. Gemessene Kosten schlagen Annahmen."""
    key = str(asset_class).strip().lower()
    measured = measured_cost_bps is not None
    cost = measured_cost_bps if measured else ASSUMED_ROUND_TURN_COST_BPS.get(key)

    if cost is None:
        return StopBudget(
            lower_bps=Decimal("0"),
            upper_bps=Decimal("0"),
            cost_bps=Decimal("0"),
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="unknown_asset_class",
            cost_is_measured=False,
        )

    lower = cost_floor_bps(cost, max_cost_drag=max_cost_drag)
    upper = margin_ceiling_bps(leverage, safety=safety)

    if lower > upper:
        return StopBudget(
            lower_bps=lower,
            upper_bps=upper,
            cost_bps=cost,
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="cost_floor_above_margin_ceiling",
            cost_is_measured=measured,
        )

    return StopBudget(
        lower_bps=lower,
        upper_bps=upper,
        cost_bps=cost,
        asset_class=key,
        leverage=leverage,
        tradeable=True,
        reason=None,
        cost_is_measured=measured,
    )


def breakeven_hit_rate(*, cost_bps: Decimal, stop_bps: Decimal) -> Decimal:
    """Trefferquote am Nulldurchgang bei 1:1. Haengt nicht vom Hebel ab."""
    if stop_bps <= 0:
        raise ValueError("stop_bps muss positiv sein")
    return Decimal("0.5") + cost_bps / (2 * stop_bps)

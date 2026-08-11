"""Risiko je Trade, ausfuehrbarer Stop-Floor und Positionsgroesse (Phase 6.2/6.3).

Die Reihenfolge ist der Kern und nicht verhandelbar:

1. **Stop-Floor** aus Spread, Ticksize, Volatilitaet, Tiefe **und dem
   Mindeststop-Abstand des Brokers**. Der Broker-Abstand kann alle anderen
   dominieren; er ist keine Feinheit, sondern haeufig der bindende Wert.
2. **Stop-Budget** je Anlageklasse. Ist der Floor groesser als das Budget:
   ``no_trade``. **Nicht** „Stop weiter setzen" — ein weiter gesetzter Stop ist
   ein anderer Trade als der bewertete.
3. **Positionsgroesse** folgt aus Risikoanteil und Stopabstand, nicht umgekehrt.
4. **Hebel** kommt zuletzt und begrenzt nur, wie viel Kapital gebunden wird.
   Er begrenzt kein Risiko.

Abrunden statt Aufrunden ist Absicht: Aufrunden auf den naechsten Volumenschritt
erhoeht das Risiko ueber das Budget hinaus. Wenn die abgerundete Groesse unter
dem Mindestvolumen liegt, ist das ``no_trade`` und kein Anlass, das Budget zu
dehnen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from typing import Any

RISK_SIZING_VERSION = "risk-sizing-v1"

#: Risikoanteil je Trade. Default am unteren Rand des zulaessigen Bereichs.
MIN_RISK_FRACTION = Decimal("0.0025")
MAX_RISK_FRACTION = Decimal("0.005")
DEFAULT_RISK_FRACTION = MIN_RISK_FRACTION


class RiskSizingError(ValueError):
    """Eingaben sind unbrauchbar. Fail-closed: kein Handel."""


@dataclass(frozen=True)
class StopFloorInputs:
    """Alles in Basispunkten des Preises, ausser wo anders vermerkt."""

    spread_bps: Decimal
    tick_size_bps: Decimal
    volatility_bps: Decimal
    #: Mindestabstand des Brokers, bereits in bps umgerechnet.
    broker_stop_level_bps: Decimal
    #: Verhaeltnis verfuegbarer Tiefe zur geplanten Groesse; ``None`` = unbekannt.
    depth_ratio: float | None = None


@dataclass(frozen=True)
class StopFloor:
    executable_floor_bps: Decimal
    binding: str
    components: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class SizingResult:
    volume: Decimal | None
    stop_floor_bps: Decimal
    stop_budget_bps: Decimal
    stop_distance_bps: Decimal
    risk_fraction: Decimal
    risk_currency: Decimal
    notional: Decimal | None
    margin_required: Decimal | None
    leverage: int | None
    reasons: tuple[str, ...]
    version: str = RISK_SIZING_VERSION

    @property
    def no_trade(self) -> bool:
        return self.volume is None


def normalise_risk_fraction(value: Any) -> Decimal:
    """Klammert auf ``[0,25 %, 0,5 %]``. Fehlender Wert -> unterer Rand."""
    if value in (None, ""):
        return DEFAULT_RISK_FRACTION
    try:
        fraction = Decimal(str(value))
    except (TypeError, ArithmeticError) as exc:
        raise RiskSizingError(f"Risikoanteil unbrauchbar: {value!r}") from exc
    if fraction <= 0:
        raise RiskSizingError("Risikoanteil muss positiv sein")
    return max(MIN_RISK_FRACTION, min(MAX_RISK_FRACTION, fraction))


def executable_stop_floor(
    inputs: StopFloorInputs,
    *,
    spread_multiplier: Decimal = Decimal("2.5"),
    tick_multiplier: Decimal = Decimal("2.0"),
    volatility_multiplier: Decimal = Decimal("0.22"),
) -> StopFloor:
    """Der groesste der Einzelfloors gewinnt. Der Broker-Abstand ist einer davon."""
    components: dict[str, Decimal] = {
        "spread": max(Decimal("0"), inputs.spread_bps) * spread_multiplier,
        "tick": max(Decimal("0"), inputs.tick_size_bps) * tick_multiplier,
        "volatility": max(Decimal("0"), inputs.volatility_bps) * volatility_multiplier,
        "broker_stop_level": max(Decimal("0"), inputs.broker_stop_level_bps),
    }
    if inputs.depth_ratio is None:
        # Unbekannte Tiefe ist nicht „ausreichende Tiefe".
        components["depth"] = Decimal("15")
    elif inputs.depth_ratio < 0.35:
        components["depth"] = Decimal("15")
    elif inputs.depth_ratio < 0.55:
        components["depth"] = Decimal("8")
    else:
        components["depth"] = Decimal("0")

    binding = max(components, key=lambda name: components[name])
    return StopFloor(
        executable_floor_bps=components[binding],
        binding=binding,
        components=components,
    )


def _quantise_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise RiskSizingError("volume_step muss positiv sein")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def size_position(
    *,
    account_equity: Decimal,
    risk_fraction: Any,
    stop_floor_bps: Decimal,
    stop_budget_bps: Decimal,
    requested_stop_bps: Decimal | None,
    price: Decimal,
    contract_size: Decimal,
    volume_min: Decimal,
    volume_step: Decimal,
    volume_max: Decimal | None,
    leverage: int | None,
) -> SizingResult:
    """Positionsgroesse aus Risikoanteil und Stopabstand."""
    reasons: list[str] = []
    fraction = normalise_risk_fraction(risk_fraction)

    if account_equity <= 0:
        reasons.append("equity_missing")
    if price <= 0:
        reasons.append("price_missing")
    if contract_size <= 0:
        reasons.append("contract_size_missing")
    if leverage is None:
        reasons.append("leverage_no_trade")

    stop_distance = max(stop_floor_bps, requested_stop_bps or Decimal("0"))

    if stop_floor_bps > stop_budget_bps:
        # Kein Ausweichen auf einen weiteren Stop: das waere ein anderer Trade.
        reasons.append("stop_floor_exceeds_budget")
    elif stop_distance > stop_budget_bps:
        reasons.append("requested_stop_exceeds_budget")

    risk_currency = (account_equity * fraction) if account_equity > 0 else Decimal("0")

    if reasons or stop_distance <= 0:
        if stop_distance <= 0:
            reasons.append("stop_distance_zero")
        return SizingResult(
            volume=None,
            stop_floor_bps=stop_floor_bps,
            stop_budget_bps=stop_budget_bps,
            stop_distance_bps=stop_distance,
            risk_fraction=fraction,
            risk_currency=risk_currency,
            notional=None,
            margin_required=None,
            leverage=leverage,
            reasons=tuple(dict.fromkeys(reasons)),
        )

    stop_distance_price = price * stop_distance / Decimal("10000")
    raw_volume = risk_currency / (stop_distance_price * contract_size)
    volume = _quantise_down(raw_volume, volume_step)

    if volume_max is not None and volume > volume_max:
        volume = _quantise_down(volume_max, volume_step)
        reasons.append("volume_max_binding")

    if volume < volume_min:
        # Aufrunden wuerde das Risikobudget ueberschreiten.
        reasons.append("below_volume_min")
        return SizingResult(
            volume=None,
            stop_floor_bps=stop_floor_bps,
            stop_budget_bps=stop_budget_bps,
            stop_distance_bps=stop_distance,
            risk_fraction=fraction,
            risk_currency=risk_currency,
            notional=None,
            margin_required=None,
            leverage=leverage,
            reasons=tuple(dict.fromkeys(reasons)),
        )

    notional = volume * contract_size * price
    margin = notional / Decimal(leverage) if leverage else None

    return SizingResult(
        volume=volume,
        stop_floor_bps=stop_floor_bps,
        stop_budget_bps=stop_budget_bps,
        stop_distance_bps=stop_distance,
        risk_fraction=fraction,
        risk_currency=risk_currency,
        notional=notional,
        margin_required=margin,
        leverage=leverage,
        reasons=tuple(dict.fromkeys(reasons)),
    )

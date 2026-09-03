"""Order-Lebenszyklus und Reconcile: Konto gegen Buch.

Der Handelsplatz fuehrt ein lokales **Buch** der Nettopositionen je Symbol (was das
System zu halten glaubt, aus den angenommenen Fills). Reconcile vergleicht das Buch mit
dem, was der Handelsplatz tatsaechlich meldet.

Weicht beides ueber die Toleranz ab, ist der sichere Zustand ein **Halt**: keine neuen
Eroeffnungen, bis ein Mensch die Divergenz aufloest. Fail-closed in zwei Richtungen:
eine Notional-Drift ueber der Grenze haelt an, und eine **nicht bewertbare** Drift (kein
Preis fuers Symbol) haelt ebenfalls an — Unwissen ist kein Grund weiterzuhandeln.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal

from mt5_trading_ai.venue.protocol import OrderSide, Position


class PositionBook:
    """Lokales Buch der Nettopositionen je Symbol (long positiv, short negativ)."""

    def __init__(self) -> None:
        self._net: dict[str, Decimal] = {}

    def apply_fill(self, symbol: str, side: OrderSide, volume: Decimal) -> None:
        signed = volume if side is OrderSide.BUY else -volume
        self._net[symbol] = self._net.get(symbol, Decimal("0")) + signed

    def net(self, symbol: str) -> Decimal:
        return self._net.get(symbol, Decimal("0"))

    def snapshot(self) -> dict[str, Decimal]:
        return {symbol: net for symbol, net in self._net.items() if net != 0}

    def adopt(self, net_by_symbol: Mapping[str, Decimal]) -> None:
        """Ersetze das Buch durch die gegebenen Nettopositionen (Neustart-Adoption)."""
        self._net = {symbol: net for symbol, net in net_by_symbol.items() if net != 0}


def positions_to_net(positions: Iterable[Position]) -> dict[str, Decimal]:
    """Fasse gemeldete Positionen zu einer Nettomenge je Symbol zusammen."""
    net: dict[str, Decimal] = {}
    for pos in positions:
        signed = pos.volume if pos.side is OrderSide.BUY else -pos.volume
        net[pos.symbol] = net.get(pos.symbol, Decimal("0")) + signed
    return {symbol: value for symbol, value in net.items() if value != 0}


@dataclass(frozen=True)
class SymbolDrift:
    symbol: str
    expected: Decimal
    actual: Decimal
    volume_drift: Decimal
    #: ``None`` heisst: nicht bewertbar (kein Preis) — fail-closed.
    notional_drift: Decimal | None


@dataclass(frozen=True)
class ReconcileResult:
    matched: bool
    halt: bool
    reason: str | None
    drifts: tuple[SymbolDrift, ...]
    total_notional_drift: Decimal


def reconcile_positions(
    *,
    expected: Mapping[str, Decimal],
    actual: Mapping[str, Decimal],
    notional_per_unit: Mapping[str, Decimal],
    max_notional_drift: Decimal,
    volume_tolerance: Decimal = Decimal("0"),
) -> ReconcileResult:
    """Vergleiche Buch (``expected``) mit Meldung (``actual``).

    ``notional_per_unit`` bewertet eine Volumeneinheit je Symbol (Kontraktgroesse mal
    Preis). Eine Drift ueber ``max_notional_drift`` oder eine nicht bewertbare Drift
    fuehrt zu ``halt=True``.
    """
    drifts: list[SymbolDrift] = []
    total = Decimal("0")
    unpriced = False
    for symbol in sorted(set(expected) | set(actual)):
        exp = expected.get(symbol, Decimal("0"))
        act = actual.get(symbol, Decimal("0"))
        volume_drift = act - exp
        if abs(volume_drift) <= volume_tolerance:
            continue
        per_unit = notional_per_unit.get(symbol)
        if per_unit is None:
            drifts.append(SymbolDrift(symbol, exp, act, volume_drift, None))
            unpriced = True
            continue
        notional = abs(volume_drift) * per_unit
        total += notional
        drifts.append(SymbolDrift(symbol, exp, act, volume_drift, notional))

    if not drifts:
        return ReconcileResult(True, False, None, (), Decimal("0"))
    if unpriced:
        return ReconcileResult(False, True, "unpriced_drift", tuple(drifts), total)
    if total > max_notional_drift:
        return ReconcileResult(
            False, True, "notional_drift_exceeds_limit", tuple(drifts), total
        )
    return ReconcileResult(False, False, "within_notional_limit", tuple(drifts), total)

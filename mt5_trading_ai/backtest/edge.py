"""Das Sechs-Bedingungen-Tor des Edge-Tests (Paket 4, §7.2).

Vorab gesetzt, nicht verhandelbar. **ALLE sechs** muessen erfuellt sein; eines reicht.
Ein sauberes Nein ist der auftragsgemaesse Ausgang, kein Scheitern: 74-89 % der Retail-
Konten verlieren (ESMA), unter 1 % sind nach Kosten dauerhaft profitabel -- das negative
Ergebnis ist das statistisch erwartete.

Ausdruecklich untersagt (hier nicht moeglich): die Schwelle senken, den Zeitraum aendern
bis es passt, oder das Ergebnis als "grundsaetzlich vielversprechend" beschreiben.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

EDGE_GATE_VERSION = "edge-gate-v1"


@dataclass(frozen=True)
class EdgeThresholds:
    """Die vorab gesetzten Schwellen. Nach dem ersten Lauf unveraenderlich."""

    min_oos_sharpe: float = 1.0
    min_deflated_sharpe: float = 0.95
    min_trades: int = 2000
    min_consecutive_positive_folds: int = 3


@dataclass(frozen=True)
class EdgeCheck:
    name: str
    met: bool
    observed: Any
    required: str


@dataclass(frozen=True)
class EdgeVerdict:
    passed: bool
    checks: tuple[EdgeCheck, ...]
    unmet: tuple[str, ...] = field(default_factory=tuple)
    version: str = EDGE_GATE_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "version": self.version,
            "unmet": list(self.unmet),
            "checks": [
                {"name": c.name, "met": c.met, "observed": c.observed,
                 "required": c.required}
                for c in self.checks
            ],
        }


def max_consecutive_positive(fold_returns: Sequence[float]) -> int:
    """Laengste Serie aufeinanderfolgender positiver Walk-Forward-Fenster."""
    best = run = 0
    for value in fold_returns:
        run = run + 1 if value > 0 else 0
        best = max(best, run)
    return best


def evaluate_edge(
    *,
    oos_sharpe: float,
    deflated_sharpe: float,
    trades: int,
    fold_returns: Sequence[float],
    net_over_hurdle: float,
    leakage_test_green: bool,
    random_reference_negative: bool,
    thresholds: EdgeThresholds | None = None,
) -> EdgeVerdict:
    """Pruefe alle sechs Bedingungen. Ein einziges Nein genuegt zum Gesamt-Nein."""
    t = thresholds or EdgeThresholds()
    consecutive = max_consecutive_positive(fold_returns)
    checks = (
        EdgeCheck(
            "oos_sharpe_after_costs", oos_sharpe >= t.min_oos_sharpe,
            oos_sharpe, f">= {t.min_oos_sharpe}",
        ),
        EdgeCheck(
            "deflated_sharpe_beats_threshold", deflated_sharpe > t.min_deflated_sharpe,
            deflated_sharpe, f"> {t.min_deflated_sharpe}",
        ),
        EdgeCheck(
            "trade_count", trades >= t.min_trades,
            trades, f">= {t.min_trades}",
        ),
        EdgeCheck(
            "consecutive_positive_folds",
            consecutive >= t.min_consecutive_positive_folds,
            consecutive, f">= {t.min_consecutive_positive_folds}",
        ),
        EdgeCheck(
            "clears_cost_hurdle", net_over_hurdle > 0,
            net_over_hurdle, "gross_return - hurdle > 0 (Kosten gedeckt)",
        ),
        EdgeCheck(
            "leakage_green_and_random_negative",
            bool(leakage_test_green and random_reference_negative),
            {"leakage_green": leakage_test_green,
             "random_negative": random_reference_negative},
            "beide wahr",
        ),
    )
    unmet = tuple(c.name for c in checks if not c.met)
    return EdgeVerdict(passed=not unmet, checks=checks, unmet=unmet)

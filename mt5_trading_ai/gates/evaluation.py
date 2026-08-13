"""Bewerten ist nicht handeln (Phase 8.3).

Ein 5-Sekunden-Bewertungstakt darf keine 5-Sekunden-Handelsfrequenz erzeugen.
Die Trennung ist hier als eigenes Modul ausgefuehrt, damit sie testbar ist und
nicht in der Bewertungsschleife verstreut liegt.

Fuenf Mechanismen, alle unabhaengig voneinander:

1. **Schwelle** — nur Bewertungen ueber ``score_threshold`` sind Kandidaten.
2. **Mindesthaltedauer** je Klasse — eine offene Position wird nicht sofort ersetzt.
3. **Abklingzeit** je Instrument — nach einem Trade ist dieses Instrument gesperrt.
4. **Obergrenzen** — Trades je Instrument und Tag, Trades je Konto und Tag,
   gleichzeitige Positionen.
5. **Rangliste statt Ausloesung** — aus allen Kandidaten eines Durchlaufs wird
   **einer** gewaehlt, nicht jeder ausgefuehrt.

Jede unterdrueckte Bewertung wird mit Begruendung zurueckgegeben und persistiert
(``decision='suppressed'``). Der Anteil der Bewertungen, die zu einem Trade
fuehren, ist damit messbar statt geschaetzt.

**Aufrufer (Paket 4):** ``execution/risk_manager.py`` fahrt ``select_one`` je
eroeffnende Live-Order (Einzelkandidat) als Drossel -- Cooldown, Mindesthaltedauer,
Tageskappen und Positionsdeckel greifen. Die Auswahl aus mehreren Kandidaten wird erst
mit einer echten Bewertungsschleife wirksam (siehe ``SPAETER.md`` S12).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

EVALUATION_GATE_VERSION = "evaluation-gate-v1"


@dataclass(frozen=True)
class ThrottlePolicy:
    """Alle Werte je Anlageklasse konfigurierbar, Defaults konservativ."""

    score_threshold: float = 75.0
    min_hold: timedelta = timedelta(minutes=15)
    cooldown_per_instrument: timedelta = timedelta(minutes=30)
    max_trades_per_instrument_per_day: int = 3
    max_trades_per_account_per_day: int = 10
    max_concurrent_positions: int = 3
    #: Zwei Positionen mit einer Korrelation darueber sind dieselbe Wette.
    max_correlation: float = 0.7


@dataclass(frozen=True)
class Candidate:
    instrument: str
    asset_class: str
    score: float
    evaluation_id: int | None = None
    #: Korrelationen zu bereits offenen Positionen, Instrument -> |rho|.
    correlations: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenPosition:
    instrument: str
    opened_at: datetime


@dataclass(frozen=True)
class GateState:
    now: datetime
    open_positions: tuple[OpenPosition, ...] = ()
    last_trade_at: dict[str, datetime] = field(default_factory=dict)
    trades_today_per_instrument: dict[str, int] = field(default_factory=dict)
    trades_today_account: int = 0


@dataclass(frozen=True)
class GateDecision:
    """Ein Kandidat und warum er ausgewaehlt oder unterdrueckt wurde."""

    instrument: str
    selected: bool
    reasons: tuple[str, ...]
    score: float
    evaluation_id: int | None = None


@dataclass(frozen=True)
class GateResult:
    selected: GateDecision | None
    suppressed: tuple[GateDecision, ...]
    version: str = EVALUATION_GATE_VERSION

    @property
    def decisions(self) -> tuple[GateDecision, ...]:
        if self.selected is None:
            return self.suppressed
        return (self.selected, *self.suppressed)


def _blocking_reasons(
    candidate: Candidate,
    state: GateState,
    policy: ThrottlePolicy,
) -> list[str]:
    reasons: list[str] = []

    if candidate.score < policy.score_threshold:
        reasons.append("below_threshold")

    last = state.last_trade_at.get(candidate.instrument)
    if last is not None and state.now - last < policy.cooldown_per_instrument:
        reasons.append("cooldown_active")

    for position in state.open_positions:
        if position.instrument != candidate.instrument:
            continue
        if state.now - position.opened_at < policy.min_hold:
            reasons.append("min_hold_not_reached")
            break

    per_instrument = state.trades_today_per_instrument.get(candidate.instrument, 0)
    if per_instrument >= policy.max_trades_per_instrument_per_day:
        reasons.append("instrument_daily_cap")

    if state.trades_today_account >= policy.max_trades_per_account_per_day:
        reasons.append("account_daily_cap")

    already_open = {position.instrument for position in state.open_positions}
    if candidate.instrument not in already_open:
        if len(state.open_positions) >= policy.max_concurrent_positions:
            reasons.append("concurrent_position_cap")

    for other, rho in candidate.correlations.items():
        if other in already_open and abs(rho) > policy.max_correlation:
            reasons.append(f"correlated_with:{other}")

    return reasons


def select_one(
    candidates: Sequence[Candidate],
    state: GateState,
    policy: ThrottlePolicy,
) -> GateResult:
    """Aus allen Kandidaten eines Durchlaufs wird hoechstens **einer** gewaehlt.

    Rangfolge: hoechster Score. Bei Gleichstand entscheidet der Instrumentenname,
    damit die Auswahl deterministisch ist und ein Backtest reproduzierbar bleibt.
    """
    evaluated: list[tuple[Candidate, list[str]]] = [
        (candidate, _blocking_reasons(candidate, state, policy))
        for candidate in candidates
    ]

    eligible = [(candidate, reasons) for candidate, reasons in evaluated if not reasons]
    eligible.sort(key=lambda item: (-item[0].score, item[0].instrument))

    selected: GateDecision | None = None
    suppressed: list[GateDecision] = []

    for index, (candidate, _) in enumerate(eligible):
        if index == 0:
            selected = GateDecision(
                instrument=candidate.instrument,
                selected=True,
                reasons=(),
                score=candidate.score,
                evaluation_id=candidate.evaluation_id,
            )
        else:
            suppressed.append(
                GateDecision(
                    instrument=candidate.instrument,
                    selected=False,
                    reasons=("not_top_ranked",),
                    score=candidate.score,
                    evaluation_id=candidate.evaluation_id,
                )
            )

    for candidate, reasons in evaluated:
        if not reasons:
            continue
        suppressed.append(
            GateDecision(
                instrument=candidate.instrument,
                selected=False,
                reasons=tuple(reasons),
                score=candidate.score,
                evaluation_id=candidate.evaluation_id,
            )
        )

    suppressed.sort(key=lambda decision: (-decision.score, decision.instrument))
    return GateResult(selected=selected, suppressed=tuple(suppressed))


def trade_rate(decisions: Iterable[GateDecision]) -> float:
    """Anteil der Bewertungen, die zu einem Trade fuehren. Soll klein sein."""
    total = 0
    traded = 0
    for decision in decisions:
        total += 1
        if decision.selected:
            traded += 1
    if total == 0:
        return 0.0
    return traded / total

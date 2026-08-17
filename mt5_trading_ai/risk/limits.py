"""Verlustgrenzen und das **Kriterium** des Kill-Switch (Phase 6.4).

WAS DIESES MODUL TRAEGT -- UND WAS NICHT (Paket 2, A3.5)
--------------------------------------------------------
Die Kopfzeile hiess frueher schlicht „Verlustgrenzen und Kill-Switch", waehrend
``FEHLT.md`` §7 den Kill-Switch als **nicht mitgekommen** fuehrte. Gemessen ist beides
halb richtig, und die Praezisierung steht darum hier:

* **Hier** liegt das *Kriterium* und der *Zustand*: wann gehalten wird
  (``max_drawdown_fraction``), wann nur noch abgebaut wird
  (``max_daily_loss_fraction``),
  und die Zustaende ``NORMAL`` / ``REDUCE_ONLY`` / ``HALTED``. Auch die *Freigabe*-Kante
  ist hier: ``AccountSnapshot.manual_release_id``. Das Modul ist eine reine Funktion --
  es **haelt** nichts.
* **Nicht hier** liegt der *Latch* und der *Griff*: ``Mt5Venue._halted`` mit
  ``latch_halt()`` (Hand anlegen), ``clear_halt()`` (Freigabe) und
  ``emergency_flatten()`` (Not-Aus mit Reduce-Only-Glattstellung). Ein Zustand, der
  sich nicht von selbst loest, braucht einen Halter; der Halter ist das Venue.
* ``execution/risk_manager.py`` verbindet beides: es ruft ``evaluate_limits``, meldet
  ``latch_halt=True`` nach oben und traegt die Freigabe (``release_drawdown``).

Der Kill-Switch **existiert** also, verteilt auf diese drei Stellen. Was aus §7 offen
bleibt, ist der uebrige Fail-Closed-Apparat: Runtime-Safety-Oracle und
Exchange-Readiness. Belegt von ``tests/test_orderpfad_verdrahtung.py``.

DIE VIER GRENZEN
----------------
Vier unabhaengige Grenzen. Jede greift fuer sich; keine hebt eine andere auf.

* **Tagesverlustlimit** — erreicht: keine neuen Positionen, bestehende nur reduzieren.
* **Maximaler Drawdown** ueber ein rollierendes Fenster — erreicht: Halt, und der
  Halt loest sich **nicht** von selbst. Er braucht eine manuelle Freigabe.
* **Maximale gleichzeitige Positionen.**
* **Gap-Regel** vor Wochenenden, Rollterminen und angekuendigten Ereignissen.

Der Unterschied zwischen den ersten beiden ist wesentlich: das Tageslimit setzt
sich mit dem naechsten Handelstag zurueck, der Drawdown-Halt nicht. Ein System,
das sich nach einem Drawdown-Halt selbst wieder freischaltet, hat keinen Halt.

**Aufrufer (Paket 4):** ``execution/risk_manager.py`` fahrt ``evaluate_limits`` fuer
jede eroeffnende Live-Order; ein Drawdown-Halt setzt den ``_halted``-Latch des Venue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

LOSS_LIMIT_POLICY_VERSION = "loss-limits-v1"


class TradingState(str, Enum):
    NORMAL = "normal"
    #: Keine neuen Positionen, bestehende nur reduzieren.
    REDUCE_ONLY = "reduce_only"
    #: Halt. Loest sich nicht von selbst.
    HALTED = "halted"


@dataclass(frozen=True)
class LossLimits:
    max_daily_loss_fraction: Decimal = Decimal("0.02")
    max_drawdown_fraction: Decimal = Decimal("0.10")
    drawdown_window: timedelta = timedelta(days=30)
    max_concurrent_positions: int = 3
    #: Kein Eroeffnen innerhalb dieser Spanne vor einem bekannten Gap-Ereignis.
    gap_blackout: timedelta = timedelta(hours=4)


@dataclass(frozen=True)
class AccountSnapshot:
    now: datetime
    equity: Decimal
    day_start_equity: Decimal
    #: Hoechster Kontostand im rollierenden Fenster.
    window_peak_equity: Decimal
    open_positions: int
    trading_day: date
    #: Manuell erteilte Freigabe nach einem Drawdown-Halt. Ohne sie bleibt der Halt.
    manual_release_id: str | None = None
    #: Bekannte Gap-Ereignisse (Wochenende, Rolltermin, Earnings), UTC.
    upcoming_gap_events: tuple[datetime, ...] = ()


@dataclass(frozen=True)
class LimitDecision:
    state: TradingState
    reasons: tuple[str, ...]
    daily_loss_fraction: Decimal
    drawdown_fraction: Decimal
    policy_version: str = LOSS_LIMIT_POLICY_VERSION
    detail: dict[str, str] = field(default_factory=dict)

    @property
    def may_open(self) -> bool:
        return self.state is TradingState.NORMAL

    @property
    def may_reduce(self) -> bool:
        """Immer True.

        Risikoabbau bleibt in jedem Zustand moeglich, auch im Halt. Eine Grenze,
        die das Schliessen einer offenen Position verhindert, erhoeht das Risiko
        statt es zu senken; ein Stop, der wegen eines Verlustlimits nicht
        ausgefuehrt werden darf, ist kein Stop. Der Unterschied zwischen
        ``REDUCE_ONLY`` und ``HALTED`` liegt nicht im Abbau, sondern in der
        Dauer: ``REDUCE_ONLY`` endet mit dem Handelstag, ``HALTED`` erst mit
        einer ausdruecklichen menschlichen Freigabe.
        """
        return True


def _fraction(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        # Nicht bewertbar -> als voll ausgeschoepft behandeln, nicht als null.
        return Decimal("1")
    return numerator / denominator


def evaluate_limits(
    snapshot: AccountSnapshot,
    limits: LossLimits,
) -> LimitDecision:
    reasons: list[str] = []

    daily_loss = max(Decimal("0"), snapshot.day_start_equity - snapshot.equity)
    daily_fraction = _fraction(daily_loss, snapshot.day_start_equity)

    drawdown = max(Decimal("0"), snapshot.window_peak_equity - snapshot.equity)
    drawdown_fraction = _fraction(drawdown, snapshot.window_peak_equity)

    state = TradingState.NORMAL

    if drawdown_fraction >= limits.max_drawdown_fraction:
        if snapshot.manual_release_id and snapshot.manual_release_id.strip():
            reasons.append("drawdown_limit_manually_released")
        else:
            reasons.append("drawdown_limit_reached")
            state = TradingState.HALTED

    if (
        state is not TradingState.HALTED
        and daily_fraction >= limits.max_daily_loss_fraction
    ):
        reasons.append("daily_loss_limit_reached")
        state = TradingState.REDUCE_ONLY

    if (
        state is TradingState.NORMAL
        and snapshot.open_positions >= limits.max_concurrent_positions
    ):
        reasons.append("concurrent_position_cap")
        state = TradingState.REDUCE_ONLY

    if state is TradingState.NORMAL:
        for event in snapshot.upcoming_gap_events:
            if timedelta(0) <= event - snapshot.now <= limits.gap_blackout:
                reasons.append("gap_blackout")
                state = TradingState.REDUCE_ONLY
                break

    return LimitDecision(
        state=state,
        reasons=tuple(reasons),
        daily_loss_fraction=daily_fraction,
        drawdown_fraction=drawdown_fraction,
        detail={
            "trading_day": snapshot.trading_day.isoformat(),
            "open_positions": str(snapshot.open_positions),
        },
    )

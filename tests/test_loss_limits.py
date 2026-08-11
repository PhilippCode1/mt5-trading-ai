"""Verlustgrenzen und Kill-Switch."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from mastertrade.risk.limits import (
    AccountSnapshot,
    LossLimits,
    TradingState,
    evaluate_limits,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _snapshot(**overrides: object) -> AccountSnapshot:
    base: dict[str, object] = {
        "now": NOW,
        "equity": Decimal("10000"),
        "day_start_equity": Decimal("10000"),
        "window_peak_equity": Decimal("10000"),
        "open_positions": 0,
        "trading_day": date(2026, 8, 6),
    }
    base.update(overrides)
    return AccountSnapshot(**base)  # type: ignore[arg-type]


def test_normal_state_allows_opening() -> None:
    decision = evaluate_limits(_snapshot(), LossLimits())
    assert decision.state is TradingState.NORMAL
    assert decision.may_open is True


def test_daily_loss_limit_switches_to_reduce_only() -> None:
    decision = evaluate_limits(_snapshot(equity=Decimal("9800")), LossLimits())
    assert decision.state is TradingState.REDUCE_ONLY
    assert decision.may_open is False
    assert "daily_loss_limit_reached" in decision.reasons


def test_drawdown_limit_halts_and_does_not_release_itself() -> None:
    decision = evaluate_limits(
        _snapshot(equity=Decimal("9000"), day_start_equity=Decimal("9000")),
        LossLimits(),
    )
    assert decision.state is TradingState.HALTED
    assert decision.may_open is False
    assert "drawdown_limit_reached" in decision.reasons


def test_drawdown_halt_needs_manual_release() -> None:
    released = evaluate_limits(
        _snapshot(
            equity=Decimal("9000"),
            day_start_equity=Decimal("9000"),
            manual_release_id="owner-2026-08-06",
        ),
        LossLimits(),
    )
    assert released.state is TradingState.NORMAL
    assert "drawdown_limit_manually_released" in released.reasons

    for blank in ("", "   ", None):
        still_halted = evaluate_limits(
            _snapshot(
                equity=Decimal("9000"),
                day_start_equity=Decimal("9000"),
                manual_release_id=blank,
            ),
            LossLimits(),
        )
        assert still_halted.state is TradingState.HALTED


def test_reducing_stays_possible_in_every_state() -> None:
    """Eine Grenze, die das Schliessen verhindert, erhoeht das Risiko."""
    for snapshot in (
        _snapshot(),
        _snapshot(equity=Decimal("9800")),
        _snapshot(equity=Decimal("9000"), day_start_equity=Decimal("9000")),
        _snapshot(
            equity=Decimal("0"),
            day_start_equity=Decimal("0"),
            window_peak_equity=Decimal("0"),
        ),
    ):
        assert evaluate_limits(snapshot, LossLimits()).may_reduce is True


def test_concurrent_position_cap() -> None:
    decision = evaluate_limits(_snapshot(open_positions=3), LossLimits())
    assert decision.state is TradingState.REDUCE_ONLY
    assert "concurrent_position_cap" in decision.reasons


def test_gap_blackout_blocks_opening_before_a_known_event() -> None:
    inside = evaluate_limits(
        _snapshot(upcoming_gap_events=(NOW + timedelta(hours=2),)), LossLimits()
    )
    assert inside.state is TradingState.REDUCE_ONLY
    assert "gap_blackout" in inside.reasons

    outside = evaluate_limits(
        _snapshot(upcoming_gap_events=(NOW + timedelta(hours=9),)), LossLimits()
    )
    assert outside.state is TradingState.NORMAL

    past = evaluate_limits(
        _snapshot(upcoming_gap_events=(NOW - timedelta(hours=1),)), LossLimits()
    )
    assert past.state is TradingState.NORMAL


def test_zero_equity_is_treated_as_fully_used_not_as_zero_loss() -> None:
    """Nicht bewertbar gilt als ausgeschoepft, nicht als unbedenklich."""
    decision = evaluate_limits(
        _snapshot(
            equity=Decimal("0"),
            day_start_equity=Decimal("0"),
            window_peak_equity=Decimal("0"),
        ),
        LossLimits(),
    )
    assert decision.state is TradingState.HALTED
    assert decision.drawdown_fraction == Decimal("1")


def test_drawdown_outranks_daily_loss() -> None:
    """Beide erreicht: der strengere Zustand gewinnt."""
    decision = evaluate_limits(
        _snapshot(equity=Decimal("8000")),
        LossLimits(),
    )
    assert decision.state is TradingState.HALTED

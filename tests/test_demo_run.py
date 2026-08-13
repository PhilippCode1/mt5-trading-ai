"""Test des Demo-Betrieb-Tors (Paket 5, §8.5). Fail-closed, negativ gefahren."""

from __future__ import annotations

from datetime import date

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue.demo_run import (
    MIN_DEMO_DAYS,
    DemoGateError,
    DemoRegistration,
    evaluate_demo_progress,
    register_for_demo,
)


def _verdict(passed: bool) -> EdgeVerdict:
    return EdgeVerdict(
        passed=passed, checks=(), unmet=() if passed else ("trade_count",)
    )


def test_register_rejects_no_edge_strategy() -> None:
    # Kern von Paket 5: ohne bestandenen Edge-Test kein Demo-Betrieb.
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="x", version="v1", edge_verdict=_verdict(False),
            registered_on=date(2026, 1, 1),
        )


def test_register_accepts_passed_strategy() -> None:
    reg = register_for_demo(
        strategy_id="x", version="v1", edge_verdict=_verdict(True),
        registered_on=date(2026, 1, 1),
    )
    assert reg.strategy_id == "x"


def test_register_requires_ids() -> None:
    with pytest.raises(DemoGateError):
        register_for_demo(
            strategy_id="  ", version="v1", edge_verdict=_verdict(True),
            registered_on=date(2026, 1, 1),
        )


def test_demo_progress_too_short_not_ready() -> None:
    reg = DemoRegistration("x", "v1", date(2026, 1, 1))
    r = evaluate_demo_progress(
        registration=reg, elapsed_days=MIN_DEMO_DAYS - 1, live_verdict=_verdict(True)
    )
    assert not r.ready_for_live_question


def test_demo_progress_ready_when_long_and_passing() -> None:
    reg = DemoRegistration("x", "v1", date(2026, 1, 1))
    r = evaluate_demo_progress(
        registration=reg, elapsed_days=MIN_DEMO_DAYS, live_verdict=_verdict(True)
    )
    assert r.ready_for_live_question


def test_demo_progress_not_ready_when_live_fails() -> None:
    reg = DemoRegistration("x", "v1", date(2026, 1, 1))
    r = evaluate_demo_progress(
        registration=reg, elapsed_days=400, live_verdict=_verdict(False)
    )
    assert not r.ready_for_live_question

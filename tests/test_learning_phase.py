"""Die vier Grenzen der Lernphase — im Code, nicht nur in der Beschreibung."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from mt5_trading_ai.gates.learning_phase import (
    LearningPhaseError,
    Proposal,
    TradeRow,
    find_weaknesses,
    rank_strategies,
    validate_proposal,
)

NOW = datetime(2026, 8, 6, 12, tzinfo=UTC)


def _trade(
    pnl_r: float, *, instrument: str = "EURUSD", hours_ago: int = 1, closed: bool = True
):
    opened = NOW - timedelta(hours=hours_ago)
    return TradeRow(
        strategy_id="smc-v1",
        version="1.0.0",
        instrument=instrument,
        asset_class="fx_major",
        opened_at=opened,
        closed_at=opened + timedelta(minutes=30) if closed else None,
        net_pnl_r=pnl_r,
        execution_mode="paper",
    )


# --- Grenze 1: kein automatisches Freischalten -----------------------------


def test_module_cannot_change_a_strategy_state() -> None:
    import mt5_trading_ai.gates.learning_phase as module

    forbidden = {"release", "approve", "promote", "activate", "set_state", "enable"}
    exported = {name.lower() for name in dir(module) if not name.startswith("_")}
    assert not (exported & forbidden)


def test_a_proposal_is_always_a_candidate() -> None:
    with pytest.raises(LearningPhaseError):
        validate_proposal(Proposal("s", "1", {"x": 1}, "r", state="released"))
    validate_proposal(Proposal("s", "1", {"x": 1}, "r"))


# --- Grenze 2: kein selbstmodifizierender Code -----------------------------


@pytest.mark.parametrize(
    "value",
    [
        "import os",
        "eval('1')",
        "lambda x: x",
        "__import__('os')",
        "os.system('x')",
        "open('f')",
    ],
)
def test_code_shaped_parameters_are_rejected(value: str) -> None:
    with pytest.raises(LearningPhaseError):
        validate_proposal(Proposal("s", "1", {"x": value}, "r"))


@pytest.mark.parametrize("value", [[1, 2], {"a": 1}, object(), None])
def test_non_scalar_parameters_are_rejected(value: object) -> None:
    with pytest.raises(LearningPhaseError):
        validate_proposal(Proposal("s", "1", {"x": value}, "r"))


def test_scalar_parameters_pass() -> None:
    validate_proposal(
        Proposal("s", "1", {"a": 1, "b": 2.5, "c": True, "d": "M15"}, "r")
    )


# --- Grenze 3: keine Optimierung ohne Ledger-Eintrag -----------------------


# --- Grenze 4: kein Training auf Trades, die nie stattfanden ---------------


def test_open_trades_are_not_counted() -> None:
    ranking = rank_strategies([_trade(1.0), _trade(5.0, closed=False)])
    assert ranking[0].trades == 1
    assert ranking[0].total_r == 1.0


# --- Diagnose ---------------------------------------------------------------


def test_ranking_orders_by_mean_r() -> None:
    good = [_trade(1.0) for _ in range(5)]
    bad = [
        TradeRow(
            "other",
            "1.0.0",
            "EURUSD",
            "fx_major",
            NOW,
            NOW + timedelta(minutes=1),
            -1.0,
            "paper",
        )
        for _ in range(5)
    ]
    ranking = rank_strategies(good + bad)
    assert ranking[0].strategy_id == "smc-v1"
    assert ranking[-1].strategy_id == "other"


def test_backtest_delta_is_reported() -> None:
    ranking = rank_strategies(
        [_trade(0.1) for _ in range(10)],
        backtest_expectation_r={("smc-v1", "1.0.0"): 0.35},
    )
    assert ranking[0].backtest_delta_r == pytest.approx(0.1 - 0.35)


def test_weaknesses_need_enough_trades() -> None:
    few = [_trade(-1.0, instrument="GBPUSD") for _ in range(5)]
    assert find_weaknesses(few, min_trades=10) == ()
    many = [_trade(-1.0, instrument="GBPUSD") for _ in range(12)]
    keys = {(w.dimension, w.key) for w in find_weaknesses(many, min_trades=10)}
    assert ("instrument", "GBPUSD") in keys

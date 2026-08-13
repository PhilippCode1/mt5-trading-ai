"""Test der Edge-Signallogik (MA-Kreuzung) und des Sechs-Bedingungen-Tors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from mt5_trading_ai.backtest.edge import (
    evaluate_edge,
    max_consecutive_positive,
)
from mt5_trading_ai.backtest.engine import MarketView, Signal
from mt5_trading_ai.backtest.strategies import moving_average_crossover
from mt5_trading_ai.data.quality import BarRow


def _view(closes: list[float]) -> MarketView:
    base = datetime(2022, 1, 3, tzinfo=UTC)
    bars = [
        BarRow(ts=base + timedelta(hours=i), open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]
    return MarketView(bars, len(bars) - 1)


# --- MA-Kreuzung ----------------------------------------------------------


def test_ma_crossover_flat_before_enough_history() -> None:
    strat = moving_average_crossover(3, 10)
    assert strat(_view([1.10] * 5)) is Signal.FLAT  # weniger als slow Bars


def test_ma_crossover_long_in_uptrend() -> None:
    strat = moving_average_crossover(3, 10)
    assert strat(_view([1.10 + 0.001 * i for i in range(20)])) is Signal.LONG


def test_ma_crossover_short_in_downtrend() -> None:
    strat = moving_average_crossover(3, 10)
    assert strat(_view([1.30 - 0.001 * i for i in range(20)])) is Signal.SHORT


def test_ma_crossover_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        moving_average_crossover(10, 5)  # slow <= fast


# --- Sechs-Bedingungen-Tor ------------------------------------------------


def _all_pass() -> dict[str, Any]:
    return {
        "oos_sharpe": 1.2, "deflated_sharpe": 0.99, "trades": 2500,
        "fold_returns": [0.1, 0.2, 0.3, 0.1], "net_over_hurdle": 0.3,
        "leakage_test_green": True, "random_reference_negative": True,
    }


def test_edge_all_conditions_met_passes() -> None:
    verdict = evaluate_edge(**_all_pass())
    assert verdict.passed
    assert verdict.unmet == ()


def test_edge_single_failure_fails_whole() -> None:
    breaks = [
        {"oos_sharpe": 0.8},                       # Sharpe unter 1.0
        {"deflated_sharpe": 0.5},                  # deflationierte Schwelle verfehlt
        {"trades": 1999},                          # unter 2000 Trades
        {"fold_returns": [0.1, -0.1, 0.1, 0.1]},   # nur 2 Fenster am Stueck positiv
        {"net_over_hurdle": -0.1},                 # Kosten nicht gedeckt
        {"random_reference_negative": False},      # Referenz nicht negativ
    ]
    for override in breaks:
        kwargs = _all_pass()
        kwargs.update(override)
        verdict = evaluate_edge(**kwargs)
        assert not verdict.passed
        assert len(verdict.unmet) >= 1


def test_max_consecutive_positive() -> None:
    assert max_consecutive_positive([0.1, 0.2, -0.1, 0.3, 0.4, 0.5]) == 3
    assert max_consecutive_positive([-0.1, -0.2]) == 0
    assert max_consecutive_positive([]) == 0

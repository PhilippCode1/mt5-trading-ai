"""Test der Edge-Signallogik (MA-Kreuzung) und des Sechs-Bedingungen-Tors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from mt5_trading_ai.backtest.edge import (
    evaluate_edge,
    max_consecutive_positive,
)
from mt5_trading_ai.backtest.engine import MarketView, Signal, Strategy
from mt5_trading_ai.backtest.strategies import (
    mean_reversion_zscore,
    moving_average_crossover,
    volatility_breakout,
)
from mt5_trading_ai.data.quality import BarRow


def _bars(closes: list[float]) -> list[BarRow]:
    base = datetime(2022, 1, 3, tzinfo=UTC)
    return [
        BarRow(ts=base + timedelta(hours=i), open=c, high=c, low=c, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def _view(closes: list[float]) -> MarketView:
    bars = _bars(closes)
    return MarketView(bars, len(bars) - 1)


def _positions(strat: Strategy, closes: list[float]) -> list[Signal]:
    """Wie die Engine: Strategie streng in Bar-Reihenfolge (haelt Zustand)."""
    bars = _bars(closes)
    return [strat(MarketView(bars, i)) for i in range(len(bars))]


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


# --- Mittelwertrueckkehr --------------------------------------------------


def test_mean_reversion_flat_before_enough_history() -> None:
    strat = mean_reversion_zscore(20, 2.0, 0.5)
    assert strat(_view([1.10] * 10)) is Signal.FLAT  # weniger als lookback Bars


def test_mean_reversion_long_on_deep_dip() -> None:
    strat = mean_reversion_zscore(20, 2.0, 0.5)
    assert strat(_view([1.10] * 19 + [1.05])) is Signal.LONG  # weit unter dem Mittel


def test_mean_reversion_short_on_spike() -> None:
    strat = mean_reversion_zscore(20, 2.0, 0.5)
    assert strat(_view([1.10] * 19 + [1.15])) is Signal.SHORT  # weit ueber dem Mittel


def test_mean_reversion_holds_then_exits() -> None:
    strat = mean_reversion_zscore(20, 2.0, 0.5)
    pos = _positions(strat, [1.10] * 19 + [1.05, 1.08, 1.10])
    assert pos[19] is Signal.LONG  # tiefer Ausschlag -> Einstieg
    assert pos[20] is Signal.LONG  # z noch jenseits exit_z -> gehalten
    assert pos[21] is Signal.FLAT  # zurueck am Mittel -> Ausstieg


def test_mean_reversion_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        mean_reversion_zscore(1, 2.0, 0.5)  # lookback < 2
    with pytest.raises(ValueError):
        mean_reversion_zscore(20, 0.5, 2.0)  # entry_z <= exit_z


# --- Volatilitaets-Ausbruch (Donchian) ------------------------------------


def test_breakout_flat_before_enough_history() -> None:
    strat = volatility_breakout(10)
    assert strat(_view([1.10] * 10)) is Signal.FLAT  # weniger als lookback+1 Bars


def test_breakout_long_on_new_high() -> None:
    strat = volatility_breakout(10)
    assert strat(_view([1.10] * 11 + [1.11])) is Signal.LONG  # Ausbruch nach oben


def test_breakout_short_on_new_low() -> None:
    strat = volatility_breakout(10)
    assert strat(_view([1.10] * 11 + [1.09])) is Signal.SHORT  # Ausbruch nach unten


def test_breakout_holds_between_breakouts() -> None:
    strat = volatility_breakout(10)
    pos = _positions(strat, [1.10] * 11 + [1.12, 1.11, 1.08])
    assert pos[11] is Signal.LONG  # neues Hoch -> LONG
    assert pos[12] is Signal.LONG  # innerhalb der Spanne -> gehalten
    assert pos[13] is Signal.SHORT  # neues Tief -> SHORT


def test_breakout_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        volatility_breakout(1)  # lookback < 2


# --- Sechs-Bedingungen-Tor ------------------------------------------------


def _all_pass() -> dict[str, Any]:
    return {
        "oos_sharpe": 1.2,
        "deflated_sharpe": 0.99,
        "trades": 2500,
        "fold_returns": [0.1, 0.2, 0.3, 0.1],
        "net_over_hurdle": 0.3,
        "leakage_test_green": True,
        "random_reference_negative": True,
    }


def test_edge_all_conditions_met_passes() -> None:
    verdict = evaluate_edge(**_all_pass())
    assert verdict.passed
    assert verdict.unmet == ()


def test_edge_single_failure_fails_whole() -> None:
    breaks = [
        {"oos_sharpe": 0.8},  # Sharpe unter 1.0
        {"deflated_sharpe": 0.5},  # deflationierte Schwelle verfehlt
        {"trades": 1999},  # unter 2000 Trades
        {"fold_returns": [0.1, -0.1, 0.1, 0.1]},  # nur 2 Fenster am Stueck positiv
        {"net_over_hurdle": -0.1},  # Kosten nicht gedeckt
        {"random_reference_negative": False},  # Referenz nicht negativ
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

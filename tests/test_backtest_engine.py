"""Test der Backtest-Maschine: Leckage-Schutz, Kosten je Trade, Zufalls-Referenzlauf,
Reproduzierbarkeit und Versuchsregister.

Die Bars sind synthetisch (deterministischer Random-Walk), damit die Tests ohne Netz und
reproduzierbar sind. Der schaerfste Test ist der Zufalls-Referenzlauf: eine wertlose
Strategie muss nach Kosten Geld verlieren -- sonst ist die Maschine kaputt.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from mt5_trading_ai.backtest.engine import (
    LookAheadError,
    MarketSpec,
    MarketView,
    Signal,
    deflated_sharpe_for_report,
    random_signal_strategy,
    run_backtest,
    run_registered_backtest,
    run_walk_forward,
)
from mt5_trading_ai.data.quality import BarRow
from mt5_trading_ai.gates.trials import append, new_trial, total_trials
from mt5_trading_ai.venue.protocol import FeeSchedule


def _bars(n: int, seed: int = 1) -> list[BarRow]:
    rng = random.Random(seed)
    out: list[BarRow] = []
    price = 1.10
    cur = datetime(2022, 1, 3, tzinfo=UTC)  # Montag
    while len(out) < n:
        if cur.weekday() < 5:
            o = price
            c = price + rng.uniform(-0.002, 0.002)
            hi = max(o, c) + abs(rng.uniform(0, 0.001))
            lo = min(o, c) - abs(rng.uniform(0, 0.001))
            out.append(BarRow(ts=cur, open=o, high=hi, low=lo, close=c, volume=1000.0))
            price = c
        cur += timedelta(days=1)
    return out


def _spec() -> MarketSpec:
    fees = FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal("-8"),
        swap_short_per_lot_per_night=Decimal("1"),
        triple_swap_weekday=2,
        currency="USD",
    )
    return MarketSpec(
        symbol="EURUSD", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
        quote_currency="USD", fees=fees, spread_pips=Decimal("0.5"),
    )


def _run(strategy: object, bars: list[BarRow] | None = None) -> object:
    return run_backtest(
        bars if bars is not None else _bars(300), strategy, _spec(),  # type: ignore[arg-type]
        strategy_id="t", seed=0, data_checksum="chk", code_commit="deadbeef",
    )


# --- Leckage-Schutz (keine Zukunft) --------------------------------------


def test_marketview_blocks_the_future() -> None:
    bars = _bars(10)
    view = MarketView(bars, 5)
    assert view.bar(5) is bars[5]           # Gegenwart erlaubt
    assert len(view.history()) == 6         # nur Vergangenheit sichtbar
    with pytest.raises(LookAheadError):
        view.bar(6)                         # ein Bar in die Zukunft


def test_leaky_strategy_makes_the_run_fail_loud() -> None:
    def leaky(view: MarketView) -> Signal:
        view.bar(view.index + 1)  # schaut in die Zukunft
        return Signal.FLAT

    with pytest.raises(LookAheadError):
        _run(leaky)


# --- Kosten (jede Order durchs Kostenmodell) -----------------------------


def test_every_trade_pays_friction() -> None:
    report = _run(lambda v: Signal.LONG if v.index % 2 == 0 else Signal.SHORT)
    assert report.trades > 0
    friction = report.cost_spread + report.cost_commission + report.cost_slippage
    assert friction > 0                 # Spread/Kommission/Slippage immer belastet
    assert report.cost_financing >= 0   # nur gezahlte Finanzierung, nie negativ
    assert report.carry_income >= 0     # Carry separat, kein negativer Kostenposten


def test_triple_swap_charged_on_start_bar_not_arrival() -> None:
    bars = _bars(5)  # Mo Di Mi Do Fr (2022-01-03 ff.); triple_weekday=2=Mi
    tue = run_backtest(bars, lambda v: Signal.LONG if v.index == 1 else Signal.FLAT,
                       _spec(), strategy_id="t", seed=0, data_checksum="c", code_commit="h")
    wed = run_backtest(bars, lambda v: Signal.LONG if v.index == 2 else Signal.FLAT,
                       _spec(), strategy_id="t", seed=0, data_checksum="c", code_commit="h")
    # Nacht Di->Mi ist KEINE Triple; Nacht Mi->Do IST Triple -> dreifache Finanzierung.
    assert wed.cost_financing == 3 * tue.cost_financing


def test_weekend_hold_counts_three_nights() -> None:
    bars = _bars(6)  # Mo Di Mi Do Fr Mo(+3 Tage ueber das Wochenende)
    r = run_backtest(bars, lambda v: Signal.LONG if v.index == 4 else Signal.FLAT,
                     _spec(), strategy_id="w", seed=0, data_checksum="c", code_commit="h")
    assert r.trade_log[0].nights == 3   # Fr->Sa->So->Mo = 3 Naechte, nicht 1 Bar
    assert r.cost_financing == 24.0     # swap_long=-8 * 3 Naechte gezahlt


def test_intraday_same_day_hold_pays_no_swap() -> None:
    # Zwei Bars am selben Kalendertag -> 0 Naechte -> keine Finanzierung.
    base = datetime(2022, 1, 3, 10, 0, tzinfo=UTC)  # Montag 10:00 und 14:00
    bars = [
        BarRow(ts=base, open=1.10, high=1.11, low=1.09, close=1.10, volume=1.0),
        BarRow(ts=base.replace(hour=14), open=1.10, high=1.11, low=1.09, close=1.101, volume=1.0),
        BarRow(ts=base.replace(hour=18), open=1.101, high=1.11, low=1.09, close=1.102, volume=1.0),
    ]
    r = run_backtest(bars, lambda v: Signal.LONG, _spec(), strategy_id="i", seed=0,
                     data_checksum="c", code_commit="h")
    assert r.cost_financing == 0.0      # kein Mitternachts-Rollover gekreuzt


def test_cost_free_spec_is_rejected() -> None:
    fees0 = FeeSchedule(
        commission_per_lot_round_turn=Decimal("0"), typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal("0"), swap_short_per_lot_per_night=Decimal("0"),
        triple_swap_weekday=2, currency="USD",
    )
    with pytest.raises(ValueError):
        MarketSpec(
            symbol="X", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
            quote_currency="USD", fees=fees0, spread_pips=Decimal("0"),
            slippage_pips_per_side=Decimal("0"),
        )


def test_zero_price_is_rejected() -> None:
    bars = _bars(10)
    bad = [BarRow(ts=bars[0].ts, open=0.0, high=0.0, low=0.0, close=0.0, volume=1.0)]
    bad += bars[1:]
    with pytest.raises(ValueError):
        run_backtest(bad, lambda v: Signal.LONG, _spec(), strategy_id="z", seed=0,
                     data_checksum="c", code_commit="h")


# --- Zufalls-Referenzlauf: muss nach Kosten verlieren --------------------


def test_random_strategy_loses_to_costs() -> None:
    bars = _bars(300)
    nets = []
    for seed in range(20):
        r = run_backtest(
            bars, random_signal_strategy(seed), _spec(),
            strategy_id="rand", seed=seed, data_checksum="chk", code_commit="x",
        )
        nets.append(r.net_return)
        assert r.net_return <= r.gross_return   # Kosten ziehen immer ab
    assert statistics_mean(nets) < 0            # im Mittel verliert Zufall nach Kosten


def statistics_mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


# --- Reproduzierbarkeit ---------------------------------------------------


def test_two_identical_runs_produce_identical_report() -> None:
    bars = _bars(300)
    a = run_backtest(bars, random_signal_strategy(42), _spec(),
                     strategy_id="r", seed=42, data_checksum="c", code_commit="h")
    b = run_backtest(bars, random_signal_strategy(42), _spec(),
                     strategy_id="r", seed=42, data_checksum="c", code_commit="h")
    assert a.as_dict() == b.as_dict()


# --- Versuchsregister: jeder Lauf zaehlt ---------------------------------


def test_registered_run_counts_every_run(tmp_path: object) -> None:
    ledger = str(tmp_path / "TRIALS.jsonl")  # type: ignore[operator]
    bars = _bars(120)
    for i in range(10):
        run_registered_backtest(
            bars, random_signal_strategy(i), _spec(),
            strategy_id="reg", version="v1", seed=i,
            data_checksum="c", code_commit="h", ledger_path=ledger,
        )
    assert total_trials(ledger) == 10


def test_walk_forward_uses_splits_and_counts_folds() -> None:
    bars = _bars(300)
    res = run_walk_forward(
        bars, lambda: random_signal_strategy(1), _spec(), 5,
        purge_ms=0, embargo_ms=0, strategy_id="wf", seed=0,
        data_checksum="c", code_commit="h",
    )
    assert res.total_folds >= 3                       # mehrere Test-Fenster
    assert 0 <= res.positive_folds <= res.total_folds
    assert all(r.trades >= 0 for r in res.folds)


def test_leaky_registered_run_still_counts(tmp_path: object) -> None:
    ledger = str(tmp_path / "TRIALS.jsonl")  # type: ignore[operator]

    def leaky(view: MarketView) -> Signal:
        view.bar(view.index + 1)
        return Signal.FLAT

    with pytest.raises(LookAheadError):
        run_registered_backtest(
            _bars(120), leaky, _spec(), strategy_id="leak", version="v1", seed=0,
            data_checksum="c", code_commit="h", ledger_path=ledger,
        )
    assert total_trials(ledger) == 1  # auch der abgebrochene Lauf zaehlt


def test_unexpected_error_still_registered(tmp_path: object) -> None:
    ledger = str(tmp_path / "TRIALS.jsonl")  # type: ignore[operator]

    def boom(_view: MarketView) -> Signal:
        raise KeyError("boom")

    with pytest.raises(KeyError):
        run_registered_backtest(
            _bars(120), boom, _spec(), strategy_id="boom", version="v1", seed=0,
            data_checksum="c", code_commit="h", ledger_path=ledger,
        )
    assert total_trials(ledger) == 1  # auch ein UNERWARTETER Fehler zaehlt


def test_deflated_sharpe_binds_true_trial_count(tmp_path: object) -> None:
    ledger = str(tmp_path / "TRIALS.jsonl")  # type: ignore[operator]
    report = _run(random_signal_strategy(3))

    def _add() -> None:
        append(new_trial(
            strategy_id="s", version="v", instruments=("EURUSD",),
            period_start=datetime(2022, 1, 1, tzinfo=UTC),
            period_end=datetime(2022, 1, 2, tzinfo=UTC),
            leverage=5, parameters={}, outcome="completed",
        ), ledger)

    _add()
    few = deflated_sharpe_for_report(report, strategy_id="s", ledger_path=ledger)
    for _ in range(60):
        _add()
    many = deflated_sharpe_for_report(report, strategy_id="s", ledger_path=ledger)
    assert 0.0 <= many <= few <= 1.0  # mehr Versuche -> strengere (kleinere) DSR


def test_walk_forward_with_nonzero_purge_still_runs() -> None:
    res = run_walk_forward(
        _bars(300), lambda: random_signal_strategy(1), _spec(), 5,
        purge_ms=86_400_000, embargo_ms=86_400_000, strategy_id="wf", seed=0,
        data_checksum="c", code_commit="h",
    )
    assert res.total_folds >= 3

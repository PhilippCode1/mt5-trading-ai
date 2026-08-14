"""Demo-Naht (Paket 6, Item 4) mit einem ECHTEN Edge-Verdict -- kein handgesetztes Flag.

``test_demo_run.py`` prueft das Tor mit konstruierten ``EdgeVerdict``-Flags. Dieser Test
schliesst die Luecke: er faehrt die **echte** Kette (``run_walk_forward`` ->
``run_registered_backtest`` -> ``deflated_sharpe`` -> ``evaluate_edge``) auf der
committeten Fixture und fuettert das so ENTSTANDENE Urteil in ``register_for_demo`` und
``evaluate_demo_progress``. So ist bewiesen, dass die Naht §8.5<->§7 ein real abgeleitetes
Urteil verarbeitet -- und dass ein ehrlich durchgefallenes (synthetisches Rauschen hat
keinen Edge) fail-closed abgelehnt wird. Ein echtes bestandenes Urteil kaeme nur aus
echten Daten mit echtem Edge; das laesst sich hier nicht ehrlich herstellen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.edge import EdgeVerdict, evaluate_edge
from mt5_trading_ai.backtest.engine import (
    LookAheadError,
    MarketSpec,
    MarketView,
    Signal,
    Strategy,
    deflated_sharpe_for_report,
    random_signal_strategy,
    run_backtest,
    run_registered_backtest,
    run_walk_forward,
)
from mt5_trading_ai.backtest.strategies import mean_reversion_zscore
from mt5_trading_ai.costs.model import load_cost_fees
from mt5_trading_ai.data.loader import FxSession, load_verified_csv
from mt5_trading_ai.venue.demo_run import (
    DemoGateError,
    DemoRegistration,
    evaluate_demo_progress,
    register_for_demo,
)

FIXTURE = Path(__file__).parent / "fixtures" / "smoke_eurusd_h1.csv"
COMMIT = "demoe2e0commit0fixed"
STRATEGY_ID = "mean_reversion_eurusd_h1"


def _real_verdict(ledger: Path) -> tuple[EdgeVerdict, int]:
    """Faehre die echte Kette und gib das ENTSTANDENE Urteil (+ OoS-Trades) zurueck."""
    bars, _chk = load_verified_csv(
        FIXTURE, instrument="EURUSD", timeframe="H1", session_predicate=FxSession(),
    )
    split = int(len(bars) * 0.70)
    in_sample, oos = bars[:split], bars[split:]
    spec = MarketSpec(
        symbol="EURUSD", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
        quote_currency="USD", fees=load_cost_fees("EURUSD"), spread_pips=Decimal("0.1"),
        leverage=Decimal("5"), obs_per_year=6000.0,
    )

    def factory() -> Strategy:
        return mean_reversion_zscore(48, 2.0, 0.5)

    wf = run_walk_forward(
        in_sample, lambda _train: factory(), spec, 5,
        purge_ms=3_600_000, embargo_ms=3_600_000,
        strategy_id=STRATEGY_ID, seed=100, data_checksum="", code_commit=COMMIT,
        ledger_path=str(ledger),
    )
    oos_report = run_registered_backtest(
        oos, factory(), spec, strategy_id=STRATEGY_ID, version="v1", seed=0,
        data_checksum="", code_commit=COMMIT, ledger_path=str(ledger),
    )
    dsr = deflated_sharpe_for_report(
        oos_report, strategy_id=STRATEGY_ID, version="v1", ledger_path=str(ledger),
        count_scope="total",
    )
    # Die beiden Booleans kommen aus ECHTEN Kontroll-Laeufen, nicht von Hand gesetzt.
    rnd = [
        run_backtest(oos, random_signal_strategy(s), spec, strategy_id="rnd", seed=s,
                     data_checksum="", code_commit="").net_return
        for s in range(5)
    ]
    random_negative = (sum(rnd) / len(rnd)) < 0

    def _leaky(view: MarketView) -> Signal:
        view.bar(view.index + 1)
        return Signal.FLAT

    leakage_green = False
    try:
        run_backtest(oos, _leaky, spec, strategy_id="leak", seed=0,
                     data_checksum="", code_commit="")
    except LookAheadError:
        leakage_green = True

    verdict = evaluate_edge(
        oos_sharpe=oos_report.trade_sharpe, deflated_sharpe=dsr,
        trades=oos_report.trades, fold_returns=[f.net_return for f in wf.folds],
        net_over_hurdle=oos_report.net_over_hurdle,
        leakage_test_green=leakage_green, random_reference_negative=random_negative,
    )
    return verdict, oos_report.trades


def test_real_no_edge_verdict_is_refused_by_demo_gate(tmp_path: Path) -> None:
    verdict, trades = _real_verdict(tmp_path / "TRIALS.jsonl")
    # Es ist ein echtes Urteil: die Kette hat gehandelt und alle sechs Checks gefuellt.
    assert len(verdict.checks) == 6
    assert trades >= 2
    assert verdict.passed is False  # ehrliches Nein auf synthetischem Rauschen

    # Die Naht §8.5<->§7: ein durchgefallenes (real abgeleitetes) Urteil sperrt den
    # Demo-Betrieb fail-closed -- mit den ECHTEN offenen Bedingungen als Begruendung.
    with pytest.raises(DemoGateError) as excinfo:
        register_for_demo(
            strategy_id=STRATEGY_ID, version="v1", edge_verdict=verdict,
            registered_on=date(2026, 1, 1),
        )
    assert verdict.unmet  # es gibt konkrete offene Bedingungen
    assert verdict.unmet[0] in str(excinfo.value)


def test_real_no_edge_verdict_blocks_live_question(tmp_path: Path) -> None:
    verdict, _trades = _real_verdict(tmp_path / "TRIALS.jsonl")
    reg = DemoRegistration(STRATEGY_ID, "v1", date(2026, 1, 1))
    # Selbst nach > 180 Tagen Demo: ein real durchgefallenes Live-Urteil sperrt die
    # Live-Frage. Der Zeitanteil ist erfuellt, die Bedingung nicht.
    readiness = evaluate_demo_progress(
        registration=reg, elapsed_days=400, live_verdict=verdict
    )
    assert not readiness.ready_for_live_question
    assert "live_demo_verfehlt_sechs_bedingungen" in readiness.reasons

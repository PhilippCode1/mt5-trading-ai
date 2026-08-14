"""E2E-Smoke (Paket 6, Item 2): die ganze Kette als EIN konvergierender Lauf.

Die Einzelinseln sind je fuer sich getestet. Dieser Test beweist die **Verdrahtung**:
eine committete Mini-Fixture laeuft durch

    load_verified_csv  ->  run_walk_forward  ->  run_registered_backtest
                       ->  deflated_sharpe_for_report  ->  evaluate_edge

in einem Zug, ohne dass ein Zwischenstueck von Hand gefuettert wird. Geprueft wird die
KONVERGENZ (jede Stufe reicht ans naechste weiter, ein Urteil faellt) -- NICHT, dass ein
Edge existiert. Auf synthetischem Rauschen ist das ehrliche Urteil "kein Edge"; genau das
erwartet dieser Test. Zugleich zeigt er, dass die Herkunft (Paket 6, Item 3) durch die
ganze Kette ins Register faellt: jeder registrierte Versuch traegt Pruefsumme + Commit.

Die Fixture ist SYNTHETISCH (kein Marktdatum) und liegt mit Manifest im Repo -- so laeuft
der Smoke in CI ohne lokale Marktdaten.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from mt5_trading_ai.backtest.edge import evaluate_edge
from mt5_trading_ai.backtest.engine import (
    MarketSpec,
    Strategy,
    deflated_sharpe_for_report,
    run_registered_backtest,
    run_walk_forward,
)
from mt5_trading_ai.backtest.strategies import moving_average_crossover
from mt5_trading_ai.costs.model import load_cost_fees
from mt5_trading_ai.data.loader import WeekdaySession, load_verified_csv
from mt5_trading_ai.gates import trials as trials_ledger

FIXTURE = Path(__file__).parent / "fixtures" / "smoke_eurusd_d1.csv"
# Angeheftet: driftet die Fixture, faellt der Smoke laut auf (das Manifest allein wuerde
# eine gemeinsame Neu-Erzeugung stumm mittragen).
PINNED_CHECKSUM = "035616dd398b1c19423e2cc25ec37d3410fc715191f7dd4c3941956a90346fd2"
COMMIT = "e2e0smoke0commit0"  # fixer Codestand -> hermetisch, ohne git im Test
OOS_FRACTION = 0.30


def _spec() -> MarketSpec:
    return MarketSpec(
        symbol="EURUSD", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
        quote_currency="USD", fees=load_cost_fees("EURUSD"), spread_pips=Decimal("0.1"),
        leverage=Decimal("5"), obs_per_year=252.0,
    )


def test_full_pipeline_converges_on_fixture(tmp_path: Path) -> None:
    ledger = str(tmp_path / "TRIALS.jsonl")

    # Stufe 1: Tor am Backtest-Rand -- Herkunft ueber das committete Manifest, Struktur
    # ueber das Qualitaetstor. Die Pruefsumme ist angeheftet.
    bars, checksum = load_verified_csv(
        FIXTURE, instrument="EURUSD", timeframe="D1",
        session_predicate=WeekdaySession(),
    )
    assert checksum == PINNED_CHECKSUM, "Fixture veraendert -- Smoke angehalten"
    assert len(bars) == 220

    spec = _spec()
    split = int(len(bars) * (1.0 - OOS_FRACTION))
    in_sample, oos = bars[:split], bars[split:]

    def factory() -> Strategy:
        return moving_average_crossover(5, 20)

    # Stufe 2: Walk-Forward auf dem In-Sample -- registriert jeden Fold ins Register.
    wf = run_walk_forward(
        in_sample, lambda _train: factory(), spec, 5,
        purge_ms=86_400_000, embargo_ms=86_400_000,
        strategy_id="smoke_ma", seed=100, data_checksum="", code_commit=COMMIT,
        ledger_path=ledger,
    )
    assert wf.total_folds >= 1

    # Stufe 3: der OoS-Abschlusslauf, registriert.
    oos_report = run_registered_backtest(
        oos, factory(), spec,
        strategy_id="smoke_ma", version="v1", seed=0,
        data_checksum="", code_commit=COMMIT, ledger_path=ledger,
    )

    # Stufe 4: Deflation gegen die WAHRE Versuchszahl im Register.
    dsr = deflated_sharpe_for_report(
        oos_report, strategy_id="smoke_ma", version="v1", ledger_path=ledger,
        count_scope="total",
    )
    assert 0.0 <= dsr <= 1.0

    # Stufe 5: das Sechs-Bedingungen-Tor faellt ein Urteil (keine Ausnahme).
    verdict = evaluate_edge(
        oos_sharpe=oos_report.trade_sharpe, deflated_sharpe=dsr,
        trades=oos_report.trades, fold_returns=[f.net_return for f in wf.folds],
        net_over_hurdle=oos_report.net_over_hurdle,
        leakage_test_green=True, random_reference_negative=True,
    )
    assert len(verdict.checks) == 6
    # Ehrliche Erwartung: synthetisches Rauschen belegt keinen Edge.
    assert verdict.passed is False

    # Konvergenz-Beleg: die Kette hat wirklich gehandelt und registriert.
    assert oos_report.trades >= 2, "OoS-Lauf ohne Trades -- Kette nicht durchlaufen"
    assert trials_ledger.total_trials(ledger) == wf.total_folds + 1  # Folds + OoS

    # Herkunft (Item 3) faellt durch die GANZE Kette ins Register: jeder Eintrag traegt
    # eine nicht-leere Pruefsumme UND den Commit -- kein beweisfreier Versuch.
    for trial in trials_ledger.iter_trials(ledger):
        assert trial.data_checksum.strip()
        assert trial.code_commit == COMMIT
    # Der OoS-Bericht traegt die ABGELEITETE (echte) Pruefsumme, nicht den Erwartungswert.
    assert oos_report.data_checksum

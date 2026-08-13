#!/usr/bin/env python3
"""Multi-Instrument-Edge-Harness (Paket 5, §8.1).

Prueft eine vorregistrierte Strategie **einzeln** auf jedem Instrument gegen dasselbe
harte Sechs-Bedingungen-Tor. Ein Instrument, das durchfaellt, kommt nicht mit (§8.1).
Kein Ausbau auf das ganze MT5-Universum -- zwei bis drei Instrumente, jedes fuer sich.

Jeder Lauf zaehlt ins geteilte Register; die Deflation nutzt die kampagnenweite Zahl.
Hebel konservativ (5:1), unter jeder ESMA-Klassengrenze. Kein Echtgeld.

Aufruf:  python tools/multi_instrument_edge.py --instrument EURUSD PATH ...
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.edge import EdgeVerdict, evaluate_edge  # noqa: E402
from mt5_trading_ai.backtest.engine import (  # noqa: E402
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
from mt5_trading_ai.backtest.strategies import mean_reversion_zscore  # noqa: E402
from mt5_trading_ai.costs.model import load_cost_fees  # noqa: E402
from mt5_trading_ai.data.loader import FxSession, load_verified_csv  # noqa: E402

VERSION = "v1"
OOS_FRACTION = 0.30
LEVERAGE = Decimal("5")  # konservativ, unter jeder ESMA-Klassengrenze


def _pip_size(symbol: str) -> Decimal:
    return Decimal("0.01") if symbol.upper().endswith("JPY") else Decimal("0.0001")


def _run_one(
    symbol: str, csv_path: Path, ledger: str, checksum: str, commit: str
) -> tuple[EdgeVerdict, int, float, float]:
    """Ein Instrument durchs Tor. -> (Urteil, Trades, Netto, DSR)."""
    # Qualitaetstor + Provenienz am Backtest-Rand (Paket 1), fail-closed je Instrument.
    bars, _chk = load_verified_csv(
        csv_path, instrument=symbol, timeframe="H1", session_predicate=FxSession(),
        expected_checksum=checksum or None,
    )
    span_years = max(1e-9, (bars[-1].ts - bars[0].ts).days / 365.25)
    spec = MarketSpec(
        symbol=symbol, contract_size=Decimal("100000"), pip_size=_pip_size(symbol),
        quote_currency=symbol[3:], fees=load_cost_fees(symbol),
        spread_pips=Decimal("0.1"), leverage=LEVERAGE,
        obs_per_year=len(bars) / span_years,
    )
    strategy_id = f"mean_reversion_{symbol.lower()}_h1"
    split = int(len(bars) * (1.0 - OOS_FRACTION))
    in_sample, oos = bars[:split], bars[split:]

    def factory() -> Strategy:
        return mean_reversion_zscore(48, 2.0, 0.5)

    wf = run_walk_forward(
        in_sample, lambda _train: factory(), spec, 5,   # Fixparameter -> Fit No-op
        purge_ms=3_600_000, embargo_ms=3_600_000,
        strategy_id=strategy_id, seed=100, version=VERSION,
        data_checksum="", code_commit=commit, ledger_path=ledger,
    )
    oos_report = run_registered_backtest(
        oos, mean_reversion_zscore(48, 2.0, 0.5), spec, strategy_id=strategy_id,
        version=VERSION, seed=0, data_checksum="", code_commit=commit,
        ledger_path=ledger,
    )
    dsr = deflated_sharpe_for_report(
        oos_report, strategy_id=strategy_id, version=VERSION, ledger_path=ledger,
        count_scope="total",
    )
    # Bedingung 6 wird je Instrument GEFAHREN, nicht behauptet: Zufalls-Referenz < 0
    # nach Kosten, und der Leckage-Schutz faengt eine Zukunfts-Strategie.
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
    return verdict, oos_report.trades, oos_report.net_return, dsr


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Multi-Instrument-Edge (Paket 5, §8.1)")
    ap.add_argument(
        "--instrument", nargs=2, action="append", metavar=("SYMBOL", "CSV"),
        required=True, help="Symbol und CSV-Pfad; mehrfach fuer mehrere Instrumente",
    )
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--data-checksum", default="")
    ap.add_argument("--code-commit", default="")
    args = ap.parse_args()

    ledger = str(args.ledger)
    passed_count = 0
    print("=== MULTI-INSTRUMENT-EDGE (jedes einzeln durchs Sechs-Bedingungen-Tor) ===")
    for symbol, csv in args.instrument:
        verdict, trades, net, dsr = _run_one(
            symbol.upper(), Path(csv), ledger, args.data_checksum, args.code_commit
        )
        mark = "EDGE BELEGT" if verdict.passed else "KEIN EDGE"
        if verdict.passed:
            passed_count += 1
        print(
            f"  {symbol.upper():8s} | {trades:4d} Trades | Netto {net * 100:+7.2f} % | "
            f"DSR {dsr:.4f} | {mark} (offen: {', '.join(verdict.unmet) or 'keine'})"
        )
    total = len(args.instrument)
    print(f"\nInstrumente mit belegtem Edge: {passed_count} / {total}")
    print(
        "Ergebnis: AUSBAU MOEGLICH" if passed_count else
        "Ergebnis: KEIN Instrument besteht -- kein Ausbau (§8.1)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

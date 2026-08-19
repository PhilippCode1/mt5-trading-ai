#!/usr/bin/env python3
"""Edge-Test (Paket 4, §7): die eine Frage -- existiert auf EURUSD ein Edge nach Kosten?

Faehrt die einfachste ernsthafte Signallogik (MA-Kreuzung, keine Optimierung) durch die
Backtest-Maschine und prueft das harte **Sechs-Bedingungen-Tor**. Jeder Lauf zaehlt ins
Versuchsregister. Der Out-of-Sample-Block (letzter Teil) wird genau einmal angefasst.

Ein sauberes Nein ist der auftragsgemaesse Ausgang, kein Scheitern. Ausdruecklich NICHT
erlaubt: Schwelle senken, Zeitraum aendern bis es passt, Instrument wechseln und den
alten Lauf verschweigen. Dieses Werkzeug tut nichts davon.

Aufruf:  python tools/edge_test.py --csv EURUSD_H1.csv --ledger TRIALS.jsonl
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.edge import evaluate_edge  # noqa: E402
from mt5_trading_ai.backtest.engine import (  # noqa: E402
    LookAheadError,
    MarketSpec,
    MarketView,
    Signal,
    Strategy,
    criteria_evidence,
    deflated_sharpe_for_report,
    random_signal_strategy,
    run_backtest,
    run_registered_backtest,
    run_walk_forward,
    stressed_spec,
)
from mt5_trading_ai.backtest.provenance import code_commit_from_git  # noqa: E402
from mt5_trading_ai.backtest.strategies import (  # noqa: E402
    mean_reversion_zscore,
    moving_average_crossover,
    volatility_breakout,
)
from mt5_trading_ai.costs.model import load_cost_fees  # noqa: E402
from mt5_trading_ai.data.loader import FxSession, load_verified_csv  # noqa: E402
from mt5_trading_ai.gates.criteria import (  # noqa: E402
    Preregistration,
    evaluate_criteria,
    percentile_against_random,
)
from mt5_trading_ai.gates.trials import check_integrity, total_trials  # noqa: E402

VERSION = "v1"
OOS_FRACTION = 0.30    # letzter Teil = Out-of-Sample, je Strategie einmal angefasst


def _strategy(name: str) -> tuple[str, Callable[[], Strategy], str]:
    """Vorab registrierte Hypothesen. Parameter per Konvention, NICHT optimiert."""
    if name == "ma_crossover":
        return (
            "ma_crossover_eurusd_h1",
            lambda: moving_average_crossover(24, 120),  # 1 Tag vs. 1 Woche
            "MA(24,120), Trendfolge",
        )
    if name == "mean_reversion":
        return (
            "mean_reversion_eurusd_h1",
            lambda: mean_reversion_zscore(48, 2.0, 0.5),  # 2 Tage, ein 2.0 / aus 0.5
            "z-Score(48, ein 2.0/aus 0.5), Mittelwertrueckkehr",
        )
    if name == "breakout":
        return (
            "breakout_eurusd_h1",
            lambda: volatility_breakout(48),  # Donchian, 2 Handelstage
            "Donchian(48), Volatilitaets-Ausbruch",
        )
    raise SystemExit(f"unbekannte Strategie: {name}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Edge-Test EURUSD (Sechs-Bedingungen-Tor)")
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument(
        "--strategy", choices=["ma_crossover", "mean_reversion", "breakout"],
        default="ma_crossover",
    )
    ap.add_argument(
        "--oos-csv", type=Path, default=None,
        help="frischer OoS-Block (eigene Datei); sonst letzte 30 % von --csv",
    )
    ap.add_argument("--data-checksum", default="")
    ap.add_argument("--code-commit", default="")
    ap.add_argument(
        "--campaign-trials", type=int, default=None,
        help="deklarierte GESAMT-Versuchszahl der Kampagne (mehrere Strategien gegen "
             "dasselbe Ledger); deflationiert jeden Lauf gegen dieselbe volle Zahl "
             "statt gegen den laufenden Registerstand -- nicht order-gameable",
    )
    args = ap.parse_args()

    # Herkunft (Paket 6): der Codestand kommt aus git, wenn nicht explizit gesetzt --
    # ein registrierter Versuch mit leerem Commit ist fail-closed nicht moeglich.
    code_commit = args.code_commit or code_commit_from_git()

    strategy_id, factory, label = _strategy(args.strategy)
    # Tor am Backtest-Rand (Paket 1): Qualitaetstor + Provenienz, fail-closed.
    bars, _chk = load_verified_csv(
        args.csv, instrument="EURUSD", timeframe="H1", session_predicate=FxSession(),
        expected_checksum=args.data_checksum or None,
    )
    span_years = max(1e-9, (bars[-1].ts - bars[0].ts).days / 365.25)
    obs_per_year = len(bars) / span_years
    fees = load_cost_fees("EURUSD")
    spec = MarketSpec(
        symbol="EURUSD", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
        quote_currency="USD", fees=fees, spread_pips=Decimal("0.1"),
        leverage=Decimal("5"), obs_per_year=obs_per_year,
    )
    print(
        f"Daten: {len(bars)} H1-Bars {bars[0].ts.date()}..{bars[-1].ts.date()} "
        f"| obs/Jahr ~ {obs_per_year:.0f} | {label}"
    )

    if args.oos_csv is not None:
        # Frischer, unberuehrter OoS-Block aus eigener Datei: In-Sample = ganzes --csv,
        # OoS = die neue Periode. Das ist der ehrliche Weg fuer einen dritten Versuch --
        # der bisherige 30-%-Block ist durch zwei Strategien belastet.
        in_sample = bars
        oos, _oos_chk = load_verified_csv(
            args.oos_csv, instrument="EURUSD", timeframe="H1",
            session_predicate=FxSession(),
        )
        print(
            f"In-Sample {len(in_sample)} (ganzes --csv) | FRISCHES OoS {len(oos)} Bars "
            f"{oos[0].ts.date()}..{oos[-1].ts.date()} -- unberuehrt, einmal angefasst"
        )
    else:
        split = int(len(bars) * (1.0 - OOS_FRACTION))
        in_sample, oos = bars[:split], bars[split:]
        print(
            f"In-Sample {len(in_sample)} | OoS ({OOS_FRACTION:.0%}) {len(oos)} "
            f"Bars ab {oos[0].ts.date()} -- je Strategie einmal angefasst"
        )
    ledger = str(args.ledger)

    # Walk-Forward NUR auf dem In-Sample-Teil -- der OoS-Block bleibt bis zum Abschluss
    # unberuehrt; die Fenster registrieren (Deflation kennt die wahre Versuchszahl).
    wf = run_walk_forward(
        in_sample, lambda _train: factory(), spec, 5,   # Fixparameter -> Fit ist No-op
        purge_ms=3_600_000, embargo_ms=3_600_000, strategy_id=strategy_id, seed=100,
        version=VERSION, data_checksum="", code_commit=code_commit,
        ledger_path=ledger,
    )
    fold_returns = [f.net_return for f in wf.folds]

    oos_report = run_registered_backtest(  # der OoS-Abschlusslauf, genau einmal
        oos, factory(), spec,
        strategy_id=strategy_id, version=VERSION, seed=0,
        data_checksum="", code_commit=code_commit,
        ledger_path=ledger,
    )
    # Deflation gegen das GESAMTE Register (count_scope="total"): bei einer Kampagne mit
    # mehreren Strategien gegen dieselben OoS-Daten ist die ehrliche Multiple-Testing-
    # Zahl die Summe aller Versuche, nicht nur die dieser einen Strategie.
    dsr = deflated_sharpe_for_report(
        oos_report, strategy_id=strategy_id, version=VERSION, ledger_path=ledger,
        count_scope="total", expected_trials=args.campaign_trials,
    )

    # Bedingung 6 wird GEFAHREN, nicht behauptet: Zufalls-Referenzlauf < 0 nach Kosten,
    # und der Leckage-Schutz faengt eine Zukunfts-Strategie (LookAheadError).
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

    print(
        f"\nOoS: {oos_report.trades} Trades | Netto {oos_report.net_return * 100:.2f} %"
        f" | Trade-Sharpe {oos_report.trade_sharpe:.3f}"
        f" | Bar-Sharpe {oos_report.annualised_sharpe:.3f}"
        f" | MaxDD {oos_report.max_drawdown * 100:.1f} %"
        f" | net_over_hurdle {oos_report.net_over_hurdle * 100:.2f} %"
    )
    print(f"Deflated Sharpe (Versuche im Register): {dsr:.4f}")
    print(f"WF In-Sample (Netto je Fenster): {[round(x, 4) for x in fold_returns]}")
    print(
        f"Zufalls-Referenz (5 Seeds) Mittel {sum(rnd) / len(rnd) * 100:.1f} % "
        f"-> negativ={random_negative} | Leckage gefangen={leakage_green}"
    )

    # Stufe 9: das Register wird geprueft, BEVOR dieser Lauf es fortschreibt. Ein
    # Register, das nur waechst, ist die Grundlage jeder Deflation -- ist es
    # beschaedigt, sagt die deflationierte Zahl nichts, und sie sieht trotzdem aus wie
    # eine Zahl. Bis Stufe 9 lag ``check_integrity`` ohne Aufrufer im Paket.
    unversehrt = check_integrity(ledger)
    if not unversehrt.ok:
        print(
            "FEHLGESCHLAGEN — Versuchsregister beschaedigt:", file=sys.stderr
        )
        for problem in unversehrt.problems:
            print(f"  {problem}", file=sys.stderr)
        print("Eine Deflation gegen ein beschaedigtes Register belegt nichts.",
              file=sys.stderr)
        return 1
    print(f"Versuchsregister: {unversehrt.lines} Zeilen, unversehrt")

    verdict = evaluate_edge(
        oos_sharpe=oos_report.trade_sharpe,  # Trade-Level, ehrlich bei seltenem Handel
        deflated_sharpe=dsr,
        trades=oos_report.trades,
        fold_returns=fold_returns,
        net_over_hurdle=oos_report.net_over_hurdle,
        leakage_test_green=leakage_green,
        random_reference_negative=random_negative,
    )

    print("\n=== SECHS-BEDINGUNGEN-TOR ===")
    for check in verdict.checks:
        mark = "ERFUELLT" if check.met else "NICHT ERFUELLT"
        print(f"  [{mark}] {check.name}: {check.observed} (verlangt {check.required})")
    print(f"\nERGEBNIS: {'EDGE BELEGT' if verdict.passed else 'KEIN EDGE'} "
          f"(nicht erfuellt: {', '.join(verdict.unmet) or 'keine'})")

    # --- Zusatz: die vollere 10-Kriterien-Auswertung (§9.3) mit Stress-Kosten ---
    prereg = Preregistration()
    stressed = run_backtest(
        oos, factory(), stressed_spec(spec, prereg.cost_stress_multiplier),
        strategy_id="stress", seed=0, data_checksum="", code_commit="",
    )
    evidence = criteria_evidence(
        oos_report, positive_folds=wf.positive_folds, deflated_sharpe=dsr,
        trial_count=total_trials(path=ledger),
        net_expectancy_at_stressed_cost=stressed.net_over_hurdle,
        random_percentile=percentile_against_random(oos_report.net_return, rnd),
    )
    crit = evaluate_criteria(evidence, prereg)
    print("\n=== VOLLE KRITERIEN (Zusatz, §9.3) ===")
    for r in crit.results:
        mark = ("ERFUELLT" if r.met else
                "NICHT BEWERTBAR" if r.reason == "not_evaluable" else "NICHT ERFUELLT")
        print(f"  [{mark}] {r.name}: {r.observed}")
    print(
        f"cost_stress bei {prereg.cost_stress_multiplier}x Kosten: "
        f"net_over_hurdle {stressed.net_over_hurdle * 100:.2f} %"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

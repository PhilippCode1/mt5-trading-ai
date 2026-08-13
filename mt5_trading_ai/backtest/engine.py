"""Backtest-Maschine: fuehrt Splits, Daten und Kostenmodell zusammen.

WARUM ES DIESES MODUL GIBT
--------------------------
Bis hier war jedes Teil einzeln gepruft: Zeitreihen-Splits (``backtest/splits.py``),
saubere Bars (``data/loader.py``), reale Kosten (``costs/model.py``). Diese Maschine
laesst eine Strategie darauf laufen und beantwortet ehrlich, was sie **nach Kosten**
verdient. Vier Eigenschaften sind nicht verhandelbar:

1. **Jede Order durchlaeuft das Kostenmodell.** Es gibt keinen kostenlosen Modus, auch
   nicht zum Debuggen. Ein Backtest ohne Kosten ist Fiktion.
2. **Keine Zukunft.** Eine Entscheidung zum Bar ``i`` sieht nur Bars bis ``i``
   (``MarketView`` wirft ``LookAheadError`` bei jedem Zukunfts-Zugriff). Die Ausfuehrung
   folgt einen Bar spaeter (shift(1)): entschieden bei ``i``, gehalten ueber ``i+1``.
3. **Reproduzierbar.** Zufallsgrundlage, Datenpruefsumme und Codestand (Commit) stehen
   im Bericht; zwei gleiche Laeufe ergeben denselben Bericht.
4. **Jeder Lauf zaehlt.** ``run_registered_backtest`` haengt IMMER einen Eintrag ans
   Versuchsregister an -- auch ein abgebrochener oder fehlgeschlagener Lauf.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import IntEnum
from typing import Any

from mt5_trading_ai.backtest.splits import Range, purged_walk_forward_indices
from mt5_trading_ai.costs.model import (
    DEFAULT_SLIPPAGE_PIPS_PER_SIDE,
    order_roundturn_cost,
)
from mt5_trading_ai.data.quality import BarRow
from mt5_trading_ai.gates import trials
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio
from mt5_trading_ai.venue.protocol import FeeSchedule, OrderSide

BACKTEST_ENGINE_VERSION = "backtest-engine-v1"


class Signal(IntEnum):
    """Zielposition, die eine Strategie fuer den naechsten Bar waehlt."""

    SHORT = -1
    FLAT = 0
    LONG = 1


class LookAheadError(RuntimeError):
    """Eine Strategie hat auf die Zukunft zugegriffen. Der Lauf ist ungueltig."""


class MarketView:
    """Was eine Strategie zum Bar ``index`` sehen darf -- und keinen Bar mehr.

    ``bar(j)`` fuer ``j > index`` wirft ``LookAheadError``. So ist Leckage nicht nur
    verboten, sondern nachweisbar: eine Strategie, die in die Zukunft greift, laesst
    den Lauf laut scheitern (statt still einen falschen Edge zu erzeugen).
    """

    def __init__(self, bars: Sequence[BarRow], index: int) -> None:
        # Nur die sichtbare Vergangenheit als unveraenderliche Kopie: die Zukunft ist
        # weder LESBAR (nicht da) noch MUTIERBAR (Tuple, BarRow frozen).
        self._past: tuple[BarRow, ...] = tuple(bars[: index + 1])
        self.index = index

    def now(self) -> BarRow:
        return self._past[self.index]

    def bar(self, j: int) -> BarRow:
        if j > self.index:
            raise LookAheadError(
                f"Zukunfts-Zugriff: bar {j} liegt nach jetzt ({self.index})"
            )
        if j < 0:
            raise IndexError("negativer Bar-Index")
        return self._past[j]

    def history(self) -> tuple[BarRow, ...]:
        """Alle sichtbaren Bars (bis einschliesslich ``index``), unveraenderlich."""
        return self._past


Strategy = Callable[[MarketView], Signal]


def random_signal_strategy(seed: int) -> Strategy:
    """Eine bewusst WERTLOSE Strategie: gleichverteilt Long/Flat/Short.

    Der Referenzlauf mit ihr muss nach Kosten **negativ** um die Kostenhuerde liegen --
    sieht eine Zufallsstrategie profitabel aus, ist die Maschine kaputt (die schaerfste
    Gegenprobe des Auftrags). Deterministisch ueber ``seed``.
    """
    rng = random.Random(seed)

    def strategy(_view: MarketView) -> Signal:
        return rng.choice((Signal.LONG, Signal.FLAT, Signal.SHORT))

    return strategy


@dataclass(frozen=True)
class MarketSpec:
    """Instrument + Kostenparameter fuer den Backtest.

    Bars haben kein Bid/Ask; ``spread_pips`` ist der angenommene Spread, aus dem das
    Kostenmodell die Spreadkosten je Roundturn rechnet (dokumentierte Annahme).
    """

    symbol: str
    contract_size: Decimal
    pip_size: Decimal
    quote_currency: str
    fees: FeeSchedule
    spread_pips: Decimal
    volume: Decimal = Decimal("1")
    leverage: Decimal = Decimal("5")
    slippage_pips_per_side: Decimal = DEFAULT_SLIPPAGE_PIPS_PER_SIDE
    obs_per_year: float = 252.0

    def __post_init__(self) -> None:
        if self.contract_size <= 0 or self.pip_size <= 0 or self.volume <= 0:
            raise ValueError("contract_size, pip_size, volume muessen positiv sein")
        if self.leverage <= 0:
            raise ValueError("leverage muss positiv sein")
        if self.spread_pips < 0 or self.slippage_pips_per_side < 0:
            raise ValueError("spread_pips und slippage duerfen nicht negativ sein")
        # Kein kostenfreier Modus (Kernregel): mindestens eine Reibungsquelle > 0.
        if (
            self.spread_pips == 0
            and self.slippage_pips_per_side == 0
            and self.fees.commission_per_lot_round_turn == 0
        ):
            raise ValueError(
                "Kostenfreier Modus verboten: Spread, Slippage und Kommission alle 0"
            )


@dataclass(frozen=True)
class TradeRecord:
    entry_ts: str
    exit_ts: str
    side: str
    nights: int
    gross: float
    cost: float
    net: float


@dataclass(frozen=True)
class BacktestReport:
    strategy_id: str
    bars: int
    trades: int
    gross_return: float
    cost_spread: float
    cost_commission: float
    cost_slippage: float
    cost_financing: float  # nur gezahlte Finanzierung (>= 0)
    carry_income: float    # empfangener Positiv-Swap (>= 0), separater Ertrag
    net_return: float
    annualised_sharpe: float       # Bar-Level (obs = Bars); fuer Daueranlagen ueblich
    trade_sharpe: float    # Trade-Level (obs=Trades); ehrlich bei seltenem Handel
    annualisation: str
    max_drawdown: float
    hit_rate: float
    mean_win: float
    mean_loss: float
    hurdle_pct: float
    net_over_hurdle: float
    seed: int
    data_checksum: str
    code_commit: str
    obs_per_year: float = 252.0
    engine_version: str = BACKTEST_ENGINE_VERSION
    trade_log: tuple[TradeRecord, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        payload = {k: v for k, v in vars(self).items() if k != "trade_log"}
        payload["trade_log"] = [vars(t) for t in self.trade_log]
        return payload


def _runs(positions: list[Signal]) -> list[tuple[int, int, Signal]]:
    """Maximale Laeufe gleicher Nicht-Flat-Richtung -> (start, end_inklusive, side)."""
    out: list[tuple[int, int, Signal]] = []
    i = 0
    n = len(positions)
    while i < n:
        side = positions[i]
        if side is Signal.FLAT:
            i += 1
            continue
        j = i
        while j + 1 < n and positions[j + 1] is side:
            j += 1
        out.append((i, j, side))
        i = j + 1
    return out


def _drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 0.0
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, (value - peak) / peak)
    return -worst


def run_backtest(
    bars: Sequence[BarRow],
    strategy: Strategy,
    spec: MarketSpec,
    *,
    strategy_id: str,
    seed: int,
    data_checksum: str,
    code_commit: str,
) -> BacktestReport:
    """Fahre ``strategy`` ueber ``bars``. Entscheidung bei Close ``i``, gehalten ueber
    ``i+1`` (shift(1)); jede Order durchs Kostenmodell; ``LookAheadError`` bricht ab.
    """
    if len(bars) < 3:
        raise ValueError("Zu wenige Bars fuer einen Backtest")

    cs = float(spec.contract_size)
    vol = float(spec.volume)
    lev = float(spec.leverage)
    tri_weekday = spec.fees.triple_swap_weekday

    # Entscheidung am Bar i (sieht nur <= i), gehalten ueber Bar i+1. Kein Look-ahead.
    positions = [strategy(MarketView(bars, i)) for i in range(len(bars) - 1)]

    per_bar: list[float] = []  # Netto je Bar (Gross; Kosten auf dem Schlussbar)
    for t in range(1, len(bars)):
        move = bars[t].close - bars[t - 1].close
        per_bar.append(int(positions[t - 1]) * move * cs * vol)

    # Trades = Laeufe gleicher Richtung; Kosten je Roundturn aufs jeweilige Schlussfeld.
    trade_log: list[TradeRecord] = []
    c_spread = c_comm = c_slip = c_fin_paid = carry_income = 0.0
    for start, end, side in _runs(positions):
        entry_price = bars[start].close
        exit_price = bars[end + 1].close
        # Naechte = ueberquerte Mitternachts-Rollover (nach Kalendertag), nicht Bars.
        # Korrekt fuer Tages- UND Stundenbars: ein Intraday-Halt kreuzt 0 Naechte, ein
        # Fr->Mo-Halt 3 (Fr->Sa->So->Mo). Triple = Rollover, dessen Start-Tag der
        # Dreifach-Wochentag ist (man haelt VOM Triple-Tag in den Folgetag).
        entry_date = bars[start].ts.date()
        exit_date = bars[end + 1].ts.date()
        nights = (exit_date - entry_date).days
        triple = 0
        if tri_weekday is not None:
            cursor = entry_date
            while cursor < exit_date:
                if cursor.weekday() == tri_weekday:
                    triple += 1
                cursor += timedelta(days=1)
        price = Decimal(str(entry_price))
        breakdown = order_roundturn_cost(
            fees=spec.fees,
            contract_size=spec.contract_size,
            pip_size=spec.pip_size,
            bid=price,
            ask=price + spec.spread_pips * spec.pip_size,
            side=OrderSide.BUY if side is Signal.LONG else OrderSide.SELL,
            volume=spec.volume,
            quote_currency=spec.quote_currency,
            holding_nights=nights,
            triple_swap_nights=triple,
            slippage_pips_per_side=spec.slippage_pips_per_side,
        )
        signed_total = float(breakdown.total)
        fin = float(breakdown.financing)  # + = gezahlt (Kosten), - = Carry-Gutschrift
        c_spread += float(breakdown.spread)
        c_comm += float(breakdown.commission)
        c_slip += float(breakdown.slippage)
        c_fin_paid += max(0.0, fin)
        carry_income += max(0.0, -fin)
        gross = int(side) * (exit_price - entry_price) * cs * vol
        per_bar[end] -= signed_total  # Netto-Transaktionskosten (Carry mindert sie)
        trade_log.append(
            TradeRecord(
                entry_ts=bars[start].ts.isoformat(),
                exit_ts=bars[end + 1].ts.isoformat(),
                side=side.name,
                nights=nights,
                gross=gross,
                cost=signed_total,
                net=gross - signed_total,
            )
        )

    equity_base = cs * vol * bars[0].close / lev
    if not math.isfinite(equity_base) or equity_base <= 0:
        raise ValueError(f"equity_base ungueltig ({equity_base}); Preis/Hebel pruefen")
    returns = [value / equity_base for value in per_bar]
    equity = [equity_base]
    for value in per_bar:
        equity.append(equity[-1] + value)

    per_obs = 0.0
    if len(returns) >= 2:
        stdev = statistics.pstdev(returns)
        if stdev > 0:
            per_obs = statistics.fmean(returns) / stdev
    annualised = per_obs * math.sqrt(spec.obs_per_year)

    nets = [t.net for t in trade_log]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x < 0]
    gross_return = sum(t.gross for t in trade_log) / equity_base
    net_return = sum(nets) / equity_base

    # Trade-Sharpe: eine Beobachtung je Trade (nicht je Bar). Ehrlich bei seltenem
    # Handel -- waehrend eines Halts sind Bar-Renditen autokorreliert, die Bar-Sharpe
    # ueberschaetzt die effektive Stichprobe.
    trade_returns = [x / equity_base for x in nets]
    trade_per_obs = 0.0
    if len(trade_returns) >= 2:
        tstd = statistics.pstdev(trade_returns)
        if tstd > 0:
            trade_per_obs = statistics.fmean(trade_returns) / tstd
    span_days = (bars[-1].ts - bars[0].ts).days
    span_years = span_days / 365.25 if span_days > 0 else 1.0 / 365.25
    trade_sharpe = trade_per_obs * math.sqrt(len(trade_log) / span_years)

    # Huerde = Gesamtperioden-Reibung als Anteil des Eigenkapitals (NICHT p. a.):
    # trades_pro_bar * bars kuerzt sich zu Trades, also hurdle = Reibung / equity_base.
    n_bars = len(bars)
    trades_per_bar = len(trade_log) / n_bars if n_bars else 0.0
    notional = cs * vol * bars[0].close
    total_friction = c_spread + c_comm + c_slip + c_fin_paid  # immer >= 0
    cost_bp = (
        (total_friction / len(trade_log) / notional * 10000.0) if trade_log else 0.0
    )
    hurdle = trades_per_bar * n_bars * (cost_bp / 10000.0) * lev

    return BacktestReport(
        strategy_id=strategy_id,
        bars=len(bars),
        trades=len(trade_log),
        gross_return=gross_return,
        cost_spread=c_spread,
        cost_commission=c_comm,
        cost_slippage=c_slip,
        cost_financing=c_fin_paid,
        carry_income=carry_income,
        net_return=net_return,
        annualised_sharpe=annualised,
        trade_sharpe=trade_sharpe,
        annualisation=f"Bar: sqrt({spec.obs_per_year:.0f}); Trade: sqrt(Trades/Jahr)",
        max_drawdown=_drawdown(equity),
        hit_rate=(len(wins) / len(nets)) if nets else 0.0,
        mean_win=statistics.fmean(wins) if wins else 0.0,
        mean_loss=statistics.fmean(losses) if losses else 0.0,
        hurdle_pct=hurdle,
        net_over_hurdle=(gross_return - hurdle),
        seed=seed,
        data_checksum=data_checksum,
        code_commit=code_commit,
        obs_per_year=spec.obs_per_year,
        trade_log=tuple(trade_log),
    )


@dataclass(frozen=True)
class WalkForwardResult:
    """Walk-Forward-Ergebnis: ein Bericht je Test-Fenster + wie viele positiv sind."""

    folds: tuple[BacktestReport, ...]
    positive_folds: int
    total_folds: int


def _bar_ranges(bars: Sequence[BarRow]) -> list[Range]:
    """Jede Bar als Zeitintervall [ts, naechste ts) in ms fuer die Split-Funktionen."""
    out: list[Range] = []
    for i, bar in enumerate(bars):
        start = int(bar.ts.timestamp() * 1000)
        if i + 1 < len(bars):
            end = int(bars[i + 1].ts.timestamp() * 1000)
        else:
            end = start + 86_400_000
        out.append(Range(start, end))
    return out


def run_walk_forward(
    bars: Sequence[BarRow],
    strategy_factory: Callable[[], Strategy],
    spec: MarketSpec,
    k: int,
    *,
    purge_ms: int,
    embargo_ms: int,
    strategy_id: str,
    seed: int,
    data_checksum: str,
    code_commit: str,
    version: str = "v1",
    ledger_path: str | None = None,
) -> WalkForwardResult:
    """Fahre die Strategie ueber ``k`` Walk-Forward-Test-Fenster (``splits.py``).

    Purge und Embargo sind pflichtig (kein stiller Default). **Ehrliche Grenze:** ohne
    einen Trainings-/Fit-Schritt je Fenster gaten Purge/Embargo hier noch NICHTS -- sie
    schliessen nur Trainingsindizes aus, die eine zustandslose Strategie nicht hat.
    Pflichtig fuer den spaeteren Fit-Schritt (S7 in SPAETER.md). Je Fenster ein frischer
    Strategie-Bau, damit ein zustandsbehafteter Generator nicht ueber Fenster leckt.
    ``positive_folds`` geht in die Kriterien: ein Ein-Fenster-Edge ist keiner.
    """
    folds = purged_walk_forward_indices(
        _bar_ranges(bars), k, purge_ms=purge_ms, embargo_ms=embargo_ms
    )
    reports: list[BacktestReport] = []
    for fold_index, (_train_idx, test_idx) in enumerate(folds):
        if len(test_idx) < 3:
            continue
        window = [bars[j] for j in test_idx]
        report = run_backtest(
            window, strategy_factory(), spec,
            strategy_id=f"{strategy_id}#fold{fold_index}", seed=seed + fold_index,
            data_checksum=data_checksum, code_commit=code_commit,
        )
        reports.append(report)
        if ledger_path is not None:
            # Jeder Lauf zaehlt (Kernregel 6.1): die Folds gehen unter dem BASIS-
            # ``strategy_id`` ins Register, damit die Deflation ihre wahre Zahl kennt.
            trials.append(
                trials.new_trial(
                    strategy_id=strategy_id, version=version,
                    instruments=(spec.symbol,),
                    period_start=window[0].ts, period_end=window[-1].ts,
                    leverage=int(spec.leverage),
                    parameters={"fold": fold_index, "seed": seed + fold_index},
                    outcome="completed", sharpe=report.annualised_sharpe,
                    net_expectancy=report.net_return, trades=report.trades,
                ),
                ledger_path,
            )
    positive = sum(1 for report in reports if report.net_return > 0)
    return WalkForwardResult(
        folds=tuple(reports), positive_folds=positive, total_folds=len(reports)
    )


def deflated_sharpe_for_report(
    report: BacktestReport,
    *,
    strategy_id: str,
    version: str | None = None,
    ledger_path: str | None = None,
) -> float:
    """Deflationiere die Berichts-Sharpe gegen die WAHRE Versuchszahl aus dem Register.

    Bindet den Bericht an ``gates/criteria.py`` mit dem echten ``trial_count`` -- ohne
    diese Anbindung waere die Deflation ein toter Gate. Rueckgabe: Wahrscheinlichkeit
    (Bailey/Lopez de Prado), dass die Sharpe echt ist und kein Zufallsfund unter vielen
    Versuchen. Je mehr Versuche im Register, desto strenger.
    """
    n_trials = max(
        1, trials.trial_count(strategy_id, version=version, path=ledger_path)
    )
    observations = max(2, report.bars - 1)
    per_obs = report.annualised_sharpe / math.sqrt(report.obs_per_year)
    return deflated_sharpe_ratio(
        observed_sharpe=per_obs, observations=observations, trials=n_trials
    )


def run_registered_backtest(
    bars: Sequence[BarRow],
    strategy: Strategy,
    spec: MarketSpec,
    *,
    strategy_id: str,
    version: str,
    seed: int,
    data_checksum: str,
    code_commit: str,
    ledger_path: str | None = None,
    ts: datetime | None = None,
) -> BacktestReport:
    """Wie ``run_backtest``, haengt aber IMMER einen Versuchsregister-Eintrag an --
    auch bei Fehler/Abbruch (jeder Lauf zaehlt, sonst ist die Deflation blind).
    """
    stamp = ts or datetime.now(UTC)
    period_start = bars[0].ts if bars else stamp
    period_end = bars[-1].ts if bars else stamp
    try:
        report = run_backtest(
            bars, strategy, spec, strategy_id=strategy_id, seed=seed,
            data_checksum=data_checksum, code_commit=code_commit,
        )
    except Exception as exc:  # jeder Lauf zaehlt -- auch unerwartete Fehler
        outcome = "aborted" if isinstance(exc, LookAheadError) else "error"
        trials.append(
            trials.new_trial(
                strategy_id=strategy_id, version=version, instruments=(spec.symbol,),
                period_start=period_start, period_end=period_end,
                leverage=int(spec.leverage),
                parameters={"seed": seed, "error": str(exc)},
                outcome=outcome, ts=stamp,
            ),
            ledger_path,
        )
        raise
    trials.append(
        trials.new_trial(
            strategy_id=strategy_id, version=version, instruments=(spec.symbol,),
            period_start=period_start, period_end=period_end,
            leverage=int(spec.leverage), parameters={"seed": seed},
            outcome="completed", sharpe=report.annualised_sharpe,
            net_expectancy=report.net_return, trades=report.trades, ts=stamp,
        ),
        ledger_path,
    )
    return report

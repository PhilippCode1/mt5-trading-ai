"""Lernphase: bewerten und ordnen (Phase 9.5).

Die Lernphase erzeugt keinen Vorteil. Sie findet ihn — falls einer da ist —
schneller. Eine Bibliothek aus hundert unvalidierten Strategien ist keine
hundertfache Chance, sondern ein hundertfaches Mehrfachtestproblem.

**Vier Grenzen, im Code verankert und nicht nur beschrieben:**

1. *Kein automatisches Freischalten.* Dieses Modul liefert ``Ranking`` und
   ``Proposal``. Es hat keine Funktion, die einen Zustand aendert, und keinen
   Zugriff auf die Registry.
2. *Kein selbstmodifizierender Code.* Ein Vorschlag ist ein **Parametersatz**,
   niemals Quelltext. ``Proposal.parameters`` ist ein Dict aus Zahlen und
   Zeichenketten; :func:`validate_proposal` lehnt alles ab, was nach Code aussieht.
3. *Keine Optimierung ohne Ledger-Eintrag.* :func:`propose_parameter_sets`
   verlangt einen Ledger-Pfad und traegt jeden Vorschlag als Versuch ein, bevor
   er zurueckgegeben wird.
4. *Kein Training auf Trades, die nie stattfanden.* :func:`rank_strategies`
   rechnet ausschliesslich mit ``mt.trades``-Zeilen. Unterdrueckte Bewertungen
   gehen in die Diagnose ein, nie in die Ergebnisrechnung.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

from mt5_trading_ai.gates import trials as trials_ledger

LEARNING_PHASE_VERSION = "learning-phase-v1"

#: Zeichenketten, die einen Parameterwert als Codeversuch entlarven.
_CODE_MARKERS = re.compile(
    r"(^|[^A-Za-z0-9_])(import|exec|eval|lambda|__[a-z]+__|os\.|subprocess|open\s*\()",
)


class LearningPhaseError(ValueError):
    """Eine der vier Grenzen wurde verletzt. Kein Vorschlag verlaesst das Modul."""


@dataclass(frozen=True)
class TradeRow:
    """Ein **stattgefundener** Trade. Hypothetische Trades gibt es hier nicht."""

    strategy_id: str
    version: str
    instrument: str
    asset_class: str
    opened_at: datetime
    closed_at: datetime | None
    net_pnl_r: float
    execution_mode: str


@dataclass(frozen=True)
class EvaluationRow:
    """Eine Bewertung, auch ohne Trade. Nur fuer die Diagnose."""

    strategy_id: str
    instrument: str
    ts: datetime
    score_total: float | None
    decision: str


@dataclass(frozen=True)
class Ranking:
    strategy_id: str
    version: str
    trades: int
    mean_r: float
    stdev_r: float
    hit_rate: float
    total_r: float
    expected_sharpe: float | None
    #: Abweichung zwischen Backtest-Erwartung und Realitaet, in R je Trade.
    backtest_delta_r: float | None


@dataclass(frozen=True)
class Weakness:
    dimension: str
    key: str
    trades: int
    mean_r: float


@dataclass(frozen=True)
class Proposal:
    """Ein **neuer Kandidat**. Er durchlaeuft den vollen Weg aus 9.2."""

    strategy_id: str
    base_version: str
    parameters: dict[str, Any]
    rationale: str
    state: str = "candidate"
    version: str = ""


@dataclass(frozen=True)
class LearningReport:
    ranking: tuple[Ranking, ...]
    weaknesses: tuple[Weakness, ...]
    proposals: tuple[Proposal, ...]
    trade_rate: float
    version: str = LEARNING_PHASE_VERSION
    notes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Grenze 4: nur stattgefundene Trades
# ---------------------------------------------------------------------------


def rank_strategies(
    trades: Sequence[TradeRow],
    *,
    backtest_expectation_r: dict[tuple[str, str], float] | None = None,
    min_trades: int = 1,
) -> tuple[Ranking, ...]:
    """Rangliste nach realisierten Kennzahlen. Nur ``trades``, nie Bewertungen."""
    grouped: dict[tuple[str, str], list[TradeRow]] = defaultdict(list)
    for trade in trades:
        if trade.closed_at is None:
            continue  # ein offener Trade hat kein Ergebnis
        grouped[(trade.strategy_id, trade.version)].append(trade)

    expectations = backtest_expectation_r or {}
    out: list[Ranking] = []
    for key, rows in grouped.items():
        if len(rows) < min_trades:
            continue
        values = [row.net_pnl_r for row in rows]
        mean = fmean(values)
        stdev = pstdev(values) if len(values) > 1 else 0.0
        wins = sum(1 for value in values if value > 0)
        expected_sharpe = (mean / stdev) if stdev > 0 else None
        expected = expectations.get(key)
        out.append(
            Ranking(
                strategy_id=key[0],
                version=key[1],
                trades=len(rows),
                mean_r=mean,
                stdev_r=stdev,
                hit_rate=wins / len(rows),
                total_r=sum(values),
                expected_sharpe=expected_sharpe,
                backtest_delta_r=None if expected is None else mean - expected,
            )
        )
    out.sort(key=lambda item: (-item.mean_r, item.strategy_id, item.version))
    return tuple(out)


def find_weaknesses(
    trades: Sequence[TradeRow],
    *,
    min_trades: int = 10,
    threshold_r: float = 0.0,
) -> tuple[Weakness, ...]:
    """Regime, Tageszeiten und Instrumente mit systematischer Schwaeche."""
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for trade in trades:
        if trade.closed_at is None:
            continue
        buckets[("instrument", trade.instrument)].append(trade.net_pnl_r)
        buckets[("asset_class", trade.asset_class)].append(trade.net_pnl_r)
        buckets[("hour_utc", f"{trade.opened_at.hour:02d}")].append(trade.net_pnl_r)
        buckets[("weekday", str(trade.opened_at.weekday()))].append(trade.net_pnl_r)

    out: list[Weakness] = []
    for (dimension, key), values in buckets.items():
        if len(values) < min_trades:
            continue
        mean = fmean(values)
        if mean < threshold_r:
            out.append(
                Weakness(dimension=dimension, key=key, trades=len(values), mean_r=mean)
            )
    out.sort(key=lambda item: (item.mean_r, item.dimension, item.key))
    return tuple(out)


def observed_trade_rate(evaluations: Sequence[EvaluationRow]) -> float:
    """Anteil der Bewertungen, die zu einem Trade fuehrten. Soll klein sein."""
    if not evaluations:
        return 0.0
    traded = sum(1 for row in evaluations if row.decision == "traded")
    return traded / len(evaluations)


# ---------------------------------------------------------------------------
# Grenze 2: ein Vorschlag ist ein Parametersatz, niemals Quelltext
# ---------------------------------------------------------------------------


def validate_proposal(proposal: Proposal) -> None:
    if proposal.state != "candidate":
        raise LearningPhaseError(
            f"Ein Vorschlag ist immer ein Kandidat, nicht {proposal.state!r}. "
            "Die Lernphase schaltet nichts frei."
        )
    for name, value in proposal.parameters.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise LearningPhaseError(f"Parametername unbrauchbar: {name!r}")
        if isinstance(value, bool | int | float):
            continue
        if isinstance(value, str):
            if _CODE_MARKERS.search(value):
                raise LearningPhaseError(
                    f"Parameter {name!r} sieht nach Code aus. "
                    "Kein selbstmodifizierender Code."
                )
            continue
        raise LearningPhaseError(
            f"Parameter {name!r} hat einen unzulaessigen Typ {type(value).__name__}. "
            "Erlaubt sind Zahlen, Wahrheitswerte und einfache Zeichenketten."
        )


# ---------------------------------------------------------------------------
# Grenze 3: keine Optimierung ohne Ledger-Eintrag
# ---------------------------------------------------------------------------


def propose_parameter_sets(
    proposals: Sequence[Proposal],
    *,
    ledger_path: Path | str,
    instruments: Sequence[str],
    period_start: datetime,
    period_end: datetime,
    leverage: int,
    data_checksum: str,
    code_commit: str,
    now: datetime,
) -> tuple[Proposal, ...]:
    """Jeder Vorschlag wird geprueft **und** als Versuch im Ledger vermerkt.

    Der Ledger-Eintrag entsteht **vor** der Rueckgabe. Wer den Vorschlag nutzt,
    kann den Versuchszaehler nicht mehr umgehen; genau darauf beruht die
    Deflated Sharpe Ratio.

    Herkunft (Paket 6): Auch ein blosser Vorschlag benennt Datenpruefsumme und
    Codestand -- man kann eine Optimierung nicht einmal *vorschlagen*, ohne zu
    sagen, gegen welche verifizierten Daten und welchen Code sie laufen soll.
    Der Aufrufer liefert beide (fail-closed am Gate-Rand); dieses Modul koppelt
    sich nicht an git.
    """
    if not proposals:
        return ()
    accepted: list[Proposal] = []
    for proposal in proposals:
        validate_proposal(proposal)
        trial = trials_ledger.new_trial(
            strategy_id=proposal.strategy_id,
            version=proposal.version or f"{proposal.base_version}+proposal",
            instruments=instruments,
            period_start=period_start,
            period_end=period_end,
            leverage=leverage,
            parameters=proposal.parameters,
            outcome="aborted",
            data_checksum=data_checksum,
            code_commit=code_commit,
            notes=f"Lernphase-Vorschlag: {proposal.rationale}",
            ts=now,
        )
        trials_ledger.append(trial, ledger_path)
        accepted.append(proposal)
    return tuple(accepted)


def build_report(
    *,
    trades: Sequence[TradeRow],
    evaluations: Sequence[EvaluationRow],
    proposals: Sequence[Proposal] = (),
    backtest_expectation_r: dict[tuple[str, str], float] | None = None,
) -> LearningReport:
    """Der Bericht. Er aendert nichts — er beschreibt."""
    notes: list[str] = []
    paper_only = {trade.execution_mode for trade in trades}
    if paper_only and paper_only <= {"paper"}:
        notes.append(
            "Nur Papier-Trades ausgewertet; keine Aussage ueber reale Ausfuehrung."
        )
    return LearningReport(
        ranking=rank_strategies(trades, backtest_expectation_r=backtest_expectation_r),
        weaknesses=find_weaknesses(trades),
        proposals=tuple(proposals),
        trade_rate=observed_trade_rate(evaluations),
        notes=tuple(notes),
    )

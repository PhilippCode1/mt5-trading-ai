"""Vorregistrierte Kriterien und ihre Auswertung (Phase 9.3).

Die Kriterien werden **vor** dem ersten Backtest festgelegt und sind danach
unveraenderlich. Diese Datei wertet sie aus; sie legt sie nicht fest.

Zwei Regeln bestimmen die Bauart:

* **Alle Kriterien. Kein „fast".** Es gibt keine Gewichtung, keine Punktzahl und
  keinen Gesamtwert, gegen den man optimieren koennte. Ein Kriterium ist erfuellt
  oder nicht.
* **Nicht bewertbar gilt als nicht erfuellt.** Fehlt eine Eingabe, ist das
  Kriterium ``met=False`` mit Grund ``not_evaluable`` — nicht ``True`` und nicht
  uebersprungen.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

STRATEGY_CRITERIA_VERSION = "strategy-criteria-v1"

#: Euler-Mascheroni-Konstante, fuer die erwartete Maximal-Sharpe
#: unter der Nullhypothese.
_EULER_MASCHERONI = 0.5772156649015329


@dataclass(frozen=True)
class Preregistration:
    """Die Schwellen. Vor dem ersten Backtest festgelegt, danach unveraenderlich."""

    min_net_expectancy: float = 0.0
    min_annualised_sharpe: float = 1.0
    min_deflated_sharpe: float = 0.95
    min_positive_folds: int = 4
    total_folds: int = 5
    min_positive_instruments: int = 3
    total_instruments: int = 5
    min_random_percentile: float = 0.95
    random_runs: int = 1000
    max_drawdown: float = 0.25
    min_trades: int = 500
    cost_stress_multiplier: float = 1.5

    def as_dict(self) -> dict[str, Any]:
        return dict(vars(self))


@dataclass(frozen=True)
class BacktestEvidence:
    """Ergebnis eines Backtests. ``None`` heisst nicht bewertbar, nicht null."""

    net_expectancy: float | None = None
    annualised_sharpe: float | None = None
    deflated_sharpe: float | None = None
    positive_folds: int | None = None
    positive_instruments: int | None = None
    random_percentile: float | None = None
    max_drawdown: float | None = None
    trades: int | None = None
    net_expectancy_at_stressed_cost: float | None = None
    trial_count: int | None = None


@dataclass(frozen=True)
class CriterionResult:
    name: str
    met: bool
    observed: Any
    required: Any
    reason: str | None = None


@dataclass(frozen=True)
class CriteriaVerdict:
    passed: bool
    results: tuple[CriterionResult, ...]
    version: str = STRATEGY_CRITERIA_VERSION
    unmet: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "version": self.version,
            "unmet": list(self.unmet),
            "results": [
                {
                    "name": r.name,
                    "met": r.met,
                    "observed": r.observed,
                    "required": r.required,
                    "reason": r.reason,
                }
                for r in self.results
            ],
        }


def _check(
    name: str, observed: Any, required: Any, predicate: bool | None
) -> CriterionResult:
    if observed is None or predicate is None:
        return CriterionResult(name, False, observed, required, "not_evaluable")
    return CriterionResult(name, bool(predicate), observed, required, None)


def evaluate_criteria(
    evidence: BacktestEvidence,
    prereg: Preregistration,
) -> CriteriaVerdict:
    """Alle Kriterien aus 9.3.

    Ein einziges nicht erfuelltes Kriterium genuegt zum Nein.
    """
    e, p = evidence, prereg
    results = [
        _check(
            "net_expectancy_positive",
            e.net_expectancy,
            f"> {p.min_net_expectancy}",
            (
                None
                if e.net_expectancy is None
                else e.net_expectancy > p.min_net_expectancy
            ),
        ),
        _check(
            "annualised_sharpe",
            e.annualised_sharpe,
            f">= {p.min_annualised_sharpe}",
            (
                None
                if e.annualised_sharpe is None
                else e.annualised_sharpe >= p.min_annualised_sharpe
            ),
        ),
        _check(
            "deflated_sharpe",
            e.deflated_sharpe,
            f"> {p.min_deflated_sharpe}",
            (
                None
                if e.deflated_sharpe is None
                else e.deflated_sharpe > p.min_deflated_sharpe
            ),
        ),
        _check(
            "walk_forward_folds",
            e.positive_folds,
            f">= {p.min_positive_folds} von {p.total_folds}",
            (
                None
                if e.positive_folds is None
                else e.positive_folds >= p.min_positive_folds
            ),
        ),
        _check(
            "instrument_breadth",
            e.positive_instruments,
            f">= {p.min_positive_instruments} von {p.total_instruments}",
            (
                None
                if e.positive_instruments is None
                else e.positive_instruments >= p.min_positive_instruments
            ),
        ),
        _check(
            "random_percentile",
            e.random_percentile,
            f"> {p.min_random_percentile} gegen {p.random_runs} Zufallslaeufe",
            (
                None
                if e.random_percentile is None
                else e.random_percentile > p.min_random_percentile
            ),
        ),
        _check(
            "max_drawdown",
            e.max_drawdown,
            f"< {p.max_drawdown}",
            None if e.max_drawdown is None else e.max_drawdown < p.max_drawdown,
        ),
        _check(
            "trade_count",
            e.trades,
            f">= {p.min_trades}",
            None if e.trades is None else e.trades >= p.min_trades,
        ),
        _check(
            "cost_stress",
            e.net_expectancy_at_stressed_cost,
            f"> 0 bei {p.cost_stress_multiplier}-facher Kostenannahme",
            (
                None
                if e.net_expectancy_at_stressed_cost is None
                else e.net_expectancy_at_stressed_cost > 0.0
            ),
        ),
        _check(
            "trial_count_honest",
            e.trial_count,
            ">= 1, aus dem Trials-Ledger",
            None if e.trial_count is None else e.trial_count >= 1,
        ),
    ]
    unmet = tuple(r.name for r in results if not r.met)
    return CriteriaVerdict(passed=not unmet, results=tuple(results), unmet=unmet)


# ---------------------------------------------------------------------------
# Deflated Sharpe Ratio
# ---------------------------------------------------------------------------


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse Standardnormalverteilung (Acklam-Approximation, Fehler < 1.15e-9)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p muss echt zwischen 0 und 1 liegen")
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def expected_max_sharpe(trials: int, sharpe_variance: float) -> float:
    """Erwartete Maximal-Sharpe unter der Nullhypothese bei ``trials`` Versuchen.

    Wer hundert Varianten testet, findet zufaellig eine mit hoher Sharpe. Diese
    Funktion sagt, wie hoch „zufaellig" ist.

    ``sharpe_variance`` muss endlich und **echt positiv** sein. Frueher stand hier
    ``math.sqrt(max(0.0, sharpe_variance))``: eine negative oder eine Null-Varianz
    wurde stillschweigend zu ``sigma = 0``, die Huerde damit exakt 0 und die
    Deflation vollstaendig aufgehoben -- der Aufruf sah unveraendert richtig aus und
    lieferte die unkorrigierte Sharpe zurueck. Ein Rueckfall auf einen Vorgabewert
    genau in der schmeichelnden Richtung; deshalb jetzt ein Fehler.
    """
    if trials < 1:
        raise ValueError("trials muss >= 1 sein")
    if not math.isfinite(sharpe_variance) or sharpe_variance <= 0.0:
        raise ValueError(
            f"sharpe_variance muss endlich und > 0 sein, nicht {sharpe_variance!r} — "
            "sonst ist die Deflationshuerde 0 und die Korrektur still aufgehoben"
        )
    if trials == 1:
        return 0.0
    sigma = math.sqrt(sharpe_variance)
    n = float(trials)
    return sigma * (
        (1.0 - _EULER_MASCHERONI) * _norm_ppf(1.0 - 1.0 / n)
        + _EULER_MASCHERONI * _norm_ppf(1.0 - 1.0 / (n * math.e))
    )


def deflated_sharpe_ratio(
    *,
    observed_sharpe: float,
    observations: int,
    trials: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_variance: float | None = None,
) -> float:
    """Deflated Sharpe Ratio nach Bailey/Lopez de Prado.

    ``observed_sharpe`` ist die **nicht annualisierte** Sharpe je Beobachtung.
    ``trials`` ist der ehrliche Versuchszaehler aus dem Trials-Ledger — jeder
    Lauf zaehlt, auch Fehlversuche. Er kommt aus
    ``gates/trials.py::deflation_trials`` und nie aus einer Konstante: eine fest
    verdrahtete Zahl sagt nichts darueber, wie viel tatsaechlich gesucht wurde.
    Gezaehlt wird dort in ganzen **Kampagnen** und nicht als Registerstand zur
    Aufrufzeit — sonst haenge diese Zahl daran, als wievielter ein Lauf einer Reihe
    gefahren wurde, und eine DSR, die man nicht nachrechnen kann, belegt nichts.

    WAS DIE VOREINSTELLUNG VON ``sharpe_variance`` IST -- UND WAS NICHT
    -------------------------------------------------------------------
    ``sharpe_variance`` ist bei Bailey/Lopez de Prado die Varianz der Sharpe-Werte
    **ueber die Versuche**. Ohne Angabe setzt diese Funktion dafuer die
    Stichprobenvarianz eines einzelnen Schaetzers ein, ``denom / (observations - 1)``.
    Das ist der Wert, den die Versuchs-Sharpes unter der Nullhypothese haetten, wenn
    alle auf gleich vielen Beobachtungen geschaetzt werden und keiner einen Vorteil
    hat; die Deflation reduziert sich damit exakt auf „ziehe vom z-Wert das erwartete
    Maximum aus ``trials`` Standardnormalen ab".

    Diese Voreinstellung ist damit **nicht konservativ**, wie hier frueher stand,
    sondern das **untere Ende** des vertretbaren Bereichs: streuen die Versuche
    staerker als reines Schaetzrauschen -- verschiedene Merkmale, verschiedene
    Parameter --, ist die wahre Varianz groesser, die Huerde hoeher und die DSR
    kleiner. Die Richtung ist gemessen und einseitig: bei ``observed_sharpe=0.2759``,
    ``observations=64``, ``trials=8`` liefert die Voreinstellung (Sigma 0,128) eine
    DSR von 0,755, eine gemessene Versuchsstreuung von Sigma 0,5 dagegen 0,0002.
    Wer die Sharpes seiner Versuche kennt, reicht ihre Varianz herein; das kann die
    DSR nur senken, nie heben.

    Nicht geaendert wurde der Wert selbst. Ein groesserer Vorgabewert (etwa 1,0)
    waere keine Verschaerfung, sondern ein Einheitenfehler -- 1,0 ist die Streuung
    **annualisierter** Sharpes, und gegen die nicht annualisierte Sharpe gehalten
    ergaebe sie eine Huerde, die kein Kandidat je nehmen kann. Eine Ampel, die nie
    gruen wird, prueft so wenig wie eine, die nie rot wird.
    """
    if observations < 2:
        raise ValueError("observations muss >= 2 sein")
    if trials < 1:
        raise ValueError("trials muss >= 1 sein")
    if sharpe_variance is not None and (
        not math.isfinite(sharpe_variance) or sharpe_variance <= 0.0
    ):
        raise ValueError(
            f"sharpe_variance muss endlich und > 0 sein, nicht {sharpe_variance!r} — "
            "ein nicht positiver Wert hob die Deflation frueher still auf"
        )

    denom = (
        1.0 - skewness * observed_sharpe + (kurtosis - 1.0) / 4.0 * observed_sharpe**2
    )
    if denom <= 0:
        # Die Momente widersprechen sich (die Varianz der Sharpe-Schaetzung waere
        # negativ). Kein Urteil moeglich -> 0, die fehlschlagende Seite.
        return 0.0

    if sharpe_variance is None:
        sharpe_variance = denom / (observations - 1)

    sr0 = expected_max_sharpe(trials, sharpe_variance)
    z = (observed_sharpe - sr0) * math.sqrt(observations - 1) / math.sqrt(denom)
    return _norm_cdf(z)


def annualise_sharpe(
    per_observation_sharpe: float, observations_per_year: float
) -> float:
    if observations_per_year <= 0:
        raise ValueError("observations_per_year muss > 0 sein")
    return per_observation_sharpe * math.sqrt(observations_per_year)


def percentile_against_random(
    observed: float, random_results: Sequence[float]
) -> float:
    """Anteil der Zufallslaeufe, die schlechter sind als das Ergebnis."""
    if not random_results:
        raise ValueError("random_results darf nicht leer sein")
    worse = sum(1 for value in random_results if value < observed)
    return worse / len(random_results)

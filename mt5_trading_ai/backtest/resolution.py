"""Aufloesung einer Ereignisstudie — kann sie den Effekt ueberhaupt sehen?

WARUM DIESES MODUL
------------------
Eine Ereignisstudie misst, ob um einen bekannten Zeitpunkt herum ein Kurseffekt liegt.
Sie kann das nur, wenn der gesuchte Effekt gross genug ist, um aus dem Rauschen der
Fensterrendite herauszuragen. Ist er das nicht, liefert die Studie trotzdem eine Zahl —
und die Zahl ist Rauschen. Genau daran waere die erste Fassung von Paket 3 gescheitert:
sie haette in 17 von 20 geplanten Faellen gemessen, ohne sehen zu koennen.

Die Bedingung hat drei Zutaten und lautet::

    noetige_Sharpe(N, T) x Fensterstreuung  <=  wirtschaftlich noetiger Effekt

* **N** ist die Ereigniszahl. Sie folgt aus Ereignisfrequenz und Historientiefe.
* **T** ist die Zahl der Versuche, gegen die deflationiert wird. Sie treibt die noetige
  Sharpe nach oben — wer viel sucht, muss mehr finden.
* **Fensterstreuung** ist die Standardabweichung der Fensterrendite, in Basispunkten.
  Sie wird **gemessen**, nicht aus dem ATR geschaetzt (siehe ``dispersion_bps``).
* Der **wirtschaftlich noetige Effekt** ist ein Vielfaches der Round-Turn-Kosten K.

Ist die Bedingung verletzt, wird der Kandidat **vor** der Messung ausgesondert. Das
kostet keinen Versuch und ist selbst ein Ergebnis: „diese Frage ist mit diesen Daten
nicht beantwortbar, und hier ist die Rechnung dazu."

DIE UMKEHRUNG, DIE DEN AUSSCHLAG GIBT
--------------------------------------
Die noetige Sharpe faellt mit der Wurzel der Ereigniszahl, die Fensterstreuung waechst
mit der Wurzel der Fensterlaenge. Beides zusammen heisst: **haeufige Ereignisse in
kurzen Fenstern** sind aufloesbar, seltene Ereignisse in langen Fenstern nicht —
unabhaengig davon, wie plausibel die zugrundeliegende Zwangslage ist. Plausibilitaet und
Nachweisbarkeit sind zwei verschiedene Dinge.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio

RESOLUTION_POLICY_VERSION = "resolution-v1"

#: Schwelle des Deflationsurteils. Wie ``gates/criteria.py`` und ``ABBRUCH.md``.
DEFAULT_DSR_THRESHOLD = 0.95

#: Vielfaches der Round-Turn-Kosten, das ein Effekt erreichen muss (M6.1).
DEFAULT_COST_FACTOR = 3.0


class ResolutionError(ValueError):
    """Die Aufloesung ist nicht berechenbar. Fail-closed: keine Studie."""


@dataclass(frozen=True)
class ResolutionVerdict:
    """Kann diese Studie den gesuchten Effekt von Null trennen?

    ``ratio`` ist das Verhaeltnis aus nachweisbarem und wirtschaftlich noetigem Effekt.
    Werte ueber 1 heissen: die Studie ist fuer genau den Effekt blind, auf den es
    ankommt.
    """

    events: int
    trials: int
    dispersion_bps: float
    cost_bps: float
    required_sharpe: float
    detectable_bps: float
    needed_bps: float
    ratio: float

    @property
    def resolvable(self) -> bool:
        return self.ratio <= 1.0


def required_sharpe(
    observations: int,
    trials: int,
    *,
    threshold: float = DEFAULT_DSR_THRESHOLD,
) -> float:
    """Kleinste Sharpe je Beobachtung, die die Deflationsschwelle erreicht.

    Binaere Suche statt geschlossener Form: die Deflationsformel ist in ``criteria.py``
    zusammengesetzt (Bailey/Lopez de Prado mit Acklam-Inverse), und sie dort umzustellen
    hiesse, eine geprueften Funktion nachzubauen. Die Suche kostet 80 Auswertungen.
    """
    if observations < 2:
        raise ResolutionError(
            f"observations muss >= 2 sein (bekommen: {observations}) — "
            "eine Studie mit weniger als zwei Ereignissen ist keine"
        )
    if trials < 1:
        raise ResolutionError(f"trials muss >= 1 sein (bekommen: {trials})")
    if not 0.0 < threshold < 1.0:
        raise ResolutionError(f"threshold ausserhalb (0, 1): {threshold}")

    low, high = 0.0, 5.0
    if deflated_sharpe_ratio(
        observed_sharpe=high, observations=observations, trials=trials
    ) < threshold:
        raise ResolutionError(
            f"selbst eine Sharpe von {high} erreicht die Schwelle {threshold} nicht "
            f"(N={observations}, T={trials}) — die Deflation ist hier unerfuellbar"
        )
    for _ in range(80):
        mid = (low + high) / 2
        if (
            deflated_sharpe_ratio(
                observed_sharpe=mid, observations=observations, trials=trials
            )
            >= threshold
        ):
            high = mid
        else:
            low = mid
    return high


def window_returns_bps(closes: list[float], window_bars: int) -> list[float]:
    """Renditen ueber **nicht ueberlappende** Fenster, in Basispunkten.

    Nicht ueberlappend, weil ueberlappende Fenster dieselbe Kursbewegung mehrfach
    zaehlen: die Streuung saehe kleiner aus, als sie ist, und die Aufloesung damit
    besser. Das waere ein Fehler in genau der Richtung, die schmeichelt.
    """
    if window_bars < 1:
        raise ResolutionError("window_bars muss >= 1 sein")
    out: list[float] = []
    for start in range(0, len(closes) - window_bars, window_bars):
        anfang = closes[start]
        ende = closes[start + window_bars]
        if anfang <= 0:
            raise ResolutionError(f"Schlusskurs <= 0 an Position {start}: {anfang}")
        out.append((ende - anfang) / anfang * 10_000.0)
    return out


def dispersion_bps(returns: list[float]) -> float:
    """Standardabweichung der Fensterrendite in bp — die gemessene Streuung."""
    if len(returns) < 2:
        raise ResolutionError(
            f"Streuung braucht mindestens zwei Fenster (bekommen: {len(returns)})"
        )
    return statistics.stdev(returns)


def assess(
    *,
    events: int,
    trials: int,
    dispersion: float,
    cost_bps: float,
    cost_factor: float = DEFAULT_COST_FACTOR,
    threshold: float = DEFAULT_DSR_THRESHOLD,
) -> ResolutionVerdict:
    """Das Urteil: ist diese Kombination aus Kandidat und Instrument aufloesbar?"""
    if dispersion <= 0:
        raise ResolutionError(f"Fensterstreuung muss positiv sein: {dispersion}")
    if cost_bps <= 0:
        raise ResolutionError(f"Round-Turn-Kosten muessen positiv sein: {cost_bps}")
    if cost_factor <= 0:
        raise ResolutionError(f"cost_factor muss positiv sein: {cost_factor}")

    sharpe = required_sharpe(events, trials, threshold=threshold)
    detectable = sharpe * dispersion
    needed = cost_factor * cost_bps
    return ResolutionVerdict(
        events=events,
        trials=trials,
        dispersion_bps=dispersion,
        cost_bps=cost_bps,
        required_sharpe=sharpe,
        detectable_bps=detectable,
        needed_bps=needed,
        ratio=detectable / needed,
    )


def min_events_for_resolution(
    *,
    trials: int,
    dispersion: float,
    cost_bps: float,
    cost_factor: float = DEFAULT_COST_FACTOR,
    threshold: float = DEFAULT_DSR_THRESHOLD,
    ceiling: int = 1_000_000,
) -> int | None:
    """Wie viele Ereignisse braeuchte es, damit diese Kombination aufloesbar wird?

    Gibt ``None``, wenn selbst ``ceiling`` Ereignisse nicht reichen. Die Zahl ist die
    ehrliche Antwort auf „was fehlt uns?" — sie sagt, ob eine tiefere Historie helfen
    wuerde oder ob das Instrument fuer diese Frage grundsaetzlich zu verrauscht ist.
    """
    low, high = 2, ceiling
    if assess(
        events=high,
        trials=trials,
        dispersion=dispersion,
        cost_bps=cost_bps,
        cost_factor=cost_factor,
        threshold=threshold,
    ).ratio > 1.0:
        return None
    while low < high:
        mid = (low + high) // 2
        verdict = assess(
            events=mid,
            trials=trials,
            dispersion=dispersion,
            cost_bps=cost_bps,
            cost_factor=cost_factor,
            threshold=threshold,
        )
        if verdict.resolvable:
            high = mid
        else:
            low = mid + 1
    return low

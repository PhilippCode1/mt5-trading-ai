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

* **N** ist die Zahl der Beobachtungen, die das Deflationsurteil TATSAECHLICH sieht --
  nicht die Ereigniszahl des Kandidaten. Siehe den naechsten Abschnitt.
* **T** ist die Zahl der Versuche, gegen die deflationiert wird. Sie treibt die noetige
  Sharpe nach oben — wer viel sucht, muss mehr finden.
* **Fensterstreuung** ist die Standardabweichung der Fensterrendite, in Basispunkten.
  Sie wird **gemessen**, nicht aus dem ATR geschaetzt (siehe ``dispersion_bps``).
* Der **wirtschaftlich noetige Effekt** ist ein Vielfaches der Round-Turn-Kosten K.

Ist die Bedingung verletzt, wird der Kandidat **vor** der Messung ausgesondert. Das
kostet keinen Versuch und ist selbst ein Ergebnis: „diese Frage ist mit diesen Daten
nicht beantwortbar, und hier ist die Rechnung dazu."

N IST NICHT DIE EREIGNISZAHL
----------------------------
Der einzige Grund, warum ``required_sharpe`` ueberhaupt eine Beobachtungszahl braucht,
ist das Deflationsurteil -- und das laeuft in der Ereignisstudie nicht auf allen
Ereignissen, sondern auf dem **Out-of-Sample-Teil**
(``ereignisstudie.bestaetige``: ``bereinigt[int(n * (1 - OOS_ANTEIL)):]``, also einem
Drittel). Wer die volle Ereigniszahl einsetzt, rechnet die Huerde um Wurzel(3), also
rund Faktor 1,7, zu klein -- und damit in genau der Richtung, die schmeichelt.

Darum ist ``oos_share`` in ``assess`` ein **pflichtiges** Argument ohne Vorgabewert.
Ein Vorgabewert von 1,0 waere ein stiller Rueckfall auf ebenjenen Fehler: der Aufruf
saehe unveraendert richtig aus und rechnete unveraendert falsch. Wer die Deflation auf
der ganzen Stichprobe fuehrt, sagt das mit ``oos_share=1.0`` ausdruecklich.

Diese Stelle ist die zweite Auspraegung des Fehlers, der in
``ABSCHLUSS-3a/09-EIGENE-FEHLER.md`` unter Nr. 6 steht: dort lief die Rechnung gegen die
geplante statt die messbare Ereigniszahl, hier gegen die gemessene statt die
deflationierte. Beide Male ist die eingesetzte Stichprobe groesser als die, auf der das
Urteil faellt.

DIE UMKEHRUNG, DIE DEN AUSSCHLAG GIBT
--------------------------------------
Die noetige Sharpe faellt mit der Wurzel der Beobachtungszahl, die Fensterstreuung
waechst mit der Wurzel der Fensterlaenge. Beides zusammen heisst: **haeufige Ereignisse
in kurzen Fenstern** sind aufloesbar, seltene Ereignisse in langen Fenstern nicht —
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

    ``events`` und ``deflation_events`` stehen beide hier, weil sie auseinanderfallen
    und der Unterschied der ganze Punkt ist: gerechnet wird mit ``deflation_events``,
    berichtet wird gern mit ``events``. Wer nur eine der beiden Zahlen ablegt, laedt
    genau die Verwechslung wieder ein, die diese Felder trennen sollen.
    """

    events: int
    oos_share: float
    deflation_events: int
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


def deflation_observations(events: int, *, oos_share: float) -> int:
    """Wie viele Beobachtungen das Deflationsurteil von ``events`` Ereignissen sieht.

    Die Arithmetik ist absichtlich Zeichen fuer Zeichen die aus
    ``ereignisstudie.bestaetige``::

        schnitt = int(len(bereinigt) * (1.0 - OOS_ANTEIL))
        oos = bereinigt[schnitt:]

    ``int`` schneidet ab statt zu runden, und bei kleinen Stichproben macht das einen
    ganzen Wert Unterschied. Eine „saubere" Rundung hier waere eine zweite Umsetzung
    derselben Rechnung -- die Fehlerklasse, an der dieses Vorhaben schon zweimal haengen
    geblieben ist. ``tests/test_resolution.py`` haelt die Zahl gegen das, was
    ``bestaetige`` in ``Bestaetigung.dsr_n`` tatsaechlich meldet.
    """
    if events < 2:
        raise ResolutionError(f"events muss >= 2 sein (bekommen: {events})")
    if not 0.0 < oos_share <= 1.0:
        raise ResolutionError(
            f"oos_share ausserhalb (0, 1]: {oos_share} -- ein Anteil von 1,0 heisst "
            "„die Deflation sieht die ganze Stichprobe\", alles darueber ist sinnlos"
        )
    return events - int(events * (1.0 - oos_share))


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
    oos_share: float,
    cost_factor: float = DEFAULT_COST_FACTOR,
    threshold: float = DEFAULT_DSR_THRESHOLD,
) -> ResolutionVerdict:
    """Das Urteil: ist diese Kombination aus Kandidat und Instrument aufloesbar?

    ``oos_share`` ist pflichtig und hat bewusst keinen Vorgabewert -- die Begruendung
    steht im Modulkopf unter „N IST NICHT DIE EREIGNISZAHL".
    """
    if dispersion <= 0:
        raise ResolutionError(f"Fensterstreuung muss positiv sein: {dispersion}")
    if cost_bps <= 0:
        raise ResolutionError(f"Round-Turn-Kosten muessen positiv sein: {cost_bps}")
    if cost_factor <= 0:
        raise ResolutionError(f"cost_factor muss positiv sein: {cost_factor}")

    beobachtungen = deflation_observations(events, oos_share=oos_share)
    if beobachtungen < 2:
        raise ResolutionError(
            f"aus {events} Ereignissen bleiben bei einem Out-of-Sample-Anteil von "
            f"{oos_share} nur {beobachtungen} Beobachtungen fuer die Deflation -- "
            "das ist keine Stichprobe"
        )
    sharpe = required_sharpe(beobachtungen, trials, threshold=threshold)
    detectable = sharpe * dispersion
    needed = cost_factor * cost_bps
    return ResolutionVerdict(
        events=events,
        oos_share=oos_share,
        deflation_events=beobachtungen,
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
    oos_share: float,
    cost_factor: float = DEFAULT_COST_FACTOR,
    threshold: float = DEFAULT_DSR_THRESHOLD,
    ceiling: int = 1_000_000,
) -> int | None:
    """Wie viele Ereignisse braeuchte es, damit diese Kombination aufloesbar wird?

    Gibt ``None``, wenn selbst ``ceiling`` Ereignisse nicht reichen. Die Zahl ist die
    ehrliche Antwort auf „was fehlt uns?" — sie sagt, ob eine tiefere Historie helfen
    wuerde oder ob das Instrument fuer diese Frage grundsaetzlich zu verrauscht ist.

    Gezaehlt werden **Ereignisse**, nicht Deflationsbeobachtungen: die Zahl soll direkt
    beantwortbar sein („so viele Monatsenden brauchen wir"), und ein Aufrufer, der sie
    mit der Beobachtungszahl verwechselt, unterschaetzt den Bedarf um den Kehrwert von
    ``oos_share``.
    """
    high = ceiling
    if assess(
        events=high,
        trials=trials,
        dispersion=dispersion,
        cost_bps=cost_bps,
        oos_share=oos_share,
        cost_factor=cost_factor,
        threshold=threshold,
    ).ratio > 1.0:
        return None
    # Kleinste Ereigniszahl, aus der ueberhaupt zwei Deflationsbeobachtungen werden.
    # Bei einem Drittel Out-of-Sample sind das vier Ereignisse, nicht zwei. Die Schleife
    # endet garantiert, weil der Aufruf oben fuer ``ceiling`` bereits durchlief.
    low = 2
    while deflation_observations(low, oos_share=oos_share) < 2:
        low += 1
    while low < high:
        mid = (low + high) // 2
        verdict = assess(
            events=mid,
            trials=trials,
            dispersion=dispersion,
            cost_bps=cost_bps,
            oos_share=oos_share,
            cost_factor=cost_factor,
            threshold=threshold,
        )
        if verdict.resolvable:
            high = mid
        else:
            low = mid + 1
    return low

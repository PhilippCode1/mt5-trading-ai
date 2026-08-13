"""Einfache, ernsthafte Signallogiken fuer den Edge-Test -- ohne Optimierung.

Der Edge-Test (Paket 4) fragt nicht nach der besten Strategie, sondern: ist auf EURUSD
nach realistischen Kosten ueberhaupt etwas zu holen? Darum hier die einfachste denkbare
Logik, die eine ernsthafte Hypothese verkoerpert. Die Parameter sind per Konvention
gesetzt, **nicht** auf die Daten optimiert -- getestet wird die Hypothese, nicht eine
getunte Variante.
"""

from __future__ import annotations

import math

from mt5_trading_ai.backtest.engine import MarketView, Signal, Strategy


def moving_average_crossover(fast: int, slow: int) -> Strategy:
    """Trendfolge: LONG wenn der schnelle Durchschnitt ueber dem langsamen liegt.

    Hypothese: EURUSD trendet, und ein schnellerer gleitender Durchschnitt ueber einem
    langsameren fasst diesen Trend. Die Strategie sieht nur die Vergangenheit
    (``MarketView``), entscheidet am Close, ausgefuehrt einen Bar spaeter (shift(1)).
    """
    if fast < 1 or slow <= fast:
        raise ValueError("0 < fast < slow noetig")

    def strategy(view: MarketView) -> Signal:
        history = view.history()
        if len(history) < slow:
            return Signal.FLAT  # noch nicht genug Historie fuer den langsamen MA
        closes = [bar.close for bar in history[-slow:]]
        slow_ma = sum(closes) / slow
        fast_ma = sum(closes[-fast:]) / fast
        if fast_ma > slow_ma:
            return Signal.LONG
        if fast_ma < slow_ma:
            return Signal.SHORT
        return Signal.FLAT

    return strategy


def mean_reversion_zscore(lookback: int, entry_z: float, exit_z: float) -> Strategy:
    """Mittelwertrueckkehr: gegen extreme Ausschlaege wetten, bis der Kurs zurueckkehrt.

    Hypothese (ernsthaft und **verschieden** von der Trendfolge): EURUSD schwankt
    intraday um einen gleitenden Mittelwert. Ein Kurs ``entry_z`` Standardabweichungen
    darunter kehrt eher zurueck als weiter zu fallen (LONG); ``entry_z`` darueber ->
    SHORT. Gehalten wird, bis der z-Wert wieder innerhalb von ``exit_z`` liegt (FLAT).

    Zustandsbehaftet: die aktuelle Richtung wird ueber die Bars gehalten (eine echte
    Mittelwertrueckkehr steigt nicht bei jedem Bar neu ein). Das ist kein Look-ahead --
    ``MarketView`` gibt weiterhin nur die Vergangenheit frei; der Zustand ist allein die
    zuletzt gewaehlte Richtung. Die Engine ruft die Strategie streng in Bar-Reihenfolge
    auf, der Lauf bleibt reproduzierbar. Parameter per Konvention, **nicht** optimiert.
    """
    if lookback < 2:
        raise ValueError("lookback >= 2 noetig")
    if not entry_z > exit_z >= 0:
        raise ValueError("entry_z > exit_z >= 0 noetig")

    pos = Signal.FLAT

    def strategy(view: MarketView) -> Signal:
        nonlocal pos
        history = view.history()
        if len(history) < lookback:
            pos = Signal.FLAT
            return pos
        window = [bar.close for bar in history[-lookback:]]
        mean = sum(window) / lookback
        var = sum((x - mean) ** 2 for x in window) / (lookback - 1)
        if var <= 0.0:
            pos = Signal.FLAT
            return pos
        z = (window[-1] - mean) / math.sqrt(var)
        if pos is Signal.FLAT:
            if z <= -entry_z:
                pos = Signal.LONG
            elif z >= entry_z:
                pos = Signal.SHORT
        elif pos is Signal.LONG and z >= -exit_z:
            pos = Signal.FLAT
        elif pos is Signal.SHORT and z <= exit_z:
            pos = Signal.FLAT
        return pos

    return strategy


def volatility_breakout(lookback: int) -> Strategy:
    """Donchian-Kanal-Ausbruch: LONG bei neuem Hoch, SHORT bei neuem Tief, sonst halten.

    Dritte ernsthafte Hypothese, verschieden von Trendfolge (MA) und Mittelwertrückkehr:
    der Markt bricht aus einer Spanne aus und laeuft weiter. Bricht der Schlusskurs
    ueber das hoechste Hoch der letzten ``lookback`` Bars -> LONG; unter das tiefste
    Tief -> SHORT; dazwischen wird die letzte Richtung gehalten (Turtle-Stil,
    zustandsbehaftet). Die Vergangenheit kommt allein aus ``MarketView``; der Zustand
    ist nur die letzte Richtung. Die Engine ruft streng in Bar-Reihenfolge auf, der
    Lauf bleibt reproduzierbar. ``lookback`` per Konvention (48), **nicht** optimiert.
    """
    if lookback < 2:
        raise ValueError("lookback >= 2 noetig")

    pos = Signal.FLAT

    def strategy(view: MarketView) -> Signal:
        nonlocal pos
        history = view.history()
        if len(history) < lookback + 1:
            pos = Signal.FLAT
            return pos
        prior = history[-lookback - 1:-1]  # die lookback Bars VOR dem aktuellen
        upper = max(bar.high for bar in prior)
        lower = min(bar.low for bar in prior)
        close = history[-1].close
        if close > upper:
            pos = Signal.LONG
        elif close < lower:
            pos = Signal.SHORT
        return pos  # dazwischen: letzte Richtung halten

    return strategy

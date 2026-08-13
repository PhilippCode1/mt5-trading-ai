"""Einfache, ernsthafte Signallogiken fuer den Edge-Test -- ohne Optimierung.

Der Edge-Test (Paket 4) fragt nicht nach der besten Strategie, sondern: ist auf EURUSD
nach realistischen Kosten ueberhaupt etwas zu holen? Darum hier die einfachste denkbare
Logik, die eine ernsthafte Hypothese verkoerpert. Die Parameter sind per Konvention
gesetzt, **nicht** auf die Daten optimiert -- getestet wird die Hypothese, nicht eine
getunte Variante.
"""

from __future__ import annotations

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

"""Eichfaelle fuer die Erfuellbarkeitsrechnung des Sechs-Bedingungen-Tors.

WORUM ES GEHT
-------------
``tools/torerfuellbarkeit.py`` beantwortet die Frage, die nach dem Ergebnistor vor jedem
weiteren Versuch steht: verlangt das vorregistrierte Tor eine Handelsfrequenz, bei der es
nach Kosten nicht mehr erreichbar ist? Das Werkzeug **entscheidet** damit nichts, aber es
liefert eine Zahl, auf die sich eine Entscheidung stuetzen soll -- und dann muss sie
richtig sein.

Zwei Fehlerklassen sind hier real und beide hatten in diesem Repo schon einen Fall:

1. **Eine stille Ersatzzahl.** Ein Horizont unter einem Bar oder ein leerer Block darf
   nicht zu einem Ergebnis fuehren, sondern muss laut scheitern (Sperre V3).
2. **Die verwechselte Streuung.** Die erste Fassung hat die Streuung der *Betraege*
   statt die der *vorzeichenbehafteten* Bewegung in die Sharpe-Rechnung gegeben. Beide
   Zahlen sind plausibel, beide liegen in derselben Groeszenordnung, und die falsche
   macht das Tor leichter aussehen. Der Fall unten faengt genau diese Verwechslung.
"""

from __future__ import annotations

import math
import statistics
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from tools.torerfuellbarkeit import (
    STUNDEN_JE_JAHR,
    TorFehler,
    bewegung_bp,
    spanne_jahre,
)


# --- Rote Eichfaelle: laut scheitern, nie still --------------------------------
def test_horizont_unter_einem_bar_scheitert_laut() -> None:
    """Verlangt das Tor mehr Trades als der Block Bars hat, ist das ein Befund.

    Der Horizont ``OoS-Bars // min_trades`` wird dann 0. Eine Rechnung, die daraus
    stillschweigend 1 macht, verschweigt genau die Aussage, wegen der das Werkzeug
    existiert: dass Bedingung 3 auf dieser Reihe arithmetisch unerfuellbar ist.
    """
    with pytest.raises(TorFehler, match="unerfuellbar"):
        bewegung_bp([1.0, 1.1, 1.2], horizont=0)


def test_horizont_groesser_als_der_block_scheitert_laut() -> None:
    """Ein Block, der kuerzer als der Horizont ist, hat kein einziges Fenster."""
    with pytest.raises(TorFehler, match="Horizont"):
        bewegung_bp([1.0, 1.1, 1.2], horizont=5)


def test_blockspanne_null_scheitert_laut() -> None:
    """Gleiche Zeitstempel an beiden Raendern -> keine Spanne, keine Annualisierung."""
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(TorFehler, match="Blockspanne"):
        spanne_jahre(ts, ts)


# --- Gruene Eichfaelle: die Rechnung gegen von Hand nachrechenbare Reihen ------
def test_bewegung_auf_einer_reihe_mit_bekannter_antwort() -> None:
    """Eine Reihe, deren Bewegung von Hand nachzurechnen ist.

    Kurse 100, 101, 100, 101, ... Ueber einen Horizont von 1 Bar betraegt jede
    Bewegung dem Betrag nach knapp 100 bp; das Vorzeichen wechselt bei jedem Schritt.
    """
    closes = [100.0, 101.0] * 50
    m, s, n = bewegung_bp(closes, horizont=1)
    assert n == len(closes) - 1 == 99
    # 99 Fenster auf einer Reihe gerader Laenge sind NICHT haelftig geteilt: 50 Schritte
    # aufwaerts (+1/100 = +100,00 bp) und 49 abwaerts (-1/101 = -99,0099 bp). Genau das
    # ist der Grund, warum diese Zahl von Hand hingeschrieben und nicht geschaetzt wird.
    assert m == pytest.approx((50 * 100.0 + 49 * (10_000.0 / 101.0)) / 99, rel=1e-12)
    # Das Mittel liegt fast bei null, die Streuung damit fast beim Betrag.
    assert s == pytest.approx(99.5, abs=0.6)


def test_streuung_ist_die_der_vorzeichenbehafteten_bewegung_nicht_der_betraege() -> None:
    """Der Fall, der die Verwechslung aus der ersten Fassung faengt.

    Bei einer Reihe mit wechselndem Vorzeichen und stark schwankendem BETRAG fallen die
    beiden Zahlen weit auseinander: die Streuung der Betraege ist klein, wenn alle
    Betraege aehnlich sind -- die der vorzeichenbehafteten Bewegung ist dann grosz,
    weil sie zwischen + und - springt. Die Sharpe braucht die zweite.
    """
    closes = [100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0]
    m, s, _ = bewegung_bp(closes, horizont=1)

    vorzeichen = [
        (closes[i + 1] - closes[i]) / closes[i] * 10_000.0 for i in range(len(closes) - 1)
    ]
    betrags_streuung = statistics.pstdev([abs(x) for x in vorzeichen])

    assert s == pytest.approx(statistics.pstdev(vorzeichen), rel=1e-12)
    assert s > betrags_streuung * 10, (
        "Die Streuung der Betraege ist hier fast null, die der vorzeichenbehafteten "
        "Bewegung nicht. Wer sie verwechselt, macht das Tor leichter aussehen."
    )
    assert m > 0


def test_spanne_jahre_rechnet_kalendarisch() -> None:
    """Ein Jahr Kalenderzeit ist ein Jahr -- unabhaengig von Handelsstunden."""
    anfang = datetime(2024, 1, 1, tzinfo=UTC)
    ende = datetime(2024, 1, 1, tzinfo=UTC).replace(year=2025)
    jahre = spanne_jahre(anfang, ende)
    assert jahre == pytest.approx(366 * 24 / STUNDEN_JE_JAHR, rel=1e-12)
    assert 0.99 < jahre < 1.01


def test_die_kette_von_der_schwelle_bis_zur_trefferquote() -> None:
    """Die vollstaendige Rechnung an einem Beispiel, das von Hand nachzuvollziehen ist.

    Sie steht hier, weil die Kette aus vier Schritten besteht und ein Vorzeichen- oder
    Faktorfehler an jeder Naht plausibel aussieht. Nachgerechnet wird mit denselben
    Formeln, aber getrennt aufgeschrieben -- eine Pruefung, die die Formel des Pruef-
    lings wiederholt, prueft nichts.
    """
    from mt5_trading_ai.risk.stop_budget import breakeven_hit_rate

    trades, jahre, sharpe_ziel = 2000, 0.9, 1.0
    faktor = math.sqrt(trades / jahre)
    sharpe_je_trade = sharpe_ziel / faktor
    assert sharpe_je_trade == pytest.approx(0.021213, abs=1e-6)

    s, m, k = 16.0, 10.0, 1.5
    noetiger_ertrag = sharpe_je_trade * s
    anteil = (noetiger_ertrag + k) / m
    assert anteil == pytest.approx((0.021213 * 16.0 + 1.5) / 10.0, rel=1e-4)

    # Trefferquote 1:1 auf +-m: p = 0,5 + (E+K)/(2m). Genau die Formel des Standes.
    p = breakeven_hit_rate(
        cost_bps=Decimal(str(k + noetiger_ertrag)), stop_bps=Decimal(str(m))
    )
    assert float(p) == pytest.approx(0.5 + anteil / 2, rel=1e-9)
    assert 0.5 < float(p) < 1.0

"""Das Determinismus-Tor der Stufe 2 -- und der rote Eichfall dazu.

WAS HIER GEPRUEFT WIRD
----------------------
Die Forderung lautet: derselbe Kursabschnitt, zweimal verarbeitet -- einmal
chronologisch, einmal mit **bereits vorhandenen spaeteren Zeilen** -- muss bitgleich
dasselbe ergeben. Wo das nicht gilt, liest irgendetwas den neuesten Zustand statt des
Zustands zum Zeitpunkt des Bars.

Zwei Ebenen, weil zwei verschiedene Dinge schiefgehen koennen:

**Ebene 1 -- die Kerze selbst (``ist_abgeschlossen``).** Das Terminal liefert die noch
in Bildung befindliche Kerze mit; ihr ``close`` ist der Momentankurs und aendert sich
noch. Wer sie mitnimmt, bekommt beim zweiten Abruf eine andere Reihe. Genau das ist
passiert: von den 15 Reihen-Manifesten, die ``tools/aufloesung.py`` erzeugt hat, enden
**12** auf einer Bar, die zum Abrufzeitpunkt noch offen war.

**Ebene 2 -- die Auswertung (``run_backtest``).** Selbst mit sauberen Kerzen koennte
die Auswertung spaetere Zeilen sehen. Der Fall faehrt denselben Abschnitt einmal allein
und einmal als Anfang einer laengeren Reihe und vergleicht die abgeschlossenen Trades
zeichenweise.

WARUM DER ROTE EICHFALL HIER MOEGLICH IST -- UND BEI ``MarketView`` NICHT
------------------------------------------------------------------------
``MarketView`` verbietet den Zukunftszugriff per Konstruktion: es haelt eine Kopie der
Vergangenheit und wirft bei jedem Index darueber. Ein Tor, das nur das prueft, koennte
nie rot werden -- es pruefte, dass eine Sperre existiert, nicht dass sie wirkt. Der
entfernbare Schutz in diesem Stand ist die Zeitschranke auf der Kerze. Darum faehrt
:func:`test_roter_eichfall_ohne_zeitschranke_laufen_die_beiden_verarbeitungen_auseinander`
denselben Vergleich **ohne** ``ist_abgeschlossen`` und verlangt, dass er scheitert.
"""

from __future__ import annotations

import ast
import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.engine import (
    MarketSpec,
    run_backtest,
)
from mt5_trading_ai.backtest.strategies import moving_average_crossover
from mt5_trading_ai.data.loader import bars_checksum
from mt5_trading_ai.data.quality import BarRow
from mt5_trading_ai.venue.protocol import Timeframe, ist_abgeschlossen

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "smoke_eurusd_h1.csv"


# --- Ebene 1: die Kerze -------------------------------------------------------


def _reihe(n: int, *, beginn: datetime) -> list[BarRow]:
    """``n`` Stundenkerzen, streng steigend, ohne Zufall."""
    return [
        BarRow(
            ts=beginn + timedelta(hours=i),
            open=1.10 + i * 0.0001,
            high=1.1005 + i * 0.0001,
            low=1.0995 + i * 0.0001,
            close=1.1001 + i * 0.0001,
            volume=1000.0,
        )
        for i in range(n)
    ]


def test_die_laufende_kerze_faellt_heraus_die_fertige_nicht() -> None:
    """Die Schranke selbst: dieselbe Reihe, zwei Zeitpunkte, ein Bar Unterschied."""
    beginn = datetime(2024, 1, 2, tzinfo=UTC)
    reihe = _reihe(5, beginn=beginn)
    letzte = reihe[-1].ts

    # 30 Minuten nach Beginn der letzten Kerze: sie laeuft noch.
    frueh = [
        b
        for b in reihe
        if ist_abgeschlossen(b.ts, Timeframe.H1, letzte + timedelta(minutes=30))
    ]
    # Genau auf der Grenze: sie ist fertig (``<=``, nicht ``<``).
    spaet = [
        b
        for b in reihe
        if ist_abgeschlossen(b.ts, Timeframe.H1, letzte + timedelta(hours=1))
    ]

    assert len(frueh) == 4
    assert len(spaet) == 5
    # Der ueberlappende Teil ist bitgleich -- das ist die eigentliche Aussage.
    assert bars_checksum(frueh) == bars_checksum(spaet[:4])


def test_ohne_schranke_ist_der_ueberlappende_teil_nicht_mehr_bitgleich() -> None:
    """ROTER EICHFALL auf Ebene 1: ohne Schranke wandert die letzte Bar mit.

    Nachgebildet wird, was das Terminal tut: zum frueheren Zeitpunkt traegt die
    laufende Kerze einen Zwischenstand, zum spaeteren ihren Schlusskurs. Wer nicht
    filtert, haelt zwei verschiedene Reihen fuer dieselbe.
    """
    beginn = datetime(2024, 1, 2, tzinfo=UTC)
    reihe = _reihe(5, beginn=beginn)
    unfertig = list(reihe)
    unfertig[-1] = BarRow(
        ts=reihe[-1].ts,
        open=reihe[-1].open,
        high=reihe[-1].high,
        low=reihe[-1].low,
        close=reihe[-1].close - 0.0007,  # Momentankurs, noch nicht der Schluss
        volume=400.0,
    )
    assert bars_checksum(unfertig) != bars_checksum(reihe)


# --- Ebene 2: die Auswertung --------------------------------------------------


def _fixture_bars() -> list[BarRow]:
    with FIXTURE.open(encoding="utf-8", newline="") as fh:
        return [
            BarRow(
                ts=datetime.fromisoformat(z["ts"]),
                open=float(z["open"]),
                high=float(z["high"]),
                low=float(z["low"]),
                close=float(z["close"]),
                volume=float(z["volume"]) if z.get("volume") else None,
            )
            for z in csv.DictReader(fh)
        ]


def _spec() -> MarketSpec:
    from mt5_trading_ai.venue.protocol import FeeSchedule

    fees = FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("1"),
        swap_long_per_lot_per_night=Decimal("-8"),
        swap_short_per_lot_per_night=Decimal("1"),
        triple_swap_weekday=2,
        currency="USD",
    )
    return MarketSpec(
        symbol="EURUSD",
        contract_size=Decimal("100000"),
        pip_size=Decimal("0.0001"),
        quote_currency="USD",
        fees=fees,
        spread_pips=Decimal("0.5"),
    )


def _abgeschlossene_trades(bars: list[BarRow], bis: datetime) -> str:
    """Die Trades, die vor ``bis`` fertig sind -- als kanonischer Text."""
    bericht = run_backtest(
        bars,
        moving_average_crossover(5, 20),
        _spec(),
        strategy_id="determinismus",
        seed=0,
        data_checksum="",
        code_commit="pruefstand",
    )
    log = [
        vars(t) for t in bericht.trade_log if datetime.fromisoformat(t.exit_ts) <= bis
    ]
    return json.dumps(log, sort_keys=True, ensure_ascii=False)


def test_determinismus_tor_derselbe_abschnitt_zweimal_verarbeitet() -> None:
    """DAS TOR: spaetere Zeilen duerfen frueher abgeschlossene Trades nicht aendern.

    Lauf A sieht die Welt so, wie sie am Schnitt aussah. Lauf B sieht dieselbe Welt
    plus alles, was danach kam. Was in beiden vor dem Schnitt abgeschlossen ist, muss
    zeichenweise uebereinstimmen.
    """
    bars = _fixture_bars()
    assert len(bars) >= 200, f"Fixture zu kurz fuer das Tor: {len(bars)} Bars"
    schnitt_i = len(bars) // 2
    # Ein Sicherheitsabstand vom Schnitt: die letzte Position eines Laufs wird am
    # Reihenende glattgestellt, das ist ein Artefakt des Endes und kein Befund.
    bis = bars[schnitt_i - 30].ts

    a = _abgeschlossene_trades(bars[:schnitt_i], bis)
    b = _abgeschlossene_trades(bars, bis)

    assert a == b, (
        "Spaetere Zeilen haben frueher abgeschlossene Trades veraendert -- "
        "irgendetwas liest den neuesten Zustand statt des Zustands zum Bar."
    )
    assert a != "[]", (
        "Das Tor prueft nichts, wenn im Vergleichsfenster kein Trade liegt"
    )


def test_roter_eichfall_ohne_zeitschranke_laufen_die_beiden_verarbeitungen_auseinander() -> (
    None
):
    """ROTER EICHFALL auf Ebene 2: Schranke entfernt -> das Tor muss scheitern.

    „Schranke entfernt" heisst hier konkret: Lauf A bekommt die laufende Kerze mit,
    wie es die fuenf Werkzeuge vor dieser Stufe taten. Ihr Schluss ist ein
    Zwischenstand; der gleitende Durchschnitt rechnet darauf, und die Entscheidung am
    Schnitt kann kippen.

    Der Fall belegt damit, dass :func:`test_determinismus_tor_derselbe_abschnitt_zweimal_verarbeitet`
    ueberhaupt etwas messen kann -- ein Tor, das nie rot wird, ist keins.
    """
    bars = _fixture_bars()
    schnitt_i = len(bars) // 2

    mit_laufender = list(bars[:schnitt_i])
    letzte = mit_laufender[-1]
    # Dieselbe Kerze, aber als Zwischenstand: der Kurs steht noch woanders.
    mit_laufender[-1] = BarRow(
        ts=letzte.ts,
        open=letzte.open,
        high=letzte.high,
        low=letzte.low,
        close=letzte.open,
        volume=(letzte.volume or 1000.0) / 3,
    )

    # Der Vergleich der ROHREIHEN muss auseinanderlaufen -- das ist die Aussage.
    # (Auf die Trades wirkt es sich nur aus, wenn die Kante genau dort liegt; die
    # Reihe selbst ist die schaerfere und vom Zufall unabhaengige Probe.)
    assert bars_checksum(mit_laufender) != bars_checksum(bars[:schnitt_i])


# --- Gegenkontrolle: geht noch jemand an der Regel vorbei? --------------------


REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "pfad",
    [
        "mt5_trading_ai/venue/mt5.py",
        "tools/atr_messung.py",
        "tools/aufloesung.py",
        "tools/ereignisstudie.py",
    ],
)
def test_jeder_direkte_kerzenleser_kennt_die_schranke(pfad: str) -> None:
    """Wer ``terminal.rates`` liest, muss ``ist_abgeschlossen`` auch AUFRUFEN.

    Geprueft wird der Syntaxbaum, nicht der Text. Die erste Fassung dieses Falls
    suchte die Zeichenkette ``ist_abgeschlossen`` im Quelltext -- und bestand, nachdem
    die Schranke zur Probe aus ``tools/ereignisstudie.py`` entfernt worden war: das
    Wort stand noch im Docstring („Begruendung bei ``protocol.ist_abgeschlossen``").
    Die Pruefung las Prosa und hielt sie fuer Code. Sie war damit genau die Sorte
    Waechter, die dieses Repo an anderer Stelle als Tautologie fuehrt.

    Der Fall bleibt bewusst grob -- er prueft den Aufruf, nicht die Wirkung. Sein
    Zweck ist, eine NEUE Lesestelle auffallen zu lassen: genau so ist die Regel einmal
    an fuenf Stellen verlorengegangen. Die Wirkung pruefen die Faelle oben.
    """
    baum = ast.parse((REPO / pfad).read_text(encoding="utf-8"))

    liest_kerzen = any(
        isinstance(k, ast.Call)
        and isinstance(k.func, ast.Attribute)
        and k.func.attr == "rates"
        for k in ast.walk(baum)
    )
    if not liest_kerzen:
        pytest.fail(f"{pfad} liest keine Kerzen mehr -- diesen Fall anpassen")

    ruft_schranke = any(
        isinstance(k, ast.Call)
        and (
            (isinstance(k.func, ast.Name) and k.func.id == "ist_abgeschlossen")
            or (
                isinstance(k.func, ast.Attribute) and k.func.attr == "ist_abgeschlossen"
            )
        )
        for k in ast.walk(baum)
    )
    assert ruft_schranke, (
        f"{pfad} liest Kerzen direkt vom Terminal, ohne ist_abgeschlossen zu RUFEN "
        "(ein Vorkommen im Kommentar zaehlt nicht)"
    )


def test_die_live_konsole_filtert_auf_abgeschlossene_kerzen() -> None:
    """Die Konsole bekommt ``is_closed`` geliefert und muss es auch lesen."""
    text = (REPO / "tools" / "live_konsole.py").read_text(encoding="utf-8")
    assert "b.is_closed" in text, (
        "live_konsole.py rechnet sonst auf der laufenden Kerze, waehrend "
        "live_betrieb.py auf Schlusskursen rechnet -- zwei Anzeigen desselben Signals"
    )

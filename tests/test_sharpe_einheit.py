"""Die Einheitenfrage an der Deflation -- Befund und Feldwahl.

WORUM ES GEHT
-------------
Stufe 3 des Dauerauftrags verlangt, Rechenfehler in geldnahen Groessen **vor** dem
ersten Lauf zu korrigieren: Maximalverlust, Stueckzahlberechnung, Kennzahleinheiten.
Alle drei waren im verworfenen Stand ``bitget-btc-ai`` defekt. Hier wurde jede
nachgerechnet (Beleg: ``AUFTRAG/stufen/03-simulator/belege/01-geldnahe-groessen.txt``):
die ersten beiden rechnen richtig.

Die dritte ist kein aktiver Fehler, aber eine scharfe Kante:
:func:`deflated_sharpe_ratio` saettigt fuer jede Sharpe ab etwa 1,0 auf **1,0** --
maximale Bestaetigung. ``BacktestReport`` traegt drei verschieden skalierte
Sharpe-Felder nebeneinander; die Deflation verlangt genau eines davon. Eine
Feldverwechslung an einer Zeile drehte ein klares Nein in ein perfektes Ja.

WARUM HIER KEINE LAUFZEITSPERRE STEHT
-------------------------------------
Ein erster Versuch hat genau das gebaut: eine Sperre, die eine unplausible Sharpe je
Beobachtung abweist. Sie brach **sieben** bestehende Faelle, deren synthetische Reihen
per Konstruktion fast keine Streuung haben und darum Sharpes von 24 bis 3e13 erzeugen
-- kein Einheitenfehler, sondern deterministische Pruefdaten. Eine Sperre, die
legitime Pruefreihen bestraft, ist das falsche Werkzeug; sie wurde zurueckgenommen
(AUFTRAG/fehler.md, F-007).

Was bleibt, ist das, was wirklich schiefgehen kann und keinen Preis hat: die
**Feldwahl** festnageln, ueber den Syntaxbaum, damit ein Umschreiben auffaellt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.resolution import required_sharpe
from mt5_trading_ai.gates.criteria import (
    Preregistration,
    annualise_sharpe,
    deflated_sharpe_ratio,
)

ENGINE = (
    Path(__file__).resolve().parents[1] / "mt5_trading_ai" / "backtest" / "engine.py"
)


# --- der Befund ----------------------------------------------------------------


def test_die_deflation_saettigt_und_das_ist_die_ganze_gefahr() -> None:
    """Nagelt fest, warum die Feldwahl zaehlt -- mit Zahlen, nicht mit einer Warnung.

    Dieselbe Messung, einmal in der richtigen und einmal in der falschen Einheit:
    aus einem klar durchgefallenen Kandidaten wird einer mit maximaler Bestaetigung.
    """
    richtig = deflated_sharpe_ratio(
        observed_sharpe=0.067, observations=500, trials=1000
    )
    falsch = deflated_sharpe_ratio(
        observed_sharpe=annualise_sharpe(0.067, 252), observations=500, trials=1000
    )
    assert richtig == pytest.approx(0.039193, abs=1e-5)
    assert falsch == 1.0
    # Und die Schwelle, gegen die beide gehalten werden:
    assert Preregistration().min_deflated_sharpe == 0.95
    assert richtig < 0.95 < falsch


# --- die Feldwahl, ueber den Syntaxbaum ----------------------------------------


def _observed_sharpe_argument() -> ast.expr:
    """Das Argument, das ``deflated_sharpe_for_report`` an die Deflation gibt."""
    baum = ast.parse(ENGINE.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if not (
            isinstance(knoten, ast.FunctionDef)
            and knoten.name == "deflated_sharpe_for_report"
        ):
            continue
        for k in ast.walk(knoten):
            if (
                isinstance(k, ast.Call)
                and isinstance(k.func, ast.Name)
                and k.func.id == "deflated_sharpe_ratio"
            ):
                for kw in k.keywords:
                    if kw.arg == "observed_sharpe":
                        return kw.value
    pytest.fail(
        "deflated_sharpe_for_report gibt kein observed_sharpe an "
        "deflated_sharpe_ratio -- diesen Fall anpassen"
    )


def test_deflationiert_wird_die_nicht_annualisierte_trade_sharpe() -> None:
    """Genau ``report.trade_sharpe_per_obs`` -- kein anderes Feld, keine Umrechnung.

    Ueber den Syntaxbaum und nicht ueber den Text: ein Vorkommen des Feldnamens in
    einem Kommentar zaehlt nicht (AUFTRAG/fehler.md, F-005).
    """
    arg = _observed_sharpe_argument()
    assert isinstance(arg, ast.Attribute), (
        f"erwartet report.<feld>, bekommen {ast.dump(arg)[:80]}"
    )
    assert arg.attr == "trade_sharpe_per_obs", (
        f"deflationiert wird {arg.attr!r}. Die Deflation verlangt die NICHT "
        "annualisierte Sharpe je Beobachtung; annualised_sharpe und trade_sharpe "
        "sind beide annualisiert und liefern hier stumm DSR 1,0."
    )


@pytest.mark.parametrize("feld", ["annualised_sharpe", "trade_sharpe"])
def test_die_beiden_annualisierten_felder_stehen_nicht_dort(feld: str) -> None:
    """Gegenprobe: die Verwechslungskandidaten sind namentlich ausgeschlossen."""
    arg = _observed_sharpe_argument()
    assert not (isinstance(arg, ast.Attribute) and arg.attr == feld)


# --- die Gegenprobe: grosse Sharpes sind anderswo richtig ----------------------


def test_der_loeser_darf_grosse_sharpes_abtasten() -> None:
    """``resolution.py`` bisektiert bewusst zwischen 0,0 und 5,0.

    Diese 5,0 ist eine mathematische Klammer, keine Messung. Der Fall haelt fest,
    dass grosse Werte an dieser Stelle richtig sind -- er ist der Grund, warum eine
    Sperre in ``deflated_sharpe_ratio`` selbst falsch waere.
    """
    assert deflated_sharpe_ratio(
        observed_sharpe=5.0, observations=100, trials=12
    ) == pytest.approx(1.0)
    noetig = required_sharpe(observations=400, trials=12, threshold=0.95)
    assert 0.0 < noetig < 5.0

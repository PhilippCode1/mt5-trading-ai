"""Die Versuchszahl der Deflation — aus dem Register, nicht aus einer Konstante.

Vier Zahlen standen fuer dieselbe Groesse im Umlauf: ``VERSUCHE_ANGENOMMEN = 12`` in
der Ereignisstudie, sieben Zeilen im Register, 60 in ``ABBRUCH.md`` (Bedingung 2) und
die stille Eins, die aus ``max(1, total_trials())`` faellt, wenn das Register fehlt.
Genau eine davon ist die gemessene: die im Register.

Die Faelle unter „Eichfaelle" waeren gegen die alte Fassung fehlgeschlagen. Die Faelle
unter „Belege" haetten das auch vorher nicht getan — sie halten die Zahlen fest, mit
denen die Entscheidung begruendet ist, und sind bewusst als Belege gekennzeichnet.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.ereignisstudie import (
    Bestaetigung,
    Kerze,
    bestaetige,
    studie,
)
from mt5_trading_ai.gates import trials as ledger
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio, expected_max_sharpe

#: Der gemessene Fall aus ``ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt``: K3
#: (Monatsende-Fixing, GBPJPY), 192 gemessene Ereignisse, davon 64 Out-of-Sample. Die
#: Sharpe je Ereignis ist die, die mit der alten Konstante 12 die berichteten 0,686
#: ergibt — sie ist der Bezugspunkt fuer jede Zahl in dieser Datei.
K3_SHARPE = 0.2759
K3_OOS = 64


def _kerzen(anzahl: int) -> list[Kerze]:
    """Stundenkerzen mit wechselnder Richtung und viel Rauschen darueber.

    Wechselnd, weil ``messe_ereignis`` ein Ereignis ohne Richtung in der Vorstunde
    verwirft. Das Rauschen ueberwiegt den Effekt bewusst: eine zu saubere Reihe ergibt
    eine DSR von 0,9999 bei jeder Versuchszahl, und an einer Zahl, die schon am
    Anschlag steht, laesst sich der Unterschied nicht mehr ablesen.
    """
    start = datetime(2020, 1, 6, tzinfo=UTC)
    kerzen: list[Kerze] = []
    kurs = 100.0
    for i in range(anzahl):
        richtung = 1.0 if i % 2 == 0 else -1.0
        rendite = richtung * 2e-4 + math.sin(i * 1.7) * 5e-4
        schluss = kurs * (1.0 + rendite)
        kerzen.append(Kerze(ts=start + timedelta(hours=i), open=kurs, close=schluss))
        kurs = schluss
    return kerzen


def _register(pfad: Path, eintraege: int) -> Path:
    for nummer in range(eintraege):
        ledger.append(
            ledger.new_trial(
                strategy_id="ereignisstudie/K3",
                version="ereignisstudie-v1",
                instruments=["GBPJPY"],
                period_start=datetime(2010, 1, 1, tzinfo=UTC),
                period_end=datetime(2026, 1, 1, tzinfo=UTC),
                leverage=1,
                parameters={"lauf": nummer},
                outcome="completed",
                data_checksum="0123456789abcdef",
                code_commit="deadbeefcafef00d",
                ts=datetime(2026, 8, 17, 12, nummer, tzinfo=UTC),
            ),
            pfad,
        )
    return pfad


def _bestaetigung(pfad: Path | None) -> Bestaetigung:
    kerzen = _kerzen(400)
    ereignisse = [k.ts for k in kerzen[4:-4:4]]
    _, werte = studie(
        kandidat="erfunden",
        instrument="ERFUNDEN",
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
    )
    return bestaetige(
        werte,
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
        saat=7,
        register_pfad=pfad,
    )


# --- Eichfaelle -----------------------------------------------------------
def test_zwei_registerstaende_ergeben_zwei_dsr_werte(tmp_path: Path) -> None:
    """Der Eichfall. Die alte Fassung haette hier zweimal dieselbe Zahl geliefert.

    Sie rechnete gegen ``VERSUCHE_ANGENOMMEN = 12``, gleich was im Register stand.
    Damit war die Deflation blind fuer das Einzige, was sie messen soll: wie viel
    tatsaechlich gesucht wurde.
    """
    wenig = _bestaetigung(_register(tmp_path / "wenig.jsonl", 3))
    viel = _bestaetigung(_register(tmp_path / "viel.jsonl", 11))

    assert wenig.dsr_versuche == 4, "drei Zeilen plus der laufende Versuch"
    assert viel.dsr_versuche == 12
    assert wenig.dsr_oos != pytest.approx(viel.dsr_oos), (
        "beide Laeufe messen dieselben Kurse; unterscheiden darf sie nur die "
        "Versuchszahl — tut sie das nicht, kommt die Zahl nicht aus dem Register"
    )
    assert wenig.dsr_oos > viel.dsr_oos, "mehr Versuche muessen strenger sein"


def test_fehlendes_register_ist_ein_fehler_keine_eins(tmp_path: Path) -> None:
    """Der zweite Eichfall: ohne Register gibt es keine Deflation, also kein Urteil.

    ``total_trials`` liefert fuer eine fehlende Datei weiter null — das ist die
    ehrliche Antwort auf „wie viele Zeilen stehen da". Erst der uebliche Aufruf
    ``max(1, ...)`` macht daraus eine Eins, und bei einem Versuch deflationiert
    nichts. Diese Umdeutung findet jetzt nicht mehr statt.
    """
    fehlt = tmp_path / "nicht_da.jsonl"
    assert ledger.total_trials(fehlt) == 0

    with pytest.raises(ledger.TrialsLedgerError, match="fehlt"):
        ledger.deflation_trials(fehlt)
    with pytest.raises(ledger.TrialsLedgerError):
        _bestaetigung(fehlt)


def test_die_stille_eins_haette_die_schwelle_genommen() -> None:
    """Warum die fehlende Datei ein Fehler ist — in einer Zahl, am echten Fall.

    Dieselbe Messung (K3, Sharpe 0,2759 auf 64 Out-of-Sample-Ereignissen) besteht die
    Schwelle 0,95, wenn die Versuchszahl auf eins zurueckfaellt, und faellt beim
    tatsaechlichen Registerstand durch. Die stille Eins ist also nicht bloss ungenau,
    sie kehrt das Urteil um.
    """
    still = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=1
    )
    echt = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=8
    )
    assert still == pytest.approx(0.9842, abs=1e-4)
    assert still > 0.95
    assert echt == pytest.approx(0.7550, abs=1e-4)
    assert echt < 0.95


def test_nicht_positive_sharpe_varianz_wird_abgewiesen() -> None:
    """Eichfall zur Varianz: der Klemmwert ``max(0.0, ...)`` ist weg.

    Vorher wurde eine negative oder eine Null-Varianz zu ``sigma = 0``, die Huerde
    damit exakt null und die DSR identisch zu der bei einem einzigen Versuch — die
    Korrektur war aufgehoben, ohne dass der Aufruf anders aussah. Alte Rueckgabewerte:
    ``expected_max_sharpe(60, -1.0) == 0.0`` und eine DSR von 0,984 statt 0,422.
    """
    with pytest.raises(ValueError, match="sharpe_variance"):
        expected_max_sharpe(60, -1.0)
    with pytest.raises(ValueError, match="sharpe_variance"):
        expected_max_sharpe(60, 0.0)
    with pytest.raises(ValueError, match="sharpe_variance"):
        deflated_sharpe_ratio(
            observed_sharpe=K3_SHARPE,
            observations=K3_OOS,
            trials=60,
            sharpe_variance=-1.0,
        )
    with pytest.raises(ValueError, match="sharpe_variance"):
        deflated_sharpe_ratio(
            observed_sharpe=K3_SHARPE,
            observations=K3_OOS,
            trials=60,
            sharpe_variance=float("nan"),
        )


# --- Belege ---------------------------------------------------------------
def test_beleg_die_studie_haengt_am_register_des_repos() -> None:
    """Ohne Pfadangabe zaehlt das Register des Repos — nachgerechnet, nicht geglaubt.

    Die Zahl selbst steht hier bewusst nicht: sie waechst mit jedem Versuch. Geprueft
    ist die Verdrahtung, und die ist der Punkt.
    """
    bestaetigung = _bestaetigung(None)
    assert bestaetigung.dsr_versuche == ledger.total_trials() + 1
    assert bestaetigung.dsr_versuche == ledger.deflation_trials()


def test_beleg_der_laufende_versuch_zaehlt_mit(tmp_path: Path) -> None:
    """Das Register wird erst nach der Messung geschrieben; ohne Zuschlag zaehlt sich
    ein Lauf selbst nicht mit — und untertreiben heisst hier schmeicheln."""
    pfad = _register(tmp_path / "TRIALS.jsonl", 7)
    assert ledger.total_trials(pfad) == 7
    assert ledger.deflation_trials(pfad) == 8
    assert ledger.deflation_trials(pfad, include_running=False) == 7


def test_beleg_leeres_register_ist_kein_fehler(tmp_path: Path) -> None:
    """Ein leeres Register heisst: dies ist der erste Versuch. Dann deflationiert
    nichts, und das ist richtig — die DSR ist dann die Probabilistic Sharpe Ratio."""
    pfad = tmp_path / "TRIALS.jsonl"
    pfad.write_text("", encoding="utf-8")
    assert ledger.deflation_trials(pfad) == 1


def test_beleg_die_varianz_voreinstellung_ist_das_milde_ende() -> None:
    """Die gemeldete Vermutung, gemessen — und nur zur Haelfte bestaetigt.

    Die Voreinstellung ist die Varianz eines einzelnen Schaetzers unter der
    Nullhypothese; sie ist damit die **kleinste** vertretbare und nicht, wie im
    Docstring stand, eine konservative. Streuen die Versuche staerker, faellt die DSR:
    0,755 bei der Voreinstellung (Sigma 0,128) gegen 0,0002 bei Sigma 0,5. Geaendert
    wurde der Wert nicht — ein groesserer Vorgabewert waere ein Einheitenfehler und
    ergaebe eine Huerde, die kein Kandidat je nimmt.
    """
    voreinstellung = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=8
    )
    breiter = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=8, sharpe_variance=0.25
    )
    assert voreinstellung == pytest.approx(0.7550, abs=1e-4)
    assert breiter == pytest.approx(0.0002, abs=1e-4)
    assert breiter < voreinstellung, (
        "mehr Streuung ueber die Versuche muss strenger sein"
    )

    # Die Voreinstellung selbst: denom / (observations - 1), unveraendert.
    erwartet = (1.0 + 0.5 * K3_SHARPE**2) / (K3_OOS - 1)
    assert deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE,
        observations=K3_OOS,
        trials=8,
        sharpe_variance=erwartet,
    ) == pytest.approx(voreinstellung)

"""Die Versuchszahl der Deflation -- aus dem Register, und nachrechenbar.

Vier Zahlen standen fuer dieselbe Groesse im Umlauf: ``VERSUCHE_ANGENOMMEN = 12`` in
der Ereignisstudie, sieben Zeilen im Register, 60 in ``archiv/ABBRUCH.md`` (Bedingung 2) und
die stille Eins, die aus ``max(1, total_trials())`` faellt, wenn das Register fehlt.
Genau eine davon ist die gemessene: die im Register.

Die zweite Frage ist erst in der Reparatur dazugekommen: WANN wird gezaehlt. Die Reihe
schreibt nach jeder Studie an; wer den Registerstand zur Aufrufzeit liest, bekommt eine
Zahl, die von der Schleifenposition abhaengt. Deshalb zaehlt ``deflation_trials`` in
ganzen Kampagnen.

KEIN FALL IN DIESER DATEI FASST DAS REGISTER DES REPOS AN. ``TRIALS.jsonl`` im
Wurzelverzeichnis ist per ``.gitignore`` nicht versioniert; ein Fall, der sie braucht,
faellt auf jedem frischen Klon und besteht nur auf dem Rechner, der ihn geschrieben
hat. Jedes Register hier wird in ``tmp_path`` selbst gebaut.

Die Faelle unter „Eichfaelle" waeren gegen die jeweils vorige Fassung fehlgeschlagen.
Die Faelle unter „Belege" halten die Zahlen fest, mit denen die Entscheidung begruendet
ist, und sind bewusst als Belege gekennzeichnet.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.ereignisstudie import (
    KAMPAGNE_PRAEFIX,
    Bestaetigung,
    Kerze,
    bestaetige,
    kampagne,
    studie,
)
from mt5_trading_ai.backtest.kalender import KANDIDATEN
from mt5_trading_ai.gates import trials as ledger
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio, expected_max_sharpe

#: Der gemessene Fall aus ``archiv/ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt``: K3
#: (Monatsende-Fixing, GBPJPY), 192 gemessene Ereignisse, davon 64 Out-of-Sample. Die
#: Sharpe je Ereignis ist die, die mit der alten Konstante 12 die berichteten 0,686
#: ergibt -- sie ist der Bezugspunkt fuer jede Zahl in dieser Datei.
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


def _anhaengen(pfad: Path, strategy_id: str, nummer: int) -> Path:
    """Ein Registereintrag -- so, wie ``tools/ereignisstudie.py::_lauf`` ihn schreibt."""
    ledger.append(
        ledger.new_trial(
            strategy_id=strategy_id,
            version="ereignisstudie-v1",
            instruments=["GBPJPY"],
            period_start=datetime(2010, 1, 1, tzinfo=UTC),
            period_end=datetime(2026, 1, 1, tzinfo=UTC),
            leverage=1,
            parameters={"lauf": nummer},
            outcome="completed",
            data_checksum="0123456789abcdef",
            code_commit="deadbeefcafef00d",
            ts=datetime(2026, 8, 17, 12, 0, tzinfo=UTC) + timedelta(minutes=nummer),
        ),
        pfad,
    )
    return pfad


def _register(
    pfad: Path, eintraege: int, *, strategy_id: str = "fremd/backtest"
) -> Path:
    for nummer in range(eintraege):
        _anhaengen(pfad, strategy_id, nummer)
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
def test_die_versuchszahl_haengt_nicht_an_der_reihenfolge(tmp_path: Path) -> None:
    """Der Eichfall der Reparatur: dieselbe Studie an Position 1 und an Position 7.

    Die vorige Fassung las den Registerstand zur Aufrufzeit, und die Reihe haengt nach
    jeder Studie an. Bei Registerstand sieben sah die erste Studie acht Versuche (DSR
    0,7550) und die siebte vierzehn (DSR 0,6594) -- gleiche Kurse, gleiches Verfahren,
    anderes Urteil, allein wegen der Schleifenposition. Wer sein Wunsch-Instrument
    zuerst fahren liess, wurde am mildesten geprueft.
    """
    pfad = _register(tmp_path / "TRIALS.jsonl", 3)
    erste = _bestaetigung(pfad)

    # Die Reihe laeuft weiter und schreibt nach jeder Studie an -- sechs Laeufe spaeter
    # steht dieselbe Studie an siebter Stelle.
    for nummer in range(6):
        _anhaengen(pfad, f"{KAMPAGNE_PRAEFIX}K{nummer}", 10 + nummer)
    letzte = _bestaetigung(pfad)

    assert erste.dsr_versuche == letzte.dsr_versuche, (
        "die Versuchszahl darf nicht davon abhaengen, als wievielte eine Studie "
        "gefahren wurde -- sonst ist dsr_oos nicht nachrechenbar"
    )
    assert erste.dsr_oos == pytest.approx(letzte.dsr_oos)


def test_ein_zweiter_durchlauf_zaehlt_eine_kampagne_mehr(tmp_path: Path) -> None:
    """Order-unabhaengig heisst nicht blind: zweimal suchen ist zweimal suchen.

    Eine Zaehlung, die die eigenen Eintraege einfach ignoriert, waere gegen den
    Reihenfolge-Befund immun und zugleich schmeichelnd -- der zehnte Durchlauf saehe so
    viele Versuche wie der erste.
    """
    gross = kampagne().groesse
    pfad = tmp_path / "TRIALS.jsonl"
    _register(pfad, 2)  # zwei fremde Laeufe
    erste_kampagne = ledger.deflation_trials(kampagne(), pfad)

    for nummer in range(gross):  # eine vollstaendige Reihe laeuft durch
        _anhaengen(pfad, f"{KAMPAGNE_PRAEFIX}K{nummer}", 20 + nummer)
    zweite_kampagne = ledger.deflation_trials(kampagne(), pfad)

    assert erste_kampagne == 2 + gross
    assert zweite_kampagne == 2 + 2 * gross


def test_zwei_registerstaende_ergeben_zwei_dsr_werte(tmp_path: Path) -> None:
    """Die Zahl kommt aus dem Register, nicht aus einer Konstante.

    Gegen die Fassung mit ``VERSUCHE_ANGENOMMEN = 12`` scheiterte dieser Fall an der
    Signatur (``bestaetige`` kannte kein ``register_pfad``); die Sachaussage -- die
    alte Fassung lieferte fuer beide Registerstaende 0,338634 -- belegt er selbst
    nicht, das tut ``test_die_stille_eins_haette_die_schwelle_genommen`` an der
    echten Messung. Was er belegt, ist die Verdrahtung: verschiedene Register,
    verschiedene Urteile, in der richtigen Richtung.
    """
    gross = kampagne().groesse
    wenig = _bestaetigung(_register(tmp_path / "wenig.jsonl", 3))
    viel = _bestaetigung(_register(tmp_path / "viel.jsonl", 11))

    assert wenig.dsr_versuche == 3 + gross, "drei fremde Laeufe plus die Kampagne"
    assert viel.dsr_versuche == 11 + gross
    assert wenig.dsr_oos != pytest.approx(viel.dsr_oos), (
        "beide Laeufe messen dieselben Kurse; unterscheiden darf sie nur die "
        "Versuchszahl -- tut sie das nicht, kommt die Zahl nicht aus dem Register"
    )
    assert wenig.dsr_oos > viel.dsr_oos, "mehr Versuche muessen strenger sein"


def test_fehlendes_register_ist_ein_fehler_keine_eins(tmp_path: Path) -> None:
    """Der zweite Eichfall: ohne Register gibt es keine Deflation, also kein Urteil.

    ``total_trials`` liefert fuer eine fehlende Datei weiter null -- das ist die
    ehrliche Antwort auf „wie viele Zeilen stehen da". Erst der uebliche Aufruf
    ``max(1, ...)`` macht daraus eine Eins, und bei einem Versuch deflationiert
    nichts. Diese Umdeutung findet jetzt nicht mehr statt.
    """
    fehlt = tmp_path / "nicht_da.jsonl"
    assert ledger.total_trials(fehlt) == 0

    with pytest.raises(ledger.TrialsLedgerError, match="fehlt"):
        ledger.deflation_trials(kampagne(), fehlt)
    with pytest.raises(ledger.TrialsLedgerError):
        _bestaetigung(fehlt)


def test_ein_verlorenes_register_faellt_nicht_unter_die_kampagne(
    tmp_path: Path,
) -> None:
    """Der dritte Eichfall -- gegen die Zusicherung, die der Code vorher nicht einloeste.

    Frueher stand im Docstring, ``check_integrity`` verhindere, dass jemand durch
    Loeschen des Registers wieder bei eins landet. Das tut sie nicht: fuer eine
    fehlende wie fuer eine leere Datei meldet sie ``ok=True, lines=0``, und die alte
    Zaehlung machte daraus eins. Was es wirklich sichert, ist die angemeldete
    Kampagnengroesse -- die steht im Code und ueberlebt den Verlust der Datei.
    """
    gross = kampagne().groesse
    verloren = tmp_path / "TRIALS.jsonl"
    verloren.write_text("", encoding="utf-8")

    assert ledger.check_integrity(verloren).ok is True, (
        "check_integrity zaehlt Zeilen und beurteilt sie; einen Sollstand kennt sie "
        "nicht -- genau deshalb trug die alte Zusicherung nicht"
    )
    assert ledger.deflation_trials(kampagne(), verloren) == gross

    # Und der Fall aus dem Befund: ein abgestuerzter Lauf hat die Datei neu angelegt.
    _anhaengen(verloren, f"{KAMPAGNE_PRAEFIX}K1", 0)
    assert ledger.deflation_trials(kampagne(), verloren) == gross, (
        "eine einzelne wieder aufgetauchte Zeile darf nicht zu zwei Versuchen werden"
    )


def test_nicht_positive_sharpe_varianz_wird_abgewiesen() -> None:
    """Eichfall zur Varianz: der Klemmwert ``max(0.0, ...)`` ist weg.

    Vorher wurde eine negative oder eine Null-Varianz zu ``sigma = 0``, die Huerde
    damit exakt null und die DSR identisch zu der bei einem einzigen Versuch -- die
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
def test_beleg_die_studie_haengt_am_register_des_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Pfadangabe zaehlt das Register des Repos -- an der Verdrahtung geprueft.

    Geprueft wird, dass ``bestaetige(register_pfad=None)`` bei
    ``default_ledger_path`` landet, nicht bei einer Konstante. Das echte
    ``TRIALS.jsonl`` wird dafuer NICHT gelesen: es ist per ``.gitignore``
    unversioniert, und ein Fall, der es braucht, faellt auf jedem frischen Klon.
    """
    pfad = _register(tmp_path / "TRIALS.jsonl", 5)
    monkeypatch.setattr(ledger, "default_ledger_path", lambda: pfad)

    bestaetigung = _bestaetigung(None)
    assert bestaetigung.dsr_versuche == ledger.deflation_trials(kampagne())
    assert bestaetigung.dsr_versuche == 5 + kampagne().groesse


def test_beleg_die_kampagne_ist_das_vorregistrierte_feld() -> None:
    """Die Kampagnengroesse wird abgeleitet, nicht danebengeschrieben.

    Jede Paarung aus Kandidat und Instrument in ``kalender.KANDIDATEN`` ist ein
    angemeldeter Lauf. Eine zweite, von Hand gepflegte Zahl fuer dieselbe Groesse waere
    die naechste, die auseinanderlaeuft.
    """
    assert kampagne().praefix == KAMPAGNE_PRAEFIX
    assert kampagne().groesse == sum(len(k.instrumente) for k in KANDIDATEN)
    assert kampagne().groesse == 7, "Feld nach der Aussonderung in A1"


def test_beleg_die_kampagnenzaehlung_untertreibt_nie(tmp_path: Path) -> None:
    """Untertreiben hiesse hier schmeicheln -- also nie unter „Zeilen plus eins".

    Nachgerechnet ueber einen ganzen Zyklus: bei ``eigene = q*groesse + r`` ist
    ``(q+1)*groesse >= eigene + 1`` fuer jedes ``0 <= r < groesse``.
    """
    gross = kampagne().groesse
    pfad = tmp_path / "TRIALS.jsonl"
    _anhaengen(pfad, "fremd/backtest", 0)
    for eigene in range(1, 2 * gross + 1):
        _anhaengen(pfad, f"{KAMPAGNE_PRAEFIX}K{eigene}", eigene)
        gezaehlt = ledger.deflation_trials(kampagne(), pfad)
        assert gezaehlt >= ledger.total_trials(pfad) + 1, (
            f"bei {eigene} eigenen Zeilen zaehlt die Kampagne {gezaehlt}, der "
            f"schlichte Stand plus eins waere {ledger.total_trials(pfad) + 1}"
        )


def test_beleg_die_stille_eins_haette_die_schwelle_genommen() -> None:
    """Warum die fehlende Datei ein Fehler ist -- in einer Zahl, am echten Fall.

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


def test_beleg_wie_teuer_die_reihenfolge_war() -> None:
    """Die Spanne, um die der Befund ging -- als Zahl, nicht als Behauptung.

    Bei Registerstand sieben lagen die sieben Studien einer Reihe zwischen acht und
    vierzehn Versuchen. Beide Urteile fallen hier zwar unter die Schwelle 0,95; der
    Punkt ist nicht das Urteil, sondern dass es zwei verschiedene Zahlen fuer dieselbe
    Messung gab.
    """
    zuerst = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=8
    )
    zuletzt = deflated_sharpe_ratio(
        observed_sharpe=K3_SHARPE, observations=K3_OOS, trials=14
    )
    assert zuerst == pytest.approx(0.7550, abs=1e-4)
    assert zuletzt == pytest.approx(0.6594, abs=1e-4)
    assert zuerst > zuletzt


def test_beleg_leeres_register_ist_kein_fehler(tmp_path: Path) -> None:
    """Ein leeres Register heisst: die erste Kampagne laeuft.

    Deflationiert wird dann gegen ihre angemeldete Groesse -- nicht gegen eins. Bei
    einem einzigen Versuch ist ``expected_max_sharpe`` exakt null, die DSR waere die
    Probabilistic Sharpe Ratio, und eine angemeldete Reihe von sieben Laeufen als
    einen einzigen zu zaehlen waere die Untertreibung, die der Befund meinte.
    """
    pfad = tmp_path / "TRIALS.jsonl"
    pfad.write_text("", encoding="utf-8")
    assert ledger.deflation_trials(kampagne(), pfad) == kampagne().groesse


def test_beleg_eine_kampagne_braucht_praefix_und_groesse() -> None:
    """Fail-closed schon an der Anmeldung: keine leere Reihe, kein leeres Praefix."""
    with pytest.raises(ledger.TrialsLedgerError, match="Praefix"):
        ledger.Kampagne(praefix="  ", groesse=7)
    with pytest.raises(ledger.TrialsLedgerError, match="groesse|Kampagnengroesse"):
        ledger.Kampagne(praefix="ereignisstudie/", groesse=0)


def test_beleg_die_varianz_voreinstellung_ist_das_milde_ende() -> None:
    """Die gemeldete Vermutung, gemessen -- und nur zur Haelfte bestaetigt.

    Die Voreinstellung ist die Varianz eines einzelnen Schaetzers unter der
    Nullhypothese; sie ist damit die **kleinste** vertretbare und nicht, wie im
    Docstring stand, eine konservative. Streuen die Versuche staerker, faellt die DSR:
    0,755 bei der Voreinstellung (Sigma 0,128) gegen 0,0002 bei Sigma 0,5. Geaendert
    wurde der Wert nicht -- ein groesserer Vorgabewert waere ein Einheitenfehler und
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

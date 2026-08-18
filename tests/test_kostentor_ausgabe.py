"""Das Beleg-Tor: die Ausgabe des Kostentors gegen den eingefrorenen Beleg.

``ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt`` ist der Beleg, auf dem Abbruchbedingung 1
des Vorhabens steht. Bisher war er ein Textstueck neben dem Werkzeug: nichts hielt die
beiden zusammen. Wer das Werkzeug umbaute, konnte den Beleg still ungueltig machen --
und genau umgekehrt konnte der Beleg eine Rechnung behaupten, die das Werkzeug nicht
fuehrt. Das ist derselbe Riss, an dem die falsche ROT-Schwelle monatelang unentdeckt
blieb: dort stand die Berichtigung im Dokument und nicht im Code.

Dieser Test schliesst den Riss in beide Richtungen. Er faellt bei jeder Abweichung --
auch bei einer erwuenschten; dann ist der Beleg nachzuziehen, und zwar sichtbar im
selben Commit.

Der Lauf haengt an nichts Fluechtigem: er liest ``config/broker_costs.json`` und
``config/atr_measurements.json`` (beide versioniert), braucht kein MT5-Terminal, kein
Netz, keine Uhr und keine Umgebungsvariable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from tools import kostentor

REPO = Path(__file__).resolve().parents[1]
BELEG = REPO / "ABSCHLUSS-3a" / "07-AUSGABEN" / "kostentor.txt"

#: Der Beleg traegt die Aufrufzeile als erste und den Rueckgabewert als letzte Zeile.
KOPFZEILE = "$ python tools/kostentor.py"
FUSSZEILE = "[exit=0]"


def _beleg_zeilen() -> list[str]:
    roh = BELEG.read_text(encoding="utf-8").splitlines()
    assert roh[0] == KOPFZEILE, f"Beleg beginnt nicht mit dem Aufruf: {roh[0]!r}"
    assert roh[-1] == FUSSZEILE, f"Beleg endet nicht mit dem Ergebnis: {roh[-1]!r}"
    return roh[1:-1]


def _lauf(capsys: pytest.CaptureFixture[str], *argumente: str) -> list[str]:
    alt = sys.argv
    sys.argv = ["kostentor.py", *argumente]
    try:
        code = kostentor.main()
    finally:
        sys.argv = alt
    assert code == 0, f"Kostentor endete mit {code}"
    return capsys.readouterr().out.splitlines()


def test_die_ausgabe_stimmt_zeile_fuer_zeile_mit_dem_beleg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Zeile fuer Zeile, nicht als Ganzes -- damit die Fehlermeldung die Stelle nennt."""
    erwartet = _beleg_zeilen()
    tatsaechlich = _lauf(capsys)

    for nummer, (soll, ist) in enumerate(zip(erwartet, tatsaechlich, strict=False), 1):
        assert ist == soll, (
            f"Zeile {nummer} weicht vom eingefrorenen Beleg ab.\n"
            f"  Beleg  : {soll!r}\n"
            f"  Werkzeug: {ist!r}"
        )
    assert len(tatsaechlich) == len(erwartet), (
        f"Der Beleg hat {len(erwartet)} Zeilen, das Werkzeug druckt "
        f"{len(tatsaechlich)}."
    )


def test_das_urteil_steht_woertlich_im_beleg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Die drei Saetze, auf denen Abbruchbedingung 1 steht.

    Absichtlich getrennt vom Zeilenvergleich oben: dieser Test nennt beim Fallen
    unmittelbar, WAS sich verschoben hat -- nicht nur, dass sich etwas verschob.
    """
    ausgabe = "\n".join(_lauf(capsys))
    assert "M1-AMPEL: GRUEN" in ausgabe
    assert (
        "ic_markets_eu allein traegt 3 davon (gefordert: mindestens 3)" in ausgabe
    )
    assert "nicht bewertbar: 1 von 6 ['BTCUSD']" in ausgabe
    assert "M2-URTEIL: 13 von 18 Kostenzeilen reissen die" in ausgabe
    assert "ERGEBNIS: M1 = GRUEN. Bezugsgroesse: 18 rechenbare Kostenzeilen" in ausgabe


def test_kurz_ist_ein_praefix_der_vollen_ausgabe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--kurz`` laesst die drei hinteren Tabellen weg und rechnet nichts anders.

    Wuerde ``--kurz`` eine der Zahlen davor veraendern, gaebe es zwei Urteile aus
    einem Werkzeug -- und niemand wuesste, welches im Beleg steht.
    """
    voll = _lauf(capsys)
    kurz = _lauf(capsys, "--kurz")
    assert len(kurz) < len(voll)
    trenner = "TABELLE 3 — Jahreskostenlast L = N x H x k auf das Eigenkapital"
    schnitt = next(i for i, z in enumerate(voll) if trenner in z)
    # Vor Tabelle 3 steht in beiden Laeufen dasselbe (bis auf den Trennstrich,
    # der Tabelle 3 einleitet).
    assert kurz[: schnitt - 1] == voll[: schnitt - 1]
    assert kurz[-1] == voll[-1]


def test_der_beleg_ist_nicht_leer_und_traegt_das_ergebnis() -> None:
    """Ein Beleg, den man versehentlich leert, darf nicht still durchgehen --
    sonst waere der Vergleich oben gegen nichts gefahren."""
    zeilen = _beleg_zeilen()
    assert len(zeilen) > 400
    assert any("ERGEBNIS: M1 = " in z for z in zeilen)

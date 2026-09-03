"""Die Buchtreue: dass ein gezählter Halt auch wirklich gesperrt hat.

WORAUS DAS ENTSTANDEN IST
-------------------------
Stufe 10 hat die Buchtreue mit **98,5 % (1.340 von 1.360 Takten)** gemessen, Ziel 99 %.
Die Aufschluesselung der 20 gesperrten Takte ergab **einen einzigen Halt-Grund** --
``reconcile_drift:notional_drift_exceeds_limit`` -- und darin zwei voellig verschiedene
Lagen:

* **16 Takte** (drei kurze Laeufe): der Halt latchte und blieb stehen. In diesen Takten
  gab es **null** Eroeffnungsversuche -- der Lauf hoerte auf, es zu versuchen. Das ist
  eine echte Sperre.
* **4 Takte** (der lange Lauf, 1.122 Takte): der Halt wurde **im selben Takt aufgeloest**
  (``halt_erklaert``, ``durch: broker_schliessung``). In jedem dieser vier Takte liefen
  danach **vier Eroeffnungsversuche** normal durch, abgelehnt aus voellig anderen
  Gruenden (``cost_unverifiable``, ``Trade disabled``, ``throttle_cooldown_active``); in
  Takt 409 fuehrte einer sogar zu einer Eroeffnung. **Gesperrt hat dieser Halt nichts.**

Die Metrik zaehlte beide Lagen gleich -- und widersprach damit ihrem eigenen Docstring
(„Beides sperrt jede Eroeffnung").

WARUM DIE REIHENFOLGE IM TAKT BLEIBT, WIE SIE IST
-------------------------------------------------
Naheliegend waere, den Buchabgleich vor den Reconcile zu ziehen, damit gar kein Halt
entsteht. **Das waere ein Rueckschritt.** Der Reconcile ist die Erkennung eines Desyncs;
laeuft der Abgleich zuerst, stimmt das Buch danach immer mit dem Broker ueberein und die
Erkennung koennte per Konstruktion nie ausloesen. Die jetzige Ordnung ist fail-closed und
richtig: erst sperren, dann **genau den einen** erkannten gutartigen Fall aufloesen.

Geaendert wurde deshalb nicht die Ordnung, sondern die **Aufzeichnung**: der
``halt_erklaert``-Satz traegt jetzt ``weiter_gesperrt`` -- den Zustand, der die
Eintritte wirklich regiert.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mt5_trading_ai.betrieb.dienstguete import (
    NICHT_REPRODUZIERBAR,
    OHNE_STEMPEL,
    buchtreue,
    nach_codestand,
)

ROOT = Path(__file__).resolve().parents[1]
JOURNALE = ROOT / "betrieb"


def _z(**felder: object) -> str:
    return json.dumps(felder)


def _takt(halt: bool = False) -> str:
    return _z(
        art="takt",
        halt=halt,
        halt_grund="reconcile_drift:notional_drift_exceeds_limit" if halt else None,
    )


def _erklaert(weiter: bool | None) -> str:
    satz: dict[str, object] = {"art": "halt_erklaert", "durch": "broker_schliessung"}
    if weiter is not None:
        satz["weiter_gesperrt"] = weiter
    return json.dumps(satz)


def _werte(*zeilen: str):
    return buchtreue([json.loads(z) for z in zeilen])


# =====================================================================
# Die Leiter je Takt — jede Sprosse einzeln
# =====================================================================


def test_gruen_ein_takt_ohne_halt_ist_sauber() -> None:
    wert = _werte(_takt(), _takt(), _takt())
    assert (wert.gelungen, wert.gesamt, wert.unbeurteilbar) == (3, 3, 0)
    assert wert.anteil == pytest.approx(1.0)


def test_rot_ein_halt_ohne_aufloesung_zaehlt_als_gesperrt() -> None:
    """Die 16 echten Faelle: der Halt stand den Takt durch."""
    wert = _werte(_takt(), _takt(halt=True), _takt())
    assert (wert.gelungen, wert.gesamt) == (2, 3)


def test_ein_im_selben_takt_aufgeloester_halt_sperrt_nicht() -> None:
    """Die 4 Faelle aus dem langen Lauf -- der Kern dieser Korrektur."""
    wert = _werte(_takt(), _takt(halt=True), _erklaert(weiter=False), _takt())
    assert (wert.gelungen, wert.gesamt, wert.unbeurteilbar) == (3, 3, 0)


def test_rot_aufgeloest_aber_weiter_gesperrt_zaehlt_trotzdem_als_gesperrt() -> None:
    """Der Fall, der die Korrektur ehrlich haelt.

    Der Scheduler wird nach dem ``clear_halt()`` erneut befragt. Latcht er sofort wieder
    -- aus einem anderen Grund --, war der Takt sehr wohl gesperrt. Ohne diesen Zweig
    hiesse „es gab eine Aufloesung" pauschal „es war frei", und die Korrektur waere
    genau die Beschoenigung, gegen die sie gebaut ist.
    """
    wert = _werte(_takt(halt=True), _erklaert(weiter=True), _takt())
    assert (wert.gelungen, wert.gesamt) == (1, 2)


def test_eine_aufloesung_ohne_das_feld_ist_unbeurteilbar() -> None:
    """V3: Aufzeichnungen von vor ``weiter_gesperrt`` sagen es nicht -- also nicht raten.

    Sie als sauber zu zaehlen waere der schmeichelnde Standardwert, als gesperrt der
    andere. Sie stehen nicht im Nenner und werden angezeigt.
    """
    wert = _werte(_takt(), _takt(halt=True), _erklaert(weiter=None), _takt())
    assert (wert.gelungen, wert.gesamt, wert.unbeurteilbar) == (2, 2, 1)
    assert wert.anteil == pytest.approx(1.0)


def test_die_aufloesung_wird_dem_richtigen_takt_zugeordnet() -> None:
    """Sie zaehlt nur bis zum NAECHSTEN Takt -- sonst deckte eine Aufloesung alles ab.

    Roter Kern: der erste Halt-Takt bleibt gesperrt, obwohl im zweiten eine Aufloesung
    steht. Ohne die Fenstergrenze waeren beide sauber.
    """
    wert = _werte(
        _takt(halt=True),  # gesperrt: keine Aufloesung hier
        _takt(halt=True),
        _erklaert(weiter=False),  # sauber
    )
    assert (wert.gelungen, wert.gesamt) == (1, 2)


def test_die_korrektur_rettet_das_ziel_NICHT() -> None:
    """Auf den echten Journalen: 98,8 % gegen eine Schwelle von 99,0 %.

    Der Fall steht hier, weil er die Redlichkeit der Aenderung traegt. Haette die
    Korrektur die Zahl ueber die Schwelle gehoben, waere sie eine
    Schwellenverschiebung durch die Hintertuer gewesen -- egal wie gut begruendet.
    """
    zeilen: list[str] = []
    for datei in sorted(JOURNALE.glob("*.jsonl")):
        zeilen.extend(datei.read_text(encoding="utf-8").splitlines())
    if not zeilen:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    wert = buchtreue([json.loads(z) for z in zeilen if z.strip()])
    assert wert.anteil is not None
    assert wert.anteil < 0.99, (
        f"Die Buchtreue liegt bei {wert.anteil:.4%} und damit ueber der Schwelle -- "
        "dann waere die Korrektur eine Beschoenigung und gehoert zurueckgenommen."
    )
    assert wert.anteil > 0.985  # aber besser als die falsche Zaehlung (98,53 %)


# =====================================================================
# Der Schreiber — das Feld entsteht wirklich
# =====================================================================


def test_das_werkzeug_schreibt_weiter_gesperrt_wirklich() -> None:
    """V1: ein Feld, das die Metrik liest und niemand schreibt, ist Zierrat.

    Geprueft wird der Quelltext: ``weiter_gesperrt`` steht im ``halt_erklaert``-Satz,
    und der Scheduler wird VORHER erneut befragt -- sonst truege das Feld den alten
    Zustand und saegte genau die Aussage ab, fuer die es da ist.

    **Die Reihenfolge ist das Eigentliche hier.** Dass der Satz ueberhaupt geschrieben
    wird und der Pfad laeuft, deckt schon
    ``test_live_betrieb_sperren.py::test_ein_reconcile_halt_...`` ab -- der faehrt
    ``takt()`` wirklich. Was dort nicht steht, ist die Frage, ob das Feld den Zustand
    NACH der Aufloesung traegt; genau die steht hier.
    """
    quelle = (ROOT / "tools" / "live_betrieb.py").read_text(encoding="utf-8")
    schreiben = quelle.index('journal.schreib("halt_erklaert"')
    assert "weiter_gesperrt=tick.halted" in quelle[schreiben : schreiben + 400]
    neu_befragt = quelle.index(
        "tick = scheduler.tick(jetzt)", quelle.index("clear_halt")
    )
    assert neu_befragt < schreiben


# =====================================================================
# Aufschluesselung nach Codestand
# =====================================================================


def test_nach_codestand_trennt_die_staende() -> None:
    zeilen = [
        _z(art="takt", halt=False, version="alt"),
        _z(art="takt", halt=True, version="alt"),
        _z(art="takt", halt=False, version="neu"),
        _z(art="takt", halt=False, version="neu"),
    ]
    staende = nach_codestand(zeilen)
    assert set(staende) == {"alt", "neu"}
    assert staende["alt"]["buchtreue"].anteil == pytest.approx(0.5)
    assert staende["neu"]["buchtreue"].anteil == pytest.approx(1.0)


def test_saetze_ohne_version_bekommen_eine_eigene_gruppe() -> None:
    """Sie verschwinden nicht und werden nicht einem Stand zugeschlagen."""
    staende = nach_codestand([_z(art="takt", halt=False)])
    assert set(staende) == {OHNE_STEMPEL}


def test_unsaubere_arbeitsverzeichnisse_sind_am_namen_erkennbar() -> None:
    """``+aenderungen`` heisst: zu welchem Quelltext die Zahlen gehoeren, weiss niemand.

    Der Marker steht im Modul, damit die Anzeige ihn nicht per Textsuche erraten muss.
    """
    staende = nach_codestand([_z(art="takt", halt=False, version="abc123+aenderungen")])
    stand = next(iter(staende))
    assert NICHT_REPRODUZIERBAR in stand


def test_auf_den_echten_journalen_sitzen_die_sperren_im_ueberholten_code() -> None:
    """Der Befund dieser Arbeit, als Dauertor.

    Alle gesperrten Takte stammen aus Staenden, die es nicht mehr gibt. Der einzige
    sauber gestempelte Stand hat keinen einzigen. Faellt dieser Fall, ist entweder ein
    neuer Betriebslauf dazugekommen (dann gehoert er neu bewertet) oder die Sperre ist
    zurueck.
    """
    zeilen: list[str] = []
    for datei in sorted(JOURNALE.glob("*.jsonl")):
        zeilen.extend(datei.read_text(encoding="utf-8").splitlines())
    if not zeilen:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    staende = nach_codestand(zeilen)
    sauber_gestempelt = {
        stand: gruppe
        for stand, gruppe in staende.items()
        if stand != OHNE_STEMPEL and NICHT_REPRODUZIERBAR not in stand
    }
    assert sauber_gestempelt, "kein einziger sauber gestempelter Lauf"
    for stand, gruppe in sauber_gestempelt.items():
        wert = gruppe["buchtreue"]
        assert wert.anteil == pytest.approx(1.0), (
            f"Codestand {stand}: Buchtreue {wert.anteil} -- eine Sperre ist zurueck."
        )

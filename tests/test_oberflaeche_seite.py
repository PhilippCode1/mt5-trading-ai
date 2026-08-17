"""Die Oberflaeche baut ihre Seite auch dann, wenn nichts da ist.

WARUM DIESE TESTS
-----------------
Bis hierher war **keine Zeile** der Oberflaeche geprueft. Eine Seite, die nur mit
laufendem Terminal und gefuelltem Journal getestet wird, faellt genau dann aus, wenn
man sie am dringendsten braucht: wenn etwas kaputt ist.

Geprueft wird darum vor allem der entartete Fall -- kein Terminal, kein Journal, ein
defektes Journal, ein leerer Lauf. Und die eine Eigenschaft, die eine Anzeige
ueberhaupt brauchbar macht: **jeder Defekt muss auf der Seite stehen.** Ein gefangener
und dann verschwiegener Fehler ist schlimmer als ein Absturz -- man sieht der Seite
nicht an, dass sie luegt. Genau das war hier der Fall: ``journalfehler`` wurde gesetzt
und nirgends gerendert.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]


def _modul() -> Any:
    """``tools/oberflaeche.py`` als Modul laden -- es ist ein Skript, kein Paket."""
    spec = importlib.util.spec_from_file_location(
        "oberflaeche", REPO / "tools" / "oberflaeche.py"
    )
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


OB = _modul()


def _leer(**zusatz: Any) -> dict[str, Any]:
    stand: dict[str, Any] = {
        "jetzt": datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
        "fehler": None, "lauf": None, "alle_laeufe": [],
    }
    stand.update(zusatz)
    return stand


# --- Der entartete Fall ---------------------------------------------------
def test_seite_baut_ohne_terminal_und_ohne_journal() -> None:
    """``seite`` liefert nur noch das FRAGMENT -- die Huelle kommt separat."""
    fragment = OB.seite(_leer())
    assert "<html" not in fragment, "Das Fragment darf kein Seitengeruest tragen"
    assert len(fragment) > 1000


def test_die_huelle_traegt_das_geruest_und_das_skript() -> None:
    ganz = OB.huelle(OB.seite(_leer()))
    assert "<html" in ganz and "</html>" in ganz
    assert 'id="inhalt"' in ganz, "Ohne dieses Ziel kann das Skript nichts tauschen"
    assert "fetch('/inhalt'" in ganz


def test_ohne_javascript_steht_ein_hinweis_da() -> None:
    """Die Seite bleibt ohne Skript lesbar -- sie sagt nur, dass sie stehen bleibt."""
    ganz = OB.huelle("x")
    assert "<noscript>" in ganz
    assert "aktualisiert sich diese" in ganz


def test_es_gibt_kein_meta_refresh_mehr() -> None:
    """Das Ganzseiten-Neuladen war der Grund fuer die Trennung.

    Es liess die Scrollposition springen und die Diagramme flackern -- alle zehn
    Sekunden. Kehrt es zurueck, ist der Gewinn wieder weg.
    """
    assert "http-equiv" not in OB.huelle("x")


def test_das_alter_des_schnappschusses_steht_auf_der_seite() -> None:
    """Eine Anzeige, die stillschweigend einfriert, ist gefaehrlicher als eine leere."""
    from datetime import timedelta
    stand = _leer()
    stand["gebaut"] = stand["jetzt"] - timedelta(seconds=45)
    stand["dauer_ms"] = 12.0
    fragment = OB.seite(stand, jetzt=stand["jetzt"])
    assert "45 s alt" in fragment
    assert "krit" in fragment, "Ein alter Stand muss auffallen, nicht nur dastehen"


def test_ein_terminalfehler_steht_auf_der_seite() -> None:
    seite = OB.seite(_leer(fehler="MT5-Terminal nicht erreichbar."))
    assert "nicht erreichbar" in seite


def test_ein_journalfehler_steht_auf_der_seite() -> None:
    """Der Befund, der diese Datei ausgeloest hat.

    ``journalfehler`` wurde gefangen, abgelegt und nie gezeigt. Die Seite meldete
    dann "Kein Journal gefunden" -- wo "defektes Journal" richtig gewesen waere.
    """
    seite = OB.seite(_leer(journalfehler="journal-x.jsonl:7 ist kein JSON"))
    assert "journal-x.jsonl:7" in seite, (
        "Ein gefangener Journalfehler muss auf der Seite erscheinen, sonst "
        "verwandelt die Oberflaeche einen Defekt in eine harmlose Leermeldung."
    )


def test_beide_fehler_gleichzeitig_erscheinen_beide() -> None:
    seite = OB.seite(_leer(fehler="Terminal weg", journalfehler="Zeile 3 kaputt"))
    assert "Terminal weg" in seite
    assert "Zeile 3 kaputt" in seite


def test_die_seite_sagt_immer_dass_keine_strategie_zugelassen_ist() -> None:
    """Der Zustand des Vorhabens gehoert auf jede Ansicht, nicht in eine Fussnote."""
    assert "Keine zugelassene Strategie" in OB.seite(_leer())


def test_die_seite_sagt_dass_sie_nicht_handeln_kann() -> None:
    assert "nur lesend" in OB.seite(_leer())


# --- Diagramme ------------------------------------------------------------
def test_linienzug_mit_zu_wenigen_punkten_zeichnet_nichts_und_sagt_es() -> None:
    aus = OB._linienzug([], titel="Equity")
    assert "<svg" not in aus
    assert "Zu wenige" in aus


def test_linienzug_zeichnet_ab_zwei_punkten() -> None:
    punkte = [
        (datetime(2026, 8, 17, 12, 0, tzinfo=UTC), Decimal("100")),
        (datetime(2026, 8, 17, 13, 0, tzinfo=UTC), Decimal("110")),
    ]
    aus = OB._linienzug(punkte, titel="Equity")
    assert "<svg" in aus and "polyline" in aus


def test_eine_flache_reihe_stuerzt_nicht_ab() -> None:
    """Alle Werte gleich -> die Spanne ist null. Eine Division dadurch waere fatal."""
    punkte = [
        (datetime(2026, 8, 17, 12, 0, tzinfo=UTC), Decimal("50000")),
        (datetime(2026, 8, 17, 13, 0, tzinfo=UTC), Decimal("50000")),
        (datetime(2026, 8, 17, 14, 0, tzinfo=UTC), Decimal("50000")),
    ]
    aus = OB._linienzug(punkte, titel="flach")
    assert "<svg" in aus


def test_eine_fallende_reihe_wird_anders_gefaerbt_als_eine_steigende() -> None:
    hoch = [(datetime(2026, 8, 17, 12, 0, tzinfo=UTC), Decimal("1")),
            (datetime(2026, 8, 17, 13, 0, tzinfo=UTC), Decimal("2"))]
    runter = [(datetime(2026, 8, 17, 12, 0, tzinfo=UTC), Decimal("2")),
              (datetime(2026, 8, 17, 13, 0, tzinfo=UTC), Decimal("1"))]
    assert "var(--gut)" in OB._linienzug(hoch, titel="x")
    assert "var(--krit)" in OB._linienzug(runter, titel="x")


# --- Kleinigkeiten, die schnell brechen -----------------------------------
@pytest.mark.parametrize("wert", [None, "", 0, Decimal("1.5")])
def test_zahlformatierung_vertraegt_alles(wert: Any) -> None:
    assert isinstance(OB._zahl(wert), str)


def test_html_wird_maskiert() -> None:
    """Ein Broker-Kommentar mit spitzen Klammern darf die Seite nicht zerlegen."""
    assert "<script>" not in OB._e("<script>alert(1)</script>")

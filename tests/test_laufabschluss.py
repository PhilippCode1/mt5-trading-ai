"""Laufabschluss: warum diese Kennzahl nicht „behoben" wird — und was stattdessen zählt.

WORAUS DAS ENTSTANDEN IST
-------------------------
``laufabschluss`` steht bei 90,5 % (19 von 21 Laeufen mit ``ende``-Satz), Ziel 95 %.
Die Untersuchung der zwei Laeufe ohne ``ende`` hat drei Dinge ergeben, und jedes
einzelne davon verbietet es, die Zahl hochzuarbeiten:

1. **Sie verlangt vom Prozess, seinen eigenen Tod zu ueberleben.** Gemessen mit einem
   Opferskript: bei ``taskkill /F`` laeuft weder Signalhandler noch ``atexit`` noch
   ``finally``. Die Ursache des laengsten Abbruchs steht im Windows-Ereignisprotokoll --
   elf Sekunden nach dem letzten Journalsatz Abmeldung und Standby (Kernel-Power 42,
   „Ursache: Application API"). Die Software hat daran keinen Anteil.
2. **Sie ist auf diesen Daten invertiert zur Gefahr.** Die zwei Laeufe ohne ``ende`` und
   die zwei Laeufe, die wirklich Geld am Markt liessen, sind disjunkte Mengen.
3. **Sie ist trivial schoenbar.** Neunzehn Trockenlaeufe von je zwanzig Sekunden heben
   sie ueber 95 % und loeschen den Alarm, ohne dass sich am Betrieb etwas bessert.

Diese Datei haelt alle drei als Dauertor fest. Sie prueft **nicht**, dass die Kennzahl
gut ist -- sie prueft, dass sie so bleibt, wie sie ist, und dass ihre Grenzen belegt
sind. Ein spaeterer Leser, der sie „reparieren" will, faellt hier auf.

Der Befund, um den es wirklich geht, steht in ``tests/test_ausstiegsdeckung.py``:
``journal-20260817T150513`` starb nach fuenf Minuten mit **drei offenen Positionen** --
und die Metrik, deren Alarmregel „Position offen geblieben" heisst, konnte ihn in ihrer
ersten Fassung nicht sehen.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from mt5_trading_ai.betrieb.dienstguete import (
    ALARMREGELN,
    ZIELE,
    ausstiegsdeckung,
    laufabschluss,
)

ROOT = Path(__file__).resolve().parents[1]
JOURNALE = ROOT / "betrieb"


def _echte_saetze() -> list[dict[str, object]]:
    saetze: list[dict[str, object]] = []
    for datei in sorted(JOURNALE.glob("*.jsonl")):
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            if zeile.strip():
                saetze.append(json.loads(zeile))
    return saetze


def _je_journal() -> dict[str, list[dict[str, object]]]:
    return {
        datei.name: [
            json.loads(z)
            for z in datei.read_text(encoding="utf-8").splitlines()
            if z.strip()
        ]
        for datei in sorted(JOURNALE.glob("*.jsonl"))
    }


# =====================================================================
# Die Schwelle bleibt, und die Zahl bleibt gerissen
# =====================================================================


def test_die_schwelle_ist_und_bleibt_95_prozent() -> None:
    """V6. Sie steht seit Stufe 10 fest und wird von dieser Arbeit nicht bewegt."""
    ziel = next(z for z in ZIELE if z.metrik == "laufabschluss")
    regel = next(r for r in ALARMREGELN if r.metrik == "laufabschluss")
    assert ziel.ziel == 0.95
    assert regel.schwelle == 0.95


def test_die_zahl_bleibt_gerissen() -> None:
    """Kein Handgriff dieser Arbeit hat sie gehoben -- und das ist die Aussage."""
    saetze = _echte_saetze()
    if not saetze:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    wert = laufabschluss(saetze)
    assert wert.anteil is not None
    assert wert.anteil < 0.95, (
        f"laufabschluss steht bei {wert.anteil:.4%}. Wenn das durch echten Betrieb "
        "kam, gehoert dieser Fall neu bewertet -- kam es durch eine Aenderung an der "
        "Zaehlung, ist es eine Schwellenverschiebung durch die Hintertuer."
    )


# =====================================================================
# Befund 1: die Kennzahl ist trivial schoenbar
# =====================================================================


def test_ROT_neunzehn_trockenlaeufe_heben_laufabschluss_ueber_die_schwelle() -> None:
    """Der Beschoenigungsweg, ausgerechnet und festgenagelt.

    ``laufabschluss`` gewichtet jeden Lauf gleich -- ob er null Sekunden oder 18,7
    Stunden dauerte. 20 der 21 Laeufe dieses Standes sind kuerzer als 90 Minuten.
    Aus ``(19+x)/(21+x) >= 0,95`` folgt ``x = 19``: neunzehn Leerlaeufe von je zwanzig
    Sekunden, zusammen rund sieben Minuten Arbeit, loeschen den Alarm.

    Dieser Fall steht hier, damit der Weg **benannt** ist. Faellt er, ist entweder die
    Kennzahl gegen Gewichtung abgesichert worden (dann gehoert er umgeschrieben) oder
    jemand hat die Rechnung veraendert.
    """
    saetze = _echte_saetze()
    if not saetze:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    ist = laufabschluss(saetze)
    trocken = [
        s
        for _ in range(19)
        for s in ({"art": "start"}, {"art": "ende", "offen_geblieben": []})
    ]
    geschoent = laufabschluss([*saetze, *trocken])
    assert ist.anteil is not None and ist.anteil < 0.95
    assert geschoent.anteil is not None
    assert geschoent.anteil >= 0.95, (
        "Die Rechnung hat sich geaendert -- der dokumentierte Beschoenigungsweg "
        "stimmt nicht mehr, der Fall gehoert neu gerechnet."
    )


def test_GRUEN_dieselben_trockenlaeufe_heben_die_ausstiegsdeckung_NICHT() -> None:
    """Der Gegenbeweis, und der Grund fuer den Nenner von ``ausstiegsdeckung``.

    Dieselben neunzehn Leerlaeufe, dieselbe Absicht -- und die Kennzahl, die auf das
    Geld sieht, bewegt sich um keinen Punkt. Sie zaehlt nur Laeufe, die nachweislich
    eine Position hielten; ein Leerlauf kann nichts zuruecklassen.
    """
    saetze = _echte_saetze()
    if not saetze:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    vorher = ausstiegsdeckung(saetze)
    trocken = [
        s
        for _ in range(19)
        for s in (
            {"art": "start"},
            {"art": "takt", "nr": 1, "positionen": []},
            {"art": "ende", "offen_geblieben": []},
        )
    ]
    nachher = ausstiegsdeckung([*saetze, *trocken])
    assert (vorher.gelungen, vorher.gesamt) == (nachher.gelungen, nachher.gesamt), (
        "Leerlaeufe sind in den Nenner der Ausstiegsdeckung gerutscht."
    )


# =====================================================================
# Befund 2: die Kennzahl ist invertiert zur Gefahr
# =====================================================================


def test_die_gefaehrlichen_laeufe_zaehlen_bei_laufabschluss_als_GELUNGEN() -> None:
    """Der unangenehmste Einzelbefund, an den echten Journalen festgehalten.

    ``173413`` und ``182800`` liessen drei bzw. zwei Positionen offen -- und haben einen
    ``ende``-Satz. ``laufabschluss`` zaehlt sie als gelungen.
    """
    journale = _je_journal()
    if not journale:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    for name in ("journal-20260817T173413.jsonl", "journal-20260817T182800.jsonl"):
        saetze = journale.get(name)
        if saetze is None:
            pytest.skip(f"{name} fehlt im Arbeitsbaum")
        ende = next(s for s in saetze if s.get("art") == "ende")
        assert ende["offen_geblieben"], f"{name} sollte Positionen offen gelassen haben"
        assert laufabschluss(saetze).anteil == 1.0, (
            f"{name} zaehlt bei laufabschluss nicht mehr als gelungen -- der "
            "dokumentierte Widerspruch stimmt nicht mehr."
        )
        assert ausstiegsdeckung(saetze).anteil == 0.0, (
            f"{name} muss bei ausstiegsdeckung als Fehlschlag zaehlen."
        )


def test_der_harmlose_abbruch_zaehlt_bei_laufabschluss_als_GESCHEITERT() -> None:
    """Die andere Haelfte der Inversion.

    ``182951`` lief 18,7 Stunden, eroeffnete 13-mal, schloss 13-mal und hinterliess ein
    leeres Buch -- und zaehlt bei ``laufabschluss`` als Fehlschlag, weil der Prozess
    getoetet wurde, bevor er den Endsatz schreiben konnte.
    """
    saetze = _je_journal().get("journal-20260817T182951.jsonl")
    if saetze is None:
        pytest.skip("journal-20260817T182951.jsonl fehlt im Arbeitsbaum")
    assert not any(s.get("art") == "ende" for s in saetze)
    assert laufabschluss(saetze).anteil == 0.0
    letzter = next(
        s for s in reversed(saetze) if s.get("art") == "takt" and "positionen" in s
    )
    assert letzter["positionen"] == []
    assert ausstiegsdeckung(saetze).anteil == 1.0, (
        "Der Lauf hinterliess ein leeres Buch und muss bei ausstiegsdeckung als "
        "gelungen zaehlen."
    )


# =====================================================================
# Befund 3: kein Abbruch hatte eine Stoppdatei -- der RUNBOOK-Satz war falsch
# =====================================================================


def test_jeder_stoppdatei_lauf_hat_einen_endsatz() -> None:
    """Widerlegt die frueher im RUNBOOK eingestandene „bekannte Ungenauigkeit".

    Dort stand, ein Stoppdatei-Lauf zaehle „hier faelschlich mit". Gemessen: der
    Stoppdatei-Pfad bricht die Schleife mit ``break`` ab, danach laeuft der
    ``finally``-Block und schreibt ``ende``. Alle Stoppdatei-Laeufe haben einen.
    """
    journale = _je_journal()
    if not journale:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    mit_stoppdatei = [
        name
        for name, saetze in journale.items()
        if any(s.get("art") == "stoppdatei" for s in saetze)
    ]
    assert mit_stoppdatei, "kein einziger Stoppdatei-Lauf -- der Fall misst nichts"
    for name in mit_stoppdatei:
        assert any(s.get("art") == "ende" for s in journale[name]), (
            f"{name} hat eine Stoppdatei, aber keinen ende-Satz."
        )


def test_kein_lauf_ohne_endsatz_hatte_eine_stoppdatei() -> None:
    """Die Gegenrichtung: die Abbrueche sind echte Abbrueche, keine gewollten Stopps."""
    journale = _je_journal()
    if not journale:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    ohne_ende = [
        name
        for name, saetze in journale.items()
        if any(s.get("art") == "start" for s in saetze)
        and not any(s.get("art") == "ende" for s in saetze)
    ]
    assert ohne_ende, "kein Lauf ohne Endsatz -- der Fall misst nichts"
    for name in ohne_ende:
        assert not any(s.get("art") == "stoppdatei" for s in journale[name]), (
            f"{name} hat eine Stoppdatei UND keinen ende-Satz -- das waere ein neuer, "
            "schwererer Befund: der geordnete Weg hat versagt."
        )


def test_das_runbook_behauptet_die_widerlegte_ungenauigkeit_nicht_mehr() -> None:
    """Eine Handlungsanweisung, die auf eine unmoegliche Lage zeigt, ist schlimmer als
    keine -- sie verbraucht die Aufmerksamkeit, die der echte Fall braucht."""
    text = (ROOT / "RUNBOOK.md").read_text(encoding="utf-8")
    assert "bekannte Ungenauigkeit der Metrik" not in text
    abschnitt = text[text.index("## Läufe brechen ab") :]
    abschnitt = abschnitt[: abschnitt.index("\n---")]
    # Zeilenumbrueche zusammenziehen: geprueft wird der Inhalt, nicht der Umbruch. Sonst
    # faellt der Fall, sobald jemand den Absatz neu umbricht -- ein Tor, das auf
    # Textsatz reagiert, meldet Rauschen und wird abgeschaltet.
    fliesstext = " ".join(abschnitt.split())
    assert "Position offen geblieben" in fliesstext, (
        "Der Abschnitt muss auf die Kennzahl verweisen, die auf das Geld sieht."
    )


# =====================================================================
# Der Abbruchzeitpunkt ist aus dem Journal ablesbar -- gegen jede spaetere Vermutung
# =====================================================================


def test_beide_abbrueche_lagen_weit_vor_der_geplanten_dauer() -> None:
    """Beleg, dass es Abbrueche waren und keine regulaeren Laufenden.

    Der ``start``-Satz traegt ``dauer_stunden``; der letzte Satz traegt einen
    Zeitstempel. Beides zusammen zeigt: kein Lauf hat seine geplante Zeit erreicht.
    """
    journale = _je_journal()
    if not journale:
        pytest.skip("keine Betriebsjournale im Arbeitsbaum")
    gefunden = 0
    for name, saetze in journale.items():
        start = next((s for s in saetze if s.get("art") == "start"), None)
        if start is None or any(s.get("art") == "ende" for s in saetze):
            continue
        gefunden += 1
        t0 = datetime.fromisoformat(str(start["ts"]))
        letzte = datetime.fromisoformat(str(saetze[-1]["ts"]))
        gelaufen = (letzte - t0).total_seconds() / 3600
        geplant = float(start["dauer_stunden"])  # type: ignore[arg-type]
        assert gelaufen < geplant, (
            f"{name}: {gelaufen:.2f} h gelaufen von {geplant} h geplant -- haette der "
            "Lauf seine Zeit erreicht, waere das kein Abbruch, sondern ein fehlender "
            "Endsatz am regulaeren Ende, also ein anderer Befund."
        )
    assert gefunden == 2, f"erwartet 2 Laeufe ohne Endsatz, gefunden {gefunden}"

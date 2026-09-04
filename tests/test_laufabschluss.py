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

WORAN GEMESSEN WIRD (Auftrag 1, T6, Befund T)
---------------------------------------------
An der eingecheckten Aufzeichnung ``aufzeichnungen/demo-2026-08-17.jsonl``, nicht mehr
an ``betrieb/``: das Verzeichnis ist gitignoriert, und die Tests dieser Datei
uebersprangen sich deshalb auf jedem Klon (8 von 12 Skips der Suite). Die Aufzeichnung
traegt seit Kopf-Fassung 2 die ``takt``-Saetze und an jedem Satz die Laufkennung
``LAUF-nn`` (laufende Nummer des Journals in Zeitreihenfolge); die drei Laeufe, um die
es hier geht, sind darueber ansprechbar. Gemessen (Beleg
``06-aufzeichnung-metriken-vergleich.txt``): alle Zahlen dieser Datei sind an der
Aufzeichnung dieselben wie an den 21 Journalen. Fehlt die Aufzeichnung, **scheitern**
diese Tests (Katalog A2) -- sie ueberspringen sich nicht.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from mt5_trading_ai.betrieb.dienstguete import (
    ALARMREGELN,
    ZIELE,
    ausstiegsdeckung,
    laufabschluss,
)

ROOT = Path(__file__).resolve().parents[1]
AUFZEICHNUNG = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"

#: Die drei Laeufe der Befunde, als stabile Kennung der Aufzeichnung. Der Kopf der
#: Aufzeichnung bildet die Kennung auf den Journalnamen ab;
#: ``test_die_kennungen_zeigen_auf_die_benannten_journale`` haelt das fest.
LAUF_173413 = "LAUF-18"  # drei Positionen offen gelassen, mit ende-Satz
LAUF_182800 = "LAUF-20"  # zwei Positionen offen gelassen, mit ende-Satz
LAUF_182951 = "LAUF-21"  # 18,7 h, leeres Buch, ohne ende-Satz (getoetet)
JOURNAL_JE_LAUF = {
    LAUF_173413: "journal-20260817T173413.jsonl",
    LAUF_182800: "journal-20260817T182800.jsonl",
    LAUF_182951: "journal-20260817T182951.jsonl",
}


def _zeilen() -> list[dict[str, object]]:
    assert AUFZEICHNUNG.is_file(), (
        f"{AUFZEICHNUNG.relative_to(ROOT).as_posix()} fehlt -- die Dauertore dieser "
        "Datei haben keinen Gegenstand (Katalog A2: kein Test ueberspringt sich). "
        "Erzeugen mit: python tools/aufzeichnung_redigieren.py"
    )
    zeilen = [
        json.loads(z)
        for z in AUFZEICHNUNG.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    assert zeilen and zeilen[0].get("art") == "_kopf", "Aufzeichnung ohne Kopfzeile"
    return zeilen


def _kopf() -> dict[str, object]:
    return _zeilen()[0]


def _echte_saetze() -> list[dict[str, object]]:
    """Alle Saetze der Aufzeichnung -- ohne die Kopfzeile, die kein Ereignis ist."""
    saetze = _zeilen()[1:]
    assert saetze, "Aufzeichnung ohne Saetze"
    return saetze


def _je_lauf() -> dict[str, list[dict[str, object]]]:
    """Die Saetze je Lauf, ueber die Laufkennung ``lauf`` an jedem Satz."""
    aus: dict[str, list[dict[str, object]]] = {}
    for satz in _echte_saetze():
        kennung = satz.get("lauf")
        assert isinstance(kennung, str) and kennung.startswith("LAUF-"), (
            f"Satz ohne stabile Laufkennung: {satz.get('art')} um {satz.get('ts')}"
        )
        aus.setdefault(kennung, []).append(satz)
    assert len(aus) == 21, f"erwartet 21 Laeufe, gefunden {len(aus)}"
    return aus


def test_die_kennungen_zeigen_auf_die_benannten_journale() -> None:
    """Die stabile Kennung ist nur dann ein Name, wenn der Kopf sie auf das Journal
    abbildet, ueber das die Befunde unten reden."""
    laeufe = _kopf()["laeufe"]
    assert isinstance(laeufe, dict)
    for kennung, journal in JOURNAL_JE_LAUF.items():
        assert laeufe.get(kennung) == journal, (
            f"{kennung} zeigt im Kopf auf {laeufe.get(kennung)!r}, erwartet {journal}"
        )


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
    """Kein Handgriff dieser Arbeit hat sie gehoben -- und das ist die Aussage.

    Gemessen an den 21 Journalen wie an der Aufzeichnung: 19 von 21.
    """
    wert = laufabschluss(_echte_saetze())
    assert (wert.gelungen, wert.gesamt) == (19, 21)
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
    assert (vorher.gelungen, vorher.gesamt) == (8, 11)  # gemessen, 10 unbeurteilbar
    assert (vorher.gelungen, vorher.gesamt) == (nachher.gelungen, nachher.gesamt), (
        "Leerlaeufe sind in den Nenner der Ausstiegsdeckung gerutscht."
    )


# =====================================================================
# Befund 2: die Kennzahl ist invertiert zur Gefahr
# =====================================================================


def test_die_gefaehrlichen_laeufe_zaehlen_bei_laufabschluss_als_GELUNGEN() -> None:
    """Der unangenehmste Einzelbefund, an den echten Laeufen festgehalten.

    ``173413`` (LAUF-18) und ``182800`` (LAUF-20) liessen drei bzw. zwei Positionen
    offen -- und haben einen ``ende``-Satz. ``laufabschluss`` zaehlt sie als gelungen.
    """
    je_lauf = _je_lauf()
    for kennung, offen in ((LAUF_173413, 3), (LAUF_182800, 2)):
        assert kennung in je_lauf, f"{kennung} fehlt in der Aufzeichnung"
        saetze = je_lauf[kennung]
        ende = next(s for s in saetze if s.get("art") == "ende")
        assert ende["offen_geblieben"], (
            f"{kennung} sollte Positionen offen gelassen haben"
        )
        assert len(ende["offen_geblieben"]) == offen  # type: ignore[arg-type]
        assert laufabschluss(saetze).anteil == 1.0, (
            f"{kennung} zaehlt bei laufabschluss nicht mehr als gelungen -- der "
            "dokumentierte Widerspruch stimmt nicht mehr."
        )
        assert ausstiegsdeckung(saetze).anteil == 0.0, (
            f"{kennung} muss bei ausstiegsdeckung als Fehlschlag zaehlen."
        )


def test_der_harmlose_abbruch_zaehlt_bei_laufabschluss_als_GESCHEITERT() -> None:
    """Die andere Haelfte der Inversion.

    ``182951`` (LAUF-21) lief 18,7 Stunden, eroeffnete 13-mal, schloss 13-mal und
    hinterliess ein leeres Buch -- und zaehlt bei ``laufabschluss`` als Fehlschlag,
    weil der Prozess getoetet wurde, bevor er den Endsatz schreiben konnte.
    """
    je_lauf = _je_lauf()
    assert LAUF_182951 in je_lauf, f"{LAUF_182951} fehlt in der Aufzeichnung"
    saetze = je_lauf[LAUF_182951]
    assert not any(s.get("art") == "ende" for s in saetze)
    assert sum(1 for s in saetze if s.get("art") == "eroeffnet") == 13
    assert (
        sum(
            1
            for s in saetze
            if s.get("art") in ("geschlossen", "vom_broker_geschlossen")
        )
        == 13
    )
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
    ``finally``-Block und schreibt ``ende``. Alle fuenf Stoppdatei-Laeufe haben einen.
    """
    je_lauf = _je_lauf()
    mit_stoppdatei = [
        kennung
        for kennung, saetze in je_lauf.items()
        if any(s.get("art") == "stoppdatei" for s in saetze)
    ]
    assert len(mit_stoppdatei) == 5, (
        f"erwartet 5 Stoppdatei-Laeufe, gefunden {len(mit_stoppdatei)}"
    )
    for kennung in mit_stoppdatei:
        assert any(s.get("art") == "ende" for s in je_lauf[kennung]), (
            f"{kennung} hat eine Stoppdatei, aber keinen ende-Satz."
        )


def test_kein_lauf_ohne_endsatz_hatte_eine_stoppdatei() -> None:
    """Die Gegenrichtung: die Abbrueche sind echte Abbrueche, keine gewollten Stopps."""
    je_lauf = _je_lauf()
    ohne_ende = [
        kennung
        for kennung, saetze in je_lauf.items()
        if any(s.get("art") == "start" for s in saetze)
        and not any(s.get("art") == "ende" for s in saetze)
    ]
    assert sorted(ohne_ende) == ["LAUF-12", LAUF_182951], (
        f"erwartet genau die zwei Abbrueche, gefunden {ohne_ende}"
    )
    for kennung in ohne_ende:
        assert not any(s.get("art") == "stoppdatei" for s in je_lauf[kennung]), (
            f"{kennung} hat eine Stoppdatei UND keinen ende-Satz -- das waere ein "
            "neuer, schwererer Befund: der geordnete Weg hat versagt."
        )


def test_die_handlung_behauptet_die_widerlegte_ungenauigkeit_nicht_mehr() -> None:
    """Eine Handlungsanweisung, die auf eine unmoegliche Lage zeigt, ist schlimmer als
    keine -- sie verbraucht die Aufmerksamkeit, die der echte Fall braucht (E-014:
    die Handlung steht in der Regel selbst)."""
    regel = next(r for r in ALARMREGELN if r.name == "laeufe_brechen_ab")
    text = regel.handlungsanweisung
    assert "bekannte Ungenauigkeit der Metrik" not in text
    assert "Kein Sicherheitsalarm" in text


def test_beide_abbrueche_lagen_weit_vor_der_geplanten_dauer() -> None:
    """Beleg, dass es Abbrueche waren und keine regulaeren Laufenden.

    Der ``start``-Satz traegt ``dauer_stunden``; der letzte Satz traegt einen
    Zeitstempel. Beides zusammen zeigt: kein Lauf hat seine geplante Zeit erreicht.
    Die Aufzeichnung laesst ``kurs`` und ``signal`` weg; ihr letzter Satz kann bis zu
    einem Takt vor dem letzten Journalsatz liegen -- gemessen sind beide Zeiten gleich
    (0,0836 h und 18,7139 h von 24 h geplant).
    """
    je_lauf = _je_lauf()
    gefunden = 0
    for kennung, saetze in je_lauf.items():
        start = next((s for s in saetze if s.get("art") == "start"), None)
        if start is None or any(s.get("art") == "ende" for s in saetze):
            continue
        gefunden += 1
        t0 = datetime.fromisoformat(str(start["ts"]))
        letzte = datetime.fromisoformat(str(saetze[-1]["ts"]))
        gelaufen = (letzte - t0).total_seconds() / 3600
        geplant = float(start["dauer_stunden"])  # type: ignore[arg-type]
        assert gelaufen < geplant, (
            f"{kennung}: {gelaufen:.2f} h gelaufen von {geplant} h geplant -- haette "
            "der Lauf seine Zeit erreicht, waere das kein Abbruch, sondern ein "
            "fehlender Endsatz am regulaeren Ende, also ein anderer Befund."
        )
    assert gefunden == 2, f"erwartet 2 Laeufe ohne Endsatz, gefunden {gefunden}"

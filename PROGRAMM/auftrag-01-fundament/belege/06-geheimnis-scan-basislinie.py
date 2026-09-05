"""Basislinie des Geheimnis-Scans einordnen (T6, Familie Geheimnis-Scan, Katalog A5).

Liest ``.secrets.baseline`` (geschrieben von ``tools/geheimnis_scan.py
--basislinie-schreiben``), ordnet jeden Eintrag nach Gattung und Pfad einer Klasse zu
und schreibt die Begruendung. Jede Regel steht hier lesbar. Vor der Zuordnung wurde
jede Fundzeile gelesen (Triage im Scratchpad; die Fundtexte selbst liegen nicht im
Repo). Ein Eintrag, den keine Regel trifft, bleibt ``ungeprueft`` -- dann sperrt die
Basislinie, und dieses Skript endet mit Exit 1.

Aufruf: ``python PROGRAMM/auftrag-01-fundament/belege/06-geheimnis-scan-basislinie.py``
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from tools.geheimnis_scan import BASISLINIE, Eintrag, basislinie_speichern  # noqa: E402

HEX = "detect-secrets: Hex High Entropy String"
KONTONUMMER = "Muster: Kontonummer (account/konto = 6-12 Ziffern)"
IP_PORT = "Muster: IP-Adresse mit Port"

KONTONUMMER_BEGRUENDUNG = (
    "Beispiel-Kontonummer der Tests (KONTO-Konstante, account_id/konto_id am "
    "Fake-Terminal); dieselbe Zahl fuehrt tests/test_risiko_zustand_geheimnis.py als "
    "Beispiel-Login; Waehrung in den Tests USD, Demokonto EUR; nicht das Demokonto "
    "(Abgleich mit der echten Kontonummer nur durch Philipp, siehe bericht.md)"
)


def einordnen(e: Eintrag) -> tuple[str, str] | None:
    pfad = e.pfad
    if e.gattung == HEX:
        if pfad.endswith(".manifest.json"):
            return "pruefsumme", (
                "SHA-256 der Datenreihe im Manifest (Feld checksum/bars_checksum, 64 "
                "Hex): Datenpruefsumme, kein Zugang"
            )
        if pfad.endswith(("trials-abzug.jsonl", "trials.jsonl")):
            return "pruefsumme", (
                "Versuchsregister-Abzug: code_commit (Git-SHA-1, 40 Hex) und "
                "data_checksum (SHA-256 der Daten, 64 Hex); Kennungen, kein Zugang"
            )
        if pfad.endswith("risikozustand.json"):
            return "testdatum", (
                "Nachstellungs-Beleg (pruefung.py, Fake-Terminal mit login=1): "
                "PBKDF2-Abdruck und Zufallssalz der Kontobindung fuer den "
                "Beispiel-Login 1, kein echtes Konto"
            )
        if pfad == "tests/test_ereignisstudie_werkzeug.py":
            return "testdatum", (
                "Erfundene Commit-Kennung im Test (monkeypatch von _code_commit, "
                "16 Hex mit Wortspiel), kein Zugang"
            )
        if pfad == "tests/test_stufe5_ausfuehrung.py":
            return "testdatum", (
                "Erfundene Laufkennung des Redaktionstests (LAUF_ROH, 32 Hex aus "
                "0123456789abcdef zweimal), kein Zugang"
            )
        if pfad.startswith("tests/"):
            return "pruefsumme", (
                "In Tests festgenagelte SHA-256 der Testreihe (PINNED_CHECKSUM bzw. "
                "Manifest-Pruefsumme aus tests/fixtures), Datenpruefsumme"
            )
        return None
    if e.gattung == KONTONUMMER:
        if pfad.startswith("PROGRAMM/eingang/"):
            return "testdatum", (
                "Zitat der Testzeilen im Messprotokoll der Bewertung (alter Scan-"
                "Lauf); " + KONTONUMMER_BEGRUENDUNG
            )
        if pfad.startswith(("tests/", "tools/")):
            return "testdatum", KONTONUMMER_BEGRUENDUNG
        if pfad.startswith("PROGRAMM/auftrag-01-fundament/belege/"):
            return "testdatum", (
                "Zitat einer Testzeile in einem Umbau- oder Belegskript des Programms; "
                + KONTONUMMER_BEGRUENDUNG
            )
        return None
    if e.gattung == IP_PORT:
        return "adresse-lokal", (
            "Loopback-Adresse (127.0.0.1) mit Port der in T5 geloeschten Oberflaeche "
            "tools/oberflaeche.py bzw. deren Protokoll in PROGRAMM/eingang; kein "
            "erreichbarer Dienst"
        )
    return None


def main() -> int:
    pfad = REPO / BASISLINIE
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    eintraege = [Eintrag(**e) for e in daten["eintraege"]]
    neu: list[Eintrag] = []
    offen: list[Eintrag] = []
    klassen: Counter[str] = Counter()
    regeln: Counter[tuple[str, str]] = Counter()
    for e in eintraege:
        zuordnung = einordnen(e)
        if zuordnung is None:
            offen.append(e)
            neu.append(e)
            continue
        klasse, begruendung = zuordnung
        klassen[klasse] += 1
        regeln[(e.gattung, begruendung[:60])] += 1
        neu.append(
            Eintrag(
                e.objekt,
                e.pfad,
                e.ort,
                e.zeile,
                e.gattung,
                e.abdruck,
                klasse,
                begruendung,
            )
        )
    basislinie_speichern(pfad, neu)
    print(
        f"Eintraege: {len(neu)}; eingeordnet: {len(neu) - len(offen)}; offen: {len(offen)}"
    )
    for klasse, n in sorted(klassen.items()):
        print(f"  Klasse {klasse:14s} {n:4d}")
    print("Regeln (Gattung | Begruendung, gekuerzt | Eintraege):")
    for (gattung, begruendung), n in sorted(regeln.items()):
        print(f"  {n:4d}  {gattung} | {begruendung}...")
    for e in offen:
        print(f"  OFFEN {e.pfad}:{e.zeile} {e.gattung}")
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())

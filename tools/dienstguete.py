#!/usr/bin/env python3
"""Dienstgüteziele, Fehlerbudget und Alarmzustellung -- aus den Betriebsjournalen.

WARUM
-----
Stufe 10 des Auftrags verlangt „Alarmzustellung bis zu einem Menschen,
Handlungsanweisungen fuer jede Alarmregel, Dienstgueteziele mit Fehlerbudget". Dieses
Werkzeug ist die Zustellstelle: es erhebt die drei Metriken, haelt sie gegen die
vorab gesetzten Ziele, rechnet das verbrauchte Fehlerbudget aus und schreibt jeden
Alarm dorthin, wo ein Mensch ihn sieht.

**Es endet mit einem Rueckgabewert ungleich 0, sobald ein Alarm steht.** Ein Werkzeug,
das einen Alarm nur ausdruckt und mit 0 endet, wird in jeder Automatik uebersehen.

WAS ES NICHT TUT
----------------
Es verschickt nichts. Kein Netzdienst, kein Anbieter. Die Begruendung steht in
``archiv/RUNBOOK.md`` unter „Wenn die Zustellung selbst scheitert": eine Zustellung,
die still
scheitert, weil jemand nicht antwortet, ist schlechter als keine -- sie erweckt den
Eindruck, jemand sei benachrichtigt worden.

Aufruf::

    python tools/dienstguete.py                       # Journale unter betrieb/
    python tools/dienstguete.py --journal aufzeichnungen/demo-2026-08-17.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.betrieb.dienstguete import (  # noqa: E402
    ALARMREGELN,
    NICHT_REPRODUZIERBAR,
    OHNE_STEMPEL,
    ZIELE,
    erhebe,
    nach_codestand,
    pruefe_alarme,
    stelle_zu,
)
from mt5_trading_ai.betrieb.journal import KOPF_ART  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _ist_kopf(zeile: str) -> bool:
    """Die Kopfzeile der Aufzeichnung ist kein Satz -- sie zaehlt in keiner Metrik.

    Ohne diese Weiche liefe sie unter ``nach_codestand`` in die Gruppe „ohne Stempel"
    und zaehlte dort als ein Satz ohne Zeitstempel. Keine Metrik liest sie, aber eine
    Auswertung, die einen Kopf als Ereignis fuehrt, hat ihre Eingabe nicht verstanden.
    """
    if f'"{KOPF_ART}"' not in zeile:
        return False
    try:
        satz = json.loads(zeile)
    except json.JSONDecodeError:
        return False
    return isinstance(satz, dict) and satz.get("art") == KOPF_ART


def _zeilen(quelle: Path) -> list[str]:
    """Alle Satzzeilen der Quelle: Verzeichnis mit Journalen oder EINE Aufzeichnung."""
    dateien = sorted(quelle.glob("*.jsonl")) if quelle.is_dir() else [quelle]
    aus: list[str] = []
    for datei in dateien:
        if datei.is_file():
            aus.extend(
                z
                for z in datei.read_text(encoding="utf-8").splitlines()
                if not _ist_kopf(z)
            )
    return aus


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Dienstgueteziele und Alarme")
    ap.add_argument("--journal", type=Path, default=ROOT / "betrieb")
    ap.add_argument("--alarmdatei", type=Path, default=ROOT / "betrieb" / "ALARME.txt")
    args = ap.parse_args()

    zeilen = _zeilen(args.journal)
    if not zeilen:
        # Laut scheitern: ohne Journal gibt es keine Dienstguete, und „alles gruen"
        # waere die gefaehrlichste Auskunft, die dieses Werkzeug geben kann.
        print(f"FEHLGESCHLAGEN — kein Journal unter {args.journal}.", file=sys.stderr)
        return 1

    werte = erhebe(zeilen)

    print("=" * 78)
    print("DIENSTGUETE — Ziele, Fehlerbudget, Alarme")
    print("=" * 78)
    print(f"Quelle: {args.journal}")
    print()
    print(f"{'Ziel':<28}{'Ist':>9}{'Soll':>8}{'Budget':>9}{'verbraucht':>12}")
    gerissen = []
    for ziel in ZIELE:
        wert = werte[ziel.metrik]
        anteil = wert.anteil
        verbraucht = ziel.verbraucht(wert)
        ist = "--" if anteil is None else f"{anteil:.1%}"
        verb = "--" if verbraucht is None else f"{verbraucht:.0%}"
        marke = "" if verbraucht is None or verbraucht <= 1.0 else "  <== gerissen"
        print(
            f"{ziel.name:<28}{ist:>9}{ziel.ziel:>8.1%}"
            f"{ziel.fehlerbudget:>9.1%}{verb:>12}{marke}"
        )
        if verbraucht is not None and verbraucht > 1.0:
            gerissen.append((ziel, wert, verbraucht))

    print()
    for ziel in ZIELE:
        wert = werte[ziel.metrik]
        print(f"  {ziel.name}: {wert.gelungen} von {wert.gesamt} {wert.bezug}")
        if wert.unbeurteilbar:
            # Muss sichtbar sein (V3): ein Anteil aus 8 Vorgaengen, waehrend 11 weitere
            # gar nicht beurteilbar waren, sagt etwas anderes als ein Anteil aus 19.
            # Sie stillschweigend wegzulassen ist dieselbe Luege wie sie mitzuzaehlen.
            print(
                f"    NICHT BEURTEILBAR: {wert.unbeurteilbar} weitere Vorgaenge -- "
                f"die Aufzeichnung gibt es nicht her, nicht im Nenner"
            )
        print(f"    Warum diese Schwelle: {ziel.begruendung}")

    # --- Diagnose: passiert es noch? -----------------------------------------
    # Die Ziele oben urteilen ueber alle Journale zusammen, und das bleibt so. Diese
    # Aufschluesselung ersetzt sie nicht -- sie beantwortet die andere Frage, die der
    # Betrieb braucht: haengt eine Zahl an Code, den es noch gibt?
    print()
    print("-" * 78)
    print("AUFSCHLUESSELUNG NACH CODESTAND (Diagnose, NICHT das Urteil)")
    print("-" * 78)
    staende = nach_codestand(zeilen)
    kopf = "Codestand".ljust(24) + "".join(z.name[:13].rjust(14) for z in ZIELE)
    print(kopf)
    for stand, gruppe in staende.items():
        marke = ""
        if NICHT_REPRODUZIERBAR in stand:
            marke = "  !! nicht reproduzierbar (Arbeitsverzeichnis war unsauber)"
        elif stand == OHNE_STEMPEL:
            marke = "  !! vor der Versionsstempelung"
        zeile = stand[:22].ljust(24)
        for ziel in ZIELE:
            wert = gruppe[ziel.metrik]
            anteil = wert.anteil
            zeile += (
                "--" if anteil is None else f"{anteil:.1%} ({wert.gesamt})"
            ).rjust(14)
        print(zeile + marke)
    print()
    print("Die Gesamtzahl oben bleibt das Urteil. Diese Tabelle sagt nur, WO die")
    print("Fehlschlaege sitzen -- an lebendem Code oder an einem ueberholten Stand.")

    alarme = pruefe_alarme(werte)
    text = stelle_zu(alarme, args.alarmdatei)
    print()
    print("-" * 78)
    if not alarme:
        print("Keine Alarmregel schlaegt an.")
        return 0
    print(f"{len(alarme)} von {len(ALARMREGELN)} Alarmregeln schlagen an:")
    print()
    print(text)
    print()
    print(f"Zugestellt nach: {args.alarmdatei}")
    print(
        "FEHLGESCHLAGEN — Alarm steht. Die Handlung steht in der Alarmzeile.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

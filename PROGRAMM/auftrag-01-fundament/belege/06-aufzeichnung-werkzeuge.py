#!/usr/bin/env python3
"""T6, Familie Aufzeichnung: die Werkzeuge mit der Aufzeichnung als Eingabe.

Faehrt jedes Werkzeug (--help, dann mit aufzeichnungen/demo-2026-08-17.jsonl) als
Unterprozess im Repo-Wurzelverzeichnis und schreibt je Aufruf Befehl, Kopf und Schwanz
der Ausgabe (stdout+stderr) und den Exit-Code. Pfade werden mit <konto> redigiert.

Aufruf::

    python PROGRAMM/auftrag-01-fundament/belege/06-aufzeichnung-werkzeuge.py \
        [--betrieb C:/Users/<konto>/mt5_trading_ai/betrieb] > belege/06-aufzeichnung-werkzeuge.txt
"""

from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUFZ = "aufzeichnungen/demo-2026-08-17.jsonl"
KONTO = getpass.getuser()


def redigiert(text: str) -> str:
    return text.replace(KONTO, "<konto>")


def lauf(titel: str, *args: str, kopf: int = 40, schwanz: int = 0) -> None:
    befehl = [sys.executable, *args]
    p = subprocess.run(
        befehl,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
    )
    zeilen = (p.stdout + ("\n[stderr]\n" + p.stderr if p.stderr.strip() else "")).rstrip().splitlines()
    print()
    print(redigiert(f"$ python {' '.join(args)}   # {titel}"))
    if len(zeilen) <= kopf + schwanz or schwanz == 0 and len(zeilen) <= kopf:
        aus = zeilen
    else:
        aus = zeilen[:kopf] + [f"  ... ({len(zeilen) - kopf - schwanz} Zeilen ausgelassen) ..."] + (zeilen[-schwanz:] if schwanz else [])
    for z in aus:
        print("  " + redigiert(z))
    traceback = any("Traceback" in z for z in zeilen)
    print(f"[exit={p.returncode}]{'  TRACEBACK!' if traceback else ''}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--betrieb", type=Path, default=None, help="Journale (nur lesend) fuer den Abgleich von --pruefen")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="t6-werkzeuge-"))
    print("# T6 Familie Aufzeichnung: die Werkzeuge mit der Aufzeichnung als Eingabe")
    print("# Worktree ohne betrieb/ (wie ein frischer Klon), Windows, Python 3.11.7, 2026-09-03")
    print("# Je Aufruf: Befehl, Ausgabe (gekuerzt), Exit. Pfade mit <konto> redigiert.")
    for t in ("betrieb_auswerten", "betrieb_reihe", "dienstguete", "torzaehlung", "auswertung", "journal_sichern", "aufzeichnung_redigieren"):
        lauf("A13: --help", f"tools/{t}.py", "--help", kopf=3)
    lauf("Laeufe der Aufzeichnung", "tools/betrieb_auswerten.py", AUFZ, "--liste")
    lauf("ohne --lauf: der letzte Lauf", "tools/betrieb_auswerten.py", AUFZ, kopf=14, schwanz=3)
    lauf("LAUF-18 = journal-20260817T173413 (drei Positionen offen gelassen)", "tools/betrieb_auswerten.py", AUFZ, "--lauf", "LAUF-18", kopf=36, schwanz=0)
    lauf("unbekannte Kennung", "tools/betrieb_auswerten.py", AUFZ, "--lauf", "LAUF-99")
    lauf("Vorgabe betrieb/, hier nicht vorhanden", "tools/betrieb_auswerten.py")
    lauf("alle Laeufe der Aufzeichnung", "tools/betrieb_reihe.py", "--journal", AUFZ, kopf=32, schwanz=24)
    lauf("Vorgabe betrieb/, hier nicht vorhanden", "tools/betrieb_reihe.py")
    lauf("Dienstguete (Exit 1 = Alarm steht, so gewollt)", "tools/dienstguete.py", "--journal", AUFZ, "--alarmdatei", str(tmp / "ALARME.txt"), kopf=34, schwanz=6)
    lauf("Torzaehlung (Vorgabe: die Aufzeichnung)", "tools/torzaehlung.py", kopf=8, schwanz=14)
    lauf("Auswertung mit Herkunftsspalte", "tools/auswertung.py", "--journal", AUFZ, kopf=30)
    lauf("Vorgabe betrieb/, hier nicht vorhanden", "tools/journal_sichern.py", "--ziel", str(tmp / "sicherung"))
    lauf("Worktree ohne betrieb/: Eigenpruefung", "tools/aufzeichnung_redigieren.py", "--pruefen")
    if args.betrieb is not None:
        lauf("Abgleich gegen die 21 Journale (nur lesend)", "tools/aufzeichnung_redigieren.py", "--quelle", str(args.betrieb), "--pruefen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

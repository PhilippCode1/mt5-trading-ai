#!/usr/bin/env python3
"""T6, Familie Aufzeichnung: Eichfall rot/gruen fuer Katalog A2 an den vier Dauertor-Dateien.

Rot: die Aufzeichnung wird kurz umbenannt -- die Dauertore muessen dann SCHEITERN
(failed), nicht sich ueberspringen (skipped). Gruen: mit Aufzeichnung 0 Skips, alle
Faelle bestanden. Beide Laeufe mit ``pytest -rs`` (Skips werden gelistet). Die Datei
wird in jedem Fall zurueckbenannt (finally).

Aufruf::

    python PROGRAMM/auftrag-01-fundament/belege/06-aufzeichnung-eichfall.py \
        > PROGRAMM/auftrag-01-fundament/belege/06-aufzeichnung-eichfall-a2.txt
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUFZ = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"
WEG = AUFZ.with_name("demo-2026-08-17.jsonl.eichfall-rot")
DATEIEN = [
    "tests/test_laufabschluss.py",
    "tests/test_buchtreue.py",
    "tests/test_ausstiegsdeckung.py",
    "tests/test_journal_leser.py",
]


def pytest_lauf(titel: str) -> str:
    befehl = [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", *DATEIEN]
    p = subprocess.run(
        befehl,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    zeilen = p.stdout.rstrip().splitlines()
    print()
    print(f"== {titel}")
    print(f"$ python -m pytest -q -rs -p no:cacheprovider {' '.join(DATEIEN)}")
    # Fortschrittszeilen, dann die Zusammenfassung; lange FAILED-Bloecke kuerzen.
    kurz = [z for z in zeilen if not z.startswith("E   ") and not z.startswith("    ")]
    if len(kurz) > 70:
        kurz = kurz[:12] + [f"  ... ({len(kurz) - 40} Zeilen ausgelassen) ..."] + kurz[-28:]
    for z in kurz:
        print("  " + z)
    print(f"[exit={p.returncode}]")
    return zeilen[-1] if zeilen else ""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("# T6 Familie Aufzeichnung: Eichfall A2 (0 Tests, die sich selbst ueberspringen) an den vier Dauertor-Dateien")
    print("# Worktree ohne betrieb/ (wie ein frischer Klon), Windows, Python 3.11.7, pytest 8.3.4, 2026-09-03")
    print(f"# Vor Auftrag 1 (Beleg 03-grundmessung-pytest-worktree.txt): 12 skipped in genau diesen vier Dateien.")
    assert AUFZ.is_file(), f"{AUFZ} fehlt -- der Eichfall braucht sie"
    try:
        AUFZ.rename(WEG)
        assert not AUFZ.exists()
        rot = pytest_lauf("ROT: Aufzeichnung umbenannt -> die Dauertore muessen SCHEITERN, nicht ueberspringen")
    finally:
        if WEG.exists():
            WEG.rename(AUFZ)
    assert AUFZ.is_file(), "Rueckbenennung fehlgeschlagen"
    gruen = pytest_lauf("GRUEN: Aufzeichnung vorhanden -> 0 skipped")

    def zahl(text: str, wort: str) -> int:
        m = re.search(rf"(\d+) {wort}", text)
        return int(m.group(1)) if m else 0

    print()
    print("== Urteil")
    print(f"  rot  : {rot}")
    print(f"  gruen: {gruen}")
    ok_rot = zahl(rot, "failed") > 0 and zahl(rot, "skipped") == 0
    ok_gruen = zahl(gruen, "failed") == 0 and zahl(gruen, "skipped") == 0 and zahl(gruen, "passed") > 0
    print(f"  rot: {zahl(rot, 'failed')} failed, {zahl(rot, 'skipped')} skipped -> {'ROT wie gefordert' if ok_rot else 'NICHT wie gefordert'}")
    print(f"  gruen: {zahl(gruen, 'passed')} passed, {zahl(gruen, 'skipped')} skipped -> {'GRUEN wie gefordert' if ok_gruen else 'NICHT wie gefordert'}")
    return 0 if ok_rot and ok_gruen else 1


if __name__ == "__main__":
    raise SystemExit(main())

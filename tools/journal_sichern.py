#!/usr/bin/env python3
"""Sichert die Betriebsjournale mit Pruefsummen -- ausserhalb des Repos.

WARUM DIESES WERKZEUG
---------------------
``betrieb/`` ist per ``.gitignore`` ausgenommen, und das ist richtig so: ein Journal
enthaelt Kontonummern und waechst mit jedem Takt. Die Folge ist aber, dass die
**einzigen Belege dafuer, dass die Maschine je lief**, auf genau einer Platte liegen
und mit ihr verschwinden.

Dieses Werkzeug legt sie an einen benannten Ort, bildet je Datei eine SHA-256-Summe und
schreibt ein Verzeichnis dazu. Ein Beleg ohne Pruefsumme ist kein Beleg -- er laesst
sich nachtraeglich aendern, und niemand kann es sehen.

Was es NICHT tut: verschluesseln, hochladen, aufraeumen. Wohin die Sicherung gehoert,
entscheidet der Betreiber; dieses Werkzeug schreibt nur dorthin, wo es geheissen wird.

Aufruf::

    python tools/journal_sichern.py --ziel D:/sicherung/mt5
    python tools/journal_sichern.py --ziel ... --pruefen   # nur vergleichen
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    JOURNALORDNER_NAME,
    standard_zustandsordner,
)

#: Die Vorgabe fuer Journale: der Journalordner im Zustandsordner des Benutzers --
#: dort schreibt ``tools/live_betrieb.py``, und dort liegt der Altbestand (A18,
#: Gegenlese T10 E14; gesichert mit Pruefsummen durch ``tools/journal_sichern.py``).
#: Nicht mehr ``betrieb/`` im Arbeitsbaum: Laufzeitdaten gehoeren nicht in den Baum.
JOURNALE = standard_zustandsordner() / JOURNALORDNER_NAME
VERZEICHNIS = "verzeichnis.json"


def _summe(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _quellen() -> list[Path]:
    if not JOURNALE.is_dir():
        return []
    return sorted(
        p
        for p in JOURNALE.iterdir()
        if p.is_file() and p.suffix in (".jsonl", ".log", ".err")
    )


def sichern(ziel: Path) -> int:
    quellen = _quellen()
    if not quellen:
        print(f"Nichts zu sichern — {JOURNALE} ist leer.", file=sys.stderr)
        return 1
    ziel.mkdir(parents=True, exist_ok=True)
    eintraege = []
    for q in quellen:
        summe = _summe(q)
        shutil.copy2(q, ziel / q.name)
        eintraege.append(
            {
                "datei": q.name,
                "bytes": q.stat().st_size,
                "sha256": summe,
                "geaendert": datetime.fromtimestamp(
                    q.stat().st_mtime, tz=UTC
                ).isoformat(timespec="seconds"),
            }
        )
        print(f"  {q.name:<40} {q.stat().st_size:>10} B  {summe[:16]}...")
    verzeichnis = {
        "gesichert_am": datetime.now(UTC).isoformat(timespec="seconds"),
        "quelle": str(JOURNALE),
        "dateien": eintraege,
    }
    (ziel / VERZEICHNIS).write_text(
        json.dumps(verzeichnis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\n{len(eintraege)} Dateien gesichert nach {ziel}")
    print(f"Verzeichnis mit Pruefsummen: {ziel / VERZEICHNIS}")
    return 0


def pruefen(ziel: Path) -> int:
    """Stimmen die gesicherten Dateien noch mit ihren Pruefsummen ueberein?"""
    pfad = ziel / VERZEICHNIS
    if not pfad.is_file():
        print(f"Kein Verzeichnis in {ziel}.", file=sys.stderr)
        return 1
    verzeichnis = json.loads(pfad.read_text(encoding="utf-8"))
    schlecht = 0
    for eintrag in verzeichnis["dateien"]:
        datei = ziel / str(eintrag["datei"])
        if not datei.is_file():
            print(f"  FEHLT    {eintrag['datei']}")
            schlecht += 1
            continue
        ist = _summe(datei)
        if ist != eintrag["sha256"]:
            print(f"  GEAENDERT {eintrag['datei']}")
            print(f"    erwartet {eintrag['sha256']}")
            print(f"    ist      {ist}")
            schlecht += 1
        else:
            print(f"  ok       {eintrag['datei']}")
    if schlecht:
        print(
            f"\nFEHLGESCHLAGEN — {schlecht} von {len(verzeichnis['dateien'])} "
            "Dateien stimmen nicht.",
            file=sys.stderr,
        )
        return 1
    print(
        f"\nok — alle {len(verzeichnis['dateien'])} Dateien unveraendert "
        f"seit {verzeichnis['gesichert_am']}"
    )
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Betriebsjournale sichern und pruefen")
    ap.add_argument(
        "--ziel",
        type=Path,
        required=True,
        help="Verzeichnis der Sicherung, ausserhalb des Repos",
    )
    ap.add_argument(
        "--pruefen",
        action="store_true",
        help="nur die Pruefsummen einer vorhandenen Sicherung vergleichen",
    )
    args = ap.parse_args()
    return pruefen(args.ziel) if args.pruefen else sichern(args.ziel)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Unveraendertheit statt Scan: SHA-256-Manifest fuer Archiv und fremde Eingaenge.

WARUM
-----
Die Doku-Tore pruefen die eigenen, lebenden Dokumente. Drei Ordner sind etwas
anderes: das Archiv des Altstands (``archiv/``), die Bewertung mit ihren Rohausgaben
(``PROGRAMM/eingang/``) und die neun Masterprompts (``PROGRAMM/masterprompts/``).
Sie werden nicht gescannt und nicht nachgezogen -- sie muessen bleiben, wie sie sind.
Das ist ohne Pruefsumme ein Vorsatz; mit Manifest, das Pre-Commit und CI vergleichen,
ein Tor (Abnahmekatalog A14, Masterprompt 01 Abschnitt 7: „Archiv mit Pruefsumme").

Ein Manifest listet jede Datei des Ordners (rekursiv, ohne sich selbst) mit ihrer
SHA-256 ueber die rohen Bytes -- Format wie ``sha256sum``. ``--pruefen`` verlangt
beides: jede gelistete Datei existiert mit gleichem Hash, UND es gibt keine
ungelistete Datei. Eine stille Ergaenzung ist auch eine Aenderung.

Aufruf::

    python tools/archiv_manifest.py --schreiben <ordner>    # Manifest anlegen
    python tools/archiv_manifest.py --pruefen [<ordner>...]  # ohne Ordner: Standard
                                            # Exit 0 ok, 1 Abweichung, 2 fehlt

``--schreiben`` auf einen Ordner, der schon ein Manifest hat, verlangt ``--erneuern``:
ein Archiv wird nicht nebenbei neu eingefroren.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = "MANIFEST.sha256"
STANDARD = (
    "archiv",
    "PROGRAMM/eingang",
    "PROGRAMM/masterprompts",
    "PROGRAMM/vorregistrierung",  # E-018: nach dem Schreiben unveraenderlich
)


def _hash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _rel(p: Path) -> str:
    """Pfad relativ zum Repo, sonst absolut -- fuer Meldungen."""
    return p.relative_to(REPO).as_posix() if p.is_relative_to(REPO) else p.as_posix()


def _dateien(ordner: Path) -> list[Path]:
    return sorted(
        p
        for p in ordner.rglob("*")
        if p.is_file() and p.name != MANIFEST and "__pycache__" not in p.parts
    )


def schreiben(ordner: Path, erneuern: bool) -> int:
    if not ordner.is_dir():
        print(f"FEHLT: {ordner}")
        return 2
    ziel = ordner / MANIFEST
    if ziel.exists() and not erneuern:
        print(f"VERWEIGERT: {_rel(ziel)} existiert; --erneuern noetig.")
        return 1
    zeilen = [
        f"{_hash(p)}  {p.relative_to(ordner).as_posix()}" for p in _dateien(ordner)
    ]
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8", newline="\n")
    print(f"geschrieben: {_rel(ziel)} ({len(zeilen)} Dateien)")
    return 0


def pruefen(ordner: Path) -> int:
    rel = _rel(ordner)
    manifest = ordner / MANIFEST
    if not ordner.is_dir():
        print(f"FEHLT: Ordner {rel}")
        return 2
    if not manifest.is_file():
        print(f"FEHLT: {rel}/{MANIFEST}")
        return 2
    soll: dict[str, str] = {}
    for zeile in manifest.read_text(encoding="utf-8").splitlines():
        if not zeile.strip():
            continue
        h, _, name = zeile.partition("  ")
        soll[name] = h.lower()
    ist = {p.relative_to(ordner).as_posix(): _hash(p) for p in _dateien(ordner)}
    befunde: list[str] = []
    for name, h in soll.items():
        if name not in ist:
            befunde.append(f"fehlt: {name}")
        elif ist[name] != h:
            befunde.append(f"veraendert: {name}")
    for name in ist:
        if name not in soll:
            befunde.append(f"ungelistet: {name}")
    if befunde:
        print(f"ABWEICHUNG in {rel} ({len(befunde)}):")
        for b in befunde[:20]:
            print(f"  {b}")
        return 1
    print(f"ok - {rel}: {len(soll)} Dateien unveraendert")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--schreiben", action="store_true")
    g.add_argument("--pruefen", action="store_true")
    ap.add_argument(
        "--erneuern", action="store_true", help="vorhandenes Manifest ersetzen"
    )
    ap.add_argument("ordner", nargs="*", help="Ordner relativ zum Repo")
    args = ap.parse_args()
    ordner = [REPO / o for o in (args.ordner or STANDARD)]
    if args.schreiben:
        if not args.ordner:
            print("--schreiben verlangt genau einen Ordner")
            return 2
        return max(schreiben(o, args.erneuern) for o in ordner)
    schlimmster = 0
    for o in ordner:
        if not o.is_dir() and not args.ordner:
            continue  # Standardordner, den es noch nicht gibt (Archiv vor T5)
        schlimmster = max(schlimmster, pruefen(o))
    return schlimmster


if __name__ == "__main__":
    sys.exit(main())

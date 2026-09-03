#!/usr/bin/env python3
"""Der Abnahmekatalog ist eingefroren -- SHA-256 festschreiben und pruefen.

WARUM
-----
Regel 3 des Rahmens: der Massstab steht vor der Messung. ``PROGRAMM/abnahmekatalog.md``
wird in Auftrag 1 eingefroren und nie gesenkt. Ein eingefrorener Text ohne Pruefsumme
ist ein Vorsatz; mit Pruefsumme, die ein Hook und die CI vergleichen, ist er ein Tor.

Der Hash wird ueber den Text mit LF-Zeilenenden gebildet, damit Windows- und
Linux-Klone dieselbe Zahl sehen.

Aufruf::

    python tools/katalog_hash.py --schreiben   # einmalig; verweigert das Ueberschreiben
    python tools/katalog_hash.py --pruefen     # 0 unveraendert, 1 Abweichung, 2 fehlt

``--pruefen`` verlangt zusaetzlich, dass ``PROGRAMM/zustand.md`` den Hash
nennt: Stand und Tor duerfen nicht auseinanderlaufen.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
KATALOG = REPO / "PROGRAMM" / "abnahmekatalog.md"
HASHDATEI = REPO / "PROGRAMM" / "abnahmekatalog.sha256"
ZUSTAND = REPO / "PROGRAMM" / "zustand.md"


def katalog_hash(pfad: Path = KATALOG) -> str:
    roh = pfad.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(roh).hexdigest()


def gespeicherter_hash(pfad: Path = HASHDATEI) -> str | None:
    if not pfad.is_file():
        return None
    erste = pfad.read_text(encoding="utf-8").strip().splitlines()
    if not erste:
        return None
    return erste[0].split()[0].lower()


def schreiben() -> int:
    if not KATALOG.is_file():
        print(f"FEHLT: {KATALOG.relative_to(REPO).as_posix()}")
        return 2
    ist = katalog_hash()
    alt = gespeicherter_hash()
    if alt is not None and alt != ist:
        print(
            "VERWEIGERT: es steht bereits ein anderer Hash fest "
            f"({alt[:16]}...). Der Katalog wird nicht neu eingefroren; "
            "verschaerfen nur in PROGRAMM/abnahmekatalog-verschaerfungen.md."
        )
        return 1
    HASHDATEI.write_text(
        f"{ist}  PROGRAMM/abnahmekatalog.md\n", encoding="utf-8", newline="\n"
    )
    print(f"eingefroren: {ist}  PROGRAMM/abnahmekatalog.md")
    return 0


def pruefen() -> int:
    if not KATALOG.is_file():
        print(f"FEHLT: {KATALOG.relative_to(REPO).as_posix()}")
        return 2
    soll = gespeicherter_hash()
    if soll is None:
        print(
            f"FEHLT: {HASHDATEI.relative_to(REPO).as_posix()} (noch nicht eingefroren)"
        )
        return 2
    ist = katalog_hash()
    if ist != soll:
        print(
            "ABWEICHUNG: der Abnahmekatalog wurde veraendert.\n"
            f"  festgeschrieben: {soll}\n"
            f"  jetzt:           {ist}\n"
            "  Der Katalog ist eingefroren; Aenderung zuruecknehmen."
        )
        return 1
    if not ZUSTAND.is_file() or soll not in ZUSTAND.read_text(encoding="utf-8"):
        print(
            "ABWEICHUNG: PROGRAMM/zustand.md nennt den Katalog-Hash nicht "
            f"({soll[:16]}...). Stand und Tor muessen dieselbe Zahl tragen."
        )
        return 1
    print(f"ok - Abnahmekatalog unveraendert ({soll[:16]}...), zustand.md nennt ihn")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--schreiben", action="store_true", help="Hash einmalig festschreiben"
    )
    g.add_argument("--pruefen", action="store_true", help="Hash vergleichen (Tor)")
    args = ap.parse_args()
    return schreiben() if args.schreiben else pruefen()


if __name__ == "__main__":
    sys.exit(main())

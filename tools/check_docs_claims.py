#!/usr/bin/env python3
"""Blockiert Reifegrad-Zusicherungen ohne ausfuehrbaren Beleg, begrenzt die Doku.

WARUM ES DIESES SKRIPT GIBT
---------------------------
Dokumentation wird nicht wertlos, weil sie umfangreich ist, sondern weil sie
Zusicherungen enthaelt, die niemand einloesen kann. Eine Behauptung ist hier
zulaessig, wenn direkt darunter ein AUSFUEHRBARER Beleg steht -- ein Testname,
ein CI-Job oder ein Skript. Wer den Beleg nicht nennen kann, soll die Behauptung
nicht aufstellen.

GEGENSTAND (Programm NEUAUFBAU, Katalog A14)
--------------------------------------------
Geprueft wird die Menge der **lebenden Dokumente** aus ``tools/doku_menge.py``: die
drei Wurzeldateien und die eigenen Dateien unter ``PROGRAMM/``. Das Archiv des
Altstands und die fremden Eingaenge (Bewertung, Masterprompts) werden nicht gescannt --
sie zitieren Zusicherungen als Befund -- sondern per Manifest auf Unveraendertheit
gesichert. Keine Ausnahmeliste: was nicht in der Menge ist, ist es, weil die Menge
positiv definiert ist.

Drei Pruefungen: (1) die Wurzel traegt genau ``README.md``, ``MODULES.md``,
``CLAUDE.md``; (2) hoechstens ``MAX_MARKDOWN_FILES`` lebende Dokumente; (3) keine
gesperrte Phrase ohne Beleg in einem lebenden Dokument.

Aufruf:  python tools/check_docs_claims.py
Exit 1 bei Verstoss.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools import doku_menge  # noqa: E402

# Der Altstand hob diese Grenze zweimal an (12 -> 24 -> 32), je fuer einen
# Abschlussordner. Sie bleibt bei 32 und gilt jetzt fuer die lebende Doku insgesamt
# (Wurzel + PROGRAMM/): rund acht feste Programmdateien plus Plan und Bericht je
# Auftrag. Wer sie anhebt, benennt hier, wofuer -- und lockert damit ein Tor (Regel 3).
MAX_MARKDOWN_FILES = 32

CLAIMS: list[tuple[str, re.Pattern[str]]] = [
    ("Notenbehauptung 10/10", re.compile(r"\b10\s*/\s*10\b")),
    ("Notenbehauptung 9/10", re.compile(r"\b9\s*/\s*10\b")),
    (
        "100 % in Verbindung mit Fertigstellung",
        re.compile(
            r"100\s*%[^\n]{0,60}\b(ready|complete|completed|abgeschlossen|fertig)\b",
            re.I,
        ),
    ),
    ("production ready", re.compile(r"production[\s_.-]?ready", re.I)),
    ("produktionsreif", re.compile(r"produktionsreif", re.I)),
    ("go live ready", re.compile(r"go[\s_.-]?live[\s_.-]?ready", re.I)),
    ("betriebsbereit", re.compile(r"betriebsbereit", re.I)),
    ("vollstaendig implementiert", re.compile(r"vollst[aä]ndig\s+implementiert", re.I)),
    ("fully implemented", re.compile(r"fully\s+implemented", re.I)),
    # Paket 2, A4.2 des Altstands: „abnahmefertig" fehlte in dieser Liste, und ein
    # Logbuch schloss damit -- eine Reifegrad-Zusicherung ohne jeden Beleg.
    ("abnahmefertig", re.compile(r"abnahme(?:fertig|reif|bereit)", re.I)),
]

# Eine ausdruecklich WIDERRUFENE Zusicherung ist keine Zusicherung mehr: der alte Satz
# bleibt lesbar (nie ueberschreiben), und er behauptet nichts mehr.
WITHDRAWN = re.compile(r"WIDERRUFEN\b")

# Ein Beleg ist ausfuehrbar, wenn er auf einen Test, einen CI-Job oder ein Skript zeigt.
PROOF = re.compile(
    r"(?i)\b(beleg|nachweis|proof|verifiziert durch|evidence)\b[^\n]*"
    r"(test_[A-Za-z0-9_]+|tests?/[A-Za-z0-9_./-]+|\.github/workflows/[A-Za-z0-9_.-]+"
    r"|tools/[A-Za-z0-9_.-]+\.py|scripts/[A-Za-z0-9_.-]+|`[^`]+`)"
)


def tracked_markdown() -> list[Path]:
    """Die lebenden Dokumente (siehe tools/doku_menge.py)."""
    return doku_menge.lebende_dokumente(REPO)


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rel = path.relative_to(REPO).as_posix()
    for i, line in enumerate(lines):
        # Eine Zeile, die SELBST der Beleg ist, stellt keine Behauptung auf.
        if PROOF.search(line):
            continue
        if WITHDRAWN.search(line):
            continue
        for label, rx in CLAIMS:
            if not rx.search(line):
                continue
            following = "\n".join(lines[i + 1 : i + 3])
            if PROOF.search(following) or WITHDRAWN.search(following):
                continue
            problems.append(
                f"{rel}:{i + 1}: {label} ohne ausfuehrbaren Beleg\n"
                f"      {line.strip()[:110]}"
            )
    return problems


def counted(files: list[Path]) -> list[Path]:
    """Die Dateien, die gegen ``MAX_MARKDOWN_FILES`` zaehlen: alle lebenden."""
    return list(files)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = tracked_markdown()
    zaehlend = counted(files)
    failures: list[str] = list(doku_menge.wurzel_befunde(REPO))

    if len(zaehlend) > MAX_MARKDOWN_FILES:
        failures.append(
            f"Obergrenze ueberschritten: {len(zaehlend)} lebende Markdown-Dateien, "
            f"erlaubt sind {MAX_MARKDOWN_FILES}. Archivieren, nicht die Grenze anheben."
        )

    for md in files:
        failures.extend(check_file(md))

    if failures:
        print("FEHLGESCHLAGEN - Zusicherung ohne Beleg, Wurzel oder Obergrenze:\n")
        for failure in failures:
            print(f"  {failure}")
        print(
            "\nEine Behauptung ist zulaessig, wenn in einer der beiden Folgezeilen "
            "ein ausfuehrbarer Beleg steht, z. B.:  "
            "Beleg: tests/security/test_x.py::test_y"
        )
        return 1

    gesichert = ", ".join(doku_menge.PRUEFSUMMEN_GESICHERT)
    print(
        f"ok - {len(zaehlend)}/{MAX_MARKDOWN_FILES} lebende Markdown-Dateien "
        f"(Wurzel: {', '.join(doku_menge.PFLICHT_WURZEL)}), keine Zusicherung ohne "
        f"Beleg; per Manifest gesichert statt gescannt: {gesichert}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

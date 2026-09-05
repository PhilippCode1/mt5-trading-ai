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

Vier Pruefungen: (1) die Wurzel traegt genau ``README.md``, ``MODULES.md``,
``CLAUDE.md``; (2) hoechstens ``MAX_MARKDOWN_FILES`` lebende Dokumente; (3) keine
gesperrte Phrase ohne Beleg in einem lebenden Dokument; (4) keine verfolgte
Markdown-Datei, die weder lebend noch per Manifest gesichert ist.

Aufruf:  python tools/check_docs_claims.py
Exit 1 bei Verstoss.
"""

from __future__ import annotations

import argparse
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
    (
        "vollstaendig implementiert",
        re.compile(r"vollst(?:ae|[aä])ndig\s+implementiert", re.I),
    ),
    ("fully implemented", re.compile(r"fully\s+implemented", re.I)),
    # Paket 2, A4.2 des Altstands: „abnahmefertig" fehlte in dieser Liste, und ein
    # Logbuch schloss damit -- eine Reifegrad-Zusicherung ohne jeden Beleg.
    ("abnahmefertig", re.compile(r"abnahme(?:fertig|reif|bereit)", re.I)),
]

# Eine ausdruecklich WIDERRUFENE Zusicherung ist keine Zusicherung mehr: der alte Satz
# bleibt lesbar (nie ueberschreiben), und er behauptet nichts mehr.
# "NICHT WIDERRUFEN" ist kein Widerruf (Gegenlese T5, Einwand B3).
WITHDRAWN = re.compile(r"(?<![Nn][Ii][Cc][Hh][Tt] )WIDERRUFEN\b")

# Ein Beleg ist ausfuehrbar, wenn er auf einen Test, einen CI-Job oder ein Skript zeigt.
PROOF = re.compile(
    r"(?i)\b(beleg|nachweis|proof|verifiziert durch|evidence)\b[^\n]*?"
    r"(?P<ref>test_[A-Za-z0-9_]+(?:\[[^\]]*\])?|tests?/[A-Za-z0-9_./:\[\]-]+"
    r"|\.github/workflows/[A-Za-z0-9_.-]+"
    r"|tools/[A-Za-z0-9_.-]+\.py|scripts/[A-Za-z0-9_.-]+|`[^`]+`)"
)

_PFAD_IM_SPAN = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|yml|yaml)(?:::[A-Za-z0-9_]+)?")
_TESTNAME = re.compile(r"^test_[A-Za-z0-9_]+")


def _beleg_existiert(ref: str) -> bool:
    """Ein Beleg zaehlt nur, wenn er auf etwas zeigt, das es gibt (Gegenlese T5, B3):
    eine Datei im Repo (optional ``::testname``) oder eine Testfunktion in tests/."""
    ref = ref.strip("`").strip()
    if ref.startswith("`"):
        ref = ref.strip("`")
    m = _PFAD_IM_SPAN.search(ref)
    if m:
        pfad, _, name = m.group(0).partition("::")
        datei = REPO / pfad
        if not datei.is_file():
            return False
        if not name:
            return True
        return f"def {name}(" in datei.read_text(encoding="utf-8", errors="replace")
    t = _TESTNAME.match(ref)
    if t:
        name = t.group(0)
        tests = REPO / "tests"
        return any(
            f"def {name}(" in p.read_text(encoding="utf-8", errors="replace")
            for p in tests.glob("*.py")
        )
    return False


_ZITAT = re.compile(r"„[^“]*“|\"[^\"]*\"|`[^`]*`")


def _ohne_zitate(line: str) -> str:
    """Eine Phrase in Anfuehrungszeichen ist Erwaehnung, keine Zusicherung -- CLAUDE.md
    Abschnitt 0 nennt („produktionsreif“) als verbotenes Wort (Gegenlese T5, B3)."""
    return _ZITAT.sub("", line)


def hat_beleg(text: str) -> bool:
    """Steht in ``text`` ein Beleg, der existiert?"""
    return any(_beleg_existiert(m.group("ref")) for m in PROOF.finditer(text))


def tracked_markdown() -> list[Path]:
    """Die lebenden Dokumente (siehe tools/doku_menge.py)."""
    return doku_menge.lebende_dokumente(REPO)


def _fenster(lines: list[str], i: int) -> str:
    """Zeile ``i`` mit der Folgezeile verbunden -- so, wie Markdown sie setzt.

    Markdown fuegt Zeilen bis zur naechsten Leerzeile zu einem Absatz zusammen; eine
    Zusicherung aus zwei Woertern kann darum ueber einen Zeilenumbruch gehen
    ("vollstaendig" / "implementiert"), und ein Bindestrich am Zeilenende verschmilzt
    mit der Folgezeile ("produktions-" / "reif"). Zeilenweise Suche sah beides nicht
    (Gegenlese T10, E13). Eine Leerzeile beendet den Absatz -- und das Fenster.
    """
    erste = lines[i].rstrip()
    zweite = lines[i + 1].strip() if i + 1 < len(lines) else ""
    if not zweite or not erste.strip():
        return erste
    if erste.endswith("-") and zweite[:1].isalpha():
        return erste[:-1] + zweite
    return erste + " " + zweite


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rel = path.relative_to(REPO).as_posix()
    for i, line in enumerate(lines):
        # Eine Zeile, die SELBST einen existierenden Beleg nennt, stellt keine
        # Behauptung auf. Ein Beleg ins Leere zaehlt nicht (Gegenlese T5, B3).
        if hat_beleg(line):
            continue
        if WITHDRAWN.search(line):
            continue
        naechste = _ohne_zitate(lines[i + 1]) if i + 1 < len(lines) else ""
        fenster = _ohne_zitate(_fenster(lines, i))
        for label, rx in CLAIMS:
            # In der Zeile selbst -- oder ueber den Umbruch hinweg (dann nicht schon
            # ganz in der Folgezeile, die fuer sich geprueft wird).
            if not rx.search(_ohne_zitate(line)) and not (
                rx.search(fenster) and not rx.search(naechste)
            ):
                continue
            following = "\n".join(lines[i + 1 : i + 3])
            if hat_beleg(following) or WITHDRAWN.search(following):
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
    # A13: jedes Werkzeug antwortet auf --help mit Exit 0 (Gegenlese T5, B11).
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = tracked_markdown()
    zaehlend = counted(files)
    failures: list[str] = list(doku_menge.wurzel_befunde(REPO))
    failures += [
        f"unbeaufsichtigt: {rel} ist weder lebend noch per Manifest gesichert -- "
        "archivieren, nach PROGRAMM/ verschieben oder loeschen"
        for rel in doku_menge.unbeaufsichtigt(REPO)
    ]

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

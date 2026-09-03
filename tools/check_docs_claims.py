#!/usr/bin/env python3
"""Blockiert Reifegrad-Zusicherungen ohne ausfuehrbaren Beleg, begrenzt die Doku.

WARUM ES DIESES SKRIPT GIBT
---------------------------
Dokumentation wird nicht wertlos, weil sie umfangreich ist, sondern weil sie
Zusicherungen enthaelt, die niemand einloesen kann. Eine Behauptung ist hier
zulaessig, wenn direkt darunter ein AUSFUEHRBARER Beleg steht -- ein Testname,
ein CI-Job oder ein Skript. Wer den Beleg nicht nennen kann, soll die Behauptung
nicht aufstellen. Geprueft wird jede vom Git verfolgte Markdown-Datei.

Aufruf:  python tools/check_docs_claims.py
Exit 1 bei Verstoss.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Bewusst angehoben, zweimal, jeweils fuer einen vorgeschriebenen Abschlussordner.
# Die Grenze soll Doku-Wildwuchs bremsen, nicht einen Auftrag verhindern.
#   12 -> 24 (Paket 2): neun Dateien aus ABSCHLUSS/ plus die drei Wurzeldokumente
#                       ABBRUCH.md, ALPHA.md und HALAL-VORFRAGE.md.
#   24 -> 32 (Paket 3a): die acht Dateien aus ABSCHLUSS-3a/.
# Jede weitere neue Markdown-Datei laesst das Tor wieder rot werden -- die Bremse bleibt
# scharf, sie steht nur ein Stueck weiter. Wer sie erneut anhebt, benennt hier, wofuer.
MAX_MARKDOWN_FILES = 32

# ``AUFTRAG/`` wird NICHT mitgezaehlt -- und die Grenze wurde dafuer auch nicht ein
# drittes Mal angehoben. Grund: dieser Ordner ist der vom Dauerauftrag vorgeschriebene
# Abschlussordner und waechst *bauartbedingt* mit jeder Stufe (ein Bericht je Stufe, bis
# zu elf). Die Grenze bei jeder Stufe nachzuziehen waere genau die Ratsche, vor der der
# Kommentar darueber warnt; die Bremse bliebe dem Namen nach scharf und waere es der
# Sache nach nicht mehr. Sie steht deshalb unveraendert bei 32 fuer die Doku des
# Projekts, und der Auftragsordner faellt gar nicht erst in ihren Geltungsbereich.
#
# Die Behauptungspruefung laeuft weiter ueber ``AUFTRAG/`` -- nur die ZAEHLUNG nicht.
# Das ist die scharfe Haelfte: der Dauerauftrag verbietet Notenbehauptungen
# ausdruecklich, und ein Bericht darin soll daran genauso scheitern wie jede
# andere Datei.
# ``PROGRAMM/`` (Programm NEUAUFBAU) ist der vom Masterprompt vorgeschriebene
# Programmordner -- derselbe Fall wie AUFTRAG/: er waechst bauartbedingt (Zustand,
# Entscheidungen, Plan und Bericht je Auftrag) und faellt deshalb nicht in die
# Zaehlung. Die Behauptungspruefung gilt fuer die eigenen Dateien darin weiter.
EXCLUDED_FROM_COUNT = ("AUFTRAG/", "PROGRAMM/")

# Fremde, unveraenderliche Eingaenge: die Bewertung samt Rohausgaben und die neun
# Masterprompts. Sie sind nicht die Doku dieses Projekts, sondern sein Pruefauftrag;
# sie werden weder gezaehlt noch auf Zusicherungen geprueft -- sie zitieren solche
# absichtlich (etwa den Commit-Titel „produktionsreif" als Befund). Dass sie
# unveraendert bleiben, sichert in Auftrag 1 ein Manifest mit Pruefsumme, nicht
# dieses Tor.
FREMDE_EINGAENGE = ("PROGRAMM/eingang/", "PROGRAMM/masterprompts/")

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
    # Paket 2, A4.2: „abnahmefertig" fehlte in dieser Liste. PROGRESS.md schloss damit
    # auf „System abnahmefertig." -- eine Reifegrad-Zusicherung ohne jeden Beleg, die
    # genau dieses Tor haette fangen sollen und durch eine Luecke im Wortschatz lief.
    ("abnahmefertig", re.compile(r"abnahme(?:fertig|reif|bereit)", re.I)),
]

# Eine ausdruecklich WIDERRUFENE Zusicherung ist keine Zusicherung mehr. Ohne diese
# Ausnahme gaebe es fuer ein anhaengendes Logbuch (Kernregel 22: nie ueberschreiben)
# keinen Weg, eine falsche Aussage zu korrigieren, ohne die Geschichte zu faelschen:
# loeschen ist verboten, stehen lassen ist unwahr. Der Widerruf loest beides -- der
# alte Satz bleibt lesbar, und er behauptet nichts mehr.
WITHDRAWN = re.compile(r"WIDERRUFEN\b")

# Ein Beleg ist ausfuehrbar, wenn er auf einen Test, einen CI-Job oder ein Skript zeigt.
PROOF = re.compile(
    r"(?i)\b(beleg|nachweis|proof|verifiziert durch|evidence)\b[^\n]*"
    r"(test_[A-Za-z0-9_]+|tests?/[A-Za-z0-9_./-]+|\.github/workflows/[A-Za-z0-9_.-]+"
    r"|tools/[A-Za-z0-9_.-]+\.py|scripts/[A-Za-z0-9_.-]+|`[^`]+`)"
)


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO / p for p in out]


def check_file(path: Path) -> list[str]:
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rel = path.relative_to(REPO).as_posix()
    for i, line in enumerate(lines):
        # Eine Zeile, die SELBST der Beleg ist, stellt keine Behauptung auf. Ohne diese
        # Ausnahme wuerde `Beleg: git grep -l '10/10' ...` sich selbst ausloesen.
        if PROOF.search(line):
            continue
        # Ein Widerruf auf derselben Zeile nimmt die Zusicherung zurueck.
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


def ist_fremder_eingang(path: Path) -> bool:
    return path.relative_to(REPO).as_posix().startswith(FREMDE_EINGAENGE)


def pruefbar(files: list[Path]) -> list[Path]:
    """Die Dateien, die auf Zusicherungen geprueft werden: alle eigenen."""
    return [p for p in files if not ist_fremder_eingang(p)]


def counted(files: list[Path]) -> list[Path]:
    """Die Dateien, die gegen ``MAX_MARKDOWN_FILES` zaehlen (siehe dort)."""
    return [
        p
        for p in files
        if not p.relative_to(REPO).as_posix().startswith(EXCLUDED_FROM_COUNT)
    ]


def main() -> int:
    files = tracked_markdown()
    eigene = pruefbar(files)
    zaehlend = counted(eigene)
    failures: list[str] = []

    if len(zaehlend) > MAX_MARKDOWN_FILES:
        failures.append(
            f"Obergrenze ueberschritten: {len(zaehlend)} Markdown-Dateien, "
            f"erlaubt sind "
            f"{MAX_MARKDOWN_FILES}. Eine loeschen oder die Grenze bewusst anheben."
        )

    for md in eigene:
        failures.extend(check_file(md))

    if failures:
        print("FEHLGESCHLAGEN - Zusicherung ohne Beleg oder zu viele Doku-Dateien:\n")
        for failure in failures:
            print(f"  {failure}")
        print(
            "\nEine Behauptung ist zulaessig, wenn in einer der beiden Folgezeilen "
            "ein ausfuehrbarer Beleg steht, z. B.:  "
            "Beleg: tests/security/test_x.py::test_y"
        )
        return 1

    print(
        f"ok - {len(zaehlend)}/{MAX_MARKDOWN_FILES} gezaehlte Markdown-Dateien "
        f"(+{len(eigene) - len(zaehlend)} in AUFTRAG/ und PROGRAMM/ auf Behauptungen "
        f"geprueft, nicht gezaehlt; {len(files) - len(eigene)} fremde Eingaenge "
        f"nicht geprueft), keine Zusicherung ohne Beleg"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

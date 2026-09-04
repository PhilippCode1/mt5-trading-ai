#!/usr/bin/env python3
"""Die Menge der lebenden Dokumente -- positiv definiert, ohne Ausnahmeliste (A14).

WARUM
-----
Die Doku-Tore des Altstands nahmen 43 von 56 Markdown-Dateien ueber Listen aus
(``HISTORICAL``, ``EXCLUDED_FROM_COUNT``); jede Stufe verlaengerte die Liste. Eine
Ausnahmeliste, die waechst, ist ein Tor, das schrumpft. Das Programm NEUAUFBAU definiert
stattdessen, **was** geprueft wird:

* **lebende Dokumente** = Markdown an der Wurzel des Repos und unter ``PROGRAMM/``,
  ausgenommen die beiden Eingangsordner ``PROGRAMM/eingang/`` (Bewertung, Rohausgaben)
  und ``PROGRAMM/masterprompts/`` (die neun Auftraege) -- beides fremde,
  unveraenderliche
  Texte;
* an der **Wurzel** liegen genau drei Dateien: ``README.md`` (Einstieg), ``MODULES.md``
  (aus dem Code erzeugt) und ``CLAUDE.md`` (der Rahmen);
* alles andere -- ``archiv/``, die Eingaenge -- wird nicht gescannt, sondern per
  SHA-256-Manifest auf Unveraendertheit geprueft (``tools/archiv_manifest.py``).

Die vier Doku-Tore und das Kopien-Tor beziehen ihre Menge von hier.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Die Wurzel traegt genau diese Dateien -- nicht mehr, nicht weniger.
PFLICHT_WURZEL: tuple[str, ...] = ("README.md", "MODULES.md", "CLAUDE.md")

#: Unterordner von PROGRAMM/, die fremde Eingaenge sind (nicht die eigene Doku).
EINGAENGE_UNTER_PROGRAMM: tuple[str, ...] = ("eingang", "masterprompts")

#: Ordner, deren Unveraendertheit ein Manifest sichert (Standard von archiv_manifest).
PRUEFSUMMEN_GESICHERT: tuple[str, ...] = (
    "archiv",
    "PROGRAMM/eingang",
    "PROGRAMM/masterprompts",
    "PROGRAMM/vorregistrierung",
)


def ist_lebend(rel: str) -> bool:
    """Ob ein repo-relativer Markdown-Pfad zur eigenen, lebenden Doku gehoert."""
    # Gesicherte Ordner (Manifest) sind nie lebend -- auch nicht unter PROGRAMM/
    # (E-018: Vorregistrierungen sind nach dem Schreiben unveraenderlich).
    if ist_gesichert(rel):
        return False
    teile = rel.replace("\\", "/").split("/")
    if len(teile) == 1:
        return True
    if teile[0] == "PROGRAMM":
        return teile[1] not in EINGAENGE_UNTER_PROGRAMM
    return False


def ist_wurzel(rel: str) -> bool:
    return "/" not in rel.replace("\\", "/")


def verfolgte_markdown(repo: Path = REPO) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout
    # Kein Pathspec: `git ls-files '*.md'` ist schreibungsempfindlich und uebersieht
    # NOTES.MD oder STAND.markdown (Gegenlese T5, Einwand B2). Gefiltert wird hier.
    return [
        z.strip()
        for z in out.splitlines()
        if z.strip().lower().endswith((".md", ".markdown"))
    ]


def lebende_dokumente(repo: Path = REPO) -> list[Path]:
    return [repo / rel for rel in verfolgte_markdown(repo) if ist_lebend(rel)]


def wurzeldokumente(repo: Path = REPO) -> list[str]:
    return sorted(rel for rel in verfolgte_markdown(repo) if ist_wurzel(rel))


def wurzel_befunde(repo: Path = REPO) -> list[str]:
    """Abweichungen der Wurzel von PFLICHT_WURZEL; leer, wenn genau die drei da sind."""
    ist = set(wurzeldokumente(repo))
    soll = set(PFLICHT_WURZEL)
    befunde = [f"fehlt an der Wurzel: {n}" for n in sorted(soll - ist)]
    befunde += [
        f"zu viel an der Wurzel: {n} (archivieren oder nach PROGRAMM/)"
        for n in sorted(ist - soll)
    ]
    return befunde


def ist_gesichert(rel: str) -> bool:
    """Ob ein Pfad in einem per Manifest gesicherten Ordner liegt."""
    rel = rel.replace(chr(92), "/")
    return any(rel.startswith(o + "/") for o in PRUEFSUMMEN_GESICHERT)


def unbeaufsichtigt(repo: Path = REPO) -> list[str]:
    """Verfolgte Markdown-Dateien, die weder lebend noch gesichert sind.

    Die Menge ist positiv definiert; damit sie keine Luecke laesst, muss jede
    verfolgte Datei in genau eine der beiden Klassen fallen. Eine .md unter
    tests/ oder tools/ waere sonst weder gescannt noch eingefroren.
    """
    return sorted(
        rel
        for rel in verfolgte_markdown(repo)
        if not ist_lebend(rel) and not ist_gesichert(rel)
    )

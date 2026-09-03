"""T5, Schritt 1: Altstand-Dokumente nach archiv/altstand-306bbaa/ verschieben (git mv),
Pfadverweise in Code, Tests und Konfiguration nachziehen, Manifest schreiben.

Eigenes Skript (2026-09-03). Es verschiebt nur; nichts wird geloescht. Jede Ersetzung
wird gezaehlt und ausgegeben. Ausfuehrung im Arbeitsrepo; danach Tore und Suite.

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-archivieren.py [--trocken]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ARCHIV = "archiv/altstand-306bbaa"
ORDNER = ("AUFTRAG", "ABSCHLUSS", "ABSCHLUSS-3a", "docs")
DATEIEN = (
    "ABBRUCH.md",
    "ABNAHME_PLAN.md",
    "ALPHA.md",
    "BERICHT_TEIL3.md",
    "FEHLT.md",
    "MASTERBERICHT.md",
    "PROGRESS.md",
    "RECHERCHE_DATEN.md",
    "RECHERCHE_KOSTEN.md",
    "RUNBOOK.md",
    "SPAETER.md",
    "VERLUST.md",
)
# Reihenfolge: laengere Praefixe zuerst, damit ABSCHLUSS-3a/ nicht als ABSCHLUSS/ + Rest zerfaellt.
MUSTER = [
    re.compile(rf"(?<!{re.escape(ARCHIV)}/)(?<![A-Za-z0-9_./-])({p})")
    for p in (
        "ABSCHLUSS-3a/",
        "ABSCHLUSS/",
        "AUFTRAG/",
        "docs/audit/",
        "docs/overview\\.html",
        *[re.escape(d) for d in DATEIEN],
    )
]
# Wo nachgezogen wird: eigener Code, Tests, Konfiguration, CI. Nicht: das Archiv selbst,
# PROGRAMM/ (Messprotokolle nennen die alten Pfade als historische Fundstellen), README.md
# (wird in T5 neu geschrieben), .git.
ZIELE = ("mt5_trading_ai", "tools", "tests", "config", ".github", "pyproject.toml", "CLAUDE.md")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def main() -> int:
    trocken = "--trocken" in sys.argv
    ziel = REPO / ARCHIV
    if not trocken:
        ziel.mkdir(parents=True, exist_ok=True)
    print(f"# Archivziel: {ARCHIV}{' (TROCKEN)' if trocken else ''}")
    for name in (*ORDNER, *DATEIEN):
        quelle = REPO / name
        if not quelle.exists():
            print(f"  FEHLT (uebersprungen): {name}")
            continue
        print(f"  git mv {name} -> {ARCHIV}/{name}")
        if not trocken:
            git("mv", name, f"{ARCHIV}/{name}")
    # Pfadverweise nachziehen
    tracked = [
        REPO / p
        for p in git("ls-files", *ZIELE).splitlines()
        if p and not p.startswith(ARCHIV)
    ]
    gesamt = 0
    for pfad in tracked:
        if pfad.suffix not in {".py", ".json", ".toml", ".yml", ".yaml", ".md", ".txt", ".cfg"}:
            continue
        try:
            text = pfad.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        neu = text
        je_datei = 0
        for rx in MUSTER:
            neu, n = rx.subn(lambda m: f"{ARCHIV}/{m.group(1)}", neu)
            je_datei += n
        if je_datei:
            gesamt += je_datei
            print(f"  {pfad.relative_to(REPO).as_posix()}: {je_datei} Verweis(e) nachgezogen")
            if not trocken:
                pfad.write_text(neu, encoding="utf-8", newline="")
    print(f"# Verweise nachgezogen: {gesamt}")
    if not trocken:
        lauf = subprocess.run(
            [sys.executable, "tools/archiv_manifest.py", "--schreiben", ARCHIV],
            cwd=REPO, capture_output=True, text=True, encoding="utf-8",
        )
        print(lauf.stdout.strip())
        return lauf.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())

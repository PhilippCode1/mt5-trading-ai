#!/usr/bin/env python3
"""Git-Pre-Commit-Hook: eingefrorene Dateien sperren, die schnellen Tore fahren.

Aufgerufen von ``.githooks/pre-commit`` (``git config core.hooksPath .githooks``).
Nichts hier laesst sich per Umgebungsvariable abschalten; wer ``--no-verify`` benutzt,
umgeht einen Hook -- das verbietet der Rahmen.

Zwei Haelften:

1. **Sperren.** Eine im Index geaenderte, geloeschte oder umbenannte Datei aus
   ``GESPERRT`` wird abgewiesen, sobald sie schon in HEAD liegt (das erstmalige Anlegen
   ist erlaubt -- so wird der Katalog eingefroren). Dasselbe fuer jede vorhandene
   Datei unter ``PROGRAMM/vorregistrierung/``.
2. **Tore.** Jedes Tor laeuft einzeln, mit Dauer; der Commit haengt an der Summe der
   Rueckgabewerte (F-002: keine ``&&``-Ketten, keine Pipes vor dem Exit-Code). Die
   Doku-Tore lesen ``git ls-files`` -- also den Index, nicht den Arbeitsbaum (F-001,
   F-003). Die volle Testsuite laeuft im Pre-Push-Hook und in der CI, nicht hier.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

GESPERRT = (
    "PROGRAMM/abnahmekatalog.md",
    "PROGRAMM/abnahmekatalog.sha256",
    "config/live_freigabe.json",
)
UNVERAENDERLICH = "PROGRAMM/vorregistrierung/"

TORE: tuple[tuple[str, list[str]], ...] = (
    ("Katalog-Hash", [sys.executable, "tools/katalog_hash.py", "--pruefen"]),
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    (
        "mypy strict",
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "mt5_trading_ai",
            "tools",
            "PROGRAMM/hooks",
        ],
    ),
    ("MODULES.md", [sys.executable, "tools/gen_docs.py", "--check"]),
    ("Doku-Behauptungen", [sys.executable, "tools/check_docs_claims.py"]),
    ("Doku-Zahlen", [sys.executable, "tools/check_doc_numbers.py"]),
    ("Kopien", [sys.executable, "tools/kopien_abgleichen.py", "--pruefen"]),
    ("Manifeste", [sys.executable, "tools/archiv_manifest.py", "--pruefen"]),
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def _in_head(pfad: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{pfad}"], cwd=REPO, capture_output=True
        ).returncode
        == 0
    )


def sperren() -> list[str]:
    """Abgewiesene Aenderungen im Index -- leer, wenn nichts gesperrt ist."""
    befunde: list[str] = []
    for zeile in _git("diff", "--cached", "--name-status", "-M").splitlines():
        teile = zeile.split("\t")
        status, pfade = teile[0], teile[1:]
        for pfad in pfade:
            gesperrt = pfad in GESPERRT
            vorreg = pfad.startswith(UNVERAENDERLICH)
            if not (gesperrt or vorreg):
                continue
            if status.startswith("A") and not _in_head(pfad):
                continue  # erstmaliges Anlegen: erlaubt
            art = "eingefroren" if gesperrt else "Vorregistrierung, unveraenderlich"
            befunde.append(f"{pfad}: {status} -- {art}")
    return befunde


def tore() -> int:
    fehler = 0
    for name, befehl in TORE:
        if (
            name == "Katalog-Hash"
            and not (REPO / "PROGRAMM" / "abnahmekatalog.sha256").is_file()
        ):
            print(f"  --  {name}: noch nicht eingefroren, uebersprungen")
            continue
        start = time.perf_counter()
        lauf = subprocess.run(befehl, cwd=REPO, capture_output=True, text=True)
        dauer = time.perf_counter() - start
        letzte = (
            lauf.stdout.strip().splitlines() or lauf.stderr.strip().splitlines() or [""]
        )[-1]
        marke = "ok " if lauf.returncode == 0 else "ROT"
        print(f"  {marke} {name} ({dauer:4.1f} s): {letzte[:100]}")
        if lauf.returncode != 0:
            fehler += 1
            if lauf.stdout.strip():
                print("      " + "\n      ".join(lauf.stdout.strip().splitlines()[-8:]))
    return fehler


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("pre-commit: Sperren")
    befunde = sperren()
    for b in befunde:
        print(f"  ABGEWIESEN {b}")
    if befunde:
        print(
            "Commit abgewiesen: eingefrorene Dateien werden nicht veraendert. "
            "Aenderung zuruecknehmen (git restore --staged / git checkout); "
            "Verschaerfung nur in PROGRAMM/abnahmekatalog-verschaerfungen.md."
        )
        return 1
    print("pre-commit: Tore (ueber den Index)")
    start = time.perf_counter()
    fehler = tore()
    dauer = time.perf_counter() - start
    print(f"pre-commit: {len(TORE)} Tore in {dauer:.1f} s, {fehler} rot")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

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
   volle Testsuite laeuft im Pre-Push-Hook und in der CI, nicht hier.

   **Sie laufen auf dem INDEX, nicht auf dem Arbeitsbaum** (F-009). Bis zum
   2026-09-05 stand hier, ``git ls-files`` lese ohnehin den Index -- das gilt fuer
   die *Dateiliste*, nicht fuer den *Inhalt*: die Werkzeuge oeffneten die Dateien
   auf der Platte. Wer eine rote Fassung stagt und eine saubere im Arbeitsbaum
   liegen laesst (``git add x`` und danach die Datei zuruecksetzen), kam damit an
   allen neun Toren vorbei -- gemessen in der Gegenlese T10, Einwand E7, mit einem
   Commit, dessen Inhalt ``ruff check`` mit neun Fehlern quittiert. Genau die
   Fehlerklasse, die dieser Hook schliessen soll (F-001, F-003, F-004).

   Darum wird der Index vor dem Lauf in ein temporaeres Verzeichnis ausgecheckt
   (``git checkout-index -a``), dort ein Wegwerf-Git angelegt (die Doku-Tore
   brauchen ``git ls-files``), und die Tore laufen mit ``cwd`` auf dieser Kopie.
   Was gemessen wird, ist damit genau das, was committet wird.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

GESPERRT = (
    "PROGRAMM/abnahmekatalog.md",
    "PROGRAMM/abnahmekatalog.sha256",
    "config/live_freigabe.json",
)
UNVERAENDERLICH = "PROGRAMM/vorregistrierung/"

#: Aenderbar, aber nie unbemerkt: wer einen Waechter anfasst, sieht eine Zeile
#: darueber im Commit-Lauf. Gegenlese T10, E11: ein Commit, der .githooks/pre-commit
#: leert, lief bis dahin durch den Hook, den er gerade entfernte -- und niemand sah
#: es. Sperren waere falsch (die Waechter muessen sich weiterentwickeln lassen);
#: stillschweigen ist es auch.
GEMELDET = (
    "PROGRAMM/hooks/waechter.py",
    "PROGRAMM/hooks/pre_commit.py",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    ".claude/settings.json",
    ".github/workflows/ci.yml",
)

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


def index_auschecken() -> tuple[Path, str]:
    """Den Index in ein temporaeres Verzeichnis legen -- mit Wegwerf-Git.

    Rueckgabe: Pfad und eine Zeile fuer die Ausgabe. Scheitert das Auschecken,
    ist das ein Fehler und kein Rueckfall auf den Arbeitsbaum: ein Tor, das
    heimlich etwas anderes misst als angekuendigt, ist schlimmer als keines.
    """
    ziel = Path(tempfile.mkdtemp(prefix="pre-commit-index-"))
    aus = subprocess.run(
        ["git", "checkout-index", "-a", "-f", "--prefix", ziel.as_posix() + "/"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if aus.returncode != 0:
        raise RuntimeError(f"git checkout-index: {(aus.stderr or '').strip()}")
    # Die Doku-Tore lesen `git ls-files`; ohne eigenes Git saehen sie nichts.
    for befehl in (
        ["git", "init", "-q"],
        ["git", "-c", "core.longpaths=true", "add", "-A"],
    ):
        for versuch in range(6):
            lauf = subprocess.run(befehl, cwd=ziel, capture_output=True, text=True)
            if lauf.returncode == 0:
                break
            if versuch == 5:
                raise RuntimeError(
                    f"Wegwerf-Git: {' '.join(befehl)} -> "
                    f"{(lauf.stderr or '').strip()[:300]}"
                )
            time.sleep(0.5 * 2**versuch)  # F-008: der Virenscanner haelt Dateien
    anzahl = len(list(ziel.rglob("*")))
    return ziel, f"Index ausgecheckt: {anzahl} Eintraege in <temp>/{ziel.name}"


def gemeldete() -> list[str]:
    """Welche Waechterdateien liegen im Index dieses Commits?"""
    aus = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO,
        capture_output=True,
        text=True,
    ).stdout.split()
    return [p for p in aus if p in GEMELDET]


def tore(auf: Path) -> int:
    fehler = 0
    for name, befehl in TORE:
        if (
            name == "Katalog-Hash"
            and not (auf / "PROGRAMM" / "abnahmekatalog.sha256").is_file()
        ):
            print(f"  --  {name}: noch nicht eingefroren, uebersprungen")
            continue
        start = time.perf_counter()
        lauf = subprocess.run(befehl, cwd=auf, capture_output=True, text=True)
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
    for pfad in gemeldete():
        print(f"  HINWEIS ein Waechter wird geaendert: {pfad}")
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
    print("pre-commit: Tore -- gefahren auf dem INDEX, nicht auf dem Arbeitsbaum")
    start = time.perf_counter()
    try:
        auf, zeile = index_auschecken()
    except RuntimeError as exc:
        print(f"  ABGEWIESEN Index nicht auscheckbar: {exc}")
        print(
            "Commit abgewiesen: ohne Kopie des Index messen die Tore den "
            "Arbeitsbaum, und genau das war der Weg an ihnen vorbei (F-009)."
        )
        return 1
    print(f"  {zeile}")
    try:
        fehler = tore(auf)
    finally:
        shutil.rmtree(auf, ignore_errors=True)
    dauer = time.perf_counter() - start
    print(f"pre-commit: {len(TORE)} Tore in {dauer:.1f} s, {fehler} rot")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

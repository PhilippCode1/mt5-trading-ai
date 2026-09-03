"""Eichfall A7 (Pre-Commit-Hook und Katalog-Hash) -- in einem Wegwerf-Klon.

Der Klon bekommt ``core.hooksPath=.githooks`` wie das Arbeitsrepo. Dann wird
versucht, (1) den eingefrorenen Abnahmekatalog, (2) die Live-Schalter, (3) eine
vorhandene Vorregistrierung zu aendern und zu committen. Erwartung: jeder Commit
wird vom Hook abgewiesen (Exit != 0, Ausgabe "ABGEWIESEN"), und
``tools/katalog_hash.py --pruefen`` meldet im Klon die Abweichung (Exit 1).
Zum Vergleich (4): eine gewoehnliche Datei laesst sich committen (Exit 0).

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/02-eichfall-pre-commit.py
Schreibt nichts ins Arbeitsrepo; der Klon liegt in einem temporaeren Verzeichnis.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
KATALOG = "PROGRAMM/abnahmekatalog.md"
SCHALTER = "config/live_freigabe.json"
VORREG = "PROGRAMM/vorregistrierung/00-HINWEIS.md"


def git(klon: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=klon, capture_output=True, text=True, encoding="utf-8"
    )


def versuch(klon: Path, pfad: str, titel: str) -> tuple[int, str]:
    datei = klon / pfad
    datei.write_text(
        datei.read_text(encoding="utf-8") + "\nEICHFALL: absichtliche Aenderung\n",
        encoding="utf-8",
        newline="\n",
    )
    git(klon, "add", pfad)
    lauf = git(klon, "commit", "-q", "-m", f"Eichfall: {titel}")
    ausgabe = (lauf.stdout + lauf.stderr).strip()
    git(klon, "reset", "-q", "--hard")
    return lauf.returncode, ausgabe


def main() -> int:
    fehler = 0
    with tempfile.TemporaryDirectory() as tmp:
        klon = Path(tmp) / "klon"
        subprocess.run(
            ["git", "clone", "-q", str(REPO), str(klon)],
            check=True,
            capture_output=True,
        )
        git(klon, "config", "core.hooksPath", ".githooks")
        git(klon, "config", "user.name", "eichfall")
        git(klon, "config", "user.email", "eichfall@example.invalid")
        head = git(klon, "rev-parse", "--short", "HEAD").stdout.strip()
        print(f"Klon: {klon}  HEAD={head}")

        faelle = [
            (KATALOG, "Abnahmekatalog aendern", True),
            (SCHALTER, "Live-Schalter aendern", True),
            (VORREG, "Vorregistrierung aendern", True),
            ("README.md", "gewoehnliche Datei aendern", False),
        ]
        for pfad, titel, soll_abgewiesen in faelle:
            rc, ausgabe = versuch(klon, pfad, titel)
            abgewiesen = rc != 0 and "ABGEWIESEN" in ausgabe
            ok = abgewiesen == soll_abgewiesen if soll_abgewiesen else rc == 0
            fehler += 0 if ok else 1
            print(
                f"\n{'OK ' if ok else '!! '} {titel} ({pfad}): git commit exit={rc}, "
                f"erwartet {'Abweisung' if soll_abgewiesen else 'Annahme'}"
            )
            for zeile in ausgabe.splitlines()[:6]:
                print("     " + zeile)

        # Katalog-Hash: im Klon veraendern, pruefen, zuruecksetzen.
        (klon / KATALOG).write_text(
            (klon / KATALOG).read_text(encoding="utf-8") + "\nEICHFALL\n",
            encoding="utf-8",
            newline="\n",
        )
        lauf = subprocess.run(
            [sys.executable, "tools/katalog_hash.py", "--pruefen"],
            cwd=klon,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        ok = lauf.returncode == 1
        fehler += 0 if ok else 1
        marke = "OK " if ok else "!! "
        print(
            f"\n{marke} katalog_hash --pruefen nach Aenderung: "
            f"exit={lauf.returncode} (erwartet 1)"
        )
        for zeile in lauf.stdout.strip().splitlines()[:4]:
            print("     " + zeile)
        git(klon, "reset", "-q", "--hard")
        lauf = subprocess.run(
            [sys.executable, "tools/katalog_hash.py", "--pruefen"],
            cwd=klon,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        ok = lauf.returncode == 0
        fehler += 0 if ok else 1
        marke = "OK " if ok else "!! "
        print(
            f"{marke} katalog_hash --pruefen unveraendert: "
            f"exit={lauf.returncode} (erwartet 0): {lauf.stdout.strip()}"
        )

    print(f"\nEichfall: {fehler} Abweichungen von der Erwartung")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

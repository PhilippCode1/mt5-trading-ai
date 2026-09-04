#!/usr/bin/env python3
"""Eichfaelle der Familie Zustand und Halt (D1, D4/D5/D6, D7, D8, Z) -- rot und gruen.

Je Befund eine Testdatei ``tests/eichfall_<befund>.py``:

  [rot]   Die Datei wird in den Referenz-Worktree (Stand 306bbaa) kopiert, dort mit
          ``pytest`` gefahren und wieder entfernt; ``git status --porcelain`` des
          Worktrees steht danach im Beleg (muss leer sein). Kein Unterprozess kann
          das Terminal starten: die Faelle, die ``tools/live_betrieb.py`` fahren,
          setzen ein ``MetaTrader5``-Shim, das ``ImportError`` wirft.
  [gruen] Dieselbe Datei im Arbeitsbaum (dieser Patch).

Ausgabe: ``06-<befund>-rot.txt`` und ``06-<befund>-gruen.txt`` im Ausgabeordner;
Pfade werden redigiert (``C:\\Users\\<konto>``).

Aufruf im Worktree:
    python PROGRAMM/auftrag-01-fundament/belege/06-zustand-eichfall.py \
        --referenz C:/Users/<konto>/nachstellung-306bbaa --ausgabe PROGRAMM/auftrag-01-fundament/belege
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[2] if HIER.name == "belege" else Path.cwd()
KONTO = str(Path.home())

BEFUNDE = {
    "d1": "eichfall_d1.py",
    "d4-d5-d6": "eichfall_d4_d5_d6.py",
    "d7": "eichfall_d7.py",
    "d8": "eichfall_d8.py",
    "z": "eichfall_z.py",
}


def redigiere(text: str) -> str:
    return (
        text.replace(KONTO, r"C:\Users\<konto>")
        .replace(KONTO.replace("\\", "/"), "C:/Users/<konto>")
        .replace(KONTO.replace("\\", "\\\\"), r"C:\\Users\\<konto>")
    )


def umgebung() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def pytest_lauf(wurzel: Path, datei: str) -> tuple[int, str, float]:
    start = time.monotonic()
    lauf = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=line",
            f"tests/{datei}",
        ],
        cwd=str(wurzel),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=umgebung(),
        timeout=900,
    )
    return lauf.returncode, lauf.stdout + lauf.stderr, time.monotonic() - start


def git_status(wurzel: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(wurzel),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--referenz", type=Path, required=True, help="Worktree 306bbaa")
    ap.add_argument("--ausgabe", type=Path, required=True)
    ap.add_argument("--nur", choices=("rot", "gruen"), default=None)
    args = ap.parse_args()
    args.ausgabe.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    for kurz, datei in BEFUNDE.items():
        quelle = REPO / "tests" / datei
        if args.nur in (None, "rot"):
            ziel = args.referenz / "tests" / datei
            shutil.copyfile(quelle, ziel)
            try:
                exit_code, text, dauer = pytest_lauf(args.referenz, datei)
            finally:
                ziel.unlink(missing_ok=True)
            status = git_status(args.referenz)
            kopf = (
                f"# Eichfall {kurz.upper()}, ROT gegen 306bbaa (Worktree "
                f"{redigiere(str(args.referenz))}, {stempel}): tests/{datei} dort "
                f"hineinkopiert, ausgefuehrt, entfernt\n"
                f"$ python -m pytest -q -p no:cacheprovider --tb=line tests/{datei}\n"
            )
            fuss = (
                f"[exit={exit_code}, {dauer:.1f} s]\n"
                f"$ git status --porcelain   (im Referenz-Worktree, danach)\n"
                f"{status or '(sauber)'}\n"
            )
            (args.ausgabe / f"06-{kurz}-rot.txt").write_text(
                kopf + redigiere(text) + fuss, encoding="utf-8", newline="\n"
            )
            print(f"rot   {kurz:9s} exit={exit_code} {dauer:6.1f} s  status={'sauber' if not status else status}")
        if args.nur in (None, "gruen"):
            exit_code, text, dauer = pytest_lauf(REPO, datei)
            kopf = (
                f"# Eichfall {kurz.upper()}, GRUEN gegen den Arbeitsbaum ({stempel})\n"
                f"$ python -m pytest -q -p no:cacheprovider --tb=line tests/{datei}\n"
            )
            (args.ausgabe / f"06-{kurz}-gruen.txt").write_text(
                kopf + redigiere(text) + f"[exit={exit_code}, {dauer:.1f} s]\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"gruen {kurz:9s} exit={exit_code} {dauer:6.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

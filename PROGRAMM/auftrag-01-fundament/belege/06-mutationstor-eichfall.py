"""Eichfall des Mutationstors: schreibt das Tor in den Arbeitsbaum? (A18, F-005, T(d))

Misst in einem Worktree vor und nach EINER Sonde des Mutationstors:
  * jede Quelldatei unter mt5_trading_ai/ und tools/ (Groesse, mtime in ns) -- genau der
    Massstab des Waechters A10 in tests/conftest.py,
  * jede .pyc unter mt5_trading_ai/ und tools/ (Bytecode-Vergiftung: Befund T(d)),
  * ``git status --porcelain`` (identisch vorher/nachher?).

Rot (306bbaa, ``python tools/mutationstor.py --sonde 13`` = stop-kostenboden): das alte Tor
schreibt den Mutanten in den Arbeitsbaum und stellt ihn aus dem Speicher zurueck -- die
Datei ist danach byteidentisch, aber neu geschrieben (mtime), und der Testlauf hat Bytecode
des Mutanten in __pycache__ hinterlassen. Gruen (HEAD, ``--sonde 10 --kopie <tmp>``): keine
Datei, keine .pyc, git status identisch.

Beide Laeufe OHNE ``PYTHONDONTWRITEBYTECODE`` in der Umgebung: so faehrt ein Entwickler oder
ein Hook das Tor; das neue Tor setzt die Variable selbst fuer die Kopie.

Aufruf: python 06-mutationstor-eichfall.py WORKTREE -- BEFEHL ...   (BEFEHL mit cwd=WORKTREE)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

Stand = dict[str, tuple[int, int]]


def _redigiert(text: str) -> str:
    heim = str(Path.home())
    return text.replace(heim, "C:\\Users\\<konto>").replace(
        heim.replace("\\", "/"), "C:/Users/<konto>"
    )


def _stand(wurzel: Path, endungen: tuple[str, ...]) -> Stand:
    aus: Stand = {}
    for start in ("mt5_trading_ai", "tools"):
        for p in (wurzel / start).rglob("*"):
            if p.is_file() and p.suffix in endungen:
                st = p.stat()
                aus[p.relative_to(wurzel).as_posix()] = (st.st_size, st.st_mtime_ns)
    return aus


def _abweichungen(vorher: Stand, nachher: Stand) -> list[str]:
    zeilen = [f"neu: {p}" for p in sorted(nachher.keys() - vorher.keys())]
    zeilen += [f"entfernt: {p}" for p in sorted(vorher.keys() - nachher.keys())]
    zeilen += [
        f"geschrieben: {p} (Groesse {vorher[p][0]} -> {nachher[p][0]}, "
        f"mtime +{(nachher[p][1] - vorher[p][1]) / 1e9:.1f} s)"
        for p in sorted(vorher.keys() & nachher.keys())
        if vorher[p] != nachher[p]
    ]
    return zeilen


def _git_status(wurzel: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=wurzel,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def main() -> int:
    wurzel = Path(sys.argv[1]).resolve()
    assert sys.argv[2] == "--"
    befehl = sys.argv[3:]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
    env["PYTHONIOENCODING"] = "utf-8"

    print(f"Worktree: {_redigiert(str(wurzel))}")
    print(f"Befehl (cwd=Worktree, ohne PYTHONDONTWRITEBYTECODE): {_redigiert(' '.join(befehl))}")
    status_vorher = _git_status(wurzel)
    quellen_vorher = _stand(wurzel, (".py",))
    pyc_vorher = _stand(wurzel, (".pyc",))
    print(
        f"vorher: {len(quellen_vorher)} Quelldateien, {len(pyc_vorher)} .pyc unter "
        "mt5_trading_ai/ und tools/; git status --porcelain: "
        f"{len(status_vorher.splitlines())} Zeilen"
    )
    start = time.perf_counter()
    lauf = subprocess.run(
        befehl,
        cwd=wurzel,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    dauer = time.perf_counter() - start
    print(f"--- Ausgabe des Tors (exit={lauf.returncode}, {dauer:.0f} s) ---")
    ausgabe = (lauf.stdout or "") + (lauf.stderr or "")
    print(_redigiert(ausgabe.rstrip()))
    print("--- Messung nachher ---")
    status_nachher = _git_status(wurzel)
    quellen = _abweichungen(quellen_vorher, _stand(wurzel, (".py",)))
    pyc = _abweichungen(pyc_vorher, _stand(wurzel, (".pyc",)))
    print(f"git status identisch: {'ja' if status_nachher == status_vorher else 'NEIN'}")
    print(f"Quelldateien geschrieben (Massstab A10): {len(quellen)}")
    for z in quellen:
        print(f"    {z}")
    print(f".pyc neu oder geschrieben: {len(pyc)}")
    for z in pyc:
        print(f"    {z}")
    rot = bool(quellen or pyc) or status_nachher != status_vorher
    print(
        "URTEIL: "
        + (
            "ROT -- das Tor hat den Arbeitsbaum angefasst."
            if rot
            else "GRUEN -- Arbeitsbaum unveraendert, kein neuer Bytecode."
        )
    )
    return 1 if rot else 0


if __name__ == "__main__":
    raise SystemExit(main())

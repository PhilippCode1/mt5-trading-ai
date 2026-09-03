"""Deterministische Nachstellung der Bytecode-Vergiftung (T d), Worktree 306bbaa.

Das Mutationstor schreibt einen Mutanten gleicher Groesse, faehrt pytest (compiliert den
Mutanten in __pycache__) und stellt die Quelle byteweise zurueck. Liegen Mutation und
Rueckstellung in derselben Sekunde, tragen Quelle und .pyc dieselbe mtime und Groesse,
und Python haelt den Mutanten-Bytecode fuer gueltig. Hier wird "dieselbe Sekunde" mit
os.utime erzwungen, damit die Mechanik nicht vom Zufall der Uhr abhaengt.

Aufruf: python pycache_mechanik.py <worktree>
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
quelle = repo / "mt5_trading_ai" / "risk" / "stop_budget.py"
probe = [sys.executable, "-c",
         "from decimal import Decimal; from mt5_trading_ai.risk.stop_budget import cost_floor_bps; print(cost_floor_bps(Decimal('0.65')))"]
env = dict(os.environ); env.pop("PYTHONDONTWRITEBYTECODE", None); env["PYTHONPATH"] = str(repo)

def lauf() -> str:
    return subprocess.run(probe, cwd=repo, capture_output=True, text=True, env=env).stdout.strip()

original = quelle.read_bytes()
anker = b"return cost_bps / (2 * max_cost_drag)"
assert original.count(anker) == 1, "Anker der Sonde 'stop-kostenboden' nicht gefunden"
for pyc in (quelle.parent / "__pycache__").glob("stop_budget.*.pyc"):
    pyc.unlink()
print("1) Quelle unveraendert, frischer Cache:  cost_floor_bps(0.65) =", lauf(), "(Soll 6.5)")
mutant = original.replace(anker, b"return cost_bps / (4 * max_cost_drag)")
assert len(mutant) == len(original)
quelle.write_bytes(mutant)
st = quelle.stat()
print("2) Mutant geschrieben (gleiche Groesse), pytest-aehnlicher Lauf compiliert ihn:", lauf(), "(Mutant: 3.25)")
quelle.write_bytes(original)
os.utime(quelle, (st.st_atime, st.st_mtime))  # Rueckstellung "in derselben Sekunde"
print("3) Quelle byteweise zurueckgestellt, mtime wie der Mutant:")
print("   git status:", subprocess.run(["git", "status", "--short", str(quelle)], cwd=repo, capture_output=True, text=True).stdout.strip() or "(sauber)")
print("   cost_floor_bps(0.65) mit vorhandenem Cache =", lauf(), "<- VERGIFTET, wenn 3.25")
env2 = dict(env); env2["PYTHONDONTWRITEBYTECODE"] = "1"
print("   dasselbe mit PYTHONPYCACHEPREFIX auf leerem Ordner =", subprocess.run(probe, cwd=repo, capture_output=True, text=True, env={**env, "PYTHONPYCACHEPREFIX": str(repo / ".leer")}).stdout.strip(), "(Soll 6.5)")
for pyc in (quelle.parent / "__pycache__").glob("stop_budget.*.pyc"):
    pyc.unlink()
print("4) Cache geloescht, erneut:", lauf(), "(Soll 6.5)")

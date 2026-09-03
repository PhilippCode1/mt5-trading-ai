"""Nachstellung T (Bytecode-Vergiftung durch das Mutationstor), Stand 306bbaa im Worktree.

Eigenes Skript nach der Methode der Bewertung (03b): fuer jede .pyc unter
mt5_trading_ai/ und tools/ den Kopf (Quell-mtime, Quellgroesse) mit der Quelle
vergleichen; gilt der Cache als gueltig, wird der Code-Objekt-Inhalt gegen einen
frischen Compile der Quelle gehalten. Weicht er ab, traegt die .pyc Mutanten-Bytecode.

Aufruf: python pycache_pruefung.py <repo>   (nach einem Lauf von tools/mutationstor.py
mit eingeschaltetem Bytecode-Schreiben)
"""

from __future__ import annotations

import importlib.util
import marshal
import struct
import sys
from pathlib import Path


def pruefe(repo: Path) -> int:
    vergiftet: list[str] = []
    geprueft = 0
    for pyc in sorted(list(repo.glob("mt5_trading_ai/**/__pycache__/*.pyc")) + list(repo.glob("tools/__pycache__/*.pyc"))):
        name = pyc.name.split(".")[0] + ".py"
        quelle = pyc.parent.parent / name
        if not quelle.is_file():
            continue
        roh = pyc.read_bytes()
        if roh[:4] != importlib.util.MAGIC_NUMBER:
            continue
        flags = struct.unpack("<I", roh[4:8])[0]
        if flags != 0:
            continue  # hash-basiert, hier nicht der Fall
        pyc_mtime, pyc_size = struct.unpack("<II", roh[8:16])
        st = quelle.stat()
        gueltig = pyc_mtime == int(st.st_mtime) & 0xFFFFFFFF and pyc_size == st.st_size & 0xFFFFFFFF
        if not gueltig:
            continue
        geprueft += 1
        try:
            im_cache = marshal.loads(roh[16:])
        except Exception:
            continue
        frisch = compile(quelle.read_bytes(), str(quelle), "exec")
        if marshal.dumps(im_cache) != marshal.dumps(frisch):
            vergiftet.append(pyc.relative_to(repo).as_posix())
    print(f"gueltige .pyc-Dateien geprueft: {geprueft}")
    print(f"davon mit Bytecode, der NICHT der Quelle entspricht: {len(vergiftet)}")
    for v in vergiftet:
        print("   VERGIFTET", v)
    return 0


if __name__ == "__main__":
    sys.exit(pruefe(Path(sys.argv[1]).resolve()))

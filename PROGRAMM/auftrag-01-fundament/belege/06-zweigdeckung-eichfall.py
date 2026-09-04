"""Eichfall des Zweigdeckungstors: der Windows-Fehlerpfad (A12-Form: kein Traceback).

Baut ein Wegwerf-Repo mit einem Mini-Paket ``mt5_trading_ai/kern.py`` und einem
absichtlich roten Test, der ein Byte 0x81 (``Ł`` in utf-8) auf stdout schreibt -- der
Fall der Grundmessung (Beleg ``03-grundmessung-mutation-pycache-worktree.txt``).

Rot: ``tools/zweigdeckung.py`` des Stands 306bbaa (Datei aus dem Referenz-Worktree kopiert)
mit ``--messen``: der Leser-Thread stirbt an ``UnicodeDecodeError`` (cp1252), ``stdout``
bleibt ``None``, ``TypeError``-Traceback, kein Urteil.
Gruen: die Fassung des Arbeitsbaums: Kopie, exit 1, der rote Fall beim Namen, die Deckung
von ``kern.py`` im Bericht, jede Geldpfad-Datei als "fehlt in der Messung" -- kein Traceback.

Beide Laeufe mit ``PYTHONIOENCODING=utf-8`` in der Umgebung (CLAUDE.md, Windows-Eigenheit 7):
das Kind schreibt utf-8, und genau daran scheiterte der alte Leser.

Aufruf: python 06-zweigdeckung-eichfall.py ALT_ZWEIGDECKUNG_PY NEU_ZWEIGDECKUNG_PY TEMPORDNER
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def _redigiert(text: str) -> str:
    heim = str(Path.home())
    return text.replace(heim, "C:\\Users\\<konto>").replace(
        heim.replace("\\", "/"), "C:/Users/<konto>"
    )


def _schreibbar(funktion, pfad, _exc) -> None:  # type: ignore[no-untyped-def]
    os.chmod(pfad, stat.S_IWRITE)
    funktion(pfad)


def _repo_bauen(x: Path) -> None:
    if x.exists():
        shutil.rmtree(x, onerror=_schreibbar)
    (x / "tests").mkdir(parents=True)
    (x / "tools").mkdir()
    (x / "mt5_trading_ai").mkdir()
    (x / "mt5_trading_ai" / "__init__.py").write_text("", encoding="utf-8")
    (x / "mt5_trading_ai" / "kern.py").write_text(
        "def sperrt(x: int) -> bool:\n    if x < 0:\n        return True\n    return False\n",
        encoding="utf-8",
    )
    (x / "tests" / "test_rot_eichfall.py").write_text(
        "import sys\n\nfrom mt5_trading_ai.kern import sperrt\n\n\n"
        "def test_rot() -> None:\n"
        '    sys.stdout.buffer.write("Zweig \\u0141 Ziel\\n".encode("utf-8"))\n'
        "    sys.stdout.buffer.flush()\n"
        '    assert False, "absichtlich rot"\n\n\n'
        "def test_gruen() -> None:\n    assert sperrt(-1) and not sperrt(1)\n",
        encoding="utf-8",
    )
    (x / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
        'markers = ["slow: Marke"]\n',
        encoding="utf-8",
    )
    git = ["git", "-c", "user.name=eichfall", "-c", "user.email=eichfall@lokal"]
    for befehl in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--no-verify", "-m", "x"]):
        subprocess.run([*git, *befehl], cwd=x, check=True, capture_output=True)


def _lauf(x: Path, werkzeug: Path, *argumente: str) -> None:
    shutil.copyfile(werkzeug, x / "tools" / "zweigdeckung.py")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    lauf = subprocess.run(
        [sys.executable, "-B", "tools/zweigdeckung.py", "--messen", *argumente],
        cwd=x,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    ausgabe = (lauf.stdout or "") + (lauf.stderr or "")
    print(_redigiert(ausgabe.rstrip()))
    print(f"[exit={lauf.returncode}]")
    print(f"Traceback in der Ausgabe: {'JA' if 'Traceback' in ausgabe else 'nein'}")
    print(
        "roter Fall beim Namen: "
        + ("ja" if "test_rot_eichfall.py::test_rot" in ausgabe else "NEIN")
    )


def main() -> int:
    alt, neu, temp = (Path(a).resolve() for a in sys.argv[1:4])
    x = temp / "eichfall-repo"
    _repo_bauen(x)
    print("=== ROT: tools/zweigdeckung.py aus 306bbaa (Referenz-Worktree), --messen ===")
    print("$ python -B tools/zweigdeckung.py --messen --bericht alt.json")
    _lauf(x, alt, "--bericht", str(x / "alt.json"))
    print()
    print("=== GRUEN: tools/zweigdeckung.py des Arbeitsbaums, --messen in der Kopie ===")
    print("$ python -B tools/zweigdeckung.py --messen --bericht neu.json --kopie <temp>/kopie")
    _lauf(x, neu, "--bericht", str(x / "neu.json"), "--kopie", str(temp / "kopie"))
    shutil.rmtree(temp / "kopie", onerror=_schreibbar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

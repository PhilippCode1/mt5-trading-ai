"""Eichfaelle des Mutationstors (Katalog A4, A17, A18; F-005; Entscheidung E-006).

Ein Waechter ohne Ausloesenachweis ist eine Behauptung (Regel 6 des Rahmens). Darum:

* **rot** -- eine absichtlich unwirksame Sonde (ihr Anker steht im Docstring, der
  Mutant aendert kein Verhalten) wird als ``UEBERLEBT`` erkannt und faerbt das Tor rot.
  Ein Tor, das diese Sonde "getoetet" meldete, wuerde jede Sonde "toeten".
* **gruen** -- der handverlesene Katalog wird in der Kopie vollstaendig getoetet
  (13/13, Toetungsrate 1,000).
* **Arbeitsbaum unveraendert** -- vor und nach jedem Lauf ist ``git status --porcelain``
  identisch, und unter ``mt5_trading_ai/`` und ``tools/`` liegt keine ``.pyc``, die
  neuer ist als vor dem Lauf. Das ist der Befund T(d) der Bewertung (Bytecode-
  Vergiftung) und F-005 (Mutant im Arbeitsbaum), als Dauertor.

Die Kopie liegt unter ``tmp_path`` (A10: kein Test schreibt ausserhalb). Die Kopie ist
der Arbeitsbaum ohne Ignoriertes (auch diese, noch unverfolgte Datei waere darin) --
gefahren wird darin ohne diese Datei (``--ignore``), sonst liefe das Tor im Tor.

Der rote Eichfall gegen 306bbaa liegt als Messung daneben, weil das alte Werkzeug diese
Datei gar nicht importieren kann (kein ``tor``): ``belege/06-mutationstor-eichfall.py``
misst vor und nach EINER Sonde jede Quelldatei und jede ``.pyc`` unter
``mt5_trading_ai/`` und ``tools/`` mit (Groesse, mtime_ns) -- dem Massstab von A10 --
und ``git status``. Bei 306bbaa: Sondendatei neu geschrieben, 6 ``.pyc`` mit dem
Mutantenlauf (``06-mutationstor-eichfall-rot.txt``); hier: nichts
(``06-mutationstor-eichfall-gruen.txt``).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from tools.mutationstor import KATALOG, Sonde, tor

ROOT = Path(__file__).resolve().parents[1]


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _bytecode_stand() -> dict[str, float]:
    """Jede ``.pyc`` unter mt5_trading_ai/ und tools/ mit ihrer Aenderungszeit."""
    aus: dict[str, float] = {}
    for start in ("mt5_trading_ai", "tools"):
        for p in (ROOT / start).rglob("*.pyc"):
            aus[p.relative_to(ROOT).as_posix()] = p.stat().st_mtime
    return aus


def _neuer_bytecode(vorher: dict[str, float], nachher: dict[str, float]) -> list[str]:
    return sorted(
        pfad
        for pfad, zeit in nachher.items()
        if pfad not in vorher or zeit > vorher[pfad]
    )


def _unwirksame_sonde() -> Sonde:
    """Anker im Modul-Docstring von ``risk/stop_budget.py``: ein Mutant ohne Wirkung."""
    datei = "mt5_trading_ai/risk/stop_budget.py"
    quelle = (ROOT / datei).read_text(encoding="utf-8")
    docstring = ast.get_docstring(ast.parse(quelle)) or ""
    anker = "hergeleitet, nicht uebertragen"
    assert anker in docstring, "Der Anker des Eichfalls steht nicht mehr im Docstring."
    assert quelle.count(anker) == 1, "Der Anker muss eindeutig sein."
    return Sonde(
        name="eichfall-docstring",
        datei=datei,
        alt=anker,
        neu="hergeleitet, nicht abgeschrieben",
        tests=("tests/test_stop_budget.py",),
        bedeutet="Ein Wort im Docstring -- kein Verhalten aendert sich.",
    )


def test_rot_eine_unwirksame_sonde_ueberlebt_und_faerbt_das_tor_rot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status_vorher = _git_status()
    bytecode_vorher = _bytecode_stand()
    kopie_basis = tmp_path / "kopie"

    urteil = tor(
        [_unwirksame_sonde()],
        kopie_basis=kopie_basis,
        behalten=True,
        vollstaendig=False,
    )

    aus = capsys.readouterr()
    assert urteil.rc == 1, aus.out + aus.err
    (ergebnis,) = urteil.ergebnisse
    assert ergebnis.getoetet is False
    assert ergebnis.anmerkung.startswith("UEBERLEBT"), ergebnis.anmerkung
    assert "UEBERLEBT" in aus.out
    assert "eichfall-docstring" in aus.out
    assert "FEHLGESCHLAGEN" in aus.err
    # Die Sonde hat ihren Gegenstand gefunden -- sonst waere das kein Ueberleben,
    # sondern ein fehlender Anker (der ebenfalls rot ist, aber ein anderer Fall).
    assert "ANKER FEHLT" not in aus.out

    # Die Kopie: ein eigenes Repo ohne Laufzeitzustand, die Sondendatei zurueckgestellt.
    kopie = kopie_basis / "kopie-0"
    assert (kopie / ".git").is_dir()
    assert not (kopie / "betrieb").exists()
    assert list(kopie.rglob("*.pyc")) == []
    original = (ROOT / "mt5_trading_ai/risk/stop_budget.py").read_bytes()
    assert (kopie / "mt5_trading_ai/risk/stop_budget.py").read_bytes() == original

    # Der Arbeitsbaum: unveraendert, kein neuer Bytecode.
    assert _git_status() == status_vorher
    assert _neuer_bytecode(bytecode_vorher, _bytecode_stand()) == []


def test_rot_eine_sonde_ohne_anker_zaehlt_nicht_als_getoetet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein Anker, den es nicht gibt, mutiert nichts -- und darf nicht gruen zaehlen."""
    sonde = Sonde(
        name="eichfall-ohne-anker",
        datei="mt5_trading_ai/risk/stop_budget.py",
        alt="diesen Text gibt es in der Datei nicht",
        neu="",
        tests=("tests/test_stop_budget.py",),
        bedeutet="Nichts -- die Sonde trifft nichts.",
    )
    urteil = tor([sonde], kopie_basis=tmp_path / "kopie", vollstaendig=False)
    aus = capsys.readouterr()
    assert urteil.rc == 1
    assert "ANKER FEHLT" in aus.out
    assert not (tmp_path / "kopie" / "kopie-0").exists(), "Kopie nicht entfernt"


@pytest.mark.slow
def test_gruen_der_katalog_wird_in_der_kopie_vollstaendig_getoetet(
    tmp_path: Path,
) -> None:
    """Der gruene Eichfall: 13/13 -- und der Arbeitsbaum bleibt, wie er war."""
    status_vorher = _git_status()
    bytecode_vorher = _bytecode_stand()

    lauf = subprocess.run(
        [
            sys.executable,
            "-B",
            "tools/mutationstor.py",
            "--katalog",
            "--kopie",
            str(tmp_path / "kopie"),
        ],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    n = len(KATALOG)
    assert f"Katalog:  {n}/{n} getoetet, Toetungsrate: 1.000" in lauf.stdout, (
        lauf.stdout
    )
    assert "UEBERLEBT" not in lauf.stdout
    assert str(tmp_path / "kopie") in lauf.stdout, "Der Lauf nennt die Kopie nicht."

    assert _git_status() == status_vorher
    assert _neuer_bytecode(bytecode_vorher, _bytecode_stand()) == []

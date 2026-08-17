"""Blockierender Test: die Kennzahlen der Doku muessen dem Code entsprechen.

Der Altbestand behauptete im README Zahlen, die der Code nicht hergab ("17 Dienste"
wo 15 waren, "alle 908 Parameter" wo die Datei 880 sagte). Dieser Test macht das
unmoeglich: er rechnet die Zahlen aus dem Code nach und vergleicht sie mit dem, was
im README steht. Weicht eine ab, ist der Test rot.

AUSWEITUNG (Paket 2, A4.1)
--------------------------
Der Test deckte lange **nur** ``README.md`` ab. Das reichte fuer den README-Block und
fuer nichts sonst: ``MASTERBERICHT.md`` fuehrte eine eigene Spalte mit Zeilenzahlen je
Modul, von der 13 von 18 Werten falsch waren, und kein Test bemerkte es. Der Grund war
nicht Nachlaessigkeit, sondern Struktur -- eine Zahl, die an zwei Stellen von Hand steht,
geht an einer davon irgendwann falsch.

Dieser Test spannt darum jetzt drei Dateien unter denselben Waechter:
``README.md``, ``MASTERBERICHT.md`` und ``FEHLT.md``. Er ruft dafuer die Regeln von
``tools/check_doc_numbers.py`` direkt auf, statt sie nachzubauen -- eine zweite Kopie
derselben Regeln waere genau der Fehler, den beide verhindern sollen.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "mt5_trading_ai"
TESTS = ROOT / "tests"
README = ROOT / "README.md"

#: Die Live-Dokumente, die unter dem Waechter stehen. ``PROGRESS.md`` und ``docs/audit/``
#: fehlen hier bewusst: sie sind anhaengende Logbuecher bzw. datierte Snapshots, deren
#: Zahlen Zeitpunkt-Belege sind (siehe ``tools/check_doc_numbers.py``, A4.2).
BEWACHTE_DOKUMENTE = ("README.md", "MASTERBERICHT.md", "FEHLT.md")


def _lade_tor() -> Any:
    """Lade ``tools/check_doc_numbers.py`` als Modul (es ist kein Paket)."""
    pfad = ROOT / "tools" / "check_doc_numbers.py"
    assert pfad.is_file(), f"Zahlen-Tor nicht gefunden: {pfad}"
    spec = importlib.util.spec_from_file_location("check_doc_numbers", pfad)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_numbers"] = modul
    spec.loader.exec_module(modul)
    return modul


def _declared() -> dict[str, int]:
    text = README.read_text(encoding="utf-8")
    block = re.search(r"KENNZAHLEN-ANFANG(.*?)KENNZAHLEN-ENDE", text, re.S)
    assert block is not None, "Kennzahlen-Block fehlt im README"
    return {
        key: int(value)
        for key, value in re.findall(r"-\s*(\w+):\s*(\d+)", block.group(1))
    }


def _module_count() -> int:
    return len([p for p in PKG.rglob("*.py") if p.name != "__init__.py"])


def _test_function_count() -> int:
    total = 0
    for path in TESTS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                total += 1
    return total


def _source_lines() -> int:
    return sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in PKG.rglob("*.py")
    )


# --- Der README-Block: die eine Quelle der Live-Kennzahlen ----------------
def test_readme_module_count_matches_code() -> None:
    assert _declared()["module_count"] == _module_count()


def test_readme_test_function_count_matches_code() -> None:
    assert _declared()["test_function_count"] == _test_function_count()


def test_readme_source_lines_matches_code() -> None:
    assert _declared()["source_lines"] == _source_lines()


# --- Die Ausweitung: drei Dokumente unter demselben Waechter --------------
@pytest.mark.parametrize("name", BEWACHTE_DOKUMENTE)
def test_bewachtes_dokument_existiert(name: str) -> None:
    """Laut scheitern, wenn der Waechter seinen Gegenstand nicht findet."""
    assert (ROOT / name).is_file(), (
        f"{name} fehlt. Ein Waechter, der nichts findet und deshalb gruen ist, "
        "ist der Fehler selbst."
    )


@pytest.mark.parametrize("name", BEWACHTE_DOKUMENTE)
def test_bewachtes_dokument_hat_keine_zahlen_drift(name: str) -> None:
    """Kein Live-Dokument wiederholt eine Kennzahl und keines fuehrt Zeilenzahlen."""
    tor = _lade_tor()
    probleme = tor.check_live_doc(ROOT / name)
    assert not probleme, "\n".join(probleme)


@pytest.mark.parametrize("name", BEWACHTE_DOKUMENTE)
def test_bewachtes_dokument_ist_nicht_von_der_pruefung_ausgenommen(name: str) -> None:
    """Die historische Ausnahme darf keines dieser drei Dokumente erfassen."""
    tor = _lade_tor()
    assert not tor.is_historical(name), (
        f"{name} faellt unter die HISTORICAL-Ausnahme und waere damit ungeprueft."
    )


def test_zeilenzahl_je_modul_lebt_nur_in_modules_md() -> None:
    """Regel 5: die Zahl wird an einer Stelle erzeugt, nicht an mehreren gepflegt."""
    tor = _lade_tor()
    assert tor.LINE_COUNT_OWNER == "MODULES.md"
    modules = ROOT / "MODULES.md"
    assert modules.is_file()
    text = modules.read_text(encoding="utf-8")
    # Stichprobe: ein reales Modul und seine echte Zeilenzahl stehen dort.
    ziel = PKG / "venue" / "mt5.py"
    zeilen = len(ziel.read_text(encoding="utf-8").splitlines())
    assert f"Zeilen: {zeilen}" in text, (
        f"MODULES.md fuehrt fuer venue/mt5.py nicht die gemessenen {zeilen} Zeilen. "
        "`python tools/gen_docs.py` ausfuehren."
    )


def test_das_zahlen_tor_faengt_eine_erfundene_zeilenzahl(tmp_path: Path) -> None:
    """Roter Eichfall fuer Regel 5 -- ohne ihn waere die Regel ungeprueft."""
    tor = _lade_tor()
    kaputt = ROOT / "PRUEFDATEI_NICHT_COMMITTEN.md"
    kaputt.write_text(
        "| Modul | Zeilen | Aufgabe |\n"
        "| --- | --- | --- |\n"
        "| `venue/mt5.py` | 818 | irgendwas |\n",
        encoding="utf-8",
    )
    try:
        probleme = tor.check_live_doc(kaputt)
        assert probleme, "Regel 5 hat eine erfundene Zeilenzahl durchgelassen"
        assert "venue/mt5.py" in probleme[0]
    finally:
        kaputt.unlink()

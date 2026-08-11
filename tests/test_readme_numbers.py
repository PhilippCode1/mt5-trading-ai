"""Blockierender Test: die Kennzahlen im README muessen dem Code entsprechen.

Der Altbestand behauptete im README Zahlen, die der Code nicht hergab ("17 Dienste"
wo 15 waren, "alle 908 Parameter" wo die Datei 880 sagte). Dieser Test macht das
unmoeglich: er rechnet die Zahlen aus dem Code nach und vergleicht sie mit dem, was
im README steht. Weicht eine ab, ist der Test rot.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "mt5_trading_ai"
TESTS = ROOT / "tests"
README = ROOT / "README.md"


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


def test_readme_module_count_matches_code() -> None:
    assert _declared()["module_count"] == _module_count()


def test_readme_test_function_count_matches_code() -> None:
    assert _declared()["test_function_count"] == _test_function_count()


def test_readme_source_lines_matches_code() -> None:
    assert _declared()["source_lines"] == _source_lines()

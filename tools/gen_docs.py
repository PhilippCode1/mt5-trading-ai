#!/usr/bin/env python3
"""Erzeugt MODULES.md AUS DEM CODE des Pakets ``mt5_trading_ai``.

Warum generiert statt geschrieben: eine handgeschriebene Modeluebersicht veraltet
lautlos. Generierung plus das Gate ``--check`` haelt die Uebersicht ehrlich -- wer
ein Modul aendert oder hinzufuegt, ohne MODULES.md neu zu erzeugen, faellt im Gate
auf. (Der alte ``gen_docs.py`` erzeugte Service- und Konfigurationsdoku aus einem
Service-Manifest und den Settings-Klassen; beides gibt es im neuen Kern nicht, ein
woertlicher Umzug waere ins Leere gelaufen. Der Zweck -- Doku aus Code plus Gate --
ist erhalten, der Umfang auf das neue Paket umgestellt.)

Aufruf:
  python tools/gen_docs.py            schreibt MODULES.md
  python tools/gen_docs.py --check    vergleicht, Exit 1 bei Abweichung
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "mt5_trading_ai"
OUT = REPO / "MODULES.md"
BANNER = "<!-- GENERIERT von tools/gen_docs.py — nicht von Hand bearbeiten -->"


def _module_summary(tree: ast.Module) -> str:
    doc = ast.get_docstring(tree)
    if not doc:
        return "(kein Docstring)"
    return doc.strip().splitlines()[0]


def _public_api(tree: ast.Module) -> list[str]:
    api: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            api.append(f"class {node.name}")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not (
            node.name.startswith("_")
        ):
            api.append(f"def {node.name}")
    return api


def render() -> str:
    out: list[str] = [
        BANNER,
        "",
        "# MODULES — oeffentliche API je Modul (generiert aus dem Code)",
        "",
        "Diese Datei ist die **einzige** Stelle, an der die Zeilenzahl je Modul steht.",
        "Sie wird erzeugt, nicht gepflegt. Andere Dokumente verweisen hierher; das",
        "Zahlen-Tor (`tools/check_doc_numbers.py`) blockt eine Wiederholung, weil eine",
        "von Hand gefuehrte Zeilenzahl mit dem naechsten Commit driftet.",
        "",
    ]
    for path in sorted(PKG.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        rel = path.relative_to(REPO).as_posix()
        out.append(f"## `{rel}`")
        out.append("")
        out.append(f"Zeilen: {len(text.splitlines())}")
        out.append("")
        out.append(_module_summary(tree))
        out.append("")
        api = _public_api(tree)
        if api:
            out.extend(f"- `{item}`" for item in api)
        else:
            out.append("- (keine oeffentliche API)")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="MODULES.md aus dem Code erzeugen.")
    parser.add_argument(
        "--check", action="store_true", help="nur pruefen, nicht schreiben"
    )
    args = parser.parse_args()
    generated = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != generated:
            print(
                "FEHLGESCHLAGEN — MODULES.md ist veraltet. "
                "`python tools/gen_docs.py` ausfuehren."
            )
            return 1
        print(f"ok — MODULES.md ist aktuell ({len(generated.splitlines())} Zeilen).")
        return 0
    OUT.write_text(generated, encoding="utf-8")
    print(f"MODULES.md geschrieben ({len(generated.splitlines())} Zeilen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

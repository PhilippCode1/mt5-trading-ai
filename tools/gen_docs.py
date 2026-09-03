#!/usr/bin/env python3
"""Erzeugt MODULES.md und den README-Kennzahlenblock AUS DEM CODE des Pakets.

MODULES.md ist das Architekturdokument (Abnahmekatalog A8): je Modul Zeilen, erste
Docstring-Zeile, oeffentliche API und die Aufrufer -- gezaehlt als Importzeilen aus
dem Paket, den Werkzeugen und den Tests. Ein Modul mit 0 Aufrufern ausserhalb der
Tests hat keinen nachgewiesenen Aufrufpfad (Regel 5 des Rahmens). Der
KENNZAHLEN-Block in README.md wird hier geschrieben, nicht gepflegt.

Warum generiert statt geschrieben: eine handgeschriebene Modeluebersicht veraltet
lautlos. Generierung plus das Gate ``--check`` haelt die Uebersicht ehrlich -- wer
ein Modul aendert oder hinzufuegt, ohne MODULES.md neu zu erzeugen, faellt im Gate
auf. (Der alte ``gen_docs.py`` erzeugte Service- und Konfigurationsdoku aus einem
Service-Manifest und den Settings-Klassen; beides gibt es im neuen Kern nicht, ein
woertlicher Umzug waere ins Leere gelaufen. Der Zweck -- Doku aus Code plus Gate --
ist erhalten, der Umfang auf das neue Paket umgestellt.)

Aufruf:
  python tools/gen_docs.py            schreibt MODULES.md und den README-Block
  python tools/gen_docs.py --check    vergleicht, Exit 1 bei Abweichung
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.check_doc_numbers import canonical  # noqa: E402

PKG = REPO / "mt5_trading_ai"
README = REPO / "README.md"
ANFANG = "<!-- KENNZAHLEN-ANFANG"
ENDE = "<!-- KENNZAHLEN-ENDE -->"
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


_QUELLEN: dict[str, list[Path]] = {}


def _zeilen(wurzel: Path) -> list[Path]:
    if wurzel.name not in _QUELLEN:
        _QUELLEN[wurzel.name] = [
            p for p in wurzel.rglob("*.py") if "__pycache__" not in p.parts
        ]
    return _QUELLEN[wurzel.name]


def _aufrufer(stamm: str, wurzel: Path, selbst: Path) -> int:
    """Importzeilen aus ``wurzel``, die ``stamm`` treffen (z. B. risk/sizing)."""
    punkt = stamm.replace("/", ".")
    name = stamm.split("/")[-1]
    paket = ".".join(stamm.split("/")[:-1])
    muster = [
        re.compile(rf"^\s*from mt5_trading_ai\.{re.escape(punkt)} import"),
        re.compile(rf"^\s*import mt5_trading_ai\.{re.escape(punkt)}\b"),
    ]
    if paket:
        muster.append(
            re.compile(
                rf"^\s*from mt5_trading_ai\.{re.escape(paket)} import "
                rf".*\b{re.escape(name)}\b"
            )
        )
    n = 0
    for p in _zeilen(wurzel):
        if p == selbst:
            continue
        for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(m.search(z) for m in muster):
                n += 1
    return n


def render() -> str:
    out: list[str] = [
        BANNER,
        "",
        "# MODULES — oeffentliche API je Modul (generiert aus dem Code)",
        "",
        "Diese Datei ist die **einzige** Stelle, an der die Zeilenzahl je Modul steht.",
        "Je Modul stehen die Aufrufer als Importzeilen (Paket / Werkzeuge / Tests);",
        "0 Aufrufer ausserhalb der Tests heisst: kein nachgewiesener Aufrufpfad.",
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
        stamm = path.relative_to(PKG).with_suffix("").as_posix()
        a = _aufrufer(stamm, PKG, path)
        b = _aufrufer(stamm, REPO / "tools", path)
        c = _aufrufer(stamm, REPO / "tests", path)
        out.append(f"Aufrufer: Paket {a} · Werkzeuge {b} · Tests {c}")
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


def kennzahlen_block() -> str:
    canon = canonical()
    zeilen = [
        ANFANG
        + " (erzeugt von tools/gen_docs.py, "
        + "geprueft von tests/test_readme_numbers.py) -->"
    ]
    zeilen += [f"- {k}: {v}" for k, v in canon.items()]
    zeilen.append(ENDE)
    return "\n".join(zeilen)


def readme_mit_block() -> tuple[str, str]:
    """(aktueller README-Text, README-Text mit erzeugtem Block)."""
    text = README.read_text(encoding="utf-8")
    start = text.index(ANFANG)
    ende = text.index(ENDE) + len(ENDE)
    return text, text[:start] + kennzahlen_block() + text[ende:]


def main() -> int:
    parser = argparse.ArgumentParser(description="MODULES.md aus dem Code erzeugen.")
    parser.add_argument(
        "--check", action="store_true", help="nur pruefen, nicht schreiben"
    )
    args = parser.parse_args()
    generated = render()
    readme_alt, readme_neu = readme_mit_block()
    if args.check:
        if readme_alt != readme_neu:
            print(
                "FEHLGESCHLAGEN — der README-Kennzahlenblock ist veraltet. "
                "`python tools/gen_docs.py` ausfuehren."
            )
            return 1
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != generated:
            print(
                "FEHLGESCHLAGEN — MODULES.md ist veraltet. "
                "`python tools/gen_docs.py` ausfuehren."
            )
            return 1
        print(f"ok — MODULES.md ist aktuell ({len(generated.splitlines())} Zeilen).")
        return 0
    OUT.write_text(generated, encoding="utf-8", newline="\n")
    if readme_alt != readme_neu:
        README.write_text(readme_neu, encoding="utf-8", newline="\n")
        print("README.md: Kennzahlenblock erneuert.")
    print(f"MODULES.md geschrieben ({len(generated.splitlines())} Zeilen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

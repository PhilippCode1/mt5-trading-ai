#!/usr/bin/env python3
"""Sperrt Zahlen-Drift zwischen Doku und Code -- die Ursache, nicht das Symptom.

WARUM ES DIESES SKRIPT GIBT
---------------------------
Die Kennzahlen, die per Test gesperrt waren (der README-KENNZAHLEN-Block), stimmten
immer. Die, die niemand sperrte (frei in MASTERBERICHT.md hingeschriebene Modul-,
Zeilen-, Test- und Commit-Zahlen), drifteten alle. Der Grund ist nicht Nachlaessigkeit,
sondern Struktur: eine Zahl, die an zwei Stellen von Hand steht, geht an einer davon
irgendwann falsch. Dieses Tor macht die Struktur richtig.

DIE REGELN (Teil 3, Paket 0, A0.4; Kernregel 9: jede Angabe nur an EINER Stelle)
--------------------------------------------------------------------------------
1. Die Live-Kennzahlen des Codebestands -- Modulzahl, Testfunktionen, Quellzeilen --
   leben AUSSCHLIESSLICH im README-KENNZAHLEN-Block. Dieser Block wird gegen den Code
   nachgerechnet; weicht er ab, ist das Tor rot.
2. Kein anderes Live-Dokument darf diese Kennzahlen als eigene Zahl WIEDERHOLEN. Es
   verweist auf den Block. Wer sie doch hinschreibt, wird geblockt.
3. Eine "N Faelle"-Angabe zu einer konkreten Testdatei (z. B. ``test_mt5_venue.py``)
   wird gegen die tatsaechliche Fallzahl dieser Datei geprueft -- egal in welchem
   Live-Dokument sie steht.
4. Eine hart hingeschriebene Commit-Zahl ist in Live-Dokumenten verboten: sie driftet
   mit dem naechsten Commit. Sie gehoert nicht in eine statische Datei.

WAS AUSGENOMMEN IST -- UND WARUM
--------------------------------
``PROGRESS.md`` ist ein anhaengendes Logbuch (Kernregel 22: nie ueberschreiben); jeder
Eintrag ist der Zeilenstand ZU DIESEM Paket und war damals wahr. ``docs/audit/`` ist ein
datierter Pruef-Snapshot. Ihre Zahlen sind Zeitpunkt-Belege, kein Ist-Zustand -- sie
gegen den heutigen Code zu "korrigieren", waere Geschichtsfaelschung. Darum prueft
dieses Tor sie NICHT gegen den aktuellen Code.

Aufruf:  python tools/check_doc_numbers.py
Exit 1 bei Verstoss. Laeuft in der CI bei jedem Push und PR.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "mt5_trading_ai"
TESTS = REPO / "tests"
README = REPO / "README.md"

#: Anhaengendes Logbuch bzw. datierte Snapshots -- eingefrorene Zeitpunkt-Belege.
HISTORICAL = ("PROGRESS.md", "docs/audit/")


# --- Kanonische Kennzahlen aus dem Code ----------------------------------------


def module_count() -> int:
    return len([p for p in PKG.rglob("*.py") if p.name != "__init__.py"])


def test_function_count() -> int:
    return sum(_test_cases(p) for p in TESTS.glob("*.py"))


def source_lines() -> int:
    return sum(
        len(p.read_text(encoding="utf-8").splitlines()) for p in PKG.rglob("*.py")
    )


def _test_cases(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def canonical() -> dict[str, int]:
    return {
        "module_count": module_count(),
        "test_function_count": test_function_count(),
        "source_lines": source_lines(),
    }


# --- Hilfen --------------------------------------------------------------------


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [REPO / p for p in out]


def is_historical(rel: str) -> bool:
    return any(rel == h or rel.startswith(h) for h in HISTORICAL)


def _int(raw: str) -> int:
    """'4.112' / '4,112' -> 4112 (deutsche/englische Tausendertrennung)."""
    return int(raw.replace(".", "").replace(",", ""))


# Kennzahlen, die nur im README-Block stehen duerfen (Wiederholung = Drift-Risiko).
OWNED = re.compile(r"\b(\d[\d.,]*)\s*(Module|Testfunktion\w*)\b")
OWNED_LINES = re.compile(r"\b(\d[\d.,]*)\s*Zeilen\s+(Kerncode|Quellcode|Test)", re.I)
COMMITS = re.compile(r"\b(\d[\d.,]*)\s*Commits?\b", re.I)
# "N Faelle" zu einer konkreten Testdatei, in beiden Wortstellungen auf einer Zeile.
PER_FILE = re.compile(r"test_([A-Za-z0-9_]+)\.py")
N_FAELLE = re.compile(r"\b(\d+)\s*F(?:ä|ae)lle", re.I)


def check_readme_block(canon: dict[str, int]) -> list[str]:
    text = README.read_text(encoding="utf-8")
    block = re.search(r"KENNZAHLEN-ANFANG(.*?)KENNZAHLEN-ENDE", text, re.S)
    if block is None:
        return ["README.md: KENNZAHLEN-Block fehlt"]
    declared = {
        k: int(v) for k, v in re.findall(r"-\s*(\w+):\s*(\d+)", block.group(1))
    }
    problems = []
    for key, want in canon.items():
        if declared.get(key) != want:
            problems.append(
                f"README.md: {key} = {declared.get(key)} im Block, Code sagt {want}"
            )
    return problems


def check_live_doc(path: Path) -> list[str]:
    rel = path.relative_to(REPO).as_posix()
    problems: list[str] = []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    in_block = False
    for i, line in enumerate(lines, 1):
        # Der README-Block ist die eine erlaubte Quelle, keine Wiederholung.
        if "KENNZAHLEN-ANFANG" in line:
            in_block = True
        if in_block:
            if "KENNZAHLEN-ENDE" in line:
                in_block = False
            continue

        # Regel 3: "N Faelle" zu einer realen Testdatei gegen die Ist-Zahl pruefen.
        file_hit = PER_FILE.search(line)
        faelle_hit = N_FAELLE.search(line)
        if file_hit and faelle_hit:
            tp = TESTS / f"test_{file_hit.group(1)}.py"
            if tp.is_file():
                actual = _test_cases(tp)
                claimed = int(faelle_hit.group(1))
                if claimed != actual:
                    problems.append(
                        f"{rel}:{i}: test_{file_hit.group(1)}.py mit {claimed} "
                        f"Faellen behauptet, tatsaechlich {actual}"
                    )

        # Nur ANDERE Docs duerfen die README-eigenen Kennzahlen nicht wiederholen.
        if rel != "README.md":
            if OWNED.search(line) or OWNED_LINES.search(line):
                problems.append(
                    f"{rel}:{i}: Kennzahl (Module/Testfunktionen/Zeilen) direkt "
                    f"hingeschrieben -- gehoert in den README-KENNZAHLEN-Block, "
                    f"hier nur verweisen:\n      {line.strip()[:100]}"
                )
        # Regel 4: harte Commit-Zahl driftet mit dem naechsten Commit.
        if COMMITS.search(line):
            problems.append(
                f"{rel}:{i}: harte Commit-Zahl in einem Live-Dokument -- "
                f"weglassen oder auf das Repo verweisen:\n      {line.strip()[:100]}"
            )
    return problems


def main() -> int:
    # Windows-Konsole (cp1252) darf an einem Sonderzeichen im Zitat nicht abstuerzen.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    canon = canonical()
    failures = check_readme_block(canon)
    for md in tracked_markdown():
        rel = md.relative_to(REPO).as_posix()
        if is_historical(rel):
            continue
        failures.extend(check_live_doc(md))

    if failures:
        print("FEHLGESCHLAGEN - Zahlen-Drift zwischen Doku und Code:\n")
        for f in failures:
            print(f"  {f}")
        print(
            "\nKennzahlen leben im README-KENNZAHLEN-Block; andere Docs verweisen. "
            "PROGRESS.md und docs/audit/ sind historische Belege und ausgenommen."
        )
        return 1

    print(
        f"ok - Code: {canon['module_count']} Module, "
        f"{canon['test_function_count']} Testfunktionen, "
        f"{canon['source_lines']} Quellzeilen; Doku widerspruchsfrei."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

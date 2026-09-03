"""T4 -- Bestandszaehlung je Modul, gemessen am Arbeitsbaum (HEAD).

Je Modul unter mt5_trading_ai/: Zeilen, Aufrufer (Importzeilen) getrennt nach Paket,
tools/, tests/; Geldpfad-Zugehoerigkeit (tools/zweigdeckung.py); Mutationssonden
(tools/mutationstor.py); Zweigdeckung aus einer coverage-JSON (Argument); Befunde der
Bewertung je Modul (Tabelle aus Masterprompt 01, Abschnitt 1, plus Nachstellung T3).

Aufruf: python 04-bestand.py <coverage.json>   -> Markdown-Tabelle auf stdout
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
PKG = REPO / "mt5_trading_ai"

#: Befunde je Modul (Bewertung 2026-09-02, Fundstellen; T3 nachgestellt).
BEFUNDE: dict[str, list[str]] = {
    "venue/mt5.py": ["D2", "D1", "D5", "D4", "D8", "V2b", "V8", "V9", "Werkzeuge(initialize)"],
    "risk/sizing.py": ["D3"],
    "execution/leverage_preflight.py": ["D3"],
    "execution/runner.py": ["D3", "D1", "E(Stops)"],
    "execution/risk_manager.py": ["D8", "D7", "D4"],
    "execution/schwebende_auftraege.py": ["D6", "D8"],
    "execution/freshness.py": ["D13/D20"],
    "backtest/kalender.py": ["D20"],
    "risk/leverage.py": ["E"],
    "backtest/edge.py": ["G"],
    "backtest/engine.py": ["K"],
    "costs/model.py": ["K(Slippage 2 Werte)"],
    "gates/erkundung.py": ["D1", "T(Flake)"],
    "backtest/llm_compare.py": ["F3(Huelle)"],
    "gates/herausforderer.py": ["F3(Huelle)"],
    "gates/learning_phase.py": ["F3(Huelle)"],
}


def zeilen(p: Path) -> int:
    return len(p.read_text(encoding="utf-8").splitlines())


def importzeilen(modul: str, wurzel: Path) -> int:
    """Zahl der Importzeilen, die ``modul`` (z. B. 'risk/sizing') aus ``wurzel`` treffen."""
    punkt = modul.replace("/", ".")
    name = modul.split("/")[-1]
    paket = ".".join(modul.split("/")[:-1])
    muster = [
        re.compile(rf"^\s*from mt5_trading_ai\.{re.escape(punkt)} import"),
        re.compile(rf"^\s*import mt5_trading_ai\.{re.escape(punkt)}\b"),
    ]
    if paket:
        muster.append(
            re.compile(
                rf"^\s*from mt5_trading_ai\.{re.escape(paket)} import .*\b{re.escape(name)}\b"
            )
        )
    else:
        muster.append(re.compile(rf"^\s*from mt5_trading_ai import .*\b{re.escape(name)}\b"))
    n = 0
    for p in wurzel.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for z in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if any(m.search(z) for m in muster):
                n += 1
    return n


def main() -> int:
    cov: dict[str, float] = {}
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        daten = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        for datei, info in daten.get("files", {}).items():
            rel = datei.replace("\\", "/")
            rel = rel[rel.index("mt5_trading_ai/") + len("mt5_trading_ai/") :] if "mt5_trading_ai/" in rel else rel
            s = info.get("summary", {})
            nb = s.get("num_branches", 0)
            cov[rel] = (100.0 * s.get("covered_branches", 0) / nb) if nb else float("nan")
    from tools.mutationstor import KATALOG
    from tools.zweigdeckung import GELDPFAD

    sonden: dict[str, int] = {}
    for s in KATALOG:
        d = s.datei.replace("mt5_trading_ai/", "")
        sonden[d] = sonden.get(d, 0) + 1

    module = sorted(
        p.relative_to(PKG).as_posix()
        for p in PKG.rglob("*.py")
        if p.name != "__init__.py" and "__pycache__" not in p.parts
    )
    print("| Modul | Zeilen | Aufrufer Paket | Aufrufer tools/ | Aufrufer tests/ | Geldpfad | Sonden | Zweigdeckung (306bbaa) | Befunde |")
    print("|---|---:|---:|---:|---:|:-:|---:|---:|---|")
    summe = 0
    for m in module:
        stamm = m[:-3]
        z = zeilen(PKG / m)
        summe += z
        a = importzeilen(stamm, PKG)
        b = importzeilen(stamm, REPO / "tools")
        c = importzeilen(stamm, REPO / "tests")
        gp = "ja" if m in GELDPFAD else ""
        so = sonden.get(m, 0)
        zd = cov.get(m)
        zd_s = "—" if zd is None else ("n/a" if zd != zd else f"{zd:.1f} %")
        bef = ", ".join(BEFUNDE.get(m, [])) or "—"
        print(f"| `{m}` | {z} | {a} | {b} | {c} | {gp} | {so} | {zd_s} | {bef} |")
    print(f"\nSumme: {len(module)} Module, {summe} Zeilen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

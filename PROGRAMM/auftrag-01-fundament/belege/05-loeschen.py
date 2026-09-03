"""T5, Schritt 2: die fuenf Loeschkandidaten (E-009) samt Tests entfernen, Verweise nachziehen.

Eigenes Skript (2026-09-03). Es loescht per ``git rm`` (der Inhalt bleibt im Verlauf), zieht
die Sondenliste des Mutationstors und die Geldpfad-Liste nach, entfernt den einen Testfall
in test_stufe7_kaltstart.py, der tools/modelllauf.py als Unterprozess faehrt, und benennt
in sechs Docstrings, dass tools/oberflaeche.py nicht mehr existiert. Jede Handlung wird
gezaehlt und ausgegeben; die Eintraege in PROGRAMM/geloescht.md schreibt es mit.

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-loeschen.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)

LOESCHEN = {
    "mt5_trading_ai/backtest/llm_compare.py": "Huelle fuer ein kuenftiges LLM; einziger Aufrufer tools/modelllauf.py fuetterte sie mit Attrappen (Bewertung F3)",
    "mt5_trading_ai/gates/herausforderer.py": "JSON-Artefakt im Zustand 'wartend' ohne Weg in den Entscheidungspfad; kein Modell, das es befoerdert (Bewertung F3)",
    "mt5_trading_ai/gates/learning_phase.py": "Modellpfad, der jeden Trade auf net_pnl_r = 0 setzt; nur von tools/modelllauf.py erreicht (Bewertung F3)",
    "tools/modelllauf.py": "'Trainingslauf' ohne Modell (Bewertung F3); Auftrag 1 schliesst Modelle aus",
    "tools/oberflaeche.py": "Web-Oberflaeche; Auftrag 1 schliesst Oberflaechen aus; Sammler-Thread starb ohne Terminal still (Bewertung F1)",
    "tests/test_llm_compare.py": "Tests des geloeschten Moduls (6 Faelle)",
    "tests/test_learning_phase.py": "Tests des geloeschten Moduls (9 Faelle)",
    "tests/test_stufe6_modellpfad.py": "Tests von modelllauf/herausforderer/learning_phase (26 Faelle)",
    "tests/test_oberflaeche_kacheln.py": "Tests der Oberflaeche (37 Faelle)",
    "tests/test_oberflaeche_seite.py": "Tests der Oberflaeche (27 Faelle)",
}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def main() -> int:
    head = git("rev-parse", "--short", "HEAD").strip()
    eintraege = [f"{NL}## 2026-09-03 — Fuenf Loeschkandidaten (E-009) samt Tests, Stand vor Loeschung {head}{NL}"]
    for rel, grund in LOESCHEN.items():
        if not (REPO / rel).exists():
            print(f"  FEHLT (uebersprungen): {rel}")
            continue
        zeilen = len((REPO / rel).read_text(encoding="utf-8").splitlines())
        git("rm", "-q", rel)
        print(f"  git rm {rel} ({zeilen} Zeilen)")
        eintraege.append(f"- `{rel}` ({zeilen} Zeilen): {grund}. Im Verlauf bei {head}.{NL}")

    # test_stufe7_kaltstart.py: der eine Fall, der tools/modelllauf.py faehrt
    p = REPO / "tests/test_stufe7_kaltstart.py"
    s = p.read_text(encoding="utf-8")
    m = re.search(r"\n\ndef test_der_trainingslauf_weist_den_anteil_erkundender_beobachtungen_aus\(.*?(?=\n\n\ndef |\Z)", s, flags=re.S)
    assert m, "Testfall in test_stufe7_kaltstart.py nicht gefunden"
    s = s[: m.start()] + s[m.end() :]
    p.write_text(s, encoding="utf-8", newline="")
    print("  tests/test_stufe7_kaltstart.py: 1 Testfall entfernt (fuhr tools/modelllauf.py)")
    eintraege.append("- `tests/test_stufe7_kaltstart.py::test_der_trainingslauf_weist_den_anteil_erkundender_beobachtungen_aus`: fuhr das geloeschte Werkzeug als Unterprozess." + NL)

    # mutationstor: drei Sonden auf herausforderer.py
    p = REPO / "tools/mutationstor.py"
    s = p.read_text(encoding="utf-8")
    s, n = re.subn(r"    Sonde\(\n        name=\"(ueberlappung|mindestmenge|schemahash)\",\n.*?\n    \),\n", "", s, flags=re.S)
    assert n == 3, f"Sonden auf herausforderer: {n}"
    p.write_text(s, encoding="utf-8", newline="")
    print("  tools/mutationstor.py: 3 Sonden entfernt (ueberlappung, mindestmenge, schemahash)")
    eintraege.append("- `tools/mutationstor.py`: die drei Sonden auf `gates/herausforderer.py` (Katalog 16 -> 13)." + NL)

    # zweigdeckung: Geldpfad-Liste
    p = REPO / "tools/zweigdeckung.py"
    s = p.read_text(encoding="utf-8")
    alt = '    "gates/herausforderer.py",\n'
    assert s.count(alt) == 1
    p.write_text(s.replace(alt, ""), encoding="utf-8", newline="")
    print("  tools/zweigdeckung.py: gates/herausforderer.py aus GELDPFAD entfernt (12 -> 11)")
    eintraege.append("- `tools/zweigdeckung.py`: `gates/herausforderer.py` aus der Geldpfad-Liste (12 -> 11 Dateien)." + NL)

    # Docstrings, die die Oberflaeche als existierend nennen
    n = 0
    for rel in (
        "mt5_trading_ai/betrieb/journal.py",
        "mt5_trading_ai/execution/freshness.py",
        "mt5_trading_ai/venue/mt5.py",
        "tests/test_frische_am_orderpfad.py",
        "tests/test_journal_leser.py",
        "tests/test_stufe10_betrieb.py",
    ):
        p = REPO / rel
        s = p.read_text(encoding="utf-8")
        t = s.replace("``tools/oberflaeche.py``", "``tools/oberflaeche.py`` (geloescht, E-009)")
        t = t.replace("``oberflaeche.py``", "``oberflaeche.py`` (geloescht, E-009)")
        t = t.replace("``test_llm_compare.py``", "``test_llm_compare.py`` (geloescht, E-009)")
        k = s.count("oberflaeche.py``") + s.count("test_llm_compare.py``")
        if t != s:
            p.write_text(t, encoding="utf-8", newline="")
            n += k
            print(f"  {rel}: {k} Nennung(en) als geloescht gekennzeichnet")
    eintraege.append(f"- {n} Nennungen der Oberflaeche/des LLM-Tests in Docstrings als geloescht gekennzeichnet (nicht entfernt: sie erklaeren Entscheidungen im Code)." + NL)

    g = REPO / "PROGRAMM/geloescht.md"
    g.write_text(g.read_text(encoding="utf-8") + "".join(eintraege), encoding="utf-8", newline="")
    print("  PROGRAMM/geloescht.md: Eintraege angehaengt")
    return 0


if __name__ == "__main__":
    sys.exit(main())

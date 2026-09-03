"""T5, Nachbesserung (F-005): Mutationstor stellt mit Wiederholung zurueck; E501-Prosa umbrechen.

Eigenes Skript (2026-09-03). Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-haerten-und-umbrechen.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)


def haerten() -> None:
    p = REPO / "tools/mutationstor.py"
    s = p.read_text(encoding="utf-8")
    alt = "    finally:" + NL + "        pfad.write_bytes(original)" + NL
    if alt not in s:
        print("  mutationstor.py: Anker nicht gefunden (schon gehaertet?)")
        return
    neu = NL.join(
        [
            "    finally:",
            "        # Zurueckschreiben mit Wiederholung: am 2026-09-03 blieb ein Mutant im Baum,",
            "        # weil write_bytes im Pre-Push-Lauf an einem Zugriffsfehler scheiterte (F-005).",
            "        letzter: OSError | None = None",
            "        for _versuch in range(10):",
            "            try:",
            "                pfad.write_bytes(original)",
            "                letzter = None",
            "                break",
            "            except OSError as exc:",
            "                letzter = exc",
            "                time.sleep(0.3)",
            "        if letzter is not None:",
            "            raise RuntimeError(",
            "                f'{sonde.datei}: Rueckstellung nach 10 Versuchen gescheitert -- '",
            "                f'MUTANT LIEGT IM ARBEITSBAUM ({sonde.name}): {letzter}'",
            "            ) from letzter",
            "",
        ]
    )
    s = s.replace(alt, neu)
    if "import time" + NL not in s:
        s = s.replace("import sys" + NL, "import sys" + NL + "import time" + NL, 1)
    p.write_text(s, encoding="utf-8", newline="")
    print("  mutationstor.py: Rueckstellung mit zehn Wiederholungen")


def umbrechen() -> None:
    out = subprocess.run(
        [sys.executable, "-m", "ruff", "check", ".", "--output-format", "concise"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    treffer = re.findall(r"^(.+?):(\d+):\d+: E501", out, flags=re.M)
    je: dict[str, list[int]] = {}
    for f, ln in treffer:
        je.setdefault(f.replace(chr(92), "/"), []).append(int(ln))
    gesamt = 0
    offen: list[str] = []
    for f, lns in je.items():
        pf = REPO / f
        zeilen = pf.read_text(encoding="utf-8").split(NL)
        for ln in sorted(lns, reverse=True):
            z = zeilen[ln - 1]
            m = re.match(r'^(\s*(?:#:? ?)?)(")?', z)
            assert m is not None
            prefix = m.group(1)
            zitat = m.group(2) or ""
            rest = z[len(prefix) + len(zitat):]
            if zitat:
                ende = rest.rstrip()
                if ende.endswith('",'):
                    schluss, inhalt = '",', ende[:-2]
                elif ende.endswith('"'):
                    schluss, inhalt = '"', ende[:-1]
                else:
                    offen.append(f"{f}:{ln}")
                    continue
                cut = inhalt.rfind(" ", 0, 88 - len(prefix) - 3)
                if cut <= 0:
                    offen.append(f"{f}:{ln}")
                    continue
                zeilen[ln - 1 : ln] = [
                    prefix + '"' + inhalt[: cut + 1] + '"',
                    prefix + '"' + inhalt[cut + 1 :] + schluss,
                ]
            else:
                cut = rest.rfind(" ", 0, 88 - len(prefix))
                if cut <= 0:
                    offen.append(f"{f}:{ln}")
                    continue
                zeilen[ln - 1 : ln] = [prefix + rest[:cut].rstrip(), prefix + rest[cut + 1 :]]
            gesamt += 1
        pf.write_text(NL.join(zeilen), encoding="utf-8", newline="")
    print(f"  umgebrochen: {gesamt} | offen: {offen}")


if __name__ == "__main__":
    haerten()
    umbrechen()

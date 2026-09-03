#!/usr/bin/env python3
"""Zweigdeckung je Datei des Geldpfads -- mit Schwelle, nicht als Bericht.

WARUM ZWEIGE UND NICHT ZEILEN
-----------------------------
Stufe 8 des Auftrags: *„Deckung von Zeilen auf Zweige je Datei."*

Eine Zeilendeckung von 95 % kann bedeuten, dass jede ``if``-Bedingung genau einmal
gelaufen ist -- immer in dieselbe Richtung. Der ganze Sinn einer Sperre liegt aber im
**anderen** Zweig: dem, der ablehnt. Zeilendeckung misst, ob Code beruehrt wurde;
Zweigdeckung misst, ob beide Ausgaenge einer Entscheidung beruehrt wurden.

Gemessen an diesem Stand ist der Unterschied greifbar: das Paket lag bei **92,8 %**
Zeilen und **86,9 %** Zweigen. Die schwaechste Datei stand bei 79,9 % Zeilen und
**67,9 %** Zweigen -- ausgerechnet ``execution/schwebende_auftraege.py``, die Akte der
ungeklaerten Auftraege aus Stufe 5. Was dort fehlte, waren genau die fail-closed-Zweige:
unlesbare Datei, defektes JSON, unvollstaendiger Eintrag. Also die Zweige, wegen derer
das Modul existiert.

**Je Datei, nicht als Gesamtzahl.** Eine Gesamtdeckung von 87 % kann eine Datei mit
99 % und eine mit 40 % bedeuten, und die mit 40 % ist die interessante. Der Auftrag sagt
„je Datei", und das Tor urteilt so.

DIE SCHWELLE
------------
:data:`MINDEST_ZWEIGDECKUNG` steht auf **0,80**. Sie ist gesetzt, nicht hergeleitet, und
sie ist **vor** dem Aufraeumen der schwaechsten Datei gesetzt worden -- nicht danach auf
den vorgefundenen Wert. Wer sie senkt, weil eine Datei stoert, hebt sie nicht auf,
sondern schafft sie ab (V6).

Aufruf::

    python tools/zweigdeckung.py --messen    # Testlauf unter coverage, dann urteilen
    python tools/zweigdeckung.py             # urteilt ueber eine vorhandene Messung
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Die Schwelle je Datei. Begruendung im Modul-Docstring.
MINDEST_ZWEIGDECKUNG = 0.80

#: Die kritischen Dateien des Geldpfads -- dieselbe Menge, die das Mutationstor trifft.
#: Ausdruecklich aufgezaehlt und nicht per Muster gesucht: eine neue Datei soll bewusst
#: aufgenommen werden, nicht stillschweigend mitlaufen.
GELDPFAD: tuple[str, ...] = (
    "venue/mt5.py",
    "venue/protocol.py",
    "execution/risk_manager.py",
    "execution/schwebende_auftraege.py",
    "execution/cost_gate.py",
    "risk/sizing.py",
    "risk/stop_budget.py",
    "risk/limits.py",
    "risk/leverage.py",
    "costs/model.py",
    "gates/erkundung.py",
)


def _kurzname(pfad: str) -> str:
    return pfad.replace(os.sep, "/").split("mt5_trading_ai/", 1)[-1]


def messen(ziel: Path) -> int:
    """Fahre die Suite unter ``coverage --branch`` und schreibe den JSON-Bericht."""
    lauf = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--source=mt5_trading_ai",
            "-m",
            "pytest",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if lauf.returncode != 0:
        print(
            "FEHLGESCHLAGEN — die Suite ist rot; eine Deckung daraus taugt nichts.",
            file=sys.stderr,
        )
        print(lauf.stdout[-2000:], file=sys.stderr)
        return 1
    bericht = subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", str(ziel)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if bericht.returncode != 0:
        print(f"FEHLGESCHLAGEN — coverage json: {bericht.stderr}", file=sys.stderr)
        return 1
    return 0


def urteile(bericht: Path) -> int:
    if not bericht.is_file():
        print(f"FEHLGESCHLAGEN — {bericht} fehlt. Erst --messen.", file=sys.stderr)
        return 1
    daten = json.loads(bericht.read_text(encoding="utf-8"))
    gemessen = {_kurzname(f): v for f, v in daten["files"].items()}

    print("=" * 74)
    print("ZWEIGDECKUNG JE DATEI DES GELDPFADS")
    print("=" * 74)
    print(f"Schwelle je Datei: {MINDEST_ZWEIGDECKUNG:.0%}")
    print()
    print(f"{'Datei':<40}{'Zeilen':>9}{'Zweige':>9}")

    zu_niedrig: list[tuple[str, float]] = []
    fehlend: list[str] = []
    for name in GELDPFAD:
        eintrag = gemessen.get(name)
        if eintrag is None:
            # Laut scheitern: eine Datei des Geldpfads, die in der Messung fehlt, ist
            # ein Befund und kein Grund, sie zu ueberspringen.
            fehlend.append(name)
            print(f"{name:<40}{'--':>9}{'FEHLT':>9}")
            continue
        s = eintrag["summary"]
        zweige = s.get("num_branches", 0)
        anteil = s.get("covered_branches", 0) / zweige if zweige else 1.0
        marke = "" if anteil >= MINDEST_ZWEIGDECKUNG else "  <== unter der Schwelle"
        print(f"{name:<40}{s['percent_covered']:>8.1f}%{anteil * 100:>8.1f}%{marke}")
        if anteil < MINDEST_ZWEIGDECKUNG:
            zu_niedrig.append((name, anteil))

    g = daten["totals"]
    gesamt = g.get("covered_branches", 0) / max(1, g.get("num_branches", 1))
    print()
    print(
        f"Paket gesamt: Zeilen {g['percent_covered']:.1f} %, "
        f"Zweige {gesamt * 100:.1f} %"
    )

    if fehlend or zu_niedrig:
        print()
        for name in fehlend:
            print(f"FEHLGESCHLAGEN — {name} fehlt in der Messung.", file=sys.stderr)
        for name, anteil in zu_niedrig:
            print(
                f"FEHLGESCHLAGEN — {name}: {anteil:.1%} Zweigdeckung, "
                f"verlangt sind {MINDEST_ZWEIGDECKUNG:.0%}.",
                file=sys.stderr,
            )
        print(
            "Was fehlt, sind in aller Regel die ablehnenden Zweige -- also die, "
            "wegen derer die Datei existiert.",
            file=sys.stderr,
        )
        return 1
    print("ok — jede Datei des Geldpfads ueber der Schwelle.")
    return 0


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Zweigdeckungstor auf dem Geldpfad")
    ap.add_argument(
        "--messen", action="store_true", help="erst die Suite unter coverage fahren"
    )
    ap.add_argument("--bericht", type=Path, default=ROOT / "betrieb" / "coverage.json")
    args = ap.parse_args()

    if args.messen:
        args.bericht.parent.mkdir(parents=True, exist_ok=True)
        rc = messen(args.bericht)
        if rc:
            return rc
    return urteile(args.bericht)


if __name__ == "__main__":
    raise SystemExit(main())

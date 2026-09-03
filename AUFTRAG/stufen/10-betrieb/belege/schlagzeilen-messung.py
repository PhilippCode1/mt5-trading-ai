#!/usr/bin/env python3
"""Beleg: was mit jeder manipulierten Schlagzeile an der Aufnahmegrenze geschieht.

Erzeugt ``schlagzeilen-messung.txt``. Der Testsatz kommt aus
``tests/test_stufe10_betrieb.py`` -- eine zweite Liste hier waere eine zweite Wahrheit.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

from mt5_trading_ai.data.loader import (  # noqa: E402
    DataLoadError,
    bars_checksum,
    from_csv,
    to_csv,
)

from test_stufe10_betrieb import (  # noqa: E402
    SCHLAGZEILEN,
    _csv_mit_pruefsumme,
    _entscheidungswert,
    _lade,
    _saubere_bars,
)

ordner = pathlib.Path(tempfile.mkdtemp(prefix="schlagzeilen-"))
bars = _saubere_bars()
pfad, chk = _csv_mit_pruefsumme(ordner, bars)
sauber = to_csv(bars).rstrip("\n")
vorher = _entscheidungswert(bars)

print("=" * 78)
print("MANIPULIERTE SCHLAGZEILEN AN DER AUFNAHMEGRENZE (load_verified_csv)")
print("=" * 78)
print(f"Basis: {len(bars)} saubere Mo-Fr-Tagesbars, Pruefsumme {chk[:16]}...")
print(
    f"Entscheidungswert vorher: {len(vorher[0])} Signale, "
    f"Nettoergebnis {vorher[1]}, {vorher[2]} Trades"
)
print()

verschoben = 0
for i, s in enumerate(SCHLAGZEILEN):
    pfad.write_text(sauber + "\n" + s + "\n", encoding="utf-8")
    kurz = s[:52].replace("\n", " ")
    try:
        geladen = _lade(pfad, chk)
    except DataLoadError as e:
        print(f"[{i}] {kurz!r}")
        print(f"     ABGEWIESEN: {str(e)[:88]}")
        continue
    gleich = _entscheidungswert(geladen) == vorher
    verschoben += 0 if gleich else 1
    print(f"[{i}] {kurz!r}")
    print(f"     ANGENOMMEN -- Entscheidungswert unveraendert: {gleich}")

print()
print(f"Entscheidungswerte verschoben: {verschoben} von {len(SCHLAGZEILEN)}")
print()
print("-" * 78)
print("ZWEITE LAGE: die Pruefsumme wurde MITGEDREHT (neu signiertes Manifest)")
print("-" * 78)
getarnt = SCHLAGZEILEN[3]
pfad.write_text(sauber + "\n" + getarnt + "\n", encoding="utf-8")
mitgedreht = bars_checksum(from_csv(pfad.read_text(encoding="utf-8")))
print(f"Zeile: {getarnt!r}")
print(f"Neue Pruefsumme: {mitgedreht[:16]}... (Sicherung 1 ist damit umgangen)")
try:
    _lade(pfad, mitgedreht)
    print("DURCHGEKOMMEN -- das Qualitaetstor haelt sie NICHT.")
except DataLoadError as e:
    print(f"Sicherung 2 (Qualitaetstor) haelt: {e}")

print()
print("-" * 78)
print("BEFUND: ``from_csv`` ALLEIN haelt die getarnte Zeile nicht")
print("-" * 78)
durch = from_csv(sauber + "\n" + getarnt)
print(f"from_csv nimmt sie an: {len(durch)} Bars statt {len(bars)}")
print(
    f"letzter Zeitstempel {durch[-1].ts} < vorletzter {durch[-2].ts}: "
    f"{durch[-1].ts < durch[-2].ts}"
)
print("Deshalb misst die Abnahme an ``load_verified_csv`` und nicht an ``from_csv``.")

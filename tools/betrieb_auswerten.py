#!/usr/bin/env python3
"""Wertet das Journal eines Betriebslaufs aus -- ehrlich, ohne Schoenrechnen.

Liest die JSONL-Datei aus ``tools/live_betrieb.py`` und beantwortet drei Fragen:

1. **Lief die Maschine sauber?** Takte, Fehler, Halts, Verbindungsabbrueche. Das ist
   die Frage, fuer die ein Tageslauf taugt.
2. **Was hat sie getan?** Eroeffnungen, an welcher Sperre die uebrigen scheiterten,
   Schliessungen mit Grund.
3. **Was sagt das Ergebnis?** Die Equity-Veraenderung -- und dazu die Einordnung, die
   verhindert, dass jemand sie fuer ein Urteil ueber die Strategie haelt.

Zu Punkt 3 im Klartext: bei den Grenzen dieses Repos (10 Trades je Konto und Tag)
liefert ein Tag hoechstens zehn Beobachtungen. Aus zehn Trades laesst sich ueber einen
Vorteil nichts sagen -- das ist keine Vorsicht, das ist Arithmetik. Diese Auswertung
beziffert darum die Unsicherheit, statt eine Zahl allein stehen zu lassen.

Aufruf::

    python tools/betrieb_auswerten.py                       # neuestes Journal
    python tools/betrieb_auswerten.py journal-2026...jsonl
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"


def _lies(pfad: Path) -> list[dict[str, Any]]:
    zeilen: list[dict[str, Any]] = []
    with pfad.open(encoding="utf-8") as fh:
        for nr, roh in enumerate(fh, 1):
            roh = roh.strip()
            if not roh:
                continue
            try:
                zeilen.append(json.loads(roh))
            except json.JSONDecodeError as exc:
                print(f"  !! Zeile {nr} unlesbar: {exc}", file=sys.stderr)
    return zeilen


def _dauer(zeilen: list[dict[str, Any]]) -> str:
    stempel = [datetime.fromisoformat(z["ts"]) for z in zeilen if "ts" in z]
    if len(stempel) < 2:
        return "?"
    spanne = max(stempel) - min(stempel)
    stunden = spanne.total_seconds() / 3600
    if stunden >= 1:
        return f"{stunden:.2f} h"
    return f"{spanne.total_seconds() / 60:.1f} min"


def auswerten(pfad: Path) -> int:
    zeilen = _lies(pfad)
    if not zeilen:
        print(f"FEHLGESCHLAGEN — {pfad} ist leer.", file=sys.stderr)
        return 1
    nach_art: dict[str, list[dict[str, Any]]] = {}
    for z in zeilen:
        nach_art.setdefault(str(z.get("art")), []).append(z)

    start = (nach_art.get("start") or [{}])[0]
    ende = (nach_art.get("ende") or [{}])[0]

    print("=" * 78)
    print(f"BETRIEBSLAUF {pfad.name}")
    print("=" * 78)
    print(f"Konto        : {start.get('konto')} (Demo: {start.get('demo')})")
    print(f"Instrumente  : {', '.join(start.get('symbole') or [])}")
    print(f"Strategie    : {start.get('strategie')}")
    print(f"Dauer        : {_dauer(zeilen)} ueber "
          f"{len(nach_art.get('takt', []))} Takte")
    scharf = start.get("scharf")
    print(f"Scharf       : {'JA' if scharf else 'nein (trocken)'}")
    if scharf:
        print(f"  Zulassung uebergangen mit Begruendung: "
              f"{start.get('zulassung_uebergangen')}")
        print(f"  {start.get('hinweis')}")
    print()

    # --- 1. Lief die Maschine sauber? ---
    print("-" * 78)
    print("1. LIEF DIE MASCHINE SAUBER?")
    print("-" * 78)
    fehler = nach_art.get("takt_fehler", [])
    halts = [z for z in nach_art.get("takt", []) if z.get("halt")]
    zu_fehl = nach_art.get("schliessen_fehlgeschlagen", [])
    auf_fehl = nach_art.get("eroeffnen_fehlgeschlagen", [])
    print(f"  Takte gesamt              : {len(nach_art.get('takt', []))}")
    print(f"  Takte mit Fehler          : {len(fehler)}")
    print(f"  Takte im Halt             : {len(halts)}")
    print(f"  Schliessen fehlgeschlagen : {len(zu_fehl)}")
    print(f"  Eroeffnen fehlgeschlagen  : {len(auf_fehl)}")
    for z in fehler[:5]:
        print(f"    Takt {z.get('nr')}: {z.get('fehler')}")
    sauber = not fehler and not halts and not zu_fehl and not auf_fehl
    print(f"  URTEIL: {'sauber durchgelaufen' if sauber else 'mit Stoerungen'}")
    print()

    # --- 2. Was hat sie getan? ---
    print("-" * 78)
    print("2. WAS HAT SIE GETAN?")
    print("-" * 78)
    versuche = nach_art.get("eroeffnungsversuch", [])
    eroeffnet = [z for z in versuche if z.get("eroeffnet")]
    print(f"  Eroeffnungsversuche : {len(versuche)}")
    print(f"  davon eroeffnet     : {len(eroeffnet)}")
    if len(versuche) > len(eroeffnet):
        print("  Woran die uebrigen scheiterten:")
        wo: Counter[str] = Counter()
        for z in versuche:
            if z.get("eroeffnet"):
                continue
            letzte = next(
                (s["naht"] for s in reversed(z.get("schritte") or []) if not s["ok"]),
                z.get("grund") or "?",
            )
            wo[f"{letzte} ({z.get('grund')})"] += 1
        for grund, n in wo.most_common():
            print(f"    {n:>4}x  {grund}")
    print()
    zu = nach_art.get("geschlossen", [])
    broker_zu = nach_art.get("vom_broker_geschlossen", [])
    print(f"  Selbst geschlossen  : {len(zu)}")
    if zu:
        for grund, n in Counter(str(z.get("grund")) for z in zu).most_common():
            print(f"    {n:>4}x  {grund}")
    print(f"  Vom Broker zu (Stop): {len(broker_zu)}")
    print()

    # --- 3. Was sagt das Ergebnis? ---
    print("-" * 78)
    print("3. WAS SAGT DAS ERGEBNIS?")
    print("-" * 78)
    if not ende:
        print("  Kein Endeintrag — der Lauf wurde hart abgebrochen.")
        return 0
    e0 = Decimal(str(ende.get("equity_start", "0")))
    e1 = Decimal(str(ende.get("equity", "0")))
    delta = e1 - e0
    print(f"  Equity   : {e0} -> {e1}   ({delta:+})")
    if e0 > 0:
        print(f"  Rendite  : {delta / e0 * 100:+.4f} %")

    n = len(eroeffnet)
    print()
    print("  EINORDNUNG — bitte lesen, bevor jemand diese Zahl deutet:")
    if n == 0:
        print("    Es wurde nichts eroeffnet. Das Ergebnis sagt ueber die Strategie")
        print("    nichts, sondern nur, dass die Kette nicht bis zum Handel kam.")
    else:
        # Wie gross muesste ein echter Vorteil sein, um ihn bei n Trades von Null zu
        # trennen? Faustregel: t = mittlere Rendite / (Streuung / sqrt(n)); fuer eine
        # ernsthafte Trennung braucht es t ~ 2. Also: noetiger Effekt ~ 2*s/sqrt(n).
        print(f"    {n} eroeffnete Position(en). Um einen echten Vorteil von Null zu")
        print("    trennen, muesste der mittlere Gewinn je Trade rund")
        print(f"    {2 / math.sqrt(n):.2f} Standardabweichungen betragen.")
        print("    Bei typischer Streuung ist das um Groessenordnungen mehr, als")
        print("    hier zu sehen ist.")
        print("    Dieser Lauf beantwortet: LIEF DIE MASCHINE. Er beantwortet nicht:")
        print("    TAUGT DIE STRATEGIE. Fuer die zweite Frage steht das Urteil aus")
        print("    Paket 3a (ABSCHLUSS-3a/05-URTEIL.md), und es lautet nein.")
    print()
    print("  Wer jetzt die Parameter auf dieses Ergebnis dreht, betreibt Anpassung an")
    print("  eine Stichprobe dieser Groesse. Genau dagegen ist die Deflation in")
    print("  gates/criteria.py gebaut.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1:
        pfad = Path(sys.argv[1])
        if not pfad.is_absolute() and not pfad.exists():
            pfad = JOURNALE / pfad
    else:
        kandidaten = sorted(JOURNALE.glob("journal-*.jsonl"))
        if not kandidaten:
            print(f"Kein Journal in {JOURNALE}.", file=sys.stderr)
            return 1
        pfad = kandidaten[-1]
    if not pfad.is_file():
        print(f"{pfad} gibt es nicht.", file=sys.stderr)
        return 1
    return auswerten(pfad)


if __name__ == "__main__":
    sys.exit(main())

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

import math
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.betrieb.journal import lies_journal  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"


def auswerten(pfad: Path) -> int:
    lauf = lies_journal(pfad)
    if not lauf.saetze:
        print(f"FEHLGESCHLAGEN — {pfad} ist leer.", file=sys.stderr)
        return 1
    start, ende = lauf.start, lauf.ende
    takte, versuche = lauf.art("takt"), lauf.art("eroeffnungsversuch")
    trades = lauf.trades()
    zu = [t for t in trades if not t.offen]

    print("=" * 78)
    print(f"BETRIEBSLAUF {pfad.name}")
    print("=" * 78)
    print(f"Konto        : {start['konto'] if start else '—'} "
          f"(Demo: {start['demo'] if start else '—'})")
    print(f"Instrumente  : {', '.join((start['symbole'] if start else []) or [])}")
    print(f"Strategie    : {start['strategie'] if start else '—'}")
    print(f"Codestand    : {lauf.version or '—'}")
    print(f"Lauf-Kennung : {lauf.lauf_id or '—'}")
    stempel = [s.ts for s in lauf.saetze]
    spanne = (max(stempel) - min(stempel)).total_seconds() / 60 if stempel else 0.0
    print(f"Dauer        : {spanne:.1f} min ueber {len(takte)} Takte")
    print(f"Scharf       : {'JA' if lauf.scharf else 'nein (trocken)'}")
    if lauf.scharf and start:
        print(f"  Zulassung uebergangen: {start['zulassung_uebergangen']}")
        print(f"  {start['hinweis']}")
    print()

    print("-" * 78)
    print("1. LIEF DIE MASCHINE SAUBER?")
    print("-" * 78)
    fehler = lauf.art("takt_fehler")
    halts = [t for t in takte if t["halt"]]
    zu_fehl = lauf.art("schliessen_fehlgeschlagen")
    auf_fehl = lauf.art("eroeffnen_fehlgeschlagen")
    print(f"  Takte gesamt              : {len(takte)}")
    print(f"  Takte mit Fehler          : {len(fehler)}")
    print(f"  Takte im Halt             : {len(halts)}")
    print(f"  Schliessen fehlgeschlagen : {len(zu_fehl)}")
    print(f"  Eroeffnen fehlgeschlagen  : {len(auf_fehl)}")
    print(f"  Geordnet beendet          : {'ja' if lauf.beendet else 'NEIN'}")
    for s in fehler[:5]:
        print(f"    Takt {s['nr']}: {s['fehler']}")
    sauber = not (fehler or halts or zu_fehl or auf_fehl) and lauf.beendet
    print(f"  URTEIL: {'sauber durchgelaufen' if sauber else 'mit Stoerungen'}")
    print()

    print("-" * 78)
    print("2. WAS HAT SIE GETAN?")
    print("-" * 78)
    auf = [v for v in versuche if v["eroeffnet"]]
    print(f"  Eroeffnungsversuche : {len(versuche)}")
    print(f"  davon eroeffnet     : {len(auf)}")
    if len(versuche) > len(auf):
        print("  Woran die uebrigen scheiterten:")
        wo: Counter[str] = Counter()
        for v in versuche:
            if v["eroeffnet"]:
                continue
            letzte = next(
                (x["naht"] for x in reversed(v["schritte"] or []) if not x["ok"]),
                str(v["grund"] or "?"),
            )
            wo[f"{letzte} ({v['grund']})"] += 1
        for grund, n in wo.most_common():
            print(f"    {n:>4}x  {grund}")
    print()
    print(f"  Trades geschlossen  : {len(zu)}")
    for grund, n in Counter(str(t.grund) for t in zu).most_common():
        print(f"    {n:>4}x  {grund}")
    print()

    print("-" * 78)
    print("3. WAS SAGT DAS ERGEBNIS?")
    print("-" * 78)
    reihe = lauf.equity_reihe()
    if ende is not None:
        e0 = Decimal(str(ende["equity_start"] or "0"))
        e1 = Decimal(str(ende["equity"] or "0"))
    elif len(reihe) >= 2:
        e0, e1 = reihe[0][1], reihe[-1][1]
        print("  (Kein Endeintrag — Equity aus dem ersten und letzten Takt.)")
    else:
        print("  Zu wenige Messpunkte fuer eine Aussage.")
        return 0
    print(f"  Equity   : {e0} -> {e1}   ({e1 - e0:+})")
    if e0 > 0:
        print(f"  Rendite  : {(e1 - e0) / e0 * 100:+.4f} %")

    rechenbar = [t.ergebnis_bps for t in zu if t.ergebnis_bps is not None]
    print()
    print(f"  Trades mit rechenbarem Ergebnis: {len(rechenbar)} von {len(zu)}")
    if rechenbar:
        treffer = sum(1 for w in rechenbar if w > 0) / len(rechenbar) * 100
        print(f"    Median {statistics.median(rechenbar):+.2f} bp | "
              f"Treffer {treffer:.0f} %")
        print("    Preisdifferenz OHNE Kommission und Swap.")
    elif zu:
        print("    Kein einziger vollstaendig — meist fehlt der Ausstiegspreis eines")
        print("    broker-seitigen Schlusses. Das ist NICHT Ergebnis null.")

    n = len(auf)
    print()
    print("  EINORDNUNG — bitte lesen, bevor jemand diese Zahl deutet:")
    if n == 0:
        print("    Es wurde nichts eroeffnet. Das Ergebnis sagt ueber die Strategie")
        print("    nichts, sondern nur, dass die Kette nicht bis zum Handel kam.")
    else:
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
    print()
    print("  Ueber ALLE Laeufe: python tools/betrieb_reihe.py")
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

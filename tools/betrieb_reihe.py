#!/usr/bin/env python3
"""Alle Betriebslaeufe hintereinander -- was ueber Tage hinweg zu sehen ist.

WARUM DIESES WERKZEUG
---------------------
``betrieb_auswerten.py`` nimmt genau eine Datei. Die Unsicherheitsrechnung darin laeuft
je Journal, und die Beobachtungen sammeln sich nie an: zehn Laeufe mit je zwei Trades
bleiben zehnmal „zu wenig fuer eine Aussage" statt einmal zwanzig.

Dieses Werkzeug liest **alle** Journale, haengt sie aneinander und sagt, was sich
zusammenzaehlen laesst -- und was nicht.

WAS SICH NICHT ZUSAMMENZAEHLEN LAESST
--------------------------------------
Zwei Dinge, und beide werden hier ausdruecklich getrennt:

1. **Trockene und scharfe Laeufe.** Ein Trockenlauf sendet nichts; seine Takte gehoeren
   nicht in dieselbe Statistik wie ein Lauf, der gehandelt hat.
2. **Verschiedene Codestaende.** Zwei Laeufe unter unterschiedlichem Commit sind zwei
   verschiedene Maschinen. Der ``version``-Eintrag macht das sichtbar; wo er fehlt
   (Journale vor der Protokollerweiterung), steht das da.

Und die **Luecken zwischen den Laeufen** bleiben Luecken: dort lief die Schleife nicht,
und was in der Pause geschah -- ein gefuellter Stop, Swap, ein Handeingriff -- steht in
keinem Journal. Die Equity springt, und der Grund ist nicht darin.

Aufruf::

    python tools/betrieb_reihe.py
    python tools/betrieb_reihe.py --nur-scharf
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.betrieb.journal import (  # noqa: E402
    Lauf,
    Trade,
    durchgehende_equity,
    lies_alle,
)

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"


def _kopfzeile(lauf: Lauf) -> str:
    reihe = lauf.equity_reihe()
    von = reihe[0][0] if reihe else (lauf.saetze[0].ts if lauf.saetze else None)
    bis = reihe[-1][0] if reihe else von
    dauer = (bis - von).total_seconds() / 60 if von and bis else 0.0
    veraenderung = (reihe[-1][1] - reihe[0][1]) if len(reihe) >= 2 else Decimal("0")
    trades = lauf.trades()
    zu = [t for t in trades if not t.offen]
    marke = "scharf" if lauf.scharf else "trocken"
    schluss = "" if lauf.beendet else "  OHNE ENDEINTRAG"
    return (
        f"{von:%d.%m %H:%M}  {dauer:>6.1f} min  {marke:<8}"
        f"{len(lauf.art('takt')):>5} Takte {len(trades):>4} Trades "
        f"({len(zu)} zu)  {veraenderung:>+9.2f}  "
        f"{(lauf.version or '—'):<20}{schluss}"
    )


def _ergebnisse(trades: list[Trade]) -> tuple[list[Decimal], int, int]:
    """(rechenbare Ergebnisse in bp, geschlossen gesamt, davon unvollstaendig)."""
    zu = [t for t in trades if not t.offen]
    werte = [t.ergebnis_bps for t in zu if t.ergebnis_bps is not None]
    return [w for w in werte if w is not None], len(zu), len(zu) - len(werte)


def auswerten(laeufe: list[Lauf], *, nur_scharf: bool) -> int:
    if nur_scharf:
        laeufe = [lauf for lauf in laeufe if lauf.scharf]
    if not laeufe:
        print("Keine passenden Laeufe.", file=sys.stderr)
        return 1

    print("=" * 100)
    print(f"BETRIEBSREIHE — {len(laeufe)} Laeufe")
    print("=" * 100)
    print(f"{'Beginn':<13}{'Dauer':>10}  {'Art':<8}{'Takte':>6}{'Trades':>10}"
          f"{'Equity':>13}  Codestand")
    print("-" * 100)
    for lauf in laeufe:
        print("  " + _kopfzeile(lauf))
    print()

    # --- Equity ueber alles ------------------------------------------------
    punkte = list(durchgehende_equity(laeufe))
    if punkte:
        anfang, ende = punkte[0][1], punkte[-1][1]
        luecken = sum(1 for _, _, luecke in punkte if luecke)
        print("-" * 100)
        print("EQUITY UEBER ALLE LAEUFE")
        print("-" * 100)
        print(f"  {len(punkte)} Messpunkte von {punkte[0][0]:%d.%m %H:%M} "
              f"bis {punkte[-1][0]:%d.%m %H:%M}")
        print(f"  {anfang} -> {ende}   ({ende - anfang:+})")
        print(f"  Luecken zwischen Laeufen: {luecken}")
        print("  In den Luecken lief die Schleife nicht. Was dort geschah -- ein")
        print("  gefuellter Stop, Swap, ein Handeingriff -- steht in keinem Journal.")
        print()

    # --- Codestaende -------------------------------------------------------
    staende = Counter((lauf.version or "unbekannt") for lauf in laeufe)
    if len(staende) > 1:
        print("-" * 100)
        print("ACHTUNG: MEHRERE CODESTAENDE")
        print("-" * 100)
        for stand, n in staende.most_common():
            print(f"  {n:>3} Laeufe  {stand}")
        print("  Laeufe unter verschiedenen Staenden sind verschiedene Maschinen.")
        print("  Ihre Trades gehoeren nicht ungeprueft in dieselbe Statistik.")
        print()

    # --- Trades ------------------------------------------------------------
    alle = [t for lauf in laeufe for t in lauf.trades()]
    werte, geschlossen, unvollstaendig = _ergebnisse(alle)
    print("-" * 100)
    print("TRADES")
    print("-" * 100)
    print(f"  gesamt           : {len(alle)}")
    print(f"  davon geschlossen: {geschlossen}")
    print(f"  davon rechenbar  : {len(werte)}   (unvollstaendig: {unvollstaendig})")
    if unvollstaendig:
        print("    Unvollstaendig heisst: mindestens ein Preis fehlt -- meist ein")
        print("    broker-seitiger Schluss, dessen Ausstiegspreis das Journal nicht")
        print("    kennt. Solche Trades gehen NICHT als Ergebnis null durch.")
    if alle:
        nach_grund = Counter(str(t.grund) for t in alle if not t.offen)
        for grund, n in nach_grund.most_common():
            print(f"    {n:>4}x  {grund}")
    print()

    if werte:
        median = statistics.median(werte)
        treffer = sum(1 for w in werte if w > 0) / len(werte)
        print(f"  Median-Ergebnis  : {median:+.2f} bp")
        print(f"  Trefferanteil    : {treffer * 100:.1f} %")
        print(f"  Spanne           : {min(werte):+.2f} .. {max(werte):+.2f} bp")
        print()
        print("  ACHTUNG, was diese Zahlen NICHT sind: sie rechnen die Preisdifferenz")
        print("  und lassen Kommission und Swap aussen vor. Sie sind das BRUTTO einer")
        print("  Handvoll Beobachtungen, kein Ertrag. Fuer die gebuchte Zahl braeuchte")
        print("  es die Kontohistorie des Brokers (history_deals_get), die dieses Repo")
        print("  nicht abruft.")
    else:
        print("  Kein einziger Trade ist rechenbar. Ueber ein Ergebnis laesst sich")
        print("  nichts sagen -- auch nicht, dass es null war.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Alle Betriebslaeufe hintereinander")
    ap.add_argument("--verzeichnis", type=Path, default=JOURNALE)
    ap.add_argument("--nur-scharf", action="store_true",
                    help="Trockenlaeufe auslassen")
    args = ap.parse_args()
    return auswerten(lies_alle(args.verzeichnis), nur_scharf=args.nur_scharf)


if __name__ == "__main__":
    sys.exit(main())

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
    bilanz,
    durchgehende_equity,
    geldbilanz,
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


def _geldbericht(trades: list[Trade]) -> None:
    """Die Geldergebnisse ueber ALLE Laeufe -- mit Herkunft, und nur summiert, wenn es
    eine gemeinsame Waehrung gibt.

    Hier ist der Fall echt: mehrere Laeufe koennen auf verschiedenen Konten und damit
    in verschiedenen Waehrungen gelaufen sein. Im Einzellauf-Werkzeug kann er nicht
    auftreten -- ein Journal ist ein Lauf ist ein Konto.
    """
    b = geldbilanz(trades)
    if not b.trades:
        return
    eigene = len(b.trades) - b.vom_broker
    print(
        f"  Geldergebnisse       : {len(b.trades)} ({b.vom_broker} vom Broker "
        f"geschlossen, {eigene} selbst geschlossen)"
    )
    for herkunft, n in sorted(b.je_herkunft.items()):
        print(f"      {n:>4}x  Herkunft: {herkunft}")
    if b.summe is None:
        print(f"  Keine Summe: {b.hindernis}.")
        return
    print(
        f"  Summe der Schaetzungen: {b.summe:+} {b.waehrung} "
        f"(brutto, ohne Swap und Kommission)"
    )


def auswerten(laeufe: list[Lauf], *, nur_scharf: bool) -> int:
    if nur_scharf:
        laeufe = [lauf for lauf in laeufe if lauf.scharf]
    if not laeufe:
        print("Keine passenden Laeufe.", file=sys.stderr)
        return 1

    print("=" * 100)
    print(f"BETRIEBSREIHE — {len(laeufe)} Laeufe")
    print("=" * 100)
    print(
        f"{'Beginn':<13}{'Dauer':>10}  {'Art':<8}{'Takte':>6}{'Trades':>10}"
        f"{'Equity':>13}  Codestand"
    )
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
        print(
            f"  {len(punkte)} Messpunkte von {punkte[0][0]:%d.%m %H:%M} "
            f"bis {punkte[-1][0]:%d.%m %H:%M}"
        )
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
    # Die Einteilung steht in ``betrieb/journal.py``: sie lag hier und in
    # ``betrieb_auswerten.py`` doppelt, und die Kopien waren schon auseinander.
    alle = [t for lauf in laeufe for t in lauf.trades()]
    b = bilanz(alle)
    print("-" * 100)
    print("TRADES")
    print("-" * 100)
    print(f"  gesamt                : {len(alle)}")
    print(f"  davon geschlossen     : {len(b.geschlossen)}")
    print(f"  mit Preisergebnis (bp): {len(b.preis)}")
    print(f"  nur mit Geldergebnis  : {len(b.nur_geld)}")
    print(f"  ohne jedes Ergebnis   : {len(b.stumm)}")
    if b.nur_geld:
        print("    Ein broker-seitiger Schluss hat keinen Fuellpreis. Was das Journal")
        print("    traegt, ist der zuletzt beobachtete Buchwert vor dem Verschwinden:")
        print("    der BETRAG ist eine Schaetzung und geht in keinen Median, das")
        print("    VORZEICHEN geht in den Trefferanteil. Ohne das fielen genau die")
        print("    Stop-Outs -- die Verlierer -- aus jeder Statistik heraus.")
    if b.stumm:
        print("    Ohne jedes Ergebnis heisst UNBEKANNT. Solche Trades gehen NICHT als")
        print("    Ergebnis null durch und zaehlen in keine Zahl unten hinein.")
    if alle:
        nach_grund = Counter(str(t.grund) for t in alle if not t.offen)
        for grund, n in nach_grund.most_common():
            print(f"    {n:>4}x  {grund}")
    print()

    if b.preis:
        print(
            f"  Median-Preisergebnis : {statistics.median(b.preis):+.2f} bp "
            f"ueber {len(b.preis)}"
        )
        print(f"  Spanne               : {min(b.preis):+.2f} .. {max(b.preis):+.2f} bp")
    if b.beurteilt:
        treffer = sum(1 for t in b.beurteilt if t.gewinn) / len(b.beurteilt)
        print(
            f"  Trefferanteil        : {treffer * 100:.1f} % ueber "
            f"{len(b.beurteilt)} beurteilbare "
            f"(davon {len(b.nur_geld)} per Geldschaetzung)"
        )
    _geldbericht(b.geschlossen)
    if b.preis or b.beurteilt:
        print()
        print("  ACHTUNG, was diese Zahlen NICHT sind: sie rechnen die Preisdifferenz")
        print("  und lassen Kommission und Swap aussen vor. Sie sind das BRUTTO einer")
        print("  Handvoll Beobachtungen, kein Ertrag. Fuer die gebuchte Zahl braeuchte")
        print("  es die Kontohistorie des Brokers (history_deals_get), die dieses Repo")
        print("  nicht abruft.")
    else:
        print("  Kein einziger Trade ist beurteilbar. Ueber ein Ergebnis laesst sich")
        print("  nichts sagen -- auch nicht, dass es null war.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Alle Betriebslaeufe hintereinander")
    ap.add_argument("--verzeichnis", type=Path, default=JOURNALE)
    ap.add_argument("--nur-scharf", action="store_true", help="Trockenlaeufe auslassen")
    args = ap.parse_args()
    return auswerten(lies_alle(args.verzeichnis), nur_scharf=args.nur_scharf)


if __name__ == "__main__":
    sys.exit(main())

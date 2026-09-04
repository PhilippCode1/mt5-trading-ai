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

EIN JOURNAL ODER DIE AUFZEICHNUNG
---------------------------------
Die Eingabe ist ein Betriebsjournal (ein Lauf) oder die eingecheckte Aufzeichnung
(``aufzeichnungen/demo-2026-08-17.jsonl``, 21 Laeufe mit stabilen Kennungen
``LAUF-01`` ... ``LAUF-21``). Bei mehreren Laeufen wird der **letzte** ausgewertet,
und das steht in der Ausgabe; ``--lauf`` waehlt einen anderen, ``--liste`` zeigt alle.
Frueher warf dieses Werkzeug auf der Kopfzeile der Aufzeichnung (``JournalError``).

Aufruf::

    python tools/betrieb_auswerten.py                       # neuestes Journal
    python tools/betrieb_auswerten.py journal-2026...jsonl
    python tools/betrieb_auswerten.py aufzeichnungen/demo-2026-08-17.jsonl --liste
    python tools/betrieb_auswerten.py <aufzeichnung> --lauf LAUF-18
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.betrieb.journal import (  # noqa: E402
    JournalError,
    Lauf,
    Trade,
    bilanz,
    geldbilanz,
    lies_alle,
)

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"
AUFZEICHNUNG = REPO / "aufzeichnungen" / "demo-2026-08-17.jsonl"


def _geldbericht(trades: list[Trade]) -> None:
    """Die Geldergebnisse: woher sie kommen, und ob sich summieren laesst.

    Uebergeben werden ALLE geschlossenen Trades, nicht nur die ohne Preisergebnis.
    Sonst bestuende die Geldstatistik wieder ausschliesslich aus Stop-Outs -- also aus
    Verlierern --, weil ``Trade.urteilsquelle`` dem Preis den Vorrang gibt und ein
    selbst geschlossener Trade damit nie im Geldtopf landet. Genau das war der Grund,
    aus dem der ``geschlossen``-Satz sein Geldfeld ueberhaupt bekommen hat.

    Die Herkunft steht dabei: ein aus einem Altjournal GEDEUTETER Betrag ist keine
    geschriebene Auskunft, und dieser Unterschied darf nicht in einer Summe
    verschwinden.
    """
    b = geldbilanz(trades)
    if not b.trades:
        return
    eigene = len(b.trades) - b.vom_broker
    print(
        f"    Geldergebnisse: {len(b.trades)} ({b.vom_broker} vom Broker "
        f"geschlossen, {eigene} selbst geschlossen)"
    )
    for herkunft, n in sorted(b.je_herkunft.items()):
        print(f"      {n:>4}x  Herkunft: {herkunft}")
    if b.summe is None:
        print(f"    Keine Summe: {b.hindernis}.")
        return
    print(
        f"    Summe dieser Schaetzungen: {b.summe:+} "
        f"{b.waehrung} (brutto, ohne Swap und Kommission)"
    )


def lauf_auswerten(lauf: Lauf) -> int:
    """Die drei Fragen fuer EINEN Lauf."""
    start, ende = lauf.start, lauf.ende
    takte, versuche = lauf.art("takt"), lauf.art("eroeffnungsversuch")
    trades = lauf.trades()
    zu = [t for t in trades if not t.offen]

    print("=" * 78)
    print(f"BETRIEBSLAUF {lauf.pfad.name}  ({lauf.lauf_id or 'ohne Kennung'})")
    print("=" * 78)
    print(
        f"Konto        : {start['konto'] if start else '—'} "
        f"(Demo: {start['demo'] if start else '—'})"
    )
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
            # Die Aufzeichnung traegt ``schritte`` nicht (im Kopf ausgewiesen); dann
            # bleibt der Grund, und der steht im selben Satz.
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
    # Zu wenige Equity-Punkte beendete diese Auswertung frueher mit ``return`` -- und
    # nahm die Trade-Zahlen darunter mit ins Grab. Ein Lauf, der nach dem ersten Takt
    # abbrach, aber einen Stop-Out gesehen hat, meldete dann ueberhaupt nichts ueber
    # den Trade. Die Equity-Aussage entfaellt, die Trades werden trotzdem gezaehlt.
    reihe = lauf.equity_reihe()
    e0: Decimal | None = None
    e1: Decimal | None = None
    if ende is not None:
        e0 = Decimal(str(ende["equity_start"] or "0"))
        e1 = Decimal(str(ende["equity"] or "0"))
    elif len(reihe) >= 2:
        e0, e1 = reihe[0][1], reihe[-1][1]
        print("  (Kein Endeintrag — Equity aus dem ersten und letzten Takt.)")
    else:
        print("  Zu wenige Messpunkte fuer eine Equity-Aussage.")
    if e0 is not None and e1 is not None:
        print(f"  Equity   : {e0} -> {e1}   ({e1 - e0:+})")
        if e0 > 0:
            print(f"  Rendite  : {(e1 - e0) / e0 * 100:+.4f} %")

    # Zwei Sorten Ergebnis, bewusst getrennt ausgewiesen. Der Median lebt weiter
    # ausschliesslich von gemessenen Preisen; der Trefferanteil darf zusaetzlich das
    # Vorzeichen des Geldergebnisses verwenden. Vermischt man beides, steht am Ende
    # eine Zahl da, der niemand ansieht, wie viel Schaetzung in ihr steckt.
    #
    # Die Einteilung selbst steht in ``betrieb/journal.py`` -- sie lag hier und in
    # ``betrieb_reihe.py`` doppelt, mit bereits auseinandergelaufenen Ausgaben.
    b = bilanz(zu)
    preis, beurteilt, nur_geld, stumm = b.preis, b.beurteilt, b.nur_geld, b.stumm
    print()
    print(f"  Trades geschlossen             : {len(zu)}")
    print(f"    mit Preisergebnis (bp)       : {len(preis)}")
    print(f"    nur mit Geldergebnis         : {len(nur_geld)}")
    print(f"    ohne jedes Ergebnis          : {len(stumm)}")
    if preis:
        print(
            f"    Median {statistics.median(preis):+.2f} bp ueber {len(preis)} Trade(s)"
        )
        print("    Preisdifferenz OHNE Kommission und Swap.")
    if beurteilt:
        treffer = sum(1 for t in beurteilt if t.gewinn) / len(beurteilt) * 100
        print(
            f"    Treffer {treffer:.0f} % ueber {len(beurteilt)} beurteilbare Trade(s)"
        )
    if nur_geld:
        print("    Beim broker-seitigen Schluss (Stop-Out) gibt es keinen Fuellpreis.")
        print("    Was es gibt, ist der zuletzt beobachtete Buchwert: sein BETRAG ist")
        print("    eine Schaetzung und geht in KEINEN Median, sein VORZEICHEN geht in")
        print("    den Trefferanteil. Ohne das fielen die Stop-Outs -- also die")
        print("    Verlierer -- ganz aus der Statistik, und sie sah besser aus.")
    _geldbericht(zu)
    if stumm:
        print("    Ohne jedes Ergebnis heisst UNBEKANNT, nicht null. Diese Trades")
        print("    zaehlen in keine Zahl oben hinein -- Journale von vor der")
        print("    Protokollerweiterung tragen den Wert nicht.")

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
        print("    Paket 3a (archiv/ABSCHLUSS-3a/05-URTEIL.md), und es lautet nein.")
    print()
    print("  Wer jetzt die Parameter auf dieses Ergebnis dreht, betreibt Anpassung an")
    print("  eine Stichprobe dieser Groesse. Genau dagegen ist die Deflation in")
    print("  gates/criteria.py gebaut.")
    print()
    print("  Ueber ALLE Laeufe: python tools/betrieb_reihe.py")
    return 0


def auswerten(pfad: Path, kennung: str | None = None) -> int:
    """Einen Lauf aus ``pfad`` auswerten -- ein Journal oder eine Aufzeichnung.

    Traegt die Datei mehrere Laeufe, wird ohne ``kennung`` der letzte (juengste)
    genommen, und die Ausgabe sagt das. Eine unbekannte Kennung ist ein Fehlschlag mit
    der Liste der vorhandenen -- kein stiller Rueckfall auf irgendeinen Lauf.
    """
    laeufe = lies_alle(pfad)
    if not laeufe:
        print(f"FEHLGESCHLAGEN — {pfad} traegt keinen Lauf.", file=sys.stderr)
        return 1
    if kennung is None:
        lauf = laeufe[-1]
    else:
        gefunden = [lf for lf in laeufe if lf.lauf_id == kennung]
        if not gefunden:
            print(
                f"FEHLGESCHLAGEN — Lauf {kennung!r} gibt es in {pfad.name} nicht. "
                f"Vorhanden: {', '.join(str(lf.lauf_id) for lf in laeufe)}",
                file=sys.stderr,
            )
            return 1
        lauf = gefunden[0]
    if len(laeufe) > 1:
        print(
            f"Aufzeichnung mit {len(laeufe)} Laeufen; ausgewertet wird "
            f"{lauf.lauf_id} ({'gewaehlt' if kennung else 'der letzte'}). "
            "--liste zeigt alle, --lauf KENNUNG waehlt."
        )
        print()
    return lauf_auswerten(lauf)


def liste(pfad: Path) -> int:
    laeufe = lies_alle(pfad)
    if not laeufe:
        print(f"FEHLGESCHLAGEN — {pfad} traegt keinen Lauf.", file=sys.stderr)
        return 1
    print(f"{len(laeufe)} Laeufe in {pfad.name}:")
    for lauf in laeufe:
        start = lauf.saetze[0].ts
        print(
            f"  {lauf.lauf_id or '—':<10} {start:%Y-%m-%d %H:%M:%S} "
            f"{len(lauf.saetze):>6} Saetze {len(lauf.art('takt')):>5} Takte "
            f"{'scharf' if lauf.scharf else 'trocken':<8}"
            f"{'' if lauf.beendet else '  OHNE ENDEINTRAG'}"
        )
    return 0


def _eingabe(arg: Path | None) -> Path | None:
    """Die Datei, die ausgewertet wird -- oder ``None`` mit Meldung."""
    if arg is None:
        kandidaten = sorted(JOURNALE.glob("journal-*.jsonl"))
        if kandidaten:
            return kandidaten[-1]
        print(
            f"FEHLGESCHLAGEN — kein Journal unter {JOURNALE}. Die eingecheckte "
            f"Aufzeichnung: {AUFZEICHNUNG.relative_to(REPO).as_posix()}",
            file=sys.stderr,
        )
        return None
    pfad = arg
    if not pfad.is_absolute() and not pfad.exists():
        pfad = JOURNALE / pfad
    if pfad.is_dir():
        kandidaten = sorted(pfad.glob("journal-*.jsonl"))
        if not kandidaten:
            print(f"FEHLGESCHLAGEN — kein Journal unter {pfad}.", file=sys.stderr)
            return None
        return kandidaten[-1]
    if not pfad.is_file():
        print(f"FEHLGESCHLAGEN — {arg} gibt es nicht.", file=sys.stderr)
        return None
    return pfad


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="Einen Betriebslauf auswerten -- Journal oder Aufzeichnung."
    )
    ap.add_argument(
        "journal",
        nargs="?",
        type=Path,
        default=None,
        help=(
            "Journaldatei, Aufzeichnung oder Verzeichnis (Vorgabe: das neueste "
            "Journal unter betrieb/)"
        ),
    )
    ap.add_argument(
        "--lauf",
        default=None,
        metavar="KENNUNG",
        help=(
            "bei mehreren Laeufen in der Datei: diesen auswerten (Vorgabe: der letzte)"
        ),
    )
    ap.add_argument(
        "--liste", action="store_true", help="nur die Laeufe der Datei auflisten"
    )
    args = ap.parse_args()
    pfad = _eingabe(args.journal)
    if pfad is None:
        return 1
    try:
        return liste(pfad) if args.liste else auswerten(pfad, args.lauf)
    except JournalError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

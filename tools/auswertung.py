#!/usr/bin/env python3
"""Auswertungstabelle mit Herkunftsspalte -- auch die Zeilen, die nie gefahren wurden.

WARUM
-----
Stufe 7, Abnahme: *„die Auswertungstabelle enthaelt gekennzeichnete Zeilen aus
abgelehnten Signalen; ein Trainingslauf weist den Anteil erkundender Beobachtungen
aus."*

Der Kreis dieser Stufe ist an den Betriebsjournalen dieses Standes abzulesen: von
**4.343** Eroeffnungsversuchen wurden **32** eroeffnet. Ueber die anderen 99,26 % gibt
es keine Zeile in irgendeiner Auswertung -- nicht, weil sie schlecht waren, sondern
weil sie nie gefahren wurden. Eine Auswertung, die nur die eigenen Zusagen zeigt, kann
ein zu strenges Tor nicht von einem richtigen unterscheiden.

Dieses Werkzeug baut die Tabelle so, dass die Absagen **darin stehen** -- gekennzeichnet
mit ``abgelehnt`` und ihrem Grund, ohne Ergebnis. Das fehlende Ergebnis ist keine Luecke
der Tabelle, sondern ihr Befund.

WAS DIE HERKUNFTSSPALTE UNTERSCHEIDET
-------------------------------------
``gefahren``  -- regulaer zugelassen und gefahren; Ergebnis vorhanden, Gewicht 1
``erkundet``  -- abgelehnt, auf dem Papierkonto dennoch gefahren; Ergebnis vorhanden,
                 Gewicht ``1/p`` nach Auswahlwahrscheinlichkeit
``abgelehnt`` -- abgelehnt und nicht gefahren; **kein** Ergebnis

Aufruf::

    python tools/auswertung.py --journal aufzeichnungen/demo-2026-08-17.jsonl
    python tools/auswertung.py --journal betrieb/ --csv auswertung.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.gates.erkundung import (  # noqa: E402
    Auswertungszeile,
    Herkunft,
    erkundungsanteil,
    gewichteter_mittelwert,
)


def _saetze(pfad: Path) -> Iterator[dict[str, Any]]:
    dateien = sorted(pfad.glob("*.jsonl")) if pfad.is_dir() else [pfad]
    for datei in dateien:
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                yield json.loads(zeile)
            except json.JSONDecodeError:
                continue


def tabelle_aus_journal(pfad: Path) -> list[Auswertungszeile]:
    """Baue die Tabelle -- Eroeffnungsversuche UND ihre Ausgaenge.

    Das Ergebnis eines gefahrenen Signals steht nicht im ``eroeffnungsversuch``,
    sondern erst im spaeteren ``geschlossen``. Beide werden ueber die Kennung
    zusammengefuehrt; findet sich kein Abschluss, bleibt das Ergebnis ``None`` -- eine
    offene Position hat keines, und ein erfundenes waere schlimmer als keines.
    """
    # DIE KETTE, UND WARUM SIE DREI SATZARTEN BRAUCHT
    # ------------------------------------------------
    # Der Abschluss traegt NICHT die Kennung der Eroeffnung: die Eroeffnung heisst
    # ``open-EURUSD-...``, der Abschluss ``close-EURUSD-...``. Gemessen an den echten
    # Journalen ist die Schnittmenge beider Kennungsmengen **leer** (16 gegen 11, 0
    # gemeinsam). Wer nur diese beiden Satzarten zusammenfuehrt, bekommt kein einziges
    # Ergebnis -- und merkt es nur, wenn er nachsieht.
    #
    # Verbunden wird ueber die **Positionskennung**, und die steht im dritten Satz:
    #   eroeffnungsversuch.client_order_id -> eroeffnet.client_order_id
    #   eroeffnet.position_id              -> geschlossen.position_id
    # Ueber diesen Weg treffen sich alle 16 gefahrenen Signale mit ihrem Abschluss.
    position_je_kennung: dict[str, str] = {}
    for satz in _saetze(pfad):
        if satz.get("art") != "eroeffnet":
            continue
        kennung, position = satz.get("client_order_id"), satz.get("position_id")
        if isinstance(kennung, str) and isinstance(position, str):
            position_je_kennung[kennung] = position

    # Ergebnis in Basispunkten des Einstiegs, mit Richtung -- ein Short gewinnt, wenn
    # der Kurs faellt. Fehlt einer der beiden Preise (die vom Broker geschlossenen
    # Saetze tragen keinen Ausstiegspreis), gibt es kein Ergebnis: eine geschaetzte
    # Zahl waere hier schlimmer als eine fehlende (V3).
    ergebnis_je_position: dict[str, float] = {}
    for satz in _saetze(pfad):
        if satz.get("art") not in ("geschlossen", "vom_broker_geschlossen"):
            continue
        position = satz.get("position_id")
        if not isinstance(position, str):
            continue
        try:
            ein = float(satz["einstiegspreis"])
            aus = float(satz["ausstiegspreis"])
        except (KeyError, TypeError, ValueError):
            continue
        if ein <= 0:
            continue
        richtung = 1.0 if satz.get("war_kauf") else -1.0
        ergebnis_je_position[position] = richtung * (aus - ein) / ein * 10_000.0

    zeilen: list[Auswertungszeile] = []
    for satz in _saetze(pfad):
        if satz.get("art") != "eroeffnungsversuch":
            continue
        kennung = satz.get("client_order_id")
        eroeffnet = bool(satz.get("eroeffnet"))
        # ``erkundet`` traegt das Journal, sobald der Betrieb die Erkundung faehrt;
        # aeltere Journale kennen das Feld nicht und sind dann schlicht ``gefahren``.
        if eroeffnet:
            herkunft = (
                Herkunft.ERKUNDET if satz.get("erkundet") else Herkunft.GEFAHREN
            )
        else:
            herkunft = Herkunft.ABGELEHNT
        zeilen.append(
            Auswertungszeile(
                ts=str(satz.get("ts", "")),
                instrument=str(satz.get("symbol", "")),
                signal=str(satz.get("signal", "")),
                herkunft=herkunft,
                ergebnis_bp=(
                    ergebnis_je_position.get(position_je_kennung.get(kennung, ""))
                    if isinstance(kennung, str)
                    else None
                ),
                ablehnungsgrund=str(satz.get("grund") or ""),
                wahrscheinlichkeit=float(satz.get("erkundung_p", 1.0) or 1.0),
            )
        )
    return zeilen


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Auswertung mit Herkunftsspalte")
    ap.add_argument("--journal", type=Path, required=True)
    ap.add_argument("--csv", type=Path, default=None)
    args = ap.parse_args()

    if not args.journal.exists():
        print(f"FEHLGESCHLAGEN — {args.journal} fehlt.", file=sys.stderr)
        return 1
    zeilen = tabelle_aus_journal(args.journal)
    if not zeilen:
        print(f"FEHLGESCHLAGEN — kein Eroeffnungsversuch in {args.journal}.",
              file=sys.stderr)
        return 1

    je_herkunft = Counter(z.herkunft.value for z in zeilen)
    gruende = Counter(z.ablehnungsgrund for z in zeilen if z.ablehnungsgrund)
    mit_ergebnis = [z for z in zeilen if z.ergebnis_bp is not None]

    print("=" * 74)
    print("AUSWERTUNG MIT HERKUNFTSSPALTE")
    print("=" * 74)
    print(f"Quelle : {args.journal}")
    print(f"Zeilen : {len(zeilen)}")
    for name in (Herkunft.GEFAHREN, Herkunft.ERKUNDET, Herkunft.ABGELEHNT):
        anzahl = je_herkunft.get(name.value, 0)
        anteil = anzahl / len(zeilen) * 100
        print(f"  {name.value:<12} {anzahl:>6}  ({anteil:5.2f} %)")
    print()
    print(f"Zeilen MIT Ergebnis          : {len(mit_ergebnis)}")
    print(f"Anteil erkundender Beobachtungen: {erkundungsanteil(zeilen) * 100:.2f} %")
    mittel = gewichteter_mittelwert(zeilen)
    print(
        "Gewichteter Mittelwert       : "
        + ("keine Zeile mit Ergebnis" if mittel is None else f"{mittel:.4f}")
    )
    print()
    print("Ablehnungsgruende -- die Zeilen, ueber die es sonst nichts gaebe:")
    for grund, anzahl in gruende.most_common(12):
        print(f"  {grund[:44]:<46} {anzahl:>6}")

    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", encoding="utf-8", newline="") as fh:
            schreiber = csv.writer(fh)
            schreiber.writerow(
                ["ts", "instrument", "signal", "herkunft", "ergebnis_bp",
                 "ablehnungsgrund", "wahrscheinlichkeit", "gewicht"]
            )
            for z in zeilen:
                schreiber.writerow(
                    [z.ts, z.instrument, z.signal, z.herkunft.value,
                     "" if z.ergebnis_bp is None else z.ergebnis_bp,
                     z.ablehnungsgrund, z.wahrscheinlichkeit, z.gewicht]
                )
        print()
        print(f"geschrieben: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

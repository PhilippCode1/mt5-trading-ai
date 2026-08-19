#!/usr/bin/env python3
"""Betriebsjournale zu redigierten Aufzeichnungen machen -- einchecken statt erzaehlen.

WARUM
-----
Stufe 5 des Auftrags verlangt Ausfuehrungserfahrung **gegen die Demoumgebung**, „als
redigierte Aufzeichnungen einchecken", und in der Abnahme: *„mindestens eine echte,
aufgezeichnete Antwort des Handelsplatzes liegt im Repo"*.

Die Antworten existierten bereits -- 21 Journale mit 17.166 Saetzen aus einem echten
Demolauf am 2026-08-17. Sie lagen nur nicht **im Repo**: ``/betrieb/`` steht in
``.gitignore``, und das aus gutem Grund (Laufzeitdatenhalde, taeglich neu). Dieses
Werkzeug schlaegt die Bruecke: es liest die Journale und schreibt eine redigierte,
verkleinerte Fassung nach ``aufzeichnungen/``, die eingecheckt wird.

WAS REDIGIERT WIRD -- UND WIE
-----------------------------
Ersetzt werden **fortlaufend nummeriert**, nicht gehasht::

    konto            -> KONTO-1
    order_id         -> ORDER-0001
    position_id      -> POSITION-01
    client_order_id  -> KENNUNG-0001
    lauf             -> LAUF-01
    pfad             -> <pfad entfernt>

Die Nummerierung ist **nicht umkehrbar**: es gibt kein Salz, keinen Schluessel und
keine gespeicherte Zuordnung. Ein Hash waere die schlechtere Wahl -- eine Kontonummer
hat so wenig Entropie, dass ein Hash davon in Sekunden zurueckgerechnet ist, und ein
gesalzener Hash braeuchte ein Salz, das irgendwo liegen muss. Die laufende Nummer
loest beides: sie haelt gleiche Werte gleich (die Aufzeichnung bleibt lesbar) und
traegt nichts vom Original in sich.

Erhalten bleiben Preise, Volumina, Zeitstempel, Symbole, Gruende und Fehlertexte des
Handelsplatzes. Das ist der Inhalt, um dessentwillen die Aufzeichnung existiert.

WAS WEGGELASSEN WIRD -- UND WARUM ES DASTEHT
--------------------------------------------
Drei Satzarten machen den Grossteil des Umfangs aus und tragen keine Auskunft ueber
eine Entscheidung: ``kurs``, ``signal`` und ``takt``. Sie werden weggelassen.

``eroeffnungsversuch`` wurde in der ersten Fassung ebenfalls weggelassen -- ein Fehler,
der erst in Stufe 7 auffiel und dort korrigiert wurde. Begruendung an :data:`BEHALTEN`.

**Die Zahl der weggelassenen Saetze steht je Art im Kopf jeder Datei.** Eine stille
Verkleinerung waere eine Aufzeichnung, die vollstaendig aussieht und es nicht ist --
und genau das soll eine Aufzeichnung nicht koennen.

Aufruf::

    python tools/aufzeichnung_redigieren.py                 # schreibt aufzeichnungen/
    python tools/aufzeichnung_redigieren.py --pruefen       # meldet nur Abweichungen
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUELLE = ROOT / "betrieb"
ZIEL = ROOT / "aufzeichnungen"

#: Satzarten, die eine Antwort des Handelsplatzes oder eine Zustandsaenderung tragen.
#: Alles andere ist Messrauschen des Laufs.
BEHALTEN: frozenset[str] = frozenset(
    {
        # Nachtrag Stufe 7: ``eroeffnungsversuch`` stand hier zuerst NICHT drin -- ich
        # habe ihn in Stufe 5 als Messrauschen weggelassen, weil er 4.343 der 17.166
        # Saetze ausmacht. Das war falsch, und zwar auf eine Weise, die erst eine Stufe
        # spaeter auffiel: die Abnahme der Stufe 7 verlangt ausdruecklich, dass die
        # Auswertungstabelle „gekennzeichnete Zeilen aus abgelehnten Signalen" enthaelt.
        # Genau diese Saetze tragen die 4.311 Absagen samt Grund. Eine Verkleinerung,
        # die den Umfang nach Haeufigkeit beurteilt statt nach Aussagekraft, wirft das
        # Seltene weg und behaelt das Laute.
        "eroeffnungsversuch",
        "start",
        "ende",
        "eroeffnet",
        "geschlossen",
        "schliessen_fehlgeschlagen",
        "vom_broker_geschlossen",
        "buch_uebernommen",
        "halt_erklaert",
        "stoppdatei",
    }
)

#: Feld -> Praefix der laufenden Nummer. Die Breite haelt die Ausgabe ausgerichtet.
KENNUNGSFELDER: dict[str, tuple[str, int]] = {
    "konto": ("KONTO", 1),
    "order_id": ("ORDER", 4),
    "position_id": ("POSITION", 2),
    "client_order_id": ("KENNUNG", 4),
    "lauf": ("LAUF", 2),
}

#: Felder, deren Wert ersatzlos verschwindet. Ein Pfad traegt den Benutzernamen und
#: sagt ueber den Handelsplatz nichts.
ENTFERNEN: frozenset[str] = frozenset({"pfad"})

#: Felder, die ganz wegfallen -- **nach Aussagekraft, nicht nach Umfang.**
#:
#: ``schritte`` traegt die Naht-fuer-Naht-Liste eines Eroeffnungsversuchs. Was daraus
#: fuer eine Auswertung zaehlt, ist die erste rote Naht -- und die steht bereits als
#: ``grund`` im selben Satz. Die uebrigen Eintraege sind die gruenen Nahte davor:
#: Diagnose ueber den Weg, nicht ueber die Entscheidung.
#:
#: Dass es zugleich 72 % des Umfangs spart (4,15 MB gegen 1,18 MB), ist ein
#: willkommener Nebeneffekt und ausdruecklich **nicht** die Begruendung. Genau diese
#: Verwechslung -- Umfang statt Aussagekraft -- hat in Stufe 5 dazu gefuehrt, die
#: Absagen komplett wegzulassen.
FELDER_WEGLASSEN: frozenset[str] = frozenset({"schritte"})


class Redaktion:
    """Vergibt laufende Nummern je Feld und haelt gleiche Werte gleich."""

    def __init__(self) -> None:
        self._zuordnung: dict[tuple[str, str], str] = {}
        self._zaehler: Counter[str] = Counter()

    def ersetze(self, feld: str, wert: Any) -> str:
        praefix, breite = KENNUNGSFELDER[feld]
        schluessel = (feld, str(wert))
        vorhanden = self._zuordnung.get(schluessel)
        if vorhanden is not None:
            return vorhanden
        self._zaehler[feld] += 1
        neu = f"{praefix}-{self._zaehler[feld]:0{breite}d}"
        self._zuordnung[schluessel] = neu
        return neu

    def satz(self, roh: dict[str, Any]) -> dict[str, Any]:
        aus: dict[str, Any] = {}
        for k, v in roh.items():
            if k in FELDER_WEGLASSEN:
                self._zaehler[f"feld:{k}"] += 1
                continue
            if k in ENTFERNEN:
                aus[k] = "<entfernt>"
            elif k in KENNUNGSFELDER and v is not None:
                aus[k] = self.ersetze(k, v)
            else:
                aus[k] = v
        return aus

    @property
    def vergeben(self) -> dict[str, int]:
        return dict(self._zaehler)


def redigiere(quelle: Path) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    """Lies alle Journale und gib (Saetze, behalten je Art, weggelassen je Art)."""
    redaktion = Redaktion()
    saetze: list[dict[str, Any]] = []
    behalten: Counter[str] = Counter()
    weg: Counter[str] = Counter()
    for datei in sorted(quelle.glob("*.jsonl")):
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                roh = json.loads(zeile)
            except json.JSONDecodeError:
                # Eine unlesbare Zeile wird gezaehlt, nicht verschwiegen.
                weg["<unlesbar>"] += 1
                continue
            art = str(roh.get("art", "<ohne art>"))
            if art not in BEHALTEN:
                weg[art] += 1
                continue
            behalten[art] += 1
            saetze.append(redaktion.satz(roh))
    return saetze, behalten, weg


def schreibform(
    saetze: list[dict[str, Any]], behalten: Counter[str], weg: Counter[str]
) -> str:
    kopf = {
        "art": "_kopf",
        "hinweis": (
            "Redigierte Aufzeichnung eines echten Demolaufs. Kennungen sind durch "
            "laufende Nummern ersetzt (nicht umkehrbar, kein Salz, keine gespeicherte "
            "Zuordnung). Erzeugt von tools/aufzeichnung_redigieren.py."
        ),
        "saetze_behalten": dict(sorted(behalten.items())),
        "saetze_weggelassen": dict(sorted(weg.items())),
        "weggelassen_gesamt": sum(weg.values()),
        "felder_weggelassen": sorted(FELDER_WEGLASSEN),
        "behalten_gesamt": sum(behalten.values()),
    }
    zeilen = [json.dumps(kopf, ensure_ascii=False, sort_keys=True)]
    zeilen += [json.dumps(s, ensure_ascii=False, sort_keys=True) for s in saetze]
    return "\n".join(zeilen) + "\n"


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pruefen", action="store_true",
                    help="nur melden, nichts schreiben (Rueckgabe 1 bei Abweichung)")
    args = ap.parse_args()

    ziel = ZIEL / "demo-2026-08-17.jsonl"
    if not QUELLE.is_dir():
        # Laut scheitern: ohne Quelle gibt es nichts zu redigieren, und ein leerer
        # Erfolg waere die schlechteste Auskunft.
        if args.pruefen and ziel.is_file():
            print(f"ok — {ziel.relative_to(ROOT).as_posix()} liegt vor; "
                  f"Quelle {QUELLE.name}/ fehlt (nichts nachzuziehen).")
            return 0
        print(f"FEHLGESCHLAGEN — Quelle {QUELLE} fehlt.", file=sys.stderr)
        return 1

    saetze, behalten, weg = redigiere(QUELLE)
    if not saetze:
        print(f"FEHLGESCHLAGEN — kein einziger Satz aus {QUELLE}.", file=sys.stderr)
        return 1
    inhalt = schreibform(saetze, behalten, weg)

    if args.pruefen:
        if not ziel.is_file():
            print(f"FEHLGESCHLAGEN — {ziel} fehlt.", file=sys.stderr)
            return 1
        if ziel.read_text(encoding="utf-8") != inhalt:
            print(f"FEHLGESCHLAGEN — {ziel} weicht von den Journalen ab.\n"
                  "Nachziehen mit: python tools/aufzeichnung_redigieren.py",
                  file=sys.stderr)
            return 1
        print(f"ok — {len(saetze)} redigierte Saetze, wortgleich mit den Journalen.")
        return 0

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8")
    print(f"geschrieben: {ziel.relative_to(ROOT).as_posix()}")
    print(f"  behalten    : {sum(behalten.values())} Saetze "
          f"({', '.join(f'{k} {v}' for k, v in sorted(behalten.items()))})")
    print(f"  weggelassen : {sum(weg.values())} Saetze "
          f"({', '.join(f'{k} {v}' for k, v in sorted(weg.items()))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

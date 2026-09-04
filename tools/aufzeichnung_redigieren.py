#!/usr/bin/env python3
"""Betriebsjournale zu redigierten Aufzeichnungen machen -- einchecken statt erzaehlen.

WARUM
-----
Stufe 5 des Altstands verlangte Ausfuehrungserfahrung **gegen die Demoumgebung**, „als
redigierte Aufzeichnungen einchecken", und in der Abnahme: *„mindestens eine echte,
aufgezeichnete Antwort des Handelsplatzes liegt im Repo"*.

Die Antworten existierten bereits -- 21 Journale mit 17.166 Saetzen aus einem echten
Demolauf am 2026-08-17. Sie lagen nur nicht **im Repo**: ``/betrieb/`` steht in
``.gitignore``, und das aus gutem Grund (Laufzeitdatenhalde, taeglich neu, mit
Kontonummer). Dieses Werkzeug schlaegt die Bruecke: es liest die Journale und schreibt
eine redigierte, verkleinerte Fassung nach ``aufzeichnungen/``, die eingecheckt wird.

Seit Auftrag 1 (Plan T6, Befund T) ist die Aufzeichnung ausserdem der **Gegenstand der
Dauertore**: zwoelf Tests, die vorher ``betrieb/`` lasen und sich auf jedem Klon
uebersprangen, lesen jetzt die Aufzeichnung und scheitern, wenn sie fehlt. Dafuer
muss sie tragen, was die Metriken lesen (``mt5_trading_ai/betrieb/dienstguete.py``):
``takt``-Saetze mit ``halt``, ``positionen`` und ``equity``, und je Satz eine
**stabile Laufkennung**.

WAS REDIGIERT WIRD -- UND WIE
-----------------------------
Ersetzt werden **fortlaufend nummeriert**, nicht gehasht::

    konto            -> KONTO-1
    order_id         -> ORDER-0001
    position_id      -> POSITION-01     (auch in takt.positionen[])
    client_order_id  -> KENNUNG-0001
    pfad             -> <entfernt>

Die Nummerierung ist **nicht umkehrbar**: es gibt kein Salz, keinen Schluessel und
keine gespeicherte Zuordnung. Ein Hash waere die schlechtere Wahl -- eine Kontonummer
hat so wenig Entropie, dass ein Hash davon in Sekunden zurueckgerechnet ist, und ein
gesalzener Hash braeuchte ein Salz, das irgendwo liegen muss. Die laufende Nummer
loest beides: sie haelt gleiche Werte gleich (die Aufzeichnung bleibt lesbar) und
traegt nichts vom Original in sich. Die Ersetzung laeuft **rekursiv** durch
verschachtelte Felder -- die Positionsliste eines Takts traegt dieselben Tickets wie
der ``eroeffnet``-Satz, und beide bekommen dieselbe Nummer.

Die **Laufkennung** ist anders gebaut, und mit Absicht: ``lauf`` wird nicht nach
erstem Auftreten nummeriert, sondern ist die laufende Nummer des **Journals in
Zeitreihenfolge** (``LAUF-01`` ... ``LAUF-21``), und sie steht an **jedem** Satz --
auch an den 17 von 21 Journalen, die noch keine Kennung schrieben. Damit ist ein Lauf
in der Aufzeichnung ansprechbar (``tests/test_laufabschluss.py`` nennt drei beim
Namen), und die Zuordnung Kennung -> Journalname steht im Kopf unter ``laeufe``. Sie
verraet nichts: der Journalname ist der Startzeitstempel, und der steht ohnehin im
``start``-Satz.

Erhalten bleiben Preise, Volumina, Zeitstempel, Symbole, Gruende, Codestaende und
Fehlertexte des Handelsplatzes. Das ist der Inhalt, um dessentwillen die Aufzeichnung
existiert.

WAS WEGGELASSEN WIRD -- UND WARUM ES DASTEHT
--------------------------------------------
Zwei Satzarten machen den Grossteil des Umfangs aus und tragen keine Auskunft ueber
eine Entscheidung: ``kurs`` und ``signal``. Sie werden weggelassen.

``takt`` wurde in der ersten Fassung ebenfalls weggelassen -- und damit war die
Aufzeichnung fuer Buchtreue und Ausstiegsdeckung unbrauchbar: beide Metriken lesen
Takte (``halt``, ``positionen``). ``eroeffnungsversuch`` fehlte in einer noch aelteren
Fassung; Begruendung an :data:`BEHALTEN`. Beide Male dieselbe Lehre: Umfang ist kein
Kriterium fuer Aussagekraft.

**Die Zahl der weggelassenen Saetze steht je Art im Kopf jeder Datei, ebenso die
weggelassenen und ersetzten Felder.** Eine stille Verkleinerung waere eine
Aufzeichnung, die vollstaendig aussieht und es nicht ist -- und genau das soll eine
Aufzeichnung nicht koennen.

DIE EIGENPRUEFUNG
-----------------
``pruefe_aufzeichnung`` haelt eine Aufzeichnung gegen ihren eigenen Kopf (Zaehlung je
Art, Laufkennung an jedem Satz, weggelassene Felder wirklich weg) und gegen die
Muster, die in einer redigierten Datei nicht vorkommen duerfen (:data:`UNREDIGIERT`).
Das Werkzeug **schreibt keine Aufzeichnung, die diese Pruefung nicht besteht**, und
``--pruefen`` faehrt sie auch ohne Quelle -- auf einem Klon ohne ``betrieb/`` ist das
die Pruefung, die bleibt. Liegen die Journale vor, kommt der Abgleich Byte fuer Byte
dazu.

Aufruf::

    python tools/aufzeichnung_redigieren.py                 # schreibt aufzeichnungen/
    python tools/aufzeichnung_redigieren.py --pruefen       # meldet nur Abweichungen
    python tools/aufzeichnung_redigieren.py --quelle <ordner> --ziel <datei>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QUELLE = ROOT / "betrieb"
ZIEL = ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl"

#: Fassung des Kopfes. 1: ohne ``takt``, Laufkennung nach erstem Auftreten. 2: mit
#: ``takt``, Laufkennung je Journal in Zeitreihenfolge, Felder ausgewiesen.
FASSUNG = 2
KOPF_ART = "_kopf"

#: Satzarten, die eine Antwort des Handelsplatzes oder eine Zustandsaenderung tragen
#: -- oder die eine Metrik liest. Alles andere ist Messrauschen des Laufs.
BEHALTEN: frozenset[str] = frozenset(
    {
        # Nachtrag Stufe 7 des Altstands: ``eroeffnungsversuch`` stand hier zuerst
        # NICHT drin -- in Stufe 5 als Messrauschen weggelassen, weil er 4.343 der
        # 17.166 Saetze ausmacht. Das war falsch, und zwar auf eine Weise, die erst
        # eine Stufe spaeter auffiel: die Abnahme der Stufe 7 verlangt ausdruecklich,
        # dass die Auswertungstabelle „gekennzeichnete Zeilen aus abgelehnten
        # Signalen" enthaelt. Genau diese Saetze tragen die 4.311 Absagen samt Grund.
        # Eine Verkleinerung, die den Umfang nach Haeufigkeit beurteilt statt nach
        # Aussagekraft, wirft das Seltene weg und behaelt das Laute.
        "eroeffnungsversuch",
        # Nachtrag Auftrag 1 (T6, Befund T): ``takt`` fehlte aus demselben Grund --
        # 1.360 Saetze -- und damit fehlten der Aufzeichnung ``halt``, ``positionen``
        # und ``equity``, also alles, woraus Buchtreue, Ausstiegsdeckung und die
        # Equity-Reihe gerechnet werden. Die Dauertore konnten sie nicht lesen und
        # lasen stattdessen das gitignorierte ``betrieb/`` -- auf jedem Klon ein Skip.
        "takt",
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
}

#: Die Laufkennung: laufende Nummer des Journals in Zeitreihenfolge, an jedem Satz.
LAUF_FELD = "lauf"
LAUF_PRAEFIX = "LAUF"
LAUF_BREITE = 2
LAUF_MUSTER = re.compile(rf"{LAUF_PRAEFIX}-\d{{{LAUF_BREITE},}}")

#: Felder, deren Wert ersatzlos verschwindet. Ein Pfad traegt den Benutzernamen und
#: sagt ueber den Handelsplatz nichts.
ENTFERNEN: frozenset[str] = frozenset({"pfad"})
ENTFERNT = "<entfernt>"

#: Felder, die ganz wegfallen -- **nach Aussagekraft, nicht nach Umfang.**
#:
#: ``schritte`` traegt die Naht-fuer-Naht-Liste eines Eroeffnungsversuchs. Was daraus
#: fuer eine Auswertung zaehlt, ist die erste rote Naht -- und die steht bereits als
#: ``grund`` im selben Satz. Die uebrigen Eintraege sind die gruenen Nahte davor:
#: Diagnose ueber den Weg, nicht ueber die Entscheidung. Ausserdem tragen 32 der
#: 36.366 ``detail``-Texte darin Ticketnummern im Klartext.
#:
#: Dass es zugleich 72 % des Umfangs spart, ist ein willkommener Nebeneffekt und
#: ausdruecklich **nicht** die Begruendung.
FELDER_WEGLASSEN: frozenset[str] = frozenset({"schritte"})

#: Muster, die in einer redigierten Aufzeichnung NICHT vorkommen duerfen -- geprueft
#: am rohen Text, nicht an den Feldern, damit auch ein Wert in einem unbekannten Feld
#: auffaellt. Name -> Muster.
UNREDIGIERT: dict[str, str] = {
    "Ziffernfolge (Kontonummer/Ticket)": r"\b\d{6,12}\b",
    "Windows-Pfad": r"[A-Za-z]:\\\\",
    "Original-Auftragskennung": r'"(?:open|close|fl)-[^"]*"',
    "Hex-Laufkennung": r"\b[0-9a-f]{32}\b",
}

HINWEIS = (
    "Redigierte Aufzeichnung eines echten Demolaufs. Konto-, Order-, Positions- und "
    "Auftragskennungen sind durch laufende Nummern ersetzt (nicht umkehrbar, kein "
    "Salz, keine gespeicherte Zuordnung). 'lauf' ist die laufende Nummer des Journals "
    "in Zeitreihenfolge; 'laeufe' bildet sie auf den Journalnamen ab. Erzeugt von "
    "tools/aufzeichnung_redigieren.py."
)


class Redaktion:
    """Vergibt laufende Nummern je Feld und haelt gleiche Werte gleich."""

    def __init__(self) -> None:
        self._zuordnung: dict[tuple[str, str], str] = {}
        self._zaehler: Counter[str] = Counter()
        self.felder_weggelassen: Counter[str] = Counter()
        self.felder_entfernt: Counter[str] = Counter()

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

    def satz(self, roh: dict[str, Any], lauf: str) -> dict[str, Any]:
        """Ein Satz, redigiert -- mit der Laufkennung des Journals an jedem Satz."""
        aus = self._redigiere(roh)
        aus[LAUF_FELD] = lauf
        return aus

    def _redigiere(self, roh: dict[str, Any]) -> dict[str, Any]:
        aus: dict[str, Any] = {}
        for k, v in roh.items():
            if k in FELDER_WEGLASSEN:
                self.felder_weggelassen[k] += 1
                continue
            if k == LAUF_FELD:
                continue  # setzt ``satz``: je Journal, nicht je Wert
            if k in ENTFERNEN:
                self.felder_entfernt[k] += 1
                aus[k] = ENTFERNT
            elif k in KENNUNGSFELDER and v is not None:
                aus[k] = self.ersetze(k, v)
            else:
                aus[k] = self._wert(v)
        return aus

    def _wert(self, v: Any) -> Any:
        if isinstance(v, dict):
            return self._redigiere(v)
        if isinstance(v, list):
            return [self._wert(x) for x in v]
        return v

    @property
    def vergeben(self) -> dict[str, int]:
        """Vergebene Nummern je Feld -- die Zahl der VERSCHIEDENEN Originalwerte."""
        return dict(self._zaehler)


@dataclass
class Ergebnis:
    """Was die Redaktion hervorgebracht hat -- Saetze und die Zaehlung dazu."""

    saetze: list[dict[str, Any]]
    behalten: Counter[str]
    weggelassen: Counter[str]
    #: Laufkennung -> Journalname, in Zeitreihenfolge.
    laeufe: dict[str, str]
    felder_weggelassen: Counter[str]
    felder_entfernt: Counter[str]
    felder_ersetzt: dict[str, int]
    quelle_saetze: int


def journale(quelle: Path) -> list[Path]:
    """Die Journale unter ``quelle`` in Zeitreihenfolge -- leer, wenn es keine gibt.

    Sortiert nach dem ersten Zeitstempel der Datei, dann nach Namen. Die Namen tragen
    denselben Zeitstempel, aber die Zeitreihenfolge ist die Zusage, nicht der Name.
    """
    if not quelle.is_dir():
        return []

    def schluessel(pfad: Path) -> tuple[str, str]:
        with pfad.open(encoding="utf-8") as fh:
            for zeile in fh:
                zeile = zeile.strip()
                if zeile:
                    try:
                        return str(json.loads(zeile).get("ts", "")), pfad.name
                    except (json.JSONDecodeError, AttributeError):
                        return "", pfad.name
        return "", pfad.name

    return sorted(quelle.glob("journal-*.jsonl"), key=schluessel)


def redigiere(dateien: Sequence[Path]) -> Ergebnis:
    """Lies die Journale (in der gegebenen Reihenfolge) und redigiere sie."""
    redaktion = Redaktion()
    saetze: list[dict[str, Any]] = []
    behalten: Counter[str] = Counter()
    weg: Counter[str] = Counter()
    laeufe: dict[str, str] = {}
    quelle_saetze = 0
    for nr, datei in enumerate(dateien, 1):
        kennung = f"{LAUF_PRAEFIX}-{nr:0{LAUF_BREITE}d}"
        laeufe[kennung] = datei.name
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            quelle_saetze += 1
            try:
                roh = json.loads(zeile)
            except json.JSONDecodeError:
                # Eine unlesbare Zeile wird gezaehlt, nicht verschwiegen.
                weg["<unlesbar>"] += 1
                continue
            if not isinstance(roh, dict):
                weg["<kein Objekt>"] += 1
                continue
            art = str(roh.get("art", "<ohne art>"))
            if art not in BEHALTEN:
                weg[art] += 1
                continue
            behalten[art] += 1
            saetze.append(redaktion.satz(roh, kennung))
    ersetzt = dict(redaktion.vergeben)
    ersetzt[LAUF_FELD] = len(laeufe)
    return Ergebnis(
        saetze=saetze,
        behalten=behalten,
        weggelassen=weg,
        laeufe=laeufe,
        felder_weggelassen=redaktion.felder_weggelassen,
        felder_entfernt=redaktion.felder_entfernt,
        felder_ersetzt=ersetzt,
        quelle_saetze=quelle_saetze,
    )


def schreibform(ergebnis: Ergebnis) -> str:
    kopf = {
        "art": KOPF_ART,
        "fassung": FASSUNG,
        "hinweis": HINWEIS,
        "quelle": {
            "journale": len(ergebnis.laeufe),
            "saetze": ergebnis.quelle_saetze,
        },
        "laeufe": ergebnis.laeufe,
        "saetze_behalten": dict(sorted(ergebnis.behalten.items())),
        "behalten_gesamt": sum(ergebnis.behalten.values()),
        "saetze_weggelassen": dict(sorted(ergebnis.weggelassen.items())),
        "weggelassen_gesamt": sum(ergebnis.weggelassen.values()),
        "felder_weggelassen": dict(sorted(ergebnis.felder_weggelassen.items())),
        "felder_entfernt": dict(sorted(ergebnis.felder_entfernt.items())),
        "felder_ersetzt": dict(sorted(ergebnis.felder_ersetzt.items())),
    }
    zeilen = [json.dumps(kopf, ensure_ascii=False, sort_keys=True)]
    zeilen += [
        json.dumps(s, ensure_ascii=False, sort_keys=True) for s in ergebnis.saetze
    ]
    return "\n".join(zeilen) + "\n"


def _schluessel(obj: Any) -> set[str]:
    """Alle Feldnamen eines Satzes, auch die verschachtelten."""
    aus: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            aus.add(str(k))
            aus |= _schluessel(v)
    elif isinstance(obj, list):
        for v in obj:
            aus |= _schluessel(v)
    return aus


def pruefe_aufzeichnung(text: str) -> list[str]:
    """Befunde gegen den eigenen Kopf und gegen :data:`UNREDIGIERT`. Leer = bestanden.

    Ein Befund nennt Zeile und Zahl, nie den gefundenen Wert -- der waere in einer
    Fehlermeldung genauso im Klartext wie in der Datei.
    """
    befunde: list[str] = []
    zeilen = [z for z in text.splitlines() if z.strip()]
    if not zeilen:
        return ["die Aufzeichnung ist leer"]
    try:
        kopf = json.loads(zeilen[0])
    except json.JSONDecodeError:
        return ["Zeile 1 ist kein JSON"]
    if not isinstance(kopf, dict) or kopf.get("art") != KOPF_ART:
        return [f"Zeile 1 ist keine Kopfzeile (art != {KOPF_ART!r})"]
    if kopf.get("fassung") != FASSUNG:
        befunde.append(f"Kopf-Fassung {kopf.get('fassung')!r}, erwartet {FASSUNG}")

    arten: Counter[str] = Counter()
    laeufe_gesehen: Counter[str] = Counter()
    ohne_lauf: list[int] = []
    verbotene_felder: Counter[str] = Counter()
    for nr, zeile in enumerate(zeilen[1:], 2):
        try:
            satz = json.loads(zeile)
        except json.JSONDecodeError:
            befunde.append(f"Zeile {nr} ist kein JSON")
            continue
        if not isinstance(satz, dict):
            befunde.append(f"Zeile {nr} ist kein Objekt")
            continue
        art = str(satz.get("art", "<ohne art>"))
        if art == KOPF_ART:
            befunde.append(f"Zeile {nr}: zweite Kopfzeile")
            continue
        arten[art] += 1
        lauf = satz.get(LAUF_FELD)
        if isinstance(lauf, str) and LAUF_MUSTER.fullmatch(lauf):
            laeufe_gesehen[lauf] += 1
        else:
            ohne_lauf.append(nr)
        for feld in _schluessel(satz) & FELDER_WEGLASSEN:
            verbotene_felder[feld] += 1

    if dict(arten) != kopf.get("saetze_behalten"):
        befunde.append(
            f"saetze_behalten im Kopf {kopf.get('saetze_behalten')} != gezaehlt "
            f"{dict(sorted(arten.items()))}"
        )
    if sum(arten.values()) != kopf.get("behalten_gesamt"):
        befunde.append(
            f"behalten_gesamt im Kopf {kopf.get('behalten_gesamt')!r} != "
            f"gezaehlt {sum(arten.values())}"
        )
    weggelassen = kopf.get("saetze_weggelassen")
    if not isinstance(weggelassen, dict):
        befunde.append("saetze_weggelassen fehlt im Kopf")
    else:
        doppelt = sorted(set(arten) & set(weggelassen))
        if doppelt:
            befunde.append(f"Arten sowohl behalten als auch weggelassen: {doppelt}")
        if sum(int(v) for v in weggelassen.values()) != kopf.get("weggelassen_gesamt"):
            befunde.append("weggelassen_gesamt im Kopf stimmt nicht mit der Summe")
    felder_weg = kopf.get("felder_weggelassen")
    if not isinstance(felder_weg, dict) or set(felder_weg) != set(FELDER_WEGLASSEN):
        befunde.append(
            f"felder_weggelassen im Kopf {felder_weg!r} != {sorted(FELDER_WEGLASSEN)}"
        )
    for feld, n in sorted(verbotene_felder.items()):
        befunde.append(f"Feld {feld!r} steht noch in {n} Saetzen")
    if ohne_lauf:
        befunde.append(
            f"{len(ohne_lauf)} Saetze ohne Laufkennung {LAUF_PRAEFIX}-nn "
            f"(zuerst Zeile {ohne_lauf[0]})"
        )
    laeufe_kopf = kopf.get("laeufe")
    if not isinstance(laeufe_kopf, dict) or not laeufe_kopf:
        befunde.append("laeufe (Kennung -> Journal) fehlt im Kopf")
    else:
        fehlend = sorted(set(laeufe_kopf) - set(laeufe_gesehen))
        fremd = sorted(set(laeufe_gesehen) - set(laeufe_kopf))
        if fehlend:
            befunde.append(f"Laeufe im Kopf ohne Satz: {fehlend}")
        if fremd:
            befunde.append(f"Laufkennungen ohne Eintrag im Kopf: {fremd}")
    for name, muster in UNREDIGIERT.items():
        treffer = [nr for nr, z in enumerate(zeilen, 1) if re.search(muster, z)]
        if treffer:
            befunde.append(
                f"{name}: {len(treffer)} Zeile(n), zuerst Zeile {treffer[0]} -- "
                "unredigiert"
            )
    return befunde


def pruefen(ziel: Path, quelle: Path) -> int:
    """``--pruefen``: Eigenpruefung immer; Abgleich gegen die Journale, wenn es sie
    gibt."""
    rel = ziel.relative_to(ROOT).as_posix() if ziel.is_relative_to(ROOT) else str(ziel)
    if not ziel.is_file():
        print(f"FEHLGESCHLAGEN — {rel} fehlt.", file=sys.stderr)
        return 1
    text = ziel.read_text(encoding="utf-8")
    befunde = pruefe_aufzeichnung(text)
    if befunde:
        print(
            f"FEHLGESCHLAGEN — {rel} besteht die Eigenpruefung nicht "
            f"({len(befunde)} Befunde):",
            file=sys.stderr,
        )
        for b in befunde:
            print(f"  {b}", file=sys.stderr)
        return 1
    kopf = json.loads(text.splitlines()[0])
    dateien = journale(quelle)
    if not dateien:
        print(
            f"ok — {rel} eigengeprueft: {kopf['behalten_gesamt']} Saetze in "
            f"{len(kopf['laeufe'])} Laeufen, Kopf und Inhalt stimmen ueberein, keine "
            f"unredigierten Muster. Quelle {quelle.name}/ fehlt -- der Abgleich gegen "
            "die Journale ist hier nicht moeglich."
        )
        return 0
    inhalt = schreibform(redigiere(dateien))
    if text != inhalt:
        print(
            f"FEHLGESCHLAGEN — {rel} weicht von den {len(dateien)} Journalen ab.\n"
            "Nachziehen mit: python tools/aufzeichnung_redigieren.py",
            file=sys.stderr,
        )
        return 1
    print(
        f"ok — {rel}: {kopf['behalten_gesamt']} redigierte Saetze in "
        f"{len(dateien)} Laeufen, wortgleich mit den Journalen; Eigenpruefung ohne "
        "Befund."
    )
    return 0


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="Betriebsjournale zu einer redigierten Aufzeichnung machen."
    )
    ap.add_argument(
        "--quelle",
        type=Path,
        default=QUELLE,
        help="Ordner mit journal-*.jsonl (Vorgabe: betrieb/)",
    )
    ap.add_argument(
        "--ziel",
        type=Path,
        default=ZIEL,
        help="Aufzeichnungsdatei (Vorgabe: aufzeichnungen/demo-2026-08-17.jsonl)",
    )
    ap.add_argument(
        "--pruefen",
        action="store_true",
        help="nur pruefen, nichts schreiben (Rueckgabe 1 bei Abweichung oder Befund)",
    )
    args = ap.parse_args()

    if args.pruefen:
        return pruefen(args.ziel, args.quelle)

    dateien = journale(args.quelle)
    if not dateien:
        # Laut scheitern: ohne Quelle gibt es nichts zu redigieren, und ein leerer
        # Erfolg waere die schlechteste Auskunft.
        print(
            f"FEHLGESCHLAGEN — kein journal-*.jsonl unter {args.quelle}.",
            file=sys.stderr,
        )
        return 1
    ergebnis = redigiere(dateien)
    if not ergebnis.saetze:
        print(
            f"FEHLGESCHLAGEN — kein einziger Satz aus {len(dateien)} Journalen.",
            file=sys.stderr,
        )
        return 1
    inhalt = schreibform(ergebnis)
    befunde = pruefe_aufzeichnung(inhalt)
    if befunde:
        # Fail-closed: eine Aufzeichnung, die die eigene Pruefung nicht besteht, wird
        # nicht geschrieben -- sonst laege ein unredigierter Wert im Repo, und die
        # Meldung darueber kaeme zu spaet.
        print(
            f"FEHLGESCHLAGEN — nichts geschrieben; die Redaktion besteht die "
            f"Eigenpruefung nicht ({len(befunde)} Befunde):",
            file=sys.stderr,
        )
        for b in befunde:
            print(f"  {b}", file=sys.stderr)
        return 1

    args.ziel.parent.mkdir(parents=True, exist_ok=True)
    with args.ziel.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(inhalt)
    rel = (
        args.ziel.relative_to(ROOT).as_posix()
        if args.ziel.is_relative_to(ROOT)
        else str(args.ziel)
    )
    print(f"geschrieben: {rel}")
    print(f"  Quelle      : {len(dateien)} Journale, {ergebnis.quelle_saetze} Saetze")
    print(
        f"  behalten    : {sum(ergebnis.behalten.values())} Saetze "
        f"({', '.join(f'{k} {v}' for k, v in sorted(ergebnis.behalten.items()))})"
    )
    print(
        f"  weggelassen : {sum(ergebnis.weggelassen.values())} Saetze "
        f"({', '.join(f'{k} {v}' for k, v in sorted(ergebnis.weggelassen.items()))})"
    )
    print(
        f"  Felder      : weggelassen {dict(ergebnis.felder_weggelassen)}, "
        f"entfernt {dict(ergebnis.felder_entfernt)}, "
        f"ersetzt {ergebnis.felder_ersetzt}"
    )
    print(f"  Laeufe      : {', '.join(ergebnis.laeufe)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Betriebsjournale lesen -- die eine Stelle, an der aus Zeilen Aussagen werden.

WARUM DIESES MODUL
------------------
Bis hierher las jedes Werkzeug das Journal fuer sich: ``betrieb_auswerten.py`` nahm
``kandidaten[-1]``, ``oberflaeche.py`` ebenfalls ``dateien[-1]``, und beide bauten ihre
Zaehlungen aus rohen Woerterbuechern. Zwei Umsetzungen derselben Rechnung sind zwei
Fehlerquellen -- dieselbe Lehre wie beim Kostentor in Paket 3a.

Vor allem aber war **keine einzige Zeile davon getestet**, waehrend die CI
``mypy --strict`` ueber ``tools/`` faehrt. Eine Auswertung ohne Test ist eine Zahl, die
man nicht zitieren kann.

WAS EIN TRADE IST -- UND WAS DIE ZAHL WERT IST
----------------------------------------------
Ein Trade entsteht aus zwei Ereignissen, die ueber ``position_id`` zusammenfinden:
``eroeffnet`` und ``geschlossen`` (oder ``vom_broker_geschlossen``, wenn der Stop lief).

Das daraus **gerechnete** Ergebnis ist die Preisdifferenz mal Volumen. Es ist
ausdruecklich **nicht** das gebuchte Ergebnis: Kommission und Swap fehlen, und der
Ausstiegspreis eines broker-seitigen Schlusses ist gar nicht bekannt. Darum traegt
jeder Trade ein Feld ``vollstaendig``, und die Auswertung sagt, wie viele es sind.
Wer die gebuchte Zahl will, braucht ``history_deals_get`` -- die gibt es hier nicht.

ZWEI SORTEN ERGEBNIS -- UND WARUM SIE GETRENNT BLEIBEN
-------------------------------------------------------
Ein broker-seitiger Schluss (Stop-Out) liefert **keinen Fuellpreis**. Damit war
``ergebnis_bps`` dort ``None``, und der Trade fiel aus Median, Trefferanteil und jeder
Bestenliste heraus. Das traf nicht irgendwelche Trades, sondern **die Verlierer** --
ein blinder Fleck in bekannter Richtung, gemessen am Lauf vom 17.08.2026: "Trades mit
rechenbarem Ergebnis: 0 von 1".

Was ein solcher Satz sehr wohl traegt, ist der zuletzt beobachtete Buchwert der
Position. Er kommt hier als ``ergebnis_geld`` an -- **in Kontowaehrung, nicht als
Preis**, und ausdruecklich als Schaetzung des Betrags:

* Der **Betrag** stammt vom Ende des vorigen Takts, also bis zu einen Takt vor dem
  wirklichen Schluss, und laesst Swap und Kommission draussen. Er gehoert in keinen
  Median.
* Das **Vorzeichen** dagegen ist die belastbare Auskunft. Genau sie fehlte, und genau
  sie entscheidet ueber den Trefferanteil.

Darum: ``ergebnis_bps`` bleibt das Preisergebnis und bekommt nichts hinzugerechnet;
``gewinn`` beantwortet die Ja/Nein-Frage und nimmt dafuer notfalls das Geldergebnis.
``None`` heisst an beiden Stellen **unbekannt** und nie null.

Was dagegen belastbar ist: die **Equity-Reihe**. Sie kommt aus dem Kontostand je Takt
und haengt ueber Laeufe hinweg lueckenlos aneinander.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

JOURNAL_LESER_VERSION = "journal-leser-v1"

#: Herkunftsmarke fuer ein Geldergebnis, das der Schreiber ALS ERGEBNIS gemeint hat.
#: Sie steht so im Journal; der Leser gibt sie nur weiter.
QUELLE_BEOBACHTET = "zuletzt_beobachtet"

#: Herkunftsmarke fuer ein Geldergebnis, das der Leser aus einem ALTEN Journal DEUTET.
#: Dort steht nur ``zuletzt_unrealisiert`` -- eine Beobachtung ohne Deutung, weil es
#: das Ergebnisfeld beim Schreiben noch nicht gab. Das Journal ist anhaengend
#: (Kernregel 22); alte Saetze werden nicht umgeschrieben, also faellt die Deutung
#: hier. Sie faellt aber SICHTBAR: die Marke reist am Trade mit, statt dass sich eine
#: gedeutete Zahl als geschriebene ausgibt.
QUELLE_ALTJOURNAL = "altjournal:zuletzt_unrealisiert"


class JournalError(ValueError):
    """Das Journal ist nicht lesbar. Fail-closed: keine halbe Auswertung."""


def _dezimal(wert: Any) -> Decimal | None:
    if wert is None:
        return None
    try:
        return Decimal(str(wert))
    except (InvalidOperation, TypeError):
        return None


def _zeit(wert: Any) -> datetime | None:
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert))
    except ValueError:
        return None


@dataclass(frozen=True)
class Satz:
    """Eine Journalzeile."""

    ts: datetime
    art: str
    lauf: str | None
    version: str | None
    felder: dict[str, Any]

    def __getitem__(self, name: str) -> Any:
        return self.felder.get(name)


def _geldergebnis(satz: Satz) -> tuple[Decimal | None, str | None, str | None]:
    """(Betrag, Waehrung, Herkunft) eines Geldergebnisses -- oder dreimal ``None``.

    Dreimal ``None`` heisst **unbekannt**. Es heisst nicht null: ein Schlusssatz aus
    einem alten Lauf, der weder das Ergebnisfeld noch den Buchwert trug, gibt keinen
    Betrag her, und ein geratener Nullwert waere die schmeichelnde Richtung -- er
    zoege jeden Median und jeden Trefferanteil zur Mitte, ohne dass es jemand saehe.

    Der geschriebene Wert hat Vorrang vor der Deutung: steht ``ergebnis_geld`` da, hat
    der Schreiber die Zahl ALS ERGEBNIS gemeint und ihre Herkunft dazugeschrieben.
    Fehlt es, bleibt nur ``zuletzt_unrealisiert`` aus einem Journal von vor dieser
    Erweiterung. Der Wert ist derselbe Buchwert, aber die Deutung faellt dann hier --
    und wird als ``QUELLE_ALTJOURNAL`` mitgefuehrt, damit die Auswertung die beiden
    Faelle auseinanderhalten kann.
    """
    wert = _dezimal(satz["ergebnis_geld"])
    if wert is not None:
        waehrung = satz["ergebnis_geld_waehrung"]
        quelle = satz["ergebnis_geld_quelle"]
        return (
            wert,
            None if waehrung is None else str(waehrung),
            "unbenannt" if quelle is None else str(quelle),
        )
    alt = _dezimal(satz["zuletzt_unrealisiert"])
    if alt is not None:
        return alt, None, QUELLE_ALTJOURNAL
    return None, None, None


@dataclass(frozen=True)
class Trade:
    """Eine Position von der Eroeffnung bis zum Schluss."""

    symbol: str
    ist_kauf: bool
    volumen: Decimal
    auf_ts: datetime
    einstieg: Decimal | None
    zu_ts: datetime | None = None
    ausstieg: Decimal | None = None
    grund: str | None = None
    position_id: str | None = None
    vom_broker: bool = False
    #: Ergebnis in KONTOWAEHRUNG -- und ausdruecklich kein Preis. Bei einem
    #: broker-seitigen Schluss ist der Fuellpreis nicht bekannt; bekannt ist der
    #: zuletzt beobachtete Buchwert der Position. Brutto: ohne Swap, ohne Kommission.
    ergebnis_geld: Decimal | None = None
    #: Ohne Waehrung ist der Betrag nicht deutbar. ``None`` heisst: nicht mitgeteilt
    #: (alte Journale) -- dann darf ueber mehrere Trades nicht summiert werden.
    ergebnis_geld_waehrung: str | None = None
    #: Woher der Betrag kommt (``QUELLE_BEOBACHTET`` / ``QUELLE_ALTJOURNAL``).
    #: ``None`` heisst: es gibt keinen.
    ergebnis_geld_quelle: str | None = None

    @property
    def offen(self) -> bool:
        return self.zu_ts is None

    @property
    def vollstaendig(self) -> bool:
        """Laesst sich ein PREIS-Ergebnis rechnen? Nur mit beiden Preisen.

        Bewusst unveraendert eng gelassen: ``vollstaendig`` heisst weiterhin "beide
        Preise gemessen". Ein Geldergebnis macht einen Trade **beurteilbar**, aber
        nicht vollstaendig -- wer die beiden Begriffe zusammenlegte, liesse eine
        Schaetzung in jeder Zahl mitlaufen, die bisher nur gemessene Preise kannte.
        """
        return self.einstieg is not None and self.ausstieg is not None

    @property
    def dauer_stunden(self) -> float | None:
        if self.zu_ts is None:
            return None
        return (self.zu_ts - self.auf_ts).total_seconds() / 3600

    @property
    def ergebnis_bps(self) -> Decimal | None:
        """Preisergebnis in Basispunkten. **Ohne** Kommission und Swap.

        Die Richtung wird beruecksichtigt: ein Verkauf gewinnt bei fallendem Kurs.
        """
        if not self.vollstaendig or self.einstieg is None or self.ausstieg is None:
            return None
        if self.einstieg <= 0:
            return None
        roh = (self.ausstieg - self.einstieg) / self.einstieg * Decimal("10000")
        return roh if self.ist_kauf else -roh

    @property
    def urteilsquelle(self) -> str | None:
        """``"preis"``, ``"geld"`` oder ``None``. Womit ueber den Trade geurteilt wird.

        Der Preis hat Vorrang: er ist am Ausstieg gemessen. Das Geldergebnis ist die
        letzte Beobachtung davor. Die Auswertung muss beides auseinanderhalten
        koennen, sonst steht am Ende eine Trefferquote da, der man nicht ansieht, wie
        viel Schaetzung in ihr steckt.
        """
        if self.ergebnis_bps is not None:
            return "preis"
        if self.ergebnis_geld is not None:
            return "geld"
        return None

    @property
    def gewinn(self) -> bool | None:
        """Ging der Trade auf? ``None`` heisst UNBEKANNT -- nicht null, nicht Verlust.

        Fuer einen broker-seitigen Schluss gibt es keinen Fuellpreis, also kein
        ``ergebnis_bps``. Bisher fiel er damit aus jedem Trefferanteil heraus -- und
        weil broker-seitige Schluesse ueberwiegend Stop-Outs sind, fielen ausgerechnet
        die Verlierer heraus. Der Anteil sah besser aus, als er war, und niemand
        konnte es der Zahl ansehen.

        Das Geldergebnis repariert genau diese Frage und nur sie: sein Betrag ist eine
        Schaetzung, sein Vorzeichen ist die Auskunft. Darum steht es hier und nicht in
        ``ergebnis_bps``.
        """
        bps = self.ergebnis_bps
        if bps is not None:
            return bps > 0
        if self.ergebnis_geld is not None:
            return self.ergebnis_geld > 0
        return None

    @property
    def beurteilbar(self) -> bool:
        """Laesst sich ueberhaupt sagen, ob der Trade aufging?"""
        return self.gewinn is not None


@dataclass
class Lauf:
    """Ein Betriebslauf: eine Journaldatei."""

    pfad: Path
    saetze: list[Satz] = field(default_factory=list)

    # -- Kopfdaten ---------------------------------------------------------
    @property
    def lauf_id(self) -> str | None:
        for s in self.saetze:
            if s.lauf:
                return s.lauf
        return None

    @property
    def version(self) -> str | None:
        for s in self.saetze:
            if s.version:
                return s.version
        return None

    def _erster(self, art: str) -> Satz | None:
        return next((s for s in self.saetze if s.art == art), None)

    @property
    def start(self) -> Satz | None:
        return self._erster("start")

    @property
    def ende(self) -> Satz | None:
        return self._erster("ende")

    @property
    def scharf(self) -> bool:
        start = self.start
        return bool(start and start["scharf"])

    @property
    def beendet(self) -> bool:
        """Wurde der Lauf geordnet beendet? Sonst fehlt der Endeintrag."""
        return self.ende is not None

    def art(self, name: str) -> list[Satz]:
        return [s for s in self.saetze if s.art == name]

    # -- Reihen ------------------------------------------------------------
    def equity_reihe(self) -> list[tuple[datetime, Decimal]]:
        """(Zeit, Equity) je Takt. Die belastbarste Reihe im Journal."""
        aus: list[tuple[datetime, Decimal]] = []
        for s in self.art("takt"):
            wert = _dezimal(s["equity"])
            if wert is not None:
                aus.append((s.ts, wert))
        return aus

    def kurs_reihe(self, symbol: str) -> list[tuple[datetime, Decimal]]:
        """(Zeit, Mittelkurs) je Takt fuer ein Instrument."""
        aus: list[tuple[datetime, Decimal]] = []
        for s in self.art("kurs"):
            if s["symbol"] != symbol:
                continue
            bid, ask = _dezimal(s["bid"]), _dezimal(s["ask"])
            if bid is not None and ask is not None:
                aus.append((s.ts, (bid + ask) / 2))
        return aus

    def symbole_mit_kursen(self) -> list[str]:
        return sorted({str(s["symbol"]) for s in self.art("kurs") if s["symbol"]})

    # -- Trades ------------------------------------------------------------
    def trades(self) -> list[Trade]:
        """Eroeffnungen und Schliessungen ueber ``position_id`` zusammenfuehren.

        Ohne Positions-ID (Journale vor der Protokollerweiterung) faellt die Zuordnung
        auf das Symbol zurueck: die aelteste offene Position desselben Symbols wird
        geschlossen. Das ist eine **Annahme**, und sie steht hier, weil ein Journal
        ohne ID sonst gar keinen Trade hergaebe.
        """
        offen: dict[str, list[Trade]] = {}
        fertig: list[Trade] = []

        def schluessel(satz: Satz) -> str:
            return str(satz["position_id"] or f"symbol:{satz['symbol']}")

        for s in self.saetze:
            if s.art == "eroeffnet":
                t = Trade(
                    symbol=str(s["symbol"]),
                    ist_kauf=str(s["signal"]).upper() != "SHORT",
                    volumen=_dezimal(s["volumen"]) or Decimal("0"),
                    auf_ts=_zeit(s["seit"]) or s.ts,
                    einstieg=_dezimal(s["einstiegspreis"]),
                    position_id=None if s["position_id"] is None
                    else str(s["position_id"]),
                )
                offen.setdefault(schluessel(s), []).append(t)
            elif s.art in ("geschlossen", "vom_broker_geschlossen"):
                geld, waehrung, quelle = _geldergebnis(s)
                kandidaten = offen.get(schluessel(s)) or offen.get(
                    f"symbol:{s['symbol']}"
                )
                if not kandidaten:
                    # Schluss ohne bekannte Eroeffnung: der Lauf hat die Position beim
                    # Start uebernommen (adopt_book journalisiert nicht).
                    fertig.append(Trade(
                        symbol=str(s["symbol"]),
                        ist_kauf=bool(s["war_kauf"]),
                        volumen=_dezimal(s["volumen"]) or Decimal("0"),
                        auf_ts=_zeit(s["seit"]) or s.ts,
                        einstieg=_dezimal(s["einstiegspreis"]),
                        zu_ts=s.ts, ausstieg=_dezimal(s["ausstiegspreis"]),
                        grund=str(s["grund"] or "uebernommen"),
                        vom_broker=s.art == "vom_broker_geschlossen",
                        ergebnis_geld=geld, ergebnis_geld_waehrung=waehrung,
                        ergebnis_geld_quelle=quelle,
                    ))
                    continue
                t = kandidaten.pop(0)
                fertig.append(Trade(
                    symbol=t.symbol, ist_kauf=t.ist_kauf, volumen=t.volumen,
                    auf_ts=t.auf_ts,
                    einstieg=t.einstieg or _dezimal(s["einstiegspreis"]),
                    zu_ts=s.ts, ausstieg=_dezimal(s["ausstiegspreis"]),
                    grund=str(s["grund"] or "?"), position_id=t.position_id,
                    vom_broker=s.art == "vom_broker_geschlossen",
                    ergebnis_geld=geld, ergebnis_geld_waehrung=waehrung,
                    ergebnis_geld_quelle=quelle,
                ))
        for rest in offen.values():
            fertig.extend(rest)
        return sorted(fertig, key=lambda t: t.auf_ts)


def lies_journal(pfad: Path) -> Lauf:
    """Eine Journaldatei lesen. Unlesbare Zeilen sind ein Fehler, kein Ueberspringen.

    Eine stillschweigend uebersprungene Zeile ist die schlimmste Sorte Datenverlust:
    die Auswertung sieht vollstaendig aus und ist es nicht.
    """
    if not pfad.is_file():
        raise JournalError(f"{pfad} gibt es nicht")
    saetze: list[Satz] = []
    for nr, roh in enumerate(pfad.read_text(encoding="utf-8", errors="replace")
                             .splitlines(), 1):
        roh = roh.strip()
        if not roh:
            continue
        try:
            d = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{pfad.name}:{nr} ist kein JSON: {exc}") from exc
        if not isinstance(d, dict) or "ts" not in d or "art" not in d:
            raise JournalError(f"{pfad.name}:{nr}: ts oder art fehlt")
        ts = _zeit(d["ts"])
        if ts is None:
            raise JournalError(f"{pfad.name}:{nr}: ts nicht lesbar ({d['ts']!r})")
        saetze.append(Satz(
            ts=ts, art=str(d["art"]),
            lauf=None if d.get("lauf") is None else str(d["lauf"]),
            version=None if d.get("version") is None else str(d["version"]),
            felder={k: v for k, v in d.items()
                    if k not in ("ts", "art", "lauf", "version")},
        ))
    return Lauf(pfad=pfad, saetze=saetze)


def lies_alle(verzeichnis: Path) -> list[Lauf]:
    """Alle Journale eines Verzeichnisses, nach Startzeit sortiert."""
    if not verzeichnis.is_dir():
        return []
    laeufe = [lies_journal(p) for p in sorted(verzeichnis.glob("journal-*.jsonl"))]
    return sorted(
        [lauf for lauf in laeufe if lauf.saetze],
        key=lambda lauf: lauf.saetze[0].ts,
    )


def durchgehende_equity(
    laeufe: list[Lauf],
) -> Iterator[tuple[datetime, Decimal, bool]]:
    """Equity ueber alle Laeufe, mit Markierung der Luecken DAZWISCHEN.

    Das dritte Feld ist ``True``, wenn vor diesem Punkt eine Pause lag -- zwischen zwei
    Laeufen laeuft die Schleife nicht, und was in der Pause geschah (Stop, Swap,
    Handeingriff), steht in keinem Journal. Eine Kurve, die das verschweigt, behauptet
    eine Lueckenlosigkeit, die sie nicht hat.
    """
    # Die Identitaet faellt auf den Dateinamen zurueck, wenn keine Lauf-Kennung da
    # ist: Journale von vor der Protokollerweiterung tragen keine, und ein Vergleich
    # ``None != None`` haette NIE eine Luecke gemeldet. Ein Melder, der nicht
    # ausloesen kann, ist schlimmer als keiner.
    vorher: str | None = None
    for lauf in laeufe:
        reihe = lauf.equity_reihe()
        kennung = lauf.lauf_id or f"datei:{lauf.pfad.name}"
        for i, (ts, wert) in enumerate(reihe):
            yield ts, wert, i == 0 and vorher is not None and vorher != kennung
        if reihe:
            vorher = kennung

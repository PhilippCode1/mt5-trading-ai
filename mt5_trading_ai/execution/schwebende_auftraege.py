"""Auftraege, deren Sendeversuch ohne Antwort endete -- „koennte beim Broker leben".

WARUM DIESES MODUL
------------------
``Mt5Venue.submit_order`` faengt jede Ausnahme aus ``terminal.order_send`` ab und haelt
fest: zu dieser Kennung kann beim Broker eine echte Order liegen, von der dieser Prozess
nichts weiss. Das ist der Zustand, den Stufe 5 des Auftrags verlangt::

    Nicht-endgueltigen Zustand „Antwort blieb aus, Auftrag koennte leben" einfuehren,
    der sichtbar bleibt und vor der naechsten Eroeffnung aufgeloest werden muss.

Bis hierher lag dieser Zustand in einem ``dict`` im Prozessgedaechtnis. Zwei Messungen
dazu (``archiv/AUFTRAG/stufen/05-ausfuehrung/belege/``):

* **Er sperrte die naechste Eroeffnung nicht.** Der Sendeversuch latcht zwar den
  Global-Halt, aber ``clear_halt()`` raeumt die Arbeitsliste ausdruecklich nicht ab --
  gemessen: nach ``clear_halt()`` ging die naechste Eroeffnung durch, **waehrend der
  ungeklaerte Eintrag noch stand**.
* **Er ueberlebte keinen Neustart.** Ein frisch gebautes Venue meldete eine leere
  Arbeitsliste. Das ist dieselbe Fehlerklasse, gegen die ``risiko_zustand.py`` gebaut
  wurde -- dort begann der Drawdown nach jedem Prozessstart bei null. Hier waere der
  Verlust schwerer: was verschwindet, ist die Kenntnis davon, dass moeglicherweise Geld
  am Markt steht.

WAS DIESER SPEICHER NICHT IST
-----------------------------
Kein zweiter Risikozustand. ``risiko_zustand.py`` fuehrt Halt, Tageszaehler und
Equity-Fenster -- Groessen mit Tagesrhythmus, Kontobindung und einer
Zwei-Schreiber-Vereinigung, die je Abschnitt eine eigene Irrtumsrichtung kennt. Ein
schwebender Auftrag hat keinen Tagesrhythmus, keine Zaehlung und nur eine
Irrtumsrichtung: **im Zweifel sperren**. Ihn in jene Struktur zu haengen hiesse, zwei
Lebenszyklen in eine Datei zu legen, deren Vereinigungsregeln fuer den einen geschrieben
sind.

**Was dagegen geteilt wird, ist der ORT.** ``standard_zustandsordner`` aus
``risiko_zustand.py`` traegt die vollstaendige Begruendung, warum Zustand ausserhalb des
Arbeitsbaums liegt (kein ``git checkout`` als stille Freigabe, kein ``git clean -xdf``
als Loeschung, kein Kontoabdruck im Verlauf) und weist relative Pfade zurueck. Diese
Regel ein zweites Mal hinzuschreiben waere genau der Fehler, den sie verhindert.

DIE EINE IRRTUMSRICHTUNG
------------------------
Jeder unklare Befund sperrt::

    Datei fehlt            -> nichts schwebt    (Regelfall: nie etwas passiert)
    Datei leer             -> nichts schwebt    (angelegt, nie geschrieben)
    Datei unlesbar         -> SPERRE mit Grund  (unbekannt, ob etwas schwebt)
    Eintrag unvollstaendig -> SPERRE mit Grund  (dito; der Eintrag zaehlt weiter)

„Datei fehlt" ist hier -- anders als beim Halt-Latch -- unbedenklich: die Datei entsteht
erst beim ersten Zwischenfall, und sie liegt an einem Ort, an dem kein Routinebefehl sie
entfernt. Ein fehlender Zwischenfall ist der Regelfall, kein Verdacht.

„Unlesbar" dagegen sperrt, und zwar ohne Ausweg ausser dem menschlichen: die Datei sagt
gerade, dass sie etwas ueber Geld am Markt weiss, das sie nicht mehr hersagen kann.

EINE DEFEKTE AKTE VERWIRFT NICHTS (D6)
--------------------------------------
Gemessen gegen 306bbaa (V6 der Bewertung): ``vermerken()`` las die Akte ueber ihren
gedeuteten Befund, brach beim ersten unlesbaren Eintrag ab und schrieb nur das zurueck,
was bis dahin gelesen war -- ``open-C`` hinter dem defekten ``open-B`` war danach weg,
und mit ihm der Sperrgrund. Ein Schreibvorgang, der Kenntnis ueber Geld am Markt
loescht, weil er sie nicht deuten kann, ist die milde Richtung in Reinform.

Darum arbeiten ``vermerken`` und ``aufloesen`` auf den **rohen** Eintraegen: was in der
Datei steht, wird unveraendert zurueckgeschrieben, ob lesbar oder nicht; ``laden``
deutet jeden Eintrag einzeln und traegt unlesbare als Platzhalter (Kennung, wenn eine
da ist, sonst ``#<Index>``) mit Sperrgrund. Ist die Datei **als Ganzes** unlesbar
(kein JSON, fremde Fassung), werden die Bytes unter ``<datei>.defekt-<zeit>`` zur Seite
gelegt und in der neuen Akte als eigener, sperrender Eintrag benannt -- der Befund ist
damit sichtbar, aufloesbar und nicht verloren.

FLUECHTIG NUR ALS TESTTYP (D8)
------------------------------
``SchwebeAkte(pfad)`` verlangt einen Pfad. Die Vorgabe „ohne Umgebungsvariable
fluechtig" ist entfallen (E-005): sie war der Zustand, in dem 21 Betriebslaeufe gefahren
wurden. Wer eine Akte nur im Prozess will, sagt es hin: :class:`FluechtigeSchwebeAkte`.

DIE AUFLOESUNG IST EINE MENSCHLICHE GESTE
-----------------------------------------
``aufloesen`` verlangt einen **Befund** -- den Text dessen, was beim Broker nachgesehen
wurde. Ohne Befund keine Aufloesung. Das ist kein Formalismus: der einzige Weg, diesen
Zustand ehrlich zu beenden, fuehrt ueber einen Menschen, der beim Gegenueber
nachgesehen hat. Ein Programm, das ihn selbst abraeumt, hat nichts nachgesehen -- es hat
nur aufgehoert zu fragen. Das Werkzeug dafuer ist ``tools/zustand.py
--schwebeakte-aufloesen <kennung> --befund "<Text>"``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mt5_trading_ai.execution.risiko_zustand import (
    SCHWEBEAKTE_DATEI,
    ZustandsortFehler,
    standard_zustandsordner,
)

#: Fassung des Dateiformats. Eine unbekannte Fassung ist ein unlesbarer Befund und
#: sperrt -- nicht „lies, was du kannst": ein spaeteres Format koennte Felder tragen,
#: deren Fehlen hier wie „nichts schwebt" aussaehe.
FORMATFASSUNG = 1


def standard_schwebedatei(ordner: Path | None = None) -> Path:
    """Der Pfad der Schwebeakte: ``SCHWEBEAKTE_DATEI`` im Zustandsordner."""
    if ordner is None:
        ordner = standard_zustandsordner()
    return ordner / SCHWEBEAKTE_DATEI


@dataclass(frozen=True)
class SchwebenderAuftrag:
    """Eine Kennung, deren Ausgang unbekannt ist -- und woran man das nachsieht."""

    client_order_id: str
    #: Was der Sendeversuch geworfen hat, als Text. Er sagt, wonach beim Broker zu
    #: sehen ist -- ein Zeitablauf liest sich anders als ein gesperrter Schreibpfad.
    grund: str
    seit: datetime
    #: Das Symbol, damit der Betrieb weiss, welche Positionsliste er ansehen muss.
    symbol: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "grund": self.grund,
            "seit": self.seit.isoformat(timespec="seconds"),
            "symbol": self.symbol,
        }


@dataclass(frozen=True)
class Schwebebefund:
    """Was die Akte hergibt -- und ob sie selbst vertrauenswuerdig war.

    ``sperrgrund`` ist gesetzt, wenn die Akte nicht vollstaendig gelesen werden konnte.
    ``eintraege`` fuehrt dann auch die unlesbaren Eintraege -- als Platzhalter mit
    Kennung oder ``#<Index>`` --, und der Aufrufer sperrt ohnehin: die Frage „schwebt
    etwas?" ist unbeantwortet, und unbeantwortet gilt als „ja".
    """

    eintraege: tuple[SchwebenderAuftrag, ...] = ()
    sperrgrund: str | None = None

    @property
    def schwebt(self) -> bool:
        return bool(self.eintraege) or self.sperrgrund is not None


@dataclass(frozen=True)
class _RohAkte:
    """Der Inhalt der Datei, unverarbeitet.

    ``lesbar`` heisst: die Datei war ein JSON-Objekt dieser Fassung mit einer Liste
    ``eintraege``. Was in der Liste steht, ist damit noch nicht gedeutet -- das tut
    ``laden`` je Eintrag. ``sperrgrund`` traegt den Grund, wenn ``lesbar`` falsch ist.
    """

    vorhanden: bool
    lesbar: bool
    eintraege: list[Any]
    sperrgrund: str | None = None


def _kennung(satz: Any, index: int) -> str:
    """Die Kennung eines rohen Eintrags -- oder ``#<Index>``, wenn er keine traegt."""
    if isinstance(satz, dict):
        kennung = satz.get("client_order_id")
        if isinstance(kennung, str) and kennung:
            return kennung
    return f"#{index}"


class SchwebeAkte:
    """Die Akte der schwebenden Auftraege. Liest fail-closed, schreibt sofort.

    **Sofort schreiben, nicht am Taktende.** Der Zustand entsteht in dem Augenblick, in
    dem eine Antwort ausbleibt -- also genau dann, wenn auch der Prozess wegbrechen
    kann. Ein Vermerk, der erst spaeter auf die Platte soll, ist im einzigen Fall
    verloren, fuer den er gedacht war.

    **Der Pfad ist Pflicht.** ``SchwebeAkte(None)`` wirft ``ZustandsortFehler``; eine
    Akte nur im Prozess heisst :class:`FluechtigeSchwebeAkte` und ist ein Testtyp.
    Die Fluechtigkeit ist **ablesbar** (:attr:`dauerhaft`): eine fluechtige Akte
    verhaelt sich bis zum Neustart genau wie eine dauerhafte. Wer das erst am Neustart
    merkt, merkt es an dem Tag, an dem es zaehlt.
    """

    def __init__(self, pfad: Path) -> None:
        if pfad is None:
            raise ZustandsortFehler(
                "SchwebeAkte ohne Pfad ist nicht konstruierbar (D8, E-005). Eine "
                "Akte nur im Prozessgedaechtnis heisst FluechtigeSchwebeAkte und ist "
                "ein Testtyp; der Betrieb nennt den Zustandsordner (--zustandsordner)."
            )
        self._pfad: Path | None = Path(pfad)

    @property
    def pfad(self) -> Path | None:
        return self._pfad

    @property
    def dauerhaft(self) -> bool:
        """Ob die Akte einen Neustart ueberdauert."""
        return self._pfad is not None

    # --- Rohes Lesen und Schreiben: die einzigen zwei Beruehrungen der Platte ---
    def _roh_lesen(self) -> _RohAkte:
        assert self._pfad is not None
        try:
            roh = self._pfad.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Der Regelfall: es hat nie einen Zwischenfall gegeben.
            return _RohAkte(vorhanden=False, lesbar=True, eintraege=[])
        except OSError as exc:
            return _RohAkte(
                vorhanden=True,
                lesbar=False,
                eintraege=[],
                sperrgrund=f"schwebeakte_unlesbar: {exc}",
            )
        if not roh.strip():
            return _RohAkte(vorhanden=True, lesbar=True, eintraege=[])
        try:
            daten = json.loads(roh)
        except json.JSONDecodeError as exc:
            return _RohAkte(True, False, [], f"schwebeakte_defekt: {exc}")
        if not isinstance(daten, dict):
            return _RohAkte(True, False, [], "schwebeakte_defekt: kein Objekt")
        if daten.get("fassung") != FORMATFASSUNG:
            return _RohAkte(
                True,
                False,
                [],
                f"schwebeakte_fassung: {daten.get('fassung')!r} statt {FORMATFASSUNG}",
            )
        roh_liste = daten.get("eintraege")
        if not isinstance(roh_liste, list):
            return _RohAkte(True, False, [], "schwebeakte_defekt: 'eintraege' fehlt")
        return _RohAkte(vorhanden=True, lesbar=True, eintraege=list(roh_liste))

    def _schreiben(self, eintraege: Sequence[Any]) -> None:
        """Der eine Schreibvorgang -- roh, atomar.

        ``eintraege`` sind rohe Saetze (``dict`` oder was sonst in der Datei stand);
        sie werden **unveraendert** geschrieben. Ueber eine Nebendatei und dann
        ``os.replace``: ein Absturz mitten im Schreiben darf keine halbe Akte
        hinterlassen. Eine halbe Akte waere zwar nach der Tabelle oben ein Sperrgrund
        und damit nicht gefaehrlich -- aber ein Sperrgrund ohne Anlass, und eine
        Sperre, die aus einem Schreibunfall entsteht, wird im Betrieb ausgebaut.

        Wirft ``OSError`` nach aussen: der Aufrufer (``Mt5Venue.submit_order``) haelt
        den Halt trotzdem und reicht beide Gruende weiter (D5).
        """
        assert self._pfad is not None
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        inhalt = json.dumps(
            {"fassung": FORMATFASSUNG, "eintraege": list(eintraege)},
            ensure_ascii=False,
            indent=2,
        )
        neben = self._pfad.with_suffix(self._pfad.suffix + ".neu")
        neben.write_text(inhalt, encoding="utf-8")
        os.replace(neben, self._pfad)

    def _defekt_bergen(self, roh: _RohAkte, jetzt: datetime) -> list[Any]:
        """Eine als Ganzes unlesbare Datei zur Seite legen, nichts verwerfen.

        Die Bytes wandern atomar nach ``<datei>.defekt-<zeit>``; die neue Akte traegt
        einen eigenen Eintrag, der den Sperrgrund und die Beweisdatei nennt. Er sperrt
        wie jeder andere und wird wie jeder andere nur mit Befund aufgeloest.
        """
        assert self._pfad is not None
        stempel = jetzt.strftime("%Y%m%dT%H%M%SZ")
        beweis = self._pfad.with_name(f"{self._pfad.name}.defekt-{stempel}")
        os.replace(self._pfad, beweis)
        marke = SchwebenderAuftrag(
            client_order_id=f"schwebeakte-defekt-{stempel}",
            grund=f"{roh.sperrgrund} -- Rohdaten gesichert unter {beweis.name}",
            seit=jetzt,
        )
        return [marke.as_dict()]

    # --- Deuten ----------------------------------------------------------------
    def laden(self) -> Schwebebefund:
        """Lies die Akte. Jeder unklare Befund sperrt (Tabelle im Modul-Docstring).

        Deutet **jeden** Eintrag und bricht beim ersten unlesbaren nicht ab: der
        Befund fuehrt alle Kennungen, lesbare wie unlesbare, und der Sperrgrund nennt
        den ersten Defekt.
        """
        roh = self._roh_lesen()
        if not roh.lesbar:
            return Schwebebefund(sperrgrund=roh.sperrgrund)
        eintraege: list[SchwebenderAuftrag] = []
        sperrgrund: str | None = None
        for i, satz in enumerate(roh.eintraege):
            gedeutet, defekt = self._deuten(satz, i)
            eintraege.append(gedeutet)
            if defekt is not None and sperrgrund is None:
                sperrgrund = defekt
        return Schwebebefund(eintraege=tuple(eintraege), sperrgrund=sperrgrund)

    @staticmethod
    def _deuten(satz: Any, index: int) -> tuple[SchwebenderAuftrag, str | None]:
        """Ein roher Satz -> Eintrag; bei Defekt ein Platzhalter samt Grund."""
        kennung = _kennung(satz, index)
        if not isinstance(satz, dict):
            return (
                SchwebenderAuftrag(kennung, "unlesbar", datetime.now(UTC)),
                f"schwebeakte_defekt: Eintrag {index} ist kein Objekt",
            )
        if kennung.startswith("#"):
            return (
                SchwebenderAuftrag(kennung, "unlesbar", datetime.now(UTC)),
                f"schwebeakte_defekt: Eintrag {index} ohne Kennung",
            )
        grund = satz.get("grund")
        seit = satz.get("seit")
        if not isinstance(grund, str) or not isinstance(seit, str):
            # Der Eintrag zaehlt trotzdem: dass hier eine Kennung steht, ist die
            # Auskunft, auf die es ankommt. Nur ihre Begleitangaben fehlen.
            return (
                SchwebenderAuftrag(kennung, "unlesbar", datetime.now(UTC)),
                f"schwebeakte_defekt: Eintrag {kennung} unvollstaendig",
            )
        try:
            zeit = datetime.fromisoformat(seit)
        except ValueError:
            return (
                SchwebenderAuftrag(kennung, grund, datetime.now(UTC)),
                f"schwebeakte_defekt: Eintrag {kennung} ohne Zeit",
            )
        symbol = satz.get("symbol")
        return (
            SchwebenderAuftrag(
                client_order_id=kennung,
                grund=grund,
                seit=zeit,
                symbol=symbol if isinstance(symbol, str) else "",
            ),
            None,
        )

    # --- Fortschreiben ---------------------------------------------------------
    def vermerken(self, auftrag: SchwebenderAuftrag) -> None:
        """Trag eine Kennung ein. Alles, was schon da ist, bleibt, wie es ist.

        Der **erste** Grund ist der interessante -- er sagt, wonach beim Broker zu
        sehen ist. Ein zweiter Versuch derselben Kennung soll ihn nicht ueberschreiben.
        Unlesbare Eintraege werden roh zurueckgeschrieben (D6).
        """
        roh = self._roh_lesen()
        eintraege = roh.eintraege
        if not roh.lesbar:
            eintraege = self._defekt_bergen(roh, auftrag.seit)
        if any(
            _kennung(satz, i) == auftrag.client_order_id
            for i, satz in enumerate(eintraege)
        ):
            return
        self._schreiben([*eintraege, auftrag.as_dict()])

    def aufloesen(self, client_order_id: str, *, befund: str) -> bool:
        """Nimm eine Kennung heraus -- nur mit einem Befund vom Gegenueber.

        Gibt zurueck, ob ueberhaupt ein Eintrag da war. Ein leerer Befund ist ein
        Fehler und kein Sonderfall: die Aufloesung ist die Behauptung, beim Broker
        nachgesehen zu haben. Wer nichts hinschreibt, hat nichts nachgesehen.

        Ein unlesbarer Eintrag ohne Kennung wird ueber seinen Platzhalter
        ``#<Index>`` aufgeloest -- so, wie ``laden`` ihn nennt. Alle anderen
        Eintraege bleiben roh, wie sie waren.
        """
        if not befund.strip():
            raise ValueError(
                "Eine schwebende Kennung wird nur mit einem Befund aufgeloest -- "
                "dem, was beim Broker nachgesehen wurde."
            )
        roh = self._roh_lesen()
        if not roh.vorhanden:
            return False
        eintraege = roh.eintraege
        if not roh.lesbar:
            eintraege = self._defekt_bergen(roh, datetime.now(UTC))
            self._schreiben(eintraege)
        bleiben = [
            satz
            for i, satz in enumerate(eintraege)
            if _kennung(satz, i) != client_order_id
        ]
        if len(bleiben) == len(eintraege):
            return False
        self._schreiben(bleiben)
        return True


class FluechtigeSchwebeAkte(SchwebeAkte):
    """Die Akte nur im Prozessgedaechtnis -- der ausdrueckliche Testtyp (D8).

    Gleiche Deutung, gleiche Sperrregeln, keine Platte. ``dauerhaft`` ist ``False``,
    ``pfad`` ist ``None``; ``tools/live_betrieb.py`` weist einen Handelsplatz mit
    dieser Akte ab.
    """

    def __init__(self) -> None:
        self._pfad = None
        self._speicher: list[Any] = []

    def _roh_lesen(self) -> _RohAkte:
        return _RohAkte(
            vorhanden=bool(self._speicher), lesbar=True, eintraege=list(self._speicher)
        )

    def _schreiben(self, eintraege: Sequence[Any]) -> None:
        self._speicher = list(eintraege)

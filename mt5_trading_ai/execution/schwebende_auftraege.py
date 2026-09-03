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

DIE AUFLOESUNG IST EINE MENSCHLICHE GESTE
-----------------------------------------
``aufloesen`` verlangt einen **Befund** -- den Text dessen, was beim Broker nachgesehen
wurde. Ohne Befund keine Aufloesung. Das ist kein Formalismus: der einzige Weg, diesen
Zustand ehrlich zu beenden, fuehrt ueber einen Menschen, der beim Gegenueber
nachgesehen hat. Ein Programm, das ihn selbst abraeumt, hat nichts nachgesehen -- es hat
nur aufgehoert zu fragen.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mt5_trading_ai.execution.risiko_zustand import (
    _absolut_oder_wurf,
    standard_zustandsordner,
)

#: Umgebungsvariable fuer den Dateipfad. Wie bei der Zustandsdatei: ein absoluter Pfad
#: oder ein Wurf, nie eine stille Zurechtbiegung.
UMGEBUNG_SCHWEBEDATEI = "MT5_SCHWEBENDE_AUFTRAEGE"

#: Fassung des Dateiformats. Eine unbekannte Fassung ist ein unlesbarer Befund und
#: sperrt -- nicht „lies, was du kannst": ein spaeteres Format koennte Felder tragen,
#: deren Fehlen hier wie „nichts schwebt" aussaehe.
FORMATFASSUNG = 1


def standard_schwebedatei(
    *,
    umgebung: Mapping[str, str] | None = None,
    ist_windows: bool | None = None,
) -> Path:
    """Der Standardpfad der Schwebeakte -- neben der Zustandsdatei, nicht darin."""
    umg = os.environ if umgebung is None else umgebung
    aus_umgebung = umg.get(UMGEBUNG_SCHWEBEDATEI)
    if aus_umgebung:
        return _absolut_oder_wurf(aus_umgebung, UMGEBUNG_SCHWEBEDATEI)
    ordner = standard_zustandsordner(umgebung=umg, ist_windows=ist_windows)
    return ordner / "schwebende_auftraege.json"


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

    ``sperrgrund`` ist gesetzt, wenn die Akte nicht gelesen werden konnte. Dann ist
    ``eintraege`` moeglicherweise unvollstaendig, und der Aufrufer sperrt ohnehin: die
    Frage „schwebt etwas?" ist unbeantwortet, und unbeantwortet gilt als „ja".
    """

    eintraege: tuple[SchwebenderAuftrag, ...] = ()
    sperrgrund: str | None = None

    @property
    def schwebt(self) -> bool:
        return bool(self.eintraege) or self.sperrgrund is not None


class SchwebeAkte:
    """Die Akte der schwebenden Auftraege. Liest fail-closed, schreibt sofort.

    **Sofort schreiben, nicht am Taktende.** Der Zustand entsteht in dem Augenblick, in
    dem eine Antwort ausbleibt -- also genau dann, wenn auch der Prozess wegbrechen
    kann. Ein Vermerk, der erst spaeter auf die Platte soll, ist im einzigen Fall
    verloren, fuer den er gedacht war.

    **``pfad=None`` heisst fluechtig** -- die Eintraege leben dann nur im Prozess. Das
    ist dieselbe Regel, die ``RiskManager`` fuer den Risikozustand faehrt
    (``_zustand_waehlen``): eine Bibliothek schreibt nicht ungefragt in das
    Zustandsverzeichnis des Benutzers, nur weil jemand ein Objekt gebaut hat. Der
    Betreiber entscheidet das ueber die Umgebung.

    Und wie dort ist die Fluechtigkeit **ablesbar** (:attr:`dauerhaft`): eine fluechtige
    Akte verhaelt sich bis zum Neustart genau wie eine dauerhafte. Wer das erst am
    Neustart merkt, merkt es an dem Tag, an dem es zaehlt.
    """

    def __init__(self, pfad: Path | None) -> None:
        self._pfad = pfad
        #: Nur im fluechtigen Betrieb benutzt.
        self._speicher: tuple[SchwebenderAuftrag, ...] = ()

    @property
    def pfad(self) -> Path | None:
        return self._pfad

    @property
    def dauerhaft(self) -> bool:
        """Ob die Akte einen Neustart ueberdauert."""
        return self._pfad is not None

    def laden(self) -> Schwebebefund:
        """Lies die Akte. Jeder unklare Befund sperrt (Tabelle im Modul-Docstring)."""
        if self._pfad is None:
            return Schwebebefund(eintraege=self._speicher)
        try:
            roh = self._pfad.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Der Regelfall: es hat nie einen Zwischenfall gegeben.
            return Schwebebefund()
        except OSError as exc:
            return Schwebebefund(sperrgrund=f"schwebeakte_unlesbar: {exc}")

        if not roh.strip():
            return Schwebebefund()

        try:
            daten = json.loads(roh)
        except json.JSONDecodeError as exc:
            return Schwebebefund(sperrgrund=f"schwebeakte_defekt: {exc}")
        if not isinstance(daten, dict):
            return Schwebebefund(sperrgrund="schwebeakte_defekt: kein Objekt")
        if daten.get("fassung") != FORMATFASSUNG:
            return Schwebebefund(
                sperrgrund=f"schwebeakte_fassung: {daten.get('fassung')!r} "
                f"statt {FORMATFASSUNG}"
            )

        roh_liste = daten.get("eintraege")
        if not isinstance(roh_liste, list):
            return Schwebebefund(sperrgrund="schwebeakte_defekt: 'eintraege' fehlt")

        eintraege: list[SchwebenderAuftrag] = []
        for i, satz in enumerate(roh_liste):
            if not isinstance(satz, dict):
                return Schwebebefund(
                    eintraege=tuple(eintraege),
                    sperrgrund=f"schwebeakte_defekt: Eintrag {i} ist kein Objekt",
                )
            kennung = satz.get("client_order_id")
            grund = satz.get("grund")
            seit = satz.get("seit")
            if not isinstance(kennung, str) or not kennung:
                return Schwebebefund(
                    eintraege=tuple(eintraege),
                    sperrgrund=f"schwebeakte_defekt: Eintrag {i} ohne Kennung",
                )
            if not isinstance(grund, str) or not isinstance(seit, str):
                # Der Eintrag zaehlt trotzdem: dass hier eine Kennung steht, ist die
                # Auskunft, auf die es ankommt. Nur ihre Begleitangaben fehlen.
                return Schwebebefund(
                    eintraege=(
                        *eintraege,
                        SchwebenderAuftrag(kennung, "unlesbar", datetime.now(UTC)),
                    ),
                    sperrgrund=f"schwebeakte_defekt: Eintrag {kennung} unvollstaendig",
                )
            try:
                zeit = datetime.fromisoformat(seit)
            except ValueError:
                return Schwebebefund(
                    eintraege=(
                        *eintraege,
                        SchwebenderAuftrag(kennung, grund, datetime.now(UTC)),
                    ),
                    sperrgrund=f"schwebeakte_defekt: Eintrag {kennung} ohne Zeit",
                )
            symbol = satz.get("symbol")
            eintraege.append(
                SchwebenderAuftrag(
                    client_order_id=kennung,
                    grund=grund,
                    seit=zeit,
                    symbol=symbol if isinstance(symbol, str) else "",
                )
            )
        return Schwebebefund(eintraege=tuple(eintraege))

    def vermerken(self, auftrag: SchwebenderAuftrag) -> None:
        """Trag eine Kennung ein. Ein vorhandener Eintrag bleibt, wie er ist.

        Der **erste** Grund ist der interessante -- er sagt, wonach beim Broker zu
        sehen ist. Ein zweiter Versuch derselben Kennung soll ihn nicht ueberschreiben.
        """
        befund = self.laden()
        if any(e.client_order_id == auftrag.client_order_id for e in befund.eintraege):
            return
        self._schreiben((*befund.eintraege, auftrag))

    def aufloesen(self, client_order_id: str, *, befund: str) -> bool:
        """Nimm eine Kennung heraus -- nur mit einem Befund vom Gegenueber.

        Gibt zurueck, ob ueberhaupt ein Eintrag da war. Ein leerer Befund ist ein
        Fehler und kein Sonderfall: die Aufloesung ist die Behauptung, beim Broker
        nachgesehen zu haben. Wer nichts hinschreibt, hat nichts nachgesehen.
        """
        if not befund.strip():
            raise ValueError(
                "Eine schwebende Kennung wird nur mit einem Befund aufgeloest -- "
                "dem, was beim Broker nachgesehen wurde."
            )
        gelesen = self.laden()
        bleiben = tuple(
            e for e in gelesen.eintraege if e.client_order_id != client_order_id
        )
        if len(bleiben) == len(gelesen.eintraege) and gelesen.sperrgrund is None:
            return False
        self._schreiben(bleiben)
        return True

    def _schreiben(self, eintraege: tuple[SchwebenderAuftrag, ...]) -> None:
        if self._pfad is None:
            self._speicher = eintraege
            return
        self._pfad.parent.mkdir(parents=True, exist_ok=True)
        inhalt = json.dumps(
            {
                "fassung": FORMATFASSUNG,
                "eintraege": [e.as_dict() for e in eintraege],
            },
            ensure_ascii=False,
            indent=2,
        )
        # Ueber eine Nebendatei und dann umbenennen: ein Absturz mitten im Schreiben
        # darf keine halbe Akte hinterlassen. Eine halbe Akte waere zwar nach der
        # Tabelle oben ein Sperrgrund und damit nicht gefaehrlich -- aber sie waere ein
        # Sperrgrund ohne Anlass, und eine Sperre, die aus einem Schreibunfall
        # entsteht, wird im Betrieb ausgebaut.
        neben = self._pfad.with_suffix(self._pfad.suffix + ".neu")
        neben.write_text(inhalt, encoding="utf-8")
        neben.replace(self._pfad)

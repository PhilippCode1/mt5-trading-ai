"""Alarmregeln, Dienstgüteziele und Fehlerbudget -- aus dem Betriebsjournal.

WORUM ES GEHT
-------------
Stufe 10 des Auftrags::

    Erst hier: Alarmzustellung bis zu einem Menschen, Handlungsanweisungen fuer jede
    Alarmregel, Dienstgueteziele mit Fehlerbudget, geprobter Wiederanlauf.

    Abnahme: ... jede Alarmregel hat eine existierende Metrik und eine existierende
    Handlungsanweisung.

„Erst hier" ist der Kern des Satzes. Eine Alarmschicht vor der Absicherung waere
Aufwand ohne Gegenstand -- man alarmiert ueber ein System, das nicht laeuft. Deshalb
steht diese Stufe am Ende und nicht am Anfang.

DIE DREI BINDUNGEN JE REGEL
---------------------------
Eine Alarmregel taugt nur, wenn drei Dinge existieren, und alle drei werden geprueft:

1. **Eine Metrik**, die es wirklich gibt -- eine Funktion in diesem Modul, die sie aus
   dem Journal rechnet. Eine Regel auf eine Zahl, die niemand erhebt, feuert nie.
2. **Eine Handlungsanweisung**, die es wirklich gibt -- ein Abschnitt in ``RUNBOOK.md``.
   Ein Alarm ohne Anweisung weckt jemanden, der dann nicht weiss, was zu tun ist.
3. **Eine Schwelle**, die vorher feststeht. Danach wird sie nicht bewegt (V6).

DIENSTGUETEZIEL UND FEHLERBUDGET
--------------------------------
Ein Ziel ohne Budget ist ein Wunsch. Das Budget ist der zulaessige Rest: bei einem Ziel
von 99 % duerfen 1 % der Vorgaenge scheitern. Verbraucht ist es, sobald mehr
scheitern -- und dann ist die Frage nicht „wie machen wir die Zahl schoener",
sondern „was aendern wir am Betrieb".

**Gemessen an den 21 Betriebslaeufen dieses Standes verfehlt der Stand alle drei Ziele**
(``tools/dienstguete.py``). Das ist der Befund dieser Stufe, nicht ihr Scheitern: eine
Dienstgueteschicht, die auf den eigenen Daten sofort Alarm schlaegt, misst etwas.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Messwert:
    """Eine erhobene Groesse: Zaehler, Nenner, Anteil -- und ihre Bezugsgroesse.

    Zaehler und Nenner stehen mit dabei, weil ein Anteil ohne sie nicht lesbar ist:
    „78,8 %" aus 26 von 33 ist etwas anderes als aus 788 von 1.000.
    """

    name: str
    gelungen: int
    gesamt: int
    bezug: str

    @property
    def anteil(self) -> float | None:
        """``None`` bei leerem Nenner -- kein Ersatzwert (V3)."""
        return self.gelungen / self.gesamt if self.gesamt else None


@dataclass(frozen=True)
class Dienstgueteziel:
    """Ein Ziel samt Fehlerbudget. Die Schwelle steht vorher fest."""

    name: str
    metrik: str
    ziel: float
    #: Warum gerade diese Zahl. Steht hier, damit sie nicht spaeter „schon immer"
    #: heisst.
    begruendung: str

    @property
    def fehlerbudget(self) -> float:
        return 1.0 - self.ziel

    def verbraucht(self, wert: Messwert) -> float | None:
        """Anteil des aufgebrauchten Fehlerbudgets. ``> 1`` heisst: gerissen."""
        if wert.anteil is None or self.fehlerbudget <= 0:
            return None
        return (1.0 - wert.anteil) / self.fehlerbudget


@dataclass(frozen=True)
class Alarmregel:
    """Eine Regel. Sie nennt ihre Metrik und ihre Handlungsanweisung beim Namen."""

    name: str
    metrik: str
    #: Ueberschrift des zugehoerigen Abschnitts in ``RUNBOOK.md``. Exakt, nicht
    #: sinngemaess.
    handlungsanweisung: str
    schwelle: float
    #: Was der Alarm bedeutet -- steht in der Zustellung, damit sie ohne Nachschlagen
    #: schon etwas sagt.
    bedeutet: str


@dataclass(frozen=True)
class Alarm:
    regel: Alarmregel
    wert: Messwert

    def als_zeile(self) -> str:
        anteil = "--" if self.wert.anteil is None else f"{self.wert.anteil:.1%}"
        return (
            f"ALARM {self.regel.name}: {anteil} "
            f"({self.wert.gelungen}/{self.wert.gesamt} {self.wert.bezug}), "
            f"Schwelle {self.regel.schwelle:.1%}. {self.regel.bedeutet} "
            f"-> RUNBOOK.md: {self.regel.handlungsanweisung}"
        )


# --- Die Metriken: je eine Funktion, die aus dem Journal rechnet ----------------


def _saetze(zeilen: Iterable[str]) -> list[dict[str, Any]]:
    aus = []
    for zeile in zeilen:
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            satz = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        if isinstance(satz, dict):
            aus.append(satz)
    return aus


def buchtreue(saetze: Sequence[dict[str, Any]]) -> Messwert:
    """Anteil der Takte ohne gesetzten Halt.

    Ein Halt heisst: das Buch und die Meldung des Handelsplatzes gehen auseinander,
    oder ein Sendeversuch blieb unbeantwortet. Beides sperrt jede Eroeffnung.
    """
    takte = [s for s in saetze if s.get("art") == "takt"]
    ohne_halt = sum(1 for s in takte if not s.get("halt"))
    return Messwert("buchtreue", ohne_halt, len(takte), "Takte")


def ausstiegsverlaesslichkeit(saetze: Sequence[dict[str, Any]]) -> Messwert:
    """Anteil der Schliessversuche, die gelungen sind.

    Die wichtigste der drei: ein Ausstieg, der nicht gelingt, laesst Geld am Markt,
    waehrend das System glaubt, es sei draussen. Sperre V5 des Auftrags haelt den
    Risikoabbau von jeder Sperre frei -- diese Metrik misst, ob er auch ankommt.
    """
    ok = sum(1 for s in saetze if s.get("art") == "geschlossen")
    fehl = sum(1 for s in saetze if s.get("art") == "schliessen_fehlgeschlagen")
    return Messwert("ausstiegsverlaesslichkeit", ok, ok + fehl, "Schliessversuche")


def laufabschluss(saetze: Sequence[dict[str, Any]]) -> Messwert:
    """Anteil der Laeufe, die sauber geendet haben (``ende`` nach ``start``).

    Ein Lauf ohne Endsatz ist abgestuerzt oder abgewuergt worden. Das ist nicht nur
    unschoen: der Wiederanlauf muss dann das Buch vom Broker uebernehmen, statt es
    fortzuschreiben.
    """
    start = sum(1 for s in saetze if s.get("art") == "start")
    ende = sum(1 for s in saetze if s.get("art") == "ende")
    return Messwert("laufabschluss", ende, start, "Laeufe")


#: Metrikname -> Funktion. **Die eine Stelle**, an der eine Metrik existiert; die
#: Alarmregeln und Ziele unten verweisen nur auf Namen aus diesem Verzeichnis, und ein
#: Dauertor prueft, dass jeder Verweis hier ankommt.
METRIKEN: dict[str, Callable[[Sequence[dict[str, Any]]], Messwert]] = {
    "buchtreue": buchtreue,
    "ausstiegsverlaesslichkeit": ausstiegsverlaesslichkeit,
    "laufabschluss": laufabschluss,
}


#: Die Ziele. Vorab gesetzt, mit Begruendung -- und der Stand verfehlt alle drei.
#: Sie zu senken, bis sie passen, waere die Schwellenverschiebung, die V6 verbietet.
ZIELE: tuple[Dienstgueteziel, ...] = (
    Dienstgueteziel(
        "Buchtreue", "buchtreue", 0.99,
        "Ein Halt sperrt jede Eroeffnung. Mehr als ein Prozent gesperrte Takte heisst, "
        "dass der Betrieb ueberwiegend mit dem Aufraeumen beschaeftigt ist.",
    ),
    Dienstgueteziel(
        "Ausstiegsverlaesslichkeit", "ausstiegsverlaesslichkeit", 0.95,
        "Ein misslungener Ausstieg laesst Geld am Markt, waehrend das System glaubt, "
        "es sei drauszen. Fuenf Prozent sind schon viel; strenger waere vertretbar.",
    ),
    Dienstgueteziel(
        "Laufabschluss", "laufabschluss", 0.95,
        "Ein Lauf ohne Endsatz zwingt den Wiederanlauf, das Buch vom Broker zu "
        "uebernehmen statt es fortzuschreiben.",
    ),
)


#: Die Alarmregeln. Jede nennt ihre Metrik und den EXAKTEN Abschnittstitel in
#: ``RUNBOOK.md``; beides wird geprueft.
ALARMREGELN: tuple[Alarmregel, ...] = (
    Alarmregel(
        "buchtreue_unter_ziel", "buchtreue",
        "Buchtreue unter Ziel", 0.99,
        "Das Buch und die Meldung des Handelsplatzes gehen zu oft auseinander.",
    ),
    Alarmregel(
        "ausstieg_misslingt", "ausstiegsverlaesslichkeit",
        "Ausstieg misslingt", 0.95,
        "Schliessversuche scheitern -- moeglicherweise steht Geld am Markt.",
    ),
    Alarmregel(
        "laeufe_brechen_ab", "laufabschluss",
        # Der EXAKTE Abschnittstitel aus ``RUNBOOK.md``, Umlaut inklusive -- eine
        # Handlungsanweisung wird ueber ihre Ueberschrift gefunden, nicht sinngemaess.
        # Die ASCII-Fassung stand hier zuerst und lief ins Leere; das Dauertor
        # ``test_jede_alarmregel_hat_eine_existierende_handlungsanweisung`` hat sie
        # beim ersten Lauf gefunden.
        "Läufe brechen ab", 0.95,
        "Laeufe enden ohne Endsatz; der Wiederanlauf muss das Buch uebernehmen.",
    ),
)


def erhebe(zeilen: Iterable[str]) -> dict[str, Messwert]:
    """Alle Metriken auf einmal, aus denselben Saetzen."""
    saetze = _saetze(zeilen)
    return {name: fn(saetze) for name, fn in METRIKEN.items()}


def pruefe_alarme(werte: dict[str, Messwert]) -> tuple[Alarm, ...]:
    """Welche Regeln schlagen an? Eine fehlende Metrik ist ein Fehler, kein Nicht-Alarm.

    Das ist die Fehlrichtung, auf die es ankommt: eine Regel, deren Metrik fehlt, darf
    nicht stillschweigend als „kein Alarm" durchgehen. Sie wirft.
    """
    aus: list[Alarm] = []
    for regel in ALARMREGELN:
        wert = werte.get(regel.metrik)
        if wert is None:
            raise KeyError(
                f"Alarmregel '{regel.name}' verweist auf die Metrik "
                f"'{regel.metrik}', die es nicht gibt."
            )
        if wert.anteil is not None and wert.anteil < regel.schwelle:
            aus.append(Alarm(regel, wert))
    return tuple(aus)


def stelle_zu(alarme: Sequence[Alarm], ziel: Path) -> str:
    """Schreib die Alarme dorthin, wo ein Mensch sie sieht -- und melde, ob es ging.

    „Zustellung bis zu einem Menschen" heisst hier: eine Datei, die der Betrieb
    beobachtet, **plus** die Rueckgabe an den Aufrufer, der sie auf die Fehlerausgabe
    schreibt und mit einem Rueckgabewert ungleich 0 endet. Kein Netzdienst: eine
    Zustellung, die still scheitert, weil ein Anbieter nicht antwortet, ist schlechter
    als keine -- sie erweckt den Eindruck, jemand sei benachrichtigt worden.

    Schlaegt das Schreiben fehl, wirft diese Funktion. Ein Alarm, dessen Zustellung
    stillschweigend misslingt, ist der schlimmste Fall dieser ganzen Stufe.
    """
    ziel.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(a.als_zeile() for a in alarme)
    ziel.write_text(text + ("\n" if text else ""), encoding="utf-8")
    return text

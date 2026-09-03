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
2. **Eine Handlungsanweisung**, die es wirklich gibt -- die Regel traegt sie
selbst (E-014).
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
    #: Vorgaenge, die sich **gar nicht beurteilen** lassen -- weil die Aufzeichnung das
    #: noetige Feld noch nicht kannte oder es fehlt. Sie stehen NICHT im Nenner.
    #:
    #: Das ist V3 an einer Stelle, an der es leicht zu uebersehen waere: einen nicht
    #: beurteilbaren Vorgang als „gelungen" zu zaehlen, ersetzt einen fehlenden
    #: Messwert durch einen Standardwert -- und zwar durch den schmeichelnden. Ihn
    #: stillschweigend als „gescheitert" zu zaehlen waere ebenso falsch, nur in die
    #: andere Richtung. Er wird deshalb gefuehrt und angezeigt, nicht verrechnet.
    unbeurteilbar: int = 0

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
    #: Die Handlung selbst -- imperativ, zwei bis vier Saetze (E-014). Frueher der
    #: Titel eines RUNBOOK-Abschnitts; das Runbook liegt im Archiv.
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
            f"-> Handlung: {self.regel.handlungsanweisung}"
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
    """Anteil der Takte, in denen **wirklich** keine Eroeffnung gesperrt war.

    WAS DIESE METRIK ZUERST GEZAEHLT HAT -- UND WARUM DAS FALSCH WAR
    ---------------------------------------------------------------
    Die erste Fassung zaehlte jeden Takt mit ``halt=true``. Ihr eigener Docstring
    begruendete das mit dem Satz „Beides sperrt jede Eroeffnung". Gemessen an den
    Journalen stimmte dieser Satz in **4 von 20** Halt-Takten nicht:

        Der Scheduler laeuft VOR dem Buchabgleich. Schliesst der Broker eine Position
        zwischen zwei Takten (ein voellig normaler Stop-Fill), sieht der Reconcile sie
        noch im Buch und latcht ``reconcile_drift`` -- fail-closed und richtig so. Der
        Abgleich im selben Takt erkennt die Schliessung, loest den Halt auf, und die
        Eintritte laufen normal. Im langen Lauf vom 2026-08-17 liefen in JEDEM dieser
        vier Takte vier Eroeffnungsversuche durch; einer fuehrte zu einer Eroeffnung.

    Der ``takt``-Satz wird vor dieser Aufloesung geschrieben und kann sie nicht kennen
    (er muss frueh geschrieben werden, sonst verschluckt eine zurueckkehrende Notbremse
    ihn ganz). Die Aufloesung steht deshalb im ``halt_erklaert``-Satz desselben Takts,
    und dort sagt ``weiter_gesperrt``, was die Eintritte wirklich regiert hat.

    **Die Korrektur rettet das Ziel nicht** -- sie hebt den Wert von 98,53 % auf
    98,82 % bei einer Schwelle von 99,0 %. Sie ist also keine Schwellenverschiebung
    durch die Hintertuer, sondern bringt die Zaehlung mit ihrer eigenen Definition in
    Deckung. Die Schwelle ist unveraendert.

    Die Leiter je Takt, ohne Ersatzwerte (V3):

    ==========================  ============================================
    Lage                        gezaehlt als
    ==========================  ============================================
    ``halt`` nicht gesetzt      sauber
    Halt, kein ``halt_erklaert``  **gesperrt** -- der Halt stand den Takt durch
    Halt, erklaert, ``weiter_gesperrt=False``  sauber
    Halt, erklaert, ``weiter_gesperrt=True``   **gesperrt**
    Halt, erklaert, Feld fehlt  **unbeurteilbar** -- nicht im Nenner
    ==========================  ============================================
    """
    takte = [i for i, s in enumerate(saetze) if s.get("art") == "takt"]
    sauber = gesperrt = unbeurteilbar = 0
    for pos, i in enumerate(takte):
        if not saetze[i].get("halt"):
            sauber += 1
            continue
        # Bis zum naechsten Takt: steht dort eine Aufloesung?
        bis = takte[pos + 1] if pos + 1 < len(takte) else len(saetze)
        erklaerung = next(
            (s for s in saetze[i + 1 : bis] if s.get("art") == "halt_erklaert"), None
        )
        if erklaerung is None:
            gesperrt += 1
        elif "weiter_gesperrt" not in erklaerung:
            unbeurteilbar += 1
        elif erklaerung["weiter_gesperrt"]:
            gesperrt += 1
        else:
            sauber += 1
    return Messwert(
        "buchtreue", sauber, sauber + gesperrt, "Takte", unbeurteilbar=unbeurteilbar
    )


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

    WAS DIESE ZAHL NICHT SAGT -- GEMESSEN, NICHT VERMUTET
    ------------------------------------------------------
    Sie steht bei 90,5 % gegen ein Ziel von 95 %, und sie bleibt es. Drei Gruende, warum
    sie **nicht** als Sicherheitsanzeige gelesen werden darf; alle drei sind an den 21
    Journalen dieses Standes gemessen (``archiv/AUFTRAG/stufen/10-betrieb/nachtrag-
    laufabschluss.md``):

    1. **Sie verlangt vom Prozess, seinen eigenen Tod zu ueberleben.** Gemessen mit
       einem Opferskript auf dieser Maschine: bei ``taskkill /F`` laeuft weder ein
       Signalhandler noch ``atexit`` noch ein ``finally``-Block. Die tatsaechliche
       Ursache des laengsten Abbruchs steht im Windows-Ereignisprotokoll -- elf
       Sekunden nach dem letzten Journalsatz: Abmeldung und Standby (Kernel-Power 42,
       „Ursache: Application API"). Die Software hat daran keinen Anteil.
    2. **Sie ist auf diesen Daten invertiert zur Gefahr.** Die zwei Laeufe ohne
       ``ende`` und die zwei Laeufe, die wirklich Geld am Markt liessen, sind
       **disjunkte Mengen**: ``journal-20260817T173413`` und ``...182800`` liessen drei
       bzw. zwei Positionen offen und zaehlen hier als GELUNGEN, weil sie einen
       ``ende``-Satz schrieben. ``...182951`` hinterliess ein leeres Buch und zaehlt als
       GESCHEITERT.
    3. **Sie ist trivial schoenbar.** Jeder Lauf zaehlt gleich, ob er null Sekunden oder
       18,7 Stunden dauerte; 20 der 21 Laeufe sind kuerzer als 90 Minuten. Neunzehn
       Trockenlaeufe von je zwanzig Sekunden -- zusammen rund sieben Minuten Arbeit --
       heben die Quote ueber 95 % und loeschen den Alarm, ohne dass sich am Betrieb
       irgendetwas bessert. ``tests/test_laufabschluss.py`` haelt diesen Weg als
       Dauertor fest, damit ihn niemand fuer eine Behebung haelt.

    Die Frage, um die es wirklich geht -- hat ein Lauf ein unbeaufsichtigtes Buch
    hinterlassen -- beantwortet ``ausstiegsdeckung``, und zwar fuer jeden Lauf, gleich
    wie er endete.
    """
    start = sum(1 for s in saetze if s.get("art") == "start")
    ende = sum(1 for s in saetze if s.get("art") == "ende")
    return Messwert("laufabschluss", ende, start, "Laeufe")


def _laeufe(saetze: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Zerlege den Satzstrom in Laeufe. Ein ``start``-Satz beginnt einen neuen.

    Saetze vor dem ersten ``start`` gehoeren zu keinem Lauf und fallen weg -- das
    passiert nur bei von Hand zusammengeschnittenen Journalen.
    """
    aus: list[list[dict[str, Any]]] = []
    for satz in saetze:
        if satz.get("art") == "start":
            aus.append([satz])
        elif aus:
            aus[-1].append(satz)
    return aus


def _hat_gehalten(lauf: Sequence[dict[str, Any]]) -> bool | None:
    """Hatte dieser Lauf je eine Position im Buch? ``None`` heisst: nicht feststellbar.

    Drei Antworten, und die dritte ist die wichtige. Ein Lauf, der nie etwas hielt, kann
    nichts unbeaufsichtigt zuruecklassen -- er gehoert weder als Erfolg noch als
    Fehlschlag in die Rechnung. Ihn als Erfolg zu zaehlen waere der Weg, die Kennzahl
    mit Trockenlaeufen zu schoenen (siehe Modul-Docstring von ``ausstiegsdeckung``).
    """
    for satz in lauf:
        art = satz.get("art")
        if art == "eroeffnungsversuch" and satz.get("eroeffnet"):
            return True
        if art in ("geschlossen", "vom_broker_geschlossen"):
            return True
        if art == "ende" and satz.get("offen_geblieben"):
            return True
        if art == "takt" and satz.get("positionen"):
            return True
    # Nichts gefunden. War das Buch nachweislich immer leer, oder wissen wir es nur
    # nicht? Nur wenn JEDER Takt das Positionsfeld traegt, ist „nie gehalten" belegt.
    takte = [s for s in lauf if s.get("art") == "takt"]
    if takte and all("positionen" in s for s in takte):
        return False
    return None


def _buch_am_ende(lauf: Sequence[dict[str, Any]]) -> int | None:
    """Wie viele Positionen standen am Ende dieses Laufs offen? ``None`` = unbekannt.

    Rangfolge, von der staerksten Auskunft zur schwaechsten:

    1. ``ende.offen_geblieben`` -- die **Aussage des Laufs selbst** ueber das, was er
       zurueckliess. Sie steht oben, weil sie nach dem letzten Schliessversuch entsteht.
    2. Der letzte ``takt`` mit Positionsfeld -- das zuletzt beobachtete Buch. Fuer einen
       Lauf, der hart gestorben ist, ist das die einzige Auskunft, die es gibt.
    3. Die Bilanz aus Eroeffnungen und Schliessungen. **Schwaecher und hier benannt:**
       sie ist abgeleitet, nicht aufgezeichnet, und eine broker-seitige Schliessung, die
       der Lauf nicht mehr mitbekam, fehlt darin. Sie steht trotzdem drin, weil sonst
       genau der schlimmste Fall dieses Standes (``journal-20260817T150513``: drei
       Eroeffnungen, keine Schliessung, dann der Tod) unsichtbar bliebe.
    """
    ende = next((s for s in lauf if s.get("art") == "ende"), None)
    if ende is not None and "offen_geblieben" in ende:
        return len(ende["offen_geblieben"] or ())
    letzter = next(
        (s for s in reversed(lauf) if s.get("art") == "takt" and "positionen" in s),
        None,
    )
    if letzter is not None:
        return len(letzter["positionen"] or ())
    auf = sum(
        1 for s in lauf if s.get("art") == "eroeffnungsversuch" and s.get("eroeffnet")
    )
    zu = sum(
        1 for s in lauf if s.get("art") in ("geschlossen", "vom_broker_geschlossen")
    )
    if auf or zu:
        return max(0, auf - zu)
    return None


def ausstiegsdeckung(saetze: Sequence[dict[str, Any]]) -> Messwert:
    """Anteil der Laeufe, die **kein unbeaufsichtigtes Buch** hinterlassen haben.

    WAS DIESE METRIK ZUERST GESEHEN HAT -- UND WAS NICHT
    ----------------------------------------------------
    Die erste Fassung sah nur Laeufe **mit** ``ende``-Satz. Damit war der schlimmste
    Vorgang des ganzen Standes fuer sie unsichtbar:

        ``journal-20260817T150513``: drei Positionen eroeffnet (EURUSD, GBPUSD,
        XAUUSD), **keine** geschlossen, dann stirbt der Prozess nach fuenf Minuten --
        ohne ``ende``-Satz. Drei Positionen standen unbeaufsichtigt am Broker. Ein
        Mensch hat es 31 Sekunden spaeter bemerkt und von Hand neu gestartet
        (``journal-20260817T151045`` schliesst genau diese drei). Um drei Uhr nachts
        waeren daraus Stunden geworden.

    Ausgerechnet die Metrik, deren Alarmregel „Position offen geblieben" heisst, konnte
    den Fall nicht sehen: er hatte keinen ``ende``-Satz, und sie zaehlte nur ``ende``-
    Saetze. ``laufabschluss`` sah ihn zwar als Fehlschlag, konnte ihn aber nicht von
    dem harmlosen zweiten Abbruch unterscheiden -- und zaehlte gleichzeitig die zwei
    wirklich gefaehrlichen Laeufe als gelungen, weil sie einen ``ende``-Satz hatten.

    Sie fragt jetzt fuer **jeden** Lauf, gleich wie er endete: stand am Ende noch etwas
    offen? Rangfolge der Auskunft in ``_buch_am_ende``.

    DER NENNER -- UND WARUM ER NICHT JEDER LAUF IST
    -----------------------------------------------
    Gezaehlt werden nur Laeufe, die **nachweislich eine Position hielten**. Das ist
    keine Bequemlichkeit, sondern der Riegel gegen die naheliegendste Beschoenigung:
    zwanzig Trockenlaeufe von je zwanzig Sekunden -- zusammen sieben Minuten Arbeit --
    wuerden sonst jede Quote ueber jede Schwelle heben, ohne dass sich am Betrieb das
    Geringste bessert. Ein Lauf ohne Position kann nichts zuruecklassen; er ist weder
    Erfolg noch Fehlschlag.

    Laeufe, bei denen sich weder das eine noch das andere feststellen laesst, sind
    **unbeurteilbar** und stehen nicht im Nenner (V3). Auf diesem Stand sind das 10 von
    21 -- alte Journale, die weder das Positionsfeld noch ``offen_geblieben`` kennen.
    Sie als sauber zu zaehlen waere der schmeichelnde Standardwert; sie koennten beim
    Start ein fremdes Buch uebernommen haben, wie ``journal-20260817T173413`` beweist.
    """
    gelungen = gescheitert = unbeurteilbar = 0
    for lauf in _laeufe(saetze):
        hielt = _hat_gehalten(lauf)
        if hielt is False:
            # Nie eine Position -- nichts zu verlieren, also nicht im Nenner.
            continue
        stand = _buch_am_ende(lauf)
        if hielt is None or stand is None:
            unbeurteilbar += 1
        elif stand:
            gescheitert += 1
        else:
            gelungen += 1
    return Messwert(
        "ausstiegsdeckung",
        gelungen,
        gelungen + gescheitert,
        "Laeufe mit Position",
        unbeurteilbar=unbeurteilbar,
    )


#: Metrikname -> Funktion. **Die eine Stelle**, an der eine Metrik existiert; die
#: Alarmregeln und Ziele unten verweisen nur auf Namen aus diesem Verzeichnis, und ein
#: Dauertor prueft, dass jeder Verweis hier ankommt.
METRIKEN: dict[str, Callable[[Sequence[dict[str, Any]]], Messwert]] = {
    "buchtreue": buchtreue,
    "ausstiegsverlaesslichkeit": ausstiegsverlaesslichkeit,
    "laufabschluss": laufabschluss,
    "ausstiegsdeckung": ausstiegsdeckung,
}


#: Die Ziele. Vorab gesetzt, mit Begruendung -- und der Stand verfehlt alle drei.
#: Sie zu senken, bis sie passen, waere die Schwellenverschiebung, die V6 verbietet.
ZIELE: tuple[Dienstgueteziel, ...] = (
    Dienstgueteziel(
        "Buchtreue",
        "buchtreue",
        0.99,
        "Ein Halt sperrt jede Eroeffnung. Mehr als ein Prozent gesperrte Takte heisst, "
        "dass der Betrieb ueberwiegend mit dem Aufraeumen beschaeftigt ist.",
    ),
    Dienstgueteziel(
        "Ausstiegsverlaesslichkeit",
        "ausstiegsverlaesslichkeit",
        0.95,
        "Ein misslungener Ausstieg laesst Geld am Markt, waehrend das System glaubt, "
        "es sei drauszen. Fuenf Prozent sind schon viel; strenger waere vertretbar.",
    ),
    Dienstgueteziel(
        "Laufabschluss",
        "laufabschluss",
        0.95,
        "Ein Lauf ohne Endsatz zwingt den Wiederanlauf, das Buch vom Broker zu "
        "uebernehmen statt es fortzuschreiben.",
    ),
    Dienstgueteziel(
        "Ausstiegsdeckung",
        "ausstiegsdeckung",
        1.00,
        "Das einzige Ziel ohne Fehlerbudget, und das mit Absicht: ein Lauf, der eine "
        "Position offen zuruecklaesst, laesst Geld am Markt OHNE beaufsichtigenden "
        "Prozess. Dafuer gibt es keinen vertretbaren Anteil -- jeder einzelne Fall ist "
        "einer zu viel. Die Schwelle wurde NACH der Messung gesetzt (3 von 11 "
        "beurteilbaren Laeufen gerissen) und ist strenger als der Befund; eine "
        "nachtraeglich VERSCHAERFTE Schwelle ist nicht die Anpassung, die V6 "
        "verbietet.",
    ),
)


#: Die Alarmregeln. Jede nennt ihre Metrik und ihre Handlung (E-014); beides wird
#: geprueft (tests/test_stufe10_betrieb.py).
ALARMREGELN: tuple[Alarmregel, ...] = (
    Alarmregel(
        "buchtreue_unter_ziel",
        "buchtreue",
        (
            "Zuerst pruefen, ob der Halt ueberhaupt gesperrt hat: ein Reconcile-Halt, "
            "der "
            "im selben Takt halt_erklaert mit weiter_gesperrt=false traegt, hat nichts "
            "blockiert (der Broker hat zwischen zwei Takten geschlossen). Nur Takte "
            "ohne "
            "solche Aufloesung zaehlen. Dann mit tools/dienstguete.py nach Codestand "
            "aufschluesseln und die Ursache im lebenden Code suchen, nicht in alten "
            "Laeufen."
        ),
        0.99,
        "Das Buch und die Meldung des Handelsplatzes gehen zu oft auseinander.",
    ),
    Alarmregel(
        "ausstieg_misslingt",
        "ausstiegsverlaesslichkeit",
        (
            "Im Journal die Saetze schliessen_fehlgeschlagen lesen; das Feld fehler "
            "traegt den Wortlaut des Handelsplatzes. Offene Positionen im Terminal "
            "gegen "
            "das Buch halten. Bei 'Trade disabled' oder 'AutoTrading disabled by "
            "client' "
            "den Schreibpfad im Terminal freigeben und bis dahin von Hand schliessen, "
            "nicht warten. Bei 'Unsupported filling mode' die Fuellart je Symbol "
            "pruefen."
        ),
        0.95,
        "Schliessversuche scheitern -- moeglicherweise steht Geld am Markt.",
    ),
    Alarmregel(
        "position_offen_geblieben",
        "ausstiegsdeckung",
        (
            "Sofort im Terminal nachsehen, welche Positionen offen sind (das Journal "
            "sagt, was der Lauf wusste; der Broker sagt, was ist), und entscheiden: "
            "von "
            "Hand schliessen oder bewusst stehen lassen. Erst danach die Ursache: der "
            "ende-Satz fuehrt die Symbole unter offen_geblieben, die "
            "schliessen_fehlgeschlagen-Saetze davor den Grund."
        ),
        1.00,
        "Ein Lauf ist beendet worden, waehrend eine Position noch offen stand.",
    ),
    Alarmregel(
        "laeufe_brechen_ab",
        "laufabschluss",
        (
            "Kein Sicherheitsalarm: die Kennzahl sagt nicht, ob Geld am Markt blieb "
            "(Nachtrag Laufabschluss des Altstands). Pruefen, ob der Rechner in den "
            "Standby ging (Windows-Ereignisprotokoll, Kernel-Power 42) oder der "
            "Prozess "
            "hart beendet wurde. Fuer offene Positionen gilt der Alarm 'Position offen "
            "geblieben'."
        ),
        0.95,
        "Laeufe enden ohne Endsatz; der Wiederanlauf muss das Buch uebernehmen.",
    ),
)


def erhebe(zeilen: Iterable[str]) -> dict[str, Messwert]:
    """Alle Metriken auf einmal, aus denselben Saetzen."""
    saetze = _saetze(zeilen)
    return {name: fn(saetze) for name, fn in METRIKEN.items()}


#: Codestand eines Laufs, der nicht reproduzierbar ist: das Arbeitsverzeichnis war beim
#: Lauf nicht sauber. Zu welchem Quelltext die Zahlen gehoeren, weiss danach niemand.
NICHT_REPRODUZIERBAR = "+aenderungen"
#: Laeufe aus der Zeit vor der Versionsstempelung.
OHNE_STEMPEL = "ohne Stempel"


def nach_codestand(zeilen: Iterable[str]) -> dict[str, dict[str, Messwert]]:
    """Dieselben Metriken, aber getrennt nach dem Codestand des Laufs.

    WARUM DAS NOETIG IST
    --------------------
    Die Ziele oben urteilen ueber **alle** Journale zusammen. Das ist als Ergebnis
    richtig -- es ist der Betrieb, den es gegeben hat -- aber als **Diagnose**
    unbrauchbar, und zwar in beide Richtungen:

    * Ein behobener Defekt drueckt die Zahl fuer immer. Von den 16 gesperrten Takten
      dieses Standes stammen **alle** aus Codestaenden, die es nicht mehr gibt.
    * Ein neuer Defekt verschwindet in der Geschichte. Der lange Lauf hat 1.122 der
      1.360 Takte; ein Fehler in den uebrigen 238 faellt kaum auf.

    Diese Aufschluesselung beantwortet die Frage, die den Betrieb wirklich leitet:
    **passiert es noch?** Sie ersetzt die Gesamtzahl nicht und darf es nicht -- sonst
    waere sie die bequeme Auswahl der guten Laeufe.

    Zwei Gruppen tragen ihre Einschraenkung im Namen: ``ohne Stempel`` (aus der Zeit
    vor der Versionsstempelung) und alles mit ``+aenderungen`` (das Arbeitsverzeichnis
    war nicht sauber -- zu welchem Quelltext die Zahlen gehoeren, weiss niemand).
    """
    gruppen: dict[str, list[dict[str, Any]]] = {}
    for satz in _saetze(zeilen):
        stand = str(satz.get("version") or OHNE_STEMPEL)
        gruppen.setdefault(stand, []).append(satz)
    return {
        stand: {name: fn(saetze) for name, fn in METRIKEN.items()}
        for stand, saetze in sorted(gruppen.items())
    }


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

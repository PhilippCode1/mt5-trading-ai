"""Ereigniskalender — wann genau ist das Ereignis, in echtem UTC?

WARUM DIESES MODUL
------------------
Die Kandidaten aus Paket 3a haengen an **Ortszeiten**: das Londoner Fixing um 16:00
London, das Tokioter TTM um 09:55 JST, der Rollover um Mitternacht Serverzeit, die
NASDAQ-Schlussauktion um 16:00 New York. Die Kerzen kommen in **Serverzeit**. Und
``RealMt5Terminal._utc`` haengt an diese Serverzeit das Etikett ``UTC``, obwohl sie
keine ist.

Drei Zeitsysteme, und ein Fehler von einer Stunde legt ein Ein-Stunden-Fenster
vollstaendig neben das Ereignis. Dieses Modul ist die einzige Stelle, an der
gedreht wird.

DIE SERVERZEIT IST GEMESSEN, NICHT ANGENOMMEN
----------------------------------------------
``SERVER_TZ`` steht nicht hier, weil es ueblich waere, sondern weil es gemessen wurde:
die Stundenrenditen des Terminals wurden gegen eine unabhaengige Quelle (Dukascopy)
ueber ganze Stundenverschiebungen abgetastet. Das Minimum ist eine Nadel, kein Tal —
bei −3 h 0,28 bp gegen 5,08 bp bei 0 h. Monatsweise wechselt es zwischen −2 h und
−3 h, und die Umschalttage sind die der **EU**-Sommerzeit, nicht der
amerikanischen: am 10.03.2024 (US-Umstellung) aendert sich nichts, am 31.03.2024
(EU) springt es. Liest man die Zeitstempel als naive ``Europe/Helsinki``-Ortszeit,
betraegt die Abweichung in jedem einzelnen Monat des Jahres 0,09 bp.

Belege: ``archiv/ABSCHLUSS-3a/02-DATENLAGE.md`` Abschnitt 3, Rohausgabe in
``archiv/ABSCHLUSS-3a/07-AUSGABEN/gegenprobe.txt``.

``SERVER_TZ`` gilt fuer **historische Kerzen** (die Studie, ``server_zu_utc``). Der
laufende Betrieb dreht seine Zeitstempel NICHT mehr ueber diese Zone: der Versatz
wird zur Laufzeit gemessen (``venue/mt5.py::RealMt5Terminal.messe_serverversatz``,
Befund D20) -- eine feste Zone waere fuer einen Broker mit anderem
Sommerzeittermin 2-4 Wochen im Jahr eine Stunde daneben.

WAS DIESES MODUL NICHT TUT
--------------------------
Es kennt keine Feiertage. Es liefert die **planmaessigen** Zeitpunkte; ob an einem
Zeitpunkt tatsaechlich gehandelt wurde, entscheidet die Kursreihe. Ein Ereignis ohne
Kerze ist kein Ereignis und faellt in der Studie heraus — das ist genauer als jeder
Feiertagskalender, den man pflegen muesste, und es kann nicht veralten.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CALENDAR_POLICY_VERSION = "kalender-v1"

#: Zeitzone der Broker-Serverzeit. **Gemessen** (siehe Modulkopf), nicht angenommen.
SERVER_TZ_NAME = "Europe/Helsinki"
SERVER_TZ = ZoneInfo(SERVER_TZ_NAME)


class KalenderError(ValueError):
    """Der Kalender ist unbrauchbar. Fail-closed: keine Studie."""


def server_zu_utc(ts: datetime) -> datetime:
    """Dreh einen Zeitstempel des Terminals in echtes UTC.

    ``RealMt5Terminal`` liefert Zeitstempel mit ``tzinfo=UTC``, deren Wanduhr die
    Serverzeit ist. Die Drehung liest die Wanduhr als Ortszeit des Servers und rechnet
    sie um. Ein bereits gedrehter Zeitstempel laesst sich daran nicht erkennen — darum
    darf diese Funktion je Zeitstempel **genau einmal** angewandt werden.
    """
    if ts.tzinfo is None:
        raise KalenderError(
            "Zeitstempel ohne Zeitzone. Aus dem Terminal kommt er mit tzinfo=UTC; "
            "fehlt sie, ist unklar, was gedreht werden soll."
        )
    return ts.replace(tzinfo=None).replace(tzinfo=SERVER_TZ).astimezone(UTC)


def verlange_echtes_utc(ts: datetime, wofuer: str) -> datetime:
    """Verlange einen Zeitstempel mit Zone und gib ihn in echtem UTC zurueck.

    Warum das eine eigene Funktion ist: ob :func:`server_zu_utc` schon gelaufen ist,
    sieht man einem Zeitstempel nicht an (Modulkopf). Pruefbar ist nur das Wenige, was
    sich pruefen laesst — dass ueberhaupt eine Zone daranhaengt. Ein naiver Stempel ist
    hier ein Fehler und kein Anlass, UTC zu **raten**: genau dieses Raten
    (``RealMt5Terminal._utc`` haengt das Etikett UTC an Serverzeit) ist die Ursache des
    ganzen Zeitproblems dieses Pakets.

    WAS DIESE FUNKTION NICHT SAGT — und was frueher darauf gebaut wurde: sie stellt
    NICHT fest, dass die Wanduhr echtes UTC zeigt. Ein Stempel aus
    :func:`utc_zu_server` traegt Serverzeit unter dem Etikett ``UTC`` und kommt hier
    anstandslos durch. Wer daraufhin irgendwo ``zeitbasis=echt-utc`` schreibt,
    behauptet mehr, als hier geprueft wurde. Genau dieses Etikett stand bis zu dieser
    Fassung im Kopf der Studienreihe und ist ersatzlos entfallen.

    Die Rueckgabe ist kanonisch (``+00:00``), damit dieselbe Zeitscheibe unter
    verschiedenen Zonen-Etiketten nicht zwei verschiedene Textformen ergibt.
    """
    if ts.tzinfo is None:
        raise KalenderError(
            f"{wofuer}: Zeitstempel {ts.isoformat()} ohne Zeitzone. Aus dem Terminal "
            "kommt er mit Zone; fehlt sie, ist unbekannt, welche Zeitbasis vorliegt — "
            "und geraten wird sie hier nicht."
        )
    return ts.astimezone(UTC)


@dataclass(frozen=True)
class Kandidat:
    """Ein vorregistrierter Kandidat und die Regel, die seine Zeitpunkte erzeugt.

    ``zone`` ist die Zeitzone, in der die Uhrzeit gilt — nicht die des Servers. Das
    Londoner Fixing liegt um 16:00 London, ob der Broker gerade UTC+2 oder UTC+3 fuehrt.
    """

    schluessel: str
    name: str
    instrumente: tuple[str, ...]
    zone_name: str
    uhrzeit: time
    regel: str  # "werktaeglich" oder "monatsende"
    fenster_stunden: float
    konvention: str
    beleg: str

    @property
    def zone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.zone_name)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - Systemfrage
            raise KalenderError(f"Zeitzone {self.zone_name} nicht auffindbar") from exc


#: Das Feld aus §5 des Auftrags, nach der Aussonderung in A1. Die Fensterlaenge ist
#: ueberall 1 h — das Ergebnis der Aufloesungsmessung, nicht eine Vorliebe.
KANDIDATEN: tuple[Kandidat, ...] = (
    Kandidat(
        schluessel="K1",
        name="London-Fixing 16:00",
        instrumente=("EURUSD", "GBPJPY"),
        zone_name="Europe/London",
        uhrzeit=time(16, 0),
        regel="werktaeglich",
        fenster_stunden=1.0,
        konvention=(
            "WM/Reuters-Referenzkurs, taeglich 16:00 Londoner Ortszeit. Indexfonds, "
            "Pensionskassen und Unternehmen rechnen gegen diesen Kurs ab und muessen "
            "ihn darum handeln."
        ),
        beleg=(
            "Konvention, nicht aus den Kursen ableitbar. Nachpruefbar ist nur, dass es "
            "zu diesem Zeitpunkt Kerzen gibt: 259 von 261 Handelstagen in 2024."
        ),
    ),
    Kandidat(
        schluessel="K2",
        name="Tokioter TTM-Fixing 09:55 JST",
        instrumente=("GBPJPY",),
        zone_name="Asia/Tokyo",
        uhrzeit=time(9, 55),
        regel="werktaeglich",
        fenster_stunden=1.0,
        konvention=(
            "Telegraphic Transfer Middle Rate; japanische Banken stellen um 09:55 JST "
            "den Tagesreferenzkurs, gegen den Importeure und Exporteure abrechnen."
        ),
        beleg=(
            "Konvention. Asia/Tokyo kennt keine Sommerzeit, der Versatz ist "
            "ganzjaehrig UTC+9. 09:55 liegt NICHT auf einer Stundengrenze — das "
            "Fenster ist die Kerze, die den Zeitpunkt enthaelt."
        ),
    ),
    Kandidat(
        schluessel="K3",
        name="Monatsende-Fixing",
        instrumente=("GBPJPY",),
        zone_name="Europe/London",
        uhrzeit=time(16, 0),
        regel="monatsende",
        fenster_stunden=1.0,
        konvention=(
            "Dieselbe Gruppe wie K1, am letzten Handelstag des Monats zusaetzlich mit "
            "Quotenabgleich. Die Ableitungsregel ist der letzte Werktag des Monats."
        ),
        beleg=(
            "Abgeleitet, keine Liste. Knappster Kandidat des Feldes: 193 Ereignisse, "
            "Aufloesungsverhaeltnis 0,62."
        ),
    ),
    Kandidat(
        schluessel="K4",
        name="Taeglicher Rollover (Serverzeit-Mitternacht)",
        instrumente=("EURUSD", "GBPJPY"),
        zone_name=SERVER_TZ_NAME,
        uhrzeit=time(0, 0),
        regel="werktaeglich",
        fenster_stunden=1.0,
        konvention=(
            "Wer ueber den Stichzeitpunkt haelt, zahlt oder erhaelt die Finanzierung. "
            "Der Zeitpunkt ist Mitternacht SERVERZEIT und wandert deshalb im Jahr "
            "zwischen 21:00 und 22:00 UTC."
        ),
        beleg=(
            "An den Kursen nachgewiesen: die Tageskerzen des Terminals beginnen an "
            "150 Tagen um 21:00 und an 111 Tagen um 22:00 echtem UTC — die "
            "Tagesgrenze des Servers, nicht die von UTC."
        ),
    ),
    Kandidat(
        schluessel="K5",
        name="NASDAQ-Schlussauktion",
        instrumente=("NVDA",),
        zone_name="America/New_York",
        uhrzeit=time(16, 0),
        regel="werktaeglich",
        fenster_stunden=1.0,
        konvention=(
            "Alle, die zum offiziellen Schlusskurs abrechnen — Indexfonds, ETFs, "
            "Bewertungsstichtage — muessen in der Schlussauktion handeln."
        ),
        beleg=(
            "An den Kursen nachgewiesen: die letzte NVDA-Stundenkerze beginnt an 233 "
            "von 252 Handelstagen um 15:00 New Yorker Zeit, deckt also 15:00-16:00 ab. "
            "Die 19 Ausnahmen liegen samtlich in den Wochen zwischen amerikanischer "
            "und europaeischer Zeitumstellung."
        ),
    ),
)


def _werktage(von: date, bis: date) -> Iterator[date]:
    tag = von
    while tag <= bis:
        if tag.weekday() < 5:
            yield tag
        tag += timedelta(days=1)


def _monatsenden(von: date, bis: date) -> Iterator[date]:
    """Letzter Werktag je Monat im Zeitraum."""
    letzter: date | None = None
    for tag in _werktage(von, bis):
        if letzter is not None and tag.month != letzter.month:
            yield letzter
        letzter = tag
    # Der letzte Monat wird NICHT ausgegeben: solange der Zeitraum in ihm endet, ist
    # unklar, ob sein letzter Werktag schon vorbei ist. Ein halber Monat ist kein Monat.


def ereignisse(kandidat: Kandidat, von: date, bis: date) -> tuple[datetime, ...]:
    """Planmaessige Ereigniszeitpunkte in **echtem UTC**.

    Ob an einem Zeitpunkt gehandelt wurde, entscheidet die Kursreihe, nicht diese Liste
    (siehe Modulkopf). Wochenenden fallen hier schon heraus, Feiertage nicht.
    """
    if bis < von:
        raise KalenderError(f"Zeitraum laeuft rueckwaerts: {von} bis {bis}")
    tage = (
        _monatsenden(von, bis)
        if kandidat.regel == "monatsende"
        else _werktage(von, bis)
    )
    if kandidat.regel not in ("werktaeglich", "monatsende"):
        raise KalenderError(f"Unbekannte Regel: {kandidat.regel}")
    zone = kandidat.zone
    aus: list[datetime] = []
    for tag in tage:
        ortszeit = datetime.combine(tag, kandidat.uhrzeit, tzinfo=zone)
        aus.append(ortszeit.astimezone(UTC))
    return tuple(aus)


def kandidat(schluessel: str) -> Kandidat:
    for k in KANDIDATEN:
        if k.schluessel == schluessel:
            return k
    raise KalenderError(
        f"Kandidat {schluessel!r} steht nicht im Feld — bekannt sind "
        f"{[k.schluessel for k in KANDIDATEN]}"
    )


@dataclass(frozen=True)
class Ereigniskalender:
    """Die geladene Kalenderdatei."""

    calendar_id: str
    calendar_version: str
    verified_on: str
    server_tz: str
    server_tz_beleg: str
    kandidaten: tuple[Kandidat, ...]


def default_calendar_path() -> Path:
    """Suche aufwaerts nach ``config/ereigniskalender.json`` (wie bei den Kosten)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        kandidatenpfad = parent / "config" / "ereigniskalender.json"
        if kandidatenpfad.is_file():
            return kandidatenpfad
    raise KalenderError(
        "config/ereigniskalender.json nicht gefunden. Kein Ersatzkalender: ohne "
        "gepruefte Zeitpunkte laeuft keine Studie."
    )


def load_ereigniskalender(path: Path | None = None) -> Ereigniskalender:
    """Lade die Kalenderdatei. Jeder Mangel ist ein Fehler, kein Standardwert.

    Die Datei ist die **nachpruefbare Ablage** dessen, was in ``KANDIDATEN`` als Code
    steht. Weichen beide voneinander ab, laedt nichts: eine Studie, die gegen eine
    andere Zeitliste laeuft als die, die dokumentiert ist, waere nicht nachvollziehbar.
    """
    pfad = path or default_calendar_path()
    try:
        roh: Any = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KalenderError(f"{pfad} nicht lesbar: {exc}") from exc
    if not isinstance(roh, dict):
        raise KalenderError(f"{pfad}: Wurzel ist kein Objekt")

    for feld in (
        "calendar_id",
        "calendar_version",
        "verified_on",
        "server_tz",
        "server_tz_beleg",
        "kandidaten",
    ):
        if feld not in roh:
            raise KalenderError(f"{pfad}: Feld {feld!r} fehlt")

    if roh["calendar_id"] != CALENDAR_POLICY_VERSION:
        raise KalenderError(
            f"{pfad}: calendar_id {roh['calendar_id']!r} passt nicht zum Modul "
            f"({CALENDAR_POLICY_VERSION!r}) — Datei und Code sind auseinandergelaufen"
        )
    if roh["server_tz"] != SERVER_TZ_NAME:
        raise KalenderError(
            f"{pfad}: server_tz {roh['server_tz']!r} weicht vom gemessenen Wert "
            f"{SERVER_TZ_NAME!r} ab. Ein anderer Broker braucht eine EIGENE Messung, "
            "keinen geaenderten Eintrag."
        )
    if not str(roh["server_tz_beleg"]).strip():
        raise KalenderError(
            f"{pfad}: server_tz_beleg ist leer — die Zeitzone ist die "
            "empfindlichste Zahl des Pakets und braucht ihren Nachweis"
        )

    datei_schluessel = [k.get("schluessel") for k in roh["kandidaten"]]
    code_schluessel = [k.schluessel for k in KANDIDATEN]
    if datei_schluessel != code_schluessel:
        raise KalenderError(
            f"{pfad}: Kandidaten {datei_schluessel} weichen vom Code "
            f"{code_schluessel} ab"
        )
    for eintrag, k in zip(roh["kandidaten"], KANDIDATEN, strict=True):
        for feld, erwartet in (
            ("zone", k.zone_name),
            ("uhrzeit", k.uhrzeit.isoformat(timespec="minutes")),
            ("regel", k.regel),
            ("instrumente", list(k.instrumente)),
        ):
            if eintrag.get(feld) != erwartet:
                raise KalenderError(
                    f"{pfad}: {k.schluessel}.{feld} ist {eintrag.get(feld)!r}, "
                    f"der Code sagt {erwartet!r}"
                )

    return Ereigniskalender(
        calendar_id=str(roh["calendar_id"]),
        calendar_version=str(roh["calendar_version"]),
        verified_on=str(roh["verified_on"]),
        server_tz=str(roh["server_tz"]),
        server_tz_beleg=str(roh["server_tz_beleg"]),
        kandidaten=KANDIDATEN,
    )

"""Handelspausen aus der Sitzungstabelle -- und die Gap-Sperre davor (Befund D13).

WARUM DIESES MODUL
------------------
Der Betrieb kannte bis Auftrag 1 keine Sperre vor dem Wochenende: eine Eroeffnung um
Freitag 20:59 UTC lief durch alle Tore, und ab 21:00 UTC nimmt der FX-Platz keine
Schliessung mehr an (Bewertung 2026-09-02, Z. 112; ``config/instrument_catalog.json``,
``_fx_sessions``). Die Position stand dann ohne Aufsicht ueber die Wochenendluecke --
der einzige Zustand, in dem ein Stop nicht greift, weil kein Kurs gestellt wird.

Die Sperre ist **rein rechnerisch** und arbeitet allein auf der Sitzungstabelle des
Katalogs. Dieselbe Tabelle darf laut ``_sessions_status`` nur **verengen** (sie kann
einen Platz schliessen, nie oeffnen); genau so wirkt sie hier: die Gap-Sperre lehnt ab,
sie gibt nichts frei. Ob der Platz gerade Preise druckt, bleibt Sache des Kursstroms
(``Mt5Venue._markt_druckt_preise``); eine Schliessung wird von dieser Sperre nie
beruehrt -- sie steht nur im eroeffnenden Zweig (``Mt5Venue._enforce_gap_sperre``).

DIE ZAHLEN
----------
``vorlauf`` (120 min) und ``mindestpause`` (24 h) stehen als Katalogblock
``_gap_sperre`` in ``config/instrument_catalog.json`` mit Herkunft; im Code liegt der
konservative Standard (``venue/catalog.py::GAP_SPERRE_STANDARD``), den die Datei nur
**verengen** darf (laengerer Vorlauf, kuerzere Mindestpause). Beide Zahlen sind eine
Annahme, keine Messung -- gemessen ist nur der Schnitt selbst (Freitag 21:00 UTC).
Warum 24 h als Mindestpause: die taegliche Luecke des FX-Fensters (21:00-24:00 UTC,
3 h) ist keine Wochenendluecke, ein Index-CFD mit Kassa-Sitzung haette naechtliche
Pausen von 16 h; erst eine Pause ueber einen ganzen Tag ist die Luecke, ueber die
kein Stop traegt. Warum 120 min Vorlauf: die Hoechsthaltedauer des Betriebs (4 h,
``tools/live_betrieb.py --max-haltedauer``) ist laenger; der Vorlauf sperrt damit nicht
jede Position, die in die Pause laufen koennte, sondern nur die, die sicher nicht
mehr regulaer schliesst. Wer den Vorlauf an die Haltedauer koppeln will, tut das im
Aufrufer, nicht hier (siehe ``PROGRAMM/auftrag-01-fundament/plan.md``, T6).

WAS EINE PAUSE IST
------------------
Die Sitzungsfenster einer Woche werden zu Bloecken zusammengelegt (angrenzende und
ueberlappende Fenster verschmelzen, ein Fenster ueber Sonntag 24:00 wird auf den
Montag umgebrochen). Eine **Pause** ist der Abstand zwischen dem Ende eines Blocks
und dem Anfang des naechsten, zyklisch ueber die Wochengrenze. Ein Instrument, dessen
Bloecke die ganze Woche decken (BTCUSD: Mo-So 00:00-24:00), hat keine Pause -- und
darum nie eine Gap-Sperre.

``naechste_pause(sessions, jetzt)``: liegt ``jetzt`` in einem Block, ist es die Pause
an dessen Ende; liegt ``jetzt`` bereits in einer Pause, ist es **diese** Pause (ihr
Beginn liegt dann in der Vergangenheit, und die Sperre greift -- eine Eroeffnung in
der Wochenendluecke ist genau der Fall, den sie verhindern soll).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mt5_trading_ai.venue.catalog import (
    MINUTEN_JE_TAG,
    InstrumentCatalogError,
    session_minutes,
)
from mt5_trading_ai.venue.protocol import TradingSession

#: Minuten einer Woche; Sitzungsfenster leben in Minuten seit Montag 00:00 UTC.
MINUTEN_JE_WOCHE = 7 * MINUTEN_JE_TAG

#: Ablehnungsgrund der Gap-Sperre (``OrderRejectedError.reason``).
GRUND_GAP_SPERRE = "weekend_gap_lock"


@dataclass(frozen=True)
class Pause:
    """Eine Handelspause: halboffen ``[beginn, ende)`` in echtem UTC."""

    beginn: datetime
    ende: datetime

    @property
    def dauer(self) -> timedelta:
        return self.ende - self.beginn


def _utc_pflicht(jetzt: datetime) -> datetime:
    """Ein naiver Zeitpunkt wird nicht als UTC geraten (wie ``is_trading_open``)."""
    if jetzt.tzinfo is None or jetzt.utcoffset() is None:
        raise ValueError(
            "naechste_pause braucht einen zonenbewussten Zeitpunkt -- ein naiver "
            "Stempel macht Wochentag und Uhrzeit zu geratenen Groessen"
        )
    return jetzt.astimezone(UTC)


def wochenbloecke(sessions: tuple[TradingSession, ...]) -> tuple[tuple[int, int], ...]:
    """Sitzungsfenster als zusammengelegte Bloecke ``[anfang, ende)`` in Minuten seit
    Montag 00:00, alle innerhalb ``0..MINUTEN_JE_WOCHE``.

    Dieselben drei Pruefungen wie ``venue/mt5.py::_sitzungsfenster`` und
    ``venue/catalog.py::_parse_sessions`` (Wochentag 0..6, Beginn nicht am Tagesende,
    Beginn ungleich Ende) -- hier ein drittes Mal, aus demselben Grund, der dort steht:
    ein handgebautes Fenster ohne Pruefung ist ein Fenster, das still nie oder immer
    greift. Wer eine der Regeln aendert, aendert alle drei Stellen.
    """
    roh: list[tuple[int, int]] = []
    for session in sessions:
        if not 0 <= session.weekday <= 6:
            raise InstrumentCatalogError(
                f"Sitzung mit Wochentag {session.weekday} (erlaubt 0..6, 0 = Montag)"
            )
        auf = session_minutes(session.open_utc)
        zu = session_minutes(session.close_utc)
        if auf >= MINUTEN_JE_TAG:
            raise InstrumentCatalogError(
                f"Sitzungsbeginn {session.open_utc!r} liegt am Tagesende"
            )
        if auf == zu:
            raise InstrumentCatalogError(
                f"Sitzung {session.open_utc!r}-{session.close_utc!r} ist mehrdeutig"
            )
        dauer = zu - auf if zu > auf else (MINUTEN_JE_TAG - auf) + zu
        anfang = session.weekday * MINUTEN_JE_TAG + auf
        ende = anfang + dauer
        if ende > MINUTEN_JE_WOCHE:
            # Sonntag 22:00 -> Montag 06:00: auf zwei Stuecke der Woche umbrechen.
            roh.append((anfang, MINUTEN_JE_WOCHE))
            roh.append((0, ende - MINUTEN_JE_WOCHE))
        else:
            roh.append((anfang, ende))
    roh.sort()
    bloecke: list[tuple[int, int]] = []
    for anfang, ende in roh:
        if bloecke and anfang <= bloecke[-1][1]:
            bloecke[-1] = (bloecke[-1][0], max(bloecke[-1][1], ende))
        else:
            bloecke.append((anfang, ende))
    return tuple(bloecke)


def naechste_pause(
    sessions: tuple[TradingSession, ...], jetzt: datetime
) -> Pause | None:
    """Die naechste (oder laufende) Handelspause ab ``jetzt`` -- ``None``, wenn die
    Tabelle keine kennt (keine Fenster, oder Fenster ueber die ganze Woche).

    ``None`` bei leerer Tabelle ist keine Freigabe: ob ueberhaupt ein Fenster deckt,
    beantwortet ``Mt5Venue.is_trading_open``; diese Funktion beantwortet nur, wann
    das naechste Fenster endet und wie lange die Luecke danach ist.
    """
    zeit = _utc_pflicht(jetzt)
    bloecke = wochenbloecke(sessions)
    if not bloecke:
        return None
    if bloecke == ((0, MINUTEN_JE_WOCHE),):
        return None  # rund um die Uhr, sieben Tage: keine Pause
    minute = zeit.weekday() * MINUTEN_JE_TAG + zeit.hour * 60 + zeit.minute
    montag = zeit - timedelta(
        minutes=minute, seconds=zeit.second, microseconds=zeit.microsecond
    )
    # Zwei Wochen hintereinander, damit die Luecke ueber Sonntag 24:00 ohne Sonderfall
    # als Abstand zweier Nachbarn erscheint.
    doppelt = list(bloecke) + [
        (a + MINUTEN_JE_WOCHE, e + MINUTEN_JE_WOCHE) for a, e in bloecke
    ]
    # Der erste Block, der NACH der Minute beginnt (existiert: die zweite Woche liegt
    # ganz hinter jeder Minute der ersten).
    k = next(i for i, (a, _) in enumerate(doppelt) if a > minute)
    vorher_ende = doppelt[k - 1][1] if k > 0 else bloecke[-1][1] - MINUTEN_JE_WOCHE
    if vorher_ende > minute:
        # ``jetzt`` liegt im Block k-1: Pause an dessen Ende. Zyklische Nachbarn ohne
        # Abstand (letzter Block endet Sonntag 24:00, erster beginnt Montag 00:00)
        # sind keine Pause -- weiter zum naechsten Abstand.
        j = k - 1
        while doppelt[j][1] >= doppelt[j + 1][0]:
            j += 1
        beginn_min, ende_min = doppelt[j][1], doppelt[j + 1][0]
    else:
        # ``jetzt`` liegt bereits in der Pause zwischen Block k-1 und Block k.
        beginn_min, ende_min = vorher_ende, doppelt[k][0]
    return Pause(
        beginn=montag + timedelta(minutes=beginn_min),
        ende=montag + timedelta(minutes=ende_min),
    )


def gap_sperre(
    sessions: tuple[TradingSession, ...],
    jetzt: datetime,
    *,
    vorlauf: timedelta,
    mindestpause: timedelta,
) -> str | None:
    """``weekend_gap_lock``, wenn in weniger als ``vorlauf`` eine Pause von mindestens
    ``mindestpause`` beginnt (oder schon laeuft) -- sonst ``None``.

    Nur eine Richtung: die Funktion kann eine Eroeffnung sperren, nie eine erlauben.
    ``None`` heisst "diese Sperre greift nicht", nicht "der Platz ist offen".
    """
    if vorlauf <= timedelta(0):
        raise ValueError("vorlauf muss positiv sein")
    if mindestpause <= timedelta(0):
        raise ValueError("mindestpause muss positiv sein")
    zeit = _utc_pflicht(jetzt)
    pause = naechste_pause(sessions, zeit)
    if pause is None or pause.dauer < mindestpause:
        return None
    if pause.beginn - zeit < vorlauf:
        return GRUND_GAP_SPERRE
    return None

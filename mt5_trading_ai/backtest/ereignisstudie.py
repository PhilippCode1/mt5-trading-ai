"""Ereignisstudie — traegt eine bekannte Zwangslage mehr als ihre Kosten?

DIE HYPOTHESE, VORAB FESTGELEGT
--------------------------------
Alle fuenf Kandidaten sind **Zwangslagen**: eine benannte Gruppe muss zu einem benannten
Zeitpunkt handeln, gleich zu welchem Preis. Die Mikrostruktur sagt dazu etwas Bestimmtes
voraus — nicht „der Kurs steigt" oder „der Kurs faellt", sondern:

    Der erzwungene Handel drueckt den Kurs in eine Richtung, und wer dagegenhaelt, wird
    dafuer mit der Rueckkehr bezahlt.

Das ist **Preisdruck und Umkehr**. Das Vorzeichen der Erwartung ist damit nicht
konstant, sondern folgt der Richtung, in die vor dem Ereignis gedrueckt wurde::

    Vorzeichen(e) = -sign(Rendite der Stunde VOR dem Ereignis)

WARUM NICHT EIN FESTES VORZEICHEN
----------------------------------
Weil es fuer keinen dieser Kandidaten begruendbar waere. Ob am Londoner Fixing per Saldo
Euro gekauft oder verkauft werden muss, haengt an der Auftragslage des Tages; ob der
Rollover den Halter belastet oder entlastet, haengt am Zinsunterschied, und der hat in
sechzehn Jahren mehrfach das Vorzeichen gewechselt. Ein festes ``+1`` waere ein
Muenzwurf mit Begruendungstext davor — und die Deflation, die diese Studie
ueberstehen muss, ist gerade dafuer gebaut, so etwas zu bestrafen.

Das bedingte Vorzeichen benutzt **ausschliesslich Information vor dem Fenster**. Die
Stunde vor dem Ereignis ist abgeschlossen, bevor die Stunde danach beginnt; es
gibt keinen Blick nach vorn. Genau eine Hypothese je Kandidat, und sie steht hier, bevor
gemessen wird — eine nachtraegliche Aenderung waere ein zweiter Versuch (M7).

WAS „HANDELBAR" HEISST
----------------------
Das Fenster beginnt am ersten Kerzenanfang **ab** dem Ereignis, nie davor, und die
Rendite wird von der **Eroeffnung** dieser Kerze bis zu ihrem Schluss gerechnet. Das
ist die Bewegung, die jemand haette mitnehmen koennen, der erst zum Ereignis handeln
darf. Wer statt der Eroeffnung den vorigen Schluss nimmt, verdient am Sprung ueber die
Kerzengrenze mit — an einem Kurs also, den es zum Einstiegszeitpunkt nicht mehr gab.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio

STUDY_POLICY_VERSION = "ereignisstudie-v1"

#: Hypothese je Kandidat. Bewusst fuer alle dieselbe — sie folgt aus der Zwangslage,
#: nicht aus dem Instrument, und je Kandidat gilt genau eine.
HYPOTHESE = "umkehr"

#: M6.1: der vorzeichenbereinigte Median muss dieses Vielfache von K erreichen.
M61_FAKTOR = 3.0
#: M6.2, zeitliche Stabilitaet: in BEIDEN Zeithaelften dieses Vielfache.
M62_STABIL_FAKTOR = 1.5
#: M6.2, Deflation: dieselbe Schwelle wie ``gates/criteria.py`` und ``ABBRUCH.md``.
M62_DSR_SCHWELLE = 0.95
#: M6.2, Randomisierung: so viele verschobene Ereignismengen, so viel darf durchkommen.
M62_ZIEHUNGEN = 1000
M62_ZUFALL_ANTEIL = 0.05
#: Budgetobergrenze aus §5 — die strengste zulaessige Annahme fuer die Deflation.
VERSUCHE_ANGENOMMEN = 12
#: Erste zwei Drittel In-Sample, letztes Drittel Out-of-Sample. Einmal gezogen.
OOS_ANTEIL = 1.0 / 3.0


class StudienError(ValueError):
    """Die Studie ist nicht rechenbar. Fail-closed: kein Ergebnis."""


@dataclass(frozen=True)
class Kerze:
    """Was die Studie von einer Kerze braucht."""

    ts: datetime
    open: float
    close: float


@dataclass(frozen=True)
class Ereigniswert:
    """Ein Ereignis, das gemessen werden konnte."""

    ts: datetime
    roh_bps: float
    vorzeichen: int

    @property
    def bereinigt_bps(self) -> float:
        return self.roh_bps * self.vorzeichen


@dataclass(frozen=True)
class Bestaetigung:
    """Die drei Pruefungen aus M6.2."""

    dsr_oos: float
    dsr_n: int
    dsr_bestanden: bool
    haelfte_frueh_bps: float
    haelfte_spaet_bps: float
    stabil_bestanden: bool
    zufall_anteil: float
    zufall_bestanden: bool

    @property
    def bestanden(self) -> bool:
        return self.dsr_bestanden and self.stabil_bestanden and self.zufall_bestanden


@dataclass(frozen=True)
class Ergebnis:
    """Das Ergebnis einer Studie. Brutto steht nie ohne Netto."""

    kandidat: str
    instrument: str
    hypothese: str
    fenster_stunden: float
    n_ereignisse: int
    n_gemessen: int
    brutto_bps: float
    p25_bps: float
    p75_bps: float
    trefferanteil: float
    k_bps: float
    netto_bps: float
    m61_schwelle_bps: float

    @property
    def m61_bestanden(self) -> bool:
        return self.brutto_bps >= self.m61_schwelle_bps


def _kerzen_index(kerzen: list[Kerze]) -> list[datetime]:
    return [k.ts for k in kerzen]


def _erste_kerze_ab(
    kerzen: list[Kerze], stempel: list[datetime], ab: datetime
) -> int | None:
    """Index der ersten Kerze, die **nicht vor** ``ab`` beginnt. Binaere Suche."""
    lo, hi = 0, len(kerzen)
    while lo < hi:
        mid = (lo + hi) // 2
        if stempel[mid] < ab:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(kerzen) else None


def messe_ereignis(
    kerzen: list[Kerze],
    stempel: list[datetime],
    ereignis: datetime,
    *,
    fenster_stunden: float,
    balkenstunden: float,
    max_luecke: timedelta = timedelta(hours=2),
) -> Ereigniswert | None:
    """Rendite ab dem ersten handelbaren Kerzenanfang, mit Vorzeichen aus der Vorstunde.

    Gibt ``None``, wenn das Ereignis nicht messbar ist — kein Handel in der Naehe,
    keine Vorkerze, oder eine Luecke zwischen Vorkerze und Fensterkerze. Ein Ereignis
    ohne Kurse ist kein Ereignis; es faellt heraus und wird nicht geraten.
    """
    i = _erste_kerze_ab(kerzen, stempel, ereignis)
    if i is None or i == 0:
        return None
    fenster = kerzen[i]
    # Zu weit weg heisst: das Ereignis fiel in eine Handelspause (Feiertag, Wochenende).
    if fenster.ts - ereignis > max_luecke:
        return None
    vor = kerzen[i - 1]
    if fenster.ts - vor.ts > max_luecke:
        return None
    if vor.open <= 0 or fenster.open <= 0:
        raise StudienError(f"Kurs <= 0 bei {fenster.ts}")

    vor_rendite = (vor.close - vor.open) / vor.open
    if vor_rendite == 0.0:
        return None  # keine Richtung, kein Vorzeichen — die Erwartung sagt hier nichts
    vorzeichen = -1 if vor_rendite > 0 else 1

    # Mehrere Kerzen, falls das Fenster laenger ist als ein Balken.
    balken = max(1, int(round(fenster_stunden / balkenstunden)))
    ende_index = i + balken - 1
    if ende_index >= len(kerzen):
        return None
    ende = kerzen[ende_index]
    if ende.ts - fenster.ts > max_luecke * balken:
        return None
    roh = (ende.close - fenster.open) / fenster.open * 10_000.0
    return Ereigniswert(ts=fenster.ts, roh_bps=roh, vorzeichen=vorzeichen)


def balkenstunden(kerzen: list[Kerze]) -> float:
    """Laenge eines Balkens in Stunden, aus der Reihe selbst.

    Einmal je Reihe bestimmt und dann durchgereicht: die Randomisierung ruft
    ``messe_ereignis`` millionenfach, und ein Median ueber 200 Abstaende je Aufruf
    waere dort der teuerste Teil der Rechnung.
    """
    if len(kerzen) < 2:
        raise StudienError("Zu wenige Kerzen, um die Balkenlaenge zu bestimmen")
    schritte = [
        (kerzen[i + 1].ts - kerzen[i].ts).total_seconds() / 3600.0
        for i in range(min(200, len(kerzen) - 1))
    ]
    return statistics.median(schritte)


def studie(
    *,
    kandidat: str,
    instrument: str,
    kerzen: list[Kerze],
    ereignisse: list[datetime],
    fenster_stunden: float,
    k_bps: float,
) -> tuple[Ergebnis, list[Ereigniswert]]:
    """Die Messung. Brutto, Streuung, Trefferanteil, Netto — alles in einem Zug."""
    if k_bps <= 0:
        raise StudienError(f"K muss positiv sein: {k_bps}")
    if not kerzen:
        raise StudienError("Keine Kerzen")
    stempel = _kerzen_index(kerzen)
    bs = balkenstunden(kerzen)
    werte = [
        w
        for e in ereignisse
        if (w := messe_ereignis(
            kerzen, stempel, e, fenster_stunden=fenster_stunden, balkenstunden=bs))
        is not None
    ]
    if len(werte) < 30:
        raise StudienError(
            f"{kandidat}/{instrument}: nur {len(werte)} messbare Ereignisse von "
            f"{len(ereignisse)} — zu wenige fuer eine Aussage"
        )
    bereinigt = [w.bereinigt_bps for w in werte]
    brutto = statistics.median(bereinigt)
    q = statistics.quantiles(bereinigt, n=4)
    return (
        Ergebnis(
            kandidat=kandidat,
            instrument=instrument,
            hypothese=HYPOTHESE,
            fenster_stunden=fenster_stunden,
            n_ereignisse=len(ereignisse),
            n_gemessen=len(werte),
            brutto_bps=brutto,
            p25_bps=q[0],
            p75_bps=q[2],
            trefferanteil=sum(1 for x in bereinigt if x > 0) / len(bereinigt),
            k_bps=k_bps,
            netto_bps=brutto - k_bps,
            m61_schwelle_bps=M61_FAKTOR * k_bps,
        ),
        werte,
    )


def bestaetige(
    werte: list[Ereigniswert],
    *,
    kerzen: list[Kerze],
    ereignisse: list[datetime],
    fenster_stunden: float,
    k_bps: float,
    saat: int,
) -> Bestaetigung:
    """M6.2 — die drei Pruefungen. Keine davon ist ein Versuch (M7)."""
    if len(werte) < 30:
        raise StudienError("Zu wenige Werte fuer die Bestaetigung")
    geordnet = sorted(werte, key=lambda w: w.ts)
    bereinigt = [w.bereinigt_bps for w in geordnet]
    gemessener_median = statistics.median(bereinigt)

    # (1) Deflation auf dem letzten Drittel.
    schnitt = int(len(bereinigt) * (1.0 - OOS_ANTEIL))
    oos = bereinigt[schnitt:]
    if len(oos) < 20:
        raise StudienError(f"Out-of-Sample-Drittel zu klein: {len(oos)}")
    streuung = statistics.stdev(oos)
    sharpe = statistics.fmean(oos) / streuung if streuung > 0 else 0.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=sharpe, observations=len(oos), trials=VERSUCHE_ANGENOMMEN
    )

    # (2) Zeitliche Stabilitaet: beide Haelften.
    mitte = len(bereinigt) // 2
    frueh = statistics.median(bereinigt[:mitte])
    spaet = statistics.median(bereinigt[mitte:])
    schwelle = M62_STABIL_FAKTOR * k_bps

    # (3) Randomisierung: verschobene Ereignismengen. Verschoben wird um ganze Tage,
    #     damit die Tageszeit erhalten bleibt — sonst pruefte der Test die Tageszeit
    #     statt das Ereignis, und jede Uhrzeit mit anderer Liquiditaet bestuende ihn.
    stempel = _kerzen_index(kerzen)
    bs = balkenstunden(kerzen)
    wuerfel = random.Random(saat)
    treffer = 0
    for _ in range(M62_ZIEHUNGEN):
        tage = wuerfel.choice([d for d in range(-30, 31) if abs(d) >= 3])
        verschoben = [e + timedelta(days=tage) for e in ereignisse]
        proben = [
            w.bereinigt_bps
            for e in verschoben
            if (w := messe_ereignis(
                kerzen, stempel, e, fenster_stunden=fenster_stunden,
                balkenstunden=bs))
            is not None
        ]
        if len(proben) >= 30 and statistics.median(proben) >= gemessener_median:
            treffer += 1
    anteil = treffer / M62_ZIEHUNGEN

    return Bestaetigung(
        dsr_oos=dsr,
        dsr_n=len(oos),
        dsr_bestanden=dsr >= M62_DSR_SCHWELLE,
        haelfte_frueh_bps=frueh,
        haelfte_spaet_bps=spaet,
        stabil_bestanden=frueh >= schwelle and spaet >= schwelle,
        zufall_anteil=anteil,
        zufall_bestanden=anteil <= M62_ZUFALL_ANTEIL,
    )

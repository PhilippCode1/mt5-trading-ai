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

DIE VERSUCHSZAHL STEHT NICHT HIER
---------------------------------
Die Deflation rechnete frueher gegen eine Konstante ``VERSUCHE_ANGENOMMEN = 12``, die
Budgetobergrenze aus §5 des Auftrags. Eine Konstante sagt aber nichts darueber, wie
viel tatsaechlich gesucht wurde — sie ist genau dann falsch, wenn es darauf ankommt:
zu streng, solange wenig gemessen wurde, und zu milde, sobald mehr gemessen wird als
geplant war. Die Zahl kommt jetzt aus dem Register
(``gates/trials.py::deflation_trials``), und ein fehlendes Register ist ein Fehler.

Gezaehlt wird die **Kampagne**, nicht der Registerstand zur Aufrufzeit. Die Reihe
schreibt nach jeder Studie an; wer beim Rechnen den Stand liest, bekaeme eine Zahl,
die davon abhaengt, als wievielte eine Studie gefahren wurde — bei Registerstand
sieben saehe die erste acht Versuche (DSR 0,7550), die siebte vierzehn (DSR 0,6594),
bei gleichen Daten. Eine Kennzahl, die man nicht nachrechnen kann, belegt nichts.
:func:`kampagne` meldet die vorregistrierte Groesse des Feldes an das Register; die
Zaehlregel steht in ``gates/trials.py::deflation_trials``.

DIE PRUEFSUMME — WAS SIE DECKT UND WAS OFFEN IST
-------------------------------------------------
Die Herkunftsangabe einer Studie stammte aus den Manifesten in ``config/reihen``. Die
tragen ausweislich ihres eigenen Feldes ``zeitbasis`` die **ungedrehten** Serverstempel
und den Datenstand ihres Abrufs; gemessen wird dagegen auf **gedrehten** und bei jedem
Lauf neu geholten Kerzen. Diese Pruefsumme konnte die gemessenen Daten also von Bauart
her nicht decken — ein Etikett, das nichts deckt, ist schlechter als keines, weil es
Nachpruefbarkeit vortaeuscht. Darum leitet :func:`reihen_pruefsumme` die Zahl aus genau
der Kerzenreihe ab, die gemessen wird, und ``Ergebnis.reihen_pruefsumme`` fuehrt sie
mit. Sie belegt genau eines: dass zwei Laeufe mit gleicher Zahl dieselben Kerzen
gesehen haben. Ob diese Kerzen richtig gedreht sind, sieht man ihnen nicht an, und die
Zahl behauptet es auch nicht.

OFFEN — hier benannt statt mit Geschirr verkleidet: der Registereintrag traegt diese
Zahl noch **nicht**. ``tools/ereignisstudie.py`` schreibt weiter die Manifest-Pruefsumme
als ``data_checksum``, und neben dem Befund liegt keine eingefrorene Reihe. Eine
fruehere Fassung dieses Moduls hatte dafuer ``friere_reihe_ein``, ``lade_reihe`` und
``pruefe_deckung`` — mit Tests, aber ohne einen einzigen Aufrufer ausserhalb dieser
Datei und der Tests. Einer Pruefung, der nie eine Erwartung uebergeben wird, kann nicht
ausloesen; sie sieht nur erledigt aus, und das ist schlechter als der offene Mangel.
Sie ist deshalb entfernt. Wer sie zurueckholt, verdrahtet sie im selben Zug in
``tools/ereignisstudie.py`` — sonst entsteht dieselbe Fassade noch einmal.
"""

from __future__ import annotations

import hashlib
import random
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from mt5_trading_ai.backtest.kalender import KANDIDATEN, verlange_echtes_utc
from mt5_trading_ai.gates import trials as register
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio

STUDY_POLICY_VERSION = "ereignisstudie-v1"

#: Hypothese je Kandidat. Bewusst fuer alle dieselbe — sie folgt aus der Zwangslage,
#: nicht aus dem Instrument, und je Kandidat gilt genau eine.
HYPOTHESE = "umkehr"

#: M6.1: der vorzeichenbereinigte Median muss dieses Vielfache von K erreichen.
M61_FAKTOR = 3.0
#: M6.2, zeitliche Stabilitaet: in BEIDEN Zeithaelften dieses Vielfache.
M62_STABIL_FAKTOR = 1.5
#: M6.2, Deflation: dieselbe Schwelle wie ``gates/criteria.py`` und
#: ``archiv/ABBRUCH.md``.
M62_DSR_SCHWELLE = 0.95
#: M6.2, Randomisierung: so viele verschobene Ereignismengen, so viel darf durchkommen.
M62_ZIEHUNGEN = 1000
M62_ZUFALL_ANTEIL = 0.05
#: Erste zwei Drittel In-Sample, letztes Drittel Out-of-Sample. Einmal gezogen.
OOS_ANTEIL = 1.0 / 3.0
#: Kanonische Textform, ueber die :func:`reihen_pruefsumme` hasht. Die Kopfzeile nennt
#: Format und Spalten, damit zwei verschiedene Formen nicht dieselbe Zahl ergeben
#: koennen. Sie nennt bewusst KEINE Zeitbasis: dass die Stempel echtes UTC tragen,
#: laesst sich nicht pruefen (``kalender.py``), und ein Etikett, das der Schreiber
#: nicht decken kann, ist genau der Mangel, gegen den dieses Modul gebaut wurde.
#: v2, weil v1 dieses Etikett noch trug -- gleiche Form, gleiche Zahl gilt nur je
#: Version.
REIHEN_FORMAT_VERSION = "ereignisreihe-v2"
_REIHEN_SPALTEN = "ts,open,close"

#: Praefix der ``strategy_id``, unter der ``tools/ereignisstudie.py`` die Laeufe dieser
#: Reihe ins Register schreibt (``ereignisstudie/K1`` usw.).
KAMPAGNE_PRAEFIX = "ereignisstudie/"


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
    #: Versuchszahl, gegen die deflationiert wurde — aus dem Register, in ganzen
    #: Kampagnen gezaehlt. Sie steht im Ergebnis, weil eine DSR ohne ihre Versuchszahl
    #: nicht nachvollziehbar ist: 0,755 bei acht Versuchen und 0,984 bei einem sind
    #: dieselbe Messung.
    dsr_versuche: int
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
    #: Pruefsumme der Reihe, auf der GEMESSEN wurde — abgeleitet, nicht mitgebracht.
    #: Das ist der Wert, der als ``data_checksum`` ins Register gehoert; ein aus einem
    #: Manifest gelesener deckt eine andere Reihe (siehe Modulkopf). Er steht dort
    #: heute NICHT — ``tools/ereignisstudie.py`` schreibt weiter die Manifestzahl; der
    #: Modulkopf fuehrt das unter „OFFEN". Pflichtfeld ohne Vorgabewert: ein leeres
    #: Herkunftsfeld waere wieder ein Etikett ohne Deckung.
    reihen_pruefsumme: str

    @property
    def m61_bestanden(self) -> bool:
        return self.brutto_bps >= self.m61_schwelle_bps


# ---------------------------------------------------------------------------
# Herkunft: Pruefsumme der gemessenen Reihe
# ---------------------------------------------------------------------------


def _kanonische_reihe(kerzen: list[Kerze]) -> str:
    """Textform der Reihe, ueber die gehasht wird.

    Gehasht wird nicht die Datei, sondern die Reihe: dieselben Kerzen ergeben
    dieselbe Pruefsumme, gleich wie sie abgelegt sind. Aufgenommen sind genau die
    Felder, die in die Messung eingehen — Zeitstempel, Eroeffnung, Schluss. Hoch und
    Tief stehen bewusst nicht dabei: ``Kerze`` fuehrt sie nicht, und sie zum Hashen zu
    erfinden hiesse, eine Pruefsumme ueber erfundene Werte zu bilden. Aus demselben
    Grund wird ``data/loader.py::bars_checksum`` hier nicht aufgerufen — es hasht die
    kanonische CSV eines ``BarRow`` mit OHLCV, den es hier nicht gibt.
    """
    if not kerzen:
        raise StudienError("Leere Reihe — es gibt nichts zu pruefsummen")
    zeilen = [REIHEN_FORMAT_VERSION, _REIHEN_SPALTEN]
    for k in kerzen:
        ts = verlange_echtes_utc(k.ts, "Kerze der Studienreihe")
        zeilen.append(f"{ts.isoformat()},{k.open!r},{k.close!r}")
    return "\n".join(zeilen) + "\n"


def reihen_pruefsumme(kerzen: list[Kerze]) -> str:
    """SHA-256 ueber die Reihe, auf der tatsaechlich gemessen wird.

    Was diese Zahl belegt und was nicht: sie bindet einen Befund an genau die Kerzen,
    aus denen er entstanden ist. Ob diese Kerzen richtig gedreht sind, kann sie nicht
    sagen — das sieht man einem Zeitstempel nicht an (``kalender.py``). Sie sagt genau
    dies: zwei Laeufe mit gleicher Zahl haben dieselben Kerzen gesehen. Was sie NICHT
    leistet, steht im Modulkopf unter „OFFEN" — ohne eine daneben liegende, festgelegte
    Reihe laesst sich ein alter Befund damit nicht nachrechnen, nur vergleichen.
    """
    return hashlib.sha256(_kanonische_reihe(kerzen).encode("utf-8")).hexdigest()


def kampagne() -> register.Kampagne:
    """Die vorregistrierte Reihe, gegen die deflationiert wird.

    Die Groesse ist das Feld selbst: jede Paarung aus Kandidat und Instrument in
    ``kalender.KANDIDATEN`` ist ein angemeldeter Lauf (heute sieben). Sie wird aus dem
    Code abgeleitet und nicht danebengeschrieben — eine zweite Zahl fuer dieselbe
    Groesse waere die naechste, die auseinanderlaeuft.
    """
    return register.Kampagne(
        praefix=KAMPAGNE_PRAEFIX,
        groesse=sum(len(k.instrumente) for k in KANDIDATEN),
    )


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
    """Die Messung. Brutto, Streuung, Trefferanteil, Netto — alles in einem Zug.

    Die berichtete Herkunft (``Ergebnis.reihen_pruefsumme``) wird aus den tatsaechlich
    gefahrenen Kerzen **abgeleitet**, nie vom Aufrufer geglaubt — es gibt hier gar
    keinen Weg, eine fremde Zahl hereinzureichen.
    """
    if k_bps <= 0:
        raise StudienError(f"K muss positiv sein: {k_bps}")
    if not kerzen:
        raise StudienError("Keine Kerzen")
    pruefsumme = reihen_pruefsumme(kerzen)
    stempel = _kerzen_index(kerzen)
    bs = balkenstunden(kerzen)
    werte = [
        w
        for e in ereignisse
        if (
            w := messe_ereignis(
                kerzen, stempel, e, fenster_stunden=fenster_stunden, balkenstunden=bs
            )
        )
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
            reihen_pruefsumme=pruefsumme,
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
    register_pfad: Path | str | None = None,
) -> Bestaetigung:
    """M6.2 — die drei Pruefungen. Keine davon ist ein Versuch (M7).

    Die Versuchszahl der Deflation kommt aus dem Register (``register_pfad``, ohne
    Angabe das Register des Repos) und nicht aus einer Konstante. Gezaehlt wird die
    ganze vorregistrierte Reihe (:func:`kampagne`), nicht der Registerstand zur
    Aufrufzeit: sonst haenge ``dsr_oos`` daran, als wievielte eine Studie gefahren
    wurde, und liesse sich nicht nachrechnen. Fehlt das Register, wirft
    ``TrialsLedgerError`` und die Bestaetigung faellt aus — das ist Absicht: eine
    Deflation gegen eine unbekannte Versuchszahl ist keine.
    """
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
    versuche = register.deflation_trials(kampagne(), register_pfad)
    # Keine Einheitensperre an dieser Stelle, und der Grund gehoert hierher:
    # ``sharpe`` entsteht zwei Zeilen darueber als Mittel/Streuung der Fensterrenditen.
    # Er ist damit per Konstruktion je Beobachtung -- eine falsche Einheit ist hier
    # nicht moeglich, anders als in ``engine.py``, wo drei verschieden skalierte
    # Sharpe-Felder nebeneinander liegen und eines gewaehlt werden muss.
    #
    # Ein anderer Fehler ist hier moeglich und NICHT behoben: bei verschwindender
    # Streuung wird ``sharpe`` beliebig gross (gemessen an den synthetischen Reihen
    # des Pruefstands: 3,06e13), und die Deflation saettigt auf 1,0 -- maximale
    # Bestaetigung aus einer entarteten Reihe. Das ist ein Streuungs- und kein
    # Einheitenproblem; siehe archiv/SPAETER.md, S9.
    dsr = deflated_sharpe_ratio(
        observed_sharpe=sharpe,
        observations=len(oos),
        trials=versuche,
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
            if (
                w := messe_ereignis(
                    kerzen,
                    stempel,
                    e,
                    fenster_stunden=fenster_stunden,
                    balkenstunden=bs,
                )
            )
            is not None
        ]
        if len(proben) >= 30 and statistics.median(proben) >= gemessener_median:
            treffer += 1
    anteil = treffer / M62_ZIEHUNGEN

    return Bestaetigung(
        dsr_oos=dsr,
        dsr_n=len(oos),
        dsr_versuche=versuche,
        dsr_bestanden=dsr >= M62_DSR_SCHWELLE,
        haelfte_frueh_bps=frueh,
        haelfte_spaet_bps=spaet,
        stabil_bestanden=frueh >= schwelle and spaet >= schwelle,
        zufall_anteil=anteil,
        zufall_bestanden=anteil <= M62_ZUFALL_ANTEIL,
    )

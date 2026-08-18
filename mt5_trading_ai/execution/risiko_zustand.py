"""Der Risikozustand, der einen Neustart ueberdauert -- und wie er fail-closed liest.

WARUM DIESES MODUL
------------------
``risk/limits.py`` sagt es selbst: *„Ein System, das sich nach einem Drawdown-Halt
selbst wieder freischaltet, hat keinen Halt."* Genau das tat dieses Haus bei **jedem
Prozessstart**. Der gesamte Risikozustand lag im Prozessgedaechtnis von
``execution/risk_manager.py``: die Equity-Beobachtungen, die Tagesstart-Equity, die
Tageszaehler je Instrument und Konto, der Halt. ``_window_peak`` begann mit der
*aktuellen* Equity, der Drawdown war nach jedem Start also null -- das beworbene
``drawdown_window`` von 30 Tagen war in Wahrheit „seit Prozessstart", und der laengste
Lauf dieses Repos war ein Tag.

Gemessen an den Betriebsjournalen: **22 Eroeffnungen an einem Konto-Tag gegen eine
Kappe von 10**, weil jeder Neustart bei null anfing. Die Kappe war kein Melder, sie war
eine Zierde.

WO DIE DATEI LIEGT -- UND WARUM NICHT WOANDERS
----------------------------------------------
Der Zustand liegt **ausserhalb des Arbeitsbaums**, unter dem Zustandsverzeichnis des
Benutzers (Windows: ``%LOCALAPPDATA%\\mt5_trading_ai\\risiko``; sonst
``$XDG_STATE_HOME`` bzw. ``~/.local/state/mt5_trading_ai/risiko``). Die drei
naheliegenden Alternativen sind alle falsch, und zwar aus jeweils eigenem Grund:

* **Im Paketbaum** (``mt5_trading_ai/...``) landete er in git. Dann waere der Halt
  *einer* Maschine der Halt *jedes* Klons, ein ``git checkout`` einer aelteren Fassung
  waere eine stille Freigabe -- und der Kontoabdruck stuende oeffentlich im Verlauf.
* **Unter ``betrieb/`` im Wurzelverzeichnis** ist er per ``.gitignore``
  Laufzeitdatenhalde. ``git clean -xdf`` -- ein Alltagsbefehl -- loescht dort alles.
  Ein Halt, den ein Aufraeumbefehl aufhebt, ist kein Halt.
* **Irgendwo im Arbeitsbaum** ueberlebt er keinen frischen Klon und keinen
  Verzeichniswechsel. Der Halt gehoert aber zur *Maschine und dem Konto*, nicht zur
  Arbeitskopie.

Erst diese Wahl macht den wichtigsten Fall unten („Datei fehlt" = neu) vertretbar:
ausserhalb des Repos kann die Datei nicht durch einen Routinebefehl verschwinden. Sie
verschwindet nur, wenn ein Mensch sie loescht -- und das ist derselbe Rang von
Entscheidung wie ``RiskManager.release_drawdown``.

Die Ortswahl ist darum **erzwungen, nicht empfohlen** (``standard_zustandsordner``,
``_absolut_oder_wurf``): ``%LOCALAPPDATA%`` wird nur unter Windows ueberhaupt gefragt,
jeder Pfad aus der Umgebung muss absolut sein, und keiner darf in den Paketbaum zeigen.
Das erste ist keine Formsache: ein Windows-Pfad ist unter POSIX ein einziges
**relatives** Namensstueck. ``Path("C:\\\\Users\\\\...").resolve()`` haengt dort das
Arbeitsverzeichnis davor, die Zustandsdatei landet mitten IM Repo -- und damit gilt
genau der Absatz oben, den die Ortswahl vermeiden sollte. Gemessen mit POSIX-Regeln:
``PurePosixPath("C:\\\\Users\\\\Test\\\\AppData\\\\Local").is_absolute()`` ist
``False``, die Datei laege unter ``<repo>/C:\\Users\\...``. Die CI dieses Repos faehrt
ubuntu-latest. Ein relativer Pfad aus ``MT5_RISIKO_ZUSTAND`` hat dieselbe Wirkung; er
wird nicht stillschweigend zurechtgebogen, sondern mit ``ZustandsortFehler``
abgewiesen -- beim Bau des ``RiskManager``, also vor der ersten Order und nicht mitten
im Takt.

DIE WICHTIGSTE ENTSCHEIDUNG: FEHLT / LEER / BESCHAEDIGT
-------------------------------------------------------
Nicht ein Urteil, sondern **fuenf**, je Abschnitt eigen -- weil die billigere
Irrtumsrichtung je Abschnitt eine andere ist:

======================  ==========================  ==============================
Befund                  Halt-Latch                  Tageszaehler
======================  ==========================  ==============================
Datei fehlt             frei (``neu``)              null
Datei leer/kaputt       **HALT**                    **ausgeschoepft**
Fremdes Konto/Waehrung  **HALT**                    **ausgeschoepft**
Abschnitt ``halt`` hin  **HALT**                    gelesen
Abschnitt Zaehler hin   gelesen                     **ausgeschoepft**
======================  ==========================  ==============================

**Halt-Latch: unlesbar heisst angehalten.** Die Richtung ist eindeutig. Eine Datei, die
*existiert*, aber nicht zu lesen ist, heisst: hier wurde Zustand geschrieben und ist
verloren. Ob er „angehalten" sagte, wissen wir nicht -- und „ich weiss nicht" darf bei
einem Halt nie „frei" bedeuten. Sonst waere das Beschaedigen der Datei der bequemste
Weg an der Freigabe vorbei.

**Fehlende Datei ist kein Halt.** Der erste Start einer Maschine hat nichts verloren:
es gibt keinen Zustand, der uebergangen wuerde. Wuerde die Abwesenheit halten, brauchte
jede Neuinstallation zuerst eine Freigabe -- und ein Werkzeug, das den Halt
wegschreibt. Dieses Werkzeug wuerde zur Standardgeste und damit zur eigentlichen
Sperre. Die Unterscheidung „fehlt" gegen „da, aber kaputt" traegt genau deshalb, weil
die Datei nach der Ortswahl oben nicht versehentlich verschwinden kann.

**Tageszaehler: unlesbar heisst ausgeschoepft.** Hier ist die Richtung nicht offensicht-
lich, also die Rechnung. Zu **hoch** irren (Kappe fuer heute als erreicht behandeln,
obwohl sie es nicht ist) kostet entgangene Eroeffnungen fuer den Rest des Tages: ein
Opportunitaetsverlust, begrenzt, und um Mitternacht von selbst vorbei. Zu **niedrig**
irren (null annehmen, obwohl 22 Trades gelaufen sind) kostet echtes Geld an echten
Positionen, unbegrenzt gegenueber der gewollten Kappe, und ist nicht ruecknehmbar --
das ist der gemessene Schaden dieses Repos. Der Irrtum nach oben ist also der billige,
und er hat zusaetzlich eine natuerliche Verfallszeit, die dem Halt gerade fehlt. Genau
diese Asymmetrie ist der Grund, dass der Halt eine **menschliche** Freigabe braucht und
die Zaehlersperre nur den **Tageswechsel**.

**Equity-Fenster: unlesbar heisst nicht bewertbar heisst Halt.** Ein kaputtes
Equity-Fenster kann nicht „leer" gelesen werden, denn leer bedeutet
``_window_peak == aktuelle Equity`` und damit Drawdown null -- der Fehler, der hier
reparieren wird. Es gilt darum als nicht bewertbar, und das Haus hat dafuer schon eine
Regel: ``risk/limits.py::_fraction`` behandelt einen nicht bewertbaren Nenner „als voll
ausgeschoepft, nicht als null". Dieselbe Richtung, hier als Halt.

**Eine Freigabe ueberdauert den Neustart NICHT.** Der Halt schon. Die Asymmetrie ist
Absicht: eine Freigabe ist die Aussage eines Menschen ueber eine Lage, die er *gerade
gesehen* hat. Nach einem Neustart -- zumal nach einem, der aus einem Absturz kam --
hat er sie nicht mehr gesehen. Nebenbei haelt das freien Text (eine Ticketnummer, die
ein Mensch tippt) aus der Datei heraus; siehe „Kein Geheimnis".

WAS OHNE GEPRUEFTES KONTO GESCHRIEBEN WIRD -- UND WARUM GENAU DAS
------------------------------------------------------------------
Der ``RiskManager`` kennt sein Konto erst mit der ersten ``AccountState``, also mit der
ersten Autorisierung. Der Scheduler beobachtet die Equity aber **je Takt**, lange
davor. Wuerde ohne Bindung gar nichts geschrieben, ginge genau der Fenster-Hoechststand
verloren, der zwischen Start und erster Order entsteht -- und der naechste Start faende
einen niedrigeren Peak, einen kleineren Drawdown und keinen Halt. Das ist der Fehler,
den dieses Modul repariert, nur eine Ebene tiefer.

Also wird auch ohne Bindung geschrieben, aber **ausschliesslich das Equity-Fenster**:

* Es ist der einzige Abschnitt, dessen Uebernahme durch einen fremden Leser nicht
  schmeicheln kann. Der Peak ist ein Maximum ueber Fenster und aktuelle Equity; ein
  fremder Korb kann ihn nur **heben**, also den Drawdown nur vergroessern, also nur
  eher halten. Die Fehlrichtung ist damit „grundlos streng", nicht „still frei".
* Alles andere wartet auf den Kontobeweis. Der **Tagesstart** waere die Ausnahme, die
  die Regel bricht: ein fremder, niedrigerer Tagesstart liesse den Tagesverlust
  kleiner aussehen. Er wird darum ohne Bindung nicht geschrieben -- der erste Takt
  eines Tages setzt ihn ohnehin neu.
* Halt, Tageszaehler und offene Positionen koennen ohne Bindung gar nicht entstehen:
  sie aendern sich erst in ``authorize_opening`` bzw. ``record_open_fill``, und
  ``authorize_opening`` bindet als Allererstes. Sie stehen darum nie unversorgt im
  Speicher.

Liegt schon eine **gebundene** Datei da, wird sie nicht ersetzt, sondern nur ihr
Fensterabschnitt fortgeschrieben; Bindung, Halt, Zaehler und Positionen bleiben Wert
fuer Wert stehen (die Datei wird dafuer gelesen, nicht neu gebaut -- nur der eine
Abschnitt wird ersetzt). Und ist die vorhandene Datei unlesbar, wird ohne Bindung
**nichts** geschrieben -- dort steht ein Halt, und der Beweis (``_beweis_sichern``)
gehoert vor die Ersetzung.

WENN DIE PLATTE NICHT MITSPIELT
-------------------------------
``sichern`` **wirft nicht**. Es meldet. Die Begruendung -- ein Absturz nach dem Fill
ist teurer als ein nicht gesicherter Zustand, und man muss zwischen beidem nicht
waehlen -- steht bei ``DateiZustand.sichern`` und ``RiskManager._sichern``.

KEIN GEHEIMNIS IN DER DATEI
---------------------------
Weder Kontonummer noch Server noch Token. Die Kontobindung steht als **Ableitung**:
``pbkdf2_hmac("sha256", konto_id, salz, KDF_RUNDEN)`` mit einem je Datei zufaelligen
Salz. Ein blanker SHA-256 waere hier *keine* Verschleierung -- MT5-Logins sind 6 bis 12
Ziffern, also hoechstens 10**12 Kandidaten, in Minuten durchprobiert. Mit
``KDF_RUNDEN`` Runden kostet ein Kandidat rund 2*10**5 SHA-256-Schritte; die volle
Menge damit ~2*10**17 Schritte, was auf einer schnellen Karte in Monaten statt Minuten
liegt. Das ist ausdruecklich **keine** Behauptung von Unmoeglichkeit -- die Zahl steht
hier, damit sie nachgerechnet werden kann. Die Aufgabe des Abdrucks ist auch nicht
Geheimhaltung, sondern **Unterscheidung**: er soll ein fremdes Konto erkennen, ohne
selbst zur Nachschlagetabelle fuer den Login zu werden. Die Kontowaehrung steht im
Klartext (``EUR`` identifiziert niemanden) -- damit eine Abweichung sagen kann, *was*
abweicht, statt nur „passt nicht". Festgenagelt von
``tests/test_risiko_zustand_geheimnis.py`` gegen die Muster aus
``tools/geheimnis_scan.py``, das in der CI laeuft.

WARUM ``execution/`` UND NICHT ``betrieb/``
-------------------------------------------
``mt5_trading_ai/betrieb/`` ist die **Lese**seite der Betriebsjournale: Auswertung im
Nachhinein, ohne Rolle im Order-Pfad. Dieses Modul steht **im** Order-Pfad -- es wird
bei jeder Autorisierung gelesen und geschrieben, und seine Fehlerfaelle sind
Order-Ablehnungen. Es unter ``betrieb/`` zu legen hiesse, den Order-Pfad von der
Auswertungsschicht abhaengig zu machen und die Schichtung umzudrehen. Es liegt darum
neben seinem einzigen Aufrufer, ``execution/risk_manager.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Final

#: Schemamarke. Eine unbekannte Marke ist ein **unlesbarer** Zustand, kein leerer:
#: eine aeltere/neuere Fassung koennte einen Halt anders benannt haben, und ein Halt,
#: den wir nicht verstehen, gilt als Halt.
RISIKO_ZUSTAND_SCHEMA: Final = "risiko-zustand-v1"

#: Schemamarke der **ungebundenen** Datei: nur das Equity-Fenster, kein Konto, kein
#: Halt, keine Zaehler (Begruendung im Modul-Docstring). Sie braucht eine eigene Marke
#: und nicht bloss ein leeres Feld: eine Datei mit ``"bindung": null`` waere nach der
#: Leiter oben unlesbar und damit ein Halt -- jeder Neustart nach einem Lauf ohne Order
#: haette dann angehalten. Eine eigene Marke sagt „unvollstaendig **und zwar
#: absichtlich**"; ein Defekt IN dieser Datei bleibt ein Halt wie ueberall sonst.
RISIKO_ZUSTAND_SCHEMA_FENSTER: Final = "risiko-zustand-fenster-v1"

#: Umgebungsvariable mit dem vollen Pfad der Zustandsdatei. Sie ist der Schalter, mit
#: dem der Betrieb die Dauerhaftigkeit einschaltet, ohne dass eine Aufrufstelle
#: geaendert werden muss -- und sie ist zugleich der Weg, wie ein Betreiber mit ZWEI
#: Konten arbeitet: eine Datei je Konto.
UMGEBUNG_ZUSTANDSDATEI: Final = "MT5_RISIKO_ZUSTAND"

#: Umgebungsvariable nur fuer das Verzeichnis (Dateiname bleibt der Standard).
UMGEBUNG_ZUSTANDSORDNER: Final = "MT5_RISIKO_ZUSTAND_ORDNER"

#: Rundenzahl der Schluesselableitung fuer den Kontoabdruck. Begruendung samt
#: Rechnung im Modul-Docstring unter „Kein Geheimnis in der Datei".
KDF_RUNDEN: Final = 200_000

#: Kornung des Equity-Fensters: ein Korb je Stunde, gefuehrt mit dem **Hoechststand**
#: der Stunde. Ohne Kornung waechst die Reihe bei Sekundentakt auf Hunderttausende
#: Eintraege in 30 Tagen -- eine Datei, die je Takt geschrieben wird, und ein
#: Speicherleck in genau dem Lauf, den dieses Haus noch nie gefahren hat. Der
#: Hoechststand je Korb ist die sichere Richtung: er kann den Fenster-Peak nur
#: **halten oder heben**, nie senken, und ein hoeherer Peak heisst ein groesserer
#: Drawdown heisst eher Halt.
FENSTER_KORB: Final = timedelta(hours=1)


class ZustandsortFehler(ValueError):
    """Der vorgegebene Ort der Zustandsdatei kann die Ortsgarantie nicht tragen.

    Wird beim **Bau** des ``RiskManager`` geworfen, nicht im Order-Pfad: eine
    Fehlkonfiguration soll den Prozess dort anhalten, wo noch nichts offen ist. Der
    Fall ist genau einer -- ein relativer Pfad aus der Umgebung. Er wuerde gegen das
    Arbeitsverzeichnis aufgeloest, und damit laege der Halt im Repo (Begruendung im
    Modul-Docstring, „Wo die Datei liegt").
    """


class _Unlesbar(Exception):
    """Intern: dieser Abschnitt ist nicht zu lesen.

    Der Fangende entscheidet die Richtung -- Halt oder ausgeschoepfter Zaehler. Die
    Ausnahme selbst urteilt nicht; sie nennt nur das Feld, damit die Ablehnung im
    Protokoll sagen kann, *woran* es lag.
    """


def _absolut_oder_wurf(roh: str, quelle: str) -> Path:
    """Ein Pfad aus der Umgebung -- absolut und ausserhalb des Pakets, oder gar nicht.

    Zwei Wege in denselben Fehler, und beide sind nachpruefbar:

    * **Relativ.** Er wird gegen das Arbeitsverzeichnis aufgeloest. Das ist bei einer
      Zustandsdatei kein Schoenheitsfehler, sondern der Verlust der ganzen Begruendung:
      „Datei fehlt = frei" traegt nur, weil die Datei ausserhalb des Arbeitsbaums liegt
      und nur ein Mensch sie loeschen kann. Im Baum loescht sie ``git clean -xdf``.
    * **Im Paketbaum.** Dort landet sie in git: der Halt *einer* Maschine waere der
      Halt *jedes* Klons, ein ``git checkout`` einer aelteren Fassung eine stille
      Freigabe, und der Kontoabdruck stuende im Verlauf. Diese Grenze ist als einzige
      exakt bekannt (``mt5_trading_ai/``) und wird darum auch geprueft -- „irgendein
      Arbeitsbaum" liesse sich nur raten.

    Zurechtbiegen (etwa gegen ``Path.home()`` aufloesen) scheidet aus: der Betreiber
    hat einen Ort **genannt**, und ein stillschweigend anderer Ort ist schlimmer als
    eine Ablehnung -- er wuerde den Halt an einer Stelle suchen, an der keiner steht.
    """
    pfad = Path(roh)
    if not pfad.is_absolute():
        raise ZustandsortFehler(
            f"{quelle}={roh!r} ist kein absoluter Pfad. Die Zustandsdatei traegt den "
            "Drawdown-Halt ueber Neustarts; ein relativer Pfad wird gegen das "
            "Arbeitsverzeichnis aufgeloest und landet damit im Arbeitsbaum, wo ein "
            "Aufraeumbefehl ihn loescht. Bitte einen absoluten Pfad angeben."
        )
    paket = Path(__file__).resolve().parents[1]
    if pfad.resolve().is_relative_to(paket):
        raise ZustandsortFehler(
            f"{quelle}={roh!r} liegt im Paketbaum ({paket}). Der Zustand gehoert zur "
            "Maschine und zum Konto, nicht zur Arbeitskopie -- im Paketbaum landete "
            "er in git, und ein Auschecken waere eine stille Freigabe."
        )
    return pfad


def standard_zustandsordner(
    *,
    umgebung: Mapping[str, str] | None = None,
    ist_windows: bool | None = None,
) -> Path:
    """Das Zustandsverzeichnis des Benutzers -- ausserhalb des Arbeitsbaums.

    Begruendung der Ortswahl im Modul-Docstring. Die Reihenfolge ist bewusst
    plattformnah: unter Windows ist ``%LOCALAPPDATA%`` der Ort fuer maschinenlokalen
    Zustand (nicht ``%APPDATA%``, das in Roaming-Profilen mitwandert -- ein Halt, der
    auf eine andere Maschine mitwandert, halt das falsche Terminal). ``%LOCALAPPDATA%``
    wird darum **nur unter Windows** gefragt: unter POSIX ist ein Windows-Pfad ein
    relatives Namensstueck, und die Datei laege im Arbeitsbaum.

    ``umgebung``/``ist_windows`` sind ausschliesslich fuer die Tests da -- die
    Plattformregel muss auf **beiden** Plattformen pruefbar sein, und ``os.name`` laesst
    sich nicht gefahrlos umbiegen (``pathlib`` liest es beim Bau jedes ``Path``).
    """
    umg = os.environ if umgebung is None else umgebung
    windows = os.name == "nt" if ist_windows is None else ist_windows
    vorgabe = umg.get(UMGEBUNG_ZUSTANDSORDNER)
    if vorgabe:
        return _absolut_oder_wurf(vorgabe, UMGEBUNG_ZUSTANDSORDNER)
    # Kein Wurf fuer die vom System gesetzten Variablen: sie sind keine Anweisung des
    # Betreibers, sondern eine Auskunft der Plattform. Ist sie unbrauchbar (leer oder
    # relativ), gilt der naechste Kandidat -- am Ende immer ein absoluter Heimatpfad.
    plattform = "LOCALAPPDATA" if windows else "XDG_STATE_HOME"
    roh = umg.get(plattform)
    if roh and Path(roh).is_absolute():
        return Path(roh) / "mt5_trading_ai" / "risiko"
    return Path.home() / ".local" / "state" / "mt5_trading_ai" / "risiko"


def standard_zustandsdatei(
    *,
    umgebung: Mapping[str, str] | None = None,
    ist_windows: bool | None = None,
) -> Path:
    """Der Standardpfad der Zustandsdatei (``UMGEBUNG_ZUSTANDSDATEI`` schlaegt alles).

    Ein **fester** Dateiname, kein aus dem Konto abgeleiteter. Ein abgeleiteter Name
    waere bequem (je Konto automatisch eine Datei), oeffnete aber ein Loch: das noetige
    Salz muesste neben den Dateien liegen, und ein verlorenes Salz liesse jede
    Zustandsdatei *unauffindbar* werden -- also jeden Halt lautlos verschwinden. Ein
    fester Name kennt diesen Weg nicht: ein fremdes Konto trifft auf eine Datei, die da
    ist, und wird erkannt (``DateiZustand.binde``). Wer zwei Konten faehrt, setzt
    ``UMGEBUNG_ZUSTANDSDATEI`` je Lauf.
    """
    umg = os.environ if umgebung is None else umgebung
    aus_umgebung = umg.get(UMGEBUNG_ZUSTANDSDATEI)
    if aus_umgebung:
        return _absolut_oder_wurf(aus_umgebung, UMGEBUNG_ZUSTANDSDATEI)
    ordner = standard_zustandsordner(umgebung=umg, ist_windows=ist_windows)
    return ordner / "risikozustand.json"


def korb_start(ts: datetime) -> datetime:
    """Der Stundenkorb einer Beobachtung (Begruendung: ``FENSTER_KORB``)."""
    return ts.replace(minute=0, second=0, microsecond=0)


def fenster_fortschreiben(
    fenster: list[tuple[datetime, Decimal]],
    ts: datetime,
    equity: Decimal,
    dauer: timedelta,
) -> list[tuple[datetime, Decimal]]:
    """Schreibe das Equity-Fenster fort: Korb-Hoechststaende, auf ``dauer`` beschnitten.

    Beschnitten wird nach dem **Ende** des Korbes (``start + FENSTER_KORB``), nicht nach
    seinem Anfang. Das ist kein Detail: der Anfang liegt bis zu eine Stunde vor der
    Beobachtung, ein Schnitt am Anfang wuerfe einen Korb also bis zu eine Stunde **zu
    frueh** hinaus. Zu frueh hinauswerfen senkt den Peak, senkt den Drawdown und macht
    den Halt milder -- die falsche Richtung. Am Ende zu schneiden haelt notfalls eine
    Stunde zu lange und irrt damit nach „eher Halt".
    """
    schluessel = korb_start(ts)
    grenze = ts - dauer - FENSTER_KORB
    neu: list[tuple[datetime, Decimal]] = []
    gesehen = False
    for korb, eq in fenster:
        if korb < grenze:
            continue
        if korb == schluessel:
            gesehen = True
            neu.append((korb, eq if eq > equity else equity))
        else:
            neu.append((korb, eq))
    if not gesehen:
        neu.append((schluessel, equity))
    neu.sort(key=lambda paar: paar[0])
    return neu


@dataclass
class RisikoLage:
    """Genau das, was einen Neustart ueberdauern soll -- und nichts darueber hinaus.

    Bewusst **nicht** dabei: die manuelle Freigabe (``manual_release_id``) und ihr
    Niveau. Begruendung im Modul-Docstring: ein Halt ueberdauert, eine Freigabe nicht.
    Ebenfalls nicht dabei: irgendetwas, was das Konto identifiziert -- die Bindung
    schreibt ``DateiZustand`` selbst, als Ableitung.
    """

    halt: bool = False
    halt_grund: str = ""
    halt_seit: datetime | None = None
    handelstag: date | None = None
    #: Die Tageszaehler dieses Tages sind nicht vertrauenswuerdig -> als ausgeschoepft
    #: behandeln. Wird **mitgeschrieben**, und das ist keine Formsache: ohne sie
    #: uebersteht die Sperre den naechsten Neustart nicht. Der erste Lauf nach dem
    #: Defekt sichert einen sauberen Stand mit Zaehlern auf null -- der zweite Lauf
    #: laese daraus „heute noch kein Trade" und haette die Sperre in dem Moment
    #: verloren, in dem sie noch gebraucht wird.
    zaehler_gesperrt: bool = False
    trades_je_instrument: dict[str, int] = field(default_factory=dict)
    trades_konto: int = 0
    letzter_trade_at: dict[str, datetime] = field(default_factory=dict)
    equity_tag: date | None = None
    tagesstart_equity: Decimal | None = None
    equity_fenster: list[tuple[datetime, Decimal]] = field(default_factory=list)
    offene_positionen: list[tuple[str, datetime]] = field(default_factory=list)


@dataclass(frozen=True)
class Zustandsbefund:
    """Was von der Platte kam -- und ob man ihm trauen darf.

    ``sperrgrund`` ist der **Halt-Befehl an den Aufrufer**: nicht ``None`` heisst, dass
    dieser Zustand nicht als „frei" gelesen werden darf (unlesbar, fremdes Konto,
    kaputtes Equity-Fenster). Der schwaechere Bruder fuer die Tageszaehler steht in
    ``lage.zaehler_gesperrt``: er sperrt nur den laufenden Tag, ohne menschliche
    Freigabe, weil der Irrtum dort um Mitternacht von selbst verfaellt.

    ``herkunft`` ist fuer das Protokoll: ``neu`` (keine Datei), ``gelesen``,
    ``unlesbar``.
    """

    lage: RisikoLage
    herkunft: str
    sperrgrund: str | None = None


@dataclass(frozen=True)
class _Bindung:
    """Die gelesene Kontobindung: Salz, Rundenzahl, Abdruck. Kein Login, kein Server."""

    salz: bytes
    runden: int
    abdruck: str


def _abdruck(konto_id: str, salz: bytes, runden: int) -> str:
    """Der Kontoabdruck. Absichtlich teuer -- Begruendung im Modul-Docstring."""
    return hashlib.pbkdf2_hmac(
        "sha256", konto_id.encode("utf-8"), salz, runden
    ).hex()


# --- Leser fuer die einzelnen Feldarten ----------------------------------------
# Jeder wirft ``_Unlesbar``, statt einen Ersatzwert zu erfinden. Ein Ersatzwert waere
# hier immer die milde Richtung (null Trades, kein Halt, leeres Fenster) -- genau die
# Richtung, die dieses Modul abschaffen soll.


def _text(wert: object, feld: str) -> str:
    if not isinstance(wert, str) or not wert:
        raise _Unlesbar(feld)
    return wert


def _ganzzahl(wert: object, feld: str) -> int:
    # ``bool`` ist in Python ein ``int``; ein ``true`` im Zaehlerfeld ist aber ein
    # Defekt und keine Eins.
    if isinstance(wert, bool) or not isinstance(wert, int) or wert < 0:
        raise _Unlesbar(feld)
    return wert


def _wahrheit(wert: object, feld: str) -> bool:
    if not isinstance(wert, bool):
        raise _Unlesbar(feld)
    return wert


def _zeitpunkt(wert: object, feld: str) -> datetime:
    """Ein Zeitpunkt MIT Zone. Ohne Zone ist er unlesbar, nicht „vermutlich UTC".

    Ein naiver Zeitstempel wuerde beim Vergleich mit dem zonenbehafteten ``now`` des
    Order-Pfads einen ``TypeError`` mitten im Live-Takt werfen. Ihn hier auf UTC zu
    raten waere schlimmer: raet man falsch, wandert der Korb aus dem Fenster, der Peak
    sinkt und der Halt wird milder. Also unlesbar -- fail-closed.
    """
    roh = _text(wert, feld)
    try:
        ts = datetime.fromisoformat(roh)
    except ValueError as fehler:
        raise _Unlesbar(feld) from fehler
    if ts.tzinfo is None:
        raise _Unlesbar(feld)
    return ts


def _tag(wert: object, feld: str) -> date:
    roh = _text(wert, feld)
    try:
        return date.fromisoformat(roh)
    except ValueError as fehler:
        raise _Unlesbar(feld) from fehler


def _betrag(wert: object, feld: str) -> Decimal:
    roh = _text(wert, feld)
    try:
        zahl = Decimal(roh)
    except InvalidOperation as fehler:
        raise _Unlesbar(feld) from fehler
    if not zahl.is_finite():
        # ``NaN`` verglichen mit einem Peak wirft ``InvalidOperation`` -- ein Absturz
        # im Order-Pfad statt einer Ablehnung.
        raise _Unlesbar(feld)
    return zahl


def _abbildung(wert: object, feld: str) -> dict[str, Any]:
    if not isinstance(wert, dict):
        raise _Unlesbar(feld)
    schluessel_geprueft: dict[str, Any] = {}
    for schluessel, inhalt in wert.items():
        if not isinstance(schluessel, str):
            raise _Unlesbar(feld)
        schluessel_geprueft[schluessel] = inhalt
    return schluessel_geprueft


class DateiZustand:
    """Der Risikozustand in einer JSON-Datei ausserhalb des Arbeitsbaums.

    Drei Schritte, in dieser Reihenfolge:

    1. ``laden()`` -- liest die Datei, **ohne** das Konto zu pruefen. Der
       ``RiskManager`` kennt das Konto beim Bau noch nicht; es kommt erst mit der ersten
       ``AccountState`` herein. Was hier schon entschieden wird, ist die
       fail-closed-Richtung je Abschnitt.
    2. ``binde(konto_id, waehrung)`` -- haelt die gelesene Bindung gegen das Konto, das
       gerade handeln will. Erst danach darf der **volle** Zustand geschrieben werden:
       eine Zustandsdatei mit fremden Zaehlern und fremdem Halt ist eine Vermischung
       zweier Konten.
    3. ``sichern(lage)`` -- atomar (Nebendatei + ``os.replace``), damit ein Abbruch
       mitten im Schreiben keine halbe Datei hinterlaesst. Eine halbe Datei waere nach
       den Regeln oben ein Halt -- korrekt, aber unnoetig. Ohne Bindung schreibt es
       ausschliesslich das Equity-Fenster (Begruendung im Modul-Docstring). Es wirft
       nie; ein Schreibfehler kommt als Grund zurueck.
    """

    def __init__(self, pfad: Path) -> None:
        self._pfad = pfad
        self._gelesene_bindung: _Bindung | None = None
        self._gelesene_waehrung: str | None = None
        self._bindung: _Bindung | None = None
        self._waehrung: str | None = None
        self._konto_id: str | None = None
        self._geladen = False
        #: Eine kaputte Datei wartet auf ihre Kopie zur Seite (siehe ``_unlesbar``).
        self._beweis_ausstehend = False
        #: Herkunft des letzten ``laden`` -- entscheidet, was ohne Bindung geschrieben
        #: werden darf: ``neu``/``fenster`` -> eigene Fensterdatei, ``gelesen`` ->
        #: nur den Fensterabschnitt der vorhandenen Datei, ``unlesbar`` -> nichts.
        self._herkunft = ""
        #: Das Fenster, wie es auf der Platte steht. Ist es unveraendert, entfaellt der
        #: ungebundene Schreibvorgang -- sonst schriebe jeder Takt eine Datei neu, die
        #: sich nicht geaendert hat.
        self._fenster_auf_platte: list[tuple[datetime, Decimal]] = []
        #: Klartext des letzten Schreibfehlers (fuer das Protokoll des Aufrufers).
        self._schreibfehler_text = ""

    @property
    def pfad(self) -> Path:
        return self._pfad

    @property
    def gebunden(self) -> bool:
        """Ob ein Konto geprueft ist. Ohne Bindung schreibt ``sichern`` nur das
        Equity-Fenster (Begruendung im Modul-Docstring)."""
        return self._bindung is not None

    @property
    def schreibfehler_text(self) -> str:
        """Klartext des letzten Schreibfehlers -- leer, wenn zuletzt geschrieben wurde.

        Der Grund als kurze Marke steht im Rueckgabewert von ``sichern`` und landet in
        der Ablehnung; der Klartext gehoert daneben ins Protokoll. Ohne ihn stuende im
        Journal „nicht gesichert" und niemand wuesste, ob die Platte voll ist, das
        Verzeichnis fehlt oder ein zweiter Prozess die Datei haelt.
        """
        return self._schreibfehler_text

    # --- Lesen ------------------------------------------------------------
    def laden(self) -> Zustandsbefund:
        """Lies die Datei und loese jeden kaputten Abschnitt fail-closed auf."""
        self._geladen = True
        self._fenster_auf_platte = []
        if not self._pfad.exists():
            # Kein Zustand ist etwas anderes als verlorener Zustand. Begruendung im
            # Modul-Docstring; sie traegt nur wegen der Ortswahl (kein ``git clean``).
            self._herkunft = "neu"
            return Zustandsbefund(lage=RisikoLage(), herkunft="neu")
        try:
            roh = self._pfad.read_bytes()
        except OSError:
            return self._unlesbar("zustand_datei_unlesbar")
        if not roh.strip():
            return self._unlesbar("zustand_datei_leer")
        try:
            daten_roh = json.loads(roh.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._unlesbar("zustand_kein_json")
        if not isinstance(daten_roh, dict):
            return self._unlesbar("zustand_kein_objekt")
        daten: dict[str, Any] = {}
        for schluessel, inhalt in daten_roh.items():
            if not isinstance(schluessel, str):
                return self._unlesbar("zustand_kein_objekt")
            daten[schluessel] = inhalt
        if daten.get("schema") == RISIKO_ZUSTAND_SCHEMA_FENSTER:
            return self._fensterdatei_lesen(daten)
        if daten.get("schema") != RISIKO_ZUSTAND_SCHEMA:
            return self._unlesbar("zustand_fremdes_schema")

        try:
            self._gelesene_waehrung = _text(daten.get("waehrung"), "waehrung")
            bindung_roh = _abbildung(daten.get("bindung"), "bindung")
            self._gelesene_bindung = _Bindung(
                salz=bytes.fromhex(_text(bindung_roh.get("salz"), "bindung.salz")),
                runden=_ganzzahl(bindung_roh.get("runden"), "bindung.runden"),
                abdruck=_text(bindung_roh.get("abdruck"), "bindung.abdruck"),
            )
        except (_Unlesbar, ValueError):
            # Ohne lesbare Bindung ist nicht feststellbar, ZU WEM dieser Zustand
            # gehoert. Ihn zu uebernehmen hiesse, den Halt eines fremden Kontos zu
            # ignorieren oder den eigenen zu verlieren.
            return self._unlesbar("zustand_bindung_unlesbar")
        if self._gelesene_bindung.runden <= 0:
            return self._unlesbar("zustand_bindung_unlesbar")

        lage = RisikoLage()

        # --- Halt: jeder Defekt hier ist ein Halt ---------------------------
        try:
            halt_roh = _abbildung(daten.get("halt"), "halt")
            lage.halt = _wahrheit(halt_roh.get("aktiv"), "halt.aktiv")
            lage.halt_grund = str(halt_roh.get("grund") or "")
            seit = halt_roh.get("seit")
            lage.halt_seit = None if seit is None else _zeitpunkt(seit, "halt.seit")
        except _Unlesbar as fehler:
            lage.halt = True
            lage.halt_grund = f"zustand_halt_unlesbar[{fehler}]"
            lage.zaehler_gesperrt = True
            return Zustandsbefund(
                lage=lage, herkunft="unlesbar", sperrgrund=lage.halt_grund
            )

        # --- Equity-Fenster: unlesbar = nicht bewertbar = Halt ---------------
        try:
            equity_roh = _abbildung(daten.get("equity"), "equity")
            tag = equity_roh.get("tag")
            lage.equity_tag = None if tag is None else _tag(tag, "equity.tag")
            start = equity_roh.get("tagesstart")
            lage.tagesstart_equity = (
                None if start is None else _betrag(start, "equity.tagesstart")
            )
            lage.equity_fenster = self._fenster_lesen(equity_roh.get("fenster"))
        except _Unlesbar as fehler:
            lage.halt = True
            lage.halt_grund = f"zustand_equity_unlesbar[{fehler}]"
            lage.zaehler_gesperrt = True
            return Zustandsbefund(
                lage=lage, herkunft="unlesbar", sperrgrund=lage.halt_grund
            )

        # --- Tageszaehler: unlesbar = ausgeschoepft, aber KEIN Halt ----------
        try:
            zaehler_roh = _abbildung(daten.get("tageszaehler"), "tageszaehler")
            tag_roh = zaehler_roh.get("tag")
            lage.handelstag = None if tag_roh is None else _tag(tag_roh, "zaehler.tag")
            je_instrument = _abbildung(
                zaehler_roh.get("je_instrument"), "zaehler.je_instrument"
            )
            lage.trades_je_instrument = {
                symbol: _ganzzahl(anzahl, f"zaehler.je_instrument.{symbol}")
                for symbol, anzahl in je_instrument.items()
            }
            lage.trades_konto = _ganzzahl(
                zaehler_roh.get("je_konto"), "zaehler.je_konto"
            )
            lage.zaehler_gesperrt = _wahrheit(
                zaehler_roh.get("gesperrt"), "zaehler.gesperrt"
            )
            letzte = _abbildung(daten.get("letzter_trade_at"), "letzter_trade_at")
            lage.letzter_trade_at = {
                symbol: _zeitpunkt(ts, f"letzter_trade_at.{symbol}")
                for symbol, ts in letzte.items()
            }
        except _Unlesbar:
            # Kein Halt: die Sperre gilt nur fuer den laufenden Tag. Der Tag selbst
            # ist hier moeglicherweise unbekannt -- ``None`` heisst fuer den
            # ``RiskManager`` „der erste Tag, den ich sehe".
            lage.handelstag = None
            lage.trades_je_instrument = {}
            lage.trades_konto = 0
            lage.letzter_trade_at = {}
            lage.zaehler_gesperrt = True

        # --- Offene Positionen: unlesbar = Halt -----------------------------
        # Sie zaehlen gegen den Positionsdeckel; „leer" waere die milde Richtung.
        try:
            lage.offene_positionen = self._positionen_lesen(
                daten.get("offene_positionen")
            )
        except _Unlesbar as fehler:
            lage.halt = True
            lage.halt_grund = f"zustand_positionen_unlesbar[{fehler}]"
            lage.zaehler_gesperrt = True
            return Zustandsbefund(
                lage=lage, herkunft="unlesbar", sperrgrund=lage.halt_grund
            )

        self._herkunft = "gelesen"
        self._fenster_auf_platte = list(lage.equity_fenster)
        return Zustandsbefund(lage=lage, herkunft="gelesen", sperrgrund=None)

    def _fensterdatei_lesen(self, daten: dict[str, Any]) -> Zustandsbefund:
        """Die ungebundene Datei: Equity-Fenster, sonst nichts -- und kein Halt.

        Sie entsteht nur zwischen Prozessstart und erster Autorisierung (Modul-
        Docstring). Was sie NICHT enthaelt, fehlt nicht aus Versehen, sondern weil es
        ohne Kontobeweis nicht geschrieben werden darf -- ein leerer Halt und ein
        Zaehler auf null sind hier also der richtige Stand und keine milde Auslegung.

        Ein Defekt **in** ihr bleibt dagegen ein Halt wie ueberall: dass sie
        absichtlich unvollstaendig ist, heisst nicht, dass sie beliebig sein darf.
        """
        try:
            equity_roh = _abbildung(daten.get("equity"), "equity")
            fenster = self._fenster_lesen(equity_roh.get("fenster"))
        except _Unlesbar as fehler:
            return self._unlesbar(f"zustand_fenster_unlesbar[{fehler}]")
        self._herkunft = "fenster"
        self._fenster_auf_platte = list(fenster)
        return Zustandsbefund(
            lage=RisikoLage(equity_fenster=fenster), herkunft="fenster"
        )

    @staticmethod
    def _fenster_lesen(wert: object) -> list[tuple[datetime, Decimal]]:
        if not isinstance(wert, list):
            raise _Unlesbar("equity.fenster")
        fenster: list[tuple[datetime, Decimal]] = []
        for eintrag in wert:
            if not isinstance(eintrag, list) or len(eintrag) != 2:
                raise _Unlesbar("equity.fenster")
            fenster.append(
                (
                    _zeitpunkt(eintrag[0], "equity.fenster.ts"),
                    _betrag(eintrag[1], "equity.fenster.equity"),
                )
            )
        return fenster

    @staticmethod
    def _positionen_lesen(wert: object) -> list[tuple[str, datetime]]:
        if not isinstance(wert, list):
            raise _Unlesbar("offene_positionen")
        positionen: list[tuple[str, datetime]] = []
        for eintrag in wert:
            eintrag_geprueft = _abbildung(eintrag, "offene_positionen")
            positionen.append(
                (
                    _text(eintrag_geprueft.get("instrument"), "position.instrument"),
                    _zeitpunkt(
                        eintrag_geprueft.get("eroeffnet_am"), "position.eroeffnet_am"
                    ),
                )
            )
        return positionen

    def _unlesbar(self, grund: str) -> Zustandsbefund:
        """Fail-closed-Befund; die Beweissicherung wird nur **vorgemerkt**.

        Die kaputten Bytes hier gleich beiseite zu legen waere der bequeme Weg -- und
        ein Loch: zwischen ``laden`` und dem ersten ``sichern`` liegt die Kontobindung,
        also mindestens eine Order. Stuerbe der Prozess in dieser Spanne, faende der
        naechste Start **gar keine** Datei mehr, laese das als „neu" und damit als
        „frei". Ein Halt, den ein Absturz aufhebt, ist kein Halt.

        Also bleibt die kaputte Datei liegen, bis sie durch eine ersetzt wird, die den
        Halt traegt; ``sichern`` zieht die Kopie unmittelbar davor. Die Beweissicherung
        selbst ist noetig, weil ein Halt, dessen Grund niemand mehr nachpruefen kann,
        irgendwann weggeklickt wird.
        """
        self._gelesene_bindung = None
        self._gelesene_waehrung = None
        self._beweis_ausstehend = True
        self._herkunft = "unlesbar"
        self._fenster_auf_platte = []
        return Zustandsbefund(
            lage=RisikoLage(halt=True, halt_grund=grund, zaehler_gesperrt=True),
            herkunft="unlesbar",
            sperrgrund=grund,
        )

    # --- Binden -----------------------------------------------------------
    def binde(self, konto_id: str, waehrung: str) -> str | None:
        """Halte die gelesene Bindung gegen das Konto, das handeln will.

        Rueckgabe ``None`` heisst „passt" (oder „es gab nichts zu vergleichen").
        Sonst der Grund -- ``zustand_fremde_waehrung`` oder ``zustand_fremdes_konto``.
        Die Waehrung wird **zuerst** geprueft, weil sie ohne Schluesselableitung
        auskommt und weil sie die groebere Verwechslung ist (ein Zustand in EUR sagt
        ueber ein USD-Konto nichts Brauchbares -- Tagesstart-Equity und Peak sind
        Betraege, nicht Verhaeltnisse).

        Nicht stillschweigend uebernommen und nicht stillschweigend verworfen: der
        Aufrufer bekommt einen Grund und lehnt damit ab.
        """
        if not self._geladen:
            # Ohne Lesen keine Bindung: sonst schriebe der erste ``sichern`` eine
            # frische Datei ueber einen vorhandenen Halt.
            self.laden()
        if self._bindung is not None:
            if self._konto_id != konto_id:
                return "zustand_fremdes_konto"
            if self._waehrung != waehrung:
                return "zustand_fremde_waehrung"
            return None
        gelesen = self._gelesene_bindung
        if gelesen is not None:
            if self._gelesene_waehrung != waehrung:
                return "zustand_fremde_waehrung"
            if _abdruck(konto_id, gelesen.salz, gelesen.runden) != gelesen.abdruck:
                return "zustand_fremdes_konto"
            self._bindung = gelesen
        else:
            salz = secrets.token_bytes(16)
            self._bindung = _Bindung(
                salz=salz,
                runden=KDF_RUNDEN,
                abdruck=_abdruck(konto_id, salz, KDF_RUNDEN),
            )
        self._konto_id = konto_id
        self._waehrung = waehrung
        return None

    # --- Schreiben --------------------------------------------------------
    def _beweis_sichern(self) -> None:
        """Kopiere eine kaputte Datei zur Seite, unmittelbar bevor sie ersetzt wird.

        **Kopie**, nicht Verschiebung: zwischen dem Wegnehmen und dem Ersetzen laege
        sonst ein Augenblick ohne Zustandsdatei, und der laese sich als „neu" -- also
        als „frei". Ein Halt, den ein unglueckliches Timing aufhebt, ist kein Halt.
        """
        if not self._beweis_ausstehend:
            return
        self._beweis_ausstehend = False
        try:
            if not self._pfad.exists():
                return
            stempel = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            beiseite = self._pfad.with_name(f"{self._pfad.name}.unlesbar-{stempel}")
            if not beiseite.exists():
                beiseite.write_bytes(self._pfad.read_bytes())
        except OSError:
            # Beweissicherung ist Kuer; der Halt ist Pflicht und steht schon.
            pass

    @staticmethod
    def _fenster_schreibform(
        fenster: list[tuple[datetime, Decimal]],
    ) -> list[list[str]]:
        return [[korb.isoformat(), str(eq)] for korb, eq in fenster]

    def _schreiben(self, daten: dict[str, Any], *, beweis: bool) -> str | None:
        """Der eine Schreibvorgang -- atomar, und ohne Wurf nach aussen.

        ``os.replace`` ist auf jeder Plattform atomar innerhalb desselben
        Verzeichnisses -- anders als ``unlink`` + ``rename``, das ein Fenster ohne
        Datei laesst. Ein solches Fenster hiesse nach den Regeln oben „neu" und damit
        „frei": ein Halt, den ein unglueckliches Timing aufhebt.

        Was hier **nicht** passiert, ist ebenso wichtig: der ``OSError`` fliegt nicht
        weiter. Er kommt als Grund zurueck (Begruendung bei ``sichern``). Auf Windows
        ist das kein Randfall -- ``os.replace`` scheitert regelmaessig mit
        ``PermissionError``, sobald ein anderer Prozess (Virenscanner, zweite Instanz,
        Editor) das Ziel offen haelt.
        """
        try:
            self._pfad.parent.mkdir(parents=True, exist_ok=True)
            if beweis:
                self._beweis_sichern()
            neben = self._pfad.with_name(self._pfad.name + ".neu")
            neben.write_text(
                json.dumps(daten, indent=1, sort_keys=True), encoding="utf-8"
            )
            os.replace(neben, self._pfad)
        except OSError as fehler:
            self._schreibfehler_text = f"{type(fehler).__name__}: {fehler}"
            return f"zustand_nicht_gesichert[{type(fehler).__name__}]"
        self._schreibfehler_text = ""
        return None

    @staticmethod
    def _fenster_vereinen(
        eins: list[tuple[datetime, Decimal]],
        zwei: list[tuple[datetime, Decimal]],
    ) -> list[tuple[datetime, Decimal]]:
        """Zwei Fenster zu einem: je Korb der Hoechststand. Nie der niedrigere.

        Dieselbe Richtung wie ``FENSTER_KORB``: der Peak darf nur steigen, damit der
        Drawdown nur groesser und der Halt nur wahrscheinlicher wird.
        """
        zusammen: dict[datetime, Decimal] = {}
        for korb, eq in [*eins, *zwei]:
            vorhanden = zusammen.get(korb)
            if vorhanden is None or eq > vorhanden:
                zusammen[korb] = eq
        return sorted(zusammen.items(), key=lambda paar: paar[0])

    def _frisch_lesen(
        self,
    ) -> tuple[dict[str, Any], list[tuple[datetime, Decimal]]] | None:
        """Der **jetzige** Inhalt der Datei -- oder ``None``, wenn er nicht taugt.

        Nur fuer den ungebundenen Schreibvorgang. Ohne ihn schriebe ein Prozess, der
        seit Stunden nur zuschaut, seinen Schnappschuss von damals zurueck -- und
        loeschte damit einen Halt, den ein zweiter Prozess inzwischen gesetzt hat.
        ``None`` heisst darum ausdruecklich „nicht anfassen", nicht „ueberschreiben".
        """
        try:
            roh = self._pfad.read_bytes()
            daten_roh = json.loads(roh.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(daten_roh, dict):
            return None
        daten: dict[str, Any] = {}
        for schluessel, inhalt in daten_roh.items():
            if not isinstance(schluessel, str):
                return None
            daten[schluessel] = inhalt
        if daten.get("schema") not in (
            RISIKO_ZUSTAND_SCHEMA,
            RISIKO_ZUSTAND_SCHEMA_FENSTER,
        ):
            return None
        try:
            equity = _abbildung(daten.get("equity"), "equity")
            return daten, self._fenster_lesen(equity.get("fenster"))
        except _Unlesbar:
            return None

    def _ungebunden_sichern(self, lage: RisikoLage) -> str | None:
        """Ohne geprueftes Konto: nur das Equity-Fenster (Modul-Docstring).

        Die Faelle, und der zweite ist der Grund fuer die Fallunterscheidung:

        * **unlesbar** oder noch gar nicht gelesen -> gar nichts. Auf der Platte steht
          ein Halt, und der Beweis (``_beweis_sichern``) gehoert vor seine Ersetzung.
        * **Datei da und lesbar** -> ihr **jetziger** Inhalt wird zurueckgeschrieben,
          nur mit vereinigtem Fensterabschnitt. Bindung, Halt, Zaehler und Positionen
          bleiben stehen -- und zwar der Stand von jetzt, nicht der von unserem
          ``laden``. Gelesen wird also unmittelbar vor dem Schreiben; sonst loeschte
          ein Prozess, der nur zuschaut, den Halt eines zweiten, der gerade handelt.
        * **Datei da, aber nicht lesbar** -> gar nichts (dasselbe Argument).
        * **keine Datei** -> eine eigene Fensterdatei.

        Ein unveraendertes Fenster schreibt gar nichts: sonst ginge bei ruhigem Markt
        je Takt eine Datei auf die Platte, die sich nicht geaendert hat.
        """
        if not self._geladen or self._herkunft == "unlesbar":
            return None
        if lage.equity_fenster == self._fenster_auf_platte:
            return None
        frisch = self._frisch_lesen()
        if frisch is None:
            if self._pfad.exists():
                return None
            daten: dict[str, Any] = {
                "schema": RISIKO_ZUSTAND_SCHEMA_FENSTER,
                "equity": {"fenster": self._fenster_schreibform(lage.equity_fenster)},
            }
        else:
            daten, fenster_platte = frisch
            equity_alt = daten.get("equity")
            equity: dict[str, Any] = (
                dict(equity_alt) if isinstance(equity_alt, dict) else {}
            )
            equity["fenster"] = self._fenster_schreibform(
                self._fenster_vereinen(fenster_platte, lage.equity_fenster)
            )
            daten["equity"] = equity
        daten["geschrieben_am"] = datetime.now(UTC).isoformat()
        grund = self._schreiben(daten, beweis=False)
        if grund is None:
            self._fenster_auf_platte = list(lage.equity_fenster)
        return grund

    def sichern(self, lage: RisikoLage) -> str | None:
        """Schreibe die Lage atomar. Rueckgabe ``None`` heisst „steht auf der Platte".

        **Es wirft nicht.** Das ist die Antwort auf die Frage, was schlimmer ist -- ein
        Absturz nach dem Fill oder ein stillschweigend nicht gesicherter Zustand: der
        Absturz. ``RiskManager.record_open_fill`` laeuft in ``venue/mt5.py`` NACH dem
        Fill und VOR ``return result``; ein Wurf von hier naehme dem Aufrufer sein
        ``OrderResult``, waehrend die Position beim Broker steht. Aus einem
        Plattenproblem wuerde eine unbeaufsichtigte offene Position -- ohne Stop-
        Pflege, ohne Abgleich, ohne Schliessung.
        Stillschweigen ist der zweitschlechteste Ausgang und deshalb auch nicht die
        Loesung: der naechste Start laese einen aelteren Stand -- weniger Trades,
        kleineren Peak, keinen Halt.
        Also der dritte Weg: fangen, melden, den Zustand als unsicher fuehren. Was aus
        der Meldung wird, entscheidet ``RiskManager._sichern`` -- dort steht die
        Ablehnung, die daraus folgt.

        Ohne Bindung wird nur das Equity-Fenster geschrieben (``_ungebunden_sichern``);
        der Aufrufer hat dann noch kein Konto gesehen, und alles Uebrige waere die
        Vermischung zweier Konten.
        """
        bindung = self._bindung
        if bindung is None or self._waehrung is None:
            return self._ungebunden_sichern(lage)
        daten: dict[str, Any] = {
            "schema": RISIKO_ZUSTAND_SCHEMA,
            "geschrieben_am": datetime.now(UTC).isoformat(),
            "waehrung": self._waehrung,
            "bindung": {
                "salz": bindung.salz.hex(),
                "runden": bindung.runden,
                "abdruck": bindung.abdruck,
            },
            "halt": {
                "aktiv": lage.halt,
                "grund": lage.halt_grund,
                "seit": None if lage.halt_seit is None else lage.halt_seit.isoformat(),
            },
            "tageszaehler": {
                "tag": None if lage.handelstag is None else lage.handelstag.isoformat(),
                "je_instrument": dict(lage.trades_je_instrument),
                "je_konto": lage.trades_konto,
                "gesperrt": lage.zaehler_gesperrt,
            },
            "letzter_trade_at": {
                symbol: ts.isoformat() for symbol, ts in lage.letzter_trade_at.items()
            },
            "equity": {
                "tag": None
                if lage.equity_tag is None
                else lage.equity_tag.isoformat(),
                "tagesstart": None
                if lage.tagesstart_equity is None
                else str(lage.tagesstart_equity),
                "fenster": self._fenster_schreibform(lage.equity_fenster),
            },
            "offene_positionen": [
                {"instrument": symbol, "eroeffnet_am": ts.isoformat()}
                for symbol, ts in lage.offene_positionen
            ],
        }
        # Kein Nachziehen von ``_herkunft``/``_fenster_auf_platte``: beide steuern
        # ausschliesslich den ungebundenen Schreibvorgang, und eine einmal gesetzte
        # Bindung wird nie wieder geloest -- ab hier laeuft jedes ``sichern`` durch
        # diesen Zweig.
        return self._schreiben(daten, beweis=True)

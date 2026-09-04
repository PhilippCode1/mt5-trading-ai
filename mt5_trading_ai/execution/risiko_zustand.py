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
``PurePosixPath("C:\\\\Users\\\\<konto>\\\\AppData\\\\Local").is_absolute()`` ist
``False``, die Datei laege unter ``<repo>/C:\\Users\\...``. Die CI dieses Repos faehrt
ubuntu-latest. Ein relativer Pfad aus ``--zustandsordner`` hat dieselbe Wirkung; er
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

ZWEI SCHREIBER AUF EINER DATEI: LESEN, VEREINEN, SCHREIBEN
----------------------------------------------------------
Die Frage ist nicht theoretisch. Ein zweiter Runner, ein Neustart waehrend der alte
Prozess noch laeuft, eine Konsole neben dem Treiber -- alle drei bauen einen
``RiskManager`` auf **dieselbe** Datei (der Pfad kommt aus der Umgebung, nicht aus dem
Aufrufer). Jeder von ihnen haelt seinen Stand im Speicher und schreibt ihn fort.

Die Regel lautet: **unmittelbar vor jedem Schreibvorgang wird neu gelesen, und der
gelesene Stand wird mit dem eigenen abschnittsweise VEREINIGT -- jeder Abschnitt in
seine strenge Richtung.** Nicht "der letzte Schreiber gewinnt", nicht eine Sperrdatei.

*Warum keine Sperrdatei.* Vier Gruende, und der dritte allein genuegt:

1. Sie loeste ein anderes Problem. Verloren geht hier kein halb geschriebener Satz --
   ``os.replace`` ist atomar --, sondern eine **Aktualisierung auf veraltetem
   Lesestand**. Eine Sperre reihte Lauf A und Lauf B ordentlich hintereinander; A
   schriebe seinen stundenalten Schnappschuss dann nur geordnet zurueck. Gegen einen
   verlorenen Aktualisierungsschritt hilft ausschliesslich Lesen-Aendern-Schreiben.
2. Sie braucht einen Eigentuemer und eine Lebensdauer. Ein abgestuerzter Prozess
   laesst sie liegen. Sie nach einer Frist zu brechen ist geraten; sie nicht zu
   brechen heisst: es wird nicht mehr geschrieben.
3. Und der Schreibvorgang, der dann ausfaellt, ist genau der, der den **Halt** traegt.
   Eine Sperrdatei machte den schlimmsten Fall dieses Moduls schlimmer -- siehe
   "Wenn die Platte nicht mitspielt". Das Vereinigen kennt diesen Ausfall nicht: es
   blockiert nie, es kann die Strenge nur erhoehen.
4. Plattform: ``fcntl.flock`` gegen ``msvcrt.locking``, und ueber ein Netzlaufwerk
   haelt keins von beiden verlaesslich. Das Zustandsverzeichnis eines Windows-Profils
   kann eine Netzfreigabe sein.

*Die Richtung je Abschnitt* (``lage_vereinen``) -- jeweils die, die eher sperrt:

======================  ====================================================
Abschnitt               Regel beim Vereinen
======================  ====================================================
Halt-Latch              **ODER** -- ein gesetzter Halt gewinnt immer
Zaehlersperre           ODER (innerhalb desselben Handelstages)
Tageszaehler            Hoechstwert je Instrument und Konto
Letzter Trade           spaeterer Zeitpunkt (laengere Abklingzeit)
Tagesstart-Equity       hoeherer Wert (groesserer Tagesverlust)
Equity-Fenster          Hoechststand je Korb
Offene Positionen       Vereinigung; je Symbol die spaetere Eroeffnung
Handelstag/Equity-Tag   der spaetere Tag gewinnt mitsamt seinen Zaehlern
======================  ====================================================

**Der Halt-Latch hat genau einen Ausgang.** Ein gesetzter Halt verschwindet nur durch
eine ausdrueckliche Freigabe (``freigabe_vormerken``, gespeist aus
``RiskManager.release_drawdown`` bzw. der Freigabekennung am Konstruktor) -- nie
dadurch, dass ein Prozess einen aelteren Stand zurueckschreibt. Die Vormerkung gilt
**einmal** und wird erst von einem *gelungenen* Schreibvorgang verbraucht: scheitert
die Platte, ist die Freigabe nicht verloren, und ein Halt, den ein zweiter Prozess
danach setzt, wird von derselben Vormerkung nicht noch einmal geloescht.

**Wem die Datei gehoert, wird beim Schreiben erneut geprueft.** Steht dort inzwischen
die Bindung eines anderen Kontos, wird **nicht** geschrieben und der Grund gemeldet --
sonst vermischte dieser Lauf zwei Konten. Dieselbe Kontonummer mit anderem Salz (zwei
Prozesse, die beide keine Datei vorfanden und je eigenes Salz zogen) ist kein fremdes
Konto: das Salz der Platte wird dann uebernommen, damit die Datei eine Bindung behaelt
und nicht zwischen zweien hin- und herspringt.

**Was das NICHT ist.** Lesen-Aendern-Schreiben ist kein gegenseitiger Ausschluss.
Zwischen dem frischen Lesen und ``os.replace`` bleibt ein Fenster von der Dauer eines
Schreibvorgangs, in dem ein zweiter Schreiber landen kann; ein Halt, der genau dort
gesetzt wird, geht verloren. Das Fenster faellt damit von der Lebensdauer eines
Prozesses (Stunden) auf Millisekunden -- es wird nicht null. Wer wirklich zwei Runner
auf **ein** Konto faehrt, gibt jedem seinen eigenen Zustandsordner ueber
``--zustandsordner``; das ist ohnehin der vorgesehene Weg fuer zwei Konten.

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
from typing import Any, Final, Protocol

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

#: Die Dateien im Zustandsordner. Feste Namen, keine aus dem Konto abgeleiteten
#: (Begruendung bei ``standard_zustandsdatei``). Es gibt KEINE Umgebungsvariable
#: mehr, die den Ort umbiegt (D8, E-005): der Ort kommt aus ``--zustandsordner``
#: des Betriebswerkzeugs oder aus ``standard_zustandsordner``; jeder Aufrufer, der
#: einen ``RiskManager``, eine ``SchwebeAkte`` oder ein ``Positionsbuch`` baut,
#: nennt den Ort ausdruecklich. Eine Vorgabe "fluechtig, wenn nichts gesetzt ist"
#: war der Befund D8 der Bewertung: der Betrieb lief 21 Laeufe lang ohne Zustand.
RISIKOZUSTAND_DATEI: Final = "risikozustand.json"
SCHWEBEAKTE_DATEI: Final = "schwebende_auftraege.json"
POSITIONSBUCH_DATEI: Final = "positionsbuch.json"
#: Wer diese Datei im Zustandsordner anlegt, beendet den Betriebslauf geordnet.
STOPPDATEI_NAME: Final = "STOP"
#: Unterordner der Betriebsjournale (A18: kein Laufzeitzustand im Arbeitsbaum).
JOURNALORDNER_NAME: Final = "journale"

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


def verbotene_baeume(*, anker: Path | None = None) -> tuple[Path, ...]:
    """Die Verzeichnisse, in denen die Zustandsdatei nicht liegen darf.

    Genau zwei, und beide sind **abgeleitet, nicht geraten**:

    * ``mt5_trading_ai/`` -- der Paketbaum selbst.
    * sein **Elternverzeichnis**. Aus einem Klon heraus ist das die Arbeitskopie:
      dort liegen ``betrieb/`` (per ``.gitignore`` Laufzeitdatenhalde, von
      ``git clean -xdf`` geleert), ``tests/`` und die Wurzel. Aus einer Installation
      heraus ist es ``site-packages``; ein Zustand, den das naechste
      ``pip install`` mitnimmt, ist genauso wenig ein Halt.

    Die zweite Grenze ist der Grund fuer diese Funktion. Vorher wurde nur gegen den
    Paketbaum geprueft -- und ``<arbeitskopie>/betrieb/risikozustand.json`` ging als
    **absoluter** Pfad glatt durch, obwohl der Modul-Docstring genau dieses
    Verzeichnis als disqualifiziert nennt. Die Ortsgarantie deckte damit die Stelle
    nicht ab, mit der sie begruendet wird.

    Was hier weiterhin NICHT geprueft werden kann: irgendein anderer Arbeitsbaum auf
    derselben Maschine. Den koennte man nur raten. Die Zusage lautet deshalb „nicht
    in DIESEM Baum", nicht „in keinem".

    ``anker`` ist ausschliesslich fuer die Tests da: die Regel muss an einem gebauten
    Verzeichnis pruefbar sein, ohne dass ein Test die eigene Arbeitskopie beschreibt.
    """
    paket = Path(__file__).resolve().parents[1] if anker is None else anker.resolve()
    umfeld = paket.parent
    if umfeld == umfeld.parent:
        # Das Paket liegt unmittelbar unter der Dateisystemwurzel. Dann waere jeder
        # Pfad „im Umfeld" und die Regel sperrte alles -- also nur der Paketbaum.
        return (paket,)
    return (paket, umfeld)


def _absolut_oder_wurf(roh: str, quelle: str) -> Path:
    """Ein Pfad aus der Umgebung -- absolut und ausserhalb des Baums, oder gar nicht.

    Zwei Wege in denselben Fehler, und beide sind nachpruefbar:

    * **Relativ.** Er wird gegen das Arbeitsverzeichnis aufgeloest. Das ist bei einer
      Zustandsdatei kein Schoenheitsfehler, sondern der Verlust der ganzen Begruendung:
      „Datei fehlt = frei" traegt nur, weil die Datei ausserhalb des Arbeitsbaums liegt
      und nur ein Mensch sie loeschen kann. Im Baum loescht sie ``git clean -xdf``.
    * **Im Paketbaum oder in dem Baum, der ihn enthaelt** (``verbotene_baeume``).
      Dort landet sie in git oder in der Laufzeitdatenhalde: der Halt *einer* Maschine
      waere der Halt *jedes* Klons, ein ``git checkout`` einer aelteren Fassung eine
      stille Freigabe, ein ``git clean -xdf`` das Ende des Halts -- und der
      Kontoabdruck stuende im Verlauf.

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
    aufgeloest = pfad.resolve()
    for baum in verbotene_baeume():
        if aufgeloest.is_relative_to(baum):
            raise ZustandsortFehler(
                f"{quelle}={roh!r} liegt in {baum}. Der Zustand gehoert zur Maschine "
                "und zum Konto, nicht zur Arbeitskopie -- dort loescht ihn ein "
                "Aufraeumbefehl oder ein Auschecken hebt ihn auf, und beides waere "
                "eine stille Freigabe."
            )
    return pfad


def standard_zustandsordner(
    *,
    umgebung: Mapping[str, str] | None = None,
    ist_windows: bool | None = None,
) -> Path:
    """Das Zustandsverzeichnis des Benutzers -- ausserhalb des Arbeitsbaums.

    Die Vorgabe fuer ``--zustandsordner`` (``tools/live_betrieb.py``,
    ``tools/zustand.py``). Keine Umgebungsvariable des Betreibers wird gelesen;
    gefragt werden nur die Plattformvariablen ``LOCALAPPDATA`` (Windows) und
    ``XDG_STATE_HOME`` (POSIX), und beide nur als Auskunft, nicht als Anweisung.

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
    # Kein Wurf fuer die vom System gesetzten Variablen: sie sind keine Anweisung des
    # Betreibers, sondern eine Auskunft der Plattform. Ist sie unbrauchbar (leer oder
    # relativ), gilt der naechste Kandidat -- am Ende immer ein absoluter Heimatpfad.
    plattform = "LOCALAPPDATA" if windows else "XDG_STATE_HOME"
    roh = umg.get(plattform)
    # Ob der Kandidat absolut ist, entscheiden die Pfadregeln der GEFRAGTEN Plattform,
    # nicht die der laufenden: ``Path("C:\\Users\\...").is_absolute()`` ist unter POSIX
    # ``False`` (dort ist ein Windows-Pfad ein relatives Namensstueck), und genau daran
    # fiel der Test dieser Regel auf ubuntu-latest (CI-Lauf 4d02db3): der
    # Windows-Zweig nahm den Heimatpfad statt ``%LOCALAPPDATA%``. ``PureWindowsPath``
    # und ``PurePosixPath`` rechnen auf jedem Rechner gleich; ``os.name`` bleibt
    # unangetastet, und das zurueckgegebene ``Path`` ist weiter das der Plattform.
    from pathlib import PurePosixPath, PureWindowsPath

    rein = PureWindowsPath if windows else PurePosixPath
    if roh and rein(roh).is_absolute():
        return Path(roh) / "mt5_trading_ai" / "risiko"
    return Path.home() / ".local" / "state" / "mt5_trading_ai" / "risiko"


def zustandsordner_pruefen(pfad: Path | str, quelle: str = "--zustandsordner") -> Path:
    """Ein vom Betreiber genannter Zustandsordner -- absolut und ausserhalb des
    Baums, oder ``ZustandsortFehler``.

    Dieselbe Regel wie frueher fuer die Umgebungsvariablen, jetzt fuer das
    Kommandozeilenargument: relativ oder im Paket-/Arbeitsbaum wird abgewiesen,
    nicht zurechtgebogen (Begruendung bei ``_absolut_oder_wurf``).
    """
    return _absolut_oder_wurf(str(pfad), quelle)


def zustandsordner_waehlen(vorgabe: Path | str | None) -> Path:
    """``--zustandsordner`` oder der Standardordner -- geprueft, nie geraten."""
    if vorgabe is None:
        return standard_zustandsordner()
    return zustandsordner_pruefen(vorgabe)


def standard_zustandsdatei(
    *,
    ordner: Path | None = None,
    umgebung: Mapping[str, str] | None = None,
    ist_windows: bool | None = None,
) -> Path:
    """Der Pfad der Zustandsdatei: ``RISIKOZUSTAND_DATEI`` im Zustandsordner.

    Ein **fester** Dateiname, kein aus dem Konto abgeleiteter. Ein abgeleiteter Name
    waere bequem (je Konto automatisch eine Datei), oeffnete aber ein Loch: das noetige
    Salz muesste neben den Dateien liegen, und ein verlorenes Salz liesse jede
    Zustandsdatei *unauffindbar* werden -- also jeden Halt lautlos verschwinden. Ein
    fester Name kennt diesen Weg nicht: ein fremdes Konto trifft auf eine Datei, die da
    ist, und wird erkannt (``DateiZustand.binde``). Wer zwei Konten faehrt, gibt
    jedem Lauf seinen eigenen ``--zustandsordner``.
    """
    if ordner is None:
        ordner = standard_zustandsordner(umgebung=umgebung, ist_windows=ist_windows)
    return ordner / RISIKOZUSTAND_DATEI


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


def fenster_vereinen(
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


def _spaeterer(eins: date | None, zwei: date | None) -> date | None:
    """Der spaetere von zwei Tagen; ``None`` heisst „kein Tag" und verliert."""
    if eins is None:
        return zwei
    if zwei is None:
        return eins
    return eins if eins >= zwei else zwei


def _halt_uebernehmen(
    platte: RisikoLage, eigen: RisikoLage
) -> tuple[str, datetime | None]:
    """Grund und Beginn des Halts, wenn beide Seiten halten.

    Der **frueher** begonnene Halt gewinnt: er ist der urspruengliche, der spaetere
    ist seine Wiederholung. Ein bekannter Beginn schlaegt einen unbekannten -- sonst
    verloere die Uebernahme genau die Angabe, mit der ein Mensch die Lage nachtraeglich
    einordnet. Sind beide unbekannt, gilt der Stand der Platte: das ist der Grund, den
    ein Leser dort ohnehin schon findet.
    """
    if eigen.halt_seit is None:
        return platte.halt_grund, platte.halt_seit
    if platte.halt_seit is None:
        return eigen.halt_grund, eigen.halt_seit
    if platte.halt_seit <= eigen.halt_seit:
        return platte.halt_grund, platte.halt_seit
    return eigen.halt_grund, eigen.halt_seit


def lage_vereinen(
    platte: RisikoLage,
    eigen: RisikoLage,
    *,
    freigabe: bool = False,
    geschlossen: frozenset[tuple[str, datetime]] = frozenset(),
) -> RisikoLage:
    """Der Stand der Platte und der eigene zu einem -- je Abschnitt strenger Richtung.

    Die Tabelle und die Begruendung stehen im Modul-Docstring unter „Zwei Schreiber
    auf einer Datei". Drei Punkte gehoeren hierher, weil sie leicht falsch
    weitergeschrieben werden:

    * ``freigabe`` ist der **einzige** Weg, auf dem ein Halt der Platte verschwindet.
      Sie steht fuer eine menschliche Entscheidung mit Kennung
      (``RiskManager.release_drawdown``), nicht fuer „mein Speicher haelt gerade
      nicht". Ohne sie gilt ODER, und zwar in beide Richtungen: auch der eigene Halt
      ueberlebt einen Stand der Platte, der frei aussieht.
    * ``geschlossen`` ist dasselbe fuer offene Positionen -- und es sind **Paare**
      ``(Symbol, Eroeffnungszeit)``, nicht blosse Symbole. Ohne die ausdrueckliche
      Geste waere die Vereinigung von Positionen eine **Ratsche**: einmal auf der
      Platte, nie wieder weg, der Positionsdeckel binnen weniger Tage dauerhaft voll
      -- eine Sperre ohne Ausgang, und die wird im Betrieb ausgebaut statt bedient.
      Ein Eintrag der Platte verschwindet darum genau dann, wenn dieser Lauf **genau
      diesen** Eintrag geschlossen hat (Symbol UND Eroeffnungszeit stimmen ueberein,
      ``RiskManager.record_close``) und er das Symbol auch nicht wieder offen fuehrt.

      Das Paar ist der ganze Punkt, und hier stand einmal nur das Symbol. Gemessen
      an jenem Stand: Lauf A eroeffnet EURUSD, die Platte klemmt, A ruft
      ``record_close`` -- der Schreibvorgang scheitert, die Vormerkung bleibt also
      absichtlich stehen. Lauf B eroeffnet EURUSD neu und schreibt es. A's naechster
      **gelungener** Takt loeschte B's Eintrag: Datei danach ohne EURUSD, ein
      Neustart sah eine Position weniger, als offen waren -- der Positionsdeckel
      zaehlte zu niedrig, also die milde Richtung. Mit dem Paar bleibt B's spaeterer
      Eintrag stehen, weil A eine **andere** Eroeffnungszeit geschlossen hat.

      **Die Grenze dieser Zusicherung, ausdruecklich:** dieser Abschnitt fuehrt je
      Symbol genau einen Eintrag (netto, ``RiskManager.record_open_fill``). Eroeffnet
      ein zweiter Lauf dasselbe Symbol **nicht spaeter** als der schliessende, ist es
      fuer diese Datei derselbe Eintrag, und er faellt mit der Schliessung. Wer je
      Bein zaehlen will, braucht einen Positionsschluessel des Brokers, nicht
      ``(Symbol, Zeit)``; das ist bewusst nicht Gegenstand dieser Schicht.
    * Bei **verschiedenen** Handelstagen gewinnt der spaetere Tag mitsamt seinen
      Zaehlern -- nicht der Hoechstwert ueber beide. Sonst truege eine Tageskappe die
      Zaehlung von gestern in heute und waere keine Tageskappe mehr. Innerhalb
      **desselben** Tages ist der Hoechstwert richtig: zu hoch irren kostet
      Eroeffnungen bis Mitternacht, zu niedrig irren kostet Geld (Modul-Docstring,
      „Tageszaehler").
    """
    halt = eigen.halt if freigabe else (platte.halt or eigen.halt)
    if not halt:
        halt_grund, halt_seit = "", None
    elif freigabe or not platte.halt:
        halt_grund, halt_seit = eigen.halt_grund, eigen.halt_seit
    elif not eigen.halt:
        halt_grund, halt_seit = platte.halt_grund, platte.halt_seit
    else:
        halt_grund, halt_seit = _halt_uebernehmen(platte, eigen)

    tage_verschieden = (
        platte.handelstag is not None
        and eigen.handelstag is not None
        and platte.handelstag != eigen.handelstag
    )
    if tage_verschieden:
        juenger = (
            platte
            if _spaeterer(platte.handelstag, eigen.handelstag) == platte.handelstag
            else eigen
        )
        handelstag = juenger.handelstag
        je_instrument = dict(juenger.trades_je_instrument)
        trades_konto = juenger.trades_konto
        zaehler_gesperrt = juenger.zaehler_gesperrt
    else:
        handelstag = _spaeterer(platte.handelstag, eigen.handelstag)
        je_instrument = dict(platte.trades_je_instrument)
        for symbol, anzahl in eigen.trades_je_instrument.items():
            if anzahl > je_instrument.get(symbol, 0):
                je_instrument[symbol] = anzahl
        trades_konto = max(platte.trades_konto, eigen.trades_konto)
        zaehler_gesperrt = platte.zaehler_gesperrt or eigen.zaehler_gesperrt

    # Die Abklingzeit haengt nicht am Tageswechsel: der spaetere Zeitpunkt sperrt
    # laenger und ist damit unabhaengig vom Tag die strenge Richtung.
    letzter = dict(platte.letzter_trade_at)
    for symbol, ts in eigen.letzter_trade_at.items():
        vorher = letzter.get(symbol)
        if vorher is None or ts > vorher:
            letzter[symbol] = ts

    if (
        platte.equity_tag is not None
        and eigen.equity_tag is not None
        and platte.equity_tag != eigen.equity_tag
    ):
        juenger_eq = platte if platte.equity_tag > eigen.equity_tag else eigen
        equity_tag = juenger_eq.equity_tag
        tagesstart = juenger_eq.tagesstart_equity
    else:
        equity_tag = _spaeterer(platte.equity_tag, eigen.equity_tag)
        # Hoeher heisst groesserer Tagesverlust: der Anteil (start - equity)/start
        # waechst mit dem Start. Also der Hoechstwert.
        kandidaten = [
            wert
            for wert in (platte.tagesstart_equity, eigen.tagesstart_equity)
            if wert is not None
        ]
        tagesstart = max(kandidaten) if kandidaten else None

    # Je Symbol die SPAETERE Eroeffnung: die Mindesthaltedauer misst
    # ``now - opened_at`` (``gates/evaluation.py``), ein juengerer Eintrag sperrt
    # also laenger. Der Positionsdeckel zaehlt ohnehin nur die Eintraege.
    eigene_symbole = {symbol for symbol, _ts in eigen.offene_positionen}
    positionen: dict[str, datetime] = {}
    for symbol, ts in platte.offene_positionen:
        if (symbol, ts) in geschlossen and symbol not in eigene_symbole:
            continue
        positionen[symbol] = ts
    for symbol, ts in eigen.offene_positionen:
        vorhanden = positionen.get(symbol)
        if vorhanden is None or ts > vorhanden:
            positionen[symbol] = ts

    return RisikoLage(
        halt=halt,
        halt_grund=halt_grund,
        halt_seit=halt_seit,
        handelstag=handelstag,
        zaehler_gesperrt=zaehler_gesperrt,
        trades_je_instrument=je_instrument,
        trades_konto=trades_konto,
        letzter_trade_at=letzter,
        equity_tag=equity_tag,
        tagesstart_equity=tagesstart,
        equity_fenster=fenster_vereinen(platte.equity_fenster, eigen.equity_fenster),
        offene_positionen=sorted(positionen.items()),
    )


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
    return hashlib.pbkdf2_hmac("sha256", konto_id.encode("utf-8"), salz, runden).hex()


@dataclass(frozen=True)
class _Gelesen:
    """Der Inhalt einer Datei, schon nach der fail-closed-Leiter aufgeloest.

    Bewusst **ohne** Nebenwirkung auf den Speicher: ``laden`` braucht dieselbe
    Auswertung wie das frische Lesen unmittelbar vor jedem Schreibvorgang. Zwei
    getrennte Parser liefen frueher oder spaeter auseinander -- und der zweite waere
    genau der, den niemand liest, weil er nur im Schreibpfad steht.

    ``beweis`` heisst: diese Datei ist am Stueck unlesbar und gehoert vor ihrer
    Ersetzung zur Seite gelegt. Ein Defekt in einem einzelnen Abschnitt setzt es
    nicht -- dort steht noch eine lesbare Bindung, und die Leiter hat den Abschnitt
    schon in einen Halt aufgeloest.
    """

    lage: RisikoLage
    herkunft: str
    sperrgrund: str | None = None
    bindung: _Bindung | None = None
    waehrung: str | None = None
    beweis: bool = False


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
        #: Einmalige, ausdrueckliche Freigabe: nur sie darf einen Halt loeschen, der
        #: auf der Platte steht (Modul-Docstring, „Zwei Schreiber"). Sie wird erst von
        #: einem GELUNGENEN gebundenen Schreibvorgang verbraucht.
        self._freigabe_vorgemerkt = False
        #: Eintraege ``(Symbol, Eroeffnungszeit)``, die dieser Lauf ausdruecklich
        #: geschlossen hat und die darum aus der Datei verschwinden duerfen. Ohne diese
        #: Liste waere die Vereinigung von Positionen eine Ratsche; die Zeit gehoert
        #: dazu, damit die Geste nicht die Position eines zweiten Laufs mitnimmt
        #: (beides: ``lage_vereinen``).
        self._geschlossen: set[tuple[str, datetime]] = set()
        #: Die zuletzt vereinigte Lage -- was beim letzten ``sichern`` wirklich galt.
        #: Der Aufrufer zieht daraus einen fremden Halt und fremde Zaehler nach; ohne
        #: das schriebe dieser Lauf den Halt eines zweiten zwar nicht mehr weg,
        #: handelte aber selbst munter weiter.
        self._zuletzt_gesehen: RisikoLage | None = None

    @property
    def pfad(self) -> Path | None:
        return self._pfad

    @property
    def dauerhaft(self) -> bool:
        """Eine Datei ueberdauert den Neustart -- im Gegensatz zum Testtyp
        ``FluechtigerZustand``."""
        return True

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

    @property
    def zuletzt_gesehen(self) -> RisikoLage | None:
        """Was beim letzten ``sichern`` wirklich auf der Platte stand -- vereinigt.

        ``None`` heisst „dort lag nichts Verwertbares" -- keine Datei, sie war unlesbar,
        oder es wurde ungebunden gesichert (dieser Zweig zieht nichts nach, Begruendung
        bei ``_ungebunden_sichern``). Sonst ist es der Stand, der eben geschrieben
        wurde: der eigene, vereinigt mit dem der Platte. Der Aufrufer zieht daraus nach
        -- vor allem einen **fremden Halt**. Ohne dieses Nachziehen waere die Reparatur
        halb: der Halt eines zweiten Prozesses bliebe zwar auf der Platte stehen,
        dieser Prozess aber wuesste nichts davon und eroeffnete weiter.
        """
        return self._zuletzt_gesehen

    def freigabe_vormerken(self) -> None:
        """Merke eine ausdrueckliche Freigabe fuer den naechsten Schreibvorgang vor.

        Der **einzige** Weg, auf dem ein Halt verschwindet, der auf der Platte steht
        (Modul-Docstring, „Zwei Schreiber"). Der Aufrufer ruft das erst, nachdem er
        die Kennung geprueft hat (``RiskManager.freigabe_gueltig``) -- dieses Modul
        sieht die Kennung nicht, weil sie freier Text ist und nicht in die Datei
        gehoert.

        Einmalig und erst von einem **gelungenen** gebundenen Schreibvorgang
        verbraucht. Beides ist Absicht: scheitert die Platte, ist die Freigabe nicht
        still verloren; und ein Halt, den ein zweiter Prozess nach dem gelungenen
        Schreiben setzt, wird von derselben Geste nicht ein zweites Mal geloescht.
        """
        self._freigabe_vorgemerkt = True

    def schliessung_vormerken(self, instrument: str, eroeffnet_am: datetime) -> None:
        """Merke: **dieser** Eintrag ist geschlossen und darf aus der Datei
        verschwinden.

        Das Gegenstueck zu ``freigabe_vormerken`` fuer die offenen Positionen -- und
        aus demselben Grund noetig: seit vereinigt statt ueberschrieben wird, wuerde
        ein Symbol, das einmal in der Datei steht, dort ewig bleiben und den
        Positionsdeckel dauerhaft fuellen. Auch das ist einmalig und wird von einem
        gelungenen gebundenen Schreibvorgang verbraucht.

        ``eroeffnet_am`` ist nicht schmueckendes Beiwerk: die Vormerkung ueberlebt
        einen gescheiterten Schreibvorgang (mit Absicht -- sonst waere sie nach einem
        Plattenfehler still verloren), und in genau diesem Fenster kann ein zweiter
        Lauf dasselbe Symbol neu eroeffnen. Ohne die Zeit naehme der naechste
        gelungene Takt dieses Laufs den fremden Eintrag mit. Die Begruendung samt
        gemessenem Ablauf und der verbleibenden Grenze steht bei ``lage_vereinen``.
        """
        self._geschlossen.add((instrument, eroeffnet_am))

    # --- Lesen ------------------------------------------------------------
    def _roh_lesen(self) -> dict[str, Any] | str | None:
        """Die Datei als geprueftes JSON-Objekt.

        ``None`` heisst „keine Datei" -- kein Defekt, sondern der erste Start. Ein
        ``str`` ist der Grund, aus dem sie nicht zu lesen war.
        """
        if not self._pfad.exists():
            return None
        try:
            roh = self._pfad.read_bytes()
        except OSError:
            return "zustand_datei_unlesbar"
        if not roh.strip():
            return "zustand_datei_leer"
        try:
            daten_roh = json.loads(roh.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "zustand_kein_json"
        if not isinstance(daten_roh, dict):
            return "zustand_kein_objekt"
        daten: dict[str, Any] = {}
        for schluessel, inhalt in daten_roh.items():
            if not isinstance(schluessel, str):
                return "zustand_kein_objekt"
            daten[schluessel] = inhalt
        return daten

    @classmethod
    def _auswerten(cls, daten: dict[str, Any]) -> _Gelesen:
        """Die fail-closed-Leiter auf ein gelesenes Objekt -- rein, ohne Speicher.

        Beide Leser dieses Moduls gehen hier durch: ``laden`` beim Start und das
        frische Lesen unmittelbar vor jedem Schreibvorgang.
        """
        if daten.get("schema") == RISIKO_ZUSTAND_SCHEMA_FENSTER:
            return cls._fensterdatei_auswerten(daten)
        if daten.get("schema") != RISIKO_ZUSTAND_SCHEMA:
            return _Gelesen(
                lage=RisikoLage(
                    halt=True,
                    halt_grund="zustand_fremdes_schema",
                    zaehler_gesperrt=True,
                ),
                herkunft="unlesbar",
                sperrgrund="zustand_fremdes_schema",
                beweis=True,
            )

        try:
            waehrung = _text(daten.get("waehrung"), "waehrung")
            bindung_roh = _abbildung(daten.get("bindung"), "bindung")
            bindung = _Bindung(
                salz=bytes.fromhex(_text(bindung_roh.get("salz"), "bindung.salz")),
                runden=_ganzzahl(bindung_roh.get("runden"), "bindung.runden"),
                abdruck=_text(bindung_roh.get("abdruck"), "bindung.abdruck"),
            )
        except (_Unlesbar, ValueError):
            # Ohne lesbare Bindung ist nicht feststellbar, ZU WEM dieser Zustand
            # gehoert. Ihn zu uebernehmen hiesse, den Halt eines fremden Kontos zu
            # ignorieren oder den eigenen zu verlieren.
            return cls._defekt("zustand_bindung_unlesbar")
        if bindung.runden <= 0:
            return cls._defekt("zustand_bindung_unlesbar")

        lage = RisikoLage()

        # --- Halt: jeder Defekt hier ist ein Halt ---------------------------
        try:
            halt_roh = _abbildung(daten.get("halt"), "halt")
            lage.halt = _wahrheit(halt_roh.get("aktiv"), "halt.aktiv")
            lage.halt_grund = str(halt_roh.get("grund") or "")
            seit = halt_roh.get("seit")
            lage.halt_seit = None if seit is None else _zeitpunkt(seit, "halt.seit")
        except _Unlesbar as fehler:
            return cls._abschnitt_defekt(
                lage, f"zustand_halt_unlesbar[{fehler}]", bindung, waehrung
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
            lage.equity_fenster = cls._fenster_lesen(equity_roh.get("fenster"))
        except _Unlesbar as fehler:
            return cls._abschnitt_defekt(
                lage, f"zustand_equity_unlesbar[{fehler}]", bindung, waehrung
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
            lage.offene_positionen = cls._positionen_lesen(
                daten.get("offene_positionen")
            )
        except _Unlesbar as fehler:
            return cls._abschnitt_defekt(
                lage, f"zustand_positionen_unlesbar[{fehler}]", bindung, waehrung
            )

        return _Gelesen(
            lage=lage, herkunft="gelesen", bindung=bindung, waehrung=waehrung
        )

    @staticmethod
    def _defekt(grund: str) -> _Gelesen:
        """Die ganze Datei ist unlesbar: Halt, Zaehlersperre, Beweis fuer die Seite."""
        return _Gelesen(
            lage=RisikoLage(halt=True, halt_grund=grund, zaehler_gesperrt=True),
            herkunft="unlesbar",
            sperrgrund=grund,
            beweis=True,
        )

    @staticmethod
    def _abschnitt_defekt(
        lage: RisikoLage, grund: str, bindung: _Bindung, waehrung: str
    ) -> _Gelesen:
        """Ein einzelner Abschnitt ist hin -- Halt, aber die Bindung bleibt lesbar.

        Kein ``beweis``: die Datei ist als Ganzes gueltiges JSON mit lesbarer Bindung,
        und der Halt steht schon in der Lage. Sie wird darum von dem Lauf ersetzt, der
        diesen Halt traegt -- so kommt der Betrieb aus dem Defekt wieder heraus.
        """
        lage.halt = True
        lage.halt_grund = grund
        lage.zaehler_gesperrt = True
        return _Gelesen(
            lage=lage,
            herkunft="unlesbar",
            sperrgrund=grund,
            bindung=bindung,
            waehrung=waehrung,
        )

    @classmethod
    def _fensterdatei_auswerten(cls, daten: dict[str, Any]) -> _Gelesen:
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
            fenster = cls._fenster_lesen(equity_roh.get("fenster"))
        except _Unlesbar as fehler:
            return cls._defekt(f"zustand_fenster_unlesbar[{fehler}]")
        return _Gelesen(lage=RisikoLage(equity_fenster=fenster), herkunft="fenster")

    def laden(self) -> Zustandsbefund:
        """Lies die Datei und loese jeden kaputten Abschnitt fail-closed auf."""
        self._geladen = True
        self._fenster_auf_platte = []
        self._gelesene_bindung = None
        self._gelesene_waehrung = None
        roh = self._roh_lesen()
        if roh is None:
            # Kein Zustand ist etwas anderes als verlorener Zustand. Begruendung im
            # Modul-Docstring; sie traegt nur wegen der Ortswahl (kein ``git clean``).
            self._herkunft = "neu"
            return Zustandsbefund(lage=RisikoLage(), herkunft="neu")
        if isinstance(roh, str):
            return self._unlesbar(roh)
        gelesen = self._auswerten(roh)
        if gelesen.beweis:
            assert gelesen.sperrgrund is not None
            return self._unlesbar(gelesen.sperrgrund)
        self._gelesene_bindung = gelesen.bindung
        self._gelesene_waehrung = gelesen.waehrung
        self._herkunft = gelesen.herkunft
        if gelesen.herkunft != "unlesbar":
            self._fenster_auf_platte = list(gelesen.lage.equity_fenster)
        return Zustandsbefund(
            lage=gelesen.lage,
            herkunft=gelesen.herkunft,
            sperrgrund=gelesen.sperrgrund,
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

    def _frisch_lesen(self) -> tuple[dict[str, Any], _Gelesen] | None:
        """Der **jetzige** Inhalt der Datei -- roh und ausgewertet, oder ``None``.

        Steht **vor jedem** Schreibvorgang, gebunden wie ungebunden. Ohne ihn schriebe
        ein Prozess seinen Schnappschuss von vorhin zurueck und loeschte damit einen
        Halt, den ein zweiter Prozess inzwischen gesetzt hat -- der Grund fuer die
        ganze Vereinigungsregel (Modul-Docstring).

        ``None`` heisst „keine Datei". Ein Defekt kommt als ``_Gelesen`` mit
        ``herkunft == "unlesbar"`` zurueck und wird vom Aufrufer entschieden -- er
        allein weiss, ob er den Halt, der darin steckt, selbst schon traegt.

        Das rohe Objekt kommt mit, weil der ungebundene Zweig die Datei **nicht neu
        baut**: er ersetzt einen einzigen Abschnitt und laesst jedes andere Feld Byte
        fuer Byte stehen -- auch Felder, die eine spaetere Fassung eingefuehrt hat und
        diese hier nicht kennt.
        """
        roh = self._roh_lesen()
        if roh is None:
            return None
        if isinstance(roh, str):
            return {}, self._defekt(roh)
        return roh, self._auswerten(roh)

    def _platte_gehoert_uns(
        self, gelesen: _Gelesen, eigen: _Bindung
    ) -> tuple[_Bindung | None, str | None]:
        """Wem gehoert die Datei, die JETZT dort steht? Rueckgabe: Bindung, Grund.

        Nicht dieselbe Frage wie ``binde``: dort ging es um den Stand von ``laden``,
        hier um den Stand von vor einer Millisekunde. Eine Datei, die inzwischen einem
        anderen Konto gehoert, wird **nicht** ueberschrieben -- der Zustand zweier
        Konten in einer Datei ist genau die Vermischung, gegen die die Bindung gebaut
        ist, und der Fehlgriff dieses Laufs darf den Halt des anderen nicht mitnehmen.

        Dieselbe Kontonummer mit **anderem Salz** ist dagegen kein fremdes Konto: zwei
        Prozesse, die beide keine Datei vorfanden, ziehen je ein eigenes Salz. Der
        Abdruck wird darum mit dem Salz DER PLATTE nachgerechnet und ihre Bindung
        uebernommen -- sonst spraenge die Datei zwischen zwei Bindungen hin und her.
        Nachgerechnet wird nur, wenn die Bindungen sich unterscheiden: die
        Schluesselableitung kostet ``KDF_RUNDEN`` Runden und laeuft sonst je Takt.
        """
        if gelesen.herkunft == "fenster":
            # Die ungebundene Datei kennt kein Konto -- da ist nichts zu vermischen.
            return eigen, None
        if gelesen.bindung is None or gelesen.waehrung is None:
            # Typwaechter, kein Melder: ``_auswerten`` liefert beide Felder fuer jede
            # Datei mit vollem Schema, und ohne sie kaeme sie hier gar nicht an
            # (``herkunft == "unlesbar"`` faengt der Aufrufer vorher ab). Er steht
            # trotzdem da, weil die stille Alternative -- ``assert`` oder eine
            # Typzusicherung -- im Zweifel schriebe statt abzulehnen.
            return None, "zustand_bindung_unlesbar_beim_sichern"
        if gelesen.waehrung != self._waehrung:
            return None, "zustand_fremde_waehrung_beim_sichern"
        if gelesen.bindung == eigen:
            return eigen, None
        konto = self._konto_id
        fremd = gelesen.bindung
        if konto is None or _abdruck(konto, fremd.salz, fremd.runden) != fremd.abdruck:
            return None, "zustand_fremdes_konto_beim_sichern"
        return fremd, None

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

        Dieser Zweig setzt ``zuletzt_gesehen`` **nicht**. Das war einmal anders und ist
        eine bewusste Ruecknahme: bevor dieser Lauf irgendetwas eroeffnen kann, ruft
        ``RiskManager.authorize_opening`` als Allererstes den Kontoabgleich und bindet
        sich -- ab da laeuft jedes ``sichern`` durch den gebundenen Zweig, der den
        fremden Stand ohnehin nachreicht. Ein Nachziehen schon hier waere ein Melder,
        der nichts meldet, was nicht ein paar Zeilen spaeter ohnehin auffiele; die
        Mutationsprobe hat genau das gezeigt (keine Zusicherung wurde rot).
        """
        if not self._geladen:
            return None
        if self._herkunft == "unlesbar":
            return None
        frisch = self._frisch_lesen()
        if frisch is None:
            if lage.equity_fenster == self._fenster_auf_platte:
                return None
            daten: dict[str, Any] = {
                "schema": RISIKO_ZUSTAND_SCHEMA_FENSTER,
                "equity": {"fenster": self._fenster_schreibform(lage.equity_fenster)},
            }
        else:
            daten, gelesen = frisch
            if gelesen.herkunft == "unlesbar":
                # Dort steht ein Halt, und der Beweis gehoert vor seine Ersetzung.
                return None
            fenster = fenster_vereinen(gelesen.lage.equity_fenster, lage.equity_fenster)
            if fenster == gelesen.lage.equity_fenster:
                self._fenster_auf_platte = list(fenster)
                return None
            equity_alt = daten.get("equity")
            equity: dict[str, Any] = (
                dict(equity_alt) if isinstance(equity_alt, dict) else {}
            )
            equity["fenster"] = self._fenster_schreibform(fenster)
            daten["equity"] = equity
        daten["geschrieben_am"] = datetime.now(UTC).isoformat()
        grund = self._schreiben(daten, beweis=False)
        if grund is None:
            self._fenster_auf_platte = list(lage.equity_fenster)
        return grund

    def _vereinen(self, platte: RisikoLage, eigen: RisikoLage) -> RisikoLage:
        """``lage_vereinen`` mit den beiden vorgemerkten Gesten dieses Laufs."""
        return lage_vereinen(
            platte,
            eigen,
            freigabe=self._freigabe_vorgemerkt,
            geschlossen=frozenset(self._geschlossen),
        )

    def _gebunden_sichern(self, lage: RisikoLage, bindung: _Bindung) -> str | None:
        """Mit geprueftem Konto: den vollen Zustand -- vereinigt, nicht ueberschrieben.

        Hier sass das Loch, das die vorige Reparatur nur im ungebundenen Zweig
        geschlossen hatte: dieser Zweig schrieb ``self._lage()`` ohne Neulesen ueber
        die Datei. Ein Lauf, der frueh gestartet war und einen Altstand ohne Halt im
        Speicher hielt, band sich mit seiner ersten Order -- und loeschte damit den
        Drawdown-Halt eines zweiten Laufs. Weil sich ein Live-Prozess mit seiner ersten
        Order dauerhaft bindet, war der geschuetzte Zustand der kurze und der
        ungeschuetzte der Dauerzustand.

        Vier Faelle:

        * **keine Datei** -> die eigene Lage ist der ganze Zustand.
        * **lesbar, gleiches Konto** -> vereinigen (``lage_vereinen``) und schreiben.
        * **lesbar, fremdes Konto/fremde Waehrung** -> **nicht** schreiben, Grund
          melden. Der Aufrufer macht daraus eine Ablehnung; zwei Konten in einer Datei
          waeren schlimmer als ein ungesicherter Takt.
        * **unlesbar** -> nur ersetzen, wenn dieser Lauf den Halt, der darin steckt,
          selbst traegt (er hat den Defekt gelesen) oder wenn eine ausdrueckliche
          Freigabe vorliegt. Sonst nicht schreiben: der Defekt IST der Halt, und ihn
          durch einen freien Stand zu ersetzen waere die stille Freigabe.
        """
        frisch = self._frisch_lesen()
        freigabe = self._freigabe_vorgemerkt
        if frisch is None:
            zu_schreiben = lage
            self._zuletzt_gesehen = None
        else:
            _roh, gelesen = frisch
            if gelesen.herkunft == "unlesbar":
                if not (self._herkunft == "unlesbar" or freigabe):
                    self._schreibfehler_text = (
                        f"Die Zustandsdatei ist seit dem Laden unlesbar geworden "
                        f"({gelesen.sperrgrund}). Sie wird nicht ersetzt -- ein "
                        "unlesbarer Zustand ist ein Halt, und dieser Lauf traegt ihn "
                        "nicht."
                    )
                    self._zuletzt_gesehen = gelesen.lage
                    return "zustand_defekt_auf_der_platte"
                zu_schreiben = lage
                self._zuletzt_gesehen = None
            else:
                platte_bindung, fremd = self._platte_gehoert_uns(gelesen, bindung)
                if fremd is not None or platte_bindung is None:
                    self._schreibfehler_text = (
                        f"Die Zustandsdatei gehoert inzwischen einem anderen Konto "
                        f"({fremd}). Sie wird nicht ueberschrieben."
                    )
                    self._zuletzt_gesehen = None
                    return fremd if fremd is not None else "zustand_bindung_unlesbar"
                bindung = platte_bindung
                self._bindung = platte_bindung
                zu_schreiben = self._vereinen(gelesen.lage, lage)
                self._zuletzt_gesehen = zu_schreiben
        grund = self._schreiben(self._schreibform(zu_schreiben, bindung), beweis=True)
        if grund is None:
            # Beide Gesten sind erst jetzt verbraucht -- ein VERSUCHTER Schreibvorgang
            # verbraucht sie nicht, sonst waere eine Freigabe nach einem Plattenfehler
            # still verloren.
            self._freigabe_vorgemerkt = False
            self._geschlossen.clear()
        return grund

    def _schreibform(self, lage: RisikoLage, bindung: _Bindung) -> dict[str, Any]:
        """Die volle Lage als JSON-Objekt (Feldvertrag: ``test_..._geheimnis.py``)."""
        return {
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
                "tag": None if lage.equity_tag is None else lage.equity_tag.isoformat(),
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

        **Beide Zweige lesen unmittelbar vorher neu und vereinigen** (Modul-Docstring,
        „Zwei Schreiber auf einer Datei"). Was dabei wirklich galt, steht danach in
        ``zuletzt_gesehen`` -- der Aufrufer zieht daraus einen fremden Halt nach.
        """
        self._zuletzt_gesehen = None
        bindung = self._bindung
        if bindung is None or self._waehrung is None:
            return self._ungebunden_sichern(lage)
        return self._gebunden_sichern(lage, bindung)


# --- Der Vertrag, den der RiskManager braucht -- und der Testtyp dazu -------------


class Risikozustand(Protocol):
    """Was ``RiskManager`` von seinem Zustand verlangt.

    Zwei Erfuellungen: :class:`DateiZustand` (der Betrieb, ueberdauert den Neustart)
    und :class:`FluechtigerZustand` (nur fuer Tests; sein Name sagt, was er ist).
    Eine dritte -- „nichts uebergeben, dann fluechtig" -- gibt es seit D8 (E-005)
    nicht mehr: der ``RiskManager`` ist ohne Zustand nicht konstruierbar.
    """

    @property
    def pfad(self) -> Path | None: ...
    @property
    def dauerhaft(self) -> bool: ...
    @property
    def gebunden(self) -> bool: ...
    @property
    def schreibfehler_text(self) -> str: ...
    @property
    def zuletzt_gesehen(self) -> RisikoLage | None: ...
    def laden(self) -> Zustandsbefund: ...
    def binde(self, konto_id: str, waehrung: str) -> str | None: ...
    def sichern(self, lage: RisikoLage) -> str | None: ...
    def freigabe_vormerken(self) -> None: ...
    def schliessung_vormerken(
        self, instrument: str, eroeffnet_am: datetime
    ) -> None: ...


class FluechtigerZustand:
    """Risikozustand NUR im Prozessgedaechtnis -- der ausdrueckliche Testtyp.

    Er heisst so, damit jede Stelle, die ihn baut, es hinschreibt. Der Betrieb weist
    ihn ab (``tools/live_betrieb.py``); ``dauerhaft`` ist ``False``, ``pfad`` ist
    ``None``. Er vereinigt nichts und sichert nichts: ``sichern`` merkt sich die Lage
    nur, damit ein Test den gesicherten Stand nachsehen kann. Ein Halt in diesem
    Zustand endet mit dem Prozess; genau das ist der Fall, den D8 aus dem Betrieb
    entfernt hat.
    """

    def __init__(self) -> None:
        self._konto_id: str | None = None
        self._waehrung: str | None = None
        self.gesichert: RisikoLage | None = None

    @property
    def pfad(self) -> Path | None:
        return None

    @property
    def dauerhaft(self) -> bool:
        return False

    @property
    def gebunden(self) -> bool:
        return self._konto_id is not None

    @property
    def schreibfehler_text(self) -> str:
        return ""

    @property
    def zuletzt_gesehen(self) -> RisikoLage | None:
        # Kein zweiter Schreiber: es gibt nichts nachzuziehen.
        return None

    def laden(self) -> Zustandsbefund:
        return Zustandsbefund(lage=RisikoLage(), herkunft="fluechtig")

    def binde(self, konto_id: str, waehrung: str) -> str | None:
        """Dieselbe Regel wie ``DateiZustand.binde``: ein Kontowechsel im Lauf
        faellt auf. Der erste Aufrufer bindet; ein zweiter mit anderem Konto wird
        abgewiesen."""
        if self._konto_id is None:
            self._konto_id = konto_id
            self._waehrung = waehrung
            return None
        if self._waehrung != waehrung:
            return "zustand_fremde_waehrung"
        if self._konto_id != konto_id:
            return "zustand_fremdes_konto"
        return None

    def sichern(self, lage: RisikoLage) -> str | None:
        self.gesichert = lage
        return None

    def freigabe_vormerken(self) -> None:
        return None

    def schliessung_vormerken(self, instrument: str, eroeffnet_am: datetime) -> None:
        return None

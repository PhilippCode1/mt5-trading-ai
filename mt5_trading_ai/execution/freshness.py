"""Frische-Latch fuer den Kontozustand — S2 aus Paket 0.

WARUM DIESE SPERRE ZUERST LAEUFT
--------------------------------
Jede der uebrigen Sperren am Order-Pfad rechnet mit **Zahlen aus dem Kontozustand**:
der Tagesverlustdeckel mit der Equity, der Drawdown-Halt mit dem Fensterhoechststand,
die Positionsgroesse mit dem Eigenkapital, und selbst die Frage, ob ueberhaupt die
Live-Freigabe noetig ist, mit ``is_demo``. Ist der Kontozustand veraltet, sind alle
diese Zahlen falsch — und zwar **still** falsch: sie sehen aus wie Messwerte. Eine
Sperre, die auf einem veralteten Schnappschuss rechnet, meldet Gruen, ohne etwas
geprueft zu haben.

Darum gilt hier die Regel des Kerns: *nicht bewertbar = nicht erfuellt*. Ein
``AccountSnapshot``, dessen Alter die Frist reisst, ist kein „wahrscheinlich noch
gueltiger" Zustand, sondern ein **unbekannter** Zustand. Die Order wird abgelehnt.

DIE FRIST -- UND WOFUER SIE BEGRUENDET IST
-----------------------------------------
``MAX_SNAPSHOT_AGE = 5 Sekunden``.

**Achtung, die Begruendung ist umgezogen.** Sie lautete frueher: der Kontozustand
wird unmittelbar vor der Pruefung abgefragt, die Latenz einer lokalen
Terminalabfrage liegt im Millisekundenbereich, fuenf Sekunden sind drei
Groessenordnungen darueber. Das war richtig fuer den Kontozustand -- nur wird der
hier gar nicht mehr gemessen (siehe den Abschnitt darunter): gemessen wird ein
**ereignisgetriebener Kursstempel**, und fuer den ist ein Alter von sechs Sekunden
kein haengendes Terminal, sondern ein Instrument, das gerade nicht gehandelt wird.
Eine mituebernommene Zahl mit einer nicht mituebernehmbaren Begruendung ist genau
die Sorte Erbstueck, die spaeter niemand mehr verteidigen kann. Also die Begruendung
fuer DIESE Verwendung:

1. Die Frist beantwortet nicht "ist der Kurs alt", sondern "darf auf diesem Kurs
   **eine Order** entstehen". Das ist eine schaerfere Frage. Eine Marktorder wird
   gegen den zuletzt gesehenen Preis gerechnet -- Stopabstand, Positionsgroesse,
   Kostentor, Hebelklammer haengen alle daran. Fuenf Sekunden sind bei einem
   Instrument, das ueberhaupt handelt, bereits eine lange Zeit.
2. Die Fehlrichtung ist die harmlose: ein Symbol, dessen Strom langsamer taktet als
   die Frist, wird **nicht gehandelt**. Es entsteht kein falscher Preis, kein
   falsches Volumen, keine Position -- es entsteht nichts.
3. Die Zahl steht bewusst **einmal** im Haus und beantwortet damit zwei Fragen:
   "darf hier eine Order entstehen" (``Mt5Venue._enforce_account_freshness``) und
   "druckt der Platz gerade Preise" (``Mt5Venue.is_trading_open``). Das ist kein
   Versehen, sondern die Absicht: beide Tore fragen dasselbe, mit derselben Uhr, und
   ein Symbol, das am zweiten haengenbleibt, wuerde am ersten ohnehin abgelehnt. Zwei
   Zahlen fuer dieselbe Frage waeren die Kopie, die auseinanderlaeuft.

**Was das kostet, ausdruecklich benannt:** ein ruhiges Instrument (Asien-Sitzung,
Index-CFD ausserhalb der Kassa-Zeit, Mittagspause) kann laenger als fuenf Sekunden
ohne Tick bleiben und ist fuer dieses System in dieser Zeit nicht handelbar. Nichts
im Repo misst heute den realen Tickabstand je Katalogsymbol; die Zahl ist also nicht
an dieser Verwendung gemessen, sondern nur an ihr begruendet. Wer sie anhebt, hebt
sie fuer beide Fragen zugleich an und macht damit auch die Marktoffen-Aussage
nachsichtiger -- das ist vor einer Aenderung zu entscheiden, nicht danach. Die
belastbare Grundlage waere eine Messung der Tickabstaende je Symbol ueber einen
Betriebstag.

DIE ZUKUNFTSKANTE
-----------------
Ein Zeitstempel **in der Zukunft** ist ebenso wenig bewertbar wie ein zu alter. Er
entsteht durch Uhrensprung oder durch einen Stempel, der nicht von der Uhr stammt,
gegen die geprueft wird. Wuerde nur „zu alt" geprueft, liesse sich die Sperre durch
einen falschen Stempel vollstaendig aushebeln — deshalb hat sie zwei Kanten.
``FUTURE_TOLERANCE = 1 Sekunde`` faengt gewoehnliche Rundungs- und
Aufloesungsunterschiede ab, ohne das Loch zu oeffnen.

**Diese Toleranz spannt zwei unabhaengige Uhren, und das ist zu wissen.** Frueher
entstanden beide Zeiten im eigenen Prozess; eine Sekunde war dafuer reichlich. Jetzt
kommt ``snapshot_ts`` vom Handelsserver und ``now`` vom lokalen Rechner. Damit gilt:

* Eine gewoehnliche Uhrenabweichung von mehr als einer Sekunde zwischen Broker-Server
  und PC sperrt den gesamten Eroeffnungspfad -- dauerhaft und ohne Bezug zur
  Datenfrische. Ein laufender Zeitabgleich auf beiden Seiten ist damit
  Betriebsvoraussetzung, keine Empfehlung.
* Schaltet der Server seine Sommerzeit nach einem anderen Termin als die
  konfigurierte Zone (der bekannte MT5-Fall: US-Termin am Server,
  ``ZoneInfo("Europe/Helsinki")`` nach EU-Termin), liegt der Stempel im Fruehjahr und
  im Herbst je rund drei Wochen eine volle Stunde daneben. Der Eroeffnungspfad steht
  dann still.

Beides ist fail-closed und damit die sichere Richtung -- aber es ist eine
Betriebsbremse, die wie ein geschlossener Markt aussieht. Wer sie sucht, findet sie
am Ablehnungsgrund: ``snapshot_from_future`` bzw. ``snapshot_stale`` bei einem
Alter nahe einer runden Stunde ist keine Marktaussage, sondern ein Uhrenbefund. Der
Beleg fuer die Serverzone in ``backtest/kalender.py`` ist an Tageskerzen-Grenzen
gemessen (Minutenaufloesung) und traegt fuer eine Sekunden-Kante ausdruecklich
nicht.

WELCHER STEMPEL HIER HINEINGEHOERT -- UND WELCHER NIE
-----------------------------------------------------
Diese Funktion vergleicht zwei Zeiten. Wenn beide aus derselben Uhr stammen, ist das
Ergebnis per Konstruktion null und die Sperre kann nicht ausloesen. Das ist kein
theoretischer Fall: es ist im Repo dreimal passiert, zuletzt am Order-Pfad selbst.

* ``RealMt5Terminal.account()`` setzt ``ts=datetime.now(UTC)`` **in genau diesem
  Aufruf**. MetaTrader liefert ueberhaupt keinen Kontozeitstempel; es gibt nichts,
  woraus dieses Feld sonst entstehen koennte. Wer es als ``snapshot_ts`` uebergibt und
  ``datetime.now(UTC)`` als ``now``, misst eine Uhr gegen sich selbst: Alter ein paar
  Mikrosekunden, Frist fuenf Sekunden, Urteil dauerhaft gruen. In 21 Journalen der
  Betriebslaeufe steht kein einziges ``snapshot_stale``.
* Zulaessig ist allein ein Stempel **von der anderen Seite der Leitung**: der
  Kursstempel des Brokers (``Mt5Tick.ts``, ``Quote.ts``). Er ist das einzige
  Lebenszeichen im System, das nicht im eigenen Prozess entsteht, und damit das
  einzige, an dem sich ein haengendes Terminal zeigen kann.

Alle vier Aufrufer messen darum den Kursstempel:
``Mt5Venue._enforce_account_freshness`` (sperrt die Order),
``Mt5Venue._markt_druckt_preise`` (beantwortet, ob der Platz gerade handelt),
``tools/live_konsole.py`` und ``tools/oberflaeche.py`` (zeigen es an).

``now`` **muss** die Uhr des messenden Bauteils sein, unmittelbar an der Messung
gelesen. Das ist keine Feinheit: ein Aufrufer, der seine Gegenwart am Kopf eines
Taktes einfriert und Sekunden spaeter hier einreicht, macht aus einem frisch
geholten Stempel rechnerisch einen Stempel aus der Zukunft -- und die Sperre steht
still, ohne dass das mit den Daten etwas zu tun haette. Genau so ist der
Eintrittspfad des Live-Betriebs einmal abgeschaltet worden.

**Eingehalten wird das an den beiden sperrenden Stellen, an den beiden anzeigenden
nicht.** Der Unterschied ist zu kennen, und er ist kein Versehen dieser Datei:

* ``Mt5Venue._enforce_account_freshness`` und ``Mt5Venue._markt_druckt_preise`` lesen
  ``self._clock()`` in derselben Anweisung, in der sie messen. Dort haengt eine Order
  daran, und dort ist die Regel eingehalten.
* ``tools/live_konsole.py`` (``jetzt`` am Kopf des Taktes) und
  ``tools/oberflaeche.py`` (``stand["jetzt"]`` als erste Anweisung der Sammlung)
  frieren ihre Gegenwart **vor** der Sammlung ein und reichen sie danach hier ein.
  Zwischen Einfrieren und Messung liegen bei der Oberflaeche der Journallauf, ein
  Kontoabruf, die Positionsliste und ein ``get_quote`` je Katalogsymbol; der
  juengste Stempel wird also NACH dem Einfrieren geholt. Ueberschreitet die Sammlung
  ``FUTURE_TOLERANCE``, meldet die Kachel ``snapshot_from_future`` -- ein Uhrenbefund
  in der Aufmachung eines Datenbefunds.

Die Fehlrichtung ist dort sichtbar (eine rote Kachel, kein stilles Gruen) und
kostet keine Order, weshalb sie hier benannt und nicht behoben wird -- beide Dateien
gehoeren nicht zu dieser Sperre. In einer Zeile nachzupruefen: steht die Zuweisung
von ``jetzt`` vor der Sammlung oder neben dem Aufruf? Wer sie an die Messung
heranschiebt, streicht diesen Absatz mit.

Ein Nebeneffekt gehoert dazu: ohne bekannte Serverzone tragen die Kursstempel die
Wanduhr des Brokers unter dem Etikett UTC, und der Vergleich gegen echte UTC hat den
vollen Versatz drin. Die Sperre steht dann dauerhaft rot -- als
``snapshot_from_future`` bei einem Server vor UTC, als ``snapshot_stale`` bei einem
dahinter. Das ist die richtige Antwort: wer den Versatz nicht kennt, kann das Alter
nicht messen.

WAS DIESE SPERRE NICHT LEISTET
------------------------------
Sie prueft das **Alter** eines Stempels, nicht die **Richtigkeit** der Zahlen daneben.
Ein Terminal, das einen frischen Kurs liefert und dazu einen veralteten Kontostand,
faellt hier nicht auf. Dagegen hilft die Verbindungspruefung, die der Aufrufer
zusaetzlich fahren muss (``connected``-Parameter): eine getrennte Sitzung liefert
keine gueltige Kontolage, egal wie frisch der Stempel aussieht. Am MT5-Adapter fuellt
``RealMt5Terminal.is_connected()`` diesen Parameter und prueft dafuer Prozess,
Serververbindung und Kontositzung.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

FRESHNESS_POLICY_VERSION = "account-freshness-v1"

#: Hoechstalter eines Kontozustands, das noch als bewertbar gilt.
MAX_SNAPSHOT_AGE = timedelta(seconds=5)

#: Toleranz fuer einen Zeitstempel in der Zukunft (Uhrenaufloesung).
FUTURE_TOLERANCE = timedelta(seconds=1)


@dataclass(frozen=True)
class FreshnessVerdict:
    """Ergebnis der Frischepruefung.

    ``evaluable`` ist nur wahr, wenn der Zustand **sicher** bewertbar ist. ``age`` ist
    positiv bei einem alten, negativ bei einem zukuenftigen Stempel.
    """

    evaluable: bool
    reason: str | None
    age: timedelta
    max_age: timedelta
    policy_version: str = FRESHNESS_POLICY_VERSION


def evaluate_account_freshness(
    *,
    snapshot_ts: datetime,
    now: datetime,
    connected: bool,
    max_age: timedelta = MAX_SNAPSHOT_AGE,
    future_tolerance: timedelta = FUTURE_TOLERANCE,
) -> FreshnessVerdict:
    """Ist der Kontozustand bewertbar?

    Vier Ablehnungsgruende, alle fail-closed:

    * ``session_not_connected`` — die Sitzung steht nicht; kein Zustand ist gueltig.
    * ``snapshot_naive`` — ein Zeitstempel ohne Zeitzone ist nicht vergleichbar.
      Ihn als UTC zu deuten waere geraten, nicht gemessen.
    * ``snapshot_from_future`` — der Stempel liegt jenseits der Toleranz in der
      Zukunft.
    * ``snapshot_stale`` — der Stempel ist aelter als ``max_age``.

    ``max_age`` muss positiv sein; ein nicht positiver Wert wuerde die Sperre
    stillschweigend in ein Dauer-Rot oder ein Dauer-Gruen verwandeln, je nach
    Vorzeichen — deshalb ein ``ValueError`` statt eines Urteils.
    """
    if max_age <= timedelta(0):
        raise ValueError("max_age muss positiv sein")
    if future_tolerance < timedelta(0):
        raise ValueError("future_tolerance darf nicht negativ sein")

    if snapshot_ts.tzinfo is None or now.tzinfo is None:
        return FreshnessVerdict(
            evaluable=False,
            reason="snapshot_naive",
            age=timedelta(0),
            max_age=max_age,
        )

    age = now - snapshot_ts

    if not connected:
        return FreshnessVerdict(
            evaluable=False,
            reason="session_not_connected",
            age=age,
            max_age=max_age,
        )
    if age < -future_tolerance:
        return FreshnessVerdict(
            evaluable=False,
            reason="snapshot_from_future",
            age=age,
            max_age=max_age,
        )
    if age > max_age:
        return FreshnessVerdict(
            evaluable=False,
            reason="snapshot_stale",
            age=age,
            max_age=max_age,
        )
    return FreshnessVerdict(
        evaluable=True, reason=None, age=age, max_age=max_age
    )

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

DIE FRIST — UND WARUM SIE SO KURZ IST
-------------------------------------
``MAX_SNAPSHOT_AGE = 5 Sekunden``.

Der Kontozustand wird im Order-Pfad **unmittelbar vor** der Pruefung abgefragt; die
normale Latenz einer lokalen Terminalabfrage liegt im Millisekundenbereich. Fuenf
Sekunden sind damit rund drei Groessenordnungen ueber dem Normalfall — die Frist
kann im gesunden Betrieb nicht zufaellig reissen. Reisst sie doch, ist genau einer
von zwei Faellen eingetreten, und beide sind Ablehnungsgruende:

1. Der Aufrufer hat einen **zwischengespeicherten** Schnappschuss weitergereicht,
   statt frisch abzufragen.
2. Das Terminal **haengt** — die Antwort kam, aber sie ist alt.

Eine laengere Frist (etwa eine Minute) wuerde beide Faelle durchlassen, ohne dafuer
etwas zu gewinnen: es gibt keinen Betriebsfall, in dem ein fuenf Sekunden alter
Kontostand richtig und ein frischer nicht zu bekommen waere.

DIE ZUKUNFTSKANTE
-----------------
Ein Zeitstempel **in der Zukunft** ist ebenso wenig bewertbar wie ein zu alter. Er
entsteht durch Uhrensprung oder durch einen Stempel, der nicht von der Uhr stammt,
gegen die geprueft wird. Wuerde nur „zu alt" geprueft, liesse sich die Sperre durch
einen falschen Stempel vollstaendig aushebeln — deshalb hat sie zwei Kanten.
``FUTURE_TOLERANCE = 1 Sekunde`` faengt gewoehnliche Rundungs- und
Aufloesungsunterschiede ab, ohne das Loch zu oeffnen.

WAS DIESE SPERRE NICHT LEISTET
------------------------------
Sie prueft das **Alter** des Schnappschusses, nicht seine **Richtigkeit**. Ein
Terminal, das einen frischen Zeitstempel auf einen veralteten Kontostand setzt (die
lokale Uhr statt der Brokerzeit — genau das tut ``RealMt5Terminal.account``), faellt
hier nicht auf. Dagegen hilft nur die Verbindungspruefung, die der Aufrufer
zusaetzlich fahren muss (``connected``-Parameter): eine getrennte Sitzung liefert
keine gueltige Kontolage, egal wie frisch der Stempel aussieht.
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

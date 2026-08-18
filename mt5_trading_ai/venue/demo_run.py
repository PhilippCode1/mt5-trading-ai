"""Paket 5: Registrierung und Fortschritts-Tor des Demo-Betriebs (§8.5).

Bevor irgendeine Live-Frage gestellt wird, laeuft die vorregistrierte Strategie
**mindestens sechs Monate** im Demo-Betrieb -- und nur, wenn sie den Edge-Test bestanden
hat. Dieses Modul haelt die Registrierung fest und prueft den Fortschritt; es
handelt nicht und oeffnet keine Order. Der eigentliche Lauf gegen ein Demo-MT5 ist Sache
des Betreibers (``venue/smoke.py``, ``allow_write`` nur auf einem Demokonto). Echtgeld
bleibt hart gesperrt.

Fail-closed: eine Strategie ohne bestandenen Edge-Test kommt nicht in den Demo-Betrieb.

DIE LAUFZEIT WIRD GERECHNET -- DAS ANFANGSDATUM WIRD GEGLAUBT
-------------------------------------------------------------
Bis hierher nahm ``evaluate_demo_progress`` einen freien ``elapsed_days: int`` und
glaubte ihn; die uebergebene ``DemoRegistration`` wurde im ganzen Funktionskoerper kein
einziges Mal gelesen. Das war kein Melder, sondern ein Echo des Aufrufers: ein
``elapsed_days=400`` reifte jedes Konto in einer Zeile, ohne dass irgendwo Zeit
vergangen waere.

Jetzt gilt: die verstrichene Zeit ist die Differenz zwischen einer **uebergebenen Uhr**
und ``DemoRegistration.registered_on``. Die Uhr ist injizierbar (wie beim Frische-Latch,
``execution/freshness.py``), weil ein Melder, der an ``datetime.now()`` haengt, nicht
pruefbar ist -- und ein ungeprueftes Tor ist kein Tor.

Eine Uhr **ohne Zeitzone** gilt als nicht bewertbar: naiv kann Ortszeit, Serverzeit oder
UTC heissen, und der Unterschied ist bis zu einem Tag. Nicht bewertbar heisst nicht
erfuellt (Regel des Kerns).

DIE GRENZE DIESER STUFE, PRAEZISE -- KEINE DICHTIGKEIT BEHAUPTEN
----------------------------------------------------------------
:func:`register_for_demo` liest ``registered_on`` aus der Uhr und nimmt es ausdruecklich
**nicht** als Argument entgegen. Daraus folgt aber nicht, dass jeder Beleg so entstanden
ist: ``DemoRegistration`` ist ein oeffentlicher, offener frozen-dataclass mit
``registered_on`` als gewoehnlichem Feld, und weder diese Datei noch ``Mt5Venue``
verlangen irgendwo, dass ein Beleg durch :func:`register_for_demo` gegangen ist. Zwei
Konstruktorzeilen mit einem Datum von vor 400 Tagen ergeben einen Beleg, den jede
Pruefung hier fuer reif haelt. Der freie ``elapsed_days`` ist damit nicht verschwunden;
er ist von einer Zahl auf ein Datum umgezogen. Wer diese Stelle liest, soll das wissen
und nicht auf eine Zusage stossen, die der Typ nicht traegt.

Was hier **belegt** wird: das im Beleg genannte Anfangsdatum liegt mindestens
``MIN_DEMO_DAYS`` vor der Uhr des pruefenden Bauteils; der Beleg ist vollstaendig; er
nennt ein Demokonto; und -- nur in :func:`evaluate_demo_progress` -- er nennt genau das
Konto, das der Aufrufer gerade liest. Was hier **nicht** belegt wird: dass an diesem
Datum wirklich etwas begonnen hat.

Warum das an dieser Stelle nicht zu schliessen ist, und nicht aus Bequemlichkeit offen
bleibt:

* Ein Beleg muss 180 Tage ueberdauern, also mindestens einen Prozessneustart und damit
  einen Speicher. Ein **Siegel** (Signatur/HMAC ueber Datum und Konto) braucht einen
  Schluessel, der dieselben 180 Tage ueberdauert und ausserhalb dieses Speichers liegt;
  wer ihn haelt, signiert genauso ein rueckdatiertes Datum. Ein Siegel verschiebt das
  Vertrauen, es erzeugt keines -- und ein Siegel, dessen Schluessel neben dem Beleg
  liegt, ist nur eine laengere Behauptung.
* Belegen koennte die Laufzeit allein ein **Zeuge von der anderen Seite der Leitung**:
  die Auftrags-/Geschaeftshistorie des Demokontos beim Broker. Das ist dasselbe Prinzip,
  aus dem der Frische-Latch nur Brokerstempel gelten laesst (``execution/freshness.py``:
  "das einzige Lebenszeichen im System, das nicht im eigenen Prozess entsteht"). Er ist
  hier strukturell nicht erreichbar: :class:`Mt5Terminal` fuehrt keine Historienabfrage,
  und das Reifetor am Order-Pfad sitzt auf der **Live**-Sitzung, in der das Demokonto
  ueberhaupt nicht sichtbar ist. Es fehlt also nicht ein Aufruf, sondern eine Naht.

Festgenagelt -- damit diese Grenze nicht stillschweigend zur Dichtigkeit wird -- in
``tests/test_demo_beleg_grenze.py``. Der Tag, an dem ein Zeuge da ist, ist der Tag, an
dem diese Datei rot wird.

Ein Rest laesst sich ohne Zeugen pruefen und wird geprueft: dass ``registered_on``
ueberhaupt ein reines Kalenderdatum ist. Ein ``datetime`` in diesem Feld (der Typ
erlaubt es, ``datetime`` ist eine Unterklasse von ``date``) liess die Zeitrechnung
frueher mit einem nackten ``TypeError`` mitten im Order-Pfad zerbrechen statt mit einer
Ablehnung. Nicht bewertbar heisst auch hier: nicht erfuellt.

DAS ZEUGNIS GEHOERT ZU EINEM KONTO
----------------------------------
Eine Laufzeit belegt nichts, solange nicht feststeht, **wo** sie gelaufen ist. Darum
traegt ``DemoRegistration`` das Konto (:class:`DemoAccount`), und
``evaluate_demo_progress`` haelt es gegen das **gerade beobachtete** Konto: ein
Reifezeugnis eines anderen Kontos, eines anderen Brokers oder eines Nicht-Demokontos
zaehlt nicht. Leere Identitaeten gelten dabei ausdruecklich als *fehlend*, nicht als
*gleich* -- sonst waere der Vergleich zweier leerer Strings eine Uebereinstimmung und
die Sperre koennte per Konstruktion nie ausloesen.

ZWEI EINSTIEGE, WEIL ES ZWEI BEOBACHTUNGSLAGEN GIBT
---------------------------------------------------
:func:`evaluate_demo_progress` ist die volle Pruefung **mit** Sicht auf das Demokonto:
sie haelt den Beleg gegen das gerade gelesene Konto. Diese Lage hat die Demo-Harness
(``venue/smoke.py``), die auf dem Demoterminal laeuft: dort ist ``get_account()``
wirklich das Demokonto.

:func:`pruefe_demo_beleg` ist derselbe Rechner **ohne** diese Sicht -- Laufzeit aus der
Uhr, Vollstaendigkeit des Belegs, Edge. Diese Lage hat das Reifetor am Order-Pfad
(``Mt5Venue._require_live_release_for_opening``): es laeuft ausschliesslich auf einem
**Live**-Konto (auf einem Demokonto kehrt die Methode vorher um). Ein Demokonto ist
dort per Konstruktion nicht zu sehen. Wer ``evaluate_demo_progress`` an diese Stelle
verdrahtet, bekommt bei JEDER Eingabe ``beobachtetes_konto_ist_kein_demokonto`` --
eine Sperre, die immer ausloest, sagt so wenig wie eine, die nie ausloest, und wird im
Betrieb ausgebaut statt bedient. Die Regel steht trotzdem nur einmal im Haus: beide
Einstiege rechnen denselben Kern (``_beleg_gruende``), ``evaluate_demo_progress`` legt
den Kontoabgleich oben drauf. Ein Test haelt die Teilung zusammen -- jeder Grund des
schmalen Rechners muss auch im vollen erscheinen (``tests/test_demo_beleg.py``).

Was das Reifetor **nicht** aus dem Beleg lesen kann, holt es sich am Ort: dass der
Beleg nicht die Nummer des Livekontos traegt, prueft ``Mt5Venue`` gegen den frisch
gelesenen Kontostand (``venue/mt5.py``, ``_require_demo_maturity``).

**Was hier ausdruecklich nicht behauptet wird:** dass irgendein Werkzeug diesen Weg im
Betrieb schon faehrt. ``tools/mt5_smoke.py`` ruft ``run_smoke`` ohne ``demo=``, und
kein Werkzeug baut ein ``Mt5Venue`` mit einer ``demo_registration``. Solange das so
ist, lehnt das Reifetor jede Live-Eroeffnung mit ``demo_registrierung_fehlt`` ab --
fail-closed und richtig, aber eben kein gefuehrter Nachweis.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

from mt5_trading_ai.backtest.edge import EdgeVerdict

#: "mindestens sechs Monate" Demo, bevor eine Live-Frage ueberhaupt gestellt wird.
MIN_DEMO_DAYS = 180


class DemoGateError(ValueError):
    """Fail-closed: der Demo-Betrieb wurde verweigert."""


@dataclass(frozen=True)
class DemoAccount:
    """Identitaet des Kontos, auf dem der Demo-Betrieb laeuft.

    Warum ein eigener Typ: ohne Kontobindung ist eine Demo-Laufzeit eine herrenlose
    Zahl. Sie liesse sich von einem beliebigen anderen Konto -- auch von einem, das
    laengst gelaufen ist -- auf die Strategie uebertragen, die gerade live gehen will.

    ``account_id`` und ``is_demo`` haben am Tor eine unabhaengige Quelle: beide stehen
    im ``AccountState``, den der Venue frisch vom Terminal liest. ``broker`` hat sie
    derzeit **nicht** -- ``AccountState`` fuehrt kein Broker-/Server-Feld, der Wert
    kommt aus der Terminal-Konfiguration. Der Vergleich ist deshalb der schwaechste der
    drei und faengt Fehlkonfiguration, nicht Taeuschung; er bleibt trotzdem drin, weil
    dieselbe Kontonummer bei zwei Brokern existieren kann.
    """

    account_id: str
    broker: str
    is_demo: bool


@dataclass(frozen=True)
class DemoRegistration:
    """Der Beleg: welche Strategie lief ab wann auf welchem Konto im Demo-Betrieb.

    **Ein offener Datentyp, und das ist eine Grenze, keine Zusage.** Wer ihn ueber
    :func:`register_for_demo` erzeugt, bekommt ein ``registered_on`` aus der Uhr. Wer
    ihn selbst baut -- was moeglich ist, noetig ist (Rekonstruktion aus einem Speicher
    nach Wochen) und nirgends verhindert wird --, setzt das Datum frei. Die Pruefungen
    unten rechnen gegen dieses Datum; sie belegen es nicht. Warum es an dieser Stelle
    nicht zu belegen ist, steht im Modul-Docstring unter "DIE GRENZE DIESER STUFE".
    """

    strategy_id: str
    version: str
    #: Tag der Registrierung. Aus der Uhr, **wenn** der Beleg aus
    #: :func:`register_for_demo` stammt -- der Typ erzwingt das nicht.
    registered_on: date
    account: DemoAccount


def register_for_demo(
    *,
    strategy_id: str,
    version: str,
    edge_verdict: EdgeVerdict,
    account: DemoAccount,
    clock: Callable[[], datetime],
) -> DemoRegistration:
    """Registriere eine Strategie fuer den Demo-Betrieb -- nur bei bestandenem Test.

    Das ist die Naht, die §8.5 an §7 bindet: ohne alle sechs Bedingungen bestanden gibt
    es keinen Demo-Betrieb, keine Vorstufe zu einer Live-Frage. Fail-closed.

    ``registered_on`` ist bewusst **kein** Parameter. Das Registrierungsdatum ist der
    Zeitpunkt der Registrierung, nicht eine Behauptung darueber; als Argument waere es
    der freie ``elapsed_days`` in neuer Verkleidung. Die Uhr wird uebergeben, damit die
    Naht pruefbar bleibt, aber der Aufrufer setzt das Datum nicht.

    Das gilt fuer **diesen Weg** und nur fuer ihn: ``DemoRegistration`` laesst sich auch
    direkt bauen, und dann ist das Datum wieder frei. Diese Funktion ist der saubere
    Eingang, kein Zwang -- siehe Modul-Docstring, "DIE GRENZE DIESER STUFE".

    Registriert wird nur auf einem **Demokonto**: ein Demo-Betrieb, der auf einem
    Echtgeldkonto beginnt, ist ein Widerspruch in sich, und ein Widerspruch ist ein
    Nein.
    """
    if not strategy_id.strip() or not version.strip():
        raise DemoGateError("strategy_id und version sind Pflicht")
    if not account.account_id.strip() or not account.broker.strip():
        raise DemoGateError(
            "Kontonummer und Broker sind Pflicht -- ein Demo-Beleg ohne Konto "
            "belegt nichts"
        )
    if not account.is_demo:
        raise DemoGateError(
            f"Konto {account.account_id} ({account.broker}) ist nicht als Demo "
            "gekennzeichnet -- kein Demo-Betrieb"
        )
    if not edge_verdict.passed:
        raise DemoGateError(
            "Strategie hat den Edge-Test nicht bestanden -- kein Demo-Betrieb "
            f"(offen: {', '.join(edge_verdict.unmet) or 'unbekannt'})"
        )
    jetzt = clock()
    if jetzt.tzinfo is None or jetzt.utcoffset() is None:
        raise DemoGateError(
            "Uhr ohne Zeitzone -- das Registrierungsdatum waere nicht belegbar"
        )
    return DemoRegistration(
        strategy_id=strategy_id,
        version=version,
        registered_on=jetzt.astimezone(UTC).date(),
        account=account,
    )


@dataclass(frozen=True)
class DemoReadiness:
    ready_for_live_question: bool
    reasons: tuple[str, ...]


def _beleg_gruende(
    *,
    registration: DemoRegistration,
    live_verdict: EdgeVerdict,
    clock: Callable[[], datetime],
) -> list[str]:
    """Alle Gruende, die sich **ohne** Sicht auf das Demokonto feststellen lassen."""
    reasons: list[str] = []

    jetzt = clock()
    beginn = registration.registered_on
    if not isinstance(beginn, date) or isinstance(beginn, datetime):
        # ``datetime`` ist eine Unterklasse von ``date``, der Typ haelt das also nicht
        # ab -- und ``date - datetime`` wirft einen nackten ``TypeError`` mitten im
        # Order-Pfad. Ein Beleg mit einem Zeitpunkt statt einem Tag ist nicht
        # bewertbar, und nicht bewertbar heisst nicht erfuellt.
        reasons.append("registrierungsdatum_ist_kein_kalendertag")
    elif jetzt.tzinfo is None or jetzt.utcoffset() is None:
        # Naiv ist nicht vergleichbar (siehe Modul-Docstring): nicht bewertbar =
        # nicht erfuellt. Die Zeitrechnung entfaellt dann komplett.
        reasons.append("uhr_ohne_zeitzone")
    else:
        gelaufen = (jetzt.astimezone(UTC).date() - beginn).days
        if gelaufen < 0:
            # Registrierung in der Zukunft: entweder eine gesprungene Uhr oder ein
            # gesetztes Datum. Beides macht die Laufzeit unbrauchbar -- und ohne
            # diese Kante liesse sich mit einem Datum von morgen jede Pruefung
            # verwirren, die nur "zu kurz" kennt.
            reasons.append(f"registrierung_in_der_zukunft_{-gelaufen}_tage")
        elif gelaufen < MIN_DEMO_DAYS:
            reasons.append(f"demo_zu_kurz_{gelaufen}_von_{MIN_DEMO_DAYS}_tagen")

    # Ein Beleg ohne Strategie belegt nichts: er passt auf jede. ``register_for_demo``
    # laesst das nicht zu -- aber ein aus einem Speicher rekonstruierter Beleg kommt
    # nicht durch dieses Tor, und die Felder wurden bis hierher ueberhaupt nicht
    # gelesen. (Was das NICHT prueft: ob der Beleg zu der Strategie gehoert, die
    # gerade handeln will. Dafuer muesste die fragende Stelle ihre Strategie nennen;
    # der Order-Pfad fuehrt derzeit keine Strategiekennung.)
    if not registration.strategy_id.strip():
        reasons.append("strategie_id_fehlt")
    if not registration.version.strip():
        reasons.append("strategie_version_fehlt")

    registriert = registration.account
    if not registriert.account_id.strip():
        reasons.append("kontonummer_fehlt_im_beleg")
    if not registriert.broker.strip():
        reasons.append("broker_fehlt_im_beleg")
    if not registriert.is_demo:
        # ``register_for_demo`` laesst das nicht zu; ``DemoRegistration`` ist aber ein
        # offener Datentyp und kann auch aus einem Speicher rekonstruiert werden.
        reasons.append("registrierung_nicht_auf_demokonto")

    if not live_verdict.passed:
        reasons.append("live_demo_verfehlt_sechs_bedingungen")
    return reasons


def pruefe_demo_beleg(
    *,
    registration: DemoRegistration,
    live_verdict: EdgeVerdict,
    clock: Callable[[], datetime],
) -> DemoReadiness:
    """Das Reifeurteil aus dem Beleg allein -- fuer Aufrufer ohne Sicht aufs Demokonto.

    Gerechnet wird: die Laufzeit (uebergebene Uhr minus ``registered_on``) und die
    Vollstaendigkeit des Belegs (Strategie, Konto, Demo-Eigenschaft). ``live_verdict``
    wird **gelesen, nicht gemessen** -- es ist ein ``EdgeVerdict``, das der Aufrufer
    mitbringt; ob im Demo wirklich weiter gemessen wurde, kann diese Datei nicht
    feststellen (``EdgeVerdict(passed=True, checks=(), unmet=())`` ist eine Zeile). Der
    Melder greift, wenn der Aufrufer ein **nicht** bestandenes Urteil mitbringt; er
    unterscheidet ein bestandenes Urteil nicht von einem behaupteten. Dieselbe Grenze
    wie beim Datum, siehe Modul-Docstring.

    Was hier **nicht** geprueft werden kann, ist der Abgleich mit dem gerade
    beobachteten Konto -- wer diese Sicht hat, nimmt :func:`evaluate_demo_progress`.

    Der Aufrufer ist das Reifetor am Order-Pfad (``venue/mt5.py``). Es bekommt die
    **Registrierung**, nicht das fertige Urteil. Das ist eine echte Verschaerfung: ein
    ``DemoReadiness(True, ())`` traegt nicht mehr, und ein Datum muss die Frist gegen
    die Uhr des Tores ueberstehen. Es ist aber kein Beweis -- ein frei gesetztes Datum
    uebersteht sie ebenso. Fail-closed: fehlt die Registrierung, fragt das Tor hier gar
    nicht erst.
    """
    reasons = _beleg_gruende(
        registration=registration, live_verdict=live_verdict, clock=clock
    )
    return DemoReadiness(ready_for_live_question=not reasons, reasons=tuple(reasons))


def evaluate_demo_progress(
    *,
    registration: DemoRegistration,
    observed_account: DemoAccount,
    live_verdict: EdgeVerdict,
    clock: Callable[[], datetime],
) -> DemoReadiness:
    """Darf nach dem Demo-Betrieb ueberhaupt eine Live-Frage gestellt werden?

    Nur wenn der Demo-Betrieb **auf diesem Konto** mindestens sechs Monate lief und die
    sechs Bedingungen im Demo weiter erfuellt sind. Fail-closed in jeder Einzelheit:
    fehlt eine Identitaet, widerspricht sie der Registrierung, laesst sich die Zeit
    nicht messen oder ist der Edge weg, lautet die Antwort nein. (Auch ein Ja ist nur
    die Erlaubnis, die Frage zu stellen -- die Live-Freigabe bleibt das vierteilige Tor,
    unberuehrt.)

    ``observed_account`` ist das Konto, das der Aufrufer gerade **am Demoterminal**
    liest (``venue/smoke.py``: ``Mt5Venue.get_account()``), nicht das der
    Registrierung. Genau die Differenz der beiden ist der Melder: wer eine fremde
    Reife vorzeigt, faellt hier auf. Am Live-Tor gibt es diese Sicht nicht (siehe
    Modul-Docstring) -- dort laeuft :func:`pruefe_demo_beleg`.

    Alle Gruende werden gesammelt, nicht beim ersten abgebrochen -- der Betreiber soll
    die vollstaendige Liste sehen und nicht nach jedem Fix erneut anlaufen.
    """
    reasons = _beleg_gruende(
        registration=registration, live_verdict=live_verdict, clock=clock
    )

    registriert = registration.account
    # Leer ist "fehlt", nicht "gleich": zwei leere Kontonummern duerfen nicht als
    # dasselbe Konto durchgehen, sonst kann der Vergleich darunter nie ausloesen.
    # (Die leere Seite DES BELEGS meldet schon ``_beleg_gruende``; hier faellt die
    # leere Seite der Beobachtung, und damit ist der Vergleich in keiner Richtung
    # per Konstruktion erfuellt.)
    if not observed_account.account_id.strip():
        reasons.append("kontonummer_fehlt")
    elif registriert.account_id.strip() != observed_account.account_id.strip():
        reasons.append("kontonummer_weicht_von_registrierung_ab")

    if not observed_account.broker.strip():
        reasons.append("broker_fehlt")
    elif registriert.broker.strip() != observed_account.broker.strip():
        reasons.append("broker_weicht_von_registrierung_ab")

    if not observed_account.is_demo:
        reasons.append("beobachtetes_konto_ist_kein_demokonto")

    return DemoReadiness(ready_for_live_question=not reasons, reasons=tuple(reasons))

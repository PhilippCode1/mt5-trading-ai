"""Kaltstart: den Kreis aufbrechen, ohne die Sperren aufzuweichen.

DER KREIS
---------
Stufe 7 des Auftrags benennt ihn wörtlich::

    Der Kreis „ohne Modell keine Entscheidung, ohne Entscheidung keine Daten, ohne
    Daten kein Modell" wird aufgebrochen: protokollierter Erkundungspfad im
    Papierkonto mit mitgeschriebenen Ablehnungsgruenden, Gewichtung nach
    Auswahlwahrscheinlichkeit im Training, Herkunftsspalte in den Auswertungen.
    Schwellen, die exakt auf dem Maximum der Ersatzheuristik liegen, davon entkoppeln.

Gemessen an den echten Betriebsjournalen dieses Standes
(``AUFTRAG/stufen/07-kaltstart/belege/``): von **4.343** Eroeffnungsversuchen wurden
**32** eroeffnet und **4.311** abgelehnt. Das sind **0,74 %**, die ueberhaupt zu Daten
wurden. Ueber die anderen 99,26 % weiss das System bis heute nichts -- nicht, weil sie
schlecht waren, sondern weil sie nie gefahren wurden.

Das ist der Kreis, und er schliesst sich von selbst: Wer nur Daten ueber die eigenen
Zusagen sammelt, kann seine Absagen nie ueberpruefen. Ein Tor, das zu streng ist,
sieht dabei genauso aus wie eines, das richtig liegt.

WAS DIESES MODUL TUT -- UND WAS AUSDRUECKLICH NICHT
---------------------------------------------------
Es entscheidet, ob ein **abgelehntes** Signal auf dem **Papierkonto** trotzdem gefahren
wird, damit sein Ausgang beobachtbar wird. Dabei gilt:

* **Nur Papier.** :func:`erkundung_erlaubt` verlangt ein Papier-/Demokonto und gibt auf
  allem anderen ``False`` zurueck. Erkundung mit echtem Geld waere keine Erkundung,
  sondern das Uebergehen einer Sperre.
* **Nie gegen eine Sicherheitssperre.** Nur Ablehnungen aus
  :data:`ERKUNDBARE_GRUENDE` sind erkundbar -- Auswahlgruende wie „nicht zugelassen"
  oder „Tageskappe". Ein Global-Halt, ein fehlender Stop, ein ungeklaerter
  Sendeversuch, ein unbewertbarer Kontostand: **niemals**. Die Liste ist eine
  Positivliste, kein Filter; ein unbekannter Grund gilt als nicht erkundbar.
* **Kein Zufall ohne Protokoll.** Die Entscheidung faellt aus einem **gesaeten**
  Generator, und die :class:`Erkundungsentscheidung` traegt die
  **Auswahlwahrscheinlichkeit** mit. Ohne sie waere die spaetere Gewichtung geraten.

DIE GEWICHTUNG -- UND WARUM SIE NOETIG IST
------------------------------------------
Erkundete Beobachtungen entstehen mit Wahrscheinlichkeit ``p`` und regulaere mit 1.
Zaehlt man beide gleich, ueberschaetzt man den Anteil des Erkundeten am Ergebnis um den
Faktor ``1/p``: bei ``p = 0,05`` traegt jede erkundete Zeile das Zwanzigfache ihres
Rechts.

Umgekehrt gewichtet (``1/p``, inverse Auswahlwahrscheinlichkeit) schaetzt der
Mittelwert wieder das, was ohne Auswahl herausgekommen waere. Die Rechnung ist
Standard (Horvitz-Thompson); neu ist hier nur, dass ``p`` ueberhaupt mitgeschrieben
wird -- ohne das Feld gibt es nichts zu gewichten.

**Die Grenze, ausdruecklich:** Die Gewichtung heilt die Auswahl, nicht die
Beobachtungszahl. Zwanzig erkundete Zeilen bei ``p = 0,05`` stehen fuer vierhundert
Gelegenheiten -- sie sind aber weiterhin zwanzig Beobachtungen, und
``gates/herausforderer.py`` zaehlt sie auch so.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

#: Voreinstellung der Erkundungsrate. Bewusst klein: Erkundung kostet Beobachtungen,
#: die sonst der regulaeren Strecke zugutekommen, und sie erzeugt Trades, die das
#: System selbst fuer schlecht haelt. 5 % heisst: neunzehn von zwanzig Absagen bleiben
#: Absagen.
ERKUNDUNGSRATE = 0.05


class Herkunft(str, Enum):
    """Woher eine Auswertungszeile stammt. **Die Herkunftsspalte der Stufe 7.**

    Ohne sie sieht eine erkundete Zeile aus wie eine regulaere, und ein Ergebnis,
    das ueberwiegend aus Erkundung stammt, sieht aus wie eines aus dem Regelbetrieb.
    """

    #: Das Signal wurde regulaer zugelassen und gefahren.
    GEFAHREN = "gefahren"
    #: Das Signal war abgelehnt und wurde zur Erkundung dennoch gefahren (nur Papier).
    ERKUNDET = "erkundet"
    #: Abgelehnt und nicht gefahren -- der Ausgang bleibt unbekannt.
    ABGELEHNT = "abgelehnt"


#: **Positivliste** der Ablehnungsgruende, die erkundet werden duerfen.
#:
#: Alle vier sind Auswahlentscheidungen: das System haelt das Signal fuer nicht
#: lohnend oder hat sein Kontingent ausgeschoepft. Keine davon schuetzt vor einem
#: Verlust, den man nicht wieder einholen kann.
#:
#: Was bewusst **nicht** drinsteht und warum: ``global_halt``, ``missing_stop_loss``,
#: ``schwebender_auftrag``, ``account_unevaluable``, ``risk_drawdown_halt``,
#: ``cost_gate``, ``insufficient_margin``, ``leverage_*``. Das sind Sicherheitssperren.
#: Eine Sperre zur Erkundung zu uebergehen hiesse, genau das aufzuweichen, was die
#: Stufen 4 und 5 dichtgemacht haben -- und es waere ein Verstoss gegen die
#: Grundregel, dass keine Sperre fuer einen Erkenntnisgewinn faellt.
ERKUNDBARE_GRUENDE: frozenset[str] = frozenset(
    {
        "strategy_not_admitted",
        "throttle_cooldown_active",
        "throttle_instrument_daily_cap",
        "risk_concurrent_position_cap",
    }
)


@dataclass(frozen=True)
class Erkundungsentscheidung:
    """Ob erkundet wird -- und mit welcher Wahrscheinlichkeit das entschieden wurde.

    ``wahrscheinlichkeit`` ist die Zahl, mit der spaeter gewichtet wird. Sie steht
    auch dann drin, wenn **nicht** erkundet wurde: eine nicht erkundete Absage ist
    eine Beobachtung ueber die Auswahl, und wer sie spaeter zaehlen will, braucht ihr
    ``p`` genauso.
    """

    erkunden: bool
    wahrscheinlichkeit: float
    grund: str
    #: Warum nicht erkundet wurde, wenn ``erkunden`` falsch ist. Leer sonst.
    verweigert_weil: str = ""


def erkundung_erlaubt(*, ist_papierkonto: bool, ablehnungsgrund: str) -> str:
    """``""`` heisst erlaubt; sonst der Grund, warum nicht. Fail-closed.

    Getrennt von der Wuerfelentscheidung, damit die **Zulaessigkeit** ohne jeden
    Zufall pruefbar ist: ein Fall, der einmal in zwanzig Laeufen anschlaegt, ist kein
    Eichfall.
    """
    if not ist_papierkonto:
        return "kein_papierkonto"
    if ablehnungsgrund not in ERKUNDBARE_GRUENDE:
        return f"grund_nicht_erkundbar:{ablehnungsgrund}"
    return ""


def entscheide_erkundung(
    *,
    ist_papierkonto: bool,
    ablehnungsgrund: str,
    schluessel: str,
    rate: float = ERKUNDUNGSRATE,
) -> Erkundungsentscheidung:
    """Wuerfle -- gesaet, reproduzierbar, mit protokollierter Wahrscheinlichkeit.

    ``schluessel`` ist die Kennung dieser Gelegenheit (Symbol + Zeitstempel + Signal).
    Aus ihr entsteht die Zufallszahl per Hash. Das ist Absicht und kein Ersatz fuer
    einen Generator: derselbe Schluessel ergibt in jedem Lauf dieselbe Entscheidung.
    Ein Zustandsgenerator haette hier zwei Nachteile -- er haengt an der Reihenfolge
    der Aufrufe (ein uebersprungener Takt verschiebt alles danach), und er ist nach
    einem Neustart nicht wiederherstellbar. Beides macht eine Auswertung
    unreproduzierbar, und eine unreproduzierbare Auswertung belegt nichts.
    """
    if not 0.0 < rate < 1.0:
        raise ValueError(f"Erkundungsrate muss zwischen 0 und 1 liegen, ist {rate}")
    hindernis = erkundung_erlaubt(
        ist_papierkonto=ist_papierkonto, ablehnungsgrund=ablehnungsgrund
    )
    if hindernis:
        # Wahrscheinlichkeit 0: diese Gelegenheit konnte nie erkundet werden. Das ist
        # etwas anderes als „gewuerfelt und verloren" und muss unterscheidbar bleiben.
        return Erkundungsentscheidung(False, 0.0, ablehnungsgrund, hindernis)

    roh = hashlib.sha256(schluessel.encode("utf-8")).digest()[:8]
    wurf = int.from_bytes(roh, "big") / float(1 << 64)
    return Erkundungsentscheidung(wurf < rate, rate, ablehnungsgrund)


@dataclass(frozen=True)
class Auswertungszeile:
    """Eine Zeile der Auswertung -- **mit** Herkunft und Auswahlwahrscheinlichkeit."""

    ts: str
    instrument: str
    signal: str
    herkunft: Herkunft
    #: Ergebnis in **Basispunkten des Einstiegspreises**. Die Einheit steht im Namen,
    #: weil dieses Repo an genau dieser Verwechslung schon einmal Zeit verloren hat
    #: (drei verschieden skalierte Sharpe-Felder, ``tests/test_sharpe_einheit.py``).
    #: ``None`` bei :attr:`Herkunft.ABGELEHNT` -- dort gibt es keines, und das ist der
    #: ganze Punkt der Stufe.
    ergebnis_bp: float | None
    ablehnungsgrund: str = ""
    wahrscheinlichkeit: float = 1.0

    @property
    def gewicht(self) -> float:
        """Inverse Auswahlwahrscheinlichkeit. Regulaere Zeilen wiegen 1."""
        if self.herkunft is not Herkunft.ERKUNDET:
            return 1.0
        if not 0.0 < self.wahrscheinlichkeit <= 1.0:
            raise ValueError(
                f"Eine erkundete Zeile ohne brauchbare Auswahlwahrscheinlichkeit "
                f"({self.wahrscheinlichkeit}) laesst sich nicht gewichten."
            )
        return 1.0 / self.wahrscheinlichkeit


def erkundungsanteil(zeilen: Sequence[Auswertungszeile]) -> float:
    """Anteil erkundender Beobachtungen an denen, die ein Ergebnis haben.

    **Bezugsgroesse ist bewusst nicht die Gesamtzahl der Zeilen.** Abgelehnte Zeilen
    haben kein Ergebnis; sie in den Nenner zu nehmen liesse den Anteil beliebig klein
    aussehen, indem man mehr Absagen protokolliert. Gezaehlt wird gegen das, woraus
    ein Modell ueberhaupt lernen kann.
    """
    mit_ergebnis = [z for z in zeilen if z.ergebnis_bp is not None]
    if not mit_ergebnis:
        return 0.0
    erkundet = sum(1 for z in mit_ergebnis if z.herkunft is Herkunft.ERKUNDET)
    return erkundet / len(mit_ergebnis)


def gewichteter_mittelwert(zeilen: Sequence[Auswertungszeile]) -> float | None:
    """Mittleres Ergebnis, nach inverser Auswahlwahrscheinlichkeit gewichtet.

    ``None``, wenn keine Zeile ein Ergebnis traegt -- kein Ersatzwert. Ein Mittelwert
    aus nichts ist keine Null, sondern eine fehlende Zahl (V3).
    """
    mit_ergebnis = [z for z in zeilen if z.ergebnis_bp is not None]
    if not mit_ergebnis:
        return None
    gewichte = [z.gewicht for z in mit_ergebnis]
    summe = sum(
        g * float(z.ergebnis_bp or 0.0)
        for z, g in zip(mit_ergebnis, gewichte, strict=True)
    )
    return summe / sum(gewichte)

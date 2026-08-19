"""Risikoschicht am Order-Pfad: die vier Grenzen als letzte Verteidigungslinie.

Vier bisher **verwaiste** Module (getestet, am Live-Pfad nie aufgerufen) werden hier zu
**einem** Aufrufer im Order-Pfad zusammengefuehrt und in der vorgeschriebenen, nicht
verhandelbaren Reihenfolge gefahren:

1. ``risk/limits.py`` (``evaluate_limits``) -- Kill-Switch: Tagesverlust, Drawdown-Halt,
   Positionsdeckel, Gap-Sperre. Der Drawdown-Halt latcht am Venue (``_halted``) und
   loest sich nicht von selbst.
2. ``gates/evaluation.py`` (``select_one``) -- Drossel: Cooldown je Instrument,
   Mindesthaltedauer, Trades je Instrument/Konto und Tag, gleichzeitige Positionen.
   „Bewerten ist nicht Handeln": eine zu schnelle Wiederholung wird abgewiesen.
3. ``risk/stop_budget.py`` (``stop_budget``) + ``risk/sizing.py``
   (``executable_stop_floor``) -- Stop-Floor gegen Budget je Anlageklasse/Hebel. Floor
   ueber Budget -> ``no_trade`` (kein weiter gesetzter Stop -- das waere ein anderer
   Trade).
4. ``risk/sizing.py`` (``size_position``) -- Positionsgroesse aus Risikoanteil und
   Stopabstand. Das **angeforderte** Volumen darf das Budget-Volumen nicht reissen.

Der ``RiskManager`` haelt den dafuer noetigen Zustand, den die Venue nicht traegt:
Equity-Verlauf (Tagesstart, rollierender Fenster-Hoechststand fuer den Drawdown),
Handelsfrequenz (letzter Trade je Instrument, Trades je Tag) und die offenen Positionen
mit Eroeffnungszeit. Die Venue meldet akzeptierte Eroeffnungen (``record_open_fill``)
und Schliessungen (``record_close``) zurueck; der Betreiber beobachtet Equity
(``observe_equity``, von der Venue je Order automatisch aufgerufen).

**Kostenbasis der dritten Grenze.** Die Budget-Untergrenze ist eine Kostenrechnung; sie
taugt nur so viel wie die Kostenzahl, die hineingeht. Diese Schicht sucht sie in dieser
Reihenfolge: das Argument ``measured_cost_bps`` (die Messung DIESER Order, die der
Runner im selben Lauf am Live-Bid/Ask genommen hat) ->
``request.meta[MEASURED_COST_BPS_META_KEY]`` (dieselbe Messung, mitgereist am Auftrag,
damit die zweite Pruefung im Venue dieselbe Zahl sieht und nicht eine mildere) ->
``RiskPolicy.measured_cost_bps`` je Klasse (eine Messkampagne) -> Annahmetabelle. Der
letzte Schritt ist der einzige ungedeckte; die Herkunft steht deshalb als erstes Wort
in ``detail["cost_basis"]`` jeder Autorisierung (``gemessen``/``auftrag``/``kampagne``/
``annahme``), und ``require_measured_cost`` macht den Rueckfall auf Wunsch zur Sperre
(Begruendung: ``risk/stop_budget.py``).

**Die mitgereiste Zahl darf nur anheben.** Der ``meta``-Kanal ueberquert eine Grenze:
er kommt als *Auftragsdatum* herein, nicht als Messung dieser Schicht. Naehme sie ihn
ungeprueft, koennte ein Aufrufer die Kostenpraemisse des Systems von aussen setzen --
und ausgerechnet ``venue/mt5.py::_enforce_risk``, die zweite Pruefung, die einen Fehler
der ersten abfangen soll, rechnete dann mit einer Zahl aus der Schicht, die sie
absichert. Sie waere nie strenger als diese. Gemessen an der neuen Fassung reichte
``meta={"measured_cost_bps": Decimal("0.001")}``, um die Untergrenze trotz einer
Politik mit 5,0 bp auf 0,01 bp zu druecken -- mit dem Etikett "gemessen".

Darum wird die mitgereiste Zahl gegen die **Praemisse** dieser Schicht gehalten
(Messkampagne der Politik, sonst die Annahmetabelle der Klasse) und kann die Rechnung
nur in **eine** Richtung bewegen: darueber zaehlt sie und verschaerft die Untergrenze
-- genau der Zweck des Kanals --, darunter bleibt die Praemisse stehen. Nicht still:
die verworfene Zahl steht mit ihrem Grund in ``detail["cost_basis"]``.

Warum hier geklammert und nicht geworfen wird -- der Unterschied zum Typfehler in
``measured_cost_from_meta``: eine zu **niedrige** Zahl ist nicht zwingend ein Defekt.
Sie entsteht auch dann, wenn ein Markt ehrlich billiger ist als die (schmeichelnde)
Annahme -- Gold ist mit 1,5 bp angenommen, 1,0 bp sind messbar. Diese Schicht kann
"ehrlich gemessen" von "erfunden" nicht unterscheiden, weil sie nur die Zahl sieht;
sie rechnet deshalb mit ihrer eigenen Praemisse weiter und laesst die vorhandenen Tore
urteilen (zu enger Stop -> ``stop_budget_below_cost_floor``, ein typisierter,
begruendeter Abbruch). Ein Wurf machte aus einem Marktzustand einen Absturz mitten im
Live-Takt, der ``VenueError`` faengt und ``ValueError`` nicht.

Wer eine echt guenstigere Kostenlage handeln will, hinterlegt sie als Messkampagne in
``RiskPolicy.measured_cost_bps`` -- eine Entscheidung des Betreibers, nicht eines
Auftrags. Politik steht ueber Auftragsdaten, nicht darunter. Der Preis dieser
Unabhaengigkeit ist benannt und gewollt: eine in-Prozess gemessene Lage UNTER der
Praemisse traegt die erste Pruefung (Argument), nicht aber die zweite im Venue, die nur
das Auftragsdatum sieht -- die Order faellt dort fail-closed durch, statt auf einer
Zahl zu eroeffnen, die niemand nachpruefen kann.

**Eine Budgetrechnung, nicht zwei.** ``stop_budget_for`` ist die einzige Stelle, an der
diese Politik in ``risk/stop_budget.py`` geht; ``execution/runner.py`` ruft dieselbe
Methode, statt ``stop_budget`` mit den Vorgabewerten der Signatur zu fahren. Sonst
rechnet der Runner die Untergrenze mit ``max_cost_drag=0.05``, waehrend eine Politik mit
``0.02`` unmittelbar danach das Doppelte verlangt -- der Runner setzt den Stop auf die
eigene Zahl und diese Schicht lehnt ihn mit ``stop_budget_below_cost_floor`` ab. Zwei
Fassungen derselben Rechnung, und die strengere Politik erzeugt nicht den weiteren
Stop, sondern gar keinen Handel.

**Der Zustand ueberdauert den Neustart -- sonst gibt es keinen Halt.** Bis hierher lag
der gesamte Risikozustand im Prozessgedaechtnis: Equity-Fenster, Tagesstart-Equity,
Tageszaehler, Halt. ``_window_peak`` begann mit der *aktuellen* Equity, der Drawdown war
nach jedem Start also null -- das ``drawdown_window`` von 30 Tagen war in Wahrheit „seit
Prozessstart". Gemessen an den Betriebsjournalen: 22 Eroeffnungen an einem Konto-Tag
gegen eine Kappe von 10, weil jeder Neustart bei null anfing. ``risk/limits.py`` sagt
es selbst: „Ein System, das sich nach einem Drawdown-Halt selbst wieder freischaltet,
hat keinen Halt."

Zwei Aenderungen tragen das:

1. **Der Halt latcht auch hier**, nicht nur im Venue (``Mt5Venue._halted``). Meldet
   ``evaluate_limits`` einmal ``HALTED``, bleibt diese Schicht angehalten, bis ein
   Mensch freigibt -- auch wenn sich die Equity danach erholt. Das ist keine
   Zugabe, sondern Bedingung fuer Punkt 2: schriebe man den Halt auf die Platte und
   lese ihn beim Start als Ablehnung, im laufenden Prozess aber nicht, dann waere ein
   Neustart **strenger** als kein Neustart. Nebenwirkung ist gewollt: die Sperre loest
   oefter aus.
2. **Der Zustand wird gesichert** (``execution/risiko_zustand.py``), sobald eine
   Zustandsdatei da ist -- ``zustand=`` am Konstruktor oder die Umgebungsvariable
   ``MT5_RISIKO_ZUSTAND``. Ohne beides bleibt diese Schicht fluechtig wie bisher;
   ``zustand_dauerhaft`` sagt, welcher Fall vorliegt. Was ein fehlender, leerer oder
   beschaedigter Zustand bedeutet -- und warum der Halt dabei anders behandelt wird als
   der Tageszaehler --, steht im Docstring von ``execution/risiko_zustand.py``.

**Die Umgebungsvariable genuegt -- auch fuer den Peak.** Sie muss es, denn alle
Produktionsstellen bauen ``RiskManager()`` ohne Argumente (``tools/live_betrieb.py``,
``tools/paper_run.py``, ``tools/live_konsole.py``, ``tools/mt5_smoke.py``). Eine
Zusage, die auf dem einzigen wirklich benutzten Weg nicht greift, ist keine. Der Weg
dorthin ist nicht der Konstruktor, sondern die Schreibseite: das Equity-Fenster wird
**auch ohne geprueftes Konto** gesichert, alles Uebrige erst danach (Begruendung und
Fehlrichtung in ``execution/risiko_zustand.py``, „Was ohne geprueftes Konto geschrieben
wird"). Sonst faellt genau der Teil aus, der vor der ersten Order entsteht: der
Scheduler beobachtet Equity je Takt (``execution/scheduler.py``), autorisiert wird
seltener -- und ein Neustart vor der ersten Order verloere den Fenster-Hoechststand,
also den Drawdown, also den Halt. ``konto_id``/``waehrung`` am Konstruktor sind damit
nur noch eine Abkuerzung fuer den vollen Zustand ab Takt eins, keine Bedingung.

Fail-closed: jede nicht sicher zulaessige Order wird abgelehnt, ohne Default. Die
**Politik** (Grenzen, Schwellen, Risikoanteil) traegt der ``RiskPolicy``; die Venue
erzwingt sie am Order-Pfad (siehe ``venue/mt5.py``).
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from mt5_trading_ai.execution.risiko_zustand import (
    UMGEBUNG_ZUSTANDSDATEI,
    UMGEBUNG_ZUSTANDSORDNER,
    DateiZustand,
    RisikoLage,
    Zustandsbefund,
    fenster_fortschreiben,
    fenster_vereinen,
    standard_zustandsdatei,
)
from mt5_trading_ai.gates.evaluation import (
    Candidate,
    GateState,
    OpenPosition,
    ThrottlePolicy,
    select_one,
)
from mt5_trading_ai.risk.limits import (
    AccountSnapshot,
    LimitDecision,
    LossLimits,
    TradingState,
    evaluate_limits,
)
from mt5_trading_ai.risk.sizing import (
    DEFAULT_RISK_FRACTION,
    SizingResult,
    StopFloorInputs,
    executable_stop_floor,
    size_position,
)
from mt5_trading_ai.risk.stop_budget import (
    StopBudget,
    assumed_cost_bps,
    stop_budget,
)
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Instrument,
    OrderRequest,
)

#: Schluessel, unter dem eine eroeffnende Order ihre **gemessene** Roundturn-Kostenlage
#: (in bp) mitfuehrt. Der Runner legt sie hinein, diese Schicht liest sie -- damit die
#: zweite, unabhaengige Pruefung in ``venue/mt5.py::submit_order`` dieselbe Messung
#: sieht wie die erste. Ohne diesen Kanal rechnete die Venue-Pruefung gegen die
#: Annahmetabelle und waere milder als die Pruefung, die sie absichern soll.
MEASURED_COST_BPS_META_KEY = "measured_cost_bps"


@dataclass(frozen=True)
class RiskPolicy:
    """Politik der Risikoschicht -- die Grenzen, gegen die jede Eroeffnung prueft.

    ``loss_limits`` und ``throttle`` sind die vorregistrierten Konfigurationen der
    Einzelmodule; ``risk_fraction`` ist der Risikoanteil je Trade (geklammert in
    ``size_position``); ``max_cost_drag``/``safety`` steuern die Budgetspanne;
    ``measured_cost_bps`` erlaubt gemessene Round-Turn-Kosten je Klasse (schlagen die
    Annahmen im Stop-Budget). Der Eintrag ist zugleich die **Praemisse**, gegen die eine
    am Auftrag mitgereiste Zahl gehalten wird: darueber zaehlt sie, darunter wirft sie.

    ``require_measured_cost`` macht eine fehlende Messung zur Sperre statt zum Griff in
    die Annahmetabelle. Die Vorgabe ist ``False``, und das ist kein Versehen: es gibt
    heute noch eroeffnende Aufrufer ohne Messung (von Hand gebaute ``OrderRequest`` am
    Venue, die Schreibprobe in ``venue/smoke.py``), die eine Umstellung ersatzlos
    sperren wuerde. Bis die nachgezogen sind, gilt sichtbar statt still: die Basis
    steht als ``cost_basis`` in jeder Autorisierung. Der Schalter gehoert **hierher**
    und nicht an eine Aufrufstelle: der Pfad, der heute wirklich eroeffnet
    (``execution/runner.py``), uebergibt seine Messung unbedingt -- dort waere der
    Schalter eine Tautologie und keine Sperre.
    """

    loss_limits: LossLimits = field(default_factory=LossLimits)
    throttle: ThrottlePolicy = field(default_factory=ThrottlePolicy)
    risk_fraction: Decimal = DEFAULT_RISK_FRACTION
    max_cost_drag: Decimal = Decimal("0.05")
    safety: Decimal = Decimal("3")
    measured_cost_bps: dict[str, Decimal] = field(default_factory=dict)
    require_measured_cost: bool = False


@dataclass(frozen=True)
class RiskAuthorization:
    """Ergebnis der Risikopruefung. ``approved`` nur bei sicherer Zulaessigkeit.

    ``latch_halt`` ist wahr, wenn ein Drawdown-Halt greift -- die Venue setzt dann ihren
    ``_halted``-Latch (der sich nicht von selbst loest). ``detail`` traegt die
    Zwischenergebnisse fuer den Nachweis (Limit-Zustand, Budgetspanne, Sizing) und --
    sobald ein Budget gerechnet wurde -- unter ``cost_basis``, worauf die
    Budget-Untergrenze beruht: ``<herkunft> <bp>`` mit ``herkunft`` aus ``gemessen``
    (Live-Messung dieses Laufs), ``auftrag`` (am ``meta`` mitgereist, gegen die
    Praemisse geprueft), ``kampagne`` (``RiskPolicy.measured_cost_bps``) oder
    ``annahme`` (Tabelle). Der Eintrag ist nicht schmueckend: er ist die Stelle, an der
    ein Aufrufer sieht, worauf er gerade handelt -- und der Kanal steht dabei, weil
    "gemessen" ohne ihn nur hiesse, dass irgendjemand irgendeine Zahl uebergeben hat.
    """

    approved: bool
    reason: str | None
    latch_halt: bool = False
    sizing: SizingResult | None = None
    budget: StopBudget | None = None
    detail: dict[str, str] = field(default_factory=dict)


#: Unicode-Gattungen, die auf dem Bildschirm nichts hinterlassen: Steuerzeichen (Cc),
#: Formatzeichen (Cf -- darunter U+200B ZERO WIDTH SPACE und U+FEFF), Ersatzzeichen
#: und Privatbereich (Cs/Co), nicht vergebene Stellen (Cn) sowie alle drei
#: Trennerarten (Zs/Zl/Zp).
_UNSICHTBARE_GATTUNGEN: Final = frozenset(
    {"Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp"}
)


def freigabe_gueltig(kennung: str | None) -> bool:
    """Ist das eine Freigabe? Genau **ein** Massstab, an allen drei Stellen derselbe.

    Die Frage entscheidet, ob ein Drawdown-Halt faellt, und sie wurde bisher an drei
    Orten verschieden beantwortet: ``risk/limits.py`` verlangte ``.strip()``, der
    Konstruktor dieser Schicht ebenfalls -- ``release_drawdown`` gar nichts. Damit
    loeschte ``release_drawdown("")`` einen dauerhaften Halt, den dieselbe Kennung am
    Konstruktor nicht geloest haette. Zwei Massstaebe fuer dieselbe menschliche Geste,
    und der laxere sass auf dem Not-Aus.

    Leerzeichen sind keine Entscheidung. Eine Freigabe ist die Aussage eines Menschen
    ueber eine Lage, die er gesehen hat; sie traegt eine Kennung, an der man ihn spaeter
    findet (Ticket, Datum, Kuerzel). Ein Leerstring benennt niemanden -- er ist ein
    durchgereichtes leeres Feld, ein Tippfehler oder eine nicht gesetzte Variable, und
    keins davon darf einen Halt aufheben.

    **Unsichtbar ist dasselbe wie leer.** ``.strip()`` allein genuegt dafuer nicht:
    ``str.isspace()`` ist fuer U+200B (ZERO WIDTH SPACE) und U+FEFF ``False``, sie
    ueberleben also jedes Strippen. ``release_drawdown("\\u200b")`` loeste damit einen
    dauerhaften Halt mit einer Kennung, die in keinem Protokoll und in keinem Ticket
    wiederzufinden ist -- und die niemand beim Lesen bemerkt. Verlangt wird darum
    mindestens **ein sichtbares Zeichen**. Kurze sichtbare Kennungen (``0``, ``-``)
    gehen weiter durch: sie sind schlechte Kennungen, aber sie stehen im Protokoll und
    ein Mensch sieht sie.

    Diese Fassung ist strikt strenger als ``risk/limits.py``. Damit der eine Massstab
    trotzdem gilt, gibt der ``RiskManager`` eine ungueltige Kennung gar nicht erst
    weiter (siehe ``__init__``): was ``evaluate_limits`` erreicht, hat hier bestanden.
    """
    if not kennung:
        return False
    return any(
        unicodedata.category(zeichen) not in _UNSICHTBARE_GATTUNGEN
        for zeichen in kennung
    )


def measured_cost_from_meta(request: OrderRequest) -> Decimal | None:
    """Hole die mitgereiste Kostenmessung aus ``request.meta``. Fail-closed.

    Ein falscher Typ ist ein **Defekt des Aufrufers**, kein fehlender Wert: ein Float
    (oder ein String) an dieser Stelle hiesse, dass jemand die Messung ungenau oder
    ungeprueft weiterreicht. Er wirft, statt auf die Annahmetabelle zurueckzufallen --
    sonst waere ein Tippfehler im Schluessel eine stille Rueckstufung der Sperre.

    Dieselbe Strenge gilt fuer den Wert: eine nicht endliche oder nicht positive Zahl
    ist keine Kostenlage (Roundturn-Kosten sind Spread + Kommission + Slippage und damit
    echt positiv). Sie wirft **hier**, denn nachgelagert wuerde sie verschwinden: die
    Praemisse in ``RiskManager._kostenbasis`` klammert alles ab, was zu niedrig ist, und
    machte aus einer unbrauchbaren Zahl stillschweigend eine Nichtzahl -- ``NaN`` waere
    dort sogar ein ``InvalidOperation`` beim Vergleich. Ein Defekt wirft, er wird nicht
    weggeklammert.

    Geprueft wird hier nur die **Form**. Ob eine formal gueltige Zahl inhaltlich gelten
    darf, entscheidet ``RiskManager._kostenbasis``: dort steht die Praemisse, die sie
    nicht unterbieten darf. Diese Funktion kennt weder Politik noch Anlageklasse.
    """
    roh = request.meta.get(MEASURED_COST_BPS_META_KEY)
    if roh is None:
        return None
    if not isinstance(roh, Decimal):
        raise ValueError(
            f"{MEASURED_COST_BPS_META_KEY} in OrderRequest.meta muss ein Decimal sein, "
            f"ist {type(roh).__name__} ({roh!r})"
        )
    if not roh.is_finite() or roh <= 0:
        raise ValueError(
            f"{MEASURED_COST_BPS_META_KEY} in OrderRequest.meta muss endlich und "
            f"positiv sein, ist {roh}"
        )
    return roh


@dataclass(frozen=True)
class _Kostenbasis:
    """Die aufgeloeste Kostenzahl, ihre Herkunft -- und was dabei verworfen wurde.

    ``herkunft`` ist eines von ``gemessen`` (Live-Messung dieses Laufs, als Argument
    hereingereicht), ``auftrag`` (am ``meta`` mitgereist und ueber der Praemisse),
    ``kampagne`` (``RiskPolicy.measured_cost_bps``) oder ``annahme`` (Tabelle).
    ``verworfen`` ist leer oder nennt eine mitgereiste Zahl, die die Praemisse
    unterboten hat -- damit die Klammerung im Protokoll steht und nicht still bleibt.
    """

    bps: Decimal | None
    herkunft: str
    verworfen: str = ""

    def als_text(self, cost_bps: Decimal) -> str:
        """Die Zeile fuer ``RiskAuthorization.detail["cost_basis"]``."""
        return f"{self.herkunft} {cost_bps} bp{self.verworfen}"


class RiskManager:
    """Traegt den Risiko-Zustand und autorisiert eroeffnende Orders am Order-Pfad."""

    def __init__(
        self,
        policy: RiskPolicy | None = None,
        *,
        manual_release_id: str | None = None,
        gap_events: tuple[datetime, ...] = (),
        zustand: DateiZustand | None = None,
        konto_id: str | None = None,
        waehrung: str | None = None,
    ) -> None:
        """``zustand`` macht den Risikozustand dauerhaft (siehe Modul-Docstring).

        Wird nichts uebergeben, entscheidet die Umgebung: ist
        ``MT5_RISIKO_ZUSTAND`` (oder ``MT5_RISIKO_ZUSTAND_ORDNER``) gesetzt, wird die
        Datei dort gefuehrt, sonst bleibt die Schicht fluechtig. Die Umgebung ist hier
        der richtige Schalter und nicht Bequemlichkeit: die Stellen, die einen
        ``RiskManager`` bauen (``tools/live_betrieb.py``, ``venue/demo_run.py``),
        gehoeren anderen Wellen -- ueber die Umgebung schaltet der Betrieb die
        Dauerhaftigkeit ein, ohne dass eine davon angefasst werden muss. Eine Vorgabe
        „immer dauerhaft am Standardpfad" scheidet aus: dann teilten sich alle Tests
        dieses Repos **eine** Zustandsdatei, und ein Halt aus einem Test haltete den
        naechsten.

        ``konto_id``/``waehrung`` binden den Zustand sofort an ein Konto. Ohne sie
        bindet die erste ``authorize_opening`` (dort kommt die ``AccountState``
        herein); bis dahin wird **nur das Equity-Fenster** gesichert -- der Teil, der
        auch ohne Kontobeweis nicht schmeicheln kann. Wer den vollen Zustand ab dem
        ersten Scheduler-Takt auf der Platte haben will, uebergibt sie hier.

        Wirft ``ZustandsortFehler``, wenn die Umgebung einen relativen Pfad vorgibt --
        beim Bau, also vor der ersten Order (Begruendung in
        ``execution/risiko_zustand.py``).
        """
        self._policy = policy if policy is not None else RiskPolicy()
        #: Manuelle Freigabe nach einem Drawdown-Halt. Ohne sie bleibt der Halt.
        #: Gilt nur fuer die AKTUELLE Episode: erholt sich der Drawdown unter die Grenze
        #: oder vertieft er sich ueber das freigegebene Niveau, wird sie verbraucht.
        #: Eine Kennung, die ``freigabe_gueltig`` nicht besteht, wird hier **verworfen**
        #: statt mitgefuehrt. Sonst reichte diese Schicht sie an ``evaluate_limits``
        #: weiter, das nur ``.strip()`` prueft -- eine unsichtbare Kennung waere dort
        #: eine Freigabe, die hier keine ist, und der laxere Massstab entschiede wieder
        #: ueber den Not-Aus.
        self._manual_release_id = (
            manual_release_id.strip()
            if manual_release_id is not None and freigabe_gueltig(manual_release_id)
            else None
        )
        #: Drawdown-Niveau, gegen das die Freigabe erteilt wurde (lazily beim ersten
        #: Sehen gesetzt); ein tieferer Drawdown macht die Freigabe ungueltig.
        self._release_ceiling: Decimal | None = None
        #: Bekannte Gap-Ereignisse (Wochenende, Rolltermin, Earnings), UTC.
        self._gap_events = gap_events
        #: Equity-Beobachtungen (ts, equity), auf das Drawdown-Fenster beschnitten.
        self._equity_obs: list[tuple[datetime, Decimal]] = []
        self._day_start_equity: Decimal | None = None
        self._equity_day: date | None = None
        #: Handelsfrequenz-Zustand, taeglich zuruecksetzend.
        self._last_trade_at: dict[str, datetime] = {}
        self._trades_today_instrument: dict[str, int] = {}
        self._trades_today_account: int = 0
        self._trade_day: date | None = None
        #: Offene Positionen mit Eroeffnungszeit (Mindesthaltedauer, Positionsdeckel).
        self._open_positions: list[OpenPosition] = []
        #: Halt-Latch DIESER Schicht. Er spiegelt, was sie als ``latch_halt`` gemeldet
        #: hat, und loest sich -- wie der des Venue -- nur durch Freigabe.
        self._halt = False
        self._halt_grund = ""
        self._halt_seit: datetime | None = None
        #: Sperre der Tageszaehler aus einem unlesbaren Zustand. Schwaecher als der
        #: Halt: sie verfaellt mit dem Tageswechsel, ohne menschliches Zutun.
        self._zaehler_gesperrt = False
        #: Grund einer fehlgeschlagenen Kontobindung (``None`` = passt/noch offen).
        self._bindungsgrund: str | None = None
        #: Der Zustand konnte zuletzt nicht auf die Platte (``None`` = konnte).
        #: Begruendung und Wirkung: ``_sichern``.
        self._schreibfehler: str | None = None

        self._zustand = self._zustand_waehlen(zustand)
        if self._zustand is not None:
            self._uebernehme(self._zustand.laden())
            if konto_id is not None and waehrung is not None:
                self._bindungsgrund = self._zustand.binde(konto_id, waehrung)
            self._sichern()

    @staticmethod
    def _zustand_waehlen(zustand: DateiZustand | None) -> DateiZustand | None:
        """Uebergeben -> Umgebung -> fluechtig. Begruendung im ``__init__``."""
        if zustand is not None:
            return zustand
        if os.environ.get(UMGEBUNG_ZUSTANDSDATEI) or os.environ.get(
            UMGEBUNG_ZUSTANDSORDNER
        ):
            return DateiZustand(standard_zustandsdatei())
        return None

    @property
    def zustand_dauerhaft(self) -> bool:
        """Ob der Risikozustand einen Neustart ueberdauert.

        Oeffentlich, weil „fluechtig" keine Eigenschaft ist, die man aus dem Verhalten
        ablesen kann, bevor es zu spaet ist: eine fluechtige Schicht verhaelt sich bis
        zum Neustart genau wie eine dauerhafte. Die Konsole/das Betriebswerkzeug soll
        das anzeigen koennen.
        """
        return self._zustand is not None

    def _uebernehme(self, befund: Zustandsbefund) -> None:
        """Uebernimm den gelesenen Zustand -- samt seiner fail-closed-Aufloesung."""
        lage = befund.lage
        self._halt = lage.halt
        self._halt_grund = lage.halt_grund
        self._halt_seit = lage.halt_seit
        self._zaehler_gesperrt = lage.zaehler_gesperrt
        self._trade_day = lage.handelstag
        self._trades_today_instrument = dict(lage.trades_je_instrument)
        self._trades_today_account = lage.trades_konto
        self._last_trade_at = dict(lage.letzter_trade_at)
        self._equity_day = lage.equity_tag
        self._day_start_equity = lage.tagesstart_equity
        self._equity_obs = list(lage.equity_fenster)
        self._open_positions = [
            OpenPosition(instrument=symbol, opened_at=ts)
            for symbol, ts in lage.offene_positionen
        ]
        if befund.sperrgrund is not None:
            self._halt = True
            self._halt_grund = befund.sperrgrund
        if self._halt and freigabe_gueltig(self._manual_release_id):
            # Eine am Konstruktor mitgegebene Freigabe ist derselbe menschliche Akt wie
            # ``release_drawdown`` -- und der einzige Weg aus einem Halt, dessen Grund
            # ein unlesbarer Zustand war. Ohne ihn bliebe nur „Datei loeschen", also
            # eine Geste, die den Zustand samt Beweis mitnimmt.
            self._halt = False
            self._halt_grund = ""
            self._halt_seit = None
            if self._zustand is not None:
                # Und sie muss beim Schreiben ausdruecklich mitkommen: seit die
                # Zustandsdatei vereinigt statt ueberschrieben wird, gewinnt ein Halt
                # der Platte gegen jeden Speicherstand -- ausser gegen diesen einen,
                # begruendeten Akt (``DateiZustand.freigabe_vormerken``).
                self._zustand.freigabe_vormerken()

    def _lage(self) -> RisikoLage:
        """Der aktuelle Zustand als sicherbare Lage (ohne Freigabe -- siehe Modul)."""
        return RisikoLage(
            halt=self._halt,
            halt_grund=self._halt_grund,
            halt_seit=self._halt_seit,
            handelstag=self._trade_day,
            zaehler_gesperrt=self._zaehler_gesperrt,
            trades_je_instrument=dict(self._trades_today_instrument),
            trades_konto=self._trades_today_account,
            letzter_trade_at=dict(self._last_trade_at),
            equity_tag=self._equity_day,
            tagesstart_equity=self._day_start_equity,
            equity_fenster=list(self._equity_obs),
            offene_positionen=[
                (pos.instrument, pos.opened_at) for pos in self._open_positions
            ],
        )

    def _sichern(self) -> None:
        """Schreibe den Zustand fort -- und lass die Platte nicht in den Order-Pfad.

        Die Frage dahinter: was ist schlimmer -- ein Absturz nach dem Fill, oder ein
        stillschweigend nicht gesicherter Zustand? Der Absturz, deutlich. Und man muss
        sich nicht entscheiden.

        **Absturz nach dem Fill** ist der schlechtestmoegliche Ausgang. ``venue/mt5.py``
        ruft ``record_open_fill`` NACH dem Fill und VOR ``return result``: die Position
        steht beim Broker, und der Aufrufer bekaeme statt des ``OrderResult`` eine
        Ausnahme -- die er nicht erwartet (der Live-Takt faengt ``VenueError``, nicht
        ``OSError``). Er wuesste dann nicht, dass er eine Position hat: kein Stop-
        Management, kein Abgleich, keine Schliessung. Aus einer vollen Platte wuerde
        eine unbeaufsichtigte offene Position. Auf Windows ist das kein Randfall --
        ``os.replace`` scheitert mit ``PermissionError``, sobald ein anderer Prozess
        das Ziel offen haelt.

        **Stillschweigend nicht sichern** ist der zweitschlechteste und darum auch
        keine Loesung: der naechste Start laese einen aelteren Stand -- weniger Trades,
        kleineren Peak, keinen Halt. Das ist genau die milde Richtung, gegen die diese
        Schicht gebaut ist.

        Also der dritte Weg: der Fehler wird gefangen (der Order-Pfad laeuft zu Ende,
        der Aufrufer bekommt sein ``OrderResult``), und der Zustand gilt ab sofort als
        **unsicher**. Die naechste ``authorize_opening`` lehnt mit
        ``risk_zustand_nicht_gesichert`` ab: es wird nichts NEUES eroeffnet, solange
        nicht gesichert werden kann, waehrend das Bestehende bedienbar bleibt. Die
        Marke loescht sich nicht durch Zeitablauf, sondern nur durch einen
        erfolgreichen Schreibvorgang -- also durch einen Beweis. Deshalb braucht sie,
        anders als der Drawdown-Halt, keine menschliche Freigabe: sie behauptet nichts
        ueber den Markt, sondern nur ueber die Platte, und die Platte antwortet selbst.

        **Sie ueberdauert einen Neustart nicht, und das kann sie auch nicht.** Hier
        stand einmal das Gegenteil; es war falsch. ``_schreibfehler`` ist ein
        Instanzfeld und beginnt in jedem neuen Prozess bei ``None`` -- eine Marke, die
        einen Neustart ueberleben soll, muesste ausgerechnet auf die Platte, die
        gerade nicht mitspielt. Der Fall, der daran haengt: Platte voll -> ein Halt
        faellt aus -> Betreiber raeumt auf -> Neustart, und es steht kein Halt mehr da.
        Was DARAN reparierbar war, ist repariert: der Halt wird jetzt VOR dem
        Plattenbefund ausgewertet und gelatcht (``authorize_opening``, 0b1), also
        schon waehrend des Ausfalls im Speicher gehalten und mit dem ersten
        gelungenen Schreibvorgang gesichert. Was bleibt, ist der Prozess, der von
        Anfang bis Ende auf eine unschreibbare Platte trifft: dessen Zustand ist
        unwiederbringlich, und keine Zeile dieser Schicht kann das aendern.

        **Und danach wird nachgezogen.** Seit die Zustandsdatei unmittelbar vor jedem
        Schreibvorgang neu gelesen und vereinigt wird (``execution/risiko_zustand.py``,
        „Zwei Schreiber auf einer Datei"), kennt sie den Stand eines zweiten Prozesses.
        Ihn nur auf der Platte stehen zu lassen waere eine halbe Reparatur: der Halt
        des zweiten Laufs ginge dann zwar nicht mehr verloren, DIESER Lauf aber wuesste
        nichts davon und eroeffnete weiter. ``_nachziehen`` holt ihn deshalb in den
        Speicher -- ausschliesslich in die strenge Richtung.
        """
        if self._zustand is None:
            return
        self._schreibfehler = self._zustand.sichern(self._lage())
        gesehen = self._zustand.zuletzt_gesehen
        if gesehen is not None:
            self._nachziehen(gesehen)

    def _nachziehen(self, lage: RisikoLage) -> None:
        """Uebernimm, was auf der Platte stand -- aber nur, wenn es strenger ist.

        Der Filter ist der ganze Punkt. ``lage`` ist bereits die Vereinigung beider
        Staende und damit je Abschnitt die strengere Seite; hier wird trotzdem noch
        einmal einzeln geprueft, damit ein spaeterer Eingriff an ``lage_vereinen``
        nicht unbemerkt eine milde Richtung hereinreicht. Ein gesetzter Halt wird
        uebernommen, ein fehlender loescht keinen -- fuer den Halt gilt derselbe Satz
        wie auf der Platte: er faellt nur durch ``release_drawdown``.

        Nicht uebernommen wird der **Handelstag** als solcher: ihn setzt
        ``_roll_trade_day`` aus der Uhr des Aufrufers. Ein Tag von der Platte koennte
        aus einer abweichenden Uhr stammen, und ein Tagessprung nach vorn wuerde beim
        naechsten Rollen als „echter Tageswechsel" gelesen -- und loeste damit die
        Zaehlersperre auf, statt sie zu tragen.

        **Das Equity-Fenster war die Luecke in genau diesem Filter.** Hier stand
        einmal ``self._equity_obs = list(lage.equity_fenster)`` -- eine blanke
        Zuweisung als einziges Feld ohne Einzelpruefung. Sie war unauffaellig, solange
        ``lage`` aus dem vereinigten Stand kam (der ist je Korb der Hoechststand und
        damit ohnehin nicht kleiner). Aber ``zuletzt_gesehen`` traegt auch den
        **Defekt-Zweig**: findet ``_gebunden_sichern`` die Datei unlesbar vor und
        traegt diesen Lauf den Halt nicht, dann steht dort die Lage aus
        ``risiko_zustand._defekt`` -- Halt gesetzt, Fenster **leer**. Die Zuweisung
        loeschte damit den Peak dieses Laufs. Gemessen: Peak 12000, Platte geht unter
        dem laufenden Prozess kaputt, naechster Takt -> Fenster ``[]``, Peak 10000;
        nach der vorgesehenen Freigabe (``release_drawdown``) war der Drawdown von
        16,7 % rechnerisch 0 und der Folgetag wieder frei. Ein Not-Aus, den ein
        Plattendefekt plus die vorgesehene Freigabegeste unsichtbar machte.
        ``fenster_vereinen`` nimmt je Korb den Hoechststand: der Peak kann nur steigen,
        der Drawdown nur groesser, der Halt nur wahrscheinlicher werden. Zu lange
        gehaltene Koerbe schneidet der naechste ``fenster_fortschreiben`` weg -- und
        auch dieser Schnitt irrt nach „eher Halt".
        """
        if lage.halt and not self._halt:
            self._halt = True
            self._halt_grund = lage.halt_grund or "zustand_fremder_halt"
            self._halt_seit = lage.halt_seit
        if lage.zaehler_gesperrt:
            self._zaehler_gesperrt = True
        for symbol, anzahl in lage.trades_je_instrument.items():
            if anzahl > self._trades_today_instrument.get(symbol, 0):
                self._trades_today_instrument[symbol] = anzahl
        if lage.trades_konto > self._trades_today_account:
            self._trades_today_account = lage.trades_konto
        for symbol, ts in lage.letzter_trade_at.items():
            vorher = self._last_trade_at.get(symbol)
            if vorher is None or ts > vorher:
                self._last_trade_at[symbol] = ts
        self._equity_obs = fenster_vereinen(self._equity_obs, lage.equity_fenster)
        if (
            lage.equity_tag == self._equity_day
            and lage.tagesstart_equity is not None
            and (
                self._day_start_equity is None
                or lage.tagesstart_equity > self._day_start_equity
            )
        ):
            self._day_start_equity = lage.tagesstart_equity
        bekannt = {pos.instrument for pos in self._open_positions}
        for symbol, ts in lage.offene_positionen:
            if symbol not in bekannt:
                self._open_positions.append(
                    OpenPosition(instrument=symbol, opened_at=ts)
                )

    # --- Zustandspflege ---------------------------------------------------
    def observe_equity(self, now: datetime, equity: Decimal) -> None:
        """Nimm eine Equity-Beobachtung auf (Tagesstart + Fenster-Hoechststand).

        Das Fenster wird in Stundenkoerben mit ihrem Hoechststand gefuehrt
        (``risiko_zustand.fenster_fortschreiben``). Roh angehaengt wuchs die Reihe im
        Sekundentakt auf Hunderttausende Eintraege je 30-Tage-Fenster -- unauffaellig,
        solange der laengste Lauf dieses Repos ein Tag war, und untragbar, sobald der
        Zustand je Beobachtung auf die Platte geht. Der Korb-Hoechststand kann den
        Peak nur halten oder heben, nie senken.
        """
        if self._equity_day != now.date():
            # Neuer Handelstag: Tagesstart-Equity neu setzen (Tageslimit-Bezug).
            self._equity_day = now.date()
            self._day_start_equity = equity
        self._equity_obs = fenster_fortschreiben(
            self._equity_obs, now, equity, self._policy.loss_limits.drawdown_window
        )
        self._sichern()

    def _window_peak(self, current_equity: Decimal) -> Decimal:
        peak = current_equity
        for _ts, eq in self._equity_obs:
            if eq > peak:
                peak = eq
        return peak

    def _roll_trade_day(self, day: date) -> None:
        """Setzt die Frequenz-Tageszaehler bei Tageswechsel zurueck. Wird auf BEIDEN
        Pfaden gerufen (Lesen in ``authorize_opening``, Schreiben in
        ``record_open_fill``), sonst blockt eine an Tag N ausgeschoepfte Kappe an
        Tag N+1 stale weiter."""
        if self._trade_day == day:
            return
        vorheriger_tag = self._trade_day
        self._trade_day = day
        self._trades_today_instrument = {}
        self._trades_today_account = 0
        if vorheriger_tag is not None:
            # Nur ein ECHTER Tageswechsel hebt die Zaehlersperre auf. Die Bedingung
            # ist der ganze Punkt: kommt der Zustand mit unbekanntem Tag herein
            # (``handelstag=None``, weil der Abschnitt unlesbar war), dann setzt der
            # erste Takt nach dem Start hier den Tag -- ohne diese Pruefung loeste
            # genau dieser Takt die Sperre wieder auf, und sie koennte per
            # Konstruktion nie greifen.
            self._zaehler_gesperrt = False
        # Den Tageswechsel sofort sichern. Ohne das bliebe ``handelstag`` in der Datei
        # auf dem Stand, mit dem sie hereinkam -- bei einem unlesbaren Zaehlerabschnitt
        # also auf ``null``. Dann saehe JEDER Neustart wieder „Tag unbekannt", die
        # Bedingung oben griffe nie, und die Zaehlersperre liefe nie ab: aus einer
        # Sperre mit Verfallsdatum waere ein zweiter, heimlicher Dauer-Halt geworden.
        self._sichern()

    def record_open_fill(self, instrument: str, now: datetime) -> None:
        """Akzeptierte Eroeffnung: Frequenz-Zaehler + offene Position fortschreiben."""
        self._roll_trade_day(now.date())
        self._last_trade_at[instrument] = now
        self._trades_today_instrument[instrument] = (
            self._trades_today_instrument.get(instrument, 0) + 1
        )
        self._trades_today_account += 1
        # Netto je Symbol: ein bereits offenes Symbol wird nicht doppelt gezaehlt
        # (spiegelt ``record_close``, das alle Eintraege eines Symbols entfernt).
        if all(pos.instrument != instrument for pos in self._open_positions):
            self._open_positions.append(
                OpenPosition(instrument=instrument, opened_at=now)
            )
        # Sofort sichern, nicht am Ende des Takts: zwischen Fill und Absturz liegt
        # sonst genau der Trade, den die Kappe nach dem Neustart nicht mehr kennt.
        self._sichern()

    def record_close(self, instrument: str) -> None:
        """Eine Schliessung: offene Positionen dieses Instruments entfernen.

        Die Schliessung wird der Zustandsdatei **ausdruecklich angesagt**, und zwar
        mit der Eroeffnungszeit des Eintrags, den dieser Lauf wirklich gefuehrt hat.
        Seit die Datei vereinigt statt ueberschrieben wird, verschwindet nichts mehr
        dadurch, dass es in einem Speicherstand fehlt -- sonst holte der naechste
        Schreibvorgang die geschlossene Position von der Platte zurueck, und der
        Positionsdeckel fuellte sich unumkehrbar.

        **Warum die Zeit mitgeht:** hier ging einmal nur das Symbol hinueber, und
        damit nahm die Geste die Position eines zweiten Laufs mit -- der gemessene
        Ablauf steht bei ``risiko_zustand.lage_vereinen``. Fuehrt dieser Lauf das
        Symbol gar nicht, wird nichts vorgemerkt: dann gehoert ein Eintrag auf der
        Platte jemand anderem, und ihn ungefragt zu loeschen waere die milde Richtung.
        """
        geschlossen = [
            pos.opened_at
            for pos in self._open_positions
            if pos.instrument == instrument
        ]
        self._open_positions = [
            pos for pos in self._open_positions if pos.instrument != instrument
        ]
        if self._zustand is not None:
            for eroeffnet_am in geschlossen:
                self._zustand.schliessung_vormerken(instrument, eroeffnet_am)
        self._sichern()

    @property
    def open_position_count(self) -> int:
        """Offene (netto je Symbol gefuehrte) Positionen -- fuer den Deckel."""
        return len(self._open_positions)

    def release_drawdown(self, release_id: str) -> None:
        """Manuelle Freigabe nach einem Drawdown-Halt (menschliche Entscheidung).

        Gilt nur fuer die aktuelle Halt-Episode -- der Kill-Switch stellt sich nach
        Erholung oder bei einem tieferen Drawdown von selbst wieder scharf.

        Sie loescht dabei den **dauerhaften** Halt-Latch: sonst bliebe der Zustand auf
        der Platte angehalten und der naechste Start haltete wieder, obwohl ein Mensch
        gerade freigegeben hat. Die Freigabe selbst wird ausdruecklich **nicht**
        gesichert (Begruendung in ``execution/risiko_zustand.py``): sie ist eine
        Aussage ueber eine Lage, die dieser Mensch gerade gesehen hat.

        Sie ist zugleich der **einzige** Weg, auf dem ein Halt von der Platte
        verschwindet. Seit dort vereinigt statt ueberschrieben wird, gewinnt ein
        gesetzter Halt gegen jeden Speicherstand; ``freigabe_vormerken`` ist die
        Ausnahme, und sie wird einmalig verbraucht -- von einem gelungenen
        Schreibvorgang, nicht von einem versuchten.

        Eine leere Kennung ist keine Freigabe (``freigabe_gueltig``) und wird
        **abgewiesen, nicht ignoriert**: sie wirft, bevor irgendetwas geaendert ist.
        Der Halt bliebe sonst zwar stehen, aber der Aufrufer glaubte, er habe
        freigegeben -- und ein Not-Aus, den man versehentlich fuer geloest haelt, ist
        so schlecht wie einer, der sich loesen laesst. Der Wurf ist hier gefahrlos:
        diese Methode steht nicht im Order-Pfad, sondern am Ende einer menschlichen
        Geste.
        """
        if not freigabe_gueltig(release_id):
            raise ValueError(
                "release_drawdown verlangt eine nicht leere Freigabekennung "
                f"(uebergeben: {release_id!r}). Sie loescht einen Drawdown-Halt, der "
                "einen Neustart ueberdauert -- an ihr muss spaeter nachvollziehbar "
                "sein, WER auf welche Lage hin freigegeben hat."
            )
        self._manual_release_id = release_id.strip()
        self._release_ceiling = None
        self._halt = False
        self._halt_grund = ""
        self._halt_seit = None
        if self._zustand is not None:
            self._zustand.freigabe_vormerken()
        self._sichern()

    # --- Kostenbasis ------------------------------------------------------
    def stop_budget_for(
        self,
        *,
        asset_class: str,
        leverage: int,
        measured_cost_bps: Decimal | None = None,
    ) -> StopBudget:
        """Die Budgetspanne nach DIESER Politik -- die eine Stelle, die sie rechnet.

        Oeffentlich, weil ``execution/runner.py`` dieselbe Spanne braucht, bevor er
        den Stop-Preis setzt. Riefe er ``stop_budget`` selbst, uebernaehme er die
        Vorgabewerte der Signatur (``max_cost_drag=0.05``, ``safety=3``) statt der
        konfigurierten Politik -- und rechnete damit an einer Politik mit
        ``max_cost_drag=0.02`` vorbei, deren Untergrenze doppelt so hoch liegt. Der
        Runner setzte den Stop auf seine Zahl, diese Schicht lehnte ihn Zeilen
        spaeter mit ``stop_budget_below_cost_floor`` ab: die strengere Politik
        erzeugte keinen weiteren Stop, sondern gar keinen Handel.

        ``measured_cost_bps`` ist die bereits aufgeloeste Kostenzahl (siehe
        ``_kostenbasis``); ``None`` bedeutet "keine Messung" -- dann entscheidet
        ``require_measured_cost`` zwischen Annahmetabelle und Sperre.
        """
        return stop_budget(
            asset_class=asset_class,
            leverage=leverage,
            measured_cost_bps=measured_cost_bps,
            max_cost_drag=self._policy.max_cost_drag,
            safety=self._policy.safety,
            require_measured_cost=self._policy.require_measured_cost,
        )

    def _kostenbasis(
        self,
        *,
        instrument: Instrument,
        request: OrderRequest,
        measured_cost_bps: Decimal | None,
    ) -> _Kostenbasis:
        """Welche Kostenzahl fuer diese Order gilt -- und **woher** sie stammt.

        Rangfolge, Praemisse und Begruendung stehen im Modul-Docstring unter
        "Kostenbasis". ``bps is None`` heisst: keine gemessene Zahl -- ``stop_budget``
        entscheidet dann zwischen Annahmetabelle und Sperre.

        Die mitgereiste Zahl gilt nur, soweit sie die Praemisse nicht unterbietet. Sie
        wird auch dann gegen die Praemisse gehalten, wenn das Argument sie schlaegt:
        sie faehrt am Auftrag weiter zur zweiten Pruefung im Venue, und was dort
        gelten wird, gehoert schon hier in die Akte.
        """
        klasse = instrument.asset_class.value
        kampagne = self._policy.measured_cost_bps.get(klasse)
        praemisse = kampagne if kampagne is not None else assumed_cost_bps(klasse)
        mitgereist = measured_cost_from_meta(request)
        verworfen = ""
        if mitgereist is not None and praemisse is not None and mitgereist < praemisse:
            verworfen = (
                f" (Auftrag {mitgereist} bp verworfen: unter Praemisse {praemisse} bp)"
            )
            mitgereist = None

        if measured_cost_bps is not None:
            return _Kostenbasis(measured_cost_bps, "gemessen", verworfen)
        if mitgereist is not None:
            return _Kostenbasis(mitgereist, "auftrag", verworfen)
        if kampagne is not None:
            return _Kostenbasis(kampagne, "kampagne", verworfen)
        return _Kostenbasis(None, "annahme", verworfen)

    # --- Kontobindung -----------------------------------------------------
    def _konto_abgleich(self, account: AccountState) -> str | None:
        """Gehoert der gespeicherte Zustand zu DIESEM Konto? ``None`` heisst ja.

        Zwei Wege in denselben Fehler, und beide muessen dicht sein:

        * Die **Datei** wurde von einem anderen Konto geschrieben -- erkannt am
          Kontoabdruck bzw. an der Kontowaehrung (``DateiZustand.binde``).
        * Der **Aufrufer** wechselt das Konto mitten im Lauf -- erkannt daran, dass die
          einmal gesetzte Bindung nicht mehr passt.

        Warum das ueberhaupt zaehlt: der Zustand besteht aus **Betraegen**
        (Tagesstart-Equity, Fenster-Peak) und aus **Zaehlungen** gegen die Kappen
        dieses Kontos. Ein 50-000-EUR-Peak, uebernommen von einem 500-USD-Konto, macht
        den Drawdown rechnerisch riesig; andersherum macht er ihn null. Die eine
        Richtung sperrt grundlos, die andere ist die stille Freigabe -- und wir wissen
        nicht, welche vorliegt. Also: keine Uebernahme, sondern Ablehnung.
        """
        if self._zustand is None:
            return None
        if self._bindungsgrund is not None:
            return self._bindungsgrund
        grund = self._zustand.binde(account.account_id, account.currency)
        if grund is not None:
            self._bindungsgrund = grund
        return grund

    # --- Autorisierung ----------------------------------------------------
    def _freigabe_episode_pflegen(self, drawdown: Decimal) -> None:
        """Gilt die Freigabe fuer DIESE Lage noch? Vor der Limit-Auswertung.

        Eine Freigabe deckt genau die Halt-Episode, die der Mensch gesehen hat.
        Erholt sich der Drawdown unter die Grenze, ist die Episode vorbei und der
        Kill-Switch wieder scharf; vertieft er sich ueber das freigegebene Niveau, ist
        es eine andere Lage als die, ueber die entschieden wurde. Beide Zweige
        **verbrauchen** die Freigabe -- die einzigen Wege hier heraus sind strenger,
        nie milder.
        """
        max_dd = self._policy.loss_limits.max_drawdown_fraction
        if self._manual_release_id is None:
            return
        if drawdown < max_dd:
            self._manual_release_id = None
            self._release_ceiling = None
        elif self._release_ceiling is None:
            self._release_ceiling = drawdown
        elif drawdown > self._release_ceiling:
            self._manual_release_id = None
            self._release_ceiling = None

    def _limits_pruefen(
        self, *, account: AccountState, peak: Decimal, now: datetime
    ) -> LimitDecision:
        """Der Kill-Switch mit dem Zustand dieser Schicht -- genau einmal je Order."""
        snapshot = AccountSnapshot(
            now=now,
            equity=account.equity,
            day_start_equity=self._day_start_equity
            if self._day_start_equity is not None
            else account.equity,
            window_peak_equity=peak,
            open_positions=len(self._open_positions),
            trading_day=now.date(),
            manual_release_id=self._manual_release_id,
            upcoming_gap_events=self._gap_events,
        )
        return evaluate_limits(snapshot, self._policy.loss_limits)

    def authorize_opening(
        self,
        *,
        instrument: Instrument,
        request: OrderRequest,
        account: AccountState,
        price: Decimal,
        spread_bps: Decimal,
        leverage: int,
        now: datetime,
        measured_cost_bps: Decimal | None = None,
    ) -> RiskAuthorization:
        """Fahre die vier Grenzen in vorgeschriebener Reihenfolge fuer eine Eroeffnung.

        Reihenfolge: Kill-Switch (Limits) -> Drossel -> Stop-Floor/Budget -> Groesse.
        Der erste Verstoss lehnt fail-closed ab. ``latch_halt=True`` bei einem
        Drawdown-Halt (die Venue setzt dann ihren ``_halted``-Latch).

        ``measured_cost_bps`` sind die am Live-Bid/Ask gemessenen Roundturn-Kosten
        DIESER Order in bp. Wer sie hat, gibt sie her: sie bestimmt die
        Budget-Untergrenze und schlaegt jede Tabelle (Rangfolge im Modul-Docstring).
        Sie steht oben in der Rangfolge, weil sie **in diesem Prozess** entstanden ist
        -- der Aufrufer hat gerade gemessen. Die am Auftrag mitgereiste Zahl ist etwas
        anderes: sie hat eine Grenze ueberquert und wird gegen die Praemisse dieser
        Schicht geprueft (``_kostenbasis``); unterbietet sie sie, wirft die
        Autorisierung, statt milder zu rechnen.
        """
        # 0) Gehoert der gespeicherte Zustand ueberhaupt zu DIESEM Konto? Diese Frage
        # steht vor allem anderen -- auch vor ``observe_equity``: die Equity eines
        # fremden Kontos in dieses Fenster zu schreiben verdirbt Peak und
        # Tagesstart, und zwar in die milde Richtung.
        fremd = self._konto_abgleich(account)
        if fremd is not None:
            return RiskAuthorization(
                approved=False,
                reason=f"risk_{fremd}",
                # Latch: eine Order fuer das falsche Konto ist ein Verdrahtungsfehler,
                # kein Marktzustand. Bewusst NICHT auf die Platte geschrieben -- der
                # Fehlgriff des Aufrufers darf nicht den Zustand des richtigen Kontos
                # vergiften. Die Ablehnung wiederholt sich ohnehin bei jedem Aufruf.
                latch_halt=True,
                detail={"zustandsdatei": str(self._zustand.pfad)}
                if self._zustand is not None
                else {},
            )

        self.observe_equity(now, account.equity)
        # Frequenz-Tageszaehler auch auf dem LESEpfad rollen (nicht nur beim Fill),
        # sonst blockt eine an Tag N ausgeschoepfte Kappe an Tag N+1 stale weiter.
        self._roll_trade_day(now.date())

        # 0b) Der gelatchte Halt -- aus diesem Lauf oder aus dem Zustand des vorigen.
        # Er steht VOR ``evaluate_limits``, weil er gerade den Fall abdeckt, in dem
        # ``evaluate_limits`` nichts mehr faende: erholte Equity nach einem Halt.
        if self._halt:
            return RiskAuthorization(
                approved=False,
                reason=f"risk_{self._halt_grund or 'halt_gelatcht'}",
                latch_halt=True,
                detail={
                    "halt_seit": (
                        self._halt_seit.isoformat()
                        if self._halt_seit is not None
                        else "unbekannt"
                    )
                },
            )

        # 0b1) Die Limit-Auswertung steht ab hier VOR dem Plattenbefund -- genauer:
        # ihr Halt-Anteil. Vorher kam der Schreibfehler zuerst, und damit wurde
        # waehrend eines Plattenausfalls der Drawdown gar nicht erst bewertet: der
        # Lauf lehnte zwar ab, latchte aber nichts. Erholten sich Platte UND Equity,
        # stand kein Halt mehr im Weg und ``approved`` war wieder ``True`` -- ein
        # Not-Aus, den ein Plattenproblem verschluckt hat. Gemessen: 16,7 % Drawdown
        # auf blockierter Platte, danach Erholung -> Order angenommen.
        # Beide Ausgaenge lehnen ab; die Reihenfolge entscheidet nur, WELCHE Aussage
        # gilt, und der Halt ist die schwerere: er braucht einen Menschen.
        peak = self._window_peak(account.equity)
        drawdown = (
            Decimal("1")
            if peak <= 0
            else max(Decimal("0"), peak - account.equity) / peak
        )
        self._freigabe_episode_pflegen(drawdown)
        limit = self._limits_pruefen(account=account, peak=peak, now=now)
        if limit.state is TradingState.HALTED:
            self._halt = True
            self._halt_grund = "drawdown_halt_gelatcht"
            self._halt_seit = now
            self._sichern()
            return RiskAuthorization(
                approved=False,
                reason=(
                    f"risk_{limit.reasons[0]}" if limit.reasons else "risk_blocked"
                ),
                latch_halt=True,
                detail={"limit_state": limit.state.value},
            )

        # 0b2) Der Zustand kommt nicht auf die Platte (Begruendung: ``_sichern``).
        # Nach dem Halt, weil der Halt die aeltere und schwerere Aussage ist -- und
        # weil die Reihenfolge sonst einen gelatchten Halt hinter einem Plattenfehler
        # verstecken wuerde, obwohl nur der Halt einen Menschen braucht.
        if self._schreibfehler is not None:
            return RiskAuthorization(
                approved=False,
                reason=f"risk_{self._schreibfehler}",
                # KEIN Latch: diese Sperre behauptet nichts ueber den Markt, sondern
                # nur ueber die Platte. Sie faellt, sobald ein Schreibvorgang gelingt
                # -- durch einen Beweis, nicht durch Zeitablauf. Ein Latch verlangte
                # dafuer einen Menschen und machte aus einem geloesten Plattenproblem
                # eine offene Ticketnummer.
                latch_halt=False,
                detail={
                    "zustandsdatei": str(self._zustand.pfad)
                    if self._zustand is not None
                    else "",
                    "schreibfehler": (
                        self._zustand.schreibfehler_text
                        if self._zustand is not None
                        else ""
                    ),
                },
            )

        # 0c) Tageszaehler aus einem unlesbaren Zustand: fuer HEUTE ausgeschoepft.
        # Kein Latch -- diese Sperre verfaellt mit dem Tageswechsel (Begruendung der
        # Asymmetrie in ``execution/risiko_zustand.py``).
        if self._zaehler_gesperrt:
            return RiskAuthorization(
                approved=False,
                reason="throttle_tageszaehler_unlesbar",
                detail={"handelstag": now.date().isoformat()},
            )

        # 1) Kill-Switch (evaluate_limits) -- der Rest davon: Tagesverlust, Deckel,
        # Gap. Der Halt ist schon oben entschieden (0b1); hier bleiben die Gruende
        # ohne Latch. Ausgewertet wurde einmal, nicht zweimal: eine zweite Auswertung
        # koennte anders ausgehen als die erste.
        if not limit.may_open:
            return RiskAuthorization(
                approved=False,
                reason=f"risk_{limit.reasons[0]}" if limit.reasons else "risk_blocked",
                latch_halt=False,
                detail={"limit_state": limit.state.value},
            )

        # 2) Drossel (select_one): Cooldown, Mindesthaltedauer, Tageskappen, Deckel.
        # Der Score liegt per Konstruktion auf der Schwelle: der Auftrag existiert, die
        # Bewertung ist also bereits getroffen -- die Drossel prueft nur die Frequenz.
        candidate = Candidate(
            instrument=request.symbol,
            asset_class=instrument.asset_class.value,
            score=self._policy.throttle.score_threshold,
        )
        gate_state = GateState(
            now=now,
            open_positions=tuple(self._open_positions),
            last_trade_at=dict(self._last_trade_at),
            trades_today_per_instrument=dict(self._trades_today_instrument),
            trades_today_account=self._trades_today_account,
        )
        gate = select_one([candidate], gate_state, self._policy.throttle)
        if gate.selected is None:
            reasons = gate.suppressed[0].reasons if gate.suppressed else ()
            reason = f"throttle_{reasons[0]}" if reasons else "throttle_blocked"
            return RiskAuthorization(approved=False, reason=reason)

        # 3) Stop-Floor gegen Stop-Budget je Klasse/Hebel.
        if price <= 0:
            return RiskAuthorization(approved=False, reason="risk_price_missing")
        requested_stop_bps = (
            abs(price - request.stop_loss) / price * Decimal("10000")
        )
        floor = executable_stop_floor(
            StopFloorInputs(
                spread_bps=spread_bps,
                tick_size_bps=instrument.tick_size / price * Decimal("10000"),
                # Volatilitaet steht am Order-Pfad nicht je Bar bereit -> 0; der Floor
                # nimmt das Maximum, die uebrigen Komponenten (Broker-Abstand, Tiefe,
                # Spread) binden weiter. Nachruesten: siehe SPAETER.
                volatility_bps=Decimal("0"),
                broker_stop_level_bps=Decimal(instrument.stop_level_points)
                * instrument.tick_size
                / price
                * Decimal("10000"),
                depth_ratio=None,
            )
        )
        # Kostenbasis samt Herkunft (Rangfolge und Pruefung: ``_kostenbasis``). Das
        # erste Wort im ``detail`` benennt den Kanal, nicht nur "jemand hat eine Zahl
        # uebergeben" -- eine mitgereiste Zahl ist etwas anderes als eine Messung
        # dieses Laufs, auch wenn beide gepruefte Zahlen sind.
        basis = self._kostenbasis(
            instrument=instrument, request=request, measured_cost_bps=measured_cost_bps
        )
        budget = self.stop_budget_for(
            asset_class=instrument.asset_class.value,
            leverage=leverage,
            measured_cost_bps=basis.bps,
        )
        kostenbasis = basis.als_text(budget.cost_bps)
        if not budget.tradeable:
            return RiskAuthorization(
                approved=False,
                reason=f"stop_budget_{budget.reason or 'untradeable'}",
                budget=budget,
                detail={"cost_basis": kostenbasis},
            )
        # Der effektive Stopabstand muss die Budget-UNTERgrenze (Kostenfloor) einhalten.
        # Ein zu enger Stop ist rechnerisch unhandelbar -- die Kosten heben den
        # Nulldurchgang zu weit (``breakeven_hit_rate``). Die Obergrenze prueft
        # ``size_position`` bereits praezise (stop_floor/requested vs. budget.upper).
        effective_stop_bps = max(floor.executable_floor_bps, requested_stop_bps)
        if effective_stop_bps < budget.lower_bps:
            return RiskAuthorization(
                approved=False,
                reason="stop_budget_below_cost_floor",
                budget=budget,
                detail={
                    "cost_basis": kostenbasis,
                    "effective_stop_bps": str(effective_stop_bps),
                    "cost_floor_bps": str(budget.lower_bps),
                },
            )

        # 4) Positionsgroesse: angefordertes Volumen darf das Budget nicht reissen.
        sizing = size_position(
            account_equity=account.equity,
            risk_fraction=self._policy.risk_fraction,
            stop_floor_bps=floor.executable_floor_bps,
            stop_budget_bps=budget.upper_bps,
            requested_stop_bps=requested_stop_bps,
            price=price,
            contract_size=instrument.contract_size,
            volume_min=instrument.volume_min,
            volume_step=instrument.volume_step,
            volume_max=instrument.volume_max,
            leverage=leverage,
        )
        if sizing.no_trade:
            first = sizing.reasons[0] if sizing.reasons else "no_trade"
            return RiskAuthorization(
                approved=False,
                reason=f"risk_sizing_{first}",
                sizing=sizing,
                budget=budget,
                detail={"cost_basis": kostenbasis},
            )
        if sizing.volume is not None and request.volume > sizing.volume:
            # Das angeforderte Volumen liegt ueber dem risikobudgetierten Maximum.
            return RiskAuthorization(
                approved=False,
                reason="volume_exceeds_risk_budget",
                sizing=sizing,
                budget=budget,
                detail={
                    "requested_volume": str(request.volume),
                    "budget_volume": str(sizing.volume),
                    "cost_basis": kostenbasis,
                },
            )

        return RiskAuthorization(
            approved=True,
            reason=None,
            sizing=sizing,
            budget=budget,
            detail={"budget_volume": str(sizing.volume), "cost_basis": kostenbasis},
        )

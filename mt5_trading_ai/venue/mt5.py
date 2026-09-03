"""MT5-Anbindung an das ``TradingVenue``-Protokoll.

Drei Eigenschaften bestimmen den Aufbau:

* **Fail-closed am Ausfuehrungspfad.** Eine eroeffnende Order an ein **Live**-Konto
  (``account.is_demo is False``) passiert nur, wenn die mehrteilige Live-Freigabe
  (``execution/release.py``) vollstaendig ist. Fehlt sie, wird die Order abgelehnt --
  nicht gesendet. Demokonten und Reduce-Only (Risikoabbau) passieren ohne Freigabe.
  Der Adapter baut damit den Anschluss, den ``archiv/FEHLT.md`` als offen markiert hat,
  **mit**
  dem Tor, nicht daran vorbei.
* **Testbar ohne Terminal.** Der Adapter spricht gegen die schmale Naht
  :class:`Mt5Terminal`. Der Vertragstest injiziert ein Fake-Terminal; kein echtes MT5
  wird gebraucht. Die eigentliche MT5→Protokoll-Abbildung liegt hier (getestet).
* **Import bleibt stdlib-rein.** Das Paket ``MetaTrader5`` wird ausschliesslich **lazy**
  in :class:`RealMt5Terminal` geladen. Der Modulimport haengt an nichts ausserhalb der
  Standardbibliothek.
"""

from __future__ import annotations

import hashlib
import importlib
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Any, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.execution.cost_gate import CostGate, evaluate_cost_gate
from mt5_trading_ai.execution.freshness import (
    MAX_SNAPSHOT_AGE,
    evaluate_account_freshness,
)
from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight
from mt5_trading_ai.execution.private_sync import PrivateEvent, PrivateSync
from mt5_trading_ai.execution.reconcile import (
    PositionBook,
    ReconcileResult,
    positions_to_net,
    reconcile_positions,
)
from mt5_trading_ai.execution.release import live_release_blocks_opening_order
from mt5_trading_ai.execution.risiko_zustand import (
    UMGEBUNG_ZUSTANDSDATEI,
    UMGEBUNG_ZUSTANDSORDNER,
)
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.schwebende_auftraege import (
    UMGEBUNG_SCHWEBEDATEI,
    SchwebeAkte,
    SchwebenderAuftrag,
    standard_schwebedatei,
)
from mt5_trading_ai.venue.catalog import (
    MINUTEN_JE_TAG,
    CatalogEntry,
    InstrumentCatalogError,
    session_minutes,
)
from mt5_trading_ai.venue.demo_run import DemoRegistration, pruefe_demo_beleg
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Bar,
    Instrument,
    OrderRejectedError,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    Position,
    Quote,
    Timeframe,
    TradingSession,
    TradingVenue,
    UnknownInstrumentError,
    VenueUnavailableError,
    ist_abgeschlossen,
)

MT5_ADAPTER_VERSION = "mt5-venue-v1"


class NotAusUnvollstaendig(VenueUnavailableError):
    """Der Not-Aus hat **nicht** alles geschlossen. Kein Rueckgabewert, ein Fehler.

    Warum eine eigene Ausnahme und nicht ein Tupel mit weniger Eintraegen: ein
    Aufrufer, der ``emergency_flatten()`` ruft, will genau eine Auskunft -- ist das
    Risiko weg? Ein kuerzeres Tupel beantwortet die Frage nicht, es verschweigt sie.
    Der Ausgang "teilweise" muss darum den normalen Weg verlassen.

    ``geschlossen`` traegt, was gelungen ist (die Information geht durch das Werfen
    nicht verloren), ``offen`` je einen Klartext-Eintrag pro Position, die steht oder
    deren Ausgang unbekannt ist. Der Global-Halt ist beim Werfen bereits gesetzt.
    """

    def __init__(
        self,
        message: str,
        *,
        geschlossen: tuple[OrderResult, ...],
        offen: tuple[str, ...],
    ) -> None:
        super().__init__(message)
        self.geschlossen = geschlossen
        self.offen = offen


# --------------------------------------------------------------------------- #
# MT5-seitige Rohwerte — was ein Terminal liefert, bereits leicht normalisiert. #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Mt5Symbol:
    name: str
    digits: int
    tick_size: Decimal
    pip_size: Decimal
    contract_size: Decimal
    volume_min: Decimal
    volume_step: Decimal
    volume_max: Decimal | None
    base_currency: str | None
    quote_currency: str | None
    #: Mindestabstand fuer Stops, gezaehlt in **Tick-Schritten** (``tick_size``) --
    #: nicht in MT5-Points. ``RealMt5Terminal`` rechnet ``trade_stops_level`` beim
    #: Einlesen um (:func:`stop_level_in_tickschritten`), weil jeder Leser des Feldes
    #: mit ``tick_size`` multipliziert. Der Name blieb, die Einheit steht hier.
    stop_level_points: int
    freeze_level_points: int
    visible: bool


@dataclass(frozen=True)
class Mt5Tick:
    ts: datetime
    bid: Decimal
    ask: Decimal
    bid_volume: Decimal | None = None
    ask_volume: Decimal | None = None


@dataclass(frozen=True)
class Mt5Rate:
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int
    real_volume: Decimal | None = None
    spread_points: Decimal | None = None


@dataclass(frozen=True)
class Mt5Position:
    ticket: str
    symbol: str
    is_buy: bool
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    opened_at: datetime
    unrealised_pnl: Decimal
    swap: Decimal


@dataclass(frozen=True)
class Mt5Account:
    account_id: str
    currency: str
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_free: Decimal
    #: ``True`` nur bei einem Demokonto. Der Live-Pfad prueft dieses Feld.
    is_demo: bool
    ts: datetime
    #: Hebel, den der Broker diesem Konto gewaehrt (1:N -> N). ``None`` = unbekannt.
    leverage: int | None = None


@dataclass(frozen=True)
class Mt5SendResult:
    accepted: bool
    venue_order_id: str | None
    filled_volume: Decimal
    average_price: Decimal | None
    ts: datetime
    reason: str
    retryable: bool = False
    #: Der Auftrag lag beim Broker bereits vor und wurde **nicht erneut gesendet**.
    #: Getrennt von ``accepted``, weil es eine andere Tatsache ist: angenommen ja,
    #: gesendet nein. Wer beides zusammenwirft, bucht eine alte Fuellung zweimal.
    idempotent_replay: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Mt5Terminal(Protocol):
    """Die schmale Naht zum Terminal.

    Real oder Fake — der Adapter unterscheidet nicht.
    """

    def initialize(self) -> bool: ...
    def shutdown(self) -> None: ...
    def is_connected(self) -> bool: ...
    def symbols(self) -> tuple[Mt5Symbol, ...]: ...
    def symbol(self, name: str) -> Mt5Symbol | None: ...
    def tick(self, name: str) -> Mt5Tick | None: ...
    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]: ...
    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult: ...
    def cancel(self, venue_order_id: str) -> bool: ...
    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool: ...
    def positions(self) -> tuple[Mt5Position, ...]: ...
    def account(self) -> Mt5Account: ...


#: Minuten einer Woche. Bezugspunkt ist Montag 00:00 UTC (``weekday() == 0``).
MINUTEN_JE_WOCHE = 7 * MINUTEN_JE_TAG


def _sitzungsfenster(session: TradingSession) -> tuple[int, int]:
    """Ein Sitzungsfenster als halboffenes Intervall in **Minuten seit Montag 00:00**.

    Warum Minuten der Woche und nicht Minuten des Tages: die alte Fassung verglich
    ``open_min <= minute_of_day < close_min`` innerhalb **eines** Wochentags. Damit war
    eine Sitzung ueber Mitternacht schlicht nicht ausdrueckbar -- und genau so laeuft
    die reale Woche: der FX-Handel oeffnet Sonntagabend und schliesst Freitagabend, ein
    Index-CFD haengt an der Kassa-Sitzung seines Platzes. Wer so ein Fenster in
    Tagesminuten pressen will, bekommt ``22:00 <= x < 06:00`` -- eine Bedingung, die
    fuer **kein** ``x`` wahr ist. Das ist die harmlose Richtung (der Filter schneidet
    Handelszeit weg), aber es ist eine Sperre, die per Konstruktion nichts sagt.

    Ueber die Wochengrenze hinaus (Sonntag 22:00 -> Montag 06:00) laeuft das Fenster
    ueber ``MINUTEN_JE_WOCHE`` hinaus; :func:`_sitzung_deckt` faengt das ab.

    **Die drei Pruefungen unten stehen ein zweites Mal im Haus** -- dieselben Regeln
    (Wochentag 0..6, Beginn nicht am Tagesende, Beginn ungleich Ende) prueft
    ``venue/catalog.py::_parse_sessions`` beim Laden der Datei. Ueber den Katalog-Lader
    sind sie hier unerreichbar; sie feuern nur an einem **handgebauten**
    ``TradingSession``, also in Tests und in kuenftigem Code, der den Lader umgeht.
    Bewusst nicht entfernt: ein Sitzungsfenster ohne Pruefung ist ein Fenster, das
    still nie (oder immer) greift, und der Lader kann fuer ein Objekt, das nie durch
    ihn lief, nicht buergen. Bewusst auch nicht zusammengezogen: die geteilte Stelle
    waere ``session_minutes`` -- die ist bereits geteilt --, waehrend die drei Regeln
    hier auf einem Objekt und dort auf JSON-Rohwerten arbeiten. Wer eine der Regeln
    aendert, aendert beide Stellen; das steht hier, damit die zweite gefunden wird.
    """
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
    return anfang, anfang + dauer


def _sitzung_deckt(sessions: tuple[TradingSession, ...], zeit: datetime) -> bool:
    """Faellt ``zeit`` (UTC, zonenbewusst) in eines der Sitzungsfenster?

    Rein rechnerisch, ohne jede Aussage darueber, ob der Platz tatsaechlich offen ist
    -- das beantwortet allein der Kursstrom (siehe :meth:`Mt5Venue.is_trading_open`).
    """
    minute = zeit.weekday() * MINUTEN_JE_TAG + zeit.hour * 60 + zeit.minute
    for session in sessions:
        anfang, ende = _sitzungsfenster(session)
        if anfang <= minute < ende:
            return True
        # Fenster, das ueber Sonntag 24:00 hinauslaeuft, deckt den Montagmorgen.
        if ende > MINUTEN_JE_WOCHE and minute < ende - MINUTEN_JE_WOCHE:
            return True
    return False


def stop_level_in_tickschritten(
    stops_level: int, *, point: Decimal, tick: Decimal
) -> int:
    """``trade_stops_level`` steht in POINTS -- hier in **Tick-Schritte** umgerechnet.

    Der Einheitenbruch, den das behebt: MT5 gibt ``SYMBOL_TRADE_STOPS_LEVEL`` als
    Vielfaches von ``SYMBOL_POINT`` an (``point``, die letzte Stelle des Kurses). Jeder
    Leser dieses Feldes im Repo multipliziert es aber mit ``tick_size``
    (``venue/smoke.py::_probe_stop``, ``execution/risk_manager.py``,
    ``execution/runner.py``) -- also mit ``SYMBOL_TRADE_TICK_SIZE``, der kleinsten
    Kursaenderung. Solange beide gleich sind (FX mit fuenf Stellen: 0.00001 = 0.00001)
    faellt das nicht auf. Wo sie auseinandergehen -- Index-CFDs mit ``point=0.01`` und
    ``tick_size=0.25`` sind der bekannte Fall -- rechnete bisher jeder dieser Leser mit
    einem falschen Mindestabstand.

    **Die Richtung ist bewusst einseitig gewaehlt.** Umgerechnet wird mit dem
    *groesseren* der beiden Massstaebe::

        tickschritte = aufgerundet(stops_level * max(point, tick) / tick)

    * ``tick >= point`` (der Normalfall): das Ergebnis ist ``stops_level``, also genau
      der bisherige Wert. Es wird nichts gelockert.
    * ``point > tick``: der bisherige Wert war **kleiner** als der Mindestabstand des
      Brokers -- ein zu enger Stop, den der Server mit INVALID_STOPS zurueckweist. Genau
      diese Richtung wird geschlossen, und zwar nach oben.

    Aufgerundet wird, weil ein halber Tick kein Tick ist: abgerundet ergaebe sich wieder
    ein Abstand unterhalb des Brokerminimums. Was hier **nicht** entschieden wird: ob
    ein Broker, dessen ``point`` und ``tick_size`` auseinandergehen, das Feld wirklich
    in Points meint. Das laesst sich am Terminal nicht feststellen; darum die
    konservative Seite und keine Verkleinerung des bisherigen Wertes.

    Der Feldname bleibt ``stop_level_points``, weil ihn drei Module ausserhalb dieses
    Adapters lesen und eine Umbenennung eine eigene Welle ist. Die Einheit steht an
    :class:`Mt5Symbol` und an ``protocol.Instrument``.
    """
    if stops_level <= 0 or point <= 0 or tick <= 0:
        # Nichts umzurechnen (kein Mindestabstand) oder kein brauchbares Raster. Der
        # Rohwert bleibt stehen; ein Raster von 0 faellt am Rauchtest auf
        # (``get_instrument``-Schritt in ``venue/smoke.py``).
        return max(stops_level, 0)
    massstab = point if point > tick else tick
    if massstab == tick:
        return stops_level
    schritte = (Decimal(stops_level) * massstab) / tick
    return int(schritte.to_integral_value(rounding=ROUND_CEILING))


def _schwebeakte_waehlen() -> SchwebeAkte:
    """Umgebung -> Datei, sonst fluechtig. Dieselbe Regel wie fuer den Risikozustand.

    ``RiskManager._zustand_waehlen`` entscheidet genauso, und aus demselben Grund: eine
    Bibliothek schreibt nicht ungefragt in das Zustandsverzeichnis des Benutzers, nur
    weil jemand ein Objekt gebaut hat. Wer die Akte dauerhaft will -- und im Betrieb
    will man das --, setzt ``MT5_SCHWEBENDE_AUFTRAEGE`` oder eine der beiden
    Zustandsordner-Variablen.

    Die Regel ist hier keine Bequemlichkeit, sondern eine Messung: ohne sie schrieb der
    Testlauf dieses Repos in ``%LOCALAPPDATA%`` des Entwicklers -- und die dort
    hinterlassenen Kennungen sperrten anschliessend 87 Faelle, die mit der Sache nichts
    zu tun hatten.
    """
    if (
        os.environ.get(UMGEBUNG_SCHWEBEDATEI)
        or os.environ.get(UMGEBUNG_ZUSTANDSDATEI)
        or os.environ.get(UMGEBUNG_ZUSTANDSORDNER)
    ):
        return SchwebeAkte(standard_schwebedatei())
    return SchwebeAkte(None)


def _halt_grund_fortschreiben(bisher: str | None, neu: str) -> str:
    """Neuer Halt-Grund, **ohne** den bestehenden zu loeschen.

    Der Grund ist die Spur, an der ein Zwischenfall spaeter nachvollzogen wird. Wird er
    beim zweiten Latch ueberschrieben, verschwindet gerade der erste -- und der erste
    ist der interessante: ein ``sendeversuch_unklar:...`` sagt, wonach beim Broker zu
    sehen ist, ein nachfolgendes ``emergency_flatten`` sagt nur, dass jemand die Bremse
    gezogen hat.

    Das Ergebnis waechst nicht unbegrenzt und **schrumpft auch nicht**: steht derselbe
    Grund schon vorn, bleibt der Wert unveraendert stehen -- mitsamt dem, was er
    bewahrt. Ein zweiter Not-Aus haengt also weder etwas an noch loescht er den
    urspruenglichen Anlass. Eine unbeschraenkte Kette waere die zweite Sorte
    Diagnoseverlust: eine Zeile, die niemand mehr liest.
    """
    if bisher is None:
        return neu
    if bisher == neu or bisher.startswith(f"{neu} ("):
        return bisher
    return f"{neu} (zuvor: {bisher})"


#: Pflichtfelder des Kontoschnappschusses, die KEINEN Vorgabewert kennen. Jedes wird
#: im Orderpfad wirklich gelesen: ``account_id`` bindet den Risikozustand an das Konto,
#: ``is_demo`` entscheidet ueber die Live-Freigabe, ``ts`` traegt die Frischepruefung,
#: ``currency`` die Bezugsgroesse jeder Geldzahl.
_KONTO_PFLICHTFELDER: tuple[str, ...] = ("account_id", "currency", "is_demo", "ts")

#: Dieselbe Frage fuer die Geldzahlen. Sie muessen zusaetzlich endlich sein: ein
#: ``NaN`` in der Equity ueberlebt jeden Vergleich klaglos und faerbt danach jede
#: Grenze in die milde Richtung -- ``NaN > limit`` ist ``False``, der Kill-Switch
#: schweigt also gerade dann, wenn die Zahl unbrauchbar ist.
_KONTO_PFLICHTZAHLEN: tuple[str, ...] = (
    "balance",
    "equity",
    "margin_used",
    "margin_free",
)


def konto_maengel(acc: object) -> str | None:
    """Was am Kontoschnappschuss fehlt -- oder ``None``, wenn er vollstaendig ist.

    Sperre V3 des Auftrags: *„Ein fehlender Messwert sperrt. Er wird nie durch einen
    Standardwert ersetzt."* Der Kontoschnappschuss ist der Messwert, auf dem die halbe
    Risikoschicht steht, und er wurde bis hierher **ungeprueft** benutzt: ein fehlender
    Schnappschuss endete in einem ``AttributeError`` mitten im Freigabe-Tor, ein
    fehlender Zeitstempel in einem ``AttributeError`` mitten in der Frischepruefung.

    Ein ``AttributeError`` ist keine Ablehnung mit Grund. Er nennt den Ort, nicht die
    Ursache; er traegt keinen ``reason``, an dem der Betrieb ihn zaehlen oder
    unterscheiden koennte; und er sieht im Protokoll aus wie ein Programmfehler, nicht
    wie eine Sperre, die getan hat, was sie soll. Genau diese Unterscheidung verlangt
    die Abnahme der Stufe 4: *„leere Kontodaten erzeugen eine Ablehnung mit Grund"*.

    **Der Parameter ist ``object``, nicht ``Any``** (Stufe 9). Der Unterschied ist keine
    Formsache: ``Any`` schaltet die Typpruefung fuer jeden Zugriff ab, ``object`` zwingt
    sie durch ``getattr``/``isinstance``. Und genau das soll sie hier -- die Funktion
    bekommt bewusst auch ``None`` und halbfertige Schnappschuesse. Ein Tor, das
    unvollstaendige Daten pruefen soll, darf nicht selbst ungeprueft auf sie zugreifen.

    Die Funktion urteilt **nicht** ueber die Fehlerart -- sie liefert den Mangel als
    Text. Welcher Ausnahmetyp daraus wird, entscheidet die Aufrufstelle: im Orderpfad
    eine ``OrderRejectedError`` mit ``reason``, an der lesenden Kontoabfrage eine
    ``VenueUnavailableError``. Eine Regel, zwei angemessene Ausgaenge -- nicht zwei
    Regeln, die auseinanderlaufen koennen.
    """
    if acc is None:
        return "kein Kontoschnappschuss (account() lieferte None)"
    for feld in _KONTO_PFLICHTFELDER:
        if getattr(acc, feld, None) is None:
            return f"Pflichtfeld '{feld}' fehlt"
    for feld in _KONTO_PFLICHTZAHLEN:
        wert = getattr(acc, feld, None)
        if wert is None:
            return f"Pflichtzahl '{feld}' fehlt"
        if isinstance(wert, Decimal) and not wert.is_finite():
            return f"Pflichtzahl '{feld}' ist nicht endlich ({wert})"
    return None


class Mt5Venue(TradingVenue):
    """MT5-Handelsplatz. Erfuellt das ``TradingVenue``-Protokoll (statisch geprueft).

    ``settings`` traegt die Live-Freigabe-Schalter (siehe ``execution/release.py``);
    fuer Demo/Reduce-Only ist es unerheblich und darf ``None`` sein.

    ``cost_gate`` traegt die im Backtest vorausgesetzte Kostenobergrenze
    (``execution/cost_gate.py``). Auf einem **Live**-Konto ist es fuer eroeffnende
    Orders Pflicht: fehlt es, wird fail-closed abgelehnt (kein ungeprueftes Live-Kosten-
    risiko). Auf Demo ist es unerheblich (kein Echtgeld) -- wie die Live-Freigabe.

    ``risk_manager`` traegt die Risikoschicht (``execution/risk_manager.py``):
    Kill-Switch (Tagesverlust/Drawdown/Deckel/Gap), Drossel, Stop-Budget und
    Positionsgroesse. **Anders als das Kostentor ist sie fuer JEDE
    eroeffnende Order Pflicht, auch auf Demo** (Paket 2, A3): das Kostentor
    schuetzen vor realem Geld und realer Zinsbelastung — auf einem Demokonto gibt es
    beides nicht. Die Risikoschicht dagegen prueft, ob der **Mechanismus** traegt, und
    genau das muss auf dem Demokonto laufen, weil das Demokonto der Beweisplatz vor
    jedem Live-Pfad ist (Reihenfolge-Regel aus ``archiv/FEHLT.md``). Eine Sperre, die
    nur auf
    dem Konto laeuft, das man noch nicht benutzt, ist nicht verdrahtet.
    Fehlt der Manager, wird jede Eroeffnung fail-closed abgelehnt.
    Drawdown-Halt setzt ``_halted``.

    ``clock`` liefert die Gegenwart fuer den **Frische-Latch** (S2,
    ``execution/freshness.py``): ein Kontozustand aelter als ``max_account_age`` gilt
    als nicht bewertbar, und nicht bewertbar heisst nicht erfuellt. Der Latch laeuft
    als **erste** der fuenf Sperren, weil jede folgende mit Zahlen aus genau diesem
    Zustand rechnet. Default ist die Systemuhr; Tests spritzen eine feste Uhr ein.

    ``demo_registration`` + ``demo_live_verdict`` (Paket 5) sind die Belege des
    Demo-Betriebs (``venue/demo_run.py``): der **Registrierungsbeleg** (welche
    Strategie lief ab wann auf welchem Demokonto) und das Edge-Urteil, das der Aufrufer
    fuer den Demo-Betrieb **mitbringt**. Eine Live-Eroeffnung verlangt >= 180 Tage seit
    dem Registrierungsdatum und ein bestandenes Edge-Urteil; die Frist rechnet das Tor
    selbst (:meth:`_require_demo_maturity`) gegen ``clock``.

    Bewusst **kein** fertiges ``DemoReadiness`` mehr: das war ein Urteil, das der
    Aufrufer in einer Zeile behaupten konnte (``DemoReadiness(True, ())``), und ein Tor,
    das ein Urteil entgegennimmt, ist kein Tor, sondern ein Echo. Ein Beleg traegt
    dagegen ein Datum, und ueber das Datum rechnet die Uhr des Tores, nicht der
    Aufrufer. Fehlt einer der beiden Belege, wird fail-closed abgelehnt.

    **Wie weit das traegt, ausdruecklich:** ``DemoRegistration`` ist ein offener
    Datentyp, ``registered_on`` ein gewoehnliches Feld. Wer den Beleg selbst baut, setzt
    das Datum frei -- die Latte ist real hoeher, aber die Behauptungsstelle ist von
    einem Urteil auf ein Datum umgezogen, nicht verschwunden. Dasselbe gilt fuer
    ``demo_live_verdict``: ``EdgeVerdict(passed=True, checks=(), unmet=())`` ist eine
    Zeile, dieser Venue misst nichts nach. Die Begruendung, warum das an dieser Stelle
    strukturell nicht zu schliessen ist (ein Zeuge muesste von der anderen Seite der
    Leitung kommen, und das Demokonto ist aus der Live-Sitzung nicht sichtbar), steht in
    ``venue/demo_run.py`` unter "DIE GRENZE DIESER STUFE"; festgenagelt in
    ``tests/test_demo_beleg_grenze.py``.

    """

    def __init__(
        self,
        *,
        name: str,
        terminal: Mt5Terminal,
        catalog: Mapping[str, CatalogEntry],
        settings: Any = None,
        max_notional_drift: Decimal = Decimal("0"),
        sync: PrivateSync | None = None,
        cost_gate: CostGate | None = None,
        risk_manager: RiskManager | None = None,
        demo_registration: DemoRegistration | None = None,
        demo_live_verdict: EdgeVerdict | None = None,
        clock: Callable[[], datetime] | None = None,
        max_account_age: timedelta = MAX_SNAPSHOT_AGE,
        schwebeakte: SchwebeAkte | None = None,
    ) -> None:
        self.name = name
        self._terminal = terminal
        self._catalog = dict(catalog)
        self._settings = settings
        self._max_notional_drift = max_notional_drift
        self._cost_gate = cost_gate
        self._risk_manager = risk_manager
        self._demo_registration = demo_registration
        self._demo_live_verdict = demo_live_verdict
        #: Gegenwart fuer den Frische-Latch. Injizierbar, damit die Sperre pruefbar ist.
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self._max_account_age = max_account_age
        #: Die Akte der Auftraege, deren Antwort ausblieb. Sie ueberdauert einen
        #: Neustart -- anders als der frueher hier gefuehrte Speicherzettel, der bei
        #: jedem Prozessstart leer war und damit gerade die Kenntnis verlor, dass
        #: moeglicherweise Geld am Markt steht (Stufe 5).
        self._schwebeakte = (
            schwebeakte if schwebeakte is not None else _schwebeakte_waehlen()
        )
        self._connected = False
        #: Idempotenz je ``client_order_id`` — nur angenommene Orders.
        #:
        #: **Reicht allein nicht** und war nie als alleiniger Schutz gedacht: dieses
        #: Verzeichnis lebt im Prozessgedaechtnis. Ein Neustart, ein zweiter Runner
        #: oder ein Zeitablauf VOR dem Eintrag findet es leer. Der belastbare Teil der
        #: Idempotenz liegt beim Broker (``RealMt5Terminal._bereits_beim_broker``, die
        #: Kennmarke am Auftrag); dieser Puffer spart nur den Umlauf im Normalfall.
        self._results: dict[str, OrderResult] = {}
        #: Kennungen, deren Sendeversuch mit einer Ausnahme endete -- Ausgang unbekannt.
        #: Sie latchen den Global-Halt und stehen hier, damit der Betrieb weiss, wonach
        #: er beim Broker sehen muss. Ein spaeteres Ergebnis derselben Kennung raeumt
        #: den Eintrag wieder ab.
        self._unklare_sendeversuche: dict[str, str] = {}
        #: Zaehler der Not-Aus-Laeufe. Er geht in die Kennung jeder Schliessorder ein,
        #: damit ein zweiter Not-Aus nicht als Wiedergaenger des ersten gilt.
        self._flatten_laeufe = 0
        #: Privater Ereignisstrom (optional). Ist er da, fuehrt er das Buch.
        self._sync = sync
        #: Lokales Buch der Nettopositionen; mit Strom ist es dessen Buch (geteilt).
        self._book = sync.book if sync is not None else PositionBook()
        #: Global-Halt-Latch (Reconcile-Drift/Desync). Klaert nur ``clear_halt``.
        self._halted = False
        #: Grund des zuletzt gesetzten Halts (best-effort, fuer Nachweis/Alarm).
        self._halt_reason: str | None = None

    # --- Verbindung -------------------------------------------------------
    def connect(self) -> None:
        if not self._terminal.initialize():
            raise VenueUnavailableError("MT5-Terminal nicht initialisierbar")
        self._connected = True

    def disconnect(self) -> None:
        self._terminal.shutdown()
        self._connected = False

    def is_healthy(self) -> bool:
        """Sitzung da und Leitung offen. **Keine** Aussage ueber das Alter der Daten.

        ``self._connected`` haelt fest, dass ``connect()`` gelaufen und
        ``disconnect()`` nicht gelaufen ist; ``Mt5Terminal.is_connected()`` prueft
        am realen Terminal
        Prozess, Serververbindung und Kontositzung (siehe dort).

        Die dritte Kante des Vertrags -- veraltete Daten -- liegt bewusst nicht hier,
        sondern am Order-Pfad (:meth:`_enforce_account_freshness`, mit Kursstempel und
        Symbol). Der Grund steht bei ``RealMt5Terminal.is_connected``: eine
        Frischepruefung braucht ein Symbol, und diese Methode laeuft am Kopf fast
        jeder anderen. Wer eine Frischezusage braucht, holt sie dort -- nicht hier.
        """
        return self._connected and self._terminal.is_connected()

    def _require_healthy(self) -> None:
        if not self.is_healthy():
            raise VenueUnavailableError("MT5-Sitzung nicht verfuegbar")

    # --- Instrumentenmetadaten -------------------------------------------
    def get_instrument(self, symbol: str) -> Instrument:
        entry = self._catalog.get(symbol)
        sym = self._terminal.symbol(symbol)
        if entry is None or sym is None:
            raise UnknownInstrumentError(f"Unbekanntes Instrument: {symbol}")
        return Instrument(
            symbol=sym.name,
            venue=self.name,
            asset_class=entry.asset_class,
            contract_size=sym.contract_size,
            tick_size=sym.tick_size,
            pip_size=sym.pip_size,
            digits=sym.digits,
            volume_min=sym.volume_min,
            volume_step=sym.volume_step,
            volume_max=sym.volume_max,
            base_currency=sym.base_currency,
            quote_currency=sym.quote_currency,
            stop_level_points=sym.stop_level_points,
            freeze_level_points=sym.freeze_level_points,
            fees=entry.fees,
            sessions=entry.sessions,
            active=sym.visible,
        )

    def list_instruments(self) -> tuple[Instrument, ...]:
        """Das handelbare Universum: jeder Katalogeintrag, am Terminal aufgeloest.

        **Ein Katalogeintrag, den das Terminal nicht kennt, ist ein Fehler und kein
        stiller Abgang.** Bis hierher fing die Schleife ``UnknownInstrumentError`` mit
        einem ``continue`` ab: ein Symbol, das der Broker anders schreibt (``EURUSD.r``,
        Suffixe je Kontotyp) oder das im MarketWatch fehlt, verschwand lautlos aus dem
        Universum. Die Liste sah dann vollstaendig aus und war es nicht -- und weil der
        Katalog die einzige belegpflichtige Quelle des Universums ist, ist eine
        stillschweigend geschrumpfte Liste genau die Sorte Befund, die niemand bemerkt.
        Der Rueckgabetyp hat keinen Platz fuer eine Nebenmeldung, also gibt es nur zwei
        ehrliche Antworten: die vollstaendige Liste oder ein Fehler.

        Fail-closed, wie ``load_instrument_catalog``: jeder Defekt ist ein Fehler, kein
        Default. Es werden **alle** unaufloesbaren Symbole gesammelt und in einer
        Meldung genannt -- wer eine Kontoumstellung nachzieht, soll die Liste einmal
        sehen und nicht nach jedem Fix erneut anlaufen.
        """
        out: list[Instrument] = []
        fehlend: list[str] = []
        for symbol in self._catalog:
            try:
                out.append(self.get_instrument(symbol))
            except UnknownInstrumentError:
                fehlend.append(symbol)
        if fehlend:
            raise UnknownInstrumentError(
                "Katalogsymbole, die dieses Terminal nicht aufloest: "
                f"{', '.join(sorted(fehlend))}. Der Katalog ist die belegte Quelle des "
                "Universums -- ein Eintrag, den der Adapter nicht findet, ist ein "
                "Defekt der Datenlage (Broker-Suffix? MarketWatch?), kein Grund, das "
                "Symbol still wegzulassen."
            )
        return tuple(out)

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        """Ist der Platz fuer dieses Symbol offen? **Zwei** Bedingungen, beide noetig.

        Die alte Fassung stellte nur eine Frage, und die falsche: sie las eine Tabelle,
        in der EURUSD, GBPUSD, USDJPY, EURGBP, XAUUSD **und US500** dieselbe Zeile
        teilten (Mo-Fr 00:00-21:00), rechnete die Wanduhr ohne Zonenpruefung in
        Tagesminuten um und kannte keine Feiertage. Die harmlose Fehlrichtung war, dass
        der Filter reale Handelszeit wegschneidet. Die gefaehrliche war die andere:
        **"offen", waehrend der Platz zu ist** -- US500 um drei Uhr nachts, alles an
        Weihnachten. Danach laeuft die ganze Eintrittskette auf einem Markt, den es
        gerade nicht gibt.

        Darum ist die Antwort jetzt die Konjunktion aus einer Tabelle und einer
        **Messung**:

        1. **Die Tabelle darf nur verengen.** Das Sitzungsfenster aus dem Katalog ist
           eine konservative Annahme, kein veroeffentlichter Boersenkalender -- die
           Datei sagt das selbst ("Handelszeiten vereinfacht"). Eine unbelegte Annahme
           darf nichts oeffnen. In dieser Konjunktion kann sie genau das nicht: sie
           kommt nur als **notwendige** Bedingung vor, also ausschliesslich in der
           harmlosen Richtung. Damit muss hier keine Handelszeit erfunden werden, um
           die gefaehrliche Richtung zu schliessen -- und erfundene Handelszeiten
           waeren in einer belegpflichtigen Datei ohnehin das groessere Uebel.
        2. **Offen ist, wo Preise entstehen.** Der Beleg dafuer, dass der Platz
           tatsaechlich handelt, kommt von der anderen Seite der Leitung: der
           Kursstempel des Symbols muss innerhalb derselben Frist liegen, die der
           Frische-Latch am Order-Pfad anlegt (:meth:`_enforce_account_freshness`).
           Ein geschlossener Platz druckt keine Preise -- der letzte Tick altert, und
           das faellt hier auf, ohne dass irgendwo ein Feiertagskalender gepflegt
           werden muesste. Das ist dieselbe Entscheidung, die
           ``config/ereigniskalender.json`` schon fuer die Studie getroffen hat:
           "ein Ereignis ohne Kerze faellt heraus, und das ist genauer als ein
           gepflegter Feiertagskalender".

        **Die beiden Bedingungen fragen nach zwei verschiedenen Zeiten, und das ist
        der Kern.** Die Tabelle wird gegen ``at`` gelesen: sie beantwortet, ob der
        gefragte Zeitpunkt in einem Sitzungsfenster liegt. Die Messung dagegen wird
        gegen ``self._clock()`` gerechnet -- die Uhr dieses Venues, dieselbe, gegen
        die zwei Zeilen spaeter der Frische-Latch misst. Die erste Fassung nahm hier
        ``at``, und daran starb der Eintrittspfad:

        * ``tools/live_betrieb.py`` friert ``jetzt = datetime.now(UTC)`` am Kopf des
          Taktes ein und fragt erst danach ``is_trading_open(symbol, at=jetzt)``.
          Dazwischen liegen ein Kontoabruf, eine Positionsliste, ein ``get_quote`` je
          Symbol, der Buchabgleich, die Notbremse und je offener Position ein
          ``get_bars`` ueber 360 Stunden.
        * Der Tick dagegen wird in genau diesem Aufruf frisch geholt und ist ~echte
          Gegenwart. Sein Alter **gegen den eingefrorenen Zeitpunkt** ist damit
          negativ, und jenseits von ``FUTURE_TOLERANCE`` (1 s) lautet das Urteil
          ``snapshot_from_future``.
        * Ergebnis: sobald ein Takt laenger als eine Sekunde unterwegs ist -- also
          praktisch immer, und fuer das letzte Symbol der Liste sicher --, meldete
          ``is_trading_open`` False, und der Aufrufer sprang mit einem stillen
          ``continue`` weiter. Eine Sperre, die aus einem Grund schliesst, der mit dem
          Zustand des Marktes nichts zu tun hat, ist genauso kaputt wie eine, die nie
          schliesst; sie wird nur nicht bemerkt, sondern irgendwann abgeschaltet.

        "Druckt der Platz gerade Preise?" ist eine Frage an die Gegenwart, nicht an
        einen mitgereichten Zeitpunkt. Die Gegenwart gehoert diesem Venue (``clock``,
        in Tests eingespritzt) -- genauso, wie das Demo-Reifetor sein Datum nicht vom
        Aufrufer entgegennimmt. Festgenagelt in
        ``tests/test_handelszeiten.py::test_der_eingefrorene_zeitpunkt_des_aufrufers_bremst_nicht``.

        Warum genau ``self._max_account_age`` als Frist und keine eigene, weichere
        Zahl: eine Order auf ein Symbol, dessen Kurs diese Frist reisst, wird zwei
        Zeilen spaeter ohnehin abgelehnt. Diese Zusage haelt jetzt woertlich -- gleiche
        Frist UND gleiche Uhr; mit ``at`` als Bezug war sie nur halb wahr, denn in der
        Zukunftsrichtung sagte ``is_trading_open`` "zu", waehrend
        ``_enforce_account_freshness`` dieselbe Lage klaglos durchliess. Eine
        grosszuegigere Frist hier wuerde nur etwas versprechen, was das naechste Tor
        zurueckweist -- und eine zweite, abweichende Zahl fuer dieselbe Frage ist die
        Sorte Kopie, die auseinanderlaeuft.

        ``at`` **muss** zonenbewusst sein. Ein naiver Zeitstempel wird nicht still als
        UTC gedeutet: ``at.weekday()`` und ``at.hour`` haetten dann eine unbekannte
        Bedeutung, und das Ergebnis waere ein geratener Wochentag. Ein ``False`` waere
        hier die schlechtere Antwort als ein Fehler, denn "geschlossen" ist eine
        gueltige Marktaussage -- ein Aufruferfehler saehe als dauerhaft geschlossener
        Markt aus und faende sich nie.

        **Was das ueber ein historisches ``at`` sagt: nichts.** Wer einen Zeitpunkt
        von gestern einreicht, bekommt die Tabelle fuer gestern und die Messung fuer
        heute. Die Antwort ist dann keine historische Aussage. Das ist bewusst nicht
        durch eine Abweichungsgrenze abgefangen: jede solche Grenze waere eine weitere
        Zahl ohne Beleg, und der Kursstrom eines vergangenen Tages laesst sich am
        Terminal ohnehin nicht mehr abfragen. Beide realen Aufrufer
        (``tools/live_betrieb.py``, ``venue/smoke.py``) reichen die Gegenwart ein.

        **Benannter Mangel, bewusst nicht behoben:** ein Broker, der auf einem
        geschlossenen Platz weiter indikative Kurse stellt, faellt hier nicht auf. Die
        saubere Gegenprobe waere ``symbol_info(...).trade_mode`` bzw.
        ``symbol_info_sessions_trade`` -- beides gehoert an die Naht
        :class:`Mt5Terminal` und damit in eine eigene Welle, weil jedes Fake-Terminal
        im Repo mitzieht. Festgenagelt in
        ``tests/test_handelszeiten.py::test_stehende_indikative_kurse_gelten_als_offen``.
        """
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError(
                "is_trading_open braucht einen zonenbewussten Zeitpunkt -- ein naiver "
                "Stempel macht Wochentag und Uhrzeit zu geratenen Groessen"
            )
        instrument = self.get_instrument(symbol)
        zeit = at.astimezone(UTC)
        if not _sitzung_deckt(instrument.sessions, zeit):
            return False
        return self._markt_druckt_preise(symbol)

    def _markt_druckt_preise(self, symbol: str) -> bool:
        """Belegt der Kursstrom, dass dieses Symbol GERADE gehandelt wird?

        Kein Tick = kein Beleg = zu. Ein Tick, dessen Stempel die Frist reisst, ist
        derselbe Fall: der letzte Preis ist alt, also druckt der Platz gerade keine.
        Die Verbindung geht mit in die Frage ein -- ueber eine tote Leitung ist ueber
        den Zustand des Platzes nichts auszusagen (``session_not_connected``).

        Gemessen wird gegen ``self._clock()`` und **nicht** gegen einen mitgereichten
        Zeitpunkt. Der Grund steht ausfuehrlich bei :meth:`is_trading_open`: ein
        eingefrorener Aufruferzeitpunkt macht den frisch geholten Tick rechnerisch zu
        einem Stempel aus der Zukunft und schaltet damit den ganzen Eintrittspfad ab,
        ohne dass das mit dem Markt etwas zu tun haette. Darum nimmt diese Methode
        auch kein Zeitargument mehr entgegen -- es gab nur eine falsche Antwort
        darauf.
        """
        tick = self._terminal.tick(symbol)
        if tick is None:
            return False
        verdict = evaluate_account_freshness(
            snapshot_ts=tick.ts,
            now=self._clock(),
            connected=self._terminal.is_connected(),
            max_age=self._max_account_age,
        )
        return verdict.evaluable

    # --- Marktdaten -------------------------------------------------------
    def get_quote(self, symbol: str) -> Quote:
        self._require_healthy()
        self.get_instrument(symbol)  # unbekanntes Symbol -> UnknownInstrumentError
        tick = self._terminal.tick(symbol)
        if tick is None:
            raise VenueUnavailableError(f"Kein Tick fuer {symbol}")
        return Quote(
            symbol=symbol,
            ts=tick.ts,
            bid=tick.bid,
            ask=tick.ask,
            bid_volume=tick.bid_volume,
            ask_volume=tick.ask_volume,
        )

    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Bar, ...]:
        """Bars im Fenster, aufsteigend -- und jede mit dem Vermerk, ob sie steht.

        ``copy_rates_range`` liefert bei ``end=jetzt`` die noch **in Bildung**
        befindliche Kerze mit. Deren ``close`` ist der momentane Kurs. Ungekennzeichnet
        weitergereicht rechnet der Live-Treiber seinen gleitenden Durchschnitt auf einer
        Zahl, die es im Backtest nicht gibt -- dort kommen die Kerzen abgeschlossen aus
        Dateien. Darum traegt jede Bar hier ``is_closed``.

        **Woher die Gegenwart kommt, ist die ganze Frage.** Sie kommt vom Platz
        (``get_quote(...).ts``, also der Zeitstempel des letzten Ticks), nicht von
        ``self._clock`` und nicht aus ``end``:

        * Die Rechneruhr waere genau der Fehler, den dieses Repo schon einmal gemacht
          hat -- eine Sperre, die per Konstruktion nie ausloest, weil sie Systemzeit
          gegen Systemzeit haelt. Hier kommt hinzu, dass Kerzen- und Tick-Stempel beide
          durch ``RealMt5Terminal._utc`` laufen: ist ``server_tz`` nicht gesetzt,
          tragen sie die Wanduhr des Servers unter dem Etikett UTC, und ein Vergleich
          gegen echte UTC-Systemzeit haette den vollen Serverversatz drin. **Welche
          Richtung dabei herauskommt, haengt am Broker.** An diesem hier (Serverzone
          ``Europe/Helsinki``, also VOR UTC, im Sommer +3 h) liegen die Stempel drei
          Stunden vor der Rechneruhr; nachgemessen: die um 11:00 UTC fertige Kerze
          traegt den Stempel 13:00, die Rechneruhr steht auf 11:30, ``13:00 + 1 h <=
          11:30`` ist falsch -- **keine** Kerze gaelte je als abgeschlossen, der
          Live-Takt bliebe auf FLAT ("nur 0 abgeschlossene von N Kerzen"). Bei Server
          HINTER UTC (etwa UTC-5) dreht das Vorzeichen, und dieselbe Rechnung meldet
          die laufende Kerze als fertig: fail-open, unbemerkt. Beide Richtungen sind
          falsch; die Rechneruhr ist hier deshalb ueberhaupt keine Quelle.
        * Dass es heute gutginge, genuegt nicht: der tatsaechlich konfigurierte
          Live-Pfad setzt ``server_tz`` (``tools/live_betrieb.py``,
          ``tools/live_konsole.py``), dort sind ``rate.ts`` und ``tick.ts`` echtes UTC
          und liegen bis auf die Tick-Latenz auf der Rechneruhr. Eine Fassung mit
          ``datetime.now(UTC)`` saehe in genau dieser Konfiguration richtig aus und
          braeche, sobald ein Aufrufer die Zone weglaesst. Ein Venue, dessen
          Richtigkeit an der Konfiguration seines Aufrufers haengt, ist nicht richtig.
        * ``end`` ist Wunsch des Aufrufers, keine Messung. Ein zu grosses ``end``
          erklaerte jede Kerze fuer offen, ein zu kleines die laufende fuer fertig.
        * Der Tick-Stempel dagegen kommt durch **dieselbe** Umrechnung wie ``rate.ts``.
          Beide stehen damit in derselben Zeitrechnung, egal ob gedreht wird oder
          nicht -- der Vergleich traegt in beiden Faellen.

        Der Tick wird **vor** den Rates geholt. Vergeht zwischen beiden Abrufen eine
        Intervallgrenze, ist die Gegenwart dann eher zu alt als zu neu: eine bereits
        fertige Kerze gilt einmal zu Unrecht als laufend (verschenkt), statt eine
        laufende als fertig (falsch gerechnet). Nur eine der beiden Richtungen ist
        verzeihlich.

        ``get_quote`` wirft ohne Tick :class:`VenueUnavailableError` -- ohne Platzzeit
        ist nicht entscheidbar, welche Kerze steht, und nicht entscheidbar heisst hier
        nicht abgeschlossen genug zum Handeln. Fail-closed statt raten.

        Bekannter Mangel: ``timeframe.duration`` ist eine feste Sekundenzahl, die
        echte Grenze von D1 und H4 liegt aber an der Server-Mitternacht. Ueber eine
        Zeitumstellung weichen beide um eine Stunde ab, am Rueckstelltag in die
        schmeichelnde Richtung. Umfang und Begruendung stehen bei
        ``protocol.Timeframe.duration``; der Live-Pfad faehrt ausschliesslich H1 und
        ist immun.
        """
        # ``get_quote`` prueft Sitzung und Symbol selbst, in genau dieser Reihenfolge
        # (``_require_healthy`` -> ``get_instrument`` -> Tick). Ein eigener Vorlauf
        # hier waere dieselbe Pruefung ein zweites Mal -- ein zweiter Terminal-Umlauf
        # je ``get_bars`` und zwei Fassungen derselben Regel, die auseinanderlaufen
        # koennen. Die Fehlerreihenfolge bleibt unveraendert.
        jetzt = self.get_quote(symbol).ts
        rates = self._terminal.rates(symbol, timeframe, start, end)
        bars = [
            Bar(
                symbol=symbol,
                timeframe=timeframe,
                ts=rate.ts,
                open=rate.open,
                high=rate.high,
                low=rate.low,
                close=rate.close,
                tick_volume=rate.tick_volume,
                # Die Regel steht in ``protocol.ist_abgeschlossen`` -- einmal, weil
                # fuenf weitere Stellen an ``get_bars`` vorbei direkt aus dem Terminal
                # lesen und dieselbe Frage beantworten muessen.
                is_closed=ist_abgeschlossen(rate.ts, timeframe, jetzt),
                volume=rate.real_volume,
                spread_avg_points=rate.spread_points,
            )
            for rate in rates
            if start <= rate.ts <= end
        ]
        bars.sort(key=lambda bar: bar.ts)  # aufsteigend, ohne stille Interpolation
        return tuple(bars)

    # --- Ausfuehrung ------------------------------------------------------
    def submit_order(self, request: OrderRequest) -> OrderResult:
        self._require_healthy()

        # Idempotenz: eine bereits angenommene Kennung erzeugt keine zweite Order.
        previous = self._results.get(request.client_order_id)
        if previous is not None:
            return replace(previous, idempotent_replay=True)

        instrument = self.get_instrument(request.symbol)

        # ``reduce_only`` ueberspringt die Eroeffnungs-Tore -- aber NUR, wenn die Order
        # eine tatsaechlich offene Gegenposition abbaut. Ein reduce_only-Flag ohne (oder
        # gleichgerichtet zu einer) offenen Position ist eine Eroeffnung und muss durch
        # alle Tore (sonst umginge es Compliance/Risiko + Global-Halt -- §9 Paket 5).
        pre_net = self._book.net(request.symbol)
        is_reducing = request.reduce_only and self._reduces_position(request)

        if is_reducing:
            # Sperre V5: *„Reduzierende Auftraege werden von keiner Sperre blockiert."*
            # ``_validate_volume`` stand bis hierher VOR dieser Weiche und traf damit
            # auch den Abbau. Gemessen an einer Gegenposition von 0,005 Lot bei einem
            # Mindestvolumen von 0,01: der volle Abbau wurde mit ``volume_below_min``
            # abgewiesen -- die Position liess sich nicht schliessen. Erreichbar ist
            # das ueber ``adopt_book`` (der Broker meldet, was er hat, nicht was
            # unsere Schrittweite erlaubt), ueber eine Teilschliessung von aussen und
            # ueber jede spaetere Aenderung der Kontraktspezifikation.
            #
            # Fuer den Abbau bleibt genau eine Bedingung, und sie ist keine Sperre,
            # sondern eine Definition: es muss etwas abgebaut werden. Die Obergrenze
            # (nicht mehr als die Gegenposition) hat ``_reduces_position`` bereits
            # erzwungen -- daher hier weder Mindestvolumen noch Schrittweite noch
            # Hoechstvolumen. Ein Broker, der einen Teilabbau ablehnt, lehnt ihn
            # selbst ab; dieses Haus stellt sich davor nicht als zweite Instanz.
            if request.volume <= 0:
                raise OrderRejectedError(
                    f"Abbau ohne Volumen ({request.volume})",
                    reason="volume_not_positive",
                    retryable=False,
                )
        else:
            self._validate_volume(instrument, request.volume)
            # Stufe 5: „Antwort blieb aus, Auftrag koennte leben" muss VOR der naechsten
            # Eroeffnung aufgeloest sein. Diese Sperre steht bewusst vor dem Global-Halt
            # und traegt einen eigenen Grund: beide latchen zwar gemeinsam, aber
            # ``clear_halt()`` loest nur den Halt. Wer nur den Halt sieht, gibt ihn frei
            # und eroeffnet weiter -- gemessen genau so, bevor es diese Sperre gab.
            self._verweigere_bei_schwebendem_auftrag()
            if self._halted:
                raise OrderRejectedError(
                    "Global-Halt aktiv (Reconcile-Drift) — keine Eroeffnung",
                    reason="global_halt",
                    retryable=False,
                )
            # Ohne Stop wird nicht eroeffnet (Protokoll).
            if request.stop_loss <= 0:
                raise OrderRejectedError(
                    "Eroeffnende Order ohne gueltigen Stop",
                    reason="missing_stop_loss",
                    retryable=False,
                )
            # Sperre 1 von 5 (Paket 2, A3.2): Frische der Lage. Sie laeuft VOR allem,
            # was aus Konto- oder Kurszahlen liest -- auch vor der Live-Freigabe, die
            # ``is_demo`` aus dem Kontoschnappschuss zieht. Gemessen wird der
            # Kursstempel des Brokers; die Begruendung steht an der Methode.
            self._enforce_account_freshness(request.symbol)
            # Live-Freigabe (inkl. Demo-Reife): nur eroeffnende Orders am Live-Konto.
            self._require_live_release_for_opening()
            # Hebelklammer am Order-Pfad: handelbar, geklammert, Marge frei?
            effective_leverage = self._enforce_leverage(instrument, request)
            # Pre-Trade-Kostentor: reale Roundturn-Kosten unter der Backtest-Schwelle?
            self._enforce_cost_gate(instrument, request)
            # Sperren 2 bis 5 von 5: Kill-Switch (risk/limits.py), Drossel
            # (gates/evaluation.py), Stop-Budget (risk/stop_budget.py) und
            # Positionsgroesse (risk/sizing.py) -- alle vier ueber den einen
            # Aggregator, kontounabhaengig.
            self._enforce_risk(instrument, request, effective_leverage)
            # Doppelorder-Riegel. Steht NACH den fuenf Sperren, weil er keine von
            # ihnen ist: er fragt nicht, ob diese Order erlaubt waere, sondern ob es
            # sie schon gibt. Begruendung an der Methode.
            self._verhindere_doppelte_eroeffnung(request)

        try:
            send = self._terminal.order_send(self._to_terminal_request(request))
        except Exception as exc:
            # E10.4: Ein Sendeversuch, der mit einer AUSNAHME endet, hat kein Ergebnis
            # -- und "kein Ergebnis" ist nicht dasselbe wie "nichts geschehen". Ein
            # Zeitablauf, ein weggebrochenes Terminal, ein Absturz zwischen Senden und
            # Antwort: in all diesen Faellen kann beim Broker eine echte Order liegen,
            # von der dieser Prozess nichts weiss. Das Buch ist ab hier unbelegt.
            #
            # Fail-closed heisst hier: Global-Halt latchen (keine weitere Eroeffnung,
            # Reduce-Only bleibt frei) und die Kennung als unklar vermerken, damit der
            # Betrieb weiss, WELCHE Order von Hand nachzusehen ist. Der Fehler wird
            # unveraendert weitergereicht -- der Aufrufer darf nicht glauben, es sei
            # nichts passiert.
            #
            # Bewusst jede Ausnahme, nicht nur ``VenueError``: aus Sicht des Venues ist
            # ``terminal.order_send`` eine geschlossene Kiste. Welche Ausnahme sie
            # wirft, sagt nichts darueber, wie weit sie vorher gekommen ist. Der Preis
            # ist ein Fehlalarm bei Ausgaengen, die nachweislich nichts gesendet haben
            # (etwa ein gesperrter Schreibpfad); ein Halt zu viel ist geraeuschvoll,
            # ein Halt zu wenig ist eine unbemerkte Position.
            grund = f"{type(exc).__name__}: {exc}"
            self._unklare_sendeversuche[request.client_order_id] = grund
            # Und auf die Platte, sofort: der Zustand entsteht genau in dem Augenblick,
            # in dem auch der Prozess wegbrechen kann.
            self._schwebeakte.vermerken(
                SchwebenderAuftrag(
                    client_order_id=request.client_order_id,
                    grund=grund,
                    seit=self._clock(),
                    symbol=request.symbol,
                )
            )
            self._halted = True
            self._halt_reason = f"sendeversuch_unklar:{request.client_order_id}"
            raise
        if send.idempotent_replay:
            # Der Handelsplatz kennt diese Kennung bereits (Marke am Broker, siehe
            # ``RealMt5Terminal._bereits_beim_broker``): der Auftrag ist NICHT ein
            # zweites Mal gesendet worden. Genau wie beim Wiedergaenger aus
            # ``self._results`` wird hier nichts gebucht und nichts gezaehlt -- was
            # damals gefuellt wurde, gehoert nicht ein zweites Mal ins Buch. Die
            # autoritative Wiederherstellung nach einem Neustart ist ``adopt_book()``;
            # ein Buch, das zu wenig fuehrt, faellt im naechsten ``reconcile()`` laut
            # auf, ein doppelt gebuchtes waere still falsch.
            wiedergaenger = OrderResult(
                client_order_id=request.client_order_id,
                venue_order_id=send.venue_order_id,
                accepted=True,
                filled_volume=Decimal("0"),
                average_price=None,
                ts=send.ts,
                idempotent_replay=True,
                raw=send.raw,
            )
            self._results[request.client_order_id] = wiedergaenger
            self._unklare_sendeversuche.pop(request.client_order_id, None)
            return wiedergaenger
        if not send.accepted:
            raise OrderRejectedError(
                f"Handelsplatz hat abgelehnt: {send.reason}",
                reason=send.reason or "rejected",
                retryable=send.retryable,
            )
        result = OrderResult(
            client_order_id=request.client_order_id,
            venue_order_id=send.venue_order_id,
            accepted=True,
            filled_volume=send.filled_volume,
            average_price=send.average_price,
            ts=send.ts,
            idempotent_replay=False,
            raw=send.raw,
        )
        self._results[request.client_order_id] = result
        # Der Broker hat geantwortet -- die Kennung ist nicht mehr unklar.
        self._unklare_sendeversuche.pop(request.client_order_id, None)
        # ``pre_net`` (oben, vor jeder Buchung erfasst) + dieser Fill ergibt den
        # resultierenden Netto-Stand -- stromunabhaengig (das lokale Buch wird nur ohne
        # Strom hier mutiert; mit Strom bucht der nachlaufende private Fill).
        #
        # ``send.filled_volume`` ist bei einer angenommenen, aber nur ANGELEGTEN Order
        # (``TRADE_RETCODE_PLACED``) null -- und dann bucht dieser Aufruf richtigerweise
        # nichts. Frueher stand hier das Anfragevolumen: das Buch fuehrte eine Position,
        # die es beim Broker nicht gab, und der naechste ``reconcile()`` latchte dafuer
        # den Global-Halt.
        if self._sync is None:
            # Ohne Strom optimistisch buchen; mit Strom bucht der autoritative Fill.
            self._book.apply_fill(request.symbol, request.side, send.filled_volume)
        # Akzeptierten Fill an die Risikoschicht melden. Kontounabhaengig: die
        # Zaehler der Drossel und der Positionsdeckel muessen auch auf Demo stimmen,
        # sonst prueft die Sperre dort gegen einen leeren Zustand.
        #
        # Gemeldet wird die ANNAHME, nicht die Fuellung -- auch eine nur angelegte
        # Pending-Order zaehlt gegen Drossel und Positionsdeckel. Sie kann jederzeit
        # fuellen, und wenn sie es tut, laeuft keine Sperre mehr. Der Zaehler kann
        # dadurch zu hoch stehen (eine stornierte Pending-Order gibt ihren Platz nicht
        # zurueck); das sperrt haeufiger als noetig und ist die einzige Richtung, in
        # der ein Zaehlfehler hier ungefaehrlich ist.
        if self._risk_manager is not None:
            if not is_reducing:
                # Eroeffnung: Frequenz-Zaehler + offene Position fortschreiben.
                self._risk_manager.record_open_fill(request.symbol, send.ts)
            else:
                signed_fill = (
                    send.filled_volume
                    if request.side is OrderSide.BUY
                    else -send.filled_volume
                )
                if pre_net + signed_fill == 0:
                    # Schliessung, die das Symbol netto glattstellt -> Deckel frei.
                    # pre_net + Fill statt book.net(): stromunabhaengig korrekt.
                    self._risk_manager.record_close(request.symbol)
        return result

    def _verhindere_doppelte_eroeffnung(self, request: OrderRequest) -> None:
        """Steht die gewollte Position beim Broker schon? Dann wird nicht eroeffnet.

        **Warum es diesen Riegel zusaetzlich zur Kennmarke braucht.** Die Idempotenz
        am Broker (E10.4, :func:`kennmarke`) erkennt eine Wiederholung an der
        ``client_order_id``: gleiche Kennung -> gleiche Marke -> der Auftrag wird im
        Bestand gefunden und nicht ein zweites Mal gesendet. Das traegt genau so weit,
        wie der Aufrufer dieselbe Kennung noch einmal schickt. Der eroeffnende Treiber
        tut das nie: ``tools/live_betrieb.py`` baut
        ``f"open-{symbol}-{uuid.uuid4().hex[:10]}"`` und leitet nach einem Zeitablauf,
        einem Neustart oder in einem zweiten Runner den Willen neu ab -- mit neuer
        Zufallskennung, neuer Marke, und die Abfrage findet nichts. Gemessen, nicht
        geschlossen: zwei Sendeversuche derselben Absicht mit uuid-Kennungen erzeugten
        zwei echte Orders (``tests/test_idempotenz_am_broker.py::
        test_zweiter_versuch_mit_neuer_zufallskennung_eroeffnet_nicht_doppelt``).

        Ein Idempotenzschutz, der nur im Test greift, ist gefaehrlicher als keiner --
        man verlaesst sich auf ihn. Also wird hier nach dem gefragt, was der Aufrufer
        **nicht** neu wuerfeln kann: dem Zustand beim Broker. Eine eroeffnende Order
        in ein Symbol, in dem bereits eine **gleichgerichtete** Position steht, ist
        fuer dieses System nie gewollt. Es fuehrt netto eine Position je Symbol
        (``RiskManager.record_open_fill`` zaehlt je Symbol einmal, der Live-Treiber
        ueberspringt jedes Symbol mit offener Position), es baut keine Pyramide auf,
        und es hat keinen Pfad, der eine bestehende Position vergroessert.

        Massgeblich ist ``get_positions()``, also eine frische Broker-Abfrage --
        dieselbe Quelle wie in :meth:`_reduces_position` und aus demselben Grund: das
        lokale Buch ist nach einem Neustart leer, und leer waere hier die schmeichelnde
        Antwort.

        **Was der Riegel NICHT faengt** -- ausdruecklich, damit sich niemand mehr
        darauf verlaesst als er traegt:

        * Eine liegende, noch nicht ausgefuehrte Pending-Order. Sie steht in
          ``orders_get``, nicht in ``positions_get``, und der Vertrag
          :class:`Mt5Terminal` kennt keine Auftragsliste. Der Live-Treiber sendet
          ausschliesslich Marktorders; fuer den Limit-Pfad bleibt die Luecke offen und
          ist in ``tests/test_idempotenz_am_broker.py`` festgenagelt.
        * Eine Wiederholung, deren erster Versuch den Broker nie erreicht hat. Dann
          ist auch nichts doppelt -- der Riegel soll dort gar nicht greifen.
        * Zwei Runner, die im selben Augenblick senden. Zwischen Abfrage und Senden
          liegt ein Umlauf; das ist ein Wettlauf, den nur der Broker selbst
          entscheiden kann.

        **Die Gegenrichtung, damit der Riegel keine Dauerbremse wird:** er greift nur
        bei gleicher Seite. Eine Gegenorder (Flip, Absicherung) laeuft weiter durch
        alle Tore, und Reduce-Only erreicht diese Stelle gar nicht erst -- Risikoabbau
        darf nie an einer Sperre haengen. Im gesunden Betrieb loest er nicht aus, weil
        der Aufrufer solche Symbole ohnehin ueberspringt; er ist eine Sicherung, kein
        Filter. Genau dadurch ist sein Ausloesen ein Alarm: es heisst, dass der
        Aufrufer eine Position nicht kannte, die es gibt.

        **Der zweite Aufrufer, damit die Wirkung vollstaendig benannt ist:**
        ``venue/smoke.py`` eroeffnet in der Schreib-Probe eine winzige BUY-Order auf dem
        Probesymbol. Steht dort schon ein Long -- der Live-Treiber faehrt auf demselben
        Demokonto, und ein gescheiterter ``smoke-close`` hinterlaesst genau das --,
        lehnt dieser Riegel die Probe ab. Die Schreib-Probe ist damit nur auf einem in
        diesem Symbol glattgestellten Konto durchfuehrbar. Die Richtung ist sicher, und
        die Harness sagt es jetzt vorher statt hinterher (``_write_probe``).
        """
        gleichgerichtet = tuple(
            pos
            for pos in self.get_positions()
            if pos.symbol == request.symbol and pos.side is request.side
        )
        if not gleichgerichtet:
            return
        tickets = ", ".join(pos.venue_position_id for pos in gleichgerichtet)
        raise OrderRejectedError(
            f"{request.symbol}: es steht bereits eine gleichgerichtete Position beim "
            f"Broker ({request.side.value}, Ticket {tickets}). Eine eroeffnende Order "
            "waere eine zweite Position auf dieselbe Absicht -- der haeufigste Weg zu "
            "einer Doppelorder ist eine neu gewuerfelte Kennung nach Zeitablauf oder "
            "Neustart. Abbau (reduce_only) bleibt frei.",
            reason="doppelte_eroeffnung",
            retryable=False,
        )

    def _reduces_position(self, request: OrderRequest) -> bool:
        """Baut die Order eine offene Gegenposition ab, OHNE sie zu ueberschreiten?

        Massgeblich ist **ausschliesslich** die autoritative Boersen-Gegenposition:
        ``get_positions()`` ist ein frischer Broker-Query (unabhaengig vom Privatstrom)
        und spiegelt jeden Stand -- auch serverseitige SL/TP- und externe Schliessungen.
        Das lokale Netto-Buch wird BEWUSST NICHT herangezogen: es kann in beide
        Richtungen veralten (kein Close-Hook ohne Strom; stiller/nachhinkender Strom
        setzt ``desync`` nicht) und darf die Reduce-Autorisierung nie tragen -- sonst
        laesst ein stale-hohes Buch einen Over-Fill/Flip an den Toren + Halt vorbei
        (§9-Fix-Re-Check). ``reduce_only`` ueberspringt die Tore nur, wenn das Volumen
        die Gegenposition nicht reisst (hedging-faehig: Summe der Gegen-Tickets). Nur
        fuer ``reduce_only``-Orders gerufen.
        """
        opposite = sum(
            (
                pos.volume
                for pos in self.get_positions()
                if pos.symbol == request.symbol and pos.side is not request.side
            ),
            Decimal("0"),
        )
        # opposite > 0: Gegenposition da; volume <= opposite: kein Flip/Over-Fill.
        return opposite > 0 and request.volume <= opposite

    def _enforce_account_freshness(self, symbol: str) -> None:
        """Frische-Latch (S2) fuer eine eroeffnende Order -- auf JEDEM Konto.

        Erste der fuenf Sperren aus A3.2. Ein Zustand, dessen Alter die Frist reisst,
        ist nicht bewertbar; nicht bewertbar gilt als nicht erfuellt. Ohne diese Sperre
        rechnen Tagesverlustdeckel, Drawdown-Halt und Positionsgroesse auf Zahlen, die
        aussehen wie Messwerte und keine sind.

        **Gemessen wird der Kursstempel des Brokers, nicht der Kontoschnappschuss.**
        Das ist der Kern dieser Sperre, und die erste Fassung hatte ihn falsch herum:

        * MetaTrader liefert ueberhaupt keinen Kontozeitstempel.
          ``RealMt5Terminal.account`` setzt ``ts`` in genau diesem Aufruf selbst auf
          ``datetime.now(UTC)``. Wer den so entstandenen Stempel gegen
          ``self._clock()`` haelt, misst die eigene Uhr gegen die eigene Uhr: das
          Alter ist per Konstruktion ein paar Mikrosekunden, die Frist betraegt fuenf
          Sekunden. Die Sperre konnte nicht ausloesen -- und hat es in 21
          Betriebsjournalen kein einziges Mal getan, kein einziges ``snapshot_stale``.
        * Der Kursstempel kommt von der anderen Seite der Leitung. Er ist das einzige
          Lebenszeichen im System, das nicht im eigenen Prozess entsteht, und damit
          das einzige, an dem sich ein haengendes Terminal ueberhaupt zeigen kann.

        Genau diese Umstellung ist in ``tools/oberflaeche.py`` (geloescht, E-009)
        (Kachel "Kursfrische")
        und ``tools/live_konsole.py`` bereits gefahren und dort begruendet; hier steht
        dieselbe Messung an der Stelle, an der sie eine Order **stoppt**, statt sie
        nur anzuzeigen.

        Gemessen wird der Stempel **des zu handelnden Symbols**, nicht irgendeiner.
        Ein frischer EURUSD-Tick sagt nichts ueber einen eingefrorenen XAUUSD-Strom,
        und alle folgenden Sperren (Hebel, Kostentor, Groesse) rechnen mit dem Preis
        genau dieses Symbols.

        Kein Kurs = kein Stempel = nicht bewertbar. Auch das ist eine Ablehnung, kein
        stilles Durchwinken.

        Bewusst **nicht** demofrei: ein veralteter Kurs ist auf dem Demokonto genauso
        wenig bewertbar wie auf dem Livekonto, und das Demokonto ist der Ort, an dem
        sich die Sperre beweisen muss.

        Nebenwirkung, die keine ist: ohne konfigurierte Serverzone
        (``RealMt5Terminal(server_tz=...)``) tragen die Kursstempel die Wanduhr des
        Servers unter dem Etikett UTC. Der Vergleich gegen echte UTC hat dann den
        vollen Serverversatz drin, und die Sperre steht dauerhaft rot -- je nach
        Richtung des Versatzes als ``snapshot_from_future`` oder als
        ``snapshot_stale``. Das ist richtig so: wer den Versatz nicht kennt, kann das
        Alter nicht messen, und nicht messbar heisst nicht bewertbar.

        Hier stand "alle drei realen Aufrufer setzen die Zone". Es sind **vier**, und
        der vierte setzt sie nicht: ``tools/mt5_smoke.py`` baut sein
        ``RealMt5Terminal`` ohne ``server_tz`` und faehrt darueber ``run_smoke`` ->
        ``_write_probe`` -> ``submit_order``. Bei einem Server vor UTC (gemessene Zone
        ``Europe/Helsinki``, im Sommer UTC+3) kommt der Tick drei Stunden in der
        Zukunft heraus, und diese Sperre steht dort dauerhaft rot. Die Schreibprobe
        des Rauchtests -- also genau das Tor, das ``RealMt5Terminal._require_write``
        als Vorbedingung fuer ``allow_write`` nennt -- ist damit nicht durchfuehrbar,
        bis ``tools/mt5_smoke.py`` die Zone mitgibt. Die Fehlrichtung ist sicher
        (fail-closed), die Freigabeprozedur ist es nicht mehr. ``tools/`` gehoert
        nicht zu dieser Datei; der Satz steht hier, damit der naechste Eingriff die
        Stelle findet statt eine falsche Zusicherung zu lesen. Zone gesetzt:
        ``tools/live_betrieb.py``, ``tools/live_konsole.py``, ``tools/oberflaeche.py``
        (geloescht, E-009).
        """
        tick = self._terminal.tick(symbol)
        if tick is None:
            raise OrderRejectedError(
                f"Kein Kursstempel fuer {symbol} -- Frische nicht bewertbar",
                reason="no_market_stamp",
                retryable=True,
            )
        verdict = evaluate_account_freshness(
            snapshot_ts=tick.ts,
            now=self._clock(),
            connected=self._terminal.is_connected(),
            max_age=self._max_account_age,
        )
        if not verdict.evaluable:
            raise OrderRejectedError(
                f"Kurslage nicht bewertbar: {verdict.reason} "
                f"(Alter {verdict.age}, Frist {verdict.max_age})",
                reason=verdict.reason or "market_state_unevaluable",
                retryable=True,
            )

    def _require_live_release_for_opening(self) -> None:
        account = self._konto_pflicht()
        if account.is_demo:
            return  # Demokonto: keine Live-Freigabe noetig.
        blocked = live_release_blocks_opening_order(self._settings, reduce_only=False)
        if blocked is not None:
            raise OrderRejectedError(
                "Live-Freigabe unvollstaendig — eroeffnende Order blockiert",
                reason=blocked.reason or "live_release_incomplete",
                retryable=False,
            )
        # Demo-Reife-Tor (Paket 5): keine Live-Eroeffnung vor >= 180 Tagen Demo-Betrieb
        # mit weiter bestandenem Edge. Gerechnet, nicht entgegengenommen.
        self._require_demo_maturity(account)

    def _require_demo_maturity(self, account: Mt5Account) -> None:
        """Demo-Reife-Tor: rechnet das Urteil hier, aus Beleg und eigener Uhr.

        Bis hierher nahm der Konstruktor ein fertiges ``DemoReadiness`` entgegen und
        das Tor las nur dessen Ja/Nein. Damit war das 180-Tage-Tor mit einer Zeile
        (``DemoReadiness(True, ())``) auf, ohne dass irgendwo Zeit vergangen waere --
        derselbe Fehler, den ``venue/demo_run.py`` fuer ``elapsed_days`` beschreibt,
        nur eine Ebene hoeher. Jetzt bekommt der Konstruktor die **Registrierung**
        (ein Datum, kein Urteil) und den im Demo gemessenen Edge; die Frist rechnet
        ``pruefe_demo_beleg`` gegen ``self._clock`` -- die Uhr des Tores.

        Warum hier nicht ``evaluate_demo_progress`` steht (die Fassung mit
        Kontoabgleich): diese Methode laeuft ausschliesslich auf einem **Live**-Konto
        -- ``_require_live_release_for_opening`` kehrt auf einem Demokonto vorher um.
        Das beobachtete Konto ist hier also nie ein Demokonto, und der Abgleich haette
        bei jeder Eingabe ``beobachtetes_konto_ist_kein_demokonto`` gemeldet: eine
        Sperre, die immer ausloest, ist so wenig ein Melder wie eine, die nie ausloest.
        Der Kontoabgleich gehoert dorthin, wo das Demokonto wirklich gelesen wird
        (``venue/smoke.py``).

        Was sich **hier** unabhaengig pruefen laesst, wird hier geprueft: ein
        Demo-Beleg, der die Nummer eben dieses Livekontos traegt, ist ein Widerspruch
        in sich (dieses Konto ist kein Demokonto) und der naechstliegende Griff, wenn
        jemand einen Beleg passend machen will. Er wird abgelehnt, statt ihn zu glauben.

        **Was dieser Vergleich nicht ist: eine Kontobindung.** Er stellt einen einzigen
        String gegen einen einzigen String und faellt bei jeder anderen Kontonummer
        stillschweigend durch -- ``account_id="irgendeine-nummer"`` kommt hier vorbei.
        Es ist ein Widerspruchstest gegen einen Wert, keine Ortsaussage. Eine echte
        Bindung braeuchte eine Sicht auf das Demokonto, und die gibt es an dieser Stelle
        strukturell nicht (siehe ``venue/demo_run.py``, "DIE GRENZE DIESER STUFE").
        """
        registration = self._demo_registration
        live_verdict = self._demo_live_verdict
        if registration is None or live_verdict is None:
            fehlend = tuple(
                name
                for name, beleg in (
                    ("demo_registrierung_fehlt", registration),
                    ("demo_edge_im_demo_fehlt", live_verdict),
                )
                if beleg is None
            )
            raise OrderRejectedError(
                f"Demo-Reife nicht belegt: {', '.join(fehlend)}",
                reason="demo_not_ready",
                retryable=False,
            )
        beleg_konto = registration.account.account_id.strip()
        if beleg_konto and beleg_konto == account.account_id.strip():
            raise OrderRejectedError(
                "Demo-Reife nicht belegt: demo_beleg_nennt_das_livekonto "
                f"({account.account_id})",
                reason="demo_not_ready",
                retryable=False,
            )
        ready = pruefe_demo_beleg(
            registration=registration,
            live_verdict=live_verdict,
            clock=self._clock,
        )
        if not ready.ready_for_live_question:
            raise OrderRejectedError(
                f"Demo-Reife nicht belegt: {', '.join(ready.reasons)}",
                reason="demo_not_ready",
                retryable=False,
            )

    def _enforce_leverage(self, instrument: Instrument, request: OrderRequest) -> int:
        """Hebelklammer am Order-Pfad. Gibt den effektiven Hebel zurueck (fuer die
        Risikoschicht, die das Stop-Budget je Hebel berechnet)."""
        raw_tick = self._terminal.tick(request.symbol)
        if raw_tick is None:
            raise OrderRejectedError(
                "Kein Preis fuer Hebelpruefung", reason="no_tick", retryable=True
            )
        price = raw_tick.ask if request.side is OrderSide.BUY else raw_tick.bid
        preflight = evaluate_leverage_preflight(
            instrument=instrument,
            request=request,
            account=self.get_account(),
            price=price,
            requested_leverage=request.meta.get("requested_leverage"),
        )
        if not preflight.approved or preflight.effective_leverage is None:
            raise OrderRejectedError(
                f"Hebel-Anschluss abgelehnt: {preflight.reason}",
                reason=preflight.reason or "leverage_rejected",
                retryable=False,
            )
        return preflight.effective_leverage

    def _enforce_cost_gate(self, instrument: Instrument, request: OrderRequest) -> None:
        """Pre-Trade-Kostentor fuer eine eroeffnende Order (Live-Pflicht, Demo-frei).

        Auf Demo entfaellt es (kein Echtgeld) -- wie die Live-Freigabe. Auf Live ohne
        konfiguriertes Tor wird fail-closed abgelehnt: eine Order, deren Kosten nie
        gegen die Backtest-Annahme geprueft wurden, darf nicht eroeffnen.
        """
        if self._konto_pflicht().is_demo:
            return  # Demokonto: keine Live-Kostenpruefung noetig.
        if self._cost_gate is None:
            raise OrderRejectedError(
                "Kein Pre-Trade-Kostentor konfiguriert -- Live-Eroeffnung blockiert",
                reason="cost_gate_unconfigured",
                retryable=False,
            )
        raw_tick = self._terminal.tick(request.symbol)
        if raw_tick is None:
            raise OrderRejectedError(
                "Kein Preis fuer das Kostentor", reason="no_tick", retryable=True
            )
        entry = self._catalog[request.symbol]  # in get_instrument bereits validiert
        decision = evaluate_cost_gate(
            gate=self._cost_gate,
            instrument=instrument,
            fees=entry.fees,
            side=request.side,
            volume=request.volume,
            bid=raw_tick.bid,
            ask=raw_tick.ask,
        )
        if not decision.approved:
            suffix = f" ({decision.detail})" if decision.detail else ""
            raise OrderRejectedError(
                f"Kostentor abgelehnt: {decision.reason}{suffix}",
                reason=decision.reason or "cost_gate",
                retryable=False,
            )

    def _enforce_risk(
        self, instrument: Instrument, request: OrderRequest, leverage: int
    ) -> None:
        """Risikoschicht fuer eine eroeffnende Order — auf JEDEM Konto Pflicht.

        Sperren 2 bis 5 der fuenf aus A3.2, gefahren ueber ``RiskManager``:
        ``risk/limits.py`` (Kill-Switch), ``gates/evaluation.py`` (Drossel),
        ``risk/stop_budget.py`` (Budgetspanne) und ``risk/sizing.py`` (Groesse).

        **Kein Demo-Ausstieg** (Paket 2, A3): bis hierher lief die Risikoschicht nur
        am Live-Konto und damit an keinem einzigen real erreichbaren Konto — sie war
        formal verdrahtet und praktisch tot. Genau diese Fehlerklasse (eine Sperre,
        die nie laeuft) schliesst dieses Paket.

        Ohne konfigurierten Risiko-Manager wird fail-closed abgelehnt. Ein
        Drawdown-Halt aus ``evaluate_limits`` setzt den ``_halted``-Latch (loest sich
        nicht von selbst).
        """
        account = self._konto_pflicht()
        if self._risk_manager is None:
            raise OrderRejectedError(
                "Kein Risiko-Manager konfiguriert -- Live-Eroeffnung blockiert",
                reason="risk_unconfigured",
                retryable=False,
            )
        raw_tick = self._terminal.tick(request.symbol)
        if raw_tick is None:
            raise OrderRejectedError(
                "Kein Preis fuer die Risikopruefung", reason="no_tick", retryable=True
            )
        price = raw_tick.ask if request.side is OrderSide.BUY else raw_tick.bid
        mid = (raw_tick.ask + raw_tick.bid) / Decimal("2")
        spread_bps = (
            (raw_tick.ask - raw_tick.bid) / mid * Decimal("10000")
            if mid > 0
            else Decimal("0")
        )
        auth = self._risk_manager.authorize_opening(
            instrument=instrument,
            request=request,
            account=self.get_account(),
            price=price,
            spread_bps=spread_bps,
            leverage=leverage,
            now=account.ts,
        )
        if not auth.approved:
            if auth.latch_halt:
                # Drawdown-Halt: Latch setzen. Loest nur ``clear_halt`` + Freigabe.
                self._halted = True
                self._halt_reason = auth.reason or "risk_drawdown_halt"
            raise OrderRejectedError(
                f"Risiko-Tor abgelehnt: {auth.reason}",
                reason=auth.reason or "risk_rejected",
                retryable=False,
            )

    def _validate_volume(self, instrument: Instrument, volume: Decimal) -> None:
        if volume < instrument.volume_min:
            raise OrderRejectedError(
                f"Volumen {volume} unter Minimum {instrument.volume_min}",
                reason="volume_below_min",
                retryable=False,
            )
        if instrument.volume_max is not None and volume > instrument.volume_max:
            raise OrderRejectedError(
                f"Volumen {volume} ueber Maximum {instrument.volume_max}",
                reason="volume_above_max",
                retryable=False,
            )
        step = instrument.volume_step
        if step > 0:
            steps = (volume - instrument.volume_min) / step
            if steps != steps.to_integral_value():
                raise OrderRejectedError(
                    f"Volumen {volume} nicht auf Schrittweite {step}",
                    reason="volume_off_step",
                    retryable=False,
                )

    def _to_terminal_request(self, request: OrderRequest) -> dict[str, Any]:
        return {
            "client_order_id": request.client_order_id,
            "symbol": request.symbol,
            "side": request.side.value,
            "order_type": request.order_type.value,
            "volume": request.volume,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
            "limit_price": request.limit_price,
            "reduce_only": request.reduce_only,
            "comment": request.comment,
        }

    def cancel_order(self, client_order_id: str) -> bool:
        self._require_healthy()
        result = self._results.get(client_order_id)
        if result is None or result.venue_order_id is None:
            return False
        return self._terminal.cancel(result.venue_order_id)

    def modify_position_stops(
        self,
        venue_position_id: str,
        *,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        self._require_healthy()
        return self._terminal.modify_stops(venue_position_id, stop_loss, take_profit)

    # --- Zustand ----------------------------------------------------------
    def get_positions(self) -> tuple[Position, ...]:
        self._require_healthy()
        return tuple(
            Position(
                venue_position_id=pos.ticket,
                symbol=pos.symbol,
                side=OrderSide.BUY if pos.is_buy else OrderSide.SELL,
                volume=pos.volume,
                entry_price=pos.entry_price,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                opened_at=pos.opened_at,
                unrealised_pnl=pos.unrealised_pnl,
                swap_accrued=pos.swap,
            )
            for pos in self._terminal.positions()
        )

    def _konto_pflicht(self) -> Mt5Account:
        """Der Kontoschnappschuss fuer den Orderpfad -- vollstaendig oder Ablehnung.

        Die eine Lesestelle, durch die jede eroeffnende Order geht. Sie ersetzt nichts
        und faellt auf nichts zurueck: fehlt eine Pflichtzahl, endet die Order hier mit
        einem Grund (V3, Abnahme der Stufe 4).

        **Nicht** auf dem reduzierenden Pfad: der braucht den Kontostand gar nicht, und
        nach V5 blockiert ihn ohnehin keine Sperre. Eine Kontopruefung dort waere eine
        Sperre auf dem Abbau -- genau das, was der Auftrag verbietet.
        """
        acc = self._terminal.account()
        mangel = konto_maengel(acc)
        if mangel is not None:
            raise OrderRejectedError(
                f"Kontostand nicht bewertbar: {mangel}",
                reason="account_unevaluable",
                # Wiederholbar: ein fehlender Schnappschuss ist in aller Regel eine
                # abgerissene Terminalsitzung, kein dauerhaft ungueltiger Auftrag.
                retryable=True,
            )
        return acc

    def get_account(self) -> AccountState:
        self._require_healthy()
        acc = self._terminal.account()
        mangel = konto_maengel(acc)
        if mangel is not None:
            # Lesende Abfrage: hier gibt es keine Order, die abgelehnt werden koennte.
            # Ein unvollstaendiger Schnappschuss heisst, dass der Handelsplatz gerade
            # keine Auskunft gibt -- und genau das sagt ``VenueUnavailableError``.
            raise VenueUnavailableError(f"Kontostand nicht lesbar: {mangel}")
        return AccountState(
            account_id=acc.account_id,
            currency=acc.currency,
            balance=acc.balance,
            equity=acc.equity,
            margin_used=acc.margin_used,
            margin_free=acc.margin_free,
            is_demo=acc.is_demo,
            ts=acc.ts,
            leverage=acc.leverage,
        )

    # --- Order-Lebenszyklus / Reconcile -----------------------------------
    def book_snapshot(self) -> dict[str, Decimal]:
        """Das lokale Buch der Nettopositionen je Symbol."""
        return self._book.snapshot()

    def is_halted(self) -> bool:
        return self._halted

    def _verweigere_bei_schwebendem_auftrag(self) -> None:
        """Keine Eroeffnung, solange ein Sendeversuch ohne Antwort ungeklaert ist.

        Gelesen wird die **Akte**, nicht der Speicher dieses Prozesses: nach einem
        Neustart ist der Speicher leer, die Akte nicht. Genau dieser Fall ist der
        gefaehrliche -- der Prozess, der die Order abgesetzt hat, ist weg, und mit ihm
        das Wissen, dass beim Broker etwas liegen koennte.

        Ein unlesbarer Befund sperrt ebenfalls (``Schwebebefund.schwebt``): die Frage
        „schwebt etwas?" ist dann unbeantwortet, und unbeantwortet gilt als „ja".
        """
        befund = self._schwebeakte.laden()
        if not befund.schwebt:
            return
        kennungen = ", ".join(e.client_order_id for e in befund.eintraege) or "?"
        raise OrderRejectedError(
            "Ungeklaerter Sendeversuch -- beim Broker nachsehen und aufloesen: "
            f"{kennungen}" + (f" ({befund.sperrgrund})" if befund.sperrgrund else ""),
            reason="schwebender_auftrag",
            retryable=False,
        )

    def sendeversuch_aufloesen(self, client_order_id: str, *, befund: str) -> bool:
        """Nimm eine Kennung aus der Akte -- mit dem Befund vom Gegenueber.

        Die einzige Geste, die den Zustand beendet, und sie gehoert einem Menschen: der
        ``befund`` ist das, was beim Broker nachgesehen wurde. Ein leerer Befund wirft.

        Der Global-Halt bleibt davon **unberuehrt**. Das sind zwei Entscheidungen: „ich
        habe nachgesehen, was aus dieser Order wurde" und „ich gebe den Handel wieder
        frei". Sie faellt derselbe Mensch, aber nicht notwendig im selben Augenblick.
        """
        self._unklare_sendeversuche.pop(client_order_id, None)
        return self._schwebeakte.aufloesen(client_order_id, befund=befund)

    def schwebende_auftraege(self) -> tuple[SchwebenderAuftrag, ...]:
        """Der Arbeitszettel aus der Akte -- ueberdauert den Neustart."""
        return self._schwebeakte.laden().eintraege

    def unklare_sendeversuche(self) -> dict[str, str]:
        """Kennungen, deren Sendeversuch ohne Antwort endete -- Ausgang unbekannt.

        Sie sind der Arbeitszettel nach einem Zwischenfall: zu jeder dieser Kennungen
        kann beim Broker eine echte Order liegen. ``clear_halt()`` raeumt sie
        ausdruecklich **nicht** ab -- die Freigabe des Halts ist eine Entscheidung des
        Betreibers, das Nachsehen beim Broker eine andere.
        """
        return dict(self._unklare_sendeversuche)

    @property
    def halt_reason(self) -> str | None:
        """Grund des zuletzt via ``latch_halt`` gesetzten Halts (best-effort)."""
        return self._halt_reason

    @property
    def risk_manager(self) -> RiskManager | None:
        """Die verdrahtete Risikoschicht — lesbar, damit ein aufrufender Runner
        erkennt, ob er sich denselben Zustand teilt.

        Zwei getrennte ``RiskManager`` bedeuten zwei getrennte Frequenz- und
        Positionszaehler, von denen keiner das Ganze sieht. Wer denselben hier
        wiederfindet, darf den Fill **nicht** ein zweites Mal buchen.
        """
        return self._risk_manager

    @property
    def has_private_stream(self) -> bool:
        """Ist ein privater Kontostrom (``PrivateSync``) konfiguriert?"""
        return self._sync is not None

    @property
    def stream_last_event_ts(self) -> datetime | None:
        """Zeitstempel des letzten Stromereignisses; ``None`` ohne Strom oder bevor je
        eines ankam. Der Treiber-Loop schliesst darueber die S2-Kante: ``check_sync``/
        ``is_stale`` faengt Stille erst NACH dem ersten Ereignis -- ein nie gestarteter
        Strom bleibt sonst unbemerkt fail-open."""
        return self._sync.last_event_ts if self._sync is not None else None

    def latch_halt(self, *, reason: str) -> None:
        """Global-Halt von aussen setzen (Scheduler-S2-Frische-Latch, Drawdown-Halt).

        Symmetrisch zu ``clear_halt``. Idempotent und **fail-safe**: Halten ist immer
        die sichere Richtung. Der Treiber-Loop nutzt es, um einen nie gestarteten oder
        still gewordenen Strom zu latchen, den ``check_sync`` selbst nicht faengt
        (``is_stale`` ist blind, solange nie ein Ereignis kam). Klaert nur via
        ``clear_halt``.
        """
        self._halted = True
        self._halt_reason = reason

    def clear_halt(self) -> None:
        """Manuelle Freigabe nach aufgeloester Drift. Der Latch klaert nicht selbst."""
        self._halted = False
        self._halt_reason = None
        if self._sync is not None:
            self._sync.clear_desync()

    def reconcile(self) -> ReconcileResult:
        """Buch gegen Meldung; bei Drift ueber der Grenze Global-Halt setzen."""
        self._require_healthy()
        actual = positions_to_net(self.get_positions())
        expected = self._book.snapshot()
        notional_per_unit: dict[str, Decimal] = {}
        for symbol in set(expected) | set(actual):
            tick = self._terminal.tick(symbol)
            if tick is None:
                continue
            try:
                instrument = self.get_instrument(symbol)
            except UnknownInstrumentError:
                continue
            mid = (tick.bid + tick.ask) / Decimal("2")
            notional_per_unit[symbol] = instrument.contract_size * mid
        result = reconcile_positions(
            expected=expected,
            actual=actual,
            notional_per_unit=notional_per_unit,
            max_notional_drift=self._max_notional_drift,
        )
        if result.halt:
            self._halted = True
            self._halt_reason = f"reconcile_drift:{result.reason or 'drift'}"
        return result

    def adopt_book(self) -> dict[str, Decimal]:
        """Uebernimm die gemeldeten Positionen als Buch (bewusster Neustart-Schritt).

        Danach deckt sich das Buch mit der Meldung; ein folgender ``reconcile()`` findet
        keine Drift. Bewusst **nicht** automatisch in ``connect()`` — das wuerde
        unerwartete Positionen still uebernehmen. Der Halt-Latch bleibt unberuehrt; die
        Freigabe ist ein getrennter Schritt (``clear_halt()``).
        """
        self._require_healthy()
        self._book.adopt(positions_to_net(self.get_positions()))
        return self._book.snapshot()

    def apply_private_event(self, event: PrivateEvent) -> None:
        """Fuehre ein Kontoereignis ins Buch. Bei Desync (Luecke) Global-Halt."""
        if self._sync is None:
            raise VenueUnavailableError("Kein PrivateSync konfiguriert")
        self._sync.apply(event)
        if self._sync.desync:
            self._halted = True
            self._halt_reason = f"stream_desync:{self._sync.desync_reason or 'desync'}"

    def check_sync(self, now: datetime, *, max_silence: timedelta) -> bool:
        """Pruefe die Stromgesundheit; bei Stille/Desync Global-Halt setzen."""
        if self._sync is None:
            return True
        healthy = self._sync.healthy(now, max_silence)
        if not healthy:
            self._halted = True
            reason = self._sync.desync_reason or "stream_stale"
            self._halt_reason = f"check_sync:{reason}"
        return healthy

    def emergency_flatten(self) -> tuple[OrderResult, ...]:
        """Not-Aus: Global-Halt **und** alle offenen Positionen per Reduce-Only zu.

        Gibt die Schliess-Ergebnisse zurueck -- **oder wirft**. Genau das war der
        Befund E10.5: die alte Fassung fing jeden ``VenueError`` mit ``continue`` und
        gab nur die Erfolge zurueck. Fuer den Aufrufer sahen "alles glatt" und "nichts
        glatt" damit gleich aus, naemlich wie ein Tupel. Beim Not-Aus ist das die
        gefaehrlichste Fehlrichtung ueberhaupt: der Betrieb glaubt, das Risiko sei weg,
        waehrend die Positionen offen stehen. Ein unvollstaendiger Not-Aus ist deshalb
        keine Rueckgabe, sondern ein :class:`NotAusUnvollstaendig` -- mit der Liste
        dessen, was steht.

        **Zweiter Befund, dieselbe Stelle: die Kennung war stabil.** Sie lautete
        ``flatten-{ticket}``. Ein zweiter Not-Aus auf dieselbe Position traf damit den
        Wiedergaenger-Zweig in :meth:`submit_order`, **sendete nichts** und meldete
        trotzdem ``accepted=True``. Der zweite Griff zur Notbremse war eine Attrappe.
        Die Kennung traegt darum jetzt Uhrzeit und Laufnummer des Not-Aus
        (``fl-{sekunde}-{lauf}-{ticket}``): jeder Not-Aus-Lauf ist ein eigener Vorgang.

        Dass das hier richtig ist und nicht die Idempotenz aushebelt, haengt an
        Reduce-Only: :meth:`_reduces_position` misst die Gegenposition bei **jedem**
        Aufruf frisch am Broker und laesst nur ein Volumen durch, das sie nicht reisst.
        Ist bereits geschlossen, findet die Schleife keine Position mehr und sendet gar
        nichts. Ein Not-Aus kann sich also nicht ueberschliessen -- eine unterlassene
        Schliessung dagegen kostet Geld.

        **Der bestehende Halt-Grund wird nicht ueberschrieben.** Der haeufigste Weg zur
        Notbremse fuehrt ueber einen Zwischenfall, der bereits gelatcht hat -- etwa
        ``sendeversuch_unklar:open-EURUSD-x`` aus :meth:`submit_order`. Wer den Grund
        hier durch ``emergency_flatten`` ersetzt, loescht genau die Angabe, mit der der
        Betrieb hinterher beim Broker nachsieht. Der neue Grund steht darum vorn und der
        alte in Klammern dahinter (:func:`_halt_grund_fortschreiben`). Das ist Diagnose,
        nicht Sicherheit: der Latch selbst ist eine Zuweisung und steht in jedem Fall,
        und die Arbeitsliste ueberlebt zusaetzlich in :meth:`unklare_sendeversuche`.

        Der Halt wird **zuerst** gesetzt -- und zwar vor der Gesundheitspruefung, nicht
        nach ihr. Das war der dritte Fehler an dieser Stelle und der stillste: die
        Reihenfolge lautete ``_require_healthy()``, dann ``_halted = True``. Bricht die
        Leitung weg -- der wahrscheinlichste Zustand, in dem jemand ueberhaupt zur
        Notbremse greift --, warf die Methode, schloss nichts UND latchte nichts. Der
        Not-Aus liess das System im Zweifel offen, waehrend sein eigener Docstring das
        Gegenteil zusagte. Das Setzen des Latches ist eine reine Zuweisung auf ein Feld
        dieses Objekts; sie braucht keine Leitung, kann nicht scheitern und darf darum
        von nichts abhaengen. Die Gesundheitspruefung laeuft unmittelbar danach und
        wirft weiter -- der Aufrufer erfaehrt also nach wie vor, dass nichts geschlossen
        wurde. Er erfaehrt es nur nicht mehr auf einem System, das weiter eroeffnen
        darf. Festgenagelt in
        ``tests/test_notaus_wirkung.py::test_der_halt_steht_auch_ohne_leitung``.

        Scheitert eine Schliessung, bleiben neue Eroeffnungen trotzdem gesperrt.
        Reduce-Only umgeht bewusst Freigabe- und Hebel-Tore: Risikoabbau darf nie an
        einer Sperre haengen. Der Latch klaert nur ``clear_halt()``.

        **Woran der Erfolg gemessen wird:** nicht am Rueckgabecode, sondern am
        bestaetigten Volumen -- ``filled_volume`` jeder Schliessung muss die Position
        vollstaendig decken. Eine Teilfuellung ist ein unvollstaendiger Not-Aus. Ein
        erneutes ``get_positions()`` unmittelbar danach ist bewusst **nicht** das Mass:
        die Positionsliste des Brokers zieht der Ausfuehrung nach, ein Nachlesen in
        derselben Millisekunde meldete die eben geschlossene Position noch offen -- und
        ein Melder, der bei jedem gelungenen Not-Aus Alarm gibt, wird nach dem zweiten
        Mal ignoriert. Der Preis dieser Wahl steht unter "offen": eine Position, die
        trotz bestaetigter Fuellung offen bleibt (Hedging-Eigenheit), faellt erst im
        naechsten ``reconcile()`` auf.
        """
        # ZUERST der Latch, dann alles, was scheitern kann. Umgekehrt waere der
        # Not-Aus in genau dem Fall wirkungslos, fuer den es ihn gibt.
        self._halted = True
        self._halt_reason = _halt_grund_fortschreiben(
            self._halt_reason, "emergency_flatten"
        )
        self._require_healthy()
        self._flatten_laeufe += 1
        # Sekunde + Laufnummer: die Sekunde trennt zwei Laeufe ueber einen Neustart
        # hinweg (der Zaehler faengt dann wieder bei 1 an), die Laufnummer zwei Laeufe
        # innerhalb derselben Sekunde. Ohne die Sekunde koennte die Marke am Broker
        # (E10.4) einen Not-Aus nach einem Neustart als Wiederholung des vorigen lesen
        # und nichts senden -- ausgerechnet den Fall, fuer den es die Bremse gibt.
        lauf = f"{int(self._clock().timestamp())}-{self._flatten_laeufe}"
        results: list[OrderResult] = []
        offen: list[str] = []
        for position in self.get_positions():
            close_side = (
                OrderSide.SELL if position.side is OrderSide.BUY else OrderSide.BUY
            )
            try:
                ergebnis = self.submit_order(
                    OrderRequest(
                        client_order_id=f"fl-{lauf}-{position.venue_position_id}",
                        symbol=position.symbol,
                        side=close_side,
                        order_type=OrderType.MARKET,
                        volume=position.volume,
                        stop_loss=Decimal("0"),
                        reduce_only=True,
                        comment="emergency-flatten",
                    )
                )
            except Exception as exc:  # noqa: BLE001 - jeder Ausgang wird gemeldet
                # Eine gescheiterte Schliessung darf die uebrigen nicht verhindern --
                # aber sie darf auch nicht verschwinden. Beides: weitermachen UND
                # merken.
                offen.append(
                    f"{position.symbol}/{position.venue_position_id}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue
            results.append(ergebnis)
            if ergebnis.filled_volume < position.volume:
                offen.append(
                    f"{position.symbol}/{position.venue_position_id}: nur "
                    f"{ergebnis.filled_volume} von {position.volume} geschlossen "
                    f"(Auftrag {ergebnis.venue_order_id}, "
                    f"Wiedergaenger={ergebnis.idempotent_replay})"
                )
        if offen:
            raise NotAusUnvollstaendig(
                "Not-Aus unvollstaendig -- der Global-Halt steht, aber Risiko ist "
                f"offen: {'; '.join(offen)}",
                geschlossen=tuple(results),
                offen=tuple(offen),
            )
        return tuple(results)


def _erfolgscodes(mt5: Any) -> set[int]:
    """Die drei dokumentierten Codes, unter denen der Server NICHT abgelehnt hat.

    Getrennt gehalten, weil drei verschiedene Fragen sie brauchen (Annahme, Fuellung,
    Aenderung/Storno) und eine Kopie je Frage genau die Sorte Abweichung erzeugt, an
    der ``cancel`` und ``modify_stops`` zuletzt haengen geblieben sind.
    """
    return {
        int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)),
        int(getattr(mt5, "TRADE_RETCODE_PLACED", 10008)),
        int(getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)),
    }


def _ohne_fehlercode(mt5: Any, res: Any) -> bool:
    """Hat der Server ueberhaupt keinen Fehler gemeldet?

    Die halbe Auskunft, und bewusst nur die halbe: ein Erfolgscode (oder der an
    diesem Broker gemessene ``retcode=0``) sagt, dass die Anfrage durchging -- **nicht**
    was danach in der Welt steht. Wer daraus eine Wirkung ableiten will, braucht eine
    zweite Messung; siehe :func:`_send_gefuellt`, :meth:`RealMt5Terminal.cancel` und
    :meth:`RealMt5Terminal.modify_stops`.

    Warum ``retcode=0`` hier mitzaehlt, steht bei :func:`_send_angenommen`: an diesem
    Broker (gemessen 2026-08-17) ist 0 der Erfolgscode einer ausgefuehrten Order.
    """
    if res is None:
        return False
    code = int(getattr(res, "retcode", -1))
    return code == 0 or code in _erfolgscodes(mt5)


def _send_gefuellt(mt5: Any, res: Any) -> bool:
    """Wurde tatsaechlich etwas AUSGEFUEHRT -- oder nur eine Order angelegt?

    Der Unterschied ist keine Feinheit. ``TRADE_RETCODE_PLACED`` (10008) heisst
    woertlich "Order im System abgelegt": eine Pending-Order existiert beim Broker,
    ausgefuehrt ist nichts. ``res.volume`` spiegelt dabei das **Anfrage**volumen, nicht
    ein Fuellvolumen -- MetaTrader gibt dasselbe Feld fuer beides her.

    Bis hierher galt PLACED als Fill. Die Folge war die Spiegelung des Fehlers, den
    :func:`_send_angenommen` behebt: das lokale Buch fuehrte eine Position, die es beim
    Broker nicht gibt, der naechste ``reconcile()`` sah diese Geisterposition als Drift
    und latchte bei ``max_notional_drift=0`` den Global-Halt -- obwohl nichts
    schiefgelaufen war.

    Gefuellt heisst hier:

    * ``DONE`` oder ``DONE_PARTIAL`` mit Volumen groesser null -- der dokumentierte
      Fall. Bei ``DONE_PARTIAL`` ist ``res.volume`` der vom Broker bestaetigte
      Teil-Fill; genau der gehoert ins Buch, nicht das Wunschvolumen.
    * ``retcode == 0`` mit zugeteilter Order- oder Deal-Kennung **und** Volumen groesser
      null -- der an diesem Broker gemessene Erfolgsfall.

    ``PLACED`` ist ausdruecklich ausgeschlossen, auch mit Volumen und Kennung. Es ist
    der einzige Code, der Annahme und Ausfuehrung auseinanderfallen laesst, und genau
    deshalb steht er hier als eigene Zeile statt in einer Menge mit den anderen.
    """
    if res is None:
        return False
    if float(getattr(res, "volume", 0) or 0) <= 0:
        return False
    code = int(getattr(res, "retcode", -1))
    if code == int(getattr(mt5, "TRADE_RETCODE_PLACED", 10008)):
        return False  # angelegt, nicht ausgefuehrt -- der Kern dieser Funktion
    if code in {
        int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)),
        int(getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)),
    }:
        return True
    if code != 0:
        return False
    return bool(int(getattr(res, "order", 0) or 0) or int(getattr(res, "deal", 0) or 0))


def _send_angenommen(mt5: Any, res: Any) -> bool:
    """Hat der Handelsplatz die Order wirklich angenommen?

    Die Dokumentation nennt ``TRADE_RETCODE_DONE`` (10009). **Nicht jeder Server haelt
    sich daran.** Am hier gemessenen Broker liefert ein erfolgreicher ``order_send``
    ``retcode=0`` mit ``comment='Done'`` -- samt gueltiger Order-Kennung, Deal-Kennung,
    Volumen und Preis. Eine Pruefung allein auf 10009 haelt so eine ausgefuehrte Order
    fuer abgelehnt.

    Das ist die gefaehrlichste Fehlrichtung, die es hier gibt: die Position steht beim
    Broker, das System weiss nichts davon, das lokale Buch bleibt leer, der naechste
    Reconcile sieht Drift und latcht den Global-Halt. Genau das ist beim ersten
    scharfen Lauf passiert.

    Angenommen wird darum:

    * ein dokumentierter Erfolgscode (DONE, PLACED, DONE_PARTIAL), **oder**
    * ``retcode == 0`` **zusammen mit dem Beweis einer Ausfuehrung** -- einer
      zugeteilten Order- oder Deal-Kennung und einem Volumen groesser null.

    Die zweite Bedingung ist bewusst konjunktiv. Ein blosses „kein Fehlercode" genuegt
    nicht; es muss etwas zugeteilt worden sein.

    **Angenommen ist nicht gefuellt.** PLACED steht oben mit Recht: die Order existiert
    beim Broker und muss darum gebucht, wiedererkannt und stornierbar bleiben. Ob dabei
    etwas ausgefuehrt wurde, beantwortet :func:`_send_gefuellt` -- getrennt, weil es
    eine andere Frage ist.
    """
    if res is None:
        return False
    code = int(getattr(res, "retcode", -1))
    if code in _erfolgscodes(mt5):
        return True
    if code != 0:
        return False
    zugeteilt = int(getattr(res, "order", 0) or 0) or int(getattr(res, "deal", 0) or 0)
    volumen = float(getattr(res, "volume", 0) or 0)
    return bool(zugeteilt) and volumen > 0


#: Laenge, auf die MetaTrader den Auftragskommentar kuerzt. Der Kommentar ist die
#: **lesbare** Spur der Kennung; die belastbare traegt ``magic`` (siehe
#: :func:`kennmarke`). Manche Server ueberschreiben den Kommentar sogar ganz -- ein
#: Grund mehr, die Wiedererkennung nicht daran zu haengen.
MAX_KOMMENTAR = 31


def kennmarke(client_order_id: str) -> int:
    """Die Kennung des Auftraggebers als Zahl, die beim Broker liegen bleibt.

    E10.4: Die Idempotenz lag ausschliesslich in ``Mt5Venue._results``, also im
    Prozessgedaechtnis, und der Eintrag entstand erst NACH einer angenommenen Antwort.
    Am Auftrag selbst stand nichts -- weder ``magic`` noch die Kennung im Kommentar.
    Beim Broker lag damit **kein einziges Merkmal**, an dem eine Wiederholung zu
    erkennen gewesen waere. Ein Zeitablauf, ein Neustart oder ein zweiter Runner
    erzeugte eine zweite echte Order, und niemand konnte das hinterher entscheiden.

    ``magic`` ist das einzige Feld, das diese Reise ueberlebt: es geht mit dem Auftrag
    hin, steht danach an Order, Position und Deal, und kein Server schreibt es um.
    Dass es damit nicht mehr die uebliche Rolle "eine Zahl je Expert Advisor" spielen
    kann, ist der bewusste Preis: eine Zahl je EA beantwortet die Frage "war ICH das?",
    aber nicht "war das GENAU DIESER Auftrag?" -- und nur die zweite verhindert eine
    Doppelorder.

    Die Abbildung ist ein Blake2b-Digest auf 63 Bit (das oberste Bit bleibt frei, weil
    ``magic`` als vorzeichenlose 64-Bit-Zahl ueber mehrere Sprachgrenzen laeuft).
    Stabil ueber Prozesse und Laeufe hinweg -- ``hash()`` waere es nicht, das ist je
    Prozess gesalzen und haette genau im Neustartfall versagt, fuer den diese Marke
    gebaut ist. Die Null wird ausgeschlossen: ``magic=0`` ist der Normalfall jeder
    fremden, handgestellten Order und darf keine Kennung sein.

    **WAS DIE MARKE AM REALEN AUFRUFER LEISTET -- UND WAS NICHT.** Sie erkennt eine
    Wiederholung *derselben Kennung*. Ob es die je gibt, entscheidet der Aufrufer, und
    der einzige reale baut sie zufaellig: ``tools/live_betrieb.py`` bildet
    ``f"open-{symbol}-{uuid.uuid4().hex[:10]}"`` bzw. ``f"close-{symbol}-..."`` und
    leitet nach Zeitablauf, Neustart oder in einem zweiten Runner den Willen NEU ab --
    mit neuer Kennung und damit neuer Marke. Fuer ihn ist die Marke deshalb heute ein
    **Zuordnungsmerkmal** (welcher Auftrag steht da beim Broker?) und kein
    Doppelorder-Schutz. Beides ist wertvoll, aber es ist nicht dasselbe, und der
    Unterschied darf nicht im Docstring verschwinden.

    Zwei Dinge stehen dagegen:

    * Der Doppelorder-Schutz, der ohne Zutun des Aufrufers greift, sitzt eine Ebene
      hoeher: :meth:`Mt5Venue._verhindere_doppelte_eroeffnung` fragt den Broker nach
      einer bereits stehenden gleichgerichteten Position. Diese Frage ist an die
      Absicht gebunden, nicht an eine Zeichenkette.
    * Damit die Marke auch als Idempotenzschluessel traegt, muesste die Kennung aus
      der ABSICHT abgeleitet sein (Symbol + Signal + Kerzenstempel), nicht gewuerfelt.
      Das ist eine Zeile im Aufrufer und steht als Vertragsaussage in
      ``venue/protocol.py`` (``TradingVenue.submit_order``). Sie hier zu erraten geht
      nicht: Volumen und Stop werden bei jedem Versuch neu gerechnet, ein Hash ueber
      die Zahlen der Anfrage waere nach einem Neustart also ohnehin ein anderer.
    """
    roh = hashlib.blake2b(client_order_id.encode("utf-8"), digest_size=8).digest()
    wert = int.from_bytes(roh, "big") >> 1
    return wert or 1


def _fuellart(mt5: Any, symbol: str) -> int:
    """Die Ausfuehrungsart, die dieser Broker fuer DIESES Symbol anbietet.

    Hier lauern zwei verschiedene Bitbelegungen, die leicht verwechselt werden -- und
    die Verwechslung kostete jede Order:

    * ``symbol_info(...).filling_mode`` ist eine **Bitmaske**:
      1 = FOK, 2 = IOC, 4 = RETURN.
    * ``request["type_filling"]`` erwartet eine **Konstante**:
      ``ORDER_FILLING_FOK`` = 0, ``ORDER_FILLING_IOC`` = 1, ``RETURN`` = 2.

    Eine fest gesetzte Art trifft deshalb nur zufaellig. An diesem Broker melden
    EURUSD, GBPUSD, USDJPY und EURGBP die Maske 1 (nur FOK), US500 die Maske 2 (nur
    IOC) und XAUUSD die Maske 3 (beides). Ein fest gesetztes IOC laesst jede
    EURUSD-Order mit ``Unsupported filling mode`` auflaufen -- und zwar erst beim
    Senden, nachdem die ganze Risikokette gruen gerechnet hat.

    Bevorzugt wird **FOK**: ganz oder gar nicht. Eine Teilfuellung braucht eine
    Buchfuehrung, die dieses Repo nicht hat, und ein halb gefuellter Auftrag mit
    vollem Stop waere eine andere Position als die berechnete.
    """
    info = mt5.symbol_info(symbol)
    maske = int(getattr(info, "filling_mode", 0)) if info is not None else 0
    if maske & 1:
        return int(mt5.ORDER_FILLING_FOK)
    if maske & 2:
        return int(mt5.ORDER_FILLING_IOC)
    if maske & 4:
        return int(mt5.ORDER_FILLING_RETURN)
    raise VenueUnavailableError(
        f"{symbol}: der Broker meldet keine unterstuetzte Ausfuehrungsart "
        f"(filling_mode={maske}). Fail-closed statt raten."
    )


class RealMt5Terminal:
    """Duenne Bindung an das echte ``MetaTrader5``-Paket.

    Bewusst getrennt vom Adapter: die MT5→Rohwert-Abbildung braucht ein laufendes
    Terminal und ist **nicht** im Vertragstest abgedeckt (das kann sie nicht sein).
    Die sicherheitskritische Logik — das Live-Freigabe-Tor — sitzt im Adapter
    :class:`Mt5Venue` und greift unabhaengig davon, welches Terminal darunter liegt.

    ``MetaTrader5`` wird erst in :meth:`initialize` geladen; ist es nicht installiert,
    scheitert der Verbindungsaufbau laut, nicht der Import.
    """

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str | None = None,
        server: str | None = None,
        path: str | None = None,
        allow_write: bool = False,
        require_demo: bool = True,
        server_tz: str | None = None,
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        #: Zeitzone der Broker-Serverzeit, z. B. ``"Europe/Helsinki"``. Ist sie
        #: gesetzt, werden ALLE Zeitstempel dieses Terminals in echtes UTC gedreht.
        #: Ist sie ``None``, kommen sie so heraus, wie MetaTrader sie liefert: mit
        #: dem Etikett UTC, aber der Wanduhr des Servers.
        #:
        #: Warum das ueberhaupt eine Wahl ist: die Zone ist eine Eigenschaft des
        #: BROKERS und laesst sich nicht erraten. Sie muss gemessen werden (siehe
        #: archiv/ABSCHLUSS-3a/02-DATENLAGE.md). Ein fest verdrahteter Wert waere fuer
        #: jeden
        #: anderen Broker falsch, und falsch waere hier schlimmer als unbekannt.
        self._server_tz = ZoneInfo(server_tz) if server_tz else None
        #: Fail-closed: der Schreibpfad (Orders senden/aendern) ist gesperrt, bis er
        #: bewusst freigegeben wird — nach einem Smoke-Test gegen ein Demo-Terminal.
        self._allow_write = allow_write
        #: Zweite, kontobezogene Klammer (Paket 2, A3): ``order_send`` liegt UNTER dem
        #: Flaschenhals ``Mt5Venue.submit_order`` und ist oeffentlich aufrufbar — wer
        #: das Terminal direkt haelt, kaeme an allen fuenf Sperren vorbei. Der
        #: Schreibpfad des realen Terminals schreibt darum standardmaessig nur auf ein
        #: **Demokonto**. Ein Live-Schreibpfad ist eine bewusste, getrennte
        #: Konstruktionsentscheidung (``require_demo=False``) und aendert nichts daran,
        #: dass die Live-Freigabe im Venue trotzdem vollstaendig sein muss.
        self._require_demo = require_demo
        self._mt5: Any = None

    def initialize(self) -> bool:
        try:
            mt5: Any = importlib.import_module("MetaTrader5")
        except ImportError as exc:
            raise VenueUnavailableError(
                "MetaTrader5 nicht installiert (pip install MetaTrader5)"
            ) from exc
        self._mt5 = mt5
        kwargs: dict[str, Any] = {}
        if self._path is not None:
            kwargs["path"] = self._path
        if self._login is not None:
            kwargs["login"] = self._login
        if self._password is not None:
            kwargs["password"] = self._password
        if self._server is not None:
            kwargs["server"] = self._server
        return bool(mt5.initialize(**kwargs))

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    def is_connected(self) -> bool:
        """Drei Fragen, nicht eine -- und die erste Fassung stellte nur die erste.

        ``terminal_info() is not None`` beantwortet ausschliesslich: **laeuft der
        Prozess?** Ein MetaTrader, das offen auf dem Bildschirm steht, aber die
        Verbindung zum Handelsserver verloren hat, beantwortet sie mit ja. Genau
        dieser Zustand ist der gefaehrliche: das Terminal liefert weiter Zahlen, sie
        sind nur alt. Der Vertrag (``venue/protocol.py``, ``is_healthy``) verlangt Rot
        bei fehlendem Terminal ODER fehlender Sitzung; geprueft wurde davon nur der
        erste Fall. (Die frueher mitzitierte dritte Kante -- veraltete Daten -- steht
        nicht mehr in dieser Zusage: sie braucht ein Symbol und ist im Vertrag als
        getrennte Pflicht je Order gefuehrt. Siehe unten.)

        Hier stehen jetzt die beiden Fragen, die dieser Aufruf beantworten kann:

        1. **Laeuft ein Terminal?** ``terminal_info()``.
        2. **Steht die Leitung zum Handelsserver?** ``terminal_info().connected``.
           Das Feld ist genau dafuer da und wurde nirgends im Adapter gelesen.
        3. **Gibt es eine Kontositzung?** ``account_info()`` ist ``None``, solange
           kein Konto angemeldet ist -- und aus genau diesem Aufruf zieht die
           Risikoschicht Equity und freie Marge.

        Fehlt das Feld ``connected`` (fremde oder aeltere Bindung), gilt das als
        **nicht verbunden**. Fail-closed: eine unbeantwortbare Frage ist keine
        bestandene Pruefung.

        Die getrennt gefuehrte Vertragspflicht -- veraltete Daten -- laesst sich hier
        nicht beantworten: sie braucht einen Kursstempel je Symbol. Sie wird am
        Order-Pfad gestellt (``Mt5Venue._enforce_account_freshness``) und in den
        Anzeigen (``tools/oberflaeche.py`` (geloescht, E-009),
        ``tools/live_konsole.py``). Sie hier ein
        zweites Mal zu bauen hiesse, dieselbe Regel an zwei Orten zu fuehren, wo sie
        auseinanderlaufen kann -- und ``is_connected`` laeuft am Kopf fast jeder
        Methode, also je Aufruf einmal pro Symbol ueber die Leitung.
        """
        if self._mt5 is None:
            return False
        info = self._mt5.terminal_info()
        if info is None:
            return False
        if not bool(getattr(info, "connected", False)):
            return False
        return bool(self._mt5.account_info() is not None)

    # --- Hilfen ----------------------------------------------------------
    @staticmethod
    def _d(value: Any) -> Decimal:
        return Decimal(str(value))

    def _zu_server(self, ts: datetime) -> datetime:
        """Echte UTC-Zeit in die Wanduhr des Servers -- die Umkehr von :meth:`_utc`.

        ``copy_rates_range`` liest seine Grenzen in **Serverzeit**, nicht in UTC. Wer
        eine echte UTC-Zeit hineinreicht, fragt einen um den Serverversatz verschobenen
        Zeitraum ab: gemessen am 17.08.2026 (Server UTC+3) endete eine Abfrage mit
        ``end=jetzt`` bei einer Kerze von **14:00 UTC**, waehrend es 17:26 UTC war --
        3,4 Stunden Rueckstand.

        Das ist nicht bloss eine unvollstaendige Anzeige: die Trendfolge im Betrieb
        rechnete ihre gleitenden Durchschnitte auf Kerzen, die drei Stunden alt waren.
        Ein Signal auf veralteten Kerzen ist ein falsches Signal.

        Die Wanduhr wird **als UTC etikettiert** zurueckgegeben, nicht naiv. Das ist
        kein Schoenheitsfehler: eine naive Zeit rechnet das MetaTrader5-Paket ueber die
        Zeitzone des RECHNERS um. Am 17.08.2026 gemessen (Rechner UTC+2, Server UTC+3)
        ergab das genau eine Stunde Rueckstand -- die Abfrage endete bei Rohstempel
        18:00 statt 20:00. Mit dem UTC-Etikett trifft sie.

        Alle vier Varianten wurden gegen dasselbe Terminal gemessen: roh 17:00,
        naiv 18:00, **als UTC etikettiert 20:00**, mit sechs Stunden Puffer 20:00.
        Nur die dritte trifft UND schiesst nicht darueber hinaus.

        Ohne bekannte Serverzone bleibt die Zeit unveraendert -- dann ist ohnehin nichts
        gedreht, und ein einseitiger Eingriff waere schlimmer als keiner.
        """
        if self._server_tz is None:
            return ts
        return ts.astimezone(self._server_tz).replace(tzinfo=None).replace(tzinfo=UTC)

    def _utc(self, epoch_seconds: Any) -> datetime:
        """Zeitstempel des Terminals -- in echtem UTC, wenn die Serverzone bekannt ist.

        MetaTrader liefert Balken- und Positionszeiten so, dass sie **als UTC gelesen
        die Server-Ortszeit ergeben**. Wer sie ungedreht weiterreicht, haengt das
        Etikett ``UTC`` an eine Zeit, die keine ist -- und jeder Verbraucher, der sie
        mit einer echten UTC-Zeit vergleicht, rechnet falsch. Gemessen an diesem
        Broker: 2 h im Winter, 3 h im Sommer.

        Ohne ``server_tz`` bleibt es beim alten Verhalten. Das ist bewusst kein
        stiller Standardwert: eine geratene Zone waere fuer einen anderen Broker
        falsch, und ein falscher Versatz ist schlimmer als ein bekannter fehlender.
        """
        roh = datetime.fromtimestamp(int(epoch_seconds), tz=UTC)
        if self._server_tz is None:
            return roh
        return roh.replace(tzinfo=None).replace(tzinfo=self._server_tz).astimezone(UTC)

    def _require_write(self) -> None:
        if not self._allow_write:
            raise VenueUnavailableError(
                "Real-Terminal: Schreibpfad gesperrt (allow_write=False). "
                "Erst gegen ein Demo-Terminal smoke-testen, dann bewusst freigeben."
            )
        if self._mt5 is None:
            raise VenueUnavailableError(
                "Real-Terminal: keine Sitzung (initialize() nicht gelaufen)"
            )
        if self._require_demo and not self.account().is_demo:
            raise VenueUnavailableError(
                "Real-Terminal: Schreibpfad nur auf einem Demokonto "
                "(require_demo=True). Der direkte Terminalzugriff liegt unter dem "
                "Order-Pfad und umginge sonst alle fuenf Sperren."
            )

    def _to_symbol(self, info: Any) -> Mt5Symbol:
        point = self._d(info.point)
        pip = point * 10 if int(info.digits) in (3, 5) else point
        vol_max_raw = getattr(info, "volume_max", 0)
        tick_raw = getattr(info, "trade_tick_size", 0)
        tick = self._d(tick_raw) if tick_raw else point
        return Mt5Symbol(
            name=str(info.name),
            digits=int(info.digits),
            tick_size=tick,
            pip_size=pip,
            contract_size=self._d(info.trade_contract_size),
            volume_min=self._d(info.volume_min),
            volume_step=self._d(info.volume_step),
            volume_max=self._d(vol_max_raw) if vol_max_raw else None,
            base_currency=str(info.currency_base) or None,
            quote_currency=str(info.currency_profit) or None,
            # Points -> Tick-Schritte: jeder Leser dieses Feldes multipliziert es mit
            # ``tick_size``, MT5 zaehlt es aber in ``point``. Siehe
            # :func:`stop_level_in_tickschritten`.
            stop_level_points=stop_level_in_tickschritten(
                int(info.trade_stops_level), point=point, tick=tick
            ),
            freeze_level_points=int(info.trade_freeze_level),
            visible=bool(info.visible),
        )

    # --- Lesen -----------------------------------------------------------
    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return tuple(self._to_symbol(i) for i in (self._mt5.symbols_get() or ()))

    def symbol(self, name: str) -> Mt5Symbol | None:
        info = self._mt5.symbol_info(name)
        return None if info is None else self._to_symbol(info)

    def tick(self, name: str) -> Mt5Tick | None:
        raw = self._mt5.symbol_info_tick(name)
        if raw is None:
            return None
        return Mt5Tick(
            ts=self._utc(raw.time), bid=self._d(raw.bid), ask=self._d(raw.ask)
        )

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        tf = getattr(self._mt5, f"TIMEFRAME_{timeframe.value}")
        rows = self._mt5.copy_rates_range(
            name, tf, self._zu_server(start), self._zu_server(end)
        )
        if rows is None:
            return ()
        names = set(rows.dtype.names)
        out: list[Mt5Rate] = []
        for row in rows:
            out.append(
                Mt5Rate(
                    ts=self._utc(row["time"]),
                    open=self._d(row["open"]),
                    high=self._d(row["high"]),
                    low=self._d(row["low"]),
                    close=self._d(row["close"]),
                    tick_volume=int(row["tick_volume"]),
                    real_volume=self._d(row["real_volume"])
                    if "real_volume" in names
                    else None,
                    spread_points=self._d(row["spread"]) if "spread" in names else None,
                )
            )
        return tuple(out)

    def positions(self) -> tuple[Mt5Position, ...]:
        buy = int(getattr(self._mt5, "POSITION_TYPE_BUY", 0))
        out: list[Mt5Position] = []
        # ``positions_get`` gibt bei einem FEHLER ``None`` zurueck und bei wirklich
        # leerem Buch ein leeres Tupel. Ein ``or ()`` macht daraus dasselbe -- und ein
        # Lesefehler saehe dann aus wie „keine Positionen offen". Wer darauf aufbaut,
        # verbucht bei jeder Verbindungsstoerung alle offenen Positionen als
        # geschlossen. Fail-closed: der Fehler wird ein Fehler.
        roh = self._mt5.positions_get()
        if roh is None:
            raise VenueUnavailableError(
                "positions_get() lieferte None — Positionsabfrage fehlgeschlagen. "
                "Das ist NICHT dasselbe wie ein leeres Buch."
            )
        for pos in roh:
            out.append(
                Mt5Position(
                    ticket=str(pos.ticket),
                    symbol=str(pos.symbol),
                    is_buy=int(pos.type) == buy,
                    volume=self._d(pos.volume),
                    entry_price=self._d(pos.price_open),
                    stop_loss=self._d(pos.sl) if pos.sl else None,
                    take_profit=self._d(pos.tp) if pos.tp else None,
                    opened_at=self._utc(pos.time),
                    unrealised_pnl=self._d(pos.profit),
                    swap=self._d(pos.swap),
                )
            )
        return tuple(out)

    def account(self) -> Mt5Account:
        raw = self._mt5.account_info()
        if raw is None:
            raise VenueUnavailableError("Kein Konto-Info vom Terminal")
        demo_mode = int(getattr(self._mt5, "ACCOUNT_TRADE_MODE_DEMO", 0))
        return Mt5Account(
            account_id=str(raw.login),
            currency=str(raw.currency),
            balance=self._d(raw.balance),
            equity=self._d(raw.equity),
            margin_used=self._d(raw.margin),
            margin_free=self._d(raw.margin_free),
            is_demo=int(raw.trade_mode) == demo_mode,
            ts=datetime.now(UTC),
            leverage=int(raw.leverage) if getattr(raw, "leverage", None) else None,
        )

    # --- Schreiben (fail-closed) -----------------------------------------
    def _bereits_beim_broker(self, marke: int) -> tuple[str, str] | None:
        """Liegt zu dieser Kennmarke beim Broker schon etwas? (Art, Ticket) oder None.

        Der belastbare Teil der Idempotenz (E10.4). Gefragt werden die beiden Bestaende,
        in denen ein soeben gesendeter Auftrag stehen kann: die offenen **Positionen**
        (er wurde ausgefuehrt) und die liegenden **Auftraege** (er wurde angelegt).
        Beide tragen das ``magic`` des Auftrags.

        ``positions_get()``/``orders_get()`` geben bei einem **Fehler** ``None`` und bei
        leerem Ergebnis ein leeres Tupel -- dieselbe Falle wie ueberall sonst in diesem
        Modul. ``None`` heisst hier: die Frage "gibt es das schon?" ist unbeantwortet.
        Sie unbeantwortet zu lassen und trotzdem zu senden hiesse, die Doppelorder in
        Kauf zu nehmen, gegen die diese Pruefung gebaut ist. Also fail-closed: laut
        scheitern, nicht senden.

        **Benannter Mangel:** die Historie wird nicht befragt. Ein Auftrag, der gefuellt
        und dessen Position bereits wieder geschlossen wurde, steht in keinem der beiden
        Bestaende mehr und gilt hier als unbekannt. Fuer den Fall, um den es geht --
        Wiederholung nach Zeitablauf oder Neustart, also Sekunden bis Minuten spaeter --
        traegt die Pruefung; fuer eine Kennung, die Tage spaeter erneut verwendet wird,
        nicht. ``history_deals_get`` braeuchte ein Zeitfenster, und jedes Fenster waere
        eine Zahl ohne Beleg. Festgenagelt in
        ``tests/test_idempotenz_am_broker.py::test_geschlossene_position_wird_nicht_erkannt``.
        """
        mt5 = self._mt5
        for abfrage, art in (
            (mt5.positions_get, "position"),
            (mt5.orders_get, "order"),
        ):
            roh = abfrage()
            if roh is None:
                raise VenueUnavailableError(
                    f"Der Bestand ({art}) ist nicht abfragbar -- ob dieser Auftrag "
                    "beim Broker schon liegt, ist damit unbekannt. Es wird nicht "
                    "gesendet: eine Doppelorder ist der teurere Ausgang."
                )
            for eintrag in tuple(roh):
                if int(getattr(eintrag, "magic", 0) or 0) == marke:
                    return art, str(getattr(eintrag, "ticket", "") or "")
        return None

    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult:
        self._require_write()
        mt5 = self._mt5
        symbol = str(request["symbol"])
        is_buy = request["side"] == "buy"
        now = datetime.now(UTC)
        # E10.4: erst fragen, dann senden. Die Marke steht am Auftrag (``magic``), also
        # laesst sich eine Wiederholung ueberhaupt erkennen -- vorher lag beim Broker
        # nichts, woran man sie haette festmachen koennen.
        marke = kennmarke(str(request["client_order_id"]))
        gefunden = self._bereits_beim_broker(marke)
        if gefunden is not None:
            art, kennung = gefunden
            return Mt5SendResult(
                accepted=True,
                venue_order_id=kennung,
                # Was damals gefuellt wurde, gehoert nicht ein zweites Mal ins Buch.
                # Null ist hier kein Messwert, sondern die Aussage "durch DIESEN
                # Aufruf ist nichts entstanden".
                filled_volume=Decimal("0"),
                average_price=None,
                ts=now,
                reason=f"bereits_beim_broker ({art} {kennung}, magic={marke})",
                idempotent_replay=True,
            )
        raw_tick = mt5.symbol_info_tick(symbol)
        if raw_tick is None:
            return Mt5SendResult(False, None, Decimal("0"), None, now, "no_tick")
        if request["order_type"] == "market":
            action = mt5.TRADE_ACTION_DEAL
            otype = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            price = float(raw_tick.ask if is_buy else raw_tick.bid)
        else:
            action = mt5.TRADE_ACTION_PENDING
            otype = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
            price = float(request["limit_price"])
        req: dict[str, Any] = {
            "action": action,
            "symbol": symbol,
            "volume": float(request["volume"]),
            "type": otype,
            "price": price,
            "sl": float(request["stop_loss"]),
            "deviation": 20,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": _fuellart(mt5, symbol),
            # Die Marke geht MIT. Ohne sie steht der Auftrag beim Broker anonym da,
            # und die Frage "habe ich den schon gesendet?" ist nach einem Neustart
            # nicht mehr beantwortbar.
            "magic": marke,
            # Der Kommentar traegt die Kennung im Klartext -- fuer den Menschen, der
            # im Terminal danach sucht. Er wird gekuerzt und darf vom Server sogar
            # ueberschrieben werden; die Wiedererkennung haengt deshalb an ``magic``
            # und nicht hier. Der frueher hier stehende freie Kommentar entfaellt: er
            # war an dieser Stelle die schwaechere Information (er sagt, WAS die Order
            # ist, nicht WELCHE sie ist).
            "comment": str(request["client_order_id"])[:MAX_KOMMENTAR],
        }
        take_profit = request.get("take_profit")
        if take_profit is not None:
            req["tp"] = float(take_profit)
        if request.get("reduce_only") and action == mt5.TRADE_ACTION_DEAL:
            # Gegenposition gezielt schliessen (Ticket setzen) — sonst entsteht auf
            # Hedging-Konten eine neue Position statt eines Close.
            #
            # ``or ()`` stand hier und war dieselbe None-Falle, die 56 Zeilen weiter
            # oben ausdruecklich fail-closed behandelt wird -- nur mit der
            # gegenteiligen Antwort: ein Abfragefehler wurde still zu "keine
            # Position", ``req['position']`` blieb leer, und der Broker machte auf
            # einem Hedging-Konto aus der Schliessung eine NEUE Gegenposition. Das ist
            # der Reduce-Only-Pfad; hier ist die schmeichelnde Richtung besonders
            # teuer, weil sie Risiko AUFBAUT, wo Risiko abgebaut werden sollte.
            roh = mt5.positions_get(symbol=symbol)
            if roh is None:
                raise VenueUnavailableError(
                    f"{symbol}: der Positionsbestand ist nicht abfragbar -- welche "
                    "Position geschlossen werden soll, ist damit unbekannt. Es wird "
                    "nicht gesendet: eine Schliessung ohne Ticket wird auf einem "
                    "Hedging-Konto zur Gegenposition."
                )
            want_long = not is_buy
            buy_type = int(getattr(mt5, "POSITION_TYPE_BUY", 0))
            for pos in tuple(roh):
                if (int(pos.type) == buy_type) == want_long:
                    req["position"] = int(pos.ticket)
                    break
        res = mt5.order_send(req)
        # Zwei Fragen, nicht eine: durfte die Order ins System (``angenommen``), und
        # ist dabei etwas ausgefuehrt worden (``gefuellt``)? Bei
        # ``TRADE_RETCODE_PLACED`` faellt beides auseinander -- die Order liegt beim
        # Broker, gefuellt ist nichts. ``Mt5SendResult`` traegt darum beide Antworten
        # getrennt: ``accepted`` fuer den Lebenszyklus (Kennung merken, stornierbar
        # bleiben, Idempotenz), ``filled_volume`` fuer das Buch.
        angenommen = _send_angenommen(mt5, res)
        gefuellt = angenommen and _send_gefuellt(mt5, res)
        ticket = int(getattr(res, "order", 0) or 0) if angenommen else 0
        if angenommen and not gefuellt and not ticket:
            # Eine angelegte, nicht ausgefuehrte Order OHNE Kennung ist der einzige
            # Ausgang, den dieses System nicht sauber halten kann: sie liegt beim
            # Broker, kann jederzeit fuellen, und ``cancel`` haette nichts, worauf es
            # zeigen koennte. Laut scheitern statt still weiterlaufen.
            raise VenueUnavailableError(
                f"{symbol}: der Broker meldet eine angelegte, aber nicht ausgefuehrte "
                f"Order (retcode={int(getattr(res, 'retcode', -1))}) OHNE "
                "Order-Kennung. Es kann eine Pending-Order beim Broker liegen, die "
                "dieses System weder buchen noch stornieren kann -- von Hand pruefen."
            )
        if gefuellt:
            reason = "done"
        elif angenommen:
            # Angenommen, aber nichts gefuellt: das muss im Journal stehen, sonst
            # sieht ein Fill mit Volumen 0 wie ein Fehler aus statt wie eine
            # wartende Pending-Order.
            reason = f"placed_pending (retcode={int(getattr(res, 'retcode', -1))})"
        elif res is not None:
            # Der Rueckgabecode gehoert in die Meldung. Ohne ihn steht im Protokoll
            # nur der Kommentar des Brokers -- und der lautet auch bei manchen
            # Fehlschlaegen "Done", was die Ursachensuche unmoeglich macht.
            reason = f"{res.comment} (retcode={int(res.retcode)})"
        else:
            reason = "no_result"
        return Mt5SendResult(
            accepted=angenommen,
            venue_order_id=str(res.order) if angenommen else None,
            # Nur ein echter Fill geht ins Buch. Eine Pending-Order mit dem
            # Anfragevolumen zu buchen erzeugte eine Geisterposition, und der naechste
            # Reconcile latchte dafuer den Global-Halt.
            filled_volume=self._d(res.volume) if gefuellt else Decimal("0"),
            # Ohne Ausfuehrung gibt es keinen Ausfuehrungspreis. ``res.price`` traegt
            # bei einer Pending-Order den Wunschpreis; als Durchschnittspreis
            # weitergereicht waere er eine erfundene Messung.
            average_price=self._d(res.price) if gefuellt else None,
            ts=now,
            reason=reason,
        )

    def cancel(self, venue_order_id: str) -> bool:
        """Pending-Order stornieren -- und die Wirkung nachmessen, nicht ablesen.

        Zwei Fehler steckten in der alten Fassung, und sie zeigen in
        entgegengesetzte Richtungen:

        * **Falsch negativ.** Geprueft wurde allein auf ``TRADE_RETCODE_DONE``. Genau
          zwanzig Zeilen ueber dieser Stelle steht mit Messdatum, dass dieser Broker
          bei Erfolg ``retcode=0`` mit ``comment='Done'`` liefert und dass eine
          Pruefung allein auf 10009 "die gefaehrlichste Fehlrichtung" ist. Eine
          tatsaechlich stornierte Order galt damit als nicht storniert.
        * **Falsch positiv.** Ein Rueckgabecode ist die Auskunft des Servers ueber die
          ANFRAGE, nicht ueber den Zustand danach. Ein "Done" auf eine Order, die
          inzwischen schon gefuellt wurde, sagt nichts darueber, ob sie noch liegt.

        Beides faellt weg, wenn die Wirkung nachgemessen wird. Gemessen werden **zwei**
        Bestaende, und der zweite war der Rest des falsch positiven Falls: aus
        ``orders_get`` verschwindet ein Auftrag naemlich auf zwei voellig
        verschiedenen Wegen -- er wurde storniert, oder er wurde **gefuellt**. Wer nur
        die Auftragsliste liest, meldet fuer beides ``True``, und der zweite Fall ist
        genau die gefaehrliche Richtung: das System glaubt, es sei kein Risiko offen,
        waehrend eine Position steht. Die Schwestermethode
        :meth:`_bereits_beim_broker` fragt aus demselben Grund beide Bestaende.

        Also: nach dem Storno darf der Auftrag weder in ``orders_get`` stehen noch als
        Position unter derselben Kennung auftauchen. Der Rueckgabecode bleibt
        Vorfilter (ein benannter Fehlercode ist ein Fehler), die Aussage traegt die
        Gegenprobe.

        Beide Abfragen geben bei einem **Fehler** ``None`` zurueck und bei wirklich
        leerem Ergebnis ein leeres Tupel -- dieselbe Falle wie ueberall in diesem
        Modul. ``None`` heisst hier deshalb **nicht belegt**, also ``False``. Ein nicht
        belegtes Storno erneut zu versuchen ist harmlos; ein nicht erfolgtes Storno
        fuer erledigt zu halten nicht.

        **Benannter Rest.** Die Positionsabfrage traegt, weil MetaTrader der Position
        in aller Regel das Ticket der eroeffnenden Order gibt. "In aller Regel" ist
        keine Zusage: auf einem Netting-Konto verschmilzt eine Fuellung mit einer
        bereits stehenden Position und behaelt DEREN Ticket -- dann findet die
        Gegenprobe nichts und das Storno gilt als erfolgt, obwohl gefuellt wurde. Die
        vollstaendige Auskunft gaebe ``history_orders_get(ticket=...)`` mit
        ``ORDER_STATE_CANCELED``; sie ist hier bewusst nicht gezogen, weil sie den
        Vertrag :class:`Mt5Terminal` um eine Historienfrage erweitert und damit jede
        Attrappe im Repo mitzieht. Festgenagelt in
        ``tests/test_schreibpfad_wirkung.py::test_gefuellte_order_gilt_nicht_als_storniert``.
        """
        self._require_write()
        mt5 = self._mt5
        ticket = int(venue_order_id)
        res = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        if not _ohne_fehlercode(mt5, res):
            return False
        rest = mt5.orders_get(ticket=ticket)
        if rest is None:
            return False  # Abfrage fehlgeschlagen -- nicht dasselbe wie "ist weg"
        if len(tuple(rest)) != 0:
            return False
        gefuellt = mt5.positions_get(ticket=ticket)
        if gefuellt is None:
            return False  # dieselbe Falle, dieselbe Antwort
        # Steht unter dieser Kennung eine Position, ist die Order nicht storniert
        # worden, sondern ausgefuehrt. Aus der Auftragsliste ist sie in beiden
        # Faellen verschwunden.
        return len(tuple(gefuellt)) == 0

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        """Stops verschieben -- und nachlesen, wo sie danach wirklich stehen.

        Dieselben zwei Fehler wie bei :meth:`cancel` (Begruendung dort), hier aber mit
        der schwereren Folge: ein Stop ist die einzige harte Verlustgrenze einer
        offenen Position. Ein Stop, den das System fuer verschoben haelt und der nicht
        verschoben ist, ist ein Risiko, von dem niemand weiss -- und ein Nachziehen,
        das faelschlich als gescheitert gilt, laesst den Betrieb den Griff verlieren.

        Darum wird die Position nach der Aenderung zurueckgelesen und ``sl``/``tp``
        gegen das Gewuenschte gehalten. Toleranz ist **ein Point** des Symbols, also
        die kleinste Preisstufe, die der Broker ueberhaupt darstellen kann; alles
        darueber ist eine echte Abweichung.

        Drei Faelle antworten bewusst ``False``, obwohl "etwas passiert" ist:

        * Die Position ist beim Nachlesen weg (Stop lief ins Ziel, Handschliessung).
          Dann ist die Aussage "der Stop steht bei X" nicht mehr wahr.
        * Der Broker hat den Stop auf sein ``stops_level`` gezogen und steht damit
          woanders als gewuenscht. Das System darf dann nicht glauben, sein Risiko sei
          X -- es ist Y.
        * ``positions_get`` oder ``symbol_info`` liefern nichts. Nicht messbar heisst
          nicht belegt.

        ``None`` als Wunsch heisst "nicht anfassen" und wird darum auch nicht geprueft.
        """
        self._require_write()
        mt5 = self._mt5
        ticket = int(venue_position_id)
        req: dict[str, Any] = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket}
        if stop_loss is not None:
            req["sl"] = float(stop_loss)
        if take_profit is not None:
            req["tp"] = float(take_profit)
        res = mt5.order_send(req)
        if not _ohne_fehlercode(mt5, res):
            return False
        return self._stops_stehen(ticket, stop_loss, take_profit)

    def _stops_stehen(
        self,
        ticket: int,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        """Gegenprobe zu :meth:`modify_stops`: stehen die Stops wirklich dort?"""
        roh = self._mt5.positions_get(ticket=ticket)
        if not roh:
            return False  # None (Fehler) und () (Position weg) sind beide kein Beleg
        pos = tuple(roh)[0]
        info = self._mt5.symbol_info(str(pos.symbol))
        if info is None:
            return False
        toleranz = self._d(getattr(info, "point", 0) or 0)
        if toleranz <= 0:
            return False  # ohne bekannte Preisstufe ist kein Vergleich moeglich
        for gewuenscht, gemeldet in (
            (stop_loss, getattr(pos, "sl", None)),
            (take_profit, getattr(pos, "tp", None)),
        ):
            if gewuenscht is None:
                continue  # nicht angefragt, also nichts zu belegen
            if gemeldet is None:
                return False
            if abs(self._d(gemeldet) - gewuenscht) > toleranz:
                return False
        return True

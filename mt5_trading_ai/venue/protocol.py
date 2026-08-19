"""Plattformunabhaengiger Handelsplatz-Vertrag.

Kein Modul ausserhalb von ``venues/<name>/`` enthaelt einen Plattformnamen. Signal-
und Risikopfad sprechen ausschliesslich gegen dieses Protokoll; welche Plattform
dahinter steht, ist eine Konfigurationsfrage.

Fail-closed ist der Vertrag, nicht eine Eigenschaft der Implementierung: jede
Methode, die eine Antwort nicht sicher geben kann, wirft. ``None`` als
„weiss nicht" ist nur dort zulaessig, wo der Docstring es ausdruecklich nennt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from mt5_trading_ai.data.quality import TIMEFRAME_SECONDS

VENUE_PROTOCOL_VERSION = "trading-venue-v1"


class AssetClass(str, Enum):
    """Pflichtfeld je Instrument. Steuert den gesetzlichen Hebeldeckel."""

    FX_MAJOR = "fx_major"
    FX_MINOR = "fx_minor"
    GOLD = "gold"
    INDEX_MAJOR = "index_major"
    INDEX_MINOR = "index_minor"
    COMMODITY_NON_GOLD = "commodity_non_gold"
    EQUITY = "equity"
    CRYPTO = "crypto"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    @property
    def duration(self) -> timedelta:
        """Laenge eines Intervalls dieser Zeitebene.

        Bewusst aus ``data.quality.TIMEFRAME_SECONDS`` gezogen statt hier noch einmal
        aufgeschrieben: dieselbe Tabelle bestimmt im Qualitaetstor die erwartete
        Bar-Zahl. Zwei Tabellen waeren zwei Wahrheiten, und die zweite faellt beim
        naechsten neuen Zeitraster still auseinander -- genau die Sorte Abweichung,
        die niemand bemerkt, weil beide Seiten fuer sich plausibel aussehen.

        Fehlt ein Eintrag, wird geworfen. Ein geratener Vorgabewert waere hier
        besonders teuer: er entscheidet mit, welche Kerze als abgeschlossen gilt.

        Geworfen wird :class:`UnknownTimeframeError`, also eine Ableitung von
        :class:`VenueError` -- **nicht** ``ValueError``. Diese Eigenschaft wird mitten
        in ``venue/mt5.py:get_bars`` ausgewertet, und die Verbraucher dort fangen
        genau ``VenueError`` (``tools/live_betrieb.py``, ``tools/live_konsole.py``).
        Ein ``ValueError`` haette den Live-Takt nicht auf FLAT heruntergefahren,
        sondern abgerissen: eine Wartungssperre, die den Vertrag bricht, den sie
        schuetzen soll. Der Name steht weiter unten im Modul -- aufgeloest wird er
        beim Aufruf, nicht beim Import.

        **Bekannter Mangel: diese Laenge ist kalenderblind (D1 und H4).**
        ``timedelta`` ist eine feste Sekundenzahl; die Raster von D1 und H4 haengen
        dagegen an der Mitternacht des Handelsservers. Hat dessen Zone Sommerzeit
        (hier gemessen: ``Europe/Helsinki``), dauert der Rueckstelltag 25 statt 24
        Stunden. Nachgerechnet fuer den 25.10.2026: die Tageskerze beginnt 21:00 UTC
        und endet 22:00 UTC am Folgetag, die starren 24 h laufen aber schon um 21:00
        ab -- eine Stunde lang gilt die noch laufende Kerze als abgeschlossen, also
        in die schmeichelnde Richtung. Am Vorstelltag (23 h) kippt es in die harmlose:
        eine fertige Kerze gilt eine Stunde zu lang als laufend. H4 trifft es an
        denselben zwei Tagen im 00:00-Eimer der Serverzeit (dort 5 bzw. 3 Stunden).
        M1 bis H1 sind immun, weil die Umstellung ein ganzes Vielfaches ihrer Laenge
        ist.

        Bewusst **nicht** hier behoben: die kalenderbewusste Rechnung braucht die
        Zone des Handelsservers, und die darf in diesem Modul nicht stehen. Es ist
        der plattformunabhaengige Vertrag (siehe Modulkopf) -- eine Broker-Zeitzone
        darin waere genau der Plattformname, den der Modulkopf verbietet. Sie muesste
        vom Terminal (``RealMt5Terminal(server_tz=...)``) bis in ``Mt5Venue``
        durchgereicht werden, also durch Bauplaetze, die diese Welle nicht anfasst.
        Bis dahin gilt: ``is_closed`` ist fuer D1 und H4 an zwei Tagen im Jahr eine
        Stunde lang falsch. Kein heutiger Verbraucher ist betroffen -- beide
        Live-Treiber und der Rauchtest holen ausschliesslich H1; ``tools/aufloesung.py``
        benutzt D1/H4, geht aber nicht ueber ``get_bars`` und liest kein ``is_closed``.
        Festgenagelt ist der Mangel in ``tests/test_bar_geschlossen.py``
        (``test_d1_ueber_die_zeitumstellung_gilt_zu_frueh_als_fertig``): wer ihn
        behebt, macht diesen Fall rot und loescht ihn zusammen mit diesem Absatz.
        """
        seconds = TIMEFRAME_SECONDS.get(self.value)
        if seconds is None:
            raise UnknownTimeframeError(
                f"Keine Intervalllaenge fuer Zeitebene {self.value} hinterlegt "
                "(data/quality.py: TIMEFRAME_SECONDS)"
            )
        return timedelta(seconds=seconds)


class VenueError(RuntimeError):
    """Basisfehler. Jede Implementierung wirft ausschliesslich Ableitungen davon."""


class VenueUnavailableError(VenueError):
    """Verbindung, Terminal oder Sitzung nicht verfuegbar. Kein Handel."""


class UnknownInstrumentError(VenueError):
    """Instrument nicht im Katalog. Kein Handel, kein Default."""


class UnknownTimeframeError(VenueError):
    """Zeitebene ohne hinterlegte Intervalllaenge. Kein Handel, kein Default.

    Wird von :attr:`Timeframe.duration` geworfen. Bewusst eine ``VenueError``-
    Ableitung: der Zugriff liegt im Lesepfad einer Implementierung, und der Vertrag
    oben sagt, dass von dort ausschliesslich ``VenueError`` herauskommt.
    """


class OrderRejectedError(VenueError):
    """Der Handelsplatz hat abgelehnt. ``reason`` ist die Begruendung des Platzes."""

    def __init__(self, message: str, *, reason: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.reason = reason
        self.retryable = retryable


@dataclass(frozen=True)
class TradingSession:
    """Ein zusammenhaengendes Handelsfenster in UTC."""

    weekday: int  # 0 = Montag
    open_utc: str  # "HH:MM"
    close_utc: str  # "HH:MM"


@dataclass(frozen=True)
class FeeSchedule:
    """Kostenmodell je Instrument, je Standardlot.

    ``commission_per_lot_round_turn`` und die ``swap_*``-Felder stehen in Kontowaehrung
    (``currency``); ``typical_spread_points`` ist in Points (nur indikativ -- das
    Kostenmodell rechnet den Spread aus dem echten Bid/Ask); ``triple_swap_weekday`` ist
    ein Wochentag (0 = Montag).
    """

    commission_per_lot_round_turn: Decimal
    typical_spread_points: Decimal
    swap_long_per_lot_per_night: Decimal
    swap_short_per_lot_per_night: Decimal
    triple_swap_weekday: int | None
    currency: str


@dataclass(frozen=True)
class Instrument:
    """Instrumentenmetadaten.

    ``asset_class`` ist Pflicht — sie steuert den Hebeldeckel.
    """

    symbol: str
    venue: str
    asset_class: AssetClass
    contract_size: Decimal
    tick_size: Decimal
    pip_size: Decimal
    digits: int
    volume_min: Decimal
    volume_step: Decimal
    volume_max: Decimal | None
    base_currency: str | None
    quote_currency: str | None
    #: Mindestabstand von Stops zum Marktpreis, gezaehlt in **Tick-Schritten**: der
    #: Abstand in Preiseinheiten ist ``stop_level_points * tick_size``. Genau so lesen
    #: ihn alle drei Verbraucher (``venue/smoke.py``, ``execution/risk_manager.py``,
    #: ``execution/runner.py``). Der Name sagt "points", weil MT5 das Rohfeld
    #: (``SYMBOL_TRADE_STOPS_LEVEL``) in MT5-Points fuehrt; die Umrechnung macht der
    #: Adapter beim Einlesen (``venue/mt5.py::stop_level_in_tickschritten``). Eine
    #: Umsetzung, die den Wert selbst fuellt, schuldet dieselbe Einheit. Geht in den
    #: Stop-Floor ein und kann ihn dominieren.
    stop_level_points: int
    #: Abstand, innerhalb dessen der Platz Aenderungen ablehnt. Rohwert des Platzes.
    freeze_level_points: int
    fees: FeeSchedule
    sessions: tuple[TradingSession, ...]
    #: Rolltermine (Terminkontrakte) und Dividendenereignisse (Aktien), UTC.
    roll_dates: tuple[datetime, ...] = ()
    dividend_dates: tuple[datetime, ...] = ()
    active: bool = True


@dataclass(frozen=True)
class Quote:
    symbol: str
    ts: datetime
    bid: Decimal
    ask: Decimal
    #: ``None`` heisst: der Platz liefert keine Tiefe. Nicht 0 und nicht geraten.
    bid_volume: Decimal | None = None
    ask_volume: Decimal | None = None

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid


@dataclass(frozen=True)
class Bar:
    """Eine Kerze -- und die Auskunft, ob sie ueberhaupt schon eine ist.

    ``is_closed`` ist **Pflichtfeld ohne Vorgabewert**, und das ist die eigentliche
    Aussage dieser Klasse. Ein Handelsplatz liefert auf die Frage nach dem Zeitraum
    bis "jetzt" die noch in Bildung befindliche Kerze mit; deren ``close`` ist der
    momentane Kurs, kein Schlusskurs. Wer beides nicht unterscheiden kann, rechnet
    live auf einer Zahl, die es im Backtest nicht gibt -- dort kommen die Kerzen
    abgeschlossen aus Dateien. Live-Signal und getestetes Signal waeren dann nicht
    dieselbe Strategie, und kein Demo- oder Lernphasenlauf koennte das noch klaeren,
    gleichgueltig wie er ausgeht.

    Warum kein Vorgabewert:

    * ``True`` waere die schmeichelnde Richtung. Jede Bauweise, die das Feld
      vergisst, saehe aus wie geprueft -- der Melder waere per Konstruktion nie rot.
    * ``False`` waere zwar die sichere Richtung, wuerde aber echte abgeschlossene
      Kerzen falsch etikettieren und dieselbe Vergesslichkeit nur leiser bestrafen.
    * Ohne Vorgabewert muss jede Bauweise die Frage beantworten. ``grep`` ueber das
      Repo zeigt genau **eine** Stelle, die dieses ``Bar`` baut
      (``venue/mt5.py:get_bars``) -- der Backtest arbeitet mit
      ``data.quality.BarRow``, einer anderen Klasse. Die Pflicht kostet hier also
      nichts und wirkt auf jede kuenftige Stelle.

    Aus demselben Grund wird die laufende Kerze **nicht** stillschweigend
    abgeschnitten: dann stuende die Entscheidung an zwei Orten, und der naechste
    Verbraucher wuesste wieder nicht, was er vor sich hat.
    """

    symbol: str
    timeframe: Timeframe
    #: Beginn des Intervalls (open time), UTC.
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int
    #: Ist das Intervall ``[ts, ts + timeframe.duration)`` vorbei? Nur dann ist
    #: ``close`` ein Schlusskurs. ``False`` heisst: Kerze in Bildung, ``close`` ist
    #: der aktuelle Kurs und aendert sich noch.
    #: Einschraenkung: fuer D1 und H4 liegt die echte Grenze an der
    #: Server-Mitternacht, nicht bei ``ts + duration``. Ueber eine Zeitumstellung
    #: weichen beide um eine Stunde ab -- bekannter Mangel, Umfang und Begruendung
    #: stehen bei :attr:`Timeframe.duration`.
    is_closed: bool
    volume: Decimal | None = None
    spread_avg_points: Decimal | None = None


def ist_abgeschlossen(ts: datetime, timeframe: Timeframe, jetzt: datetime) -> bool:
    """Ist das Intervall, das bei ``ts`` beginnt, um ``jetzt`` vorbei?

    WARUM DIESE FUNKTION UND NICHT DER AUSDRUCK
    -------------------------------------------
    Die Regel stand einmal, als Ausdruck, in ``venue/mt5.py:get_bars`` -- und
    **fuenf** andere Stellen lasen ihre Kerzen an ``get_bars`` vorbei direkt aus dem
    Terminal (``tools/atr_messung.py``, ``tools/aufloesung.py``,
    ``tools/ereignisstudie.py``). Sie bekamen damit gar kein ``is_closed`` und nahmen
    die letzte, noch in Bildung befindliche Kerze stillschweigend mit. Nachgemessen an
    den 15 Reihen-Manifesten, die ``tools/aufloesung.py`` erzeugt hat: bei **12 von
    15** lag die letzte Bar zum Abrufzeitpunkt noch offen (etwa EURUSD H1,
    ``last=13:00``, ``retrieved_at=13:14`` -- die Kerze schliesst erst um 14:00).
    Deren Pruefsumme deckt damit eine Bar, die sich noch aendert; ein zweiter Abruf
    ergibt eine andere Zahl.

    Eine Regel, die an einer Stelle steht und an fuenf anderen fehlt, ist keine Regel.
    Darum hier, einmal, mit Namen.

    ``jetzt`` MUSS vom Handelsplatz kommen (Tick-Zeitstempel), nicht von der
    Rechneruhr: Kerzen- und Tick-Stempel laufen durch dieselbe Umrechnung, die
    Rechneruhr nicht. Die ausfuehrliche Begruendung -- samt der Messung, dass ein
    Vergleich gegen die Systemzeit je nach Serverzone in beide Richtungen falsch
    liegt -- steht bei ``venue/mt5.py:get_bars``.

    ``<=`` und nicht ``<``: zum Zeitpunkt ``ts + dauer`` laeuft bereits die naechste
    Kerze, die vorige ist fertig.

    Einschraenkung, unveraendert und bewusst nicht hier behoben: fuer D1 und H4 liegt
    die echte Grenze an der Server-Mitternacht statt bei ``ts + duration``. Ueber eine
    Zeitumstellung weichen beide um eine Stunde ab. Umfang und Begruendung stehen bei
    :attr:`Timeframe.duration`. Fuer die fuenf Stellen oben ist das trotzdem ein
    Fortschritt: sie nahmen die unfertige Kerze bisher **immer** mit, kuenftig nur
    noch moeglicherweise an zwei Tagen im Jahr eine Stunde lang.
    """
    return ts + timeframe.duration <= jetzt


@dataclass(frozen=True)
class OrderRequest:
    """Ein Auftrag mit Stop. Ohne Stop wird nicht eroeffnet."""

    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    volume: Decimal
    stop_loss: Decimal
    take_profit: Decimal | None = None
    limit_price: Decimal | None = None
    reduce_only: bool = False
    comment: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderResult:
    client_order_id: str
    venue_order_id: str | None
    accepted: bool
    filled_volume: Decimal
    average_price: Decimal | None
    ts: datetime
    idempotent_replay: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    venue_position_id: str
    symbol: str
    side: OrderSide
    volume: Decimal
    entry_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    opened_at: datetime
    unrealised_pnl: Decimal
    swap_accrued: Decimal


@dataclass(frozen=True)
class AccountState:
    account_id: str
    currency: str
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_free: Decimal
    #: ``True`` nur bei einem Demokonto. Der Live-Pfad prueft dieses Feld.
    is_demo: bool
    ts: datetime
    #: Hebel, den der BROKER diesem Konto gewaehrt (1:N -> N). ``None`` heisst
    #: unbekannt. Er ist eine harte Obergrenze: mehr als der Broker gibt, kann keine
    #: Politik sich nehmen. Ohne dieses Feld rechnet die Margenpruefung mit dem
    #: GEWUENSCHTEN Hebel und laesst Positionen zu, die der Broker ablehnt.
    leverage: int | None = None


@runtime_checkable
class TradingVenue(Protocol):
    """Der Vertrag. Signal- und Risikopfad kennen nichts anderes."""

    name: str

    # --- Verbindung -------------------------------------------------------
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_healthy(self) -> bool:
        """False bei fehlendem Terminal oder fehlender Sitzung.

        Praezisiert, nachdem die MT5-Fassung zwei der drei zugesagten Faelle gar
        nicht prueft: sie fragte nur, ob der Terminal-**Prozess** laeuft. Ein
        laufendes Terminal ohne Leitung zum Handelsserver galt als gesund.

        Was diese Frage beantwortet -- und was jede Umsetzung liefern muss:

        * **kein Terminal** -- keine Bindung, kein Prozess.
        * **keine Sitzung** -- Prozess laeuft, aber die Verbindung zum Handelsserver
          steht nicht oder es ist kein Konto angemeldet.

        Was sie **nicht** beantwortet: das **Alter der Daten**. Frische ist immer die
        Frage nach einem konkreten Stempel eines konkreten Symbols; sie braucht ein
        Symbol als Eingabe und einen Stempel von der Gegenseite der Leitung. Diese
        Methode bekommt kein Symbol und laeuft am Kopf fast jeder anderen -- sie
        koennte die Frage also weder stellen noch bezahlen.

        **Die dritte Zusage ist damit nicht entfallen, sondern umgezogen.** Frueher
        stand hier "oder veralteten Daten", und keine Umsetzung hat es je geprueft:
        die MT5-Fassung fragte allein, ob der Terminal-Prozess laeuft. Eine Zusage,
        die keine Umsetzung einhalten kann, ist keine Sperre, sondern ein
        Missverstaendnis mit Vertragstext. Sie lautet jetzt: **jede Umsetzung schuldet
        die Frischepruefung je Order und je Symbol, vor der ersten Sperre, die mit
        Zahlen rechnet** -- gegen einen Stempel, der von der Gegenseite der Leitung
        kommt, nicht gegen einen selbst gesetzten. Wo eine Umsetzung sie fuehrt, ist
        ihre Sache; im MT5-Adapter ist es ``Mt5Venue._enforce_account_freshness`` mit
        ``execution/freshness.py``. Ein gesundes ``is_healthy`` ist deshalb kein
        Freibrief.

        Wer diesen Vertragstext zitiert, zitiert diese zwei Faelle und den Verweis --
        nicht die alte Dreierliste (nachgezogen in ``venue/mt5.py`` und
        ``tests/test_terminal_gesundheit.py``).
        """
        ...

    # --- Instrumentenmetadaten -------------------------------------------
    def list_instruments(self) -> tuple[Instrument, ...]: ...
    def get_instrument(self, symbol: str) -> Instrument:
        """Wirft :class:`UnknownInstrumentError`, wenn das Symbol unbekannt ist."""
        ...

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        """Handelt der Platz dieses Symbol? **Zwei** Bedingungen, beide notwendig.

        Der frueher hier stehende Einzeiler ("Handelszeiten der Klasse, inklusive
        Sitzungspausen. UTC.") beschrieb nur die erste Haelfte und liess offen, woran
        eine Umsetzung die zweite misst. Eine Zeitplantabelle allein beantwortet die
        Frage nicht: sie kennt keine Feiertage, keinen ausgefallenen Platz und keine
        haengende Leitung -- sie wuerde "offen" sagen, waehrend nichts gehandelt wird.
        Das ist die gefaehrliche Fehlrichtung, denn danach laeuft die ganze
        Eintrittskette auf einem Markt, den es gerade nicht gibt.

        Was jede Umsetzung schuldet:

        1. **Zeitplan gegen ``at``.** Faellt ``at`` in ein Sitzungsfenster? Ein
           Fahrplan, der nicht aus einem veroeffentlichten Boersenkalender stammt, darf
           ausschliesslich **verengen** -- er darf nie das einzige Ja sein.
        2. **Beleg gegen die Gegenwart.** Dass der Platz wirklich handelt, belegt nur
           ein Lebenszeichen von der anderen Seite der Leitung -- im MT5-Adapter der
           Kursstempel des Symbols, gemessen mit derselben Frist wie der Frische-Latch
           am Order-Pfad (``execution/freshness.py``). Gemessen wird gegen die **Uhr der
           Umsetzung**, nicht gegen ``at``: ein Aufrufer, der seine Gegenwart am Kopf
           eines Taktes einfriert, macht den frisch geholten Stempel sonst rechnerisch
           zu einem aus der Zukunft und schaltet den Eintrittspfad ab, ohne dass das mit
           dem Markt zu tun haette. Genau so ist er einmal abgeschaltet worden.

        Daraus folgt, was ein **historisches** ``at`` liefert: keine historische
        Antwort. Es waehlt das Zeitfenster von damals und bekommt die Messung von jetzt.
        Wer Vergangenheit beurteilen will, fragt die Daten, nicht diese Methode.

        ``at`` muss **zonenbewusst** sein; ein naiver Stempel ist ein Aufruferfehler und
        wirft. Ein ``False`` waere hier die schlechtere Antwort, weil "geschlossen" eine
        gueltige Marktaussage ist -- der Fehler saehe wie ein dauerhaft geschlossener
        Markt aus und faende sich nie.

        Umsetzung und Begruendung im Einzelnen: ``Mt5Venue.is_trading_open``.
        """
        ...

    # --- Marktdaten -------------------------------------------------------
    def get_quote(self, symbol: str) -> Quote: ...
    def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        start: datetime,
        end: datetime,
    ) -> tuple[Bar, ...]:
        """Bars mit ``ts`` = Intervallbeginn, aufsteigend, ohne stille Interpolation.

        Reicht ``end`` bis in die Gegenwart, ist die letzte Bar in aller Regel noch
        in Bildung. Sie wird **mitgeliefert und als** ``is_closed=False``
        **gekennzeichnet**, nicht entfernt: wer nur abgeschlossene Kerzen rechnen
        will, filtert sichtbar; wer den laufenden Kurs braucht, hat ihn. Eine
        Implementierung, die das Feld nicht sicher bestimmen kann, wirft --
        "vermutlich abgeschlossen" gibt es nicht.
        """
        ...

    # --- Ausfuehrung ------------------------------------------------------
    def submit_order(self, request: OrderRequest) -> OrderResult:
        """Idempotent ueber ``client_order_id``.

        Ein zweiter Aufruf mit derselben Kennung darf **keine** zweite Order
        erzeugen; er liefert das Ergebnis der ersten mit
        ``idempotent_replay=True``.

        **Damit ist der Aufrufer in der Pflicht, und zwar an der einen Stelle, an der
        er es nicht merkt.** Diese Zusage kann eine Umsetzung nur einloesen, wenn sie
        dieselbe Kennung ein zweites Mal zu sehen bekommt. Eine je Versuch neu
        gewuerfelte Kennung (``uuid4``) macht daraus zwei verschiedene Auftraege --
        aus Sicht jeder Umsetzung sind sie es dann auch. Der Schutz ist damit nicht
        schwach, sondern abgeschaltet, und das faellt nirgends auf: der Normalfall
        sieht genauso aus.

        Die Kennung muss darum aus der **Absicht** abgeleitet sein und nicht aus dem
        Versuch: Symbol + Signal + Kerzenstempel ergibt fuer denselben Willen
        zweimal dieselbe Zeichenkette -- ueber einen Zeitablauf, einen Neustart und
        einen zweiten Runner hinweg. Genau diese drei Faelle sind der Grund fuer die
        Zusage; in allen dreien ist das Prozessgedaechtnis leer.

        Eine Umsetzung darf sich auf diese Mitwirkung nicht verlassen. Der MT5-Adapter
        fuehrt darum zusaetzlich einen kennungsunabhaengigen Riegel: eine eroeffnende
        Order in ein Symbol, in dem beim Handelsplatz bereits eine gleichgerichtete
        Position steht, wird abgelehnt
        (``Mt5Venue._verhindere_doppelte_eroeffnung``, Grund
        ``doppelte_eroeffnung``). Das ist keine Vertragspflicht -- eine Umsetzung, die
        Pyramiden zulassen will, darf ihn nicht haben --, aber es ist die einzige
        Wiedererkennung, die auch ohne Zutun des Aufrufers greift.
        """
        ...

    def cancel_order(self, client_order_id: str) -> bool: ...

    def modify_position_stops(
        self,
        venue_position_id: str,
        *,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool: ...

    # --- Zustand ----------------------------------------------------------
    def get_positions(self) -> tuple[Position, ...]: ...
    def get_account(self) -> AccountState: ...

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
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol, runtime_checkable

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


class VenueError(RuntimeError):
    """Basisfehler. Jede Implementierung wirft ausschliesslich Ableitungen davon."""


class VenueUnavailableError(VenueError):
    """Verbindung, Terminal oder Sitzung nicht verfuegbar. Kein Handel."""


class UnknownInstrumentError(VenueError):
    """Instrument nicht im Katalog. Kein Handel, kein Default."""


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
    #: Mindestabstand von Stops zum Marktpreis, in Points. Geht in den Stop-Floor ein
    #: und kann ihn dominieren.
    stop_level_points: int
    #: Abstand, innerhalb dessen der Platz Aenderungen ablehnt.
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
    symbol: str
    timeframe: Timeframe
    #: Beginn des Intervalls (open time), UTC.
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    tick_volume: int
    volume: Decimal | None = None
    spread_avg_points: Decimal | None = None


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


@runtime_checkable
class TradingVenue(Protocol):
    """Der Vertrag. Signal- und Risikopfad kennen nichts anderes."""

    name: str

    # --- Verbindung -------------------------------------------------------
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_healthy(self) -> bool:
        """False bei fehlendem Terminal, fehlender Sitzung oder veralteten Daten."""
        ...

    # --- Instrumentenmetadaten -------------------------------------------
    def list_instruments(self) -> tuple[Instrument, ...]: ...
    def get_instrument(self, symbol: str) -> Instrument:
        """Wirft :class:`UnknownInstrumentError`, wenn das Symbol unbekannt ist."""
        ...

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        """Handelszeiten der Klasse, inklusive Sitzungspausen. UTC."""
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
        """Bars mit ``ts`` = Intervallbeginn, aufsteigend, ohne stille Interpolation."""
        ...

    # --- Ausfuehrung ------------------------------------------------------
    def submit_order(self, request: OrderRequest) -> OrderResult:
        """Idempotent ueber ``client_order_id``.

        Ein zweiter Aufruf mit derselben Kennung darf **keine** zweite Order
        erzeugen; er liefert das Ergebnis der ersten mit
        ``idempotent_replay=True``.
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

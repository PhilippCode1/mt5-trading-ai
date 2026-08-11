"""MT5-Anbindung an das ``TradingVenue``-Protokoll.

Drei Eigenschaften bestimmen den Aufbau:

* **Fail-closed am Ausfuehrungspfad.** Eine eroeffnende Order an ein **Live**-Konto
  (``account.is_demo is False``) passiert nur, wenn die mehrteilige Live-Freigabe
  (``execution/release.py``) vollstaendig ist. Fehlt sie, wird die Order abgelehnt --
  nicht gesendet. Demokonten und Reduce-Only (Risikoabbau) passieren ohne Freigabe.
  Der Adapter baut damit den Anschluss, den ``FEHLT.md`` als offen markiert hat, **mit**
  dem Tor, nicht daran vorbei.
* **Testbar ohne Terminal.** Der Adapter spricht gegen die schmale Naht
  :class:`Mt5Terminal`. Der Vertragstest injiziert ein Fake-Terminal; kein echtes MT5
  wird gebraucht. Die eigentliche MT5→Protokoll-Abbildung liegt hier (getestet).
* **Import bleibt stdlib-rein.** Das Paket ``MetaTrader5`` wird ausschliesslich **lazy**
  in :class:`RealMt5Terminal` geladen. Der Modulimport haengt an nichts ausserhalb der
  Standardbibliothek.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight
from mt5_trading_ai.execution.reconcile import (
    PositionBook,
    ReconcileResult,
    positions_to_net,
    reconcile_positions,
)
from mt5_trading_ai.execution.release import live_release_blocks_opening_order
from mt5_trading_ai.venue.catalog import CatalogEntry
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Bar,
    Instrument,
    OrderRejectedError,
    OrderRequest,
    OrderResult,
    OrderSide,
    Position,
    Quote,
    Timeframe,
    TradingVenue,
    UnknownInstrumentError,
    VenueUnavailableError,
)

MT5_ADAPTER_VERSION = "mt5-venue-v1"


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


@dataclass(frozen=True)
class Mt5SendResult:
    accepted: bool
    venue_order_id: str | None
    filled_volume: Decimal
    average_price: Decimal | None
    ts: datetime
    reason: str
    retryable: bool = False
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


def _hhmm_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


class Mt5Venue(TradingVenue):
    """MT5-Handelsplatz. Erfuellt das ``TradingVenue``-Protokoll (statisch geprueft).

    ``settings`` traegt die Live-Freigabe-Schalter (siehe ``execution/release.py``);
    fuer Demo/Reduce-Only ist es unerheblich und darf ``None`` sein.
    """

    def __init__(
        self,
        *,
        name: str,
        terminal: Mt5Terminal,
        catalog: Mapping[str, CatalogEntry],
        settings: Any = None,
        max_notional_drift: Decimal = Decimal("0"),
    ) -> None:
        self.name = name
        self._terminal = terminal
        self._catalog = dict(catalog)
        self._settings = settings
        self._max_notional_drift = max_notional_drift
        self._connected = False
        #: Idempotenz je ``client_order_id`` — nur angenommene Orders.
        self._results: dict[str, OrderResult] = {}
        #: Lokales Buch der Nettopositionen; Reconcile vergleicht es mit der Meldung.
        self._book = PositionBook()
        #: Global-Halt-Latch (Reconcile-Drift). Klaert nicht selbst, nur ``clear_halt``.
        self._halted = False

    # --- Verbindung -------------------------------------------------------
    def connect(self) -> None:
        if not self._terminal.initialize():
            raise VenueUnavailableError("MT5-Terminal nicht initialisierbar")
        self._connected = True

    def disconnect(self) -> None:
        self._terminal.shutdown()
        self._connected = False

    def is_healthy(self) -> bool:
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
        out: list[Instrument] = []
        for symbol in self._catalog:
            try:
                out.append(self.get_instrument(symbol))
            except UnknownInstrumentError:
                continue
        return tuple(out)

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        instrument = self.get_instrument(symbol)
        minute_of_day = at.hour * 60 + at.minute
        for session in instrument.sessions:
            if session.weekday != at.weekday():
                continue
            open_min = _hhmm_to_minutes(session.open_utc)
            close_min = _hhmm_to_minutes(session.close_utc)
            if open_min <= minute_of_day < close_min:
                return True
        return False

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
        self._require_healthy()
        self.get_instrument(symbol)
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
        self._validate_volume(instrument, request.volume)

        if not request.reduce_only:
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
            # Live-Freigabe-Tor: nur eroeffnende Orders an einem Live-Konto.
            self._require_live_release_for_opening()
            # Hebelklammer am Order-Pfad: handelbar, geklammert, Marge frei?
            self._enforce_leverage(instrument, request)

        send = self._terminal.order_send(self._to_terminal_request(request))
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
        self._book.apply_fill(request.symbol, request.side, send.filled_volume)
        return result

    def _require_live_release_for_opening(self) -> None:
        account = self._terminal.account()
        if account.is_demo:
            return  # Demokonto: keine Live-Freigabe noetig.
        blocked = live_release_blocks_opening_order(self._settings, reduce_only=False)
        if blocked is not None:
            raise OrderRejectedError(
                "Live-Freigabe unvollstaendig — eroeffnende Order blockiert",
                reason=blocked.reason or "live_release_incomplete",
                retryable=False,
            )

    def _enforce_leverage(self, instrument: Instrument, request: OrderRequest) -> None:
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
        if not preflight.approved:
            raise OrderRejectedError(
                f"Hebel-Anschluss abgelehnt: {preflight.reason}",
                reason=preflight.reason or "leverage_rejected",
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

    def get_account(self) -> AccountState:
        self._require_healthy()
        acc = self._terminal.account()
        return AccountState(
            account_id=acc.account_id,
            currency=acc.currency,
            balance=acc.balance,
            equity=acc.equity,
            margin_used=acc.margin_used,
            margin_free=acc.margin_free,
            is_demo=acc.is_demo,
            ts=acc.ts,
        )

    # --- Order-Lebenszyklus / Reconcile -----------------------------------
    def book_snapshot(self) -> dict[str, Decimal]:
        """Das lokale Buch der Nettopositionen je Symbol."""
        return self._book.snapshot()

    def is_halted(self) -> bool:
        return self._halted

    def clear_halt(self) -> None:
        """Manuelle Freigabe nach aufgeloester Drift. Der Latch klaert nicht selbst."""
        self._halted = False

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
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        #: Fail-closed: der Schreibpfad (Orders senden/aendern) ist gesperrt, bis er
        #: bewusst freigegeben wird — nach einem Smoke-Test gegen ein Demo-Terminal.
        self._allow_write = allow_write
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
        if self._mt5 is None:
            return False
        return self._mt5.terminal_info() is not None

    # --- Hilfen ----------------------------------------------------------
    @staticmethod
    def _d(value: Any) -> Decimal:
        return Decimal(str(value))

    @staticmethod
    def _utc(epoch_seconds: Any) -> datetime:
        return datetime.fromtimestamp(int(epoch_seconds), tz=UTC)

    def _require_write(self) -> None:
        if not self._allow_write:
            raise VenueUnavailableError(
                "Real-Terminal: Schreibpfad gesperrt (allow_write=False). "
                "Erst gegen ein Demo-Terminal smoke-testen, dann bewusst freigeben."
            )

    def _to_symbol(self, info: Any) -> Mt5Symbol:
        point = self._d(info.point)
        pip = point * 10 if int(info.digits) in (3, 5) else point
        vol_max_raw = getattr(info, "volume_max", 0)
        tick_raw = getattr(info, "trade_tick_size", 0)
        return Mt5Symbol(
            name=str(info.name),
            digits=int(info.digits),
            tick_size=self._d(tick_raw) if tick_raw else point,
            pip_size=pip,
            contract_size=self._d(info.trade_contract_size),
            volume_min=self._d(info.volume_min),
            volume_step=self._d(info.volume_step),
            volume_max=self._d(vol_max_raw) if vol_max_raw else None,
            base_currency=str(info.currency_base) or None,
            quote_currency=str(info.currency_profit) or None,
            stop_level_points=int(info.trade_stops_level),
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
        rows = self._mt5.copy_rates_range(name, tf, start, end)
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
                    spread_points=self._d(row["spread"])
                    if "spread" in names
                    else None,
                )
            )
        return tuple(out)

    def positions(self) -> tuple[Mt5Position, ...]:
        buy = int(getattr(self._mt5, "POSITION_TYPE_BUY", 0))
        out: list[Mt5Position] = []
        for pos in self._mt5.positions_get() or ():
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
        )

    # --- Schreiben (fail-closed) -----------------------------------------
    def order_send(self, request: Mapping[str, Any]) -> Mt5SendResult:
        self._require_write()
        mt5 = self._mt5
        symbol = str(request["symbol"])
        is_buy = request["side"] == "buy"
        now = datetime.now(UTC)
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
            "type_filling": mt5.ORDER_FILLING_IOC,
            "comment": str(request.get("comment", "")),
        }
        take_profit = request.get("take_profit")
        if take_profit is not None:
            req["tp"] = float(take_profit)
        if request.get("reduce_only") and action == mt5.TRADE_ACTION_DEAL:
            # Gegenposition gezielt schliessen (Ticket setzen) — sonst entsteht auf
            # Hedging-Konten eine neue Position statt eines Close.
            want_long = not is_buy
            buy_type = int(getattr(mt5, "POSITION_TYPE_BUY", 0))
            for pos in mt5.positions_get(symbol=symbol) or ():
                if (int(pos.type) == buy_type) == want_long:
                    req["position"] = int(pos.ticket)
                    break
        res = mt5.order_send(req)
        done = int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
        accepted = res is not None and int(res.retcode) == done
        if accepted:
            reason = "done"
        elif res is not None:
            reason = str(res.comment)
        else:
            reason = "no_result"
        return Mt5SendResult(
            accepted=accepted,
            venue_order_id=str(res.order) if accepted else None,
            filled_volume=self._d(res.volume) if accepted else Decimal("0"),
            average_price=self._d(res.price) if accepted else None,
            ts=now,
            reason=reason,
        )

    def cancel(self, venue_order_id: str) -> bool:
        self._require_write()
        mt5 = self._mt5
        res = mt5.order_send(
            {"action": mt5.TRADE_ACTION_REMOVE, "order": int(venue_order_id)}
        )
        done = int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
        return res is not None and int(res.retcode) == done

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        self._require_write()
        mt5 = self._mt5
        req: dict[str, Any] = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(venue_position_id),
        }
        if stop_loss is not None:
            req["sl"] = float(stop_loss)
        if take_profit is not None:
            req["tp"] = float(take_profit)
        res = mt5.order_send(req)
        done = int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
        return res is not None and int(res.retcode) == done

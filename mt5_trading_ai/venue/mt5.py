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
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

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
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.catalog import CatalogEntry
from mt5_trading_ai.venue.demo_run import DemoReadiness
from mt5_trading_ai.venue.halal import screen_halal
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
    TradingVenue,
    UnknownInstrumentError,
    VenueError,
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

    ``cost_gate`` traegt die im Backtest vorausgesetzte Kostenobergrenze
    (``execution/cost_gate.py``). Auf einem **Live**-Konto ist es fuer eroeffnende
    Orders Pflicht: fehlt es, wird fail-closed abgelehnt (kein ungeprueftes Live-Kosten-
    risiko). Auf Demo ist es unerheblich (kein Echtgeld) -- wie die Live-Freigabe.

    ``risk_manager`` traegt die Risikoschicht (``execution/risk_manager.py``):
    Kill-Switch (Tagesverlust/Drawdown/Deckel/Gap), Drossel, Stop-Budget und
    Positionsgroesse. **Anders als Kostentor und Halal-Screen ist sie fuer JEDE
    eroeffnende Order Pflicht, auch auf Demo** (Paket 2, A3): Kostentor und Halal
    schuetzen vor realem Geld und realer Zinsbelastung — auf einem Demokonto gibt es
    beides nicht. Die Risikoschicht dagegen prueft, ob der **Mechanismus** traegt, und
    genau das muss auf dem Demokonto laufen, weil das Demokonto der Beweisplatz vor
    jedem Live-Pfad ist (Reihenfolge-Regel aus ``FEHLT.md``). Eine Sperre, die nur auf
    dem Konto laeuft, das man noch nicht benutzt, ist nicht verdrahtet.
    Fehlt der Manager, wird jede Eroeffnung fail-closed abgelehnt.
    Drawdown-Halt setzt ``_halted``.

    ``clock`` liefert die Gegenwart fuer den **Frische-Latch** (S2,
    ``execution/freshness.py``): ein Kontozustand aelter als ``max_account_age`` gilt
    als nicht bewertbar, und nicht bewertbar heisst nicht erfuellt. Der Latch laeuft
    als **erste** der fuenf Sperren, weil jede folgende mit Zahlen aus genau diesem
    Zustand rechnet. Default ist die Systemuhr; Tests spritzen eine feste Uhr ein.

    ``demo_readiness`` (Paket 5) ist das Ergebnis des Demo-Reife-Tors
    (``venue/demo_run.py``): eine Live-Eroeffnung verlangt >= 180 Tage Demo-Betrieb
    **und** weiter bestandenen Edge; fehlt es oder ist es nicht reif, blockt die
    Live-Freigabe. Der Halal-Screen (``venue/halal.py``) laeuft ebenfalls je
    eroeffnender Live-Order und liest swapfrei/zinsfrei/Freigabe aus ``settings``.
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
        demo_readiness: DemoReadiness | None = None,
        clock: Callable[[], datetime] | None = None,
        max_account_age: timedelta = MAX_SNAPSHOT_AGE,
    ) -> None:
        self.name = name
        self._terminal = terminal
        self._catalog = dict(catalog)
        self._settings = settings
        self._max_notional_drift = max_notional_drift
        self._cost_gate = cost_gate
        self._risk_manager = risk_manager
        self._demo_readiness = demo_readiness
        #: Gegenwart fuer den Frische-Latch. Injizierbar, damit die Sperre pruefbar ist.
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self._max_account_age = max_account_age
        self._connected = False
        #: Idempotenz je ``client_order_id`` — nur angenommene Orders.
        self._results: dict[str, OrderResult] = {}
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

        # ``reduce_only`` ueberspringt die Eroeffnungs-Tore -- aber NUR, wenn die Order
        # eine tatsaechlich offene Gegenposition abbaut. Ein reduce_only-Flag ohne (oder
        # gleichgerichtet zu einer) offenen Position ist eine Eroeffnung und muss durch
        # alle Tore (sonst umginge es Compliance/Risiko + Global-Halt -- §9 Paket 5).
        pre_net = self._book.net(request.symbol)
        is_reducing = request.reduce_only and self._reduces_position(request)

        if not is_reducing:
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
            # Sperre 1 von 5 (Paket 2, A3.2): Frische des Kontozustands. Sie laeuft
            # VOR allem, was aus dem Kontozustand liest -- auch vor der Live-Freigabe,
            # die ``is_demo`` aus genau diesem Schnappschuss zieht.
            self._enforce_account_freshness()
            # Live-Freigabe (inkl. Demo-Reife): nur eroeffnende Orders am Live-Konto.
            self._require_live_release_for_opening()
            # Halal-Screen: mechanische Konformitaet + hinterlegte Gelehrten-Freigabe.
            self._enforce_halal(instrument)
            # Hebelklammer am Order-Pfad: handelbar, geklammert, Marge frei?
            effective_leverage = self._enforce_leverage(instrument, request)
            # Pre-Trade-Kostentor: reale Roundturn-Kosten unter der Backtest-Schwelle?
            self._enforce_cost_gate(instrument, request)
            # Sperren 2 bis 5 von 5: Kill-Switch (risk/limits.py), Drossel
            # (gates/evaluation.py), Stop-Budget (risk/stop_budget.py) und
            # Positionsgroesse (risk/sizing.py) -- alle vier ueber den einen
            # Aggregator, kontounabhaengig.
            self._enforce_risk(instrument, request, effective_leverage)

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
        # ``pre_net`` (oben, vor jeder Buchung erfasst) + dieser Fill ergibt den
        # resultierenden Netto-Stand -- stromunabhaengig (das lokale Buch wird nur ohne
        # Strom hier mutiert; mit Strom bucht der nachlaufende private Fill).
        if self._sync is None:
            # Ohne Strom optimistisch buchen; mit Strom bucht der autoritative Fill.
            self._book.apply_fill(request.symbol, request.side, send.filled_volume)
        # Akzeptierten Fill an die Risikoschicht melden. Kontounabhaengig: die
        # Zaehler der Drossel und der Positionsdeckel muessen auch auf Demo stimmen,
        # sonst prueft die Sperre dort gegen einen leeren Zustand.
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

    def _enforce_account_freshness(self) -> None:
        """Frische-Latch (S2) fuer eine eroeffnende Order — auf JEDEM Konto.

        Erste der fuenf Sperren aus A3.2. Ein Kontozustand, dessen Alter die Frist
        reisst, ist nicht bewertbar; nicht bewertbar gilt als nicht erfuellt. Ohne
        diese Sperre rechnen Tagesverlustdeckel, Drawdown-Halt und Positionsgroesse
        auf Zahlen, die aussehen wie Messwerte und keine sind.

        Bewusst **nicht** demo-frei: ein veralteter Kontostand ist auf dem Demokonto
        genauso wenig bewertbar wie auf dem Live-Konto, und das Demokonto ist der Ort,
        an dem sich die Sperre beweisen muss.
        """
        account = self._terminal.account()
        verdict = evaluate_account_freshness(
            snapshot_ts=account.ts,
            now=self._clock(),
            connected=self._terminal.is_connected(),
            max_age=self._max_account_age,
        )
        if not verdict.evaluable:
            raise OrderRejectedError(
                f"Kontozustand nicht bewertbar: {verdict.reason} "
                f"(Alter {verdict.age}, Frist {verdict.max_age})",
                reason=verdict.reason or "account_state_unevaluable",
                retryable=True,
            )

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
        # Demo-Reife-Tor (Paket 5): keine Live-Eroeffnung vor >= 180 Tagen Demo-Betrieb
        # mit weiter bestandenem Edge. Fehlt das Reife-Ergebnis -> fail-closed.
        ready = self._demo_readiness
        if ready is None or not ready.ready_for_live_question:
            reasons = ready.reasons if ready is not None else ("demo_readiness_fehlt",)
            raise OrderRejectedError(
                f"Demo-Reife nicht belegt: {', '.join(reasons)}",
                reason="demo_not_ready",
                retryable=False,
            )

    def _enforce_halal(self, instrument: Instrument) -> None:
        """Halal-Screen fuer eine eroeffnende Live-Order (Demo-frei).

        Zweiteilig, beide fail-closed: (1) **mechanische** Konformitaet -- swapfreies
        Konto, zinsfreie Margin, Instrument nicht verboten (``screen_halal``, liest die
        Kontokonfiguration aus ``settings``, Defaults konservativ = nicht konform);
        (2) **Gelehrten-Freigabe** -- ``requires_scholar_review`` ist per Kernregel 16
        IMMER wahr; der Code entscheidet die fiqh-Grundfrage nicht. Eine Live-Order kann
        daher nur eroeffnen, wenn ein Mensch die Gelehrten-Entscheidung als
        ``halal_scholar_review_id`` hinterlegt hat. Auf Demo entfaellt der Screen.
        """
        if self._terminal.account().is_demo:
            return  # Demokonto: kein Echtgeld, Halal-Screen nicht bindend.
        # Defaults konservativ (fail-closed): unbekannt = nicht swapfrei / zinsbehaftet.
        verdict = screen_halal(
            asset_class=instrument.asset_class,
            account_swap_free=getattr(
                self._settings, "halal_account_swap_free", False
            )
            is True,
            interest_bearing_margin=getattr(
                self._settings, "halal_interest_bearing_margin", True
            )
            is not False,
        )
        if not verdict.mechanically_conformant:
            raise OrderRejectedError(
                f"Halal-Screen nicht bestanden: {', '.join(verdict.reasons)}",
                reason="halal_not_conformant",
                retryable=False,
            )
        # Kernregel 16: die fiqh-Grundfrage entscheidet ein Gelehrter, nicht der Code.
        review_id = getattr(self._settings, "halal_scholar_review_id", None)
        if not (review_id is not None and str(review_id).strip()):
            raise OrderRejectedError(
                "Halal: keine Gelehrten-Freigabe (halal_scholar_review_id) hinterlegt",
                reason="halal_scholar_review_missing",
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

    def _enforce_cost_gate(
        self, instrument: Instrument, request: OrderRequest
    ) -> None:
        """Pre-Trade-Kostentor fuer eine eroeffnende Order (Live-Pflicht, Demo-frei).

        Auf Demo entfaellt es (kein Echtgeld) -- wie die Live-Freigabe. Auf Live ohne
        konfiguriertes Tor wird fail-closed abgelehnt: eine Order, deren Kosten nie
        gegen die Backtest-Annahme geprueft wurden, darf nicht eroeffnen.
        """
        if self._terminal.account().is_demo:
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
        account = self._terminal.account()
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
        """Not-Aus: sperrt sofort neue Eroeffnungen (Global-Halt) **und** schliesst alle
        offenen Positionen per Reduce-Only. Gibt die Schliess-Ergebnisse zurueck.

        Der Halt wird **zuerst** gesetzt — scheitert eine Schliessung, bleiben neue
        Eroeffnungen trotzdem gesperrt. Reduce-Only umgeht bewusst Freigabe- und
        Hebel-Tore: Risikoabbau darf nie an einer Sperre haengen. Der Latch klaert nur
        ``clear_halt()``.
        """
        self._require_healthy()
        self._halted = True
        self._halt_reason = "emergency_flatten"
        results: list[OrderResult] = []
        for position in self.get_positions():
            close_side = (
                OrderSide.SELL if position.side is OrderSide.BUY else OrderSide.BUY
            )
            try:
                results.append(
                    self.submit_order(
                        OrderRequest(
                            client_order_id=f"flatten-{position.venue_position_id}",
                            symbol=position.symbol,
                            side=close_side,
                            order_type=OrderType.MARKET,
                            volume=position.volume,
                            stop_loss=Decimal("0"),
                            reduce_only=True,
                            comment="emergency-flatten",
                        )
                    )
                )
            except VenueError:
                # Eine gescheiterte Schliessung darf die uebrigen nicht verhindern;
                # der Global-Halt steht bereits.
                continue
        return tuple(results)


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
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
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

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

Fail-closed: jede nicht sicher zulaessige Order wird abgelehnt, ohne Default. Die
**Politik** (Grenzen, Schwellen, Risikoanteil) traegt der ``RiskPolicy``; die Venue
erzwingt sie am Order-Pfad (siehe ``venue/mt5.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from mt5_trading_ai.gates.evaluation import (
    Candidate,
    GateState,
    OpenPosition,
    ThrottlePolicy,
    select_one,
)
from mt5_trading_ai.risk.limits import (
    AccountSnapshot,
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
from mt5_trading_ai.risk.stop_budget import StopBudget, stop_budget
from mt5_trading_ai.venue.protocol import (
    AccountState,
    Instrument,
    OrderRequest,
)


@dataclass(frozen=True)
class RiskPolicy:
    """Politik der Risikoschicht -- die Grenzen, gegen die jede Eroeffnung prueft.

    ``loss_limits`` und ``throttle`` sind die vorregistrierten Konfigurationen der
    Einzelmodule; ``risk_fraction`` ist der Risikoanteil je Trade (geklammert in
    ``size_position``); ``max_cost_drag``/``safety`` steuern die Budgetspanne;
    ``measured_cost_bps`` erlaubt gemessene Round-Turn-Kosten je Klasse (schlagen die
    Annahmen im Stop-Budget).
    """

    loss_limits: LossLimits = field(default_factory=LossLimits)
    throttle: ThrottlePolicy = field(default_factory=ThrottlePolicy)
    risk_fraction: Decimal = DEFAULT_RISK_FRACTION
    max_cost_drag: Decimal = Decimal("0.05")
    safety: Decimal = Decimal("3")
    measured_cost_bps: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskAuthorization:
    """Ergebnis der Risikopruefung. ``approved`` nur bei sicherer Zulaessigkeit.

    ``latch_halt`` ist wahr, wenn ein Drawdown-Halt greift -- die Venue setzt dann ihren
    ``_halted``-Latch (der sich nicht von selbst loest). ``detail`` traegt die
    Zwischenergebnisse fuer den Nachweis (Limit-Zustand, Budgetspanne, Sizing).
    """

    approved: bool
    reason: str | None
    latch_halt: bool = False
    sizing: SizingResult | None = None
    budget: StopBudget | None = None
    detail: dict[str, str] = field(default_factory=dict)


class RiskManager:
    """Traegt den Risiko-Zustand und autorisiert eroeffnende Orders am Order-Pfad."""

    def __init__(
        self,
        policy: RiskPolicy | None = None,
        *,
        manual_release_id: str | None = None,
        gap_events: tuple[datetime, ...] = (),
    ) -> None:
        self._policy = policy if policy is not None else RiskPolicy()
        #: Manuelle Freigabe nach einem Drawdown-Halt. Ohne sie bleibt der Halt.
        #: Gilt nur fuer die AKTUELLE Episode: erholt sich der Drawdown unter die Grenze
        #: oder vertieft er sich ueber das freigegebene Niveau, wird sie verbraucht.
        self._manual_release_id = manual_release_id
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

    # --- Zustandspflege ---------------------------------------------------
    def observe_equity(self, now: datetime, equity: Decimal) -> None:
        """Nimm eine Equity-Beobachtung auf (Tagesstart + Fenster-Hoechststand)."""
        if self._equity_day != now.date():
            # Neuer Handelstag: Tagesstart-Equity neu setzen (Tageslimit-Bezug).
            self._equity_day = now.date()
            self._day_start_equity = equity
        window = self._policy.loss_limits.drawdown_window
        self._equity_obs.append((now, equity))
        # Alte Beobachtungen ausserhalb des Drawdown-Fensters verwerfen.
        cutoff = now - window
        self._equity_obs = [(ts, eq) for ts, eq in self._equity_obs if ts >= cutoff]

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
        if self._trade_day != day:
            self._trade_day = day
            self._trades_today_instrument = {}
            self._trades_today_account = 0

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

    def record_close(self, instrument: str) -> None:
        """Eine Schliessung: offene Positionen dieses Instruments entfernen."""
        self._open_positions = [
            pos for pos in self._open_positions if pos.instrument != instrument
        ]

    @property
    def open_position_count(self) -> int:
        """Offene (netto je Symbol gefuehrte) Positionen -- fuer den Deckel."""
        return len(self._open_positions)

    def release_drawdown(self, release_id: str) -> None:
        """Manuelle Freigabe nach einem Drawdown-Halt (menschliche Entscheidung).

        Gilt nur fuer die aktuelle Halt-Episode -- der Kill-Switch stellt sich nach
        Erholung oder bei einem tieferen Drawdown von selbst wieder scharf.
        """
        self._manual_release_id = release_id
        self._release_ceiling = None

    # --- Autorisierung ----------------------------------------------------
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
    ) -> RiskAuthorization:
        """Fahre die vier Grenzen in vorgeschriebener Reihenfolge fuer eine Eroeffnung.

        Reihenfolge: Kill-Switch (Limits) -> Drossel -> Stop-Floor/Budget -> Groesse.
        Der erste Verstoss lehnt fail-closed ab. ``latch_halt=True`` bei einem
        Drawdown-Halt (die Venue setzt dann ihren ``_halted``-Latch).
        """
        self.observe_equity(now, account.equity)
        # Frequenz-Tageszaehler auch auf dem LESEpfad rollen (nicht nur beim Fill),
        # sonst blockt eine an Tag N ausgeschoepfte Kappe an Tag N+1 stale weiter.
        self._roll_trade_day(now.date())

        # Freigabe-Gueltigkeit VOR der Limit-Auswertung bestimmen, damit die AKTUELLE
        # Order korrekt entscheidet: die Freigabe deckt nur die aktuelle Halt-Episode.
        peak = self._window_peak(account.equity)
        drawdown = (
            Decimal("1")
            if peak <= 0
            else max(Decimal("0"), peak - account.equity) / peak
        )
        max_dd = self._policy.loss_limits.max_drawdown_fraction
        if self._manual_release_id is not None:
            if drawdown < max_dd:
                # Erholt -> Episode vorbei, Kill-Switch wieder scharf.
                self._manual_release_id = None
                self._release_ceiling = None
            elif self._release_ceiling is None:
                # Erstes Sehen in der Episode -> freigegebenes Niveau festhalten.
                self._release_ceiling = drawdown
            elif drawdown > self._release_ceiling:
                # Drawdown vertieft sich ueber das freigegebene Niveau -> neuer Halt.
                self._manual_release_id = None
                self._release_ceiling = None

        # 1) Kill-Switch (evaluate_limits): Tagesverlust, Drawdown, Deckel, Gap.
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
        limit = evaluate_limits(snapshot, self._policy.loss_limits)
        if not limit.may_open:
            halt = limit.state is TradingState.HALTED
            reason = f"risk_{limit.reasons[0]}" if limit.reasons else "risk_blocked"
            return RiskAuthorization(
                approved=False,
                reason=reason,
                latch_halt=halt,
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
        budget = stop_budget(
            asset_class=instrument.asset_class.value,
            leverage=leverage,
            measured_cost_bps=self._policy.measured_cost_bps.get(
                instrument.asset_class.value
            ),
            max_cost_drag=self._policy.max_cost_drag,
            safety=self._policy.safety,
        )
        if not budget.tradeable:
            return RiskAuthorization(
                approved=False,
                reason=f"stop_budget_{budget.reason or 'untradeable'}",
                budget=budget,
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
                },
            )

        return RiskAuthorization(
            approved=True,
            reason=None,
            sizing=sizing,
            budget=budget,
            detail={"budget_volume": str(sizing.volume)},
        )

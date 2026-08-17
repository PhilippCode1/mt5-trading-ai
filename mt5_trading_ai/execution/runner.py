"""Integrierender Paper/Dry-Run-Runner (Paket 7): die eine beweisbare Kette.

Die Naehte aus Paket 3-5 sind einzeln verdrahtet und getestet; dieser Runner fuehrt sie
in EINEM Durchlauf je Signal zusammen und quittiert jede als Checklisten-Punkt:

    Zulassung(§9.3) -> Signal -> Daten-Tor -> Halal -> Hebel -> Stop-Preis -> Kostentor
    -> Limits -> Evaluation -> Stop-Budget -> Sizing -> submit_order -> Buchung.

**Warum die Tore hier explizit stehen und nicht nur ueber submit_order laufen:** der
Runner quittiert jede Naht einzeln. ``submit_order`` faellt bei der ersten Sperre mit
einer Begruendung aus; die Checkliste braucht dagegen je Naht ein Ergebnis, auch fuer
die Naehte hinter der ersten roten. Ausserdem sind Kostentor und Halal-Screen am Venue
demo-frei (kein Echtgeld, keine reale Zinsbelastung) -- der Runner faehrt sie trotzdem,
damit die Nachweisfahrt sie belegt.

**Kein Doppel-Buchen:** Runner und Venue teilen **einen** ``RiskManager``. Zwei
getrennte Manager haetten zwei getrennte Frequenz- und Positionszaehler, von denen
keiner das Ganze saehe. Seit Paket 2 (A3) faehrt ``Mt5Venue.submit_order`` die
Risikoschicht auf **jedem** Konto und bucht den akzeptierten Fill selbst; erkennt der
Runner denselben Manager wieder, quittiert er nur (Schritt 10). Haelt ein Aufrufer
bewusst zwei getrennte Manager, bucht der Runner -- beides fuehrt zu genau einer
Buchung.

Fail-closed: jede Naht, die nicht sicher gruen ist, bricht die Kette ab und wird mit
Begruendung protokolliert; es wird nichts eroeffnet.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal

from mt5_trading_ai.backtest.engine import Signal
from mt5_trading_ai.execution.cost_gate import CostGate, evaluate_cost_gate
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.gates.criteria import CriteriaVerdict
from mt5_trading_ai.risk.leverage import clamp_leverage
from mt5_trading_ai.risk.sizing import StopFloorInputs, executable_stop_floor
from mt5_trading_ai.risk.stop_budget import stop_budget
from mt5_trading_ai.venue.halal import screen_halal
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.protocol import (
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderType,
    VenueError,
)

RUNNER_VERSION = "paper-runner-v1"


@dataclass(frozen=True)
class RunnerConfig:
    """Politik/Konfiguration des Runners fuer eine eroeffnende Order.

    ``account_swap_free``/``interest_bearing_margin``/``scholar_review_id`` speisen den
    Halal-Screen (Defaults konservativ = nicht konform, wie am Venue). ``cost_gate``
    traegt die im Backtest vorausgesetzte Kostenobergrenze; ``requested_leverage`` den
    Hebelwunsch (fehlt er -> konservativer Klassendefault). ``measured_cost_bps`` sind
    die je Klasse gemessenen Round-Turn-Kosten fuer die Stop-Budget-Spanne (leer ->
    Annahmetabelle).
    """

    cost_gate: CostGate
    account_swap_free: bool = False
    interest_bearing_margin: bool = True
    scholar_review_id: str = ""
    requested_leverage: object | None = None
    measured_cost_bps: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class SeamStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class RunnerReport:
    """Die Abnahme-Checkliste eines Laufs: je Naht ein Schritt, plus das Ergebnis."""

    steps: list[SeamStep] = field(default_factory=list)
    submitted: OrderResult | None = None
    reject_reason: str | None = None
    version: str = RUNNER_VERSION

    @property
    def opened(self) -> bool:
        return self.submitted is not None and self.submitted.accepted

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.steps.append(SeamStep(name, ok, detail))

    def _reject(self, name: str, reason: str, detail: str = "") -> RunnerReport:
        self.add(name, False, detail or reason)
        self.reject_reason = reason
        return self


def _spread_bps(bid: Decimal, ask: Decimal) -> Decimal:
    mid = (ask + bid) / Decimal("2")
    if mid <= 0:
        return Decimal("0")
    return (ask - bid) / mid * Decimal("10000")


def _quantise(value: Decimal, tick: Decimal, side: OrderSide) -> Decimal:
    """Stop VOM Markt weg auf das Tick-Raster runden (BUY runter, SELL rauf) -- sonst
    lehnt der Platz mit INVALID_STOPS ab."""
    rounding = ROUND_DOWN if side is OrderSide.BUY else ROUND_UP
    return (value / tick).to_integral_value(rounding=rounding) * tick


def run_signal(
    *,
    venue: Mt5Venue,
    risk_manager: RiskManager,
    admission: CriteriaVerdict,
    symbol: str,
    side: Signal,
    config: RunnerConfig,
    now: datetime,
    client_order_id: str,
) -> RunnerReport:
    """Fuehre EIN Signal durch die volle Kette. Gibt die Checkliste + das Ergebnis.

    ``admission`` ist das §9.3-Zulassungsurteil (``evaluate_criteria``) -- ohne
    bestandene Zulassung handelt die Strategie nicht (Stufe A, fail-closed). ``side``
    ist die Signalrichtung; ``Signal.FLAT`` eroeffnet nichts (kein Handel).
    """
    report = RunnerReport()

    # Stufe A: Zulassung (§9.3). Provenienz + Deflation stecken in der Evidenz
    # (deflated_sharpe/trial_count aus dem herkunftsgebundenen Register).
    if not admission.passed:
        return report._reject(
            "zulassung", "strategy_not_admitted",
            detail=f"nicht erfuellt: {', '.join(admission.unmet) or 'unbekannt'}",
        )
    report.add("zulassung", True, "§9.3-Kriterien bestanden")

    # 1) Signal.
    if side is Signal.FLAT:
        report.add("signal", True, "FLAT -- keine Eroeffnung")
        return report
    side_enum = OrderSide.BUY if side is Signal.LONG else OrderSide.SELL
    report.add("signal", True, side_enum.value)

    # 2) Daten-Tor: Instrument/Quote/Konto; Referenzpreis > 0.
    try:
        instrument = venue.get_instrument(symbol)
        quote = venue.get_quote(symbol)
        account = venue.get_account()
    except VenueError as exc:
        return report._reject("daten-tor", "venue_unavailable", detail=str(exc))
    ref = quote.ask if side_enum is OrderSide.BUY else quote.bid
    if ref <= 0:
        return report._reject("daten-tor", "price_missing", detail=f"ref={ref}")
    # Der Paper-Runner laeuft ausschliesslich auf Demo -- fail-closed. Er fuehrt eine
    # Nachweisfahrt und traegt weder Live-Freigabe noch Demo-Reife; ein Live-Konto
    # gehoert nicht an diesen Pfad. (Die frueher hier begruendete Doppelbuchung ist
    # seit Paket 2 anders geloest: Runner und Venue teilen einen RiskManager, und
    # gebucht wird genau einmal -- siehe Schritt 10.)
    if not account.is_demo:
        return report._reject(
            "daten-tor", "runner_requires_demo",
            detail="Paper-Runner laeuft nur auf einem Demokonto")
    report.add("daten-tor", True, f"ref={ref} spread={quote.spread}")

    # 3) Halal-Screen (am Venue demo-frei -> hier bindend, damit belegt).
    halal = screen_halal(
        asset_class=instrument.asset_class,
        account_swap_free=config.account_swap_free,
        interest_bearing_margin=config.interest_bearing_margin,
    )
    if not halal.mechanically_conformant:
        return report._reject("halal", "halal_not_conformant",
                              detail=", ".join(halal.reasons))
    if not config.scholar_review_id.strip():
        return report._reject("halal", "halal_scholar_review_missing",
                              detail="keine Gelehrten-Freigabe hinterlegt")
    report.add("halal", True, "mechanisch konform + Gelehrten-Freigabe hinterlegt")

    # 4) Hebel-Klammer: effektiver Hebel (einzige gueltige Quelle fuer Budget + Sizing).
    lev = clamp_leverage(
        requested=config.requested_leverage,
        asset_class=instrument.asset_class.value,
    )
    if lev.leverage is None:
        return report._reject("hebel", lev.reason or "leverage_no_trade")
    eff_lev = lev.leverage
    report.add("hebel", True, f"eff_lev={eff_lev} ({lev.binding})")

    # 5) Stop-Distanz (bps) -> Stop-PREIS. Floor gegen Budget-Spanne je Klasse/Hebel.
    floor = executable_stop_floor(
        StopFloorInputs(
            spread_bps=_spread_bps(quote.bid, quote.ask),
            tick_size_bps=instrument.tick_size / ref * Decimal("10000"),
            volatility_bps=Decimal("0"),  # je Bar nicht da (SPAETER); Floor nimmt max
            broker_stop_level_bps=Decimal(instrument.stop_level_points)
            * instrument.tick_size / ref * Decimal("10000"),
            depth_ratio=None,
        )
    )
    budget = stop_budget(
        asset_class=instrument.asset_class.value,
        leverage=eff_lev,
        measured_cost_bps=config.measured_cost_bps.get(instrument.asset_class.value),
    )
    if not budget.tradeable:
        return report._reject(
            "stop-preis", f"stop_budget_{budget.reason or 'untradeable'}")
    stop_bps = min(max(floor.executable_floor_bps, budget.lower_bps), budget.upper_bps)
    dist = ref * stop_bps / Decimal("10000")
    stop_loss = _quantise(
        ref - dist if side_enum is OrderSide.BUY else ref + dist,
        instrument.tick_size, side_enum,
    )
    if stop_loss <= 0:
        return report._reject("stop-preis", "stop_price_nonpositive")
    report.add("stop-preis", True, f"{stop_bps:.1f}bps -> stop={stop_loss}")

    # 6) Kandidaten-OrderRequest (vorlaeufiges Volumen = Mindestvolumen).
    request = OrderRequest(
        client_order_id=client_order_id,
        symbol=symbol,
        side=side_enum,
        order_type=OrderType.MARKET,
        volume=instrument.volume_min,
        stop_loss=stop_loss,
        meta={"requested_leverage": eff_lev},
    )

    # 7) Kostentor (am Venue demo-frei -> hier bindend, damit belegt).
    cost = evaluate_cost_gate(
        gate=config.cost_gate, instrument=instrument, fees=instrument.fees,
        side=side_enum, volume=request.volume, bid=quote.bid, ask=quote.ask,
    )
    if not cost.approved:
        return report._reject("kostentor", cost.reason or "cost_gate",
                              detail=cost.detail or "")
    report.add("kostentor", True, f"cost_fraction={cost.cost_fraction}")

    # 8) Risikoschicht: Limits -> Evaluation -> Stop-Budget -> Sizing (fusioniert).
    auth = risk_manager.authorize_opening(
        instrument=instrument, request=request, account=account, price=ref,
        spread_bps=_spread_bps(quote.bid, quote.ask), leverage=eff_lev, now=now,
    )
    if not auth.approved:
        if auth.latch_halt:
            # Drawdown-Halt: der Latch haelt nicht von selbst -> am Venue setzen (S2).
            venue.latch_halt(reason=auth.reason or "risk_halt")
        detail = ", ".join(f"{k}={v}" for k, v in auth.detail.items())
        return report._reject("risiko", auth.reason or "risk_blocked", detail=detail)
    # Die vier fusionierten Naehte als je eigenen Checklisten-Punkt quittieren.
    report.add("limits", True, "Kill-Switch: NORMAL")
    report.add("evaluation", True, "Drossel: ausgewaehlt")
    if auth.budget is not None:
        report.add("stop-budget", True,
                   f"[{auth.budget.lower_bps:.1f}, {auth.budget.upper_bps:.1f}]bps")
    sized_volume = auth.sizing.volume if auth.sizing is not None else None
    if sized_volume is None:
        return report._reject("sizing", "risk_sizing_no_volume")
    report.add("sizing", True, f"volume={sized_volume}")

    # 9) Submit: die eigentliche Paper-Order. ``submit_order`` erzwingt Hebel, Frische
    # und die volle Risikoschicht erneut (auf jedem Konto), auf Live zusaetzlich
    # Halal-Screen, Live-Freigabe und Kostentor -- Defense-in-Depth.
    request = replace(request, volume=sized_volume)
    try:
        result = venue.submit_order(request)
    except VenueError as exc:
        reason = getattr(exc, "reason", None) or "submit_rejected"
        return report._reject("submit", reason, detail=str(exc))
    report.submitted = result
    report.add("submit", result.accepted, f"venue_order_id={result.venue_order_id}")

    # 10) Buchung: den akzeptierten Fill der Risikoschicht melden (Frequenz/Deckel).
    # Genau EINMAL. Seit Paket 2 (A3) faehrt ``submit_order`` die Risikoschicht auf
    # jedem Konto und bucht den Fill selbst. Teilt sich der Runner denselben Manager
    # mit dem Venue -- der Regelfall, weil zwei getrennte Zaehlerstaende keiner
    # kennt --, dann hat das Venue bereits gebucht und der Runner quittiert nur.
    # NICHT bei einem idempotenten Replay: submit_order gibt bei wiederholter
    # client_order_id accepted=True OHNE zweite Order zurueck -- ein zweites
    # record_open_fill wuerde den Frequenz-/Tagesdeckel-Zaehler verfaelschen (§9).
    if result.accepted and not result.idempotent_replay:
        if venue.risk_manager is risk_manager:
            report.add("buchung", True, "record_open_fill (Venue, geteilter Manager)")
        else:
            risk_manager.record_open_fill(symbol, result.ts)
            report.add("buchung", True, "record_open_fill")
    elif result.idempotent_replay:
        report.add("buchung", True, "idempotenter Replay -- nicht erneut gebucht")

    return report

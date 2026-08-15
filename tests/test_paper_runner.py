"""Paket 7: der integrierende Runner + der Treiber-Loop, gegen ein Fake-Terminal.

Prueft die volle Kette Signal -> ... -> submit_order als EINEN Lauf (Checkliste Punkt fuer
Punkt gruen) und den Scheduler, der Frische/Drift getaktet in den Halt setzt -- inklusive
der S2-Kante (ein nie gestarteter Strom) und simulierter Positions-Drift. Jede Wache ist
negativ gefahren.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.engine import Signal
from mt5_trading_ai.execution.cost_gate import CostGate
from mt5_trading_ai.execution.private_sync import (
    PrivateEvent,
    PrivateEventKind,
    PrivateSync,
)
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal
from mt5_trading_ai.execution.scheduler import SyncScheduler
from mt5_trading_ai.gates.criteria import CriteriaVerdict
from mt5_trading_ai.venue.mt5 import (
    CatalogEntry,
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (
    AssetClass,
    FeeSchedule,
    Timeframe,
    TradingSession,
)

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)  # Dienstag, 12:00 UTC
LENIENT_GATE = CostGate(max_roundturn_cost_fraction=Decimal("0.0005"))  # 5 bp
MAX_SILENCE = timedelta(minutes=5)


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _sym(symbol: str) -> Mt5Symbol:
    crypto = symbol == "BTCUSD"
    return Mt5Symbol(
        name=symbol,
        digits=2 if crypto else 5,
        tick_size=Decimal("0.01") if crypto else Decimal("0.00001"),
        pip_size=Decimal("0.01") if crypto else Decimal("0.0001"),
        contract_size=Decimal("1") if crypto else Decimal("100000"),
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="BTC" if crypto else "EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        visible=True,
    )


def _catalog() -> dict[str, CatalogEntry]:
    sessions = tuple(
        TradingSession(weekday=d, open_utc="00:00", close_utc="22:00") for d in range(5)
    )
    return {
        "EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), sessions),
        "BTCUSD": CatalogEntry(AssetClass.CRYPTO, _fees(), sessions),
    }


class FakeTerminal:
    """In-Memory-Terminal (erfuellt ``Mt5Terminal``). Konfigurierbar fuer die Szenarien."""

    def __init__(
        self,
        *,
        is_demo: bool = True,
        equity: Decimal = Decimal("10000"),
        positions: tuple[Mt5Position, ...] = (),
        accept: bool = True,
    ) -> None:
        self._connected = False
        self._symbols = {"EURUSD": _sym("EURUSD"), "BTCUSD": _sym("BTCUSD")}
        self._account = Mt5Account(
            account_id="123", currency="USD", balance=equity, equity=equity,
            margin_used=Decimal("0"), margin_free=Decimal("100000"),
            is_demo=is_demo, ts=TS,
        )
        self._positions = positions
        self._accept = accept
        self.order_send_calls = 0

    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return tuple(self._symbols.values())

    def symbol(self, name: str) -> Mt5Symbol | None:
        return self._symbols.get(name)

    def tick(self, name: str) -> Mt5Tick | None:
        if name not in self._symbols:
            return None
        if name == "BTCUSD":
            return Mt5Tick(ts=TS, bid=Decimal("60000"), ask=Decimal("60010"))
        return Mt5Tick(ts=TS, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return (
            Mt5Rate(ts=TS, open=Decimal("1.1"), high=Decimal("1.2"),
                    low=Decimal("1.0"), close=Decimal("1.15"), tick_volume=100),
        )

    def order_send(self, request: object) -> Mt5SendResult:
        self.order_send_calls += 1
        return Mt5SendResult(
            accepted=self._accept, venue_order_id="V-1" if self._accept else None,
            filled_volume=Decimal("0.15") if self._accept else Decimal("0"),
            average_price=Decimal("1.10000"), ts=TS,
            reason="done" if self._accept else "rejected",
        )

    def cancel(self, venue_order_id: str) -> bool:
        return True

    def modify_stops(self, vid: str, sl: Decimal | None, tp: Decimal | None) -> bool:
        return True

    def positions(self) -> tuple[Mt5Position, ...]:
        return self._positions

    def account(self) -> Mt5Account:
        return self._account


def _venue(
    *,
    is_demo: bool = True,
    equity: Decimal = Decimal("10000"),
    positions: tuple[Mt5Position, ...] = (),
    accept: bool = True,
    sync: PrivateSync | None = None,
    max_notional_drift: Decimal = Decimal("0"),
) -> Mt5Venue:
    terminal = FakeTerminal(
        is_demo=is_demo, equity=equity, positions=positions, accept=accept
    )
    venue = Mt5Venue(
        name="mt5-demo", terminal=terminal, catalog=_catalog(),
        sync=sync, max_notional_drift=max_notional_drift,
    )
    venue.connect()
    return venue


def _admitted() -> CriteriaVerdict:
    return CriteriaVerdict(passed=True, results=())


def _config(**overrides: object) -> RunnerConfig:
    base: dict[str, object] = {
        "cost_gate": LENIENT_GATE,
        "account_swap_free": True,
        "interest_bearing_margin": False,
        "scholar_review_id": "scholar-2026/eurusd-cfd",
    }
    base.update(overrides)
    return RunnerConfig(**base)  # type: ignore[arg-type]


def _run(**overrides: object):
    kwargs: dict[str, object] = {
        "venue": _venue(),
        "risk_manager": RiskManager(),
        "admission": _admitted(),
        "symbol": "EURUSD",
        "side": Signal.LONG,
        "config": _config(),
        "now": TS,
        "client_order_id": "run-1",
    }
    kwargs.update(overrides)
    return run_signal(**kwargs)  # type: ignore[arg-type]


# --- Runner: die volle Kette ---------------------------------------------

_SEAMS = {
    "zulassung", "signal", "daten-tor", "halal", "hebel", "stop-preis",
    "kostentor", "limits", "evaluation", "stop-budget", "sizing", "submit", "buchung",
}


def test_full_chain_opens_and_every_seam_is_green() -> None:
    report = _run()
    assert report.opened, [s for s in report.steps if not s.ok]
    assert report.ok
    names = {step.name for step in report.steps}
    assert _SEAMS <= names, f"fehlende Naht: {_SEAMS - names}"
    assert report.reject_reason is None


def test_records_fill_so_frequency_state_advances() -> None:
    rm = RiskManager()
    _run(venue=_venue(), risk_manager=rm)
    assert rm.open_position_count == 1  # record_open_fill lief genau einmal


def test_not_admitted_strategy_does_not_trade() -> None:
    report = _run(admission=CriteriaVerdict(passed=False, results=(), unmet=("deflated_sharpe",)))
    assert not report.opened
    assert report.reject_reason == "strategy_not_admitted"
    assert report.steps[0].name == "zulassung" and not report.steps[0].ok


def test_non_demo_account_is_rejected_variant_b() -> None:
    # Variante B laeuft nur auf Demo: gegen ein Live-Konto wuerde submit_order die
    # Risikoschicht selbst fahren + buchen -> Doppelzaehlung; fail-closed davor.
    report = _run(venue=_venue(is_demo=False))
    assert not report.opened
    assert report.reject_reason == "runner_requires_demo"


def test_flat_signal_opens_nothing() -> None:
    report = _run(side=Signal.FLAT)
    assert not report.opened
    assert report.submitted is None
    assert {s.name for s in report.steps} == {"zulassung", "signal"}


def test_halal_rejects_crypto() -> None:
    report = _run(symbol="BTCUSD")
    assert not report.opened
    assert report.reject_reason == "halal_not_conformant"


def test_missing_scholar_review_rejects() -> None:
    report = _run(config=_config(scholar_review_id=""))
    assert not report.opened
    assert report.reject_reason == "halal_scholar_review_missing"


def test_cost_gate_rejects_when_over_threshold() -> None:
    report = _run(config=_config(cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.00001"))))
    assert not report.opened
    assert report.reject_reason == "cost_gate"


def test_drawdown_halt_latches_the_venue() -> None:
    # Risiko-Naht -> Halt -> S2-Latch: ein Fenster-Peak weit ueber der aktuellen Equity
    # (>10 % Drawdown) haltet, und der Runner setzt den Venue-Latch (haelt nicht selbst).
    venue = _venue(equity=Decimal("8000"))
    rm = RiskManager()
    rm.observe_equity(TS - timedelta(days=1), Decimal("10000"))  # Peak
    report = _run(venue=venue, risk_manager=rm)
    assert not report.opened
    assert report.reject_reason is not None and report.reject_reason.startswith("risk_")
    assert venue.is_halted()  # der Latch ist gesetzt


# --- Scheduler: Frische/Drift getaktet -----------------------------------


def _fill(seq: int, ts: datetime) -> PrivateEvent:
    return PrivateEvent(seq=seq, ts=ts, kind=PrivateEventKind.HEARTBEAT)


def test_scheduler_clean_tick_does_not_halt() -> None:
    venue = _venue(sync=PrivateSync())
    venue.adopt_book()  # Buch = Meldung -> keine Drift
    sched = SyncScheduler(venue, max_silence=MAX_SILENCE, started_at=TS)
    result = sched.tick(TS, events=[_fill(1, TS)])
    assert not result.halted
    assert result.sync_healthy


def test_scheduler_never_started_stream_latches_halt_S2() -> None:
    # S2: ein konfigurierter Strom, der bis started_at+max_silence NIE ein Ereignis
    # lieferte, ist fuer check_sync unsichtbar (is_stale blind) -> der Scheduler latcht.
    venue = _venue(sync=PrivateSync())
    venue.adopt_book()
    sched = SyncScheduler(venue, max_silence=MAX_SILENCE, started_at=TS)
    result = sched.tick(TS + 2 * MAX_SILENCE)  # keine Ereignisse
    assert result.stream_never_started
    assert result.halted
    assert venue.halt_reason == "stream_never_started"


def test_scheduler_silence_after_first_event_halts() -> None:
    venue = _venue(sync=PrivateSync())
    venue.adopt_book()
    sched = SyncScheduler(venue, max_silence=MAX_SILENCE, started_at=TS)
    sched.tick(TS, events=[_fill(1, TS)])           # Strom lebt
    result = sched.tick(TS + 2 * MAX_SILENCE)       # danach still
    assert result.halted
    assert not result.sync_healthy


def test_scheduler_position_drift_latches_halt() -> None:
    # Simulierte Drift: das Buch ist leer, die Boerse meldet eine Position -> reconcile
    # setzt den Halt automatisch (Abnahmekriterium).
    drift_pos = Mt5Position(
        ticket="T-1", symbol="EURUSD", is_buy=True, volume=Decimal("0.10"),
        entry_price=Decimal("1.10000"), stop_loss=None, take_profit=None,
        opened_at=TS, unrealised_pnl=Decimal("0"), swap=Decimal("0"),
    )
    venue = _venue(sync=PrivateSync(), positions=(drift_pos,))
    # Buch bewusst NICHT adoptiert -> leer, weicht von der gemeldeten Position ab.
    sched = SyncScheduler(venue, max_silence=MAX_SILENCE, started_at=TS)
    result = sched.tick(TS, events=[_fill(1, TS)])
    assert result.reconcile is not None and result.reconcile.halt
    assert result.halted
    # §9 Finding 3: der Halt-Grund ist gesetzt (nicht None) und nennt die Ursache.
    assert venue.halt_reason is not None and "reconcile_drift" in venue.halt_reason


def test_scheduler_dead_session_latches_even_with_risk_manager() -> None:
    # §9-BLOCKER: get_account() wirft bei toter Sitzung. Mit verdrahtetem RiskManager
    # darf die Ausnahme aus Schritt 1 (observe_equity) die Halt-Logik NICHT praemptieren
    # -- der Takt muss trotzdem fail-closed latchen, statt aus tick() zu propagieren.
    venue = _venue(sync=PrivateSync())
    venue.adopt_book()
    venue.disconnect()  # Sitzung weg
    sched = SyncScheduler(
        venue, max_silence=MAX_SILENCE, started_at=TS, risk_manager=RiskManager()
    )
    result = sched.tick(TS)  # darf NICHT werfen
    assert result.halted
    assert venue.is_halted()


def test_idempotent_replay_is_not_rebooked() -> None:
    # §9 Finding 2: ein Retry mit stabiler client_order_id liefert idempotent_replay=True
    # OHNE zweite Order -- der Runner darf record_open_fill nicht ein zweites Mal rufen.
    venue = _venue()
    rm = RiskManager()
    r1 = _run(venue=venue, risk_manager=rm, client_order_id="dup", now=TS)
    assert r1.opened
    r2 = _run(
        venue=venue, risk_manager=rm, client_order_id="dup", now=TS + timedelta(hours=1)
    )
    assert r2.submitted is not None and r2.submitted.idempotent_replay
    assert rm._trades_today_account == 1  # nicht doppelt gezaehlt


# --- Das eine Kommando (tools/paper_run.py) ------------------------------


def _load_paper_run() -> object:
    tools = Path(__file__).resolve().parents[1] / "tools"
    spec = importlib.util.spec_from_file_location("paper_run_cli", tools / "paper_run.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paper_run_full_chain_opens_green() -> None:
    module = _load_paper_run()
    report, halted = module.run_paper("EURUSD")  # type: ignore[attr-defined]
    assert report.opened and report.ok
    assert not halted  # sauberer Takt (Heartbeat, keine Drift)


def test_paper_run_command_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_paper_run()
    monkeypatch.setattr(sys, "argv", ["paper_run.py", "--symbol", "EURUSD"])
    assert int(module.main()) == 0  # type: ignore[attr-defined]

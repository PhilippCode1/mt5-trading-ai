#!/usr/bin/env python3
"""Paket 7: das EINE Kommando -- die volle Kette Signal -> ... -> Order als Paper-Lauf.

Fuehrt ``execution/runner.py`` (die integrierte Naht-Kette) und
``execution/scheduler.py`` (Frische/Drift getaktet) gegen ein **synthetisches
Demo-Terminal** vor und druckt die
Abnahme-Checkliste Punkt fuer Punkt. Kein Echtgeld, kein echtes MT5 noetig -- der reale
Lauf steckt statt des synthetischen Terminals ein ``RealMt5Terminal`` (Demokonto)
hinein; die sicherheits- und ablaufkritische Logik ist dieselbe.

Die **Zulassung** (§9.3) ist hier ein deutlich markierter DEMO-Platzhalter: im echten
Betrieb kommt sie aus ``evaluate_criteria`` eines realen OoS-Laufs (``edge_test``) --
ohne bestandene Zulassung handelt keine Strategie.

Der Zustand des Laufs (Risikozustand, Schwebeakte, Positionsbuch) liegt in
``--zustandsordner``; ohne Angabe in einem Wegwerfordner, der nach dem Lauf
geloescht wird -- eine Nachweisfahrt gegen ein synthetisches Terminal hat im
Zustandsordner des Betriebs nichts verloren (D8, E-005).

Aufruf:  python tools/paper_run.py [--symbol EURUSD] [--zustandsordner ORDNER]
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.engine import Signal  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.private_sync import (  # noqa: E402
    PrivateEvent,
    PrivateEventKind,
    PrivateSync,
)
from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    DateiZustand,
    standard_zustandsdatei,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import (  # noqa: E402
    RunnerConfig,
    RunnerReport,
    run_signal,
)
from mt5_trading_ai.execution.scheduler import SyncScheduler  # noqa: E402
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.venue.catalog import CatalogEntry  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Account,
    Mt5Position,
    Mt5Rate,
    Mt5SendResult,
    Mt5Symbol,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AssetClass,
    FeeSchedule,
    Timeframe,
    TradingSession,
)

_TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


class PaperTerminal:
    """Synthetisches Demo-Terminal (erfuellt ``Mt5Terminal``). KEIN Marktdatum -- ein
    fester, plausibler Zustand fuer die Nachweisfahrt. ``is_demo=True`` (Echtgeld hart
    gesperrt)."""

    def __init__(self) -> None:
        self._connected = False
        self._symbol = Mt5Symbol(
            name="EURUSD",
            digits=5,
            tick_size=Decimal("0.00001"),
            pip_size=Decimal("0.0001"),
            contract_size=Decimal("100000"),
            volume_min=Decimal("0.01"),
            volume_step=Decimal("0.01"),
            volume_max=Decimal("100"),
            base_currency="EUR",
            quote_currency="USD",
            stop_level_points=10,
            freeze_level_points=0,
            visible=True,
        )
        self._account = Mt5Account(
            account_id="DEMO-1",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=Decimal("100000"),
            is_demo=True,
            ts=_TS,
        )

    def initialize(self) -> bool:
        self._connected = True
        return True

    def shutdown(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (self._symbol,)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return self._symbol if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        if name != "EURUSD":
            return None
        return Mt5Tick(ts=_TS, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return (
            Mt5Rate(
                ts=_TS,
                open=Decimal("1.1"),
                high=Decimal("1.2"),
                low=Decimal("1.0"),
                close=Decimal("1.15"),
                tick_volume=100,
            ),
        )

    def order_send(self, request: object) -> Mt5SendResult:
        return Mt5SendResult(
            accepted=True,
            venue_order_id="PAPER-1",
            filled_volume=Decimal("0.15"),
            average_price=Decimal("1.10000"),
            ts=_TS,
            reason="done",
        )

    def cancel(self, venue_order_id: str) -> bool:
        return True

    def modify_stops(self, vid: str, sl: Decimal | None, tp: Decimal | None) -> bool:
        return True

    def positions(self) -> tuple[Mt5Position, ...]:
        return ()

    def account(self) -> Mt5Account:
        return self._account


def _catalog() -> dict[str, CatalogEntry]:
    fees = FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )
    sessions = tuple(
        TradingSession(weekday=d, open_utc="00:00", close_utc="22:00") for d in range(5)
    )
    return {"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, fees, sessions)}


def build_paper_venue(
    risk_manager: RiskManager, *, now: datetime = _TS, zustandsordner: Path
) -> Mt5Venue:
    """Ein verbundenes Demo-Venue mit verdrahteter Risikoschicht.

    Der Manager wird von aussen hereingereicht und ist **derselbe**, den der Runner
    benutzt: zwei getrennte Manager haetten zwei getrennte Frequenz- und
    Positionszaehler, und keiner saehe das Ganze. Gebucht wird genau einmal (das
    Venue bucht, der Runner quittiert).

    ``now`` setzt die Uhr des Frische-Latches auf die Zeitbasis des Laufs -- das
    synthetische Terminal stempelt einen festen Kontozustand. ``zustandsordner``
    traegt Schwebeakte und Positionsbuch (D8): auch ein Paper-Venue ist ohne Ort
    nicht konstruierbar.
    """
    venue = Mt5Venue(
        name="paper",
        terminal=PaperTerminal(),
        catalog=_catalog(),
        sync=PrivateSync(),
        max_notional_drift=Decimal("0"),
        risk_manager=risk_manager,
        clock=lambda: now,
        zustandsordner=zustandsordner,
    )
    venue.connect()
    return venue


def _demo_admission() -> CriteriaVerdict:
    """DEMO-Platzhalter fuer die §9.3-Zulassung -- im echten Betrieb aus
    ``evaluate_criteria`` eines realen OoS-Laufs (siehe Docstring)."""
    return CriteriaVerdict(passed=True, results=())


def run_paper(
    symbol: str, *, now: datetime | None = None, zustandsordner: Path
) -> tuple[RunnerReport, bool]:
    """Fahre einen Paper-Lauf: volle Kette + ein Scheduler-Takt -> (Report, halt).

    ``zustandsordner`` ist Pflicht (D8): der Risikozustand des Laufs liegt dort als
    Datei, nie fluechtig -- ``main`` legt ohne Angabe einen Wegwerfordner an.
    """
    at = now if now is not None else _TS
    risk_manager = RiskManager(
        zustand=DateiZustand(standard_zustandsdatei(ordner=zustandsordner))
    )
    venue = build_paper_venue(risk_manager, now=at, zustandsordner=zustandsordner)
    venue.adopt_book()  # Buch = Meldung -> ein sauberer erster Reconcile
    config = RunnerConfig(
        cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
    )
    report = run_signal(
        venue=venue,
        risk_manager=risk_manager,
        admission=_demo_admission(),
        symbol=symbol,
        side=Signal.LONG,
        config=config,
        now=at,
        client_order_id=f"paper-{symbol}-{int(at.timestamp())}",
        # Die Nachweisfahrt sendet an das synthetische Terminal -- mit Schreibrecht,
        # sonst endete die Kette vor dem Senden (D1).
        darf_schreiben=True,
    )
    # Ein Scheduler-Takt mit einem Startup-Heartbeat: Frische/Drift getaktet geprueft.
    scheduler = SyncScheduler(venue, max_silence=timedelta(minutes=5), started_at=at)
    tick = scheduler.tick(
        at, events=[PrivateEvent(seq=1, ts=at, kind=PrivateEventKind.HEARTBEAT)]
    )
    return report, tick.halted


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Paper-Run: volle Kette + Checkliste")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument(
        "--zustandsordner",
        type=Path,
        default=None,
        metavar="ORDNER",
        help="Ordner fuer den Zustand des Laufs (Vorgabe: Wegwerfordner, wird "
        "danach geloescht)",
    )
    args = ap.parse_args(argv)

    wegwerf = args.zustandsordner is None
    ordner = (
        Path(tempfile.mkdtemp(prefix="paper_run-")) if wegwerf else args.zustandsordner
    )
    try:
        report, halted = run_paper(args.symbol, zustandsordner=ordner)
    finally:
        if wegwerf:
            shutil.rmtree(ordner, ignore_errors=True)

    print("=== ABNAHME-CHECKLISTE (Signal -> ... -> Order, Paper) ===")
    for step in report.steps:
        mark = "OK  " if step.ok else "FAIL"
        print(f"  [{mark}] {step.name:12s} {step.detail}")
    ergebnis = "EROEFFNET" if report.opened else f"KEIN OPEN ({report.reject_reason})"
    print(f"\nErgebnis: {ergebnis}")
    print(f"Scheduler-Takt: Halt={'JA' if halted else 'nein'} (Frische/Drift geprueft)")
    # Exit 0, wenn die Kette sauber durchlief UND eroeffnete (Abnahme-Happy-Path).
    return 0 if report.opened and report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

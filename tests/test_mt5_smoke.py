"""Test der Smoke-Orchestrierung gegen ein Fake-Terminal.

Prueft die Sicherheits- und Ablauflogik von ``run_smoke`` ohne echtes MT5: der
lesende Durchlauf, der **harte Demo-Abbruch** auf einem Nicht-Demokonto, und die
Schreib-Probe (nur auf Demo mit ``allow_write``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.smoke import DemoRunInputs, _probe_stop, run_smoke

from test_mt5_venue import FakeMt5Terminal, _catalog, _mt5_position

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _edge(passed: bool) -> EdgeVerdict:
    return EdgeVerdict(passed=passed, checks=(), unmet=() if passed else ("trades",))


def _venue(*, is_demo: bool, positions: tuple[object, ...] = ()) -> Mt5Venue:
    return Mt5Venue(
        name="mt5-demo",
        terminal=FakeMt5Terminal(is_demo=is_demo, positions=positions),  # type: ignore[arg-type]
        catalog=_catalog(),
        # Seit A3 faehrt die Schreib-Probe durch dieselben fuenf Sperren wie jede andere
        # Eroeffnung -- auch auf Demo. Ohne Manager wuerde sie fail-closed abgelehnt.
        risk_manager=RiskManager(),
        clock=lambda: TS,
    )


def _names(report: object) -> list[str]:
    return [step.name for step in report.steps]  # type: ignore[attr-defined]


def test_smoke_readonly_all_steps_ok_on_demo() -> None:
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS)
    assert report.ok is True
    names = _names(report)
    for expected in ("connect", "demo_guard", "get_quote", "reconcile", "disconnect"):
        assert expected in names
    write = next(s for s in report.steps if s.name == "write_probe")
    assert "uebersprungen" in write.detail
    assert "write_open" not in names


def test_smoke_demo_registration_produces_readiness() -> None:
    # Naht §8.5->§7: bestandener Edge -> register_for_demo -> >= 180 Tage -> reif.
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(True),
        elapsed_days=200, live_verdict=_edge(True),
    )
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS, demo=demo)
    assert "demo_registration" in _names(report)
    assert report.demo_readiness is not None
    assert report.demo_readiness.ready_for_live_question is True


def test_smoke_demo_registration_fail_closed_without_edge() -> None:
    # Ohne bestandenen Edge verweigert register_for_demo den Demo-Betrieb (fail-closed).
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(False),
        elapsed_days=200, live_verdict=_edge(True),
    )
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS, demo=demo)
    reg = next(s for s in report.steps if s.name == "demo_registration")
    assert reg.ok is False
    assert report.demo_readiness is None  # keine Reife ohne Registrierung
    assert report.ok is False


def test_smoke_demo_guard_hard_stops_on_live() -> None:
    report = run_smoke(_venue(is_demo=False), symbol="EURUSD", now=TS)
    assert report.ok is False
    guard = next(s for s in report.steps if s.name == "demo_guard")
    assert guard.ok is False
    # Nach dem Abbruch keine Marktdaten- oder Schreibschritte mehr.
    names = _names(report)
    assert "reconcile" not in names
    assert "write_open" not in names
    assert "disconnect" in names  # sauber getrennt


def test_smoke_write_probe_runs_on_demo_with_allow_write() -> None:
    # Das Terminal meldet die (winzige) offene Long-Position autoritativ, sodass die
    # Reduce-Only-Schliessung der Write-Probe als echter Abbau erkannt wird.
    venue = _venue(
        is_demo=True,
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.01")),),
    )
    report = run_smoke(venue, symbol="EURUSD", allow_write=True, now=TS)
    assert report.ok is True
    names = _names(report)
    assert "write_open" in names
    assert "write_close" in names


def test_smoke_write_probe_not_reached_on_live_even_with_allow_write() -> None:
    report = run_smoke(_venue(is_demo=False), symbol="EURUSD", allow_write=True, now=TS)
    assert report.ok is False
    assert "write_open" not in _names(report)


def test_probe_stop_snaps_to_tick_grid() -> None:
    venue = _venue(is_demo=True)
    venue.connect()
    instrument = venue.get_instrument("EURUSD")
    quote = venue.get_quote("EURUSD")
    stop = _probe_stop(instrument, quote)
    assert stop > 0
    assert stop < quote.bid  # unter dem Einstieg (Kauf)
    # auf dem Tick-Raster: stop / tick_size ist ganzzahlig, sonst lehnt MT5 ab
    ratio = stop / instrument.tick_size
    assert ratio == ratio.to_integral_value()

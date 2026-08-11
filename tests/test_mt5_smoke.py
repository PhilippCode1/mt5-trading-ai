"""Test der Smoke-Orchestrierung gegen ein Fake-Terminal.

Prueft die Sicherheits- und Ablauflogik von ``run_smoke`` ohne echtes MT5: der
lesende Durchlauf, der **harte Demo-Abbruch** auf einem Nicht-Demokonto, und die
Schreib-Probe (nur auf Demo mit ``allow_write``).
"""

from __future__ import annotations

from datetime import UTC, datetime

from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.smoke import _probe_stop, run_smoke

from test_mt5_venue import FakeMt5Terminal, _catalog

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


def _venue(*, is_demo: bool) -> Mt5Venue:
    return Mt5Venue(
        name="mt5-demo",
        terminal=FakeMt5Terminal(is_demo=is_demo),
        catalog=_catalog(),
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
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", allow_write=True, now=TS)
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

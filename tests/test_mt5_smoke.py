"""Test der Smoke-Orchestrierung gegen ein Fake-Terminal.

Prueft die Sicherheits- und Ablauflogik von ``run_smoke`` ohne echtes MT5: der
lesende Durchlauf, der **harte Demo-Abbruch** auf einem Nicht-Demokonto, und die
Schreib-Probe (nur auf Demo mit ``allow_write``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.demo_run import (
    DemoAccount,
    DemoRegistration,
    register_for_demo,
)
from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.smoke import DemoRunInputs, _probe_stop, run_smoke

from test_mt5_venue import FakeMt5Terminal, _catalog, _mt5_position

TS = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
#: Broker-/Serverkennung des Fake-Terminals. Sie steht in keinem Kontoschnappschuss
#: (``AccountState`` fuehrt kein solches Feld) und kommt darum vom Aufrufer.
BROKER = "Demo-Broker"


def _edge(passed: bool) -> EdgeVerdict:
    return EdgeVerdict(passed=passed, checks=(), unmet=() if passed else ("trades",))


class _TerminalMitFolgeposition(FakeMt5Terminal):
    """Ein Broker, der die Position erst NACH der Fuellung meldet.

    So verhaelt sich ein echter, und nur so ist die Schreib-Probe abbildbar: sie
    eroeffnet 0,01 Lot und schliesst dieselbe Menge gleich wieder ueber
    ``reduce_only``. Ein Bestand, der schon VOR der Eroeffnung steht, waere eine Lage,
    in der die Eroeffnung selbst eine zweite gleichgerichtete Position waere -- und
    darauf antwortet seit dem Doppelorder-Riegel dieser und nicht die Probe.
    """

    def order_send(self, request: object) -> object:
        ergebnis = super().order_send(request)
        if not isinstance(request, dict):
            return ergebnis
        if request.get("reduce_only"):
            self.set_positions(())
        else:
            volumen = Decimal(str(request["volume"]))
            self.set_positions(
                (_mt5_position("EURUSD", is_buy=True, volume=volumen),)
            )
        return ergebnis


def _venue(
    *,
    is_demo: bool,
    positions: tuple[object, ...] = (),
    folgeposition: bool = False,
) -> Mt5Venue:
    bauart = _TerminalMitFolgeposition if folgeposition else FakeMt5Terminal
    return Mt5Venue(
        name="mt5-demo",
        terminal=bauart(is_demo=is_demo, positions=positions),  # type: ignore[arg-type]
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


def _beleg(*, tage: int, konto: str = "123") -> DemoRegistration:
    """Ein Registrierungsbeleg, der ``tage`` vor ``TS`` entstanden ist -- das Datum
    kommt aus der Uhr, nicht aus einem Argument."""
    stand = TS - timedelta(days=tage)
    return register_for_demo(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(True),
        account=DemoAccount(account_id=konto, broker=BROKER, is_demo=True),
        clock=lambda: stand,
    )


def test_smoke_demo_registration_produces_readiness() -> None:
    # Naht §8.5->§7: bestandener Edge -> register_for_demo -> >= 180 Tage -> reif.
    # ``elapsed_days=200`` gibt es nicht mehr; die 200 Tage stehen jetzt im BELEG und
    # werden gegen ``now=TS`` gerechnet.
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(True),
        live_verdict=_edge(True), broker=BROKER, registration=_beleg(tage=200),
    )
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS, demo=demo)
    assert "demo_registration" in _names(report)
    assert report.demo_readiness is not None
    assert report.demo_readiness.ready_for_live_question is True


def test_smoke_ohne_bestehenden_beleg_ist_null_tage_alt() -> None:
    """Wer ohne Beleg fragt, registriert gerade erst -- und null Tage sind nicht 180.

    Vorher war genau das der Ort, an dem ``elapsed_days=200`` die Frist in einer Zeile
    ueberspringen konnte. Der Schritt ist damit rot, und das ist die Antwort des Tors,
    kein Fehler der Harness.
    """
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(True),
        live_verdict=_edge(True), broker=BROKER,
    )
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS, demo=demo)
    reg = next(s for s in report.steps if s.name == "demo_registration")
    assert reg.ok is True
    assert report.demo_readiness is not None
    assert report.demo_readiness.ready_for_live_question is False
    assert "demo_zu_kurz_0_von_180_tagen" in report.demo_readiness.reasons


def test_smoke_fremdes_konto_reift_nicht() -> None:
    """Der Beleg eines anderen Demokontos zaehlt hier nicht: das beobachtete Konto
    liest die Harness frisch vom Terminal (``get_account()`` = "123")."""
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(True),
        live_verdict=_edge(True), broker=BROKER,
        registration=_beleg(tage=200, konto="9999"),
    )
    report = run_smoke(_venue(is_demo=True), symbol="EURUSD", now=TS, demo=demo)
    assert report.demo_readiness is not None
    assert report.demo_readiness.ready_for_live_question is False
    assert (
        "kontonummer_weicht_von_registrierung_ab" in report.demo_readiness.reasons
    )


def test_smoke_demo_registration_fail_closed_without_edge() -> None:
    # Ohne bestandenen Edge verweigert register_for_demo den Demo-Betrieb (fail-closed).
    demo = DemoRunInputs(
        strategy_id="eurusd", version="v1", edge_verdict=_edge(False),
        live_verdict=_edge(True), broker=BROKER,
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
    # Das Terminal meldet die (winzige) offene Long-Position autoritativ, sobald die
    # Probe sie eroeffnet hat -- so, wie es ein echter Broker tut. Dadurch erkennt die
    # Reduce-Only-Schliessung sie als echten Abbau.
    venue = _venue(is_demo=True, folgeposition=True)
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

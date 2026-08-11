"""Demo-Smoke-Test der MT5-Bindung — die Orchestrierung, terminalunabhaengig.

``run_smoke`` faehrt eine feste Folge gegen einen :class:`Mt5Venue`: verbinden, Konto
lesen (und auf **Demo** bestehen), Marktdaten, Positionen, Buch adoptieren, reconcilen.
Die optionale Schreib-Probe (winzige Order, sofort per Reduce-Only geschlossen) laeuft
nur bei ``allow_write=True`` **und** auf einem Demokonto — der Demo-Check hier ist ein
**harter Abbruch**: auf einem Nicht-Demokonto wird nichts weiter getan.

Die Folge ist gegen ein Fake-Terminal testbar; der echte Lauf (``tools/mt5_smoke.py``)
steckt ein ``RealMt5Terminal`` hinein. So ist die Sicherheits- und Ablauflogik geprueft,
ohne dass ein echtes Terminal noetig ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from mt5_trading_ai.venue.mt5 import Mt5Venue
from mt5_trading_ai.venue.protocol import (
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
    Quote,
    Timeframe,
    VenueError,
)


@dataclass
class SmokeStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeReport:
    steps: list[SmokeStep] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.steps) and all(step.ok for step in self.steps)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.steps.append(SmokeStep(name, ok, detail))


def run_smoke(
    venue: Mt5Venue,
    *,
    symbol: str,
    allow_write: bool = False,
    now: datetime | None = None,
) -> SmokeReport:
    """Fahre die Smoke-Folge. Standardmaessig nur lesend; ``allow_write`` schaltet die
    Schreib-Probe frei (die dennoch ein Demokonto verlangt).
    """
    report = SmokeReport()
    at = now if now is not None else datetime.now(UTC)

    try:
        venue.connect()
        report.add("connect", True, venue.name)
    except VenueError as exc:
        report.add("connect", False, str(exc))
        return report

    try:
        report.add("healthy", venue.is_healthy())
        account = venue.get_account()
        report.add("account", True, f"{account.account_id} equity={account.equity}")
        if not account.is_demo:
            report.add("demo_guard", False, "KEIN Demokonto — Smoke abgebrochen")
            return report
        report.add("demo_guard", True, "Demokonto bestaetigt")

        instruments = venue.list_instruments()
        report.add(
            "list_instruments", len(instruments) > 0, f"{len(instruments)} Instrumente"
        )
        instrument = venue.get_instrument(symbol)
        report.add("get_instrument", True, f"{symbol} {instrument.asset_class.value}")
        quote = venue.get_quote(symbol)
        report.add("get_quote", quote.ask > 0, f"bid={quote.bid} ask={quote.ask}")
        bars = venue.get_bars(
            symbol, Timeframe.H1, start=at - timedelta(days=3), end=at
        )
        report.add("get_bars", True, f"{len(bars)} Bars")
        report.add("is_trading_open", True, str(venue.is_trading_open(symbol, at=at)))

        venue.get_positions()
        adopted = venue.adopt_book()
        report.add("adopt_book", True, f"{len(adopted)} Symbole im Buch")
        recon = venue.reconcile()
        report.add("reconcile", not recon.halt, f"matched={recon.matched}")

        if allow_write:
            _write_probe(venue, symbol, instrument, quote, report)
        else:
            report.add("write_probe", True, "uebersprungen (nur lesend)")
    except VenueError as exc:
        report.add("error", False, str(exc))
    finally:
        try:
            venue.disconnect()
            report.add("disconnect", True)
        except VenueError as exc:
            report.add("disconnect", False, str(exc))
    return report


def _probe_stop(instrument: Instrument, quote: Quote) -> Decimal:
    """Ein gueltiger Stop unter dem Einstieg (Kauf): min. ``stop_level`` entfernt und
    auf das Tick-Raster gerundet (sonst lehnt MT5 mit INVALID_STOPS ab)."""
    min_dist = instrument.tick_size * Decimal(max(instrument.stop_level_points, 1))
    raw = quote.bid - max(min_dist, quote.bid * Decimal("0.01"))
    tick = instrument.tick_size
    return (raw / tick).to_integral_value(rounding=ROUND_DOWN) * tick


def _write_probe(
    venue: Mt5Venue,
    symbol: str,
    instrument: Instrument,
    quote: Quote,
    report: SmokeReport,
) -> None:
    """Eine winzige Kauf-Order, sofort per Reduce-Only geschlossen. Nur auf Demo (der
    Aufrufer hat das Demokonto bereits als harte Sperre geprueft)."""
    volume = instrument.volume_min
    stop = _probe_stop(instrument, quote)
    try:
        opened = venue.submit_order(
            OrderRequest(
                client_order_id="smoke-open",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                volume=volume,
                stop_loss=stop,
                comment="smoke",
            )
        )
        report.add("write_open", opened.accepted, f"id={opened.venue_order_id}")
        closed = venue.submit_order(
            OrderRequest(
                client_order_id="smoke-close",
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                volume=volume,
                stop_loss=Decimal("0"),
                reduce_only=True,
                comment="smoke-close",
            )
        )
        report.add("write_close", closed.accepted, f"id={closed.venue_order_id}")
    except VenueError as exc:
        report.add("write_probe", False, str(exc))

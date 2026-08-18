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

from mt5_trading_ai.backtest.edge import EdgeVerdict
from mt5_trading_ai.venue.demo_run import (
    DemoAccount,
    DemoGateError,
    DemoReadiness,
    DemoRegistration,
    evaluate_demo_progress,
    register_for_demo,
)
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


@dataclass(frozen=True)
class DemoRunInputs:
    """Belege, mit denen die Demo-Harness den Demo-Betrieb registriert und den
    Fortschritt prueft -- die Naht §8.5->§7 (``venue/demo_run.py``).

    ``edge_verdict`` ist das Ergebnis des Sechs-Bedingungen-Tors aus ``run_backtest ->
    evaluate_edge`` **zum Registrierungszeitpunkt**; ``live_verdict`` das im Demo weiter
    gemessene Ergebnis.

    ``elapsed_days`` gibt es nicht mehr. Es war eine frei behauptete Laufzeit: ein
    ``elapsed_days=400`` reifte jedes Konto in einer Zeile (siehe ``demo_run.py``).
    Die Laufzeit ist jetzt die Differenz zwischen der Uhr des Laufs
    (``run_smoke(now=)``) und dem Registrierungsdatum.

    ``registration`` ist der **bestehende** Beleg, wenn der Demo-Betrieb schon laeuft.
    Fehlt er, registriert die Harness jetzt -- und ein Beleg von heute ist null Tage
    alt, also nicht reif. Das ist die richtige Antwort, keine Panne: eine Frist beginnt
    mit der Registrierung und nicht mit der Frage danach.

    ``broker`` ist die Broker-/Serverkennung des Terminals, das die Harness gerade
    liest. Sie steht **nicht** im Kontoschnappschuss (``AccountState`` fuehrt kein
    solches Feld), muss also vom Aufrufer aus derselben Terminal-Konfiguration kommen,
    aus der auch die Registrierung stammt. Der Vergleich faengt damit
    Fehlkonfiguration, nicht Taeuschung -- so steht es auch an ``DemoAccount``.
    """

    strategy_id: str
    version: str
    edge_verdict: EdgeVerdict
    live_verdict: EdgeVerdict
    broker: str
    registration: DemoRegistration | None = None


@dataclass
class SmokeStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeReport:
    steps: list[SmokeStep] = field(default_factory=list)
    #: Ergebnis des Demo-Reife-Tors, falls ``run_smoke`` mit ``demo`` gefahren wurde.
    demo_readiness: DemoReadiness | None = None

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
    demo: DemoRunInputs | None = None,
) -> SmokeReport:
    """Fahre die Smoke-Folge. Standardmaessig nur lesend; ``allow_write`` schaltet die
    Schreib-Probe frei (die dennoch ein Demokonto verlangt).

    ``demo`` fuettert die Naht §8.5->§7: die Harness registriert die Strategie fuer den
    Demo-Betrieb (``register_for_demo`` -- fail-closed ohne bestandenen Edge, auf dem
    Konto, das sie gerade liest) und prueft den Fortschritt
    (``evaluate_demo_progress``); das Ergebnis liegt in ``report.demo_readiness``.

    Die Uhr des Demo-Tors ist ``now`` (Default: Systemuhr) -- dieselbe, die den ganzen
    Lauf datiert. Damit haengt die Frist an einer injizierbaren Groesse und nicht an
    ``datetime.now()`` im Modul.

    Der Schritt ``demo_progress`` ist **rot, solange die Frist nicht voll ist**. Das ist
    die Antwort des Tors, kein Fehler der Harness: wer ohne bestehenden Beleg fragt,
    registriert gerade erst und hat null von 180 Tagen. Wer nur die Verdrahtung des
    Smoke pruefen will, laesst ``demo`` weg.

    Was ``report.demo_readiness`` **nicht** ist: die Eingabe des Live-Freigabe-Tors.
    ``Mt5Venue`` nimmt kein fertiges Urteil mehr entgegen, sondern die Registrierung,
    und rechnet selbst (``venue/mt5.py``, ``_require_demo_maturity``). Der Bericht hier
    ist der Nachweis des Betreibers, nicht die Freigabe.
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

        if demo is not None:
            # Naht §8.5->§7: Demo-Registrierung (fail-closed ohne Edge) + Fortschritt.
            # Das beobachtete Konto ist das gerade gelesene -- und HIER ist es
            # wirklich ein Demokonto (der harte Abbruch oben hat das erzwungen).
            beobachtet = DemoAccount(
                account_id=account.account_id,
                broker=demo.broker,
                is_demo=account.is_demo,
            )
            registration: DemoRegistration | None = demo.registration
            if registration is None:
                try:
                    registration = register_for_demo(
                        strategy_id=demo.strategy_id, version=demo.version,
                        edge_verdict=demo.edge_verdict, account=beobachtet,
                        clock=lambda: at,
                    )
                except DemoGateError as exc:
                    report.add("demo_registration", False, str(exc))
            if registration is not None:
                report.add(
                    "demo_registration", True,
                    f"{registration.strategy_id} seit {registration.registered_on}",
                )
                readiness = evaluate_demo_progress(
                    registration=registration, observed_account=beobachtet,
                    live_verdict=demo.live_verdict, clock=lambda: at,
                )
                report.demo_readiness = readiness
                report.add(
                    "demo_progress", readiness.ready_for_live_question,
                    ", ".join(readiness.reasons) or "reif fuer Live-Frage",
                )

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

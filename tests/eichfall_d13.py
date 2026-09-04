"""Eichfall D13 (MP01 Tabelle; Bewertung 2026-09-02 Z. 112): Gap-Sperre vor der
Wochenendluecke.

ROT gegen 306bbaa (belege/06-d13-rot.txt): eine eroeffnende Order um Freitag 19:30
UTC laeuft durch alle Tore bis zum Terminal; ab 21:00 UTC nimmt der FX-Platz keine
Schliessung mehr an (``_fx_sessions``), die Position steht ohne Aufsicht ueber die
Luecke. GRUEN gegen HEAD (belege/06-d13-gruen.txt): ``weekend_gap_lock``
(``execution/handelspause.py``, Tor ``Mt5Venue._enforce_gap_sperre``). Freitag 18:59
bleibt erlaubt (Vorlauf 120 min), Mittwoch 19:30 ebenso (Nachtluecke 3 h < 24 h).

Nachstellung, WO nach Freitag 21:00 UTC eine Schliessung scheitert: in beiden
Fassungen erreicht eine Schliessung um 21:30 mit druckendem Kursstrom das Terminal
(``test_schliessung_freitag_2130_erreicht_das_terminal``), und ``_schliesse`` in
``tools/live_betrieb.py`` fragt die Sitzungstabelle nicht
(``test_die_schliessung_des_betriebs_fragt_die_tabelle_nicht``). Die Schliessung
scheitert also nicht an einer Tabelle im Haus, sondern am Platz, der keinen Kurs
mehr stellt -- ein Zustand, den kein Code oeffnen kann. Die Behebung ist darum die
Sperre VOR der Luecke, nicht ein Umbau der Schliessung.

Die Datei importiert nur Namen, die es in BEIDEN Fassungen gibt (``position_ticket``
wird nur gesetzt, wenn ``OrderRequest`` das Feld kennt -- D2).
"""

from __future__ import annotations

import dataclasses
import inspect
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
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
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
    Timeframe,
    TradingSession,
)

#: 2026-09-04 ist ein Freitag, 2026-09-02 ein Mittwoch (weekday 4 bzw. 2).
FREITAG_1859 = datetime(2026, 9, 4, 18, 59, tzinfo=UTC)
FREITAG_1930 = datetime(2026, 9, 4, 19, 30, tzinfo=UTC)
FREITAG_2130 = datetime(2026, 9, 4, 21, 30, tzinfo=UTC)
MITTWOCH_1930 = datetime(2026, 9, 2, 19, 30, tzinfo=UTC)
#: Die FX-Zeilen des Katalogs: Mo-Fr 00:00-21:00 UTC.
FX_FENSTER = tuple(
    TradingSession(weekday=tag, open_utc="00:00", close_utc="21:00") for tag in range(5)
)


def _fees() -> FeeSchedule:
    return FeeSchedule(
        commission_per_lot_round_turn=Decimal("7"),
        typical_spread_points=Decimal("6"),
        swap_long_per_lot_per_night=Decimal("-2"),
        swap_short_per_lot_per_night=Decimal("-1"),
        triple_swap_weekday=2,
        currency="USD",
    )


def _symbol() -> Mt5Symbol:
    return Mt5Symbol(
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


class _Terminal:
    """Ein Terminal, das zu JEDER Zeit Preise druckt und jede Order annimmt.

    So bleibt allein die Frage uebrig, ob das Haus die Order bis hierher laesst.
    """

    def __init__(
        self, jetzt: datetime, positions: tuple[Mt5Position, ...] = ()
    ) -> None:
        self.jetzt = jetzt
        self._positions = positions
        self._verbunden = False
        self.gesendet: list[dict[str, Any]] = []

    def initialize(self) -> bool:
        self._verbunden = True
        return True

    def shutdown(self) -> None:
        self._verbunden = False

    def is_connected(self) -> bool:
        return self._verbunden

    def symbols(self) -> tuple[Mt5Symbol, ...]:
        return (_symbol(),)

    def symbol(self, name: str) -> Mt5Symbol | None:
        return _symbol() if name == "EURUSD" else None

    def tick(self, name: str) -> Mt5Tick | None:
        return Mt5Tick(ts=self.jetzt, bid=Decimal("1.09990"), ask=Decimal("1.10000"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        return ()

    def order_send(self, request: Any) -> Mt5SendResult:
        self.gesendet.append(dict(request))
        return Mt5SendResult(
            accepted=True,
            venue_order_id=f"V-{len(self.gesendet)}",
            filled_volume=Decimal(str(request["volume"])),
            average_price=Decimal("1.10000"),
            ts=self.jetzt,
            reason="done",
        )

    def cancel(self, venue_order_id: str) -> bool:
        return True

    def modify_stops(
        self,
        venue_position_id: str,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
    ) -> bool:
        return True

    def positions(self) -> tuple[Mt5Position, ...]:
        return self._positions

    def account(self) -> Mt5Account:
        return Mt5Account(
            account_id="123",
            currency="USD",
            balance=Decimal("10000"),
            equity=Decimal("10000"),
            margin_used=Decimal("0"),
            margin_free=Decimal("10000"),
            is_demo=True,
            ts=self.jetzt,
        )


def _risk_manager() -> RiskManager:
    """Ein Risikokern -- mit Zustand, wo er Pflicht ist. Gegen 306bbaa gibt es
    ``FluechtigerZustand`` nicht; der Fall soll dort an seiner Zusicherung fallen,
    nicht am Import."""
    try:
        from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
    except ImportError:
        return RiskManager()
    return RiskManager(zustand=FluechtigerZustand())


def _ablagen() -> dict[str, Any]:
    """Fluechtige Ablagen -- aber nur, wo es sie gibt. Gegen 306bbaa (roter Lauf)
    kennt das Paket weder ``FluechtigeSchwebeAkte`` noch ``FluechtigesPositionsbuch``;
    ein Sammel- oder Importfehler waere kein Befund, sondern ein Werkzeugfehler.
    """
    felder = inspect.signature(Mt5Venue.__init__).parameters
    ablagen: dict[str, Any] = {}
    try:
        from mt5_trading_ai.execution.schwebende_auftraege import (
            FluechtigeSchwebeAkte,
        )

        if "schwebeakte" in felder:
            ablagen["schwebeakte"] = FluechtigeSchwebeAkte()
    except ImportError:
        pass
    try:
        from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch

        if "positionsbuch" in felder:
            ablagen["positionsbuch"] = FluechtigesPositionsbuch()
    except ImportError:
        pass
    return ablagen


def _venue(
    jetzt: datetime, positions: tuple[Mt5Position, ...] = ()
) -> tuple[Mt5Venue, _Terminal]:
    terminal = _Terminal(jetzt, positions)
    venue = Mt5Venue(
        name="mt5-d13",
        terminal=terminal,  # type: ignore[arg-type]
        catalog={"EURUSD": CatalogEntry(AssetClass.FX_MAJOR, _fees(), FX_FENSTER)},
        risk_manager=_risk_manager(),
        clock=lambda: jetzt,
        **_ablagen(),
    )
    venue.connect()
    return venue, terminal


def _eroeffnung() -> OrderRequest:
    return OrderRequest(
        client_order_id="c-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("1.09000"),
        meta={"requested_leverage": 5},
    )


def _position() -> Mt5Position:
    return Mt5Position(
        ticket="P1",
        symbol="EURUSD",
        is_buy=True,
        volume=Decimal("0.01"),
        entry_price=Decimal("1.10000"),
        stop_loss=Decimal("1.09000"),
        take_profit=None,
        opened_at=FREITAG_1930,
        unrealised_pnl=Decimal("0"),
        swap=Decimal("0"),
    )


def _schliessung() -> OrderRequest:
    felder = {f.name for f in dataclasses.fields(OrderRequest)}
    extra: dict[str, Any] = (
        {"position_ticket": "P1"} if "position_ticket" in felder else {}
    )
    return OrderRequest(
        client_order_id="close-1",
        symbol="EURUSD",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("0"),
        reduce_only=True,
        **extra,
    )


def test_freitag_1930_wird_vor_der_luecke_abgewiesen() -> None:
    """ROT gegen 306bbaa: die Order erreicht das Terminal."""
    venue, terminal = _venue(FREITAG_1930)
    with pytest.raises(OrderRejectedError) as abgelehnt:
        venue.submit_order(_eroeffnung())
    assert abgelehnt.value.reason == "weekend_gap_lock"
    assert terminal.gesendet == []


def test_freitag_1859_ist_noch_erlaubt() -> None:
    venue, terminal = _venue(FREITAG_1859)
    assert venue.submit_order(_eroeffnung()).accepted is True
    assert len(terminal.gesendet) == 1


def test_mittwoch_1930_ist_erlaubt_die_nachtluecke_ist_keine_wochenendluecke() -> None:
    venue, terminal = _venue(MITTWOCH_1930)
    assert venue.submit_order(_eroeffnung()).accepted is True
    assert len(terminal.gesendet) == 1


def test_schliessung_freitag_2130_erreicht_das_terminal() -> None:
    """Die Tabelle deckt 21:30 nicht (``is_trading_open`` ist zu) -- die Schliessung
    haengt trotzdem NICHT an ihr, sondern nur am Terminal. In beiden Fassungen."""
    venue, terminal = _venue(FREITAG_2130, positions=(_position(),))
    assert venue.is_trading_open("EURUSD", at=FREITAG_2130) is False
    ergebnis = venue.submit_order(_schliessung())
    assert ergebnis.accepted is True
    assert terminal.gesendet[-1]["reduce_only"] is True
    assert terminal.gesendet[-1]["side"] == "sell"


class _SchliessVenue:
    """Zeichnet auf, was ``live_betrieb._schliesse`` vom Handelsplatz will."""

    def __init__(self) -> None:
        self.gesendet: list[Any] = []

    def is_trading_open(self, symbol: str, *, at: datetime) -> bool:
        raise AssertionError("Eine Schliessung darf die Sitzungstabelle nicht fragen")

    def submit_order(self, anfrage: Any) -> Any:
        self.gesendet.append(anfrage)
        return dataclasses.make_dataclass(
            "Ergebnis",
            [
                ("venue_order_id", str),
                ("average_price", Decimal),
                ("filled_volume", Decimal),
            ],
        )("V-1", Decimal("1.10000"), Decimal("0.01"))


def test_die_schliessung_des_betriebs_fragt_die_tabelle_nicht(tmp_path: Path) -> None:
    """``tools/live_betrieb._schliesse`` um Freitag 21:30: die Order geht an den
    Handelsplatz, ``is_trading_open`` wird nicht gerufen. In beiden Fassungen."""
    from tools.live_betrieb import Journal, Lage, _schliesse

    venue = _SchliessVenue()
    lage = Lage(
        symbol="EURUSD",
        ist_kauf=True,
        volumen=Decimal("0.01"),
        seit=FREITAG_1930,
        position_id="P1",
        einstiegspreis=Decimal("1.10000"),
        unrealisiert=Decimal("-1.5"),
        swap=Decimal("0"),
    )
    journal = Journal(tmp_path / "journal.jsonl", lauf="eichfall", version="test")
    geschlossen = _schliesse(
        venue,  # type: ignore[arg-type]
        _risk_manager(),
        lage,
        FREITAG_2130,
        "haltedauer_2.0h",
        journal,
        waehrung="USD",
    )
    assert geschlossen is True
    assert len(venue.gesendet) == 1
    assert venue.gesendet[0].reduce_only is True
    assert '"geschlossen"' in (tmp_path / "journal.jsonl").read_text(encoding="utf-8")


def test_der_ausgelieferte_katalog_traegt_die_zahlen_der_sperre() -> None:
    """HEAD-Fall: der Block ``_gap_sperre`` steht in der Datei und entspricht dem
    Standard (120 min Vorlauf, 24 h Mindestpause) -- eine lockerere Datei laedt nicht."""
    from mt5_trading_ai.venue.catalog import (
        GAP_SPERRE_STANDARD,
        load_instrument_catalog,
    )

    katalog = load_instrument_catalog()
    assert katalog["EURUSD"].gap_sperre == GAP_SPERRE_STANDARD
    assert GAP_SPERRE_STANDARD.vorlauf == timedelta(minutes=120)
    assert GAP_SPERRE_STANDARD.mindestpause == timedelta(hours=24)

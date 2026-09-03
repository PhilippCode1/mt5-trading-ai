"""Eichfaelle D2 (Bewertung 3.3): eine Schliessung ohne Positionsticket ist nicht darstellbar.

ROT gegen 306bbaa (Ausgabe in belege/06-d2-rot.txt): dort baute ``OrderRequest`` einen
Reduce-only-Auftrag ohne Ticket, und ``RealMt5Terminal.order_send`` schickte die
Marktorder auch dann, wenn die Gegenposition zwischen Pruefung und Senden verschwunden
war -- ohne ``position``, mit ``sl=0``, an allen Toren vorbei (Nachstellung V2).
GRUEN gegen HEAD (belege/06-d2-gruen.txt).

Die Klasse, nicht der Fall: das Ticket steht im Typ (``position_ticket``), der
Konstruktor weist einen Schliessauftrag ohne Ticket ab, das Terminal prueft das
Ticket unmittelbar vor dem Senden und sendet bei Abweichung nichts.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.venue.mt5 import RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRequest,
    OrderSide,
    OrderType,
    VenueUnavailableError,
)

DONE = 10009


@dataclass
class _Ergebnis:
    retcode: int
    order: int = 0
    deal: int = 0
    volume: float = 0.0
    price: float = 0.0
    comment: str = "Done"


@dataclass
class _Mt5:
    """So viel MetaTrader5, wie der Schliesspfad anfasst; ``positionen`` frei setzbar."""

    positionen: Any = ()
    gesendet: list[dict[str, Any]] = field(default_factory=list)
    TRADE_RETCODE_DONE = DONE
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_REMOVE = 7
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    ACCOUNT_TRADE_MODE_DEMO = 0
    POSITION_TYPE_BUY = 0

    def account_info(self) -> Any:
        return SimpleNamespace(
            login=4242,
            currency="USD",
            balance=1e4,
            equity=1e4,
            margin=0.0,
            margin_free=1e4,
            trade_mode=0,
            leverage=30,
        )

    def symbol_info(self, name: str) -> Any:
        return SimpleNamespace(filling_mode=1, point=0.00001)

    def symbol_info_tick(self, name: str) -> Any:
        return SimpleNamespace(bid=1.0999, ask=1.1, time=1786000000)

    def order_send(self, req: Any) -> Any:
        self.gesendet.append(dict(req))
        return _Ergebnis(
            retcode=DONE, order=555, deal=556, volume=req.get("volume", 0.0)
        )

    def orders_get(self, **kw: Any) -> Any:
        return ()

    def positions_get(self, **kw: Any) -> Any:
        return self.positionen


def _terminal(mt5: _Mt5) -> RealMt5Terminal:
    t = RealMt5Terminal(allow_write=True, require_demo=True)
    t._mt5 = mt5  # Sitzung ohne Terminal
    return t


def _schliessung(ticket: str | None) -> dict[str, Any]:
    return {
        "client_order_id": "close-EURUSD-abc",
        "symbol": "EURUSD",
        "side": "sell",
        "order_type": "market",
        "volume": Decimal("0.10"),
        "stop_loss": Decimal("0"),
        "take_profit": None,
        "limit_price": None,
        "reduce_only": True,
        "position_ticket": ticket,
        "comment": "x",
    }


def test_schliessauftrag_ohne_ticket_ist_nicht_konstruierbar() -> None:
    """ROT gegen 306bbaa: dort entsteht der Auftrag anstandslos."""
    with pytest.raises(ValueError, match="position_ticket"):
        OrderRequest(
            client_order_id="close-1",
            symbol="EURUSD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            volume=Decimal("0.10"),
            stop_loss=Decimal("0"),
            reduce_only=True,
        )


def test_verschwundene_position_wird_nicht_gesendet() -> None:
    """ROT gegen 306bbaa: dort geht die Marktorder ohne ``position`` und mit sl=0 raus."""
    mt5 = _Mt5(positionen=())  # Stop hat gefeuert: nichts mehr offen
    ergebnis = _terminal(mt5).order_send(_schliessung("777"))
    assert mt5.gesendet == [], (
        "es wurde ohne Gegenposition gesendet -- neue Gegenposition"
    )
    assert ergebnis.accepted is False
    assert ergebnis.reason == "position_vanished"


def test_fremdes_ticket_wird_nicht_gesendet() -> None:
    """Das Ticket zeigt auf eine Position anderer Richtung: keine Schliessung."""
    mt5 = _Mt5(positionen=(SimpleNamespace(ticket=777, type=1, symbol="EURUSD"),))
    ergebnis = _terminal(mt5).order_send(_schliessung("777"))
    assert mt5.gesendet == []
    assert ergebnis.reason == "position_vanished"


def test_schliessung_ohne_ticket_wird_vom_terminal_abgewiesen() -> None:
    """Auch am Terminal selbst: kein Ticket, kein Senden (zweite Sperre hinter dem Typ)."""
    mt5 = _Mt5(positionen=(SimpleNamespace(ticket=777, type=0, symbol="EURUSD"),))
    with pytest.raises(VenueUnavailableError):
        _terminal(mt5).order_send(_schliessung(None))
    assert mt5.gesendet == []


def test_gruen_schliessung_mit_ticket_traegt_position() -> None:
    """GRUEN: die Normalschliessung sendet genau dieses Ticket als ``position``."""
    mt5 = _Mt5(positionen=(SimpleNamespace(ticket=777, type=0, symbol="EURUSD"),))
    ergebnis = _terminal(mt5).order_send(_schliessung("777"))
    assert ergebnis.accepted is True
    assert mt5.gesendet[0]["position"] == 777


def test_modify_stops_sendet_symbol_und_laesst_take_profit_stehen() -> None:
    """V2b: der SLTP-Request nannte kein ``symbol`` und loeschte bei tp=None den TP."""
    mt5 = _Mt5(
        positionen=(
            SimpleNamespace(ticket=777, type=0, symbol="EURUSD", sl=1.09, tp=1.12),
        )
    )
    _terminal(mt5).modify_stops("777", Decimal("1.095"), None)
    req = mt5.gesendet[0]
    assert req["symbol"] == "EURUSD"
    assert req["tp"] == pytest.approx(1.12)
    assert req["sl"] == pytest.approx(1.095)

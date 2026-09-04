"""Der Frische-Latch misst den Broker-Stempel -- nicht die eigene Uhr (E9).

WARUM DIESER TEST
-----------------
``Mt5Venue._enforce_account_freshness`` ist Sperre 1 von 5 am Order-Pfad. Sie soll
verhindern, dass die vier folgenden Sperren mit veralteten Zahlen rechnen. Bis zu
diesem Paket konnte sie das nicht: sie holte ``self._terminal.account()`` und hielt
dessen ``ts`` gegen ``self._clock()``.

``RealMt5Terminal.account()`` setzt ``ts=datetime.now(UTC)`` **in genau diesem
Aufruf** -- MetaTrader liefert ueberhaupt keinen Kontozeitstempel, es gibt nichts
anderes, woraus das Feld entstehen koennte. Das gemessene Alter war damit per
Konstruktion ein paar Mikrosekunden gegen eine Frist von fuenf Sekunden. Die Sperre
konnte nicht ausloesen, und in 21 Journalen der Betriebslaeufe steht kein einziges
``snapshot_stale``.

Das ist die Hausfehlerklasse dieses Repos in Reinform: ein Melder, der per
Konstruktion nie ausloest. Dieselbe Kachel in ``tools/oberflaeche.py`` (geloescht, E-009) und dieselbe
Zeile in ``tools/live_konsole.py`` hatten den Fehler bereits -- und dort wurde er
behoben, indem gegen den juengsten **Kursstempel** gemessen wird. Der kommt von der
anderen Seite der Leitung und ist damit das einzige Lebenszeichen im System, an dem
sich ein haengendes Terminal ueberhaupt zeigen kann.

DIE EICHUNG
-----------
Der Bauplan des Terminals unten ist der Kern: ``account()`` stempelt frisch aus der
eigenen Uhr, ``tick()`` traegt den Stempel des Brokers. Gegen die alte Fassung ist
jeder rote Fall hier gruen gewesen -- die Order lief durch. Ohne diesen Bauplan
misst ein Test das Problem gar nicht, weil das Fake-Terminal der uebrigen Tests
Konto- und Kursstempel auf denselben festen Wert setzt.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Account,
    Mt5Tick,
    Mt5Venue,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import (  # noqa: E402
    TS,
    FakeMt5Terminal,
    _catalog,
    _fresh_risk,
    _krypto_risk,
)


class SelbstgestempeltesTerminal(FakeMt5Terminal):
    """Ein Terminal, das sich verhaelt wie das echte.

    Der Unterschied zum ``FakeMt5Terminal`` ist genau der, um den es geht:

    * ``account()`` stempelt aus der **eigenen** Uhr -- so wie
      ``RealMt5Terminal.account`` es mit ``datetime.now(UTC)`` tut. Dieser Stempel ist
      immer frisch, ganz gleich wie tot die Leitung ist.
    * ``tick()`` traegt den Stempel des **Brokers**. Er ist einstellbar alt, denn
      genau das ist der Zustand, den die Sperre fangen soll: das Terminal antwortet,
      aber die Kurse stehen.

    ``kursalter`` je Symbol, damit sich pruefen laesst, dass die Sperre das Symbol der
    Order misst und nicht irgendeines.
    """

    def __init__(
        self,
        *,
        uhr: Callable[[], datetime],
        kursalter: dict[str, timedelta] | None = None,
        ohne_kurs: frozenset[str] = frozenset(),
        **rest: Any,
    ) -> None:
        super().__init__(**rest)
        self._uhr = uhr
        self._kursalter = dict(kursalter or {})
        self._ohne_kurs = ohne_kurs

    def account(self) -> Mt5Account:
        return replace(super().account(), ts=self._uhr())

    def tick(self, name: str) -> Mt5Tick | None:
        if name in self._ohne_kurs:
            return None
        roh = super().tick(name)
        if roh is None:
            return None
        return replace(roh, ts=self._uhr() - self._kursalter.get(name, timedelta(0)))


def _uhr() -> datetime:
    """Die feste Gegenwart aller Faelle hier.

    Geprueft wird ueber das KURSALTER, nicht ueber eine wandernde Uhr: so steht in
    jedem Fall genau eine Groesse zur Debatte, und das Ergebnis ist reproduzierbar.
    """
    return TS


def _venue_mit(
    *,
    kursalter: dict[str, timedelta] | None = None,
    ohne_kurs: frozenset[str] = frozenset(),
    risk_manager: RiskManager | None = None,
) -> tuple[Mt5Venue, SelbstgestempeltesTerminal]:
    """Ein verbundenes Venue an einem selbstgestempelten Terminal.

    Uhr und Konto-Stempel laufen bewusst zusammen: so ist der Kontozustand nach der
    ALTEN Rechnung immer taufrisch, und jedes Rot hier stammt allein vom Kurs.
    """
    terminal = SelbstgestempeltesTerminal(
        uhr=_uhr, kursalter=kursalter, ohne_kurs=ohne_kurs, is_demo=True
    )
    venue = Mt5Venue(
        name="frische",
        terminal=terminal,
        catalog=_catalog(),
        risk_manager=risk_manager if risk_manager is not None else _fresh_risk(),
        clock=_uhr,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    return venue, terminal


def _order(**over: object) -> OrderRequest:
    base: dict[str, object] = {
        "client_order_id": "frische-1",
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "volume": Decimal("0.01"),
        "stop_loss": Decimal("1.09000"),
        "meta": {"requested_leverage": 5},
    }
    base.update(over)
    return OrderRequest(**base)  # type: ignore[arg-type]


# --- Der Befund selbst -----------------------------------------------------
def test_frischer_kontostempel_rettet_keinen_alten_kurs() -> None:
    """Der rote Eichfall von E9.

    Das Konto meldet sich taufrisch (eigene Uhr), der Broker hat seit fuenf Minuten
    keinen Kurs geliefert. Gegen die alte Fassung ging die Order durch, weil dort nur
    der selbstgesetzte Kontostempel geprueft wurde.
    """
    venue, terminal = _venue_mit(kursalter={"EURUSD": timedelta(minutes=5)})
    # Vorbedingung, die den Test ueberhaupt scharf macht: der Kontostempel ist frisch.
    assert terminal.account().ts == TS
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    assert fehler.value.reason == "snapshot_stale"
    assert terminal.order_send_calls == 0, (
        "Die Order ist trotz stehender Kurse gesendet worden -- die Sperre misst "
        "immer noch gegen die eigene Uhr."
    )


def test_frischer_kurs_laesst_dieselbe_order_durch() -> None:
    """Gegenprobe: ohne sie liesse sich der Test oben durch pauschales Ablehnen bestehen."""
    venue, terminal = _venue_mit(kursalter={"EURUSD": timedelta(seconds=1)})
    assert venue.submit_order(_order()).accepted is True
    assert terminal.order_send_calls == 1


def test_kurs_aus_der_zukunft_ist_ebenso_wenig_bewertbar() -> None:
    """Die zweite Kante. Ein Stempel vor der eigenen Uhr entsteht durch Uhrensprung
    oder durch eine nicht gedrehte Serverzone -- beides macht das Alter unmessbar."""
    venue, terminal = _venue_mit(kursalter={"EURUSD": timedelta(minutes=-5)})
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    assert fehler.value.reason == "snapshot_from_future"
    assert terminal.order_send_calls == 0


def test_ohne_kurs_keine_eroeffnung() -> None:
    """Kein Kurs = kein Stempel = nicht bewertbar. Fail-closed statt durchwinken."""
    venue, terminal = _venue_mit(ohne_kurs=frozenset({"EURUSD"}))
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    assert fehler.value.reason == "no_market_stamp"
    assert terminal.order_send_calls == 0


# --- Die Sperre misst das Symbol der Order, nicht irgendeines ---------------
def test_stehender_fremder_strom_blockt_die_order_nicht() -> None:
    """BTCUSD steht seit einer Stunde -- eine EURUSD-Order geht trotzdem durch.

    Die Gegenrichtung zur Ueberstrenge: eine Sperre, die bei jedem beliebigen alten
    Symbol im Katalog rot wird, waere im Betrieb dauerrot und flogen binnen einer
    Woche raus.
    """
    venue, terminal = _venue_mit(kursalter={"BTCUSD": timedelta(hours=1)})
    assert venue.submit_order(_order()).accepted is True
    assert terminal.order_send_calls == 1


def test_stehender_eigener_strom_blockt_die_order() -> None:
    """Dasselbe Terminal, aber die Order laeuft auf das stehende Symbol."""
    venue, terminal = _venue_mit(
        kursalter={"BTCUSD": timedelta(hours=1)}, risk_manager=_krypto_risk()
    )
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(
            _order(
                client_order_id="btc-1",
                symbol="BTCUSD",
                stop_loss=Decimal("56400"),
            )
        )
    assert fehler.value.reason == "snapshot_stale"
    assert terminal.order_send_calls == 0


def test_gegenprobe_frischer_krypto_kurs_geht_durch() -> None:
    """Ohne diese Zeile bewiese der Test darueber nur, dass BTCUSD ueberhaupt faellt."""
    venue, terminal = _venue_mit(risk_manager=_krypto_risk())
    ergebnis = venue.submit_order(
        _order(client_order_id="btc-1", symbol="BTCUSD", stop_loss=Decimal("56400"))
    )
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


# --- Reduce-Only bleibt frei ----------------------------------------------
def test_reduce_only_haengt_nicht_am_kursstempel() -> None:
    """Risikoabbau darf nie an einer Sperre haengen -- auch nicht an dieser.

    Ein stehender Kursstrom ist genau der Moment, in dem man eine Position loswerden
    will. Wuerde der Frische-Latch hier greifen, waere er ein Risiko und keine Sperre.
    """
    from test_mt5_venue import _mt5_position

    terminal = SelbstgestempeltesTerminal(
        uhr=_uhr,
        kursalter={"EURUSD": timedelta(hours=2)},
        is_demo=True,
        positions=(_mt5_position("EURUSD", is_buy=True, volume=Decimal("0.10")),),
    )
    venue = Mt5Venue(
        name="frische-reduce",
        terminal=terminal,
        catalog=_catalog(),
        risk_manager=_fresh_risk(),
        clock=_uhr,
        positionsbuch=FluechtigesPositionsbuch(),
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    venue.connect()
    ergebnis = venue.submit_order(
        _order(
            client_order_id="reduce-1",
            side=OrderSide.SELL,
            reduce_only=True,
            position_ticket="t1",
            stop_loss=Decimal("0"),
        )
    )
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1


# --- Die Frist selbst ------------------------------------------------------
def test_die_frist_ist_die_konfigurierte_und_nicht_die_uhr() -> None:
    """Genau an der Frist gruen, eine Sekunde darueber rot.

    Belegt, dass ``max_account_age`` wirklich die entscheidende Groesse ist -- und
    nicht ein zufaelliges Nebenprodukt, wie es die alte Fassung war.
    """
    for alter, erwartet_gruen in (
        (timedelta(seconds=5), True),
        (timedelta(seconds=6), False),
    ):
        terminal = SelbstgestempeltesTerminal(
            uhr=_uhr, kursalter={"EURUSD": alter}, is_demo=True
        )
        venue = Mt5Venue(
            name="frist",
            terminal=terminal,
            catalog=_catalog(),
            risk_manager=_fresh_risk(),
            clock=_uhr,
            positionsbuch=FluechtigesPositionsbuch(),
            schwebeakte=FluechtigeSchwebeAkte(),
        )
        venue.connect()
        if erwartet_gruen:
            assert venue.submit_order(_order()).accepted is True
        else:
            with pytest.raises(OrderRejectedError) as fehler:
                venue.submit_order(_order())
            assert fehler.value.reason == "snapshot_stale"
        assert terminal.order_send_calls == (1 if erwartet_gruen else 0)


def test_alter_wird_in_der_ablehnung_genannt() -> None:
    """Wer die Ablehnung liest, muss sehen, WIE alt der Kurs war.

    Ohne Zahl in der Meldung ist im Journal nicht unterscheidbar, ob die Leitung
    zuckte oder seit Stunden tot ist.
    """
    venue, _ = _venue_mit(kursalter={"EURUSD": timedelta(minutes=5)})
    with pytest.raises(OrderRejectedError) as fehler:
        venue.submit_order(_order())
    text = str(fehler.value)
    assert "Alter" in text and "Frist" in text, text
    assert "0:05:00" in text, f"Das gemessene Alter fehlt in der Meldung: {text!r}"

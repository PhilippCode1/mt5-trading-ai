"""Der Einheitenbruch am Mindest-Stopabstand -- gemessen, nicht behauptet.

MT5 fuehrt ``SYMBOL_TRADE_STOPS_LEVEL`` als Vielfaches von ``SYMBOL_POINT``. Jeder
Leser des Feldes im Repo multipliziert es aber mit ``tick_size``
(``venue/smoke.py::_probe_stop``, ``execution/risk_manager.py``,
``execution/runner.py``). Solange ``point == tick_size`` faellt das nicht auf; sobald
sie auseinandergehen, rechnet jeder dieser Leser mit einem falschen Abstand.

``stop_level_in_tickschritten`` rechnet beim Einlesen um -- mit dem GROESSEREN der
beiden Massstaebe, damit die Umstellung in keinem Fall einen kleineren Mindestabstand
ergibt als bisher. Alle Erwartungen unten sind von Hand gerechnet und stehen als
Rechnung im Test; keine ist aus der Implementierung abgelesen.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from mt5_trading_ai.venue.mt5 import RealMt5Terminal, stop_level_in_tickschritten


def _d(text: str) -> Decimal:
    return Decimal(text)


def test_fx_mit_fuenf_stellen_bleibt_unveraendert() -> None:
    """EURUSD: point = tick_size = 0.00001. Rechnung: 10 * 0.00001 = 0.0001 Preis,
    geteilt durch 0.00001 = 10 Tickschritte. Es aendert sich nichts -- und das ist der
    Fall, in dem die Umstellung nichts kaputt machen darf."""
    assert stop_level_in_tickschritten(
        10, point=_d("0.00001"), tick=_d("0.00001")
    ) == 10


def test_grobes_tickraster_wird_nicht_verkleinert() -> None:
    """Index-CFD: point = 0.01, tick_size = 0.25 (tick > point).

    Der Rohwert 50 meint in MT5 50 * 0.01 = 0.50 Preiseinheiten, also 2 Tickschritte.
    Umgerechnet waere der geforderte Abstand damit KLEINER als der bisher gerechnete
    (50 * 0.25 = 12.50). Die Umstellung tut das ausdruecklich nicht: sie senkt keine
    Schwelle, sie schliesst nur die andere Richtung. Erwartung von Hand: 50.
    """
    assert stop_level_in_tickschritten(50, point=_d("0.01"), tick=_d("0.25")) == 50


def test_feineres_tickraster_hebt_den_abstand_an() -> None:
    """Die gefaehrliche Richtung: point = 0.01 > tick_size = 0.001.

    Der Broker verlangt 50 * 0.01 = 0.50 Preiseinheiten Abstand. Bisher rechnete jeder
    Leser 50 * 0.001 = 0.05 -- ein Zehntel davon, also ein zu enger Stop, den der
    Server mit INVALID_STOPS zurueckweist. Von Hand: 0.50 / 0.001 = 500 Tickschritte,
    und 500 * 0.001 = 0.50 trifft den geforderten Abstand genau.
    """
    assert stop_level_in_tickschritten(50, point=_d("0.01"), tick=_d("0.001")) == 500


def test_es_wird_aufgerundet_nie_ab() -> None:
    """Ein halber Tick ist kein Tick. point = 0.01, tick = 0.003, Rohwert 50.

    Von Hand: gefordert sind 50 * 0.01 = 0.50 Preiseinheiten. 0.50 / 0.003 = 166,66...
    -- 166 Ticks waeren 0.498 und damit UNTER dem Minimum des Brokers, 167 Ticks sind
    0.501 und darueber. Erwartung: 167. Wer hier abrundet, baut den Fehler wieder ein,
    den die Umrechnung beheben soll.
    """
    schritte = stop_level_in_tickschritten(50, point=_d("0.01"), tick=_d("0.003"))
    assert schritte == 167
    assert Decimal(166) * _d("0.003") < _d("0.50")  # die Rechnung, nachgestellt
    assert Decimal(schritte) * _d("0.003") >= _d("0.50")


@pytest.mark.parametrize(
    ("rohwert", "point", "tick"),
    [
        (0, "0.01", "0.001"),  # kein Mindestabstand
        (10, "0", "0.001"),  # kein point gemeldet
        (10, "0.01", "0"),  # kein Raster gemeldet
        (-5, "0.01", "0.001"),  # unsinniger Rohwert
    ],
)
def test_unbrauchbare_eingaben_ergeben_nie_etwas_negatives(
    rohwert: int, point: str, tick: str
) -> None:
    """Fail-closed am Rand: ohne brauchbares Raster wird nicht geraten, und ein
    negativer Abstand entsteht nie (er wuerde als "kein Minimum" gelesen)."""
    schritte = stop_level_in_tickschritten(rohwert, point=_d(point), tick=_d(tick))
    assert schritte >= 0
    assert schritte <= max(rohwert, 0)


@pytest.mark.parametrize(
    ("point", "tick"),
    [("0.00001", "0.00001"), ("0.01", "0.25"), ("0.01", "0.001"), ("0.01", "0.003")],
)
def test_die_umstellung_senkt_nie_unter_den_rohwert(point: str, tick: str) -> None:
    """Die Zusage der Reparatur in einem Satz: kein Fall wird nachsichtiger als vorher.

    Vorher stand der Rohwert im Feld. Danach steht mindestens er dort.
    """
    assert stop_level_in_tickschritten(50, point=_d(point), tick=_d(tick)) >= 50


def _symbol_info(*, point: str, tick_size: str, stops_level: int) -> SimpleNamespace:
    """Die Felder, die ``RealMt5Terminal._to_symbol`` aus ``symbol_info`` liest."""
    return SimpleNamespace(
        name="US500",
        digits=2,
        point=point,
        trade_tick_size=tick_size,
        trade_contract_size="1",
        volume_min="0.1",
        volume_step="0.1",
        volume_max="50",
        currency_base="USD",
        currency_profit="USD",
        trade_stops_level=stops_level,
        trade_freeze_level=0,
        visible=True,
    )


def test_der_adapter_traegt_die_umrechnung_ins_symbol() -> None:
    """Nicht nur die Rechenfunktion, sondern der Weg dorthin.

    ``RealMt5Terminal`` laesst sich ohne MetaTrader5 bauen (das Paket wird erst in
    ``initialize`` geladen), also ist die Rohwert-Abbildung hier pruefbar. Von Hand:
    point = 0.01, tick_size = 0.001, Rohwert 50 -> 0.50 Preiseinheiten -> 500
    Tickschritte, und ``stop_level_points * tick_size`` ergibt wieder 0.50.
    """
    terminal = RealMt5Terminal()
    symbol = terminal._to_symbol(
        _symbol_info(point="0.01", tick_size="0.001", stops_level=50)
    )
    assert symbol.tick_size == _d("0.001")
    assert symbol.stop_level_points == 500
    # Die Einheit, auf die sich alle drei Verbraucher verlassen:
    assert Decimal(symbol.stop_level_points) * symbol.tick_size == _d("0.50")


def test_der_adapter_laesst_das_gleiche_raster_in_ruhe() -> None:
    """Gegenprobe am selben Weg: wo point und tick_size gleich sind, bleibt der
    Rohwert stehen (FX mit fuenf Stellen, Rohwert 10)."""
    terminal = RealMt5Terminal()
    symbol = terminal._to_symbol(
        _symbol_info(point="0.00001", tick_size="0.00001", stops_level=10)
    )
    assert symbol.stop_level_points == 10

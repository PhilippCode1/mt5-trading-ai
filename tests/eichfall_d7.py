"""Eichfall D7 (Bewertung 3.7): Geisterpositionen werden beim Start ausgetragen.

ROT gegen 306bbaa (belege/06-d7-rot.txt), Nachstellung V5: drei offene Positionen im
Zustand, der Broker hatte sie im Stillstand geschlossen -- nach dem Neustart zaehlte
der Risikozaehler weiter 3, jede Eroeffnung fiel an ``risk_concurrent_position_cap``,
ohne Ablauf, ohne Werkzeug. Ein Positionsbuch gab es nicht. GRUEN gegen HEAD
(belege/06-d7-gruen.txt).

Die Klasse, nicht der Fall: ``Mt5Venue.adopt_book`` haelt Risikozaehler UND
Positionsbuch gegen ``positions_get()``; Geister werden ausgetragen und in
``startabgleich`` benannt, ``tools/live_betrieb.py`` schreibt sie als
``startabgleich``-Satz ins Journal.
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import SchwebeAkte  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import TS, FakeMt5Terminal, _catalog  # noqa: E402

KONTO = "123"  # das Konto des Fake-Terminals
WAEHRUNG = "USD"
GEISTER = ("EURUSD", "GBPUSD", "XAUUSD")


def _instrument() -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="x",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=None,
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        fees=FeeSchedule(Decimal(7), Decimal(6), Decimal(0), Decimal(0), None, "USD"),
        sessions=(),
    )


def _konto() -> AccountState:
    return AccountState(
        KONTO,
        WAEHRUNG,
        Decimal(10000),
        Decimal(10000),
        Decimal(0),
        Decimal(10000),
        True,
        TS,
    )


def _autorisiere(rm: RiskManager) -> Any:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=OrderRequest(
            "y",
            "EURUSD",
            OrderSide.BUY,
            OrderType.MARKET,
            Decimal("0.01"),
            Decimal("1.0983"),
        ),
        account=_konto(),
        price=Decimal("1.1"),
        spread_bps=Decimal("1"),
        leverage=5,
        now=TS + timedelta(days=1),
    )


def _zustand_mit_drei_geistern(tmp_path: Path) -> Path:
    """Lauf 1: drei Eroeffnungen gebucht, dann hart beendet."""
    pfad = tmp_path / "risikozustand.json"
    rm1 = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    for symbol in GEISTER:
        rm1.record_open_fill(symbol, TS - timedelta(days=2))
    offen = json.loads(pfad.read_text(encoding="utf-8"))["offene_positionen"]
    assert sorted(p["instrument"] for p in offen) == sorted(GEISTER)
    return pfad


def _neustart(tmp_path: Path, pfad: Path) -> tuple[Mt5Venue, RiskManager]:
    """Lauf 2: neuer Prozess, dieselbe Datei, der Broker fuehrt nichts mehr."""
    rm2 = RiskManager(zustand=DateiZustand(pfad))
    kw: dict[str, Any] = {}
    if "zustandsordner" in inspect.signature(Mt5Venue.__init__).parameters:
        kw["zustandsordner"] = tmp_path
    else:
        kw["schwebeakte"] = SchwebeAkte(tmp_path / "schwebende_auftraege.json")
    venue = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True, positions=()),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=rm2,
        clock=lambda: TS,
        **kw,
    )
    venue.connect()
    venue.adopt_book()
    return venue, rm2


def test_geister_werden_beim_start_ausgetragen(tmp_path: Path) -> None:
    pfad = _zustand_mit_drei_geistern(tmp_path)
    _venue, rm2 = _neustart(tmp_path, pfad)

    assert rm2.open_position_count == 0, (
        f"nach dem Neustart zaehlt der Deckel {rm2.open_position_count} Geister"
    )
    auth = _autorisiere(rm2)
    assert auth.reason != "risk_concurrent_position_cap", auth.reason
    assert auth.approved is True, auth.reason
    # Und die Platte weiss es auch: ein dritter Start faende die Geister nicht wieder.
    offen = json.loads(pfad.read_text(encoding="utf-8"))["offene_positionen"]
    assert offen == [], offen


def test_der_startabgleich_nennt_jeden_geist(tmp_path: Path) -> None:
    pfad = _zustand_mit_drei_geistern(tmp_path)
    venue, _rm2 = _neustart(tmp_path, pfad)

    abgleich = venue.startabgleich
    assert abgleich is not None
    assert sorted(sym for sym, _ in abgleich.geister_zaehler) == sorted(GEISTER)
    assert abgleich.offen_beim_broker == ()
    assert abgleich.auffaellig is True


def test_geister_im_positionsbuch_werden_ausgetragen(tmp_path: Path) -> None:
    from mt5_trading_ai.execution.reconcile import Buchposition, Positionsbuch
    from mt5_trading_ai.execution.risiko_zustand import POSITIONSBUCH_DATEI

    buch = Positionsbuch(tmp_path / POSITIONSBUCH_DATEI)
    buch.eintragen(
        Buchposition(
            kennung="open-XAUUSD-1",
            ticket="4711",
            symbol="XAUUSD",
            richtung="kauf",
            menge=Decimal("0.01"),
            eroeffnet_am=TS - timedelta(days=2),
            stop=Decimal("2000"),
        )
    )
    pfad = _zustand_mit_drei_geistern(tmp_path)
    venue, _rm2 = _neustart(tmp_path, pfad)

    assert venue.positionsbuch.laden() == ()
    abgleich = venue.startabgleich
    assert abgleich is not None
    assert [b.kennung for b in abgleich.geister_buch] == ["open-XAUUSD-1"]


def test_live_betrieb_schreibt_den_startabgleich_ins_journal(tmp_path: Path) -> None:
    from tools.live_betrieb import Journal, _startabgleich_journalisieren

    pfad = _zustand_mit_drei_geistern(tmp_path)
    venue, _rm2 = _neustart(tmp_path, pfad)
    journal = Journal(tmp_path / "journale" / "j.jsonl", lauf="eichfall", version="t")

    _startabgleich_journalisieren(venue, journal)

    saetze = [
        json.loads(z)
        for z in journal.pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    assert [s["art"] for s in saetze] == ["startabgleich"]
    geister = sorted(g["instrument"] for g in saetze[0]["geister_zaehler"])
    assert geister == sorted(GEISTER)

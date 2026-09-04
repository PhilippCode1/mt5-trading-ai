"""Eichfaelle D1 (Bewertung 3.1): ein Trockenlauf erreicht das Terminal nie.

ROT gegen 306bbaa (belege/06-d1-rot.txt): im Trockenlauf befragte ``run_signal`` den
Erkundungswuerfel trotzdem; der Versuch lief bis ``RealMt5Terminal._require_write``,
dessen Wurf ``submit_order`` als ungeklaerten Sendeversuch latchte -- Schwebeakteneintrag
plus Global-Halt, und ``clear_halt()`` loeste die naechste Eroeffnung nicht (Nachstellung
V1). Ein Werkzeug fuer die menschlichen Gesten gab es nicht. GRUEN gegen HEAD
(belege/06-d1-gruen.txt).

Die Klasse, nicht der Fall: ``run_signal`` bekommt ``darf_schreiben`` (Vorgabe ``False``
-- ein fehlender Wert sperrt). Ohne Schreibrecht wird nicht erkundet, und auch eine
zugelassene Strategie endet vor dem Senden (``kein_schreibrecht``). ``tools/zustand.py``
traegt die beiden Gesten, die einen persistierten Zustand beenden: ``--halt-freigeben``
und ``--schwebeakte-aufloesen``, dazu ``--zeigen`` ohne Kontonummer.

Alle Ablagen liegen in ``tmp_path`` (A10). Die Attrappen stammen aus
``tests/test_mt5_venue.py``; die Konstruktion des Venues folgt der Signatur des
jeweiligen Standes, damit der rote Lauf an der Zusicherung faellt und nicht am Bau.
"""

from __future__ import annotations

import inspect
import os
import subprocess
import sys
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.backtest.engine import Signal  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import (  # noqa: E402
    SchwebeAkte,
    SchwebenderAuftrag,
)
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.gates.erkundung import entscheide_erkundung  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
    VenueUnavailableError,
)

from test_mt5_venue import TS, FakeMt5Terminal, _catalog  # noqa: E402

KONTO = "50123456"
WAEHRUNG = "USD"


# ---------------------------------------------------------------------------
# Bau je Stand
# ---------------------------------------------------------------------------
class GesperrtesTerminal(FakeMt5Terminal):
    """``order_send`` wie ``RealMt5Terminal._require_write`` bei ``allow_write=False``."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.sendeversuche = 0

    def order_send(self, request: object) -> Any:
        self.sendeversuche += 1
        raise VenueUnavailableError(
            "Real-Terminal: Schreibpfad gesperrt (allow_write=False). "
            "Erst gegen ein Demo-Terminal smoke-testen, dann bewusst freigeben."
        )


def _risk_manager(tmp_path: Path) -> RiskManager:
    return RiskManager(zustand=DateiZustand(tmp_path / "risikozustand.json"))


def _venue(tmp_path: Path, terminal: FakeMt5Terminal, rm: RiskManager) -> Mt5Venue:
    """HEAD: ``zustandsordner=``; 306bbaa: ``schwebeakte=`` mit Pfad in tmp_path."""
    kw: dict[str, Any] = {}
    if "zustandsordner" in inspect.signature(Mt5Venue.__init__).parameters:
        kw["zustandsordner"] = tmp_path
    else:
        kw["schwebeakte"] = SchwebeAkte(tmp_path / "schwebende_auftraege.json")
    venue = Mt5Venue(
        name="t",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=rm,
        clock=lambda: TS,
        **kw,
    )
    venue.connect()
    venue.adopt_book()
    return venue


def _lauf(venue: Mt5Venue, rm: RiskManager, *, zugelassen: bool, cid: str) -> Any:
    """``run_signal`` ohne Schreibrecht -- ``darf_schreiben`` nur, wo es der Stand kennt."""
    kw: dict[str, Any] = {}
    if "darf_schreiben" in inspect.signature(run_signal).parameters:
        kw["darf_schreiben"] = False
    return run_signal(
        venue=venue,
        risk_manager=rm,
        admission=CriteriaVerdict(passed=zugelassen, results=()),
        symbol="EURUSD",
        side=Signal.LONG,
        config=RunnerConfig(
            cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005"))
        ),
        now=TS,
        client_order_id=cid,
        **kw,
    )


def _erkundungskennung() -> str:
    """Eine Kennung, bei der der 5-%-Wuerfel zieht -- deterministisch je Kennung."""
    for _ in range(4000):
        cid = f"open-EURUSD-{uuid.uuid4().hex[:10]}"
        e = entscheide_erkundung(
            ist_papierkonto=True,
            ablehnungsgrund="strategy_not_admitted",
            schluessel=f"EURUSD|LONG|{cid}",
        )
        if e.erkunden:
            return cid
    raise AssertionError("keine Erkundungskennung in 4000 Versuchen")


def _order(cid: str) -> OrderRequest:
    return OrderRequest(
        cid, "EURUSD", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("1.09")
    )


# ---------------------------------------------------------------------------
# V1: nicht zugelassen, kein Schreibrecht -> keine Erkundung, kein Halt, keine Akte
# ---------------------------------------------------------------------------
def test_trockenlauf_ohne_zulassung_erkundet_nicht_und_latcht_nichts(
    tmp_path: Path,
) -> None:
    terminal = GesperrtesTerminal(is_demo=True)
    rm = _risk_manager(tmp_path)
    venue = _venue(tmp_path, terminal, rm)
    cid = _erkundungskennung()

    bericht = _lauf(venue, rm, zugelassen=False, cid=cid)

    assert bericht.opened is False
    assert bericht.reject_reason == "strategy_not_admitted"
    assert bericht.erkundet is False, "ohne Schreibrecht wird nicht gewuerfelt"
    assert terminal.sendeversuche == 0, "das Terminal wurde erreicht"
    assert venue.is_halted() is False, f"Halt gelatcht: {venue.halt_reason}"
    assert venue.schwebende_auftraege() == ()
    assert not (tmp_path / "schwebende_auftraege.json").exists()

    # Die naechste Eroeffnung ist nicht durch den Trockenlauf gesperrt: sie kommt bis
    # zum (gesperrten) Terminal -- das ist der Beweis, dass nichts gelatcht war.
    with pytest.raises(VenueUnavailableError):
        venue.submit_order(_order("open-EURUSD-neu"))


def test_trockenlauf_mit_zulassung_endet_vor_dem_senden(tmp_path: Path) -> None:
    """Auch eine zugelassene Strategie erreicht ohne Schreibrecht das Terminal nie:
    die Kette rechnet bis zum Margendeckel und endet mit ``kein_schreibrecht``."""
    terminal = GesperrtesTerminal(is_demo=True)
    rm = _risk_manager(tmp_path)
    venue = _venue(tmp_path, terminal, rm)

    bericht = _lauf(venue, rm, zugelassen=True, cid="open-EURUSD-zugelassen")

    assert bericht.opened is False
    assert bericht.reject_reason == "kein_schreibrecht", bericht.reject_reason
    namen = [s.name for s in bericht.steps]
    assert "risiko" not in namen or all(
        s.ok for s in bericht.steps if s.name in ("zulassung", "kostentor", "sizing")
    )
    assert "submit" not in namen, "es wurde ein Sendeversuch unternommen"
    assert terminal.sendeversuche == 0
    assert venue.is_halted() is False, f"Halt gelatcht: {venue.halt_reason}"
    assert venue.schwebende_auftraege() == ()


# ---------------------------------------------------------------------------
# tools/zustand.py: --zeigen | --halt-freigeben | --schwebeakte-aufloesen
# ---------------------------------------------------------------------------
def _instrument() -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="mt5",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        fees=FeeSchedule(Decimal(7), Decimal(6), Decimal(-2), Decimal(-1), 2, "USD"),
        sessions=(),
    )


def _konto(equity: str) -> AccountState:
    return AccountState(
        account_id=KONTO,
        currency=WAEHRUNG,
        balance=Decimal(equity),
        equity=Decimal(equity),
        margin_used=Decimal("0"),
        margin_free=Decimal(equity),
        is_demo=True,
        ts=TS,
    )


def _autorisiere(rm: RiskManager, equity: str, now: Any) -> Any:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=OrderRequest(
            "c-probe",
            "EURUSD",
            OrderSide.BUY,
            OrderType.MARKET,
            Decimal("0.01"),
            Decimal("1.09000"),
        ),
        account=_konto(equity),
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def _halt_auf_platte(tmp_path: Path) -> Path:
    """Ein Drawdown-Halt, gebunden an KONTO, in tmp_path/risikozustand.json."""
    pfad = tmp_path / "risikozustand.json"
    rm = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    rm.observe_equity(TS - timedelta(hours=2), Decimal("12000"))
    auth = _autorisiere(rm, "10000", TS)  # 16,7 % Drawdown -> Halt
    assert auth.latch_halt is True, auth.reason
    assert DateiZustand(pfad).laden().lage.halt is True
    return pfad


def test_zustand_zeigen_nennt_halt_akte_und_buch_ohne_kontonummer(
    tmp_path: Path,
) -> None:
    from tools.zustand import zeigen

    _halt_auf_platte(tmp_path)
    SchwebeAkte(tmp_path / "schwebende_auftraege.json").vermerken(
        SchwebenderAuftrag("open-EURUSD-offen", "Timeout", TS, "EURUSD")
    )
    text = "\n".join(zeigen(tmp_path))
    assert "halt: JA" in text
    assert "open-EURUSD-offen" in text
    assert "Positionsbuch" in text
    assert KONTO not in text, "die Kontonummer steht in der Anzeige"


def test_halt_freigeben_loest_nur_mit_passendem_konto(tmp_path: Path) -> None:
    from tools.zustand import EXIT_NICHTS_GETAN, EXIT_OK, halt_freigeben

    pfad = _halt_auf_platte(tmp_path)

    exit_code, meldung = halt_freigeben(tmp_path, "ops-2026-09-04", "99999999")
    assert exit_code == EXIT_NICHTS_GETAN
    assert "zustand_fremdes_konto" in meldung
    assert DateiZustand(pfad).laden().lage.halt is True, "fremdes Konto hat geloest"

    exit_code, meldung = halt_freigeben(tmp_path, "ops-2026-09-04", KONTO)
    assert exit_code == EXIT_OK, meldung
    assert DateiZustand(pfad).laden().lage.halt is False
    assert KONTO not in meldung

    # Ein zweiter Lauf auf derselben Datei sieht keinen Halt mehr.
    rm2 = RiskManager(zustand=DateiZustand(pfad), konto_id=KONTO, waehrung=WAEHRUNG)
    assert _autorisiere(rm2, "12000", TS + timedelta(hours=3)).approved is True


def test_schwebeakte_aufloesen_verlangt_einen_befund(tmp_path: Path) -> None:
    from tools.zustand import EXIT_OK, EXIT_UNBRAUCHBAR, schwebeakte_aufloesen

    akte = SchwebeAkte(tmp_path / "schwebende_auftraege.json")
    akte.vermerken(SchwebenderAuftrag("open-EURUSD-x", "Timeout", TS, "EURUSD"))

    exit_code, _ = schwebeakte_aufloesen(tmp_path, "open-EURUSD-x", "   ")
    assert exit_code == EXIT_UNBRAUCHBAR
    assert [e.client_order_id for e in akte.laden().eintraege] == ["open-EURUSD-x"]

    exit_code, meldung = schwebeakte_aufloesen(
        tmp_path, "open-EURUSD-x", "beim Broker nachgesehen: keine Order"
    )
    assert exit_code == EXIT_OK, meldung
    assert akte.laden().eintraege == ()


def test_zustand_werkzeug_als_prozess(tmp_path: Path) -> None:
    """Die Kommandozeile: ``--zeigen`` Exit 0; ``--schwebeakte-aufloesen`` ohne
    ``--befund`` ist ein Aufruffehler (Exit 2, usage)."""
    werkzeug = ROOT / "tools" / "zustand.py"
    assert werkzeug.is_file(), "tools/zustand.py fehlt"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    zeigen = subprocess.run(
        [sys.executable, str(werkzeug), "--zeigen", "--zustandsordner", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(ROOT),
        timeout=120,
    )
    assert zeigen.returncode == 0, zeigen.stdout + zeigen.stderr
    assert "Risikozustand" in zeigen.stdout
    ohne_befund = subprocess.run(
        [
            sys.executable,
            str(werkzeug),
            "--schwebeakte-aufloesen",
            "open-x",
            "--zustandsordner",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(ROOT),
        timeout=120,
    )
    assert ohne_befund.returncode == 2
    assert "usage" in ohne_befund.stderr
    assert not (tmp_path / "schwebende_auftraege.json").exists()

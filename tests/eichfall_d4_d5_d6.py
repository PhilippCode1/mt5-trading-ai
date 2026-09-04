"""Eichfaelle D4, D5, D6 (Bewertung 3.4-3.6): Halt-Kette, Plattenfehler, defekte Akte.

ROT gegen 306bbaa (belege/06-d4-d5-d6-rot.txt), Nachstellungen V4, V7, V6:

* **D4** ``reconcile()`` ueberschrieb den Grund ``tagesverlust`` mit
  ``reconcile_drift:...``, und ``tools/live_betrieb.py`` loeste daraufhin per
  ``clear_halt()`` beides -- die Notbremse mit.
* **D5** Scheiterte ``SchwebeAkte.vermerken`` mit ``OSError``, blieb ``_halted`` False;
  der Sendeversuch stand nur im Prozessspeicher, die naechste Eroeffnung lief durch.
* **D6** ``vermerken()`` auf einer Akte mit einem unlesbaren Eintrag verwarf alles hinter
  dem Defekt (``open-C``) samt Sperrgrund; eine als Ganzes unlesbare Akte wurde
  ueberschrieben.

GRUEN gegen HEAD (belege/06-d4-d5-d6-gruen.txt). Die Klasse, nicht der Fall: der Halt
fuehrt ALLE Gruende als Kette (``halt_gruende``), ``halt_grund_loesen`` nimmt genau
einen Anteil heraus; im except-Zweig von ``submit_order`` steht der Latch VOR der
Platte, ein Plattenfehler kommt als zweiter Grund und als Ursache-Kette nach aussen;
``vermerken``/``aufloesen`` arbeiten auf den rohen Eintraegen und bergen eine unlesbare
Datei zur Seite.
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.scheduler import SyncScheduler  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import (  # noqa: E402
    SchwebeAkte,
    SchwebenderAuftrag,
)
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Position, Mt5Venue  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import TS, FakeMt5Terminal, _catalog  # noqa: E402


def _risk_manager(tmp_path: Path) -> RiskManager:
    return RiskManager(zustand=DateiZustand(tmp_path / "risikozustand.json"))


def _venue(
    tmp_path: Path,
    terminal: FakeMt5Terminal,
    rm: RiskManager,
    *,
    schwebeakte: SchwebeAkte | None = None,
) -> Mt5Venue:
    """HEAD: ``zustandsordner=`` (Akte darf ausdruecklich uebergeben werden); 306bbaa:
    ``schwebeakte=`` mit Pfad in tmp_path."""
    kw: dict[str, Any] = {}
    if "zustandsordner" in inspect.signature(Mt5Venue.__init__).parameters:
        kw["zustandsordner"] = tmp_path
    akte = schwebeakte or SchwebeAkte(tmp_path / "schwebende_auftraege.json")
    venue = Mt5Venue(
        name="t",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=rm,
        clock=lambda: TS,
        schwebeakte=akte,
        **kw,
    )
    venue.connect()
    venue.adopt_book()
    return venue


def _order(cid: str) -> OrderRequest:
    return OrderRequest(
        cid,
        "EURUSD",
        OrderSide.BUY,
        OrderType.MARKET,
        Decimal("0.01"),
        Decimal("1.0983"),
    )


def _position(ticket: str = "9", volume: str = "0.5") -> Mt5Position:
    return Mt5Position(
        ticket,
        "EURUSD",
        True,
        Decimal(volume),
        Decimal("1.1"),
        None,
        None,
        TS,
        Decimal(0),
        Decimal(0),
    )


# ---------------------------------------------------------------------------
# D4: Halt-Gruende als Kette
# ---------------------------------------------------------------------------
def test_reconcile_ergaenzt_den_halt_grund_und_ueberschreibt_nicht(
    tmp_path: Path,
) -> None:
    terminal = FakeMt5Terminal(is_demo=True)
    venue = _venue(tmp_path, terminal, _risk_manager(tmp_path))
    venue.latch_halt(reason="tagesverlust")
    terminal.set_positions((_position(),))

    ergebnis = venue.reconcile()

    assert ergebnis.halt is True
    grund = str(venue.halt_reason)
    assert grund.startswith("reconcile_drift"), grund
    assert "tagesverlust" in grund, f"der erste Grund ist weg: {grund}"
    assert venue.halt_gruende == (
        "tagesverlust",
        "reconcile_drift:notional_drift_exceeds_limit",
    )


def test_nur_der_eigene_anteil_wird_geloest(tmp_path: Path) -> None:
    terminal = FakeMt5Terminal(is_demo=True)
    venue = _venue(tmp_path, terminal, _risk_manager(tmp_path))
    venue.latch_halt(reason="tagesverlust")
    terminal.set_positions((_position(),))
    venue.reconcile()

    geloest = venue.halt_grund_loesen("reconcile_drift")

    assert geloest == ("reconcile_drift:notional_drift_exceeds_limit",)
    assert venue.is_halted() is True, "die Notbremse ist mit geloest worden"
    assert venue.halt_reason == "tagesverlust"
    assert venue.halt_grund_loesen("reconcile_drift") == ()
    # Erst wenn kein Grund mehr steht, faellt der Halt.
    assert venue.halt_grund_loesen("tagesverlust") == ("tagesverlust",)
    assert venue.is_halted() is False
    assert venue.halt_reason is None


def test_live_betrieb_loest_im_takt_nur_die_erklaerte_drift(tmp_path: Path) -> None:
    """Der Takt von ``tools/live_betrieb.py`` gegen ein ECHTES Venue: eine erkannte
    Broker-Schliessung erklaert die Drift -- die Notbremse bleibt stehen."""
    from tools.live_betrieb import Journal, Lage, takt

    terminal = FakeMt5Terminal(is_demo=True, positions=(_position("t1", "0.10"),))
    rm = _risk_manager(tmp_path)
    venue = _venue(tmp_path, terminal, rm)  # adopt_book: Buch fuehrt EURUSD 0,10
    venue.latch_halt(reason="tagesverlust")
    terminal.set_positions(())  # der Broker hat die Position im Stillstand geschlossen
    bekannt = {
        "EURUSD": Lage(
            symbol="EURUSD",
            ist_kauf=True,
            volumen=Decimal("0.10"),
            seit=TS,
            position_id="t1",
            einstiegspreis=Decimal("1.1"),
            unrealisiert=Decimal("0"),
            swap=Decimal("0"),
        )
    }
    journal = Journal(tmp_path / "journale" / "j.jsonl", lauf="eichfall", version="t")
    scheduler = SyncScheduler(
        venue, max_silence=timedelta(minutes=5), started_at=TS, risk_manager=rm
    )

    takt(
        venue,
        rm,
        scheduler,
        ["EURUSD"],
        CriteriaVerdict(passed=False, results=()),
        journal,
        nr=1,
        max_haltedauer=timedelta(hours=4),
        bekannt=bekannt,
        equity_start=Decimal("10000"),
        verlustgrenze=Decimal("0.02"),
    )

    saetze = [
        json.loads(z)
        for z in journal.pfad.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    erklaert = [s for s in saetze if s["art"] == "halt_erklaert"]
    assert len(erklaert) == 1, [s["art"] for s in saetze]
    assert erklaert[0]["grund"].startswith("reconcile_drift")
    assert erklaert[0]["weiter_gesperrt"] is True
    assert venue.is_halted() is True, "die Notbremse ist mit der Drift geloest worden"
    assert venue.halt_reason == "tagesverlust"


# ---------------------------------------------------------------------------
# D5: Plattenfehler beim Vermerken
# ---------------------------------------------------------------------------
class AkteKaputt(SchwebeAkte):
    def _schreiben(self, eintraege: Any) -> None:
        raise OSError(28, "No space left on device")


class TerminalTimeout(FakeMt5Terminal):
    def order_send(self, request: object) -> Any:
        raise TimeoutError("Antwort blieb aus")


def test_halt_steht_auch_wenn_die_akte_nicht_schreibbar_ist(tmp_path: Path) -> None:
    terminal = TerminalTimeout(is_demo=True)
    venue = _venue(
        tmp_path,
        terminal,
        _risk_manager(tmp_path),
        schwebeakte=AkteKaputt(tmp_path / "akte_voll.json"),
    )

    with pytest.raises(TimeoutError) as ex:
        venue.submit_order(_order("open-EURUSD-z"))

    assert venue.is_halted() is True, "OSError beim Vermerken hat den Halt verhindert"
    assert "open-EURUSD-z" in venue.unklare_sendeversuche()
    grund = str(venue.halt_reason)
    assert "sendeversuch_unklar:open-EURUSD-z" in grund
    assert "schwebeakte_nicht_vermerkt:OSError" in grund
    # Beide Gruende nach aussen: die Platte als Ursache-Kette und als Notiz.
    assert isinstance(ex.value.__cause__, OSError)
    assert any(
        "Schwebeakte nicht vermerkt" in n for n in getattr(ex.value, "__notes__", [])
    )
    # Und die naechste Eroeffnung ist gesperrt -- obwohl die Akte leer blieb.
    with pytest.raises(OrderRejectedError) as abgelehnt:
        venue.submit_order(_order("open-EURUSD-danach"))
    assert abgelehnt.value.reason == "global_halt"


# ---------------------------------------------------------------------------
# D6: eine defekte Akte verwirft nichts
# ---------------------------------------------------------------------------
def _defekte_akte(tmp_path: Path) -> Path:
    pfad = tmp_path / "akte_defekt.json"
    pfad.write_text(
        json.dumps(
            {
                "fassung": 1,
                "eintraege": [
                    {
                        "client_order_id": "open-A",
                        "grund": "Timeout",
                        "seit": "2026-08-17T10:00:00+00:00",
                        "symbol": "EURUSD",
                    },
                    {"client_order_id": "open-B", "grund": "Timeout"},
                    {
                        "client_order_id": "open-C",
                        "grund": "Timeout",
                        "seit": "2026-08-17T11:00:00+00:00",
                        "symbol": "XAUUSD",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return pfad


def test_vermerken_auf_defekter_akte_verwirft_keinen_eintrag(tmp_path: Path) -> None:
    akte = SchwebeAkte(_defekte_akte(tmp_path))
    vorher = akte.laden()
    assert vorher.sperrgrund is not None
    assert "open-C" in [e.client_order_id for e in vorher.eintraege], (
        "schon das Lesen laesst open-C hinter dem Defekt fallen"
    )

    akte.vermerken(SchwebenderAuftrag("open-D", "neu", TS, "GBPUSD"))

    nachher = akte.laden()
    kennungen = [e.client_order_id for e in nachher.eintraege]
    assert kennungen == ["open-A", "open-B", "open-C", "open-D"], kennungen
    assert nachher.sperrgrund is not None, "der Sperrgrund ist mit dem Vermerken weg"
    roh = json.loads(akte.pfad.read_text(encoding="utf-8"))  # type: ignore[union-attr]
    assert roh["eintraege"][1] == {"client_order_id": "open-B", "grund": "Timeout"}, (
        "der unlesbare Eintrag wurde nicht roh zurueckgeschrieben"
    )


def test_eine_unlesbare_akte_wird_geborgen_nicht_ueberschrieben(tmp_path: Path) -> None:
    pfad = tmp_path / "akte.json"
    pfad.write_bytes(b"{kein json")
    akte = SchwebeAkte(pfad)

    akte.vermerken(SchwebenderAuftrag("open-E", "neu", datetime.now(UTC), "EURUSD"))

    beweise = list(tmp_path.glob("akte.json.defekt-*"))
    assert len(beweise) == 1, "die unlesbaren Bytes sind nicht zur Seite gelegt"
    assert beweise[0].read_bytes() == b"{kein json"
    befund = akte.laden()
    assert befund.schwebt is True
    kennungen = [e.client_order_id for e in befund.eintraege]
    assert "open-E" in kennungen
    assert any(k.startswith("schwebeakte-defekt-") for k in kennungen), kennungen

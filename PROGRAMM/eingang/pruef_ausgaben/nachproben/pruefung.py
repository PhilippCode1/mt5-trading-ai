"""Nachpruefung einzelner Befunde -- nur lesend, gegen Fake-Terminal / Stub-mt5."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

REPO = Path("/root/mt5-trading-ai")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))
SCRATCH = Path(__file__).parent

for k in ("MT5_RISIKO_ZUSTAND", "MT5_RISIKO_ZUSTAND_ORDNER", "MT5_SCHWEBENDE_AUFTRAEGE"):
    os.environ.pop(k, None)

from test_mt5_venue import FakeMt5Terminal, _catalog, TS  # noqa: E402
from mt5_trading_ai.venue.mt5 import (  # noqa: E402
    Mt5Venue, RealMt5Terminal, kennmarke, _fuellart,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRequest, OrderSide, OrderType, VenueUnavailableError, AccountState,
    Instrument, AssetClass, FeeSchedule,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal  # noqa: E402
from mt5_trading_ai.execution.cost_gate import CostGate  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import SchwebeAkte  # noqa: E402
from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402
from mt5_trading_ai.gates.erkundung import entscheide_erkundung  # noqa: E402
from mt5_trading_ai.backtest.engine import Signal  # noqa: E402
from mt5_trading_ai.risk.sizing import size_position  # noqa: E402
from mt5_trading_ai.risk.leverage import clamp_leverage  # noqa: E402
from mt5_trading_ai.execution.leverage_preflight import evaluate_leverage_preflight  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Position  # noqa: E402


def kopf(t: str) -> None:
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---------------------------------------------------------------------------
kopf("V1  Trockenlauf + Erkundung: _require_write-Wurf wird als 'schwebender Auftrag' + Global-Halt gelatcht")


class GesperrtesTerminal(FakeMt5Terminal):
    """order_send verhaelt sich wie RealMt5Terminal._require_write bei allow_write=False."""

    def order_send(self, request):  # type: ignore[override]
        raise VenueUnavailableError(
            "Real-Terminal: Schreibpfad gesperrt (allow_write=False). "
            "Erst gegen ein Demo-Terminal smoke-testen, dann bewusst freigeben."
        )


akte_pfad = SCRATCH / "schwebende_auftraege.json"
akte_pfad.unlink(missing_ok=True)
term = GesperrtesTerminal(is_demo=True)
rm = RiskManager()
venue = Mt5Venue(name="t", terminal=term, catalog=_catalog(), risk_manager=rm,
                 clock=lambda: TS, schwebeakte=SchwebeAkte(akte_pfad))
venue.connect()
venue.adopt_book()
# Eine Kennung finden, bei der die 5%-Erkundung zieht (wie live_betrieb: uuid im Schluessel).
import uuid
for _ in range(2000):
    cid = f"open-EURUSD-{uuid.uuid4().hex[:10]}"
    e = entscheide_erkundung(ist_papierkonto=True, ablehnungsgrund="strategy_not_admitted",
                             schluessel=f"EURUSD|LONG|{cid}")
    if e.erkunden:
        break
print("Erkundungs-Kennung:", cid, "p=", e.wahrscheinlichkeit)
bericht = run_signal(
    venue=venue, risk_manager=rm,
    admission=CriteriaVerdict(passed=False, results=()),  # wie live_betrieb ohne --scharf
    symbol="EURUSD", side=Signal.LONG,
    config=RunnerConfig(cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005"))),
    now=TS, client_order_id=cid,
)
for s in bericht.steps:
    print(f"  {'OK' if s.ok else '!!'} {s.name}: {s.detail[:90]}")
print("reject_reason:", bericht.reject_reason)
print("venue.is_halted():", venue.is_halted(), "| halt_reason:", venue.halt_reason)
print("Schwebeakte auf Platte:", akte_pfad.read_text() if akte_pfad.exists() else "(keine)")
print("-> naechste Eroeffnung (auch nach clear_halt):")
venue.clear_halt()
try:
    venue.submit_order(OrderRequest("open-EURUSD-neu", "EURUSD", OrderSide.BUY, OrderType.MARKET,
                                    Decimal("0.01"), Decimal("1.09")))
except Exception as exc:
    print("  ", type(exc).__name__, getattr(exc, "reason", ""), str(exc)[:120])

# ---------------------------------------------------------------------------
kopf("V2  RealMt5Terminal.order_send: Reduce-Only ohne passende Position -> Marktorder OHNE 'position' geht raus")


class StubMt5:
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_REMOVE = 8
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    POSITION_TYPE_BUY = 0
    ACCOUNT_TRADE_MODE_DEMO = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self) -> None:
        self.gesendet: list[dict] = []
        self.positions = ()

    def terminal_info(self):
        return SimpleNamespace(connected=True, trade_allowed=True)

    def account_info(self):
        return SimpleNamespace(login=1, currency="USD", balance=1e4, equity=1e4, margin=0.0,
                               margin_free=1e4, trade_mode=0, leverage=30)

    def symbol_info(self, name):
        return SimpleNamespace(name=name, filling_mode=1, point=0.00001, digits=5,
                               trade_tick_size=0.00001, trade_contract_size=100000.0,
                               volume_min=0.01, volume_step=0.01, volume_max=100.0,
                               currency_base="EUR", currency_profit="USD",
                               trade_stops_level=10, trade_freeze_level=0, visible=True)

    def symbol_info_tick(self, name):
        return SimpleNamespace(time=int(TS.timestamp()), bid=1.0999, ask=1.1)

    def positions_get(self, **kw):
        # Die Position ist zwischen _reduces_position (Venue) und order_send (Terminal)
        # vom Broker-Stop geschlossen worden: leerer Bestand, KEIN Fehler.
        return self.positions

    def orders_get(self, **kw):
        return ()

    def order_send(self, req):
        self.gesendet.append(dict(req))
        return SimpleNamespace(retcode=10009, order=777, deal=778, volume=req.get("volume", 0),
                               price=req.get("price", 0), comment="Done")


stub = StubMt5()
real = RealMt5Terminal(allow_write=True, require_demo=True)
real._mt5 = stub
res = real.order_send({
    "client_order_id": "close-EURUSD-abc", "symbol": "EURUSD", "side": "sell",
    "order_type": "market", "volume": Decimal("0.10"), "stop_loss": Decimal("0"),
    "take_profit": None, "limit_price": None, "reduce_only": True, "comment": "x",
})
print("gesendeter Request:", {k: v for k, v in stub.gesendet[-1].items() if k != "magic"})
print("'position' im Request?", "position" in stub.gesendet[-1], "| sl =", stub.gesendet[-1]["sl"])
print("Mt5SendResult.accepted =", res.accepted, "filled =", res.filled_volume)

kopf("V2b RealMt5Terminal.modify_stops: Request ohne 'symbol'; nur-SL-Aufruf schickt kein 'tp'")
stub.positions = (SimpleNamespace(ticket=777, symbol="EURUSD", type=0, volume=0.1, sl=1.09, tp=0.0),)
real.modify_stops("777", Decimal("1.09"), None)
print("SLTP-Request:", stub.gesendet[-1])

# ---------------------------------------------------------------------------
kopf("V3  Positionsgroesse ohne Waehrungsumrechnung (Konto USD, Instrument EURGBP, Notierung GBP)")
eq = Decimal("10000")  # USD
r = size_position(account_equity=eq, risk_fraction=Decimal("0.005"), stop_floor_bps=Decimal("15"),
                  stop_budget_bps=Decimal("333"), requested_stop_bps=Decimal("15"),
                  price=Decimal("0.8500"), contract_size=Decimal("100000"),
                  volume_min=Decimal("0.01"), volume_step=Decimal("0.01"), volume_max=None,
                  leverage=5)
gbpusd = Decimal("1.27")
stop_price = Decimal("0.85") * Decimal("15") / Decimal("10000")
risiko_gbp = r.volume * Decimal("100000") * stop_price
print(f"volume={r.volume}  risk_currency(USD)={r.risk_currency}  "
      f"Verlust am Stop = {risiko_gbp:.2f} GBP = {risiko_gbp * gbpusd:.2f} USD "
      f"(+{(risiko_gbp * gbpusd / r.risk_currency - 1) * 100:.0f} % ueber Budget)")
r2 = size_position(account_equity=eq, risk_fraction=Decimal("0.0025"), stop_floor_bps=Decimal("15"),
                   stop_budget_bps=Decimal("333"), requested_stop_bps=Decimal("15"),
                   price=Decimal("150.00"), contract_size=Decimal("100000"),
                   volume_min=Decimal("0.01"), volume_step=Decimal("0.01"), volume_max=None,
                   leverage=5)
print("USDJPY auf USD-Konto: volume =", r2.volume, "reasons =", r2.reasons,
      "(korrekt waeren ~", (Decimal("25") * Decimal("150") / (Decimal("150") * Decimal("0.0015") * Decimal("100000"))).quantize(Decimal("0.01")), "Lot)")

kopf("V3b Hebelklammer: effektiver Hebel je Klasse ohne requested_leverage (Betriebsfall)")
for k in ("fx_major", "fx_minor", "gold", "index_major", "index_minor", "commodity_non_gold", "equity", "crypto"):
    d = clamp_leverage(requested=None, asset_class=k)
    print(f"  {k:20s} class_cap={d.class_cap:>3} -> effektiv={d.leverage} ({d.binding})")

kopf("V3c leverage_preflight USDJPY (USD-Konto, 0,01 Lot, margin_free 5000 USD)")
inst = Instrument(symbol="USDJPY", venue="x", asset_class=AssetClass.FX_MAJOR,
                  contract_size=Decimal("100000"), tick_size=Decimal("0.001"), pip_size=Decimal("0.01"),
                  digits=3, volume_min=Decimal("0.01"), volume_step=Decimal("0.01"), volume_max=None,
                  base_currency="USD", quote_currency="JPY", stop_level_points=0, freeze_level_points=0,
                  fees=FeeSchedule(Decimal(7), Decimal(7), Decimal(0), Decimal(0), None, "USD"),
                  sessions=())
acc = AccountState("1", "USD", Decimal(10000), Decimal(10000), Decimal(0), Decimal(5000), True, TS, leverage=30)
req = OrderRequest("x", "USDJPY", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("149"))
p = evaluate_leverage_preflight(instrument=inst, request=req, account=acc, price=Decimal("150"))
print("approved =", p.approved, "reason =", p.reason, "required_margin =", p.required_margin,
      "(echte Marge bei 1:30 = 0,01*100000/30 = 33 USD)")

# ---------------------------------------------------------------------------
kopf("V4  reconcile() ueberschreibt einen fremden Halt-Grund; live_betrieb loest 'reconcile_drift*'")
term4 = FakeMt5Terminal(is_demo=True)
v4 = Mt5Venue(name="t", terminal=term4, catalog=_catalog(), risk_manager=RiskManager(), clock=lambda: TS)
v4.connect(); v4.adopt_book()
v4.latch_halt(reason="tagesverlust")
print("vorher:", v4.halt_reason)
term4.set_positions((Mt5Position("9", "EURUSD", True, Decimal("0.5"), Decimal("1.1"), None, None, TS, Decimal(0), Decimal(0)),))
v4.reconcile()
print("nach reconcile():", v4.halt_reason, "| startswith('reconcile_drift') =", str(v4.halt_reason).startswith("reconcile_drift"))

# ---------------------------------------------------------------------------
kopf("V5  Geisterpositionen: Zustand mit 3 offenen Positionen, Broker hat sie im Stillstand geschlossen")
zpfad = SCRATCH / "risikozustand.json"
zpfad.unlink(missing_ok=True)
rm1 = RiskManager(zustand=DateiZustand(zpfad), konto_id="123", waehrung="USD")
inst_eur = Instrument(symbol="EURUSD", venue="x", asset_class=AssetClass.FX_MAJOR,
                      contract_size=Decimal("100000"), tick_size=Decimal("0.00001"), pip_size=Decimal("0.0001"),
                      digits=5, volume_min=Decimal("0.01"), volume_step=Decimal("0.01"), volume_max=None,
                      base_currency="EUR", quote_currency="USD", stop_level_points=10, freeze_level_points=0,
                      fees=FeeSchedule(Decimal(7), Decimal(6), Decimal(0), Decimal(0), None, "USD"), sessions=())
acc2 = AccountState("123", "USD", Decimal(10000), Decimal(10000), Decimal(0), Decimal(10000), True, TS)
for s in ("EURUSD", "GBPUSD", "XAUUSD"):
    rm1.record_open_fill(s, TS - timedelta(days=2))
print("Datei offene_positionen:", json.loads(zpfad.read_text())["offene_positionen"])
# Neustart: neuer Prozess, gleicher Zustand; beim Broker ist nichts mehr offen.
rm2 = RiskManager(zustand=DateiZustand(zpfad))
req2 = OrderRequest("y", "EURUSD", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("1.0983"))
a = rm2.authorize_opening(instrument=inst_eur, request=req2, account=acc2, price=Decimal("1.1"),
                          spread_bps=Decimal("1"), leverage=5, now=TS + timedelta(days=1))
print("open_position_count nach Neustart:", rm2.open_position_count, "| approved:", a.approved, "| reason:", a.reason)

# ---------------------------------------------------------------------------
kopf("V6  SchwebeAkte: vermerken() auf defekter Akte verwirft die unlesbaren Eintraege dauerhaft")
akte2 = SCRATCH / "akte_defekt.json"
akte2.write_text(json.dumps({"fassung": 1, "eintraege": [
    {"client_order_id": "open-A", "grund": "Timeout", "seit": "2026-08-17T10:00:00+00:00", "symbol": "EURUSD"},
    {"client_order_id": "open-B", "grund": "Timeout"},   # 'seit' fehlt -> Abbruch des Lesens
    {"client_order_id": "open-C", "grund": "Timeout", "seit": "2026-08-17T11:00:00+00:00", "symbol": "XAUUSD"},
]}))
ak = SchwebeAkte(akte2)
b = ak.laden()
print("vorher: eintraege =", [e.client_order_id for e in b.eintraege], "| sperrgrund =", b.sperrgrund)
from mt5_trading_ai.execution.schwebende_auftraege import SchwebenderAuftrag
ak.vermerken(SchwebenderAuftrag("open-D", "neu", TS, "GBPUSD"))
b2 = ak.laden()
print("nachher: eintraege =", [e.client_order_id for e in b2.eintraege], "| sperrgrund =", b2.sperrgrund,
      "| 'open-C' noch da?", any(e.client_order_id == "open-C" for e in b2.eintraege))

# ---------------------------------------------------------------------------
kopf("V7  submit_order-except-Zweig: scheitert vermerken() (OSError), bleibt _halted False")


class AkteKaputt(SchwebeAkte):
    def _schreiben(self, eintraege):  # type: ignore[override]
        raise OSError(28, "No space left on device")


class TerminalTimeout(FakeMt5Terminal):
    def order_send(self, request):  # type: ignore[override]
        raise TimeoutError("Antwort blieb aus")


term7 = TerminalTimeout(is_demo=True)
v7 = Mt5Venue(name="t", terminal=term7, catalog=_catalog(), risk_manager=RiskManager(), clock=lambda: TS,
              schwebeakte=AkteKaputt(SCRATCH / "akte_voll.json"))
v7.connect(); v7.adopt_book()
try:
    v7.submit_order(OrderRequest("open-EURUSD-z", "EURUSD", OrderSide.BUY, OrderType.MARKET,
                                 Decimal("0.01"), Decimal("1.0983")))
except Exception as exc:
    print("Ausnahme nach aussen:", type(exc).__name__, "-", exc)
print("venue.is_halted():", v7.is_halted(), "| unklare_sendeversuche:", v7.unklare_sendeversuche())

# ---------------------------------------------------------------------------
kopf("V8  kennmarke: Groesse der magic-Zahl")
m = kennmarke("open-EURUSD-1a2b3c4d5e")
print("magic =", m, "| bits =", m.bit_length(), "| > 2^32:", m >= 2**32, "| > 2^53:", m >= 2**53)

kopf("V9  _fuellart: Bitmaske 4 wird als ORDER_FILLING_RETURN gedeutet")
class M:
    ORDER_FILLING_FOK = 0; ORDER_FILLING_IOC = 1; ORDER_FILLING_RETURN = 2
    @staticmethod
    def symbol_info(s): return SimpleNamespace(filling_mode=4)
print("filling_mode=4 ->", _fuellart(M, "X"), "(MT5: Bit 4 = SYMBOL_FILLING_BOC, ORDER_FILLING_BOC=3)")

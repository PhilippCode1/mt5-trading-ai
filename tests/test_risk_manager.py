"""Tests fuer die Risikoschicht (``execution/risk_manager.py``).

Die reine ``authorize_opening`` fuehrt die vier Grenzen in der vorgeschriebenen
Reihenfolge (Kill-Switch -> Drossel -> Stop-Budget -> Groesse). Jeder Test belegt, dass
das jeweilige Modul im Order-Pfad **greift** -- nicht nur, dass es existiert.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from mt5_trading_ai.execution.risk_manager import RiskManager, RiskPolicy
from mt5_trading_ai.gates.evaluation import ThrottlePolicy
from mt5_trading_ai.risk.limits import LossLimits
from mt5_trading_ai.venue.protocol import (
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


def _instrument(
    *, asset_class: AssetClass = AssetClass.FX_MAJOR, stop_level_points: int = 10
) -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="mt5",
        asset_class=asset_class,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=stop_level_points,
        freeze_level_points=0,
        fees=FeeSchedule(
            commission_per_lot_round_turn=Decimal("7"),
            typical_spread_points=Decimal("6"),
            swap_long_per_lot_per_night=Decimal("-2"),
            swap_short_per_lot_per_night=Decimal("-1"),
            triple_swap_weekday=2,
            currency="USD",
        ),
        sessions=(),
    )


def _account(equity: str = "10000") -> AccountState:
    return AccountState(
        account_id="1",
        currency="USD",
        balance=Decimal(equity),
        equity=Decimal(equity),
        margin_used=Decimal("0"),
        margin_free=Decimal(equity),
        is_demo=False,
        ts=NOW,
    )


def _request(*, volume: str = "0.01", stop_loss: str = "1.09000") -> OrderRequest:
    return OrderRequest(
        client_order_id="c-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal(volume),
        stop_loss=Decimal(stop_loss),
    )


def _authorize(
    rm: RiskManager,
    *,
    request: OrderRequest,
    account: AccountState,
    instrument: Instrument | None = None,
    now: datetime = NOW,
):
    return rm.authorize_opening(
        instrument=instrument or _instrument(),
        request=request,
        account=account,
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def test_approves_a_budget_respecting_order() -> None:
    rm = RiskManager()
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is True
    assert auth.reason is None


def test_rejects_volume_over_risk_budget() -> None:
    # (a) 0.10 Lot auf 10k Equity mit ~91 bps Stop riskiert ~1 % >> 0,25 % Budget.
    rm = RiskManager()
    auth = _authorize(rm, request=_request(volume="0.10"), account=_account())
    assert auth.approved is False
    assert auth.reason == "volume_exceeds_risk_budget"


def test_rejects_when_stop_floor_exceeds_budget() -> None:
    # (b) safety=100 druckt die Budget-Obergrenze auf ~10 bps; der Tiefe-Floor (15 bps,
    # Tiefe unbekannt) liegt darueber -> stop_floor_exceeds_budget, no_trade.
    rm = RiskManager(RiskPolicy(safety=Decimal("100")))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is False
    assert auth.reason == "risk_sizing_stop_floor_exceeds_budget"


def test_rejects_untradeable_stop_budget() -> None:
    # safety=300 -> Margin-Obergrenze < Kosten-Untergrenze -> Budget untradeable.
    rm = RiskManager(RiskPolicy(safety=Decimal("300")))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is False
    assert auth.reason == "stop_budget_cost_floor_above_margin_ceiling"


def test_drawdown_halt_latches() -> None:
    # (c) Fenster-Hoechststand 12k, Equity 10k -> Drawdown 16,7 % >= 10 % -> HALT.
    rm = RiskManager()
    rm.observe_equity(NOW - timedelta(hours=1), Decimal("12000"))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account("10000"))
    assert auth.approved is False
    assert auth.reason == "risk_drawdown_limit_reached"
    assert auth.latch_halt is True


def test_drawdown_halt_clears_with_manual_release() -> None:
    rm = RiskManager(manual_release_id="ops-2026-08-13")
    rm.observe_equity(NOW - timedelta(hours=1), Decimal("12000"))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account("10000"))
    # Freigabe hebt den Halt: Drawdown bleibt gemeldet, aber kein HALT-Zustand.
    assert auth.latch_halt is False


def test_daily_loss_blocks_without_latch() -> None:
    # Tagesverlust 3 % >= 2 % -> REDUCE_ONLY (kein Eroeffnen), aber kein Latch-Halt.
    rm = RiskManager()
    rm.observe_equity(NOW, Decimal("10000"))  # Tagesstart
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account("9700"))
    assert auth.approved is False
    assert auth.reason == "risk_daily_loss_limit_reached"
    assert auth.latch_halt is False


def test_throttle_blocks_second_trade_in_cooldown() -> None:
    # (d) Nach einem Fill ist dasselbe Instrument im Cooldown/der Mindesthaltedauer.
    rm = RiskManager()
    rm.record_open_fill("EURUSD", NOW)
    auth = _authorize(
        rm,
        request=_request(volume="0.01"),
        account=_account(),
        now=NOW + timedelta(minutes=1),
    )
    assert auth.approved is False
    assert auth.reason.startswith("throttle_")


def test_concurrent_position_cap_blocks() -> None:
    rm = RiskManager()
    rm.record_open_fill("GBPUSD", NOW - timedelta(hours=2))
    rm.record_open_fill("USDCHF", NOW - timedelta(hours=2))
    rm.record_open_fill("AUDUSD", NOW - timedelta(hours=2))  # 3 offen = Deckel
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is False
    assert auth.reason == "risk_concurrent_position_cap"


def test_record_close_frees_a_slot() -> None:
    rm = RiskManager()
    for sym in ("GBPUSD", "USDCHF", "AUDUSD"):
        rm.record_open_fill(sym, NOW - timedelta(hours=2))
    rm.record_close("AUDUSD")  # ein Platz frei
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is True


def test_gap_blackout_blocks_opening() -> None:
    rm = RiskManager(gap_events=(NOW + timedelta(hours=1),))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account())
    assert auth.approved is False
    assert auth.reason == "risk_gap_blackout"


def test_new_day_resets_day_start_equity() -> None:
    # Verlust am Vortag zaehlt am Folgetag nicht mehr gegen das Tageslimit.
    rm = RiskManager()
    rm.observe_equity(NOW, Decimal("10000"))
    next_day = NOW + timedelta(days=1)
    auth = rm.authorize_opening(
        instrument=_instrument(),
        request=_request(volume="0.01"),
        account=AccountState(
            account_id="1",
            currency="USD",
            balance=Decimal("9700"),
            equity=Decimal("9700"),
            margin_used=Decimal("0"),
            margin_free=Decimal("9700"),
            is_demo=False,
            ts=next_day,
        ),
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=next_day,
    )
    # Tagesstart ist neu 9700 -> kein Tagesverlust -> kein daily_loss-Block.
    assert auth.reason != "risk_daily_loss_limit_reached"


def test_custom_loss_limits_are_honoured() -> None:
    strict = RiskPolicy(loss_limits=LossLimits(max_daily_loss_fraction=Decimal("0.01")))
    rm = RiskManager(strict)
    rm.observe_equity(NOW, Decimal("10000"))
    auth = _authorize(rm, request=_request(volume="0.01"), account=_account("9850"))
    assert auth.reason == "risk_daily_loss_limit_reached"  # 1,5 % >= 1 %


# --- §9-Regressionen (Paket-4-Review) ------------------------------------


def test_release_rearms_after_recovery_then_new_episode_halts() -> None:
    # §9 #1: eine Freigabe entwaffnet den Kill-Switch NICHT dauerhaft.
    rm = RiskManager()
    rm.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    # Halt-Episode: Drawdown 16,7 % -> HALT.
    a1 = _authorize(rm, request=_request(), account=_account("10000"))
    assert a1.latch_halt is True
    # Betreiber gibt frei -> sofort weiter handelbar (Drawdown noch >= Grenze).
    rm.release_drawdown("ops-1")
    a2 = _authorize(
        rm,
        request=_request(),
        account=_account("10000"),
        now=NOW + timedelta(minutes=1),
    )
    assert a2.latch_halt is False
    # Erholung ueber die Grenze -> Freigabe verbraucht, Kill-Switch wieder scharf.
    _authorize(
        rm,
        request=_request(),
        account=_account("11900"),
        now=NOW + timedelta(minutes=2),
    )  # ~0,8 % Drawdown < 10 %
    # Neue, unabhaengige Episode -> HALT feuert erneut.
    a4 = _authorize(
        rm, request=_request(), account=_account("9000"), now=NOW + timedelta(minutes=3)
    )  # 25 % Drawdown
    assert a4.latch_halt is True
    assert a4.reason == "risk_drawdown_limit_reached"


def test_release_voided_when_drawdown_deepens() -> None:
    # §9 #1: vertieft sich der Drawdown ueber das freigegebene Niveau -> neuer Halt.
    rm = RiskManager()
    rm.observe_equity(NOW - timedelta(hours=2), Decimal("12000"))
    _authorize(rm, request=_request(), account=_account("10600"))  # ~11,7 % -> HALT
    rm.release_drawdown("ops-1")
    a2 = _authorize(
        rm,
        request=_request(),
        account=_account("10600"),
        now=NOW + timedelta(minutes=1),
    )
    assert a2.latch_halt is False  # Freigabe deckt das aktuelle Niveau
    # Ohne Erholung tiefer (25 %) -> Freigabe ungueltig, HALT erneut.
    a3 = _authorize(
        rm, request=_request(), account=_account("9000"), now=NOW + timedelta(minutes=2)
    )
    assert a3.latch_halt is True


def test_rejects_stop_below_cost_floor() -> None:
    # §9 #2: fx_minor Kosten-Floor = 40 bps; ein 25-bps-Stop ist unhandelbar.
    rm = RiskManager()
    inst = _instrument(asset_class=AssetClass.FX_MINOR)
    # stop_loss 1.09725 -> ~25 bps von 1.10000; Tiefe-Floor 15 bps aendert das nicht.
    req = _request(volume="0.01", stop_loss="1.09725")
    auth = _authorize(rm, request=req, account=_account(), instrument=inst)
    assert auth.approved is False
    assert auth.reason == "stop_budget_below_cost_floor"


def test_daily_account_cap_resets_next_day() -> None:
    # §9 #4: die Tageskappe muss am Folgetag zuruecksetzen (Lesepfad-Reset).
    rm = RiskManager(
        RiskPolicy(throttle=ThrottlePolicy(max_trades_per_account_per_day=1))
    )
    rm.record_open_fill("EURUSD", NOW)
    # Gleicher Tag: Kappe erreicht -> Drossel.
    same_day = _authorize(
        rm, request=_request(), account=_account(), now=NOW + timedelta(minutes=1)
    )
    assert same_day.approved is False and same_day.reason.startswith("throttle_")
    # Folgetag: Kappe zurueckgesetzt -> keine Konto-Tageskappen-Sperre mehr.
    next_day = _authorize(
        rm, request=_request(), account=_account(), now=NOW + timedelta(days=1)
    )
    assert next_day.approved is True


def test_open_positions_are_deduped_per_symbol() -> None:
    # §9 #6: derselbe Symbol zaehlt fuer den Deckel nur einmal (netto je Symbol).
    rm = RiskManager()
    rm.record_open_fill("EURUSD", NOW)
    rm.record_open_fill("EURUSD", NOW)  # kein Doppelzaehlen
    assert rm.open_position_count == 1
    rm.record_open_fill("GBPUSD", NOW)
    assert rm.open_position_count == 2
    rm.record_close("EURUSD")
    assert rm.open_position_count == 1

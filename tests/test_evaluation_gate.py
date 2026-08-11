"""Bewerten ist nicht handeln — die Trennung ist testbar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mastertrade.gates.evaluation import (
    Candidate,
    GateState,
    OpenPosition,
    ThrottlePolicy,
    select_one,
    trade_rate,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
POLICY = ThrottlePolicy()


def test_at_most_one_trade_per_run() -> None:
    """Rangliste statt Ausloesung: aus vier Kandidaten wird einer."""
    candidates = [
        Candidate("EURUSD", "fx_major", 88.0),
        Candidate("GBPUSD", "fx_major", 91.0),
        Candidate("USDJPY", "fx_major", 85.0),
        Candidate("XAUUSD", "gold", 80.0),
    ]
    result = select_one(candidates, GateState(now=NOW), POLICY)
    assert result.selected is not None
    assert result.selected.instrument == "GBPUSD"
    assert len(result.suppressed) == 3
    assert all(d.reasons == ("not_top_ranked",) for d in result.suppressed)


def test_below_threshold_is_never_a_candidate() -> None:
    result = select_one(
        [Candidate("EURUSD", "fx_major", POLICY.score_threshold - 0.01)],
        GateState(now=NOW),
        POLICY,
    )
    assert result.selected is None
    assert result.suppressed[0].reasons == ("below_threshold",)


def test_cooldown_blocks_the_same_instrument() -> None:
    state = GateState(
        now=NOW,
        last_trade_at={
            "EURUSD": NOW - POLICY.cooldown_per_instrument + timedelta(seconds=1)
        },
    )
    result = select_one([Candidate("EURUSD", "fx_major", 95.0)], state, POLICY)
    assert result.selected is None
    assert "cooldown_active" in result.suppressed[0].reasons

    expired = GateState(
        now=NOW,
        last_trade_at={"EURUSD": NOW - POLICY.cooldown_per_instrument},
    )
    assert (
        select_one([Candidate("EURUSD", "fx_major", 95.0)], expired, POLICY).selected
        is not None
    )


def test_min_hold_blocks_replacing_a_fresh_position() -> None:
    state = GateState(
        now=NOW,
        open_positions=(OpenPosition("EURUSD", NOW - timedelta(minutes=1)),),
    )
    result = select_one([Candidate("EURUSD", "fx_major", 95.0)], state, POLICY)
    assert result.selected is None
    assert "min_hold_not_reached" in result.suppressed[0].reasons


def test_daily_caps() -> None:
    per_instrument = GateState(
        now=NOW,
        trades_today_per_instrument={
            "EURUSD": POLICY.max_trades_per_instrument_per_day
        },
    )
    result = select_one([Candidate("EURUSD", "fx_major", 95.0)], per_instrument, POLICY)
    assert "instrument_daily_cap" in result.suppressed[0].reasons

    account = GateState(
        now=NOW, trades_today_account=POLICY.max_trades_per_account_per_day
    )
    result = select_one([Candidate("EURUSD", "fx_major", 95.0)], account, POLICY)
    assert result.selected is None
    assert "account_daily_cap" in result.suppressed[0].reasons


def test_concurrent_position_cap_blocks_new_instruments_only() -> None:
    open_positions = tuple(
        OpenPosition(symbol, NOW - timedelta(hours=2))
        for symbol in ("EURUSD", "GBPUSD", "USDJPY")
    )
    state = GateState(now=NOW, open_positions=open_positions)

    blocked = select_one([Candidate("XAUUSD", "gold", 95.0)], state, POLICY)
    assert blocked.selected is None
    assert "concurrent_position_cap" in blocked.suppressed[0].reasons

    # Ein bereits offenes Instrument erhoeht die Positionszahl nicht.
    allowed = select_one([Candidate("EURUSD", "fx_major", 95.0)], state, POLICY)
    assert allowed.selected is not None


def test_correlation_cap_blocks_the_same_bet_twice() -> None:
    state = GateState(
        now=NOW,
        open_positions=(OpenPosition("EURUSD", NOW - timedelta(hours=2)),),
    )
    candidate = Candidate("GBPUSD", "fx_major", 95.0, correlations={"EURUSD": 0.85})
    result = select_one([candidate], state, POLICY)
    assert result.selected is None
    assert any(r.startswith("correlated_with:") for r in result.suppressed[0].reasons)

    weak = Candidate("GBPUSD", "fx_major", 95.0, correlations={"EURUSD": 0.4})
    assert select_one([weak], state, POLICY).selected is not None


def test_selection_is_deterministic_on_ties() -> None:
    """Gleicher Score: der Instrumentenname entscheidet. Ein Backtest bleibt reproduzierbar."""
    candidates = [
        Candidate("GBPUSD", "fx_major", 90.0),
        Candidate("EURUSD", "fx_major", 90.0),
    ]
    first = select_one(candidates, GateState(now=NOW), POLICY)
    second = select_one(list(reversed(candidates)), GateState(now=NOW), POLICY)
    assert first.selected is not None and second.selected is not None
    assert first.selected.instrument == second.selected.instrument == "EURUSD"


def test_trade_rate_is_measured_not_estimated() -> None:
    candidates = [Candidate(f"SYM{i}", "fx_major", 90.0) for i in range(10)]
    result = select_one(candidates, GateState(now=NOW), POLICY)
    assert trade_rate(result.decisions) == 0.1

    none_eligible = select_one(
        [Candidate("SYM", "fx_major", 10.0)], GateState(now=NOW), POLICY
    )
    assert trade_rate(none_eligible.decisions) == 0.0


def test_every_candidate_is_accounted_for() -> None:
    """Keine Bewertung verschwindet. Auch die unterdrueckten werden persistiert."""
    candidates = [
        Candidate("EURUSD", "fx_major", 95.0),
        Candidate("GBPUSD", "fx_major", 90.0),
        Candidate("USDJPY", "fx_major", 10.0),
    ]
    result = select_one(candidates, GateState(now=NOW), POLICY)
    assert len(result.decisions) == len(candidates)
    assert {d.instrument for d in result.decisions} == {
        c.instrument for c in candidates
    }

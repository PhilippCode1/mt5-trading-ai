"""Nachrechnung der Backtest-Maschine: Fill-Preis, Kosten je Trade, Purge-Beispiel,
Naechte am FX-Rollover, Konto-Ruin, Equity-Definition."""
import sys
sys.path.insert(0, "/root/mt5-trading-ai")
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from mt5_trading_ai.backtest.engine import (
    MarketSpec, Signal, run_backtest, _bar_ranges, random_signal_strategy,
)
from mt5_trading_ai.backtest.splits import purged_walk_forward_indices, Range, _overlaps, _band_for_purge_and_embargo
from mt5_trading_ai.data.quality import BarRow
from mt5_trading_ai.costs.model import load_cost_fees

fees = load_cost_fees("EURUSD")
spec = MarketSpec(symbol="EURUSD", contract_size=Decimal("100000"), pip_size=Decimal("0.0001"),
                  quote_currency="USD", fees=fees, spread_pips=Decimal("0.1"),
                  leverage=Decimal("5"), obs_per_year=6254.0)
print("FeeSchedule EURUSD:", fees)

def bar(ts, o, h, l, c):
    return BarRow(ts=ts, open=o, high=h, low=l, close=c, volume=1.0)

# ---------------------------------------------------------------- (A) Fill-Preis
print("\n(A) FILL-PREIS: Signal auf Bar i -> welcher Preis?")
t0 = datetime(2024, 3, 4, 10, 0, tzinfo=UTC)  # Montag
bars = [
    bar(t0,                     1.1000, 1.1010, 1.0990, 1.1000),   # i=0
    bar(t0 + timedelta(hours=1), 1.1050, 1.1060, 1.1040, 1.1050),  # i=1 (Open 50 Pips ueber Close_0!)
    bar(t0 + timedelta(hours=2), 1.1050, 1.1100, 1.1040, 1.1100),  # i=2
    bar(t0 + timedelta(hours=3), 1.1100, 1.1110, 1.1090, 1.1100),  # i=3
]
# Strategie: LONG genau am Bar 0 (entscheidet mit Close_0), sonst FLAT
r = run_backtest(bars, lambda v: Signal.LONG if v.index == 0 else Signal.FLAT, spec,
                 strategy_id="fill", seed=0, data_checksum="", code_commit="x")
t = r.trade_log[0]
print(f"   entry_ts={t.entry_ts} exit_ts={t.exit_ts} gross={t.gross:.2f} USD")
print(f"   -> gross = (Close_1 - Close_0) * 100000 = ({bars[1].close}-{bars[0].close})*1e5 = {(bars[1].close-bars[0].close)*1e5:.2f}")
print(f"   Der Trade wird zum CLOSE des Signalbars gefuellt (1.1000), nicht zum OPEN des Folgebars (1.1050).")
print(f"   Waere Fill am Open_{{i+1}}: gross = (Close_1-Open_1)*1e5 = {(bars[1].close-bars[1].open)*1e5:.2f} USD")

# ---------------------------------------------------------------- (B) Kosten je Trade (Hand)
print("\n(B) KOSTEN JE ROUNDTURN, 1 Lot, 0 Naechte (Handrechnung):")
spread = 0.1 * 0.0001 * 100000          # 1.00 USD
comm = 7.0
slip = 0.5 * 0.0001 * 100000 * 2         # 10.00 USD
print(f"   spread={spread:.2f} comm={comm:.2f} slippage={slip:.2f} -> total={spread+comm+slip:.2f} USD")
print(f"   engine: spread={r.cost_spread:.2f} comm={r.cost_commission:.2f} slip={r.cost_slippage:.2f} fin={r.cost_financing:.2f} carry={r.carry_income:.2f} -> trade.cost={t.cost:.2f}")
notional = 1.10 * 100000
print(f"   in bp des Nominals ({notional:.0f} USD): {(spread+comm+slip)/notional*1e4:.4f} bp  (Slippage-Anteil {slip/(spread+comm+slip)*100:.1f} %)")

# ---------------------------------------------------------------- (C) Equity/Return-Definition
print("\n(C) EQUITY-DEFINITION:")
eb = 100000 * 1 * bars[0].close / 5
print(f"   equity_base = cs*vol*Close_0/lev = {eb:.2f} USD (= Margin bei 5:1)")
print(f"   net_return = {r.net_return*100:.3f} %  = net {t.net:.2f} / {eb:.2f}  -> 50 Pips (0.45 % Preis) ergeben {t.gross/eb*100:.2f} % 'gross_return' (Hebel 5 eingerechnet)")
print(f"   hurdle_pct = {r.hurdle_pct*100:.4f} %  = Reibung {r.cost_spread+r.cost_commission+r.cost_slippage:.2f} / {eb:.2f}")
print(f"   net_over_hurdle = {r.net_over_hurdle*100:.4f} % = gross_return - hurdle = net_return - carry/eb")

# ---------------------------------------------------------------- (D) Naechte-Zaehlung am FX-Rollover
print("\n(D) NAECHTE: Kalendertag-Wechsel nach UTC vs. FX-Rollover 17:00 NY (=21/22 UTC):")
def nights_for(entry_hour_utc, hold_hours):
    t0 = datetime(2024, 3, 4, entry_hour_utc, 0, tzinfo=UTC)  # Montag
    bs = [bar(t0 + timedelta(hours=k), 1.1, 1.101, 1.099, 1.1) for k in range(hold_hours + 2)]
    rep = run_backtest(bs, lambda v: Signal.LONG if 0 <= v.index < hold_hours else Signal.FLAT, spec,
                       strategy_id="n", seed=0, data_checksum="", code_commit="x")
    return rep.trade_log[0].nights, rep.cost_financing, rep.carry_income
for eh, hh, real in [(19, 2, "kreuzt 21/22 UTC -> real 1 Nacht"), (22, 3, "kreuzt UTC-Mitternacht, NICHT den 22-UTC-Rollover -> real 0 Naechte"), (23, 1, "Entscheidungsbar 23:00, Fill um 00:00 -> real 0 Naechte")]:
    n, fin, carry = nights_for(eh, hh)
    print(f"   Einstieg {eh:02d}:00 UTC, {hh} h gehalten: engine nights={n} fin={fin:.2f} USD | {real}")

# ---------------------------------------------------------------- (E) Purge-Beispiel mit Zahlen
print("\n(E) PURGE/EMBARGO auf H1-Bars, purge=embargo=3_600_000 ms (wie edge_test.py):")
t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
hb = [bar(t0 + timedelta(hours=k), 1.1, 1.101, 1.099, 1.1) for k in range(20)]
ranges = _bar_ranges(hb)
print("   Bar-Ranges (ms/3.6e6 = Stunde):", [(int(r.start/3.6e6 - ranges[0].start/3.6e6), int(r.end/3.6e6 - ranges[0].start/3.6e6)) for r in ranges[:4]], "...")
folds = purged_walk_forward_indices(ranges, 2, purge_ms=3_600_000, embargo_ms=3_600_000, exclude_prior_test=False)
for fi, (train, test) in enumerate(folds):
    t0i, t1i = min(ranges[j].start for j in test), max(ranges[j].end for j in test)
    band = _band_for_purge_and_embargo(t0i, t1i, purge_ms=3_600_000, embargo_ms=3_600_000)
    base = ranges[0].start
    print(f"   Fold {fi}: test={test[0]}..{test[-1]}  Band=[{(band.start-base)/3.6e6:.0f}h,{(band.end-base)/3.6e6:.0f}h]  train={train[:3]}..{train[-3:] if train else []}  (n_train={len(train)})")
    if train:
        purged = [j for j in range(test[0]) if j not in train]
        print(f"           gepurgte Trainingsbars: {purged}  -> Bar {test[0]-1} hat Range [{test[0]-1}h,{test[0]}h), Band beginnt bei {(band.start-base)/3.6e6:.0f}h -> ueberlappt; Bar {test[0]-2} endet bei {test[0]-1}h = Bandanfang -> _overlaps False (a.end <= b.start)")
print("   => purge=1h entfernt auf luekenlosen H1-Bars genau EINEN Bar. Eine Strategie mit 120-Bar-Lookback und tagelanger Haltedauer")
print("      haette Labels, die weit in den Testblock reichen -- 1 Bar Purge deckt das nicht (moot, solange der Fitter ein No-op ist).")

# ---------------------------------------------------------------- (F) Konto-Ruin
print("\n(F) KONTO-RUIN: Equity kann negativ werden, der Lauf laeuft weiter:")
import random
rng = random.Random(3)
price = 1.10; cur = datetime(2022, 1, 3, tzinfo=UTC); rb = []
while len(rb) < 3000:
    if cur.weekday() < 5:
        c = price * (1 + rng.gauss(0, 0.006)); rb.append(bar(cur, price, max(price, c)*1.001, min(price, c)*0.999, c)); price = c
    cur += timedelta(hours=1)
rr = run_backtest(rb, random_signal_strategy(7), spec, strategy_id="ruin", seed=7, data_checksum="", code_commit="x")
eq = [eb]
print(f"   net_return={rr.net_return*100:.1f} %  max_drawdown={rr.max_drawdown*100:.1f} %  trades={rr.trades}")
print(f"   -> ein net_return < -100 % heisst: Margin mehr als einmal verloren; kein Margin-Call, keine Stop-Out-Logik im Backtest.")
print(f"   (Zum Vergleich Beleg 05-laeufe: Zufalls-Referenz Mittel -218.3 % -- dieselbe Groessenordnung.)")

# ---------------------------------------------------------------- (G) O(n^2)-Kopie in MarketView
print("\n(G) MarketView kopiert je Bar die gesamte Vergangenheit (tuple(bars[:i+1])):")
n = 18715
print(f"   fuer n={n}: Summe der Kopien = n(n+1)/2 = {n*(n+1)//2:,} Elementreferenzen je Backtest-Lauf")

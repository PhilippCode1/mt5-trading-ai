"""Trennschaerfe des Sechs-Bedingungen-Tors: Monte-Carlo unter der ALTERNATIVE
(die Strategie HAT einen echten Vorteil). Frage: wie oft besteht sie Bedingung 1+2+3?"""
import sys, math, random
sys.path.insert(0, "/root/mt5-trading-ai")
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio
from mt5_trading_ai.backtest.edge import EdgeThresholds
from mt5_trading_ai.backtest.resolution import required_sharpe

th = EdgeThresholds()
OOS_YEARS = 0.899   # aus Beleg 07
N_TRIALS = 60

print("1) Noetige Sharpe je Trade fuer DSR>0.95 bei N=60, je nach OoS-Trade-Zahl T (Bisektion auf criteria.deflated_sharpe_ratio):")
for T in [58, 59, 123, 250, 500, 1000, 2000, 5000]:
    try:
        s = required_sharpe(T, N_TRIALS, threshold=th.min_deflated_sharpe)
        ann = s * math.sqrt(T / OOS_YEARS)
        print(f"   T={T:5d}: SR/Trade >= {s:.4f}  -> annualisiert (sqrt(T/0.899 a)) {ann:6.2f}   | Bedingung 1 verlangt annualisiert {th.min_oos_sharpe} = SR/Trade {th.min_oos_sharpe/math.sqrt(T/OOS_YEARS):.4f}")
    except Exception as e:
        print(f"   T={T}: {e}")

print("\n2) Standardfehler der Sharpe-Schaetzung je Trade ~ 1/sqrt(T) (Lo 2002, SR~0):")
for T in [59, 123, 2000]:
    print(f"   T={T:5d}: SE(SR/Trade) ~ {1/math.sqrt(T):.4f}  -> annualisiert {math.sqrt(1/OOS_YEARS):.2f}  (unabhaengig von T!)")
print("   => Die annualisierte Trade-Sharpe hat auf 0,9 Jahren OoS IMMER einen Standardfehler von ~1,05, egal wie viele Trades.")

print("\n3) Monte-Carlo: wahre annualisierte Sharpe S_true, T Trades i.i.d. normal, 20.000 Wiederholungen.")
print("   Anteil, der Bedingung 1 (Trade-Sharpe>=1.0), Bedingung 2 (DSR>0.95, N=60) und beide besteht:")
rng = random.Random(20260902)
def sim(S_true, T, reps=20000):
    mu = S_true / math.sqrt(T / OOS_YEARS)   # SR je Trade
    c1 = c2 = both = 0
    for _ in range(reps):
        xs = [rng.gauss(mu, 1.0) for _ in range(T)]
        m = sum(xs) / T
        v = sum((x - m) ** 2 for x in xs) / T
        sr = m / math.sqrt(v)
        ann = sr * math.sqrt(T / OOS_YEARS)
        dsr = deflated_sharpe_ratio(observed_sharpe=sr, observations=T, trials=N_TRIALS)
        a = ann >= th.min_oos_sharpe; b = dsr > th.min_deflated_sharpe
        c1 += a; c2 += b; both += (a and b)
    return c1 / reps, c2 / reps, both / reps
for S_true in [0.0, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]:
    for T in [123, 2000]:
        p1, p2, pb = sim(S_true, T, reps=4000)
        print(f"   S_true={S_true:.1f} T={T:5d}: P(Bed.1)={p1:5.1%}  P(Bed.2)={p2:5.1%}  P(beide)={pb:5.1%}" + ("   <- Bedingung 3 (>=2000) zusaetzlich verfehlt" if T < th.min_trades else ""))

print("\n4) Fehler 1. Art unter der NULL (S_true=0): P(Bed.1 und Bed.2) bei T=2000:")
p1, p2, pb = sim(0.0, 2000, reps=4000)
print(f"   P(Bed.1)={p1:.2%} P(Bed.2)={p2:.2%} P(beide)={pb:.2%}  (Bed.2 allein ist bereits ein 5-%-Test gegen N=60 Versuche)")

print("\n5) Was 'Trade-Sharpe 0,185' der Mittelwertrueckkehr (T=123) als Konfidenzintervall heisst (Lo 2002, i.i.d.):")
sr_t = 0.185 / math.sqrt(123 / OOS_YEARS)
se = math.sqrt((1 + 0.5 * sr_t ** 2) / 123)
lo, hi = (sr_t - 1.96 * se) * math.sqrt(123 / OOS_YEARS), (sr_t + 1.96 * se) * math.sqrt(123 / OOS_YEARS)
print(f"   SR/Trade={sr_t:.4f} SE={se:.4f} -> 95%-KI annualisiert [{lo:.2f}, {hi:.2f}]  (enthaelt 0 UND 1,0)")

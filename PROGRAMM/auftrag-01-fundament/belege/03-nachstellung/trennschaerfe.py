# Abgeleitet aus PROGRAMM/eingang/pruef_ausgaben/trennschaerfe.py (Bewertung 2026-09-02). Aenderung: REPO zeigt auf den
# Worktree C:/Users/<konto>/nachstellung-306bbaa (Stand 306bbaa); Ausfuehrung 2026-09-03 unter Windows/Python 3.11.7.
"""Unabhängige Trennschärfe-Messung des Sechs-Bedingungen-Tors mit den Funktionen des Repos.
Annahme: i.i.d. normale Trade-Renditen, T Trades in 0,9 Jahren OoS, N=60 Versuche (Repo-Kampagne),
Bedingung 1: annualisierte Trade-Sharpe >= 1,0; Bedingung 2: DSR > 0,95 (Repo-Funktion, Standardvarianz)."""
import random, math, statistics
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio, annualise_sharpe
random.seed(20260902)
OOS_JAHRE = 0.9; N_TRIALS = 60; REPS = 3000
def lauf(true_ann_sharpe, T):
    tpj = T / OOS_JAHRE
    mu = true_ann_sharpe / math.sqrt(tpj)   # Sharpe je Trade bei sigma=1
    b1 = b2 = beide = 0
    for _ in range(REPS):
        r = [random.gauss(mu, 1.0) for _ in range(T)]
        m = statistics.fmean(r); s = statistics.stdev(r)
        sr = m / s
        ann = annualise_sharpe(sr, tpj)
        dsr = deflated_sharpe_ratio(observed_sharpe=sr, observations=T, trials=N_TRIALS)
        c1 = ann >= 1.0; c2 = dsr > 0.95
        b1 += c1; b2 += c2; beide += (c1 and c2)
    return b1/REPS, b2/REPS, beide/REPS
# nötige SR je Trade für DSR>0.95 (bisection), T=2000
def noetig(T):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo+hi)/2
        if deflated_sharpe_ratio(observed_sharpe=mid, observations=T, trials=N_TRIALS) > 0.95: hi = mid
        else: lo = mid
    return hi
for T in (59, 123, 2000):
    sr = noetig(T); print(f"T={T:5d}: noetige Sharpe je Trade fuer DSR>0,95 bei N=60: {sr:.4f}  = annualisiert {annualise_sharpe(sr, T/OOS_JAHRE):.2f}")
print(f"\nPasswahrscheinlichkeit (Monte-Carlo, {REPS} Wiederholungen je Zeile, T=2000 Trades, 0,9 Jahre OoS, N=60):")
print("wahre ann. Sharpe | P(Bed.1: ann>=1,0) | P(Bed.2: DSR>0,95) | P(beide)")
for S in (0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0):
    p1, p2, pb = lauf(S, 2000)
    print(f"{S:17.1f} | {p1:18.1%} | {p2:18.1%} | {pb:8.1%}")

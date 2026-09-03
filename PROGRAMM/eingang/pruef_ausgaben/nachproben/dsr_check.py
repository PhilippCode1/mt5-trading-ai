"""Unabhaengige Nachrechnung der DSR-Formeln aus gates/criteria.py gegen
Bailey & Lopez de Prado (2014) mit scipy.stats.norm (nicht Acklam)."""
import sys, math
sys.path.insert(0, "/root/mt5-trading-ai")
from scipy.stats import norm
from mt5_trading_ai.gates.criteria import (
    deflated_sharpe_ratio, expected_max_sharpe, _norm_ppf, _norm_cdf, annualise_sharpe,
    percentile_against_random,
)

GAMMA = 0.5772156649015329

def lit_expected_max(N, var):
    if N == 1:
        return 0.0
    return math.sqrt(var) * ((1 - GAMMA) * norm.ppf(1 - 1 / N) + GAMMA * norm.ppf(1 - 1 / (N * math.e)))

def lit_psr(sr, sr0, T, g3=0.0, g4=3.0):
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    return norm.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom))

def lit_dsr(sr, T, N, g3=0.0, g4=3.0, var=None):
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    if var is None:
        var = denom / (T - 1)          # Repo-Voreinstellung nachgebaut
    return lit_psr(sr, lit_expected_max(N, var), T, g3, g4)

print("1) Acklam-Inverse vs scipy.norm.ppf (max. abs. Fehler):")
worst = 0.0
for p in [1e-6, 0.001, 0.02, 0.0243, 0.1, 0.5, 0.9, 0.975, 0.99, 0.999, 1 - 1e-6]:
    worst = max(worst, abs(_norm_ppf(p) - norm.ppf(p)))
print(f"   {worst:.3e}")
print("   erf-CDF vs scipy:", max(abs(_norm_cdf(x) - norm.cdf(x)) for x in [-4, -1, 0, 0.5, 1.645, 3]))

print("\n2) expected_max_sharpe(N, var) vs Literaturformel:")
for N, var in [(2, 0.01), (10, 1.0), (60, 1.0), (60, 1/1999), (1000, 0.001)]:
    a = expected_max_sharpe(N, var); b = lit_expected_max(N, var)
    print(f"   N={N:5d} var={var:.5f}: repo={a:.6f} lit={b:.6f} diff={a-b:+.2e}")

print("\n3) DSR (Voreinstellung sharpe_variance=denom/(T-1)) vs Literatur mit derselben Varianz:")
cases = [(0.067, 500, 1000), (1.0636, 500, 1000), (0.2759, 64, 8), (0.0167, 123, 60), (0.0894, 2000, 60), (0.12675, 1000, 60)]
for sr, T, N in cases:
    a = deflated_sharpe_ratio(observed_sharpe=sr, observations=T, trials=N)
    b = lit_dsr(sr, T, N)
    print(f"   SR={sr:.4f} T={T:5d} N={N:4d}: repo={a:.6f} lit={b:.6f} diff={a-b:+.2e}")

print("\n4) ABBRUCH.md-Tabelle (T=1000): sr0 in Standardeinheiten und noetige SR je Beobachtung fuer DSR=0.95")
for N in [1, 10, 30, 60, 100, 200]:
    sr0_unit = expected_max_sharpe(N, 1.0) if N > 1 else 0.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if deflated_sharpe_ratio(observed_sharpe=mid, observations=1000, trials=N) >= 0.95:
            hi = mid
        else:
            lo = mid
    print(f"   N={N:4d}: sr0(unit)={sr0_unit:.4f}  SR*={hi:.5f}  x sqrt(252)={hi*math.sqrt(252):.2f}")

print("\n5) Was die Varianz ueber die Versuche tut (Beispiel aus dem Docstring, SR=0.2759, T=64, N=8):")
for var in [None, 0.25]:
    print(f"   var={var}: repo={deflated_sharpe_ratio(observed_sharpe=0.2759, observations=64, trials=8, sharpe_variance=var):.4f}")

print("\n6) Sensitivitaet gegen Schiefe/Kurtosis (Trade-Renditen sind nicht normal):")
for g3, g4 in [(0, 3), (-0.5, 3), (-1.0, 5), (0.5, 5), (-1.0, 8)]:
    v = deflated_sharpe_ratio(observed_sharpe=0.0894, observations=2000, trials=60, skewness=g3, kurtosis=g4)
    print(f"   g3={g3:+.1f} g4={g4}: DSR={v:.4f}")

print("\n7) Kleinstes N, bei dem sr0 (Deflation) ueberhaupt >0 ist, und was N=1 bedeutet:")
print("   N=1 -> sr0 =", expected_max_sharpe(1, 0.5), " (keine Deflation, PSR pur)")

print("\n8) annualise_sharpe und percentile_against_random:")
print("   annualise(0.0167, 123/0.899) =", annualise_sharpe(0.0167, 123 / 0.899))
print("   percentile(0.0322, [-2.18]*5) =", percentile_against_random(0.0322, [-2.18] * 5), "(Anteil 'schlechter', strikt <)")
print("   percentile(0.5, [0.5,0.5,0.5]) =", percentile_against_random(0.5, [0.5, 0.5, 0.5]), "(Gleichstand zaehlt als nicht schlechter)")

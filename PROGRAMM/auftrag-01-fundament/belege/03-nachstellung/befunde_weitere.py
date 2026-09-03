"""Nachstellung weiterer Befunde der Bewertung gegen den Stand 306bbaa (Worktree).

Eigenes Skript (2026-09-03). Gegenstand: D8 (Persistenz per Vorgabe fluechtig),
Z (Zulassung als Kommandozeilenargument), D13/D20 (Serverzone fest, keine Gap-Sperre),
T (Selbstueberspringer, Windows-Pfad-Test, Umgebungsvariablen), Doku-Widersprueche
(Stichprobe). Nur lesend; schreibt nichts in den Worktree.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

REPO = Path(r"C:/Users/Acer/nachstellung-306bbaa")
sys.path.insert(0, str(REPO))
for k in ("MT5_RISIKO_ZUSTAND", "MT5_RISIKO_ZUSTAND_ORDNER", "MT5_SCHWEBENDE_AUFTRAEGE"):
    os.environ.pop(k, None)


def kopf(t: str) -> None:
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def grep(rel: str, muster: str, flags: int = 0) -> list[tuple[int, str]]:
    text = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    rx = re.compile(muster, flags)
    return [(i + 1, z.rstrip()) for i, z in enumerate(text) if rx.search(z)]


# ---------------------------------------------------------------------------
kopf("D8  Persistenz per Vorgabe fluechtig (Umgebung leer, wie ein frischer Betriebsstart)")
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.venue.mt5 import _schwebeakte_waehlen  # noqa: E402

rm = RiskManager()
print("RiskManager().zustand_dauerhaft =", rm.zustand_dauerhaft)
akte = _schwebeakte_waehlen()
print("_schwebeakte_waehlen().dauerhaft =", akte.dauerhaft, "| pfad =", akte.pfad)
print("tools/live_betrieb.py baut den RiskManager so:")
for nr, z in grep("tools/live_betrieb.py", r"RiskManager\("):
    print(f"  live_betrieb.py:{nr}: {z.strip()}")
env_reads = []
for rel in sorted(p.relative_to(REPO).as_posix() for p in (REPO / "mt5_trading_ai").rglob("*.py")):
    env_reads += [(rel, nr, z.strip()) for nr, z in grep(rel, r"os\.environ|os\.getenv")]
print(f"Lesestellen von os.environ im Paket: {len(env_reads)}")
for rel, nr, z in env_reads:
    print(f"  {rel}:{nr}: {z[:90]}")
env_doku = (REPO / ".env.example").read_text(encoding="utf-8")
print(".env.example sagt:", [z for z in env_doku.splitlines() if "liest" in z][0].strip())
md_env = 0
for p in REPO.rglob("*.md"):
    if ".git" in p.parts:
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    md_env += sum(1 for k in ("MT5_RISIKO_ZUSTAND", "MT5_SCHWEBENDE_AUFTRAEGE") if k in t)
print("Markdown-Dateien, die eine der drei Variablen nennen:", md_env)

# ---------------------------------------------------------------------------
kopf("Z   Zulassung ist ein Kommandozeilenargument (--scharf <Freitext>)")
for nr, z in grep("tools/live_betrieb.py", r"--scharf|args\.scharf"):
    print(f"  live_betrieb.py:{nr}: {z.strip()[:100]}")
print("bool('Maschinenprobe') =", bool("Maschinenprobe"), "-> passed=True ohne Torurteil")
from mt5_trading_ai.gates.criteria import CriteriaVerdict  # noqa: E402

v = CriteriaVerdict(passed=bool("irgendein Text"), results=())
print("CriteriaVerdict(passed=bool(args.scharf), results=()).passed =", v.passed)
print("Konstruktionsstellen mit settings= (Live-Freigabe) in Paket+tools:", end=" ")
n = 0
for d in ("mt5_trading_ai", "tools"):
    for p in (REPO / d).rglob("*.py"):
        n += len(re.findall(r"settings\s*=", p.read_text(encoding="utf-8", errors="replace")))
print(n, "(Zuweisung self._settings = settings im Venue mitgezaehlt)")

# ---------------------------------------------------------------------------
kopf("D13/D20  Serverzone fest 'Europe/Helsinki'; Sommerzeit-Versatz; keine Gap-Sperre")
for nr, z in grep("mt5_trading_ai/backtest/kalender.py", r"SERVER_TZ"):
    print(f"  kalender.py:{nr}: {z.strip()[:90]}")
eu, us = ZoneInfo("Europe/Helsinki"), ZoneInfo("America/New_York")
tage = 0
jahr = 2026
d = date(jahr, 1, 1)
while d.year == jahr:
    t = datetime(d.year, d.month, d.day, 12)
    if (t.replace(tzinfo=eu).utcoffset() - timedelta(hours=7)) != t.replace(
        tzinfo=us
    ).utcoffset():
        tage += 1
    d += timedelta(days=1)
print(f"Tage im Jahr {jahr}, an denen EU- und US-Sommerzeitregel nicht deckungsgleich sind: {tage}")
for nr, z in grep("mt5_trading_ai/execution/freshness.py", r"MAX_SNAPSHOT_AGE\s*=|FUTURE_TOLERANCE\s*="):
    print(f"  freshness.py:{nr}: {z.strip()}")
print("  -> ein Stundenversatz (3600 s) > MAX_SNAPSHOT_AGE: jeder Schnappschuss gilt als veraltet")
for nr, z in grep("mt5_trading_ai/execution/risk_manager.py", r"gap_events"):
    print(f"  risk_manager.py:{nr}: {z.strip()[:90]}")
    break
treffer = grep("tools/live_betrieb.py", r"gap_events|wochenend|freitag", re.I)
print(f"  live_betrieb.py nennt gap_events/Wochenende/Freitag: {len(treffer)} Zeilen")

# ---------------------------------------------------------------------------
kopf("T   Selbstueberspringer und Windows-Pfad-Test")
skips = []
for p in sorted((REPO / "tests").glob("*.py")):
    skips += [(p.name, nr, z.strip()) for nr, z in grep(f"tests/{p.name}", r"pytest\.skip\(")]
print(f"pytest.skip(-Stellen in tests/: {len(skips)}")
journal = [s for s in skips if "betrieb" in s[2].lower() or "journal" in s[2].lower()]
print(f"  davon mit Bezug auf betrieb/ oder Journale: {len(journal)}")
for name, nr, z in skips:
    print(f"  {name}:{nr}: {z[:80]}")
print("betrieb/ in .gitignore:", any(z.strip() == "/betrieb/" for z in (REPO / ".gitignore").read_text().splitlines()))
print("betrieb/ im Worktree vorhanden:", (REPO / "betrieb").is_dir())
print()
print("Windows-Pfad-Test (tests/test_risiko_zustand.py): Mechanik des Fehlschlags unter POSIX")
lokal = r"C:\Users\Test\AppData\Local"
print(f"  Path({lokal!r}).is_absolute() unter Windows:", Path(lokal).is_absolute())
print(f"  PurePosixPath({lokal!r}).is_absolute() (Linux-Sicht):", PurePosixPath(lokal).is_absolute())
for nr, z in grep("mt5_trading_ai/execution/risiko_zustand.py", r"is_absolute\(\)"):
    print(f"  risiko_zustand.py:{nr}: {z.strip()[:90]}")
print("  -> unter Linux faellt LOCALAPPDATA durch is_absolute() und der Fallback ~/.local/state greift")

# ---------------------------------------------------------------------------
kopf("Doku-Widersprueche (Stichprobe aus Bewertung 6.2)")
fehlt = grep("FEHLT.md", r"[Bb]acktest|[Ss]trategie")
print(f"FEHLT.md nennt Backtest/Strategie in {len(fehlt)} Zeilen, z. B.:")
for nr, z in fehlt[:3]:
    print(f"  FEHLT.md:{nr}: {z[:100]}")
print("  mt5_trading_ai/backtest/engine.py existiert:", (REPO / "mt5_trading_ai/backtest/engine.py").is_file(),
      "| strategies.py:", (REPO / "mt5_trading_ai/backtest/strategies.py").is_file())
readme447 = grep("README.md", r"mt5\.py:447")
print(f"README.md verweist auf venue/mt5.py:447 in {len(readme447)} Zeile(n)")
z447 = (REPO / "mt5_trading_ai/venue/mt5.py").read_text(encoding="utf-8").splitlines()
print("  mt5.py:447 ist:", z447[446].strip()[:80])
aufruf = [i + 1 for i, z in enumerate(z447) if "_require_live_release_for_opening()" in z]
print("  Aufruf der Live-Freigabe steht in Zeile(n):", aufruf)
stand = 0
for p in REPO.rglob("*.md"):
    if ".git" in p.parts:
        continue
    kopfzeilen = p.read_text(encoding="utf-8", errors="replace").splitlines()[:12]
    if any(re.search(r"\bStand\b", z) for z in kopfzeilen):
        stand += 1
print("Markdown-Dateien mit 'Stand' in den ersten 12 Zeilen:", stand)
md = [p for p in REPO.rglob("*.md") if ".git" not in p.parts]
print("Markdown-Dateien gesamt:", len(md), "| Woerter:", sum(len(p.read_text(encoding='utf-8', errors='replace').split()) for p in md))

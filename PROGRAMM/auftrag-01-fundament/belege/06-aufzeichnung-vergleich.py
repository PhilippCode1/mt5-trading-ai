#!/usr/bin/env python3
"""T6, Familie Aufzeichnung: dieselben Zahlen aus betrieb/ und aus der Aufzeichnung?

Misst die vier Metriken (mt5_trading_ai/betrieb/dienstguete.py), die Aufschluesselung
nach Codestand, die Zahlen der Dauertore (tests/test_laufabschluss.py,
test_buchtreue.py, test_ausstiegsdeckung.py, test_journal_leser.py) und die
Trade-Zaehlung des Journal-Lesers -- einmal auf den Originaljournalen, einmal auf der
redigierten Aufzeichnung -- und sagt je Zahl, ob beide gleich sind.

Aufruf (Pfade absolut; die Journale liegen nur auf diesem Rechner)::

    python PROGRAMM/auftrag-01-fundament/belege/06-aufzeichnung-vergleich.py \
        --betrieb C:/Users/<konto>/mt5_trading_ai/betrieb \
        --aufzeichnung aufzeichnungen/demo-2026-08-17.jsonl

Gibt KEINE Werte aus den Journalen aus, nur Zaehlungen und Anteile; Pfade werden mit
<konto> redigiert.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from mt5_trading_ai.betrieb.dienstguete import (  # noqa: E402
    METRIKEN,
    ausstiegsdeckung,
    laufabschluss,
    nach_codestand,
)
from mt5_trading_ai.betrieb.journal import lies_alle  # noqa: E402

KONTO = getpass.getuser()


def redigiert(text: str) -> str:
    return text.replace(KONTO, "<konto>")


def _saetze_betrieb(ordner: Path) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    alle: list[dict[str, Any]] = []
    je: dict[str, list[dict[str, Any]]] = {}
    for datei in sorted(ordner.glob("journal-*.jsonl")):
        saetze = [json.loads(z) for z in datei.read_text(encoding="utf-8").splitlines() if z.strip()]
        je[datei.name] = saetze
        alle.extend(saetze)
    return alle, je


def _saetze_aufzeichnung(datei: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    zeilen = [json.loads(z) for z in datei.read_text(encoding="utf-8").splitlines() if z.strip()]
    kopf, rest = zeilen[0], zeilen[1:]
    assert kopf["art"] == "_kopf"
    je: dict[str, list[dict[str, Any]]] = {}
    for s in rest:
        je.setdefault(s["lauf"], []).append(s)
    return kopf, rest, je


def messwerte(saetze: list[dict[str, Any]]) -> dict[str, tuple[int, int, int]]:
    return {name: (m.gelungen, m.gesamt, m.unbeurteilbar) for name, m in ((n, fn(saetze)) for n, fn in METRIKEN.items())}


def dauertore(je: dict[str, list[dict[str, Any]]], namen: dict[str, str]) -> dict[str, Any]:
    """Die Zahlen, die die vier Testdateien pruefen -- je Lauf, ueber Kennung/Name."""
    aus: dict[str, Any] = {}
    for kurz, schluessel in namen.items():
        saetze = je[schluessel]
        ende = next((s for s in saetze if s.get("art") == "ende"), None)
        letzter_takt = next((s for s in reversed(saetze) if s.get("art") == "takt" and "positionen" in s), None)
        aus[kurz] = {
            "saetze": len(saetze),
            "hat_ende": ende is not None,
            "offen_geblieben": len(ende["offen_geblieben"]) if ende and ende.get("offen_geblieben") else 0,
            "laufabschluss": laufabschluss(saetze).anteil,
            "ausstiegsdeckung": ausstiegsdeckung(saetze).anteil,
            "letzter_takt_positionen": None if letzter_takt is None else len(letzter_takt["positionen"] or []),
        }
    mit_stoppdatei = sorted(k for k, s in je.items() if any(x.get("art") == "stoppdatei" for x in s))
    ohne_ende = sorted(k for k, s in je.items() if any(x.get("art") == "start" for x in s) and not any(x.get("art") == "ende" for x in s))
    aus["stoppdatei_laeufe"] = len(mit_stoppdatei)
    aus["stoppdatei_laeufe_mit_ende"] = sum(1 for k in mit_stoppdatei if any(x.get("art") == "ende" for x in je[k]))
    aus["laeufe_ohne_ende"] = len(ohne_ende)
    aus["laeufe_ohne_ende_mit_stoppdatei"] = sum(1 for k in ohne_ende if any(x.get("art") == "stoppdatei" for x in je[k]))
    gelaufen = {}
    for k in ohne_ende:
        s = je[k]
        start = next(x for x in s if x.get("art") == "start")
        t0 = datetime.fromisoformat(str(start["ts"]))
        t1 = datetime.fromisoformat(str(s[-1]["ts"]))
        gelaufen[k] = (round((t1 - t0).total_seconds() / 3600, 4), float(start["dauer_stunden"]))
    aus["ohne_ende_gelaufen_h_vs_geplant_h"] = gelaufen
    return aus


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--betrieb", type=Path, required=True)
    ap.add_argument("--aufzeichnung", type=Path, required=True)
    args = ap.parse_args()

    alle_b, je_b = _saetze_betrieb(args.betrieb)
    kopf, alle_a, je_a = _saetze_aufzeichnung(args.aufzeichnung)
    namen_b = {n: n for n in je_b}
    kennung_je_name = {name: kennung for kennung, name in kopf["laeufe"].items()}
    namen_a = {n: kennung_je_name[n] for n in je_b}

    print("# T6 Familie Aufzeichnung: dieselben Zahlen aus den Originaljournalen (nur gelesen) und aus der eingecheckten Aufzeichnung (Kopf-Fassung 2)")
    print(redigiert(f"# Befehl: python PROGRAMM/auftrag-01-fundament/belege/06-aufzeichnung-vergleich.py --betrieb {args.betrieb} --aufzeichnung {args.aufzeichnung}"))
    print("# Windows, Python 3.11.7, 2026-09-03. Metriken: mt5_trading_ai/betrieb/dienstguete.py; Leser: mt5_trading_ai/betrieb/journal.py")
    print(redigiert(f"betrieb      : {args.betrieb}  ({len(je_b)} Journale, {len(alle_b)} Saetze)"))
    print(redigiert(f"aufzeichnung : {args.aufzeichnung}  ({len(je_a)} Laeufe, {len(alle_a)} Saetze; Kopf: behalten {kopf['behalten_gesamt']}, weggelassen {kopf['weggelassen_gesamt']})"))
    print()
    gleich = 0
    ungleich = 0

    def zeile(name: str, b: Any, a: Any) -> None:
        nonlocal gleich, ungleich
        ok = b == a
        gleich += ok
        ungleich += not ok
        print(f"  {'gleich' if ok else 'UNGLEICH':<9} {name:<52} betrieb={b!r}  aufzeichnung={a!r}")

    def info(name: str, b: Any, a: Any) -> None:
        print(f"  {'(info)':<9} {name:<52} betrieb={b!r}  aufzeichnung={a!r}")

    print("Metriken (gelungen, gesamt, unbeurteilbar):")
    mb, ma = messwerte(alle_b), messwerte(alle_a)
    for name in METRIKEN:
        zeile(name, mb[name], ma[name])
    for name in METRIKEN:
        b, a = mb[name], ma[name]
        zeile(f"{name} Anteil", None if not b[1] else round(b[0] / b[1], 6), None if not a[1] else round(a[0] / a[1], 6))
    print()
    print("Nach Codestand (buchtreue gelungen/gesamt je Stand):")
    sb = {k: (v["buchtreue"].gelungen, v["buchtreue"].gesamt) for k, v in nach_codestand([json.dumps(s) for s in alle_b]).items()}
    sa = {k: (v["buchtreue"].gelungen, v["buchtreue"].gesamt) for k, v in nach_codestand([json.dumps(s) for s in alle_a]).items()}
    zeile("Staende", sorted(sb), sorted(sa))
    for stand in sorted(sb):
        zeile(f"  {stand}", sb.get(stand), sa.get(stand))
    print()
    print("Dauertore je Lauf (test_laufabschluss.py):")
    db, da = dauertore(je_b, namen_b), dauertore(je_a, namen_a)
    for name in je_b:
        b, a = dict(db[name]), dict(da[name])
        info(f"{name} -> {kennung_je_name[name]} Saetze", b.pop("saetze"), a.pop("saetze"))
        zeile(f"{name} -> {kennung_je_name[name]}", b, a)
    for k in ("stoppdatei_laeufe", "stoppdatei_laeufe_mit_ende", "laeufe_ohne_ende", "laeufe_ohne_ende_mit_stoppdatei"):
        zeile(k, db[k], da[k])
    gb = {kennung_je_name[k]: v for k, v in db["ohne_ende_gelaufen_h_vs_geplant_h"].items()}
    ga = da["ohne_ende_gelaufen_h_vs_geplant_h"]
    for k in sorted(gb):
        zeile(f"ohne ende {k}: gelaufen h, geplant h", gb[k], ga.get(k))
    print("  (gelaufen = letzter Satz minus start; die Aufzeichnung laesst kurs/signal weg, der letzte Satz kann frueher liegen)")
    print()
    print("Journal-Leser (lies_alle):")
    lb, la = lies_alle(args.betrieb), lies_alle(args.aufzeichnung)
    zeile("Laeufe", len(lb), len(la))
    info("Saetze gesamt (kurs/signal weggelassen)", sum(len(lf.saetze) for lf in lb), sum(len(lf.saetze) for lf in la))
    zeile("Trades gesamt", sum(len(lf.trades()) for lf in lb), sum(len(lf.trades()) for lf in la))
    zeile("Trades geschlossen", sum(1 for lf in lb for t in lf.trades() if not t.offen), sum(1 for lf in la for t in lf.trades() if not t.offen))
    zeile("Equity-Punkte", sum(len(lf.equity_reihe()) for lf in lb), sum(len(lf.equity_reihe()) for lf in la))
    zeile("Laeufe beendet", sum(1 for lf in lb if lf.beendet), sum(1 for lf in la if lf.beendet))
    zeile("Laeufe scharf", sum(1 for lf in lb if lf.scharf), sum(1 for lf in la if lf.scharf))
    info("Kennungen der Aufzeichnung", None, [lf.lauf_id for lf in la])
    print()
    print(f"Vergleich: {gleich} Zahlen gleich, {ungleich} ungleich; (info)-Zeilen sind Auskuenfte ohne Gleichheitsforderung")
    return 0 if ungleich == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

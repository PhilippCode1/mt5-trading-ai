#!/usr/bin/env python3
"""Welches Tor hat je ausgeloest -- im Test und im Betrieb?

WARUM
-----
Stufe 9 des Auftrags::

    Ein Werkzeug, das Tore ohne Ausloesung im Betrieb meldet.
    Abnahme: fuer jedes verbliebene Tor existiert ein Test, der es ausloest, und eine
    Betriebszaehlung je Ablehnungsgrund.

§0 des Auftrags benennt die Krankheit dieses Vorhabens beim Namen: „Module ohne
Aufrufer, Gates ohne Ausloesung". Die erste Haelfte misst Stufe 8 (Importpfad vom
Diensteinstiegspunkt). Die zweite misst dieses Werkzeug: ein Tor, das im Code steht,
einen Aufrufer hat und trotzdem nie zugeschlagen hat, ist eine Behauptung.

ZWEI SPALTEN, DIE NICHT DASSELBE SAGEN
--------------------------------------
* **Test** -- hat irgendein Testfall diesen Grund je erzeugt? Fehlt er hier, ist das
  Tor **nirgends** nachgewiesen, und das ist ein Befund, den der Auftrag ausdruecklich
  verlangt („fuer jedes verbliebene Tor existiert ein Test, der es ausloest").
* **Betrieb** -- ist der Grund je in einem echten Journal aufgetaucht? Fehlt er hier,
  heisst das **nicht**, dass das Tor kaputt ist. Ein Not-Aus, der nie ausgeloest hat,
  ist ein gutes Zeichen. Die Spalte sagt nur: dieses Tor ist im Betrieb unerprobt.

Die beiden zu verwechseln waere der naheliegende Fehler. Ein fehlender Test ist ein
Mangel; ein fehlender Betriebsfall ist eine Auskunft.

WOHER DIE GRUENDE KOMMEN
------------------------
Aus dem Syntaxbaum, nicht aus einer gepflegten Liste: ``OrderRejectedError(...,
reason="x")`` im Paket und ``report._reject("naht", "x", ...)`` im Runner. Eine
gepflegte Liste haette dasselbe Problem wie jede zweite Wahrheit -- sie laeuft
auseinander, und zwar in die bequeme Richtung.

Aufruf::

    python tools/torzaehlung.py                 # Test + Betrieb, blockierend
    python tools/torzaehlung.py --journal betrieb/
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAKET = ROOT / "mt5_trading_ai"

#: Gruende, fuer die es keinen Testfall geben muss -- mit Begruendung, je einzeln.
#: Die Liste ist bewusst kurz und wird nicht zum Ablagefach: wer einen Grund hier
#: eintraegt, nimmt ihn aus der Nachweispflicht.
OHNE_TESTPFLICHT: dict[str, str] = {
    "session_not_connected": (
        "Setzt eine abgerissene MT5-Sitzung voraus; der Pruefstand faehrt ein "
        "Fake-Terminal, das immer verbunden ist. Nachweisbar nur am echten Terminal."
    ),
    # Ein Waechter, der hinter einem strengeren Pruefer sitzt, kann nicht ausloesen.
    # Er steht hier statt in einem erzwungenen Test, weil ein Test, der seinen Fall
    # nur mit Gewalt herstellt, nichts belegt. Zwei weitere standen hier bis zur
    # Gegenlese T10 (E15/E16): ``stop_price_nonpositive`` (unerreichbar, entfernt)
    # und ``margin_below_min_volume`` -- dessen Begruendung galt nur fuer Konten OHNE
    # gemeldeten Hebel; mit Hebel greift der Margendeckel des Runners vor dem
    # Preflight, und der Fall hat seit E15 einen eigenen Test
    # (``tests/test_orderpfad_zweige_e15.py``). Eine Freistellung, deren Klammer nur
    # fuer einen Teil der Konten gilt, ist keine.
    "risk_sizing_no_volume": (
        "Sitzt hinter der Risikoschicht: eine genehmigte Autorisierung traegt immer "
        "eine Groessenberechnung; ohne sie lehnt ``authorize_opening`` bereits ab. "
        "Der Zweig faengt einen Zustand, den der Aufrufer nicht herstellen kann."
    ),
}


#: Klassen, deren Ablehnungsgrund als **zweites Positionsargument** kommt. Ohne diese
#: Liste findet der Scanner sie nicht -- und genau so ist er beim ersten Lauf an
#: ``cost_unverifiable`` vorbeigelaufen, dem mit 2.258 Faellen haeufigsten Grund
#: ueberhaupt. Eine Pruefung, die ihren Gegenstand nur halb findet, meldet Vollzug.
GRUND_ALS_ZWEITES_ARGUMENT: frozenset[str] = frozenset({"CostGateDecision"})


def gruende_im_code() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """``(aufzaehlbare Gruende, zusammengesetzte Gruende)`` -- je mit Fundstellen.

    Drei Formen kommen im Haus vor, und alle drei muessen gefunden werden:

    1. ``OrderRejectedError(..., reason="x")`` -- Schluesselwort, Konstante,
    2. ``report._reject("naht", "x", ...)`` -- zweites Positionsargument,
    3. ``CostGateDecision(False, "x", ...)`` -- ebenfalls positional, andere Klasse.

    Eine vierte Form ist **nicht aufzaehlbar**: ``reason=f"risk_{...}"``. Der Grund
    entsteht dort zur Laufzeit aus einem fremden Text. Er wird getrennt gemeldet statt
    verschwiegen -- ein Grund, den kein Werkzeug vorher kennt, kann auch kein Test
    gezielt ausloesen, und das ist eine Auskunft ueber den Stand, kein Messfehler.
    """
    fest: dict[str, list[str]] = {}
    zusammengesetzt: dict[str, list[str]] = {}
    for pfad in sorted(PAKET.rglob("*.py")):
        if "__pycache__" in pfad.parts:
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        rel = pfad.relative_to(PAKET).as_posix()
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.keyword) and knoten.arg == "reason":
                if isinstance(knoten.value, ast.Constant) and isinstance(
                    knoten.value.value, str
                ):
                    fest.setdefault(knoten.value.value, []).append(rel)
                elif isinstance(knoten.value, ast.JoinedStr | ast.IfExp):
                    zusammengesetzt.setdefault(
                        f"{rel}:{knoten.value.lineno}", []
                    ).append(rel)
                continue
            if not isinstance(knoten, ast.Call) or len(knoten.args) < 2:
                continue
            zweites = knoten.args[1]
            if not (
                isinstance(zweites, ast.Constant) and isinstance(zweites.value, str)
            ):
                continue
            f = knoten.func
            if isinstance(f, ast.Attribute) and f.attr == "_reject":
                fest.setdefault(zweites.value, []).append(rel)
            elif isinstance(f, ast.Name) and f.id in GRUND_ALS_ZWEITES_ARGUMENT:
                fest.setdefault(zweites.value, []).append(rel)
    return fest, zusammengesetzt


def gruende_in_tests() -> set[str]:
    """Welche Gruende kommen in ``tests/`` als Zeichenkette vor?

    Bewusst eine Textsuche und **nicht** der Syntaxbaum: ein Testfall belegt einen
    Grund typischerweise mit ``assert ex.value.reason == "global_halt"`` oder in einer
    ``parametrize``-Liste, und beide Formen sind Konstanten an wechselnden Stellen. Die
    Grenze der Methode gehoert dazugesagt: ein Grund, der nur in einem Kommentar steht,
    zaehlt hier faelschlich als nachgewiesen.
    """
    text = "\n".join(
        p.read_text(encoding="utf-8") for p in sorted((ROOT / "tests").glob("*.py"))
    )
    fest, _ = gruende_im_code()
    return {g for g in fest if f'"{g}"' in text or f"'{g}'" in text}


def gruende_im_betrieb(quelle: Path) -> Counter[str]:
    zaehler: Counter[str] = Counter()
    dateien = sorted(quelle.glob("*.jsonl")) if quelle.is_dir() else [quelle]
    for datei in dateien:
        if not datei.is_file():
            continue
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                satz = json.loads(zeile)
            except json.JSONDecodeError:
                continue
            if satz.get("art") == "eroeffnungsversuch" and not satz.get("eroeffnet"):
                grund = satz.get("grund")
                if isinstance(grund, str) and grund:
                    zaehler[grund] += 1
    return zaehler


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Tore ohne Ausloesung melden")
    ap.add_argument(
        "--journal",
        type=Path,
        default=ROOT / "aufzeichnungen" / "demo-2026-08-17.jsonl",
    )
    args = ap.parse_args()

    im_code, zusammengesetzt = gruende_im_code()
    if not im_code:
        print(
            "FEHLGESCHLAGEN — kein einziger Ablehnungsgrund im Paket gefunden.",
            file=sys.stderr,
        )
        return 1
    in_tests = gruende_in_tests()
    im_betrieb = gruende_im_betrieb(args.journal)

    print("=" * 78)
    print("TORZAEHLUNG — welches Tor hat je ausgeloest?")
    print("=" * 78)
    print(f"Journal: {args.journal}")
    print(f"Ablehnungsgruende im Code: {len(im_code)}")
    if zusammengesetzt:
        print(
            f"Zur Laufzeit zusammengesetzt (nicht aufzaehlbar): "
            f"{len(zusammengesetzt)} Stellen"
        )
        print("  Sie entstehen aus fremdem Text. Kein Test")
        print("  kann sie gezielt ausloesen, und keine Auswertung sie vorher kennen.")
    print()
    print(f"{'Grund':<38}{'Test':>6}{'Betrieb':>10}  Fundstelle")
    ohne_test: list[str] = []
    for grund in sorted(im_code):
        getestet = grund in in_tests
        n = im_betrieb.get(grund, 0)
        if not getestet and grund not in OHNE_TESTPFLICHT:
            ohne_test.append(grund)
        marke = "ja" if getestet else ("frei" if grund in OHNE_TESTPFLICHT else "NEIN")
        print(f"{grund:<38}{marke:>6}{n:>10}  {im_code[grund][0]}")

    nie_betrieb = sorted(g for g in im_code if g not in im_betrieb)
    fremde = sorted(g for g in im_betrieb if g not in im_code)

    print()
    ausgeloest = len(im_code) - len(nie_betrieb)
    print(f"Im Betrieb je ausgeloest : {ausgeloest} von {len(im_code)}")
    print(f"Im Betrieb NIE ausgeloest: {len(nie_betrieb)}")
    print("  Das ist kein Mangel. Ein Not-Aus, der nie ausgeloest hat, ist ein gutes")
    print("  Zeichen -- die Zahl sagt nur, welche Tore im Betrieb unerprobt sind.")
    if fremde:
        print()
        print(f"Im Betrieb aufgetaucht, aber KEIN Grund dieses Hauses: {len(fremde)}")
        print("  Das sind durchgereichte Brokertexte. Sie tragen keinen Code, an dem")
        print("  eine Auswertung sie zaehlen koennte:")
        for g in fremde[:8]:
            print(f"    {im_betrieb[g]:>5}x  {g}")

    if ohne_test:
        print()
        for grund in ohne_test:
            print(
                f"FEHLGESCHLAGEN — kein Test loest '{grund}' aus "
                f"({im_code[grund][0]}).",
                file=sys.stderr,
            )
        print(
            "Ein Tor ohne Test, der es ausloest, ist eine Behauptung.", file=sys.stderr
        )
        return 1
    print()
    print("ok — jedes Tor hat einen Test, der es ausloest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

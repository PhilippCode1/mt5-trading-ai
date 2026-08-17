#!/usr/bin/env python3
"""Kostentor (A1.3/A1.4): traegt die geplante Betriebsauslegung nach echten Kosten?

Dieses Werkzeug baut **kein** neues Kostenmodell. Es fuettert die vorhandenen
Funktionen aus ``mt5_trading_ai/risk/stop_budget.py`` -- ``cost_floor_bps``,
``margin_ceiling_bps``, ``breakeven_hit_rate`` -- mit zwei Eingaben:

* ``config/broker_costs.json``   -- recherchiert, je Zeile mit Quelle und Abrufdatum
* ``config/atr_measurements.json`` -- gemessen ueber den lesenden MT5-Demo-Pfad

Beide sind fail-closed: fehlt eine, bricht der Lauf ab. Fehlt eine **einzelne** Zahl
(kein Symbol am Terminal, kein veroeffentlichter Spread), faellt genau diese Zeile aus
der Rechnung und wird als „nicht rechenbar" mit Grund ausgewiesen -- nie mit einer
Ersatzzahl gefuellt.

DIE FORMELN (aus dem Auftrag, damit es keine Auslegungsfrage gibt)
------------------------------------------------------------------
::

    K = Spread + Kommission + Slippage-Annahme        (Round-Turn-Kosten)
    p* = 0,5 + K / (2 x S)                            S = Stopabstand
    k  = K / P                                        Kostenanteil am Nominal
    L  = N x H x k                                    Jahreskostenlast

Gerechnet wird durchgehend in **Basispunkten des Nominals**. Das ist keine
Bequemlichkeit, sondern der einzige Weg, sechs Instrumente in vier Notierungen
(USD, JPY, EUR, USD je Aktie) miteinander zu vergleichen, ohne bei jedem Schritt eine
Waehrung mitzuschleppen. ``p*`` bleibt davon unberuehrt: es ist ein Verhaeltnis zweier
Groessen derselben Einheit.

DIE MASSSTAEBE (M1/M2, vor der ersten Messung festgeschrieben)
---------------------------------------------------------------
M1 gruen  : p* <= 56 % bei mindestens 3 der 6 Pruefinstrumente bei mindestens
            einem Broker
M1 gelb   : p* zwischen 56 % und 62 %
M1 rot    : p* > 62 % bei allen sechs Instrumenten bei allen Brokern
M2        : Jahreskostenlast > 50 % des Eigenkapitals -> Betriebsauslegung aendern

Aufruf:
  python tools/kostentor.py            volle Matrix + Urteil
  python tools/kostentor.py --kurz     nur die Urteilstabelle
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mt5_trading_ai.costs.broker_costs import (  # noqa: E402
    BrokerCosts,
    BrokerCostsError,
    InstrumentCost,
    load_broker_costs,
)
from mt5_trading_ai.costs.volatility import (  # noqa: E402
    AtrMeasurement,
    AtrMeasurementError,
    load_atr_measurements,
    load_fx_rates,
)
from mt5_trading_ai.risk.stop_budget import (  # noqa: E402
    breakeven_hit_rate,
    cost_floor_bps,
    margin_ceiling_bps,
)

# --- Maszstaebe aus §2 des Auftrags. Vor der Messung gesetzt, nicht verhandelbar. ---
M1_GRUEN_MAX = Decimal("0.56")
M1_GELB_MAX = Decimal("0.62")
M1_MIN_INSTRUMENTE_GRUEN = 3
M2_MAX_JAHRESLAST = Decimal("0.50")

#: Stopabstaende als Vielfaches des gemessenen Median-ATR(14) auf H1.
STOP_VIELFACHE: tuple[Decimal, ...] = (Decimal("1.0"), Decimal("1.5"), Decimal("2.0"))
#: Umschlag in Round-Turns je Handelstag.
UMSCHLAEGE: tuple[int, ...] = (2, 4, 8)
#: Handelstage je Jahr (Vorgabe aus M2).
HANDELSTAGE = 250
#: Hebel je Lauf. Krypto bleibt hart bei 1/2 (ESMA 2:1).
HEBEL: tuple[int, ...] = (1, 2, 5)
HEBEL_KRYPTO: tuple[int, ...] = (1, 2)

#: Das Pruefuniversum aus §4: Schluessel -> (Klartext, Anlageklasse, ESMA-Deckel).
UNIVERSUM: tuple[tuple[str, str, str, int], ...] = (
    ("EURUSD", "Haupt-Waehrungspaar", "fx_major", 30),
    ("GBPJPY", "Nebenpaar", "fx_minor", 20),
    ("XAUUSD", "Edelmetall", "gold", 20),
    ("DE40", "Hauptindex (DAX40)", "index_major", 20),
    ("BTCUSD", "Krypto", "crypto", 2),
    ("NVDA", "Einzelaktie (Technik/KI)", "equity", 5),
)


class KostentorError(RuntimeError):
    """Eingaben unbrauchbar. Fail-closed: kein Urteil."""


@dataclass(frozen=True)
class Zeile:
    """Eine Kostenzeile: ein Instrument bei einem Broker."""

    instrument: str
    broker: str
    rechenbar: bool
    grund: str | None
    spread_bps: Decimal | None
    kommission_bps: Decimal | None
    slippage_bps: Decimal | None
    k_bps: Decimal | None
    atr_median_bps: Decimal | None
    atr_p25_bps: Decimal | None
    swap_bps_nacht: Decimal | None
    #: Am Demo-Feed GEMESSENER Median-Spread desselben Instruments, in Basispunkten.
    #: Nicht Teil von K -- er stammt von einem anderen Handelsplatz. Er dient als
    #: unabhaengige Gegenprobe zum veroeffentlichten Spread (Robustheitsrechnung).
    gemessener_spread_bps: Decimal | None


def _fx(betrag: Decimal, von: str, nach: str, kurse: dict[str, float]) -> Decimal:
    """Rechne einen Betrag von einer Waehrung in eine andere. Laut scheitern.

    Nur die drei gemessenen Paare stehen zur Verfuegung. Eine Waehrung, die sich damit
    nicht erreichen laesst, ist ein Fehler und keine Naeherung -- ein geratener Kurs
    verfaelscht die Kommission und damit das ganze Urteil.
    """
    if von == nach:
        return betrag

    def kurs(paar: str) -> Decimal:
        if paar not in kurse:
            raise KostentorError(
                f"Umrechnung {von}->{nach} braucht den Kurs {paar}, der in der "
                "Messdatei fehlt. Kein Ersatzkurs."
            )
        return Decimal(str(kurse[paar]))

    # Erst alles nach USD, dann von USD in die Zielwaehrung.
    if von == "USD":
        in_usd = betrag
    elif von == "EUR":
        in_usd = betrag * kurs("EURUSD")
    elif von == "GBP":
        in_usd = betrag * kurs("GBPUSD")
    elif von == "JPY":
        in_usd = betrag / kurs("USDJPY")
    else:
        raise KostentorError(f"Unbekannte Ausgangswaehrung {von!r}")

    if nach == "USD":
        return in_usd
    if nach == "EUR":
        return in_usd / kurs("EURUSD")
    if nach == "GBP":
        return in_usd / kurs("GBPUSD")
    if nach == "JPY":
        return in_usd * kurs("USDJPY")
    raise KostentorError(f"Unbekannte Zielwaehrung {nach!r}")


def _zeile(
    schluessel: str,
    broker_key: str,
    kosten: InstrumentCost | None,
    messung: AtrMeasurement | None,
    slippage: dict[str, Decimal],
    kurse: dict[str, float],
) -> Zeile:
    """Rechne eine Zeile durch.

    Jede fehlende Eingabe wird zu einem begruendeten Nein.
    """

    def nein(grund: str) -> Zeile:
        return Zeile(
            instrument=schluessel, broker=broker_key, rechenbar=False, grund=grund,
            spread_bps=None, kommission_bps=None, slippage_bps=None, k_bps=None,
            atr_median_bps=None, atr_p25_bps=None, swap_bps_nacht=None,
            gemessener_spread_bps=None,
        )

    if kosten is None:
        return nein("Broker fuehrt dieses Instrument nicht in der Kostendatei")
    if not kosten.available:
        return nein(f"{kosten.status}: {kosten.reason or 'ohne Grund'}")
    if messung is None:
        return nein("kein Eintrag in der Messdatei")
    if not messung.measured:
        return nein(f"Volatilitaet nicht gemessen: {messung.reason}")

    preis = messung.price_median
    if preis is None or preis <= 0:
        return nein("kein gemessener Referenzpreis")
    p = Decimal(str(preis))

    if kosten.spread_price is None or kosten.contract_size is None:
        return nein("Spread oder Kontraktgroesse fehlt")

    # Spread: Preiseinheiten -> Basispunkte des Nominals.
    spread_bps = kosten.spread_price / p * Decimal("10000")

    # Kommission -> Basispunkte des Nominals. Ein veroeffentlichter PROZENTSATZ schlaegt
    # den Betrag je Lot: er skaliert mit der Position, der Betrag tut das nicht, und bei
    # Aktien-CFDs liegt zwischen beiden Lesarten eine Groessenordnung (0,04 USD je Aktie
    # Mindestgebuehr gegen 0,1 % je Seite Regelsatz).
    if kosten.commission_bps_round_turn is not None:
        kommission_bps = kosten.commission_bps_round_turn
    else:
        kommission = kosten.commission_round_turn or Decimal("0")
        if kommission > 0:
            quelle = kosten.commission_currency or ""
            ziel = kosten.quote_currency or ""
            kommission = _fx(kommission, quelle, ziel, kurse)
        nominal = kosten.contract_size * p
        if nominal <= 0:
            return nein("Nominal je Lot ist nicht positiv")
        kommission_bps = kommission / nominal * Decimal("10000")

    slip = slippage.get(schluessel)
    if slip is None:
        return nein("keine bezifferte Slippage-Annahme fuer dieses Instrument")

    k_bps = spread_bps + kommission_bps + slip

    atr50 = messung.atr_median_bps
    atr25 = messung.atr_p25_bps
    if atr50 is None or atr25 is None:
        return nein("ATR-Kennzahlen unvollstaendig")

    return Zeile(
        instrument=schluessel, broker=broker_key, rechenbar=True, grund=None,
        spread_bps=spread_bps, kommission_bps=kommission_bps, slippage_bps=slip,
        k_bps=k_bps,
        atr_median_bps=Decimal(str(atr50)), atr_p25_bps=Decimal(str(atr25)),
        swap_bps_nacht=kosten.swap_bps_night_long,
        gemessener_spread_bps=(
            Decimal(str(messung.spread_median_points)) * Decimal(str(messung.point)) / p
            * Decimal("10000")
            if messung.spread_median_points is not None and messung.point is not None
            else None
        ),
    )


def _p_stern(k_bps: Decimal, stop_bps: Decimal) -> Decimal:
    """Erforderliche Trefferquote bei CRV 1:1 -- aus der Risikoschicht, nicht neu."""
    return breakeven_hit_rate(cost_bps=k_bps, stop_bps=stop_bps)


def _ampel(p: Decimal) -> str:
    if p <= M1_GRUEN_MAX:
        return "GRUEN"
    if p <= M1_GELB_MAX:
        return "GELB"
    return "ROT"


def _q(wert: Decimal, stellen: str = "0.01") -> Decimal:
    return wert.quantize(Decimal(stellen))


def lade() -> tuple[BrokerCosts, dict[str, AtrMeasurement], dict[str, float]]:
    try:
        kosten = load_broker_costs()
    except BrokerCostsError as exc:
        raise KostentorError(f"Kostendatei unbrauchbar: {exc}") from exc
    try:
        messungen = load_atr_measurements()
        kurse = load_fx_rates()
    except AtrMeasurementError as exc:
        raise KostentorError(f"Messdatei unbrauchbar: {exc}") from exc
    return kosten, messungen, kurse


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Kostentor: erforderliche Trefferquote und Jahreskostenlast."
    )
    parser.add_argument("--kurz", action="store_true", help="nur die Urteilstabelle")
    args = parser.parse_args()

    try:
        kosten, messungen, kurse = lade()
    except KostentorError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 2

    print("=" * 100)
    print("KOSTENTOR — Paket 2, A1.3/A1.4")
    print("=" * 100)
    print(f"Kostendatei : {kosten.costs_id} (geprueft {kosten.verified_on}), "
          f"{len(kosten.brokers)} Broker")
    print(
        "Messdatei   : ATR(14) H1, 12 Monate, gemessen ueber den lesenden MT5-Demo-Pfad"
    )
    print(f"Umrechnung  : {kurse}")
    print()

    zeilen: list[Zeile] = []
    for schluessel, _klartext, _klasse, _deckel in UNIVERSUM:
        for broker_key, broker in kosten.brokers.items():
            zeilen.append(
                _zeile(
                    schluessel, broker_key, broker.instruments.get(schluessel),
                    messungen.get(schluessel), kosten.slippage_bps, kurse,
                )
            )

    rechenbar = [z for z in zeilen if z.rechenbar]
    print(f"Kostenzeilen: {len(rechenbar)} von {len(zeilen)} rechenbar "
          f"({len(UNIVERSUM)} Instrumente x {len(kosten.brokers)} Broker)")
    print()

    # --- Tabelle 1: Round-Turn-Kosten je Zeile -----------------------------
    print("-" * 100)
    print("TABELLE 1 — Round-Turn-Kosten K in Basispunkten des Nominals")
    print("-" * 100)
    print(f"{'Instrument':<10} {'Broker':<16} {'Spread':>9} {'Komm.':>9} "
          f"{'Slip.':>7} {'K':>9} {'ATR50':>8} {'ATR25':>8}")
    for z in zeilen:
        if not z.rechenbar:
            print(f"{z.instrument:<10} {z.broker:<16} NICHT RECHENBAR — {z.grund}")
            continue
        assert z.spread_bps is not None and z.kommission_bps is not None
        assert z.slippage_bps is not None and z.k_bps is not None
        assert z.atr_median_bps is not None and z.atr_p25_bps is not None
        print(f"{z.instrument:<10} {z.broker:<16} {_q(z.spread_bps):>9} "
              f"{_q(z.kommission_bps):>9} {_q(z.slippage_bps):>7} "
              f"{_q(z.k_bps):>9} {_q(z.atr_median_bps):>8} {_q(z.atr_p25_bps):>8}")
    print()

    # --- Tabelle 2: erforderliche Trefferquote p* --------------------------
    print("-" * 100)
    print("TABELLE 2 — erforderliche Trefferquote p* bei CRV 1:1")
    print("            S = Vielfaches x Median-ATR(14) H1. Zweite Zeile je Fall: das")
    print(
        "            25. Perzentil (ruhige Marktphase) -- dort beissen die Kosten am "
        "staerksten."
    )
    print("-" * 100)
    kopf = "".join(f"{'S=' + str(m) + 'xATR':>16}" for m in STOP_VIELFACHE)
    print(f"{'Instrument':<10} {'Broker':<16}{kopf}")
    bestes_je_instrument: dict[str, Decimal] = {}
    for z in rechenbar:
        assert z.k_bps is not None and z.atr_median_bps is not None
        assert z.atr_p25_bps is not None
        felder_50, felder_25 = "", ""
        for mult in STOP_VIELFACHE:
            p50 = _p_stern(z.k_bps, mult * z.atr_median_bps)
            p25 = _p_stern(z.k_bps, mult * z.atr_p25_bps)
            felder_50 += f"{_q(p50 * 100, '0.1'):>10}% {_ampel(p50)[:4]:>4}"
            felder_25 += f"{_q(p25 * 100, '0.1'):>10}% {_ampel(p25)[:4]:>4}"
            if mult == Decimal("1.0"):
                vorher = bestes_je_instrument.get(z.instrument)
                if vorher is None or p50 < vorher:
                    bestes_je_instrument[z.instrument] = p50
        print(f"{z.instrument:<10} {z.broker:<16}{felder_50}   (Median)")
        print(f"{'':<10} {'':<16}{felder_25}   (25. Perzentil)")
    print()

    # --- Urteil gegen M1 ---------------------------------------------------
    print("=" * 100)
    print("URTEIL GEGEN M1 — Kennzahl: p* bei CRV 1:1 und S = 1,0 x Median-ATR(14) H1")
    print("=" * 100)
    gemessene_instrumente = [s for s, _, _, _ in UNIVERSUM if s in bestes_je_instrument]
    nicht_bewertbar = [s for s, _, _, _ in UNIVERSUM if s not in bestes_je_instrument]
    gruen = [
        s for s in gemessene_instrumente
        if bestes_je_instrument[s] <= M1_GRUEN_MAX
    ]
    gelb = [
        s for s in gemessene_instrumente
        if M1_GRUEN_MAX < bestes_je_instrument[s] <= M1_GELB_MAX
    ]
    rot = [s for s in gemessene_instrumente if bestes_je_instrument[s] > M1_GELB_MAX]

    for s, klartext, _, deckel in UNIVERSUM:
        if s in bestes_je_instrument:
            p = bestes_je_instrument[s]
            print(f"  {s:<8} {klartext:<26} bestes p* = {_q(p * 100, '0.1')} % "
                  f"-> {_ampel(p):<5} (ESMA-Deckel {deckel}:1)")
        else:
            print(f"  {s:<8} {klartext:<26} NICHT BEWERTBAR (siehe Tabelle 1)")
    print()
    print(f"  gruen: {len(gruen)} von {len(UNIVERSUM)} Instrumenten {gruen}")
    print(f"  gelb : {len(gelb)} von {len(UNIVERSUM)} Instrumenten {gelb}")
    print(f"  rot  : {len(rot)} von {len(UNIVERSUM)} Instrumenten {rot}")
    if nicht_bewertbar:
        print(f"  nicht bewertbar: {len(nicht_bewertbar)} von {len(UNIVERSUM)} "
              f"{nicht_bewertbar}")
    print()
    # M1 sagt "bei mindestens einem Broker". Streng gelesen heisst das: EIN Broker muss
    # die geforderten drei gruenen Instrumente tragen -- nicht drei Broker je eines.
    # Der Unterschied ist keine Spitzfindigkeit: wer je Instrument den guenstigsten
    # Anbieter nimmt, baut ein Konto zusammen, das es nicht gibt.
    je_broker: dict[str, list[str]] = {}
    for z in rechenbar:
        assert z.k_bps is not None and z.atr_median_bps is not None
        if _p_stern(z.k_bps, z.atr_median_bps) <= M1_GRUEN_MAX:
            je_broker.setdefault(z.broker, []).append(z.instrument)
    print(
        "  Strenge Lesart ('bei mindestens einem Broker') — gruene Instrumente je "
        "Broker:"
    )
    for broker_key, liste in sorted(je_broker.items()):
        print(f"    {broker_key:<16} {len(liste)} {sorted(liste)}")
    fehlende = [b for b in kosten.brokers if b not in je_broker]
    for broker_key in sorted(fehlende):
        print(f"    {broker_key:<16} 0 []")
    bester_broker = max(je_broker.items(), key=lambda kv: len(kv[1]), default=("-", []))
    print(f"    -> bester einzelner Broker: {bester_broker[0]} mit "
          f"{len(bester_broker[1])} gruenen Instrumenten "
          f"(gefordert: mindestens {M1_MIN_INSTRUMENTE_GRUEN})")
    print()

    if (
        len(gruen) >= M1_MIN_INSTRUMENTE_GRUEN
        and len(bester_broker[1]) >= M1_MIN_INSTRUMENTE_GRUEN
    ):
        m1 = "GRUEN"
        satz = (f"p* <= {M1_GRUEN_MAX * 100:.0f} % bei {len(gruen)} Instrumenten, und "
                f"{bester_broker[0]} allein traegt {len(bester_broker[1])} davon "
                f"(gefordert: mindestens {M1_MIN_INSTRUMENTE_GRUEN}).")
    elif rot and len(rot) == len(UNIVERSUM):
        m1 = "ROT"
        satz = "p* > 62 % bei allen sechs Instrumenten bei allen Brokern."
    else:
        m1 = "GELB"
        satz = (f"Weniger als {M1_MIN_INSTRUMENTE_GRUEN} Instrumente unter "
                f"{M1_GRUEN_MAX * 100:.0f} %, aber nicht alle ueber "
                f"{M1_GELB_MAX * 100:.0f} %.")
    print(f"  M1-AMPEL: {m1} — {satz}")
    print()

    if nicht_bewertbar:
        print(
            "  ZUR AMPEL SELBST, ausdruecklich: solange ein Instrument nicht bewertbar"
        )
        print(f"  ist ({nicht_bewertbar}), kann ROT nach dem Wortlaut von M1 gar nicht")
        print(
            "  eintreten -- ROT verlangt 'bei allen sechs Instrumenten'. Die Ampel ist"
        )
        print(
            "  in dieser Richtung fail-open, und das widerspricht der Kernregel 'nicht"
        )
        print(
            "  bewertbar = nicht erfuellt'. Das nicht bewertbare Instrument zaehlt hier"
        )
        print(
            "  darum als NICHT gruen; ein ROT-Urteil waere mit dieser Datenlage nicht"
        )
        print("  feststellbar und wird auch nicht behauptet.")
        print()

    _robustheit(rechenbar, gruen)

    if not args.kurz:
        _jahreslast(rechenbar)
        _swaps(rechenbar, kosten)
        _gegenrechnung(rechenbar)

    print("=" * 100)
    print(f"ERGEBNIS: M1 = {m1}. Bezugsgroesse: {len(rechenbar)} rechenbare "
          f"Kostenzeilen "
          f"aus {len(UNIVERSUM)} Instrumenten x {len(kosten.brokers)} Brokern.")
    print("=" * 100)
    return 0


def _robustheit(rechenbar: list[Zeile], gruen_basis: list[str]) -> None:
    """Wie belastbar ist das Urteil? Fuenf gleich vertretbare Lesarten derselben Daten.

    Der Massstab M1 wird dabei **nicht** angetastet -- er stand vor der Messung fest und
    wird nicht im Licht der Ergebnisse eingeordnet. Was hier steht, ist etwas anderes:
    dieselbe Rechnung unter Annahmen, die genauso gut begruendbar sind wie die
    gewaehlten.
    Kippt die Ampel dabei, ist das Urteil duenn -- und das gehoert zum Urteil dazu.
    """
    print("-" * 100)
    print("TABELLE 2b — ROBUSTHEIT: p* bei S = 1,0 x ATR unter fuenf Lesarten")
    print("-" * 100)
    print("  A  wie gerechnet: veroeffentlichter Spread, Median-ATR, ohne Swap")
    print("  B  GEMESSENER Median-Spread des Demo-Feeds statt des veroeffentlichten")
    print(
        "  C  Slippage-Annahme verdoppelt (sie ist der einzige ungemessene Posten in K)"
    )
    print("  D  Swap eingerechnet: 25 % der Trades kreuzen den Rollover (4 RT/Tag)")
    print("  E  25. Perzentil der Volatilitaet statt des Medians (ruhige Marktphase)")
    print("  F  B, C, D und E zusammen -- die unguenstige, aber vertretbare Lesart")
    print()
    kopf = "".join(f"{buchstabe:>10}" for buchstabe in "ABCDEF")
    print(f"{'Instrument':<10} {'Broker':<16}{kopf}")
    bestes: dict[str, dict[str, Decimal]] = {}
    for z in rechenbar:
        assert z.k_bps is not None and z.atr_median_bps is not None
        assert z.atr_p25_bps is not None and z.slippage_bps is not None
        assert z.spread_bps is not None
        swap = (
            abs(z.swap_bps_nacht) * Decimal("0.25")
            if z.swap_bps_nacht
            else Decimal(0)
        )
        gemessen = z.gemessener_spread_bps
        k_b = z.k_bps - z.spread_bps + gemessen if gemessen is not None else z.k_bps
        varianten: dict[str, tuple[Decimal, Decimal]] = {
            "A": (z.k_bps, z.atr_median_bps),
            "B": (k_b, z.atr_median_bps),
            "C": (z.k_bps + z.slippage_bps, z.atr_median_bps),
            "D": (z.k_bps + swap, z.atr_median_bps),
            "E": (z.k_bps, z.atr_p25_bps),
            "F": (k_b + z.slippage_bps + swap, z.atr_p25_bps),
        }
        felder = ""
        for name, (k, stop) in varianten.items():
            p = _p_stern(k, stop)
            felder += f"{_q(p * 100, '0.1'):>9}{'*' if p <= M1_GRUEN_MAX else ' '}"
            eintrag = bestes.setdefault(z.instrument, {})
            if name not in eintrag or p < eintrag[name]:
                eintrag[name] = p
        marke = "" if gemessen is not None else "   (B ohne gemessenen Spread)"
        print(f"{z.instrument:<10} {z.broker:<16}{felder}{marke}")
    print("  * = unter der 56-%-Schwelle")
    print()
    print("  Zahl der gruenen Instrumente je Lesart (gefordert: mindestens 3):")
    for name in "ABCDEF":
        zahl = [inst for inst, werte in bestes.items()
                if name in werte and werte[name] <= M1_GRUEN_MAX]
        ampel = "GRUEN" if len(zahl) >= M1_MIN_INSTRUMENTE_GRUEN else "NICHT GRUEN"
        print(
            f"    {name}: {len(zahl)} von {len(UNIVERSUM)} -> {ampel:<11} "
            f"{sorted(zahl)}"
        )
    print()
    print(f"  Ausgangslage (Lesart A): {len(gruen_basis)} gruene Instrumente "
          f"{sorted(gruen_basis)}.")
    print()


def _jahreslast(rechenbar: list[Zeile]) -> None:
    print("-" * 100)
    print("TABELLE 3 — Jahreskostenlast L = N x H x k auf das Eigenkapital")
    print(f"            N = Round-Turns/Jahr ({HANDELSTAGE} Handelstage), H = Hebel, "
          "k = K/10000")
    print(
        "            M2: ueber 50 % ist die Betriebsauslegung zu aendern, nicht der "
        "Massstab."
    )
    print("-" * 100)
    print(f"{'Instrument':<10} {'Broker':<16} {'RT/Tag':>7} {'Hebel':>6} "
          f"{'L in % des Eigenkapitals':>26}")
    verstoesse = 0
    gesamt = 0
    for z in rechenbar:
        assert z.k_bps is not None
        k = z.k_bps / Decimal("10000")
        hebel = HEBEL_KRYPTO if z.instrument == "BTCUSD" else HEBEL
        for rt in UMSCHLAEGE:
            n = rt * HANDELSTAGE
            for h in hebel:
                last = Decimal(n) * Decimal(h) * k
                gesamt += 1
                marke = ""
                if last > M2_MAX_JAHRESLAST:
                    verstoesse += 1
                    marke = "  <-- M2 gerissen"
                print(f"{z.instrument:<10} {z.broker:<16} {rt:>7} {h:>6} "
                      f"{_q(last * 100, '0.1'):>25} %{marke}")
    print()
    print(
        f"  M2 ueber alle Kombinationen: {verstoesse} von {gesamt} reissen die Grenze."
    )
    print()
    # M2 ist auf die GEPLANTE Auslegung gemuenzt: 4 Round-Turns je Handelstag, 250 Tage,
    # Hebel 5 (Krypto 2). Die Gesamtzahl oben ist nur Kontext -- das Urteil faellt hier.
    print("  URTEIL GEGEN M2 — geplante Auslegung: 4 RT/Tag, 250 Tage, Hebel 5 "
          "(Krypto 2)")
    gerissen: list[tuple[str, str, Decimal]] = []
    gehalten: list[tuple[str, str, Decimal]] = []
    for z in rechenbar:
        assert z.k_bps is not None
        hebel_m2 = 2 if z.instrument == "BTCUSD" else 5
        last = (
            Decimal(4 * HANDELSTAGE) * Decimal(hebel_m2) * z.k_bps / Decimal("10000")
        )
        (gerissen if last > M2_MAX_JAHRESLAST else gehalten).append(
            (z.instrument, z.broker, last)
        )
    for name, broker_key, last in gerissen + gehalten:
        marke = "REISST" if last > M2_MAX_JAHRESLAST else "haelt "
        print(f"    {marke}  {name:<8} {broker_key:<16} {_q(last * 100, '0.1'):>8} %")
    print()
    betroffen = sorted({name for name, _, _ in gerissen})
    print(f"  M2-URTEIL: {len(gerissen)} von {len(rechenbar)} Kostenzeilen reissen die "
          f"50-%-Grenze")
    print(f"  bei der geplanten Auslegung. Betroffen: {betroffen}.")
    if gerissen:
        print(
            "  Folge nach M2: die BETRIEBSAUSLEGUNG wird geaendert -- Umschlag runter"
        )
        print(
            "  oder Horizont hoch. Nicht der Maszstab. Die Gegenrechnung steht unten."
        )
        print()
        print("  GEGENRECHNUNG: welche Auslegung haelt M2?")
        print("  Gerechnet je Instrument mit dem GUENSTIGSTEN Broker -- wer ein")
        print("  Instrument handelt, waehlt dafuer nicht den teuersten Anbieter.")
        guenstigste: dict[str, Decimal] = {}
        for z in rechenbar:
            assert z.k_bps is not None
            vorher = guenstigste.get(z.instrument)
            if vorher is None or z.k_bps < vorher:
                guenstigste[z.instrument] = z.k_bps
        for rt in (8, 4, 2, 1):
            for h in (5, 2, 1):
                lasten = {
                    name: Decimal(rt * HANDELSTAGE) * Decimal(h) * k / Decimal("10000")
                    for name, k in guenstigste.items()
                }
                schlimmste = max(lasten.values())
                reisser = sorted(n for n, v in lasten.items() if v > M2_MAX_JAHRESLAST)
                zustand = "haelt " if not reisser else "reisst"
                print(f"    {rt} RT/Tag, Hebel {h}: hoechste Last "
                      f"{_q(schlimmste * 100, '0.1'):>8} %  -> {zustand} {reisser}")
    print()


def _swaps(rechenbar: list[Zeile], kosten: BrokerCosts) -> None:
    print("-" * 100)
    print("TABELLE 4 — Swap, GETRENNT ausgewiesen (nicht in K enthalten)")
    print("-" * 100)
    print("  Der Anteil der Positionen, die den Rollover kreuzen, ist eine SCHAETZUNG,")
    print(
        "  keine Messung. Herleitung: bei gleichverteiltem Einstieg ueber den "
        "Handelstag"
    )
    print("  und einer mittleren Haltedauer von 24/RT Stunden kreuzt ein Anteil von")
    print(
        "  Haltedauer/24 den taeglichen Rollover-Zeitpunkt. Bei 4 RT/Tag sind das 6 h"
    )
    print("  Haltedauer und damit 25 % der Trades.")
    print()
    print(f"{'Instrument':<10} {'Broker':<16} {'bp/Nacht (long)':>17} "
          f"{'Kreuzanteil':>12} {'Swap-Last/Jahr in %':>22}")
    ohne_bps: list[str] = []
    for z in rechenbar:
        if z.swap_bps_nacht is None:
            ohne_bps.append(f"{z.instrument}/{z.broker}")
            continue
        for rt in UMSCHLAEGE:
            haltedauer = Decimal(24) / Decimal(rt)
            anteil = min(Decimal(1), haltedauer / Decimal(24))
            n = rt * HANDELSTAGE
            last = Decimal(n) * anteil * abs(z.swap_bps_nacht) / Decimal("10000")
            print(f"{z.instrument:<10} {z.broker:<16} "
                  f"{_q(z.swap_bps_nacht, '0.001'):>17} "
                  f"{_q(anteil * 100, '0.1'):>11} % {_q(last * 100, '0.1'):>20} %")
    print()
    if ohne_bps:
        print(f"  Ohne Swap in Basispunkten: {len(ohne_bps)} Zeilen — "
              "die Quelle veroeffentlicht den Satz in 'Punkten je Lot' und den dafuer")
        print(
            "  noetigen Pip-Wert NICHT. Ein geratener Pip-Wert waere die stille "
            "Annahme,"
        )
        print("  die dieses Paket ausschliesst. Betroffen:")
        for name in ohne_bps:
            print(f"    - {name}")
    print()
    print(f"  Slippage-Annahme (beziffert, keine Messung): {kosten.slippage_note}")
    print()


def _gegenrechnung(rechenbar: list[Zeile]) -> None:
    print("-" * 100)
    print(
        "TABELLE 5 — Gegenrechnung: ab welchem Stopabstand faellt p* unter die "
        "Schwellen?"
    )
    print("-" * 100)
    print("  Aufgeloest nach S: p* <= x  <=>  S >= K / (2 x (x - 0,5))")
    print(
        f"Fuer x = {M1_GRUEN_MAX} gilt S >= 8,33 x K; fuer x = {M1_GELB_MAX} gilt S >= "
        f"4,17 x K."
    )
    print()
    print(f"{'Instrument':<10} {'Broker':<16} {'K (bp)':>8} {'S fuer 56 %':>12} "
          f"{'als xATR50':>11} {'S fuer 62 %':>12} {'als xATR50':>11}")
    for z in rechenbar:
        assert z.k_bps is not None and z.atr_median_bps is not None
        s_gruen = z.k_bps / (2 * (M1_GRUEN_MAX - Decimal("0.5")))
        s_gelb = z.k_bps / (2 * (M1_GELB_MAX - Decimal("0.5")))
        print(f"{z.instrument:<10} {z.broker:<16} {_q(z.k_bps):>8} "
              f"{_q(s_gruen):>12} {_q(s_gruen / z.atr_median_bps, '0.001'):>11} "
              f"{_q(s_gelb):>12} {_q(s_gelb / z.atr_median_bps, '0.001'):>11}")
    print()
    print("  Zur Einordnung: ein Stopabstand von n x ATR(14) auf H1 entspricht bei")
    print(
        "  Wurzel-t-Skalierung rund n^2 Stunden Haltedauer. S = 2 x ATR(H1) ist damit"
    )
    print("  ein Horizont von rund vier Stunden, S = 4 x ATR(H1) rund sechzehn.")
    print()
    print("  KONTROLLE GEGEN DIE EIGENE RISIKOSCHICHT — der wichtigste Nebenbefund:")
    print("  `risk/stop_budget.py` setzt `max_cost_drag = 0,05`, laesst die Kosten den")
    print(
        "  Nulldurchgang also um hoechstens 5 Prozentpunkte anheben (p <= 55 %). Daraus"
    )
    print("  folgt eine Kostenuntergrenze von 10 x K. Liegt sie UEBER dem gemessenen")
    print(
        "  Median-ATR, ist ein Stop von 1,0 x ATR nach der Politik des Systems selbst"
    )
    print(
        "  unzulaessig -- unabhaengig davon, was M1 mit seiner lockereren 56-%-Schwelle"
    )
    print("  sagt. Das ist kein Widerspruch im Maszstab, sondern einer im Vorhaben.")
    print()
    print(f"{'Instrument':<10} {'K (bp)':>8} {'Kostenfloor':>12} {'ATR50':>9} "
          f"{'1,0 x ATR zulaessig?':>22}")
    unzulaessig: list[str] = []
    beste_zeile: dict[str, Zeile] = {}
    for z in rechenbar:
        assert z.k_bps is not None
        vorher = beste_zeile.get(z.instrument)
        if vorher is None or (vorher.k_bps is not None and z.k_bps < vorher.k_bps):
            beste_zeile[z.instrument] = z
    for schluessel, _, _, _ in UNIVERSUM:
        beste = beste_zeile.get(schluessel)
        if beste is None:
            continue
        assert beste.k_bps is not None and beste.atr_median_bps is not None
        floor = cost_floor_bps(beste.k_bps)
        ok = floor <= beste.atr_median_bps
        if not ok:
            unzulaessig.append(schluessel)
        print(f"{schluessel:<10} {_q(beste.k_bps):>8} {_q(floor):>12} "
              f"{_q(beste.atr_median_bps):>9} {('ja' if ok else 'NEIN'):>22}")
    print()
    if unzulaessig:
        print(f"  BEFUND: bei {len(unzulaessig)} von {len(beste_zeile)} gerechneten")
        print(f"  Instrumenten {unzulaessig} liegt die Kostenuntergrenze der eigenen")
        print("  Risikoschicht ueber dem gemessenen Median-ATR. Fuer diese Instrumente")
        print("  ist der Stopabstand, auf dem M1 gemessen wird, nach der hauseigenen")
        print("  Politik nicht handelbar. M1 bleibt davon unberuehrt -- der Maszstab")
        print("  wird nicht nachtraeglich verschoben --, aber das gruene Urteil dieser")
        print(
            "  Instrumente ist ohne eine Verlaengerung des Horizonts nicht umsetzbar."
        )
    else:
        print(
            "  BEFUND: bei allen gerechneten Instrumenten liegt die Kostenuntergrenze"
        )
        print("  unter dem gemessenen Median-ATR. 1,0 x ATR ist ueberall zulaessig.")
    print()
    print("  Kontrolle der Randbedingung (Stop-Budget der Risikoschicht):")
    print(
        f"{'Instrument':<10} {'Hebel':>6} {'Kostenuntergrenze':>18} "
        f"{'Margin-Obergrenze':>18}"
    )
    gesehen: set[str] = set()
    for z in rechenbar:
        if z.instrument in gesehen:
            continue
        gesehen.add(z.instrument)
        assert z.k_bps is not None
        unten = cost_floor_bps(z.k_bps)
        hebel = HEBEL_KRYPTO if z.instrument == "BTCUSD" else HEBEL
        for h in hebel:
            oben = margin_ceiling_bps(h)
            marke = "  <-- nicht handelbar" if unten > oben else ""
            print(f"{z.instrument:<10} {h:>6} {_q(unten):>18} {_q(oben):>18}{marke}")
    print()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""A1 aus Paket 3a: Historientiefe, Herkunft und Fensterstreuung messen.

Das Werkzeug beantwortet die Frage, die vor jeder Ereignisstudie steht: **kann die
Studie den gesuchten Effekt ueberhaupt von Null trennen?** Es misst dafuer drei Dinge
ueber den bestehenden lesenden MT5-Pfad (``RealMt5Terminal``, ``allow_write=False``,
Demokonto) und rechnet die Aufloesungstabelle aus
``mt5_trading_ai/backtest/resolution.py``.

A1.1  Historientiefe je Instrument und Zeitrahmen.
A1.2  Herkunft: die gelesene Reihe wird gehasht und mit Manifest abgelegt. Die
      Pruefsumme ist die ``data_checksum``, die ``gates/trials.py`` verlangt.
A1.3  Fensterstreuung, **gemessen** statt aus dem ATR skaliert, und daraus die
      Aufloesung je Kombination aus Instrument und Fensterlaenge. Gerechnet wird gegen
      die Stichprobe, die das Deflationsurteil sieht -- das Out-of-Sample-Drittel der
      Ereignisstudie --, nicht gegen die volle Ereigniszahl. ``OOS_ANTEIL`` wird dafuer
      aus ``backtest/ereignisstudie.py`` GELESEN und nicht hier wiederholt: eine Zahl,
      die an zwei Stellen steht, geht an einer davon irgendwann falsch.

LAUT SCHEITERN, NIE STILL
-------------------------
Eine leere Antwort von ``copy_rates_range`` heisst „noch nicht vom Server geladen",
nicht „gibt es nicht". In der Vorbereitung lieferte dasselbe Symbol im ersten Lauf null
und im zweiten 6.492 Kerzen. Jede leere Antwort wird deshalb **ein zweites Mal**
abgefragt; erst der zweite Fehlschlag ist ein Befund, dann mit beiden Zeitstempeln.

Aufruf:
  python tools/aufloesung.py            misst und schreibt config/aufloesung.json
  python tools/aufloesung.py --check    prueft nur die vorhandene Datei (ohne MT5)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mt5_trading_ai.backtest.ereignisstudie import OOS_ANTEIL  # noqa: E402
from mt5_trading_ai.backtest.resolution import (  # noqa: E402
    RESOLUTION_POLICY_VERSION,
    ResolutionError,
    ResolutionVerdict,
    assess,
    deflation_observations,
    dispersion_bps,
    min_events_for_resolution,
    window_returns_bps,
)
from mt5_trading_ai.costs.broker_costs import load_broker_costs  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Rate, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    Timeframe,
    VenueUnavailableError,
    ist_abgeschlossen,
)

OUT = REPO / "config" / "aufloesung.json"
MANIFESTE = REPO / "config" / "reihen"

#: Versuchszahl, gegen die deflationiert wird. Budgetobergrenze aus §5 des Auftrags —
#: die strengste zulaessige Annahme, weil T vorher nicht bekannt ist.
TRIALS = 12

#: Wie weit der Anteil in der Messdatei von ``OOS_ANTEIL`` abweichen darf. Das ist
#: Fliesskomma-Spielraum, kein Ermessen: ein Drittel ist als Dezimalzahl nicht
#: darstellbar, jede andere Abweichung ist ein Befund.
OOS_TOLERANZ = 1e-9

#: Pruefuniversum. XAUUSD und DE40 sind dabei, obwohl die Naeherung sie als knapp blind
#: fuehrt (1,36 und 1,07): genau sie koennte die gemessene Streuung kippen.
INSTRUMENTE: tuple[str, ...] = ("EURUSD", "GBPJPY", "XAUUSD", "DE40", "NVDA")

#: Zeitrahmen mit Balkenlaenge in Stunden UND dem Abrufzeitraum in Jahren.
#: Der Zeitraum je Zeitrahmen ist noetig, nicht Bequemlichkeit: ein Abruf ueber 25 Jahre
#: lieferte auf H1 zunaechst auch beim zweiten Versuch nichts.
#:
#: Die Zahlen sind ABGETASTET, nicht geschaetzt -- die erste Fassung hatte hier 25/25/2
#: stehen und damit die Historie an zwei Stellen zu kurz abgeschnitten:
#:   * H1: eine Treppenprobe (3, 5, 8, 9, 10, 11 Jahre) liefert bis 11 Jahre Kerzen,
#:     an allen fuenf Instrumenten (EURUSD 68.324). Der Fehlschlag bei 12 Jahren kam
#:     SOFORT und zweimal -- und dennoch lieferten spaetere Abrufe ueber 11 Jahre. Das
#:     Terminal laedt Historie auf Anfrage nach; eine leere Antwort ist ein Zustand,
#:     kein Befund. Mit 2 Jahren fiel N je 1h-Fenster um Faktor 5,5 zu klein aus.
#:   * D1/H4: 45 Jahre statt 25 -- EURUSD reicht bis 1981, GBPJPY bis 1993. Mit 25
#:     Jahren fehlten GBPJPY rund 2.200 Handelstage.
ZEITRAHMEN: tuple[tuple[Timeframe, float, int], ...] = (
    (Timeframe.D1, 24.0, 45),
    (Timeframe.H4, 4.0, 45),
    (Timeframe.H1, 1.0, 45),
)

#: Frueheste Kerze, die als das Instrument selbst zaehlt. Fehlt ein Eintrag, gilt alles.
#:
#: EURUSD liefert Tageskerzen ab 1981-08-18, nahtlos ueber den Jahreswechsel 1998/99
#: (Schluss 1,17240 am 31.12.1998, Eroeffnung 1,18010 am 04.01.1999). Den Euro gibt es
#: seit dem 01.01.1999; alles davor ist eine zurueckgerechnete Korbreihe, kein
#: gehandelter Kurs. Sie zaehlt trotzdem 4.480 Kerzen und wuerde N um 71 % aufblaehen --
#: mit einer Tagesrendite-Streuung von 67,1 bp gegen 58,1 bp danach, also aus einem
#: anderen Regime. Ein Ereignis, das nie handelbar war, ist kein Ereignis.
FRUEHESTE_KERZE: dict[str, datetime] = {
    "EURUSD": datetime(1999, 1, 1, tzinfo=UTC),
}

#: Fensterlaengen, fuer die die Streuung gemessen wird: (Name, Stunden).
FENSTER: tuple[tuple[str, float], ...] = (
    ("1h", 1.0),
    ("4h", 4.0),
    ("1d", 24.0),
)

#: Ereignisfrequenzen der Kandidaten aus §5 des Auftrags, je Jahr.
#: DIES ist die Ereigniszahl des Kandidaten -- nicht die Zahl der verfuegbaren Fenster.
#: Ein taegliches Ereignis liefert je Handelstag EIN Ereignis, auch wenn der Tag sechs
#: Vier-Stunden-Fenster enthaelt.
#:
#: Es ist auch NICHT die Zahl, gegen die deflationiert wird: die Deflation der
#: Ereignisstudie laeuft auf dem Out-of-Sample-Drittel. Die Umrechnung macht
#: ``resolution.assess`` selbst, es muss ihr nur der Anteil genannt werden -- siehe
#: ``OOS_ANTEIL``.
FREQUENZEN: tuple[tuple[str, int], ...] = (
    ("taeglich", 252),
    ("monatlich", 12),
)


#: Groesse einer Abrufscheibe in Jahren. Das Terminal beantwortet eine Anfrage, die zu
#: viele Kerzen umspannt, mit einer LEEREN Liste statt mit einem Fehler -- und das sieht
#: von aussen genauso aus wie „es gibt keine Daten".
#:
#: Abgetastet: H1 ueber 11 Jahre liefert 68.276 Kerzen, ueber 12 Jahre zweimal nichts.
#: Dieselbe Reihe stueckweise abgefragt liefert aber Kerzen bis **2010-07-07** --
#: ein Abruf 2013-2016 gibt 18.505, ein Abruf 2005-2006 klemmt auf den 07.07.2010.
#: Die Grenze liegt also bei rund 70.000 Kerzen JE ABFRAGE, nicht an der Historie.
#: Fuenf Jahre H1 sind rund 31.000 Kerzen und damit sicher darunter.
SCHEIBE_JAHRE = 5


def _hole(
    terminal: RealMt5Terminal, symbol: str, tf: Timeframe, jahre: int
) -> tuple[tuple[Mt5Rate, ...], list[str]]:
    """Kerzen holen — in Scheiben, mit zweitem Versuch je Scheibe.

    Von jung nach alt, damit das Protokoll zeigt, wo die Historie endet. Eine leere
    Scheibe wird vermerkt und nicht als Abbruch behandelt: vor dem Anfang des Archivs
    ist Leere die richtige Antwort. Erst wenn ALLE Scheiben leer sind, ist die
    Reihe leer.

    **Die noch in Bildung befindliche Kerze bleibt draussen.** Sie kam frueher mit,
    und das ist an den erzeugten Manifesten nachweisbar: bei 12 der 15 lag die letzte
    Bar zum Abrufzeitpunkt noch offen (EURUSD H1 ``last=13:00`` gegen
    ``retrieved_at=13:14`` -- die Kerze schliesst erst um 14:00). Die Pruefsumme im
    Manifest deckte damit eine Bar, die sich noch aenderte; ein zweiter Abruf ergab
    eine andere Zahl, und die Reihe war per Konstruktion nicht reproduzierbar.

    ``jetzt`` kommt vom Tick des Symbols, nicht von der Rechneruhr -- Begruendung bei
    ``protocol.ist_abgeschlossen``. Ohne Tick wird nicht geraten: die Reihe bleibt
    leer und das Protokoll sagt warum.
    """
    ende = datetime.now(UTC)
    beginn = ende - timedelta(days=365 * jahre)
    protokoll: list[str] = []
    gesammelt: dict[datetime, Mt5Rate] = {}

    tick = terminal.tick(symbol)
    if tick is None:
        protokoll.append(
            f"{symbol}/{tf.value}: kein Tick -- ohne Platzzeit ist nicht entscheidbar, "
            "welche Kerze abgeschlossen ist; Reihe bleibt leer (fail-closed)"
        )
        return (), protokoll
    jetzt = tick.ts

    scheibe_ende = ende
    while scheibe_ende > beginn:
        scheibe_start = max(beginn, scheibe_ende - timedelta(days=365 * SCHEIBE_JAHRE))
        for versuch in (1, 2):
            zeit = datetime.now(UTC)
            reihe = terminal.rates(symbol, tf, scheibe_start, scheibe_ende)
            if reihe:
                for r in reihe:
                    if not ist_abgeschlossen(r.ts, tf, jetzt):
                        continue
                    gesammelt[r.ts] = r
                protokoll.append(
                    f"{symbol}/{tf.value} {scheibe_start.date()}.."
                    f"{scheibe_ende.date()} Versuch {versuch} um "
                    f"{zeit.isoformat(timespec='seconds')}: {len(reihe)} Kerzen"
                )
                break
        else:
            protokoll.append(
                f"{symbol}/{tf.value} {scheibe_start.date()}.."
                f"{scheibe_ende.date()}: zweimal leer (vor dem Anfang des "
                f"Archivs oder nicht geladen)"
            )
        scheibe_ende = scheibe_start

    grenze = FRUEHESTE_KERZE.get(symbol)
    if grenze is not None:
        vorher = len(gesammelt)
        gesammelt = {ts: r for ts, r in gesammelt.items() if ts >= grenze}
        if vorher != len(gesammelt):
            protokoll.append(
                f"{symbol}/{tf.value}: {vorher - len(gesammelt)} Kerzen vor "
                f"{grenze.date()} verworfen (Instrument existierte noch nicht)"
            )
    return tuple(gesammelt[ts] for ts in sorted(gesammelt)), protokoll


def _manifest(symbol: str, tf: Timeframe, reihe: tuple[Mt5Rate, ...]) -> dict[str, Any]:
    """Pruefsumme und Manifest der gelesenen Reihe — die Herkunft aus A1.2.

    Gehasht wird die Reihe selbst (Zeitstempel und OHLC je Kerze, kanonisch als Text),
    nicht die Datei. So haengt die Pruefsumme an den Daten und nicht an einer
    Formatierung.
    """
    hasher = hashlib.sha256()
    for r in reihe:
        hasher.update(
            f"{int(r.ts.timestamp())};{r.open};{r.high};{r.low};{r.close}\n".encode()
        )
    return {
        "symbol": symbol,
        "timeframe": tf.value,
        "bars": len(reihe),
        "first": reihe[0].ts.isoformat() if reihe else None,
        "last": reihe[-1].ts.isoformat() if reihe else None,
        "checksum": hasher.hexdigest(),
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "mt5-terminal-read-only",
        # Welche Zeitbasis die Stempel tragen. Dieses Werkzeug baut sein Terminal
        # BEWUSST ohne ``server_tz``: die hier abgelegten Manifeste sind der Beleg
        # von Paket 3a und muessen reproduzierbar bleiben. Eine Drehung verschoebe
        # jeden Stempel und damit jede Pruefsumme, ohne an den Messungen etwas zu
        # aendern (Streuung und Ereigniszahlen haengen an der Reihenfolge der Kerzen,
        # nicht an ihrer Beschriftung). Wer neu misst, entscheidet neu -- aber dann
        # sagt dieses Feld, was er vor sich hat.
        "zeitbasis": "server-etikett",
    }


def messen() -> int:
    terminal = RealMt5Terminal(allow_write=False)
    try:
        verbunden = terminal.initialize()
    except VenueUnavailableError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 2
    if not verbunden:
        print("FEHLGESCHLAGEN — MT5-Terminal nicht initialisierbar.", file=sys.stderr)
        return 2

    kosten = load_broker_costs()

    try:
        konto = terminal.account()
        if not konto.is_demo:
            print("FEHLGESCHLAGEN — kein Demokonto.", file=sys.stderr)
            return 2
        print(f"Terminal verbunden. Demokonto: ja. Waehrung: {konto.currency}")
        print(f"Deflation gegen T = {TRIALS} Versuche (Budgetobergrenze aus §5).")
        print()

        # --- A1.1 + A1.2 -----------------------------------------------------
        print("-" * 96)
        print("A1.1 HISTORIENTIEFE  /  A1.2 HERKUNFT")
        print("-" * 96)
        print(f"{'Symbol':<8} {'TF':<4} {'Kerzen':>8} {'von':>12} {'bis':>12} "
              f"{'Jahre':>6}  Pruefsumme")
        reihen: dict[tuple[str, str], tuple[Mt5Rate, ...]] = {}
        manifeste: list[dict[str, Any]] = []
        protokolle: list[str] = []
        for symbol in INSTRUMENTE:
            for tf, _stunden, jahre_tf in ZEITRAHMEN:
                reihe, prot = _hole(terminal, symbol, tf, jahre_tf)
                protokolle.extend(prot)
                reihen[(symbol, tf.value)] = reihe
                man = _manifest(symbol, tf, reihe)
                manifeste.append(man)
                if not reihe:
                    print(f"{symbol:<8} {tf.value:<4} {0:>8} {'-':>12} {'-':>12} "
                          f"{0:>6}  LEER NACH ZWEI VERSUCHEN")
                    continue
                jahre = (reihe[-1].ts - reihe[0].ts).days / 365.25
                print(f"{symbol:<8} {tf.value:<4} {len(reihe):>8} "
                      f"{str(reihe[0].ts.date()):>12} {str(reihe[-1].ts.date()):>12} "
                      f"{jahre:>6.1f}  {man['checksum'][:16]}...")
        print()
    finally:
        terminal.shutdown()

    MANIFESTE.mkdir(parents=True, exist_ok=True)
    for man in manifeste:
        ziel = MANIFESTE / f"{man['symbol']}_{man['timeframe']}.manifest.json"
        ziel.write_text(
            json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"{len(manifeste)} Manifeste geschrieben nach "
          f"{MANIFESTE.relative_to(REPO).as_posix()}/")
    print()

    # --- A1.3 ---------------------------------------------------------------
    print("-" * 100)
    print("A1.3 FENSTERSTREUUNG — gemessen, nicht aus dem ATR skaliert")
    print("-" * 100)
    print("Die Streuung kommt aus ALLEN nicht ueberlappenden Fenstern der Reihe.")
    print(
        "Die Ereigniszahl N kommt aus der Kandidatenfrequenz — ein taegliches Ereignis"
    )
    print("liefert je Handelstag EIN Ereignis, auch wenn der Tag sechs 4h-Fenster hat.")
    print(
        f"Gerechnet wird gegen N_defl: die Deflation der Ereignisstudie laeuft auf dem "
        f"Out-of-Sample-Anteil von {OOS_ANTEIL:.4f}, nicht auf allen Ereignissen."
    )
    print()
    print(f"{'Symbol':<8} {'Fenster':<8} {'Streuung':>10} {'Fenster':>9} {'K':>7} "
          f"{'3xK':>7}   {'Frequenz':<10} {'N':>7} {'N_defl':>7} {'nachweisb.':>11} "
          f"{'Verh.':>7}  Urteil")
    print(f"{'':<8} {'':<8} {'(bp)':>10} {'(Anz.)':>9} {'(bp)':>7} {'(bp)':>7}   "
          f"{'':<10} {'':>7} {'':>7} {'(bp)':>11}")

    eintraege: list[dict[str, Any]] = []
    for symbol in INSTRUMENTE:
        k = _kosten_bps(kosten, symbol)
        if k is None:
            print(f"{symbol:<8} — keine Kostenzeile in broker_costs.json, "
                  f"nicht bewertbar")
            continue
        for fenster_name, fenster_stunden in FENSTER:
            tf, tf_stunden = _bester_zeitrahmen(fenster_stunden)
            reihe = reihen.get((symbol, tf.value), ())
            if len(reihe) < 3:
                print(f"{symbol:<8} {fenster_name:<8} "
                      f"— Reihe {tf.value} zu kurz ({len(reihe)} Kerzen), "
                      f"nicht bewertbar")
                continue
            balken = max(1, int(round(fenster_stunden / tf_stunden)))
            closes = [float(r.close) for r in reihe]
            try:
                renditen = window_returns_bps(closes, balken)
                streu = dispersion_bps(renditen)
            except ResolutionError as exc:
                print(f"{symbol:<8} {fenster_name:<8} — {exc}")
                continue
            jahre = (reihe[-1].ts - reihe[0].ts).days / 365.25
            for freq_name, pro_jahr in FREQUENZEN:
                ereignisse = int(pro_jahr * jahre)
                if ereignisse < 2:
                    continue
                try:
                    urteil = assess(
                        events=ereignisse,
                        trials=TRIALS,
                        dispersion=streu,
                        cost_bps=k,
                        oos_share=OOS_ANTEIL,
                    )
                    # Gehoert in DENSELBEN try wie ``assess``: die Funktion rechnet mit
                    # denselben Groessen und weist an denselben Grenzen ab. Stand sie
                    # ausserhalb (sie stand es), brach ein Messlauf hier ab -- nach der
                    # gedruckten Tabelle und VOR dem Schreiben von aufloesung.json.
                    mindest = min_events_for_resolution(
                        trials=TRIALS,
                        dispersion=streu,
                        cost_bps=k,
                        oos_share=OOS_ANTEIL,
                    )
                except ResolutionError as exc:
                    print(f"{symbol:<8} {fenster_name:<8} {freq_name:<10} — {exc}")
                    continue
                marke = "AUFLOESBAR" if urteil.resolvable else "blind"
                print(f"{symbol:<8} {fenster_name:<8} {streu:>10.2f} "
                      f"{len(renditen):>9} {k:>7.2f} {urteil.needed_bps:>7.2f}   "
                      f"{freq_name:<10} {ereignisse:>7} {urteil.deflation_events:>7} "
                      f"{urteil.detectable_bps:>11.2f} {urteil.ratio:>7.2f}  {marke}")
                eintraege.append({
                    "instrument": symbol,
                    "window": fenster_name,
                    "timeframe": tf.value,
                    "series_windows": len(renditen),
                    "series_years": round(jahre, 2),
                    "frequency": freq_name,
                    "events_per_year": pro_jahr,
                    "events": ereignisse,
                    "oos_share": OOS_ANTEIL,
                    "deflation_events": urteil.deflation_events,
                    "dispersion_bps": round(streu, 4),
                    "cost_bps": round(k, 4),
                    "required_sharpe": round(urteil.required_sharpe, 6),
                    "detectable_bps": round(urteil.detectable_bps, 4),
                    "needed_bps": round(urteil.needed_bps, 4),
                    "ratio": round(urteil.ratio, 4),
                    "resolvable": urteil.resolvable,
                    "min_events_for_resolution": mindest,
                })
        print()

    aufloesbar = [e for e in eintraege if e["resolvable"]]
    print("=" * 96)
    print(f"ERGEBNIS: {len(aufloesbar)} von {len(eintraege)} Kombinationen aus "
          f"Instrument und Fensterlaenge sind aufloesbar.")
    print("=" * 96)
    for e in aufloesbar:
        print(f"  {e['instrument']:<8} {e['window']:<4} {e['frequency']:<10} "
              f"N={e['events']:<6} N_defl={e['deflation_events']:<6} "
              f"Verhaeltnis {e['ratio']}")
    print()

    dokument: dict[str, Any] = {
        # 2 (Paket 3b, E2): jede Zeile fuehrt jetzt ``oos_share`` und
        # ``deflation_events``. Eine Datei nach Schema 1 traegt Verhaeltnisse, die
        # gegen die volle Ereigniszahl gerechnet sind, und ist damit zu guenstig --
        # ``pruefen()`` faellt darauf ausdruecklich rot.
        "schema_version": 2,
        "resolution_id": RESOLUTION_POLICY_VERSION,
        "measured_on": datetime.now(UTC).date().isoformat(),
        "trials_assumed": TRIALS,
        "dsr_threshold": 0.95,
        "cost_factor": 3.0,
        "oos_share": OOS_ANTEIL,
        "note": (
            "Fensterstreuung als Standardabweichung nicht ueberlappender "
            "Fensterrenditen, gemessen ueber den lesenden MT5-Demo-Pfad. K je "
            "Instrument aus config/broker_costs.json, guenstigster Broker. Die "
            "Die Ereigniszahl N folgt aus der Kandidatenfrequenz mal der "
            "Historientiefe, NICHT aus der Zahl verfuegbarer Fenster: ein taegliches "
            "Ereignis liefert je Handelstag ein Ereignis, auch wenn der Tag sechs "
            "Vier-Stunden-Fenster enthaelt. Die Fensterzahl steht daneben und dient "
            "nur der Streuungsmessung. Gerechnet wird nicht gegen N, sondern gegen "
            "deflation_events: die Deflation der Ereignisstudie laeuft auf dem "
            "Out-of-Sample-Anteil (oos_share), und nur diese Beobachtungen sieht das "
            "Urteil, das die Aufloesungsrechnung umkehrt."
        ),
        "retrieval_log": protokolle,
        "entries": eintraege,
    }
    OUT.write_text(
        json.dumps(dokument, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Geschrieben: {OUT.relative_to(REPO).as_posix()}")
    return 0 if eintraege else 2


def _kosten_bps(kosten: Any, symbol: str) -> float | None:
    """Kleinstes K ueber alle Broker, in Basispunkten des Nominals.

    Gerechnet wird **nicht hier**, sondern in ``tools/kostentor.py::_zeile`` — derselben
    Funktion, die das Kostentor aus Paket 2 fuehrt. Der erste Entwurf dieser Funktion
    hat die Formel nachgebaut und dabei die Waehrungsumrechnung der Kommission
    vergessen: bei GBPJPY steht das Nominal in JPY und die Kommission in USD, und ohne
    ``_fx`` fiel sie von 0,44 auf 0,003 bp. K sank von 1,75 auf 1,31 bp, und weil ein
    kleineres K die nachzuweisende Wirkung (3 x K) senkt, kippte allein dadurch eine
    Kandidatenzeile auf „blind". Eine zweite Umsetzung derselben Rechnung ist eine
    zweite Fehlerquelle; die einzige Fassung, die zaehlt, steht im Kostentor.
    """
    from tools.kostentor import _zeile, lade

    _, messungen, kurse = lade()
    messung = messungen.get(symbol)
    if messung is None or not messung.measured:
        return None
    bester: float | None = None
    for broker_key, broker in kosten.brokers.items():
        zeile = _zeile(
            symbol,
            broker_key,
            broker.instruments.get(symbol),
            messung,
            kosten.slippage_bps,
            kurse,
        )
        if not zeile.rechenbar or zeile.k_bps is None:
            continue
        k = float(zeile.k_bps)
        if bester is None or k < bester:
            bester = k
    return bester


def _bester_zeitrahmen(fenster_stunden: float) -> tuple[Timeframe, float]:
    """Der Zeitrahmen mit der tiefsten Historie fuer dieses Fenster.

    H1 reicht nur zwoelf Monate zurueck, H4 rund 25 Jahre. Fuer ein Ein-Stunden-Fenster
    gibt es keine Wahl; fuer alles ab vier Stunden ist H4 die tiefere Reihe.
    """
    if fenster_stunden < 4.0:
        return Timeframe.H1, 1.0
    return Timeframe.H4, 4.0


def gegenprobe(csv_pfad: Path, *, schwelle: float = 2.0) -> int:
    """A1.2: Terminal-Feed gegen eine zweite Quelle halten (Dukascopy).

    Verglichen werden **Renditen**, nicht Kursstaende: liegt zwischen den Quellen ein
    Zeitversatz, laufen schon die Kursstaende auseinander, ohne dass der Feed schlechter
    waere. Die Rendite ueber dieselbe Periode beantwortet die Frage, auf die es ankommt:
    erzaehlen beide Quellen dieselbe Geschichte?

    Der Zeitrahmen kommt aus dem Dateinamen (``EURUSD_H1.csv``). Bei H1 wird zusaetzlich
    der **Serverzeit-Versatz** gemessen, indem die Abweichung ueber ganze Stunden-
    verschiebungen abgetastet wird — ein unbemerkter Versatz von einer Stunde wuerde
    jede 1h-Fensterstudie wertlos machen, und er faellt hier als Minimum auf.

    Schwelle aus dem Auftrag: Median ueber 2 bp -> der Terminal-Feed ist fuer diese
    Studie nicht brauchbar.
    """
    import csv
    import statistics

    if not csv_pfad.is_file():
        print(f"FEHLGESCHLAGEN — {csv_pfad} fehlt.", file=sys.stderr)
        return 1
    teile = csv_pfad.stem.split("_")
    if len(teile) != 2:
        print(f"FEHLGESCHLAGEN — {csv_pfad.name} ist nicht SYMBOL_ZEITRAHMEN.csv",
              file=sys.stderr)
        return 1
    symbol, tf_name = teile[0], teile[1].upper()
    try:
        tf = Timeframe(tf_name)
    except ValueError:
        print(f"FEHLGESCHLAGEN — unbekannter Zeitrahmen {tf_name}", file=sys.stderr)
        return 1

    fremd: dict[datetime, float] = {}
    with csv_pfad.open(encoding="utf-8", newline="") as fh:
        for zeile in csv.DictReader(fh):
            fremd[datetime.fromisoformat(zeile["ts"])] = float(zeile["close"])
    if len(fremd) < 30:
        print(f"FEHLGESCHLAGEN — nur {len(fremd)} Fremdkerzen.", file=sys.stderr)
        return 1

    terminal = RealMt5Terminal(allow_write=False)
    if not terminal.initialize():
        print("FEHLGESCHLAGEN — Terminal nicht erreichbar.", file=sys.stderr)
        return 2
    try:
        beginn = min(fremd) - timedelta(days=3)
        ende = max(fremd) + timedelta(days=3)
        roh = terminal.rates(symbol, tf, beginn, ende)
        # Diese Stelle ist die weniger ausgesetzte der beiden: ``ende`` kommt aus der
        # Fremddatei, nicht aus ``jetzt``. Reicht die Vergleichsdatei aber bis heute,
        # liegt die Grenze in der Zukunft und die laufende Kerze kaeme mit -- und
        # verglichen wuerde ein Momentankurs gegen einen Schlusskurs. Dieselbe Regel
        # wie oben, damit sie nicht an vier von fuenf Stellen gilt.
        tick = terminal.tick(symbol)
        if tick is None:
            print(
                f"FEHLGESCHLAGEN — kein Tick fuer {symbol}: ohne Platzzeit ist nicht "
                "entscheidbar, welche Kerze abgeschlossen ist.",
                file=sys.stderr,
            )
            return 2
        reihe = tuple(r for r in roh if ist_abgeschlossen(r.ts, tf, tick.ts))
    finally:
        terminal.shutdown()
    eigen = {r.ts: float(r.close) for r in reihe}
    print(f"Gegenprobe {symbol} {tf_name}: {len(fremd)} Fremd-, "
          f"{len(eigen)} Eigenkerzen")

    def abweichung(versatz_h: int) -> tuple[float, float, float, int]:
        verschoben = {ts + timedelta(hours=versatz_h): k for ts, k in eigen.items()}
        gemeinsam = sorted(set(fremd) & set(verschoben))
        werte = [
            abs(
                (fremd[b] - fremd[a]) / fremd[a] * 10_000
                - (verschoben[b] - verschoben[a]) / verschoben[a] * 10_000
            )
            for a, b in zip(gemeinsam, gemeinsam[1:], strict=False)
            if (b - a) <= timedelta(days=4)
        ]
        if len(werte) < 30:
            return (float("inf"), float("inf"), float("inf"), len(werte))
        return (statistics.median(werte), statistics.fmean(werte),
                max(werte), len(werte))

    versaetze = range(-4, 5) if tf is not Timeframe.D1 else (0,)
    ergebnisse = {v: abweichung(v) for v in versaetze}
    bester = min(ergebnisse, key=lambda v: ergebnisse[v][0])
    if len(ergebnisse) > 1:
        print("  Serverzeit-Versatz abgetastet (Median-Abweichung je Verschiebung):")
        for v in sorted(ergebnisse):
            med = ergebnisse[v][0]
            marke = "  <- Minimum" if v == bester else ""
            zahl = f"{med:8.2f} bp" if med != float("inf") else "  zu wenige"
            print(f"    {v:+d} h: {zahl}{marke}")
        if bester != 0:
            print(f"  BEFUND: der Terminal-Feed liegt {bester:+d} h gegen UTC. "
                  "Jede 1h-Fensterstudie auf ungedrehten Zeitstempeln waere falsch.")
        else:
            print("  Serverzeit-Versatz gegen UTC: 0 h — Zeitstempel decken sich.")

    median, mittel, groesste, n = ergebnisse[bester]
    if median == float("inf"):
        print("FEHLGESCHLAGEN — zu wenige gemeinsame Perioden.", file=sys.stderr)
        return 1
    print(f"  Renditeabweichung bei {bester:+d} h: Median {median:.2f} bp | "
          f"Mittel {mittel:.2f} bp | max {groesste:.2f} bp  (n={n})")
    if median > schwelle:
        print(f"  URTEIL: ueber der Schwelle von {schwelle} bp — der Terminal-Feed ist "
              f"fuer {symbol} auf {tf_name} NICHT brauchbar.")
        return 1
    print(f"  URTEIL: unter der Schwelle von {schwelle} bp — brauchbar.")
    return 0


def _kennung(e: Any) -> str:
    """Wie eine Zeile in einer Fehlermeldung heisst -- auch wenn sie kaputt ist."""
    if not isinstance(e, dict):
        return f"Eintrag {e!r}"
    return f"{e.get('instrument')}/{e.get('window')}/{e.get('frequency')}"


def _datei_anteil(roh: dict[str, Any]) -> float | None:
    """Der Out-of-Sample-Anteil, den die Datei fuehrt -- ``None``, wenn keiner taugt.

    ``bool`` wird ausdruecklich abgewiesen: in Python ist ``True`` ein ``int``, und
    ``"oos_share": true`` waere sonst klaglos 1,0.
    """
    wert = roh.get("oos_share")
    if isinstance(wert, bool) or not isinstance(wert, int | float):
        return None
    return float(wert)


def _zeilenfelder(
    e: dict[str, Any], nach: ResolutionVerdict, *, anteil: float, schema: Any
) -> list[str]:
    """Die uebrigen Felder der Zeile gegen den Kopf und gegen die Rechnung halten.

    ``pruefen()`` hat frueher nur ``ratio`` und ``resolvable`` nachgerechnet. Die von
    ``messen()`` je Zeile geschriebenen ``oos_share`` und ``deflation_events`` blieben
    ungelesen -- eine Datei, deren Zeilen ihrem eigenen Kopf widersprechen, kam gruen
    durch, und welche der beiden Zahlen die gedruckte war, stand nirgends. Dasselbe galt
    fuer die drei abgeleiteten Groessen: ein Verhaeltnis kann stimmen, waehrend der
    daneben gedruckte nachweisbare Effekt aus einer anderen Rechnung stammt.
    """
    out: list[str] = []
    for feld, nachgerechnet in (
        ("required_sharpe", nach.required_sharpe),
        ("detectable_bps", nach.detectable_bps),
        ("needed_bps", nach.needed_bps),
    ):
        if feld not in e:
            continue
        zahl = e[feld]
        if isinstance(zahl, bool) or not isinstance(zahl, int | float):
            out.append(f"{_kennung(e)}: {feld} ist keine Zahl: {zahl!r}")
        elif abs(float(zahl) - nachgerechnet) > 1e-3:
            out.append(
                f"{_kennung(e)}: Zeile fuehrt {feld} {zahl}, nachgerechnet "
                f"{nachgerechnet:.4f}"
            )
    pflicht = isinstance(schema, int) and not isinstance(schema, bool) and schema >= 2
    if "oos_share" in e:
        wert = e["oos_share"]
        untauglich = isinstance(wert, bool) or not isinstance(wert, int | float)
        if untauglich or abs(float(wert) - anteil) > OOS_TOLERANZ:
            out.append(
                f"{_kennung(e)}: Zeile fuehrt oos_share {wert!r}, der Kopf {anteil}"
            )
    elif pflicht:
        out.append(f"{_kennung(e)}: Schema {schema} verlangt oos_share je Zeile")
    if "deflation_events" in e:
        if e["deflation_events"] != nach.deflation_events:
            out.append(
                f"{_kennung(e)}: Zeile fuehrt deflation_events "
                f"{e['deflation_events']!r}, nachgerechnet {nach.deflation_events}"
            )
    elif pflicht:
        out.append(f"{_kennung(e)}: Schema {schema} verlangt deflation_events je Zeile")
    return out


def pruefen(pfad: Path | None = None) -> int:
    """Die abgelegte Messdatei nachrechnen -- ohne MT5, aber mit Urteil.

    Diese Pruefung hat frueher nur gezaehlt, ob ueberhaupt Eintraege dastehen. Damit war
    sie eine Ampel, die nicht rot werden konnte: eine Datei mit falschen Verhaeltnissen
    haette sie genauso bestanden wie eine richtige -- und genau das ist passiert. Die
    abgelegten Verhaeltnisse waren gegen die volle Ereigniszahl gerechnet, obwohl die
    Deflation nur das Out-of-Sample-Drittel sieht.

    Jetzt wird jede Zeile mit ``resolution.assess`` nachgerechnet. Nachgerechnet, nicht
    nachgebaut: es ist dasselbe Modul, das die Datei erzeugt hat, und ein Auseinander-
    laufen kann nur noch heissen, dass die Datei aelter ist als das Modul.

    ZWEI EIGENE FEHLER DIESER FUNKTION, BEHOBEN
    -------------------------------------------
    (1) Die zweite Fassung fragte ``"oos_share" not in roh`` -- also die ANWESENHEIT
    eines Schluessels statt seinen WERT. Wer der falsch gerechneten Datei die eine
    Zeile ``"oos_share": 1.0`` nachtrug, drehte diese Pruefung von rot auf gruen, ohne
    dass eine einzige Zahl neu gemessen worden waere. Das ist wortwoertlich die
    Fehlerklasse, gegen die diese Pruefung gebaut wurde: ein Melder, der das Falsche
    misst. Verglichen wird deshalb gegen ``OOS_ANTEIL`` -- den Anteil, auf dem die
    Deflation tatsaechlich laeuft.

    (2) Im Fehlschlag stand die gruene Zeile „ok — ... aufloesbar" samt Tabelle auf
    stdout und der Befund erst danach auf stderr. Wer die Ausgabe ueberflog oder stderr
    verwarf, las Gruen ueber falschen Zahlen. Es gilt jetzt: **kein Wort auf stdout,
    solange die Datei nicht durch ist.**
    """
    ziel = OUT if pfad is None else pfad
    if not ziel.is_file():
        print(f"FEHLGESCHLAGEN — {ziel.name} fehlt.", file=sys.stderr)
        return 1
    roh = json.loads(ziel.read_text(encoding="utf-8"))
    eintraege = roh.get("entries", [])
    if not eintraege:
        print("FEHLGESCHLAGEN — Datei ohne Eintraege.", file=sys.stderr)
        return 1

    trials = roh.get("trials_assumed")
    if not isinstance(trials, int) or isinstance(trials, bool):
        print(f"FEHLGESCHLAGEN — {ziel.name} ohne trials_assumed.", file=sys.stderr)
        return 1

    datei_anteil = _datei_anteil(roh)
    if datei_anteil is None:
        # Kein brauchbarer Anteil: die Datei stammt aus der Zeit vor der Korrektur. Sie
        # wird so nachgerechnet, wie sie entstanden ist (voller Anteil) -- damit ihre
        # Zahlen erklaerbar bleiben -- und faellt trotzdem, mit der Liste der Zeilen,
        # die bei richtiger Rechnung kippen.
        anteil = 1.0
        beanstandung = [
            f"FEHLGESCHLAGEN — {ziel.name} fuehrt kein brauchbares oos_share und ist "
            "damit gegen die VOLLE Ereigniszahl gerechnet.",
            "Die Deflation der Ereignisstudie sieht nur das Out-of-Sample-Drittel; "
            "die Verhaeltnisse der Datei sind rund Faktor 1,7 zu guenstig.",
        ]
    elif abs(datei_anteil - OOS_ANTEIL) > OOS_TOLERANZ:
        anteil = datei_anteil
        beanstandung = [
            f"FEHLGESCHLAGEN — {ziel.name} fuehrt oos_share = {datei_anteil}, die "
            f"Deflation der Ereignisstudie laeuft aber auf {OOS_ANTEIL}.",
            "Die Verhaeltnisse sind damit gegen eine Stichprobe gerechnet, die das "
            "Urteil nie sieht. Ein nachgetragener Schluessel ist keine Messung.",
        ]
    else:
        anteil = datei_anteil
        beanstandung = []

    schema = roh.get("schema_version")
    abweichungen: list[str] = []
    for e in eintraege:
        if not isinstance(e, dict):
            abweichungen.append(f"{_kennung(e)}: kein Objekt, nicht nachrechenbar")
            continue
        try:
            nach = assess(
                events=int(e["events"]),
                trials=trials,
                dispersion=float(e["dispersion_bps"]),
                cost_bps=float(e["cost_bps"]),
                oos_share=anteil,
            )
            # Diese beiden Zeilen standen frueher AUSSERHALB des ``try``. Eine Datei
            # ohne ``ratio`` liess ``pruefen()`` mit KeyError abstuerzen, statt 1 zu
            # melden -- ein Tor, das nicht rot wird, sondern zerbricht.
            datei_verhaeltnis = float(e["ratio"])
            datei_urteil = bool(e["resolvable"])
        except (ResolutionError, KeyError, TypeError, ValueError) as exc:
            abweichungen.append(f"{_kennung(e)}: nicht nachrechenbar — {exc}")
            continue
        if abs(nach.ratio - datei_verhaeltnis) > 1e-3:
            abweichungen.append(
                f"{_kennung(e)}: Datei sagt {datei_verhaeltnis}, nachgerechnet "
                f"{nach.ratio:.4f}"
            )
        elif datei_urteil != nach.resolvable:
            abweichungen.append(
                f"{_kennung(e)}: Urteil in der Datei {datei_urteil}, nachgerechnet "
                f"{nach.resolvable}"
            )
        abweichungen.extend(_zeilenfelder(e, nach, anteil=anteil, schema=schema))

    if abweichungen:
        print(f"FEHLGESCHLAGEN — {len(abweichungen)} Zeile(n) rechnen sich nicht nach:",
              file=sys.stderr)
        for zeile in abweichungen:
            print(f"  {zeile}", file=sys.stderr)
        return 1

    if beanstandung:
        for zeile in beanstandung:
            print(zeile, file=sys.stderr)
        for zeile in _korrigiert(eintraege, trials):
            print(f"  {zeile}", file=sys.stderr)
        print("Abhilfe: `python tools/aufloesung.py` neu messen (braucht MT5).",
              file=sys.stderr)
        return 1

    aufloesbar = [e for e in eintraege if e.get("resolvable")]
    print(f"ok — {ziel.name} nachgerechnet: {len(aufloesbar)} von {len(eintraege)} "
          f"Kombinationen aufloesbar (T = {trials}, Out-of-Sample-Anteil {anteil}).")
    for e in aufloesbar:
        print(f"  {e['instrument']:<8} {e['window']:<4} {e['frequency']:<10} "
              f"N={e['events']:<6} Verhaeltnis {e['ratio']}")
    return 0


def _korrigiert(eintraege: list[dict[str, Any]], trials: int) -> list[str]:
    """Welche Zeilen einer Schema-1-Datei ihr Urteil wechseln, wenn richtig gerechnet.

    Steht getrennt, weil diese Liste der eigentliche Befund ist und nicht in einer
    Fehlermeldung untergehen soll.

    Unlesbare Zeilen werden hier uebersprungen und nicht gemeldet -- sie sind an dieser
    Stelle schon gemeldet: ``pruefen()`` kommt nur hierher, wenn sich zuvor JEDE Zeile
    nachrechnen liess. Der ganze Rumpf steht deshalb im ``try``; frueher lagen der
    Vergleich und die Ausgabezeile davor und konnten mit KeyError abstuerzen.
    """
    out: list[str] = []
    for e in eintraege:
        try:
            nach = assess(
                events=int(e["events"]),
                trials=trials,
                dispersion=float(e["dispersion_bps"]),
                cost_bps=float(e["cost_bps"]),
                oos_share=OOS_ANTEIL,
            )
            if nach.resolvable == bool(e["resolvable"]):
                continue
            zeile = (
                f"{e['instrument']:<8} {e['window']:<4} {e['frequency']:<10} "
                f"N={e['events']:<6} N_defl="
                f"{deflation_observations(int(e['events']), oos_share=OOS_ANTEIL):<6} "
                f"{e['ratio']} -> {nach.ratio:.4f}  "
                f"{'aufloesbar' if e['resolvable'] else 'blind'} -> "
                f"{'aufloesbar' if nach.resolvable else 'blind'}"
            )
        except (ResolutionError, KeyError, TypeError, ValueError):
            continue
        out.append(zeile)
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="A1: Historientiefe, Herkunft und Fensterstreuung messen."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="die vorhandene Datei Zeile fuer Zeile nachrechnen (ohne MT5)",
    )
    parser.add_argument(
        "--gegenprobe",
        type=Path,
        default=None,
        metavar="CSV",
        help="Terminal-Feed gegen eine Dukascopy-CSV halten (A1.2)",
    )
    args = parser.parse_args()
    if args.gegenprobe is not None:
        return gegenprobe(args.gegenprobe)
    return pruefen() if args.check else messen()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Ereignisstudie je Kandidat (Paket 3a, A3).

Zwei Betriebsarten:

``--selbsttest``
    Rechnet gegen eine eingebaute synthetische Reihe mit **bekanntem** Effekt und
    registriert **keinen** Versuch. Nur diese Betriebsart laeuft im Pruefstand: liefe
    dort die echte Studie, schriebe jeder CI-Lauf einen Versuch ins anhaengende Register
    und triebe die Deflationshuerde mit der Zahl der CI-Laeufe nach oben.

ohne Schalter
    Die echten Studien. Jede verbraucht einen Versuch und wird in ``gates/trials.py``
    eingetragen — **auch wenn sie scheitert**. Das ist der Sinn der Regel: ein Versuch
    ist verbraucht, sobald gemessen wurde, nicht erst, wenn das Ergebnis gefaellt.

ZUR REGISTRIERUNG „VOR DEM LAUF"
---------------------------------
Der Auftrag verlangt die Eintragung vor der Messung. Das Register kennt aber nur
abgeschlossene Zustaende (``completed``/``aborted``/``error``) und ist anhaengend — ein
Eintrag „laeuft gerade", der spaeter berichtigt wird, ist darin nicht vorgesehen.
Umgesetzt ist deshalb die Substanz der Regel: alles, was den Versuch ausmacht — Fenster,
Vorzeichenregel, Instrument, Zeitraum, ``data_checksum``, ``code_commit`` — wird **vor**
der Messung festgezurrt und ausgegeben; der Eintrag folgt unmittelbar danach und in
jedem Ausgang. Was die Regel verhindern soll, ist damit verhindert: es gibt keinen
Weg, erst zu messen und dann zu entscheiden, ob der Versuch zaehlt.

Aufruf:
  python tools/ereignisstudie.py --selbsttest
  python tools/ereignisstudie.py --kandidat K1 --instrument EURUSD
  python tools/ereignisstudie.py --alle
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.ereignisstudie import (  # noqa: E402
    HYPOTHESE,
    STUDY_POLICY_VERSION,
    Bestaetigung,
    Ergebnis,
    Kerze,
    StudienError,
    bestaetige,
    studie,
)
from mt5_trading_ai.backtest.kalender import (  # noqa: E402
    KANDIDATEN,
    Kandidat,
    ereignisse,
    kandidat,
    load_ereigniskalender,
    server_zu_utc,
)
from mt5_trading_ai.costs.broker_costs import load_broker_costs  # noqa: E402
from mt5_trading_ai.gates.trials import append, new_trial  # noqa: E402
from mt5_trading_ai.venue.mt5 import RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import Timeframe  # noqa: E402

from tools.aufloesung import _kosten_bps  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
MANIFESTE = REPO / "config" / "reihen"
#: Saat der Randomisierung. Fest, damit derselbe Lauf dieselbe Zahl liefert -- eine
#: Zufallsprobe, die sich bei jedem Aufruf aendert, laedt zum Wiederholen ein.
SAAT = 20260817


def _code_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StudienError(f"code_commit nicht bestimmbar: {exc}") from exc


def _data_checksum(symbol: str) -> str:
    pfad = MANIFESTE / f"{symbol}_H1.manifest.json"
    if not pfad.is_file():
        raise StudienError(
            f"{pfad} fehlt — ohne Herkunft zaehlt eine Studie nach der eigenen Regel "
            "des Repos nicht. Erst `python tools/aufloesung.py` laufen lassen."
        )
    return str(json.loads(pfad.read_text(encoding="utf-8"))["checksum"])


def _lade_kerzen(symbol: str) -> list[Kerze]:
    """Stundenkerzen aus dem Terminal, Zeitstempel in ECHTES UTC gedreht."""
    terminal = RealMt5Terminal(allow_write=False)
    if not terminal.initialize():
        raise StudienError("Terminal nicht erreichbar")
    try:
        ende = datetime.now(UTC)
        roh: dict[datetime, Kerze] = {}
        scheibe_ende = ende
        for _ in range(9):  # 45 Jahre in Fuenfjahresscheiben, wie in aufloesung.py
            scheibe_start = scheibe_ende - timedelta(days=365 * 5)
            reihe = terminal.rates(symbol, Timeframe.H1, scheibe_start, scheibe_ende)
            for r in reihe:
                echt = server_zu_utc(r.ts)
                roh[echt] = Kerze(ts=echt, open=float(r.open), close=float(r.close))
            scheibe_ende = scheibe_start
    finally:
        terminal.shutdown()
    return [roh[ts] for ts in sorted(roh)]


def _synthetisch() -> tuple[list[Kerze], list[datetime]]:
    """Eine Reihe mit BEKANNTEM Umkehreffekt: 12 bp, jeden Werktag um 16:00 UTC.

    Gebaut wird eine Vorstunde mit wechselnder Richtung und eine Fensterstunde, die
    genau dagegen laeuft. Der Selbsttest prueft, dass die Studie diesen Effekt findet
    und **mit dem richtigen Vorzeichen** — ein Vorzeichenfehler waere der Fehler, den
    man einer einzelnen Zahl am wenigsten ansieht.
    """
    kerzen: list[Kerze] = []
    termine: list[datetime] = []
    kurs = 100.0
    start = datetime(2015, 1, 1, tzinfo=UTC)
    for tag in range(1400):
        stempel_tag = start + timedelta(days=tag)
        if stempel_tag.weekday() >= 5:
            continue
        for stunde in range(24):
            ts = stempel_tag.replace(hour=stunde)
            if stunde == 15:  # Vorstunde: abwechselnd hoch und runter
                richtung = 1.0 if tag % 2 == 0 else -1.0
                schluss = kurs * (1 + richtung * 20e-4)
            elif stunde == 16:  # Fensterstunde: 12 bp GEGEN die Vorstunde
                richtung = -1.0 if tag % 2 == 0 else 1.0
                schluss = kurs * (1 + richtung * 12e-4)
                termine.append(ts)
            else:  # Rauschen ohne Drift, deterministisch
                schluss = kurs * (1 + math.sin(tag * 7 + stunde) * 3e-4)
            kerzen.append(Kerze(ts=ts, open=kurs, close=schluss))
            kurs = schluss
    return kerzen, termine


def selbsttest() -> int:
    print("=" * 90)
    print("SELBSTTEST — synthetische Reihe mit bekanntem Effekt, KEIN Versuch")
    print("=" * 90)
    kerzen, termine = _synthetisch()
    erwartet = 12.0
    erg, werte = studie(
        kandidat="SELBSTTEST", instrument="SYNTH", kerzen=kerzen,
        ereignisse=termine, fenster_stunden=1.0, k_bps=1.0,
    )
    print(f"Kerzen {len(kerzen)} | Ereignisse {len(termine)} | "
          f"gemessen {erg.n_gemessen}")
    print(f"Erwarteter Effekt      : {erwartet:.2f} bp")
    print(f"Gemessener Bruttoeffekt: {erg.brutto_bps:.2f} bp")
    print(f"Trefferanteil          : {erg.trefferanteil * 100:.1f} %")
    print(f"Netto (K = 1,00 bp)    : {erg.netto_bps:.2f} bp")
    abweichung = abs(erg.brutto_bps - erwartet)
    if abweichung > 0.5:
        print(f"\nFEHLGESCHLAGEN — {abweichung:.2f} bp neben dem Ziel.",
              file=sys.stderr)
        return 1
    if erg.trefferanteil < 0.95:
        print(f"\nFEHLGESCHLAGEN — Trefferanteil {erg.trefferanteil:.2f} zu niedrig; "
              "bei einem so klaren Effekt muss fast jedes Ereignis treffen.",
              file=sys.stderr)
        return 1

    # Gegenprobe: dieselbe Reihe OHNE Ereignisse an den richtigen Stellen darf nichts
    # finden. Ohne sie wuerde der Selbsttest auch bestehen, wenn die Studie einfach
    # immer 12 bp meldet.
    versetzt = [t + timedelta(hours=3) for t in termine]
    leer, _ = studie(
        kandidat="SELBSTTEST-PLACEBO", instrument="SYNTH", kerzen=kerzen,
        ereignisse=versetzt, fenster_stunden=1.0, k_bps=1.0,
    )
    print(f"Gegenprobe (Fenster 3 h versetzt): {leer.brutto_bps:.2f} bp")
    if abs(leer.brutto_bps) > 2.0:
        print(f"\nFEHLGESCHLAGEN — die Gegenprobe findet {leer.brutto_bps:.2f} bp, "
              "wo nichts sein darf.", file=sys.stderr)
        return 1
    print("\nBESTANDEN — Effekt und Vorzeichen richtig, Gegenprobe leer. "
          "Kein Versuch registriert.")
    return 0


def _lauf(k: Kandidat, symbol: str, kerzen: list[Kerze], kosten: Any) -> int:
    k_bps = _kosten_bps(kosten, symbol)
    if k_bps is None:
        print(f"{k.schluessel}/{symbol}: keine Kostenzeile — nicht bewertbar")
        return 1
    termine = list(
        ereignisse(k, kerzen[0].ts.date(), kerzen[-1].ts.date())
    )
    pruefsumme = _data_checksum(symbol)
    commit = _code_commit()

    print("-" * 90)
    print(f"{k.schluessel} — {k.name} — {symbol}")
    print("-" * 90)
    print("VOR DER MESSUNG festgezurrt:")
    print(f"  Hypothese      : {HYPOTHESE} (Vorzeichen = -sign(Rendite der Vorstunde))")
    print(f"  Fenster        : {k.fenster_stunden:.0f} h ab dem ersten handelbaren "
          f"Kerzenanfang")
    print(f"  Zeitpunkt      : {k.uhrzeit.isoformat(timespec='minutes')} {k.zone_name}")
    print(f"  Zeitraum       : {kerzen[0].ts.date()} .. {kerzen[-1].ts.date()}")
    print(f"  Ereignisse     : {len(termine)}")
    print(f"  K (guenstigster Broker): {k_bps:.2f} bp | M6.1-Schwelle {3*k_bps:.2f} bp")
    print(f"  data_checksum  : {pruefsumme[:16]}...")
    print(f"  code_commit    : {commit[:12]}")

    ausgang, erg, best = "error", None, None
    try:
        erg, werte = studie(
            kandidat=k.schluessel, instrument=symbol, kerzen=kerzen,
            ereignisse=termine, fenster_stunden=k.fenster_stunden, k_bps=k_bps,
        )
        best = bestaetige(
            werte, kerzen=kerzen, ereignisse=termine,
            fenster_stunden=k.fenster_stunden, k_bps=k_bps, saat=SAAT,
        )
        ausgang = "completed"
    except StudienError as exc:
        print(f"\n  ABGEBROCHEN: {exc}")
        ausgang = "aborted"
    finally:
        append(new_trial(
            strategy_id=f"ereignisstudie/{k.schluessel}",
            version=STUDY_POLICY_VERSION,
            instruments=[symbol],
            period_start=kerzen[0].ts,
            period_end=kerzen[-1].ts,
            leverage=1,
            parameters={
                "hypothese": HYPOTHESE,
                "fenster_stunden": k.fenster_stunden,
                "uhrzeit": k.uhrzeit.isoformat(timespec="minutes"),
                "zone": k.zone_name,
                "regel": k.regel,
                "k_bps": round(k_bps, 4),
                "ereignisse_geplant": len(termine),
            },
            outcome=ausgang,
            data_checksum=pruefsumme,
            code_commit=commit,
            net_expectancy=None if erg is None else round(erg.netto_bps, 4),
            trades=None if erg is None else erg.n_gemessen,
            notes=f"Paket 3a A3, {k.name}",
        ))
    if erg is None or best is None:
        return 1
    _bericht(erg, best)
    return 0


def _bericht(e: Ergebnis, b: Bestaetigung) -> None:
    print("\nERGEBNIS")
    print(f"  gemessene Ereignisse : {e.n_gemessen} von {e.n_ereignisse}")
    print(f"  Bruttoeffekt (Median): {e.brutto_bps:+.2f} bp")
    print(f"  Streuung (25 %/75 %) : {e.p25_bps:+.2f} / {e.p75_bps:+.2f} bp")
    print(f"  Trefferanteil        : {e.trefferanteil * 100:.1f} %")
    print(f"  Kosten K             : {e.k_bps:.2f} bp")
    print(f"  NETTOEFFEKT          : {e.netto_bps:+.2f} bp")
    print(f"\n  M6.1 (Brutto >= {e.m61_schwelle_bps:.2f} bp): "
          f"{'BESTANDEN' if e.m61_bestanden else 'GESCHEITERT'}")
    print(f"  M6.2 Deflation   : DSR {b.dsr_oos:.3f} auf {b.dsr_n} OoS-Ereignissen "
          f"-> {'ok' if b.dsr_bestanden else 'gescheitert'}")
    print(f"  M6.2 Stabilitaet : {b.haelfte_frueh_bps:+.2f} / "
          f"{b.haelfte_spaet_bps:+.2f} bp -> "
          f"{'ok' if b.stabil_bestanden else 'gescheitert'}")
    print(f"  M6.2 Zufall      : {b.zufall_anteil * 100:.1f} % der 1.000 verschobenen "
          f"Mengen -> {'ok' if b.zufall_bestanden else 'gescheitert'}")
    urteil = "BESTANDEN" if (e.m61_bestanden and b.bestanden) else "GESCHEITERT"
    print(f"\n  URTEIL M6: {urteil}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Ereignisstudie (Paket 3a)")
    p.add_argument("--selbsttest", action="store_true",
                   help="synthetische Reihe, registriert KEINEN Versuch")
    p.add_argument("--kandidat", default=None)
    p.add_argument("--instrument", default=None)
    p.add_argument("--alle", action="store_true", help="alle Kandidaten des Feldes")
    args = p.parse_args()

    if args.selbsttest:
        return selbsttest()

    load_ereigniskalender()  # fail-closed: laedt nicht, wenn Datei und Code abweichen
    kosten = load_broker_costs()
    paare: list[tuple[Kandidat, str]] = []
    if args.alle:
        paare = [(k, s) for k in KANDIDATEN for s in k.instrumente]
    elif args.kandidat and args.instrument:
        paare = [(kandidat(args.kandidat), args.instrument)]
    else:
        p.error("--selbsttest, --alle oder --kandidat mit --instrument")

    print(f"Ereignisstudie {STUDY_POLICY_VERSION} — {len(paare)} Studien, "
          f"jede verbraucht einen Versuch")
    reihen: dict[str, list[Kerze]] = {}
    schlecht = 0
    for k, symbol in paare:
        if symbol not in reihen:
            reihen[symbol] = _lade_kerzen(symbol)
        schlecht += _lauf(k, symbol, reihen[symbol], kosten)
        print()
    return 1 if schlecht == len(paare) else 0


if __name__ == "__main__":
    sys.exit(main())

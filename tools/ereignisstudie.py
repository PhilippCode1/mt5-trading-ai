#!/usr/bin/env python3
"""Ereignisstudie je Kandidat (Paket 3a, A3).

Zwei Betriebsarten:

``--selbsttest``
    Rechnet gegen eine eingebaute synthetische Reihe mit **bekanntem** Effekt und
    registriert **keinen** Versuch. Nur diese Betriebsart laeuft im Pruefstand: liefe
    dort die echte Studie, schriebe jeder CI-Lauf einen Versuch ins anhaengende Register
    und triebe die Deflationshuerde mit der Zahl der CI-Laeufe nach oben.

    Sie laeuft dort auch tatsaechlich — als Fall in
    ``tests/test_ereignisstudie_werkzeug.py``, samt drei absichtlich verfaelschten
    Messungen, die sie faengt. Vorher stand sie nur in dieser Aufrufzeile und in keiner
    CI-Stufe; ein Waechter, den niemand faehrt, ist Dokumentation.

ohne Schalter
    Die echten Studien. Jede verbraucht einen Versuch und wird in ``gates/trials.py``
    eingetragen — **auch wenn sie scheitert**. Das ist der Sinn der Regel: ein Versuch
    ist verbraucht, sobald gemessen wurde, nicht erst, wenn das Ergebnis gefaellt.

    Voraussetzung: das Register muss **dastehen**. Es wird hier nie angelegt, auch
    nicht im ``finally``-Block — warum, steht bei :func:`verlange_register`.

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

DER EINGEFRORENE ABZUG IST AELTER ALS DIESES WERKZEUG
------------------------------------------------------
``ABSCHLUSS-3a/07-AUSGABEN/ereignisstudie.txt`` ist mit dem Werkzeugstand
``a9ed7ad57dac`` erzeugt worden und laesst sich mit dem heutigen nicht mehr Zeile fuer
Zeile nachbauen: die Deflation zaehlt seit Welle 1b in ganzen Kampagnen statt
Registerzeilen, und die Berichtszeile nennt die Versuchszahl seitdem mit. Das ist eine
gewollte Verschaerfung, keine Drift. Der Abzug traegt darum einen Kopf, der den
Werkzeugstand nennt; was sich geaendert hat und warum nicht neu gemessen wird, steht in
``ABSCHLUSS-3a/04-EREIGNISSTUDIE.md``, Abschnitt 6. Wer hier etwas an der Ausgabe
aendert, zieht diesen Abschnitt mit nach -- ein Beleg, den sein eigenes Werkzeug
stillschweigend nicht mehr erzeugt, ist keiner.

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

#: Als MODUL eingebunden, nicht als Namensliste: ``M61_FAKTOR`` wird unten fuer die
#: Vorregistrierung gebraucht, und ``from ... import M61_FAKTOR`` bindet eine Kopie.
#: Eine Kopie laeuft von ihrem Original weg, sobald jemand am Original dreht -- und der
#: gedruckte Schwellenwert stuende dann neben dem, gegen den tatsaechlich geprueft wird.
from mt5_trading_ai.backtest import ereignisstudie as kern  # noqa: E402
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
from mt5_trading_ai.gates.trials import (  # noqa: E402
    append,
    default_ledger_path,
    new_trial,
)
from mt5_trading_ai.venue.mt5 import RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    Timeframe,
    ist_abgeschlossen,
)

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


def verlange_register(pfad: Path | str | None = None) -> Path:
    """Das Register muss VOR der Messung dastehen — angelegt wird es hier nie.

    ``gates/trials.py::deflation_trials`` wirft bei fehlendem Register, weil eine
    Deflation gegen eine unbekannte Versuchszahl keine ist. ``append`` dagegen legt die
    Datei an (Modus ``"a"``), und ueber diesen Weg liess sich die Sperre bisher von der
    Werkzeugseite her entwaffnen: fehlte das Register, warf ``bestaetige`` — mitten im
    ``try`` von :func:`_lauf` —, der ``finally``-Block schrieb den Versuch trotzdem an
    und legte die Datei dabei NEU an. Der naechste Lauf fand ein Register mit einer
    einzigen Zeile vor und deflationierte gegen die angemeldete Kampagnengroesse
    (sieben) statt gegen alle bisherigen Versuche. Die Kampagnenzaehlung faengt den
    Absturz also nur bis zu dieser Untergrenze ab; alles darueber war weg, und eine zu
    kleine Versuchszahl macht die DSR milder — die schmeichelnde Richtung.

    Ein LEERES Register ist zulaessig (dann laeuft die erste Kampagne), ein fehlendes
    nicht. Geheilt wird es durch den versionierten Abzug
    ``ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl``, nicht durch einen weiteren Lauf.
    """
    ledger = Path(pfad) if pfad is not None else default_ledger_path()
    if not ledger.is_file():
        raise StudienError(
            f"Versuchsregister {ledger} fehlt. Es wird hier NICHT angelegt: ein "
            "frisches Register meldete die Kampagnengroesse statt aller bisherigen "
            "Versuche, und eine zu kleine Versuchszahl macht die Deflation milder. "
            "Den versionierten Abzug ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl "
            "zurueckspielen. Ein leeres Register ist zulaessig, ein fehlendes nicht."
        )
    return ledger


def _registerkennung(register: Path) -> str:
    """Wie das Register im Beleg heisst -- ohne den Pfad des Rechners, der es fuhr.

    Die Zeile stand hier zuerst als nacktes ``{register}`` und druckte damit einen
    ABSOLUTEN Pfad; im Lauf, aus dem der eingefrorene Abzug stammt, waere das
    ``C:\\Users\\<kontoname>\\...\\TRIALS.jsonl`` gewesen. Zweierlei ist daran falsch.
    Erstens haengt ein Beleg, dessen Inhalt am Benutzerkonto des Ausfuehrenden haengt,
    an einem Rechner -- dieselbe Klasse Mangel, gegen die dieses Repo sonst mit
    ``data_checksum`` und ``code_commit`` arbeitet. Zweitens laesst dieses Repo weder
    Konto- noch Servernamen in eine Datei, die weitergegeben wird, und ein
    Windows-Benutzerpfad ist ein Kontoname.

    Gedruckt wird darum der Pfad RELATIV zum Repo, mit ``/`` als Trenner, damit
    derselbe Lauf unter Windows und unter Linux dieselbe Zeile erzeugt. Liegt das
    Register ausserhalb des Repos, bleibt nur sein Dateiname -- mit dem ausdruecklichen
    Vermerk. Das ist keine Verschleierung, sondern die verwertbare Auskunft: ob gegen
    das versionierte Register deflationiert wurde oder gegen ein Seitenstueck.

    Was hier BEWUSST NICHT steht, ist die Zahl der Registerzeilen. Die Versuchszahl,
    gegen die wirklich deflationiert wird, ist die der ganzen Kampagne; sie steht im
    Ergebnisblock (``gegen N Versuche``). Eine zweite, kleinere Zahl daneben liesse
    sich mit ihr verwechseln, und im Beleg ist eine verwechselbare Zahl schlimmer als
    keine.
    """
    try:
        innen = register.resolve().relative_to(REPO)
    except ValueError:
        return f"{register.name} (ausserhalb des Repos)"
    return innen.as_posix()


def _tausender(zahl: int) -> str:
    """Deutsche Tausendertrennung: ``1000`` wird ``1.000``.

    Die Zahl der Ziehungen stand frueher als Text ``1.000`` im Bericht und wurde
    richtigerweise durch ``kern.M62_ZIEHUNGEN`` ersetzt -- dabei ging der Trennpunkt
    verloren, und der eingefrorene Abzug las sich ploetzlich anders als der Lauf. Der
    Bericht ist durchweg deutsch gesetzt; die Trennung gehoert dazu.
    """
    return f"{zahl:,}".replace(",", ".")


def _lade_kerzen(symbol: str) -> list[Kerze]:
    """Stundenkerzen aus dem Terminal, Zeitstempel in ECHTES UTC gedreht.

    Die noch in Bildung befindliche Kerze bleibt draussen. Sie kam frueher mit: der
    Abruf endet bei ``jetzt``, und ``terminal.rates`` liefert die laufende Kerze
    mit -- ihr ``close`` ist der Momentankurs. Eine Studie, die ihr letztes Fenster
    darauf rechnet, misst einen Zwischenstand, und ein zweiter Lauf ergaebe eine
    andere Zahl.

    ``jetzt`` kommt vom Platz (Tick-Stempel), durch **dieselbe** Umrechnung wie die
    Kerzenstempel -- nicht von der Rechneruhr. Begruendung bei
    ``protocol.ist_abgeschlossen``.
    """
    terminal = RealMt5Terminal(allow_write=False)
    if not terminal.initialize():
        raise StudienError("Terminal nicht erreichbar")
    try:
        tick = terminal.tick(symbol)
        if tick is None:
            raise StudienError(
                f"kein Tick fuer {symbol} -- ohne Platzzeit ist nicht entscheidbar, "
                "welche Kerze abgeschlossen ist (fail-closed)"
            )
        jetzt = server_zu_utc(tick.ts)
        ende = datetime.now(UTC)
        roh: dict[datetime, Kerze] = {}
        scheibe_ende = ende
        for _ in range(9):  # 45 Jahre in Fuenfjahresscheiben, wie in aufloesung.py
            scheibe_start = scheibe_ende - timedelta(days=365 * 5)
            reihe = terminal.rates(symbol, Timeframe.H1, scheibe_start, scheibe_ende)
            for r in reihe:
                echt = server_zu_utc(r.ts)
                if not ist_abgeschlossen(echt, Timeframe.H1, jetzt):
                    continue
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


def _lauf(
    k: Kandidat,
    symbol: str,
    kerzen: list[Kerze],
    kosten: Any,
    *,
    register_pfad: Path | str | None = None,
) -> int:
    k_bps = _kosten_bps(kosten, symbol)
    if k_bps is None:
        print(f"{k.schluessel}/{symbol}: keine Kostenzeile — nicht bewertbar")
        return 1
    termine = list(
        ereignisse(k, kerzen[0].ts.date(), kerzen[-1].ts.date())
    )
    pruefsumme = _data_checksum(symbol)
    commit = _code_commit()
    # Das Register gehoert zu dem, was VOR der Messung feststehen muss — genau wie
    # Pruefsumme und Codestand. Steht es hier, kann der ``finally``-Block unten es
    # nicht mehr anlegen; siehe :func:`verlange_register`.
    register = verlange_register(register_pfad)

    print("-" * 90)
    print(f"{k.schluessel} — {k.name} — {symbol}")
    print("-" * 90)
    # DIESER BLOCK IST DAS BLATT, DAS SPAETER BELEGEN SOLL, WAS VORHER FESTSTAND.
    # Er wird deshalb als Ganzes gehalten: ``test_der_block_vor_der_messung_nennt_
    # alle_acht_stuecke`` faellt, sobald eine Zeile verschwindet. Die angekuendigte
    # Vorzeichenregel haengt an keiner gemeinsamen Konstante mit dem Kernmodul -- das
    # Kernmodul rechnet sie, benennt sie aber nicht. Gebunden wird sie stattdessen
    # ueber die Messung: ``test_die_angekuendigte_vorzeichenregel_ist_die_gerechnete``
    # laesst DENSELBEN Lauf auf einer Reihe mit bekanntem Vorzeichen laufen. Wer die
    # Ankuendigung dreht, faellt ueber die eine Haelfte des Falls; wer die Rechnung
    # dreht, ueber die andere.
    print("VOR DER MESSUNG festgezurrt:")
    print(f"  Hypothese      : {HYPOTHESE} (Vorzeichen = -sign(Rendite der Vorstunde))")
    print(f"  Fenster        : {k.fenster_stunden:.0f} h ab dem ersten handelbaren "
          f"Kerzenanfang")
    print(f"  Zeitpunkt      : {k.uhrzeit.isoformat(timespec='minutes')} {k.zone_name}")
    print(f"  Zeitraum       : {kerzen[0].ts.date()} .. {kerzen[-1].ts.date()}")
    print(f"  Ereignisse     : {len(termine)}")
    print(f"  K (guenstigster Broker): {k_bps:.2f} bp | "
          f"M6.1-Schwelle {kern.M61_FAKTOR * k_bps:.2f} bp")
    print(f"  data_checksum  : {pruefsumme[:16]}...")
    print(f"  code_commit    : {commit[:12]}")
    print(f"  Register       : {_registerkennung(register)}")

    ausgang, erg, best = "error", None, None
    try:
        erg, werte = studie(
            kandidat=k.schluessel, instrument=symbol, kerzen=kerzen,
            ereignisse=termine, fenster_stunden=k.fenster_stunden, k_bps=k_bps,
        )
        best = bestaetige(
            werte, kerzen=kerzen, ereignisse=termine,
            fenster_stunden=k.fenster_stunden, k_bps=k_bps, saat=SAAT,
            # Dasselbe Register, gegen das oben geprueft wurde. Ohne diese Angabe
            # deflationierte die Studie gegen ein anderes Register als das, in das sie
            # gleich schreibt — zwei Register fuer eine Reihe sind eines zu viel.
            register_pfad=register,
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
        ), register)
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
    # Die Versuchszahl steht MIT der DSR. Sie ist kein Beiwerk: dieselbe Messung
    # ergibt 0,755 bei acht Versuchen und 0,984 bei einem (siehe
    # ``gates/trials.py::deflation_trials``) -- einmal durchgefallen, einmal
    # bestanden. Eine DSR ohne ihre Versuchszahl ist nicht nachrechenbar, und
    # ``Bestaetigung.dsr_versuche`` gibt es genau dafuer.
    print(f"  M6.2 Deflation   : DSR {b.dsr_oos:.3f} auf {b.dsr_n} OoS-Ereignissen "
          f"gegen {b.dsr_versuche} Versuche "
          f"-> {'ok' if b.dsr_bestanden else 'gescheitert'}")
    print(f"  M6.2 Stabilitaet : {b.haelfte_frueh_bps:+.2f} / "
          f"{b.haelfte_spaet_bps:+.2f} bp -> "
          f"{'ok' if b.stabil_bestanden else 'gescheitert'}")
    # Die Zahl der Ziehungen wird gelesen, nicht wiederholt: sie stand hier als
    # „1.000" im Text, waehrend ``M62_ZIEHUNGEN`` sie im Kern fuehrt. Der Trennpunkt
    # kommt seitdem aus :func:`_tausender` und nicht mehr aus dem Text.
    print(f"  M6.2 Zufall      : {b.zufall_anteil * 100:.1f} % der "
          f"{_tausender(kern.M62_ZIEHUNGEN)} verschobenen Mengen "
          f"-> {'ok' if b.zufall_bestanden else 'gescheitert'}")
    urteil = "BESTANDEN" if (e.m61_bestanden and b.bestanden) else "GESCHEITERT"
    print(f"\n  URTEIL M6: {urteil}")


def _pruefe_paare(paare: list[tuple[Kandidat, str]]) -> None:
    """Nur vorregistrierte Paarungen aus Kandidat und Instrument.

    ``--kandidat K1 --instrument NVDA`` lief bisher glatt durch: das Londoner Fixing
    auf einer Aktie, gemessen, berichtet und als Versuch der Reihe registriert. Das ist
    keine Wiederholung des Feldes, sondern eine NEUE Hypothese — und M7 zaehlt sie als
    eigenen Versuch. Zugleich verschiebt sie die Kampagnengrenze, gegen die
    deflationiert wird: das Feld hat sieben angemeldete Paarungen, der achte Lauf faellt
    in dieselbe Kampagne und rueckt die Grenze fuer alle folgenden schief.
    """
    for k, symbol in paare:
        if symbol not in k.instrumente:
            raise StudienError(
                f"{k.schluessel} ({k.name}) ist fuer {list(k.instrumente)} "
                f"vorregistriert, nicht fuer {symbol!r}. Eine Paarung ausserhalb des "
                "Feldes ist eine neue Hypothese (M7), kein Lauf dieser Reihe."
            )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Ereignisstudie (Paket 3a)")
    p.add_argument("--selbsttest", action="store_true",
                   help="synthetische Reihe, registriert KEINEN Versuch")
    p.add_argument("--kandidat", default=None)
    p.add_argument("--instrument", default=None)
    p.add_argument("--alle", action="store_true", help="alle Kandidaten des Feldes")
    args = p.parse_args(argv)

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

    # Beides VOR der ersten Kerzenabfrage: ein Abbruch nach 45 Jahren Historie ist
    # derselbe Abbruch, nur eine halbe Stunde spaeter.
    try:
        _pruefe_paare(paare)
        register = verlange_register()
    except StudienError as exc:
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 1

    print(f"Ereignisstudie {STUDY_POLICY_VERSION} — {len(paare)} Studien, "
          f"jede verbraucht einen Versuch")
    reihen: dict[str, list[Kerze]] = {}
    schlecht = 0
    for k, symbol in paare:
        if symbol not in reihen:
            reihen[symbol] = _lade_kerzen(symbol)
        schlecht += _lauf(k, symbol, reihen[symbol], kosten, register_pfad=register)
        print()
    # Frueher: ``1 if schlecht == len(paare) else 0`` — gruen, solange auch nur eine
    # Studie durchlief. Sechs von sieben unbewertbar und trotzdem Rueckgabe 0 heisst:
    # sechs verbrauchte Versuche, und wer nur den Rueckgabewert liest, sieht Erfolg.
    # Eine geplante und nicht gerechnete Studie ist eine Luecke im Beleg, kein Rest.
    return 1 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())

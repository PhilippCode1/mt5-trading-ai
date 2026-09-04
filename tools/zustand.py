#!/usr/bin/env python3
"""Der Zustandsordner, lesbar -- und die zwei menschlichen Gesten (D1, D4, D8).

WAS HIER LIEGT
--------------
Risikozustand (``risikozustand.json``), Schwebeakte (``schwebende_auftraege.json``),
Positionsbuch (``positionsbuch.json``), Stoppdatei (``STOP``) und die Journale
(``journale/``) -- alles in EINEM Ordner ausserhalb des Arbeitsbaums
(``--zustandsordner``, Vorgabe ``standard_zustandsordner()``; A18, E-005). Dieses
Werkzeug zeigt ihn an, ohne eine Kontonummer auszugeben: die Zustandsdatei traegt das
Konto nur als Schluesselabdruck, und die Journale werden hier nicht zitiert.

DIE ZWEI GESTEN
---------------
Beide sind bewusst kein Knopf im Betrieb, sondern ein Werkzeug fuer einen Menschen:

* ``--halt-freigeben <kennung> --konto <kontonummer>`` loest den **dauerhaften**
  Drawdown-Halt (``RiskManager.release_drawdown``). Die Kennung ist Pflicht und wird
  nicht geprueft, aber verlangt -- an ihr muss spaeter nachvollziehbar sein, wer auf
  welche Lage hin freigegeben hat. Die Kontonummer bindet den Zustand
  (``DateiZustand.binde``); passt sie nicht zum Abdruck in der Datei, wird nichts
  geschrieben. Ein laufender Betrieb behaelt seinen Halt im Speicher und schriebe ihn
  beim naechsten Sichern zurueck: erst den Lauf beenden (Stoppdatei), dann freigeben.
* ``--schwebeakte-aufloesen <client_order_id> --befund "<Text>"`` raeumt einen
  ungeklaerten Sendeversuch ab -- nur mit dem Befund dessen, was beim Broker
  nachgesehen wurde (``SchwebeAkte.aufloesen``). Ohne Befund keine Aufloesung.

Der Global-Halt des laufenden Prozesses (``Mt5Venue.halt_gruende``) lebt im Speicher
und endet mit dem Prozess; was ueberdauert, sind der Drawdown-Halt in der
Zustandsdatei und die Eintraege der Schwebeakte -- genau die beiden Dinge, die dieses
Werkzeug bewegt.

Aufruf::

    python tools/zustand.py --zeigen
    python tools/zustand.py --halt-freigeben ops-2026-09-04 --konto 12345678
    python tools/zustand.py --schwebeakte-aufloesen open-EURUSD-1a2b3c --befund "..."
    python tools/zustand.py --zeigen --zustandsordner <ordner>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.execution.reconcile import (  # noqa: E402
    Positionsbuch,
    PositionsbuchDefekt,
)
from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    JOURNALORDNER_NAME,
    POSITIONSBUCH_DATEI,
    RISIKOZUSTAND_DATEI,
    SCHWEBEAKTE_DATEI,
    STOPPDATEI_NAME,
    DateiZustand,
    ZustandsortFehler,
    standard_zustandsordner,
    zustandsordner_waehlen,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import SchwebeAkte  # noqa: E402

EXIT_OK = 0
EXIT_NICHTS_GETAN = 1
EXIT_UNBRAUCHBAR = 2


def _waehrung_der_datei(pfad: Path) -> str | None:
    """Die Kontowaehrung aus der Zustandsdatei -- das einzige Feld, das dieses
    Werkzeug roh liest; alles Uebrige deutet ``DateiZustand``."""
    try:
        daten: Any = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    wert = daten.get("waehrung") if isinstance(daten, dict) else None
    return wert if isinstance(wert, str) and wert else None


def zeigen(ordner: Path) -> list[str]:
    """Der Zustandsordner als Zeilen -- ohne Kontonummer."""
    zeilen = [f"Zustandsordner: {ordner}", ""]

    zustandsdatei = ordner / RISIKOZUSTAND_DATEI
    zeilen.append(f"Risikozustand ({RISIKOZUSTAND_DATEI}):")
    if not zustandsdatei.exists():
        zeilen.append("  keine Datei -- neu (kein Halt, keine Zaehler)")
    else:
        befund = DateiZustand(zustandsdatei).laden()
        lage = befund.lage
        zeilen.append(f"  herkunft: {befund.herkunft}")
        if befund.sperrgrund is not None:
            zeilen.append(f"  SPERRE: {befund.sperrgrund}")
        zeilen.append(
            f"  waehrung: {_waehrung_der_datei(zustandsdatei) or 'ungebunden'}"
        )
        zeilen.append(
            f"  halt: {'JA' if lage.halt else 'nein'}"
            + (f" -- {lage.halt_grund} seit {lage.halt_seit}" if lage.halt else "")
        )
        zeilen.append(
            f"  tageszaehler: tag={lage.handelstag} konto={lage.trades_konto} "
            f"je_instrument={dict(lage.trades_je_instrument)} "
            f"gesperrt={'ja' if lage.zaehler_gesperrt else 'nein'}"
        )
        zeilen.append(
            f"  equity: tag={lage.equity_tag} tagesstart={lage.tagesstart_equity} "
            f"fenster={len(lage.equity_fenster)} Punkte"
            + (
                f", hoechststand={max(e for _, e in lage.equity_fenster)}"
                if lage.equity_fenster
                else ""
            )
        )
        zeilen.append(
            f"  offene_positionen (Risikozaehler): {len(lage.offene_positionen)}"
        )
        for symbol, seit in lage.offene_positionen:
            zeilen.append(f"    {symbol} seit {seit.isoformat(timespec='seconds')}")

    zeilen.append("")
    aktendatei = ordner / SCHWEBEAKTE_DATEI
    zeilen.append(f"Schwebeakte ({SCHWEBEAKTE_DATEI}):")
    if not aktendatei.exists():
        zeilen.append("  keine Datei -- nichts schwebt")
    else:
        akte = SchwebeAkte(aktendatei).laden()
        if akte.sperrgrund is not None:
            zeilen.append(f"  SPERRE: {akte.sperrgrund}")
        zeilen.append(f"  eintraege: {len(akte.eintraege)}")
        for e in akte.eintraege:
            zeilen.append(
                f"    {e.client_order_id} [{e.symbol or '?'}] seit "
                f"{e.seit.isoformat(timespec='seconds')}: {e.grund}"
            )

    zeilen.append("")
    buchdatei = ordner / POSITIONSBUCH_DATEI
    zeilen.append(f"Positionsbuch ({POSITIONSBUCH_DATEI}):")
    if not buchdatei.exists():
        zeilen.append("  keine Datei -- keine eigene Position gebucht")
    else:
        try:
            positionen = Positionsbuch(buchdatei).laden()
        except PositionsbuchDefekt as exc:
            zeilen.append(f"  SPERRE: {exc}")
        else:
            zeilen.append(f"  positionen: {len(positionen)}")
            for b in positionen:
                zeilen.append(
                    f"    {b.kennung} #{b.ticket} {b.symbol} {b.richtung} {b.menge} "
                    f"seit {b.eroeffnet_am.isoformat(timespec='seconds')} stop={b.stop}"
                )

    zeilen.append("")
    stoppdatei = ordner / STOPPDATEI_NAME
    stopp = "VORHANDEN" if stoppdatei.exists() else "nein"
    zeilen.append(f"Stoppdatei ({STOPPDATEI_NAME}): {stopp}")
    journale = ordner / JOURNALORDNER_NAME
    dateien = sorted(journale.glob("journal-*.jsonl")) if journale.is_dir() else []
    zeilen.append(
        f"Journale ({JOURNALORDNER_NAME}/): {len(dateien)}"
        + (f", juengstes {dateien[-1].name}" if dateien else "")
    )
    return zeilen


def halt_freigeben(ordner: Path, kennung: str, konto: str) -> tuple[int, str]:
    """Den dauerhaften Drawdown-Halt loesen. Gibt (Exit, Meldung)."""
    if not kennung.strip():
        return EXIT_UNBRAUCHBAR, "FEHLGESCHLAGEN -- leere Freigabekennung."
    zustandsdatei = ordner / RISIKOZUSTAND_DATEI
    if not zustandsdatei.exists():
        return EXIT_NICHTS_GETAN, f"Kein Zustand unter {zustandsdatei} -- kein Halt."
    zustand = DateiZustand(zustandsdatei)
    befund = zustand.laden()
    if befund.sperrgrund is not None:
        return (
            EXIT_NICHTS_GETAN,
            f"Der Zustand ist gesperrt ({befund.sperrgrund}); eine Freigabe schreibt "
            "ueber einen Defekt nicht hinweg. Datei ansehen (--zeigen).",
        )
    if not befund.lage.halt:
        return EXIT_NICHTS_GETAN, "Kein Halt steht -- nichts freigegeben."
    waehrung = _waehrung_der_datei(zustandsdatei)
    if waehrung is None:
        return (
            EXIT_NICHTS_GETAN,
            "Zustand ohne Waehrung/Bindung -- kein Halt freigebbar.",
        )
    grund = zustand.binde(konto, waehrung)
    if grund is not None:
        return (
            EXIT_NICHTS_GETAN,
            f"FEHLGESCHLAGEN -- {grund}: die Kontonummer passt nicht zum Abdruck in "
            "der Zustandsdatei. Nichts geschrieben.",
        )
    manager = RiskManager(zustand=zustand, konto_id=konto, waehrung=waehrung)
    manager.release_drawdown(kennung)
    danach = DateiZustand(zustandsdatei).laden()
    if danach.lage.halt:
        return (
            EXIT_NICHTS_GETAN,
            "FEHLGESCHLAGEN -- der Halt steht nach dem Schreiben noch "
            f"({zustand.schreibfehler_text or 'Grund unbekannt'}).",
        )
    return (
        EXIT_OK,
        f"Halt geloest mit Kennung {kennung.strip()!r} (vorher: "
        f"{befund.lage.halt_grund} seit {befund.lage.halt_seit}). Wirkt beim naechsten "
        "Start; ein laufender Betrieb behaelt seinen Halt.",
    )


def schwebeakte_aufloesen(ordner: Path, kennung: str, befund: str) -> tuple[int, str]:
    """Einen ungeklaerten Sendeversuch abraeumen -- nur mit Befund."""
    akte = SchwebeAkte(ordner / SCHWEBEAKTE_DATEI)
    try:
        entfernt = akte.aufloesen(kennung, befund=befund)
    except ValueError as exc:
        return EXIT_UNBRAUCHBAR, f"FEHLGESCHLAGEN -- {exc}"
    if not entfernt:
        return EXIT_NICHTS_GETAN, f"Kennung {kennung!r} steht nicht in der Schwebeakte."
    rest = akte.laden()
    return (
        EXIT_OK,
        f"Kennung {kennung!r} aufgeloest (Befund: {befund.strip()}). "
        f"Verbleibend: {len(rest.eintraege)}"
        + (f", SPERRE {rest.sperrgrund}" if rest.sperrgrund else ""),
    )


def main(argv: list[str] | None = None) -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="Zustandsordner anzeigen; Drawdown-Halt freigeben; "
        "Schwebeakte aufloesen"
    )
    ap.add_argument(
        "--zustandsordner",
        type=Path,
        default=None,
        metavar="ORDNER",
        help=f"Zustandsordner (Vorgabe: {standard_zustandsordner()})",
    )
    was = ap.add_mutually_exclusive_group(required=True)
    was.add_argument("--zeigen", action="store_true", help="den Zustand anzeigen")
    was.add_argument(
        "--halt-freigeben",
        metavar="KENNUNG",
        help="den dauerhaften Drawdown-Halt mit dieser Freigabekennung loesen "
        "(verlangt --konto)",
    )
    was.add_argument(
        "--schwebeakte-aufloesen",
        metavar="CLIENT_ORDER_ID",
        help="einen ungeklaerten Sendeversuch abraeumen (verlangt --befund)",
    )
    ap.add_argument(
        "--konto",
        default=None,
        metavar="KONTONUMMER",
        help="Kontonummer, an die der Zustand gebunden ist (nur --halt-freigeben)",
    )
    ap.add_argument(
        "--befund",
        default=None,
        metavar="TEXT",
        help="was beim Broker nachgesehen wurde (nur --schwebeakte-aufloesen)",
    )
    args = ap.parse_args(argv)
    if args.halt_freigeben is not None and not args.konto:
        ap.error("--halt-freigeben verlangt --konto <kontonummer>")
    if args.schwebeakte_aufloesen is not None and not (args.befund or "").strip():
        ap.error('--schwebeakte-aufloesen verlangt --befund "<Text>"')

    try:
        ordner = zustandsordner_waehlen(args.zustandsordner)
    except ZustandsortFehler as exc:
        print(f"FEHLGESCHLAGEN -- Zustandsordner unbrauchbar: {exc}", file=sys.stderr)
        return EXIT_UNBRAUCHBAR

    if args.zeigen:
        print("\n".join(zeigen(ordner)))
        return EXIT_OK
    if args.halt_freigeben is not None:
        exit_code, meldung = halt_freigeben(ordner, args.halt_freigeben, args.konto)
    else:
        exit_code, meldung = schwebeakte_aufloesen(
            ordner, args.schwebeakte_aufloesen, args.befund
        )
    print(meldung, file=sys.stderr if exit_code != EXIT_OK else sys.stdout)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

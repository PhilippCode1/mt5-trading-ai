#!/usr/bin/env python3
"""CLI: Demo-Smoke-Test gegen ein echtes MT5-Terminal.

NUR auf einem Demokonto ausfuehren. Standardmaessig **nur lesend**; die Schreib-Probe
(``--allow-write``) platziert eine winzige Order und schliesst sie sofort wieder,
und auch das nur, wenn das Konto ein Demokonto ist (harte Sperre in ``run_smoke``).

Voraussetzung: ein installiertes MT5-Terminal, **im Demokonto angemeldet**, plus das
Paket ``MetaTrader5`` (``pip install MetaTrader5``). Der Smoke haengt sich an das
laufende Terminal — es werden **keine** Zugangsdaten auf der Kommandozeile erwartet.

Der lesende Lauf prueft jedes Katalogsymbol einzeln (``symbol_<NAME>`` mit
``currency_profit`` und ``currency_margin``) und misst den Serverzeitversatz
(Tick-Zeit des Terminals gegen die lokale UTC-Uhr, Sekunden) -- Abnahmekatalog A9.

Rueckgabewerte:

* 0 -- alle Schritte gruen;
* 1 -- der Bericht traegt einen roten Schritt (steht mit Namen in der Ausgabe);
* 2 -- **kein Terminal**: genau eine Zeile ``FEHLGESCHLAGEN -- MT5-Terminal nicht
  erreichbar: <Grund>`` auf stderr, kein Traceback (Abnahmekatalog A12). Das deckt
  beide Ausgaenge von ``RealMt5Terminal.initialize`` ab: die Ausnahme
  ``VenueUnavailableError`` (Paket fehlt) und ``False`` (Terminal nicht gestartet).

Beispiele::

    python tools/mt5_smoke.py                 # nur lesend, Symbol EURUSD
    python tools/mt5_smoke.py --symbol GBPUSD
    python tools/mt5_smoke.py --allow-write    # winzige Demo-Order, sofort geschlossen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.venue.catalog import load_instrument_catalog  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.smoke import run_smoke  # noqa: E402

#: Rueckgabewert, wenn das Terminal nicht erreichbar ist (A12).
EXIT_KEIN_TERMINAL = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo-Smoke-Test der MT5-Bindung")
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="winzige Demo-Order platzieren und sofort schliessen (nur Demokonto)",
    )
    parser.add_argument("--login", type=int, default=None, help="Kontonummer")
    parser.add_argument("--server", default=None)
    parser.add_argument("--path", default=None, help="Pfad zur terminal64.exe")
    args = parser.parse_args(argv)

    terminal = RealMt5Terminal(
        login=args.login,
        server=args.server,
        path=args.path,
        allow_write=args.allow_write,
    )
    katalog = load_instrument_catalog()
    # Die Risikoschicht ist seit Paket 2 fuer JEDE eroeffnende Order Pflicht -- auch
    # auf dem Demokonto. Ohne Manager lehnt der Order-Pfad fail-closed ab; die
    # Schreib-Probe wuerde also gar nicht erst laufen. Standard-Politik: die Probe
    # soll unter denselben Grenzen laufen wie der spaetere Betrieb.
    venue = Mt5Venue(
        name="mt5",
        terminal=terminal,
        catalog=katalog,
        risk_manager=RiskManager(),
    )

    report = run_smoke(
        venue,
        symbol=args.symbol,
        allow_write=args.allow_write,
        symbole=sorted(katalog),
    )
    # ``run_smoke`` faengt den Verbindungsaufbau selbst ab und bricht dann mit genau
    # einem Schritt ab. Das ist der Fall "kein Terminal" -- eine Zeile, Exit 2, kein
    # Bericht, der wie ein gelaufener Rauchtest aussieht.
    if report.steps and report.steps[0].name == "connect" and not report.steps[0].ok:
        print(
            "FEHLGESCHLAGEN -- MT5-Terminal nicht erreichbar: "
            f"{report.steps[0].detail}",
            file=sys.stderr,
        )
        return EXIT_KEIN_TERMINAL
    for step in report.steps:
        print(f"{'OK ' if step.ok else '!! '}{step.name}: {step.detail}")
    print("SMOKE OK" if report.ok else "SMOKE FEHLGESCHLAGEN")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

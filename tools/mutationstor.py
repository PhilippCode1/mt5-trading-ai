#!/usr/bin/env python3
"""Mutationstor: faellt eine Aenderung am Geldpfad auf -- oder merkt es keiner?

WORUM ES GEHT
-------------
Stufe 8 des Auftrags::

    Mutationstor auf die kritischen Dateien des Geldpfads mit einer Toetungsrate als
    blockierender Schwelle.
    Abnahme: die Mutationssonden faerben den Lauf rot.

Eine Testsuite mit 1.516 gruenen Faellen sagt nichts darueber, ob sie **wirkt**. Sie
sagt
nur, dass niemand sie hat rot werden lassen. Die Frage dieser Stufe ist die
umgekehrte: wenn ich am Geldpfad etwas kaputt mache -- merkt es jemand?

In den Stufen 4 bis 7 dieses Auftrags habe ich das je einmal von Hand gefahren. Das war
richtig und reicht nicht: eine Probe, die nur laeuft, wenn ich daran denke, ist keine
Sperre. Dieses Werkzeug macht sie zu einer.

WIE ES ARBEITET
---------------
Der Katalog unten ist **von Hand geschrieben, nicht erzeugt**. Jeder Eintrag ist ein
echter Rueckfall: eine Vergleichsrichtung umgedreht, eine Grenze verschoben, eine Sperre
uebersprungen. Ein Zufallsmutator haette den umgekehrten Fehler -- er erzeugt viel
Belangloses (Docstrings, Protokolltexte), und eine Toetungsrate ueber Belanglosem misst
nichts.

Je Eintrag:

1. Datei einlesen und **im Speicher** sichern,
2. mutieren,
3. den zugehoerigen Testausschnitt fahren,
4. **aus dem Speicher** zurueckschreiben und die Pruefsumme vergleichen.

Punkt 4 ist keine Formsache. In dieser Sitzung ist einmal ``git checkout`` benutzt
worden, um eine Mutation zurueckzunehmen -- er stellte den letzten Commit her und
loeschte damit
die noch nicht eingecheckte Arbeit (``AUFTRAG/fehler.md``, F-010). Dieses Werkzeug kennt
den Befehl nicht.

DIE SCHWELLE
------------
:data:`MINDEST_TOETUNGSRATE` steht auf **1,0**, und das ist eine Entscheidung, keine
Zierde: der Katalog ist von Hand ausgewaehlt, jeder Eintrag ist ein echter Defekt. Eine
Rate von 0,9 hiesse, dass einer davon unbemerkt durchginge -- und welcher, waere Zufall.
Wer den Katalog erweitert und die neue Sonde ueberlebt, hat ein Loch gefunden; das ist
der Zweck, und das Tor sagt es rot.

Aufruf::

    python tools/mutationstor.py            # alle Sonden, blockierend
    python tools/mutationstor.py --liste     # nur den Katalog zeigen
    python tools/mutationstor.py --sonde N   # eine einzelne Sonde
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Die Schwelle. Begruendung im Modul-Docstring: der Katalog ist handverlesen, jeder
#: Eintrag ein echter Defekt. Senken ist nach V6 des Auftrags nicht vorgesehen.
MINDEST_TOETUNGSRATE = 1.0


@dataclass(frozen=True)
class Sonde:
    """Eine benannte Mutation samt dem Testausschnitt, der sie fangen soll.

    ``tests`` ist bewusst ein Ausschnitt und nicht die ganze Suite: eine Sonde, die
    erst nach einer Minute rot wird, wird im Betrieb abgeschaltet. Der Ausschnitt ist
    zugleich eine Behauptung -- „diese Dateien sind fuer diesen Defekt zustaendig" --
    und sie faellt auf, wenn sie falsch ist.
    """

    name: str
    datei: str
    alt: str
    neu: str
    tests: tuple[str, ...]
    #: Was der Defekt in der Sache bedeutet. Steht in der Ausgabe, damit eine
    #: ueberlebende Sonde nicht nur eine Nummer ist.
    bedeutet: str


KATALOG: tuple[Sonde, ...] = (
    Sonde(
        name="reduce-only-sperre",
        datei="mt5_trading_ai/venue/mt5.py",
        alt="        if is_reducing:\n",
        neu="        if False:\n",
        tests=("tests/test_stufe4_risikokern.py",),
        bedeutet="Der Risikoabbau laeuft durch die Eroeffnungstore (V5-Verstosz).",
    ),
    Sonde(
        name="kontopruefung",
        datei="mt5_trading_ai/venue/mt5.py",
        alt="        mangel = konto_maengel(acc)\n        if mangel is not None:\n"
        "            raise OrderRejectedError(",
        neu="        mangel = None\n        if mangel is not None:\n"
        "            raise OrderRejectedError(",
        tests=("tests/test_stufe4_risikokern.py",),
        bedeutet="Leere Kontodaten stuerzen wieder ab, statt mit Grund abzulehnen.",
    ),
    Sonde(
        name="schwebender-auftrag",
        datei="mt5_trading_ai/venue/mt5.py",
        alt="            self._verweigere_bei_schwebendem_auftrag()\n",
        neu="",
        tests=("tests/test_stufe5_ausfuehrung.py",),
        bedeutet="Nach einem Sendeversuch ohne Antwort wird weiter eroeffnet.",
    ),
    Sonde(
        name="schwebeakte-fluechtig",
        datei="mt5_trading_ai/execution/schwebende_auftraege.py",
        alt=(
            "        if self._pfad is None:\n"
            "            return Schwebebefund(eintraege=self._speicher)"
        ),
        neu=(
            "        if True:\n"
            "            return Schwebebefund(eintraege=self._speicher)"
        ),
        tests=("tests/test_stufe5_ausfuehrung.py",),
        bedeutet="Ein ungeklaerter Auftrag ueberlebt den Neustart nicht mehr.",
    ),
    Sonde(
        name="aufloesung-ohne-befund",
        datei="mt5_trading_ai/execution/schwebende_auftraege.py",
        alt="        if not befund.strip():",
        neu="        if False:",
        tests=("tests/test_stufe5_ausfuehrung.py",),
        bedeutet="Ein schwebender Auftrag laesst sich ohne Nachsehen abraeumen.",
    ),
    Sonde(
        name="ueberlappung",
        datei="mt5_trading_ai/gates/herausforderer.py",
        alt="        gesamt += belegt / mittlere",
        neu="        gesamt += float(len(eintraege))",
        tests=("tests/test_stufe6_modellpfad.py",),
        bedeutet="Fuenfmal dieselbe Marktbewegung zaehlt wieder als fuenf Belege.",
    ),
    Sonde(
        name="mindestmenge",
        datei="mt5_trading_ai/gates/herausforderer.py",
        alt="MINDESTBEOBACHTUNGEN_JE_MERKMAL = 30",
        neu="MINDESTBEOBACHTUNGEN_JE_MERKMAL = 1",
        tests=("tests/test_stufe6_modellpfad.py",),
        bedeutet="Acht Parameter lassen sich wieder aus drei Trades schaetzen.",
    ),
    Sonde(
        name="schemahash",
        datei="mt5_trading_ai/gates/herausforderer.py",
        alt=(
            '    beschreibung = ";".join('
            'f"{f.name}:{f.type}" for f in fields(Herausforderer))'
        ),
        neu='    beschreibung = "fest"',
        tests=("tests/test_stufe6_modellpfad.py",),
        bedeutet="Ein Artefakt aus einer anderen Feldwelt wird still gedeutet.",
    ),
    Sonde(
        name="erkundung-positivliste",
        datei="mt5_trading_ai/gates/erkundung.py",
        alt="    if ablehnungsgrund not in ERKUNDBARE_GRUENDE:",
        neu="    if False:",
        tests=("tests/test_stufe7_kaltstart.py",),
        bedeutet="Jede Sicherheitssperre wird erkundbar -- auch der Global-Halt.",
    ),
    Sonde(
        name="erkundung-echtgeld",
        datei="mt5_trading_ai/gates/erkundung.py",
        alt="    if not ist_papierkonto:",
        neu="    if False:",
        tests=("tests/test_stufe7_kaltstart.py",),
        bedeutet="Erkundet wird mit echtem Geld.",
    ),
    Sonde(
        name="gewichtung",
        datei="mt5_trading_ai/gates/erkundung.py",
        alt="        return 1.0 / self.wahrscheinlichkeit",
        neu="        return 1.0",
        tests=("tests/test_stufe7_kaltstart.py",),
        bedeutet="Erkundete Beobachtungen wiegen wie regulaere.",
    ),
    Sonde(
        name="kostenpraemisse",
        datei="mt5_trading_ai/execution/risk_manager.py",
        alt="kampagne if kampagne is not None else kostenpraemisse_bps(klasse)",
        neu="kampagne if kampagne is not None else assumed_cost_bps(klasse)",
        tests=("tests/test_stop_budget_kostenbasis.py",),
        bedeutet="Die Kostenschwelle misst wieder ihre eigene Ausgabe (V2).",
    ),
    Sonde(
        name="stop-kostenboden",
        datei="mt5_trading_ai/risk/stop_budget.py",
        alt="    return cost_bps / (2 * max_cost_drag)",
        neu="    return cost_bps / (4 * max_cost_drag)",
        tests=("tests/test_stop_budget.py", "tests/test_stop_budget_kostenbasis.py"),
        bedeutet="Die Stop-Untergrenze halbiert sich; Kosten fressen mehr vom Rand.",
    ),
    Sonde(
        name="margen-obergrenze",
        datei="mt5_trading_ai/risk/stop_budget.py",
        alt='MARGIN_CLOSE_OUT_FRACTION = Decimal("0.5")',
        neu='MARGIN_CLOSE_OUT_FRACTION = Decimal("0.9")',
        tests=("tests/test_stop_budget.py",),
        bedeutet="Der Abstand zum Margin-Close-out schrumpft fast auf null.",
    ),
    Sonde(
        name="geschlossene-kerze",
        datei="mt5_trading_ai/venue/protocol.py",
        alt="    return ts + timeframe.duration <= jetzt",
        neu="    return ts <= jetzt",
        tests=("tests/test_zeitschranken.py",),
        bedeutet="Auf der noch offenen Kerze wird gerechnet (Leckage).",
    ),
    Sonde(
        name="journal-zeitstempel",
        datei="tools/live_betrieb.py",
        alt="    if isinstance(wert, _DATETIME):",
        neu="    if isinstance(wert, datetime):",
        tests=("tests/test_live_betrieb_sperren.py",),
        bedeutet="Das Betriebsprotokoll wirft wieder bei eingefrorener Uhr (F-008).",
    ),
)


def _pruefsumme(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:16]


def _fahre(sonde: Sonde) -> tuple[bool, str]:
    """``(getoetet, Anmerkung)``. Stellt die Datei in jedem Fall wieder her."""
    pfad = ROOT / sonde.datei
    original = pfad.read_bytes()
    vorher = hashlib.sha256(original).hexdigest()[:16]
    # Auf LF normalisiert vergleichen: dieses Repo laeuft mit ``core.autocrlf=true``,
    # die Dateien liegen unter Windows als CRLF auf der Platte, und der Katalog oben
    # ist in LF geschrieben. Ohne die Normalisierung findet **keine** Sonde ihren
    # Anker -- und weil das Werkzeug das laut meldet statt still zu bestehen, ist es
    # beim ersten Lauf sofort aufgefallen. Zurueckgeschrieben wird byteweise das
    # Original, die Zeilenenden bleiben also, wie sie waren.
    text = original.decode("utf-8").replace(chr(13) + chr(10), chr(10))
    if sonde.alt not in text:
        # Laut scheitern: eine Sonde, die ihren Gegenstand nicht findet, ist keine
        # bestandene Sonde. Genau diese Sorte Pruefung (findet nichts, ist deshalb
        # gruen) schliesst dieser Auftrag an mehreren Stellen.
        return False, "ANKER FEHLT -- die Sonde trifft nichts mehr"
    try:
        pfad.write_bytes(text.replace(sonde.alt, sonde.neu, 1).encode("utf-8"))
        lauf = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", *sonde.tests],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        getoetet = lauf.returncode != 0
        anmerkung = "" if getoetet else "UEBERLEBT -- kein Test hat es bemerkt"
    finally:
        pfad.write_bytes(original)
    nachher = _pruefsumme(pfad)
    if nachher != vorher:
        # Darf nicht vorkommen; wenn doch, ist das schlimmer als jede ueberlebende
        # Sonde und muss den Lauf sofort beenden.
        raise RuntimeError(
            f"{sonde.datei} nach der Sonde '{sonde.name}' NICHT wiederhergestellt "
            f"({vorher} -> {nachher})."
        )
    return getoetet, anmerkung


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Mutationstor auf dem Geldpfad")
    ap.add_argument("--liste", action="store_true", help="nur den Katalog zeigen")
    ap.add_argument(
        "--sonde", type=int, default=None, help="nur diese Sonde (1-basiert)"
    )
    args = ap.parse_args()

    if args.liste:
        print(f"{len(KATALOG)} Sonden:")
        for i, s in enumerate(KATALOG, 1):
            print(f"  {i:>2}. {s.name:<26} {s.datei}")
            print(f"      {s.bedeutet}")
        return 0

    sonden = [KATALOG[args.sonde - 1]] if args.sonde is not None else list(KATALOG)
    print("=" * 78)
    print("MUTATIONSTOR -- faerbt eine Aenderung am Geldpfad den Lauf rot?")
    print("=" * 78)
    print(f"Sonden: {len(sonden)}   Mindest-Toetungsrate: {MINDEST_TOETUNGSRATE}")
    print()

    ueberlebt: list[Sonde] = []
    for i, sonde in enumerate(sonden, 1):
        getoetet, anmerkung = _fahre(sonde)
        marke = "getoetet" if getoetet else "UEBERLEBT"
        print(f"  {i:>2}/{len(sonden)}  {sonde.name:<26} {marke}")
        if not getoetet:
            print(f"          {sonde.datei}")
            print(f"          {sonde.bedeutet}")
            print(f"          {anmerkung}")
            ueberlebt.append(sonde)

    rate = (len(sonden) - len(ueberlebt)) / len(sonden)
    print()
    print(f"Toetungsrate: {rate:.3f} ({len(sonden) - len(ueberlebt)}/{len(sonden)})")
    if rate < MINDEST_TOETUNGSRATE:
        print()
        print(
            f"FEHLGESCHLAGEN — unter der Schwelle {MINDEST_TOETUNGSRATE}.",
            file=sys.stderr,
        )
        print(
            "Jede ueberlebende Sonde ist ein Loch: der Defekt ist eingebaut worden,",
            file=sys.stderr,
        )
        print("und kein Test hat ihn bemerkt.", file=sys.stderr)
        return 1
    print("ok — jede Sonde wurde gefangen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

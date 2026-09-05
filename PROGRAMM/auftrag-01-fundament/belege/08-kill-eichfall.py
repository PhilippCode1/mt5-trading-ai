#!/usr/bin/env python3
"""T8 -- Persistenz-Eichfall ``kill`` (Abnahmekatalog A6).

WAS DIESER EICHFALL MEHR ZEIGT ALS ``tools/wiederanlaufprobe.py``
----------------------------------------------------------------
Die vorhandene Probe laesst die Objekte fallen und baut neue -- das prueft die
Semantik des Zustands, nicht das Betriebssystem. Hier wird der Prozess **hart
abgeschossen** (``taskkill /F`` bzw. ``SIGKILL``): kein ``atexit``, kein ``finally``,
kein Puffer, der beim sauberen Ende noch auf die Platte laeuft. Genau das ist der
Fall, fuer den die Persistenz gebaut ist -- und der einzige, der einen gepufferten
Schreibvorgang entlarvt.

ZWEI TEILE
----------
1. **Das Werkzeug.** ``tools/live_betrieb.py --terminal fake --zustandsordner Z``
   laeuft an, schreibt Zustand und Journal, und wird mitten im Takt abgeschossen.
   Danach: liegen die Dateien da, sind sie lesbar, ist nichts halb geschrieben?
2. **Die Bedeutung.** Ein zweiter Prozess setzt Zustand ueber die echten Klassen
   (Drawdown-Halt, Schwebeakteneintrag, Positionsbuch) und wird abgeschossen; ein
   dritter, frisch gebauter Prozess wird gefragt, was er noch weiss -- nicht durch
   Nachsehen in einem Feld, sondern indem er eine Eroeffnung zu autorisieren versucht,
   **mit wieder vollem Konto**. Ein Halt, den man nur im Zustand sieht, der aber keine
   Order mehr aufhaelt, ist keiner. Dazu das kanonische JSON der drei Dateien vor und
   nach dem Neustart: identisch, sonst hat der Neustart den Zustand veraendert.

ROT GEGEN 306bbaa
-----------------
Dort ist ``RiskManager(zustand=None)`` die Vorgabe, die Schwebeakte fluechtig und das
Positionsbuch wird nie geschrieben (der Altstand sicherte das ausdruecklich zu).
Nach dem Abschuss ist der Zustandsordner leer, und der Neustart eroeffnet weiter.

Aufruf::

    python PROGRAMM/auftrag-01-fundament/belege/08-kill-eichfall.py
"""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    POSITIONSBUCH_DATEI,
    RISIKOZUSTAND_DATEI,
    SCHWEBEAKTE_DATEI,
)

#: Kopf beider Kindprozesse: Repo und Werkzeugordner in den Suchpfad, ohne dass ein
#: Benutzerpfad im Quelltext dieses Belegs steht (er kommt zur Laufzeit ueber argv).
IMPORTE = """
import json, sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

repo, ordner = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "tools"))

from mt5_trading_ai.execution.reconcile import Buchposition, Positionsbuch
from mt5_trading_ai.execution.risiko_zustand import (
    POSITIONSBUCH_DATEI, RISIKOZUSTAND_DATEI, SCHWEBEAKTE_DATEI, DateiZustand,
)
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.execution.schwebende_auftraege import (
    SchwebeAkte, SchwebenderAuftrag,
)
from wiederanlaufprobe import KONTO, TS, WAEHRUNG, _autorisiere, _konto

DREI = (RISIKOZUSTAND_DATEI, SCHWEBEAKTE_DATEI, POSITIONSBUCH_DATEI)
"""

#: Den Kern bauen -- in beiden Kindern gleich.
KERN = """
zustand = DateiZustand(ordner / RISIKOZUSTAND_DATEI)
kern = RiskManager(zustand=zustand, konto_id=KONTO, waehrung=WAEHRUNG)
"""

#: Setzt Zustand und wartet dann ewig. Kein try/finally, kein atexit, kein sauberes
#: Ende -- der Abschuss kommt von aussen.
KIND_SETZEN = (
    IMPORTE
    + """
ordner.mkdir(parents=True, exist_ok=True)
"""
    + KERN
    + """
kern.observe_equity(TS, Decimal("10000"))
kern.record_open_fill("EURUSD", TS)
# 10.000 -> 8.000 sind 20 % Drawdown gegen eine Grenze von 10 %: latcht den Halt.
urteil = _autorisiere(kern, _konto("8000"), TS + timedelta(minutes=1))
assert not urteil.approved and urteil.latch_halt, urteil

SchwebeAkte(ordner / SCHWEBEAKTE_DATEI).vermerken(
    SchwebenderAuftrag("open-EURUSD-kill", "Zeitablauf beim Senden", TS, "EURUSD")
)
Positionsbuch(ordner / POSITIONSBUCH_DATEI).eintragen(
    Buchposition(kennung="open-EURUSD-kill", ticket="4711", symbol="EURUSD",
                 richtung="kauf", menge=Decimal("0.01"), eroeffnet_am=TS,
                 stop=Decimal("1.09000"))
)

import time
print("BEREIT", flush=True)
while True:
    time.sleep(0.2)
"""
)

#: Der Neustart: dieselbe Platte, ERHOLTES Konto -- und die Frage, ob der Halt wirkt.
#: Er meldet ZUERST, was er vorfindet (vor jedem eigenen Schreibvorgang): das ist der
#: Vergleichsgegenstand. Was er danach selbst schreibt, ist sein Stand und darf
#: abweichen -- eine Datei, die sich nach dem Lesen nie aendert, waere tot.
KIND_FRAGEN = (
    IMPORTE
    + """
gelesen = {
    name: ((ordner / name).read_text(encoding="utf-8")
           if (ordner / name).is_file() else "<fehlt>")
    for name in DREI
}
"""
    + KERN
    + """
urteil = _autorisiere(kern, _konto("10000"), TS + timedelta(hours=2))
befund = SchwebeAkte(ordner / SCHWEBEAKTE_DATEI).laden()
print(json.dumps({
    "gelesen": gelesen,
    "approved": urteil.approved,
    "latch_halt": urteil.latch_halt,
    "reason": urteil.reason or "",
    "zustand_dauerhaft": kern.zustand_dauerhaft,
    "schwebende": [e.client_order_id for e in befund.eintraege],
    "buch": [p.kennung for p in Positionsbuch(ordner / POSITIONSBUCH_DATEI).laden()],
}, ensure_ascii=False))
"""
)


def kanonisch_text(roh: str) -> str:
    """Ein Dateiinhalt als sortiertes JSON -- vergleichbar, ohne Rauschen."""
    if roh == "<fehlt>":
        return roh
    try:
        return json.dumps(json.loads(roh), sort_keys=True, ensure_ascii=False)
    except json.JSONDecodeError:
        zeilen = [z for z in roh.splitlines() if z.strip()]
        return " | ".join(
            json.dumps(json.loads(z), sort_keys=True, ensure_ascii=False)
            for z in zeilen
        )


def kanonisch(ordner: Path) -> dict[str, str]:
    """Die drei Zustandsdateien als sortiertes JSON -- vergleichbar, ohne Rauschen."""
    aus: dict[str, str] = {}
    for name in (RISIKOZUSTAND_DATEI, SCHWEBEAKTE_DATEI, POSITIONSBUCH_DATEI):
        pfad = ordner / name
        if not pfad.is_file():
            aus[name] = "<fehlt>"
            continue
        aus[name] = kanonisch_text(pfad.read_text(encoding="utf-8"))
    return aus


def abschiessen(prozess: subprocess.Popen[str]) -> str:
    """Hart, ohne Aufraeumen. Windows: ``taskkill /F``; sonst ``SIGKILL``."""
    if platform.system() == "Windows":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(prozess.pid)],
            capture_output=True,
            check=False,
        )
        art = "taskkill /F /T"
    else:
        os.kill(prozess.pid, signal.SIGKILL)
        art = "SIGKILL"
    prozess.wait(timeout=30)
    return f"{art} -> Rueckgabewert {prozess.returncode}"


def warte_auf(bedingung: Callable[[], bool], sekunden: float = 60.0) -> bool:
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.2)
    return False


def teil1_werkzeug(basis: Path) -> bool:
    """``live_betrieb --terminal fake`` mitten im Takt abschiessen."""
    ordner = basis / "werkzeug"
    print("\n== TEIL 1: das Betriebswerkzeug wird mitten im Takt abgeschossen ==")
    lauf = subprocess.Popen(
        [
            sys.executable,
            "-B",
            "tools/live_betrieb.py",
            "--terminal",
            "fake",
            "--zustandsordner",
            str(ordner),
            "--dauer",
            "1",
            "--takt",
            "1",
        ],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    zustand = ordner / RISIKOZUSTAND_DATEI
    if not warte_auf(lambda: zustand.is_file() and (ordner / "journale").is_dir()):
        lauf.kill()
        print("  ROT: der Lauf hat in 60 s keinen Zustand geschrieben")
        return False
    time.sleep(2.0)  # mindestens ein voller Takt
    print(f"  {abschiessen(lauf)}")

    journale = sorted((ordner / "journale").glob("*.jsonl"))
    saetze = [
        json.loads(z)
        for j in journale
        for z in j.read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    gelesen = json.loads(zustand.read_text(encoding="utf-8"))
    print(f"  Zustandsdatei lesbar, Felder: {sorted(gelesen)[:5]} ...")
    print(f"  Journale: {len(journale)} Datei(en), {len(saetze)} Saetze, alle lesbar")
    print(f"  Satzarten: {sorted({str(s.get('art')) for s in saetze})}")
    reste = [p.name for p in ordner.glob("*.neu")] + [
        p.name for p in ordner.glob("*.tmp")
    ]
    print(f"  halb geschriebene Reste (*.neu, *.tmp): {reste or 'keine'}")
    ok = bool(journale) and bool(saetze) and isinstance(gelesen, dict) and not reste
    print(f"  -> {'GRUEN' if ok else 'ROT'}: nichts halb geschrieben")
    return ok


def _kind(quelle: str, ordner: Path, *, warten: bool) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-B", "-c", quelle, str(REPO), str(ordner)],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def teil2_bedeutung(basis: Path) -> bool:
    """Zustand setzen, abschiessen, mit vollem Konto erneut fragen."""
    ordner = basis / "bedeutung"
    print("\n== TEIL 2: Halt, Schwebeakte, Buch -- und dann der Abschuss ==")
    kind = _kind(KIND_SETZEN, ordner, warten=True)
    kopf = kind.stdout.readline().strip() if kind.stdout else ""
    if kopf != "BEREIT":
        kind.kill()
        rest = kind.stdout.read() if kind.stdout else ""
        print(f"  ROT: der Kindprozess meldete {kopf!r} statt BEREIT")
        print(rest[:1200])
        return False

    vorher = kanonisch(ordner)
    print(f"  {abschiessen(kind)}")
    for name, text in vorher.items():
        print(f"  {name}: {len(text)} Zeichen kanonisch")

    antwort = subprocess.run(
        [sys.executable, "-B", "-c", KIND_FRAGEN, str(REPO), str(ordner)],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if antwort.returncode != 0:
        print("  ROT: der Neustart scheiterte")
        print((antwort.stdout + antwort.stderr)[-1500:])
        return False
    gelesen = json.loads(antwort.stdout.strip().splitlines()[-1])
    print("  Neustart mit VOLLEM Konto (10.000, der Drawdown ist weg) sagt:")
    for schluessel, wert in gelesen.items():
        if schluessel == "gelesen":
            continue  # der Inhalt steht als Vergleich unten, nicht als Wand
        print(f"    {schluessel}: {wert}")

    # Der Vergleich: was der Neustart VORFAND gegen das, was der Abschuss
    # hinterliess. Was der Neustart danach selbst schreibt, ist sein eigener
    # Stand -- eine Zustandsdatei, die sich nach dem Lesen nie aendert, waere tot.
    gefunden = {name: kanonisch_text(text) for name, text in gelesen["gelesen"].items()}
    gleich = {k: vorher[k] == gefunden.get(k) for k in vorher}
    print(f"  der Neustart fand vor, was der Abschuss hinterliess: {gleich}")

    ok = (
        gelesen["approved"] is False
        and gelesen["latch_halt"] is True
        and gelesen["zustand_dauerhaft"] is True
        and gelesen["schwebende"] == ["open-EURUSD-kill"]
        and gelesen["buch"] == ["open-EURUSD-kill"]
        and ("gelatcht" in gelesen["reason"] or "drawdown" in gelesen["reason"])
        and all(gleich.values())
    )
    print(f"  -> {'GRUEN' if ok else 'ROT'}: der Zustand hat den Abschuss ueberlebt")
    return ok


def main() -> int:
    print("KILL-EICHFALL (A6) -- ueberlebt der Zustand einen harten Abschuss?")
    print(
        f"Rechner: {platform.system()} {platform.release()}, "
        f"Python {sys.version.split()[0]}"
    )
    print(f"Zeit: {datetime.now(UTC).isoformat(timespec='seconds')}")
    basis = Path(tempfile.mkdtemp(prefix="kill-eichfall-"))
    print(f"Zustandsordner: <temp>/{basis.name} (ausserhalb des Arbeitsbaums, A18)")
    eins = teil1_werkzeug(basis)
    zwei = teil2_bedeutung(basis)
    print(
        f"\nERGEBNIS: Teil 1 {'gruen' if eins else 'rot'}, "
        f"Teil 2 {'gruen' if zwei else 'rot'}"
    )
    return 0 if (eins and zwei) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Zweigdeckung je Datei des Geldpfads -- mit Schwelle, nicht als Bericht.

WARUM ZWEIGE UND NICHT ZEILEN
-----------------------------
Eine Zeilendeckung von 95 % kann bedeuten, dass jede ``if``-Bedingung genau einmal
gelaufen ist -- immer in dieselbe Richtung. Der ganze Sinn einer Sperre liegt aber im
**anderen** Zweig: dem, der ablehnt. Zeilendeckung misst, ob Code beruehrt wurde;
Zweigdeckung misst, ob beide Ausgaenge einer Entscheidung beruehrt wurden.

**Je Datei, nicht als Gesamtzahl.** Eine Gesamtdeckung von 87 % kann eine Datei mit
99 % und eine mit 40 % bedeuten, und die mit 40 % ist die interessante.

DIE SCHWELLE
------------
:data:`MINDEST_ZWEIGDECKUNG` steht auf **0,90** (Abnahmekatalog A15, Programm
NEUAUFBAU).
Bis Auftrag 1 stand sie auf 0,80; die Anhebung ist eine Verschaerfung, keine Anpassung
an den Befund: bei der Grundmessung (Beleg ``03-grundmessung-coverage-direkt-worktree``)
lagen drei der elf Dateien zwischen 80 % und 90 % (``venue/mt5.py`` 80,7 %,
``risk/leverage.py`` 83,3 %, ``costs/model.py`` 83,3 %) -- das Tor ist mit 0,90 also
**rot**, und das ist der Zweck: es nennt je Datei die fehlenden Zweige, damit jemand die
Tests ergaenzt. Wer die Schwelle senkt, weil eine Datei stoert, hebt sie nicht auf,
sondern schafft sie ab.

WIE GEMESSEN WIRD
-----------------
``--messen`` faehrt die Suite (ohne ``slow``) unter ``coverage --branch`` -- nicht im
Arbeitsbaum, sondern in einer **Kopie** des Arbeitsbaums ohne Ignoriertes
(``git ls-files --cached --others --exclude-standard``: verfolgte und neue Dateien im
Stand des Arbeitsbaums, nichts aus ``.gitignore`` wie ``betrieb/``, ``daten/``,
``__pycache__``; dazu ``aufzeichnungen/`` und ``config/`` vollstaendig), mit
``PYTHONDONTWRITEBYTECODE=1``. Der Arbeitsbaum bekommt weder ``.coverage`` noch
``__pycache__`` ab (Katalog A18). Die Kopie ist ein eigenes Wegwerf-Git (``git init``,
ein Commit), weil Werkzeuge und Tests ``git ls-files`` und ``git rev-parse`` lesen.
Dieselbe Kopie benutzt ``tools/mutationstor.py``.

Unterprozesse werden mit ``encoding="utf-8", errors="replace"`` gelesen. Unter Windows
las die alte Fassung mit cp1252: der Leser-Thread starb an einem ``UnicodeDecodeError``,
``stdout`` blieb ``None``, und das Werkzeug stuerzte mit ``TypeError`` ab, statt zu
urteilen (Beleg ``03-grundmessung-mutation-pycache-worktree.txt``).

**Rote Suite.** Faellt in der Kopie ein Test (pytest exit 1), wird die Deckung trotzdem
berichtet -- sie ist die Messung dessen, was gelaufen ist --, aber das Tor bleibt rot
und nennt die roten Faelle (Knotenkennungen aus den ``FAILED``/``ERROR``-Zeilen). Kann
pytest nicht laufen (exit >= 2: Sammelfehler, Abbruch) oder laesst sich kein roter Fall
benennen, gibt es keinen Bericht und kein Urteil. Ein gruenes Urteil setzt eine gruene
Suite voraus; ein rotes Urteil ohne Zahl hilft niemandem.

Aufruf::

    python tools/zweigdeckung.py --messen            # Kopie, Suite unter coverage
    python tools/zweigdeckung.py --bericht DATEI     # urteilt ueber eine Messung
    python tools/zweigdeckung.py --messen --zweige   # fehlende Zweige aller Dateien
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Die Schwelle je Datei. Begruendung im Modul-Docstring; Katalog A15: nie gesenkt.
MINDEST_ZWEIGDECKUNG = 0.90

#: Die kritischen Dateien des Geldpfads -- dieselbe Menge, die das Mutationstor trifft.
#: Ausdruecklich aufgezaehlt und nicht per Muster gesucht: eine neue Datei soll bewusst
#: aufgenommen werden, nicht stillschweigend mitlaufen.
GELDPFAD: tuple[str, ...] = (
    "venue/mt5.py",
    "venue/protocol.py",
    "execution/risk_manager.py",
    "execution/schwebende_auftraege.py",
    "execution/cost_gate.py",
    "risk/sizing.py",
    "risk/stop_budget.py",
    "risk/limits.py",
    "risk/leverage.py",
    "costs/model.py",
    "gates/erkundung.py",
    # E-020: in Auftrag 1 dazugekommen bzw. nach dem Kriterium nachgetragen.
    "risk/waehrung.py",
    "execution/handelspause.py",
    "execution/reconcile.py",
)

#: Verzeichnisse, die zusaetzlich zu den verfolgten Dateien in die Kopie wandern
#: (eingecheckte Aufzeichnung und Konfiguration; auch unverfolgte Dateien darunter).
KOPIE_ZUSAETZLICH: tuple[str, ...] = ("aufzeichnungen", "config")

#: Die Suite, die in der Kopie laeuft: ohne ``slow`` (die slow-Faelle fahren selbst ein
#: Tor in einer Kopie) und ohne die Eichfaelle des Mutationstors (sie fahren ebenfalls
#: Kopie und Unterprozess; in der Kopie liefen sie verschachtelt).
SUITE_ARGUMENTE: tuple[str, ...] = (
    "-q",
    "-p",
    "no:cacheprovider",
    "-m",
    "not slow",
    "--ignore=tests/eichfall_mutationstor.py",
)

#: ``FAILED tests/x.py::test_y - ...`` / ``ERROR tests/x.py`` im Kurzbericht von pytest
#: (``-q`` druckt ihn noch; ``-qq`` nicht -- darum steht in SUITE_ARGUMENTE ein ``-q``).
_FEHLSCHLAG = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)


def fehlschlaege(ausgabe: str) -> tuple[str, ...]:
    """Die roten Faelle eines pytest-Laufs als Knotenkennungen, in Reihenfolge, ohne
    Dubletten. Eine Kennung mit Leerzeichen in der Parametrisierung wird am ersten
    Leerzeichen abgeschnitten; ``--deselect`` vergleicht Praefixe, das reicht."""
    return tuple(dict.fromkeys(_FEHLSCHLAG.findall(ausgabe)))


def _kurzname(pfad: str) -> str:
    return pfad.replace(os.sep, "/").split("mt5_trading_ai/", 1)[-1]


def kopie_umgebung() -> dict[str, str]:
    """Umgebung fuer Unterprozesse in der Kopie: kein Bytecode, utf-8-Ausgabe."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class KopieFehler(RuntimeError):
    """Die Kopie laesst sich nicht anlegen (kein Git, ``git add`` scheitert ...)."""


def _dateien_des_arbeitsbaums(wurzel: Path) -> list[str]:
    """Verfolgte und unverfolgte, nicht ignorierte Dateien -- der Arbeitsbaum, wie
    ihn ein Entwickler sieht (eine neue Testdatei zaehlt, ``betrieb/`` nicht)."""
    try:
        lauf = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=wurzel,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise KopieFehler(f"git ls-files in {wurzel}: {exc}") from exc
    if lauf.returncode != 0:
        grund = lauf.stderr.decode("utf-8", "replace").strip()[-300:]
        raise KopieFehler(
            f"git ls-files in {wurzel}: exit={lauf.returncode}: {grund or '(leer)'}"
        )
    return list(
        dict.fromkeys(
            eintrag.decode("utf-8", "replace")
            for eintrag in lauf.stdout.split(b"\0")
            if eintrag
        )
    )


def repo_kopieren(ziel: Path, wurzel: Path = ROOT) -> int:
    """Kopiere den Arbeitsbaum nach ``ziel`` und mache die Kopie zu einem Wegwerf-Git.

    Kopiert werden die verfolgten und die neuen, nicht ignorierten Dateien im Stand
    des Arbeitsbaums (:func:`_dateien_des_arbeitsbaums`) sowie alles unter
    :data:`KOPIE_ZUSAETZLICH` (ohne ``__pycache__``). ``betrieb/``, ``daten/``,
    ``.git`` und jeder andere Laufzeitzustand bleiben draussen. Der Arbeitsbaum wird nur
    gelesen. Rueckgabe: Anzahl der kopierten Dateien. Wirft :class:`KopieFehler`.
    """
    ziel.mkdir(parents=True, exist_ok=True)
    kopiert: set[str] = set()
    for rel in _dateien_des_arbeitsbaums(wurzel):
        quelle = wurzel / rel
        if not quelle.is_file():
            continue  # im Index, aber nicht im Arbeitsbaum (geloescht, nicht committed)
        nach = ziel / rel
        nach.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(quelle, nach)
        kopiert.add(rel)
    for ordner in KOPIE_ZUSAETZLICH:
        start = wurzel / ordner
        if not start.is_dir():
            continue
        for quelle in sorted(start.rglob("*")):
            if not quelle.is_file() or "__pycache__" in quelle.parts:
                continue
            rel = quelle.relative_to(wurzel).as_posix()
            if rel in kopiert:
                continue
            nach = ziel / rel
            nach.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(quelle, nach)
            kopiert.add(rel)
    _wegwerf_git(ziel)
    return len(kopiert)


def _schreibbar_und_nochmal(
    funktion: Callable[[str], object], pfad: str, _exc: object
) -> None:
    # Windows: Git legt seine Objekte schreibgeschuetzt an, und ``rmtree`` bricht
    # daran ab -- also Schreibrecht setzen und den Schritt wiederholen.
    os.chmod(pfad, stat.S_IWRITE)
    funktion(pfad)


def kopie_entfernen(pfad: Path) -> None:
    """Die Kopie samt Wegwerf-Git loeschen; schreibgeschuetzte Dateien inbegriffen."""
    if pfad.exists():
        shutil.rmtree(pfad, onerror=_schreibbar_und_nochmal)


#: Versuche fuer jeden Git-Befehl in der Kopie (F-008: unter Last hielt ein
#: Virenscanner Dateien laenger fest, als drei Versuche abdeckten).
VERSUCHE_WEGWERF_GIT = 6


def _wegwerf_git(ziel: Path) -> None:
    """Ein eigenes Git in der Kopie -- ohne Hooks, ohne Remote, ohne Signatur."""
    basis = [
        "git",
        "-c",
        "user.name=zweigdeckung-kopie",
        "-c",
        "user.email=kopie@lokal",
        "-c",
        "commit.gpgsign=false",
        "-c",
        # Windows: die Kopie liegt tief im Temp-Verzeichnis; ohne longpaths bricht
        # ``git add`` bei Pfaden ueber 260 Zeichen ab ("Filename too long").
        "core.longpaths=true",
        "-c",
        # Ein nicht vorhandenes Hook-Verzeichnis: kein Hook des Arbeitsbaums greift.
        f"core.hooksPath={(ziel / '.keine-hooks').as_posix()}",
    ]
    for befehl in (
        ["init", "-q"],
        ["add", "-A"],
        [
            "commit",
            "-q",
            "--no-verify",
            "-m",
            "Kopie fuer Zweigdeckung und Mutationstor",
        ],
    ):
        # Sechs Versuche mit wachsender Wartezeit: unter Windows haelt ein
        # Virenscanner frisch kopierte Dateien kurz fest, und ``git add`` endet dann
        # mit exit 128 (gemessen beim ersten Lauf zweier Kopien zugleich). Unter der
        # Last des Pre-Push-Laufs reichten drei Versuche nicht: der Push fiel zweimal
        # an genau dieser Stelle (F-008), einmal zusaetzlich wegen fehlenden Platzes.
        # Der Fehler bleibt hart -- nur die Zahl der Versuche steigt.
        for versuch in range(VERSUCHE_WEGWERF_GIT):
            lauf = subprocess.run(
                [*basis, *befehl],
                cwd=ziel,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env=kopie_umgebung(),
            )
            if lauf.returncode == 0:
                break
            if versuch == VERSUCHE_WEGWERF_GIT - 1:
                raise KopieFehler(
                    f"Wegwerf-Git in {ziel}: git {' '.join(befehl)} endete mit "
                    f"exit={lauf.returncode} nach {VERSUCHE_WEGWERF_GIT} Versuchen: "
                    f"{(lauf.stderr or '').strip()[-500:]}"
                )
            time.sleep(0.5 * 2**versuch)


def _ausgabe(lauf: subprocess.CompletedProcess[str]) -> str:
    """Nie ``None`` slicen: bleibt ein Strom leer, ist es ein leerer Text."""
    return (lauf.stdout or "") + (lauf.stderr or "")


@dataclass(frozen=True)
class Messlauf:
    """Ergebnis eines Suitelaufs unter coverage in der Kopie."""

    rc: int
    ausgabe: str
    dauer: float
    datendatei: Path

    @property
    def fehlschlaege(self) -> tuple[str, ...]:
        return fehlschlaege(self.ausgabe)


@dataclass(frozen=True)
class Messung:
    """Ergebnis von :func:`messen`: ``rc`` 0 nur bei gruener Suite und geschriebenem
    Bericht; ``bericht`` ist der geschriebene Bericht (auch bei roter Suite) oder
    ``None``, wenn nichts messbar war; ``fehlschlaege`` die roten Faelle der Suite."""

    rc: int
    fehlschlaege: tuple[str, ...]
    bericht: Path | None


def _umgebung_mit_coverage(kopie: Path) -> dict[str, str]:
    env = kopie_umgebung()
    env["COVERAGE_FILE"] = str(kopie / ".coverage")
    return env


def deckung_messen(
    kopie: Path, tests: Sequence[str] = ("tests",), kontexte: bool = False
) -> Messlauf:
    """Die Tests in der Kopie unter ``coverage --branch`` fahren (Daten: ``.coverage``).

    ``kontexte``: mit ``dynamic_context = test_function`` -- dann steht je Zeile,
    welche Testfunktion sie ausgefuehrt hat (das Mutationstor liest daraus die
    zustaendigen Tests). Die Konfiguration dafuer liegt als ``.coveragerc-kopie`` in
    der Kopie, nie im Arbeitsbaum; ohne Kontexte gilt ``pyproject.toml``.
    """
    befehl = [sys.executable, "-m", "coverage", "run"]
    if kontexte:
        rc = kopie / ".coveragerc-kopie"
        rc.write_text(
            "[run]\nbranch = True\nsource = mt5_trading_ai\n"
            "dynamic_context = test_function\n",
            encoding="utf-8",
        )
        befehl.append(f"--rcfile={rc}")
    else:
        befehl.extend(["--branch", "--source=mt5_trading_ai"])
    befehl.extend(["-m", "pytest", *SUITE_ARGUMENTE, *tests])
    start = time.perf_counter()
    lauf = subprocess.run(
        befehl,
        cwd=kopie,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_umgebung_mit_coverage(kopie),
        check=False,
    )
    return Messlauf(
        lauf.returncode,
        _ausgabe(lauf),
        time.perf_counter() - start,
        kopie / ".coverage",
    )


def bericht_schreiben(kopie: Path, ziel: Path) -> str | None:
    """``coverage json`` aus der Kopie nach ``ziel``; bei Fehler den Fehlertext."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    bericht = subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", str(ziel.resolve())],
        cwd=kopie,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=_umgebung_mit_coverage(kopie),
        check=False,
    )
    if bericht.returncode != 0:
        return _ausgabe(bericht).strip()
    return None


def messen(
    ziel: Path,
    kopie: Path | None = None,
    tests: Sequence[str] = ("tests",),
) -> Messung:
    """Suite unter ``coverage --branch`` in einer Kopie fahren, JSON-Bericht schreiben.

    ``kopie``: Verzeichnis, in dem die Kopie angelegt wird (Vorgabe: temporaer, wird
    danach entfernt). ``tests``: Testpfade fuer pytest (Vorgabe: die ganze Suite).
    Ein alter Bericht unter ``ziel`` wird vorher entfernt, damit nie ein fremder Stand
    beurteilt wird. Kein Traceback: jeder Fehlerpfad endet in einer benannten Zeile.
    """
    temporaer = kopie is None
    basis = Path(tempfile.mkdtemp(prefix="zweigdeckung-")) if kopie is None else kopie
    ziel.unlink(missing_ok=True)
    try:
        start = time.perf_counter()
        try:
            anzahl = repo_kopieren(basis)
        except KopieFehler as exc:
            sys.stdout.flush()
            print(f"FEHLGESCHLAGEN — Kopie: {exc}", file=sys.stderr)
            return Messung(1, (), None)
        print(f"Kopie: {basis} ({anzahl} Dateien, {time.perf_counter() - start:.1f} s)")
        lauf = deckung_messen(basis, tests)
        letzte = (lauf.ausgabe.strip().splitlines() or [""])[-1]
        print(f"Suite unter coverage: exit={lauf.rc}, {lauf.dauer:.0f} s -- {letzte}")
        rot = lauf.fehlschlaege
        if lauf.rc != 0 and (lauf.rc != 1 or not rot):
            sys.stdout.flush()
            print(
                f"FEHLGESCHLAGEN — pytest endete mit exit={lauf.rc}"
                + ("" if lauf.rc != 1 else " ohne benennbaren roten Fall")
                + "; daraus ist keine Deckung zu messen.",
                file=sys.stderr,
            )
            print(lauf.ausgabe[-2000:], file=sys.stderr)
            return Messung(1, rot, None)
        fehler = bericht_schreiben(basis, ziel)
        if fehler is not None:
            sys.stdout.flush()
            print(f"FEHLGESCHLAGEN — coverage json: {fehler}", file=sys.stderr)
            return Messung(1, rot, None)
        print(f"Bericht: {ziel}")
        if rot:
            print(f"Suite rot: {len(rot)} Faelle -- das Tor bleibt rot, s. Urteil.")
            for kennung in rot:
                print(f"    {kennung}")
        return Messung(1 if rot else 0, rot, ziel)
    finally:
        if temporaer:
            kopie_entfernen(basis)


def _zweigziel(ziel: int) -> str:
    # coverage kodiert Funktionsausgaenge als negative Zeilennummern.
    return "Ausgang" if ziel <= 0 else str(ziel)


def fehlende_zweige(eintrag: dict[str, object]) -> list[str]:
    """``["106->111", "152->153"]`` -- die nicht gelaufenen Zweige einer Datei."""
    roh = eintrag.get("missing_branches", [])
    aus: list[str] = []
    if isinstance(roh, list):
        for paar in roh:
            if isinstance(paar, list) and len(paar) == 2:
                von, nach = int(paar[0]), int(paar[1])
                aus.append(f"{von}->{_zweigziel(nach)}")
    return aus


def urteile(
    bericht: Path, zeige_zweige: bool = False, suite_rot: Sequence[str] = ()
) -> int:
    """Urteil ueber einen Bericht; ``suite_rot`` (rote Faelle der Messung) macht das
    Urteil rot, auch wenn jede Datei ueber der Schwelle liegt."""
    sys.stdout.flush()
    if not bericht.is_file():
        print(f"FEHLGESCHLAGEN — {bericht} fehlt. Erst --messen.", file=sys.stderr)
        return 1
    try:
        daten = json.loads(bericht.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FEHLGESCHLAGEN — {bericht} unlesbar: {exc}", file=sys.stderr)
        return 1
    if not isinstance(daten, dict) or "files" not in daten or "totals" not in daten:
        print(f"FEHLGESCHLAGEN — {bericht} ist kein coverage-Bericht.", file=sys.stderr)
        return 1
    gemessen = {_kurzname(f): v for f, v in daten["files"].items()}

    print("=" * 74)
    print("ZWEIGDECKUNG JE DATEI DES GELDPFADS")
    print("=" * 74)
    print(f"Schwelle je Datei: {MINDEST_ZWEIGDECKUNG:.0%} (Katalog A15)")
    print()
    print(f"{'Datei':<40}{'Zeilen':>9}{'Zweige':>9}{'fehlend':>9}")

    zu_niedrig: list[tuple[str, float, list[str]]] = []
    fehlend: list[str] = []
    zweige_je_datei: dict[str, list[str]] = {}
    for name in GELDPFAD:
        eintrag = gemessen.get(name)
        if eintrag is None:
            # Laut scheitern: eine Datei des Geldpfads, die in der Messung fehlt, ist
            # ein Befund und kein Grund, sie zu ueberspringen.
            fehlend.append(name)
            print(f"{name:<40}{'--':>9}{'FEHLT':>9}{'--':>9}")
            continue
        s = eintrag["summary"]
        zweige = s.get("num_branches", 0)
        anteil = s.get("covered_branches", 0) / zweige if zweige else 1.0
        offen = fehlende_zweige(eintrag)
        zweige_je_datei[name] = offen
        marke = "" if anteil >= MINDEST_ZWEIGDECKUNG else "  <== unter der Schwelle"
        print(
            f"{name:<40}{s['percent_covered']:>8.1f}%{anteil * 100:>8.1f}%"
            f"{len(offen):>9}{marke}"
        )
        if anteil < MINDEST_ZWEIGDECKUNG:
            zu_niedrig.append((name, anteil, offen))

    g = daten["totals"]
    gesamt = g.get("covered_branches", 0) / max(1, g.get("num_branches", 1))
    print()
    print(
        f"Paket gesamt: Zeilen {g['percent_covered']:.1f} %, "
        f"Zweige {gesamt * 100:.1f} %"
    )

    # Die fehlenden Zweige je Datei -- fuer die roten Dateien immer, fuer alle mit
    # --zweige. Das ist die Arbeitsliste fuer die Tests, die noch fehlen.
    zu_zeigen = (
        [(n, z) for n, z in zweige_je_datei.items() if z]
        if zeige_zweige
        else [(n, z) for n, _a, z in zu_niedrig]
    )
    for name, offen in zu_zeigen:
        print()
        print(f"{name}: {len(offen)} fehlende Zweige (Zeile->Ziel)")
        for i in range(0, len(offen), 8):
            print("    " + ", ".join(offen[i : i + 8]))
        zeilen = gemessen[name].get("missing_lines", [])
        if zeilen:
            print(f"    nicht gelaufene Zeilen: {', '.join(str(z) for z in zeilen)}")

    if fehlend or zu_niedrig or suite_rot:
        print()
        # stdout leeren, bevor stderr schreibt (Reihenfolge in Umleitungen).
        sys.stdout.flush()
        if suite_rot:
            print(
                f"FEHLGESCHLAGEN — die Suite ist rot ({len(suite_rot)} Faelle); die "
                "Deckung oben stammt aus einem roten Lauf, ein gruenes Urteil setzt "
                "eine gruene Suite voraus: " + ", ".join(suite_rot),
                file=sys.stderr,
            )
        for name in fehlend:
            print(f"FEHLGESCHLAGEN — {name} fehlt in der Messung.", file=sys.stderr)
        for name, anteil, offen in zu_niedrig:
            print(
                f"FEHLGESCHLAGEN — {name}: {anteil:.1%} Zweigdeckung, "
                f"verlangt sind {MINDEST_ZWEIGDECKUNG:.0%} "
                f"({len(offen)} Zweige fehlen).",
                file=sys.stderr,
            )
        if fehlend or zu_niedrig:
            print(
                "Was fehlt, sind in aller Regel die ablehnenden Zweige -- also die, "
                "wegen derer die Datei existiert.",
                file=sys.stderr,
            )
        return 1
    print("ok — jede Datei des Geldpfads ueber der Schwelle.")
    return 0


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Zweigdeckungstor auf dem Geldpfad")
    ap.add_argument(
        "--messen",
        action="store_true",
        help="erst die Suite (ohne slow) unter coverage in einer Kopie fahren",
    )
    ap.add_argument(
        "--bericht",
        type=Path,
        default=None,
        help="coverage-JSON (Vorgabe: <temp>/zweigdeckung/coverage.json)",
    )
    ap.add_argument(
        "--kopie",
        type=Path,
        default=None,
        help="Verzeichnis fuer die Kopie (Vorgabe: temporaer, wird entfernt)",
    )
    ap.add_argument(
        "--zweige",
        action="store_true",
        help="fehlende Zweige auch fuer Dateien ueber der Schwelle zeigen",
    )
    args = ap.parse_args()

    bericht: Path = (
        args.bericht
        if args.bericht is not None
        else Path(tempfile.gettempdir()) / "zweigdeckung" / "coverage.json"
    )
    if args.messen:
        messung = messen(bericht, kopie=args.kopie)
        if messung.bericht is None:
            return messung.rc
        return urteile(
            messung.bericht, zeige_zweige=args.zweige, suite_rot=messung.fehlschlaege
        )
    return urteile(bericht, zeige_zweige=args.zweige)


if __name__ == "__main__":
    raise SystemExit(main())

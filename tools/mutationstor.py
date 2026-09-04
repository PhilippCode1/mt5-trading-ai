#!/usr/bin/env python3
"""Mutationstor: faellt eine Aenderung am Geldpfad auf -- oder merkt es keiner?

WORUM ES GEHT
-------------
Eine Testsuite mit 1.500 gruenen Faellen sagt nichts darueber, ob sie **wirkt**. Sie
sagt nur, dass niemand sie hat rot werden lassen. Die Frage dieses Tors ist die
umgekehrte: wenn ich am Geldpfad etwas kaputt mache -- merkt es jemand?

ZWEI TORE, KEINE SCHWELLE GESENKT (Katalog A4, A17; Entscheidung E-006)
-----------------------------------------------------------------------
1. **Der handverlesene Katalog** (:data:`KATALOG`). Jeder Eintrag ist ein echter
   Rueckfall: eine Sperre uebersprungen, eine Grenze verschoben, eine Vergleichsrichtung
   umgedreht. Schwelle :data:`MINDEST_TOETUNGSRATE` = **1,0**: der Katalog ist von Hand
   ausgewaehlt, und eine Rate von 0,9 hiesse, dass einer der Defekte unbemerkt
   durchginge -- welcher, waere Zufall.
2. **Erzeugte Sonden** (:func:`erzeugte_sonden`) ueber **alle** Dateien des Geldpfads
   (:data:`tools.zweigdeckung.GELDPFAD`). Operatoren: Vergleich kippen (``<`` <->
   ``<=``, ``>`` <-> ``>=``, ``==`` <-> ``!=``, ``is`` <-> ``is not``, ``in`` <->
   ``not in``), Konstante +1, ``not`` entfernen, ``if``-Bedingung negieren, ``and`` <->
   ``or``, ``return True`` <-> ``return False``. Mindestens
   :data:`MINDEST_SONDEN_JE_DATEI` je Datei, Katalog und erzeugte zusammen mindestens
   :data:`MINDEST_SONDEN_GESAMT`, Gesamtrate mindestens
   :data:`MINDEST_TOETUNGSRATE_GESAMT` = **0,90**. Liegt die gemessene Rate darunter,
   bleibt das Tor rot und nennt die ueberlebenden Sonden beim Namen: das sind
   Testluecken, kein Grund, die Schwelle zu senken.

**Auswahl, deterministisch.** Je Datei werden alle Kandidatenstellen aus dem
Syntaxbaum gesammelt und nach (Zeile, Spalte, Operator) sortiert. Die Quote je Datei
ist ``max(3, ceil(50 * sqrt(k_i) / sum_j sqrt(k_j)))`` mit ``k`` = Kandidatenzahl
(Wurzel, damit ``venue/mt5.py`` mit der Haelfte aller Kandidaten nicht die Haelfte
aller Sonden bekommt). Gezogen wird mit ``random.Random(f"{SEED}:{Dateiname}")``
(Seed :data:`SEED`; je Datei ein eigener Strom, damit eine Aenderung in Datei A die
Auswahl in Datei B nicht verschiebt). Ausgeschlossen sind Stellen in ``assert``, in
f-Strings, in Indizes, in Protokoll-/``print``-Aufrufen, auf Zeilen mit
``pragma: no cover``, unter ``if TYPE_CHECKING`` und -- ausser Konstanten in
Zuweisungen -- auf Modulebene: dort steht Belangloses, und eine Toetungsrate ueber
Belanglosem misst nichts.

**Zustaendige Tests, aus der Deckung.** Der Grundlauf faehrt die Suite ohne ``slow``
unmutiert unter ``coverage`` mit ``dynamic_context = test_function``; danach steht je
Quellzeile, welche Testfunktionen sie ausgefuehrt haben. Je erzeugter Sonde gilt:
(a) die Testdateien der Kontexte der mutierten Zeilen, dazu (b) die Testdateien, die
ein Werkzeug als Unterprozess starten und die Datei im Importabschluss haben (Deckung
sieht keinen Unterprozess); (c) tragen die Zeilen den leeren Kontext (ausserhalb einer
Testfunktion ausgefuehrt: Import, Fixture), ist die Zuordnung unbekannt, und es faehrt
die ganze Suite ohne ``slow``; (d) erreicht keine Testdatei die Zeilen, gilt die Sonde
ohne Lauf als ueberlebt -- kein Test kann sie fangen. Die Katalogsonden nennen ihre
Tests selbst: der Ausschnitt ist dort eine Behauptung ("diese Dateien sind fuer diesen
Defekt zustaendig"), die auffallen soll, wenn sie falsch ist.

NIE IM ARBEITSBAUM
------------------
Mutanten laufen in einer **Kopie** des Arbeitsbaums ohne Ignoriertes (verfolgte und
neue Dateien, dazu ``aufzeichnungen/`` und ``config/``;
:func:`tools.zweigdeckung.repo_kopieren`), mit ``cwd`` = Kopie und
``PYTHONDONTWRITEBYTECODE=1``. Der Arbeitsbaum wird nur gelesen. Die Vorgaenger-Fassung
schrieb Mutanten in den Arbeitsbaum und stellte sie aus dem Speicher zurueck; einmal
scheiterte das Zurueckschreiben (F-005), und ein Mutant blieb liegen. Ausserdem
vergiftete jeder Lauf den Bytecode-Cache (Beleg ``03-pycache-mechanik-worktree``).
Beides ist mit der Kopie beseitigt; ``tests/eichfall_mutationstor.py`` misst es.

**Grundlauf.** Bevor ein Mutant laeuft, faehrt das Tor die zustaendigen Tests einmal
**ohne** Mutant in der Kopie. Sonst waere ein roter Lauf mit Mutant kein Beleg (der Test
koennte aus einem anderen Grund fallen). Faellt im Grundlauf ein Test (pytest exit 1),
wird er beim Namen genannt und in **jedem** Mutantenlauf mit ``--deselect`` abgewaehlt:
er kann dann keinen Mutanten toeten, die Rate wird ohne ihn gemessen -- und das Tor
bleibt **rot**, weil ein Teil der Suite ohne Beleg ist (Regel 7: fehlender Wert sperrt).
Kann pytest im Grundlauf nicht laufen (exit >= 2, etwa ein Sammelfehler) oder ist kein
roter Fall benennbar, gibt es kein Urteil (``TorFehler``, exit 2). Jede Toetung nennt
den ersten fallenden Test; der Bericht nennt je erzeugter Sonde die zustaendigen
Testdateien (Deckungs-Dateien zuerst, dann die mit Unterprozess-Reichweite -- mit
``-x`` faellt der Toeter aus der Deckung so frueh).

Aufruf::

    python tools/mutationstor.py                  # beide Tore, blockierend
    python tools/mutationstor.py --liste          # Katalog und erzeugte Sonden zeigen
    python tools/mutationstor.py --sonde N        # einzelne Sonden (Nummer aus --liste)
    python tools/mutationstor.py --selbsttest     # zwei Katalogsonden (der slow-Test)
    python tools/mutationstor.py --katalog        # nur der Katalog (Eichfall gruen)
    python tools/mutationstor.py --parallel 4     # vier Kopien, vier Sonden zugleich
"""

from __future__ import annotations

import argparse
import ast
import functools
import hashlib
import math
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    # Als Skript: kein Bytecode aus diesem Prozess in den Arbeitsbaum (A18).
    sys.dont_write_bytecode = True

from tools.zweigdeckung import (  # noqa: E402
    GELDPFAD,
    SUITE_ARGUMENTE,
    KopieFehler,
    deckung_messen,
    fehlschlaege,
    kopie_entfernen,
    kopie_umgebung,
    repo_kopieren,
)

#: Schwelle des handverlesenen Katalogs. Begruendung im Modul-Docstring; nie gesenkt.
MINDEST_TOETUNGSRATE = 1.0
#: Schwelle ueber Katalog und erzeugte Sonden zusammen (Katalog A4, A17).
MINDEST_TOETUNGSRATE_GESAMT = 0.90
#: Mindestzahl aller Sonden (Katalog + erzeugt) fuer ein gueltiges Urteil (A4).
MINDEST_SONDEN_GESAMT = 50
#: Mindestzahl erzeugter Sonden je Datei des Geldpfads (A17).
MINDEST_SONDEN_JE_DATEI = 3
#: Zielzahl erzeugter Sonden, auf die Dateien nach Wurzel der Kandidatenzahl verteilt.
ZIEL_ERZEUGT = 50
#: Seed der Auswahl; Verfahren im Modul-Docstring.
SEED = 20260903
#: Die ganze Suite ohne ``slow`` -- der Rueckfall bei unbekannter Zuordnung.
SUITE: tuple[str, ...] = ("tests",)
#: Zeitlimit je pytest-Lauf, mindestens (ein Mutant kann eine Schleife endlos machen;
#: ein Zeitueberschreiten gilt als Toetung, wird aber genannt).
ZEITLIMIT_MINDESTENS = 600.0


@dataclass(frozen=True)
class Sonde:
    """Eine benannte Mutation samt dem Testausschnitt, der sie fangen soll.

    Katalogsonden tragen ``alt`` als Ankertext (erste Fundstelle wird ersetzt) und
    nennen ihre ``tests``. Erzeugte Sonden tragen in ``alt`` die vollstaendigen
    Quellzeilen ab ``zeile`` und werden nur dort angewendet -- ein kurzer Anker wie
    ``<`` waere mehrdeutig; ihre Tests kommen zur Laufzeit aus der Deckung (``tests``
    leer).
    """

    name: str
    datei: str
    alt: str
    neu: str
    tests: tuple[str, ...]
    #: Was der Defekt in der Sache bedeutet. Steht in der Ausgabe, damit eine
    #: ueberlebende Sonde nicht nur eine Nummer ist.
    bedeutet: str
    zeile: int | None = None
    operator: str = ""
    herkunft: str = "katalog"

    @property
    def zeilen(self) -> tuple[int, ...]:
        """Die mutierten Zeilennummern (leer bei Katalogsonden)."""
        if self.zeile is None:
            return ()
        return tuple(range(self.zeile, self.zeile + self.alt.count("\n") + 1))


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
        # Seit D8 (E-005) gibt es in ``laden`` keinen fluechtigen Zweig mehr, der sich
        # erzwingen liesse; die Sonde nimmt darum den Schreibvorgang selbst: die
        # Nebendatei wird verworfen statt an ihren Platz gesetzt -- die Akte ueberlebt
        # den Prozess nicht.
        name="schwebeakte-fluechtig",
        datei="mt5_trading_ai/execution/schwebende_auftraege.py",
        alt=(
            '        neben.write_text(inhalt, encoding="utf-8")\n'
            "        os.replace(neben, self._pfad)"
        ),
        neu=(
            '        neben.write_text(inhalt, encoding="utf-8")\n        neben.unlink()'
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

#: Die zwei Katalogsonden des Selbsttests (``--selbsttest``; der slow-Test der Suite).
SELBSTTEST: tuple[str, ...] = ("stop-kostenboden", "geschlossene-kerze")


class TorFehler(RuntimeError):
    """Das Tor kann nicht urteilen (Grundlauf rot, pytest-Fehler, Kopie defekt)."""


# =====================================================================
# Erzeugte Sonden: Kandidatenstellen aus dem Syntaxbaum
# =====================================================================
_VERGLEICH: dict[type[ast.cmpop], tuple[str, str]] = {
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
    ast.Is: ("is", "is not"),
    ast.IsNot: ("is not", "is"),
    ast.In: ("in", "not in"),
    ast.NotIn: ("not in", "in"),
}
#: Suchmuster je Vergleichsoperator im Segment zwischen den Operanden.
_VERGLEICH_MUSTER: dict[str, bytes] = {
    "<": rb"<",
    "<=": rb"<=",
    ">": rb">",
    ">=": rb">=",
    "==": rb"==",
    "!=": rb"!=",
    "is": rb"\bis\b",
    "is not": rb"\bis\s+not\b",
    "in": rb"\bin\b",
    "not in": rb"\bnot\s+in\b",
}
_PROTOKOLL_NAMEN = frozenset(
    {
        "print",
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "exception",
        "critical",
        "log",
    }
)
_KONSTANTEN_ELTERN: tuple[type[ast.AST], ...] = (
    ast.Compare,
    ast.Return,
    ast.BinOp,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.arguments,
)


@dataclass(frozen=True)
class _Stelle:
    """Ein Bereich im Quelltext und die Bytes, die ihn ersetzen.

    Zeilen 1-basiert, Spalten in utf-8-Bytes (wie ``ast``), Ende exklusiv.
    """

    operator: str
    z1: int
    s1: int
    z2: int
    s2: int
    neu: bytes


def _bereich(zeilen: Sequence[bytes], z1: int, s1: int, z2: int, s2: int) -> bytes:
    if z1 == z2:
        return zeilen[z1 - 1][s1:s2]
    teile = [zeilen[z1 - 1][s1:], *zeilen[z1 : z2 - 1], zeilen[z2 - 1][:s2]]
    return b"\n".join(teile)


def _ende(knoten: ast.AST) -> tuple[int, int]:
    return (
        int(getattr(knoten, "end_lineno", 0)),
        int(getattr(knoten, "end_col_offset", 0)),
    )


def _anfang(knoten: ast.AST) -> tuple[int, int]:
    return int(getattr(knoten, "lineno", 0)), int(getattr(knoten, "col_offset", 0))


def _ist_protokollaufruf(knoten: ast.AST) -> bool:
    if not isinstance(knoten, ast.Call):
        return False
    f = knoten.func
    if isinstance(f, ast.Name):
        return f.id in _PROTOKOLL_NAMEN
    if isinstance(f, ast.Attribute):
        return f.attr in _PROTOKOLL_NAMEN
    return False


def _ist_type_checking(knoten: ast.AST) -> bool:
    return (
        isinstance(knoten, ast.If)
        and isinstance(knoten.test, ast.Name)
        and knoten.test.id == "TYPE_CHECKING"
    )


def _ausgeschlossen(
    eltern: Sequence[ast.AST], knoten: ast.AST, pragma: set[int]
) -> bool:
    if _anfang(knoten)[0] in pragma:
        return True
    for e in eltern:
        if isinstance(e, ast.Assert | ast.JoinedStr | ast.Subscript):
            return True
        if _ist_protokollaufruf(e) or _ist_type_checking(e):
            return True
    return False


def _in_funktion(eltern: Sequence[ast.AST]) -> bool:
    return any(isinstance(e, ast.FunctionDef | ast.AsyncFunctionDef) for e in eltern)


def _konstante_erlaubt(eltern: Sequence[ast.AST], knoten: ast.Constant) -> bool:
    if isinstance(knoten.value, bool) or not isinstance(knoten.value, int | float):
        return False
    elter = eltern[-1]
    if isinstance(elter, ast.UnaryOp) and isinstance(elter.op, ast.USub):
        elter = eltern[-2]
    return isinstance(elter, _KONSTANTEN_ELTERN)


def _konstante_neu(wert: int | float) -> bytes:
    if isinstance(wert, int):
        return str(wert + 1).encode()
    return repr(wert + 1.0).encode()


def _stellen(quelle: str) -> list[_Stelle]:
    """Alle Kandidatenstellen einer Quelldatei (LF-normalisiert), unsortiert."""
    baum = ast.parse(quelle)
    zeilen = quelle.encode("utf-8").split(b"\n")
    pragma = {i for i, z in enumerate(zeilen, 1) if b"pragma: no cover" in z}
    aus: list[_Stelle] = []
    rand: list[tuple[ast.AST, tuple[ast.AST, ...]]] = [(baum, ())]
    while rand:
        knoten, eltern = rand.pop()
        for kind in ast.iter_child_nodes(knoten):
            rand.append((kind, (*eltern, knoten)))
        if not eltern or _ausgeschlossen(eltern, knoten, pragma):
            continue
        aus.extend(_stellen_des_knotens(knoten, eltern, zeilen))
    return aus


def _stellen_des_knotens(
    knoten: ast.AST, eltern: Sequence[ast.AST], zeilen: Sequence[bytes]
) -> list[_Stelle]:
    in_funktion = _in_funktion(eltern)
    if isinstance(knoten, ast.Compare) and in_funktion:
        paar = _VERGLEICH.get(type(knoten.ops[0]))
        if paar is None:
            return []
        z1, s1 = _ende(knoten.left)
        z2, s2 = _anfang(knoten.comparators[0])
        segment = _bereich(zeilen, z1, s1, z2, s2)
        alt_op, neu_op = paar
        muster = re.compile(_VERGLEICH_MUSTER[alt_op])
        if len(muster.findall(segment)) != 1:
            return []
        neu = muster.sub(neu_op.encode(), segment, count=1)
        return [_Stelle("vergleich", z1, s1, z2, s2, neu)]
    if isinstance(knoten, ast.BoolOp) and in_funktion:
        alt_op, neu_op = (
            ("and", "or") if isinstance(knoten.op, ast.And) else ("or", "and")
        )
        z1, s1 = _ende(knoten.values[0])
        z2, s2 = _anfang(knoten.values[1])
        segment = _bereich(zeilen, z1, s1, z2, s2)
        muster = re.compile(rb"\b" + alt_op.encode() + rb"\b")
        if len(muster.findall(segment)) != 1:
            return []
        neu = muster.sub(neu_op.encode(), segment, count=1)
        return [_Stelle("bool", z1, s1, z2, s2, neu)]
    if (
        isinstance(knoten, ast.UnaryOp)
        and isinstance(knoten.op, ast.Not)
        and in_funktion
    ):
        z1, s1 = _anfang(knoten)
        if zeilen[z1 - 1][s1 : s1 + 3] != b"not":
            return []
        return [_Stelle("not-entfernt", z1, s1, z1, s1 + 3, b"")]
    if isinstance(knoten, ast.If) and in_funktion:
        if isinstance(knoten.test, ast.UnaryOp) and isinstance(knoten.test.op, ast.Not):
            return []  # deckt "not-entfernt" ab
        z1, s1 = _anfang(knoten.test)
        z2, s2 = _ende(knoten.test)
        segment = _bereich(zeilen, z1, s1, z2, s2)
        return [_Stelle("not-ergaenzt", z1, s1, z2, s2, b"not (" + segment + b")")]
    if isinstance(knoten, ast.Return) and isinstance(knoten.value, ast.Constant):
        if isinstance(knoten.value.value, bool):
            z1, s1 = _anfang(knoten.value)
            z2, s2 = _ende(knoten.value)
            neu = b"False" if knoten.value.value else b"True"
            return [_Stelle("return", z1, s1, z2, s2, neu)]
    if isinstance(knoten, ast.Constant) and _konstante_erlaubt(eltern, knoten):
        if not in_funktion and not isinstance(eltern[-1], ast.Assign | ast.AnnAssign):
            return []
        z1, s1 = _anfang(knoten)
        z2, s2 = _ende(knoten)
        return [_Stelle("konstante", z1, s1, z2, s2, _konstante_neu(knoten.value))]
    return []


def _sonde_aus_stelle(datei: str, stelle: _Stelle, zeilen: Sequence[bytes]) -> Sonde:
    alt_zeilen = list(zeilen[stelle.z1 - 1 : stelle.z2])
    vorher = zeilen[stelle.z1 - 1][: stelle.s1]
    nachher = zeilen[stelle.z2 - 1][stelle.s2 :]
    neu_zeilen = (vorher + stelle.neu + nachher).split(b"\n")
    alt = b"\n".join(alt_zeilen).decode("utf-8")
    neu = b"\n".join(neu_zeilen).decode("utf-8")
    kurz = datei.split("mt5_trading_ai/", 1)[-1]
    segment_alt = _bereich(zeilen, stelle.z1, stelle.s1, stelle.z2, stelle.s2)
    beschreibung = (
        f"{_kurz(segment_alt.decode('utf-8'))} -> {_kurz(stelle.neu.decode('utf-8'))}"
    )
    return Sonde(
        name=f"{kurz}:{stelle.z1}:{stelle.s1}:{stelle.operator}",
        datei=datei,
        alt=alt,
        neu=neu,
        tests=(),
        bedeutet=beschreibung,
        zeile=stelle.z1,
        operator=stelle.operator,
        herkunft="erzeugt",
    )


def _kurz(text: str, breite: int = 48) -> str:
    text = " ".join(text.split())
    if not text:
        return "''"
    return f"'{text}'" if len(text) <= breite else f"'{text[: breite - 3]}...'"


def _quelltext(datei: str) -> str:
    return (ROOT / datei).read_text(encoding="utf-8").replace("\r\n", "\n")


def kandidaten_je_datei() -> dict[str, list[_Stelle]]:
    """Alle Kandidatenstellen je Geldpfad-Datei, sortiert nach Zeile und Spalte."""
    aus: dict[str, list[_Stelle]] = {}
    for kurz in GELDPFAD:
        datei = f"mt5_trading_ai/{kurz}"
        stellen = _stellen(_quelltext(datei))
        aus[datei] = sorted(stellen, key=lambda s: (s.z1, s.s1, s.operator))
    return aus


def quoten(kandidaten: dict[str, list[_Stelle]]) -> dict[str, int]:
    """Quote je Datei: ``max(3, ceil(ZIEL_ERZEUGT * sqrt(k_i) / sum sqrt(k_j)))``."""
    gewichte = {d: math.sqrt(len(s)) for d, s in kandidaten.items()}
    summe = sum(gewichte.values())
    if summe == 0:
        raise TorFehler(
            "keine Kandidatenstellen im Geldpfad -- Pruefung ohne Gegenstand"
        )
    aus: dict[str, int] = {}
    for datei, stellen in kandidaten.items():
        if len(stellen) < MINDEST_SONDEN_JE_DATEI:
            raise TorFehler(
                f"{datei}: nur {len(stellen)} Kandidatenstellen, verlangt sind "
                f"{MINDEST_SONDEN_JE_DATEI} Sonden"
            )
        anteil = math.ceil(ZIEL_ERZEUGT * gewichte[datei] / summe)
        aus[datei] = min(len(stellen), max(MINDEST_SONDEN_JE_DATEI, anteil))
    return aus


@functools.lru_cache(maxsize=1)
def erzeugte_sonden() -> tuple[Sonde, ...]:
    """Die erzeugten Sonden -- deterministisch aus dem heutigen Quelltext."""
    kandidaten = kandidaten_je_datei()
    quote = quoten(kandidaten)
    aus: list[Sonde] = []
    for datei, stellen in kandidaten.items():
        zeilen = _quelltext(datei).encode("utf-8").split(b"\n")
        rng = random.Random(f"{SEED}:{datei}")
        gewaehlt = sorted(rng.sample(range(len(stellen)), quote[datei]))
        aus.extend(_sonde_aus_stelle(datei, stellen[i], zeilen) for i in gewaehlt)
    return tuple(aus)


def alle_sonden() -> tuple[Sonde, ...]:
    return (*KATALOG, *erzeugte_sonden())


# =====================================================================
# Reichweite ueber Unterprozesse: Importabschluss je Testdatei
# =====================================================================
_MODULMUSTER = re.compile(r"(mt5_trading_ai|tools)(\.[A-Za-z_][A-Za-z0-9_]*)+")
_WERKZEUGMUSTER = re.compile(r"tools/([A-Za-z_][A-Za-z0-9_]*)\.py")


def _modulname(rel: str) -> str:
    teile = list(Path(rel).with_suffix("").parts)
    if teile and teile[-1] == "__init__":
        teile.pop()
    return ".".join(teile)


def _praefixe(modul: str) -> list[str]:
    teile = modul.split(".")
    return [".".join(teile[: i + 1]) for i in range(len(teile))]


def _importe(pfad: Path, bekannt: frozenset[str]) -> set[str]:
    """Paket- und Werkzeugmodule, die eine Datei importiert oder als Prozess ruft."""
    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    roh: set[str] = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.Import):
            for alias in k.names:
                roh.update(_praefixe(alias.name))
        elif isinstance(k, ast.ImportFrom) and k.level == 0 and k.module:
            roh.update(_praefixe(k.module))
            roh.update(f"{k.module}.{alias.name}" for alias in k.names)
        elif isinstance(k, ast.Constant) and isinstance(k.value, str):
            for treffer in _MODULMUSTER.finditer(k.value):
                roh.update(_praefixe(treffer.group(0)))
            for treffer in _WERKZEUGMUSTER.finditer(k.value):
                roh.add(f"tools.{treffer.group(1)}")
    return {m for m in roh if m in bekannt}


@functools.lru_cache(maxsize=1)
def _modulgraph() -> dict[str, frozenset[str]]:
    module: dict[str, Path] = {}
    for start in ("mt5_trading_ai", "tools"):
        for p in (ROOT / start).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            module[_modulname(p.relative_to(ROOT).as_posix())] = p
    bekannt = frozenset(module)
    return {name: frozenset(_importe(p, bekannt)) for name, p in module.items()}


def _abschluss(start: Iterable[str]) -> set[str]:
    graph = _modulgraph()
    gesehen: set[str] = set()
    rand = list(start)
    while rand:
        m = rand.pop()
        if m in gesehen:
            continue
        gesehen.add(m)
        rand.extend(graph.get(m, ()))
    return gesehen


def _testdateien() -> list[Path]:
    return [
        p
        for p in sorted((ROOT / "tests").glob("*.py"))
        if (p.name.startswith("test_") or p.name.startswith("eichfall_"))
        and p.name != "eichfall_mutationstor.py"
    ]


def _startet_unterprozess(pfad: Path) -> bool:
    try:
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for k in ast.walk(baum):
        if isinstance(k, ast.Import) and any(a.name == "subprocess" for a in k.names):
            return True
        if isinstance(k, ast.ImportFrom) and k.module == "subprocess":
            return True
    return False


@functools.cache
def unterprozess_reichweite(datei: str) -> tuple[str, ...]:
    """Testdateien mit Unterprozess-Start, die ``datei`` im Importabschluss haben.

    Die Deckung des Grundlaufs sieht keinen Unterprozess; diese Dateien koennten die
    mutierte Zeile trotzdem erreichen (``tools/live_betrieb.py --terminal fake`` usw.).
    """
    modul = _modulname(datei)
    bekannt = frozenset(_modulgraph())
    aus: list[str] = []
    for p in _testdateien():
        if not _startet_unterprozess(p):
            continue
        if modul in _abschluss(_importe(p, bekannt)):
            aus.append(f"tests/{p.name}")
    return tuple(aus)


# =====================================================================
# Zuordnung: Tests je Quellzeile aus der Deckung des Grundlaufs
# =====================================================================
@dataclass(frozen=True)
class Zuordnung:
    """Kontexte je Datei und Zeile (``dynamic_context = test_function``)."""

    kontexte: dict[str, dict[int, tuple[str, ...]]]

    @classmethod
    def aus_deckung(cls, datendatei: Path, dateien: Iterable[str]) -> Zuordnung:
        import coverage

        cov = coverage.Coverage(data_file=str(datendatei))
        cov.load()
        daten = cov.get_data()
        gemessen = {Path(f).as_posix(): f for f in daten.measured_files()}
        kontexte: dict[str, dict[int, tuple[str, ...]]] = {}
        for datei in dateien:
            treffer = [f for f in gemessen if f.endswith("/" + datei)]
            if not treffer:
                kontexte[datei] = {}
                continue
            roh = daten.contexts_by_lineno(gemessen[treffer[0]])
            kontexte[datei] = {int(z): tuple(k) for z, k in roh.items()}
        return cls(kontexte)

    def tests_fuer(self, sonde: Sonde) -> tuple[tuple[str, ...], str]:
        """``(Tests, Art)`` -- Art: ``deckung``, ``suite`` oder ``unerreicht``."""
        je_zeile = self.kontexte.get(sonde.datei, {})
        gesehen: set[str] = set()
        for z in sonde.zeilen:
            gesehen.update(je_zeile.get(z, ()))
        deckung: set[str] = set()
        for kontext in gesehen:
            if kontext == "":
                # Ausserhalb einer Testfunktion ausgefuehrt (Import, Fixture): welche
                # Tests davon abhaengen, ist nicht bestimmbar -- die ganze Suite.
                return SUITE, "suite"
            modul = kontext.split(".", 1)[0]
            pfad = ROOT / "tests" / f"{modul}.py"
            if not pfad.is_file():
                return SUITE, "suite"
            deckung.add(f"tests/{modul}.py")
        # Deckungs-Dateien zuerst: pytest faehrt in Aufrufreihenfolge, und mit ``-x``
        # faellt der Toeter aus der Deckung, bevor die Unterprozess-Dateien (teuer,
        # etwa 29 mal ``--help``) an der Reihe sind.
        unterprozess = [
            d for d in unterprozess_reichweite(sonde.datei) if d not in deckung
        ]
        dateien = (*sorted(deckung), *sorted(unterprozess))
        if not dateien:
            return (), "unerreicht"
        return dateien, "deckung"


# =====================================================================
# Ausfuehrung in der Kopie
# =====================================================================
@dataclass(frozen=True)
class Lauf:
    rc: int
    ausgabe: str
    dauer: float
    zeitueberschritten: bool = False

    @property
    def fehlschlaege(self) -> tuple[str, ...]:
        """Die roten Faelle (Kennungen der FAILED/ERROR-Zeilen), ohne Dubletten."""
        return fehlschlaege(self.ausgabe)


@dataclass(frozen=True)
class Ergebnis:
    sonde: Sonde
    getoetet: bool
    anmerkung: str
    dauer: float
    tests: tuple[str, ...]
    art: str
    durch: str | None = None


def _pytest(
    kopie: Path,
    tests: Sequence[str],
    zeitlimit: float,
    abbruch_beim_ersten: bool,
    abwahl: Sequence[str] = (),
) -> Lauf:
    """pytest in der Kopie; ``abwahl``: Knotenkennungen, die nicht laufen (die roten
    Faelle des Grundlaufs -- ``--deselect`` vergleicht Praefixe)."""
    befehl = [sys.executable, "-m", "pytest"]
    if abbruch_beim_ersten:
        befehl.append("-x")
    befehl.extend(SUITE_ARGUMENTE)
    for kennung in abwahl:
        befehl.extend(["--deselect", kennung])
    befehl.extend(tests)
    start = time.perf_counter()
    try:
        lauf = subprocess.run(
            befehl,
            cwd=kopie,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=kopie_umgebung(),
            check=False,
            timeout=zeitlimit,
        )
    except subprocess.TimeoutExpired:
        return Lauf(-1, "", time.perf_counter() - start, zeitueberschritten=True)
    return Lauf(
        lauf.returncode,
        (lauf.stdout or "") + (lauf.stderr or ""),
        time.perf_counter() - start,
    )


class Grundlauf:
    """Der Lauf ohne Mutant: erst er macht den roten Lauf mit Mutant zum Beleg.

    Ein Lauf der ganzen Suite deckt jeden Ausschnitt ab; sonst wird je Ausschnitt
    einmal ohne Mutant gefahren (in der Kopie des Aufrufers, die zu diesem Zeitpunkt
    unmutiert ist). Rote Faelle des Grundlaufs werden je Ausschnitt gemerkt
    (:meth:`abwahl`) und im Mutantenlauf abgewaehlt; :meth:`rote_faelle` nennt sie
    alle fuer das Urteil.
    """

    def __init__(self) -> None:
        self._laeufe: dict[tuple[str, ...], Lauf] = {}
        self._sperre = threading.Lock()

    def dauer(self, tests: tuple[str, ...]) -> float | None:
        lauf = self._laeufe.get(tests)
        return None if lauf is None else lauf.dauer

    def eintragen(self, tests: tuple[str, ...], lauf: Lauf) -> None:
        _pruefe_grundlauf(tests, lauf)
        with self._sperre:
            self._laeufe[tests] = lauf

    def sichere(self, tests: tuple[str, ...], kopie: Path, zeitlimit: float) -> Lauf:
        with self._sperre:
            if SUITE in self._laeufe:
                return self._laeufe[SUITE]
            if tests in self._laeufe:
                return self._laeufe[tests]
            lauf = _pytest(kopie, tests, zeitlimit, abbruch_beim_ersten=False)
            _pruefe_grundlauf(tests, lauf)
            self._laeufe[tests] = lauf
            return lauf

    def abwahl(self, tests: tuple[str, ...]) -> tuple[str, ...]:
        """Die roten Faelle des Grundlaufs, der ``tests`` deckt (Suite/Ausschnitt)."""
        with self._sperre:
            lauf = self._laeufe.get(SUITE) or self._laeufe.get(tests)
        return () if lauf is None else lauf.fehlschlaege

    def rote_faelle(self) -> tuple[str, ...]:
        """Alle roten Faelle aller Grundlaeufe, ohne Dubletten."""
        with self._sperre:
            laeufe = list(self._laeufe.values())
        return tuple(dict.fromkeys(f for lauf in laeufe for f in lauf.fehlschlaege))


def _pruefe_grundlauf(tests: tuple[str, ...], lauf: Lauf) -> None:
    """Gruen (exit 0) oder rot mit benennbaren Faellen (exit 1) -- alles andere ist
    kein Grundlauf: Sammelfehler oder Abbruch (exit >= 2) wuerden jeden Mutanten
    scheinbar toeten, ein exit 1 ohne FAILED-Zeile liesse sich nicht abwaehlen."""
    if lauf.rc == 0 or (lauf.rc == 1 and lauf.fehlschlaege):
        return
    letzte = (lauf.ausgabe.strip().splitlines() or [""])[-8:]
    raise TorFehler(
        f"GRUNDLAUF OHNE URTEIL in der Kopie ({' '.join(tests)}, exit={lauf.rc}, "
        f"{lauf.dauer:.0f} s"
        + (", kein roter Fall benennbar" if lauf.rc == 1 else "")
        + ") -- ohne brauchbaren Grundlauf ist keine Toetung ein Beleg:\n"
        "  " + "\n  ".join(letzte)
    )


def anwenden(text: str, sonde: Sonde) -> str | None:
    """Der mutierte Text -- oder ``None``, wenn der Anker nicht (mehr) gefunden wird."""
    if sonde.zeile is None:
        if sonde.alt not in text:
            return None
        return text.replace(sonde.alt, sonde.neu, 1)
    zeilen = text.split("\n")
    n = sonde.alt.count("\n") + 1
    von, bis = sonde.zeile - 1, sonde.zeile - 1 + n
    if "\n".join(zeilen[von:bis]) != sonde.alt:
        return None
    zeilen[von:bis] = sonde.neu.split("\n")
    return "\n".join(zeilen)


def _getoetet(lauf: Lauf) -> bool:
    if lauf.zeitueberschritten:
        return True
    if lauf.rc == 0:
        return False
    if lauf.rc in (1, 2):
        return True
    letzte = (lauf.ausgabe.strip().splitlines() or [""])[-5:]
    raise TorFehler(
        f"pytest endete mit exit={lauf.rc} (kein Testurteil):\n  " + "\n  ".join(letzte)
    )


def _mit_mutant(
    pfad: Path,
    original: bytes,
    mutiert: bytes,
    kopie: Path,
    tests: tuple[str, ...],
    zeitlimit: float,
    abwahl: tuple[str, ...] = (),
) -> Lauf:
    vorher = hashlib.sha256(original).hexdigest()
    try:
        pfad.write_bytes(mutiert)
        return _pytest(kopie, tests, zeitlimit, abbruch_beim_ersten=True, abwahl=abwahl)
    finally:
        letzter: OSError | None = None
        for _versuch in range(10):
            try:
                pfad.write_bytes(original)
                letzter = None
                break
            except OSError as exc:
                letzter = exc
                time.sleep(0.3)
        if letzter is not None:
            raise TorFehler(
                f"{pfad}: Rueckstellung in der Kopie nach 10 Versuchen gescheitert: "
                f"{letzter}"
            ) from letzter
        if hashlib.sha256(pfad.read_bytes()).hexdigest() != vorher:
            raise TorFehler(f"{pfad}: nach der Sonde NICHT wiederhergestellt.")


def fahre_sonde(
    sonde: Sonde,
    kopie: Path,
    grundlauf: Grundlauf,
    zeitlimit: float,
    zuordnung: Zuordnung | None = None,
) -> Ergebnis:
    """Eine Sonde in der Kopie fahren. Die Datei in der Kopie ist danach wie vorher."""
    pfad = kopie / sonde.datei
    original = pfad.read_bytes()
    text = original.decode("utf-8").replace("\r\n", "\n")
    mutiert = anwenden(text, sonde)
    if mutiert is None:
        # Laut scheitern: eine Sonde, die ihren Gegenstand nicht findet, ist keine
        # bestandene Sonde.
        return Ergebnis(
            sonde, False, "ANKER FEHLT -- die Sonde trifft nichts mehr", 0.0, (), "-"
        )
    if mutiert == text:
        return Ergebnis(sonde, False, "MUTANT IDENTISCH MIT DEM ORIGINAL", 0.0, (), "-")
    tests, art = sonde.tests, "katalog"
    if not tests:
        if zuordnung is None:
            tests, art = SUITE, "suite"
        else:
            tests, art = zuordnung.tests_fuer(sonde)
    if not tests:
        return Ergebnis(
            sonde,
            False,
            "UEBERLEBT -- keine Testdatei erreicht die Zeile (Deckung ohne Kontext, "
            "kein Unterprozess-Pfad)",
            0.0,
            (),
            art,
        )
    grundlauf.sichere(tests, kopie, zeitlimit)
    lauf = _mit_mutant(
        pfad,
        original,
        mutiert.encode("utf-8"),
        kopie,
        tests,
        zeitlimit,
        abwahl=grundlauf.abwahl(tests),
    )
    if _getoetet(lauf):
        rote = lauf.fehlschlaege
        durch = "ZEITLIMIT" if lauf.zeitueberschritten else (rote[0] if rote else None)
        return Ergebnis(sonde, True, "", lauf.dauer, tests, art, durch)
    return Ergebnis(
        sonde, False, "UEBERLEBT -- kein Test hat es bemerkt", lauf.dauer, tests, art
    )


# =====================================================================
# Das Tor
# =====================================================================
@dataclass(frozen=True)
class Urteil:
    ergebnisse: tuple[Ergebnis, ...]
    rc: int
    laufzeit: float


def _rate(ergebnisse: Sequence[Ergebnis]) -> tuple[int, int, float]:
    n = len(ergebnisse)
    getoetet = sum(1 for e in ergebnisse if e.getoetet)
    return getoetet, n, (getoetet / n if n else 0.0)


def _kopien_anlegen(basis: Path, anzahl: int) -> list[Path]:
    kopien = [basis / f"kopie-{i}" for i in range(anzahl)]
    for k in kopien:
        kopie_entfernen(k)
    start = time.perf_counter()
    dateien = repo_kopieren(kopien[0])
    for k in kopien[1:]:
        shutil.copytree(kopien[0], k)
    print(
        f"Kopie: {kopien[0]} ({dateien} Dateien, {anzahl} Kopie(n), "
        f"{time.perf_counter() - start:.1f} s)"
    )
    return kopien


def _grundlauf_mit_deckung(kopie: Path, grundlauf: Grundlauf) -> Zuordnung:
    """Die Suite ohne slow unmutiert unter coverage mit Kontexten; Zuordnung daraus."""
    messung = deckung_messen(kopie, SUITE, kontexte=True)
    lauf = Lauf(messung.rc, messung.ausgabe, messung.dauer)
    grundlauf.eintragen(SUITE, lauf)
    letzte = (lauf.ausgabe.strip().splitlines() or [""])[-1]
    print(
        f"Grundlauf (Suite ohne slow, unmutiert, unter coverage): exit={lauf.rc}, "
        f"{lauf.dauer:.0f} s -- {letzte}"
    )
    rote = lauf.fehlschlaege
    if rote:
        print(
            f"Grundlauf ROT: {len(rote)} Faelle -- in jedem Mutantenlauf abgewaehlt, "
            "das Tor bleibt rot:"
        )
        for kennung in rote:
            print(f"    {kennung}")
    start = time.perf_counter()
    zuordnung = Zuordnung.aus_deckung(
        messung.datendatei, [f"mt5_trading_ai/{k}" for k in GELDPFAD]
    )
    print(f"Zuordnung aus der Deckung gelesen ({time.perf_counter() - start:.1f} s)")
    return zuordnung


def tor(
    sonden: Sequence[Sonde],
    kopie_basis: Path | None = None,
    parallel: int = 1,
    behalten: bool = False,
    vollstaendig: bool = False,
) -> Urteil:
    """Sonden in Kopien fahren, Bericht drucken, Urteil zurueckgeben (``rc`` 0 = gruen).

    ``vollstaendig``: das ganze Tor (beide Schwellen, Mindestzahlen). Sonst gilt: rot,
    sobald eine Sonde ueberlebt. Erzeugte Sonden brauchen den Grundlauf unter coverage
    (Zuordnung); Katalogsonden nur den Grundlauf ihres Ausschnitts.
    """
    start_gesamt = time.perf_counter()
    parallel = max(1, min(parallel, len(sonden) or 1))
    temporaer = kopie_basis is None
    basis = (
        Path(tempfile.mkdtemp(prefix="mutationstor-"))
        if kopie_basis is None
        else kopie_basis
    )
    print("=" * 78)
    print("MUTATIONSTOR -- faerbt eine Aenderung am Geldpfad den Lauf rot?")
    print("=" * 78)
    katalog_n = sum(1 for s in sonden if s.herkunft == "katalog")
    print(
        f"Sonden: {len(sonden)} (Katalog {katalog_n}, erzeugt "
        f"{len(sonden) - katalog_n})   Schwellen: Katalog {MINDEST_TOETUNGSRATE}, "
        f"gesamt {MINDEST_TOETUNGSRATE_GESAMT} bei >= {MINDEST_SONDEN_GESAMT} Sonden"
    )
    ergebnisse: list[Ergebnis | None] = [None] * len(sonden)
    grundlauf = Grundlauf()
    try:
        try:
            kopien = _kopien_anlegen(basis, parallel)
        except KopieFehler as exc:
            raise TorFehler(f"Kopie: {exc}") from exc
        zeitlimit = ZEITLIMIT_MINDESTENS
        zuordnung: Zuordnung | None = None
        if any(s.herkunft == "erzeugt" for s in sonden):
            zuordnung = _grundlauf_mit_deckung(kopien[0], grundlauf)
            suite_dauer = grundlauf.dauer(SUITE) or 0.0
            zeitlimit = max(ZEITLIMIT_MINDESTENS, 4 * suite_dauer)
        print()
        ausgabe_sperre = threading.Lock()
        naechste = iter(range(len(sonden)))
        zaehler_sperre = threading.Lock()

        def arbeiter(kopie: Path) -> None:
            while True:
                with zaehler_sperre:
                    i = next(naechste, None)
                if i is None:
                    return
                e = fahre_sonde(sonden[i], kopie, grundlauf, zeitlimit, zuordnung)
                ergebnisse[i] = e
                with ausgabe_sperre:
                    _drucke_zeile(i + 1, len(sonden), e)

        if parallel == 1:
            arbeiter(kopien[0])
        else:
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                for zukunft in [pool.submit(arbeiter, k) for k in kopien]:
                    zukunft.result()
    finally:
        if temporaer or not behalten:
            for k in basis.glob("kopie-*"):
                kopie_entfernen(k)
        if temporaer:
            kopie_entfernen(basis)
        else:
            print(f"Kopien unter {basis} {'behalten' if behalten else 'entfernt'}.")
    fertig = tuple(e for e in ergebnisse if e is not None)
    laufzeit = time.perf_counter() - start_gesamt
    rc = _bericht(
        fertig, laufzeit, vollstaendig, grundlauf.dauer(SUITE), grundlauf.rote_faelle()
    )
    return Urteil(fertig, rc, laufzeit)


def _umfang(e: Ergebnis) -> str:
    if e.art == "katalog":
        return f"{len(e.tests)} Testdateien (Katalog)"
    if e.art == "suite":
        return "Suite"
    if e.art == "unerreicht":
        return "keine"
    return f"{len(e.tests)} Testdateien (Deckung)"


def _drucke_zeile(i: int, n: int, e: Ergebnis) -> None:
    marke = "getoetet " if e.getoetet else "UEBERLEBT"
    zusatz = f"  {e.durch}" if e.getoetet and e.durch else ""
    print(
        f"  {i:>3}/{n}  {e.sonde.name:<40} {marke} {e.dauer:6.1f} s  "
        f"[{_umfang(e)}]{zusatz}"
    )
    if not e.getoetet:
        print(f"           {e.sonde.datei}: {e.sonde.bedeutet}")
        print(f"           {e.anmerkung}")


def _zuordnung_drucken(erzeugt: Sequence[Ergebnis]) -> None:
    """Je erzeugter Sonde die zustaendigen Testdateien -- die Behauptung, die der
    Grundlauf aus der Deckung abgeleitet hat, nachlesbar im Beleg."""
    print()
    print("Zuordnung je erzeugter Sonde (Art; Testdateien in Laufreihenfolge):")
    for e in erzeugt:
        if e.art == "deckung":
            namen = ", ".join(t.removeprefix("tests/") for t in e.tests)
            print(f"  {e.sonde.name}: Deckung, {len(e.tests)} Testdateien: {namen}")
        else:
            print(f"  {e.sonde.name}: {e.art}")


def _bericht(
    ergebnisse: Sequence[Ergebnis],
    laufzeit: float,
    vollstaendig: bool,
    grundlauf_dauer: float | None,
    rote_grundlauf: Sequence[str] = (),
) -> int:
    katalog = [e for e in ergebnisse if e.sonde.herkunft == "katalog"]
    erzeugt = [e for e in ergebnisse if e.sonde.herkunft == "erzeugt"]
    kg, kn, kr = _rate(katalog)
    eg, en, er = _rate(erzeugt)
    gg, gn, gr = _rate(ergebnisse)
    print()
    if katalog:
        print(
            f"Katalog:  {kg}/{kn} getoetet, Toetungsrate: {kr:.3f} "
            f"(Schwelle {MINDEST_TOETUNGSRATE})"
        )
    if erzeugt:
        print(f"Erzeugt:  {eg}/{en} getoetet, Toetungsrate: {er:.3f}")
        je_datei: dict[str, list[Ergebnis]] = {}
        for e in erzeugt:
            je_datei.setdefault(e.sonde.datei, []).append(e)
        for datei, liste in je_datei.items():
            g, n, _r = _rate(liste)
            print(f"          {datei:<52} {g:>2}/{n}")
        arten: dict[str, int] = {}
        for e in erzeugt:
            arten[e.art] = arten.get(e.art, 0) + 1
        print(
            "          Zuordnung: "
            + ", ".join(f"{k} {v}" for k, v in sorted(arten.items()))
        )
    print(
        f"Gesamt:   {gg}/{gn} getoetet, Toetungsrate: {gr:.3f} "
        f"(Schwelle {MINDEST_TOETUNGSRATE_GESAMT} bei >= {MINDEST_SONDEN_GESAMT} "
        "Sonden)"
    )
    sonden_dauer = sum(e.dauer for e in ergebnisse)
    grund = (
        f", Grundlauf {grundlauf_dauer:.0f} s" if grundlauf_dauer is not None else ""
    )
    print(f"Laufzeit: {laufzeit:.0f} s (Sonden {sonden_dauer:.0f} s{grund})")

    ueberlebt = [e for e in ergebnisse if not e.getoetet]
    if ueberlebt:
        print()
        print(f"Ueberlebende Sonden ({len(ueberlebt)}) -- Testluecken, beim Namen:")
        for e in ueberlebt:
            print(f"  - {e.sonde.name}: {e.sonde.bedeutet} [{_umfang(e)}]")
    if erzeugt:
        _zuordnung_drucken(erzeugt)

    rot: list[str] = []
    if rote_grundlauf:
        rot.append(
            f"Grundlauf rot: {len(rote_grundlauf)} Faelle ohne Mutant, in den "
            "Mutantenlaeufen abgewaehlt -- fuer sie gibt es keinen Beleg: "
            + ", ".join(rote_grundlauf)
        )
    if katalog and kr < MINDEST_TOETUNGSRATE:
        rot.append(
            f"Katalog: Toetungsrate {kr:.3f} unter der Schwelle {MINDEST_TOETUNGSRATE}."
        )
    if vollstaendig:
        if gn < MINDEST_SONDEN_GESAMT:
            rot.append(f"nur {gn} Sonden, verlangt sind {MINDEST_SONDEN_GESAMT}.")
        if gr < MINDEST_TOETUNGSRATE_GESAMT:
            rot.append(
                f"Gesamt: Toetungsrate {gr:.3f} unter der Schwelle "
                f"{MINDEST_TOETUNGSRATE_GESAMT}."
            )
        for kurz in GELDPFAD:
            datei = f"mt5_trading_ai/{kurz}"
            anzahl = sum(1 for e in erzeugt if e.sonde.datei == datei)
            if anzahl < MINDEST_SONDEN_JE_DATEI:
                rot.append(
                    f"{datei}: {anzahl} erzeugte Sonden, verlangt sind "
                    f"{MINDEST_SONDEN_JE_DATEI}."
                )
    elif ueberlebt:
        rot.append(f"{len(ueberlebt)} Sonde(n) ueberlebt.")
    if rot:
        print()
        # stdout leeren, bevor stderr schreibt: in einer Umleitung (Beleg, CI-Log)
        # stuende das Urteil sonst vor dem Bericht (stderr ist ungepuffert).
        sys.stdout.flush()
        for grund_text in rot:
            print(f"FEHLGESCHLAGEN — {grund_text}", file=sys.stderr)
        print(
            "Jede ueberlebende Sonde ist ein Loch: der Defekt ist eingebaut worden, "
            "und kein Test hat ihn bemerkt.",
            file=sys.stderr,
        )
        return 1
    print("ok — jede Schwelle gehalten.")
    return 0


def _liste() -> None:
    print(
        f"Katalog: {len(KATALOG)} Sonden (handverlesen, Schwelle "
        f"{MINDEST_TOETUNGSRATE})"
    )
    for i, s in enumerate(KATALOG, 1):
        print(f"  {i:>3}. {s.name:<40} {s.datei}")
        print(f"       {s.bedeutet}")
    kandidaten = kandidaten_je_datei()
    quote = quoten(kandidaten)
    erzeugt = erzeugte_sonden()
    print()
    print(
        f"Erzeugt: {len(erzeugt)} Sonden ueber {len(GELDPFAD)} Dateien (Seed {SEED}; "
        f"Quote je Datei max({MINDEST_SONDEN_JE_DATEI}, ceil({ZIEL_ERZEUGT} * "
        "sqrt(Kandidaten) / Summe)); Tests aus der Deckung des Grundlaufs)"
    )
    for i, s in enumerate(erzeugt, len(KATALOG) + 1):
        print(f"  {i:>3}. {s.name:<40} {s.bedeutet}")
    print()
    print("Kandidatenstellen je Datei (Quote):")
    for datei, stellen in kandidaten.items():
        arten: dict[str, int] = {}
        for st in stellen:
            arten[st.operator] = arten.get(st.operator, 0) + 1
        verteilung = ", ".join(f"{k} {v}" for k, v in sorted(arten.items()))
        print(f"  {datei:<52} {len(stellen):>4} ({quote[datei]:>2})  {verteilung}")
    print()
    print(
        f"Gesamt: {len(KATALOG) + len(erzeugt)} Sonden "
        f"(Mindestzahl {MINDEST_SONDEN_GESAMT})"
    )


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Mutationstor auf dem Geldpfad")
    ap.add_argument(
        "--liste", action="store_true", help="Katalog und erzeugte Sonden zeigen"
    )
    ap.add_argument(
        "--sonde",
        type=int,
        action="append",
        default=None,
        help="nur diese Sonde(n) (Nummer aus --liste, 1-basiert; mehrfach erlaubt)",
    )
    ap.add_argument(
        "--selbsttest",
        action="store_true",
        help=f"nur die zwei Katalogsonden {SELBSTTEST}",
    )
    ap.add_argument(
        "--katalog", action="store_true", help="nur den handverlesenen Katalog"
    )
    ap.add_argument(
        "--kopie",
        type=Path,
        default=None,
        help="Verzeichnis fuer die Kopie(n) (Vorgabe: temporaer)",
    )
    ap.add_argument(
        "--behalten", action="store_true", help="Kopie(n) nach dem Lauf stehen lassen"
    )
    ap.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Sonden gleichzeitig, je in eigener Kopie",
    )
    args = ap.parse_args()

    if args.liste:
        _liste()
        return 0

    try:
        if args.selbsttest:
            sonden: list[Sonde] = [s for s in KATALOG if s.name in SELBSTTEST]
            vollstaendig = False
        elif args.katalog:
            sonden = list(KATALOG)
            vollstaendig = False
        elif args.sonde:
            alle = alle_sonden()
            sonden = []
            for nummer in args.sonde:
                if not 1 <= nummer <= len(alle):
                    print(
                        f"FEHLGESCHLAGEN — Sonde {nummer}: es gibt 1..{len(alle)}.",
                        file=sys.stderr,
                    )
                    return 2
                sonden.append(alle[nummer - 1])
            vollstaendig = False
        else:
            sonden = list(alle_sonden())
            vollstaendig = True
        urteil = tor(
            sonden,
            kopie_basis=args.kopie,
            parallel=args.parallel,
            behalten=args.behalten,
            vollstaendig=vollstaendig,
        )
    except TorFehler as exc:
        sys.stdout.flush()
        print(f"FEHLGESCHLAGEN — {exc}", file=sys.stderr)
        return 2
    return urteil.rc


if __name__ == "__main__":
    raise SystemExit(main())

"""Zwei Waechter ueber der ganzen Suite (Programm NEUAUFBAU, Auftrag 1, T6 "T").

Beide sind Hooks, kein Vorsatz (CLAUDE.md, Arbeitsweise 5): sie greifen bei jedem
Lauf, auch bei dem des Agenten, der sie eingerichtet hat. Ihre Eichfaelle -- je ein
roter und ein gruener -- stehen in ``tests/eichfall_skipgate.py``.

**Waechter 1 -- A2, ein uebersprungener Test ist ein Fehlschlag.** Jeder Skip wird zum
Fehlschlag mit der urspruenglichen Begruendung im Text: ``pytest.skip`` im Test oder
in einer Fixture, ``@pytest.mark.skip``, ``skipif`` mit wahrer Bedingung,
``pytest.importorskip`` -- und ebenso ein Skip auf Modulebene beim Sammeln. Der Grund
steht in Regel 4 des Rahmens: eine Pruefung ohne Gegenstand besteht nicht. Wer den
Gegenstand nicht hat, prueft sein Fehlen mit ``assert`` und benennt es. Nicht
angetastet wird ein erwarteter Fehlschlag (``xfail``), der wirklich gelaufen ist;
ein ``xfail(run=False)`` dagegen ist ein Skip mit anderem Namen und faellt mit.

**Waechter 2 -- A10, kein Test schreibt in den echten Zustandsordner des Benutzers
oder in den Arbeitsbaum.** Eine autouse-Fixture nimmt vor und nach jedem Test einen
Schnappschuss (Pfad, Groesse, mtime in ns) zweier Baeume: des Zustandsordners, den
``standard_zustandsordner()`` aus der ECHTEN Umgebung des Laufs ableitet (einmal beim
Laden dieser Datei, bevor ein Test ``monkeypatch`` anfasst), und des Arbeitsbaums
dieses Repositories. Jede Abweichung -- neue, entfernte, geaenderte Datei, angelegter
Ordner -- ist ein Fehlschlag, der die Dateien nennt; bei einer Abweichung im
Arbeitsbaum steht zusaetzlich ``git status --porcelain`` daneben. Nicht gezaehlt
werden ``.git/`` (kein Teil des Arbeitsbaums), eingebettete fremde Arbeitsbaeume
(Unterordner mit eigenem ``.git``, etwa ``.claude/worktrees/``) und Werkzeugcaches,
die kein Test schreibt: Bytecode des Interpreters (Unterprozesse ohne
``PYTHONDONTWRITEBYTECODE``), ``.pytest_cache``, ``.mypy_cache``, ``.ruff_cache``,
``.coverage*``, ``htmlcov``. Gitignorierte Laufzeitdaten wie ``/betrieb/`` zaehlen
ausdruecklich MIT -- genau dort laege Laufzeitzustand im Arbeitsbaum (A18).

Warum ein eigener Schnappschuss und nicht ``git status`` je Test: gemessen im
Worktree mit 510 verfolgten Dateien braucht ``git status --porcelain --ignored
--untracked-files=all`` 128 ms ohne und 171 ms mit Rechnerlast, der
``os.scandir``-Schnappschuss 20 ms bzw. 60 ms (Beleg
``06-stub-skipgate-schnappschuss-kosten.txt``); bei 1.505 Tests sind das 193 s gegen
30 s je Lauf ohne Last, und A11 verlangt 100 Laeufe. Der "Vorher"-Stand eines Tests
ist der "Nachher"-Stand seines Vorgaengers -- dazwischen laeuft kein Testcode --,
darum je Test ein Schnappschuss des Arbeitsbaums (gemessene Fixture-Summe in der Suite:
131,9 s ueber 1.518 Tests unter Last, Beleg ``06-stub-skipgate-suite.txt``).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator, Iterator
from pathlib import Path
from typing import Any

import pytest

NL = chr(10)
from mt5_trading_ai.execution.risiko_zustand import (
    ZustandsortFehler,
    standard_zustandsordner,
)

# Fuer die Eichfaelle: ``pytester`` faehrt eine Testdatei in einem eigenen pytest-Lauf.
pytest_plugins = ["pytester"]

REPO: Path = Path(__file__).resolve().parents[1]

#: Nicht Teil des Arbeitsbaums bzw. Werkzeugcaches, die kein Test schreibt.
#:
#: Jede Ausnahme ist ein Loch, durch das ein Test unbemerkt schreiben kann; sie
#: sind darum so eng wie moeglich gefasst (Gegenlese T10, Einwand E9). ``.git``
#: gehoert nicht zum Arbeitsbaum; die Cacheordner gehoeren Werkzeugen, nicht
#: Tests. **Innerhalb** dieser Ordner wird aber nur noch das ignoriert, was dort
#: hingehoert: ``__pycache__`` deckt ``.pyc``/``.pyo``, nicht eine JSON-Datei,
#: die jemand dort ablegt.
_NICHT_GEZAEHLT_ORDNER = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
    }
)
#: In ``__pycache__`` zaehlt alles ausser Bytecode -- eine Datei mit anderem
#: Namen ist dort kein Cache, sondern ein Versteck (E9, gemessen: eine
#: ``laufzeit.json`` unter ``mt5_trading_ai/__pycache__/`` blieb unbemerkt).
_BYTECODE_ORDNER = "__pycache__"
_NICHT_GEZAEHLT_ENDUNGEN = (".pyc", ".pyo")
#: Die Datendateien von ``coverage`` -- sie entstehen unter dem Werkzeug, nicht
#: unter einem Test. Der Praefix deckt ``.coverage`` und ``.coverage.<host>``;
#: eine ``.coverage_laufzeit.json`` faellt seit E9 NICHT mehr darunter.
_NICHT_GEZAEHLT_DATEIEN = frozenset({".coverage"})
_NICHT_GEZAEHLT_PRAEFIXE = (".coverage.",)

Schnappschuss = dict[str, tuple[int, int]]


def _fremde_baeume() -> frozenset[str]:
    """Arbeitsbaeume, die git selbst kennt -- und nur die.

    Eine ``.git``-Marke im Dateisystem ist kein Beleg: sie laesst sich anlegen.
    ``git worktree list`` fragt das Repository.
    """
    try:
        aus = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return frozenset()
    pfade = {
        os.path.normpath(z[len("worktree ") :].strip())
        for z in aus.splitlines()
        if z.startswith("worktree ")
    }
    return frozenset(p for p in pfade if os.path.normpath(p) != str(REPO))


_FREMDE_BAEUME = _fremde_baeume()


def _zustandsordner_der_umgebung() -> Path:
    """Der echte Zustandsordner dieses Laufs -- aus der Umgebung, nicht aus einem Test."""
    try:
        return standard_zustandsordner()
    except ZustandsortFehler as exc:  # pragma: no cover - Umgebung des Laufs defekt
        raise pytest.UsageError(
            f"Waechter A10 (tests/conftest.py): {exc} -- die Umgebung des Testlaufs "
            "nennt einen unbrauchbaren Zustandsordner."
        ) from exc


#: Einmal beim Laden bestimmt, bevor irgendein Test ``os.environ`` anfasst.
ZUSTANDSORDNER: Path = _zustandsordner_der_umgebung()


def _schnappschuss(wurzel: Path) -> Schnappschuss | None:
    """Alle Dateien unter ``wurzel`` mit (Groesse, mtime_ns); ``None`` = Ordner fehlt."""
    if not wurzel.is_dir():
        return None
    stand: Schnappschuss = {}
    wurzel_str = str(wurzel)
    stapel = [wurzel_str]
    while stapel:
        ordner = stapel.pop()
        try:
            with os.scandir(ordner) as es:
                eintraege = list(es)
        except FileNotFoundError:
            continue
        for e in eintraege:
            name = e.name
            if (
                name in _NICHT_GEZAEHLT_ORDNER
                or name in _NICHT_GEZAEHLT_DATEIEN
                or name.startswith(_NICHT_GEZAEHLT_PRAEFIXE)
                or (
                    os.path.basename(ordner) == _BYTECODE_ORDNER
                    and name.endswith(_NICHT_GEZAEHLT_ENDUNGEN)
                )
            ):
                continue
            if e.is_dir(follow_symlinks=False):
                # Ein fremder Arbeitsbaum gehoert nicht hierher -- aber nur einer,
                # den git selbst kennt. Eine ``.git``-Marke genuegte bis E9: ein
                # Test legte ``mt5_trading_ai/laufzeit/.git`` an und schrieb
                # daneben, ohne dass der Waechter etwas sah.
                if e.path in _FREMDE_BAEUME:
                    continue
                stapel.append(e.path)
                continue
            try:
                st = e.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            stand[os.path.relpath(e.path, wurzel_str)] = (st.st_size, st.st_mtime_ns)
    return stand


def _abweichungen(
    vorher: Schnappschuss | None, nachher: Schnappschuss | None
) -> list[str]:
    if vorher is None and nachher is None:
        return []
    if vorher is None:
        angelegt = sorted(nachher or {})
        return ["Ordner angelegt"] + [f"neu: {p}" for p in angelegt]
    if nachher is None:
        return ["Ordner entfernt"]
    zeilen = [f"neu: {p}" for p in sorted(nachher.keys() - vorher.keys())]
    zeilen += [f"entfernt: {p}" for p in sorted(vorher.keys() - nachher.keys())]
    zeilen += [
        f"geaendert: {p}"
        for p in sorted(vorher.keys() & nachher.keys())
        if vorher[p] != nachher[p]
    ]
    return zeilen


def _git_status() -> str:
    try:
        lauf = subprocess.run(
            ["git", "status", "--porcelain", "--ignored", "--untracked-files=all"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"(git status nicht verfuegbar: {exc})"
    return lauf.stdout.strip() or "(git status: sauber)"


# --- Waechter 1: Skip = Fehlschlag ---------------------------------------------


def _skip_begruendung(longrepr: Any) -> str:
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        pfad, zeile, text = longrepr
        return f"{pfad}:{zeile}: {text}"
    return str(longrepr)


def _als_fehlschlag(report: Any, art: str) -> None:
    begruendung = _skip_begruendung(report.longrepr)
    report.outcome = "failed"
    report.longrepr = (
        f"Waechter A2 (tests/conftest.py): ein uebersprungener {art} ist ein "
        f"Fehlschlag.\n{begruendung}\n"
        "Eine Pruefung ohne Gegenstand besteht nicht (CLAUDE.md, Regel 4). Den "
        "Gegenstand bereitstellen -- oder sein Fehlen mit assert benennen, nicht "
        "mit skip."
    )


def _xfail_ohne_lauf(item: pytest.Item) -> str | None:
    """Traegt dieses Element ein ``xfail(run=False)``? Dann laeuft es nie.

    Gegenlese T10, Einwand E8 (S1): der Wrapper unten sah den Fall nicht. Pytests
    eigener ``pytest_runtest_makereport`` ist mit ``tryfirst=True`` registriert und
    liegt damit AUSSEN -- wenn dieser Wrapper laeuft, steht ``report.outcome`` noch
    nicht auf ``skipped``, und die Pruefung auf ``[NOTRUN]`` lief ins Leere.
    Gemessen: ein Test mit ``@pytest.mark.xfail(run=False)`` meldete
    ``1 xfailed``, Exit 0. Ein Dekorator genuegte, um einen Test stillzulegen.

    Darum wird der Fall hier beim SAMMELN abgefangen, wo kein fremder Wrapper
    dazwischenliegt. ``xfail`` mit Lauf bleibt erlaubt: ein erwarteter Fehlschlag,
    der wirklich gefahren wird, ist eine Messung.
    """
    for marke in item.iter_markers(name="xfail"):
        if marke.kwargs.get("run", True) is False:
            return str(marke.kwargs.get("reason") or "ohne Begruendung")
    return None


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """``xfail(run=False)`` ist ein Skip mit anderem Namen -- und hier verboten."""
    verboten = [(i, g) for i in items if (g := _xfail_ohne_lauf(i)) is not None]
    if not verboten:
        return
    zeilen = NL.join(f"  {i.nodeid}: {g}" for i, g in verboten)
    raise pytest.UsageError(
        f"Waechter A2 (tests/conftest.py): {len(verboten)} Fall/Faelle mit "
        "xfail(run=False) -- ein Test, der nie laeuft, ist ein Skip mit anderem "
        f"Namen (Katalog A2, CLAUDE.md Regel 4).{NL}{zeilen}{NL}"
        "Entweder den Fall laufen lassen (xfail ohne run=False) oder das fehlende "
        "Stueck mit assert benennen."
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, Any, None]:
    ergebnis = yield
    report: pytest.TestReport = ergebnis.get_result()
    # Der zweite Weg in denselben Zustand: ``pytest.xfail()`` mitten im Test. Er
    # bricht mit ``XFailed`` ab, und der Rest des Falles laeuft nicht mehr.
    if call.excinfo is not None and call.excinfo.typename == "XFailed":
        report.outcome = "failed"
        report.longrepr = (
            "Waechter A2 (tests/conftest.py): pytest.xfail() bricht den Fall ab -- "
            "was danach steht, wird nie geprueft. Das ist ein Skip mit anderem "
            f"Namen (Katalog A2).{NL}{call.excinfo.value}"
        )
        return
    if report.outcome != "skipped":
        return
    xfail = getattr(report, "wasxfail", None)
    if xfail is not None and not str(xfail).startswith("[NOTRUN]"):
        return  # ein erwarteter Fehlschlag, der wirklich gelaufen ist
    _als_fehlschlag(report, "Test")


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(
    collector: pytest.Collector,
) -> Generator[None, Any, None]:
    ergebnis = yield
    report: pytest.CollectReport = ergebnis.get_result()
    if report.outcome == "skipped":
        _als_fehlschlag(report, "Sammelschritt (Skip auf Modulebene)")


# --- Waechter 2: kein Schreiben in Zustandsordner oder Arbeitsbaum -------------

#: "Nachher"-Stand des zuletzt gelaufenen Tests = "Vorher"-Stand des naechsten.
_letzter_baum: Schnappschuss | None = None
_letzter_baum_gueltig = False


@pytest.fixture(autouse=True)
def _waechter_a10(request: pytest.FixtureRequest) -> Iterator[None]:
    """Vor und nach jedem Test: Zustandsordner des Benutzers und Arbeitsbaum unveraendert."""
    global _letzter_baum, _letzter_baum_gueltig
    zustand_vorher = _schnappschuss(ZUSTANDSORDNER)
    baum_vorher = _letzter_baum if _letzter_baum_gueltig else _schnappschuss(REPO)
    yield
    zustand_nachher = _schnappschuss(ZUSTANDSORDNER)
    baum_nachher = _schnappschuss(REPO)
    _letzter_baum, _letzter_baum_gueltig = baum_nachher, True

    meldung: list[str] = []
    z = _abweichungen(zustand_vorher, zustand_nachher)
    if z:
        meldung.append(
            f"Zustandsordner des Benutzers veraendert ({ZUSTANDSORDNER}):\n  "
            + "\n  ".join(z)
        )
    b = _abweichungen(baum_vorher, baum_nachher)
    if b:
        meldung.append(
            f"Arbeitsbaum veraendert ({REPO}):\n  "
            + "\n  ".join(b)
            + "\n  git status --porcelain --ignored --untracked-files=all:\n  "
            + "\n  ".join(_git_status().splitlines())
        )
    if meldung:
        _letzter_baum_gueltig = False  # der naechste Test misst frisch
        pytest.fail(
            f"Waechter A10 (tests/conftest.py): {request.node.nodeid} hat ausserhalb "
            "von tmp_path geschrieben.\n" + "\n".join(meldung),
            pytrace=False,
        )


def pytest_report_header(config: pytest.Config) -> list[str]:
    vorhanden = ZUSTANDSORDNER.is_dir()
    dateien = len(_schnappschuss(ZUSTANDSORDNER) or {}) if vorhanden else 0
    return [
        "Waechter A2 (tests/conftest.py): Skip = Fehlschlag.",
        "Waechter A10 (tests/conftest.py): Zustandsordner "
        f"{ZUSTANDSORDNER} (vorhanden: {'ja' if vorhanden else 'nein'}, "
        f"{dateien} Dateien) und Arbeitsbaum {REPO} bleiben unveraendert.",
    ]

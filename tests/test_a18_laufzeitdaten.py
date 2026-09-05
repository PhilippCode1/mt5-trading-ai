"""A18: keine Laufzeitdaten im Arbeitsbaum -- gemessen am Bestand, nicht am Commit.

WARUM DIESE DATEI
-----------------
Gegenlese T10, Einwand E14: der Katalogpunkt A18 ("Laufzeitdaten liegen ausserhalb des
Arbeitsbaums") war nur fuer NEUE Schreibvorgaenge geprueft (Stoppdatei, Zustand, Journale
des Live-Betriebs wandern in den Zustandsordner). Der ALTBESTAND lag weiter im Baum:
``betrieb/`` mit 21 Journalen, Logs, ``ALARME.txt`` und einer ``coverage.json`` --
8,1 MB, gitignoriert, und vier Werkzeuge zeigten mit ihrer Vorgabe dorthin. Ein Punkt,
der nur die Aenderung misst und nicht den Bestand, ist am Tag danach schon wieder
verletzt.

Dieser Test misst den Bestand: (1) das Verzeichnis ``betrieb/`` gibt es nicht;
(2) nirgends im Arbeitsbaum liegt eine Datei, die nach Laufzeitdaten aussieht;
(3) kein Werkzeug hat seine Vorgabe fuer Journale im Arbeitsbaum.

ROT gegen den Stand vor der Verschiebung (belege/06-a18-rot.txt): alle drei Zusicherungen
fielen. GRUEN, seit der Altbestand mit Pruefsummen (``tools/journal_sichern.py``) in den
Zustandsordner des Benutzers gewandert ist und die Vorgaben dorthin zeigen.

WAS AUSGENOMMEN IST -- UND WARUM
--------------------------------
``archiv/`` (eingefrorene Altbestaende, dort per Katalog nichts mehr lebendig) und die
Belegordner ``PROGRAMM/**/belege/`` (dort liegen KOPIEN von Zustandsdateien als Beweis
eines Befunds -- ``risikozustand.json`` aus der Nachstellung 306bbaa). Beides sind
Belege, keine Laufzeitdaten: nichts schreibt sie zur Laufzeit fort. Dasselbe gilt fuer
den versiegelten Eingang ``PROGRAMM/eingang/`` (Bewertung mit Pruefausgaben, per Manifest
gesichert) und fuer fremde Arbeitsbaeume unter ``.claude/worktrees/``. Werkzeug-Caches
(``.git``, ``__pycache__``, ``.mypy_cache`` ...) sind keine Laufzeitdaten des Programms.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Namen, die im Betrieb entstehen. Wer hier ein Muster ergaenzt, ergaenzt einen Schreiber.
LAUFZEITMUSTER: tuple[str, ...] = (
    "journal-*.jsonl",
    "*.log",
    "*.err",
    "ALARME.txt",
    "risikozustand.json",
    "schwebende_auftraege.json",
    "STOP",
    "coverage.json",
    "TRIALS.jsonl",
)

#: Ordner, in denen nicht gesucht wird (Begruendung im Modul-Docstring).
_NICHT_DURCHSUCHT: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "htmlcov",
        "node_modules",
        "archiv",
        "daten",
    }
)


def _laufzeitdateien() -> list[str]:
    funde: list[str] = []
    for wurzel, ordner, dateien in os.walk(REPO):
        rel = Path(wurzel).relative_to(REPO)
        ordner[:] = [
            o
            for o in ordner
            if o not in _NICHT_DURCHSUCHT
            and not (o == "belege" and rel.parts[:1] == ("PROGRAMM",))
            # PROGRAMM/eingang/ ist der versiegelte Eingang (Bewertung samt ihren
            # Pruefausgaben), per Manifest gesichert -- eingefroren, nicht Laufzeit.
            and not (o == "eingang" and rel.parts == ("PROGRAMM",))
            # Fremde Arbeitsbaeume (git worktree) unter .claude/worktrees/ sind
            # Kopien des Repos, kein Bestand dieses Baums.
            and not (o == "worktrees" and rel.parts == (".claude",))
        ]
        for name in dateien:
            if any(fnmatch.fnmatch(name, muster) for muster in LAUFZEITMUSTER):
                funde.append((rel / name).as_posix())
    return sorted(funde)


def test_das_verzeichnis_betrieb_gibt_es_im_arbeitsbaum_nicht() -> None:
    """Der Altbestand ist verschoben, nicht nur ignoriert. ``.gitignore`` versteckt
    ihn vor ``git status`` -- vor diesem Test versteckt ihn nichts."""
    assert not (REPO / "betrieb").exists(), (
        "betrieb/ liegt im Arbeitsbaum -- Laufzeitdaten gehoeren in den Zustandsordner "
        "(tools/journal_sichern.py sichert sie mit Pruefsummen dorthin)"
    )


def test_keine_datei_im_arbeitsbaum_sieht_nach_laufzeitdaten_aus() -> None:
    funde = _laufzeitdateien()
    assert funde == [], "Laufzeitdaten im Arbeitsbaum: " + ", ".join(funde)


@pytest.mark.parametrize(
    ("werkzeug", "name"),
    [
        ("tools/aufzeichnung_redigieren.py", "QUELLE"),
        ("tools/betrieb_auswerten.py", "JOURNALE"),
        ("tools/betrieb_reihe.py", "JOURNALE"),
        ("tools/journal_sichern.py", "JOURNALE"),
    ],
)
def test_die_vorgabe_des_werkzeugs_liegt_ausserhalb_des_arbeitsbaums(
    werkzeug: str, name: str
) -> None:
    """Vier Werkzeuge lesen Journale. Zeigt eine Vorgabe in den Baum, legt der naechste
    Aufruf den Altbestand genau dort wieder an."""
    spec = importlib.util.spec_from_file_location(
        "a18_" + Path(werkzeug).stem, REPO / werkzeug
    )
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    # Vor dem Ausfuehren registrieren: ``@dataclass`` schlaegt das Modul in
    # ``sys.modules`` nach und faellt sonst mit AttributeError auf None.
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    vorgabe = Path(getattr(modul, name)).resolve()
    assert vorgabe != REPO.resolve() and REPO.resolve() not in vorgabe.parents, (
        f"{werkzeug}: {name} zeigt in den Arbeitsbaum ({vorgabe.relative_to(REPO)})"
    )

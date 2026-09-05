"""Die Waechter selbst: laufen sie, sind sie verdrahtet, und sperren sie sich?

WARUM DIESE DATEI
-----------------
Gegenlese T10, Einwand E11: kein Tor und kein Test fuhr die Waechter. Weder die Suite
noch die CI noch der Pre-Commit-Hook fassten ``PROGRAMM/hooks/waechter.py``,
``PROGRAMM/hooks/pre_commit.py``, ``.githooks/`` oder ``core.hooksPath`` an. Folge:
``git config --unset core.hooksPath`` schaltete alle neun Tore ab, ohne dass etwas rot
wurde -- und ein Commit, der ``.githooks/pre-commit`` leert, lief durch den Hook, den
er gerade entfernt.

Ein Waechter, dessen Ausfall niemand bemerkt, ist keiner (CLAUDE.md, Regel 6). Diese
Datei ist der Nachweis, dass es sie gibt, dass sie greifen und dass ihre eigenen
Dateien gegen Aenderungen gesperrt sind. Sie laeuft in der Suite, damit auch im
Pre-Push-Hook und in der CI.

WAS SIE NICHT LEISTET
---------------------
``core.hooksPath`` ist lokale Konfiguration; ein frischer Klon hat sie nicht, und die
CI arbeitet ohne Git-Hooks (dort laufen dieselben Tore als eigene Schritte). Der Test
verlangt sie darum nur, wo ein Arbeitsbaum mit Hooks vorliegt -- und sagt es, wenn
nicht. Was er ausdruecklich prueft: dass die Hook-Dateien da sind, dass sie
funktionieren, und dass niemand sie unbemerkt aendert.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "PROGRAMM" / "hooks"
GITHOOKS = REPO / ".githooks"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout.strip()


# --- Die Dateien gibt es, und sie laufen -------------------------------------


@pytest.mark.parametrize(
    "pfad",
    [
        "PROGRAMM/hooks/waechter.py",
        "PROGRAMM/hooks/pre_commit.py",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".claude/settings.json",
    ],
)
def test_jede_waechterdatei_ist_verfolgt(pfad: str) -> None:
    """Verfolgt, nicht nur vorhanden: eine ungetrackte Datei fehlt im naechsten Klon."""
    assert (REPO / pfad).is_file(), f"{pfad} fehlt"
    assert _git("ls-files", "--", pfad) == pfad, f"{pfad} ist nicht verfolgt"


def test_der_pretooluse_waechter_besteht_seinen_selbsttest() -> None:
    """Elf Faelle, je BLOCK oder frei -- der Waechter prueft sich selbst."""
    lauf = subprocess.run(
        [sys.executable, "-B", str(HOOKS / "waechter.py"), "--selbsttest"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Faelle wie erwartet" in lauf.stdout, lauf.stdout


def test_der_waechter_weist_jeden_weg_auf_den_katalog_ab() -> None:
    """Nicht nur die vier Schreibwerkzeuge: jede Eingabe wird auf Felder geprueft.

    Gegenlese T10, E10: ein ``Set-Content`` ueber das PowerShell-Werkzeug lief mit
    Exit 0 durch, weil der Waechter nach Werkzeugnamen entschied.
    """
    faelle = [
        ("Write", {"file_path": "PROGRAMM/abnahmekatalog.md", "content": "x"}),
        ("Bash", {"command": "echo x >> PROGRAMM/abnahmekatalog.md"}),
        ("PowerShell", {"command": "Set-Content -Path config/live_freigabe.json 1"}),
        ("EinFremdesWerkzeug", {"befehl": "rm config/live_freigabe.json"}),
    ]
    for werkzeug, eingabe in faelle:
        lauf = subprocess.run(
            [sys.executable, "-B", str(HOOKS / "waechter.py")],
            cwd=REPO,
            input=json.dumps(
                {"tool_name": werkzeug, "tool_input": eingabe, "cwd": str(REPO)}
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert lauf.returncode == 2, f"{werkzeug} kam durch: {lauf.stdout}{lauf.stderr}"
        assert "WAECHTER: abgewiesen" in lauf.stderr


def test_der_waechter_laesst_gewoehnliche_arbeit_durch() -> None:
    """Die Gegenprobe, ohne die das Verbot alles blockierte."""
    lauf = subprocess.run(
        [sys.executable, "-B", str(HOOKS / "waechter.py")],
        cwd=REPO,
        input=json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "PROGRAMM/zustand.md", "content": "x"},
                "cwd": str(REPO),
            }
        ),
        capture_output=True,
        text=True,
    )
    assert lauf.returncode == 0, lauf.stderr


# --- Der Pre-Commit-Hook: seine Tore und seine Sperrliste --------------------


def _pre_commit() -> object:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "pre_commit_probe", HOOKS / "pre_commit.py"
    )
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_der_pre_commit_hook_fuehrt_die_neun_tore() -> None:
    """Die Liste ist der Hook. Faellt ein Tor heraus, faellt es lautlos heraus."""
    modul = _pre_commit()
    namen = [name for name, _ in modul.TORE]  # type: ignore[attr-defined]
    assert namen == [
        "Katalog-Hash",
        "ruff check",
        "ruff format",
        "mypy strict",
        "MODULES.md",
        "Doku-Behauptungen",
        "Doku-Zahlen",
        "Kopien",
        "Manifeste",
    ], namen


def test_die_gesperrten_dateien_umfassen_die_waechter_selbst() -> None:
    """E11: wer den Hook aendert, kommt sonst durch den Hook, den er gerade aendert."""
    modul = _pre_commit()
    gesperrt = set(modul.GESPERRT)  # type: ignore[attr-defined]
    for pflicht in (
        "PROGRAMM/abnahmekatalog.md",
        "PROGRAMM/abnahmekatalog.sha256",
        "config/live_freigabe.json",
    ):
        assert pflicht in gesperrt, pflicht
    for waechterdatei in (
        "PROGRAMM/hooks/waechter.py",
        "PROGRAMM/hooks/pre_commit.py",
        ".githooks/pre-commit",
        ".githooks/pre-push",
    ):
        assert waechterdatei in modul.GEMELDET, (  # type: ignore[attr-defined]
            f"{waechterdatei} wird bei Aenderung nicht gemeldet -- ein Waechter, "
            "dessen Abschaltung niemand sieht, ist keiner"
        )


def test_die_tore_laufen_auf_dem_index_nicht_auf_dem_arbeitsbaum() -> None:
    """F-009 (Gegenlese T10, E7): eine rote Fassung stagen und eine saubere im Baum
    liegen lassen kam an allen neun Toren vorbei. Der Hook checkt den Index aus."""
    modul = _pre_commit()
    assert hasattr(modul, "index_auschecken"), (
        "ohne Kopie des Index messen die Tore den Arbeitsbaum"
    )
    quelle = (HOOKS / "pre_commit.py").read_text(encoding="utf-8")
    assert "cwd=auf" in quelle, "die Tore laufen nicht auf der Kopie"
    assert "cwd=REPO, capture_output=True, text=True)" not in quelle


# --- core.hooksPath: nur wo Hooks gelten ------------------------------------


def test_dieser_arbeitsbaum_hat_die_hooks_verdrahtet_oder_sagt_warum_nicht() -> None:
    """``git config core.hooksPath`` zeigt auf ``.githooks`` -- oder es gibt keine
    Git-Konfiguration (frischer Klon, CI). Beides ist zulaessig, das Dritte nicht:
    ein Arbeitsbaum, in dem gearbeitet wird und die Hooks abgeschaltet sind."""
    gesetzt = _git("config", "--get", "core.hooksPath")
    if not gesetzt:
        # Frischer Klon oder CI: dort laufen dieselben Tore als eigene Schritte.
        assert (REPO / ".github" / "workflows" / "ci.yml").is_file(), (
            "weder Git-Hooks noch CI -- dann prueft nichts mehr"
        )
        return
    # Der Wert darf relativ oder absolut sein -- beides zeigt auf denselben Ordner.
    ziel = Path(gesetzt)
    if not ziel.is_absolute():
        ziel = REPO / ziel
    assert ziel.resolve() == GITHOOKS.resolve(), gesetzt
    assert (GITHOOKS / "pre-commit").is_file()
    assert (GITHOOKS / "pre-push").is_file()


def test_die_hooks_rufen_die_python_seite_und_reichen_den_rueckgabewert_durch() -> None:
    """Ein Wrapper, der den Rueckgabewert schluckt, ist ein abgeschalteter Hook."""
    for name, erwartet in (
        ("pre-commit", "pre_commit.py"),
        ("pre-push", "pytest"),
    ):
        text = (GITHOOKS / name).read_text(encoding="utf-8")
        assert erwartet in text, f"{name} ruft {erwartet} nicht"
        # ``exec`` ersetzt die Shell: der Rueckgabewert des Werkzeugs IST der des
        # Hooks. Ein Aufruf ohne exec braucht ein ausdrueckliches exit.
        assert "exec " in text or "exit" in text or "set -e" in text, (
            f"{name} reicht den Rueckgabewert nicht durch"
        )

"""Herkunft eines Backtest-Laufs: der Codestand aus git (Paket 6).

Ein registrierter Versuch muss belegen, GEGEN WELCHEN CODE er lief -- sonst ist der
Ledger-Eintrag beweisfrei. Die **Datenpruefsumme** liefert der Datenlader
(``bars_checksum``/``load_verified_csv``, Paket 1); den **Codestand** liefert git.

Fail-closed in VIER Faellen: (1) git fehlt, (2) kein Repo, (3) HEAD unbestimmt (frisches
Repo ohne Commit) und (4) **schmutziger Arbeitsbaum** -- dann wird ``ProvenanceError``
geworfen, der Lauf darf nicht registriert werden. Fall 4 ist entscheidend: liefe ein
Backtest gegen uncommitteten Code, waere der HEAD-Hash zwar non-empty, aber eine LUEGE
ueber den tatsaechlich gefahrenen Code -- ein beweisfrei-falscher Eintrag, den ein
Pruefer beim Auschecken des Commits nie reproduzieren koennte. Ein sauberer Hash fuer
einen schmutzigen Lauf ist genau das Schein-Gate, das dieses Paket schliesst.

Die Schmutz-Erkennung ist bewusst **hermetisch und config-unabhaengig** (ein §9-Review
zeigte, dass ``git status --porcelain`` allein umgehbar ist): sie erzwingt
``--untracked-files=all`` (ueberschreibt eine ``status.showUntrackedFiles=no``-Config,
die sonst neue untracked Quelldateien verstecken wuerde) UND lehnt jedes Index-Bit ab,
das git blind macht (``assume-unchanged`` -> Kleinbuchstaben-Tag, ``skip-worktree`` ->
``S`` in ``git ls-files -v``). Ein gesetztes Suppress-Bit macht die Status-Ausgabe
unzuverlaessig -- dann fail-closed, unabhaengig davon, ob die Datei gerade abweicht.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class ProvenanceError(RuntimeError):
    """Die Herkunft ist nicht ableitbar. Fail-closed: kein Register-Eintrag."""


def _run_git(args: list[str], *, cwd: Path) -> str:
    """Ein git-Aufruf, fail-closed. Gibt stdout (stripped) zurueck."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:  # git nicht installiert
        raise ProvenanceError(
            "git nicht verfuegbar -- Codestand nicht ableitbar"
        ) from exc
    except subprocess.CalledProcessError as exc:  # kein Repo / HEAD unbestimmt
        raise ProvenanceError(
            f"git {' '.join(args)} fehlgeschlagen: {exc.stderr.strip()}"
        ) from exc
    return result.stdout.strip()


def _working_tree_is_dirty(cwd: Path) -> bool:
    """Weicht der Arbeitsbaum von HEAD ab? Hermetisch, config-unabhaengig, fail-closed.

    Zwei Pruefungen, weil ``git status`` allein umgehbar ist:

    1. ``--no-optional-locks status --porcelain --untracked-files=all`` -- erfasst
       tracked-Modifikationen (staged + unstaged) UND *alle* untracked Dateien; das
       feste ``--untracked-files=all`` neutralisiert eine
       ``status.showUntrackedFiles=no``-Config, die sonst neue Quelldateien verbergen
       wuerde. ``--no-optional-locks`` haelt den Aufruf rein lesend.
    2. ``ls-files -v`` -- ``status`` ist per git-Design BLIND fuer Dateien mit
       ``assume-unchanged`` (Kleinbuchstaben-Tag) oder ``skip-worktree`` (``S``). Ist
       auch nur EIN solches Suppress-Bit gesetzt, ist die Status-Ausgabe nicht
       vertrauenswuerdig -> schmutzig, unabhaengig vom aktuellen Inhalt.
    """
    status = _run_git(
        ["--no-optional-locks", "status", "--porcelain", "--untracked-files=all"],
        cwd=cwd,
    )
    if status:
        return True
    for line in _run_git(["ls-files", "-v"], cwd=cwd).splitlines():
        tag = line[:1]
        # Kleinbuchstabe -> assume-unchanged; ``S`` -> skip-worktree. Beide machen git
        # blind fuer Aenderungen; ein Grossbuchstabe (z.B. ``H``) ist normal.
        if tag.islower() or tag == "S":
            return True
    return False


def code_commit_from_git(*, repo: Path | str | None = None) -> str:
    """Der git-Commit (voller HEAD-Hash) des Codestands. Fail-closed.

    ``repo`` ist das Arbeitsverzeichnis; ``None`` nutzt das Verzeichnis dieses Moduls
    (also den Paketbaum). Wirft ``ProvenanceError``, wenn git fehlt, kein Repo vorliegt,
    HEAD unbestimmt ist -- ODER der Arbeitsbaum schmutzig ist (uncommittet).

    Der Dirty-Check (``_working_tree_is_dirty``) beachtet ``.gitignore``, also zaehlen
    lokale Daten/``TRIALS.jsonl`` NICHT als Schmutz, wohl aber modifizierte versionierte
    Dateien und neue (untracked) Quelldateien -- config-unabhaengig und gegen
    Index-Suppress-Bits gehaertet. Wer bewusst gegen uncommitteten Code faehrt, muss den
    Commit explizit setzen (``--code-commit``) und uebernimmt damit die Herkunft selbst
    -- der Code leitet keine Luege ab.

    ALLE git-Aufrufe laufen vom Repo-**Toplevel** (``rev-parse --show-toplevel``), NICHT
    vom Modul-Unterverzeichnis: ``git ls-files`` ist verzeichnis-skopiert (§9-Befund) --
    aus einem Unterordner saehe der Suppress-Bit-Scan nur diesen Teilbaum und liesse ein
    ``assume-unchanged``/``skip-worktree``-Bit auf Dateien anderswo im Repo unentdeckt.
    """
    start = Path(repo) if repo is not None else Path(__file__).resolve().parent
    # Toplevel aufloesen: fail-closed ohne Repo (``--show-toplevel`` schlaegt fehl) und
    # macht den nachfolgenden ls-files-Scan repo-weit statt teilbaum-lokal.
    root = Path(_run_git(["rev-parse", "--show-toplevel"], cwd=start))
    commit = _run_git(["rev-parse", "HEAD"], cwd=root)
    if not commit:
        raise ProvenanceError("git lieferte einen leeren Commit -- Herkunft unbestimmt")
    if _working_tree_is_dirty(root):
        raise ProvenanceError(
            "Arbeitsbaum ist schmutzig (uncommittete Aenderungen oder ein "
            "assume-unchanged/skip-worktree-Bit) -- HEAD belegt den gefahrenen Code "
            "nicht. Erst committen, oder den Commit explizit setzen (--code-commit)."
        )
    return commit

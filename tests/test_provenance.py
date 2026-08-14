"""Code-Herkunft aus git (Paket 6) -- fail-closed, inklusive Schmutz-Wache (§9-Blocker).

Der §9-Review zeigte: ``code_commit_from_git`` gab bei einem SCHMUTZIGEN Arbeitsbaum den
sauberen HEAD-Hash zurueck -- eine Luege ueber den gefahrenen Code, die der non-empty-
Guard durchwinkte. Diese Tests fahren die Wache negativ (schmutzig -> Fehler) und positiv
(sauber -> voller Hash) auf einem hermetischen tmp-git-Repo, ohne den Zustand des
Haupt-Repos zu beruehren.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.provenance import ProvenanceError, code_commit_from_git


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    )


def _clean_repo(root: Path) -> None:
    _git(root, "init")
    (root / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "code.py")
    _git(root, "commit", "-m", "erst")


def test_clean_tree_returns_full_head_hash(tmp_path: Path) -> None:
    _clean_repo(tmp_path)
    commit = code_commit_from_git(repo=tmp_path)
    assert len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)


def test_dirty_tracked_change_is_rejected(tmp_path: Path) -> None:
    # Der §9-Blocker: ein modifizierter versionierter Quelltext -> HEAD luegt.
    _clean_repo(tmp_path)
    (tmp_path / "code.py").write_text("x = 2  # uncommitted\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)


def test_untracked_source_file_is_rejected(tmp_path: Path) -> None:
    # Eine neue, nicht versionierte Quelldatei koennte importiert werden -> Schmutz.
    _clean_repo(tmp_path)
    (tmp_path / "neu.py").write_text("y = 3\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)


def test_untracked_hidden_by_config_is_still_rejected(tmp_path: Path) -> None:
    # §9-Re-Review-Vektor 1: status.showUntrackedFiles=no (gutartige Performance-Config)
    # versteckt neue untracked .py vor `git status --porcelain`. Der Guard erzwingt
    # --untracked-files=all und faengt sie trotzdem.
    _clean_repo(tmp_path)
    _git(tmp_path, "config", "status.showUntrackedFiles", "no")
    (tmp_path / "evil.py").write_text("boese = True\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)


def test_assume_unchanged_modified_file_is_rejected(tmp_path: Path) -> None:
    # §9-Re-Review-Vektor 2a: assume-unchanged macht `git status` blind fuer eine
    # geaenderte tracked Datei. Der Guard lehnt das Index-Bit (ls-files -v -> 'h') ab.
    _clean_repo(tmp_path)
    _git(tmp_path, "update-index", "--assume-unchanged", "code.py")
    (tmp_path / "code.py").write_text("x = 999  # verdeckt\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)


def test_skip_worktree_file_is_rejected(tmp_path: Path) -> None:
    # §9-Re-Review-Vektor 2b: skip-worktree ebenso -- ls-files -v -> 'S'.
    _clean_repo(tmp_path)
    _git(tmp_path, "update-index", "--skip-worktree", "code.py")
    (tmp_path / "code.py").write_text("x = 777  # verdeckt\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)


def test_suppress_bit_outside_cwd_subtree_is_rejected(tmp_path: Path) -> None:
    # §9-Re-Review Runde 3: `git ls-files -v` ist verzeichnis-skopiert. Der Produktions-
    # cwd ist ein Modul-UNTERverzeichnis (Path(__file__).parent); ein Suppress-Bit auf
    # einer Datei in einem ANDEREN Top-Level-Ordner darf nicht durch die Skopierung
    # entkommen. Der Guard loest aufs Repo-Toplevel auf und scannt repo-weit -- dieser
    # Test faehrt den Default-Pfad-cwd (tiefes Unterverzeichnis) nach.
    _clean_repo(tmp_path)  # committet code.py im Root
    sub = tmp_path / "pkg" / "backtest"
    sub.mkdir(parents=True)
    (sub / "mod.py").write_text("m = 1\n", encoding="utf-8")
    far = tmp_path / "other" / "far.py"
    far.parent.mkdir()
    far.write_text("f = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "tree")
    _git(tmp_path, "update-index", "--assume-unchanged", "other/far.py")
    far.write_text("f = 999  # verdeckt, ausserhalb des cwd-Teilbaums\n", encoding="utf-8")
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=sub)  # cwd = tiefes Unterverzeichnis


def test_gitignored_file_does_not_count_as_dirty(tmp_path: Path) -> None:
    # .gitignore-Dateien (lokale Daten/TRIALS.jsonl) sind KEIN Schmutz -- sonst waere
    # jeder Lauf mit lokalem Ledger blockiert. Der Hash bleibt ableitbar.
    _clean_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("TRIALS.jsonl\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-m", "ignore")
    (tmp_path / "TRIALS.jsonl").write_text("{}\n", encoding="utf-8")
    commit = code_commit_from_git(repo=tmp_path)
    assert len(commit) == 40


def test_no_repo_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError):
        code_commit_from_git(repo=tmp_path)  # kein `git init`

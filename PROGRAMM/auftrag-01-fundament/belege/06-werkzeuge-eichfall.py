#!/usr/bin/env python3
"""Eichfall Familie Werkzeuge (Abnahmekatalog A12, A13) -- rot und gruen.

Faehrt **dieselben Pruefer** wie ``tests/eichfall_werkzeuge.py`` (``pruefe_help``,
``pruefe_benannt``) dreimal:

  [A] gegen den Stand 306bbaa (Stand der Bewertung), nur die neun betroffenen
      Werkzeuge -- ``git show 306bbaa:tools/<datei>`` in einen Tempordner;
  [B] gegen den Stand 97ee206 (HEAD vor dieser Aenderung), alle Werkzeuge;
  [C] gegen den Arbeitsbaum (dieser Patch), alle Werkzeuge.

[A] und [B] gehen nach ``06-werkzeuge-rot.txt``, [C] nach ``06-werkzeuge-gruen.txt``.
Alte Werkzeuge laufen aus dem Tempordner mit dem heutigen Paket (``PYTHONPATH`` =
Shim, Repo); ``import MetaTrader5`` scheitert ueberall am Shim -- kein Unterprozess
kann ``MetaTrader5.initialize()`` erreichen, das unter Windows das Terminal startet.

Zwei Zugestaendnisse an die alten Staende, beide im Beleg vermerkt: ``fetch_data``
kennt dort kein ``--versuche`` (der Fehlschlag dauert die sechs Versuche, 42 s), und
``ereignisstudie`` kennt kein ``--register`` -- fuer [A] und [B] legt das Skript ein
LEERES ``TRIALS.jsonl`` an der Repo-Wurzel an (gitignoriert) und entfernt es danach,
sonst endete der alte Stand vor dem Terminal am fehlenden Register.

Aufruf im Worktree:  python PROGRAMM/auftrag-01-fundament/belege/06-werkzeuge-eichfall.py
Pfade werden redigiert (C:\\Users\\<konto>).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import eichfall_werkzeuge as E  # noqa: E402

ALT_BEWERTUNG = "306bbaa"
ALT_VORHER = "97ee206"
RELEVANT_HELP = ("edge_test.py", "betrieb_auswerten.py")
KONTO = str(Path.home())


def redigiere(text: str) -> str:
    return (
        text.replace(KONTO, r"C:\Users\<konto>")
        .replace(KONTO.replace("\\", "/"), "C:/Users/<konto>")
        .replace(KONTO.replace("\\", "\\\\"), r"C:\\Users\\<konto>")
    )


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def alter_stand(ref: str, ziel: Path) -> list[Path]:
    """``tools/*.py`` des Standes ``ref`` nach ``ziel/tools/``; zurueck die Dateien."""
    (ziel / "tools").mkdir(parents=True)
    dateien: list[Path] = []
    for rel in git("ls-tree", "--name-only", ref, "--", "tools/").split():
        if not rel.endswith(".py"):
            continue
        inhalt = subprocess.run(
            ["git", "show", f"{ref}:{rel}"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout
        pfad = ziel / rel
        pfad.write_bytes(inhalt)
        dateien.append(pfad)
    return dateien


def zeile(befund: E.Befund) -> list[str]:
    aus = [f"  [{'gruen' if befund.gruen else 'ROT  '}] {befund.werkzeug}: {befund.grund}"]
    if not befund.gruen:
        schwanz = befund.lauf.ausgabe.strip().splitlines()[-6:]
        aus.extend(f"           | {z}" for z in schwanz)
    return aus


def pruefe_stand(
    tools_dir: Path,
    *,
    tmp: Path,
    env: dict[str, str],
    cwd: Path,
    nur_relevante: bool,
    neuer_stand: bool,
) -> list[str]:
    aus: list[str] = []
    tmp.mkdir(parents=True, exist_ok=True)
    werkzeuge = E.werkzeuge_mit_main(tools_dir)
    if nur_relevante:
        werkzeuge = [w for w in werkzeuge if w.name in RELEVANT_HELP]
    aus.append(f"## A13 --help ({len(werkzeuge)} Werkzeuge mit main())")
    gruen = 0
    t0 = time.monotonic()
    for w in werkzeuge:
        b = E.pruefe_help(w, env=env, cwd=cwd)
        gruen += b.gruen
        aus.extend(zeile(b))
    aus.append(
        f"  => {gruen} von {len(werkzeuge)} gruen, {time.monotonic() - t0:.0f} s"
    )
    aus.append("")

    aus.append("## A12 ohne Terminal (Shim: import MetaTrader5 wirft ImportError)")
    gruen = 0
    gesamt = 0
    t0 = time.monotonic()
    for a in E.TERMINALAUFRUFE:
        argumente = a.argumente(tmp)
        if not neuer_stand and a.datei == "ereignisstudie.py":
            argumente = ("--alle",)  # alter Stand: kein --register
        b = E.pruefe_benannt(tools_dir / a.datei, argumente, env=env, cwd=cwd)
        gruen += b.gruen
        gesamt += 1
        aus.extend(zeile(b))
    b = E.pruefe_benannt(
        tools_dir / "fetch_data.py",
        E._fetch_data_argumente(tmp, ein_versuch=neuer_stand),
        env=E.ohne_quelle(env),
        cwd=cwd,
        praefix=E.PRAEFIX_QUELLE,
    )
    gruen += b.gruen
    gesamt += 1
    aus.extend(zeile(b))
    aus.append(f"  => {gruen} von {gesamt} gruen, {time.monotonic() - t0:.0f} s")
    aus.append("")
    return aus


def kopf(titel: str) -> list[str]:
    return ["=" * 78, titel, "=" * 78]


def main() -> int:
    register = REPO / "TRIALS.jsonl"
    register_angelegt = False
    rot: list[str] = kopf(
        "ROTER EICHFALL Familie Werkzeuge -- Staende VOR der Aenderung, "
        f"{time.strftime('%Y-%m-%d')}"
    )
    rot.append(
        "Pruefer: tests/eichfall_werkzeuge.py (pruefe_help, pruefe_benannt); "
        "Kriterien: --help Exit 0 + 'usage'; ohne Terminal Exit 2, genau eine Zeile "
        "'FEHLGESCHLAGEN -- MT5-Terminal nicht erreichbar: <Grund>', kein Traceback."
    )
    rot.append("")
    with tempfile.TemporaryDirectory(prefix="eichfall-werkzeuge-") as t:
        tmp = Path(t)
        env = E.shim_umgebung(tmp / "shim", weitere_pfade=(REPO,))
        if not register.exists():
            register.write_text("", encoding="utf-8")
            register_angelegt = True
            rot.append(
                "Hinweis: leeres TRIALS.jsonl an der Repo-Wurzel angelegt (gitignoriert), "
                "damit die alten ereignisstudie-Staende bis zum Terminal kommen; wird am "
                "Ende entfernt."
            )
            rot.append("")
        try:
            for ref, nur_relevante, titel in (
                (ALT_BEWERTUNG, True, "[A] Stand 306bbaa (Bewertung), 9 Werkzeuge"),
                (ALT_VORHER, False, "[B] Stand 97ee206 (HEAD vor der Aenderung)"),
            ):
                ziel = tmp / ref
                dateien = alter_stand(ref, ziel)
                rot.extend(kopf(f"{titel} -- {len(dateien)} Dateien per git show"))
                rot.extend(
                    pruefe_stand(
                        ziel / "tools",
                        tmp=tmp / f"daten-{ref}",
                        env=env,
                        cwd=REPO,
                        nur_relevante=nur_relevante,
                        neuer_stand=False,
                    )
                )
            (tmp / "daten-neu").mkdir()
            gruen: list[str] = kopf(
                "GRUENER EICHFALL Familie Werkzeuge -- Arbeitsbaum (dieser Patch), "
                f"{time.strftime('%Y-%m-%d')}"
            )
            gruen.append(f"HEAD: {git('rev-parse', '--short', 'HEAD').strip()}")
            gruen.append("")
            gruen.extend(
                pruefe_stand(
                    REPO / "tools",
                    tmp=tmp / "daten-neu",
                    env=E.shim_umgebung(tmp / "shim"),
                    cwd=REPO,
                    nur_relevante=False,
                    neuer_stand=True,
                )
            )
        finally:
            if register_angelegt:
                register.unlink()
    for name, inhalt in (("06-werkzeuge-rot.txt", rot), ("06-werkzeuge-gruen.txt", gruen)):
        (HIER / name).write_text(redigiere("\n".join(inhalt)) + "\n", encoding="utf-8")
        print(f"geschrieben: {HIER / name}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.exit(main())

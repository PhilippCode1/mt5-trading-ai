#!/usr/bin/env python3
"""Claude-Code-Hook (PreToolUse): weist Schreibzugriffe auf eingefrorene Dateien ab.

Rahmen, Abschnitt 0, Punkt 5: „Ein Claude-Code-Hook (PreToolUse) weist Schreibzugriffe
auf PROGRAMM/abnahmekatalog.md und auf die Live-Schalter ab -- auch deine eigenen. Was
ein Hook blockt, wird nicht umgangen, sondern in entscheidungen.md beantragt."

Eingang: das JSON, das Claude Code jedem PreToolUse-Hook auf stdin gibt
(``tool_name``, ``tool_input``, ``cwd``). Ausgang: Exit 2 mit Begruendung auf stderr
blockt den Aufruf; Exit 0 laesst ihn durch.

Geschuetzt sind:
* ``PROGRAMM/abnahmekatalog.md`` und ``PROGRAMM/abnahmekatalog.sha256`` (Regel 3),
* ``config/live_freigabe.json`` (die vier Live-Schalter und die Freigabekennung),
* jede schon vorhandene Datei unter ``PROGRAMM/vorregistrierung/`` (unveraenderlich
  nach dem Schreiben; neue Dateien duerfen angelegt werden).

Bei Bash-Befehlen ist der Hook eine Heuristik: er blockt, wenn der Befehl einen
geschuetzten Dateinamen nennt UND ein Schreibmuster enthaelt (Umleitung, sed -i, tee,
mv, cp, rm, git rm/mv, Python-Schreibaufrufe, PowerShell-Schreib-Cmdlets). Lesen
(cat, git diff, sha256sum, katalog_hash.py --pruefen) bleibt erlaubt. Ein Bash-Befehl,
der die Heuristik unterlaeuft, trifft danach den Pre-Commit-Hook (zweite Sperre) und
die CI (dritte).

Selbsttest: ``python PROGRAMM/hooks/waechter.py --selbsttest`` faehrt die Eichfaelle
und meldet je Fall erwartet/erhalten.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

GESCHUETZT = (
    "PROGRAMM/abnahmekatalog.md",
    "PROGRAMM/abnahmekatalog.sha256",
    "config/live_freigabe.json",
)
UNVERAENDERLICHER_ORDNER = "PROGRAMM/vorregistrierung/"
SCHREIBWERKZEUGE = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SCHREIBMUSTER = re.compile(
    r"(>>?|\btee\b|\bsed\b[^|;&]*\s-i|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bdd\b"
    r"|write_text|write_bytes|\bopen\(|\bgit\s+(rm|mv|checkout|restore)\b"
    r"|python3?\s+-\s*$|python3?\s+-\s*<|Set-Content|Out-File|Add-Content|Remove-Item"
    r"|Move-Item|Copy-Item)",
    re.M,
)


def _wurzel(daten: dict[str, object]) -> Path:
    for kandidat in (daten.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if isinstance(kandidat, str) and kandidat:
            return Path(kandidat).resolve()
    return Path.cwd().resolve()


def _normal(pfad: str, wurzel: Path) -> str:
    p = Path(pfad)
    if not p.is_absolute():
        p = wurzel / p
    try:
        rel = p.resolve().relative_to(wurzel)
    except ValueError:
        return p.as_posix().replace("\\", "/")
    return rel.as_posix()


def pruefe_pfad(pfad: str, wurzel: Path) -> str | None:
    """Begruendung, wenn ``pfad`` geschuetzt ist, sonst None."""
    rel = _normal(pfad, wurzel)
    for g in GESCHUETZT:
        if rel == g or rel.endswith("/" + g) or rel.endswith(g.split("/")[-1]):
            return f"{g} ist eingefroren (Rahmen 0.5, Regel 3)."
    if rel.startswith(UNVERAENDERLICHER_ORDNER) or "/vorregistrierung/" in rel:
        ziel = wurzel / rel
        if ziel.exists():
            return (
                f"{rel} ist eine Vorregistrierung, nach dem Schreiben unveraenderlich."
            )
    return None


def pruefe_bash(befehl: str, wurzel: Path) -> str | None:
    namen = [g.split("/")[-1] for g in GESCHUETZT]
    genannt = [n for n in namen if n in befehl]
    vorreg = "vorregistrierung" in befehl
    if not genannt and not vorreg:
        return None
    if SCHREIBMUSTER.search(befehl):
        was = ", ".join(genannt) if genannt else "PROGRAMM/vorregistrierung/"
        return (
            f"Bash-Befehl nennt {was} und enthaelt ein Schreibmuster; "
            "eingefrorene Dateien werden nicht beschrieben (Rahmen 0.5)."
        )
    return None


def _strings(wert: object, tiefe: int = 0) -> Iterator[str]:
    """Jede Zeichenkette in der Werkzeugeingabe -- gleich wie tief sie liegt."""
    if tiefe > 6:
        return
    if isinstance(wert, str):
        yield wert
    elif isinstance(wert, dict):
        for v in wert.values():
            yield from _strings(v, tiefe + 1)
    elif isinstance(wert, list | tuple):
        for v in wert:
            yield from _strings(v, tiefe + 1)


def entscheide(daten: dict[str, object]) -> str | None:
    """Entscheidet ueber FELDER, nicht ueber Werkzeugnamen.

    Bis zum 2026-09-05 kannte diese Funktion vier Schreibwerkzeuge und ``Bash``;
    jeder andere Name fiel durch. Diese Sitzung hat neben ``Bash`` ein Werkzeug
    namens ``PowerShell``, und auf einem Windows-Rechner ist ``Set-Content`` der
    gewoehnliche Schreibweg -- keine Umgehung, sondern der Normalfall. Gemessen in
    der Gegenlese T10 (Einwand E10): ein ``Set-Content`` auf
    ``config/live_freigabe.json`` lief ohne Ausgabe und mit Exit 0 durch.

    Jetzt gilt: (1) die bekannten Schreibwerkzeuge wie bisher ueber ihren Pfad;
    (2) JEDE andere Eingabe wird auf ihre Zeichenketten hin durchsucht -- nennt
    eine davon eine gesperrte Datei, entscheidet dieselbe Befehlspruefung wie bei
    ``Bash``. Der Matcher in ``.claude/settings.json`` steht dafuer auf ``.*``.

    Was das NICHT leistet, steht weiter unten am Modulkopf: eine Heuristik ueber
    Text bleibt eine Heuristik. Sie ist die erste von drei Sperren; die zweite
    (Pre-Commit-Hash) und die dritte (CI) haengen nicht an ihr.
    """
    werkzeug = str(daten.get("tool_name", ""))
    eingabe = daten.get("tool_input") or {}
    if not isinstance(eingabe, dict):
        return None
    wurzel = _wurzel(daten)
    if werkzeug in SCHREIBWERKZEUGE:
        pfad = eingabe.get("file_path") or eingabe.get("notebook_path") or ""
        if isinstance(pfad, str) and pfad:
            return pruefe_pfad(pfad, wurzel)
        return None
    for text in _strings(eingabe):
        grund = pruefe_bash(text, wurzel)
        if grund is not None:
            return grund
    return None


def selbsttest() -> int:
    wurzel = Path(__file__).resolve().parents[2]
    faelle: list[tuple[str, dict[str, object], bool]] = [
        (
            "Write auf den Katalog",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "PROGRAMM/abnahmekatalog.md"},
            },
            True,
        ),
        (
            "Edit auf den Katalog (absoluter Pfad)",
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(wurzel / "PROGRAMM" / "abnahmekatalog.md")
                },
            },
            True,
        ),
        (
            "Write auf die Live-Schalter",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "config/live_freigabe.json"},
            },
            True,
        ),
        (
            "Bash: Umleitung in den Katalog",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "echo x >> PROGRAMM/abnahmekatalog.md"},
            },
            True,
        ),
        (
            "Bash: sed -i auf die Live-Schalter",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "sed -i 's/false/true/' config/live_freigabe.json"
                },
            },
            True,
        ),
        (
            "Bash: Python-Heredoc, das den Katalog nennt",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": (
                        "python - <<'PY'\nopen('PROGRAMM/abnahmekatalog.md','w')\nPY"
                    ),
                },
            },
            True,
        ),
        (
            "Bash: nur lesen (cat)",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cat PROGRAMM/abnahmekatalog.md"},
            },
            False,
        ),
        (
            "Bash: Hash pruefen",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python tools/katalog_hash.py --pruefen"},
            },
            False,
        ),
        (
            "Write auf eine gewoehnliche Datei",
            {"tool_name": "Write", "tool_input": {"file_path": "PROGRAMM/zustand.md"}},
            False,
        ),
        (
            "Edit auf vorhandene Vorregistrierung",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "PROGRAMM/vorregistrierung/00-HINWEIS.md"},
            },
            True,
        ),
        (
            "Write auf neue Vorregistrierung",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "PROGRAMM/vorregistrierung/9999-neu.md"},
            },
            False,
        ),
    ]
    fehler = 0
    for name, daten, soll_block in faelle:
        daten = dict(daten, cwd=str(wurzel))
        grund = entscheide(daten)
        ist_block = grund is not None
        ok = ist_block == soll_block
        fehler += 0 if ok else 1
        print(
            f"{'OK ' if ok else '!! '} {name}: erwartet "
            f"{'BLOCK' if soll_block else 'frei'}, erhalten "
            f"{'BLOCK' if ist_block else 'frei'}" + (f" -- {grund}" if grund else "")
        )
    print(f"Selbsttest: {len(faelle) - fehler}/{len(faelle)} Faelle wie erwartet")
    return 0 if fehler == 0 else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--selbsttest":
        return selbsttest()
    roh = sys.stdin.read()
    try:
        daten = json.loads(roh) if roh.strip() else {}
    except json.JSONDecodeError:
        print("waechter: Eingang kein JSON -- nicht geprueft", file=sys.stderr)
        return 0
    if not isinstance(daten, dict):
        return 0
    grund = entscheide(daten)
    if grund is None:
        return 0
    print(
        f"WAECHTER: abgewiesen -- {grund} Nicht umgehen; Aenderungswunsch in "
        "PROGRAMM/entscheidungen.md eintragen, Verschaerfung in "
        "PROGRAMM/abnahmekatalog-verschaerfungen.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

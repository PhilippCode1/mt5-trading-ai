"""T5, Nachbesserung: jede verfolgte Markdown-Datei ist entweder lebend (gescannt) oder
liegt in einem per Manifest gesicherten Ordner -- sonst rot (Luecke der Mengenregel).

Eigenes Skript (2026-09-03). Patcht tools/doku_menge.py (Funktion ``unbeaufsichtigt``)
und tools/check_docs_claims.py (vierte Pruefung) und haengt zwei Eichfaelle an
tests/test_doku_menge.py an (rot: eine .md unter tests/; gruen: der echte Bestand).

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/05-mengenregel-luecke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)


def main() -> int:
    p = REPO / "tools/doku_menge.py"
    s = p.read_text(encoding="utf-8")
    assert "def unbeaufsichtigt(" not in s, "schon gepatcht"
    s = s.rstrip(NL) + NL + NL.join(
        [
            "",
            "",
            "def ist_gesichert(rel: str) -> bool:",
            '    """Ob ein Pfad in einem per Manifest gesicherten Ordner liegt."""',
            '    rel = rel.replace(chr(92), "/")',
            '    return any(rel.startswith(o + "/") for o in PRUEFSUMMEN_GESICHERT)',
            "",
            "",
            "def unbeaufsichtigt(repo: Path = REPO) -> list[str]:",
            '    """Verfolgte Markdown-Dateien, die weder lebend noch gesichert sind.',
            "",
            "    Die Menge ist positiv definiert; damit sie keine Luecke laesst, muss jede",
            "    verfolgte Datei in genau eine der beiden Klassen fallen. Eine .md unter",
            "    tests/ oder tools/ waere sonst weder gescannt noch eingefroren.",
            '    """',
            "    return sorted(",
            "        rel",
            "        for rel in verfolgte_markdown(repo)",
            "        if not ist_lebend(rel) and not ist_gesichert(rel)",
            "    )",
            "",
        ]
    )
    p.write_text(s, encoding="utf-8", newline="")
    print("  tools/doku_menge.py: ist_gesichert, unbeaufsichtigt")

    p = REPO / "tools/check_docs_claims.py"
    s = p.read_text(encoding="utf-8")
    alt = "    failures: list[str] = list(doku_menge.wurzel_befunde(REPO))" + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        alt
        + "    failures += [" + NL
        + '        f"unbeaufsichtigt: {rel} ist weder lebend noch per Manifest gesichert -- "' + NL
        + '        "archivieren, nach PROGRAMM/ verschieben oder loeschen"' + NL
        + "        for rel in doku_menge.unbeaufsichtigt(REPO)" + NL
        + "    ]" + NL,
    )
    alt = "Drei Pruefungen: (1) die Wurzel traegt genau ``README.md``, ``MODULES.md``,"
    assert s.count(alt) == 1
    s = s.replace(alt, "Vier Pruefungen: (1) die Wurzel traegt genau ``README.md``, ``MODULES.md``,")
    alt = "gesperrte Phrase ohne Beleg in einem lebenden Dokument." + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "gesperrte Phrase ohne Beleg in einem lebenden Dokument; (4) keine verfolgte" + NL
        + "Markdown-Datei, die weder lebend noch per Manifest gesichert ist." + NL,
    )
    p.write_text(s, encoding="utf-8", newline="")
    print("  tools/check_docs_claims.py: vierte Pruefung (unbeaufsichtigt)")

    p = REPO / "tests/test_doku_menge.py"
    s = p.read_text(encoding="utf-8")
    s = s.rstrip(NL) + NL + NL.join(
        [
            "",
            "",
            "# --- keine Luecke zwischen lebend und gesichert ----------------------------------",
            "",
            "",
            "def test_keine_verfolgte_markdown_ist_unbeaufsichtigt() -> None:",
            '    """Gruener Eichfall am Bestand: jede .md ist lebend oder per Manifest gesichert."""',
            "    assert doku_menge.unbeaufsichtigt() == []",
            "",
            "",
            "def test_eine_markdown_unter_tests_ist_rot(monkeypatch: pytest.MonkeyPatch) -> None:",
            '    """ROTER EICHFALL: eine .md an einem Ort, den kein Tor sieht, wird gemeldet."""',
            "    monkeypatch.setattr(",
            "        doku_menge,",
            '        "verfolgte_markdown",',
            '        lambda repo=None: ["README.md", "tests/NOTIZEN.md", "archiv/x.md"],',
            "    )",
            '    assert doku_menge.unbeaufsichtigt() == ["tests/NOTIZEN.md"]',
            "",
        ]
    )
    p.write_text(s, encoding="utf-8", newline="")
    print("  tests/test_doku_menge.py: zwei Eichfaelle")
    return 0


if __name__ == "__main__":
    sys.exit(main())

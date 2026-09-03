"""Die Doku-Tore als Mengenregel (Katalog A14) -- rote und gruene Eichfaelle.

Ersetzt ``tests/test_auftrag_doku_tore.py`` des Altstands (dort: Ausnahmeliste fuer
``AUFTRAG/``). Geprueft wird die Definition der lebenden Dokumente, die Pflichtmenge an
der Wurzel, dass eigene Programmdokumente scharf geprueft bleiben und dass fremde
Eingaenge und das Archiv nicht gescannt, sondern per Manifest gesichert sind.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools import archiv_manifest, check_doc_numbers, check_docs_claims, doku_menge

REPO = Path(__file__).resolve().parents[1]


# --- die Menge selbst ------------------------------------------------------------


def test_wurzel_und_eigene_programmdateien_sind_lebend() -> None:
    assert doku_menge.ist_lebend("README.md")
    assert doku_menge.ist_lebend("PROGRAMM/zustand.md")
    assert doku_menge.ist_lebend("PROGRAMM/auftrag-01-fundament/bericht.md")


def test_eingaenge_und_archiv_sind_nicht_lebend() -> None:
    assert not doku_menge.ist_lebend("PROGRAMM/eingang/BEWERTUNG.md")
    assert not doku_menge.ist_lebend(
        "PROGRAMM/masterprompts/MASTERPROMPT-CC-01-FUNDAMENT.md"
    )
    assert not doku_menge.ist_lebend("archiv/MASTERBERICHT.md")
    assert not doku_menge.ist_lebend("archiv/AUFTRAG/zustand.md")


def test_die_wurzel_traegt_genau_die_drei_pflichtdateien() -> None:
    """Gruener Eichfall am echten Repo: keine vierte Datei an der Wurzel."""
    assert doku_menge.wurzel_befunde() == []
    assert doku_menge.wurzeldokumente() == sorted(doku_menge.PFLICHT_WURZEL)


def test_eine_vierte_wurzeldatei_ist_rot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROTER EICHFALL: eine zusaetzliche Wurzeldatei wird gemeldet, eine fehlende auch."""
    monkeypatch.setattr(
        doku_menge,
        "verfolgte_markdown",
        lambda repo=None: ["README.md", "MODULES.md", "CLAUDE.md", "STAND.md"],
    )
    assert doku_menge.wurzel_befunde() == [
        "zu viel an der Wurzel: STAND.md (archivieren oder nach PROGRAMM/)"
    ]
    monkeypatch.setattr(
        doku_menge, "verfolgte_markdown", lambda repo=None: ["README.md", "CLAUDE.md"]
    )
    assert doku_menge.wurzel_befunde() == ["fehlt an der Wurzel: MODULES.md"]


# --- das Behauptungs-Tor auf der Menge -------------------------------------------


def test_die_obergrenze_wurde_nicht_angehoben() -> None:
    assert check_docs_claims.MAX_MARKDOWN_FILES == 32


def test_das_echte_repo_besteht_die_zaehlung() -> None:
    gezaehlt = check_docs_claims.counted(doku_menge.lebende_dokumente())
    assert 0 < len(gezaehlt) <= check_docs_claims.MAX_MARKDOWN_FILES


def test_eigene_programmdatei_bleibt_scharf_geprueft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROTER EICHFALL: eine Zusicherung in einer eigenen PROGRAMM/-Datei faellt auf."""
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    ordner = tmp_path / "PROGRAMM"
    ordner.mkdir()
    datei = ordner / "bericht.md"
    inhalt = (
        "# Auftrag 1" + 2 * chr(10) + "Das Fundament ist produktionsreif." + chr(10)
    )
    datei.write_text(inhalt, encoding="utf-8")
    probleme = check_docs_claims.check_file(datei)
    assert probleme, "eine Zusicherung ohne Beleg muss gemeldet werden"
    assert any("produktionsreif" in p for p in probleme)


def test_fremde_eingaenge_werden_nicht_gescannt_sondern_gesichert() -> None:
    """Die Bewertung zitiert gesperrte Phrasen als Befund; sie ist kein Pruefgegenstand.

    Dafuer sichert ein Manifest ihre Unveraendertheit -- gruener Eichfall am Bestand.
    """
    lebend = {p.relative_to(REPO).as_posix() for p in doku_menge.lebende_dokumente()}
    assert not any(rel.startswith("PROGRAMM/eingang/") for rel in lebend)
    assert not any(rel.startswith("PROGRAMM/masterprompts/") for rel in lebend)
    assert not any(rel.startswith("archiv/") for rel in lebend)
    for ordner in doku_menge.PRUEFSUMMEN_GESICHERT:
        assert archiv_manifest.pruefen(REPO / ordner) == 0, ordner


# --- das Zahlen-Tor auf der Menge --------------------------------------------------


def test_zahlen_tor_prueft_die_wurzel_und_nicht_das_messprotokoll() -> None:
    """E-012: PROGRAMM/ traegt Commit-Kennungen und Messwerte; die Wurzel nicht."""
    assert check_doc_numbers.ist_zahlen_gegenstand("README.md")
    assert check_doc_numbers.ist_zahlen_gegenstand("MODULES.md")
    assert not check_doc_numbers.ist_zahlen_gegenstand("PROGRAMM/zustand.md")
    assert not check_doc_numbers.ist_zahlen_gegenstand("archiv/PROGRESS.md")
    assert not check_doc_numbers.ist_zahlen_gegenstand("PROGRAMM/eingang/BEWERTUNG.md")

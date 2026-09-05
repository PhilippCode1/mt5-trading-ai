"""Die Doku-Tore als Mengenregel (Katalog A14) -- rote und gruene Eichfaelle.

Ersetzt ``tests/test_auftrag_doku_tore.py`` des Altstands (dort: Ausnahmeliste fuer
``AUFTRAG/``). Geprueft wird die Definition der lebenden Dokumente, die Pflichtmenge an
der Wurzel, dass eigene Programmdokumente scharf geprueft bleiben und dass fremde
Eingaenge und das Archiv nicht gescannt, sondern per Manifest gesichert sind.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

NL = chr(10)
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


def test_eine_ueber_zeilen_umgebrochene_zusicherung_faellt_auf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROTER EICHFALL (Gegenlese T10, E13): Markdown setzt Zeilen zu einem Absatz
    zusammen -- das Tor muss es auch. "vollstaendig" / "implementiert" auf zwei Zeilen
    und "produktions-" / "reif" mit Bindestrich-Umbruch kamen zeilenweise durch.
    Gemeldet wird an der Zeile, in der die Zusicherung beginnt (3 und 4)."""
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    ordner = tmp_path / "PROGRAMM"
    ordner.mkdir()
    datei = ordner / "bericht.md"
    zeilen = [
        "# Auftrag 1",
        "",
        "Der Geldpfad ist vollstaendig",
        "implementiert und damit produktions-",
        "reif.",
        "",
    ]
    datei.write_text(NL.join(zeilen), encoding="utf-8")
    probleme = check_docs_claims.check_file(datei)
    zeilen = sorted(int(p.split(":")[1]) for p in probleme)
    assert zeilen == [3, 4], probleme
    assert any("vollstaendig implementiert" in p for p in probleme), probleme
    assert any("produktionsreif" in p for p in probleme), probleme


def test_ein_beleg_unmittelbar_nach_dem_absatz_entlastet_ihn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GRUENE GEGENPROBE: der Beleg in den zwei Zeilen nach der Zusicherung entlastet
    sie -- auch wenn sie ueber den Umbruch geht. Das Fenster darf nicht strenger sein
    als die Zeile, fuer die der Beleg schon galt."""
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    ordner = tmp_path / "PROGRAMM"
    ordner.mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_beleg.py").write_text("def test_x(): pass" + NL)
    datei = ordner / "bericht.md"
    zeilen = [
        "Der Geldpfad ist vollstaendig",
        "implementiert.",
        "Beleg: `tests/test_beleg.py::test_x`",
        "",
    ]
    datei.write_text(NL.join(zeilen), encoding="utf-8")
    assert check_docs_claims.check_file(datei) == []


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


# --- keine Luecke zwischen lebend und gesichert ----------------------------------


def test_keine_verfolgte_markdown_ist_unbeaufsichtigt() -> None:
    """Gruener Eichfall am Bestand: jede .md ist lebend oder per Manifest gesichert."""
    assert doku_menge.unbeaufsichtigt() == []


def test_eine_markdown_unter_tests_ist_rot(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROTER EICHFALL: eine .md an einem Ort, den kein Tor sieht, wird gemeldet."""
    monkeypatch.setattr(
        doku_menge,
        "verfolgte_markdown",
        lambda repo=None: ["README.md", "tests/NOTIZEN.md", "archiv/x.md"],
    )
    assert doku_menge.unbeaufsichtigt() == ["tests/NOTIZEN.md"]


# --- Gegenlese T5 (2026-09-04): Einwaende B2, B3, B4/B5 als Eichfaelle ------------------


def _git(repo: Path, *args: str) -> None:
    # Windows haelt frisch geschriebene Git-Objekte sporadisch fest
    # (Virenscanner): sechs Versuche mit wachsender Pause, dann hart (F-008).
    for versuch in range(6):
        lauf = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        if lauf.returncode == 0:
            return
        flatter = any(
            m in (lauf.stderr or "")
            for m in ("Permission denied", "failed to insert into database")
        )
        if not flatter or versuch == 5:
            raise AssertionError(f"git {args} (Versuch {versuch + 1}): {lauf.stderr}")
        time.sleep(0.5 * 2**versuch)


def test_rot_eine_gross_geschriebene_md_an_der_wurzel_wird_gesehen(
    tmp_path: Path,
) -> None:
    """ROTER EICHFALL (B2): `git ls-files '*.md'` sah NOTES.MD nicht; die Menge sah sie nicht."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@t")
    _git(tmp_path, "config", "user.name", "t")
    for name in (*doku_menge.PFLICHT_WURZEL, "NOTES.MD", "STAND.markdown"):
        (tmp_path / name).write_text("# x\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    gesehen = doku_menge.verfolgte_markdown(tmp_path)
    assert "NOTES.MD" in gesehen and "STAND.markdown" in gesehen
    befunde = doku_menge.wurzel_befunde(tmp_path)
    assert any("NOTES.MD" in b for b in befunde), befunde
    assert any("STAND.markdown" in b for b in befunde), befunde


def test_rot_ein_beleg_ins_leere_zaehlt_nicht(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROTER EICHFALL (B3): Beleg auf nicht existierende Datei/Test/Codespan, NICHT WIDERRUFEN."""
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    (tmp_path / "PROGRAMM").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_echt.py").write_text(
        "def test_echt() -> None:\n    assert True\n", encoding="utf-8"
    )
    doc = tmp_path / "PROGRAMM" / "bericht.md"
    doc.write_text(
        "Das Fundament ist produktionsreif. Beleg: `gibt_es_nicht`\n"
        "A1 ist erfuellt und abnahmefertig (Nachweis: tests/test_gibt_es_nicht.py).\n"
        "production ready\n"
        "Beleg: tools/nicht_vorhanden.py\n"
        "Zustand: betriebsbereit (dieser Satz wurde NICHT WIDERRUFEN)\n"
        "Weiter im Text.\n"
        "Noch ein Satz ohne Beleg.\n"
        "Dieser Stand ist produktionsreif.\n"
        "Beleg: tests/test_echt.py::test_echt\n"
        "Dieser Stand ist abnahmefertig. Beleg: test_echt\n",
        encoding="utf-8",
    )
    probleme = check_docs_claims.check_file(doc)
    zeilen = sorted(int(p.split(":")[1]) for p in probleme)
    assert zeilen == [1, 2, 3, 5], probleme


def test_gruen_ein_existierender_beleg_deckt_die_behauptung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    (tmp_path / "PROGRAMM").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "tor.py").write_text("print(1)\n", encoding="utf-8")
    doc = tmp_path / "PROGRAMM" / "zustand.md"
    doc.write_text(
        "produktionsreif -- WIDERRUFEN am 2026-09-04.\n"
        "Keine Zusicherung („produktionsreif“, „fertig“) ohne Katalogpunkt.\n"
        "Das Wort `betriebsbereit` faellt hier nur als Erwaehnung.\n"
        "Der Stand ist betriebsbereit.\n"
        "Beleg: `python tools/tor.py --pruefen`\n",
        encoding="utf-8",
    )
    assert check_docs_claims.check_file(doc) == []


def test_vorregistrierungen_sind_gesichert_und_zaehlen_nicht() -> None:
    """E-018: der Ordner ist per Manifest gesichert, seine Dateien sind nicht lebend."""
    assert "PROGRAMM/vorregistrierung" in doku_menge.PRUEFSUMMEN_GESICHERT
    assert "PROGRAMM/vorregistrierung" in archiv_manifest.STANDARD
    assert not doku_menge.ist_lebend("PROGRAMM/vorregistrierung/00-HINWEIS.md")
    assert doku_menge.ist_gesichert("PROGRAMM/vorregistrierung/00-HINWEIS.md")
    assert (
        doku_menge.REPO / "PROGRAMM" / "vorregistrierung" / "MANIFEST.sha256"
    ).is_file()
    assert doku_menge.ist_lebend("PROGRAMM/zustand.md")

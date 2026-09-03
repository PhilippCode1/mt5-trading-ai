"""Die Doku-Tore gegenueber ``AUFTRAG/`` -- roter und gruener Eichfall.

WARUM ES DIESE DATEI GIBT
-------------------------
Stufe 1 des Dauerauftrags hat zwei Tore in ihrem Geltungsbereich beschnitten
(``AUFTRAG/entscheidungen.md``, E-004). Eine Beschneidung, die niemand festhaelt, ist
von einer Aushoehlung nicht zu unterscheiden: beide sehen im Code gleich aus, und die
zweite faellt erst auf, wenn ein Bericht mit einer Notenbehauptung durchlaeuft.

Darum pinnen diese Faelle **beide Haelften**:

* die weiche -- ``AUFTRAG/`` zaehlt nicht gegen die Dateiobergrenze,
* die scharfe -- ``AUFTRAG/`` wird weiterhin auf Zusicherungen geprueft.

Der zweite Fall ist der wichtigere. Faellt er weg, ist §0 des Auftrags („Du darfst dir
keine Note geben") im eigenen Abschlussordner unbewacht.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools import check_doc_numbers, check_docs_claims

REPO = Path(__file__).resolve().parents[1]


# --- die weiche Haelfte: nicht mitzaehlen --------------------------------------


def test_auftrag_zaehlt_nicht_gegen_die_obergrenze() -> None:
    """``counted`` laesst jede Datei unter ``AUFTRAG/`` aus der Zaehlung."""
    alle = [REPO / "README.md", REPO / "AUFTRAG" / "zustand.md"]
    gezaehlt = check_docs_claims.counted(alle)
    assert REPO / "README.md" in gezaehlt
    assert REPO / "AUFTRAG" / "zustand.md" not in gezaehlt


def test_die_obergrenze_selbst_wurde_nicht_angehoben() -> None:
    """Die Grenze bleibt bei 32 -- beschnitten wurde der Geltungsbereich, nicht sie.

    Waere sie angehoben worden, waere das eine gesenkte Schwelle, damit etwas
    durchgeht (V6). Dieser Fall haelt genau das fest.
    """
    assert check_docs_claims.MAX_MARKDOWN_FILES == 32


def test_das_echte_repo_besteht_die_zaehlung() -> None:
    """Gruener Eichfall am echten Bestand, nicht an einer Attrappe."""
    gezaehlt = check_docs_claims.counted(check_docs_claims.tracked_markdown())
    assert len(gezaehlt) <= check_docs_claims.MAX_MARKDOWN_FILES


# --- die scharfe Haelfte: weiter pruefen ---------------------------------------


def test_notenbehauptung_in_auftrag_wird_gefunden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ROTER EICHFALL: eine Zusicherung ohne Beleg faellt auch in ``AUFTRAG/`` auf.

    Geprueft wird ``check_file`` -- dieselbe Funktion, die ``main`` ueber JEDE
    getrackte Markdown-Datei laufen laesst, ``AUFTRAG/`` eingeschlossen. Der
    Repo-Bezugspunkt wird umgehaengt, weil ``check_file`` den Pfad relativ dazu
    meldet; die Datei liegt sonst ausserhalb.
    """
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    ordner = tmp_path / "AUFTRAG"
    ordner.mkdir()
    datei = ordner / "bericht.md"
    datei.write_text(
        "# Stufe X\n\nDieses Vorhaben ist 10/10 und produktionsreif.\n",
        encoding="utf-8",
    )
    probleme = check_docs_claims.check_file(datei)
    # Zuerst, dass ueberhaupt etwas gefunden wurde -- ``all`` auf einer leeren Liste
    # ist wahr und wuerde den Fall sonst still bestehen lassen.
    assert probleme, "eine Notenbehauptung ohne Beleg muss gemeldet werden"
    assert any("10/10" in p for p in probleme)
    assert any("produktionsreif" in p for p in probleme)
    assert all(p.startswith("AUFTRAG/") for p in probleme)


def test_dieselbe_behauptung_mit_beleg_geht_durch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GRUENER EICHFALL: mit ausfuehrbarem Beleg ist dieselbe Zeile zulaessig."""
    monkeypatch.setattr(check_docs_claims, "REPO", tmp_path)
    ordner = tmp_path / "AUFTRAG"
    ordner.mkdir()
    datei = ordner / "bericht.md"
    datei.write_text(
        "# Stufe X\n\nDieses Vorhaben ist 10/10 und produktionsreif.\n"
        "Beleg: tests/test_auftrag_doku_tore.py::"
        "test_notenbehauptung_in_auftrag_wird_gefunden\n",
        encoding="utf-8",
    )
    assert check_docs_claims.check_file(datei) == []


def test_der_auftragsordner_liegt_wirklich_im_pruefumfang() -> None:
    """``main`` prueft, was ``tracked_markdown`` liefert -- und das enthaelt AUFTRAG/."""
    getrackt = {
        p.relative_to(REPO).as_posix() for p in check_docs_claims.tracked_markdown()
    }
    assert any(rel.startswith("AUFTRAG/") for rel in getrackt), (
        "AUFTRAG/ muss getrackt und damit im Pruefumfang sein"
    )


# --- das Zahlen-Tor ------------------------------------------------------------


def test_auftrag_gilt_dem_zahlen_tor_als_historisch() -> None:
    """``AUFTRAG/`` ist ausgenommen wie ``PROGRESS.md`` und ``docs/audit/``."""
    assert check_doc_numbers.is_historical("AUFTRAG/zustand.md")
    assert check_doc_numbers.is_historical("AUFTRAG/stufen/01-historie/bericht.md")


def test_das_zahlen_tor_bleibt_fuer_projektdoku_scharf() -> None:
    """Gegenprobe: die Ausnahme greift NUR fuer die benannten Praefixe.

    ``ABSCHLUSS-3a/`` stand hier bis Stufe 9 auf der scharfen Seite. Es ist dorthin
    gewandert, wo ``PROGRESS.md`` und ``docs/audit/`` schon standen -- der Ordner traegt
    im Kopf woertlich, dass er eingefroren ist und nicht mehr nachgezogen wird, und ihn
    rueckwirkend zu aendern verbietet E-007. Was scharf bleibt, ist die **lebende**
    Projektdoku: README, MASTERBERICHT, FEHLT, SPAETER, ABBRUCH.
    """
    for lebend in (
        "README.md",
        "MASTERBERICHT.md",
        "FEHLT.md",
        "SPAETER.md",
        "ABBRUCH.md",
        "BERICHT_TEIL3.md",
    ):
        assert not check_doc_numbers.is_historical(lebend), lebend
    for eingefroren in (
        "PROGRESS.md",
        "docs/audit/x.md",
        "AUFTRAG/zustand.md",
        "ABSCHLUSS/06-ABBRUCHKRITERIUM.md",
        "ABSCHLUSS-3a/05-URTEIL.md",
    ):
        assert check_doc_numbers.is_historical(eingefroren), eingefroren


# --- Programm NEUAUFBAU: PROGRAMM/ ist Programmordner, eingang/ und masterprompts/ ---
# --- sind fremde Eingaenge -----------------------------------------------------


def test_programm_zaehlt_nicht_gegen_die_obergrenze() -> None:
    """``PROGRAMM/`` ist wie ``AUFTRAG/`` der vorgeschriebene Programmordner."""
    alle = [REPO / "README.md", REPO / "PROGRAMM" / "zustand.md"]
    gezaehlt = check_docs_claims.counted(alle)
    assert REPO / "README.md" in gezaehlt
    assert REPO / "PROGRAMM" / "zustand.md" not in gezaehlt


def test_fremde_eingaenge_werden_nicht_auf_zusicherungen_geprueft() -> None:
    """Bewertung und Masterprompts zitieren Zusicherungen als Befund; eigene nicht."""
    bewertung = REPO / "PROGRAMM" / "eingang" / "BEWERTUNG.md"
    prompt = REPO / "PROGRAMM" / "masterprompts" / "MASTERPROMPT-CC-01-FUNDAMENT.md"
    eigene = REPO / "PROGRAMM" / "zustand.md"
    readme = REPO / "README.md"
    pruefbar = check_docs_claims.pruefbar([bewertung, prompt, eigene, readme])
    assert bewertung not in pruefbar
    assert prompt not in pruefbar
    assert eigene in pruefbar
    assert readme in pruefbar


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


def test_das_echte_repo_hat_fremde_eingaenge_im_baum() -> None:
    """Gruener Eichfall am echten Bestand: die Eingaenge liegen da, ausgenommen."""
    alle = check_docs_claims.tracked_markdown()
    fremd = [p for p in alle if check_docs_claims.ist_fremder_eingang(p)]
    assert len(fremd) >= 11, "zehn Masterprompts und die Bewertung"
    pruefbar = check_docs_claims.pruefbar(alle)
    assert not any(p in pruefbar for p in fremd)


def test_doc_numbers_nimmt_fremde_eingaenge_aus_und_prueft_eigene() -> None:
    assert check_doc_numbers.ist_fremder_eingang("PROGRAMM/eingang/BEWERTUNG.md")
    assert check_doc_numbers.ist_fremder_eingang(
        "PROGRAMM/masterprompts/MASTERPROMPT-CC-01-FUNDAMENT.md"
    )
    assert not check_doc_numbers.ist_fremder_eingang("PROGRAMM/zustand.md")
    assert not check_doc_numbers.is_historical("PROGRAMM/zustand.md")
    # Der Programmordner ist Messprotokoll (Commit-Kennungen, Messwerte je Modul):
    # vom Zahlen-Tor ausgenommen, vom Behauptungs-Tor nicht.
    assert check_doc_numbers.ist_programmordner("PROGRAMM/zustand.md")
    assert not check_doc_numbers.ist_programmordner("README.md")
    assert REPO / "PROGRAMM" / "zustand.md" in check_docs_claims.pruefbar(
        [REPO / "PROGRAMM" / "zustand.md"]
    )

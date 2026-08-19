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
    """Gegenprobe: die Ausnahme greift NUR fuer die drei benannten Praefixe."""
    assert not check_doc_numbers.is_historical("README.md")
    assert not check_doc_numbers.is_historical("MASTERBERICHT.md")
    assert not check_doc_numbers.is_historical("ABSCHLUSS-3a/05-URTEIL.md")

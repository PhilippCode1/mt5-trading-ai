"""Eichfaelle fuer das Manifest-Tor (tools/archiv_manifest.py, Katalog A14).

Rot: eine veraenderte, eine fehlende und eine ungelistete Datei werden gemeldet.
Gruen: ein unveraenderter Ordner besteht; die echten Eingaenge des Repos bestehen.
"""

from __future__ import annotations

from pathlib import Path

from tools import archiv_manifest as tor

REPO = Path(__file__).resolve().parents[1]


def _ordner(tmp_path: Path) -> Path:
    o = tmp_path / "archiv"
    (o / "unter").mkdir(parents=True)
    (o / "a.md").write_text("alpha\n", encoding="utf-8")
    (o / "unter" / "b.txt").write_text("beta\n", encoding="utf-8")
    assert tor.schreiben(o, erneuern=False) == 0
    return o


def test_unveraendert_besteht(tmp_path: Path) -> None:
    o = _ordner(tmp_path)
    assert tor.pruefen(o) == 0


def test_veraenderte_datei_ist_rot(tmp_path: Path) -> None:
    o = _ordner(tmp_path)
    (o / "a.md").write_text("alpha geaendert\n", encoding="utf-8")
    assert tor.pruefen(o) == 1


def test_fehlende_datei_ist_rot(tmp_path: Path) -> None:
    o = _ordner(tmp_path)
    (o / "unter" / "b.txt").unlink()
    assert tor.pruefen(o) == 1


def test_ungelistete_datei_ist_rot(tmp_path: Path) -> None:
    """Eine stille Ergaenzung ist auch eine Aenderung."""
    o = _ordner(tmp_path)
    (o / "neu.md").write_text("dazu\n", encoding="utf-8")
    assert tor.pruefen(o) == 1


def test_manifest_wird_nicht_nebenbei_ueberschrieben(tmp_path: Path) -> None:
    o = _ordner(tmp_path)
    assert tor.schreiben(o, erneuern=False) == 1
    assert tor.schreiben(o, erneuern=True) == 0


def test_fehlendes_manifest_ist_kein_gruen(tmp_path: Path) -> None:
    """Eine Pruefung ohne Gegenstand besteht nicht (Regel 4)."""
    o = tmp_path / "leer"
    o.mkdir()
    assert tor.pruefen(o) == 2


def test_die_echten_eingaenge_sind_unveraendert() -> None:
    """Gruener Eichfall am echten Bestand: Bewertung und Masterprompts wie eingecheckt."""
    for rel in ("PROGRAMM/eingang", "PROGRAMM/masterprompts"):
        assert tor.pruefen(REPO / rel) == 0, rel

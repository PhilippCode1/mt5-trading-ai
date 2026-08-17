"""Tests fuer das Kopie-Tor aus ``tools/kopien_abgleichen.py``.

Anlass: ``ABSCHLUSS/04-ALPHA.md`` trug im Kopf die Zusicherung, wortgleiche Kopie von
``ALPHA.md`` zu sein, und war um den gesamten Block "Stand Paket 3a -- nach der Messung"
veraltet. Der Abschlussordner gab damit zur Kernfrage des Vorhabens zwei einander
widersprechende Antworten, von denen eine sich selbst als identisch mit der anderen
bezeichnete. Eine Zusicherung, die niemand prueft, ist keine.
"""

from __future__ import annotations

import pytest
from tools import kopien_abgleichen as ka

KOPF = (
    "<!-- Wortgleiche Kopie von ORIGINAL.md (Testfall). Gepflegt wird die\n"
    "     Wurzeldatei. -->\n"
)
RUMPF = "# Titel\n\nEin Absatz.\n"


def _baue(tmp_path, rumpf_der_kopie: str = RUMPF, original: str = RUMPF):
    (tmp_path / "ORIGINAL.md").write_bytes(original.encode("utf-8"))
    (tmp_path / "KOPIE.md").write_bytes((KOPF + "\n" + rumpf_der_kopie).encode("utf-8"))
    return tmp_path


def test_kopie_wird_am_kopf_erkannt() -> None:
    zerlegt = ka.zerlege(KOPF + "\n" + RUMPF)
    assert zerlegt is not None
    kopf, rumpf = zerlegt
    assert rumpf == RUMPF
    assert kopf.endswith("\n\n")


def test_datei_ohne_zusicherung_ist_keine_kopie() -> None:
    assert ka.zerlege("# Ein ganz normales Dokument\n") is None
    assert ka.zerlege("<!-- irgendein anderer Kommentar -->\n\n# Titel\n") is None


def test_crlf_wird_wie_lf_zerlegt() -> None:
    """Sonst haengt das Urteil daran, auf welchem Rechner die Datei geschrieben wurde."""
    zerlegt = ka.zerlege((KOPF + "\n" + RUMPF).replace("\n", "\r\n"))
    assert zerlegt is not None
    _, rumpf = zerlegt
    assert ka._normal(rumpf) == RUMPF


def test_gleiche_kopie_wird_nicht_beanstandet(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ka, "REPO", _baue(tmp_path))
    assert ka.abweichende() == []


def test_roter_eichfall_abweichende_kopie_wird_gefunden(tmp_path, monkeypatch) -> None:
    """Der Fall, den es im Repo wirklich gab: die Kopie ist veraltet."""
    monkeypatch.setattr(
        ka, "REPO", _baue(tmp_path, rumpf_der_kopie="# Titel\n\nEin ANDERER Absatz.\n")
    )
    schief = ka.abweichende()
    assert len(schief) == 1
    kopie, quelle = schief[0]
    assert kopie.name == "KOPIE.md"
    assert quelle.name == "ORIGINAL.md"


def test_fehlendes_original_ist_ein_fehler_kein_stilles_ueberspringen(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / "KOPIE.md").write_bytes((KOPF + "\n" + RUMPF).encode("utf-8"))
    monkeypatch.setattr(ka, "REPO", tmp_path)
    with pytest.raises(ka.KopieFehler, match="ORIGINAL.md"):
        ka.abweichende()


def test_nur_zeilenenden_gelten_nicht_als_abweichung(tmp_path, monkeypatch) -> None:
    """Bewusste Entscheidung: git normalisiert (``core.autocrlf``), das Tor auch.

    Ein Tor, dessen Urteil davon abhaengt, auf welchem Rechner ausgecheckt wurde,
    schlaegt mal an und mal nicht -- und wird dann abgeschaltet statt befolgt.
    """
    monkeypatch.setattr(
        ka, "REPO", _baue(tmp_path, rumpf_der_kopie=RUMPF.replace("\n", "\r\n"))
    )
    assert ka.abweichende() == []
    # Streng gerechnet ist es sehr wohl ein Unterschied -- den nutzt nur der Schreiber.
    assert len(ka.abweichende(streng=True)) == 1


def test_die_kopien_dieses_repos_sind_wortgleich() -> None:
    """Das eigentliche Tor. Schlaegt an, sobald ein Original ohne seine Kopie waechst."""
    schief = [
        f"{k.relative_to(ka.REPO).as_posix()} != {q.relative_to(ka.REPO).as_posix()}"
        for k, q in ka.abweichende()
    ]
    assert not schief, (
        "Kopien weichen von ihren Originalen ab: "
        + ", ".join(schief)
        + " — nachziehen mit: python tools/kopien_abgleichen.py"
    )

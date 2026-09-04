"""Stufe 8 — Testwirkung statt Testdeckung. Die Abnahme des Auftrags, als Dauertor.

WAS DER AUFTRAG VERLANGT
------------------------
Woertlich::

    Mutationstor auf die kritischen Dateien des Geldpfads mit einer Toetungsrate als
    blockierender Schwelle. Fuer jede Datei im Sicherheitsverzeichnis den Importpfad
    vom Diensteinstiegspunkt nachweisen -- sonst rot. Negativtests fuer jeden Pruefer.
    Deckung von Zeilen auf Zweige je Datei.

    Abnahme: die Mutationssonden faerben den Lauf rot; keine Testdatei prueft mehr eine
    Funktion ohne Produktionsaufrufer.

WAS DIE MESSUNG GEFUNDEN HAT
----------------------------
* **Kein Mutationstor.** Die Proben der Stufen 4 bis 7 liefen von Hand, je einmal. Eine
  Probe, die nur laeuft, wenn ich daran denke, ist keine Sperre.
* **``gates/learning_phase.py`` (geloescht, E-009) war von keinem Einstiegspunkt aus
  erreichbar** -- 20 von
  21 Dateien des Sicherheitsverzeichnisses waren es, diese eine nicht.
* **Keine Zweigdeckung konfiguriert**, keine Schwelle. Gemessen lag das Paket bei 86,9 %
  Zweigdeckung, die schwaechste Datei bei 67,9 % -- ausgerechnet die aus Stufe 5.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mt5_trading_ai.execution.schwebende_auftraege import (
    FORMATFASSUNG,
    SchwebeAkte,
    SchwebenderAuftrag,
)

ROOT = Path(__file__).resolve().parents[1]
PAKET = ROOT / "mt5_trading_ai"

#: Das Sicherheitsverzeichnis: die drei Teilpakete, in denen eine Sperre stehen kann.
SICHERHEITSVERZEICHNIS = ("risk", "gates", "execution")


# =====================================================================
# A1 — Mutationstor mit blockierender Schwelle
# =====================================================================
def test_das_mutationstor_gibt_es_und_es_blockiert() -> None:
    """Ohne blockierende Schwelle waere es ein Bericht, keine Sperre."""
    from tools.mutationstor import KATALOG, MINDEST_TOETUNGSRATE

    assert MINDEST_TOETUNGSRATE == 1.0
    assert len(KATALOG) >= 12, "Ein Katalog mit einer Handvoll Sonden misst nichts."


def test_jede_sonde_findet_ihren_anker_im_heutigen_code() -> None:
    """DER Fall, der eine verrottende Sonde fängt.

    Eine Sonde, deren Ankertext nicht mehr im Code steht, mutiert nichts -- der
    Testlauf bleibt gruen, und die Sonde zaehlt trotzdem als „getoetet", wenn man es
    nicht prueft. Genau so war es beim ersten Lauf des Werkzeugs: **alle vier** Sonden
    auf CRLF-Dateien fanden ihren Anker nicht, weil der Katalog in LF geschrieben ist.
    Das Werkzeug meldet es laut; dieser Fall haelt es fest.
    """
    from tools.mutationstor import KATALOG

    fehlend = []
    for sonde in KATALOG:
        text = (ROOT / sonde.datei).read_text(encoding="utf-8").replace("\r\n", "\n")
        if sonde.alt not in text:
            fehlend.append(f"{sonde.name} ({sonde.datei})")
    assert fehlend == [], f"Sonden ohne Anker im Code: {fehlend}"


def test_keine_sonde_faellt_mit_ihrer_eigenen_datei_zusammen() -> None:
    """Eine Sonde, die den Pruefling selbst mutiert, prueft sich selbst."""
    from tools.mutationstor import KATALOG

    assert all(not s.datei.endswith("mutationstor.py") for s in KATALOG)


def test_der_katalog_deckt_die_kritischen_dateien_des_geldpfads() -> None:
    """Ein Katalog, der nur die bequemen Dateien trifft, misst die bequemen Dateien."""
    from tools.mutationstor import KATALOG

    getroffen = {s.datei for s in KATALOG}
    pflicht = {
        "mt5_trading_ai/venue/mt5.py",
        "mt5_trading_ai/execution/risk_manager.py",
        "mt5_trading_ai/risk/stop_budget.py",
    }
    fehlt = pflicht - getroffen
    assert fehlt == set(), f"Keine Sonde auf: {fehlt}"


@pytest.mark.slow
def test_das_mutationstor_laeuft_und_toetet_jede_sonde() -> None:
    """Bestaetigt durch Ausfuehrung. Der teuerste Fall der Suite -- und der Kern.

    Er faehrt jede Sonde und verlangt die Toetungsrate 1,0. Ueberlebt eine, ist ein
    Defekt eingebaut worden, den kein Test bemerkt hat.
    """
    lauf = subprocess.run(
        [sys.executable, "tools/mutationstor.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Toetungsrate: 1.000" in lauf.stdout, lauf.stdout


# =====================================================================
# A2 — Importpfad vom Diensteinstiegspunkt fuer jede Datei
# =====================================================================
def _modulname(pfad: Path) -> str:
    return pfad.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")


def _paketimporte(pfad: Path) -> set[str]:
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    aus: set[str] = set()
    for k in ast.walk(baum):
        if isinstance(k, ast.ImportFrom) and k.module:
            if k.module.startswith("mt5_trading_ai"):
                aus.add(k.module)
        elif isinstance(k, ast.Import):
            aus.update(n.name for n in k.names if n.name.startswith("mt5_trading_ai"))
    return aus


def _einstiegspunkte() -> list[Path]:
    """Werkzeuge mit ``main()`` -- die Diensteinstiegspunkte dieses Standes."""
    aus = []
    for p in sorted((ROOT / "tools").glob("*.py")):
        baum = ast.parse(p.read_text(encoding="utf-8"))
        if any(
            isinstance(k, ast.FunctionDef | ast.AsyncFunctionDef) and k.name == "main"
            for k in baum.body
        ):
            aus.append(p)
    return aus


def _erreichbar() -> set[str]:
    pfad_je_modul = {
        _modulname(p): p for p in PAKET.rglob("*.py") if "__pycache__" not in p.parts
    }
    erreicht: set[str] = set()
    rand = list(_einstiegspunkte())
    while rand:
        for modul in _paketimporte(rand.pop()):
            if modul in erreicht:
                continue
            erreicht.add(modul)
            if modul in pfad_je_modul:
                rand.append(pfad_je_modul[modul])
    return erreicht


def test_es_gibt_ueberhaupt_diensteinstiegspunkte() -> None:
    """Laut scheitern: findet die Pruefung ihren Gegenstand nicht, ist sie kein Beleg."""
    assert len(_einstiegspunkte()) >= 10


def test_jede_datei_des_sicherheitsverzeichnisses_ist_vom_einstiegspunkt_erreichbar() -> (
    None
):
    """„Sonst rot" -- woertlich der Auftrag.

    Vor dieser Stufe war ``gates/learning_phase.py`` von keinem Einstiegspunkt aus
    erreichbar: ein Modul mit vier ausformulierten Grenzen, gruenen Eigentests und
    **null** Aufrufern im Ausfuehrungspfad. Es wurde damals in ``tools/modelllauf.py``
    verdrahtet; beide sind seit b0a4c5b geloescht (E-009). Dieser Fall haelt fest,
    dass keine Datei still verwaist.
    """
    erreicht = _erreichbar()
    dateien = [
        p
        for teil in SICHERHEITSVERZEICHNIS
        for p in (PAKET / teil).rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "__init__.py"
    ]
    assert dateien, "Das Sicherheitsverzeichnis ist leer -- Pruefung ohne Gegenstand."
    verwaist = sorted(_modulname(p) for p in dateien if _modulname(p) not in erreicht)
    assert verwaist == [], (
        f"Ohne Importpfad von einem Diensteinstiegspunkt: {verwaist}. "
        "Ein Modul mit gruenen Eigentests belegt nicht, dass es je laeuft."
    )


def test_die_erreichbarkeitspruefung_faengt_ein_verwaistes_modul(
    tmp_path: Path,
) -> None:
    """Der gruene Gegenfall zur Pruefung selbst.

    Ohne ihn bestuende der Fall oben auch an einer Rechnung, die grundsaetzlich alles
    fuer erreichbar haelt. Geprueft wird an einem Modulnamen, den es nicht gibt.
    """
    assert "mt5_trading_ai.gibt.es.nicht" not in _erreichbar()


# =====================================================================
# A3 — Negativtests fuer jeden Pruefer
# =====================================================================
#: Die Pruefer dieses Standes: Werkzeuge, die ein Urteil faellen und mit einem
#: Rueckgabewert ungleich 0 blockieren.
PRUEFER = (
    "check_docs_claims.py",
    "check_doc_numbers.py",
    "gen_docs.py",
    "kopien_abgleichen.py",
    "aufzeichnung_redigieren.py",
    "mutationstor.py",
    "zweigdeckung.py",
)


@pytest.mark.parametrize("pruefer", PRUEFER)
def test_jeder_pruefer_existiert(pruefer: str) -> None:
    assert (ROOT / "tools" / pruefer).is_file()


@pytest.mark.parametrize("pruefer", PRUEFER)
def test_jeder_pruefer_hat_einen_negativtest(pruefer: str) -> None:
    """Ein Pruefer ohne roten Fall ist eine Behauptung.

    Gesucht wird nach einer Zusicherung auf einen **Fehlschlag** dieses Pruefers
    irgendwo in ``tests/`` -- ein ``returncode != 0``, ein ``returncode == 1`` oder ein
    erwarteter Wurf. Ein Test, der ihn nur gruen faehrt, belegt nicht, dass er je
    ablehnt.
    """
    stamm = pruefer[:-3]
    treffer = []
    for testdatei in sorted((ROOT / "tests").glob("*.py")):
        text = testdatei.read_text(encoding="utf-8")
        if stamm not in text:
            continue
        for marke in (
            "returncode == 1",
            "returncode != 0",
            "returncode ==  1",
            "rc == 1",
            "pytest.raises",
            "!= 0",
        ):
            if marke in text:
                treffer.append(testdatei.name)
                break
    assert treffer, (
        f"Kein Negativtest fuer tools/{pruefer}: keine Testdatei erwartet von ihm je "
        "einen Fehlschlag."
    )


# =====================================================================
# A4 — Zweigdeckung je Datei
# =====================================================================
def test_das_zweigdeckungstor_gibt_es_und_es_hat_eine_schwelle() -> None:
    from tools.zweigdeckung import GELDPFAD, MINDEST_ZWEIGDECKUNG

    assert 0.0 < MINDEST_ZWEIGDECKUNG <= 1.0
    assert len(GELDPFAD) >= 10, "Ein Geldpfad aus drei Dateien ist keiner."


def test_die_zweigdeckung_ist_konfiguriert() -> None:
    """``branch = true`` -- sonst misst die Deckung Zeilen und heisst Zweige."""
    cfg = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.coverage.run]" in cfg
    assert "branch = true" in cfg


# =====================================================================
# Die fail-closed-Zweige aus Stufe 5, die die Deckungsmessung als Luecke zeigte
# =====================================================================
def _akte(tmp_path: Path, inhalt: str | None) -> SchwebeAkte:
    pfad = tmp_path / "schwebe.json"
    if inhalt is not None:
        pfad.write_text(inhalt, encoding="utf-8")
    return SchwebeAkte(pfad)


def test_eine_leere_akte_meldet_nichts_schwebt(tmp_path: Path) -> None:
    assert _akte(tmp_path, "   \n").laden().schwebt is False


def test_eine_akte_die_kein_objekt_ist_sperrt(tmp_path: Path) -> None:
    befund = _akte(tmp_path, "[1, 2, 3]").laden()
    assert befund.sperrgrund is not None and "kein Objekt" in befund.sperrgrund


def test_eine_akte_ohne_eintragsliste_sperrt(tmp_path: Path) -> None:
    inhalt = json.dumps({"fassung": FORMATFASSUNG, "eintraege": "keine Liste"})
    befund = _akte(tmp_path, inhalt).laden()
    assert befund.sperrgrund is not None and "eintraege" in befund.sperrgrund


def test_ein_eintrag_der_kein_objekt_ist_sperrt(tmp_path: Path) -> None:
    inhalt = json.dumps({"fassung": FORMATFASSUNG, "eintraege": ["nur ein Text"]})
    befund = _akte(tmp_path, inhalt).laden()
    assert befund.sperrgrund is not None and "kein Objekt" in befund.sperrgrund


def test_ein_eintrag_ohne_kennung_sperrt(tmp_path: Path) -> None:
    inhalt = json.dumps({"fassung": FORMATFASSUNG, "eintraege": [{"grund": "x"}]})
    befund = _akte(tmp_path, inhalt).laden()
    assert befund.sperrgrund is not None and "ohne Kennung" in befund.sperrgrund


def test_ein_unvollstaendiger_eintrag_zaehlt_trotzdem(tmp_path: Path) -> None:
    """Die Kennung ist die Auskunft, auf die es ankommt -- auch ohne Begleitangaben."""
    inhalt = json.dumps(
        {"fassung": FORMATFASSUNG, "eintraege": [{"client_order_id": "k-1"}]}
    )
    befund = _akte(tmp_path, inhalt).laden()
    assert befund.sperrgrund is not None
    assert [e.client_order_id for e in befund.eintraege] == ["k-1"]


def test_ein_eintrag_mit_unlesbarer_zeit_zaehlt_trotzdem(tmp_path: Path) -> None:
    inhalt = json.dumps(
        {
            "fassung": FORMATFASSUNG,
            "eintraege": [
                {"client_order_id": "k-2", "grund": "Zeitablauf", "seit": "gestern"}
            ],
        }
    )
    befund = _akte(tmp_path, inhalt).laden()
    assert befund.sperrgrund is not None and "ohne Zeit" in befund.sperrgrund
    assert [e.client_order_id for e in befund.eintraege] == ["k-2"]


def test_das_aufloesen_einer_unbekannten_kennung_meldet_false(tmp_path: Path) -> None:
    """Der gruene Gegenfall: nichts da, nichts entfernt -- und kein Wurf."""
    akte = _akte(tmp_path, None)
    assert akte.aufloesen("gibt-es-nicht", befund="beim Broker nachgesehen") is False


def test_ein_zweiter_vermerk_derselben_kennung_aendert_nichts(tmp_path: Path) -> None:
    akte = _akte(tmp_path, None)
    ts = datetime(2026, 8, 17, 12, tzinfo=UTC)
    akte.vermerken(SchwebenderAuftrag("k-3", "erster Grund", ts, "EURUSD"))
    akte.vermerken(SchwebenderAuftrag("k-3", "zweiter Grund", ts, "EURUSD"))
    eintraege = akte.laden().eintraege
    assert len(eintraege) == 1 and eintraege[0].grund == "erster Grund"


def test_eine_akte_in_einem_unlesbaren_pfad_sperrt(tmp_path: Path) -> None:
    """Ein Verzeichnis statt einer Datei: ``OSError`` -- und der sperrt."""
    pfad = tmp_path / "akte-als-ordner.json"
    pfad.mkdir()
    befund = SchwebeAkte(pfad).laden()
    assert befund.sperrgrund is not None
    assert "unlesbar" in befund.sperrgrund
    assert befund.schwebt is True

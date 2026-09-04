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
import textwrap
from collections import Counter
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
#
# Programm NEUAUFBAU, Auftrag 1 (T6, Entscheidung E-006; Katalog A4, A15, A17, A18):
# * Das Mutationstor faehrt in einer Kopie des Arbeitsbaums, nie im Arbeitsbaum (F-005,
#   Bytecode-Vergiftung T(d)); der slow-Fall unten faehrt nur den Selbsttest mit zwei
#   Sonden, das volle Tor ist ein CI-Schritt. Die Eichfaelle (rot: unwirksame Sonde
#   ueberlebt; gruen: Katalog 13/13; Arbeitsbaum unveraendert) stehen in
#   tests/eichfall_mutationstor.py.
# * Zwei Tore: der handverlesene Katalog bei 1,0; dazu erzeugte Sonden ueber alle
#   Geldpfad-Dateien (>= 3 je Datei, gesamt >= 50, Rate >= 0,90). Die Pins unten halten
#   beide Schwellen fest. Ein roter Grundlauf (Test faellt ohne Mutant) wird benannt,
#   in den Mutantenlaeufen abgewaehlt und macht das Urteil rot.
# * Zweigdeckung je Geldpfad-Datei >= 0,90 (A15; vorher 0,80), gemessen in der Kopie;
#   die Ausgabe nennt je roter Datei die fehlenden Zweige; eine rote Suite wird
#   berichtet, macht das Urteil aber rot.
# =====================================================================
def test_das_mutationstor_gibt_es_und_es_blockiert() -> None:
    """Ohne blockierende Schwelle waere es ein Bericht, keine Sperre -- zwei Tore."""
    from tools.mutationstor import (
        KATALOG,
        MINDEST_SONDEN_GESAMT,
        MINDEST_SONDEN_JE_DATEI,
        MINDEST_TOETUNGSRATE,
        MINDEST_TOETUNGSRATE_GESAMT,
    )

    assert MINDEST_TOETUNGSRATE == 1.0
    assert len(KATALOG) >= 12, "Ein Katalog mit einer Handvoll Sonden misst nichts."
    # Das zweite Tor (A4, A17): erzeugte Sonden, nie unter diese Zahlen.
    assert MINDEST_TOETUNGSRATE_GESAMT >= 0.90
    assert MINDEST_SONDEN_GESAMT >= 50
    assert MINDEST_SONDEN_JE_DATEI >= 3


def test_jede_sonde_findet_ihren_anker_im_heutigen_code() -> None:
    """DER Fall, der eine verrottende Sonde fängt.

    Eine Sonde, deren Ankertext nicht mehr im Code steht, mutiert nichts -- der
    Testlauf bleibt gruen, und die Sonde zaehlt trotzdem als „getoetet", wenn man es
    nicht prueft. Genau so war es beim ersten Lauf des Werkzeugs: **alle vier** Sonden
    auf CRLF-Dateien fanden ihren Anker nicht, weil der Katalog in LF geschrieben ist.
    Das Werkzeug meldet es laut; dieser Fall haelt es fest -- fuer den Katalog und fuer
    die erzeugten Sonden (deren Anker sind ganze Quellzeilen an fester Stelle).
    """
    from tools.mutationstor import alle_sonden, anwenden

    fehlend = []
    for sonde in alle_sonden():
        text = (ROOT / sonde.datei).read_text(encoding="utf-8").replace("\r\n", "\n")
        if anwenden(text, sonde) is None:
            fehlend.append(f"{sonde.name} ({sonde.datei})")
    assert fehlend == [], f"Sonden ohne Anker im Code: {fehlend}"


def test_keine_sonde_faellt_mit_ihrer_eigenen_datei_zusammen() -> None:
    """Eine Sonde, die den Pruefling selbst mutiert, prueft sich selbst."""
    from tools.mutationstor import alle_sonden

    assert all(not s.datei.endswith("mutationstor.py") for s in alle_sonden())


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


def test_erzeugte_sonden_treffen_jede_geldpfad_datei_mindestens_dreimal() -> None:
    """A17: >= 3 Sonden je Geldpfad-Datei; A4: >= 50 Sonden gesamt. Namen eindeutig."""
    from tools.mutationstor import (
        KATALOG,
        MINDEST_SONDEN_GESAMT,
        MINDEST_SONDEN_JE_DATEI,
        erzeugte_sonden,
    )
    from tools.zweigdeckung import GELDPFAD

    erzeugt = erzeugte_sonden()
    je_datei = Counter(s.datei for s in erzeugt)
    zu_wenig = {
        kurz: je_datei[f"mt5_trading_ai/{kurz}"]
        for kurz in GELDPFAD
        if je_datei[f"mt5_trading_ai/{kurz}"] < MINDEST_SONDEN_JE_DATEI
    }
    assert zu_wenig == {}, f"Dateien unter {MINDEST_SONDEN_JE_DATEI} Sonden: {zu_wenig}"
    assert set(je_datei) == {f"mt5_trading_ai/{k}" for k in GELDPFAD}
    assert len(KATALOG) + len(erzeugt) >= MINDEST_SONDEN_GESAMT
    namen = [s.name for s in erzeugt]
    assert len(namen) == len(set(namen)), "doppelte Sondennamen"
    assert all(s.herkunft == "erzeugt" and s.zeile is not None for s in erzeugt)


def test_jeder_erzeugte_mutant_kompiliert_und_aendert_den_quelltext() -> None:
    """Ein Mutant mit Syntaxfehler stirbt an jedem Import -- das misst nichts."""
    from tools.mutationstor import anwenden, erzeugte_sonden

    for sonde in erzeugte_sonden():
        text = (ROOT / sonde.datei).read_text(encoding="utf-8").replace("\r\n", "\n")
        mutiert = anwenden(text, sonde)
        assert mutiert is not None and mutiert != text, sonde.name
        compile(mutiert, sonde.datei, "exec")


def test_die_erzeugung_ist_deterministisch() -> None:
    """Fester Seed je Datei: derselbe Quelltext, dieselben Sonden -- auch in einem
    zweiten Prozess (``--liste``), also unabhaengig von PYTHONHASHSEED."""
    from tools.mutationstor import KATALOG, erzeugte_sonden

    erste = erzeugte_sonden()
    erzeugte_sonden.cache_clear()
    assert erzeugte_sonden() == erste

    lauf = subprocess.run(
        [sys.executable, "-B", "tools/mutationstor.py", "--liste"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert f"Katalog: {len(KATALOG)} Sonden" in lauf.stdout
    assert f"Erzeugt: {len(erste)} Sonden" in lauf.stdout
    for sonde in erste:
        assert sonde.name in lauf.stdout, sonde.name
    assert f"Gesamt: {len(KATALOG) + len(erste)} Sonden" in lauf.stdout


def test_die_operatoren_der_erzeugung_an_einem_beispiel() -> None:
    """Jeder Operator findet seine Stelle; assert, print und Modulebene bleiben aussen."""
    from tools.mutationstor import _stellen

    quelle = textwrap.dedent(
        """\
        LIMIT = 10


        def pruefe(a, b, x):
            if a < b and not x:
                return True
            if a is None:
                return 3
            print(a == b)
            assert a != 0
            return False
        """
    )
    stellen = _stellen(quelle)
    arten = Counter(st.operator for st in stellen)
    assert arten == {
        "vergleich": 2,  # a < b, a is None -- nicht print(a == b), nicht assert
        "bool": 1,
        "not-entfernt": 1,
        "not-ergaenzt": 2,
        "return": 2,
        "konstante": 2,  # LIMIT = 10 (Modulebene, Zuweisung) und return 3
    }, arten
    zeilen = quelle.encode("utf-8").split(b"\n")
    for st in stellen:
        vorher = zeilen[st.z1 - 1][: st.s1]
        nachher = zeilen[st.z2 - 1][st.s2 :]
        mutiert = list(zeilen)
        mutiert[st.z1 - 1 : st.z2] = (vorher + st.neu + nachher).split(b"\n")
        text = b"\n".join(mutiert).decode("utf-8")
        assert text != quelle
        compile(text, "<beispiel>", "exec")


def test_die_zuordnung_aus_der_deckung_kennt_drei_faelle() -> None:
    """Testdatei aus dem Kontext; leerer Kontext -> Suite; nichts -> unerreicht."""
    from tools.mutationstor import SUITE, Sonde, Zuordnung

    datei = "mt5_trading_ai/gibt/es/nicht.py"  # keine Unterprozess-Reichweite
    zuordnung = Zuordnung(
        {
            datei: {
                5: ("test_stop_budget.test_x", "test_risk_sizing.TestK.test_y"),
                6: ("",),
            }
        }
    )

    def sonde(zeile: int) -> Sonde:
        return Sonde("s", datei, "x", "y", (), "", zeile=zeile, herkunft="erzeugt")

    assert zuordnung.tests_fuer(sonde(5)) == (
        ("tests/test_risk_sizing.py", "tests/test_stop_budget.py"),
        "deckung",
    )
    assert zuordnung.tests_fuer(sonde(6)) == (SUITE, "suite")
    assert zuordnung.tests_fuer(sonde(7)) == ((), "unerreicht")


def test_die_zuordnung_stellt_deckungsdateien_vor_unterprozessdateien() -> None:
    """Mit ``-x`` faellt der Toeter aus der Deckung, bevor die teuren Dateien mit
    Unterprozess-Start laufen -- also stehen die Deckungsdateien vorn."""
    from tools.mutationstor import Sonde, Zuordnung, unterprozess_reichweite

    datei = "mt5_trading_ai/risk/stop_budget.py"
    reichweite = unterprozess_reichweite(datei)
    assert reichweite, "keine Testdatei mit Unterprozess erreicht stop_budget.py?"
    assert "tests/eichfall_werkzeuge.py" in reichweite  # 29 x --help: teuer
    deckung = "tests/test_stop_budget.py"
    assert deckung not in reichweite
    zuordnung = Zuordnung({datei: {5: ("test_stop_budget.test_x",)}})
    sonde = Sonde("s", datei, "x", "y", (), "", zeile=5, herkunft="erzeugt")
    tests, art = zuordnung.tests_fuer(sonde)
    assert art == "deckung"
    assert tests[0] == deckung
    assert tests[1:] == tuple(sorted(reichweite))


def test_der_fehlschlagparser_liest_failed_und_error_zeilen() -> None:
    """Knotenkennungen aus dem Kurzbericht; ohne Dubletten; nichts aus dem Fliesstext."""
    from tools.zweigdeckung import fehlschlaege

    ausgabe = (
        "....F..E                                                          [100%]\n"
        "=================================== FAILURES ===================================\n"
        "FAILED tests/test_a.py::test_x - AssertionError: FAILED nicht am Zeilenanfang\n"
        "ERROR tests/test_b.py::test_y[param mit Leerzeichen] - RuntimeError\n"
        "FAILED tests/test_a.py::test_x - AssertionError\n"
        "ERROR tests/test_c.py\n"
        "2 failed, 4 passed, 2 errors in 1.23s\n"
    )
    assert fehlschlaege(ausgabe) == (
        "tests/test_a.py::test_x",
        "tests/test_b.py::test_y[param",
        "tests/test_c.py",
    )
    assert fehlschlaege("5 passed in 0.10s\n") == ()


def test_der_grundlauf_merkt_rote_faelle_und_weist_unbrauchbare_laeufe_ab() -> None:
    """exit 1 mit FAILED-Zeile: gemerkt und abgewaehlt; exit 2 (Sammelfehler) oder
    exit 1 ohne benennbaren Fall: kein Grundlauf (TorFehler)."""
    from tools.mutationstor import SUITE, Grundlauf, Lauf, TorFehler

    g = Grundlauf()
    g.eintragen(("tests/test_a.py",), Lauf(0, "3 passed\n", 1.0))
    assert g.abwahl(("tests/test_a.py",)) == ()
    g.eintragen(
        ("tests/test_b.py",),
        Lauf(1, "FAILED tests/test_b.py::test_rot - AssertionError\n1 failed\n", 1.0),
    )
    assert g.abwahl(("tests/test_b.py",)) == ("tests/test_b.py::test_rot",)
    assert g.rote_faelle() == ("tests/test_b.py::test_rot",)
    with pytest.raises(TorFehler, match="exit=2"):
        g.eintragen(("tests/test_c.py",), Lauf(2, "Interrupted: 1 error\n", 1.0))
    with pytest.raises(TorFehler, match="kein roter Fall benennbar"):
        g.eintragen(("tests/test_d.py",), Lauf(1, "1 failed\n", 1.0))
    # Ein Suite-Grundlauf deckt jeden Ausschnitt: seine roten Faelle gelten ueberall.
    g.eintragen(SUITE, Lauf(1, "FAILED tests/test_e.py::test_z - X\n", 9.0))
    assert g.abwahl(("tests/irgendwas.py",)) == ("tests/test_e.py::test_z",)
    assert g.dauer(SUITE) == 9.0


def test_das_urteil_bleibt_rot_bei_rotem_grundlauf(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Jede Sonde getoetet -- und trotzdem rot, weil ein Fall der Suite ohne Beleg ist."""
    from tools.mutationstor import KATALOG, Ergebnis, _bericht

    ergebnisse = tuple(
        Ergebnis(s, True, "", 1.0, s.tests, "katalog", f"{s.tests[0]}::t")
        for s in KATALOG
    )
    assert _bericht(ergebnisse, 10.0, False, None) == 0
    rc = _bericht(ergebnisse, 10.0, False, None, ("tests/test_e.py::test_z",))
    aus = capsys.readouterr()
    assert rc == 1
    assert "Toetungsrate: 1.000" in aus.out
    assert "FEHLGESCHLAGEN — Grundlauf rot: 1 Faelle" in aus.err
    assert "tests/test_e.py::test_z" in aus.err


def test_der_bericht_nennt_je_erzeugter_sonde_die_testdateien(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tools.mutationstor import Ergebnis, Sonde, _bericht

    sonde = Sonde(
        "x.py:1:0:vergleich",
        "mt5_trading_ai/risk/x.py",
        "a",
        "b",
        (),
        "",
        1,
        "vergleich",
        "erzeugt",
    )
    tests = ("tests/test_p.py", "tests/test_q.py")
    rc = _bericht(
        (Ergebnis(sonde, True, "", 1.0, tests, "deckung", "tests/test_p.py::t"),),
        1.0,
        False,
        5.0,
    )
    aus = capsys.readouterr().out
    assert rc == 0
    assert "Zuordnung je erzeugter Sonde" in aus
    assert "x.py:1:0:vergleich: Deckung, 2 Testdateien: test_p.py, test_q.py" in aus


@pytest.mark.slow
def test_das_mutationstor_selbsttest_toetet_zwei_katalogsonden_in_der_kopie(
    tmp_path: Path,
) -> None:
    """Bestaetigt durch Ausfuehrung: der Selbsttest (zwei Katalogsonden) in der Kopie.

    Das volle Tor (Katalog + erzeugte Sonden, Grundlauf unter coverage) ist ein
    CI-Schritt und liefe hier ein zweites Mal; der Eichfall 13/13 steht in
    ``tests/eichfall_mutationstor.py``.
    """
    lauf = subprocess.run(
        [
            sys.executable,
            "-B",
            "tools/mutationstor.py",
            "--selbsttest",
            "--kopie",
            str(tmp_path / "kopie"),
        ],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Katalog:  2/2 getoetet, Toetungsrate: 1.000" in lauf.stdout, lauf.stdout
    assert str(tmp_path / "kopie") in lauf.stdout, "Der Lauf nennt die Kopie nicht."
    assert not (tmp_path / "kopie" / "kopie-0").exists(), "Kopie nicht entfernt"


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
    """A15: >= 0,90 je Geldpfad-Datei (vorher 0,80; nie gesenkt)."""
    from tools.zweigdeckung import GELDPFAD, MINDEST_ZWEIGDECKUNG

    assert 0.90 <= MINDEST_ZWEIGDECKUNG <= 1.0
    assert len(GELDPFAD) >= 10, "Ein Geldpfad aus drei Dateien ist keiner."


def test_die_zweigdeckung_ist_konfiguriert() -> None:
    """``branch = true`` -- sonst misst die Deckung Zeilen und heisst Zweige."""
    cfg = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.coverage.run]" in cfg
    assert "branch = true" in cfg


def _deckungsbericht(
    tmp_path: Path,
    zweige: dict[str, tuple[int, int]],
    fehlende_zweige: dict[str, list[list[int]]] | None = None,
    fehlende_zeilen: dict[str, list[int]] | None = None,
    weglassen: str | None = None,
) -> Path:
    """Ein coverage-JSON (Format 3) fuer alle Geldpfad-Dateien."""
    from tools.zweigdeckung import GELDPFAD

    dateien: dict[str, object] = {}
    for kurz in GELDPFAD:
        if kurz == weglassen:
            continue
        gedeckt, gesamt = zweige.get(kurz, (20, 20))
        dateien[f"mt5_trading_ai/{kurz}"] = {
            "summary": {
                "percent_covered": 100.0 * gedeckt / gesamt,
                "covered_branches": gedeckt,
                "num_branches": gesamt,
            },
            "missing_branches": (fehlende_zweige or {}).get(kurz, []),
            "missing_lines": (fehlende_zeilen or {}).get(kurz, []),
        }
    bericht = tmp_path / "coverage.json"
    bericht.write_text(
        json.dumps(
            {
                "meta": {"format": 3, "branch_coverage": True},
                "files": dateien,
                "totals": {
                    "percent_covered": 95.0,
                    "covered_branches": 200,
                    "num_branches": 220,
                },
            }
        ),
        encoding="utf-8",
    )
    return bericht


def test_das_zweigdeckungstor_ist_rot_unter_der_schwelle_und_nennt_die_zweige(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der rote Fall: 83,3 % in risk/leverage.py (die Zahl der Grundmessung) -- und die
    Ausgabe nennt die fehlenden Zweige, damit jemand die Tests ergaenzen kann."""
    from tools.zweigdeckung import urteile

    bericht = _deckungsbericht(
        tmp_path,
        {"risk/leverage.py": (25, 30)},
        {"risk/leverage.py": [[106, 111], [136, 137], [152, -1]]},
        {"risk/leverage.py": [111, 137]},
    )
    rc = urteile(bericht)
    aus = capsys.readouterr()
    assert rc == 1
    assert "risk/leverage.py: 3 fehlende Zweige" in aus.out
    assert "106->111, 136->137, 152->Ausgang" in aus.out
    assert "nicht gelaufene Zeilen: 111, 137" in aus.out
    assert "FEHLGESCHLAGEN — risk/leverage.py: 83.3% Zweigdeckung" in aus.err
    assert "verlangt sind 90%" in aus.err


def test_das_zweigdeckungstor_ist_gruen_ueber_der_schwelle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools.zweigdeckung import urteile

    assert urteile(_deckungsbericht(tmp_path, {"risk/leverage.py": (27, 30)})) == 0
    assert (
        "ok — jede Datei des Geldpfads ueber der Schwelle." in capsys.readouterr().out
    )


def test_das_zweigdeckungstor_ist_rot_wenn_eine_datei_in_der_messung_fehlt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Laut scheitern: eine Geldpfad-Datei ohne Messung ist ein Befund, kein Skip."""
    from tools.zweigdeckung import urteile

    rc = urteile(_deckungsbericht(tmp_path, {}, weglassen="costs/model.py"))
    assert rc == 1
    assert "costs/model.py fehlt in der Messung" in capsys.readouterr().err


def test_das_zweigdeckungstor_ist_rot_bei_fehlendem_oder_unlesbarem_bericht(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tools.zweigdeckung import urteile

    assert urteile(tmp_path / "gibt-es-nicht.json") == 1
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("kein json", encoding="utf-8")
    assert urteile(kaputt) == 1
    aus = capsys.readouterr().err
    assert "fehlt. Erst --messen." in aus and "unlesbar" in aus


def test_die_messung_faellt_ohne_absturz_wenn_die_suite_rot_ist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der rote Eichfall der Messung, mit dem Windows-Fall aus der Grundmessung.

    Vor T6 las ``--messen`` den Unterprozess mit der Systemkodierung (cp1252): ein Byte
    0x81 in der Ausgabe liess den Leser-Thread sterben, ``stdout`` blieb ``None``, und
    das Werkzeug stuerzte mit ``TypeError`` ab (Beleg ``03-grundmessung-mutation-
    pycache-worktree.txt``). Hier schreibt ein absichtlich roter Test genau so ein Byte
    (``Ł`` = C5 81 in utf-8) -- und die Messung urteilt: rot, der rote Fall wird beim
    Namen genannt, die Deckung des gelaufenen Codes steht trotzdem im Bericht, kein
    Traceback. ``messen(kopie=...)`` legt die Kopie des Arbeitsbaums in diesem Ordner
    an; der synthetische Test und das Modul ``kern.py`` liegen daneben, und nur der
    synthetische Test laeuft: ``kern.py`` wird vollstaendig gedeckt, der echte Geldpfad
    zu 0 % -- und das Urteil nennt beides, die rote Suite und jede Datei unter der
    Schwelle.
    """
    from tools.zweigdeckung import messen, urteile

    kopie = tmp_path / "kopie"
    (kopie / "tests").mkdir(parents=True)
    (kopie / "mt5_trading_ai").mkdir()
    (kopie / "mt5_trading_ai" / "__init__.py").write_text("", encoding="utf-8")
    (kopie / "mt5_trading_ai" / "kern.py").write_text(
        "def sperrt(x: int) -> bool:\n    if x < 0:\n        return True\n    return False\n",
        encoding="utf-8",
    )
    (kopie / "tests" / "test_rot_eichfall_zweigdeckung.py").write_text(
        "import sys\n"
        "\n"
        "from mt5_trading_ai.kern import sperrt\n"
        "\n"
        "\n"
        "def test_rot() -> None:\n"
        '    sys.stdout.buffer.write("Zweig \\u0141 Ziel\\n".encode("utf-8"))\n'
        "    sys.stdout.buffer.flush()\n"
        '    assert False, "absichtlich rot"\n'
        "\n"
        "\n"
        "def test_gruen() -> None:\n"
        "    assert sperrt(-1) and not sperrt(1)\n",
        encoding="utf-8",
    )
    messung = messen(
        tmp_path / "cov.json",
        kopie=kopie,
        tests=("tests/test_rot_eichfall_zweigdeckung.py",),
    )
    aus = capsys.readouterr()
    assert messung.rc == 1, aus.out + aus.err
    assert messung.fehlschlaege == (
        "tests/test_rot_eichfall_zweigdeckung.py::test_rot",
    )
    assert messung.bericht == tmp_path / "cov.json"
    assert (tmp_path / "cov.json").is_file()
    assert "Suite rot: 1 Faelle" in aus.out
    assert "Traceback" not in aus.out + aus.err
    assert not (kopie / "betrieb").exists()
    bericht = json.loads((tmp_path / "cov.json").read_text(encoding="utf-8"))
    kern = [v for k, v in bericht["files"].items() if k.endswith("kern.py")]
    assert kern and kern[0]["summary"]["covered_branches"] == 2

    # Das Urteil ueber diesen Bericht: rot wegen der Suite UND wegen der fehlenden
    # Geldpfad-Dateien -- beide Gruende beim Namen.
    rc = urteile(messung.bericht, suite_rot=messung.fehlschlaege)
    aus = capsys.readouterr()
    assert rc == 1
    assert "FEHLGESCHLAGEN — die Suite ist rot (1 Faelle)" in aus.err
    assert "test_rot_eichfall_zweigdeckung.py::test_rot" in aus.err
    assert "FEHLGESCHLAGEN — venue/mt5.py: 0.0% Zweigdeckung" in aus.err
    assert "Traceback" not in aus.out + aus.err


def test_die_kopie_ausserhalb_eines_git_repos_ist_ein_benannter_fehler(
    tmp_path: Path,
) -> None:
    """``git ls-files`` ausserhalb eines Repos: ``KopieFehler`` mit Ort und Exit, kein
    ``CalledProcessError``-Traceback (``messen`` und ``tor`` fangen ihn benannt)."""
    from tools.zweigdeckung import KopieFehler, repo_kopieren

    (tmp_path / "kein-repo").mkdir()
    with pytest.raises(KopieFehler, match="git ls-files .*exit=128"):
        repo_kopieren(tmp_path / "kopie", wurzel=tmp_path / "kein-repo")


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

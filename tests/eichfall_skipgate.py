"""Eichfaelle der beiden Waechter in ``tests/conftest.py`` -- rot und gruen (A2, A10).

Kein Waechter ohne Ausloesenachweis (CLAUDE.md, Regel 6): je Waechter ein Lauf, in
dem er ausloest, und einer, in dem er nichts zu beanstanden hat. Die Laeufe sind
echte pytest-Unterprozesse (``pytester.runpytest_subprocess``) ueber Testdateien im
tmp_path des ``pytester``; der Waechter kommt per ``-p conftest`` hinein -- dieselbe
Datei ``tests/conftest.py``, die ueber dieser Suite liegt, nicht eine Kopie.

Der rote A10-Fall fuer den Zustandsordner schreibt NICHT in den echten Ordner des
Benutzers -- das waere genau der Verstoss, den A10 verbietet. Er setzt im Unterprozess
die Plattformvariablen ``LOCALAPPDATA`` und ``XDG_STATE_HOME`` (die einzigen, die
``standard_zustandsordner()`` noch liest -- die Betreibervariable
``MT5_RISIKO_ZUSTAND_ORDNER`` ist mit D8 entfallen) auf einen Ordner im tmp_path;
``standard_zustandsordner()`` und damit der Waechter folgen ihnen. Welchen
Ordner der Waechter in einem gewoehnlichen Lauf bewacht, steht in dessen Kopfzeile
(``pytest_report_header``).

Der rote A10-Fall fuer den Arbeitsbaum legt eine Datei im Repository an und raeumt
sie nach dem Unterprozess wieder weg -- der Waechter des aeusseren Laufs sieht darum
nichts; bliebe sie liegen, faellt dieser Test selbst durch ihn.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS = REPO / "tests"
CONFTEST = TESTS / "conftest.py"


def _lauf(
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
    quelle: str,
    *,
    umgebung: dict[str, str] | None = None,
) -> pytest.RunResult:
    """Ein pytest-Unterprozess ueber ``test_eichfall.py`` im tmp_path, Waechter geladen."""
    pytester.makepyfile(test_eichfall=textwrap.dedent(quelle))
    # Paket und tests/ importierbar machen: ``-p conftest`` findet tests/conftest.py.
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join((str(REPO), str(TESTS))))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    for name, wert in (umgebung or {}).items():
        monkeypatch.setenv(name, wert)
    # Ohne ``-q``: die Kopfzeilen der Waechter (``pytest_report_header``) gehoeren
    # zur Ausgabe, die die Eichfaelle pruefen.
    return pytester.runpytest_subprocess(
        "-p", "conftest", "-p", "no:cacheprovider", "-rs", "test_eichfall.py"
    )


def _zaehlung(ergebnis: pytest.RunResult) -> dict[str, int]:
    zaehlung = ergebnis.parseoutcomes()
    return {
        "passed": zaehlung.get("passed", 0),
        "failed": zaehlung.get("failed", 0),
        "errors": zaehlung.get("errors", 0),
        "skipped": zaehlung.get("skipped", 0),
    }


# --- Beide Waechter liegen ueber DIESER Suite ---------------------------------------


def test_beide_waechter_sind_in_diesem_lauf_aktiv(
    request: pytest.FixtureRequest,
) -> None:
    """Nicht nur im Unterprozess: die Hooks und die autouse-Fixture stammen aus
    tests/conftest.py und sind fuer diesen Test hier registriert."""
    assert "_waechter_a10" in request.fixturenames
    quellen = {
        Path(getattr(impl.plugin, "__file__", "")).resolve()
        for impl in request.config.hook.pytest_runtest_makereport.get_hookimpls()
    }
    assert CONFTEST.resolve() in quellen
    quellen_sammeln = {
        Path(getattr(impl.plugin, "__file__", "")).resolve()
        for impl in request.config.hook.pytest_make_collect_report.get_hookimpls()
    }
    assert CONFTEST.resolve() in quellen_sammeln


# --- Waechter 1 (A2): Skip = Fehlschlag --------------------------------------------


def test_rot_a2_jede_skip_art_wird_zum_fehlschlag(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fuenf Skip-Arten, fuenf Fehlschlaege, null Skips."""
    ergebnis = _lauf(
        pytester,
        monkeypatch,
        """
        import pytest

        def test_skip_im_test():
            pytest.skip("Gegenstand fehlt (Eichfall pytest.skip)")

        @pytest.mark.skip(reason="Eichfall mark.skip")
        def test_mark_skip():
            pass

        @pytest.mark.skipif(True, reason="Eichfall skipif")
        def test_skipif():
            pass

        def test_importorskip():
            pytest.importorskip("modul_das_es_nicht_gibt_4711")

        @pytest.fixture
        def gegenstand():
            pytest.skip("Eichfall Skip in der Fixture")

        def test_skip_in_der_fixture(gegenstand):
            pass
        """,
    )
    zaehlung = _zaehlung(ergebnis)
    assert ergebnis.ret != 0, ergebnis.outlines[-5:]
    assert zaehlung["skipped"] == 0, zaehlung
    assert zaehlung["failed"] + zaehlung["errors"] == 5, zaehlung
    assert zaehlung["passed"] == 0, zaehlung
    text = "\n".join(ergebnis.outlines)
    assert text.count("Waechter A2 (tests/conftest.py)") >= 5
    for begruendung in (
        "Eichfall pytest.skip",
        "Eichfall mark.skip",
        "Eichfall skipif",
        "modul_das_es_nicht_gibt_4711",
        "Eichfall Skip in der Fixture",
    ):
        assert begruendung in text, begruendung


def test_rot_a2_skip_auf_modulebene_bricht_das_sammeln(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``importorskip`` beim Import des Moduls: kein stilles Wegfallen der Datei."""
    ergebnis = _lauf(
        pytester,
        monkeypatch,
        """
        import pytest

        pytest.importorskip("modul_das_es_nicht_gibt_4711")

        def test_wird_nie_erreicht():
            pass
        """,
    )
    assert ergebnis.ret != 0, ergebnis.outlines[-5:]
    text = "\n".join(ergebnis.outlines)
    assert "Waechter A2 (tests/conftest.py)" in text
    assert "Sammelschritt" in text
    assert "modul_das_es_nicht_gibt_4711" in text
    assert "skipped" not in text.splitlines()[-1]


def test_gruen_a2_und_a10_ein_sauberer_lauf_bleibt_gruen(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Skip und mit Schreiben nur in tmp_path beanstandet kein Waechter etwas."""
    ergebnis = _lauf(
        pytester,
        monkeypatch,
        """
        from pathlib import Path

        def test_rechnet():
            assert 1 + 1 == 2

        def test_schreibt_nur_in_tmp_path(tmp_path: Path):
            datei = tmp_path / "zustand.json"
            datei.write_text("{}", encoding="utf-8")
            assert datei.is_file()
        """,
    )
    assert ergebnis.ret == 0, ergebnis.outlines[-5:]
    assert _zaehlung(ergebnis) == {
        "passed": 2,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }
    text = "\n".join(ergebnis.outlines)
    assert "Waechter A2 (tests/conftest.py): Skip = Fehlschlag." in text
    assert "Waechter A10 (tests/conftest.py): Zustandsordner" in text


# --- Waechter 2 (A10): kein Schreiben in Zustandsordner oder Arbeitsbaum -----------


def test_rot_a10_schreiben_in_den_zustandsordner_faellt(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Test besteht selbst -- und faellt im Abbau durch den Waechter."""
    attrappe = pytester.path / "zustand-attrappe"
    assert not attrappe.exists()
    ergebnis = _lauf(
        pytester,
        monkeypatch,
        """
        from mt5_trading_ai.execution.risiko_zustand import standard_zustandsordner

        def test_schreibt_in_den_zustandsordner():
            ordner = standard_zustandsordner()
            ordner.mkdir(parents=True, exist_ok=True)
            (ordner / "risikozustand.json").write_text("{}", encoding="utf-8")
        """,
        umgebung={"LOCALAPPDATA": str(attrappe), "XDG_STATE_HOME": str(attrappe)},
    )
    assert ergebnis.ret != 0, ergebnis.outlines[-5:]
    zaehlung = _zaehlung(ergebnis)
    assert zaehlung["errors"] == 1 and zaehlung["skipped"] == 0, zaehlung
    text = "\n".join(ergebnis.outlines)
    assert "Waechter A10 (tests/conftest.py)" in text
    assert "Zustandsordner des Benutzers veraendert" in text
    assert "Ordner angelegt" in text
    assert "neu: risikozustand.json" in text
    # Der Waechter hat wirklich diesen Ordner bewacht, nicht den echten.
    assert str(attrappe) in text


def test_rot_a10_schreiben_in_den_arbeitsbaum_faellt(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Datei im Repository ausserhalb von tmp_path: Fehlschlag mit Dateiliste
    und git-status-Zeile. Die Datei wird danach entfernt."""
    ziel = REPO / "eichfall-a10-arbeitsbaum.tmp"
    assert not ziel.exists()
    try:
        ergebnis = _lauf(
            pytester,
            monkeypatch,
            """
            import os
            from pathlib import Path

            def test_schreibt_in_den_arbeitsbaum():
                Path(os.environ["EICHFALL_ZIEL"]).write_text(
                    "Laufzeitzustand", encoding="utf-8"
                )
            """,
            umgebung={"EICHFALL_ZIEL": str(ziel)},
        )
        assert ziel.is_file(), "der Unterprozess hat die Datei nicht angelegt"
    finally:
        if ziel.exists():
            ziel.unlink()
    assert ergebnis.ret != 0, ergebnis.outlines[-5:]
    zaehlung = _zaehlung(ergebnis)
    assert zaehlung["errors"] == 1 and zaehlung["skipped"] == 0, zaehlung
    text = "\n".join(ergebnis.outlines)
    assert "Waechter A10 (tests/conftest.py)" in text
    assert "Arbeitsbaum veraendert" in text
    assert "neu: eichfall-a10-arbeitsbaum.tmp" in text
    assert "?? eichfall-a10-arbeitsbaum.tmp" in text  # git sieht sie ebenfalls

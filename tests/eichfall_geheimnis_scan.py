"""Eichfaelle fuer den Geheimnis-Scan (tools/geheimnis_scan.py, Katalog A5).

ROT: ein gepflanztes Testgeheimnis (AWS-Schluesselmuster) im Arbeitsbaum und -- nach
seiner Loeschung -- nur noch im Verlauf gibt Exit 1; der Fund wird mit Datei und
Gattung genannt, der Fundtext nicht. GRUEN: ein Wegwerf-Klon dieses Repos ohne
Pflanzung hat gegen die eingecheckte Basislinie 0 neue Funde. BASISLINIE: ein Eintrag
gilt nur fuer sein Git-Objekt -- aendert sich die Datei, faellt der Fund heraus;
ungepruefte Eintraege, fehlende Basislinie oder ein Muster in einer Begruendung sind
Exit 2. KONTONAME: ``C:\\Users\\<name>`` in verfolgten Dateien wird gezaehlt und je
Datei mit Gruppe gelistet; in lebenden Dateien ist es per Vorgabe ein Tor (Exit 1),
in den eingefrorenen Gruppen (``archiv/``, ``PROGRAMM/eingang/``,
``PROGRAMM/masterprompts/``) erst mit ``--kontoname-sperre alle``; Platzhalter in
spitzen Klammern zaehlen nicht; ein Abschalten gibt es nicht; der Name steht nie in
der Ausgabe. WERKZEUG: flacher Klon Exit 2, ``--help`` Exit 0 mit ``usage``, keine
absoluten Pfade in der Ausgabe, auch nicht im Werkzeugfehler.

Die Faelle am Mini-Repo brauchen je Scan wenige Sekunden. Die Faelle am Klon dieses
Repos scannen alle Objekte des Verlaufs (rund 1.500) und dauern je Scan etwa 90 s
ohne Last; sie tragen die Marke ``slow`` wie das Mutationstor und laufen in der
Datei-Auswahl, im Pre-Push-Hook und in der CI -- nicht in der Schnellschleife. Der
gruene Klon wird einmal je Modul gescannt (Fixture ``klon_scan``), zwei Faelle lesen
dieselbe Ausgabe.

A10: alles liegt in ``tmp_path`` -- die Wegwerf-Repos, und ueber ``TMP``/``TEMP``/
``TMPDIR`` auch der temporaere Ordner, in den das Werkzeug die Objekte fuer
detect-secrets legt. Der gepflanzte Schluessel wird zur Laufzeit zusammengesetzt,
damit diese Datei selbst kein Fund ist; ebenso die Kontonamen der Kontoname-Faelle.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from tools import geheimnis_scan as gs

REPO = Path(__file__).resolve().parents[1]
WERKZEUG = REPO / "tools" / "geheimnis_scan.py"
BASISLINIE = REPO / gs.BASISLINIE

UMGEBUNG = {
    **os.environ,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONIOENCODING": "utf-8",
    "GIT_AUTHOR_NAME": "Eichfall",
    "GIT_AUTHOR_EMAIL": "eichfall@example.invalid",
    "GIT_COMMITTER_NAME": "Eichfall",
    "GIT_COMMITTER_EMAIL": "eichfall@example.invalid",
}


def _umgebung(tmp: Path) -> dict[str, str]:
    """Umgebung eines Unterprozesses, dessen Temp-Ordner in ``tmp_path`` liegt (A10)."""
    tmp.mkdir(parents=True, exist_ok=True)
    return {**UMGEBUNG, "TMP": str(tmp), "TEMP": str(tmp), "TMPDIR": str(tmp)}


#: Windows haelt frisch geschriebene Git-Objekte sporadisch fest (Virenscanner,
#: Indexer). Sechs Versuche mit wachsender Pause; der Fehler bleibt hart (F-008).
GIT_VERSUCHE = 6
GIT_FLATTER = ("Permission denied", "failed to insert into database", "unable to index")


def _git(repo: Path, *args: str) -> str:
    """Git im Wegwerf-Repo; Schreibfehler mit 'Permission denied' werden wiederholt.

    Unter Windows scheitert das Umbenennen einer frisch geschriebenen Objektdatei
    sporadisch mit EACCES, wenn ein Virenscanner oder Indexer sie gerade haelt
    (gemessen: 5 von 30 Repo-Anlagen bei Volllast des Rechners, Beleg
    06-geheimnis-scan-eichfall-pytest.txt; unter der Last des Pre-Push-Laufs fiel
    derselbe Fall zweimal trotz dreier Versuche, F-008). Das ist kein Verhalten des
    geprueften Werkzeugs; sechs Versuche mit wachsender Pause, dann Fehlschlag.
    """
    for versuch in range(GIT_VERSUCHE):
        res = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, env=UMGEBUNG
        )
        fehler = res.stderr.decode("utf-8", "replace")
        if res.returncode == 0:
            return res.stdout.decode("utf-8", "replace")
        vorbei = versuch == GIT_VERSUCHE - 1
        if not any(m in fehler for m in GIT_FLATTER) or vorbei:
            raise AssertionError(f"git {args} (Versuch {versuch + 1}): {fehler}")
        time.sleep(0.5 * 2**versuch)
    raise AssertionError("unerreichbar")


def _scan(repo: Path, basislinie: Path, *extra: str) -> tuple[int, str]:
    """Das Werkzeug als Unterprozess; Temp-Ordner neben dem Repo (in ``tmp_path``)."""
    res = subprocess.run(
        [
            sys.executable,
            str(WERKZEUG),
            "--repo",
            str(repo),
            "--basislinie",
            str(basislinie),
            *extra,
        ],
        capture_output=True,
        env=_umgebung(repo.parent / "tmp"),
    )
    text = (
        res.stdout.decode("utf-8", "replace") + res.stderr.decode("utf-8", "replace")
    ).replace("\r\n", "\n")
    assert "Traceback" not in text, text
    return res.returncode, text


def _pflanzung() -> str:
    """AWS-Schluesselmuster (AKIA + 16 Grossbuchstaben/Ziffern), zusammengesetzt."""
    return "AKIA" + "ZZTESTPFLANZUNG1"


def _leere_basislinie(pfad: Path) -> Path:
    pfad.write_text(
        json.dumps({"format": gs.FORMAT, "eintraege": []}) + "\n", encoding="utf-8"
    )
    return pfad


def _basislinie_mit(pfad: Path, eintraege: list[dict[str, object]]) -> Path:
    pfad.write_text(
        json.dumps({"format": gs.FORMAT, "eintraege": eintraege}) + "\n",
        encoding="utf-8",
    )
    return pfad


def _commit(repo: Path, nachricht: str, *pfade: str) -> None:
    _git(repo, "add", *pfade)
    _git(repo, "commit", "-q", "-m", nachricht)


@pytest.fixture
def mini(tmp_path: Path) -> tuple[Path, Path]:
    """Ein Repo mit einem Commit und eine leere Basislinie daneben."""
    repo = tmp_path / "mini"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("# Mini\n", encoding="utf-8")
    _commit(repo, "start", "README.md")
    return repo, _leere_basislinie(tmp_path / "basislinie.json")


# --- Mini-Repo: Mechanik ---------------------------------------------------------


def test_mini_repo_ohne_fund_ist_gruen_und_nennt_keine_absoluten_pfade(
    mini: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, basislinie = mini
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 0, text
    assert "NEUE FUNDE: 0" in text
    assert (
        "Tor --kontoname-sperre lebend: 0 Treffer im Geltungsbereich -> gruen" in text
    )
    assert "Exit 0" in text
    # CI-tauglich: kein Pfad dieses Rechners in der Ausgabe.
    assert str(tmp_path) not in text
    assert str(REPO) not in text
    assert "Users" not in text.replace("C:\\Users\\<name>", "")
    # A10: der Temp-Ordner des Werkzeugs lag in tmp_path und ist wieder leer.
    assert (tmp_path / "tmp").is_dir()
    assert list((tmp_path / "tmp").iterdir()) == []


def test_gepflanztes_geheimnis_im_baum_ist_rot(mini: tuple[Path, Path]) -> None:
    """ROTER EICHFALL (Arbeitsbaum): verfolgt, noch nicht committet."""
    repo, basislinie = mini
    (repo / "zugang.txt").write_text(f"zugang: {_pflanzung()}\n", encoding="utf-8")
    _git(repo, "add", "zugang.txt")
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 1, text
    assert "NEU  Baum" in text and "zugang.txt:1" in text
    assert "AWS" in text
    assert _pflanzung() not in text, "der Fundtext darf nicht in der Ausgabe stehen"


def test_geheimnis_nur_im_verlauf_ist_rot(mini: tuple[Path, Path]) -> None:
    """ROTER EICHFALL (Verlauf): committet, danach geloescht -- bleibt abrufbar."""
    repo, basislinie = mini
    (repo / "zugang.txt").write_text(f"zugang: {_pflanzung()}\n", encoding="utf-8")
    _commit(repo, "pflanzung", "zugang.txt")
    _git(repo, "rm", "-q", "zugang.txt")
    _git(repo, "commit", "-q", "-m", "loeschung")
    assert not (repo / "zugang.txt").exists()
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 1, text
    assert "NEU  Verlauf" in text and "zugang.txt:1" in text
    assert _pflanzung() not in text


def test_basislinie_deckt_genau_dieses_objekt(
    mini: tuple[Path, Path], tmp_path: Path
) -> None:
    """Ungeprueft sperrt; eingeordnet deckt; die geaenderte Datei faellt heraus."""
    repo, basislinie = mini
    (repo / "zugang.txt").write_text(f"zugang: {_pflanzung()}\n", encoding="utf-8")
    _commit(repo, "pflanzung", "zugang.txt")

    exit_code, text = _scan(repo, basislinie, "--basislinie-schreiben")
    assert exit_code == 0, text
    daten = json.loads(basislinie.read_text(encoding="utf-8"))
    assert daten["format"] == gs.FORMAT
    assert all(e["klasse"] == gs.UNGEPRUEFT for e in daten["eintraege"])
    assert {e["gattung"] for e in daten["eintraege"]} >= {
        "Muster: AWS-Zugangsschluessel",
        "detect-secrets: AWS Access Key",
    }
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 2 and gs.UNGEPRUEFT in text, text

    for e in daten["eintraege"]:
        e["klasse"] = "testdatum"
        e["begruendung"] = "Eichfall: absichtlich gepflanztes Muster"
    _basislinie_mit(basislinie, daten["eintraege"])
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 0, text
    assert f"{len(daten['eintraege'])} verwendet" in text

    with (repo / "zugang.txt").open("a", encoding="utf-8") as f:
        f.write("eine zweite Zeile\n")
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 1, text
    assert "NEU  Baum" in text and "zugang.txt:1" in text
    assert "ohne Fund im Repo" in text  # der alte Eintrag deckt nur das alte Objekt


def test_basislinie_fehlt_oder_ist_ungueltig_ist_werkzeugfehler(
    mini: tuple[Path, Path], tmp_path: Path
) -> None:
    repo, _ = mini
    exit_code, text = _scan(repo, tmp_path / "gibt-es-nicht.json")
    assert exit_code == 2 and "Basislinie fehlt" in text, text

    eintrag: dict[str, object] = {
        "objekt": "0" * 40,
        "pfad": "x",
        # Der Ort gehoert seit E12 zum Schluessel (tools/geheimnis_scan.py).
        "ort": "lebend",
        "zeile": 1,
        "gattung": "Muster: IP-Adresse mit Port",
        "abdruck": "0" * 16,
        "klasse": "adresse-lokal",
        # IP:Port zur Laufzeit zusammengesetzt -- sonst waere diese Zeile selbst ein Fund.
        "begruendung": "Adresse " + "10.0.0.1" + ":8080 im Beleg",
    }
    exit_code, text = _scan(repo, _basislinie_mit(tmp_path / "b1.json", [eintrag]))
    assert exit_code == 2 and "enthaelt selbst ein Muster" in text, text

    eintrag["begruendung"] = "harmlos"
    eintrag["klasse"] = "erfunden"
    exit_code, text = _scan(repo, _basislinie_mit(tmp_path / "b2.json", [eintrag]))
    assert exit_code == 2 and "unbekannt" in text, text

    exit_code, text = _scan(repo, _basislinie_mit(tmp_path / "b3.json", [{"x": 1}]))
    assert exit_code == 2 and "genau die Felder" in text, text


def test_werkzeugfehler_nennt_keinen_rechnerpfad(tmp_path: Path) -> None:
    """Auch Exit 2 ist CI-Protokoll: kein Ordner dieses Rechners in der Meldung."""
    kein_repo = tmp_path / "kein-repo"
    kein_repo.mkdir()
    exit_code, text = _scan(kein_repo, _leere_basislinie(tmp_path / "b.json"))
    assert exit_code == 2 and "WERKZEUGFEHLER: kein Git-Repository" in text, text
    assert str(tmp_path) not in text and str(REPO) not in text


def test_flacher_klon_ist_werkzeugfehler(
    mini: tuple[Path, Path], tmp_path: Path
) -> None:
    """Ein Verlauf ohne Tiefe ist kein Verlauf: die CI muss fetch-depth 0 setzen."""
    repo, basislinie = mini
    flach = tmp_path / "flach"
    _git(tmp_path, "clone", "-q", "--depth", "1", repo.as_uri(), str(flach))
    exit_code, text = _scan(flach, basislinie)
    assert exit_code == 2 and "flacher Klon" in text, text


def test_kontoname_lebend_ist_tor_platzhalter_und_eingefrorene_gruppen_nicht(
    mini: tuple[Path, Path],
) -> None:
    """Zaehlung nach Gruppen; Tor per Vorgabe nur ueber lebende Dateien; kein Name in
    der Ausgabe; Platzhalter ``<konto>`` und ``...`` zaehlen nicht; kein Abschalten."""
    repo, basislinie = mini
    # Namen zur Laufzeit zusammengesetzt, damit diese Datei keinen Kontonamen zaehlt.
    name = "test" + "konto"
    (repo / "notiz.txt").write_text(
        f"Pfad: C:\\Users\\{name}\\x.txt und /c/Users/{name}/y\n", encoding="utf-8"
    )
    (repo / "redigiert.txt").write_text(
        "C:\\Users\\<konto>\\x.txt, C:\\Users\\...\\y.txt, C:\\Users\\<name>\\z\n",
        encoding="utf-8",
    )
    (repo / "archiv").mkdir()
    (repo / "archiv" / "alt.txt").write_text(
        f"C:\\Users\\{name}\\alt.txt\n", encoding="utf-8"
    )
    _commit(repo, "notizen", "notiz.txt", "redigiert.txt", "archiv/alt.txt")

    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 1, text
    assert "3 Treffer in 2 Dateien, 1 Namen (Treffer je Name: [3])" in text
    assert (
        "nach Gruppe: lebend 2, archiv/ 1, PROGRAMM/eingang/ 0, PROGRAMM/masterprompts/ 0"
        in text
    )
    assert "Tor --kontoname-sperre lebend: 2 Treffer im Geltungsbereich -> rot" in text
    assert re.search(r"^\s+2\s+\[lebend\] notiz\.txt$", text, re.M), text
    assert re.search(r"^\s+1\s+\[archiv/\] archiv/alt\.txt$", text, re.M), text
    assert "redigiert.txt" not in text
    assert "3 Kontonamen (2 im Tor 'lebend')" in text
    assert name not in text

    # Nur noch die eingefrorene Gruppe: per Vorgabe gruen, mit "alle" rot.
    _git(repo, "rm", "-q", "notiz.txt")
    _git(repo, "commit", "-q", "-m", "notiz entfernt")
    exit_code, text = _scan(repo, basislinie)
    assert exit_code == 0, text
    assert (
        "Tor --kontoname-sperre lebend: 0 Treffer im Geltungsbereich -> gruen" in text
    )
    assert "1 Kontonamen (0 im Tor 'lebend')" in text
    exit_code, text = _scan(repo, basislinie, "--kontoname-sperre", "alle")
    assert exit_code == 1, text
    assert "Tor --kontoname-sperre alle: 1 Treffer im Geltungsbereich -> rot" in text
    assert name not in text

    # Kein Abschalten: argparse weist jeden anderen Wert ab (Exit 2, usage).
    exit_code, text = _scan(repo, basislinie, "--kontoname-sperre", "aus")
    assert exit_code == 2 and "usage" in text and "invalid choice" in text, text


def test_help_ist_exit_0_mit_usage() -> None:
    """Katalog A13: jedes Werkzeug antwortet auf --help mit Exit 0 und ``usage``."""
    res = subprocess.run(
        [sys.executable, str(WERKZEUG), "--help"], capture_output=True, env=UMGEBUNG
    )
    stdout = res.stdout.decode("utf-8", "replace")
    assert res.returncode == 0, res.stderr.decode("utf-8", "replace")
    assert "usage" in stdout.lower() and "--kontoname-sperre {lebend,alle}" in stdout


def test_muster_bleiben_fuer_den_zustandstest_importierbar() -> None:
    """tests/test_risiko_zustand_geheimnis.py faehrt MUSTER ueber die Zustandsdatei."""
    assert len(gs.MUSTER) == 9
    for titel, muster in gs.MUSTER:
        assert isinstance(titel, str) and isinstance(muster.pattern, bytes)


def test_platzhalter_und_redaktionsmarke_sind_keine_namen() -> None:
    """Das Muster des Werkzeugs selbst: ``<konto>`` und ``...`` fallen durch, ein
    Name faellt hinein -- auch mit doppelten Backslashes (JSON, repr)."""
    name = "irgend" + "wer"
    assert (
        gs.kontonamen(b"C:\\Users\\<konto>\\x C:/Users/.../y C--Users-<konto>-z") == []
    )
    assert gs.kontonamen(f"C:\\\\Users\\\\{name}\\\\x".encode()) == [name.encode()]
    assert gs.kontonamen(f"/c/Users/{name}/y".encode()) == [name.encode()]
    # Bindestrich-Schreibweise eines Pfads (Werkzeugordner): der Name endet am Strich.
    assert gs.kontonamen(f"C--Users-{name}-OneDrive-x".encode()) == [name.encode()]


# --- Klon dieses Repos: die echte Basislinie -----------------------------------------


def _klon(basis: Path) -> Path:
    """Wegwerf-Klon dieses Repos: nur der aktuelle Zweig mit seinem ganzen Verlauf.

    ``--single-branch``, weil das Objektlager eines Worktrees auch die Zweige
    paralleler Worktrees traegt; die gehoeren nicht zu diesem Stand.
    """
    ziel = basis / "klon"
    _git(basis, "clone", "-q", "--shared", "--single-branch", str(REPO), str(ziel))
    return ziel


@pytest.fixture(scope="module")
def klon_scan(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[int, str]]:
    """Ein Scan des unveraenderten Klons je Modul; zwei Faelle lesen die Ausgabe."""
    basis = tmp_path_factory.mktemp("klon")
    yield _scan(_klon(basis), BASISLINIE)


@pytest.mark.slow
def test_klon_dieses_repos_hat_keine_neuen_funde(
    klon_scan: tuple[int, str],
) -> None:
    """GRUENER EICHFALL (A5): jeder Fund des Verlaufs steht eingeordnet in der
    Basislinie. Exit 0 verlangt zusaetzlich das Kontonamen-Tor (naechster Fall).

    Ein Eintrag "ohne Fund im Repo" ist erlaubt: die Basislinie wird im Worktree
    geschrieben, dessen ``rev-list --all`` auch die Zweige paralleler Worktrees sieht;
    im ``--single-branch``-Klon fehlen deren Blobs (gemessen: 2 von 133, Beleg
    06-geheimnis-scan-eichfall-pytest.txt). Ein verwaister Eintrag deckt nichts und
    schwaecht das Tor nicht; ``--basislinie-schreiben`` raeumt ihn beim naechsten
    Lauf weg."""
    exit_code, text = klon_scan
    assert exit_code in (0, 1), text
    assert "NEUE FUNDE: 0" in text, text
    treffer = re.search(r"Basislinie \S+: (\d+) Eintraege, (\d+) verwendet", text)
    assert treffer, text
    assert int(treffer.group(2)) >= 1, text


@pytest.mark.slow
def test_klon_dieses_repos_hat_keine_kontonamen_in_lebenden_dateien(
    klon_scan: tuple[int, str],
) -> None:
    """Das Kontonamen-Tor ueber die lebenden Dateien dieses Repos: 0 Treffer, Exit 0."""
    exit_code, text = klon_scan
    assert "Tor --kontoname-sperre lebend: 0 Treffer im Geltungsbereich -> gruen" in (
        text
    ), text
    assert exit_code == 0, text


@pytest.mark.slow
def test_klon_mit_pflanzung_und_geaenderter_basisdatei_ist_rot(tmp_path: Path) -> None:
    """ROTER EICHFALL am Klon: Geheimnis nur im Verlauf, Basisdatei geaendert."""
    klon = _klon(tmp_path)
    (klon / "zugang.txt").write_text(f"zugang: {_pflanzung()}\n", encoding="utf-8")
    _commit(klon, "pflanzung", "zugang.txt")
    _git(klon, "rm", "-q", "zugang.txt")
    _git(klon, "commit", "-q", "-m", "loeschung")

    im_baum = {
        zeile.split("\t", 1)[1]: zeile.split()[2]
        for zeile in _git(klon, "ls-tree", "-r", "HEAD").splitlines()
    }
    daten = json.loads(BASISLINIE.read_text(encoding="utf-8"))
    kandidaten = [
        e for e in daten["eintraege"] if im_baum.get(e["pfad"]) == e["objekt"]
    ]
    assert kandidaten, "kein Basislinien-Eintrag zeigt auf eine Datei in HEAD"
    gedeckt = kandidaten[0]["pfad"]
    with (klon / gedeckt).open("a", encoding="utf-8") as f:
        f.write("\n# Eichfall: eine Zeile mehr, der Fund bleibt\n")

    exit_code, text = _scan(klon, BASISLINIE)
    assert exit_code == 1, text
    assert "NEU  Verlauf" in text and "zugang.txt:1" in text
    assert f"NEU  Baum         {gedeckt}:" in text, text
    assert _pflanzung() not in text

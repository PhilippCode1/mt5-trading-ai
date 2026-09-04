"""Eichfaelle der Familie Werkzeuge (Abnahmekatalog A12, A13; Plan T6 "Werkzeuge").

Drei Zusicherungen, jede als Unterprozess gemessen, nicht aus dem Quelltext gelesen:

(a) **A13** -- jedes ``tools/*.py`` mit ``main()`` antwortet auf ``--help`` mit Exit 0
    und einer ``usage``-Zeile.
(b) **A12** -- jedes Werkzeug, das ein Terminal braucht, endet ohne Terminal mit genau
    einer Zeile ``FEHLGESCHLAGEN -- MT5-Terminal nicht erreichbar: <Grund>``, Exit 2
    und ohne ``Traceback`` in stdout+stderr. "Ohne Terminal" wird mit einem **Shim**
    nachgestellt: ``PYTHONPATH`` zeigt auf einen Ordner mit ``MetaTrader5.py``, das
    ``ImportError`` wirft -- wie auf dem Linux-Klon der CI. Das ist zugleich die
    Sicherung dieser Datei: ``MetaTrader5.initialize()`` startet unter Windows das
    Terminal; mit dem Shim kann kein Unterprozess dorthin gelangen
    (``test_der_shim_macht_metatrader5_unsichtbar`` misst das zuerst).
    ``tools/fetch_data.py`` braucht kein Terminal, aber eine Quelle: ohne sie dieselbe
    Form, ``FEHLGESCHLAGEN -- Datenquelle nicht erreichbar: <Grund>``.
(c) **Roter Eichfall** -- dieselben Pruefer (``pruefe_help``, ``pruefe_benannt``)
    laufen in ``PROGRAMM/auftrag-01-fundament/belege/06-werkzeuge-eichfall.py`` gegen
    den Stand **vor** der Aenderung (``git show 97ee206:tools/<datei>`` in einen
    Tempordner) und zeigen Traceback bzw. Exit != 2; Ausgabe in
    ``belege/06-werkzeuge-rot.txt``, der Lauf gegen den Arbeitsbaum in
    ``belege/06-werkzeuge-gruen.txt``. Damit die Pruefer selbst einen roten und einen
    gruenen Eichfall haben, laufen sie hier zusaetzlich gegen synthetische Skripte
    (``test_der_pruefer_*``).

Dazu der lesende Smoke-Test (A9) gegen das Fake-Terminal des Vertragstests: je
Katalogsymbol ein Schritt mit ``currency_profit``/``currency_margin``, ein fehlendes
Symbol ist ein roter Schritt mit Namen, der Serverzeitversatz wird trotzdem gemessen.

Kein Fall dieser Datei liest oder schreibt ausserhalb des Repos und ``tmp_path``
(A10): der Shim liegt in ``tmp_path``, Bytecode wird nicht geschrieben, die
Zustands-Umgebungsvariablen des Entwicklers werden dem Unterprozess nicht mitgegeben.
"""

from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.mt5 import CatalogEntry, Mt5Tick, Mt5Venue
from mt5_trading_ai.venue.protocol import AssetClass
from mt5_trading_ai.venue.smoke import run_smoke

from test_mt5_venue import TS, FakeMt5Terminal, _catalog, _fees

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
FIXTURE_H1 = REPO / "tests" / "fixtures" / "smoke_eurusd_h1.csv"

#: Die eine Zeile, mit der ein Terminalwerkzeug ohne Terminal endet (A12).
PRAEFIX_TERMINAL = "FEHLGESCHLAGEN -- MT5-Terminal nicht erreichbar: "
#: Dieselbe Form fuer ein Werkzeug, dem statt des Terminals die Datenquelle fehlt.
PRAEFIX_QUELLE = "FEHLGESCHLAGEN -- Datenquelle nicht erreichbar: "
EXIT_KEIN_TERMINAL = 2
#: Obergrenze je Unterprozess. Ein Werkzeug, das ohne Terminal haengt, ist rot.
ZEITSCHRANKE_S = 120
#: Obergrenze fuer ``--help``: wer laenger braucht, druckt keine Hilfe, sondern
#: faehrt seinen Lauf (``geheimnis_scan.py`` brauchte so 241 s, T3-Beleg).
HELP_ZEITSCHRANKE_S = 60

#: Zustands-Umgebungsvariablen (Befund D8): sie duerfen einen Unterprozess dieser
#: Datei nie auf den echten Zustandsordner des Entwicklers lenken (A10).
ZUSTANDS_VARIABLEN = (
    "MT5_RISIKO_ZUSTAND",
    "MT5_RISIKO_ZUSTAND_ORDNER",
    "MT5_SCHWEBENDE_AUFTRAEGE",
)

SHIM_QUELLE = (
    '"""Shim der Eichfaelle: das Paket MetaTrader5 ist absichtlich unsichtbar."""\n'
    'raise ImportError("MetaTrader5 (Shim der Eichfaelle): Paket absichtlich '
    'unsichtbar")\n'
)


# ---------------------------------------------------------------------------
# Die Pruefer -- auch der Beleg-Lauf gegen den alten Stand benutzt genau diese
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Lauf:
    befehl: tuple[str, ...]
    #: ``None``: die Zeitschranke ist gerissen -- der Prozess wurde beendet.
    exit: int | None
    stdout: str
    stderr: str

    @property
    def ausgabe(self) -> str:
        return self.stdout + self.stderr


@dataclass(frozen=True)
class Befund:
    werkzeug: str
    gruen: bool
    grund: str
    lauf: Lauf


def shim_umgebung(
    ordner: Path, *, weitere_pfade: tuple[Path, ...] = ()
) -> dict[str, str]:
    """Umgebung eines Unterprozesses, in der ``import MetaTrader5`` scheitert.

    ``ordner`` bekommt das Shim und steht vorn im ``PYTHONPATH``; ``weitere_pfade``
    folgen (der Beleg-Lauf haengt so das Repo an, damit ein aus git ausgepacktes
    altes Werkzeug das Paket findet). Bytecode wird nicht geschrieben, die Ausgabe ist
    UTF-8, die Zustandsvariablen des Entwicklers fehlen.
    """
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "MetaTrader5.py").write_text(SHIM_QUELLE, encoding="utf-8")
    env = dict(os.environ)
    pfade = [str(ordner), *(str(p) for p in weitere_pfade)]
    alt = env.get("PYTHONPATH")
    if alt:
        pfade.append(alt)
    env["PYTHONPATH"] = os.pathsep.join(pfade)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    for name in ZUSTANDS_VARIABLEN:
        env.pop(name, None)
    return env


def ohne_quelle(env: dict[str, str]) -> dict[str, str]:
    """Dieselbe Umgebung, aber jeder HTTP-Abruf laeuft auf einen geschlossenen Port.

    Ein Proxy auf ``127.0.0.1:<frei>`` wird sofort abgewiesen -- schneller und
    bestimmter als DNS-Fehler oder ein gekapptes Netz. Nur Grossschreibung: unter
    Windows sind Umgebungsnamen fallunabhaengig, zwei Schreibweisen im selben Block
    waeren ein Duplikat.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    aus = dict(env)
    for name in list(aus):
        if name.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"):
            aus.pop(name)
    aus["HTTP_PROXY"] = f"http://127.0.0.1:{port}"
    aus["HTTPS_PROXY"] = f"http://127.0.0.1:{port}"
    return aus


def lauf(
    befehl: tuple[str, ...],
    *,
    env: dict[str, str],
    cwd: Path,
    zeitschranke: float = ZEITSCHRANKE_S,
) -> Lauf:
    """Ein Unterprozess; eine gerissene Zeitschranke ist ein Befund (``exit=None``),
    kein Testfehler -- ein Werkzeug, das auf ``--help`` seinen vollen Lauf faehrt,
    soll als rot mit Grund erscheinen, auch im Beleg."""
    try:
        ergebnis = subprocess.run(
            list(befehl),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(cwd),
            timeout=zeitschranke,
        )
    except subprocess.TimeoutExpired as exc:
        return Lauf(
            befehl,
            None,
            _text(exc.stdout),
            _text(exc.stderr) + f"\n<Zeitschranke {zeitschranke:g} s ueberschritten>",
        )
    return Lauf(befehl, ergebnis.returncode, ergebnis.stdout, ergebnis.stderr)


def _text(roh: str | bytes | None) -> str:
    if roh is None:
        return ""
    return roh if isinstance(roh, str) else roh.decode("utf-8", "replace")


def _modulbaum(datei: Path) -> ast.Module:
    return ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))


def werkzeuge_mit_main(ordner: Path) -> list[Path]:
    """Jedes ``*.py`` im Ordner mit einer Funktion ``main`` auf Modulebene."""
    gefunden: list[Path] = []
    for datei in sorted(ordner.glob("*.py")):
        if any(
            isinstance(k, ast.FunctionDef | ast.AsyncFunctionDef) and k.name == "main"
            for k in _modulbaum(datei).body
        ):
            gefunden.append(datei)
    return gefunden


def importiert_realmt5terminal(datei: Path) -> bool:
    """Bindet die Datei ``RealMt5Terminal`` ein? Gelesen am Importbaum, nicht am
    Text -- ``paper_run.py`` nennt die Klasse nur im Modulkopf."""
    for knoten in ast.walk(_modulbaum(datei)):
        if isinstance(knoten, ast.ImportFrom) and any(
            a.name == "RealMt5Terminal" for a in knoten.names
        ):
            return True
    return False


def pruefe_help(werkzeug: Path, *, env: dict[str, str], cwd: Path) -> Befund:
    """A13: ``--help`` -> Exit 0 und ``usage`` in stdout.

    Die Zeitschranke ist knapp: eine Hilfe braucht keine Sekunde. Ein Werkzeug, das
    ``--help`` ignoriert und seinen Lauf faehrt, faellt hier -- mit Grund.
    """
    ergebnis = lauf(
        (sys.executable, str(werkzeug), "--help"),
        env=env,
        cwd=cwd,
        zeitschranke=HELP_ZEITSCHRANKE_S,
    )
    usage = "usage" in ergebnis.stdout.lower()
    gruen = ergebnis.exit == 0 and usage
    stderr_kopf = ergebnis.stderr.strip().splitlines()[-1:] if ergebnis.stderr else []
    grund = f"exit={ergebnis.exit}, usage={'ja' if usage else 'nein'}"
    if stderr_kopf:
        grund += f", stderr: {stderr_kopf[0]}"
    return Befund(werkzeug.name, gruen, grund, ergebnis)


def pruefe_benannt(
    werkzeug: Path,
    argumente: tuple[str, ...],
    *,
    env: dict[str, str],
    cwd: Path,
    praefix: str = PRAEFIX_TERMINAL,
) -> Befund:
    """A12: Exit 2, genau eine ``FEHLGESCHLAGEN``-Zeile mit ``praefix``, kein Traceback.

    Gezaehlt wird ueber stdout **und** stderr: eine zweite ``FEHLGESCHLAGEN``-Zeile
    oder ein Traceback auf dem jeweils anderen Strom zaehlt genauso.
    """
    ergebnis = lauf((sys.executable, str(werkzeug), *argumente), env=env, cwd=cwd)
    zeilen = ergebnis.ausgabe.splitlines()
    benannt = [z for z in zeilen if z.startswith(praefix)]
    fehlgeschlagen = [z for z in zeilen if "FEHLGESCHLAGEN" in z]
    traceback = "Traceback" in ergebnis.ausgabe
    gruen = (
        ergebnis.exit == EXIT_KEIN_TERMINAL
        and len(benannt) == 1
        and len(fehlgeschlagen) == 1
        and not traceback
    )
    grund = (
        f"exit={ergebnis.exit} (verlangt {EXIT_KEIN_TERMINAL}), benannte Zeilen="
        f"{len(benannt)} (verlangt 1), FEHLGESCHLAGEN-Zeilen={len(fehlgeschlagen)} "
        f"(verlangt 1), Traceback={'ja' if traceback else 'nein'} (verlangt nein)"
    )
    return Befund(
        f"{werkzeug.name} {' '.join(argumente)}".strip(), gruen, grund, ergebnis
    )


# ---------------------------------------------------------------------------
# Was gemessen wird
# ---------------------------------------------------------------------------
WERKZEUGE = werkzeuge_mit_main(TOOLS)


@dataclass(frozen=True)
class Terminalaufruf:
    """Ein Werkzeug, das ein Terminal braucht, mit Argumenten, die es bis zum
    Terminal kommen lassen (Datenvorbedingungen liegen in ``tmp_path``)."""

    datei: str
    kennung: str
    argumente: Callable[[Path], tuple[str, ...]]


def _csv_fuer_gegenprobe(tmp: Path) -> tuple[str, ...]:
    """``aufloesung --gegenprobe`` liest SYMBOL_ZEITRAHMEN.csv mit >= 30 Zeilen, bevor
    es das Terminal oeffnet -- die Fixture des Edge-Tests, umbenannt."""
    csv = tmp / "EURUSD_H1.csv"
    csv.write_bytes(FIXTURE_H1.read_bytes())
    return ("--gegenprobe", str(csv))


def _leeres_register(tmp: Path) -> tuple[str, ...]:
    """``ereignisstudie`` verlangt ein existierendes Register vor der ersten
    Kerzenabfrage; ein leeres ist zulaessig, angelegt wird es vom Werkzeug nie."""
    register = tmp / "TRIALS.jsonl"
    register.write_text("", encoding="utf-8")
    return ("--alle", "--register", str(register))


TERMINALAUFRUFE: tuple[Terminalaufruf, ...] = (
    Terminalaufruf("atr_messung.py", "atr_messung", lambda tmp: ()),
    Terminalaufruf("aufloesung.py", "aufloesung", lambda tmp: ()),
    Terminalaufruf("aufloesung.py", "aufloesung --gegenprobe", _csv_fuer_gegenprobe),
    Terminalaufruf("ereignisstudie.py", "ereignisstudie --alle", _leeres_register),
    Terminalaufruf(
        "live_betrieb.py",
        "live_betrieb",
        lambda tmp: ("--dauer", "0.001", "--takt", "1"),
    ),
    Terminalaufruf("live_konsole.py", "live_konsole", lambda tmp: ("--takte", "1")),
    Terminalaufruf("mt5_smoke.py", "mt5_smoke", lambda tmp: ()),
)


def _fetch_data_argumente(tmp: Path, *, ein_versuch: bool = True) -> tuple[str, ...]:
    """Ein Jahr Tageskerzen, ein Versuch: mit abgewiesenem Proxy sofort benannt rot.

    ``ein_versuch=False`` laesst ``--versuche`` weg -- der Stand vor der Aenderung
    kennt den Schalter nicht (der Beleg-Lauf braucht das; dort dauert der Fehlschlag
    dann die sechs Versuche mit Wartezeit, 42 s).
    """
    argumente = (
        "--from-year",
        "2024",
        "--to-year",
        "2024",
        "--out",
        str(tmp / "daten"),
    )
    return argumente + (("--versuche", "1") if ein_versuch else ())


# ---------------------------------------------------------------------------
# Sicherung: der Shim wirkt, bevor irgendein Werkzeug laeuft
# ---------------------------------------------------------------------------
def test_der_shim_macht_metatrader5_unsichtbar(tmp_path: Path) -> None:
    """Ohne diese Zusicherung koennte ein Unterprozess das echte Paket laden -- und
    ``MetaTrader5.initialize()`` startet unter Windows das Terminal (T3-Befund)."""
    env = shim_umgebung(tmp_path / "shim")
    ergebnis = lauf((sys.executable, "-c", "import MetaTrader5"), env=env, cwd=REPO)
    assert ergebnis.exit != 0
    assert "Shim der Eichfaelle" in ergebnis.stderr, ergebnis.stderr


# ---------------------------------------------------------------------------
# (a) A13: --help
# ---------------------------------------------------------------------------
def test_es_gibt_werkzeuge_mit_main() -> None:
    assert len(WERKZEUGE) >= 29, [w.name for w in WERKZEUGE]


@pytest.mark.parametrize("werkzeug", WERKZEUGE, ids=[w.name for w in WERKZEUGE])
def test_help_antwortet_mit_exit_0_und_usage(werkzeug: Path, tmp_path: Path) -> None:
    befund = pruefe_help(werkzeug, env=shim_umgebung(tmp_path / "shim"), cwd=REPO)
    assert befund.gruen, f"{befund.werkzeug}: {befund.grund}\n{befund.lauf.ausgabe}"


# ---------------------------------------------------------------------------
# (b) A12: ohne Terminal eine benannte Zeile, Exit 2, kein Traceback
# ---------------------------------------------------------------------------
def test_jedes_terminalwerkzeug_ist_erfasst() -> None:
    """Wer ``RealMt5Terminal`` benutzt, steht in ``TERMINALAUFRUFE`` -- sonst kaeme
    ein neues Terminalwerkzeug ohne diesen Eichfall davon."""
    benutzer = {p.name for p in TOOLS.glob("*.py") if importiert_realmt5terminal(p)}
    erfasst = {a.datei for a in TERMINALAUFRUFE}
    assert benutzer == erfasst, f"nicht erfasst: {benutzer - erfasst}"
    assert "paper_run.py" not in benutzer  # nennt die Klasse nur im Modulkopf


@pytest.mark.parametrize(
    "aufruf", TERMINALAUFRUFE, ids=[a.kennung for a in TERMINALAUFRUFE]
)
def test_ohne_terminal_eine_benannte_zeile_und_exit_2(
    aufruf: Terminalaufruf, tmp_path: Path
) -> None:
    env = shim_umgebung(tmp_path / "shim")
    befund = pruefe_benannt(
        TOOLS / aufruf.datei, aufruf.argumente(tmp_path), env=env, cwd=REPO
    )
    assert befund.gruen, f"{befund.werkzeug}: {befund.grund}\n{befund.lauf.ausgabe}"


def test_fetch_data_ohne_quelle_eine_benannte_zeile_und_exit_2(tmp_path: Path) -> None:
    env = ohne_quelle(shim_umgebung(tmp_path / "shim"))
    befund = pruefe_benannt(
        TOOLS / "fetch_data.py",
        _fetch_data_argumente(tmp_path),
        env=env,
        cwd=REPO,
        praefix=PRAEFIX_QUELLE,
    )
    assert befund.gruen, f"{befund.werkzeug}: {befund.grund}\n{befund.lauf.ausgabe}"
    assert not (tmp_path / "daten").exists(), "ohne Quelle darf nichts abgelegt werden"


# ---------------------------------------------------------------------------
# (c) Die Pruefer selbst: rot, wo sie rot sein muessen, gruen, wo gruen
# ---------------------------------------------------------------------------
def _skript(tmp: Path, name: str, quelle: str) -> Path:
    pfad = tmp / name
    pfad.write_text(quelle, encoding="utf-8")
    return pfad


def test_der_pruefer_erkennt_die_alten_fehlerbilder_als_rot(tmp_path: Path) -> None:
    """Die drei Fehlerbilder des Standes vor der Aenderung, synthetisch: Traceback
    (``live_konsole``, ``live_betrieb``), Exit 1 mit Meldung (``mt5_smoke``),
    zwei Zeilen (``atr_messung``). Jedes muss rot sein."""
    env = shim_umgebung(tmp_path / "shim")
    zeile = PRAEFIX_TERMINAL + "synthetisch"
    faelle = {
        "traceback": 'raise RuntimeError("MetaTrader5 nicht installiert")\n',
        "exit_1": f"import sys\nprint({zeile!r}, file=sys.stderr)\nsys.exit(1)\n",
        "zwei_zeilen": (
            "import sys\n"
            f"print({zeile!r}, file=sys.stderr)\n"
            f"print({zeile!r}, file=sys.stderr)\n"
            "sys.exit(2)\n"
        ),
        "stiller_exit_2": "import sys\nsys.exit(2)\n",
        "traceback_mit_exit_2": (
            "import sys, traceback\n"
            f"print({zeile!r}, file=sys.stderr)\n"
            "try:\n    raise RuntimeError('x')\nexcept RuntimeError:\n"
            "    traceback.print_exc()\n"
            "sys.exit(2)\n"
        ),
    }
    for name, quelle in faelle.items():
        befund = pruefe_benannt(
            _skript(tmp_path, f"{name}.py", quelle), (), env=env, cwd=tmp_path
        )
        assert befund.gruen is False, f"{name} haette rot sein muessen: {befund.grund}"


def test_der_pruefer_erkennt_die_verlangte_form_als_gruen(tmp_path: Path) -> None:
    env = shim_umgebung(tmp_path / "shim")
    zeile = PRAEFIX_TERMINAL + "MetaTrader5 nicht installiert (synthetisch)"
    richtig = _skript(
        tmp_path,
        "richtig.py",
        f"import sys\nprint('Kopfzeile')\nprint({zeile!r}, file=sys.stderr)\nsys.exit(2)\n",
    )
    befund = pruefe_benannt(richtig, (), env=env, cwd=tmp_path)
    assert befund.gruen is True, befund.grund


def test_der_help_pruefer_ist_rot_bei_kaputtem_hilfetext_und_gruen_bei_usage(
    tmp_path: Path,
) -> None:
    """Das Fehlerbild von ``edge_test.py`` vor der Aenderung (nacktes ``%`` im
    Hilfetext -> ``ValueError``) und das von ``betrieb_auswerten.py`` (kein
    argparse) -- beide rot; ein argparse-Werkzeug gruen."""
    env = shim_umgebung(tmp_path / "shim")
    kaputt = _skript(
        tmp_path,
        "kaputt.py",
        "import argparse\np = argparse.ArgumentParser()\n"
        "p.add_argument('--x', help='letzte 30 % von --csv')\np.parse_args()\n",
    )
    ohne_argparse = _skript(
        tmp_path,
        "ohne_argparse.py",
        "import sys\nprint('--help gibt es nicht')\nsys.exit(1)\n",
    )
    gut = _skript(
        tmp_path,
        "gut.py",
        "import argparse\np = argparse.ArgumentParser()\n"
        "p.add_argument('--x', help='letzte 30 %% von --csv')\np.parse_args()\n",
    )
    assert pruefe_help(kaputt, env=env, cwd=tmp_path).gruen is False
    assert pruefe_help(ohne_argparse, env=env, cwd=tmp_path).gruen is False
    assert pruefe_help(gut, env=env, cwd=tmp_path).gruen is True


# ---------------------------------------------------------------------------
# A9 im Smoke-Test: Katalogsymbole, Waehrungen, Serverzeitversatz (Fake-Terminal)
# ---------------------------------------------------------------------------
def _katalog_mit_fremdsymbol() -> dict[str, CatalogEntry]:
    """EURUSD und BTCUSD kennt das Fake-Terminal; GBPUSD steht nur im Katalog -- der
    Fall ``BTCUSD`` am Demoterminal dieses Rechners, nachgestellt."""
    katalog = _catalog()
    katalog["GBPUSD"] = CatalogEntry(
        AssetClass.FX_MAJOR, _fees(), _catalog()["EURUSD"].sessions
    )
    return katalog


def _venue(terminal: FakeMt5Terminal, katalog: dict[str, CatalogEntry]) -> Mt5Venue:
    return Mt5Venue(
        name="mt5-demo",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=katalog,
        risk_manager=RiskManager(),
        clock=lambda: TS,
    )


def _schritt(report: object, name: str) -> object:
    return next(s for s in report.steps if s.name == name)  # type: ignore[attr-defined]


def test_smoke_fehlendes_katalogsymbol_ist_roter_schritt_und_versatz_wird_gemessen() -> (
    None
):
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _katalog_mit_fremdsymbol()),
        symbol="EURUSD",
        now=TS,
        symbole=("EURUSD", "GBPUSD", "BTCUSD"),
    )
    namen = [s.name for s in report.steps]
    assert report.ok is False
    fehlend = _schritt(report, "symbol_GBPUSD")
    assert fehlend.ok is False  # type: ignore[attr-defined]
    assert "GBPUSD" in fehlend.detail  # type: ignore[attr-defined]
    # die uebrigen Symbole laufen weiter ...
    assert _schritt(report, "symbol_EURUSD").ok is True  # type: ignore[attr-defined]
    assert _schritt(report, "symbol_BTCUSD").ok is True  # type: ignore[attr-defined]
    assert namen.index("symbol_BTCUSD") > namen.index("symbol_GBPUSD")
    # ... und der Versatz wird trotzdem gemessen: Fake-Tick = TS, Uhr = TS -> 0 s
    versatz = _schritt(report, "serverzeitversatz")
    assert versatz.ok is True  # type: ignore[attr-defined]
    assert report.serverzeitversatz_s == 0.0
    assert namen.index("serverzeitversatz") > namen.index("symbol_BTCUSD")
    # Der Adapter-Vertrag bleibt: ``list_instruments`` nennt das fehlende Symbol als
    # ``error`` (tests/test_rauchtest_schaerfe.py) -- jetzt NACH dem Versatz.
    assert "GBPUSD" in _schritt(report, "error").detail  # type: ignore[attr-defined]
    assert namen.index("error") > namen.index("serverzeitversatz")


def test_smoke_versatz_ist_tickzeit_minus_lokale_utc_uhr() -> None:
    """+10796 s -- der am 2026-09-03 gemessene Wert der Broker-Serverzone (UTC+3),
    hier als Tick-Stempel ins Fake-Terminal gelegt. Vorzeichen: Tick minus Uhr."""
    terminal = FakeMt5Terminal(is_demo=True, jetzt=TS + timedelta(seconds=10796))
    report = run_smoke(_venue(terminal, _catalog()), symbol="EURUSD", now=TS)
    assert report.serverzeitversatz_s == 10796.0
    versatz = _schritt(report, "serverzeitversatz")
    assert versatz.detail.startswith("+10796.0 s")  # type: ignore[attr-defined]
    assert "EURUSD" in versatz.detail  # type: ignore[attr-defined]

    frueher = FakeMt5Terminal(is_demo=True, jetzt=TS - timedelta(seconds=90))
    report = run_smoke(_venue(frueher, _catalog()), symbol="EURUSD", now=TS)
    assert report.serverzeitversatz_s == -90.0


def test_smoke_versatz_ohne_tick_ist_rot_und_kein_wert() -> None:
    """Kein Tick ist kein Versatz von null: Schritt rot, Feld ``None``."""

    class _OhneTick(FakeMt5Terminal):
        def tick(self, name: str) -> Mt5Tick | None:
            return None

    report = run_smoke(
        _venue(_OhneTick(is_demo=True), _catalog()), symbol="EURUSD", now=TS
    )
    versatz = _schritt(report, "serverzeitversatz")
    assert versatz.ok is False  # type: ignore[attr-defined]
    assert "EURUSD" in versatz.detail  # type: ignore[attr-defined]
    assert report.serverzeitversatz_s is None
    assert report.ok is False


def test_smoke_versatz_kommt_vom_probesymbol_sonst_vom_ersten_aufloesbaren() -> None:
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _katalog_mit_fremdsymbol()),
        symbol="GBPUSD",  # das Probesymbol fehlt am Terminal
        now=TS,
        symbole=("GBPUSD", "BTCUSD", "EURUSD"),
    )
    versatz = _schritt(report, "serverzeitversatz")
    assert versatz.ok is True  # type: ignore[attr-defined]
    assert "Tick BTCUSD" in versatz.detail  # type: ignore[attr-defined]


def test_smoke_versatz_ohne_ein_einziges_aufloesbares_symbol_ist_rot() -> None:
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _katalog_mit_fremdsymbol()),
        symbol="GBPUSD",
        now=TS,
        symbole=("GBPUSD",),
    )
    versatz = _schritt(report, "serverzeitversatz")
    assert versatz.ok is False  # type: ignore[attr-defined]
    assert report.serverzeitversatz_s is None


def test_smoke_nennt_je_katalogsymbol_currency_profit_und_currency_margin() -> None:
    """``currency_profit`` ist das gelesene Feld (``quote_currency`` des Adapters);
    ``currency_margin`` ist ``Instrument.margin_currency`` (D3). Das Fake meldet EUR
    fuer EURUSD; ein Terminal ohne Angabe ergibt ``unbekannt``, nie einen geratenen
    Wert (Smoke-Lauf 1 am Terminal las den falschen Feldnamen: 09-smoke-lauf1.txt)."""
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _catalog()),
        symbol="EURUSD",
        now=TS,
        symbole=("EURUSD", "BTCUSD"),
    )
    eurusd = _schritt(report, "symbol_EURUSD").detail  # type: ignore[attr-defined]
    btcusd = _schritt(report, "symbol_BTCUSD").detail  # type: ignore[attr-defined]
    assert "currency_profit=USD" in eurusd
    assert "currency_profit=USD" in btcusd
    assert "currency_margin=EUR" in eurusd
    assert "currency_margin=unbekannt" not in eurusd


def test_smoke_ohne_symbole_prueft_das_probesymbol() -> None:
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _catalog()), symbol="EURUSD", now=TS
    )
    namen = [s.name for s in report.steps]
    assert "symbol_EURUSD" in namen
    assert "symbol_BTCUSD" not in namen
    assert report.ok is True


def test_smoke_versatz_ohne_gestellte_uhr_liest_die_lokale_uhr() -> None:
    """Ohne ``now`` misst die Harness gegen ``datetime.now(UTC)``: der Fake-Tick TS
    liegt Wochen zurueck, der Versatz ist also deutlich negativ -- und nicht 0."""
    vorher = datetime.now(UTC)
    report = run_smoke(
        _venue(FakeMt5Terminal(is_demo=True), _catalog()), symbol="EURUSD"
    )
    assert report.serverzeitversatz_s is not None
    assert report.serverzeitversatz_s <= (TS - vorher).total_seconds()

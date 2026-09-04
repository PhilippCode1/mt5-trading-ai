"""Eichfaelle D8 (Bewertung 3.8; Katalog A6, A18): Zustand nur mit Ort.

ROT gegen 306bbaa (belege/06-d8-rot.txt): ``RiskManager()`` ohne Zustand war
fluechtig per Vorgabe (``zustand_dauerhaft False``), ``SchwebeAkte(None)`` ebenso,
ein Positionsbuch gab es nicht, drei undokumentierte Umgebungsvariablen schalteten den
Ort, ``tools/live_betrieb.py`` baute ``RiskManager()`` und schrieb Stoppdatei und
Journale nach ``betrieb/`` im Arbeitsbaum; ``--terminal fake`` gab es nicht. GRUEN
gegen HEAD (belege/06-d8-gruen.txt).

Die Klasse, nicht der Fall (E-005): ``RiskManager``, ``SchwebeAkte``, ``Positionsbuch``
und ``Mt5Venue`` sind ohne Ort nicht konstruierbar; fluechtig heisst
``FluechtigerZustand`` / ``FluechtigeSchwebeAkte`` / ``FluechtigesPositionsbuch`` und
wird vom Betrieb abgewiesen; der Ort ist ``--zustandsordner``; Stoppdatei und Journale
liegen dort (A18); jede Ablage schreibt atomar (Nebendatei + ``os.replace``).

Der Trockenlauf unten faehrt ``tools/live_betrieb.py --terminal fake`` als Unterprozess
mit einem ``MetaTrader5``-Shim, das ``ImportError`` wirft: kein Weg fuehrt zu
``MetaTrader5.initialize()``, das unter Windows das Terminal startet.
"""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution import risiko_zustand  # noqa: E402
from mt5_trading_ai.execution.risiko_zustand import (  # noqa: E402
    DateiZustand,
    standard_zustandsordner,
)
from mt5_trading_ai.execution.risk_manager import RiskManager  # noqa: E402
from mt5_trading_ai.execution.schwebende_auftraege import SchwebeAkte  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import TS, FakeMt5Terminal, _catalog  # noqa: E402

PAKET = ROOT / "mt5_trading_ai"
TOOLS = ROOT / "tools"
VARIABLEN = (
    "MT5_RISIKO_ZUSTAND",
    "MT5_RISIKO_ZUSTAND_ORDNER",
    "MT5_SCHWEBENDE_AUFTRAEGE",
)
SHIM = (
    '"""Shim des Eichfalls: das Paket MetaTrader5 ist absichtlich unsichtbar."""\n'
    'raise ImportError("MetaTrader5 (Shim des Eichfalls): Paket absichtlich unsichtbar")\n'
)


# ---------------------------------------------------------------------------
# Nur mit Ort konstruierbar; fluechtig nur als Testtyp
# ---------------------------------------------------------------------------
def test_riskmanager_ohne_zustand_ist_nicht_konstruierbar(tmp_path: Path) -> None:
    ohne_zustand = RiskManager
    with pytest.raises(TypeError):
        ohne_zustand()  # 306bbaa: fluechtig per Vorgabe -- kein Wurf
    from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand

    fluechtig = RiskManager(zustand=FluechtigerZustand())
    assert fluechtig.zustand_dauerhaft is False
    assert fluechtig.zustandsort == "fluechtig"
    datei = tmp_path / "risikozustand.json"
    dauerhaft = RiskManager(zustand=DateiZustand(datei))
    assert dauerhaft.zustand_dauerhaft is True
    assert dauerhaft.zustandsort == str(datei)


def test_schwebeakte_ohne_pfad_ist_nicht_konstruierbar(tmp_path: Path) -> None:
    ohne_pfad = SchwebeAkte
    with pytest.raises(ValueError):
        ohne_pfad(None)  # 306bbaa: fluechtige Akte -- kein Wurf
    from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte

    assert FluechtigeSchwebeAkte().dauerhaft is False
    assert SchwebeAkte(tmp_path / "a.json").dauerhaft is True


def test_positionsbuch_persistiert_sieben_felder_atomar(tmp_path: Path) -> None:
    from mt5_trading_ai.execution.reconcile import (
        Buchposition,
        FluechtigesPositionsbuch,
        Positionsbuch,
    )

    pfad = tmp_path / "positionsbuch.json"
    position = Buchposition(
        kennung="open-EURUSD-1",
        ticket="4711",
        symbol="EURUSD",
        richtung="kauf",
        menge=Decimal("0.02"),
        eroeffnet_am=TS,
        stop=Decimal("1.09000"),
    )
    Positionsbuch(pfad).eintragen(position)

    assert Positionsbuch(pfad).laden() == (
        position,
    )  # ein neuer Prozess liest dasselbe
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    assert set(roh["positionen"][0]) == {
        "kennung",
        "ticket",
        "symbol",
        "richtung",
        "menge",
        "eroeffnet_am",
        "stop",
    }
    assert not list(tmp_path.glob("*.neu")), "die Nebendatei blieb liegen"
    ohne_pfad = Positionsbuch
    with pytest.raises(ValueError):
        ohne_pfad(None)  # type: ignore[arg-type]
    assert FluechtigesPositionsbuch().dauerhaft is False
    assert Positionsbuch(pfad).austragen("open-EURUSD-1") == position
    assert Positionsbuch(pfad).laden() == ()


def _order(cid: str) -> OrderRequest:
    return OrderRequest(
        cid, "EURUSD", OrderSide.BUY, OrderType.MARKET, Decimal("0.01"), Decimal("1.09")
    )


def test_venue_ohne_ablage_ist_nicht_konstruierbar(tmp_path: Path) -> None:
    rm = RiskManager(zustand=DateiZustand(tmp_path / "risikozustand.json"))
    with pytest.raises(ValueError):
        Mt5Venue(
            name="t",
            terminal=FakeMt5Terminal(is_demo=True),  # type: ignore[arg-type]
            catalog=_catalog(),
            risk_manager=rm,
            clock=lambda: TS,
        )  # 306bbaa: fluechtige Akte per Vorgabe -- kein Wurf


def test_venue_bucht_die_eigene_eroeffnung_in_den_zustandsordner(
    tmp_path: Path,
) -> None:
    rm = RiskManager(zustand=DateiZustand(tmp_path / "risikozustand.json"))
    venue = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=rm,
        clock=lambda: TS,
        zustandsordner=tmp_path,
    )
    venue.connect()
    venue.adopt_book()
    assert venue.zustand_dauerhaft is True

    ergebnis = venue.submit_order(_order("open-EURUSD-buch"))

    assert ergebnis.accepted is True
    buch = json.loads((tmp_path / "positionsbuch.json").read_text(encoding="utf-8"))
    assert [p["kennung"] for p in buch["positionen"]] == ["open-EURUSD-buch"]
    eintrag = buch["positionen"][0]
    assert eintrag["ticket"] == "V-1"
    assert eintrag["symbol"] == "EURUSD"
    assert eintrag["richtung"] == "kauf"
    assert Decimal(eintrag["menge"]) == Decimal("0.01")
    assert Decimal(eintrag["stop"]) == Decimal("1.09")
    assert not list(tmp_path.glob("*.neu"))


# ---------------------------------------------------------------------------
# Keine Umgebungsvariable schaltet den Ort
# ---------------------------------------------------------------------------
def test_keine_umgebungsvariable_schaltet_den_ort(tmp_path: Path) -> None:
    for name in ("UMGEBUNG_ZUSTANDSDATEI", "UMGEBUNG_ZUSTANDSORDNER"):
        assert not hasattr(risiko_zustand, name), f"{name} existiert noch"
    from mt5_trading_ai.execution import schwebende_auftraege

    assert not hasattr(schwebende_auftraege, "UMGEBUNG_SCHWEBEDATEI")
    lesestellen = []
    for datei in [*PAKET.rglob("*.py"), *TOOLS.glob("*.py")]:
        if "__pycache__" in datei.parts:
            continue
        for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            # Ein Zugriff, kein Prosa-Verweis: ``environ[``, ``environ.get(``, ``getenv(``.
            zugriff = re.search(r"environ\s*(\[|\.get\s*\()|getenv\s*\(", zeile)
            if zugriff and any(v in zeile for v in VARIABLEN):
                lesestellen.append(f"{datei.relative_to(ROOT).as_posix()}:{nr}")
    assert lesestellen == [], lesestellen
    # Und zur Laufzeit: die frueheren Betreibervariablen bewegen den Ort nicht mehr.
    umgebung = {
        "MT5_RISIKO_ZUSTAND_ORDNER": str(tmp_path),
        "LOCALAPPDATA": str(tmp_path / "lokal"),
        "XDG_STATE_HOME": str(tmp_path / "xdg"),
    }
    for windows in (True, False):
        ordner = standard_zustandsordner(umgebung=umgebung, ist_windows=windows)
        assert ordner != tmp_path, "MT5_RISIKO_ZUSTAND_ORDNER wird noch gelesen"


# ---------------------------------------------------------------------------
# Der Betrieb weist fluechtigen Zustand ab; Stoppdatei und Journale liegen im Ordner
# ---------------------------------------------------------------------------
def test_live_betrieb_weist_fluechtigen_zustand_ab(tmp_path: Path) -> None:
    from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch
    from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand
    from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte
    from tools.live_betrieb import zustand_abweisen

    fluechtig = RiskManager(zustand=FluechtigerZustand())
    venue_fluechtig = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=fluechtig,
        clock=lambda: TS,
        schwebeakte=FluechtigeSchwebeAkte(),
        positionsbuch=FluechtigesPositionsbuch(),
    )
    grund = zustand_abweisen(fluechtig, venue_fluechtig)
    assert grund is not None and "fluechtig" in grund

    dauerhaft = RiskManager(zustand=DateiZustand(tmp_path / "risikozustand.json"))
    venue_dauerhaft = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=dauerhaft,
        clock=lambda: TS,
        zustandsordner=tmp_path,
    )
    assert zustand_abweisen(dauerhaft, venue_dauerhaft) is None
    # Auch eine gemischte Lage wird abgewiesen: nur die Akte fluechtig.
    gemischt = Mt5Venue(
        name="t",
        terminal=FakeMt5Terminal(is_demo=True),  # type: ignore[arg-type]
        catalog=_catalog(),
        risk_manager=dauerhaft,
        clock=lambda: TS,
        zustandsordner=tmp_path,
        schwebeakte=FluechtigeSchwebeAkte(),
    )
    assert zustand_abweisen(dauerhaft, gemischt) is not None


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--porcelain", "--ignored", "--untracked-files=all"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=120,
    ).stdout


def _shim_umgebung(ordner: Path) -> dict[str, str]:
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "MetaTrader5.py").write_text(SHIM, encoding="utf-8")
    env = dict(os.environ)
    pfade = [str(ordner)]
    if env.get("PYTHONPATH"):
        pfade.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pfade)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def test_trockenlauf_gegen_das_fake_terminal_laesst_den_arbeitsbaum_unveraendert(
    tmp_path: Path,
) -> None:
    """A18: Stoppdatei, Journal und Risikozustand entstehen im Zustandsordner; der
    Arbeitsbaum ist vor und nach dem Lauf byteweise derselbe (``git status``)."""
    from tools import live_betrieb

    assert not hasattr(live_betrieb, "STOPPDATEI"), "Stoppdatei fest im Arbeitsbaum"
    assert not hasattr(live_betrieb, "JOURNALE"), "Journale fest im Arbeitsbaum"
    zustand = tmp_path / "zustand"
    env = _shim_umgebung(tmp_path / "shim")
    vorher = _git_status()

    lauf = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "live_betrieb.py"),
            "--terminal",
            "fake",
            "--zustandsordner",
            str(zustand),
            "--dauer",
            "0.0003",
            "--takt",
            "1",
            "--symbol",
            "EURUSD",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(ROOT),
        timeout=180,
    )

    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Traceback" not in lauf.stdout + lauf.stderr
    assert "TROCKEN" in lauf.stdout
    assert _git_status() == vorher, "der Lauf hat den Arbeitsbaum veraendert"
    journale = sorted(
        (zustand / risiko_zustand.JOURNALORDNER_NAME).glob("journal-*.jsonl")
    )
    assert len(journale) == 1, journale
    saetze = [
        json.loads(z)
        for z in journale[0].read_text(encoding="utf-8").splitlines()
        if z.strip()
    ]
    arten = [s["art"] for s in saetze]
    assert arten[0] == "start" and "startabgleich" in arten and "ende" in arten, arten
    start = saetze[0]
    assert start["terminal"] == "fake"
    assert start["scharf"] is False and start["demo_schreiben"] is False
    assert start["zulassung"]["gueltig"] is False
    assert (zustand / risiko_zustand.RISIKOZUSTAND_DATEI).is_file()
    assert not (zustand / risiko_zustand.STOPPDATEI_NAME).exists()
    assert not list(zustand.rglob("*.neu"))
    ende = next(s for s in saetze if s["art"] == "ende")
    assert ende["takte"] >= 1 and ende["offen_geblieben"] == []


def test_die_stoppdatei_beendet_den_lauf_aus_dem_zustandsordner(tmp_path: Path) -> None:
    """Eine vor dem Start angelegte Stoppdatei wird entfernt (sonst endete jeder Lauf
    sofort); die Auskunft, wo sie liegt, nennt den Zustandsordner."""
    zustand = tmp_path / "zustand"
    zustand.mkdir()
    (zustand / risiko_zustand.STOPPDATEI_NAME).write_text("", encoding="utf-8")
    lauf = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "live_betrieb.py"),
            "--terminal",
            "fake",
            "--zustandsordner",
            str(zustand),
            "--dauer",
            "0.0003",
            "--takt",
            "1",
            "--symbol",
            "EURUSD",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_shim_umgebung(tmp_path / "shim"),
        cwd=str(ROOT),
        timeout=180,
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert str(zustand / risiko_zustand.STOPPDATEI_NAME) in lauf.stdout
    assert not (zustand / risiko_zustand.STOPPDATEI_NAME).exists()
    # Der Lauf hat wirklich getaktet, die Stoppdatei ihn also nicht sofort beendet.
    journale = sorted((zustand / risiko_zustand.JOURNALORDNER_NAME).glob("*.jsonl"))
    assert len(journale) == 1
    assert '"art": "takt"' in journale[0].read_text(encoding="utf-8")


def test_das_fake_terminal_importiert_kein_metatrader5() -> None:
    from mt5_trading_ai.venue import fake

    quelle = Path(inspect.getsourcefile(fake) or "").read_text(encoding="utf-8")
    assert "import MetaTrader5" not in quelle
    assert "import_module" not in quelle
    attrappe = fake.FakeMt5Terminal()
    assert attrappe.initialize() is True
    assert attrappe.account().is_demo is True
    assert attrappe.symbol("EURUSD") is not None

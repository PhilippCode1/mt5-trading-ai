"""Eichfaelle Z (Bewertung 3.5, E-010): Zulassung und Schreibrecht sind zwei Dinge.

ROT gegen 306bbaa (belege/06-z-rot.txt): ``--scharf "<Text>"`` setzte zugleich
``allow_write`` und ``CriteriaVerdict(passed=True)`` -- ein Freitext ersetzte das
Zulassungstor (15 von 21 Demolaeufen); die vier Live-Schalter kamen aus einem
``settings``-Objekt, das nie jemand uebergab. GRUEN gegen HEAD (belege/06-z-gruen.txt).

Die Klasse, nicht der Fall: ``--scharf`` ist kein Argument mehr (argparse, Exit 2);
``--demo-schreiben`` setzt nur ``allow_write`` (``require_demo`` bleibt ``True``);
``--zulassung <datei>`` verlangt einen vollstaendigen Registereintrag; die Schalter der
Live-Freigabe liest ``release.lies_live_freigabe`` aus ``config/live_freigabe.json``
(fehlende Datei/Schluessel = nicht freigegeben), und ``Mt5Venue`` nimmt nur noch einen
Dateipfad (``freigabedatei=``).

Der ``--scharf``-Lauf ist ein Unterprozess mit ``MetaTrader5``-Shim: gegen 306bbaa kaeme
das Argument durch und ``RealMt5Terminal.initialize()`` wuerde gerufen -- mit dem Shim
endet das in ``ImportError``, nie im Start des Terminals.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_trading_ai.execution import release as release_modul  # noqa: E402
from mt5_trading_ai.execution.release import (  # noqa: E402
    RELEASE_ID_FIELD,
    REQUIRED_SWITCHES,
    evaluate_live_release,
)
from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.execution.risk_manager import RiskManager, RiskPolicy  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    OrderRejectedError,
    OrderRequest,
    OrderSide,
    OrderType,
)

from test_mt5_venue import (  # noqa: E402
    _LENIENT_COST_GATE,
    TS,
    FakeMt5Terminal,
    _bestandener_edge,
    _catalog,
    _reifer_demo_beleg,
)

TOOLS = ROOT / "tools"
FREIGABEDATEI = ROOT / "config" / "live_freigabe.json"
SCHALTER = [attribut for attribut, _ in REQUIRED_SWITCHES]


def lies_live_freigabe(pfad: Path | None = None) -> Any:
    """Die Lesefunktion des Standes -- gegen 306bbaa gibt es sie nicht: dort faellt
    jeder Freigabe-Fall an dieser Zusicherung, nicht am Sammeln."""
    lesen = getattr(release_modul, "lies_live_freigabe", None)
    assert lesen is not None, "release.lies_live_freigabe fehlt -- keine Datei-Freigabe"
    return lesen(pfad)


SHIM = (
    '"""Shim des Eichfalls: das Paket MetaTrader5 ist absichtlich unsichtbar."""\n'
    'raise ImportError("MetaTrader5 (Shim des Eichfalls): Paket absichtlich unsichtbar")\n'
)


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


def _live_betrieb(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOLS / "live_betrieb.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_shim_umgebung(tmp_path / "shim"),
        cwd=str(ROOT),
        timeout=180,
    )


# ---------------------------------------------------------------------------
# --scharf entfaellt
# ---------------------------------------------------------------------------
def test_scharf_ist_kein_argument_mehr(tmp_path: Path) -> None:
    lauf = _live_betrieb(
        ["--scharf", "Maschinenprobe", "--dauer", "0.0003", "--takt", "1"], tmp_path
    )
    assert lauf.returncode == 2, lauf.stdout + lauf.stderr
    assert "usage" in lauf.stderr
    assert "--scharf" in lauf.stderr
    assert "Traceback" not in lauf.stdout + lauf.stderr


def test_die_hilfe_kennt_schreibrecht_und_zulassung_aber_keine_freigabe(
    tmp_path: Path,
) -> None:
    hilfe = _live_betrieb(["--help"], tmp_path)
    assert hilfe.returncode == 0
    assert "--demo-schreiben" in hilfe.stdout
    assert "--zulassung" in hilfe.stdout
    assert "--zustandsordner" in hilfe.stdout
    assert "--scharf" not in hilfe.stdout
    assert "freigabe" not in hilfe.stdout.lower(), "die Live-Freigabe ist kein Argument"


# ---------------------------------------------------------------------------
# --demo-schreiben setzt nur allow_write; require_demo bleibt
# ---------------------------------------------------------------------------
def test_demo_schreiben_setzt_nur_das_schreibrecht() -> None:
    from mt5_trading_ai.venue.fake import FakeMt5Terminal as Attrappe
    from tools.live_betrieb import _terminal_bauen

    # Der Konstruktor von RealMt5Terminal importiert MetaTrader5 nicht; initialize()
    # wird hier nie gerufen.
    mit = _terminal_bauen("real", darf_schreiben=True)
    ohne = _terminal_bauen("real", darf_schreiben=False)
    assert isinstance(mit, RealMt5Terminal) and isinstance(ohne, RealMt5Terminal)
    assert mit._allow_write is True
    assert ohne._allow_write is False
    assert mit._require_demo is True and ohne._require_demo is True
    assert isinstance(_terminal_bauen("fake", darf_schreiben=True), Attrappe)


# ---------------------------------------------------------------------------
# --zulassung: nur ein vollstaendiger Registereintrag laesst zu
# ---------------------------------------------------------------------------
def _eintrag(tmp_path: Path, **felder: str) -> Path:
    datei = tmp_path / "zulassung.json"
    datei.write_text(json.dumps(felder), encoding="utf-8")
    return datei


def test_zulassung_kommt_nur_aus_einem_vollstaendigen_registereintrag(
    tmp_path: Path,
) -> None:
    from tools.live_betrieb import ZULASSUNGSFELDER, zulassung_lesen

    assert zulassung_lesen(None).urteil.passed is False
    fehlt = zulassung_lesen(tmp_path / "fehlt.json")
    assert fehlt.urteil.passed is False
    assert fehlt.befund["mangel"] == "zulassungsdatei_fehlt"

    vollstaendig = {
        "strategie": "moving_average_crossover(12,26)",
        "torurteil_hash": "sha256:0f9d8dcf",
        "datum": "2026-09-04",
        "kennung": "reg-2026-09-04-01",
    }
    assert tuple(vollstaendig) == ZULASSUNGSFELDER
    for feld in ZULASSUNGSFELDER:
        ohne = {k: v for k, v in vollstaendig.items() if k != feld}
        befund = zulassung_lesen(_eintrag(tmp_path, **ohne))
        assert befund.urteil.passed is False, feld
        assert befund.befund["mangel"] == f"zulassung_unvollstaendig: {feld}"
        leer = dict(vollstaendig, **{feld: "   "})
        assert zulassung_lesen(_eintrag(tmp_path, **leer)).urteil.passed is False, feld
    kein_objekt = tmp_path / "liste.json"
    kein_objekt.write_text("[1, 2]", encoding="utf-8")
    assert zulassung_lesen(kein_objekt).urteil.passed is False

    zugelassen = zulassung_lesen(_eintrag(tmp_path, **vollstaendig))
    assert zugelassen.urteil.passed is True
    assert zugelassen.befund["gueltig"] is True
    assert zugelassen.befund["kennung"] == "reg-2026-09-04-01"


# ---------------------------------------------------------------------------
# Die Live-Freigabe kommt aus der Datei -- fail-closed
# ---------------------------------------------------------------------------
def _freigabe(tmp_path: Path, **werte: object) -> Path:
    daten: dict[str, object] = {s: True for s in SCHALTER}
    daten[RELEASE_ID_FIELD[0]] = "2026-09-04/eurusd/v1"
    daten.update(werte)
    datei = tmp_path / "live_freigabe_test.json"
    datei.write_text(json.dumps(daten), encoding="utf-8")
    return datei


def test_die_eingecheckte_freigabedatei_hat_alle_schalter_aus() -> None:
    roh = json.loads(FREIGABEDATEI.read_text(encoding="utf-8"))
    assert [roh[s] for s in SCHALTER] == [False, False, False, False]
    assert roh[RELEASE_ID_FIELD[0]] == ""
    gelesen = lies_live_freigabe()
    assert gelesen.quelle == str(FREIGABEDATEI)
    assert evaluate_live_release(gelesen).allowed is False


def test_fehlende_datei_oder_schluessel_heisst_nicht_freigegeben(
    tmp_path: Path,
) -> None:
    fehlt = lies_live_freigabe(tmp_path / "fehlt.json")
    assert fehlt.mangel == "freigabedatei_fehlt"
    assert evaluate_live_release(fehlt).allowed is False
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{kein json", encoding="utf-8")
    assert evaluate_live_release(lies_live_freigabe(kaputt)).allowed is False
    for schalter in SCHALTER:
        datei = _freigabe(tmp_path)
        daten = json.loads(datei.read_text(encoding="utf-8"))
        del daten[schalter]
        datei.write_text(json.dumps(daten), encoding="utf-8")
        assert evaluate_live_release(lies_live_freigabe(datei)).allowed is False, (
            schalter
        )
    # "true" als Text ist nicht true.
    assert (
        evaluate_live_release(
            lies_live_freigabe(_freigabe(tmp_path, live_release_owner_ack="true"))
        ).allowed
        is False
    )
    assert (
        evaluate_live_release(lies_live_freigabe(_freigabe(tmp_path))).allowed is True
    )


def _order() -> OrderRequest:
    return OrderRequest(
        "z-1",
        "EURUSD",
        OrderSide.BUY,
        OrderType.MARKET,
        Decimal("0.01"),
        Decimal("1.09"),
    )


def _live_venue(
    tmp_path: Path, freigabedatei: Path | None
) -> tuple[Mt5Venue, FakeMt5Terminal]:
    terminal = FakeMt5Terminal(is_demo=False)
    venue = Mt5Venue(
        name="mt5-live",
        terminal=terminal,  # type: ignore[arg-type]
        catalog=_catalog(),
        freigabedatei=freigabedatei,
        cost_gate=_LENIENT_COST_GATE,
        risk_manager=RiskManager(
            RiskPolicy(risk_fraction=Decimal("0.005")),
            zustand=DateiZustand(tmp_path / "risikozustand.json"),
        ),
        demo_registration=_reifer_demo_beleg(),
        demo_live_verdict=_bestandener_edge(),
        clock=lambda: TS,
        zustandsordner=tmp_path,
    )
    venue.connect()
    return venue, terminal


def test_eroeffnung_am_livekonto_mit_eingecheckter_datei_gesperrt(
    tmp_path: Path,
) -> None:
    venue, terminal = _live_venue(tmp_path, None)  # Vorgabe: config/live_freigabe.json
    with pytest.raises(OrderRejectedError) as ex:
        venue.submit_order(_order())
    assert ex.value.reason == "live_release_incomplete"
    assert terminal.order_send_calls == 0


def test_eroeffnung_am_livekonto_mit_testdatei_nicht_gesperrt(tmp_path: Path) -> None:
    venue, terminal = _live_venue(tmp_path, _freigabe(tmp_path))
    ergebnis = venue.submit_order(_order())
    assert ergebnis.accepted is True
    assert terminal.order_send_calls == 1

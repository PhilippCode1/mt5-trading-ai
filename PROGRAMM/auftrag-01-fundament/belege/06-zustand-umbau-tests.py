"""T6, Familie Zustand und Halt (D8, E-005): der Testumbau als nachvollziehbares Skript.

Seit D8 sind ``RiskManager``, ``SchwebeAkte``, ``Positionsbuch`` und ``Mt5Venue`` ohne
Zustandsort nicht konstruierbar; die drei Umgebungsvariablen sind entfallen; die
Live-Freigabe kommt aus einer Datei (Z, E-010); ``run_signal`` sendet nur mit
``darf_schreiben=True`` (D1). Dieses Skript zieht die bestehenden Tests nach -- so wenig
wie noetig, mechanisch und gezaehlt:

  (a) jede ``RiskManager(...)`` ohne ``zustand=`` bekommt ``zustand=FluechtigerZustand()``
      (in ``test_risikozustand_eichfaelle.py``: ``DateiZustand`` in ``tmp_path``, wo
      der Test vorher die Umgebungsvariable setzte);
  (b) jede ``Mt5Venue(...)`` ohne Zustandsordner bekommt die fluechtigen Testtypen
      (``FluechtigeSchwebeAkte``, ``FluechtigesPositionsbuch``);
  (c) ``settings=`` wird zu ``freigabedatei=`` mit einer Datei in ``tmp_path``;
  (d) Tests der Umgebungsvariablen pruefen jetzt ``zustandsordner_pruefen``;
  (e) die Attrappen von ``tools/live_betrieb.py`` bekommen ``halt_grund_loesen`` (D4);
  (f) Aufrufer von ``run_signal``/``build_paper_venue``/``run_paper`` nennen
      Schreibrecht und Zustandsordner.

Aufruf im Worktree:  python PROGRAMM/auftrag-01-fundament/belege/06-zustand-umbau-tests.py
Danach: ruff check --select I,F401 --fix tests ; ruff format tests
(Importe sortieren, zwei unbenutzt gewordene Importe in test_paper_runner.py entfernen).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TESTS = REPO / "tests"

IMPORTE = {
    "FluechtigerZustand": "from mt5_trading_ai.execution.risiko_zustand import FluechtigerZustand\n",
    "FluechtigeSchwebeAkte": "from mt5_trading_ai.execution.schwebende_auftraege import FluechtigeSchwebeAkte\n",
    "FluechtigesPositionsbuch": "from mt5_trading_ai.execution.reconcile import FluechtigesPositionsbuch\n",
    "DateiZustand": "from mt5_trading_ai.execution.risiko_zustand import DateiZustand\n",
    "zustandsordner_pruefen": "from mt5_trading_ai.execution.risiko_zustand import zustandsordner_pruefen\n",
}

ZAEHLUNG: dict[str, int] = {}


def zaehle(schluessel: str, n: int = 1) -> None:
    ZAEHLUNG[schluessel] = ZAEHLUNG.get(schluessel, 0) + n


def schliessende_klammer(s: str, i: int) -> int:
    """Index der Klammer, die ``s[i] == '('`` schliesst -- Strings werden uebersprungen."""
    tiefe = 0
    j = i
    in_str: str | None = None
    while j < len(s):
        c = s[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
        elif c == "(":
            tiefe += 1
        elif c == ")":
            tiefe -= 1
            if tiefe == 0:
                return j
        j += 1
    raise ValueError("Klammer nicht geschlossen")


def mit_argument(s: str, name: str, kw: str, *, ueberspringe: tuple[str, ...]) -> tuple[str, int]:
    """Haenge ``kw`` an jeden Aufruf ``name(...)``, der keines der Woerter enthaelt."""
    muster = re.compile(r"(?<![\w.])" + re.escape(name) + r"\(")
    aus: list[str] = []
    pos = 0
    n = 0
    for m in muster.finditer(s):
        if m.start() < pos:
            continue
        vor = s[max(0, m.start() - 6) : m.start()]
        if vor.endswith("def ") or vor.endswith("class "):
            continue
        auf = m.end() - 1
        zu = schliessende_klammer(s, auf)
        innen = s[auf + 1 : zu]
        if any(w in innen for w in ueberspringe):
            continue
        kern = innen.rstrip()
        if not kern.strip():
            neu = kw
        elif kern.endswith(","):
            neu = kern + " " + kw + "," + innen[len(kern) :]
        else:
            neu = innen + ", " + kw
        aus.append(s[pos : auf + 1])
        aus.append(neu)
        pos = zu
        n += 1
    aus.append(s[pos:])
    return "".join(aus), n


def import_sichern(s: str, name: str) -> str:
    zeile = IMPORTE[name]
    if name not in s or re.search(r"import[^\n]*\b" + name + r"\b", s):
        return s
    for anker in ("\nfrom mt5_trading_ai.", "\nimport pytest\n", "\nfrom pathlib import Path\n"):
        i = s.find(anker)
        if i >= 0:
            return s[: i + 1] + zeile + s[i + 1 :]
    raise ValueError(f"kein Importanker fuer {name}")


def tmp_path_sichern(s: str, stelle: int) -> str:
    """Die umschliessende ``def`` von ``stelle`` bekommt ``tmp_path: Path``."""
    i = s.rfind("\ndef ", 0, stelle)
    auf = s.index("(", i)
    zu = schliessende_klammer(s, auf)
    params = s[auf + 1 : zu]
    if re.search(r"\btmp_path\b", params):
        return s
    if not params.strip():
        neu = "tmp_path: Path"
    elif "*" in params.split(",")[0] or params.lstrip().startswith("*"):
        neu = "tmp_path: Path, " + params.lstrip()
    else:
        neu = "tmp_path: Path, " + params.lstrip()
    zaehle("tmp_path-Parameter")
    return s[: auf + 1] + neu + s[zu:]


def tmp_path_fuer_alle(s: str, muster: str) -> str:
    """Jede Fundstelle von ``muster`` liegt in einer ``def`` mit ``tmp_path``."""
    for m in list(re.finditer(re.escape(muster), s))[::-1]:
        s = tmp_path_sichern(s, m.start())
    return s


def ersetze(s: str, alt: str, neu: str, *, datei: str, genau: int = 1) -> str:
    n = s.count(alt)
    assert n == genau, f"{datei}: Anker {n}x statt {genau}x: {alt[:70]!r}"
    zaehle(f"gezielt: {datei}", n)
    return s.replace(alt, neu)


def lese(name: str) -> str:
    return (TESTS / name).read_text(encoding="utf-8")


def schreibe(name: str, s: str) -> None:
    (TESTS / name).write_text(s, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# (a)+(b) mechanisch ueber alle Testdateien
# ---------------------------------------------------------------------------
BESONDERS = {"test_risikozustand_eichfaelle.py", "test_risiko_zustand.py"}


def mechanisch(name: str, s: str) -> str:
    if name not in BESONDERS:
        s, n = mit_argument(
            s, "RiskManager", "zustand=FluechtigerZustand()", ueberspringe=("zustand=",)
        )
        if n:
            zaehle(f"RiskManager: {name}", n)
            s = import_sichern(s, "FluechtigerZustand")
    # Mt5Venue: erst die Faelle mit Akte, aber ohne Buch ...
    s, n1 = mit_argument(
        s,
        "Mt5Venue",
        "positionsbuch=FluechtigesPositionsbuch()",
        ueberspringe=("zustandsordner=", "positionsbuch="),
    )
    # ... dann alle ohne beides (die eben ergaenzten tragen jetzt ein Buch).
    s, n2 = mit_argument(
        s,
        "Mt5Venue",
        "schwebeakte=FluechtigeSchwebeAkte()",
        ueberspringe=("zustandsordner=", "schwebeakte="),
    )
    if n1 or n2:
        zaehle(f"Mt5Venue: {name}", n1)
        s = import_sichern(s, "FluechtigesPositionsbuch")
        if n2:
            s = import_sichern(s, "FluechtigeSchwebeAkte")
    return s


# ---------------------------------------------------------------------------
# (c) Live-Freigabe aus einer Datei
# ---------------------------------------------------------------------------
FREIGABE_DEF = '''def _released_settings() -> SimpleNamespace:
    return SimpleNamespace(
        live_release_owner_ack=True,
        live_release_strategy_approved=True,
        live_release_risk_limits_configured=True,
        live_release_venue_demo_verified=True,
        live_release_id="2026-08-11/eurusd/v1",
    )
'''
FREIGABE_NEU = '''def _freigabedatei(tmp_path: Path) -> Path:
    """Eine Live-Freigabe mit allen vier Schaltern und Kennung -- als Datei in
    ``tmp_path``, weil ``Mt5Venue`` die Schalter nur noch aus einer Datei liest
    (Z, E-010; ``execution/release.py::lies_live_freigabe``). Die eingecheckte
    ``config/live_freigabe.json`` hat alle Schalter aus."""
    datei = tmp_path / "live_freigabe_test.json"
    datei.write_text(
        json.dumps(
            {
                "live_release_owner_ack": True,
                "live_release_strategy_approved": True,
                "live_release_risk_limits_configured": True,
                "live_release_venue_demo_verified": True,
                "live_release_id": "2026-08-11/eurusd/v1",
            }
        ),
        encoding="utf-8",
    )
    return datei
'''


def test_mt5_venue(s: str) -> str:
    d = "test_mt5_venue.py"
    s = ersetze(s, FREIGABE_DEF, FREIGABE_NEU, datei=d)
    s = ersetze(s, "    settings: object = None,\n", "    freigabedatei: Path | None = None,\n", datei=d)
    s = ersetze(s, "        settings=settings,\n", "        freigabedatei=freigabedatei,\n", datei=d)
    s = ersetze(
        s,
        "        schwebeakte=schwebeakte,\n",
        "        schwebeakte=(\n"
        "            schwebeakte if schwebeakte is not None else FluechtigeSchwebeAkte()\n"
        "        ),\n",
        datei=d,
    )
    s = ersetze(s, ", settings=None)", ")", datei=d, genau=3)
    s = ersetze(s, "        settings=None,\n", "", datei=d)
    s = ersetze(s, "        settings=None,  # keine Freigabe\n", "", datei=d)
    # _live_risk_venue reicht tmp_path durch -- ZUERST, damit der generische Schritt
    # danach den Parameter nicht an den Anfang setzt.
    s = ersetze(
        s,
        "def _live_risk_venue(\n    risk_manager: RiskManager, *, positions: tuple[Mt5Position, ...] = ()\n)",
        "def _live_risk_venue(\n    risk_manager: RiskManager,\n    tmp_path: Path,\n    *,\n    positions: tuple[Mt5Position, ...] = (),\n)",
        datei=d,
    )
    n = s.count("settings=_released_settings()")
    s = s.replace("settings=_released_settings()", "freigabedatei=_freigabedatei(tmp_path)")
    zaehle(f"freigabedatei: {d}", n)
    s = tmp_path_fuer_alle(s, "freigabedatei=_freigabedatei(tmp_path)")
    muster = re.compile(r"(?<![\w.])_live_risk_venue\(")
    aus: list[str] = []
    pos = 0
    for m in muster.finditer(s):
        vor = s[max(0, m.start() - 4) : m.start()]
        if vor.endswith("def "):
            continue
        auf = m.end() - 1
        zu = schliessende_klammer(s, auf)
        aus.append(s[pos:zu])
        aus.append(", tmp_path")
        pos = zu
        zaehle(f"_live_risk_venue: {d}")
    aus.append(s[pos:])
    s = "".join(aus)
    s = tmp_path_fuer_alle(s, "_live_risk_venue(")
    s = s.replace("from types import SimpleNamespace\n", "")
    s = s.replace("import inspect\n", "import inspect\nimport json\nfrom pathlib import Path\n")
    return import_sichern(s, "FluechtigeSchwebeAkte")


def demo_beleg_grenze(s: str) -> str:
    d = "test_demo_beleg_grenze.py"
    s = ersetze(s, "    _released_settings,\n", "    _freigabedatei,\n", datei=d)
    s = ersetze(
        s,
        "def _live_venue(beleg: Any) -> tuple[Mt5Venue, FakeMt5Terminal]:",
        "def _live_venue(beleg: Any, tmp_path: Path) -> tuple[Mt5Venue, FakeMt5Terminal]:",
        datei=d,
    )
    s = ersetze(s, "        settings=_released_settings(),\n", "        freigabedatei=_freigabedatei(tmp_path),\n", datei=d)
    muster = re.compile(r"(?<![\w.])_live_venue\(")
    aus: list[str] = []
    pos = 0
    for m in muster.finditer(s):
        if s[max(0, m.start() - 4) : m.start()].endswith("def "):
            continue
        auf = m.end() - 1
        zu = schliessende_klammer(s, auf)
        aus.append(s[pos:zu])
        aus.append(", tmp_path")
        pos = zu
        zaehle(f"_live_venue: {d}")
    aus.append(s[pos:])
    s = "".join(aus)
    s = tmp_path_fuer_alle(s, ", tmp_path)")
    s = s.replace("from decimal import Decimal\n", "from decimal import Decimal\nfrom pathlib import Path\n", 1)
    return s


def demo_tor_eichfall(s: str) -> str:
    d = "test_demo_tor_eichfall.py"
    s = ersetze(s, "    _released_settings,\n", "    _freigabedatei,\n", datei=d)
    s = ersetze(
        s,
        "def _live_venue(**demo_argumente: Any) -> tuple[Mt5Venue, FakeMt5Terminal]:",
        "def _live_venue(\n    tmp_path: Path, **demo_argumente: Any\n) -> tuple[Mt5Venue, FakeMt5Terminal]:",
        datei=d,
    )
    s = ersetze(
        s,
        "        settings=_released_settings(),  # Live-Freigabe vollstaendig\n",
        "        freigabedatei=_freigabedatei(tmp_path),  # Live-Freigabe vollstaendig\n",
        datei=d,
    )
    n = len(re.findall(r"= _live_venue\(", s))
    s = re.sub(r"= _live_venue\(", "= _live_venue(tmp_path, ", s)
    zaehle(f"_live_venue: {d}", n)
    s = tmp_path_fuer_alle(s, "= _live_venue(tmp_path, ")
    s = s.replace("from decimal import Decimal\n", "from decimal import Decimal\nfrom pathlib import Path\n", 1)
    return s


# ---------------------------------------------------------------------------
# (d) Die Tests der Umgebungsvariablen
# ---------------------------------------------------------------------------
def risiko_zustand(s: str) -> str:
    d = "test_risiko_zustand.py"
    s = ersetze(
        s,
        '    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)\n'
        '    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)\n'
        "\n"
        "    pfad = standard_zustandsdatei()\n",
        "    pfad = standard_zustandsdatei()\n",
        datei=d,
    )
    s = ersetze(
        s,
        '''def test_relativer_pfad_aus_der_umgebung_wird_abgewiesen() -> None:
    """Der Betreiber hat einen Ort GENANNT -- ein stiller anderer waere schlimmer.

    Zurechtbiegen hiesse: der Halt liegt woanders, als der Betreiber denkt. Also ein
    Wurf, und zwar beim Bau des ``RiskManager`` -- vor der ersten Order.
    """
    for variable in ("MT5_RISIKO_ZUSTAND", "MT5_RISIKO_ZUSTAND_ORDNER"):
        with pytest.raises(ZustandsortFehler):
            standard_zustandsdatei(umgebung={variable: "betrieb/risikozustand.json"})
    # Gegenprobe: absolut geht durch.
    absolut = str(Path.home() / "risikozustand.json")
    assert standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": absolut}) == Path(
        absolut
    )
''',
        '''def test_relativer_zustandsordner_wird_abgewiesen() -> None:
    """Der Betreiber hat einen Ort GENANNT -- ein stiller anderer waere schlimmer.

    Zurechtbiegen hiesse: der Halt liegt woanders, als der Betreiber denkt. Also ein
    Wurf, und zwar beim Waehlen des Ordners (``--zustandsordner``, D8) -- vor dem Bau
    des ``RiskManager`` und vor der ersten Order.
    """
    for relativ in ("betrieb", "betrieb/risikozustand.json", "."):
        with pytest.raises(ZustandsortFehler):
            zustandsordner_pruefen(relativ)
    # Gegenprobe: absolut geht durch.
    absolut = Path.home() / "eigener-zustand"
    assert zustandsordner_pruefen(str(absolut)) == absolut
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    im_paket = Path(modul.__file__).resolve().parents[1] / "risikozustand.json"
    with pytest.raises(ZustandsortFehler):
        standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": str(im_paket)})
''',
        '''    im_paket = Path(modul.__file__).resolve().parents[1]
    with pytest.raises(ZustandsortFehler):
        zustandsordner_pruefen(im_paket)
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''def test_umgebung_schlaegt_den_standardpfad(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwei Konten = zwei Dateien; der Betreiber setzt den Pfad je Lauf."""
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", str(tmp_path / "konto-a.json"))
    assert standard_zustandsdatei() == tmp_path / "konto-a.json"
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND")
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND_ORDNER", str(tmp_path / "ordner"))
    assert standard_zustandsordner() == tmp_path / "ordner"
    assert standard_zustandsdatei().parent == tmp_path / "ordner"


def test_ohne_umgebung_bleibt_die_schicht_fluechtig(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)
    assert RiskManager().zustand_dauerhaft is False


def test_mit_umgebung_ist_die_schicht_dauerhaft(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", str(tmp_path / "z.json"))
    assert RiskManager().zustand_dauerhaft is True
''',
        '''def test_der_genannte_ordner_schlaegt_den_standardordner(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Zwei Konten = zwei Ordner; der Betreiber nennt ihn je Lauf (``--zustandsordner``).
    Keine Umgebungsvariable entscheidet mehr (D8, E-005)."""
    assert zustandsordner_waehlen(tmp_path / "ordner") == tmp_path / "ordner"
    assert zustandsordner_waehlen(None) == standard_zustandsordner()
    assert standard_zustandsdatei(ordner=tmp_path / "ordner") == (
        tmp_path / "ordner" / "risikozustand.json"
    )


def test_ohne_zustand_ist_der_riskmanager_nicht_konstruierbar() -> None:
    """D8: ``RiskManager()`` gibt es nicht mehr; fluechtig heisst so und ist ablesbar."""
    ohne_zustand = RiskManager
    with pytest.raises(TypeError):
        ohne_zustand()  # der Konstruktor verlangt zustand=
    assert RiskManager(zustand=FluechtigerZustand()).zustand_dauerhaft is False


def test_mit_datei_ist_die_schicht_dauerhaft(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert (
        RiskManager(zustand=DateiZustand(tmp_path / "z.json")).zustand_dauerhaft is True
    )
''',
        datei=d,
    )
    # Mechanisch NACH den gezielten Ersetzungen: der neue Fall oben ruft den
    # Konstruktor ueber einen Alias, damit er hier nicht ergaenzt wird.
    s, n = mit_argument(
        s, "RiskManager", "zustand=FluechtigerZustand()", ueberspringe=("zustand=",)
    )
    zaehle(f"RiskManager: {d}", n)
    s = ersetze(
        s,
        "    standard_zustandsdatei,\n    standard_zustandsordner,\n)",
        "    FluechtigerZustand,\n    standard_zustandsdatei,\n    standard_zustandsordner,\n    zustandsordner_pruefen,\n    zustandsordner_waehlen,\n)",
        datei=d,
    )
    return s


def restbefunde(s: str) -> str:
    d = "test_risiko_zustand_restbefunde.py"
    s = ersetze(
        s,
        '''        with pytest.raises(ZustandsortFehler):
            standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": str(ziel)})
        with pytest.raises(ZustandsortFehler):
            standard_zustandsdatei(
                umgebung={"MT5_RISIKO_ZUSTAND_ORDNER": str(ziel.parent)}
            )
''',
        '''        with pytest.raises(ZustandsortFehler):
            zustandsordner_pruefen(ziel.parent)
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    assert standard_zustandsdatei(umgebung={"MT5_RISIKO_ZUSTAND": str(ziel)}) == ziel
''',
        '''    assert zustandsordner_pruefen(tmp_path) == tmp_path
    assert standard_zustandsdatei(ordner=tmp_path) == ziel
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)

''',
        "",
        datei=d,
        genau=2,
    )
    s = ersetze(
        s,
        "    Ohne Zustandsdatei (die Umgebung wird geraeumt): geprueft wird die Weitergabe der\n    Kennung, nicht die Platte.\n",
        "    Ohne Zustandsdatei (fluechtiger Testtyp): geprueft wird die Weitergabe der\n    Kennung, nicht die Platte.\n",
        datei=d,
    )
    s = ersetze(s, "    standard_zustandsdatei,\n", "    standard_zustandsdatei,\n    zustandsordner_pruefen,\n", datei=d)
    return s


def geheimnis(s: str) -> str:
    d = "test_risiko_zustand_geheimnis.py"
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND_ORDNER", str(tmp_path))
    pfad = standard_zustandsdatei()
''',
        "    pfad = standard_zustandsdatei(ordner=tmp_path)\n",
        datei=d,
    )
    return s


def eichfaelle(s: str) -> str:
    d = "test_risikozustand_eichfaelle.py"
    s = ersetze(
        s,
        '''Diese Datei ist absichtlich **frei von jedem Import des neuen Moduls**. Sie kennt nur
``RiskManager``, ``RiskPolicy`` und ``ThrottlePolicy`` -- alles, was es am Stand 5e7c4f7
schon gab -- und schaltet die Dauerhaftigkeit ueber die Umgebungsvariable
``MT5_RISIKO_ZUSTAND`` ein. Das ist kein Stilentscheid: gegen HEAD ausgepackt faellt
jeder Test hier an einer **Zusicherung**, nicht an einem ``ImportError``. Ein
Sammelfehler beweist nur, dass eine Datei fehlt; eine gerissene Zusicherung beweist,
dass das Verhalten falsch war.
''',
        '''Diese Datei war bis D8 absichtlich frei von jedem Import des Zustandsmoduls und
schaltete die Dauerhaftigkeit ueber die Umgebungsvariable ``MT5_RISIKO_ZUSTAND`` ein,
damit sie gegen den Stand 5e7c4f7 an einer **Zusicherung** fiel und nicht an einem
``ImportError``. Seit D8 (E-005) gibt es die Variable nicht mehr: der Ort ist ein
Konstruktorargument (``zustand=DateiZustand(...)`` in ``tmp_path``), und die Messungen
unten gelten fuer den Stand, an dem sie gemacht wurden.
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''def _dauerhaft(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Schalte die Dauerhaftigkeit auf eine Datei im Temp-Verzeichnis.

    Ausdruecklich ueber ``tmp_path``: kein Test dieses Repos darf an einer Datei
    haengen, die nicht versioniert ist -- weder an ``TRIALS.jsonl`` noch an
    ``betrieb/*.jsonl`` noch am Zustandsverzeichnis des Benutzers.
    """
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", str(tmp_path / "risikozustand.json"))
''',
        '''def _zustand(tmp_path) -> DateiZustand:  # type: ignore[no-untyped-def]
    """Die Dauerhaftigkeit auf eine Datei im Temp-Verzeichnis -- je Aufruf ein
    frischer ``DateiZustand`` auf derselben Datei, also ein Prozessstart.

    Ausdruecklich ueber ``tmp_path``: kein Test dieses Repos darf an einer Datei
    haengen, die nicht versioniert ist -- weder an ``TRIALS.jsonl`` noch an
    ``betrieb/*.jsonl`` noch am Zustandsverzeichnis des Benutzers (A10).
    """
    return DateiZustand(tmp_path / "risikozustand.json")
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", "betrieb/risikozustand.json")
    with pytest.raises(ValueError):
        RiskManager()

    monkeypatch.delenv("MT5_RISIKO_ZUSTAND")
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND_ORDNER", "betrieb")
    with pytest.raises(ValueError):
        RiskManager()

    # Gegenprobe: ein absoluter Pfad geht durch -- die Sperre trifft nur den Fall,
    # den sie treffen soll.
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND_ORDNER", str(tmp_path))
    assert RiskManager().zustand_dauerhaft is True
''',
        '''    for relativ in ("betrieb/risikozustand.json", "betrieb"):
        with pytest.raises(ValueError):
            zustandsordner_pruefen(relativ)

    # Gegenprobe: ein absoluter Pfad geht durch -- die Sperre trifft nur den Fall,
    # den sie treffen soll.
    assert zustandsordner_pruefen(tmp_path) == tmp_path
    assert RiskManager(zustand=_zustand(tmp_path)).zustand_dauerhaft is True
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    """ROT gegen HEAD: dort wurde die Umgebungsvariable gar nicht gelesen (kein Wurf).
''',
        '''    """ROT gegen HEAD: dort wurde der genannte Ort gar nicht geprueft (kein Wurf).
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    Der eigentliche Betriebsweg: ``RiskManager()`` ohne Argumente (so bauen ihn
    ``tools/live_betrieb.py``, ``tools/paper_run.py``, ``tools/live_konsole.py`` und
    ``tools/mt5_smoke.py``), Dauerhaftigkeit ueber die Umgebungsvariable. Der Scheduler
''',
        '''    Der eigentliche Betriebsweg: ``RiskManager`` ohne Konto (so bauen ihn
    ``tools/live_betrieb.py``, ``tools/paper_run.py``, ``tools/live_konsole.py`` und
    ``tools/mt5_smoke.py``), Dauerhaftigkeit ueber die Zustandsdatei. Der Scheduler
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND", raising=False)
    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)

    rm = RiskManager()
''',
        "    rm = RiskManager(zustand=FluechtigerZustand())\n",
        datei=d,
    )
    # Die Faelle mit Zustandsdatei: die frueheren ``_dauerhaft``-Aufrufer.
    bloecke = s.split("\ndef ")
    for i, block in enumerate(bloecke):
        if "_dauerhaft(monkeypatch, tmp_path)" in block:
            block = block.replace("    _dauerhaft(monkeypatch, tmp_path)\n\n", "").replace(
                "    _dauerhaft(monkeypatch, tmp_path)\n", ""
            )
            block, n = mit_argument(block, "RiskManager", "zustand=_zustand(tmp_path)", ueberspringe=("zustand=",))
            zaehle(f"RiskManager(DateiZustand): {d}", n)
            bloecke[i] = block
    s = "\ndef ".join(bloecke)
    # Die uebrigen: Schreibfehler-Faelle setzten die Variable auf einen gesperrten Pfad.
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", str(sperre / "risikozustand.json"))

    rm = RiskManager()
''',
        '''    rm = RiskManager(zustand=DateiZustand(sperre / "risikozustand.json"))
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    monkeypatch.delenv("MT5_RISIKO_ZUSTAND_ORDNER", raising=False)
    monkeypatch.setenv("MT5_RISIKO_ZUSTAND", str(ziel))
    ordner.write_text("kein Verzeichnis", encoding="utf-8")

    rm = RiskManager()
''',
        '''    ordner.write_text("kein Verzeichnis", encoding="utf-8")

    rm = RiskManager(zustand=DateiZustand(ziel))
''',
        datei=d,
    )
    s, n = mit_argument(s, "RiskManager", "zustand=FluechtigerZustand()", ueberspringe=("zustand=",))
    zaehle(f"RiskManager: {d}", n)
    s = import_sichern(s, "FluechtigerZustand")
    s = import_sichern(s, "DateiZustand")
    s = import_sichern(s, "zustandsordner_pruefen")
    return s


def skipgate(s: str) -> str:
    d = "eichfall_skipgate.py"
    s = ersetze(
        s,
        '''Benutzers -- das waere genau der Verstoss, den A10 verbietet. Er setzt im Unterprozess
``MT5_RISIKO_ZUSTAND_ORDNER`` (die dokumentierte Betreibervariable) auf einen Ordner
im tmp_path; ``standard_zustandsordner()`` und damit der Waechter folgen ihr. Welchen
''',
        '''Benutzers -- das waere genau der Verstoss, den A10 verbietet. Er setzt im Unterprozess
die Plattformvariablen ``LOCALAPPDATA`` und ``XDG_STATE_HOME`` (die einzigen, die
``standard_zustandsordner()`` noch liest -- die Betreibervariable
``MT5_RISIKO_ZUSTAND_ORDNER`` ist mit D8 entfallen) auf einen Ordner im tmp_path;
``standard_zustandsordner()`` und damit der Waechter folgen ihnen. Welchen
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''        import os
        from pathlib import Path

        def test_schreibt_in_den_zustandsordner():
            ordner = Path(os.environ["MT5_RISIKO_ZUSTAND_ORDNER"])
            ordner.mkdir(parents=True, exist_ok=True)
            (ordner / "risikozustand.json").write_text("{}", encoding="utf-8")
        """,
        umgebung={"MT5_RISIKO_ZUSTAND_ORDNER": str(attrappe)},
''',
        '''        from mt5_trading_ai.execution.risiko_zustand import standard_zustandsordner

        def test_schreibt_in_den_zustandsordner():
            ordner = standard_zustandsordner()
            ordner.mkdir(parents=True, exist_ok=True)
            (ordner / "risikozustand.json").write_text("{}", encoding="utf-8")
        """,
        umgebung={"LOCALAPPDATA": str(attrappe), "XDG_STATE_HOME": str(attrappe)},
''',
        datei=d,
    )
    return s


# ---------------------------------------------------------------------------
# (e) Attrappen von live_betrieb: halt_grund_loesen (D4), startabgleich (D7)
# ---------------------------------------------------------------------------
LOESEN = '''
    def halt_grund_loesen(self, praefix: str) -> tuple[str, ...]:
        """Wie ``Mt5Venue.halt_grund_loesen`` (D4): nur der eigene Anteil faellt."""
        if self.halt_reason is None or not self.halt_reason.startswith(praefix):
            return ()
        geloest = (self.halt_reason,)
        self.halt_reason = None
        self.geloest += 1
        return geloest
'''


def sperren(s: str) -> str:
    d = "test_live_betrieb_sperren.py"
    s = ersetze(
        s,
        '''    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1


@dataclass
class SpiegelScheduler:''',
        '''    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1
'''
        + LOESEN
        + '''

@dataclass
class SpiegelScheduler:''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    gesund: bool = False
    halt_reason: str | None = None
    verbunden: int = 0
    uebernommen: int = 0
    geloest: int = 0
''',
        '''    gesund: bool = False
    halt_reason: str | None = None
    verbunden: int = 0
    uebernommen: int = 0
    geloest: int = 0
    #: Ergebnis von ``adopt_book`` (D7); die Attrappe fuehrt kein Buch, also keines.
    startabgleich: Any = None
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1


def _journal(tmp_path: Path) -> Journal:''',
        '''    def clear_halt(self) -> None:
        self.halt_reason = None
        self.geloest += 1
'''
        + LOESEN
        + '''

def _journal(tmp_path: Path) -> Journal:''',
        datei=d,
    )
    s = ersetze(
        s,
        "``clear_halt`` setzt ``_halt_reason`` auf ``None`` (``venue/mt5.py:1416``), der\n    Grund wurde also NACH dem Loeschen gelesen.",
        "``clear_halt`` setzte ``_halt_reason`` auf ``None`` (``venue/mt5.py:1416`` am\n    Stand 306bbaa), der Grund wurde also NACH dem Loeschen gelesen.",
        datei=d,
    )
    return s


def live_betrieb(s: str) -> str:
    d = "test_live_betrieb.py"
    s = ersetze(
        s,
        '''    def submit_order(self, anfrage: Any) -> _Angenommen:
        self.gesendet.append(anfrage.client_order_id)
        return _Angenommen()


@dataclass
class FakeScheduler:''',
        '''    def submit_order(self, anfrage: Any) -> _Angenommen:
        self.gesendet.append(anfrage.client_order_id)
        return _Angenommen()

    def halt_grund_loesen(self, praefix: str) -> tuple[str, ...]:
        """Diese Attrappe fuehrt keinen Halt -- es gibt nichts zu loesen (D4)."""
        return ()


@dataclass
class FakeScheduler:''',
        datei=d,
    )
    return s


# ---------------------------------------------------------------------------
# (f) run_signal / build_paper_venue / run_paper
# ---------------------------------------------------------------------------
def paper_runner(s: str) -> str:
    d = "test_paper_runner.py"
    s = ersetze(
        s,
        '''        "now": TS,
        "client_order_id": "run-1",
    }
    kwargs.update(overrides)
    return run_signal(**kwargs)  # type: ignore[arg-type]
''',
        '''        "now": TS,
        "client_order_id": "run-1",
        # Die Runner-Faelle senden an das Fake-Terminal -- mit Schreibrecht (D1).
        "darf_schreiben": True,
    }
    kwargs.update(overrides)
    return run_signal(**kwargs)  # type: ignore[arg-type]
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''def test_paper_run_full_chain_opens_green() -> None:
    module = _load_paper_run()
    report, halted = module.run_paper("EURUSD")  # type: ignore[attr-defined]
''',
        '''def test_paper_run_full_chain_opens_green(tmp_path: Path) -> None:
    module = _load_paper_run()
    report, halted = module.run_paper(  # type: ignore[attr-defined]
        "EURUSD", zustandsordner=tmp_path
    )
''',
        datei=d,
    )
    s = ersetze(
        s,
        '''def test_paper_run_command_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_paper_run()
    monkeypatch.setattr(sys, "argv", ["paper_run.py", "--symbol", "EURUSD"])
    assert int(module.main()) == 0  # type: ignore[attr-defined]
''',
        '''def test_paper_run_command_exits_zero(tmp_path: Path) -> None:
    module = _load_paper_run()
    argv = ["--symbol", "EURUSD", "--zustandsordner", str(tmp_path)]
    assert int(module.main(argv)) == 0  # type: ignore[attr-defined]
    assert (tmp_path / "risikozustand.json").is_file()  # der Zustand lag dort (D8)
''',
        datei=d,
    )
    return s


def kostenbasis(s: str) -> str:
    d = "test_stop_budget_kostenbasis.py"
    s = ersetze(s, "    venue = modul.build_paper_venue(rm)\n", "    venue = modul.build_paper_venue(rm, zustandsordner=tmp_path)\n", datei=d, genau=2)
    s = tmp_path_fuer_alle(s, "modul.build_paper_venue(rm, zustandsordner=tmp_path)")
    s = ersetze(
        s,
        '_paper_run().run_paper("EURUSD")',
        '_paper_run().run_paper("EURUSD", zustandsordner=tmp_path)',
        datei=d,
        genau=3,
    )
    s = tmp_path_fuer_alle(s, '_paper_run().run_paper("EURUSD", zustandsordner=tmp_path)')
    n = s.count("        client_order_id=\"k3-strikt\",\n    )")
    s = s.replace(
        "        client_order_id=\"k3-strikt\",\n    )",
        "        client_order_id=\"k3-strikt\",\n        darf_schreiben=True,\n    )",
    )
    zaehle(f"run_signal darf_schreiben: {d}", n)
    zeilen = s.split("\n")
    # Der zweite run_signal-Aufruf: client_order_id-Zeile innerhalb von run_signal(...).
    for i, z in enumerate(zeilen):
        if z.strip().startswith("client_order_id=") and "k3-strikt" not in z:
            # nur, wenn wir in einem run_signal-Aufruf stehen
            rueck = "\n".join(zeilen[max(0, i - 15) : i])
            if "run_signal(" in rueck and "darf_schreiben" not in "\n".join(zeilen[i : i + 3]):
                zeilen.insert(i + 1, "        darf_schreiben=True,")
                zaehle(f"run_signal darf_schreiben: {d}")
                break
    return "\n".join(zeilen)


def stufe5(s: str) -> str:
    d = "test_stufe5_ausfuehrung.py"
    s = ersetze(s, "    assert SchwebeAkte(None).dauerhaft is False\n", "    assert FluechtigeSchwebeAkte().dauerhaft is False\n", datei=d)
    s = ersetze(
        s,
        "    venue, terminal = _venue(is_demo=True, schwebeakte=SchwebeAkte(None))\n",
        "    venue, terminal = _venue(is_demo=True, schwebeakte=FluechtigeSchwebeAkte())\n",
        datei=d,
    )
    s = ersetze(
        s,
        "from mt5_trading_ai.execution.schwebende_auftraege import (\n    FORMATFASSUNG,\n    SchwebeAkte,\n",
        "from mt5_trading_ai.execution.schwebende_auftraege import (\n    FORMATFASSUNG,\n    FluechtigeSchwebeAkte,\n    SchwebeAkte,\n",
        datei=d,
    )
    return s


def stufe10(s: str) -> str:
    d = "test_stufe10_betrieb.py"
    s = ersetze(
        s,
        '    erster = RiskManager(konto_id="50123456", waehrung="USD")  # kein ``zustand=``\n',
        '    erster = RiskManager(  # der fluechtige Testtyp, ausdruecklich (D8)\n        zustand=FluechtigerZustand(), konto_id="50123456", waehrung="USD"\n    )\n',
        datei=d,
    )
    s = ersetze(
        s,
        '    zweiter = RiskManager(konto_id="50123456", waehrung="USD")\n',
        '    zweiter = RiskManager(\n        zustand=FluechtigerZustand(), konto_id="50123456", waehrung="USD"\n    )\n',
        datei=d,
    )
    return import_sichern(s, "FluechtigerZustand")


def ausstiegsdeckung(s: str) -> str:
    """Die Meldung des Ausstiegsriegels nennt den neuen Schalter (Z)."""
    return ersetze(
        s,
        '    assert "--scharf" in grund\n',
        '    assert "--demo-schreiben" in grund\n',
        datei="test_ausstiegsdeckung.py",
    )


def orderpfad_verdrahtung(s: str) -> str:
    d = "test_orderpfad_verdrahtung.py"
    s = ersetze(
        s,
        "def test_live_eroeffnung_faehrt_alle_fuenf_sperren(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:",
        "def test_live_eroeffnung_faehrt_alle_fuenf_sperren(\n    monkeypatch: pytest.MonkeyPatch, tmp_path: Path\n) -> None:",
        datei=d,
    )
    s = ersetze(s, "        _released_settings,\n", "        _freigabedatei,\n", datei=d)
    s = ersetze(
        s,
        "        settings=_released_settings(),\n",
        "        freigabedatei=_freigabedatei(tmp_path),\n",
        datei=d,
    )
    if "from pathlib import Path" not in s:
        s = s.replace("from decimal import Decimal\n", "from decimal import Decimal\nfrom pathlib import Path\n", 1)
    return s


GEZIELT = {
    "test_ausstiegsdeckung.py": ausstiegsdeckung,
    "test_orderpfad_verdrahtung.py": orderpfad_verdrahtung,
    "test_mt5_venue.py": test_mt5_venue,
    "test_demo_beleg_grenze.py": demo_beleg_grenze,
    "test_demo_tor_eichfall.py": demo_tor_eichfall,
    "test_risiko_zustand.py": risiko_zustand,
    "test_risiko_zustand_restbefunde.py": restbefunde,
    "test_risiko_zustand_geheimnis.py": geheimnis,
    "test_risikozustand_eichfaelle.py": eichfaelle,
    "eichfall_skipgate.py": skipgate,
    "test_live_betrieb_sperren.py": sperren,
    "test_live_betrieb.py": live_betrieb,
    "test_paper_runner.py": paper_runner,
    "test_stop_budget_kostenbasis.py": kostenbasis,
    "test_stufe5_ausfuehrung.py": stufe5,
    "test_stufe10_betrieb.py": stufe10,
}


def main() -> int:
    geaendert: list[str] = []
    for pfad in sorted(TESTS.glob("*.py")):
        name = pfad.name
        if name == "conftest.py" or name.startswith("eichfall_d") or name == "eichfall_z.py":
            continue
        alt = lese(name)
        s = alt
        if name in GEZIELT:
            s = GEZIELT[name](s)
        s = mechanisch(name, s)
        if s != alt:
            schreibe(name, s)
            geaendert.append(name)
    print(f"{len(geaendert)} Testdateien geaendert:")
    for name in geaendert:
        print("  ", name)
    print("Zaehlung:")
    for k in sorted(ZAEHLUNG):
        print(f"  {ZAEHLUNG[k]:3d}  {k}")
    print(
        "  RiskManager gesamt:",
        sum(v for k, v in ZAEHLUNG.items() if k.startswith("RiskManager")),
    )
    print("  Mt5Venue gesamt:", sum(v for k, v in ZAEHLUNG.items() if k.startswith("Mt5Venue")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

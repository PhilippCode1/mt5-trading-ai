"""Das Werkzeug, das die Zahlen von Paket 3a erzeugt hat -- bisher ohne einen Test.

WARUM DIESE DATEI SPAET KOMMT UND TROTZDEM NOETIG IST
-----------------------------------------------------
``tools/aufloesung.py`` hat die Aufloesungstabelle gemessen, aus der das Kandidatenfeld
folgt, und stand dabei bei null Prozent Abdeckung. Drei der sechs in
``ABSCHLUSS-3a/09-EIGENE-FEHLER.md`` benannten Fehler sassen in genau diesem Werkzeug --
in der Historienabfrage, im Schnitt vor der Euro-Einfuehrung und in der Kostenzeile. Ein
Werkzeug, dessen Ausgabe als Beleg zitiert wird, muss nachpruefbar sein wie eine Messung.

Geprueft wird, was ohne MT5-Terminal pruefbar ist: die Zusammensetzung der Reihe aus
Scheiben, der Schnitt an ``FRUEHESTE_KERZE``, die Herkunftspruefsumme und die
Nachrechnung der abgelegten Messdatei. Der lesende Terminalpfad selbst gehoert zu
``tests/test_mt5_venue.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.backtest.ereignisstudie import OOS_ANTEIL
from mt5_trading_ai.backtest.resolution import deflation_observations
from mt5_trading_ai.venue.mt5 import Mt5Rate, Mt5Tick
from mt5_trading_ai.venue.protocol import Timeframe
from tools import aufloesung
from tools.aufloesung import (
    SCHEIBE_JAHRE,
    _bester_zeitrahmen,
    _hole,
    _korrigiert,
    _manifest,
    pruefen,
)

#: Die Zeile aus ``config/aufloesung.json``, an der der Rechenfehler aufgefallen ist:
#: K3 (Monatsende-Fixing) auf GBPJPY im 1h-Fenster.
K3_ZEILE: dict[str, Any] = {
    "instrument": "GBPJPY",
    "window": "1h",
    "frequency": "monatlich",
    "events": 193,
    "dispersion_bps": 14.1517,
    "cost_bps": 1.8351,
}
#: Verhaeltnis gegen die volle Ereigniszahl -- so stand es in der Datei, so war es falsch.
K3_VERHAELTNIS_VOLL = 0.6229
#: Verhaeltnis gegen die 65 Beobachtungen, die die Deflation tatsaechlich sieht.
K3_VERHAELTNIS_DEFLATION = 1.1121


def _rate(ts: datetime) -> Mt5Rate:
    """Eine Kerze, deren einziger interessanter Teil ihr Zeitstempel ist."""
    return Mt5Rate(
        ts=ts,
        open=Decimal("1.10"),
        high=Decimal("1.20"),
        low=Decimal("1.00"),
        close=Decimal("1.15"),
        tick_volume=1,
    )


#: Uhr der Attrappen: weit hinter jeder erzeugten Kerze, damit alle als
#: abgeschlossen gelten. Begruendung bei ``tick`` unten.
_PLATZZEIT = datetime(2999, 1, 1, tzinfo=UTC)


class _StubTerminal:
    """Ein Terminal, das ``rates`` und ``tick`` kann -- mehr fasst ``_hole`` nicht an.

    Bewusst ohne Mock-Rahmenwerk: die Faelle unten fragen, WELCHE Zeitscheiben abgefragt
    werden und in welcher Reihenfolge. Dafuer ist eine mitgeschriebene Liste lesbarer als
    ein Aufrufprotokoll, das man erst wieder auswerten muss.
    """

    def __init__(self, antwort: Any) -> None:
        self._antwort = antwort
        self.abfragen: list[tuple[datetime, datetime]] = []

    def tick(self, name: str) -> Mt5Tick:
        """Die Platzzeit -- seit Stufe 2 fragt der Aufrufer danach.

        Bewusst weit voraus. Diese Faelle messen die Scheibenbildung, nicht die
        Kante zwischen laufender und fertiger Kerze; mit einer Uhr, die hinter den
        erzeugten Kerzen laege, fiele die juengste heraus und die Erwartungen unten
        wuerden eine andere Frage beantworten als die, fuer die sie geschrieben sind.
        Die Kante selbst misst ``tests/test_zeitschranken.py``.
        """
        return Mt5Tick(ts=_PLATZZEIT, bid=Decimal("1"), ask=Decimal("1"))

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        nr = len(self.abfragen)
        self.abfragen.append((start, end))
        result: tuple[Mt5Rate, ...] = self._antwort(name, start, end, nr)
        return result


# --- Zeitrahmenwahl -------------------------------------------------------
@pytest.mark.parametrize(
    "fenster_stunden,erwartet",
    [(1.0, Timeframe.H1), (3.9, Timeframe.H1), (4.0, Timeframe.H4),
     (24.0, Timeframe.H4)],
)
def test_bester_zeitrahmen_waehlt_die_tiefere_reihe(
    fenster_stunden: float, erwartet: Timeframe
) -> None:
    """Unter vier Stunden gibt es keine Wahl, ab vier Stunden ist H4 die tiefere Reihe."""
    tf, _stunden = _bester_zeitrahmen(fenster_stunden)
    assert tf is erwartet


# --- Die Reihe aus Scheiben ----------------------------------------------
def test_hole_setzt_die_reihe_aus_fuenfjahresscheiben_zusammen() -> None:
    """Von Hand nachgerechnet: 45 Jahre sind 16.425 Tage, das sind genau neun Scheiben.

    Die Scheibengroesse ist kein Schoenheitsfehler, sondern Fehler 5 aus
    ``09-EIGENE-FEHLER.md``: eine EINZELNE Abfrage ueber mehr als rund 70.000 Kerzen
    kommt leer zurueck, und zwar leer statt als Fehler. Faellt die Stueckelung weg,
    verkuerzt sich die Historie still -- also in der Richtung, die gegen die Kandidaten
    zeigt, aber ebenso unbemerkt.
    """
    gemeinsam = datetime(2015, 6, 1, tzinfo=UTC)

    def antwort(
        name: str, start: datetime, end: datetime, nr: int
    ) -> tuple[Mt5Rate, ...]:
        eigene = tuple(_rate(start + timedelta(hours=k)) for k in (1, 2, 3))
        return (*eigene, _rate(gemeinsam))

    terminal = _StubTerminal(antwort)
    reihe, protokoll = _hole(terminal, "TESTFX", Timeframe.D1, 45)  # type: ignore[arg-type]

    # 45 * 365 / (5 * 365) = 9 Scheiben, jede beim ersten Versuch beantwortet.
    assert len(terminal.abfragen) == 9
    assert len(protokoll) == 9
    # 9 x 3 eigene Kerzen plus die eine, die in jeder Scheibe steckt und nur einmal zaehlt.
    assert len(reihe) == 9 * 3 + 1
    assert [r.ts for r in reihe] == sorted(r.ts for r in reihe)
    assert sum(1 for r in reihe if r.ts == gemeinsam) == 1

    # Von jung nach alt, luecken- und ueberlappungsfrei aneinander.
    starts = [a for a, _ in terminal.abfragen]
    enden = [e for _, e in terminal.abfragen]
    assert starts == sorted(starts, reverse=True)
    assert starts[:-1] == enden[1:]
    assert enden[0] - starts[0] == timedelta(days=365 * SCHEIBE_JAHRE)


def test_hole_haelt_eine_zweimal_leere_scheibe_aus() -> None:
    """Vor dem Anfang des Archivs ist Leere die richtige Antwort, kein Abbruch.

    Zwei Versuche je Scheibe, weil eine leere Antwort auch „noch nicht vom Server
    geladen" heissen kann. Von Hand: zwei Scheiben, die erste einmal beantwortet, die
    zweite zweimal leer -- macht drei Abfragen und zwei Protokollzeilen.
    """
    fest = datetime(2019, 3, 4, tzinfo=UTC)

    def antwort(
        name: str, start: datetime, end: datetime, nr: int
    ) -> tuple[Mt5Rate, ...]:
        return (_rate(fest),) if nr == 0 else ()

    terminal = _StubTerminal(antwort)
    reihe, protokoll = _hole(terminal, "TESTFX", Timeframe.D1, 10)  # type: ignore[arg-type]

    assert len(terminal.abfragen) == 3
    assert len(reihe) == 1
    assert len(protokoll) == 2
    assert "zweimal leer" in protokoll[1]


def test_hole_verwirft_eurusd_kerzen_vor_der_euro_einfuehrung() -> None:
    """Fehler 4 aus ``09-EIGENE-FEHLER.md``, festgenagelt am Werkzeug statt am Manifest.

    ``test_resolution.py`` prueft das Ergebnis (die abgelegten Manifeste). Hier wird der
    Schnitt selbst geprueft -- er muss auch dann greifen, wenn gerade keine Manifeste im
    Repo liegen, und er muss im Protokoll stehen statt still zu geschehen.
    """
    vor_dem_euro = datetime(1990, 5, 7, tzinfo=UTC)
    danach = datetime(2000, 5, 7, tzinfo=UTC)

    def antwort(
        name: str, start: datetime, end: datetime, nr: int
    ) -> tuple[Mt5Rate, ...]:
        return (_rate(vor_dem_euro), _rate(danach))

    terminal = _StubTerminal(antwort)
    reihe, protokoll = _hole(terminal, "EURUSD", Timeframe.D1, 45)  # type: ignore[arg-type]

    assert [r.ts for r in reihe] == [danach]
    assert any("verworfen" in zeile for zeile in protokoll)


# --- Herkunft -------------------------------------------------------------
def test_manifest_haengt_an_den_daten_nicht_an_der_formatierung() -> None:
    """Pruefsumme von Hand nachgerechnet, ueber die kanonische Textform der Reihe.

    Erwartet wird der SHA-256 von::

        1577923200;1.1;1.2;1.0;1.15\\n1578009600;1.15;1.25;1.05;1.2\\n

    Die Zeitstempel sind Sekunden seit 1970: 2020-01-01T00:00Z ist 1.577.836.800, ein
    Tag mehr 1.577.923.200, zwei Tage mehr 1.578.009.600. Steht hier eine andere Summe,
    hat sich die Kanonisierung geaendert -- und damit die ``data_checksum``, mit der das
    Versuchsregister die Reihe wiedererkennt.
    """
    reihe = (
        Mt5Rate(
            ts=datetime(2020, 1, 2, tzinfo=UTC),
            open=Decimal("1.1"),
            high=Decimal("1.2"),
            low=Decimal("1.0"),
            close=Decimal("1.15"),
            tick_volume=7,
        ),
        Mt5Rate(
            ts=datetime(2020, 1, 3, tzinfo=UTC),
            open=Decimal("1.15"),
            high=Decimal("1.25"),
            low=Decimal("1.05"),
            close=Decimal("1.2"),
            tick_volume=9,
        ),
    )
    man = _manifest("TESTFX", Timeframe.D1, reihe)

    assert man["bars"] == 2
    assert man["first"] == "2020-01-02T00:00:00+00:00"
    assert man["last"] == "2020-01-03T00:00:00+00:00"
    assert man["checksum"] == (
        "0308a8d253f3bd67028fcef8c94b13951297c49e3e616223340cd27989d5f4bc"
    )
    assert man["zeitbasis"] == "server-etikett"

    # Das Handelsvolumen ist bewusst NICHT Teil der Summe -- die Studie rechnet auf
    # Kursen. Aendert sich daran etwas, ist es eine Entscheidung und kein Versehen.
    anders = (reihe[0], Mt5Rate(**{**reihe[1].__dict__, "tick_volume": 99}))
    assert _manifest("TESTFX", Timeframe.D1, anders)["checksum"] == man["checksum"]

    geaendert = (reihe[0], Mt5Rate(**{**reihe[1].__dict__, "close": Decimal("1.21")}))
    assert _manifest("TESTFX", Timeframe.D1, geaendert)["checksum"] != man["checksum"]


# --- Die Nachrechnung der Messdatei --------------------------------------
def _datei(tmp_path: Path, **felder: Any) -> Path:
    """Eine erfundene Messdatei mit genau der einen Zeile, um die es geht.

    Schema 2 fuehrt ``oos_share`` und ``deflation_events`` auch JE ZEILE. Sie werden
    hier aus dem Kopf abgeleitet, damit die Fixtur dasselbe Format hat wie das, was
    ``messen()`` schreibt -- eine Fixtur, die schlanker ist als das Erzeugnis, prueft
    ein Format, das es nicht gibt. ``zeile=`` ueberschreibt einzelne Zeilenfelder; so
    bekommt ein Fall eine Zeile, die ihrem eigenen Kopf widerspricht.
    """
    zeile = dict(K3_ZEILE)
    zeile["ratio"] = felder.pop("ratio")
    zeile["resolvable"] = felder.pop("resolvable")
    ueberschreibungen: dict[str, Any] = felder.pop("zeile", {})
    dokument: dict[str, Any] = {
        "schema_version": felder.pop("schema_version", 2),
        "trials_assumed": felder.pop("trials_assumed", 12),
        "entries": [zeile],
    }
    dokument.update(felder)
    kopf_anteil = dokument.get("oos_share")
    if dokument["schema_version"] >= 2 and isinstance(kopf_anteil, float):
        zeile["oos_share"] = kopf_anteil
        zeile["deflation_events"] = deflation_observations(
            int(zeile["events"]), oos_share=kopf_anteil
        )
    zeile.update(ueberschreibungen)
    ziel = tmp_path / "aufloesung.json"
    ziel.write_text(json.dumps(dokument, indent=2), encoding="utf-8")
    return ziel


def test_pruefen_nimmt_eine_nachrechenbare_datei_an(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der Positivfall: Anteil genannt UND richtig, Verhaeltnis passt, Urteil passt.

    Die Gegenprobe zur Regel „im Fehlschlag nichts auf stdout": hier gehoert die
    gruene Zeile hin, und nur hier.
    """
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_DEFLATION,
        resolvable=False,
        oos_share=OOS_ANTEIL,
    )
    assert pruefen(ziel) == 0
    ausgabe = capsys.readouterr()
    assert ausgabe.out.startswith("ok — ")
    assert ausgabe.err == ""


def test_pruefen_faellt_auf_ein_falsches_verhaeltnis_rot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eichfall. Gegen die alte Fassung waere er fehlgeschlagen.

    ``pruefen()`` hat frueher nur gezaehlt, ob ueberhaupt Eintraege dastehen. Damit war
    es eine Ampel, die per Konstruktion nicht rot werden konnte: die Datei unten -- mit
    dem alten, gegen die volle Ereigniszahl gerechneten Verhaeltnis -- haette sie
    genauso bestanden wie eine richtige.
    """
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_VOLL,
        resolvable=True,
        oos_share=OOS_ANTEIL,
    )
    assert pruefen(ziel) == 1
    fehler = capsys.readouterr().err
    assert "rechnen sich nicht nach" in fehler
    assert "GBPJPY/1h/monatlich" in fehler


def test_pruefen_faellt_auf_eine_datei_ohne_oos_anteil_rot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eichfall. Die Datei ist in sich stimmig -- und trotzdem falsch gerechnet.

    Das ist der heikle Fall: jede Zeile rechnet sich nach, solange man gegen die volle
    Ereigniszahl rechnet. Nur sieht die Deflation der Ereignisstudie das
    Out-of-Sample-Drittel, und damit ist das ganze Blatt rund Faktor 1,7 zu guenstig.
    Eine Pruefung, die sich auf die innere Stimmigkeit verlaesst, geht hier gruen durch.

    Schema 1, wie die echte Datei: die Zeilenfelder aus Schema 2 gibt es dort nicht.
    """
    ziel = _datei(
        tmp_path, ratio=K3_VERHAELTNIS_VOLL, resolvable=True, schema_version=1
    )
    assert pruefen(ziel) == 1
    fehler = capsys.readouterr().err
    assert "oos_share" in fehler
    assert "aufloesbar -> blind" in fehler


def test_pruefen_faellt_auf_einen_nachgetragenen_anteil_rot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """DER EICHFALL DIESER REPARATUR. Gegen die vorige Fassung gruen, mit Rueckgabe 0.

    Die vorige Fassung fragte ``"oos_share" not in roh`` -- die ANWESENHEIT eines
    Schluessels statt seinen WERT. Wer der falsch gerechneten Datei die eine Zeile
    ``"oos_share": 1.0`` nachtrug, ohne eine einzige Zahl zu messen, drehte das Tor von
    rot auf gruen; ``pruefen()`` druckte dann „ok" ueber genau den Verhaeltnissen, deren
    Zurueckweisung sein Zweck ist. Das ist wortwoertlich die Fehlerklasse, gegen die
    dieses Werkzeug gebaut wurde: ein Melder, der das Falsche misst.

    Massgeblich ist jetzt der Abgleich gegen ``OOS_ANTEIL`` -- den Anteil, auf dem die
    Deflation tatsaechlich laeuft.
    """
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_VOLL,
        resolvable=True,
        schema_version=1,
        oos_share=1.0,
    )
    assert pruefen(ziel) == 1
    ausgabe = capsys.readouterr()
    assert "oos_share = 1.0" in ausgabe.err
    assert "aufloesbar -> blind" in ausgabe.err
    assert ausgabe.out == ""


def test_pruefen_druckt_im_fehlschlag_kein_wort_auf_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eichfall. Vorher stand die gruene Zeile VOR dem Befund -- und auf stdout.

    ``pruefen()`` druckte im Fehlschlag zuerst „ok — ... Kombinationen aufloesbar"
    samt Tabelle nach stdout und schob die Beanstandung danach auf stderr. Wer die
    Ausgabe ueberflog -- oder stderr verwarf, wie es jede Pipe tut -- las Gruen ueber
    falschen Zahlen. Eine Ampel, deren erstes Wort im Fehlschlag „ok" ist, ist keine.
    """
    ziel = _datei(
        tmp_path, ratio=K3_VERHAELTNIS_VOLL, resolvable=True, schema_version=1
    )
    assert pruefen(ziel) == 1
    ausgabe = capsys.readouterr()
    assert ausgabe.out == "", "im Fehlschlag gehoert nichts auf stdout"
    assert "ok" not in ausgabe.out
    assert ausgabe.err.startswith("FEHLGESCHLAGEN")


def test_pruefen_faellt_auf_eine_zeile_ohne_verhaeltnis_rot(tmp_path: Path) -> None:
    """Eichfall. Vorher stuerzte ``pruefen()`` hier mit KeyError ab, statt 1 zu melden.

    Das ``except`` umschloss nur den ``assess``-Aufruf; ``float(e["ratio"])`` und
    ``e["resolvable"]`` standen davor bzw. dahinter im Freien. Eine Datei mit einer
    unvollstaendigen Zeile riss das Tor ab, statt es rot zu faerben -- und ein
    abgerissenes Tor ist von einem gruenen nur am Rueckgabewert zu unterscheiden.
    """
    zeile = dict(K3_ZEILE)
    zeile["resolvable"] = False
    zeile["oos_share"] = OOS_ANTEIL
    zeile["deflation_events"] = deflation_observations(
        int(zeile["events"]), oos_share=OOS_ANTEIL
    )
    ziel = tmp_path / "aufloesung.json"
    ziel.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "trials_assumed": 12,
                "oos_share": OOS_ANTEIL,
                "entries": [zeile],
            }
        ),
        encoding="utf-8",
    )
    assert pruefen(ziel) == 1


def test_pruefen_haelt_die_zeilenfelder_gegen_den_kopf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eichfall. Vorher gruen: die Zeilenfelder von Schema 2 wurden nie gelesen.

    ``messen()`` schreibt je Zeile ``oos_share`` und ``deflation_events``.
    ``pruefen()`` rechnete nur ``ratio`` und ``resolvable`` nach -- eine Datei, deren
    Zeilen ihrem eigenen Kopf widersprechen, kam durch, und welche der beiden Zahlen
    die gedruckte war, stand nirgends.
    """
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_DEFLATION,
        resolvable=False,
        oos_share=OOS_ANTEIL,
        zeile={"deflation_events": 193, "oos_share": 1.0},
    )
    assert pruefen(ziel) == 1
    fehler = capsys.readouterr().err
    assert "deflation_events" in fehler
    assert "oos_share" in fehler


def test_pruefen_rechnet_auch_die_abgeleiteten_zahlen_nach(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eichfall. Vorher gruen: nachgerechnet wurde nur das Verhaeltnis.

    ``needed_bps``, ``detectable_bps`` und ``required_sharpe`` stehen in der Messdatei
    und in der gedruckten Tabelle. Solange nur ``ratio`` geprueft wurde, konnte daneben
    eine beliebige Zahl stehen -- und gelesen wird die Tabelle, nicht das Verhaeltnis.
    """
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_DEFLATION,
        resolvable=False,
        oos_share=OOS_ANTEIL,
        zeile={"detectable_bps": 0.5, "needed_bps": 1.0},
    )
    assert pruefen(ziel) == 1
    fehler = capsys.readouterr().err
    assert "detectable_bps" in fehler
    assert "needed_bps" in fehler


def test_pruefen_verlangt_die_zeilenfelder_von_schema_zwei(tmp_path: Path) -> None:
    """Schema 2 ohne die Felder von Schema 2 ist keine Schema-2-Datei."""
    ziel = _datei(
        tmp_path,
        ratio=K3_VERHAELTNIS_DEFLATION,
        resolvable=False,
        oos_share=OOS_ANTEIL,
        zeile={"deflation_events": None, "oos_share": None},
    )
    roh = json.loads(ziel.read_text(encoding="utf-8"))
    del roh["entries"][0]["deflation_events"]
    del roh["entries"][0]["oos_share"]
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    assert pruefen(ziel) == 1


def test_korrigiert_nennt_die_zeilen_die_ihr_urteil_wechseln() -> None:
    """Der Befund selbst: K3 kippt von 0,62 auf 1,11 und damit von aufloesbar auf blind."""
    zeile = dict(K3_ZEILE)
    zeile["ratio"] = K3_VERHAELTNIS_VOLL
    zeile["resolvable"] = True
    treffer = _korrigiert([zeile], 12)
    assert len(treffer) == 1
    assert "GBPJPY" in treffer[0]
    assert "N_defl=65" in treffer[0]
    assert "aufloesbar -> blind" in treffer[0]

    # Eine Zeile, die schon blind war, bleibt es -- sie taucht hier nicht auf.
    unveraendert = dict(K3_ZEILE)
    unveraendert["ratio"] = K3_VERHAELTNIS_DEFLATION
    unveraendert["resolvable"] = False
    assert _korrigiert([unveraendert], 12) == []


@pytest.mark.parametrize(
    "inhalt,grund",
    [
        ({"entries": []}, "Datei ohne Eintraege"),
        ({"entries": [{"instrument": "X"}]}, "ohne trials_assumed"),
    ],
)
def test_pruefen_faellt_auf_eine_unbrauchbare_datei_rot(
    tmp_path: Path, inhalt: dict[str, Any], grund: str
) -> None:
    ziel = tmp_path / "aufloesung.json"
    ziel.write_text(json.dumps(inhalt), encoding="utf-8")
    assert pruefen(ziel) == 1


def test_pruefen_erfindet_keine_datei(tmp_path: Path) -> None:
    """Fail-closed: keine Datei ist ein Befund, kein leeres Ergebnis."""
    assert pruefen(tmp_path / "gibtsnicht.json") == 1


# --- Das Beweiswerkzeug darf nur lesen ------------------------------------
def test_messen_oeffnet_das_terminal_ausschliesslich_lesend(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """DIE NAHT, AN DER DIE GLAUBWUERDIGKEIT DES BELEGS HAENGT.

    ``messen()`` ist der Pfad, der die Messdatei und die Manifeste von Paket 3a erzeugt
    hat. Dass diese Zahlen aus einem Terminal stammen, das gar nicht handeln KANN, ist
    die Zusicherung des Modulkopfs -- und sie stand allein in einem Aufrufargument.
    Umgestellt auf ``allow_write=True`` blieb die ganze Suite gruen; in der
    ``gegenprobe`` daneben ist dieselbe Zusicherung seit jeher festgenagelt, hier
    fehlte sie.

    Zerlegt wird ``messen()`` dafuer nicht. Die Attrappe meldet beim Verbinden
    Fehlschlag, der Lauf endet also unmittelbar nach dem Bau des Terminals mit
    Rueckgabe 2 -- geprueft wird genau die eine Zeile, die die Nur-Lese-Eigenschaft
    herstellt. Alles danach braucht ein echtes MT5-Terminal und gehoert nicht in einen
    Pruefstand, der auf ubuntu-latest laeuft.

    Festgehalten wird das Schluesselwort SAMT Wert: eine positionale Uebergabe, ein
    weggelassenes Argument und ``True`` fallen alle drei durch.
    """
    bauten: list[dict[str, Any]] = []

    class _Attrappe:
        def __init__(self, **kwargs: Any) -> None:
            bauten.append(kwargs)

        def initialize(self) -> bool:
            return False

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(aufloesung, "RealMt5Terminal", _Attrappe)

    assert aufloesung.messen() == 2
    assert "nicht initialisierbar" in capsys.readouterr().err

    assert len(bauten) == 1, "genau ein Terminal, und zwar dieses"
    assert bauten[0].get("allow_write") is False, (
        "Das Werkzeug, das den Beleg erzeugt hat, darf kein schreibfaehiges Terminal "
        "oeffnen -- sonst ist die Nur-Lesen-Zusage des Modulkopfs unbelegt"
    )
    assert bauten[0] == {"allow_write": False}

"""Die Gegenprobe aus A1.2 -- der Teil von ``tools/aufloesung.py`` ohne einen Test.

WARUM DAS ZAEHLT
----------------
``gegenprobe`` beantwortet die Frage, ob der Terminal-Feed ueberhaupt dieselbe
Geschichte erzaehlt wie eine unabhaengige Quelle. Sie hat dabei den **Serverzeit-
Versatz** gefunden -- die Erkenntnis, aus der die Drehung in ``venue/mt5.py`` und
``server_tz`` in ``live_betrieb.py`` folgen. Ein unbemerkter Versatz von einer Stunde
macht jede 1h-Fensterstudie wertlos, und er faellt nur auf, weil hier ueber ganze
Stundenverschiebungen abgetastet wird.

Die Funktion stand bei null Prozent Abdeckung. Geprueft wird alles ausser der
Terminalabfrage selbst: die Vergleichsrechnung, die Versatzabtastung, das Urteil an
der Schwelle und die vier Wege, auf denen die Funktion abbricht, bevor ueberhaupt ein
Terminal gebaut wird.

DIE ERWARTUNGEN SIND VON HAND GERECHNET
----------------------------------------
Beide Reihen sind geometrisch angelegt, damit die Renditen je Schritt **konstant**
sind und sich im Kopf nachrechnen lassen: eine Reihe mit dem Faktor 1,001 hat je
Schritt 10,0 bp, eine mit 1,0015 hat 15,0 bp, die Abweichung ist also exakt 5,0 bp --
in jedem Paar, und damit auch im Median. Die Schwelle aus dem Auftrag liegt bei 2 bp.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.venue.mt5 import Mt5Rate
from mt5_trading_ai.venue.protocol import Timeframe
from tools import aufloesung
from tools.aufloesung import _kosten_bps, gegenprobe

BASIS = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _rate(ts: datetime, close: float) -> Mt5Rate:
    preis = Decimal(str(close))
    return Mt5Rate(
        ts=ts, open=preis, high=preis, low=preis, close=preis, tick_volume=1
    )


def _csv(tmp_path: Path, name: str, punkte: list[tuple[datetime, float]]) -> Path:
    ziel = tmp_path / name
    zeilen = ["ts,close"]
    zeilen += [f"{ts.isoformat()},{wert!r}" for ts, wert in punkte]
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return ziel


class StubTerminal:
    """Ein Terminal, das nur ``rates`` beantwortet -- und mitschreibt, wie es gebaut wurde.

    ``allow_write`` wird hier **geprueft und nicht nur entgegengenommen**: die
    Gegenprobe ist ein lesendes Werkzeug, und ein schreibfaehiges Terminal haette in
    ihr nichts verloren. Ein Test, der das Schluesselwort nur schluckt, koennte eine
    Umstellung auf ``True`` nicht bemerken.
    """

    letzte: StubTerminal | None = None
    #: Antwort, die das NAECHSTE gebaute Terminal liefert. Das Objekt entsteht erst in
    #: ``gegenprobe``; die Reihe muss darum vorher an der Klasse liegen.
    vorgabe: tuple[Mt5Rate, ...] = ()

    def __init__(self, *, allow_write: bool = False, **rest: Any) -> None:
        assert allow_write is False, (
            "Die Gegenprobe darf kein schreibfaehiges Terminal oeffnen"
        )
        self.rest = rest
        self.reihe: tuple[Mt5Rate, ...] = StubTerminal.vorgabe
        self.abfragen: list[tuple[str, Timeframe, datetime, datetime]] = []
        self.beendet = 0
        StubTerminal.letzte = self

    def initialize(self) -> bool:
        return True

    def shutdown(self) -> None:
        self.beendet += 1

    def rates(
        self, name: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> tuple[Mt5Rate, ...]:
        self.abfragen.append((name, timeframe, start, end))
        return self.reihe


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> type[StubTerminal]:
    """``RealMt5Terminal`` im Modul ersetzen -- der Produktionspfad bleibt, wie er ist.

    Die Naht liegt am Modulnamen und nicht in der Funktion: ``gegenprobe`` baut ihr
    Terminal weiterhin selbst und mit denselben Argumenten.
    """
    StubTerminal.letzte = None
    StubTerminal.vorgabe = ()
    monkeypatch.setattr(aufloesung, "RealMt5Terminal", StubTerminal)
    return StubTerminal


def _setze_reihe(reihe: tuple[Mt5Rate, ...]) -> None:
    """Die Antwort des naechsten Terminals festlegen."""
    StubTerminal.vorgabe = reihe


# --- Die vier Wege, auf denen abgebrochen wird ----------------------------
def test_ohne_csv_gibt_es_keine_gegenprobe(tmp_path: Path) -> None:
    """Fail-closed: eine fehlende Vergleichsquelle ist ein Befund, kein leeres Urteil."""
    assert gegenprobe(tmp_path / "gibtsnicht.csv") == 1


def test_ein_dateiname_ohne_zeitrahmen_wird_abgewiesen(tmp_path: Path) -> None:
    """Der Zeitrahmen kommt aus dem Dateinamen. Raten waere hier eine stille Annahme.

    Er entscheidet ueber die Versatzabtastung: bei D1 wird gar nicht abgetastet. Ein
    geratener Zeitrahmen liesse die Abtastung auf Tageskerzen laufen und produzierte
    einen Versatzbefund, den es nicht gibt.
    """
    ziel = _csv(tmp_path, "EURUSD.csv", [(BASIS, 100.0)])
    assert gegenprobe(ziel) == 1


def test_ein_unbekannter_zeitrahmen_wird_abgewiesen(tmp_path: Path) -> None:
    ziel = _csv(tmp_path, "EURUSD_H9.csv", [(BASIS, 100.0)])
    assert gegenprobe(ziel) == 1


def test_zu_wenige_fremdkerzen_sind_keine_gegenprobe(
    tmp_path: Path, stub: type[StubTerminal]
) -> None:
    """29 Kerzen sind keine Stichprobe -- und ein Terminal wird gar nicht erst gebaut.

    Von Hand: die Schranke steht bei 30. Ein Median ueber weniger waere eine Zahl mit
    dem Anschein einer Messung.
    """
    punkte = [(BASIS + timedelta(days=i), 100.0) for i in range(29)]
    assert gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte)) == 1
    assert stub.letzte is None, "Vor der Schranke darf kein Terminal geoeffnet werden"


# --- Der Serverzeit-Versatz ------------------------------------------------
#: Eine Reihe mit wechselnden Renditen. Rein geometrisch waere sie gegen jede
#: Verschiebung unempfindlich -- dann fiele der Versatz nicht auf, und der Fall
#: prueefte nichts. Die Periode 7 sorgt dafuer, dass im abgetasteten Bereich
#: (-4 .. +4) genau EINE Verschiebung passt.
def _wechselnd(n: int) -> list[float]:
    return [100.0 + (i % 7) for i in range(n)]


def test_die_abtastung_findet_einen_stundenversatz(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """DER Befund, aus dem die Zeitdrehung des ganzen Repos folgt.

    Aufbau von Hand: 60 Stundenkerzen. Der Terminal-Feed traegt DIESELBEN Kurse, aber
    jeden Zeitstempel eine Stunde spaeter. Die Funktion verschiebt den eigenen Feed um
    ``versatz`` und sucht das Minimum -- bei ``-1 h`` decken sich beide Reihen exakt,
    die Abweichung ist dort null und ueberall sonst positiv.

    Ohne diese Abtastung meldete die Gegenprobe schlicht eine grosse Abweichung und
    saehe aus wie ein schlechter Feed. Der Feed ist aber in Ordnung -- nur seine
    Beschriftung nicht, und das ist ein voellig anderer Befund.
    """
    kurse = _wechselnd(60)
    punkte = [(BASIS + timedelta(hours=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(hours=i + 1), k) for i, k in enumerate(kurse)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_H1.csv", punkte)) == 0
    aus = capsys.readouterr().out
    assert "Serverzeit-Versatz abgetastet" in aus
    assert "-1 h:     0.00 bp  <- Minimum" in aus
    assert "der Terminal-Feed liegt -1 h gegen UTC" in aus


def test_ohne_versatz_sagt_die_gegenprobe_null_stunden(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """Die Gegenprobe zur Gegenprobe.

    Sonst waere oben nur bewiesen, dass irgendein Versatz gemeldet wird. Hier tragen
    beide Reihen dieselben Stempel, und das Minimum liegt bei 0 h -- es darf dann kein
    BEFUND gemeldet werden.
    """
    kurse = _wechselnd(60)
    punkte = [(BASIS + timedelta(hours=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(hours=i), k) for i, k in enumerate(kurse)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_H1.csv", punkte)) == 0
    aus = capsys.readouterr().out
    assert "Serverzeit-Versatz gegen UTC: 0 h" in aus
    assert "BEFUND" not in aus


def test_auf_tageskerzen_wird_nicht_nach_stunden_gesucht(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine Stundenverschiebung kann auf Tagesstempeln nichts zur Deckung bringen.

    Wuerde trotzdem abgetastet, laege jede Verschiebung ausser null bei „zu wenige"
    (also unendlich), das Minimum fiele auf den ERSTEN Eintrag der Reihe -- ``-4`` --
    und die Funktion meldete einen Versatz von vier Stunden, den es nicht gibt. Ein
    erfundener Befund ist schlimmer als keiner.
    """
    kurse = [100.0 * 1.001**i for i in range(40)]
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte)) == 0
    aus = capsys.readouterr().out
    assert "Serverzeit-Versatz abgetastet" not in aus
    assert "BEFUND" not in aus


# --- Das Urteil an der Schwelle -------------------------------------------
def test_ueber_der_schwelle_ist_der_feed_nicht_brauchbar(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """Von Hand: 10,0 bp gegen 15,0 bp je Schritt -- Abweichung exakt 5,00 bp.

    Fremdreihe mit Faktor 1,001 (je Schritt ``(1,001 - 1) * 10 000 = 10 bp``),
    Terminalreihe mit Faktor 1,0015 (15 bp). Beide Reihen sind geometrisch, die
    Abweichung ist deshalb in JEDEM Paar dieselbe und damit auch im Median: 5,00 bp.
    Die Schwelle des Auftrags liegt bei 2 bp -- also nicht brauchbar, Rueckgabe 1.

    Mutationsprobe: ``median > schwelle`` zu ``median >= schwelle`` gedreht aendert
    hier nichts; gedreht zu ``<`` faellt dieser Fall zusammen mit dem naechsten. Die
    beiden Faelle stehen deshalb als Paar -- einer allein liesse die Richtung offen.
    """
    fremd = [100.0 * 1.001**i for i in range(40)]
    eigen = [100.0 * 1.0015**i for i in range(40)]
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(fremd)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(days=i), k) for i, k in enumerate(eigen)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte)) == 1
    aus = capsys.readouterr().out
    assert "Median 5.00 bp" in aus
    assert "NICHT brauchbar" in aus


def test_unter_der_schwelle_ist_der_feed_brauchbar(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """Von Hand: 10,0 bp gegen 11,0 bp je Schritt -- Abweichung exakt 1,00 bp.

    Dieselbe Rechnung wie oben mit dem Faktor 1,0011 statt 1,0015. Ein Median von
    1,00 bp liegt unter der Schwelle von 2 bp: brauchbar, Rueckgabe 0.
    """
    fremd = [100.0 * 1.001**i for i in range(40)]
    eigen = [100.0 * 1.0011**i for i in range(40)]
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(fremd)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(days=i), k) for i, k in enumerate(eigen)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte)) == 0
    aus = capsys.readouterr().out
    assert "Median 1.00 bp" in aus
    assert "unter der Schwelle" in aus


def test_ohne_gemeinsame_perioden_faellt_die_gegenprobe_rot(
    tmp_path: Path, stub: type[StubTerminal], capsys: pytest.CaptureFixture[str]
) -> None:
    """Zwei Reihen, die sich nicht ueberschneiden, ergeben kein Urteil -- und duerfen
    keines vortaeuschen.

    Der Terminal-Feed liegt hier ein ganzes Jahr neben der Fremdquelle. Es gibt keinen
    gemeinsamen Zeitpunkt, also auch keine vergleichbare Rendite. Ein „brauchbar" aus
    null Vergleichen waere die schlimmste Sorte gruen.
    """
    kurse = _wechselnd(40)
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(days=365 + i), k) for i, k in enumerate(kurse)
    ))
    assert gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte)) == 1
    assert "zu wenige gemeinsame Perioden" in capsys.readouterr().err


def test_das_terminal_wird_immer_wieder_geschlossen(
    tmp_path: Path, stub: type[StubTerminal]
) -> None:
    """Der Abruf steht im ``try``/``finally``. Eine offen gelassene Sitzung blockiert
    das Terminal fuer den naechsten Lauf -- und die Gegenprobe wird mehrmals gefahren.
    """
    kurse = _wechselnd(40)
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(tuple(
        _rate(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)
    ))
    gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte))
    assert stub.letzte is not None
    assert stub.letzte.beendet == 1


def test_der_abrufzeitraum_umschliesst_die_fremdreihe(
    tmp_path: Path, stub: type[StubTerminal]
) -> None:
    """Von Hand: drei Tage Luft auf jeder Seite.

    Ohne den Puffer fielen die Randkerzen aus dem Vergleich -- und beim Suchen eines
    Versatzes ist der Rand genau der Bereich, in dem die Verschiebung greift.
    """
    kurse = _wechselnd(40)
    punkte = [(BASIS + timedelta(days=i), k) for i, k in enumerate(kurse)]
    _setze_reihe(())
    gegenprobe(_csv(tmp_path, "EURUSD_D1.csv", punkte))
    assert stub.letzte is not None
    name, tf, start, ende = stub.letzte.abfragen[0]
    assert name == "EURUSD"
    assert tf is Timeframe.D1
    assert start == BASIS - timedelta(days=3)
    assert ende == BASIS + timedelta(days=39) + timedelta(days=3)


# --- Die Kostenzeile -------------------------------------------------------
class _Zeile:
    """Was ``_kosten_bps`` an einer Kostenzeile liest -- und nur das."""

    def __init__(self, *, rechenbar: bool, k_bps: Decimal | None) -> None:
        self.rechenbar = rechenbar
        self.k_bps = k_bps


class _Broker:
    def __init__(self, instrumente: dict[str, Any]) -> None:
        self.instruments = instrumente


class _Kosten:
    def __init__(self, brokers: dict[str, _Broker]) -> None:
        self.brokers = brokers
        self.slippage_bps = {"TESTFX": Decimal("0.4")}


class _Messung:
    measured = True


def _stelle_kostenzeilen(
    monkeypatch: pytest.MonkeyPatch, werte: dict[str, Decimal | None]
) -> list[tuple[Any, ...]]:
    """``tools.kostentor`` so vorbereiten, dass die Rechnung nachpruefbar ist.

    Ersetzt werden ``lade`` (sonst haengt der Fall an den Messdateien im Repo) und
    ``_zeile`` (sonst muesste die Erwartung aus der echten Kostenformel abgeleitet
    werden -- also aus genau dem Code, den der Fall pruefen soll). ``_kosten_bps``
    importiert beide erst beim Aufruf; die Naht liegt darum am Modul.
    """
    import tools.kostentor as kostentor

    aufrufe: list[tuple[Any, ...]] = []

    def fake_zeile(
        symbol: str, broker_key: str, zeile: Any, messung: Any,
        slippage: Any, kurse: Any,
    ) -> _Zeile:
        aufrufe.append((symbol, broker_key, zeile, messung, slippage, kurse))
        k = werte[broker_key]
        return _Zeile(rechenbar=k is not None, k_bps=k)

    monkeypatch.setattr(kostentor, "_zeile", fake_zeile)
    monkeypatch.setattr(
        kostentor, "lade", lambda: (None, {"TESTFX": _Messung()}, {"EURUSD": 1.0})
    )
    return aufrufe


def test_kosten_bps_nimmt_den_guenstigsten_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Von Hand: drei Broker mit K = 3,00 / 1,75 / 2,40 bp -> 1,75.

    Das kleinste K ist die strengste Annahme fuer die Kandidatenfrage: es senkt die
    nachzuweisende Wirkung (3 x K) und macht damit eine Zeile eher „aufloesbar". Wer
    hier versehentlich das groesste naehme, machte das Feld enger -- konservativ, aber
    eben nicht die gemessene Groesse. Wer den Mittelwert naehme, erfaende eine dritte.
    """
    aufrufe = _stelle_kostenzeilen(monkeypatch, {
        "a": Decimal("3.00"), "b": Decimal("1.75"), "c": Decimal("2.40"),
    })
    kosten = _Kosten({k: _Broker({"TESTFX": object()}) for k in ("a", "b", "c")})
    assert _kosten_bps(kosten, "TESTFX") == pytest.approx(1.75)
    assert [a[1] for a in aufrufe] == ["a", "b", "c"], (
        "Gerechnet wird ueber ``kostentor._zeile`` -- eine zweite Umsetzung derselben "
        "Formel war Fehler 6 aus 09-EIGENE-FEHLER.md."
    )
    assert aufrufe[0][4] == {"TESTFX": Decimal("0.4")}


def test_eine_nicht_rechenbare_zeile_zaehlt_nicht_mit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Zeile ohne K ist keine Null. Sie faellt aus der Auswahl, nicht in sie.

    Wuerde sie als 0 gelesen, waere der guenstigste Broker immer der, ueber den man am
    wenigsten weiss -- und K fiele auf null. Genau dann behauptete die
    Aufloesungstabelle, jede noch so kleine Wirkung sei nachweisbar.
    """
    _stelle_kostenzeilen(monkeypatch, {"a": None, "b": Decimal("2.20")})
    kosten = _Kosten({k: _Broker({"TESTFX": object()}) for k in ("a", "b")})
    assert _kosten_bps(kosten, "TESTFX") == pytest.approx(2.20)


def test_ohne_gemessene_atr_zeile_gibt_es_kein_k(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed: ``None`` heisst „nicht bewertbar" und fuehrt in ``messen()`` dazu,
    dass das Instrument uebersprungen und als solches gedruckt wird.
    """
    _stelle_kostenzeilen(monkeypatch, {})
    kosten = _Kosten({"a": _Broker({"ANDERS": object()})})
    assert _kosten_bps(kosten, "GIBTSNICHT") is None

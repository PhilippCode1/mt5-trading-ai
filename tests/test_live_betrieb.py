"""Der Live-Treiber -- bisher bei null Prozent Abdeckung.

WARUM DIESE DATEI
-----------------
``tools/live_betrieb.py`` ist die Schleife, die wirklich Orders an das Demokonto
schickt, das Journal schreibt und aus dem hinterher jede Auswertung faellt. Sie hatte
**keinen einzigen Test**. Zwei Befunde sind genau dort entstanden und blieben lange
unbemerkt, weil nichts sie haette bemerken koennen:

* **E5** -- der Satz ``vom_broker_geschlossen`` trug keinen Ausstiegswert. Damit war
  jeder Stop-Out "nicht rechenbar", und weil broker-seitige Schluesse ueberwiegend
  Stop-Outs sind, fielen ausgerechnet die Verlierer aus Median und Trefferanteil.
  Gemessen am Lauf vom 17.08.2026: "Trades mit rechenbarem Ergebnis: 0 von 1".
* **K4, Verbraucherseite** -- ``_signal`` rechnete den gleitenden Durchschnitt auf
  ``MarketView(reihe, len(reihe) - 1)``, also auf der noch in Bildung befindlichen
  Kerze. Deren ``close`` ist der momentane Kurs; der Backtest kennt ihn nicht.

Geprueft wird, was ohne MT5-Terminal pruefbar ist: die Signalableitung gegen ein
Fake-Terminal, das Journalschreiben, und die Auswertung ueber den echten Leser. Der
lesende Terminalpfad selbst gehoert zu ``tests/test_mt5_venue.py`` und
``tests/test_bar_geschlossen.py``.

WAS HIER BEWUSST NICHT GEPRUEFT WIRD
-------------------------------------
Kein Test setzt eine Sicherheitssperre ausser Kraft, und keiner sendet eine Order:
``_eroeffne`` und ``_schliesse`` gehen ueber ``run_signal`` bzw. ``submit_order`` und
brauchen den ganzen Orderpfad. Geprueft wird ausschliesslich, was die Maschine
**protokolliert** und **rechnet**.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.backtest.engine import Signal
from mt5_trading_ai.betrieb.journal import lies_alle, lies_journal
from mt5_trading_ai.execution.risk_manager import RiskManager
from mt5_trading_ai.venue.protocol import Bar, Timeframe, VenueUnavailableError
from tools.betrieb_auswerten import auswerten
from tools.betrieb_reihe import auswerten as reihe_auswerten
from tools.live_betrieb import (
    LANGSAM,
    Journal,
    Lage,
    _buch_abgleichen,
    _schliesse,
    _signal,
    _signal_mit_protokoll,
)

T0 = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)


# --- Fakes ----------------------------------------------------------------
def _bar(nr: int, close: float, *, is_closed: bool) -> Bar:
    """Eine Stundenkerze. ``is_closed`` ist Pflichtfeld -- hier wie im Vertrag."""
    preis = Decimal(str(close))
    return Bar(
        symbol="EURUSD", timeframe=Timeframe.H1, ts=T0 + timedelta(hours=nr),
        open=preis, high=preis, low=preis, close=preis, tick_volume=1,
        is_closed=is_closed,
    )


@dataclass
class FakeVenue:
    """Nur das, was die geprueften Funktionen wirklich anfassen.

    Bewusst kein ``Mt5Venue``-Erbe und kein Mock-Framework: was hier fehlt, faellt
    sofort als ``AttributeError`` auf, statt still ein Standardverhalten zu erfinden.
    """

    bars: tuple[Bar, ...] = ()
    wirft: Exception | None = None
    buch_uebernommen: int = 0

    def get_bars(
        self, symbol: str, timeframe: Timeframe, *, start: datetime, end: datetime
    ) -> tuple[Bar, ...]:
        if self.wirft is not None:
            raise self.wirft
        return self.bars

    def adopt_book(self) -> dict[str, Decimal]:
        self.buch_uebernommen += 1
        return {}


def _journal(tmp_path: Path) -> Journal:
    return Journal(tmp_path / "journal-test.jsonl", lauf="lauf-t", version="testv")


def _saetze(journal: Journal) -> list[dict[str, Any]]:
    text = journal.pfad.read_text(encoding="utf-8")
    return [json.loads(z) for z in text.splitlines() if z.strip()]


def _lage(unrealisiert: str = "-2.68") -> Lage:
    return Lage(
        symbol="XAUUSD", ist_kauf=True, volumen=Decimal("0.01"),
        seit=T0 + timedelta(hours=1), position_id="10060725485",
        einstiegspreis=Decimal("4415.18"), unrealisiert=Decimal(unrealisiert),
        swap=Decimal("-0.11"),
    )


# --- K4, Verbraucherseite: auf welcher Kerze gerechnet wird ---------------
#
# Aufbau: 26 fallende abgeschlossene Kerzen ergeben MA12 < MA26, also SHORT. Die
# 27. Kerze ist die LAUFENDE und traegt einen Ausreisser nach oben, der -- wenn man
# sie mitrechnet -- MA12 ueber MA26 hebt und das Signal auf LONG dreht.
FALLEND = tuple(_bar(i, 1.30 - i * 0.001, is_closed=True) for i in range(LANGSAM))
AUSREISSER = _bar(LANGSAM, 1.60, is_closed=False)


def test_die_laufende_kerze_geht_nicht_ins_signal() -> None:
    """DER Eichfall fuer K4 auf der Verbraucherseite.

    Gegen die alte Fassung: sie baute die Reihe aus JEDER gelieferten Bar und rechnete
    ueber ``len(reihe) - 1``, also einschliesslich der laufenden. Der Ausreisser drehte
    das Signal, und der Test bekaeme LONG statt SHORT.
    """
    lage = _signal(FakeVenue(bars=(*FALLEND, AUSREISSER)), "EURUSD", T0)
    assert lage.signal is Signal.SHORT
    assert lage.kerzen_verwendet == LANGSAM
    assert lage.kerzen_laufend == 1


def test_die_gegenprobe_ohne_laufende_kerze_ergibt_dasselbe() -> None:
    """Sonst waere oben nur bewiesen, dass irgendetwas weggeworfen wird.

    Dieselben abgeschlossenen Kerzen, aber ohne die laufende: identisches Signal und
    identische Kerzenzahl. Waere die Filterung zu gierig (etwa "immer die letzte
    weg"), faellt dieser Test.
    """
    lage = _signal(FakeVenue(bars=FALLEND), "EURUSD", T0)
    assert lage.signal is Signal.SHORT
    assert lage.kerzen_verwendet == LANGSAM
    assert lage.kerzen_laufend == 0


def test_gerechnet_wird_auf_der_juengsten_abgeschlossenen_kerze() -> None:
    """Nicht irgendeine abgeschlossene -- die letzte vor der laufenden."""
    lage = _signal(FakeVenue(bars=(*FALLEND, AUSREISSER)), "EURUSD", T0)
    assert lage.kerze_ts == FALLEND[-1].ts


def test_zu_wenige_abgeschlossene_kerzen_ergeben_kein_signal() -> None:
    """Fail-closed: die laufende Kerze fuellt die Historie NICHT auf.

    Gegen die alte Fassung: 26 gelieferte Bars reichten ihr, egal ob die letzte noch
    lief -- sie haette ein Signal ausgeworfen statt FLAT.
    """
    bars = (*FALLEND[: LANGSAM - 1], _bar(LANGSAM, 1.60, is_closed=False))
    lage = _signal(FakeVenue(bars=bars), "EURUSD", T0)
    assert lage.signal is Signal.FLAT
    assert lage.kerze_ts is None
    assert "abgeschlossene" in lage.detail


def test_ohne_kerzen_gibt_es_kein_signal_und_keinen_absturz() -> None:
    """Ein Defekt am Platz haelt den Takt an, statt den Lauf zu toeten.

    FLAT ist hier kein geratener Vorgabewert: FLAT eroeffnet nichts und schliesst
    nichts. Der Grund steht im Detail und geht ins Journal.
    """
    lage = _signal(
        FakeVenue(wirft=VenueUnavailableError("kein Tick")), "EURUSD", T0
    )
    assert lage.signal is Signal.FLAT
    assert lage.kerze_ts is None
    assert "keine Kerzen" in lage.detail


def test_das_journal_nennt_die_kerze_auf_der_gerechnet_wurde(tmp_path: Path) -> None:
    """Zweiter Eichfall fuer K4: ohne diesen Satz war der Befund nicht nachweisbar.

    Gegen die alte Fassung: es gab weder ``_signal_mit_protokoll`` noch die Satzart
    ``signalbasis`` -- der Import allein scheitert. Und selbst mit Import stuende
    nirgends, welche Kerze gerechnet wurde; genau darum liess sich monatelang nicht
    feststellen, worauf die Maschine ihr Signal gebaut hat.
    """
    j = _journal(tmp_path)
    _signal_mit_protokoll(
        FakeVenue(bars=(*FALLEND, AUSREISSER)), "EURUSD", T0, j, zweck="eintritt"
    )
    satz = _saetze(j)[0]
    assert satz["art"] == "signalbasis"
    assert satz["zweck"] == "eintritt"
    assert satz["signal"] == "SHORT"
    assert satz["kerze_ts"] == FALLEND[-1].ts.isoformat(timespec="seconds")
    assert satz["kerzen_verwendet"] == LANGSAM
    assert satz["kerzen_laufend_verworfen"] == 1


def test_auch_ein_flat_wird_protokolliert(tmp_path: Path) -> None:
    """Ein Takt ohne Satz war frueher nicht deutbar.

    Kein Signal, Instrument schon offen, Kerzenabfrage gescheitert -- alle drei sahen
    im Journal gleich aus, naemlich wie nichts.
    """
    j = _journal(tmp_path)
    _signal_mit_protokoll(
        FakeVenue(wirft=VenueUnavailableError("weg")), "EURUSD", T0, j,
        zweck="ausstieg",
    )
    satz = _saetze(j)[0]
    assert satz["art"] == "signalbasis"
    assert satz["signal"] == "FLAT"
    assert satz["kerze_ts"] is None


# --- E5: der broker-seitige Schluss ---------------------------------------
def _broker_schluss(tmp_path: Path, unrealisiert: str = "-2.68") -> Journal:
    """Einen echten ``vom_broker_geschlossen``-Satz schreiben lassen."""
    j = _journal(tmp_path)
    weg = _lage(unrealisiert)
    j.schreib("eroeffnet", symbol=weg.symbol, signal="LONG", volumen=weg.volumen,
              position_id=weg.position_id, einstiegspreis=weg.einstiegspreis,
              seit=weg.seit)
    _buch_abgleichen(
        FakeVenue(), RiskManager(), {weg.symbol: weg}, {}, j, waehrung="EUR",
    )
    return j


def test_broker_schluss_liefert_ein_rechenbares_ergebnis(tmp_path: Path) -> None:
    """DER Eichfall fuer E5.

    Gegen die alte Fassung: der Satz trug ``einstiegspreis``, ``volumen``, ``war_kauf``
    und ``zuletzt_unrealisiert`` -- aber keinen Ausstiegswert. ``Trade`` kannte weder
    ``beurteilbar`` noch ``gewinn``; der Zugriff waere ein ``AttributeError``, und
    fachlich galt der Trade als nicht rechenbar. Genau die Stop-Outs -- also die
    Verlierer -- fielen damit aus jeder Statistik.

    Und die Aussage bleibt praezise: ein PREIS-Ergebnis gibt es weiterhin nicht
    (``vollstaendig is False``). Beurteilbar ist der Trade trotzdem.
    """
    t = lies_journal(_broker_schluss(tmp_path).pfad).trades()[0]
    assert t.vom_broker is True
    assert t.vollstaendig is False, "Der Fuellpreis des Stops ist nach wie vor unbekannt"
    assert t.ergebnis_bps is None
    assert t.beurteilbar is True
    assert t.gewinn is False
    assert t.ergebnis_geld == Decimal("-2.68")
    assert t.ergebnis_geld_waehrung == "EUR"
    assert t.urteilsquelle == "geld"


def test_kein_ausstiegspreis_wird_erfunden(tmp_path: Path) -> None:
    """Sperre gegen die naheliegende FALSCHE Reparatur.

    Ehrlich eingeordnet: dieser Test waere gegen die alte Fassung GRUEN gewesen -- sie
    schrieb ebenfalls keinen Ausstiegspreis. Sein Zweck ist die Gegenrichtung: aus
    Buchwert, Volumen und Kontraktgroesse liesse sich ein Preis zurueckrechnen, und
    der stuende dann in ``ausstiegspreis``, ununterscheidbar von einem gemessenen
    Fill. Er wuerde ueber ``ergebnis_bps`` in denselben Median wandern wie die echten
    Preise, obwohl er vom Ende des VORIGEN Takts stammt und ein Stop ueblicherweise
    schlechter fuellt als der zuletzt gesehene Kurs.

    Nachgemessen statt behauptet: mit einem eingebauten ``ausstiegspreis =
    einstiegspreis + unrealisiert / (volumen * 100)`` faellt dieser Test -- und mit
    ihm vier weitere, weil der erfundene Preis den Trade ploetzlich als
    preis-beurteilt ausweist.
    """
    satz = next(s for s in _saetze(_broker_schluss(tmp_path))
                if s["art"] == "vom_broker_geschlossen")
    assert "ausstiegspreis" not in satz
    t = lies_journal(_broker_schluss(tmp_path).pfad).trades()[0]
    assert t.ausstieg is None


def test_die_herkunft_des_betrags_steht_dabei(tmp_path: Path) -> None:
    """Eine Schaetzung ohne Herkunftsangabe ist spaeter eine Messung.

    Gegen die alte Fassung: das Feld gab es nicht.
    """
    satz = next(s for s in _saetze(_broker_schluss(tmp_path))
                if s["art"] == "vom_broker_geschlossen")
    assert satz["ergebnis_geld_quelle"] == "zuletzt_beobachtet"
    assert satz["ergebnis_geld_waehrung"] == "EUR"
    assert satz["zuletzt_swap"] == "-0.11"
    assert "keine Messung" in satz["hinweis"]


def test_ein_gewinnbringender_broker_schluss_zaehlt_als_treffer(
    tmp_path: Path,
) -> None:
    """Die Gegenprobe zur Richtung.

    Waere ``gewinn`` versehentlich auf "vom Broker geschlossen heisst Verlust"
    verdrahtet, faellt dieser Test. Ein Take-Profit ist auch ein broker-seitiger
    Schluss.
    """
    t = lies_journal(_broker_schluss(tmp_path, "+7.40").pfad).trades()[0]
    assert t.gewinn is True


def test_auch_der_eigene_schluss_traegt_ein_geldergebnis(tmp_path: Path) -> None:
    """Sonst besteht jede Geldstatistik nur aus Stop-Outs, also nur aus Verlierern.

    Das waere derselbe blinde Fleck wie zuvor, nur mit umgekehrtem Vorzeichen. Gegen
    die alte Fassung: der ``geschlossen``-Satz trug kein Geldfeld.
    """
    j = _journal(tmp_path)

    class Angenommen:
        venue_order_id = "O1"
        average_price = Decimal("4420.00")
        filled_volume = Decimal("0.01")

    class Sendend:
        def submit_order(self, anfrage: Any) -> Angenommen:
            return Angenommen()

    assert _schliesse(Sendend(), RiskManager(), _lage("+4.82"), T0,
                      "signalwechsel", j, waehrung="EUR") is True
    satz = next(s for s in _saetze(j) if s["art"] == "geschlossen")
    assert satz["ergebnis_geld"] == "4.82"
    assert satz["ergebnis_geld_waehrung"] == "EUR"
    assert satz["ergebnis_geld_quelle"] == "zuletzt_beobachtet"


def test_beim_eigenen_schluss_schlaegt_der_preis_die_schaetzung(
    tmp_path: Path,
) -> None:
    """Vorrangregel, und sie ist nachpruefbar gemacht.

    Der Satz traegt beide Zahlen und sie widersprechen sich absichtlich: der Buchwert
    sagt Verlust, die Preise sagen Gewinn. Gerechnet wird nach dem gemessenen Preis --
    er stammt vom Ausstieg, der Buchwert vom Takt davor.
    """
    j = _journal(tmp_path)
    j.schreib("geschlossen", symbol="EURUSD", war_kauf=True, volumen="0.1",
              position_id="P1", einstiegspreis="1.10000", ausstiegspreis="1.10110",
              grund="signalwechsel", ergebnis_geld="-5.00",
              ergebnis_geld_waehrung="EUR", ergebnis_geld_quelle="zuletzt_beobachtet")
    t = lies_journal(j.pfad).trades()[0]
    assert t.urteilsquelle == "preis"
    assert t.gewinn is True


# --- E5, Punkt 2: alte Journale -------------------------------------------
def test_ein_alter_satz_ohne_jeden_wert_bleibt_nicht_rechenbar(
    tmp_path: Path,
) -> None:
    """Kernregel 22: alte Saetze werden nicht umgeschrieben, also muessen sie passen.

    Das ist der erste echte Satz aus ``betrieb/journal-20260817T160253.jsonl`` -- er
    trug nur das Symbol. Er darf kein Ergebnis bekommen, und schon gar nicht null:
    eine geratene Null zoege jeden Median zur Mitte und jeden Trefferanteil nach
    oben, ohne dass es jemand saehe.
    """
    p = tmp_path / "journal-alt.jsonl"
    p.write_text(json.dumps({"ts": T0.isoformat(), "art": "vom_broker_geschlossen",
                             "symbol": "XAUUSD"}) + "\n", encoding="utf-8")
    t = lies_journal(p).trades()[0]
    assert t.ergebnis_geld is None
    assert t.gewinn is None
    assert t.beurteilbar is False
    assert t.urteilsquelle is None


def test_ein_alter_satz_mit_buchwert_wird_gedeutet_und_sagt_es(tmp_path: Path) -> None:
    """Die beiden anderen echten Altsaetze tragen ``zuletzt_unrealisiert``.

    Der Wert ist derselbe Buchwert wie heute, aber die DEUTUNG "das ist das Ergebnis"
    faellt beim Lesen, nicht beim Schreiben. Sie faellt darum sichtbar: die
    Herkunftsmarke sagt, dass hier gedeutet wurde. Gegen die alte Fassung: der Leser
    sah das Feld gar nicht an, der Trade blieb nicht rechenbar.
    """
    p = tmp_path / "journal-alt.jsonl"
    p.write_text(json.dumps({
        "ts": T0.isoformat(), "art": "vom_broker_geschlossen", "symbol": "XAUUSD",
        "volumen": "0.01", "war_kauf": True, "position_id": "10061561023",
        "einstiegspreis": "4406.02", "zuletzt_unrealisiert": "-2.43",
    }) + "\n", encoding="utf-8")
    t = lies_journal(p).trades()[0]
    assert t.ergebnis_geld == Decimal("-2.43")
    assert t.gewinn is False
    assert t.ergebnis_geld_quelle == "altjournal:zuletzt_unrealisiert"
    assert t.ergebnis_geld_waehrung is None, "Alte Saetze nennen keine Waehrung"


def test_ein_gemessener_nullwert_ist_kein_fehlender_wert(tmp_path: Path) -> None:
    """Der Unterschied, an dem "nicht rechenbar" haengt.

    Null ist ein Ergebnis (Trade ging plus/minus null aus, also kein Treffer). Fehlend
    ist kein Ergebnis. Wer beides gleich behandelt, hat den Befund nur verschoben.
    """
    t = lies_journal(_broker_schluss(tmp_path, "0").pfad).trades()[0]
    assert t.ergebnis_geld == Decimal("0")
    assert t.beurteilbar is True
    assert t.gewinn is False


# --- Die Auswertung -------------------------------------------------------
def test_die_auswertung_zaehlt_den_stop_out_mit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Die Kachel, an der der Befund aufgefallen ist.

    Gegen die alte Fassung stand hier "Trades mit rechenbarem Ergebnis: 0 von 1" und
    darunter "Kein einziger vollstaendig". Jetzt steht da, dass es kein PREIS-Ergebnis
    gibt und trotzdem ein Urteil -- und der Trefferanteil enthaelt den Verlierer.
    """
    j = _broker_schluss(tmp_path)
    j.schreib("takt", nr=1, equity="50000")
    j.schreib("takt", nr=2, equity="49997.32")
    assert auswerten(j.pfad) == 0
    aus = capsys.readouterr().out
    assert "mit Preisergebnis (bp)       : 0" in aus
    assert "nur mit Geldergebnis         : 1" in aus
    assert "ohne jedes Ergebnis          : 0" in aus
    assert "Treffer 0 % ueber 1 beurteilbare" in aus
    assert "Summe dieser Schaetzungen: -2.68 EUR" in aus


def test_die_auswertung_summiert_keine_gemischten_waehrungen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Eine Summe ueber gemischte Einheiten sieht aus wie Geld und ist keines.

    Der zweite Satz kommt ohne Waehrung -- genau der Fall eines Altjournals.
    """
    j = _broker_schluss(tmp_path)
    j.schreib("vom_broker_geschlossen", symbol="EURUSD", war_kauf=True,
              volumen="0.1", position_id="P7", einstiegspreis="1.1",
              zuletzt_unrealisiert="-1.10")
    assert auswerten(j.pfad) == 0
    aus = capsys.readouterr().out
    assert "Keine Summe:" in aus
    assert "Summe dieser Schaetzungen" not in aus


def test_ohne_equity_punkte_verschwinden_die_trades_nicht(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Frueher hoerte die Auswertung an dieser Stelle mit ``return`` auf.

    Ein Lauf, der nach dem ersten Takt abbrach, aber einen Stop-Out gesehen hat,
    meldete dann ueber den Trade ueberhaupt nichts -- die Equity-Luecke nahm die
    Trade-Zahlen mit. Gegen die alte Fassung faellt dieser Test: nach "Zu wenige
    Messpunkte" kam keine Zeile mehr.
    """
    assert auswerten(_broker_schluss(tmp_path).pfad) == 0
    aus = capsys.readouterr().out
    assert "Zu wenige Messpunkte" in aus
    assert "nur mit Geldergebnis         : 1" in aus


def test_die_reihe_ueber_mehrere_laeufe_zaehlt_den_stop_out_mit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dieselbe Frage ueber alle Journale -- ``tools/betrieb_reihe.py``.

    Gegen die alte Fassung stand hier "davon rechenbar: 0 (unvollstaendig: 1)" und
    darunter "Kein einziger Trade ist rechenbar".
    """
    j = _broker_schluss(tmp_path)
    j.schreib("takt", nr=1, equity="50000")
    assert reihe_auswerten(lies_alle(tmp_path), nur_scharf=False) == 0
    aus = capsys.readouterr().out
    assert "mit Preisergebnis (bp): 0" in aus
    assert "nur mit Geldergebnis  : 1" in aus
    assert "Trefferanteil        : 0.0 % ueber 1 beurteilbare" in aus
    assert "Kein einziger Trade ist beurteilbar" not in aus

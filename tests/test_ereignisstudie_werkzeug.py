"""Das Werkzeug, das die sieben Studien gefahren hat — bisher ohne einen Test.

WARUM DIESE DATEI NOETIG IST
----------------------------
``tools/ereignisstudie.py`` hat die Zahlen erzeugt, aus denen das Urteil des Vorhabens
folgt: groesster Bruttoeffekt 1,36 bp gegen eine Schwelle von 5,51 bp, alle sieben
Nettoeffekte negativ, hoechste DSR 0,686 gegen 0,95. Das KERNMODUL
``backtest/ereignisstudie.py`` ist geprueft; das Werkzeug darum herum stand bei null
Prozent — und dort sitzt die Verdrahtung zum Versuchsregister, die Datenbeschaffung
und die Berichtsausgabe.

DER SELBSTTEST LAEUFT JETZT IM PRUEFSTAND
------------------------------------------
``python tools/ereignisstudie.py --selbsttest`` gab es, aber keine CI-Stufe rief ihn
auf. Ein Test, den niemand faehrt, ist Dokumentation. Er laeuft hier als regulaerer
Fall (0,35 s, kein Netz, kein MT5-Terminal, kein Register) — und, weil ein Waechter
nichts wert ist, solange niemand ihn hat rot werden sehen, mit drei absichtlich
verfaelschten Messungen daneben, die er faengt.

KEIN FALL DIESER DATEI FASST DAS REGISTER DES REPOS AN
-------------------------------------------------------
``TRIALS.jsonl`` ist per ``.gitignore`` nicht versioniert; ein Fall, der sie braucht,
faellt auf jedem frischen Klon. Die Fixtur ``_kein_repo_register`` biegt
``default_ledger_path`` auf einen Pfad um, den es NICHT gibt — greift ein Fall
versehentlich doch aufs Register, faellt er sofort auf, statt lokal gruen zu sein.
Aus demselben Grund haengt kein Fall an der Rechneruhr, einer Umgebungsvariablen
oder dem Netz.

Faelle unter „Eichfall" waeren gegen die vorige Fassung des Werkzeugs rot gewesen.
Faelle unter „Beleg" halten die Zahlen fest, mit denen das Urteil begruendet ist.
"""

from __future__ import annotations

import dataclasses
import json
import math
import subprocess
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.backtest import ereignisstudie as kern
from mt5_trading_ai.backtest.ereignisstudie import (
    Bestaetigung,
    Ergebnis,
    Kerze,
    StudienError,
)
from mt5_trading_ai.backtest.kalender import Kandidat
from mt5_trading_ai.gates import trials as register
from mt5_trading_ai.venue.mt5 import Mt5Rate, Mt5Tick
from mt5_trading_ai.venue.protocol import Timeframe
from tools import ereignisstudie as werkzeug

# ---------------------------------------------------------------------------
# Gemeinsame Vorrichtungen
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _kein_repo_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Das Register des Repos ist fuer jeden Fall dieser Datei unerreichbar.

    Der Pfad zeigt bewusst ins Leere statt auf eine leere Datei: so ist jeder
    unbeabsichtigte Registerzugriff ein Fehlschlag und keine stille Null. Das Werkzeug
    hat den Namen mit ``from ... import`` gebunden, das Register-Modul benutzt seinen
    eigenen — beide muessen umgebogen werden.
    """
    ins_leere = tmp_path / "ohne-register" / "TRIALS.jsonl"
    monkeypatch.setattr(register, "default_ledger_path", lambda: ins_leere)
    monkeypatch.setattr(werkzeug, "default_ledger_path", lambda: ins_leere)
    return ins_leere


#: Ein Kandidat fuer den Pruefstand. Die Zone ist UTC statt Europe/London, damit die
#: Ereigniszeitpunkte nicht mit der Sommerzeit wandern — geprueft wird hier die
#: Verdrahtung des Werkzeugs, nicht die Zeitzonenrechnung des Kalenders (die steht in
#: ``tests/test_kalender.py``). Der Schluessel ist ``K1``, weil die ``strategy_id``
#: daraus gebaut wird und im Register echt aussehen muss.
PRUEFKANDIDAT = Kandidat(
    schluessel="K1",
    name="Pruefstand",
    instrumente=("SYNTH",),
    zone_name="UTC",
    uhrzeit=time(16, 0),
    regel="werktaeglich",
    fenster_stunden=1.0,
    konvention="Pruefstand",
    beleg="Pruefstand",
)


def _reihe(werktage: int) -> list[Kerze]:
    """Stundenkerzen mit BEKANNTEM Umkehreffekt um 16:00 UTC.

    Gleiche Bauart wie ``werkzeug._synthetisch``, nur kurz genug, dass die 1.000
    Randomisierungsziehungen von ``bestaetige`` in einem Fuenftel einer Sekunde
    durchlaufen. Von Hand: Vorstunde +/-20 bp, Fensterstunde 12 bp DAGEGEN, also
    bereinigt genau +12,00 bp je Ereignis; Median 12,00, Trefferanteil 100 %.
    """
    kerzen: list[Kerze] = []
    kurs = 100.0
    tag = datetime(2020, 1, 6, tzinfo=UTC)  # ein Montag
    gezaehlt = 0
    while gezaehlt < werktage:
        if tag.weekday() < 5:
            for stunde in range(24):
                ts = tag.replace(hour=stunde)
                if stunde == 15:
                    richtung = 1.0 if gezaehlt % 2 == 0 else -1.0
                    schluss = kurs * (1 + richtung * 20e-4)
                elif stunde == 16:
                    richtung = -1.0 if gezaehlt % 2 == 0 else 1.0
                    schluss = kurs * (1 + richtung * 12e-4)
                else:
                    schluss = kurs * (1 + math.sin(gezaehlt * 7 + stunde) * 3e-4)
                kerzen.append(Kerze(ts=ts, open=kurs, close=schluss))
                kurs = schluss
            gezaehlt += 1
        tag += timedelta(days=1)
    return kerzen


@pytest.fixture
def herkunft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kosten, Pruefsumme und Codestand als feste Werte.

    Alle drei sind fremde Quellen (Kostendatei, Manifest, ``git``). Sie hier
    festzulegen macht die Erwartungswerte von Hand nachrechenbar: K = 1,00 bp, also
    Nettoeffekt = Brutto - 1,00.
    """
    monkeypatch.setattr(werkzeug, "_kosten_bps", lambda kosten, symbol: 1.0)
    monkeypatch.setattr(werkzeug, "_data_checksum", lambda symbol: f"summe-{symbol}")
    monkeypatch.setattr(werkzeug, "_code_commit", lambda: "c0ffee1234567890")


def _darf_nicht_messen(**kwargs: Any) -> Any:
    """Ein ``studie``-Ersatz, der nur eines kann: auffallen, wenn er gerufen wird."""
    raise AssertionError("gemessen, obwohl vorher haette abgebrochen werden muessen")


def _leeres_register(tmp_path: Path) -> Path:
    """Ein LEERES Register ist zulaessig (erste Kampagne), ein fehlendes nicht."""
    ledger = tmp_path / "TRIALS.jsonl"
    ledger.write_text("", encoding="utf-8")
    return ledger


def _fremde_zeile(ledger: Path, nummer: int) -> None:
    """Ein Lauf einer ANDEREN Reihe — er zaehlt in der Deflation als ``fremd``."""
    register.append(
        register.new_trial(
            strategy_id=f"andere-reihe/L{nummer}",
            version="fremd-v1",
            instruments=["EURUSD"],
            period_start=datetime(2010, 1, 1, tzinfo=UTC),
            period_end=datetime(2020, 1, 1, tzinfo=UTC),
            leverage=1,
            parameters={"lauf": nummer},
            outcome="completed",
            data_checksum="summe-fremd",
            code_commit="abc123",
        ),
        ledger,
    )


# ---------------------------------------------------------------------------
# 1) Der Selbsttest — jetzt im Pruefstand statt nur in der Aufrufzeile
# ---------------------------------------------------------------------------


def test_selbsttest_laeuft_ohne_netz_ohne_terminal_und_ohne_register(
    capsys: pytest.CaptureFixture[str], _kein_repo_register: Path
) -> None:
    """Der eingebaute Selbsttest, gefahren statt nur dokumentiert.

    Er rechnet gegen eine synthetische Reihe mit bekanntem Effekt und darf dabei
    KEINEN Versuch registrieren. Beides wird hier geprueft: der Rueckgabewert und die
    Tatsache, dass das Register — auf einen nicht existierenden Pfad gebogen — danach
    immer noch nicht existiert. Griffe der Selbsttest doch zu, legte ``append`` die
    Datei an, und der Fall faellt.

    Zugleich der Nachweis, dass ``--selbsttest`` vor dem Registertor abbiegt: laege
    ``verlange_register`` davor, waere die Rueckgabe 1.
    """
    assert werkzeug.main(["--selbsttest"]) == 0
    ausgabe = capsys.readouterr()
    assert "BESTANDEN" in ausgabe.out
    assert "Kein Versuch registriert" in ausgabe.out
    assert ausgabe.err == ""
    assert not _kein_repo_register.exists()


@pytest.mark.parametrize(
    "verfaelschung,erwarteter_grund",
    [
        ("vorzeichen", "neben dem Ziel"),
        ("immer_zwoelf", "wo nichts sein darf"),
        ("trefferanteil", "Trefferanteil"),
    ],
)
def test_der_selbsttest_faengt_eine_verfaelschte_messung(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    verfaelschung: str,
    erwarteter_grund: str,
) -> None:
    """Mutationsprobe, im Pruefstand festgeschrieben — nach dem Muster von
    ``test_readme_numbers.py::test_das_zahlen_tor_faengt_eine_erfundene_zeilenzahl``.

    Ein Waechter, den niemand hat rot werden sehen, ist kein Waechter. Drei
    Verfaelschungen, jede eine eigene Fehlerklasse:

    ``vorzeichen``
        Die Studie meldet -12 statt +12 bp. Genau der Fehler, den man einer einzelnen
        Zahl am wenigsten ansieht, und der Grund, warum der Selbsttest ein VORZEICHEN
        prueft und nicht nur einen Betrag.
    ``immer_zwoelf``
        Ein Melder, der stur 12 bp und 100 % ausgibt, egal was er bekommt. Die
        Hauptmessung besteht er; ihn faengt allein die Gegenprobe mit den um drei
        Stunden versetzten Fenstern — die Daseinsberechtigung dieser Gegenprobe.
    ``trefferanteil``
        Effekt und Vorzeichen stimmen, aber nur die Haelfte der Ereignisse trifft. Bei
        einem so klaren Effekt ist das unmoeglich; der Median allein saehe es nicht.
    """
    echte_studie = werkzeug.studie

    def verfaelscht(**kwargs: Any) -> Any:
        if verfaelschung == "immer_zwoelf":
            erg, werte = echte_studie(**kwargs)
            return dataclasses.replace(
                erg, brutto_bps=12.0, trefferanteil=1.0
            ), werte
        erg, werte = echte_studie(**kwargs)
        if verfaelschung == "vorzeichen":
            return dataclasses.replace(erg, brutto_bps=-erg.brutto_bps), werte
        return dataclasses.replace(erg, trefferanteil=0.5), werte

    monkeypatch.setattr(werkzeug, "studie", verfaelscht)
    assert werkzeug.selbsttest() == 1
    fehler = capsys.readouterr().err
    assert "FEHLGESCHLAGEN" in fehler
    assert erwarteter_grund in fehler


def test_die_synthetische_reihe_traegt_genau_zwoelf_basispunkte() -> None:
    """Von Hand nachgerechnet — die Reihe, gegen die der Selbsttest misst.

    Der Selbsttest vergleicht mit dem Literal ``erwartet = 12.0``. Ob die Reihe diesen
    Effekt wirklich traegt, sagt er nicht; das steht hier.

    ZAHL DER KERZEN: ``range(1400)`` ab Donnerstag, 01.01.2015. 1400 Tage sind genau
    200 Wochen, also 200 x 5 = 1.000 Werktage, je 24 Stundenkerzen = 24.000 Kerzen und
    1.000 Ereignisse.

    DER EFFEKT, Tag fuer Tag: Stunde 15 laeuft um 20 bp (Richtung wechselt taeglich),
    Stunde 16 um 12 bp DAGEGEN. Die Vorstunde gibt das Vorzeichen
    ``-sign(Vorstundenrendite)``; an geraden Tagen also ``-1`` auf eine Rohrendite von
    ``-12`` bp, an ungeraden ``+1`` auf ``+12`` bp. Bereinigt in beiden Faellen genau
    ``+12,00`` bp — Trefferanteil 100 %, Median 12,00.
    """
    kerzen, termine = werkzeug._synthetisch()
    assert len(termine) == 1000
    assert len(kerzen) == 1000 * 24
    assert {t.hour for t in termine} == {16}

    stempel = [k.ts for k in kerzen]
    # Erster Werktag (tag = 0, gerade) und der naechste (tag = 1, ungerade).
    for termin, vor_richtung, roh_richtung, vorzeichen in (
        (termine[0], +1.0, -1.0, -1),
        (termine[1], -1.0, +1.0, +1),
    ):
        i = stempel.index(termin)
        vor, fenster = kerzen[i - 1], kerzen[i]
        assert (vor.close - vor.open) / vor.open == pytest.approx(
            vor_richtung * 20e-4, rel=1e-9
        )
        assert (fenster.close - fenster.open) / fenster.open == pytest.approx(
            roh_richtung * 12e-4, rel=1e-9
        )
        wert = kern.messe_ereignis(
            kerzen, stempel, termin, fenster_stunden=1.0, balkenstunden=1.0
        )
        assert wert is not None
        assert wert.vorzeichen == vorzeichen
        assert wert.roh_bps == pytest.approx(roh_richtung * 12.0, rel=1e-9)
        assert wert.bereinigt_bps == pytest.approx(12.0, rel=1e-9)


# ---------------------------------------------------------------------------
# 2) Datenbeschaffung — ohne MT5-Terminal pruefbar
# ---------------------------------------------------------------------------


def _rate(ts: datetime, *, close: str = "1.15") -> Mt5Rate:
    return Mt5Rate(
        ts=ts,
        open=Decimal("1.10"),
        high=Decimal("1.20"),
        low=Decimal("1.00"),
        close=Decimal(close),
        tick_volume=1,
    )


def _terminal(
    monkeypatch: pytest.MonkeyPatch,
    antwort: Any,
    *,
    initialisierbar: bool = True,
) -> dict[str, Any]:
    """Setze ein Stellvertreter-Terminal ein und gib sein Protokoll zurueck.

    Bewusst ohne Mock-Rahmenwerk, wie in ``test_aufloesung_werkzeug.py``: die Faelle
    unten fragen, WELCHE Zeitscheiben abgefragt wurden, mit welchem ``allow_write`` das
    Terminal aufgemacht und ob es wieder geschlossen wurde. Eine mitgeschriebene Liste
    liest sich dafuer besser als ein Aufrufprotokoll.
    """
    protokoll: dict[str, Any] = {
        "allow_write": "nie geoeffnet",
        "abfragen": [],
        "shutdowns": 0,
    }

    class _Stellvertreter:
        def __init__(self, allow_write: bool = True) -> None:
            protokoll["allow_write"] = allow_write

        def initialize(self) -> bool:
            return initialisierbar

        def tick(self, name: str) -> Mt5Tick:
            """Die Platzzeit -- seit Stufe 2 fragt ``_lade_kerzen`` danach.

            Bewusst weit voraus, damit jede erzeugte Kerze als abgeschlossen gilt:
            diese Faelle messen die Scheibenbildung und die Zeitdrehung, nicht die
            Kante. Die misst ``tests/test_zeitschranken.py``.
            """
            return Mt5Tick(
                ts=datetime(2999, 1, 1, tzinfo=UTC), bid=Decimal("1"), ask=Decimal("1")
            )

        def rates(
            self, name: str, timeframe: Timeframe, start: datetime, end: datetime
        ) -> tuple[Mt5Rate, ...]:
            nummer = len(protokoll["abfragen"])
            protokoll["abfragen"].append((start, end))
            result: tuple[Mt5Rate, ...] = antwort(name, timeframe, start, end, nummer)
            return result

        def shutdown(self) -> None:
            protokoll["shutdowns"] += 1

    monkeypatch.setattr(werkzeug, "RealMt5Terminal", _Stellvertreter)
    return protokoll


def test_lade_kerzen_dreht_die_serverstempel_in_echtes_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Von Hand nachgerechnet — der empfindlichste Schritt der Datenbeschaffung.

    ``RealMt5Terminal`` haengt an die Serverzeit das Etikett ``UTC``, obwohl sie keine
    ist; die Serverzone ist gemessen ``Europe/Helsinki`` (Winter UTC+2, Sommer UTC+3).
    Also gilt:

        15.01.2020, 18:00 Serverzeit -> 16:00 echtes UTC   (Winter, -2 h)
        15.07.2020, 19:00 Serverzeit -> 16:00 echtes UTC   (Sommer, -3 h)

    Beide Stempel liegen nach der Drehung auf 16:00 — dem Londoner Fixing. Faellt
    ``server_zu_utc`` weg, liegt das Ein-Stunden-Fenster jeder Studie VOLLSTAENDIG
    neben dem Ereignis; ein fester Abzug von zwei Stunden traefe nur den Winter. Beide
    Faelle stehen deshalb nebeneinander.
    """
    winter = datetime(2020, 1, 15, 18, 0, tzinfo=UTC)
    sommer = datetime(2020, 7, 15, 19, 0, tzinfo=UTC)

    def antwort(
        name: str, tf: Timeframe, start: datetime, end: datetime, nummer: int
    ) -> tuple[Mt5Rate, ...]:
        return (_rate(winter), _rate(sommer))

    _terminal(monkeypatch, antwort)
    reihe = werkzeug._lade_kerzen("EURUSD")

    assert [k.ts for k in reihe] == [
        datetime(2020, 1, 15, 16, 0, tzinfo=UTC),
        datetime(2020, 7, 15, 16, 0, tzinfo=UTC),
    ]
    # Neun Scheiben liefern dieselben zwei Kerzen -- doppelte Stempel fallen zusammen.
    assert len(reihe) == 2


def test_lade_kerzen_setzt_die_reihe_aus_neun_fuenfjahresscheiben_zusammen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Von Hand: 45 Jahre in Fuenfjahresscheiben sind neun Abfragen.

    Nachgerechnet wird die FORM, nicht das Datum: der Zeitraum haengt an
    ``datetime.now`` und damit an der Rechneruhr. Geprueft wird darum, dass neun
    Scheiben zu je 5 x 365 Tagen rueckwaerts aneinanderstossen — ohne Luecke und ohne
    Ueberlappung. Die Stueckelung ist kein Schoenheitsfehler: eine einzelne Abfrage
    ueber die volle Historie kommt beim Terminal LEER zurueck statt als Fehler, und
    eine still verkuerzte Historie verkleinert die Ereigniszahl jeder Studie.

    Zugleich der Nachweis der harten Grenze ``allow_write=False``: die Studie liest,
    sie handelt nicht.
    """
    protokoll = _terminal(
        monkeypatch,
        lambda name, tf, start, end, nummer: (_rate(start + timedelta(hours=nummer)),),
    )
    werkzeug._lade_kerzen("EURUSD")

    assert protokoll["allow_write"] is False
    abfragen: list[tuple[datetime, datetime]] = protokoll["abfragen"]
    assert len(abfragen) == 9
    starts = [a for a, _ in abfragen]
    enden = [e for _, e in abfragen]
    assert starts == sorted(starts, reverse=True)
    assert starts[:-1] == enden[1:]
    assert all(e - a == timedelta(days=365 * 5) for a, e in abfragen)
    assert protokoll["shutdowns"] == 1


def test_lade_kerzen_schliesst_das_terminal_auch_im_absturz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein offenes Terminal ist eine Ressource, die der naechste Lauf nicht bekommt."""

    def bricht_ab(
        name: str, tf: Timeframe, start: datetime, end: datetime, nummer: int
    ) -> tuple[Mt5Rate, ...]:
        raise RuntimeError("Verbindung weggebrochen")

    protokoll = _terminal(monkeypatch, bricht_ab)
    with pytest.raises(RuntimeError, match="Verbindung weggebrochen"):
        werkzeug._lade_kerzen("EURUSD")
    assert protokoll["shutdowns"] == 1


def test_lade_kerzen_faellt_ohne_terminal_laut_aus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail-closed: kein Terminal heisst keine Reihe, nicht eine leere Reihe.

    Eine leere Reihe liefe in ``_lauf`` weiter und wuerde dort zum Absturz an
    ``kerzen[0]`` — mit einem Fehlerbild, das nichts mehr mit der Ursache zu tun hat.
    """
    protokoll = _terminal(
        monkeypatch,
        lambda name, tf, start, end, nummer: (),
        initialisierbar=False,
    )
    with pytest.raises(StudienError, match="Terminal nicht erreichbar"):
        werkzeug._lade_kerzen("EURUSD")
    assert protokoll["abfragen"] == []


# ---------------------------------------------------------------------------
# 3) Herkunft — Pruefsumme und Codestand, beide fail-closed
# ---------------------------------------------------------------------------


def test_data_checksum_verlangt_das_h1_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Herkunft zaehlt eine Studie nach der eigenen Regel des Repos nicht.

    Der Zeitrahmen im Dateinamen ist nicht beliebig: ``_lade_kerzen`` holt H1, also
    muss die Pruefsumme die H1-Reihe meinen. Ein D1-Manifest deckte eine andere Reihe
    als die gemessene.
    """
    monkeypatch.setattr(werkzeug, "MANIFESTE", tmp_path)
    with pytest.raises(StudienError) as fehler:
        werkzeug._data_checksum("GBPJPY")
    text = str(fehler.value)
    assert "GBPJPY_H1.manifest.json" in text
    assert "aufloesung.py" in text


def test_data_checksum_liest_die_summe_aus_dem_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(werkzeug, "MANIFESTE", tmp_path)
    (tmp_path / "GBPJPY_H1.manifest.json").write_text(
        json.dumps({"symbol": "GBPJPY", "timeframe": "H1", "checksum": "f98e4199cc61"}),
        encoding="utf-8",
    )
    assert werkzeug._data_checksum("GBPJPY") == "f98e4199cc61"


def test_code_commit_faellt_aus_statt_leer_zu_bleiben(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein leerer Codestand wuerde erst im ``finally`` auffallen — zu spaet.

    ``Trial.__post_init__`` weist eine leere Herkunft zurueck. Kaeme sie aus dieser
    Funktion, floege der Fehler im ``finally``-Block von ``_lauf`` und ueberdeckte
    dabei den urspruenglichen Grund des Abbruchs. Hier faellt er vor der Messung.
    """

    def kaputt(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(subprocess, "run", kaputt)
    with pytest.raises(StudienError, match="code_commit nicht bestimmbar"):
        werkzeug._code_commit()


# ---------------------------------------------------------------------------
# 4) Das Versuchsregister — die fail-closed-Sperre und der finally-Block
# ---------------------------------------------------------------------------


def test_ein_fehlendes_register_wird_nicht_angelegt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, herkunft: None
) -> None:
    """EICHFALL. Gegen die vorige Fassung rot — sie legte das Register hier an.

    Der Ablauf, der die Sperre entwaffnete: ``deflation_trials`` wirft bei fehlendem
    Register (fail-closed, weil eine Deflation gegen eine unbekannte Versuchszahl
    keine ist). Dieser Wurf traf mitten ins ``try`` von ``_lauf``. Der
    ``finally``-Block schrieb den Versuch trotzdem an, und ``append`` oeffnet im Modus
    ``"a"`` — also legte er die Datei NEU an. Der naechste Lauf fand ein Register mit
    einer einzigen Zeile und deflationierte gegen die Kampagnengroesse sieben statt
    gegen alle bisherigen Versuche. Die Kampagnenzaehlung des Registers faengt den
    Absturz nur bis zu dieser Untergrenze ab; alles darueber war weg — und eine zu
    kleine Versuchszahl macht die DSR milder, also in die schmeichelnde Richtung.

    Geprueft wird beides: die Datei entsteht nicht, UND es wird gar nicht erst
    gemessen. Ein verbrauchter Versuch ohne Register waere der zweite Schaden.
    """
    fehlt = tmp_path / "TRIALS.jsonl"
    monkeypatch.setattr(werkzeug, "studie", _darf_nicht_messen)

    with pytest.raises(StudienError) as fehler:
        werkzeug._lauf(
            PRUEFKANDIDAT, "SYNTH", _reihe(40), None, register_pfad=fehlt
        )

    assert not fehlt.exists(), "ein fehlendes Register wird nie neu angelegt"
    text = str(fehler.value)
    assert "Versuchsregister" in text
    assert "ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl" in text


def test_ein_abgebrochener_lauf_verbraucht_trotzdem_einen_versuch(
    tmp_path: Path, herkunft: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Der Sinn der Regel: verbraucht ist ein Versuch, sobald gemessen WURDE.

    Zehn Ereignisse, ``studie`` verlangt dreissig — die Studie bricht ab. Sie hat aber
    gemessen, und darum steht sie im Register. Nur weil der Eintrag im ``finally``
    steht und nicht hinter dem gelungenen Zweig, gibt es keinen Weg, erst zu messen und
    dann zu entscheiden, ob der Versuch zaehlt.

    KAMPAGNENZAEHLUNG, von Hand: das Feld meldet sieben Laeufe an (K1 auf EURUSD und
    GBPJPY, K2, K3, K4 auf beiden, K5 — 2+1+1+2+1). Ein EIGENER Lauf im Register
    ergibt ``fremd 0 + (1 // 7 + 1) * 7 = 7``. Traegt die ``strategy_id`` das Praefix
    der Kampagne NICHT, zaehlt derselbe Lauf als fremd: ``1 + (0 // 7 + 1) * 7 = 8``.
    Die Zahl unten haelt also die Kopplung zwischen der ``strategy_id`` dieses
    Werkzeugs und ``KAMPAGNE_PRAEFIX`` im Kernmodul fest.
    """
    ledger = _leeres_register(tmp_path)
    kurz = _reihe(10)

    assert (
        werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", kurz, None, register_pfad=ledger) == 1
    )
    assert "ABGEBROCHEN" in capsys.readouterr().out

    eintraege = list(register.iter_trials(ledger))
    assert len(eintraege) == 1
    eintrag = eintraege[0]
    assert eintrag.outcome == "aborted"
    assert eintrag.strategy_id == "ereignisstudie/K1"
    assert eintrag.strategy_id.startswith(kern.KAMPAGNE_PRAEFIX)
    assert eintrag.data_checksum == "summe-SYNTH"
    assert eintrag.code_commit == "c0ffee1234567890"
    assert eintrag.net_expectancy is None
    assert eintrag.trades is None
    assert eintrag.parameters["ereignisse_geplant"] == 10
    assert eintrag.parameters["hypothese"] == kern.HYPOTHESE

    assert kern.kampagne().groesse == 7
    assert register.deflation_trials(kern.kampagne(), ledger) == 7


def test_ein_absturz_wird_als_error_registriert_und_nicht_verschluckt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, herkunft: None
) -> None:
    """Ein Fehler, der KEIN ``StudienError`` ist, faellt durch — und zaehlt trotzdem.

    ``ausgang`` startet auf ``"error"`` und wird erst nach der Bestaetigung auf
    ``"completed"`` gesetzt. Faengt jemand hier breit (``except Exception``), sieht ein
    abgestuerzter Lauf wie ein abgebrochener aus und der Aufrufer bekommt eine 1 statt
    eines Stapelabzugs.

    Von Hand nachgerechnet, weil gemessen WURDE und die Zahlen darum im Eintrag stehen:
    40 Ereignisse zu je +12,00 bp bereinigt -> Median 12,00; K = 1,00 bp ->
    Nettoeffekt 12,00 - 1,00 = 11,00 bp; ``trades`` = 40.
    """

    def kaputt(*args: Any, **kwargs: Any) -> Any:
        raise register.TrialsLedgerError("Register unbrauchbar")

    monkeypatch.setattr(werkzeug, "bestaetige", kaputt)
    ledger = _leeres_register(tmp_path)

    with pytest.raises(register.TrialsLedgerError, match="Register unbrauchbar"):
        werkzeug._lauf(
            PRUEFKANDIDAT, "SYNTH", _reihe(40), None, register_pfad=ledger
        )

    eintraege = list(register.iter_trials(ledger))
    assert len(eintraege) == 1
    assert eintraege[0].outcome == "error"
    assert eintraege[0].trades == 40
    assert eintraege[0].net_expectancy == pytest.approx(11.0)


def test_ohne_pruefsumme_wird_nicht_gemessen_und_nichts_registriert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Herkunft wird VOR der Messung festgezurrt, nicht danach gesucht.

    Steht das Manifest nicht da, bricht ``_lauf`` ab, bevor ``studie`` laeuft — und
    darum bleibt das Register leer. Waere die Reihenfolge umgekehrt, waere ein Versuch
    verbraucht, dessen Ergebnis niemand einer Datenlage zuordnen kann; ein Eintrag ohne
    Herkunft ist beweisfrei, und ``Trial`` nimmt ihn gar nicht erst an.
    """
    ledger = _leeres_register(tmp_path)
    monkeypatch.setattr(werkzeug, "_kosten_bps", lambda kosten, symbol: 1.0)
    monkeypatch.setattr(werkzeug, "MANIFESTE", tmp_path / "keine-manifeste")
    monkeypatch.setattr(werkzeug, "studie", _darf_nicht_messen)

    with pytest.raises(StudienError, match="manifest.json"):
        werkzeug._lauf(
            PRUEFKANDIDAT, "SYNTH", _reihe(40), None, register_pfad=ledger
        )

    assert list(register.iter_trials(ledger)) == []


def test_ohne_kostenzeile_laeuft_nichts_und_kostet_nichts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nicht bewertbar heisst: kein Versuch verbraucht.

    Ohne K gibt es keine M6.1-Schwelle und keinen Nettoeffekt — gemessen wird nichts,
    also zaehlt auch nichts. Der Rueckgabewert ist trotzdem 1: eine geplante und nicht
    gerechnete Studie ist eine Luecke im Beleg.
    """
    ledger = _leeres_register(tmp_path)
    monkeypatch.setattr(werkzeug, "_kosten_bps", lambda kosten, symbol: None)
    monkeypatch.setattr(werkzeug, "studie", _darf_nicht_messen)

    assert (
        werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(40), None, register_pfad=ledger)
        == 1
    )
    assert "keine Kostenzeile" in capsys.readouterr().out
    assert list(register.iter_trials(ledger)) == []


def test_ein_gelungener_lauf_deflationiert_gegen_dasselbe_register(
    tmp_path: Path, herkunft: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """EICHFALL. Vorher bekam ``bestaetige`` den Registerpfad nicht.

    Die Studie deflationierte damit gegen das Register des Repos, waehrend sie ihren
    eigenen Versuch woandershin schrieb. Zwei Register fuer eine Reihe sind eines zu
    viel, und die berichtete DSR gehoerte zu einer anderen Versuchszahl als der, die
    der Lauf selbst erhoeht.

    VON HAND: drei fremde Zeilen liegen im Register, kein eigener Lauf. Zum Zeitpunkt
    der Bestaetigung gilt also ``fremd 3 + (eigen 0 // 7 + 1) * 7 = 10``. Diese Zehn
    muss im Bericht neben der DSR stehen. Nach dem Lauf steht ein eigener Eintrag mehr
    im Register, und die Zahl bleibt zehn (``3 + (1 // 7 + 1) * 7``) — genau die
    Konstanz, wegen der in ganzen Kampagnen gezaehlt wird.
    """
    ledger = _leeres_register(tmp_path)
    for nummer in range(3):
        _fremde_zeile(ledger, nummer)

    assert (
        werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(70), None, register_pfad=ledger)
        == 0
    )
    ausgabe = capsys.readouterr().out
    assert "gegen 10 Versuche" in ausgabe
    assert "URTEIL M6:" in ausgabe

    eintraege = list(register.iter_trials(ledger))
    assert len(eintraege) == 4
    assert eintraege[-1].outcome == "completed"
    assert eintraege[-1].trades == 70
    assert eintraege[-1].net_expectancy == pytest.approx(11.0)
    assert register.deflation_trials(kern.kampagne(), ledger) == 10


def test_die_vorregistrierte_schwelle_stammt_aus_dem_kernmodul(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, herkunft: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """EICHFALL. Vorher stand ``3*k_bps`` als nackte Zahl im Block
    „VOR DER MESSUNG festgezurrt".

    ``M61_FAKTOR`` ist eine Zahl, die an zwei Stellen stand. Dreht jemand am Kernmodul,
    kuendigt die Vorregistrierung weiter die alte Schwelle an, waehrend gegen die neue
    geprueft wird — und die Vorregistrierung ist genau das Blatt, das spaeter belegen
    soll, was vorher feststand.

    Der Fall dreht den Faktor auf 4,0 und verlangt, dass BEIDE gedruckten Schwellen
    mitgehen: die angekuendigte und die im Ergebnis. Bei K = 1,00 bp sind das 4,00 bp.
    """
    monkeypatch.setattr(kern, "M61_FAKTOR", 4.0)
    ledger = _leeres_register(tmp_path)

    werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(70), None, register_pfad=ledger)

    ausgabe = capsys.readouterr().out
    assert "M6.1-Schwelle 4.00 bp" in ausgabe
    assert "M6.1 (Brutto >= 4.00 bp)" in ausgabe


# ---------------------------------------------------------------------------
# 4b) Der Block „VOR DER MESSUNG festgezurrt" — das Blatt, das spaeter belegen soll,
#     was vorher feststand. Er war bis auf die M6.1-Schwelle ungeprueft: sechs seiner
#     Zeilen liessen sich loeschen, ohne dass ein Fall fiel, und die angekuendigte
#     Vorzeichenregel liess sich UMDREHEN, ohne dass ein Fall fiel.
# ---------------------------------------------------------------------------


def test_der_block_vor_der_messung_nennt_alle_acht_stuecke(
    tmp_path: Path, herkunft: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """Die Vorregistrierung ist eine Aufzaehlung, und eine Aufzaehlung mit Luecke
    belegt nichts.

    Was den Versuch ausmacht, steht in ``STUDY_POLICY_VERSION`` und im Modulkopf:
    Hypothese, Fenster, Zeitpunkt, Zeitraum, Ereigniszahl, Kosten samt Schwelle,
    ``data_checksum``, ``code_commit`` und das Register, gegen das deflationiert wird.
    Fehlt eine dieser Zeilen, laesst sich hinterher nicht mehr sagen, was vor der
    Messung feststand — und genau das ist der einzige Zweck des Blocks.

    Alle Werte sind von Hand gesetzt: K = 1,00 bp aus der ``herkunft``-Fixtur, also
    M6.1-Schwelle 3 x 1,00 = 3,00 bp; Pruefsumme und Codestand kommen ebenfalls von
    dort und werden auf 16 bzw. 12 Zeichen gekuerzt gedruckt. Die Reihe laeuft ueber
    70 Werktage ab Montag, dem 06.01.2020, also bis zum 10.04.2020, mit einem Ereignis
    je Werktag.

    Mutationsprobe: je eine der neun Zeilen aus ``_lauf`` entfernt — dieser Fall faellt
    neunmal, jedes Mal mit der fehlenden Zeile in der Meldung.
    """
    ledger = _leeres_register(tmp_path)
    werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(70), None, register_pfad=ledger)
    ausgabe = capsys.readouterr().out

    erwartet = [
        "VOR DER MESSUNG festgezurrt:",
        "Hypothese      : umkehr (Vorzeichen = -sign(Rendite der Vorstunde))",
        "Fenster        : 1 h ab dem ersten handelbaren Kerzenanfang",
        "Zeitpunkt      : 16:00 UTC",
        "Zeitraum       : 2020-01-06 .. 2020-04-10",
        "Ereignisse     : 70",
        "K (guenstigster Broker): 1.00 bp | M6.1-Schwelle 3.00 bp",
        "data_checksum  : summe-SYNTH...",
        "code_commit    : c0ffee123456",
        "Register       : TRIALS.jsonl (ausserhalb des Repos)",
    ]
    for zeile in erwartet:
        assert zeile in ausgabe, f"Die Vorregistrierung nennt {zeile!r} nicht mehr"


def test_die_angekuendigte_vorzeichenregel_ist_die_gerechnete(
    tmp_path: Path, herkunft: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """DIE SCHAERFSTE ZEILE DES BLOCKS — und die einzige, die sich lautlos umdrehen
    liess.

    Die Vorregistrierung kuendigt ``-sign(Rendite der Vorstunde)`` an. Das Kernmodul
    RECHNET diese Regel, aber es BENENNT sie nicht: es gibt keine gemeinsame Konstante,
    an der beide haengen (und das Kernmodul gehoert nicht zu dieser Arbeit). Ein ``+``
    statt des ``-`` in der gedruckten Zeile kuendigte darum die UMGEKEHRTE Hypothese
    an — die Umkehrung dessen, worauf die ganze Studie ruht —, ohne dass etwas rot
    wurde.

    Gebunden wird die Ankuendigung hier ueber die Messung im selben Lauf. ``_reihe``
    baut die Fensterstunde ausdruecklich GEGEN die Vorstunde: Vorstunde +/-20 bp,
    Fenster 12 bp dagegen. Unter der angekuendigten Regel ``-sign(Vorstunde)`` ist der
    bereinigte Effekt darum **+12,00 bp**; unter der umgekehrten Regel waere er
    **-12,00 bp**. Beide Haelften stehen in einem Fall, weil nur zusammen sie etwas
    festhalten:

    * dreht jemand die gedruckte Ankuendigung, faellt die erste Zusicherung;
    * dreht jemand die Rechnung im Kernmodul, faellt die zweite.
    """
    ledger = _leeres_register(tmp_path)
    werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(70), None, register_pfad=ledger)
    ausgabe = capsys.readouterr().out

    assert "Vorzeichen = -sign(Rendite der Vorstunde)" in ausgabe
    assert "+sign(Rendite der Vorstunde)" not in ausgabe
    assert "Bruttoeffekt (Median): +12.00 bp" in ausgabe, (
        "Die Reihe laeuft GEGEN die Vorstunde; unter der angekuendigten Regel ist das "
        "ein PLUS. Steht hier -12.00, rechnet das Kernmodul die Gegenhypothese."
    )


# --- Die Registerzeile: ein Beleg darf nicht am Rechner haengen ------------
def test_die_registerzeile_nennt_keinen_rechnerpfad(
    tmp_path: Path, herkunft: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """EICHFALL. Vorher stand hier der absolute Pfad des ausfuehrenden Rechners.

    Im Lauf, aus dem der eingefrorene Abzug stammt, waere das
    ``C:\\Users\\<kontoname>\\...\\TRIALS.jsonl`` gewesen — in einer Datei, die als
    Beleg eingecheckt und weitergegeben wird. Zwei Regeln dieses Repos zugleich
    verletzt: ein Beleg haengt nicht am Rechner (dafuer gibt es ``data_checksum`` und
    ``code_commit``), und Konto- oder Servernamen gehen nie in eine weitergegebene
    Datei — ein Windows-Benutzerpfad ist ein Kontoname.

    Geprueft wird beides: die Zeile steht da (loeschen macht diesen Fall rot), und sie
    enthaelt das Verzeichnis nicht.
    """
    ledger = _leeres_register(tmp_path)
    werkzeug._lauf(PRUEFKANDIDAT, "SYNTH", _reihe(70), None, register_pfad=ledger)
    ausgabe = capsys.readouterr().out

    assert "Register       : TRIALS.jsonl (ausserhalb des Repos)" in ausgabe
    assert str(tmp_path) not in ausgabe, (
        "Der Pfad des ausfuehrenden Rechners darf in keiner Zeile des Belegs stehen"
    )
    assert str(tmp_path.parent) not in ausgabe


def test_ein_register_im_repo_heisst_relativ_zum_repo() -> None:
    """Damit derselbe Lauf unter Windows und unter Linux dieselbe Zeile erzeugt.

    Der uebliche Fall: ``TRIALS.jsonl`` liegt in der Wurzel des Repos. Gedruckt wird
    genau der Name, nicht der Pfad dorthin. Der zweite Fall haelt den ``/``-Trenner
    fest — mit dem Windows-Trenner haetten zwei Rechner zwei verschiedene Belege
    erzeugt, und der Unterschied saehe aus wie eine andere Messung.

    Die Dateien muessen dafuer nicht existieren: die Kennung ist eine reine
    Namensrechnung und liest die Platte nicht an.
    """
    assert werkzeug._registerkennung(werkzeug.REPO / "TRIALS.jsonl") == "TRIALS.jsonl"
    tief = werkzeug.REPO / "ABSCHLUSS-3a" / "07-AUSGABEN" / "trials.jsonl"
    assert (
        werkzeug._registerkennung(tief) == "ABSCHLUSS-3a/07-AUSGABEN/trials.jsonl"
    )


def test_ein_register_ausserhalb_des_repos_wird_als_solches_benannt(
    tmp_path: Path,
) -> None:
    """Kein Weglassen, sondern eine Auskunft: gegen welches Register lief die Deflation?

    Ein Seitenstueck ausserhalb des Repos ist nicht das versionierte Register. Das
    gehoert in den Beleg — nur eben ohne den Pfad, der den Kontonamen traegt. Der
    Dateiname allein ist keine Auskunft ueber den Rechner: er heisst auf jedem
    ``TRIALS.jsonl``.
    """
    kennung = werkzeug._registerkennung(tmp_path / "TRIALS.jsonl")
    assert kennung == "TRIALS.jsonl (ausserhalb des Repos)"
    assert str(tmp_path) not in kennung


# ---------------------------------------------------------------------------
# 5) Die Berichtsausgabe — das Urteil selbst
# ---------------------------------------------------------------------------


def _ergebnis(*, brutto: float, k_bps: float) -> Ergebnis:
    """Ein Ergebnis mit frei gesetzten Kennzahlen; die Schwelle ist M61_FAKTOR x K."""
    return Ergebnis(
        kandidat="K3",
        instrument="GBPJPY",
        hypothese=kern.HYPOTHESE,
        fenster_stunden=1.0,
        n_ereignisse=193,
        n_gemessen=192,
        brutto_bps=brutto,
        p25_bps=-8.0,
        p75_bps=9.0,
        trefferanteil=0.51,
        k_bps=k_bps,
        netto_bps=brutto - k_bps,
        m61_schwelle_bps=kern.M61_FAKTOR * k_bps,
        reihen_pruefsumme="a" * 64,
    )


def _bestaetigung(
    *,
    dsr: float = 0.99,
    versuche: int = 8,
    dsr_ok: bool = True,
    stabil_ok: bool = True,
    zufall_ok: bool = True,
) -> Bestaetigung:
    return Bestaetigung(
        dsr_oos=dsr,
        dsr_n=64,
        dsr_versuche=versuche,
        dsr_bestanden=dsr_ok,
        haelfte_frueh_bps=2.0,
        haelfte_spaet_bps=2.0,
        stabil_bestanden=stabil_ok,
        zufall_anteil=0.01,
        zufall_bestanden=zufall_ok,
    )


@pytest.mark.parametrize(
    "brutto,dsr_ok,stabil_ok,zufall_ok,urteil",
    [
        (9.0, True, True, True, "BESTANDEN"),
        (1.0, True, True, True, "GESCHEITERT"),  # M6.1 gerissen
        (9.0, False, True, True, "GESCHEITERT"),  # Deflation gerissen
        (9.0, True, False, True, "GESCHEITERT"),  # Stabilitaet gerissen
        (9.0, True, True, False, "GESCHEITERT"),  # Randomisierung gerissen
    ],
)
def test_das_urteil_faellt_bei_jeder_einzelnen_gerissenen_pruefung(
    capsys: pytest.CaptureFixture[str],
    brutto: float,
    dsr_ok: bool,
    stabil_ok: bool,
    zufall_ok: bool,
    urteil: str,
) -> None:
    """Die Wahrheitstafel des Schlusssatzes — vier Sperren in Reihe, nicht parallel.

    ``URTEIL M6`` ist der Satz, den ein Leser des Berichts mitnimmt. Er steht am Ende
    einer Druckkaskade, in der ein ``and`` versehentlich ein ``or`` sein koennte; dann
    genuegte eine bestandene Pruefung von vieren fuer ein „BESTANDEN". Jede der vier
    Zeilen unten reisst genau eine Pruefung und verlangt GESCHEITERT.

    Bei K = 3,00 bp liegt die M6.1-Schwelle bei 3 x 3,00 = 9,00 bp. Brutto 9,00
    besteht sie (``>=``), Brutto 1,00 nicht.
    """
    werkzeug._bericht(
        _ergebnis(brutto=brutto, k_bps=3.0),
        _bestaetigung(dsr_ok=dsr_ok, stabil_ok=stabil_ok, zufall_ok=zufall_ok),
    )
    assert f"URTEIL M6: {urteil}" in capsys.readouterr().out


def test_der_bericht_nennt_die_versuchszahl_neben_der_dsr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """EICHFALL. Vorher druckte die Zeile DSR und OoS-Zahl — aber nicht, wogegen
    deflationiert wurde.

    Dieselbe Messung ergibt 0,755 bei acht Versuchen und 0,984 bei einem: einmal
    durchgefallen, einmal bestanden. ``Bestaetigung.dsr_versuche`` gibt es genau
    deshalb; im Bericht fehlte sie, und damit war die wichtigste Kennzahl des Pakets
    nicht nachrechenbar.
    """
    werkzeug._bericht(
        _ergebnis(brutto=1.36, k_bps=1.8351),
        _bestaetigung(dsr=0.686, versuche=8, dsr_ok=False),
    )
    ausgabe = capsys.readouterr().out
    assert "DSR 0.686 auf 64 OoS-Ereignissen gegen 8 Versuche" in ausgabe


def test_der_bericht_nennt_die_wirklich_gefahrenen_ziehungen(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """EICHFALL. Vorher stand „1.000" als Text in der Zeile.

    ``M62_ZIEHUNGEN`` fuehrt die Zahl im Kernmodul. Solange sie hier als Text
    danebenstand, konnte der Bericht 1.000 Ziehungen behaupten, waehrend 25 gefahren
    wurden — und der Anteil daneben liest sich bei 25 Ziehungen ganz anders. Derselbe
    Fehler wie bei der M6.1-Schwelle, nur eine Zeile tiefer.
    """
    monkeypatch.setattr(kern, "M62_ZIEHUNGEN", 25)
    werkzeug._bericht(_ergebnis(brutto=9.0, k_bps=3.0), _bestaetigung())
    assert "25 verschobenen Mengen" in capsys.readouterr().out


def test_der_bericht_setzt_den_deutschen_tausenderpunkt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Die Behebung oben hatte den Trennpunkt verloren — ein Rueckschritt im Beleg.

    Der eingefrorene Abzug liest sich „27.6 % der 1.000 verschobenen Mengen"; nachdem
    die Zahl aus ``M62_ZIEHUNGEN`` kam, druckte das Werkzeug „1000". Der Bericht ist
    durchweg deutsch gesetzt, und ein Beleg, dessen Zahlensatz sich zwischen zwei
    Staenden aendert, sieht bei jedem Vergleich nach einer Abweichung aus, die keine
    ist.

    Der laufende Wert des Kernmoduls wird hier NICHT gesetzt: geprueft wird der Satz
    der Zahl, die wirklich gilt. Steht dort eines Tages eine andere Zahl, prueft dieser
    Fall sie mit — dafuer wird die Erwartung aus derselben Quelle gebildet und nur die
    Trennung von Hand nachgestellt.
    """
    werkzeug._bericht(_ergebnis(brutto=9.0, k_bps=3.0), _bestaetigung())
    ausgabe = capsys.readouterr().out
    assert kern.M62_ZIEHUNGEN == 1000, "Von Hand: der Kern faehrt 1.000 Ziehungen"
    assert "der 1.000 verschobenen Mengen" in ausgabe
    assert "der 1000 verschobenen Mengen" not in ausgabe


def test_der_bericht_des_staerksten_kandidaten_sagt_gescheitert(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """BELEG — die schaerfste Zeile des Befunds, von Hand nachgerechnet.

    K3 (Monatsende-Fixing, GBPJPY) trug den GROESSTEN Bruttoeffekt des ganzen Feldes.
    Mit K = 1,8351 bp (guenstigster Broker, siehe ``tools/kostentor.py``):

        M6.1-Schwelle : 3 x 1,8351 = 5,5053 bp  -> gedruckt „5.51"
        Bruttoeffekt  : 1,36 bp                 -> gedruckt „+1.36", und 1,36 < 5,51
        Nettoeffekt   : 1,36 - 1,8351 = -0,4751 -> gedruckt „-0.48"
        DSR           : 0,686 < 0,95

    Der beste Kandidat des Feldes verfehlt die Schwelle um den Faktor vier und kostet
    mehr, als er einbringt. Wenn dieser Bericht je „BESTANDEN" sagt, stimmt etwas
    nicht mit dem Werkzeug und nicht mit dem Markt.
    """
    assert kern.M61_FAKTOR * 1.8351 == pytest.approx(5.5053)
    werkzeug._bericht(
        _ergebnis(brutto=1.36, k_bps=1.8351),
        _bestaetigung(dsr=0.686, versuche=8, dsr_ok=False),
    )
    ausgabe = capsys.readouterr().out
    assert "Bruttoeffekt (Median): +1.36 bp" in ausgabe
    assert "NETTOEFFEKT          : -0.48 bp" in ausgabe
    assert "M6.1 (Brutto >= 5.51 bp): GESCHEITERT" in ausgabe
    assert "URTEIL M6: GESCHEITERT" in ausgabe


# ---------------------------------------------------------------------------
# 6) Der Einstieg — was vor der ersten Kerze geprueft wird
# ---------------------------------------------------------------------------


def test_main_weist_eine_paarung_ausserhalb_des_feldes_zurueck(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """EICHFALL. ``--kandidat K1 --instrument NVDA`` lief vorher glatt durch.

    Das Londoner Fixing, gemessen auf einer amerikanischen Aktie, berichtet und als
    Lauf DIESER Reihe ins Register geschrieben. Das ist keine Wiederholung des Feldes,
    sondern eine neue Hypothese — M7 zaehlt sie als eigenen Versuch. Und sie rueckt
    die Kampagnengrenze schief, gegen die alle folgenden Studien deflationieren.

    Dass der Abbruch VOR ``_lade_kerzen`` kommt, ist kein Beiwerk: die Kerzenabfrage
    dauert eine halbe Stunde und braucht ein MT5-Terminal.
    """

    def darf_nicht_laden(symbol: str) -> list[Kerze]:
        raise AssertionError("Kerzen geholt, obwohl die Paarung ungueltig ist")

    monkeypatch.setattr(werkzeug, "_lade_kerzen", darf_nicht_laden)

    assert werkzeug.main(["--kandidat", "K1", "--instrument", "NVDA"]) == 1
    fehler = capsys.readouterr().err
    assert "K1" in fehler
    assert "NVDA" in fehler
    assert "M7" in fehler


def test_main_ohne_schalter_laeuft_nicht_einfach_alles(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein nackter Aufruf raet nicht — er bricht ab.

    Waere ``--alle`` der stille Vorgabewert, kostete ein Tippfehler in der Aufrufzeile
    sieben Versuche im Register. Es gibt keinen Weg, sie wieder herauszunehmen; das
    Register ist anhaengend und kennt keine Loeschung.
    """

    def darf_nicht_laden(symbol: str) -> list[Kerze]:
        raise AssertionError("Kerzen geholt, obwohl kein Schalter gesetzt war")

    monkeypatch.setattr(werkzeug, "_lade_kerzen", darf_nicht_laden)

    with pytest.raises(SystemExit) as ende:
        werkzeug.main([])
    assert ende.value.code == 2
    assert "--selbsttest" in capsys.readouterr().err


def test_main_meldet_ein_fehlendes_register_vor_der_ersten_kerzenabfrage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Fail-closed, und zwar frueh.

    Die Fixtur ``_kein_repo_register`` biegt das Register auf einen Pfad, den es nicht
    gibt. ``main`` muss das melden, bevor es 45 Jahre Historie holt — ein Abbruch nach
    der Abfrage ist derselbe Abbruch, nur eine halbe Stunde spaeter, und er endete
    bisher damit, dass der ``finally``-Block das Register neu anlegte.
    """

    def darf_nicht_laden(symbol: str) -> list[Kerze]:
        raise AssertionError("Kerzen geholt, obwohl das Register fehlt")

    monkeypatch.setattr(werkzeug, "_lade_kerzen", darf_nicht_laden)

    assert werkzeug.main(["--kandidat", "K1", "--instrument", "EURUSD"]) == 1
    fehler = capsys.readouterr().err
    assert "Versuchsregister" in fehler
    assert "fehlt" in fehler


@pytest.mark.parametrize(
    "ausgaenge,erwartet",
    [
        ([0, 0, 0, 0, 0, 0, 0], 0),
        ([0, 0, 0, 1, 0, 0, 0], 1),
        ([1, 1, 1, 1, 1, 1, 1], 1),
    ],
)
def test_main_meldet_rot_sobald_eine_studie_nicht_bewertbar_ist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ausgaenge: list[int],
    erwartet: int,
) -> None:
    """EICHFALL. Vorher: ``1 if schlecht == len(paare) else 0``.

    Sechs von sieben Studien unbewertbar und trotzdem Rueckgabe 0 — sechs verbrauchte
    Versuche unter einem gruenen Rueckgabewert. Wer nur den Rueckgabewert liest, und
    das tut jede Automatik, sah Erfolg. Eine geplante und nicht gerechnete Studie ist
    eine Luecke im Beleg, kein Rest.

    Die mittlere Zeile ist der Fall, der vorher 0 ergab.
    """
    ledger = _leeres_register(tmp_path)
    monkeypatch.setattr(register, "default_ledger_path", lambda: ledger)
    monkeypatch.setattr(werkzeug, "default_ledger_path", lambda: ledger)
    monkeypatch.setattr(werkzeug, "_lade_kerzen", lambda symbol: [])

    folge = iter(ausgaenge)
    monkeypatch.setattr(werkzeug, "_lauf", lambda *a, **kw: next(folge))

    assert werkzeug.main(["--alle"]) == erwartet


# ---------------------------------------------------------------------------
# 7) Der eingefrorene Abzug — er muss sagen, mit welchem Werkzeugstand er entstand
# ---------------------------------------------------------------------------

#: Der Werkzeugstand, mit dem ``07-AUSGABEN/ereignisstudie.txt`` erzeugt wurde. Er steht
#: an drei Stellen und muss an allen dreien derselbe sein: im Kopf des Abzugs, in jedem
#: seiner sieben Messbloecke (``code_commit``) und in ``04-EREIGNISSTUDIE.md``.
ABZUG_WERKZEUGSTAND = "a9ed7ad57dac"
ABZUG = werkzeug.REPO / "ABSCHLUSS-3a" / "07-AUSGABEN" / "ereignisstudie.txt"
ABZUG_DOKUMENT = werkzeug.REPO / "ABSCHLUSS-3a" / "04-EREIGNISSTUDIE.md"
ABZUG_REGISTER = werkzeug.REPO / "ABSCHLUSS-3a" / "07-AUSGABEN" / "trials.jsonl"


def test_der_eingefrorene_abzug_nennt_seinen_werkzeugstand() -> None:
    """Ein Beleg, den sein eigenes Werkzeug nicht mehr erzeugt, ist keiner.

    Die Datei ist mit ``a9ed7ad57dac`` gemessen worden; das heutige Werkzeug druckt
    zwei Zeilen anders (die Versuchszahl neben der DSR, die Registerzeile) und
    deflationiert gegen eine andere Versuchszahl. Neu gemessen wird deshalb NICHT --
    jede Messung verbraucht einen Versuch, und sieben weitere sprengten das Budget von
    zwoelf. Stehen bleiben darf der Abzug aber nur, wenn er selbst sagt, woher er
    kommt.

    Dieser Fall haelt genau das fest, und zwar an drei Stellen zugleich, damit keine
    von ihnen allein wandern kann: der Kopf der Datei, der ``code_commit`` jedes
    Messblocks und das Dokument, das die Datei als Beleg fuehrt. Wer den Abzug neu
    erzeugt, verliert den Kopf -- und wird hier rot, statt stillschweigend einen Beleg
    ohne Herkunft einzuchecken.

    Der Fall liest ausschliesslich versionierte Dateien: kein Terminal, kein Netz,
    keine Rechneruhr, kein nicht versioniertes ``TRIALS.jsonl``.
    """
    # Getrennt wird an der ersten Zeile der Werkzeugausgabe selbst, nicht an einer
    # gezaehlten Zeilenzahl: der Kopf darf wachsen, ohne diesen Fall zu bewegen.
    kopf, trenner, koerper = ABZUG.read_text(encoding="utf-8").partition(
        "\nEreignisstudie ereignisstudie-v1"
    )
    assert trenner, "Die Kopfzeile des Werkzeuglaufs fehlt im Abzug"

    assert (
        f"EINGEFRORENER ABZUG -- ERZEUGT MIT WERKZEUGSTAND {ABZUG_WERKZEUGSTAND}"
        in kopf
    ), "Der Abzug nennt seinen Werkzeugstand nicht mehr"
    assert "04-EREIGNISSTUDIE.md" in kopf, (
        "Der Kopf muss auf die Stelle zeigen, an der die Abweichung begruendet ist"
    )

    stempel = [
        z.split(":", 1)[1].strip()
        for z in koerper.splitlines() if "code_commit" in z
    ]
    assert len(stempel) == 7, f"sieben Messbloecke erwartet, {len(stempel)} gefunden"
    assert set(stempel) == {ABZUG_WERKZEUGSTAND}, (
        f"Der Kopf sagt {ABZUG_WERKZEUGSTAND}, die Messbloecke sagen {set(stempel)}"
    )

    dokument = ABZUG_DOKUMENT.read_text(encoding="utf-8")
    assert ABZUG_WERKZEUGSTAND in dokument, (
        "04-EREIGNISSTUDIE.md fuehrt die Datei als Beleg und muss denselben "
        "Werkzeugstand nennen"
    )
    assert "Abschnitt 6" in kopf
    assert "## 6." in dokument


def test_die_versuchszahl_der_begruendung_stimmt_mit_dem_register() -> None:
    """Abschnitt 6 behauptet eine Zahl -- hier wird sie nachgerechnet.

    Die Begruendung, warum der Abzug nicht neu gemessen wird, ruht darauf, dass die
    Aenderung an der Versuchszahl in die STRENGE Richtung geht: der eingefrorene Stand
    zaehlte Registerzeilen zur Aufrufzeit (die erste Studie sah acht), der heutige
    zaehlt ganze Kampagnen. Gegen den versionierten Abzug des Registers sind das
    vierzehn -- fuer jede der sieben Studien dieselbe Zahl, und mehr Versuche heissen
    eine kleinere DSR.

    Von Hand: sieben eigene Zeilen, keine fremden, Kampagnengroesse sieben, also
    ``0 + (7 // 7 + 1) * 7 = 14``.

    Gelesen wird der versionierte Abzug ``07-AUSGABEN/trials.jsonl``, nicht das nicht
    versionierte ``TRIALS.jsonl`` -- sonst haenge dieser Fall an einer Datei, die auf
    einem frischen Klon fehlt.
    """
    assert kern.kampagne().groesse == 7
    eigene = [
        t for t in register.iter_trials(ABZUG_REGISTER)
        if t.strategy_id.startswith(kern.KAMPAGNE_PRAEFIX)
    ]
    assert len(eigene) == 7, "sieben verbrauchte Versuche, so steht es im Dokument"
    assert register.deflation_trials(kern.kampagne(), ABZUG_REGISTER) == 14

    dokument = ABZUG_DOKUMENT.read_text(encoding="utf-8")
    assert "gegen 14 Versuche deflationiert" in dokument

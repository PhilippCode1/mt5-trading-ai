"""Ereigniskalender: die Zeitzonenfalle, gegen die der Auftrag ausdruecklich warnt.

Ein Fehler von einer Stunde legt ein Ein-Stunden-Fenster vollstaendig neben das Ereignis.
Die Studie liefert dann trotzdem eine Zahl. Diese Tests pruefen darum vor allem die
Uebergaenge — Sommerzeit, Jahreswechsel, Monatsenden —, weil dort ein Fehler entsteht,
den man einer einzelnen Zahl nicht ansieht.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.kalender import (
    CALENDAR_POLICY_VERSION,
    KANDIDATEN,
    SERVER_TZ_NAME,
    KalenderError,
    ereignisse,
    kandidat,
    load_ereigniskalender,
    server_zu_utc,
)

REPO = Path(__file__).resolve().parents[1]
ECHTE_DATEI = REPO / "config" / "ereigniskalender.json"


# --- Die Drehung -----------------------------------------------------------
def test_serverzeit_wird_im_winter_um_zwei_stunden_gedreht() -> None:
    """Terminal sagt 12:00, echt ist 10:00 UTC — EET, also UTC+2."""
    assert server_zu_utc(datetime(2024, 1, 15, 12, 0, tzinfo=UTC)) == datetime(
        2024, 1, 15, 10, 0, tzinfo=UTC
    )


def test_serverzeit_wird_im_sommer_um_drei_stunden_gedreht() -> None:
    """Derselbe Wanduhrwert im Juli ist eine andere UTC-Zeit. Genau das ist die Falle."""
    assert server_zu_utc(datetime(2024, 7, 15, 12, 0, tzinfo=UTC)) == datetime(
        2024, 7, 15, 9, 0, tzinfo=UTC
    )


def test_die_drehung_wechselt_am_eu_termin_nicht_am_amerikanischen() -> None:
    """Gemessen: am 10.03. (US) aendert sich nichts, am 31.03. (EU) springt es."""
    vor_us = server_zu_utc(datetime(2024, 3, 8, 12, 0, tzinfo=UTC))
    nach_us = server_zu_utc(datetime(2024, 3, 15, 12, 0, tzinfo=UTC))
    assert vor_us.hour == nach_us.hour == 10, "US-Umstellung darf nichts aendern"
    nach_eu = server_zu_utc(datetime(2024, 4, 2, 12, 0, tzinfo=UTC))
    assert nach_eu.hour == 9, "EU-Umstellung muss den Versatz aendern"


def test_zeitstempel_ohne_zeitzone_ist_ein_fehler() -> None:
    with pytest.raises(KalenderError):
        server_zu_utc(datetime(2024, 1, 15, 12, 0))  # noqa: DTZ001


# --- Die Ereigniszeitpunkte ------------------------------------------------
def test_londoner_fixing_wandert_mit_der_britischen_sommerzeit() -> None:
    """16:00 London ist im Winter 16:00 UTC und im Sommer 15:00 UTC."""
    k = kandidat("K1")
    winter = ereignisse(k, date(2024, 1, 15), date(2024, 1, 15))
    sommer = ereignisse(k, date(2024, 7, 15), date(2024, 7, 15))
    assert winter[0] == datetime(2024, 1, 15, 16, 0, tzinfo=UTC)
    assert sommer[0] == datetime(2024, 7, 15, 15, 0, tzinfo=UTC)


def test_tokioter_fixing_wandert_nicht() -> None:
    """Asia/Tokyo kennt keine Sommerzeit — 09:55 JST ist immer 00:55 UTC."""
    k = kandidat("K2")
    for tag in (date(2024, 1, 15), date(2024, 7, 15)):
        assert ereignisse(k, tag, tag)[0] == datetime(
            tag.year, tag.month, tag.day, 0, 55, tzinfo=UTC
        )


def test_rollover_folgt_der_serverzeit_und_nicht_utc() -> None:
    """Mitternacht Serverzeit ist 22:00 UTC im Winter und 21:00 UTC im Sommer.

    Das ist der Kandidat, bei dem die Verwechslung am teuersten waere: wer hier UTC
    einsetzt, misst ein Fenster, in dem gar nichts abgerechnet wird.
    """
    k = kandidat("K4")
    assert ereignisse(k, date(2024, 1, 15), date(2024, 1, 15))[0] == datetime(
        2024, 1, 14, 22, 0, tzinfo=UTC
    )
    assert ereignisse(k, date(2024, 7, 15), date(2024, 7, 15))[0] == datetime(
        2024, 7, 14, 21, 0, tzinfo=UTC
    )


def test_nasdaq_schluss_folgt_der_amerikanischen_sommerzeit() -> None:
    """16:00 New York: 21:00 UTC im Winter, 20:00 UTC im Sommer.

    Die amerikanische Umstellung liegt drei Wochen vor der europaeischen. In dieser
    Luecke stimmt weder ein fester Versatz zu UTC noch einer zur Serverzeit.
    """
    k = kandidat("K5")
    assert ereignisse(k, date(2024, 1, 15), date(2024, 1, 15))[0].hour == 21
    assert ereignisse(k, date(2024, 7, 15), date(2024, 7, 15))[0].hour == 20
    # In der Luecke (US schon Sommerzeit, EU noch nicht) muss NY fuehren.
    assert ereignisse(k, date(2024, 3, 15), date(2024, 3, 15))[0].hour == 20


def test_die_drei_zonen_fallen_im_sommer_auseinander() -> None:
    """Der eigentliche Grund fuer dieses Modul: ein Versatz reicht nicht fuer alle."""
    # Ein Monatsende, damit auch K3 an diesem Tag ein Ereignis hat.
    tag = date(2024, 7, 31)
    stunden = {
        k.schluessel: treffer[0].hour
        for k in KANDIDATEN
        if (treffer := ereignisse(k, date(2024, 7, 1), date(2024, 8, 15)))
        and (treffer := [t for t in treffer if t.astimezone(k.zone).date() == tag])
    }
    assert len(stunden) == len(KANDIDATEN), f"nicht alle Kandidaten am {tag}: {stunden}"
    assert len(set(stunden.values())) >= 3, (
        f"Die Kandidaten liegen zu dicht beieinander: {stunden} — dann pruefte dieser "
        "Test die Zeitzonen nicht mehr"
    )


def test_wochenenden_kommen_nicht_vor() -> None:
    k = kandidat("K1")
    for ts in ereignisse(k, date(2024, 1, 1), date(2024, 12, 31)):
        assert ts.weekday() < 5 or ts.hour >= 20, f"{ts} faellt auf ein Wochenende"


def test_monatsende_liefert_den_letzten_werktag() -> None:
    k = kandidat("K3")
    treffer = ereignisse(k, date(2024, 1, 1), date(2024, 4, 30))
    tage = [t.astimezone(k.zone).date() for t in treffer]
    # Januar endet Mi 31., Februar Do 29., Maerz faellt auf Sonntag 31. -> Freitag 29.
    assert tage[:3] == [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29)]


def test_der_angebrochene_letzte_monat_zaehlt_nicht() -> None:
    """Ein halber Monat hat kein Monatsende — sonst waere ein Zufallstag ein Ereignis."""
    treffer = ereignisse(kandidat("K3"), date(2024, 1, 1), date(2024, 3, 15))
    assert len(treffer) == 2  # Januar und Februar, nicht der angebrochene Maerz


def test_rueckwaerts_laufender_zeitraum_ist_ein_fehler() -> None:
    with pytest.raises(KalenderError):
        ereignisse(kandidat("K1"), date(2024, 5, 1), date(2024, 4, 1))


def test_unbekannter_kandidat_ist_ein_fehler() -> None:
    with pytest.raises(KalenderError, match="K9"):
        kandidat("K9")


# --- Das Feld --------------------------------------------------------------
def test_alle_kandidaten_laufen_im_stundenfenster() -> None:
    """Ergebnis der Aufloesungsmessung aus A1, hier festgehalten."""
    assert {k.fenster_stunden for k in KANDIDATEN} == {1.0}


def test_jeder_kandidat_nennt_seine_wirtschaftliche_begruendung_und_seinen_beleg() -> (
    None
):
    for k in KANDIDATEN:
        assert len(k.konvention) > 60, f"{k.schluessel}: Begruendung zu duenn"
        assert len(k.beleg) > 40, f"{k.schluessel}: kein Beleg"


# --- Der Loader: fail-closed ----------------------------------------------
def test_die_echte_datei_laedt() -> None:
    k = load_ereigniskalender()
    assert k.server_tz == SERVER_TZ_NAME
    assert len(k.kandidaten) == len(KANDIDATEN)
    assert "0,09 bp" in k.server_tz_beleg or "0.09" in k.server_tz_beleg


@pytest.mark.parametrize(
    "feld",
    [
        "calendar_id",
        "calendar_version",
        "verified_on",
        "server_tz",
        "server_tz_beleg",
        "kandidaten",
    ],
)
def test_fehlendes_pflichtfeld_laedt_nicht(tmp_path: Path, feld: str) -> None:
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    del roh[feld]
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(KalenderError, match=feld):
        load_ereigniskalender(ziel)


def test_andere_serverzone_laedt_nicht(tmp_path: Path) -> None:
    """Eine andere Zone heisst anderer Broker — und der braucht eine eigene Messung."""
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    roh["server_tz"] = "Europe/Berlin"
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(KalenderError, match="EIGENE Messung"):
        load_ereigniskalender(ziel)


def test_leerer_zeitzonenbeleg_laedt_nicht(tmp_path: Path) -> None:
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    roh["server_tz_beleg"] = "   "
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(KalenderError, match="Nachweis"):
        load_ereigniskalender(ziel)


def test_datei_die_vom_code_abweicht_laedt_nicht(tmp_path: Path) -> None:
    """Der teuerste stille Fehler waere eine Datei, die etwas anderes sagt als der Code."""
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    roh["kandidaten"][0]["uhrzeit"] = "15:00"
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(KalenderError, match="uhrzeit"):
        load_ereigniskalender(ziel)


def test_veraltete_kalender_id_laedt_nicht(tmp_path: Path) -> None:
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    roh["calendar_id"] = "kalender-v0"
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(KalenderError, match="auseinandergelaufen"):
        load_ereigniskalender(ziel)


def test_kaputte_datei_laedt_nicht(tmp_path: Path) -> None:
    ziel = tmp_path / "ereigniskalender.json"
    ziel.write_text("{kein json", encoding="utf-8")
    with pytest.raises(KalenderError, match="nicht lesbar"):
        load_ereigniskalender(ziel)


def test_die_uhrzeiten_im_code_sind_die_der_datei() -> None:
    """Positivprobe zur Negativprobe oben — sonst prueft sie nur sich selbst."""
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    aus_datei = {e["schluessel"]: e["uhrzeit"] for e in roh["kandidaten"]}
    erwartet = {
        "K1": time(16, 0),
        "K2": time(9, 55),
        "K3": time(16, 0),
        "K4": time(0, 0),
        "K5": time(16, 0),
    }
    for k in KANDIDATEN:
        assert k.uhrzeit == erwartet[k.schluessel]
        assert aus_datei[k.schluessel] == k.uhrzeit.isoformat(timespec="minutes")


def test_kalender_id_ist_die_des_moduls() -> None:
    roh = json.loads(ECHTE_DATEI.read_text(encoding="utf-8"))
    assert roh["calendar_id"] == CALENDAR_POLICY_VERSION

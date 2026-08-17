"""Die Herkunft einer Ereignisstudie muss decken, was gemessen wurde.

Die sieben Studien aus Paket 3a trugen als ``data_checksum`` die Pruefsumme aus
``config/reihen/<Symbol>_H1.manifest.json``. Die Manifeste halten die Reihe fest, wie
``tools/aufloesung.py`` sie geholt hat: mit den **ungedrehten** Serverstempeln und dem
Datenstand ihres eigenen Abrufs. Gemessen wird dagegen auf **gedrehten** und bei jedem
Lauf neu geholten Kerzen. Diese Pruefsumme konnte die gemessenen Daten also nie decken —
und ein Etikett, das nichts deckt, ist schlechter als keines: es sieht nach
Nachpruefbarkeit aus.

Alle Faelle in dieser Datei waeren gegen die alte Fassung fehlgeschlagen; dort gab es
weder eine abgeleitete Pruefsumme noch eine Pruefung einer mitgebrachten.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.ereignisstudie import (
    Kerze,
    StudienError,
    friere_reihe_ein,
    lade_reihe,
    pruefe_deckung,
    reihen_pruefsumme,
    studie,
)
from mt5_trading_ai.backtest.kalender import (
    KalenderError,
    server_zu_utc,
)
from mt5_trading_ai.data.loader import MIN_CHECKSUM_PREFIX

REPO = Path(__file__).resolve().parents[1]
EURUSD_MANIFEST = REPO / "config" / "reihen" / "EURUSD_H1.manifest.json"


def _kerzen(anzahl: int, *, ab: datetime | None = None) -> list[Kerze]:
    start = ab or datetime(2020, 1, 6, tzinfo=UTC)
    kerzen: list[Kerze] = []
    kurs = 100.0
    for i in range(anzahl):
        schluss = kurs * (1.0 + (0.001 if i % 2 == 0 else -0.0008))
        kerzen.append(Kerze(ts=start + timedelta(hours=i), open=kurs, close=schluss))
        kurs = schluss
    return kerzen


def _studie(kerzen: list[Kerze], erwartet: str | None = None) -> str:
    ereignisse = [k.ts for k in kerzen[4:-4:4]]
    ergebnis, _ = studie(
        kandidat="erfunden",
        instrument="ERFUNDEN",
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
        erwartete_pruefsumme=erwartet,
    )
    return ergebnis.reihen_pruefsumme


# --- Die Pruefsumme haengt an den gemessenen Kerzen -----------------------
def test_eine_kerze_mehr_ist_eine_andere_reihe() -> None:
    """Der Eichfall in seiner reinsten Form.

    Zwischen zwei Laeufen kommt eine Stunde dazu — die Studie holt die Kerzen bei
    jedem Lauf frisch. Die alte Fassung meldete fuer beide Laeufe dieselbe Zahl aus
    demselben Manifest und konnte den Unterschied gar nicht sehen. Die neue leitet die
    Zahl aus der Reihe ab, also unterscheiden sich beide.
    """
    kurz = _kerzen(300)
    lang = _kerzen(301)
    assert _studie(kurz) != _studie(lang)
    assert _studie(kurz) == reihen_pruefsumme(kurz)


def test_ein_geaenderter_kurs_aendert_die_pruefsumme() -> None:
    kerzen = _kerzen(300)
    geaendert = list(kerzen)
    geaendert[150] = Kerze(
        ts=kerzen[150].ts, open=kerzen[150].open, close=kerzen[150].close * 1.0001
    )
    assert reihen_pruefsumme(kerzen) != reihen_pruefsumme(geaendert)


def test_dieselbe_reihe_ergibt_dieselbe_pruefsumme() -> None:
    """Sonst waere die Zahl kein Beleg, sondern ein Zufall."""
    assert reihen_pruefsumme(_kerzen(120)) == reihen_pruefsumme(_kerzen(120))


def test_dieselben_kurse_mit_anderer_zeitbasis_sind_andere_daten() -> None:
    """Der Kern des Befundes: Drehung oder nicht macht eine andere Reihe.

    Dieselben Kurse, einmal mit dem Serveretikett und einmal gedreht. Gemessen wird auf
    der gedrehten Reihe; die Manifeste halten die ungedrehte fest. Eine Pruefsumme, die
    beide nicht unterscheidet, deckt hoechstens eine von beiden.
    """
    etikett = _kerzen(120)
    gedreht = [
        Kerze(ts=server_zu_utc(k.ts), open=k.open, close=k.close) for k in etikett
    ]
    assert reihen_pruefsumme(etikett) != reihen_pruefsumme(gedreht)


def test_gleiche_zeitpunkte_in_anderer_zone_ergeben_dieselbe_pruefsumme() -> None:
    """Kanonisch heisst: derselbe Augenblick, dieselbe Zahl — auch als +02:00."""
    utc = _kerzen(48)
    verschoben = [
        Kerze(
            ts=k.ts.astimezone(timezone(timedelta(hours=2))),
            open=k.open,
            close=k.close,
        )
        for k in utc
    ]
    assert reihen_pruefsumme(utc) == reihen_pruefsumme(verschoben)


# --- Eine mitgebrachte Pruefsumme wird geprueft ---------------------------
def test_die_manifest_pruefsumme_deckt_die_gemessene_reihe_nicht() -> None:
    """Der Befund an der echten Zahl: das Manifest aus Paket 3a gegen eine Messung.

    ``3f7474f0...`` steht als ``data_checksum`` an den Studien K1/EURUSD und
    K4/EURUSD im Register. Wird sie als Erwartung mitgegeben, bricht die Studie jetzt
    ab, statt sie als eigene Herkunft weiterzureichen.
    """
    if not EURUSD_MANIFEST.is_file():
        pytest.skip("config/reihen/EURUSD_H1.manifest.json nicht vorhanden")
    manifest = json.loads(EURUSD_MANIFEST.read_text(encoding="utf-8"))
    aus_dem_manifest = str(manifest["checksum"])
    with pytest.raises(StudienError, match="deckt die gemessene Reihe nicht"):
        _studie(_kerzen(300), aus_dem_manifest)


def test_zu_kurze_erwartung_ist_ein_fehler() -> None:
    """Ein kurzes Praefix deckt beliebige Datenstaende — Regel wie im Engine."""
    kerzen = _kerzen(120)
    echt = reihen_pruefsumme(kerzen)
    with pytest.raises(StudienError, match="zu kurz"):
        pruefe_deckung(echt[: MIN_CHECKSUM_PREFIX - 1], kerzen)
    assert pruefe_deckung(echt[:MIN_CHECKSUM_PREFIX], kerzen) == echt


def test_passende_erwartung_geht_durch() -> None:
    kerzen = _kerzen(300)
    assert _studie(kerzen, reihen_pruefsumme(kerzen)) == reihen_pruefsumme(kerzen)


# --- Einfrieren: ohne die Reihe belegt die Pruefsumme nichts --------------
def test_eingefrorene_reihe_laesst_sich_nachrechnen(tmp_path: Path) -> None:
    """Die Kerzen kommen bei jedem Lauf frisch aus dem Terminal — was gemessen wurde,
    gibt es nachher nicht mehr. Erst die festgelegte Reihe macht die Zahl pruefbar."""
    kerzen = _kerzen(300)
    ziel = tmp_path / "reihen" / "ERFUNDEN_H1.reihe"
    pruefsumme = friere_reihe_ein(kerzen, ziel)

    assert pruefsumme == _studie(kerzen)
    zurueck = lade_reihe(ziel)
    assert zurueck == kerzen
    assert reihen_pruefsumme(zurueck) == pruefsumme


def test_kopf_nennt_die_zeitbasis(tmp_path: Path) -> None:
    ziel = tmp_path / "reihe.txt"
    friere_reihe_ein(_kerzen(10), ziel)
    kopf = ziel.read_text(encoding="utf-8").splitlines()[0]
    assert "zeitbasis=echt-utc" in kopf


def test_reihe_mit_fremdem_kopf_wird_nicht_geladen(tmp_path: Path) -> None:
    ziel = tmp_path / "reihe.txt"
    friere_reihe_ein(_kerzen(10), ziel)
    zeilen = ziel.read_text(encoding="utf-8").splitlines()
    zeilen[0] = "ereignisreihe-v1 zeitbasis=server-etikett"
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(StudienError, match="Kopf passt nicht"):
        lade_reihe(ziel)


# --- Zeitbasis: geraten wird nicht ----------------------------------------
def test_naiver_zeitstempel_wird_abgewiesen() -> None:
    """Ein Stempel ohne Zone koennte Serverzeit sein oder UTC. Geraten wird nicht —
    genau dieses Raten ist die Ursache des Zeitproblems dieses Pakets."""
    kerzen = [Kerze(ts=datetime(2020, 1, 6, 1), open=100.0, close=100.1)]
    with pytest.raises(KalenderError, match="ohne Zeitzone"):
        reihen_pruefsumme(kerzen)


def test_leere_reihe_ist_ein_fehler() -> None:
    with pytest.raises(StudienError, match="Leere Reihe"):
        reihen_pruefsumme([])

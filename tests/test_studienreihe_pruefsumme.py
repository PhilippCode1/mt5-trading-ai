"""Die Herkunft einer Ereignisstudie muss decken, was gemessen wurde.

Die sieben Studien aus Paket 3a trugen als ``data_checksum`` die Pruefsumme aus
``config/reihen/<Symbol>_H1.manifest.json``. Die Manifeste halten die Reihe fest, wie
``tools/aufloesung.py`` sie geholt hat: mit den **ungedrehten** Serverstempeln und dem
Datenstand ihres eigenen Abrufs. Gemessen wird dagegen auf **gedrehten** und bei jedem
Lauf neu geholten Kerzen. Diese Pruefsumme konnte die gemessenen Daten also nie decken --
und ein Etikett, das nichts deckt, ist schlechter als keines: es sieht nach
Nachpruefbarkeit aus.

WAS DIESE DATEI PRUEFT UND WAS OFFEN BLEIBT
--------------------------------------------
Geprueft ist die abgeleitete Pruefsumme: ``Ergebnis.reihen_pruefsumme`` entsteht aus
genau den Kerzen, auf denen gemessen wurde, und aus keiner anderen Quelle.

OFFEN und hier ausdruecklich nicht bemaentelt: diese Zahl steht noch nicht im
Register. ``tools/ereignisstudie.py`` schreibt weiter die Manifest-Pruefsumme. Eine
fruehere Fassung hatte dafuer ``friere_reihe_ein``/``lade_reihe``/``pruefe_deckung``
samt Tests -- aber ohne einen einzigen Aufrufer ausserhalb des Moduls und dieser Datei.
Tests fuer eine Vorrichtung, die kein Produktionspfad je betritt, belegen nur, dass sie
uebersetzt. Sie sind mit der Vorrichtung entfallen; der Mangel steht im Modulkopf von
``backtest/ereignisstudie.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from mt5_trading_ai.backtest.ereignisstudie import (
    Kerze,
    StudienError,
    reihen_pruefsumme,
    studie,
)
from mt5_trading_ai.backtest.kalender import (
    KalenderError,
    server_zu_utc,
)

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


def _studie(kerzen: list[Kerze]) -> str:
    ereignisse = [k.ts for k in kerzen[4:-4:4]]
    ergebnis, _ = studie(
        kandidat="erfunden",
        instrument="ERFUNDEN",
        kerzen=kerzen,
        ereignisse=ereignisse,
        fenster_stunden=1.0,
        k_bps=1.0,
    )
    return ergebnis.reihen_pruefsumme


# --- Die Pruefsumme haengt an den gemessenen Kerzen -----------------------
def test_eine_kerze_mehr_ist_eine_andere_reihe() -> None:
    """Der Eichfall in seiner reinsten Form.

    Zwischen zwei Laeufen kommt eine Stunde dazu -- die Studie holt die Kerzen bei
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
    beide nicht unterscheidet, deckt hoechstens eine von beiden. Unterschieden werden
    sie an den STEMPELN -- nicht an einem Etikett im Kopf (siehe den Fall unten).
    """
    etikett = _kerzen(120)
    gedreht = [
        Kerze(ts=server_zu_utc(k.ts), open=k.open, close=k.close) for k in etikett
    ]
    assert reihen_pruefsumme(etikett) != reihen_pruefsumme(gedreht)


def test_gleiche_zeitpunkte_in_anderer_zone_ergeben_dieselbe_pruefsumme() -> None:
    """Kanonisch heisst: derselbe Augenblick, dieselbe Zahl -- auch als +02:00."""
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


def test_die_manifest_pruefsumme_ist_nicht_die_gemessene() -> None:
    """Der Befund an der echten Zahl: das Manifest aus Paket 3a gegen eine Messung.

    ``3f7474f0...`` steht als ``data_checksum`` an den Studien K1/EURUSD und K4/EURUSD
    im Register. Sie ist nicht die Pruefsumme irgendeiner gemessenen Reihe -- sie kann
    es von Bauart her nicht sein. Der Registereintrag traegt sie trotzdem noch; das ist
    der offene Rest von E3 und steht im Modulkopf von ``backtest/ereignisstudie.py``.
    """
    if not EURUSD_MANIFEST.is_file():
        pytest.skip("config/reihen/EURUSD_H1.manifest.json nicht vorhanden")
    manifest = json.loads(EURUSD_MANIFEST.read_text(encoding="utf-8"))
    aus_dem_manifest = str(manifest["checksum"])
    assert _studie(_kerzen(300)) != aus_dem_manifest


# --- Zeitbasis: geraten wird nicht ----------------------------------------
def test_naiver_zeitstempel_wird_abgewiesen() -> None:
    """Ein Stempel ohne Zone koennte Serverzeit sein oder UTC. Geraten wird nicht --
    genau dieses Raten ist die Ursache des Zeitproblems dieses Pakets."""
    kerzen = [Kerze(ts=datetime(2020, 1, 6, 1), open=100.0, close=100.1)]
    with pytest.raises(KalenderError, match="ohne Zeitzone"):
        reihen_pruefsumme(kerzen)


def test_leere_reihe_ist_ein_fehler() -> None:
    with pytest.raises(StudienError, match="Leere Reihe"):
        reihen_pruefsumme([])

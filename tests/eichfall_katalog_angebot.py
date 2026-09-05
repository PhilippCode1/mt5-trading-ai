"""Eichfall E-019: ein Katalogsymbol, das der Broker nicht fuehrt, wird gemessen gefuehrt.

ROT gegen den Stand vor E-019 (Beleg ``belege/09-smoke-lauf1.txt``): der Rauchtest am
Demo-Terminal endete mit ``SMOKE FEHLGESCHLAGEN``, weil ``BTCUSD`` im Katalog steht und
dieser Broker es nicht anbietet (12.455 Symbole in Forex, Indexes, Metals, Nasdaq; kein
Krypto-CFD). ``Mt5Venue.list_instruments`` warf ``UnknownInstrumentError``. A9 war damit
nicht erreichbar -- und die einzigen zwei Auswege waeren gewesen, das Symbol still
wegzulassen (verboten) oder es aus dem Katalog zu nehmen (das entscheidet Auftrag 3).

GRUEN hier: der Katalogeintrag traegt die Messung (``nicht_angeboten`` mit Broker, Datum
und Beleg). Damit ist das Universum vollstaendig **und** wahr:

* ohne Messung bleibt ein unaufloesbares Symbol ein Fehler -- der Vertrag ist unveraendert;
* mit Messung faellt es nicht still weg, sondern steht im Rauchtest als benannter Schritt;
* loest das Terminal es DOCH auf, ist die Messung veraltet und das wiederum ein Fehler.

Die dritte Richtung ist der Kern: eine Ausnahme, die nur in eine Richtung geprueft wird,
verfaellt beim naechsten Broker- oder Kontowechsel zu einer stillen Luecke.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.venue.catalog import (
    Angebotsbefund,
    InstrumentCatalogError,
    load_instrument_catalog,
)
from mt5_trading_ai.venue.protocol import UnknownInstrumentError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_mt5_venue import _catalog  # noqa: E402
from test_zweige_mt5 import _Terminal, _venue_mit  # noqa: E402

KATALOGDATEI = ROOT / "config" / "instrument_catalog.json"


def test_der_eingecheckte_katalog_fuehrt_btcusd_als_gemessen_nicht_angeboten() -> None:
    """Die Messung steht in der Datei -- mit Broker, Datum und Beleg, nicht als Wort."""
    katalog = load_instrument_catalog()
    befund = katalog["BTCUSD"].nicht_angeboten

    assert befund is not None, "BTCUSD ist am gemessenen Broker nicht handelbar"
    assert befund.broker == "MetaQuotes-Demo"
    assert befund.gemessen_am == date(2026, 9, 4)
    assert (ROOT / befund.beleg).is_file(), f"Beleg fehlt: {befund.beleg}"
    assert katalog["EURUSD"].nicht_angeboten is None, "der Normalfall bleibt leer"


@pytest.mark.parametrize(
    "fehlt", ["broker", "gemessen_am", "beleg"], ids=lambda f: f"ohne-{f}"
)
def test_eine_halbe_messung_macht_die_katalogdatei_unbrauchbar(
    tmp_path: Path, fehlt: str
) -> None:
    """ROTER EICHFALL: ohne Broker, Datum oder Beleg ist es keine Messung.

    Ein halb ausgefuellter Block naehme ein Symbol aus dem Universum, ohne dass
    jemand nachschlagen kann, worauf das beruht -- dieselbe Luecke wie das stille
    Weglassen, nur mit besserem Gewissen.
    """
    daten: dict[str, Any] = json.loads(KATALOGDATEI.read_text(encoding="utf-8"))
    block = {
        "broker": "X-Demo",
        "gemessen_am": "2026-09-04",
        "beleg": "PROGRAMM/auftrag-01-fundament/belege/09-smoke-lauf1.txt",
    }
    del block[fehlt]
    daten["instruments"]["BTCUSD"]["nicht_angeboten"] = block
    ziel = tmp_path / "katalog.json"
    ziel.write_text(json.dumps(daten), encoding="utf-8")

    with pytest.raises(InstrumentCatalogError, match=f"nicht_angeboten ohne {fehlt}"):
        load_instrument_catalog(ziel)


def _mit_fremdsymbol(nicht_angeboten: Angebotsbefund | None) -> dict[str, Any]:
    """Der Testkatalog plus ein Symbol, das das Fake-Terminal NICHT fuehrt."""
    katalog = dict(_catalog())
    katalog["XYZUSD"] = dataclasses.replace(
        katalog["EURUSD"], nicht_angeboten=nicht_angeboten
    )
    return katalog


def test_ohne_messung_bleibt_ein_unbekanntes_symbol_ein_fehler() -> None:
    """Der Vertrag ist unveraendert: nur die MESSUNG macht den Unterschied."""
    venue = _venue_mit(_Terminal(), katalog=_mit_fremdsymbol(None))

    with pytest.raises(UnknownInstrumentError, match="XYZUSD"):
        venue.list_instruments()


def test_mit_messung_ist_das_universum_vollstaendig() -> None:
    """Dasselbe Terminal, derselbe Katalog -- nur mit der Messung am Eintrag."""
    venue = _venue_mit(
        _Terminal(),
        katalog=_mit_fremdsymbol(
            Angebotsbefund(
                broker="MetaQuotes-Demo",
                gemessen_am=date(2026, 9, 4),
                beleg="PROGRAMM/auftrag-01-fundament/belege/09-smoke-lauf1.txt",
            )
        ),
    )

    namen = [i.symbol for i in venue.list_instruments()]
    assert "XYZUSD" not in namen
    assert namen == ["EURUSD", "BTCUSD"], namen


def test_eine_veraltete_messung_ist_ein_fehler() -> None:
    """Die dritte Richtung: das Terminal loest das Symbol DOCH auf.

    Ohne diese Pruefung waere die Ausnahme eine Einbahnstrasse -- ein Kontowechsel,
    bei dem der Broker das Instrument fuehrt, liesse es dauerhaft aus dem Universum
    fallen, und niemand saehe es.
    """
    katalog = dict(_catalog())
    katalog["BTCUSD"] = dataclasses.replace(
        katalog["BTCUSD"],
        nicht_angeboten=Angebotsbefund(
            broker="MetaQuotes-Demo",
            gemessen_am=date(2026, 9, 4),
            beleg="PROGRAMM/auftrag-01-fundament/belege/09-smoke-lauf1.txt",
        ),
    )
    venue = _venue_mit(_Terminal(), katalog=katalog)

    with pytest.raises(UnknownInstrumentError, match="Messung im Katalog ist veraltet"):
        venue.list_instruments()

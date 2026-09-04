"""Der Risikozustand traegt kein Geheimnis -- festgenagelt, nicht behauptet.

WARUM DIESE DATEI EIGENS EXISTIERT
----------------------------------
``tools/geheimnis_scan.py`` laeuft in der CI, prueft aber nur, was **git verfolgt** und
was im Verlauf steht. Die Zustandsdatei ist beides nicht: sie liegt ausserhalb des
Arbeitsbaums und wird zur Laufzeit erzeugt. Genau darum ist sie der gefaehrliche Fall
-- niemand sieht sie, und sie ist der Anhang, der in einem Fehlerbericht landet.

Dieser Test dreht die Richtung um: er **erzeugt** eine Zustandsdatei und faehrt die
Muster der CI-Pruefung darueber. Damit gilt fuer die erzeugte Datei derselbe Massstab
wie fuer eine eingecheckte. Die Muster werden aus ``tools/geheimnis_scan.py``
importiert und nicht abgeschrieben: eine zweite Kopie liefe irgendwann auseinander, und
dann prueft dieser Test etwas anderes als die CI.

Zusaetzlich steht hier ein **Schluesselvertrag**: welche Felder die Datei ueberhaupt
haben darf. Ein reiner Musterlauf faende nur die heute bekannten Gattungen; der
Schluesselvertrag reisst auch dann, wenn eine spaetere Welle ein neues Feld einfuehrt,
das die Muster noch nicht kennen -- und zwingt damit zu einer Entscheidung statt zu
einem Versehen.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from mt5_trading_ai.execution.risiko_zustand import DateiZustand, RisikoLage
from tools.geheimnis_scan import MUSTER

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

#: Echte MT5-Logins sind 6 bis 12 Ziffern. Genau diese Gattung sucht
#: ``tools/geheimnis_scan.py`` unter „Kontonummer".
LOGINS = ("123456", "50123456", "1234567890", "987654321012")

#: Alles, was die Datei auf oberster Ebene haben darf. Aenderungen hier sind eine
#: bewusste Entscheidung -- siehe Modul-Docstring.
ERLAUBTE_FELDER = {
    "schema",
    "geschrieben_am",
    "waehrung",
    "bindung",
    "halt",
    "tageszaehler",
    "letzter_trade_at",
    "equity",
    "offene_positionen",
}


def _zustandsdatei(pfad: Path, login: str, waehrung: str = "USD") -> bytes:
    """Eine vollstaendig gefuellte Zustandsdatei -- moeglichst viel Angriffsflaeche."""
    speicher = DateiZustand(pfad)
    speicher.laden()
    assert speicher.binde(login, waehrung) is None
    speicher.sichern(
        RisikoLage(
            halt=True,
            halt_grund="drawdown_halt_gelatcht",
            halt_seit=NOW,
            handelstag=NOW.date(),
            zaehler_gesperrt=True,
            trades_je_instrument={"EURUSD": 3, "XAUUSD": 1},
            trades_konto=4,
            letzter_trade_at={"EURUSD": NOW},
            equity_tag=NOW.date(),
            tagesstart_equity=Decimal("10000.00"),
            equity_fenster=[(NOW, Decimal("10250.50"))],
            offene_positionen=[("EURUSD", NOW)],
        )
    )
    return pfad.read_bytes()


def test_die_kontonummer_steht_nicht_in_der_datei(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Nicht im Klartext, nicht in irgendeiner Feldform -- fuer jede Login-Laenge."""
    for index, login in enumerate(LOGINS):
        roh = _zustandsdatei(tmp_path / f"z{index}.json", login)
        assert login.encode() not in roh, f"Login {login} steht in der Datei"


def test_der_abdruck_ist_kein_blanker_hash(tmp_path) -> None:
    """Ein blanker SHA-256 waere keine Verschleierung, sondern eine Kodierung.

    Ein 6- bis 12-stelliger Login hat hoechstens 10**12 Kandidaten; die durch SHA-256
    zu schicken ist Minutensache. Der Abdruck muss also gesalzen und gestreckt sein --
    dieser Test verbietet den bequemen Rueckfall auf ``sha256(login)``.
    """
    roh = _zustandsdatei(tmp_path / "z.json", "50123456")
    daten: dict[str, Any] = json.loads(roh.decode("utf-8"))
    abdruck = daten["bindung"]["abdruck"]
    assert abdruck != hashlib.sha256(b"50123456").hexdigest()
    assert daten["bindung"]["runden"] >= 100_000
    assert len(bytes.fromhex(daten["bindung"]["salz"])) >= 16


def test_zwei_konten_bekommen_verschiedene_abdruecke(tmp_path) -> None:
    """Sonst waere die Bindung ein Melder, der nie ausloest.

    Die Gegenprobe zum Rest dieser Datei: die Ableitung darf nicht so weit
    verschleiern, dass sie zwei Konten gleich aussehen laesst.
    """
    a = json.loads(_zustandsdatei(tmp_path / "a.json", "50123456").decode("utf-8"))
    b = json.loads(_zustandsdatei(tmp_path / "b.json", "99887766").decode("utf-8"))
    assert a["bindung"]["abdruck"] != b["bindung"]["abdruck"]
    # Und auch dasselbe Konto bekommt je Datei ein eigenes Salz -- sonst waere der
    # Abdruck ueber Dateien hinweg dieselbe Kennung und damit selbst ein Merkmal.
    c = json.loads(_zustandsdatei(tmp_path / "c.json", "50123456").decode("utf-8"))
    assert a["bindung"]["salz"] != c["bindung"]["salz"]
    assert a["bindung"]["abdruck"] != c["bindung"]["abdruck"]


def test_die_muster_der_ci_pruefung_finden_nichts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Dieselben Muster, die ``tools/geheimnis_scan.py`` in der CI faehrt."""
    funde: list[str] = []
    for index, login in enumerate(LOGINS):
        roh = _zustandsdatei(tmp_path / f"z{index}.json", login)
        for titel, muster in MUSTER:
            for treffer in muster.finditer(roh):
                funde.append(f"{titel}: {treffer.group(0)!r}")
    assert funde == []


def test_nur_vereinbarte_felder_stehen_in_der_datei(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Der Schluesselvertrag: ein neues Feld muss hier eingetragen werden.

    Ohne ihn faende dieser Test nur die heute bekannten Geheimnisgattungen. Ein
    spaeter eingefuehrtes ``server`` oder ``login`` liefe durch, bis jemand ein neues
    Muster schreibt -- also vermutlich nie.
    """
    daten: dict[str, Any] = json.loads(
        _zustandsdatei(tmp_path / "z.json", "50123456").decode("utf-8")
    )
    assert set(daten) == ERLAUBTE_FELDER
    assert set(daten["bindung"]) == {"salz", "runden", "abdruck"}
    # Die Waehrung steht im Klartext und darf es: „USD" identifiziert niemanden,
    # und ohne sie koennte eine Abweichung nicht sagen, WAS abweicht.
    assert daten["waehrung"] == "USD"


def test_auch_die_ungebundene_datei_traegt_nur_vereinbarte_felder(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Die zweite Dateiform faellt nicht durch den Schluesselvertrag.

    Zwischen Prozessstart und erster Autorisierung schreibt der Speicher eine
    **ungebundene** Datei: nur das Equity-Fenster. Sie ist per Bauart harmlos -- sie
    kennt kein Konto --, aber genau das ist der Satz, den man in einer spaeteren Welle
    ungeprueft weiterschreibt. Also festgenagelt statt behauptet.
    """
    pfad = tmp_path / "z.json"
    speicher = DateiZustand(pfad)
    speicher.laden()  # keine Bindung
    speicher.sichern(RisikoLage(equity_fenster=[(NOW, Decimal("10250.50"))]))

    roh = pfad.read_bytes()
    daten: dict[str, Any] = json.loads(roh.decode("utf-8"))
    assert set(daten) == {"schema", "geschrieben_am", "equity"}
    assert set(daten["equity"]) == {"fenster"}
    funde = [
        f"{titel}: {treffer.group(0)!r}"
        for titel, muster in MUSTER
        for treffer in muster.finditer(roh)
    ]
    assert funde == []


def test_der_dateiname_traegt_die_kontonummer_nicht(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Ein aus dem Konto abgeleiteter Name waere ein Leck an der Datei vorbei.

    Er waere ausserdem ein Loch: das noetige Salz muesste neben den Dateien liegen,
    und ein verlorenes Salz liesse jeden Zustand unauffindbar -- also jeden Halt
    lautlos verschwinden.
    """
    from mt5_trading_ai.execution.risiko_zustand import standard_zustandsdatei

    pfad = standard_zustandsdatei(ordner=tmp_path)
    _zustandsdatei(pfad, "50123456")
    for datei in tmp_path.iterdir():
        assert "50123456" not in datei.name

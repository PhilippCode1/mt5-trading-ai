"""Instrumentenkatalog — die Metadaten, die MT5 nicht liefert.

MT5 kennt je Symbol Tick-Groesse, Volumina und Stop-Level, aber **nicht** die
Anlageklasse (die den gesetzlichen Hebeldeckel steuert), das Kostenmodell und die
Handelszeiten. Die stehen in einer versionierten Datei mit Quelle, Gueltigkeits- und
Pruefdatum — eine Aenderung ist damit eine Datenaenderung, keine Codeaenderung.

Fail-closed: jeder Defekt ist ein Fehler, kein Default. Ein Symbol ohne Katalogeintrag
ist unbekannt, und der Handelsplatz lehnt es ab (siehe ``Mt5Venue.get_instrument``). Die
``asset_class`` muss ein bekannter Wert sein — sonst faende die Hebelklammer keinen
Deckel. Umgekehrt gilt dasselbe: ein Katalogeintrag, den das Terminal nicht aufloest,
verschwindet nicht still aus dem Universum, sondern ist ein Fehler
(``Mt5Venue.list_instruments``).

``valid_from`` und ``verified_on`` werden nicht nur auf Anwesenheit, sondern auf
**Form** geprueft (``YYYY-MM-DD``). Sie sind der einzige Beleg dafuer, wann die Zahlen
darunter gegen den Broker gehalten wurden; ein Pruefdatum, das kein Datum ist, belegt
nichts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mt5_trading_ai.venue.protocol import AssetClass, FeeSchedule, TradingSession

INSTRUMENT_CATALOG_VERSION = "instrument-catalog-v1"
CATALOG_FILENAME = "instrument_catalog.json"

#: Minuten eines Tages. ``"24:00"`` (= 1440) ist als **Schluss** ausdruecklich
#: erlaubt, als Oeffnung nicht -- siehe :func:`session_minutes`.
MINUTEN_JE_TAG = 24 * 60

_FEE_DECIMAL_FIELDS = (
    "commission_per_lot_round_turn",
    "typical_spread_points",
    "swap_long_per_lot_per_night",
    "swap_short_per_lot_per_night",
)


class InstrumentCatalogError(ValueError):
    """Die Katalog-Datei ist unbrauchbar. Fail-closed: kein Handel."""


@dataclass(frozen=True)
class GapSperre:
    """Die zwei Zahlen der Gap-Sperre (Befund D13, ``execution/handelspause.py``).

    ``vorlauf``: so lange vor Beginn einer Handelspause wird nicht mehr eroeffnet.
    ``mindestpause``: erst eine Pause dieser Laenge zaehlt als Luecke (die taegliche
    Luecke 21:00-24:00 UTC des FX-Fensters ist keine).
    """

    vorlauf: timedelta
    mindestpause: timedelta

    def __post_init__(self) -> None:
        if self.vorlauf <= timedelta(0):
            raise InstrumentCatalogError("Gap-Sperre: vorlauf muss positiv sein")
        if self.mindestpause <= timedelta(0):
            raise InstrumentCatalogError("Gap-Sperre: mindestpause muss positiv sein")

    def verengt_hoechstens(self, standard: GapSperre) -> bool:
        """Ist diese Sperre mindestens so streng wie ``standard``?

        Strenger heisst: laengerer Vorlauf oder kuerzere Mindestpause. Die Datei darf
        die Sperre nur verengen -- wie die Sitzungstabelle (``_sessions_status``).
        """
        return (
            self.vorlauf >= standard.vorlauf
            and self.mindestpause <= standard.mindestpause
        )


#: Konservativer Standard der Gap-Sperre; Herkunft der Zahlen steht im Katalogblock
#: ``_gap_sperre`` (``config/instrument_catalog.json``) und im Modulkopf von
#: ``execution/handelspause.py``. Die Datei darf ihn nur verengen (Regel: keine
#: Schwelle sinkt); fehlt der Block, gilt der Standard -- ein fehlender Block oeffnet
#: nichts.
GAP_SPERRE_STANDARD = GapSperre(
    vorlauf=timedelta(minutes=120), mindestpause=timedelta(hours=24)
)
GAP_SPERRE_SCHLUESSEL = "_gap_sperre"


@dataclass(frozen=True)
class CatalogEntry:
    """Metadaten je Symbol, die MT5 nicht liefert: Klasse, Kosten, Handelszeiten.

    ``asset_class`` ist Pflicht — sie steuert den gesetzlichen Hebeldeckel.
    ``gap_sperre`` traegt die Zahlen der Gap-Sperre aus dem Katalogblock
    ``_gap_sperre``; ein handgebauter Eintrag bekommt den Standard.
    """

    asset_class: AssetClass
    fees: FeeSchedule
    sessions: tuple[TradingSession, ...]
    gap_sperre: GapSperre = GAP_SPERRE_STANDARD


def default_catalog_path() -> Path:
    """Suche aufwaerts nach ``config/instrument_catalog.json``.

    Bewusst kein ENV-Override — der Katalog ist Teil der gepruften Datenlage, kein
    Laufzeitschalter. Paketinterne Kopie als letzter Rueckfall (Wheel ohne Repo-Baum).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / CATALOG_FILENAME
        if candidate.is_file():
            return candidate
    return here.parent / "data" / CATALOG_FILENAME


def load_instrument_catalog(path: Path | str | None = None) -> dict[str, CatalogEntry]:
    """Lade und validiere den Katalog. Jeder Defekt ist ein Fehler, kein Default."""
    catalog_path = Path(path) if path is not None else default_catalog_path()
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InstrumentCatalogError(f"Katalog-Datei fehlt: {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise InstrumentCatalogError(
            f"Katalog-Datei ist kein gueltiges JSON: {exc}"
        ) from exc

    for field in ("catalog_id", "valid_from", "verified_on", "instruments"):
        if field not in raw:
            raise InstrumentCatalogError(f"Katalog-Datei ohne Pflichtfeld {field!r}")

    _pruefe_datum("valid_from", raw["valid_from"])
    _pruefe_datum("verified_on", raw["verified_on"])

    instruments = raw["instruments"]
    if not isinstance(instruments, dict) or not instruments:
        raise InstrumentCatalogError("Katalog-Datei ohne Instrumente")

    gap = _parse_gap_sperre(raw.get(GAP_SPERRE_SCHLUESSEL))
    out: dict[str, CatalogEntry] = {}
    for symbol, entry in instruments.items():
        out[str(symbol)] = _parse_entry(str(symbol), entry, gap)
    return out


def _parse_gap_sperre(block: Any) -> GapSperre:
    """Den Katalogblock ``_gap_sperre`` lesen -- fehlt er, gilt der Standard.

    Fail-closed in der einen Richtung, die zaehlt: ein Block, der die Sperre
    **lockert** (kuerzerer Vorlauf oder laengere Mindestpause als der Standard), ist
    ein Fehler und kein Wert. Eine Datei kann die Sperre damit nur verengen -- wie die
    Sitzungstabelle den Platz nur schliessen kann. Jeder andere Defekt (kein Objekt,
    keine ganze Zahl, nicht positiv) ist ebenfalls ein Fehler.
    """
    if block is None:
        return GAP_SPERRE_STANDARD
    if not isinstance(block, dict):
        raise InstrumentCatalogError(
            f"Katalog-Datei: {GAP_SPERRE_SCHLUESSEL} ist kein Objekt: {block!r}"
        )

    def ganzzahl(field: str) -> int:
        value = block.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise InstrumentCatalogError(
                f"Katalog-Datei: {GAP_SPERRE_SCHLUESSEL}.{field} ist keine positive "
                f"ganze Zahl: {value!r}"
            )
        return value

    gelesen = GapSperre(
        vorlauf=timedelta(minutes=ganzzahl("vorlauf_minuten")),
        mindestpause=timedelta(hours=ganzzahl("mindestpause_stunden")),
    )
    if not gelesen.verengt_hoechstens(GAP_SPERRE_STANDARD):
        raise InstrumentCatalogError(
            f"Katalog-Datei: {GAP_SPERRE_SCHLUESSEL} lockert die Sperre "
            f"(vorlauf {gelesen.vorlauf}, mindestpause {gelesen.mindestpause}) unter "
            f"den Standard (vorlauf {GAP_SPERRE_STANDARD.vorlauf}, mindestpause "
            f"{GAP_SPERRE_STANDARD.mindestpause}) -- die Datei darf nur verengen"
        )
    return gelesen


def _pruefe_datum(field: str, value: Any) -> date:
    """``valid_from``/``verified_on`` muessen echte Kalendertage sein (``YYYY-MM-DD``).

    Bis hierher wurde nur geprueft, dass der Schluessel **da** ist. Ein
    ``"verified_on": "irgendwann"`` kam damit klaglos durch -- und genau dieses Feld ist
    der ganze Beleg dafuer, dass jemand die Zahlen darunter einmal gegen den Broker
    gehalten hat. Ein Pruefdatum, das kein Datum ist, ist keine schlechtere Angabe als
    ein gutes; es ist gar keine. Fail-closed wie alles in dieser Datei: jeder Defekt ist
    ein Fehler, kein Default.

    Geprueft wird die **Form**, nicht die Wahrheit: dass am genannten Tag wirklich
    jemand nachgesehen hat, kann diese Datei nicht wissen (und behauptet es auch nicht).
    ``date.fromisoformat`` allein reicht dafuer nicht -- es nimmt seit 3.11 auch
    ``"20260812"`` und volle Zeitstempel an. Verlangt wird die eine Schreibweise, die
    im Datenbestand steht und sich sortieren laesst.
    """
    text = value if isinstance(value, str) else None
    if text is None or len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise InstrumentCatalogError(
            f"Katalog-Datei: {field} ist kein Datum als YYYY-MM-DD: {value!r}"
        )
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise InstrumentCatalogError(
            f"Katalog-Datei: {field} ist kein gueltiger Kalendertag: {value!r}"
        ) from exc


def _parse_entry(
    symbol: str, entry: Any, gap: GapSperre = GAP_SPERRE_STANDARD
) -> CatalogEntry:
    if not isinstance(entry, dict):
        raise InstrumentCatalogError(f"{symbol}: Eintrag ist kein Objekt")
    return CatalogEntry(
        asset_class=_parse_asset_class(symbol, entry.get("asset_class")),
        fees=_parse_fees(symbol, entry.get("fees")),
        sessions=_parse_sessions(symbol, entry.get("sessions")),
        gap_sperre=gap,
    )


def _parse_asset_class(symbol: str, value: Any) -> AssetClass:
    try:
        return AssetClass(str(value))
    except ValueError as exc:
        raise InstrumentCatalogError(
            f"{symbol}: unbekannte Anlageklasse {value!r}"
        ) from exc


def _decimal(symbol: str, field: str, value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InstrumentCatalogError(
            f"{symbol}: Feld {field!r} ist keine Zahl: {value!r}"
        ) from exc


def _parse_fees(symbol: str, value: Any) -> FeeSchedule:
    if not isinstance(value, dict):
        raise InstrumentCatalogError(f"{symbol}: fees fehlt oder ist kein Objekt")

    def fee(field: str) -> Decimal:
        return _decimal(symbol, field, value.get(field))

    currency = str(value.get("currency") or "")
    if not currency:
        raise InstrumentCatalogError(f"{symbol}: fees ohne currency")
    triple = value.get("triple_swap_weekday")
    return FeeSchedule(
        commission_per_lot_round_turn=fee("commission_per_lot_round_turn"),
        typical_spread_points=fee("typical_spread_points"),
        swap_long_per_lot_per_night=fee("swap_long_per_lot_per_night"),
        swap_short_per_lot_per_night=fee("swap_short_per_lot_per_night"),
        triple_swap_weekday=int(triple) if triple is not None else None,
        currency=currency,
    )


def session_minutes(value: str) -> int:
    """``"HH:MM"`` -> Minuten seit Mitternacht. Jede andere Form ist ein Fehler.

    Bis hierher stand die Umrechnung ungeprueft in ``venue/mt5.py``: ein
    ``int(hours) * 60 + int(minutes)`` ohne Formatpruefung und ohne Wertebereich.
    ``"25:99"`` ergab damit klaglos 1599 Minuten, ``"9"`` warf einen nackten
    ``ValueError`` mitten im Handelszeitfilter. Eine Katalogdatei ist eine
    **belegpflichtige** Datei; ein Wert, den niemand liest, ist kein Beleg.

    ``"24:00"`` ist erlaubt und meint das **Tagesende**, nicht den Tagesanfang. Ohne
    diese Schreibweise laesst sich eine Sitzung, die bis Mitternacht laeuft, gar nicht
    ausdruecken: ``"00:00"`` als Schluss waere null Minuten nach Tagesbeginn, und ein
    ``"23:59"`` reisst jede Nacht ein Loch von einer Minute in einen durchgehenden
    Strom (genau das stand fuer BTCUSD im Katalog). Als **Oeffnung** ist ``"24:00"``
    sinnlos und darum verboten -- eine Sitzung, die am Tagesende beginnt, ist eine
    Sitzung des Folgetags.
    """
    teile = value.split(":")
    if len(teile) != 2 or len(teile[0]) != 2 or len(teile[1]) != 2:
        raise InstrumentCatalogError(f"Uhrzeit nicht als HH:MM geschrieben: {value!r}")
    if not (teile[0].isdigit() and teile[1].isdigit()):
        raise InstrumentCatalogError(f"Uhrzeit ist keine Zahl: {value!r}")
    stunden, minuten = int(teile[0]), int(teile[1])
    if stunden == 24 and minuten == 0:
        return MINUTEN_JE_TAG
    if not (0 <= stunden <= 23 and 0 <= minuten <= 59):
        raise InstrumentCatalogError(f"Uhrzeit ausserhalb des Tages: {value!r}")
    return stunden * 60 + minuten


def _parse_sessions(symbol: str, value: Any) -> tuple[TradingSession, ...]:
    """Sitzungsfenster lesen -- und jedes einzelne auf Sinn pruefen.

    Der Katalog ist die einzige Quelle der Handelszeiten, und der Filter
    (``Mt5Venue.is_trading_open``) rechnet ohne weitere Pruefung mit dem, was hier
    herauskommt. Ein Wochentag 9 oder ein Schluss ``"25:99"`` erzeugte bis hierher ein
    Fenster, das der Filter still ins Leere laufen liess -- also eine Sperre, die
    nicht mehr sperrt. Fail-closed: jeder Defekt ist ein Fehler, kein Default.

    Ein Fenster mit ``open == close`` wird abgelehnt, weil es zwei Lesarten hat
    (null Minuten oder volle 24 Stunden) und beide plausibel sind. Wer 24 Stunden
    meint, schreibt ``"00:00"`` bis ``"24:00"``.
    """
    if not isinstance(value, list) or not value:
        raise InstrumentCatalogError(f"{symbol}: sessions fehlt oder ist leer")
    out: list[TradingSession] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise InstrumentCatalogError(f"{symbol}: Session ist kein Objekt")
        try:
            weekday = int(entry["weekday"])
            auf = str(entry["open_utc"])
            zu = str(entry["close_utc"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InstrumentCatalogError(
                f"{symbol}: Session unvollstaendig oder falsch: {entry!r}"
            ) from exc
        if not 0 <= weekday <= 6:
            raise InstrumentCatalogError(
                f"{symbol}: Wochentag {weekday} liegt nicht in 0..6 (0 = Montag)"
            )
        try:
            auf_min, zu_min = session_minutes(auf), session_minutes(zu)
        except InstrumentCatalogError as exc:
            raise InstrumentCatalogError(f"{symbol}: {exc}") from exc
        if auf_min >= MINUTEN_JE_TAG:
            raise InstrumentCatalogError(
                f"{symbol}: Sitzungsbeginn {auf!r} liegt am Tagesende -- eine Sitzung, "
                "die um 24:00 beginnt, gehoert auf den Folgetag"
            )
        if auf_min == zu_min:
            raise InstrumentCatalogError(
                f"{symbol}: Sitzung {auf!r}-{zu!r} ist mehrdeutig (null Minuten oder "
                "volle 24 Stunden?) -- fuer einen ganzen Tag 00:00-24:00 schreiben"
            )
        out.append(TradingSession(weekday=weekday, open_utc=auf, close_utc=zu))
    return tuple(out)

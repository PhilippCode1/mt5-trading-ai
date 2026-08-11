"""Instrumentenkatalog — die Metadaten, die MT5 nicht liefert.

MT5 kennt je Symbol Tick-Groesse, Volumina und Stop-Level, aber **nicht** die
Anlageklasse (die den gesetzlichen Hebeldeckel steuert), das Kostenmodell und die
Handelszeiten. Die stehen in einer versionierten Datei mit Quelle, Gueltigkeits- und
Pruefdatum — eine Aenderung ist damit eine Datenaenderung, keine Codeaenderung.

Fail-closed: jeder Defekt ist ein Fehler, kein Default. Ein Symbol ohne Katalogeintrag
ist unbekannt, und der Handelsplatz lehnt es ab (siehe ``Mt5Venue.get_instrument``). Die
``asset_class`` muss ein bekannter Wert sein — sonst faende die Hebelklammer keinen
Deckel.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mt5_trading_ai.venue.protocol import AssetClass, FeeSchedule, TradingSession

INSTRUMENT_CATALOG_VERSION = "instrument-catalog-v1"
CATALOG_FILENAME = "instrument_catalog.json"

_FEE_DECIMAL_FIELDS = (
    "commission_per_lot_round_turn",
    "typical_spread_points",
    "swap_long_per_lot_per_night",
    "swap_short_per_lot_per_night",
)


class InstrumentCatalogError(ValueError):
    """Die Katalog-Datei ist unbrauchbar. Fail-closed: kein Handel."""


@dataclass(frozen=True)
class CatalogEntry:
    """Metadaten je Symbol, die MT5 nicht liefert: Klasse, Kosten, Handelszeiten.

    ``asset_class`` ist Pflicht — sie steuert den gesetzlichen Hebeldeckel.
    """

    asset_class: AssetClass
    fees: FeeSchedule
    sessions: tuple[TradingSession, ...]


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

    instruments = raw["instruments"]
    if not isinstance(instruments, dict) or not instruments:
        raise InstrumentCatalogError("Katalog-Datei ohne Instrumente")

    out: dict[str, CatalogEntry] = {}
    for symbol, entry in instruments.items():
        out[str(symbol)] = _parse_entry(str(symbol), entry)
    return out


def _parse_entry(symbol: str, entry: Any) -> CatalogEntry:
    if not isinstance(entry, dict):
        raise InstrumentCatalogError(f"{symbol}: Eintrag ist kein Objekt")
    return CatalogEntry(
        asset_class=_parse_asset_class(symbol, entry.get("asset_class")),
        fees=_parse_fees(symbol, entry.get("fees")),
        sessions=_parse_sessions(symbol, entry.get("sessions")),
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


def _parse_sessions(symbol: str, value: Any) -> tuple[TradingSession, ...]:
    if not isinstance(value, list) or not value:
        raise InstrumentCatalogError(f"{symbol}: sessions fehlt oder ist leer")
    out: list[TradingSession] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise InstrumentCatalogError(f"{symbol}: Session ist kein Objekt")
        try:
            out.append(
                TradingSession(
                    weekday=int(entry["weekday"]),
                    open_utc=str(entry["open_utc"]),
                    close_utc=str(entry["close_utc"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InstrumentCatalogError(
                f"{symbol}: Session unvollstaendig oder falsch: {entry!r}"
            ) from exc
    return tuple(out)

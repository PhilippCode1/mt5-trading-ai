"""Broker-Kostentabelle — versioniert, belegt, fail-closed.

WARUM DIESES MODUL
------------------
``config/instrument_catalog.json`` traegt **ein** indikatives Kostenprofil je Symbol,
gedacht fuer den Betrieb an genau einem Konto. Das Kostentor (A1) braucht etwas
anderes: dieselben Instrumente bei **mehreren** Brokern, jede Zahl mit Quelle und
Abrufdatum, und die ehrliche Unterscheidung zwischen einem abgelesenen typischen
Spread und einem Werbewert („ab 0,0 Pips"). Beides in eine Datei zu pressen haette
den Katalog zu einem Recherchearchiv gemacht; darum eine eigene Datei nach demselben
Muster: ``config/broker_costs.json``.

DIE EINHEITENFALLE — UND WIE SIE HIER GESCHLOSSEN IST
-----------------------------------------------------
Broker veroeffentlichen Spreads in Pips, in Punkten, in Indexpunkten oder in nackten
Zahlen ohne jede Einheitsangabe. Wer diese Zahlen ungeprueft in eine Rechnung schiebt,
verrechnet sich um Faktor 10, 100 oder 1000 — und merkt es nicht, weil das Ergebnis
plausibel aussieht. Deshalb steht hier **jede** Spreadangabe dreiteilig:

* ``spread_published`` — die Zahl, wie sie auf der Quelle steht.
* ``spread_unit`` — die Einheit, wie sie auf der Quelle steht (Freitext, zum Nachlesen).
* ``unit_in_price`` — wie viel **eine** solche Einheit in Preiseinheiten des Instruments
  ist (Pip auf EURUSD = 0,0001; Indexpunkt auf DE40 = 1).

Der wirksame Spread in Preiseinheiten ist damit ein **gerechneter**, nicht ein
abgetippter Wert. Die Umrechnung steht sichtbar in der Datei und nicht im Kopf dessen,
der sie eingetragen hat.

FAIL-CLOSED
-----------
Jeder Defekt ist ein Fehler, kein Default (wie ``venue/catalog.py``, aber mit dem
strengeren Kopfblock von ``risk/leverage.py``). Konkret:

* Eine Zeile ohne ``source_url`` oder ohne ``retrieved_on`` ist unbrauchbar — eine
  Kostenzahl ohne Quelle ist eine Behauptung.
* Ein Werbewert (``spread_kind = "ab-wert"``) verlangt einen **bezifferten** Aufschlag
  ``spread_markup_factor`` > 1. Ein stiller Aufschlag waere schlimmer als gar keiner,
  weil er im Ergebnis nicht mehr zu erkennen ist.
* ``unit_in_price`` muss positiv sein. Fehlt sie, ist der Spread nicht umrechenbar,
  und ein nicht umrechenbarer Spread darf nicht als Null durchgehen.
* Eine Kommission > 0 ohne ``commission_currency`` ist nicht umrechenbar — Fehler.
* ``status = "nicht_gefuehrt"`` (der Broker bietet das Instrument nicht an) verlangt
  eine Begruendung. Das ist ein Ergebnis, kein Loch.
* Ein unbekannter ``status`` bricht ab, statt auf einen Default zu fallen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

BROKER_COSTS_VERSION = "broker-costs-v1"
BROKER_COSTS_FILENAME = "broker_costs.json"

#: Der Broker fuehrt das Instrument und die Zahlen sind von einer Quelle abgelesen.
STATUS_BELEGT = "belegt"
#: Der Broker fuehrt das Instrument nicht (fuer Retail in der EU). Ergebnis, kein Loch.
STATUS_NICHT_GEFUEHRT = "nicht_gefuehrt"
#: Der Broker fuehrt das Instrument, veroeffentlicht aber keinen Spread. Das ist etwas
#: anderes als „bietet es nicht an" und etwas anderes als „kostet nichts" -- beides
#: waere falsch. Der Fall wird als eigener Zustand gefuehrt und faellt aus der
#: Rechnung, statt sie mit einer Null zu verfaelschen.
STATUS_OHNE_SPREAD = "spread_nicht_veroeffentlicht"
_STATUS_VALUES = (STATUS_BELEGT, STATUS_NICHT_GEFUEHRT, STATUS_OHNE_SPREAD)

#: Abgelesener typischer/durchschnittlicher Spread.
SPREAD_TYPISCH = "typisch"
#: Werbewert „ab X". Verlangt einen bezifferten Aufschlag.
SPREAD_AB_WERT = "ab-wert"
_SPREAD_KINDS = (SPREAD_TYPISCH, SPREAD_AB_WERT)


class BrokerCostsError(ValueError):
    """Die Kostendatei ist unbrauchbar. Fail-closed: keine Kostenrechnung."""


@dataclass(frozen=True)
class InstrumentCost:
    """Kosten eines Instruments bei einem Broker, je Standardlot.

    ``spread_price`` ist der **wirksame** Spread in Preiseinheiten: bereits umgerechnet
    und bei einem Werbewert bereits mit dem Aufschlag multipliziert. Die drei
    Ausgangswerte bleiben daneben stehen, damit die Rechnung nachvollziehbar ist.
    """

    key: str
    broker_symbol: str
    status: str
    reason: str | None
    quote_currency: str | None
    spread_published: Decimal | None
    spread_unit: str | None
    unit_in_price: Decimal | None
    spread_kind: str | None
    spread_markup_factor: Decimal | None
    spread_price: Decimal | None
    commission_round_turn: Decimal | None
    commission_currency: str | None
    #: Kommission als **Anteil am Nominal** in Basispunkten je Round-Turn. Nur gesetzt,
    #: wo der Broker die Kommission als Prozentsatz veroeffentlicht (Aktien-CFDs sind
    #: der Regelfall). Ist sie gesetzt, schlaegt sie den Betrag je Lot: ein Prozentsatz
    #: skaliert mit der Position, ein fester Betrag tut das nicht, und die beiden
    #: unterscheiden sich bei Aktien um eine Groessenordnung.
    commission_bps_round_turn: Decimal | None
    swap_long: Decimal | None
    swap_short: Decimal | None
    swap_unit: str | None
    #: Swap in Basispunkten des Nominals je Nacht -- **nur** gefuellt, wo die Quelle
    #: den Satz selbst als Anteil am Nominal ausweist. Ein in „Punkten je Lot"
    #: veroeffentlichter Swap braucht dafuer den Pip-Wert, den dieselben Quellen
    #: NICHT veroeffentlichen; ihn zu raten waere die stille Annahme, die dieses
    #: Paket ausschliesst. Dann bleibt das Feld ``None`` und faellt sichtbar aus der
    #: Swap-Rechnung.
    swap_bps_night_long: Decimal | None
    swap_bps_night_short: Decimal | None
    min_lot: Decimal | None
    contract_size: Decimal | None
    tick_size: Decimal | None
    trading_hours: str | None
    rollover: str | None
    source_url: str | None
    retrieved_on: str | None
    quote: str | None
    #: Ergebnis der unabhaengigen Gegenpruefung. Ein Wert, den ein zweiter Leser auf
    #: der Quelle nicht wiederfinden konnte, bleibt hier als solcher stehen.
    verification: str | None

    @property
    def available(self) -> bool:
        """Nur ``belegt`` traegt eine vollstaendige Kostenrechnung."""
        return self.status == STATUS_BELEGT


@dataclass(frozen=True)
class Broker:
    """Ein Broker mit seiner Aufsicht und seinen Instrumentenkosten."""

    key: str
    name: str
    regulator: str
    account_type: str
    instruments: dict[str, InstrumentCost]


@dataclass(frozen=True)
class BrokerCosts:
    """Die geladene Kostendatei.

    ``slippage_bps`` je Instrumentenschluessel ist die **bezifferte Annahme** aus A1.3
    — keine Messung. ``slippage_note`` traegt ihre Begruendung; ohne Begruendung laedt
    die Datei nicht. In Basispunkten des Nominals je Round-Turn, weil das Kostentor in
    Basispunkten rechnet und eine Angabe in Preiseinheiten je Instrument neu
    umgerechnet werden muesste.
    """

    costs_id: str
    costs_version: str
    verified_on: str
    slippage_bps: dict[str, Decimal]
    slippage_note: str
    brokers: dict[str, Broker]


def default_costs_path() -> Path:
    """Suche aufwaerts nach ``config/broker_costs.json`` (wie beim Katalog).

    Bewusst kein ENV-Override — die Kostentabelle ist Teil der gepruften Datenlage,
    kein Laufzeitschalter.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / BROKER_COSTS_FILENAME
        if candidate.is_file():
            return candidate
    return here.parent / "data" / BROKER_COSTS_FILENAME


def load_broker_costs(path: Path | str | None = None) -> BrokerCosts:
    """Lade und validiere die Kostendatei. Jeder Defekt ist ein Fehler."""
    file_path = Path(path) if path is not None else default_costs_path()
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BrokerCostsError(f"Kostendatei fehlt: {file_path}") from exc
    except json.JSONDecodeError as exc:
        raise BrokerCostsError(f"Kostendatei ist kein gueltiges JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise BrokerCostsError("Kostendatei ist kein Objekt")
    for field in (
        "schema_version",
        "costs_id",
        "costs_version",
        "valid_from",
        "verified_on",
        "slippage",
        "brokers",
    ):
        if field not in raw:
            raise BrokerCostsError(f"Kostendatei ohne Pflichtfeld {field!r}")

    slippage_bps, note = _parse_slippage(raw["slippage"])

    brokers_raw = raw["brokers"]
    if not isinstance(brokers_raw, dict) or not brokers_raw:
        raise BrokerCostsError("Kostendatei ohne Broker")

    return BrokerCosts(
        costs_id=str(raw["costs_id"]),
        costs_version=str(raw["costs_version"]),
        verified_on=str(raw["verified_on"]),
        slippage_bps=slippage_bps,
        slippage_note=note,
        brokers={
            str(key): _parse_broker(str(key), entry)
            for key, entry in brokers_raw.items()
        },
    )


def _parse_slippage(slippage: Any) -> tuple[dict[str, Decimal], str]:
    if not isinstance(slippage, dict):
        raise BrokerCostsError("'slippage' ist kein Objekt")
    note = slippage.get("note")
    if not (isinstance(note, str) and note.strip()):
        raise BrokerCostsError(
            "'slippage.note' fehlt — eine Annahme ohne Begruendung ist unbrauchbar"
        )
    values = slippage.get("bps_per_instrument")
    if not isinstance(values, dict) or not values:
        raise BrokerCostsError("'slippage.bps_per_instrument' fehlt oder ist leer")
    out: dict[str, Decimal] = {}
    for key, value in values.items():
        number = _decimal("slippage", str(key), value)
        if number < 0:
            raise BrokerCostsError(f"slippage[{key!r}] ist negativ: {number}")
        out[str(key)] = number
    return out, note


def _decimal(scope: str, field: str, value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerCostsError(
            f"{scope}: Feld {field!r} ist keine Zahl: {value!r}"
        ) from exc


def _optional_decimal(scope: str, field: str, value: Any) -> Decimal | None:
    return None if value is None else _decimal(scope, field, value)


def _parse_broker(key: str, entry: Any) -> Broker:
    if not isinstance(entry, dict):
        raise BrokerCostsError(f"{key}: Broker-Eintrag ist kein Objekt")
    for field in ("name", "regulator", "account_type", "instruments"):
        if not entry.get(field):
            raise BrokerCostsError(f"{key}: Broker ohne {field!r}")
    instruments = entry["instruments"]
    if not isinstance(instruments, dict) or not instruments:
        raise BrokerCostsError(f"{key}: Broker ohne Instrumente")
    return Broker(
        key=key,
        name=str(entry["name"]),
        regulator=str(entry["regulator"]),
        account_type=str(entry["account_type"]),
        instruments={
            str(sym): _parse_instrument(f"{key}/{sym}", str(sym), value)
            for sym, value in instruments.items()
        },
    )


def _parse_instrument(scope: str, key: str, entry: Any) -> InstrumentCost:
    if not isinstance(entry, dict):
        raise BrokerCostsError(f"{scope}: Eintrag ist kein Objekt")

    status = str(entry.get("status", ""))
    if status not in _STATUS_VALUES:
        raise BrokerCostsError(
            f"{scope}: unbekannter status {status!r}, erlaubt: {_STATUS_VALUES}"
        )

    reason = entry.get("reason")
    if status in (STATUS_NICHT_GEFUEHRT, STATUS_OHNE_SPREAD):
        if not (isinstance(reason, str) and reason.strip()):
            raise BrokerCostsError(
                f"{scope}: status={status} ohne Begruendung ('reason') — ein "
                "fehlender Wert ist ein Ergebnis, kein Loch"
            )
        return _empty_instrument(
            key,
            str(entry.get("broker_symbol") or key),
            status,
            str(reason),
            str(entry.get("verification") or "") or None,
        )

    for field in ("source_url", "retrieved_on", "quote_currency"):
        value = entry.get(field)
        if not (isinstance(value, str) and value.strip()):
            raise BrokerCostsError(
                f"{scope}: {field!r} fehlt — eine Kostenzahl ohne Quelle und ohne "
                "Notierungswaehrung ist nicht nachrechenbar"
            )

    spread_kind = str(entry.get("spread_kind", ""))
    if spread_kind not in _SPREAD_KINDS:
        raise BrokerCostsError(
            f"{scope}: unbekannte spread_kind {spread_kind!r}, erlaubt: {_SPREAD_KINDS}"
        )

    published = _optional_decimal(
        scope, "spread_published", entry.get("spread_published")
    )
    if published is None or published < 0:
        raise BrokerCostsError(
            f"{scope}: 'spread_published' fehlt oder ist negativ "
            f"({entry.get('spread_published')!r})"
        )
    unit_in_price = _optional_decimal(
        scope, "unit_in_price", entry.get("unit_in_price")
    )
    if unit_in_price is None or unit_in_price <= 0:
        raise BrokerCostsError(
            f"{scope}: 'unit_in_price' fehlt oder ist nicht positiv "
            f"({entry.get('unit_in_price')!r}). Ohne sie ist der Spread nicht in "
            "Preiseinheiten umrechenbar, und ein nicht umrechenbarer Spread darf "
            "nicht als Null durchgehen."
        )
    spread_unit = entry.get("spread_unit")
    if not (isinstance(spread_unit, str) and spread_unit.strip()):
        raise BrokerCostsError(
            f"{scope}: 'spread_unit' fehlt — die Einheit der Quelle gehoert "
            "dokumentiert, sonst ist 'unit_in_price' nicht nachpruefbar"
        )

    markup = _optional_decimal(
        scope, "spread_markup_factor", entry.get("spread_markup_factor")
    )
    if spread_kind == SPREAD_AB_WERT:
        if markup is None or markup <= 1:
            raise BrokerCostsError(
                f"{scope}: Werbewert ('{SPREAD_AB_WERT}') ohne bezifferten Aufschlag "
                "('spread_markup_factor' > 1). Ein stiller Aufschlag ist unzulaessig."
            )
    spread_price = published * unit_in_price * (markup if markup is not None else 1)

    commission = _optional_decimal(
        scope, "commission_round_turn", entry.get("commission_round_turn")
    )
    if commission is None or commission < 0:
        raise BrokerCostsError(
            f"{scope}: 'commission_round_turn' fehlt oder ist negativ "
            f"({entry.get('commission_round_turn')!r}). Null ist zulaessig "
            "(Nur-Spread-Konto) und muss ausdruecklich dastehen."
        )
    ad_valorem = _optional_decimal(
        scope, "commission_bps_round_turn", entry.get("commission_bps_round_turn")
    )
    if ad_valorem is not None and ad_valorem < 0:
        raise BrokerCostsError(f"{scope}: 'commission_bps_round_turn' ist negativ")
    commission_currency = str(entry.get("commission_currency") or "") or None
    if commission > 0 and commission_currency is None:
        raise BrokerCostsError(
            f"{scope}: Kommission {commission} ohne 'commission_currency' — nicht "
            "umrechenbar"
        )

    contract_size = _optional_decimal(
        scope, "contract_size", entry.get("contract_size")
    )
    if contract_size is not None and contract_size <= 0:
        raise BrokerCostsError(f"{scope}: 'contract_size' ist nicht positiv")

    return InstrumentCost(
        key=key,
        broker_symbol=str(entry.get("broker_symbol") or key),
        status=status,
        reason=str(reason) if isinstance(reason, str) and reason.strip() else None,
        quote_currency=str(entry["quote_currency"]),
        spread_published=published,
        spread_unit=str(spread_unit),
        unit_in_price=unit_in_price,
        spread_kind=spread_kind,
        spread_markup_factor=markup,
        spread_price=spread_price,
        commission_round_turn=commission,
        commission_currency=commission_currency,
        commission_bps_round_turn=ad_valorem,
        swap_long=_optional_decimal(scope, "swap_long", entry.get("swap_long")),
        swap_short=_optional_decimal(scope, "swap_short", entry.get("swap_short")),
        swap_unit=str(entry.get("swap_unit") or "") or None,
        swap_bps_night_long=_optional_decimal(
            scope, "swap_bps_night_long", entry.get("swap_bps_night_long")
        ),
        swap_bps_night_short=_optional_decimal(
            scope, "swap_bps_night_short", entry.get("swap_bps_night_short")
        ),
        min_lot=_optional_decimal(scope, "min_lot", entry.get("min_lot")),
        contract_size=contract_size,
        tick_size=_optional_decimal(scope, "tick_size", entry.get("tick_size")),
        trading_hours=str(entry.get("trading_hours") or "") or None,
        rollover=str(entry.get("rollover") or "") or None,
        source_url=str(entry["source_url"]),
        retrieved_on=str(entry["retrieved_on"]),
        quote=str(entry.get("quote") or "") or None,
        verification=str(entry.get("verification") or "") or None,
    )


def _empty_instrument(
    key: str,
    broker_symbol: str,
    status: str,
    reason: str,
    verification: str | None,
) -> InstrumentCost:
    """Ein nicht rechenbares Instrument — ohne jede Ersatzzahl."""
    return InstrumentCost(
        key=key,
        broker_symbol=broker_symbol,
        status=status,
        reason=reason,
        quote_currency=None,
        spread_published=None,
        spread_unit=None,
        unit_in_price=None,
        spread_kind=None,
        spread_markup_factor=None,
        spread_price=None,
        commission_round_turn=None,
        commission_currency=None,
        commission_bps_round_turn=None,
        swap_long=None,
        swap_short=None,
        swap_unit=None,
        swap_bps_night_long=None,
        swap_bps_night_short=None,
        min_lot=None,
        contract_size=None,
        tick_size=None,
        trading_hours=None,
        rollover=None,
        source_url=None,
        retrieved_on=None,
        quote=None,
        verification=verification,
    )

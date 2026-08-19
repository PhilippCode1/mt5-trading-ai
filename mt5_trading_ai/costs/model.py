"""Kostenmodell: die realen Kosten einer Order, gemessen statt angenommen.

WARUM ES DIESES MODUL GIBT
--------------------------
Ohne realistisches Kostenmodell ist jeder Backtest Fiktion: eine Strategie, die nur
ohne Kosten funktioniert, sieht in einem kostenlosen Backtest genauso aus wie eine,
die wirklich verdient. Darum ist das Kostenmodell das erste Bauteil des Edge-Nachweises,
nicht das letzte.

Es rechnet die **Roundturn**-Kosten (eroeffnen + schliessen) einer Order aus vier
getrennten Bestandteilen:

1. **Spread** aus dem *tatsaechlichen* Bid/Ask zum Entscheidungszeitpunkt -- nicht aus
   einem Durchschnitt. Eine Order kostet den Spread, den der Markt in dem Moment stellt.
2. **Kommission** je Standardlot Roundturn aus der versionierten ``FeeSchedule`` des
   Instrumentenkatalogs (eine Quelle, keine Dublette).
3. **Slippage** als Modell mit einstellbarem Parameter in **Pips** je Seite. Der
   Standardwert ist der obere Rand des ruhigen Bandes -- bewusst nicht optimistisch;
   fuer bewegte Phasen setzt der Aufrufer ihn hoeher.
4. **Finanzierung** je gehaltener Nacht, inklusive Dreifach-Swap-Tag.

FAIL-CLOSED
-----------
Fehlt eine Kostenangabe fuer ein Symbol, ist das ein **Fehler, nicht Null**. Eine
fehlende Kostenangabe darf nie als kostenlos durchgehen. Ebenso: ein nicht-endlicher
Wert (NaN/Infinity, z. B. aus einem korrupten Tick) ist ein Fehler, nie eine Zahl --
sonst wuerde Unbrauchbares still als echte Kosten weitergereicht.

WAEHRUNG -- KEINE STILLE ANNAHME
--------------------------------
Spread und Slippage entstehen in der **Notierungswaehrung** (``quote_currency``);
Kommission und Swap stehen in Kontowaehrung (``FeeSchedule.currency``). Sind beide
gleich (EURUSD, XAUUSD, US500 in USD), gilt Kurs 1. Sind sie **verschieden** (z. B.
EURGBP in GBP bei USD-Konto), **muss** der Aufrufer ``quote_to_account_rate`` liefern --
sonst ``CostModelError``. Es gibt keinen stillen Default 1 bei Waehrungsdifferenz: eine
unbemerkte Fehlanpassung waere genau die versteckte Annahme, gegen die dieses Modul
gebaut ist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mt5_trading_ai.venue.catalog import (
    CatalogEntry,
    InstrumentCatalogError,
    load_instrument_catalog,
)
from mt5_trading_ai.venue.protocol import AssetClass, FeeSchedule, OrderSide

#: Standard-Slippage je Seite in **Pips** (nicht Ticks -- die Recherche denkt in Pips).
#: 0,5 Pip/Seite ist der obere Rand des ruhigen Bandes (RECHERCHE_KOSTEN.md, EURUSD
#: ruhig 0-0,5 Pip/Seite): bewusst nicht optimistisch. Fuer News/duenne Liquiditaet
#: setzt der Backtest ihn hoeher (dort 3-10+ Pip). Ein Nullwert waere optimistisch.
DEFAULT_SLIPPAGE_PIPS_PER_SIDE = Decimal("0.5")

#: Anlageklassen, die auf einem A-Book eine Kommission je Lot tragen (FX + Metalle).
#: Eine 0 dort ist eine Datenluecke, kein legitimer Nulltarif -- fail-closed.
_COMMISSION_REQUIRED = frozenset(
    {AssetClass.FX_MAJOR, AssetClass.FX_MINOR, AssetClass.GOLD}
)


class CostModelError(ValueError):
    """Kostenangaben fehlen oder sind unbrauchbar. Fail-closed, keine Schaetzung."""


@dataclass(frozen=True)
class CostBreakdown:
    """Roundturn-Kosten einer Order, nach Bestandteil getrennt. Alle in ``currency``.

    Positiv = Kosten (Geld raus). ``financing`` kann negativ sein (Gutschrift), wenn der
    Swap in Halterichtung positiv ist. ``total`` ist die Summe der vier Bestandteile.
    """

    spread: Decimal
    commission: Decimal
    slippage: Decimal
    financing: Decimal
    total: Decimal
    currency: str


def _require_positive(name: str, value: Decimal) -> None:
    if not value.is_finite() or value <= 0:
        raise CostModelError(f"{name} muss endlich und positiv sein, ist {value}")


def _require_finite(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise CostModelError(f"{name} muss endlich sein, ist {value}")


def order_roundturn_cost(
    *,
    fees: FeeSchedule,
    contract_size: Decimal,
    pip_size: Decimal,
    bid: Decimal,
    ask: Decimal,
    side: OrderSide,
    volume: Decimal,
    quote_currency: str,
    holding_nights: int = 0,
    triple_swap_nights: int = 0,
    slippage_pips_per_side: Decimal = DEFAULT_SLIPPAGE_PIPS_PER_SIDE,
    quote_to_account_rate: Decimal | None = None,
) -> CostBreakdown:
    """Roundturn-Kosten (eroeffnen + schliessen) einer Order. Fail-closed bei Unfug.

    ``bid``/``ask`` sind der Live-Markt zum Entscheidungszeitpunkt (der Spread wird
    daraus gerechnet, nicht aus ``fees.typical_spread_points``). ``quote_currency`` ist
    die Notierungswaehrung des Instruments; weicht sie von ``fees.currency`` ab, ist
    ``quote_to_account_rate`` Pflicht. ``holding_nights`` sind gehaltene Naechte,
    ``triple_swap_nights`` davon die Dreifach-Naechte (jede zaehlt dreifach). Der volle
    Spread faellt einmal je Roundturn an, Slippage auf beiden Seiten (zwei Fills).
    """
    _require_positive("volume", volume)
    _require_positive("contract_size", contract_size)
    _require_positive("pip_size", pip_size)
    _require_positive("bid", bid)
    _require_positive("ask", ask)
    _require_finite("slippage_pips_per_side", slippage_pips_per_side)
    _require_finite("commission", fees.commission_per_lot_round_turn)

    # Waehrung: keine stille 1 bei Nichtuebereinstimmung.
    if quote_currency == fees.currency:
        # Gleiche Waehrung -> der Umrechnungskurs ist definitionsgemaess 1. Ein
        # uebergebener Kurs waere sinnlos (er verzerrte Spread/Slippage) und wird
        # bewusst ignoriert -- verhindert stille Fehlbepreisung same-currency (§9).
        rate = Decimal("1")
    elif quote_to_account_rate is None:
        raise CostModelError(
            f"Notierungswaehrung {quote_currency} != Gebuehrenwaehrung "
            f"{fees.currency} (aus dem Instrumentenkatalog, NICHT die Waehrung des "
            f"Kontos): quote_to_account_rate noetig"
        )
    else:
        rate = quote_to_account_rate
    _require_positive("quote_to_account_rate", rate)

    if ask < bid:
        raise CostModelError(f"Ask {ask} unter Bid {bid} -- verschraenkte Notierung")
    if slippage_pips_per_side < 0:
        raise CostModelError("Slippage darf nicht negativ sein")
    if holding_nights < 0 or triple_swap_nights < 0:
        raise CostModelError("Naechte duerfen nicht negativ sein")
    if triple_swap_nights > holding_nights:
        raise CostModelError(
            f"Dreifach-Naechte {triple_swap_nights} > Naechte {holding_nights}"
        )
    if fees.commission_per_lot_round_turn < 0:
        raise CostModelError("Kommission darf nicht negativ sein")

    # Spread aus dem echten Bid/Ask; voller Spread einmal je Roundturn.
    spread = (ask - bid) * contract_size * volume * rate

    commission = fees.commission_per_lot_round_turn * volume

    # Slippage in Pips, auf beiden Seiten (Eroeffnung + Schliessung).
    slippage = (
        slippage_pips_per_side
        * pip_size
        * contract_size
        * volume
        * Decimal("2")
        * rate
    )

    # Finanzierung: Swap je Nacht (Dreifach-Naechte zaehlen dreifach). Negativer Swap
    # ist Kosten, positiver eine Gutschrift.
    swap_per_night = (
        fees.swap_long_per_lot_per_night
        if side is OrderSide.BUY
        else fees.swap_short_per_lot_per_night
    )
    _require_finite("swap", swap_per_night)
    swap_units = Decimal(holding_nights) + Decimal("2") * Decimal(triple_swap_nights)
    financing = -(swap_per_night * volume * swap_units)

    total = spread + commission + slippage + financing
    return CostBreakdown(
        spread=spread,
        commission=commission,
        slippage=slippage,
        financing=financing,
        total=total,
        currency=fees.currency,
    )


def load_cost_fees(
    symbol: str,
    *,
    catalog: dict[str, CatalogEntry] | None = None,
    catalog_path: str | None = None,
) -> FeeSchedule:
    """Hole die ``FeeSchedule`` eines Symbols aus dem Katalog, fail-closed.

    Jeder Ladefehler (Datei fehlt, kaputt, Pflichtfeld fehlt, unbekannte Klasse) und ein
    unbekanntes Symbol werden zu ``CostModelError``. Zusaetzliche Datensanitaet: ein
    Aktien-CFD wird abgelehnt (die Fixbetrag-``FeeSchedule`` kann ad-valorem-Kommission
    und %-p.a.-Swap nicht abbilden), und eine Nullkommission auf FX/Gold ist eine
    Datenluecke, kein Nulltarif. Ein Symbol ohne Kostendaten fuehrt nie zu Nullkosten.
    """
    if catalog is None:
        try:
            catalog = load_instrument_catalog(catalog_path)
        except InstrumentCatalogError as exc:
            raise CostModelError(f"Kostendaten nicht ladbar: {exc}") from exc
    try:
        entry = catalog[symbol]
    except KeyError as exc:
        raise CostModelError(
            f"Unbekanntes Symbol ohne Kostendaten: {symbol!r}"
        ) from exc
    if entry.asset_class is AssetClass.EQUITY:
        raise CostModelError(
            f"{symbol}: Aktien-CFD-Kosten (ad valorem) sind noch nicht modelliert"
        )
    if (
        entry.asset_class in _COMMISSION_REQUIRED
        and entry.fees.commission_per_lot_round_turn == 0
    ):
        raise CostModelError(
            f"{symbol}: {entry.asset_class.value} mit Kommission 0 -- Datenluecke"
        )
    return entry.fees

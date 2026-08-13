"""Pre-Trade-Kostentor am Order-Pfad.

``costs/model.py`` rechnet die realen Roundturn-Kosten einer Order (Spread, Kommission,
Slippage) aus dem echten Bid/Ask und der versionierten ``FeeSchedule``. Der Backtest
prueft eine Strategie **gegen eine angenommene Kostenobergrenze**; dieses Modul bringt
dieselbe Obergrenze an den Live-Order-Pfad: es entscheidet, ob die **tatsaechlichen**
Roundturn-Transaktionskosten einer eroeffnenden Order noch unter der im Backtest
vorausgesetzten Schwelle liegen.

Grund (die eine Fehlerklasse, die dieses Tor schliesst): eine Strategie, die im
Backtest bei z. B. 1 bp Roundturn-Kosten gerade eben traegt, verliert live, wenn der
Spread sich auf ein Mehrfaches weitet -- die Kostenannahme des Backtests wurde nie
gegen den Live-Markt geprueft. Ohne dieses Tor eroeffnet das System solche Orders
blind.

Fail-closed: sind die Kosten nicht sicher bestimmbar (Waehrungsdifferenz, verschraenkte
Notierung, unplausibles Notional), wird **nicht** freigegeben -- ohne Default. Die
**Politik** (welche Obergrenze) traegt der Aufrufer, der die Backtest-Evidenz hat; der
Venue erzwingt sie nur (siehe ``venue/mt5.py``).

WAEHRUNG (aus dem §9-Review): Die Kostenquote ist nur korrekt, wenn Zaehler
(``friction``) und Nenner (``notional``) in **derselben** Waehrung stehen. ``friction``
kommt aus ``order_roundturn_cost`` in **Kontowaehrung** (``fees.currency``); das
``notional`` bildet sich aus dem rohen Preis in **Notierungswaehrung**. Beide stimmen
genau dann ueberein, wenn Notierungs- = Kontowaehrung ist. Darum gilt das Tor nur fuer
**gleich notierte** Instrumente (rate = 1); ein kreuznotiertes Instrument (z. B. USDJPY
auf USD-Konto) wird **fail-closed** abgewiesen -- die korrekte Umrechnung braucht einen
**instrumentspezifischen** Live-FX-Kurs, den ein einzelner Venue-Skalar nicht liefern
kann (siehe ``SPAETER.md`` S10). Lieber nicht handeln als falsch bepreisen.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from mt5_trading_ai.costs.model import CostModelError, order_roundturn_cost
from mt5_trading_ai.venue.protocol import FeeSchedule, Instrument, OrderSide


@dataclass(frozen=True)
class CostGate:
    """Politik des Pre-Trade-Kostentors: die im Backtest vorausgesetzte Kostenschwelle.

    ``max_roundturn_cost_fraction`` ist die hoechste noch zulaessige Summe der
    Roundturn-**Transaktionskosten** (Spread + Kommission + Slippage) als Anteil des
    Notionals -- die Kostenannahme, unter der die Strategie ihren Edge belegt hat (z. B.
    ``Decimal("0.0002")`` fuer 2 bp). Die Finanzierung bleibt aussen vor: sie haengt
    von der beim Eroeffnen unbekannten Haltedauer ab -- dieselbe Trennung wie
    ``stressed_spec`` im Backtest (Transaktionskosten schon, Finanzierung nicht).

    Bewusst **kein** ``quote_to_account_rate``: ein einzelner Skalar am Konto-Venue kann
    nicht zugleich fuer USD- und JPY-notierte Paare stimmen (§9). Das Tor prueft nur
    gleich notierte Instrumente; kreuznotierte werden fail-closed abgewiesen.
    """

    max_roundturn_cost_fraction: Decimal


@dataclass(frozen=True)
class CostGateDecision:
    """Ergebnis des Kostentors. ``approved`` nur bei sicher gedeckter Kostenannahme."""

    approved: bool
    reason: str | None
    cost_fraction: Decimal | None
    detail: str | None = None


def evaluate_cost_gate(
    *,
    gate: CostGate,
    instrument: Instrument,
    fees: FeeSchedule,
    side: OrderSide,
    volume: Decimal,
    bid: Decimal,
    ask: Decimal,
) -> CostGateDecision:
    """Pruefe die realen Roundturn-Transaktionskosten gegen die Backtest-Schwelle.

    ``bid``/``ask`` sind der Live-Markt zum Entscheidungszeitpunkt. Die Finanzierung
    wird bewusst nicht einbezogen (``holding_nights=0``): das Tor misst die beim
    Eroeffnen bekannten Transaktionskosten, nicht die haltedauerabhaengige Finanzierung.

    Nur gleich notierte Instrumente: ``order_roundturn_cost`` wird OHNE Umrechnungskurs
    gerufen; bei kreuznotiertem Instrument (Notierung != Kontowaehrung) wirft es und das
    Tor weist fail-closed ab (``cost_unverifiable``). So bleiben Zaehler und Nenner der
    Kostenquote garantiert in derselben Waehrung.
    """
    if gate.max_roundturn_cost_fraction < 0:
        return CostGateDecision(False, "invalid_threshold", None)
    # Unbekannte Notierungswaehrung -> KEINE stille Annahme "= Kontowaehrung": ein real
    # kreuznotiertes Instrument (currency_profit leer -> None) wuerde sonst als gleich
    # notiert bepreist (rate=1), die Waehrungs-Mischung schluepfte durch (§9-Re-Check).
    if instrument.quote_currency is None:
        return CostGateDecision(
            False, "cost_unverifiable", None,
            detail="Notierungswaehrung des Instruments unbekannt",
        )
    try:
        # KEIN quote_to_account_rate: same-currency -> rate=1 (Kosten in Kontowaehrung =
        # Notierungswaehrung); cross-currency -> CostModelError -> fail-closed unten.
        breakdown = order_roundturn_cost(
            fees=fees,
            contract_size=instrument.contract_size,
            pip_size=instrument.pip_size,
            bid=bid,
            ask=ask,
            side=side,
            volume=volume,
            quote_currency=instrument.quote_currency,
        )
    except CostModelError as exc:
        # Kosten nicht bestimmbar (z. B. kreuznotiert) -> nicht handeln (fail-closed).
        return CostGateDecision(False, "cost_unverifiable", None, detail=str(exc))

    # Nur die Transaktionsreibung (haltedauerunabhaengig); financing bleibt aussen vor.
    # friction steht in Kontowaehrung; notional im rohen Preis (Notierungswaehrung). Der
    # Aufruf oben laesst nur same-currency durch (rate=1) -> beides dieselbe Waehrung,
    # die Quote ist dimensionslos korrekt.
    friction = breakdown.spread + breakdown.commission + breakdown.slippage
    entry_price = ask if side is OrderSide.BUY else bid
    notional = instrument.contract_size * volume * entry_price
    if notional <= 0:
        return CostGateDecision(False, "invalid_notional", None)
    fraction = friction / notional
    if fraction > gate.max_roundturn_cost_fraction:
        return CostGateDecision(False, "cost_gate", fraction)
    return CostGateDecision(True, None, fraction)

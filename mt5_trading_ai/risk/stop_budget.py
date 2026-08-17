"""Stop-Budget je Anlageklasse — hergeleitet, nicht uebertragen (Phase 6.5).

Die alte Kurve (7x -> 100 bp, 75x -> 10 bp) stammt aus Krypto-Perpetual-Kosten
und aus der Liquidationsnaehe bei 75x. Beides gilt hier nicht mehr. Diese Datei
leitet das Budget neu her, aus zwei Groessen, die je Klasse verschieden sind.

**Untergrenze — aus den Kosten.** Bei einem Chancen-Risiko-Verhaeltnis von 1:1,
Stopdistanz ``R`` und Round-Turn-Kosten ``C`` liegt die Trefferquote am
Nulldurchgang bei

    p = 0,5 + C / (2R)

Fordert man, dass die Kosten den Nulldurchgang um hoechstens ``max_cost_drag``
anheben (Default 5 Prozentpunkte, also p <= 55 %), folgt

    R >= C / (2 · max_cost_drag)          Default: R >= 10 · C

Ein Stop unterhalb dieser Distanz macht die Klasse rechnerisch unhandelbar —
unabhaengig davon, wie gut das Signal ist.

**Obergrenze — aus der Margin.** Der Hebel bestimmt, wie weit der Preis laufen
darf, bevor der Margin-Close-out greift. Bei Kleinanlegern in der EU schliesst
der Broker bei 50 % der Ersteinschusszahlung; das entspricht einer
Gegenbewegung von ``0,5 / L``. Mit einem Sicherheitsfaktor ``safety`` (Default 3)
gilt

    R <= 0,5 / (L · safety)

| Hebel | Close-out-Abstand | Obergrenze bei safety = 3 |
|---|---|---|
| 5x  | 1000 bp | **333 bp** |
| 10x |  500 bp | **167 bp** |

Der Hebel wirkt also nur noch auf die **Obergrenze** und nicht mehr, wie in der
alten Kurve, auf einen einzigen Zielwert. Das ist der inhaltliche Unterschied:
enge Stops entstehen hier aus Kosten und Ausfuehrbarkeit, nicht aus
Liquidationsangst.

Ist die Untergrenze groesser als die Obergrenze, ist die Kombination aus Klasse
und Hebel nicht handelbar: ``no_trade``, keine Aufweichung.

**Kostenbasis -- warum die Annahmetabelle nicht stillschweigend einspringt.**
Die Untergrenze ist nur so belastbar wie die Zahl ``C``. Die Werte in
``ASSUMED_ROUND_TURN_COST_BPS`` sind ausdruecklich Annahmen, und sie sind nicht
konservativ, sondern **schmeichelnd**: fuer ``fx_major`` stehen dort 0,65 bp,
waehrend das Kostentor am Live-Bid/Ask des scharfen Laufs 1,55 bp gemessen hat.
Die Untergrenze faellt damit auf 6,5 statt 15,5 bp -- Faktor 2,4 zugunsten des
Handels, und die Zusage ``max_cost_drag`` (Nulldurchgang hoechstens 55 %) waere
bei jedem so eroeffneten Trade gerissen, ohne dass es jemand saehe.

Ein Rueckfall auf die Tabelle ist deshalb **kein sicherer Vorgabewert**: er
senkt die Sperre, statt sie zu halten. Daraus folgen drei Regeln, und sie sind
der Grund fuer die Form der Schnittstelle:

1. Liegt eine Messung vor, schlaegt sie die Tabelle **immer**.
2. Liegt keine vor, traegt das Ergebnis ``cost_is_measured=False`` und
   ``cost_basis == "annahme"``. Die Basis reist mit dem Ergebnis mit, damit sie
   kein Aufrufer uebersehen kann; ``execution/risk_manager.py`` reicht sie als
   ``cost_basis`` in die Autorisierung durch, der Runner druckt sie in die
   Checkliste. Still ist der Rueckfall an keiner Stelle.
3. Wer nicht auf Annahmen handeln darf, setzt ``require_measured_cost=True``:
   dann ist die fehlende Messung ``no_trade`` (``cost_not_measured``) und nicht
   Tabelle. Der Order-Pfad des Runners misst die Kosten im Schritt "Kostentor"
   selbst und setzt den Schalter; die Tabelle bleibt fuer Herleitung, Doku und
   Backtest, wo keine Order entsteht.

Warum ``require_measured_cost`` nicht schon per Vorgabe gilt: es gibt Aufrufer
am Order-Pfad, die heute noch keine Messung mitfuehren (eine von Hand gebaute
``OrderRequest`` am Venue, die Schreibprobe in ``venue/smoke.py``). Die Vorgabe
umzustellen wuerde sie ohne Ersatz sperren, und ihre Dateien gehoeren nicht zu
diesem Auftrag. Bis dahin gilt: sichtbar statt still — und der einzige Pfad, der
heute wirklich eroeffnet (``execution/runner.py``), misst.

**Aufrufer (Paket 4):** ``execution/risk_manager.py`` fahrt ``stop_budget`` fuer jede
eroeffnende Live-Order; ein untradeables Budget lehnt die Order fail-closed ab.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

STOP_BUDGET_POLICY_VERSION = "stop-budget-v3-measured-cost"

#: Round-Turn-Kosten je Klasse in Basispunkten. **Annahmen**, keine Messungen —
#: vor dem ersten Backtest gegen den Demo-Feed des gewaehlten Brokers zu ersetzen
#: (Phase 7.3, geschichtete Stichprobe). Die Schluessel sind zugleich das
#: Verzeichnis der bekannten Anlageklassen (deckungsgleich mit ``AssetClass``):
#: eine Klasse, die hier fehlt, ist unbekannt und damit ``no_trade`` -- auch dann,
#: wenn eine Messung vorliegt. Eine Messung ersetzt die Kostenzahl, nicht das
#: Wissen darueber, was da gehandelt werden soll.
ASSUMED_ROUND_TURN_COST_BPS: dict[str, Decimal] = {
    "fx_major": Decimal("0.65"),
    "fx_minor": Decimal("4.0"),
    "gold": Decimal("1.5"),
    "index_major": Decimal("1.5"),
    "index_minor": Decimal("5.0"),
    "commodity_non_gold": Decimal("7.0"),
    "equity": Decimal("20.0"),
    "crypto": Decimal("40.0"),
}

#: Margin-Close-out fuer Kleinanleger in der EU: 50 % der Ersteinschusszahlung.
MARGIN_CLOSE_OUT_FRACTION = Decimal("0.5")


@dataclass(frozen=True)
class StopBudget:
    lower_bps: Decimal
    upper_bps: Decimal
    cost_bps: Decimal
    asset_class: str
    leverage: int
    tradeable: bool
    reason: str | None
    policy_version: str = STOP_BUDGET_POLICY_VERSION
    cost_is_measured: bool = False

    def allows(self, stop_bps: Decimal) -> bool:
        return self.tradeable and self.lower_bps <= stop_bps <= self.upper_bps

    @property
    def cost_basis(self) -> str:
        """Woher ``cost_bps`` stammt: ``gemessen`` oder ``annahme``.

        Ein Wort statt eines Wahrheitswerts, weil diese Zeile in Protokolle und
        Checklisten wandert und dort gelesen wird. Die Basis gehoert zum
        Ergebnis, nicht in den Kopf des Aufrufers.
        """
        return "gemessen" if self.cost_is_measured else "annahme"


def cost_bps_from_fraction(cost_fraction: Decimal) -> Decimal:
    """Kostenquote des Kostentors (Anteil am Notional) in Basispunkte.

    Die **eine** Umrechnung zwischen ``execution/cost_gate.py`` (rechnet einen
    Anteil) und dieser Datei (rechnet in bp). Sie steht hier, damit der Faktor
    10000 nicht an jeder Aufrufstelle neu auftaucht -- an zwei Orten ist er
    einmal zu oft.

    Fail-closed: eine nicht endliche oder nicht positive Quote ist ein Defekt der
    Messung und keine Zahl. Roundturn-Kosten sind Spread + Kommission + Slippage
    und damit echt positiv; eine 0 hiesse kostenloses Handeln und wuerde die
    Untergrenze auf 0 druecken -- genau der Rueckfall, den dieses Modul
    verhindert.
    """
    if not cost_fraction.is_finite() or cost_fraction <= 0:
        raise ValueError(
            f"gemessene Kostenquote muss endlich und positiv sein, ist {cost_fraction}"
        )
    return cost_fraction * Decimal("10000")


def cost_floor_bps(
    cost_bps: Decimal, *, max_cost_drag: Decimal = Decimal("0.05")
) -> Decimal:
    """Kleinste Stopdistanz, bei der die Kosten den Nulldurchgang
    um hoechstens ``max_cost_drag`` anheben.
    """
    if max_cost_drag <= 0:
        raise ValueError("max_cost_drag muss positiv sein")
    return cost_bps / (2 * max_cost_drag)


def margin_ceiling_bps(leverage: int, *, safety: Decimal = Decimal("3")) -> Decimal:
    """Groesste Stopdistanz mit Abstand zum Margin-Close-out."""
    if leverage <= 0:
        raise ValueError("leverage muss positiv sein")
    if safety <= 0:
        raise ValueError("safety muss positiv sein")
    return MARGIN_CLOSE_OUT_FRACTION * Decimal("10000") / (Decimal(leverage) * safety)


def stop_budget(
    *,
    asset_class: str,
    leverage: int,
    measured_cost_bps: Decimal | None = None,
    max_cost_drag: Decimal = Decimal("0.05"),
    safety: Decimal = Decimal("3"),
    require_measured_cost: bool = False,
) -> StopBudget:
    """Budgetspanne je Klasse und Hebel. Gemessene Kosten schlagen Annahmen.

    ``measured_cost_bps`` sind die am Markt gemessenen Roundturn-Kosten dieser
    Order (aus ``execution/cost_gate.py`` ueber ``cost_bps_from_fraction``).
    ``require_measured_cost=True`` macht ihr Fehlen zu ``no_trade`` statt zum
    Griff in die Annahmetabelle -- die Begruendung steht im Modul-Docstring
    unter "Kostenbasis"; kurz: die Tabelle ist schmeichelnd, nicht konservativ,
    und ein schmeichelnder Vorgabewert ist kein fail-closed.

    Die Klasse wird **vor** der Kostenbasis geprueft. Eine Messung liefert die
    Kostenzahl, aber sie macht eine unbekannte Anlageklasse nicht bekannt --
    sonst haette das Durchreichen der Messung die Klassensperre still entwertet.
    """
    key = str(asset_class).strip().lower()
    if measured_cost_bps is not None and (
        not measured_cost_bps.is_finite() or measured_cost_bps <= 0
    ):
        raise ValueError(
            f"measured_cost_bps muss endlich und positiv sein, ist {measured_cost_bps}"
        )
    measured = measured_cost_bps is not None

    if key not in ASSUMED_ROUND_TURN_COST_BPS:
        return StopBudget(
            lower_bps=Decimal("0"),
            upper_bps=Decimal("0"),
            cost_bps=Decimal("0"),
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="unknown_asset_class",
            cost_is_measured=False,
        )

    if not measured and require_measured_cost:
        # Kein stiller Rueckfall auf die Annahme: der Aufrufer hat erklaert, dass
        # er die Zusage ``max_cost_drag`` belegen muss, und ohne Messung kann er
        # das nicht. Nicht handeln ist die einzige Antwort, die nicht luegt.
        return StopBudget(
            lower_bps=Decimal("0"),
            upper_bps=Decimal("0"),
            cost_bps=Decimal("0"),
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="cost_not_measured",
            cost_is_measured=False,
        )

    cost = (
        measured_cost_bps
        if measured_cost_bps is not None
        else ASSUMED_ROUND_TURN_COST_BPS[key]
    )

    lower = cost_floor_bps(cost, max_cost_drag=max_cost_drag)
    upper = margin_ceiling_bps(leverage, safety=safety)

    if lower > upper:
        return StopBudget(
            lower_bps=lower,
            upper_bps=upper,
            cost_bps=cost,
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="cost_floor_above_margin_ceiling",
            cost_is_measured=measured,
        )

    return StopBudget(
        lower_bps=lower,
        upper_bps=upper,
        cost_bps=cost,
        asset_class=key,
        leverage=leverage,
        tradeable=True,
        reason=None,
        cost_is_measured=measured,
    )


def breakeven_hit_rate(*, cost_bps: Decimal, stop_bps: Decimal) -> Decimal:
    """Trefferquote am Nulldurchgang bei 1:1. Haengt nicht vom Hebel ab."""
    if stop_bps <= 0:
        raise ValueError("stop_bps muss positiv sein")
    return Decimal("0.5") + cost_bps / (2 * stop_bps)

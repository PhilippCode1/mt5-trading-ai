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

1. Liegt eine Messung vor, schlaegt sie die Tabelle **immer**. Dieses Modul
   nimmt die Zahl, die es bekommt; **welche** Zahl als Messung gilt, entscheidet
   der Aufrufer. Das ist keine Nachlaessigkeit, sondern eine Zustaendigkeit:
   ``execution/risk_manager.py`` kennt die Herkunft (in-Prozess gemessen,
   am Auftrag mitgereist, Messkampagne der Politik) und prueft sie dort -- eine
   am Auftrag mitgereiste Zahl darf die Kostenpraemisse nur anheben, nie senken.
2. Liegt keine vor, traegt das Ergebnis ``cost_is_measured=False`` und
   ``cost_basis == "annahme"``. Die Basis reist mit dem Ergebnis mit, damit sie
   kein Aufrufer uebersehen kann; ``execution/risk_manager.py`` reicht sie als
   ``detail["cost_basis"]`` in **jede** Autorisierung durch, der Runner druckt
   sie in die Checkliste.

   Wie weit das heute traegt, gehoert dazu: der Runner misst immer, in seiner
   Checkliste kann das Wort "annahme" also gar nicht stehen. Und der Pfad, auf
   dem der Rueckfall wirklich stattfindet -- eine von Hand gebaute
   ``OrderRequest`` am Venue, die Schreibprobe in ``venue/smoke.py`` -- laeuft
   ueber ``venue/mt5.py::_enforce_risk``, und das verwirft ``auth.detail``
   vollstaendig (bei Ablehnung wird nur ``auth.reason`` gehoben, bei Freigabe
   nichts). Die Basis steht dort im Rueckgabewert, aber in keinem Protokoll.
   SPAETER (``venue/mt5.py``, nicht dieses Paket): ``detail["cost_basis"]`` in
   die Ablehnungs- bzw. Freigabemeldung heben. Bis dahin gilt die Zusage
   "sichtbar statt still" fuer den Runner-Pfad und fuer jeden Aufrufer, der die
   Autorisierung selbst liest -- nicht fuer den Venue-Pfad.
3. Wer nicht auf Annahmen handeln darf, setzt ``require_measured_cost=True``:
   dann ist die fehlende Messung ``no_trade`` (``cost_not_measured``) und nicht
   Tabelle. Diesen Schalter setzt die **Politik** (``RiskPolicy``), nicht der
   einzelne Aufrufer: am Order-Pfad des Runners waere er eine Tautologie -- der
   Runner uebergibt die Messung des Kostentors unbedingt, die fehlende Messung
   ist dort per Konstruktion unerreichbar, und ein Schalter mit nur einer
   Stellung ist keiner. Die Tabelle bleibt fuer Herleitung, Doku und Backtest,
   wo keine Order entsteht.

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

#: **Plausibilitaetsboden je Klasse -- NICHT die Annahme.** Unterhalb dieser Zahl ist
#: eine gemeldete Round-Turn-Kostenmessung unglaubwuerdig, weil schon der halbe Spread
#: darueber liegt.
#:
#: Warum es diese Tabelle ueberhaupt gibt (Stufe 7, „Schwellen, die exakt auf dem
#: Maximum der Ersatzheuristik liegen, davon entkoppeln"): Bis hierher benutzte
#: ``RiskManager._kostenbasis`` **dieselbe** Zahl in zwei Rollen -- als Rueckfallwert,
#: wenn nichts gemessen wurde, UND als Schwelle, unter der eine gemessene Zahl
#: verworfen wird. Gemessen an fx_major: eine echte Messung von 0,30 bp wurde gegen
#: die Annahme 0,65 bp verworfen, und danach galt 0,65 bp. Ein Zugang, der wirklich
#: billiger ist, konnte so nie erkannt werden -- die Schwelle mass ihre eigene Ausgabe
#: (Sperre V2).
#:
#: Die Zahlen sind bewusst **deutlich unter** der Annahme angesetzt: sie sollen Unsinn
#: abweisen (0 bp, 0,001 bp), nicht eine bessere Ausfuehrung. Hergeleitet aus dem
#: halben typischen Roh-Spread der Klasse ohne Kommission und ohne Slippage -- also
#: der Groesse, die ein Round-Turn selbst dann nicht unterschreiten kann, wenn der
#: Handelsplatz nichts weiter berechnet.
#:
#: Sie sind **getrennt** von ``ASSUMED_ROUND_TURN_COST_BPS`` zu pflegen. Ein Dauertor
#: haelt fest, dass jeder Boden echt unter der zugehoerigen Annahme liegt; wer beide
#: gleichsetzt, stellt die Kopplung wieder her.
KOSTENPRAEMISSE_BPS: dict[str, Decimal] = {
    "fx_major": Decimal("0.05"),
    "fx_minor": Decimal("0.30"),
    "gold": Decimal("0.10"),
    "index_major": Decimal("0.10"),
    "index_minor": Decimal("0.40"),
    "commodity_non_gold": Decimal("0.50"),
    "equity": Decimal("1.00"),
    "crypto": Decimal("2.00"),
}

#: Margin-Close-out fuer Kleinanleger in der EU: 50 % der Ersteinschusszahlung.
MARGIN_CLOSE_OUT_FRACTION = Decimal("0.5")


def kostenpraemisse_bps(asset_class: str) -> Decimal | None:
    """Der Plausibilitaetsboden dieser Klasse -- ``None`` bei unbekannter Klasse.

    Getrennt von :func:`assumed_cost_bps` gehalten, und das ist der ganze Punkt: die
    eine Zahl sagt „womit rechnen wir, wenn nichts gemessen wurde", die andere „ab
    wann glauben wir einer Messung nicht mehr". Sie in einer Zahl zu fuehren machte
    aus der Annahme eine Schwelle gegen sich selbst.
    """
    return KOSTENPRAEMISSE_BPS.get(_klassen_schluessel(asset_class))


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
        """Ob ``cost_bps`` uebergeben wurde (``gemessen``) oder aus der Tabelle
        stammt (``annahme``).

        Ein Wort statt eines Wahrheitswerts, weil diese Zeile in Protokolle und
        Checklisten wandert und dort gelesen wird. Die Basis gehoert zum
        Ergebnis, nicht in den Kopf des Aufrufers.

        Genau lesen: dieses Modul sieht eine Zahl, nicht ihre Herkunft. Es kann
        deshalb nur "jemand hat gemessen und die Zahl uebergeben" von "niemand
        hat" unterscheiden -- ob die Zahl aus einem Live-Bid/Ask, aus einer
        Messkampagne oder aus dem ``meta`` eines Auftrags kam, weiss allein der
        Aufrufer. Wer den Kanal braucht, liest ihn dort, wo er bekannt ist:
        ``execution/risk_manager.py`` schreibt ihn als erstes Wort in
        ``RiskAuthorization.detail["cost_basis"]`` (``gemessen``/``auftrag``/
        ``kampagne``/``annahme``) und prueft die mitgereiste Zahl, bevor sie
        dieses Etikett bekommt.
        """
        return "gemessen" if self.cost_is_measured else "annahme"


def _klassen_schluessel(asset_class: str) -> str:
    """Die **eine** Normalisierung des Klassennamens (Rand, Grossschreibung)."""
    return str(asset_class).strip().lower()


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
    key = _klassen_schluessel(asset_class)
    if measured_cost_bps is not None and (
        not measured_cost_bps.is_finite() or measured_cost_bps <= 0
    ):
        raise ValueError(
            f"measured_cost_bps muss endlich und positiv sein, ist {measured_cost_bps}"
        )
    measured = measured_cost_bps is not None

    if key not in ASSUMED_ROUND_TURN_COST_BPS:
        # Die Klasse ist unbekannt -- die Kostenlage deswegen aber nicht. Wer
        # gemessen hat, hat gemessen: die Zahl und ihr Etikett gehen in die
        # Ablehnungsakte, sonst meldete der eine Datensatz, der die Kostenbasis
        # dokumentieren soll, ausgerechnet im Fehlerfall "annahme 0 bp" ueber
        # einen Aufrufer, der am Live-Bid/Ask gemessen hat. Das Budget bleibt
        # 0/0: ohne bekannte Klasse gibt es keine Spanne, nur einen Grund.
        return StopBudget(
            lower_bps=Decimal("0"),
            upper_bps=Decimal("0"),
            cost_bps=measured_cost_bps if measured_cost_bps is not None else Decimal(0),
            asset_class=key,
            leverage=leverage,
            tradeable=False,
            reason="unknown_asset_class",
            cost_is_measured=measured,
        )

    if not measured and require_measured_cost:
        # Kein stiller Rueckfall auf die Annahme: der Aufrufer hat erklaert, dass
        # er die Zusage ``max_cost_drag`` belegen muss, und ohne Messung kann er
        # das nicht. Nicht handeln ist die einzige Antwort, die nicht luegt.
        # ``cost_is_measured=False``/``cost_bps=0`` verlieren hier nichts: dieser
        # Zweig ist nur ohne Messung erreichbar (``not measured``).
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

"""Befund K3: das Stop-Budget rechnete mit Annahmen, obwohl die Messung vorlag.

Der Runner misst die Roundturn-Kosten im Kostentor aus dem Live-Bid/Ask; das Stop-Budget
befragte daneben ``ASSUMED_ROUND_TURN_COST_BPS`` (fx_major 0,65 bp) und leitete daraus
die Untergrenze ab. Im scharfen Lauf standen 1,554 bp im Journal -- Faktor 2,4 in die
schmeichelnde Richtung, und die Zusage ``max_cost_drag`` war bei jedem eroeffneten
EURUSD-Trade gerissen, ohne dass es jemand sah.

Jeder Test hier ist ein **roter Eichfall**: er waere gegen die Fassung, die immer die
Tabelle befragte, fehlgeschlagen. Wo er das nicht waere, steht es dabei.

Die Bausteine (Instrument, Konto, Auftrag) stehen bewusst lokal und nicht per Import aus
einer anderen Testdatei: sie sind der Gegenstand des Eichfalls und duerfen sich nicht
unter der Hand mitaendern.
"""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mt5_trading_ai.backtest.engine import Signal
from mt5_trading_ai.execution import runner as runner_modul
from mt5_trading_ai.execution.cost_gate import CostGate, CostGateDecision
from mt5_trading_ai.execution.risk_manager import (
    MEASURED_COST_BPS_META_KEY,
    RiskAuthorization,
    RiskManager,
    RiskPolicy,
)
from mt5_trading_ai.execution.runner import RunnerConfig, run_signal
from mt5_trading_ai.gates.criteria import CriteriaVerdict
from mt5_trading_ai.risk.stop_budget import (
    ASSUMED_ROUND_TURN_COST_BPS,
    KOSTENPRAEMISSE_BPS,
    cost_bps_from_fraction,
    stop_budget,
)
from mt5_trading_ai.venue.protocol import (
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

#: Die im Journal des scharfen Laufs gemessene EURUSD-Kostenquote (Schritt Kostentor).
JOURNAL_COST_FRACTION = Decimal("0.0001554")
#: Dieselbe Lage in Basispunkten -- und die Annahme, gegen die sie antritt.
GEMESSEN_BPS = Decimal("1.554")
ANGENOMMEN_BPS = ASSUMED_ROUND_TURN_COST_BPS["fx_major"]  # 0,65 bp
#: Der getrennt gepflegte Plausibilitaetsboden (Stufe 7). BEWUSST eine andere Zahl.
BODEN_BPS = KOSTENPRAEMISSE_BPS["fx_major"]  # 0,05 bp


def _instrument() -> Instrument:
    return Instrument(
        symbol="EURUSD",
        venue="mt5",
        asset_class=AssetClass.FX_MAJOR,
        contract_size=Decimal("100000"),
        tick_size=Decimal("0.00001"),
        pip_size=Decimal("0.0001"),
        digits=5,
        volume_min=Decimal("0.01"),
        volume_step=Decimal("0.01"),
        volume_max=Decimal("100"),
        base_currency="EUR",
        quote_currency="USD",
        stop_level_points=10,
        freeze_level_points=0,
        fees=FeeSchedule(
            commission_per_lot_round_turn=Decimal("7"),
            typical_spread_points=Decimal("6"),
            swap_long_per_lot_per_night=Decimal("-2"),
            swap_short_per_lot_per_night=Decimal("-1"),
            triple_swap_weekday=2,
            currency="USD",
        ),
        sessions=(),
    )


def _account() -> AccountState:
    return AccountState(
        account_id="1",
        currency="USD",
        balance=Decimal("10000"),
        equity=Decimal("10000"),
        margin_used=Decimal("0"),
        margin_free=Decimal("10000"),
        is_demo=True,
        ts=NOW,
    )


def _request(*, volume: str = "0.01", stop_loss: str = "1.09000") -> OrderRequest:
    return OrderRequest(
        client_order_id="k3-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal(volume),
        stop_loss=Decimal(stop_loss),
    )


def _autorisiere(
    rm: RiskManager,
    *,
    stop_loss: str = "1.09000",
    volume: str = "0.01",
    meta: dict[str, Any] | None = None,
    measured_cost_bps: Decimal | None = None,
) -> RiskAuthorization:
    request = _request(volume=volume, stop_loss=stop_loss)
    if meta is not None:
        request = replace(request, meta=meta)
    return rm.authorize_opening(
        instrument=_instrument(),
        request=request,
        account=_account(),
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=NOW,
        measured_cost_bps=measured_cost_bps,
    )


# --------------------------------------------------------------------------- #
# 1) Die Rechnung selbst: gemessen ergibt ein anderes Budget als angenommen.   #
# --------------------------------------------------------------------------- #
def test_gemessene_kostenlage_ergibt_ein_anderes_stop_budget() -> None:
    """1,554 bp gemessen -> Untergrenze 15,54 bp; 0,65 bp angenommen -> 6,5 bp.

    Der numerische Anker des Befunds. Halb roter Eichfall, und die Haelfte gehoert
    benannt: die vier Zahlen-Zusicherungen waeren auch gegen die alte Fassung gruen
    gewesen -- ``stop_budget`` konnte eine Messung schon verarbeiten --, die beiden
    ``cost_basis``-Zusicherungen dagegen nicht: die Eigenschaft gab es dort nicht
    (``hasattr(StopBudget, "cost_basis")`` war ``False``, der Test waere mit
    ``AttributeError`` gefallen). Rot an der Sache selbst wird die alte Fassung erst
    bei den Aufrufern weiter unten: dort wurde die Messung nie uebergeben, und genau
    das war der Befund.
    """
    angenommen = stop_budget(asset_class="fx_major", leverage=5)
    gemessen = stop_budget(
        asset_class="fx_major", leverage=5, measured_cost_bps=GEMESSEN_BPS
    )
    assert angenommen.lower_bps == Decimal("6.5")
    assert gemessen.lower_bps == Decimal("15.54")
    assert gemessen.lower_bps > angenommen.lower_bps * Decimal("2.3")
    assert angenommen.cost_is_measured is False
    assert angenommen.cost_basis == "annahme"
    assert gemessen.cost_is_measured is True
    assert gemessen.cost_basis == "gemessen"


def test_kostenquote_wird_an_einer_stelle_in_bp_umgerechnet() -> None:
    """Die Bruecke Kostentor -> Stop-Budget. 0,0001554 sind 1,554 bp."""
    assert cost_bps_from_fraction(JOURNAL_COST_FRACTION) == GEMESSEN_BPS


@pytest.mark.parametrize("unbrauchbar", ["0", "-0.0001", "NaN", "Infinity"])
def test_unbrauchbare_kostenquote_wirft(unbrauchbar: str) -> None:
    """Ein Defekt der Messung wirft; er faellt nicht auf die Tabelle zurueck.

    Eine Quote von 0 hiesse kostenloses Handeln und drueckte die Untergrenze auf 0 --
    das waere derselbe Fehler noch einmal, nur besser getarnt.
    """
    with pytest.raises(ValueError):
        cost_bps_from_fraction(Decimal(unbrauchbar))
    with pytest.raises(ValueError):
        stop_budget(
            asset_class="fx_major",
            leverage=5,
            measured_cost_bps=Decimal(unbrauchbar),
        )


def test_die_ablehnungsakte_verliert_die_messung_nicht() -> None:
    """ROTER EICHFALL: der no-trade-Zweig meldete 'annahme 0 bp' trotz Messung.

    Gemessen an der Vorfassung: ``stop_budget(asset_class='unbekannte_klasse',
    measured_cost_bps=1.554)`` lieferte ``cost_bps=0``, ``cost_is_measured=False``,
    also ``cost_basis == 'annahme'``. Der eine Datensatz, der die Kostenbasis
    dokumentieren soll, gab sie ausgerechnet im Fehlerfall falsch wieder -- und die
    Ablehnungsakte des Order-Pfads (``detail['cost_basis']``) schrieb es ab.

    Die Klasse ist unbekannt, die Kostenlage deswegen nicht. Das Budget bleibt 0/0:
    ohne Klasse gibt es keine Spanne, nur einen Grund.
    """
    ergebnis = stop_budget(
        asset_class="unbekannte_klasse", leverage=5, measured_cost_bps=GEMESSEN_BPS
    )
    assert ergebnis.reason == "unknown_asset_class"
    assert ergebnis.tradeable is False
    assert ergebnis.cost_bps == GEMESSEN_BPS
    assert ergebnis.cost_is_measured is True
    assert ergebnis.cost_basis == "gemessen"
    assert ergebnis.lower_bps == 0 and ergebnis.upper_bps == 0

    ohne = stop_budget(asset_class="unbekannte_klasse", leverage=5)
    assert ohne.cost_bps == 0
    assert ohne.cost_basis == "annahme"  # ohne Messung gibt es nichts zu berichten


def test_messung_macht_eine_unbekannte_klasse_nicht_handelbar() -> None:
    """ROTER EICHFALL: alte Fassung -> handelbar, neue -> ``unknown_asset_class``.

    Alt stand die Klassenpruefung hinter der Kostenbasis (``cost = measured if
    measured else TABELLE.get(key)``): sobald eine Messung mitkam, war ``cost``
    gesetzt und die Klassensperre unerreichbar. Solange niemand eine Messung
    uebergab, fiel das nicht auf -- mit dem Durchreichen aus dem Runner waere die
    Sperre still gestorben.
    """
    ergebnis = stop_budget(
        asset_class="unbekannte_klasse", leverage=5, measured_cost_bps=GEMESSEN_BPS
    )
    assert ergebnis.tradeable is False
    assert ergebnis.reason == "unknown_asset_class"


def test_schalter_macht_die_fehlende_messung_zur_sperre() -> None:
    """ROTER EICHFALL: ``require_measured_cost`` gab es nicht (alt: TypeError).

    Ohne Messung ist die Zusage ``max_cost_drag`` unbelegt behauptet. Wer das nicht
    darf, bekommt ``no_trade`` -- und nicht die Tabelle.
    """
    ergebnis = stop_budget(
        asset_class="fx_major", leverage=5, require_measured_cost=True
    )
    assert ergebnis.tradeable is False
    assert ergebnis.reason == "cost_not_measured"
    mit_messung = stop_budget(
        asset_class="fx_major",
        leverage=5,
        measured_cost_bps=GEMESSEN_BPS,
        require_measured_cost=True,
    )
    assert mit_messung.tradeable is True  # derselbe Schalter sperrt nicht blind


def test_guenstigere_messung_senkt_die_untergrenze() -> None:
    """Gruener Gegenpol: die Messung ist kein Einbahn-Verschaerfer.

    Eine Pruefung, die nur in eine Richtung wirken kann, belegt nichts. Gold ist mit
    1,5 bp angenommen; eine gemessene Lage von 1,0 bp senkt die Untergrenze.
    """
    guenstig = stop_budget(
        asset_class=AssetClass.GOLD.value,
        leverage=5,
        measured_cost_bps=Decimal("1.0"),
        require_measured_cost=True,
    )
    angenommen = stop_budget(asset_class=AssetClass.GOLD.value, leverage=5)
    assert guenstig.tradeable is True
    assert guenstig.lower_bps < angenommen.lower_bps


# --------------------------------------------------------------------------- #
# 2) Der Order-Pfad: die Messung kommt an, die Annahme ist sichtbar.           #
# --------------------------------------------------------------------------- #
def test_uebergebene_messung_hebt_die_untergrenze_am_orderpfad() -> None:
    """ROTER EICHFALL: alt kannte ``authorize_opening`` das Argument nicht.

    Und selbst wenn: es befragte allein ``policy.measured_cost_bps``, das kein
    Aufrufer je fuellte -> Untergrenze 6,5 statt 15,54 bp.
    """
    auth = _autorisiere(RiskManager(), measured_cost_bps=GEMESSEN_BPS)
    assert auth.budget is not None
    assert auth.budget.cost_is_measured is True
    assert auth.budget.lower_bps == Decimal("15.54")


def test_messung_reist_im_meta_zur_zweiten_pruefung_mit() -> None:
    """ROTER EICHFALL: alt las niemand ``meta[measured_cost_bps]``.

    ``submit_order`` faehrt die Risikoschicht ein zweites Mal und bekommt kein eigenes
    Argument. Ohne diesen Kanal rechnete die zweite Pruefung gegen die Annahmetabelle
    -- also milder als die erste, die sie absichern soll.
    """
    auth = _autorisiere(RiskManager(), meta={MEASURED_COST_BPS_META_KEY: GEMESSEN_BPS})
    assert auth.budget is not None
    assert auth.budget.cost_is_measured is True
    assert auth.budget.lower_bps == Decimal("15.54")


def test_auftragsdaten_koennen_die_politik_nicht_unterbieten() -> None:
    """ROTER EICHFALL: die mitgereiste Zahl schlug die Politik des Betreibers.

    Gemessen an der Vorfassung: ``RiskPolicy(measured_cost_bps={'fx_major': 5.0})``
    ergab eine Untergrenze von 50 bp; dieselbe Politik mit
    ``meta={'measured_cost_bps': 0.001}`` ergab 0,01 bp, ``approved=True`` und das
    Etikett 'gemessen 0.001 bp'. Ein Auftrag konnte damit die Kostenpraemisse des
    Systems von aussen setzen -- und ausgerechnet die zweite Pruefung im Venue, die
    einen Fehler der ersten abfangen soll, rechnete mit der Zahl des Aufrufers.

    Jetzt bewegt die mitgereiste Zahl die Rechnung nur nach oben. Die Klammerung ist
    nicht still: die verworfene Zahl steht mit ihrem Grund in der Akte.
    """
    politik = RiskPolicy(measured_cost_bps={"fx_major": Decimal("5.0")})
    ohne = _autorisiere(RiskManager(politik))
    assert ohne.budget is not None
    assert ohne.budget.lower_bps == Decimal("50")

    unterbietung = _autorisiere(
        RiskManager(politik), meta={MEASURED_COST_BPS_META_KEY: Decimal("0.001")}
    )
    assert unterbietung.budget is not None
    assert unterbietung.budget.lower_bps == Decimal("50")
    assert unterbietung.detail["cost_basis"] == (
        "kampagne 5.0 bp (Auftrag 0.001 bp verworfen: unter Praemisse 5.0 bp)"
    )


def test_auftragsdaten_koennen_den_plausibilitaetsboden_nicht_unterbieten() -> None:
    """ROTER EICHFALL: ohne Messkampagne war die Luecke noch weiter offen.

    Ohne ``RiskPolicy.measured_cost_bps`` gab es in der ersten Fassung gar keine Zahl,
    gegen die die mitgereiste haette antreten koennen -- 0,001 bp aus dem ``meta``
    drueckten die Untergrenze auf 0,01 bp statt 6,5 bp.

    **Geaendert in Stufe 7:** Die Praemisse ist nicht mehr die Annahmetabelle, sondern
    ein getrennt gepflegter Plausibilitaetsboden (``KOSTENPRAEMISSE_BPS``). Der Grund
    steht dort: dieselbe Zahl als Rueckfall UND als Schwelle zu benutzen hiess, dass
    ein wirklich billigerer Zugang nie erkannt werden konnte. Die Sache dieses Falls
    ist davon unberuehrt -- 0,001 bp liegt auch unter dem Boden und wird verworfen.
    """
    auth = _autorisiere(
        RiskManager(), meta={MEASURED_COST_BPS_META_KEY: Decimal("0.001")}
    )
    assert auth.budget is not None
    assert auth.budget.lower_bps == Decimal("6.5")
    assert auth.budget.cost_is_measured is False
    assert auth.detail["cost_basis"] == (
        f"annahme {ANGENOMMEN_BPS} bp "
        f"(Auftrag 0.001 bp verworfen: unter Praemisse {BODEN_BPS} bp)"
    )


def test_eine_wirklich_bessere_ausfuehrung_wird_jetzt_erkannt() -> None:
    """GRUENER EICHFALL zur Entkopplung -- vor Stufe 7 war er rot.

    0,30 bp liegen unter der Annahme (0,65 bp) und ueber dem Plausibilitaetsboden
    (0,05 bp). In der alten Fassung wurde die Zahl gegen die Annahme verworfen, und
    danach galt die Annahme: ein Handelsplatz, der wirklich billiger ist, war nicht
    erkennbar. Jetzt gilt die Messung.
    """
    auth = _autorisiere(
        RiskManager(), meta={MEASURED_COST_BPS_META_KEY: Decimal("0.30")}
    )
    assert auth.budget is not None
    assert auth.detail["cost_basis"].startswith("auftrag 0.30 bp")
    assert "verworfen" not in auth.detail["cost_basis"]
    assert auth.budget.lower_bps < Decimal("6.5"), (
        "Eine billigere gemessene Ausfuehrung muss die Untergrenze senken duerfen."
    )


def test_die_herkunft_der_kostenzahl_steht_im_protokoll() -> None:
    """ROTER EICHFALL: jede uebergebene Zahl hiess 'gemessen', egal woher sie kam.

    Vier Kanaele, vier Woerter. 'gemessen' allein sagte nur "jemand hat eine Zahl
    uebergeben" -- eine am Auftrag mitgereiste Zahl (``auftrag``) ist etwas anderes
    als die Live-Messung dieses Laufs (``gemessen``) und etwas anderes als die
    Messkampagne des Betreibers (``kampagne``). Nachgemessen an der Vorfassung: der
    ``meta``- und der Kampagnen-Kanal lieferten beide 'gemessen ... bp'.
    """
    gemessen = _autorisiere(RiskManager(), measured_cost_bps=GEMESSEN_BPS)
    assert gemessen.detail["cost_basis"] == f"gemessen {GEMESSEN_BPS} bp"

    auftrag = _autorisiere(
        RiskManager(), meta={MEASURED_COST_BPS_META_KEY: GEMESSEN_BPS}
    )
    assert auftrag.detail["cost_basis"] == f"auftrag {GEMESSEN_BPS} bp"

    kampagne = _autorisiere(
        RiskManager(RiskPolicy(measured_cost_bps={"fx_major": Decimal("5.0")}))
    )
    assert kampagne.detail["cost_basis"] == "kampagne 5.0 bp"

    annahme = _autorisiere(RiskManager())
    assert annahme.detail["cost_basis"] == f"annahme {ANGENOMMEN_BPS} bp"


def test_die_praemisse_klammert_nur_nach_unten() -> None:
    """Gruener Gegenpol: der Kanal bleibt ein Verschaerfer, kein Kaefig.

    Eine Klammer, die in beide Richtungen zieht, waere keine Sicherung, sondern eine
    Abschaffung des Kanals: seine Aufgabe ist, die zweite Pruefung im Venue NICHT
    milder rechnen zu lassen als die erste. Die mitgereiste Zahl ueber der Praemisse
    zaehlt deshalb unveraendert weiter -- das ist der Regelfall am Live-Bid/Ask, wo
    gemessen fast immer teurer ist als die schmeichelnde Annahme.
    """
    auth = _autorisiere(
        RiskManager(), meta={MEASURED_COST_BPS_META_KEY: GEMESSEN_BPS}
    )
    assert auth.budget is not None
    assert auth.budget.lower_bps == Decimal("15.54")
    assert "verworfen" not in auth.detail["cost_basis"]


def test_falscher_typ_im_meta_wirft_statt_zurueckzufallen() -> None:
    """Ein Float ist keine gepruefte Messung. Defekt wirft, kein stiller Rueckfall."""
    with pytest.raises(ValueError, match=MEASURED_COST_BPS_META_KEY):
        _autorisiere(RiskManager(), meta={MEASURED_COST_BPS_META_KEY: 1.554})


@pytest.mark.parametrize("unbrauchbar", ["0", "-1.554", "NaN", "-Infinity"])
def test_unbrauchbare_zahl_im_meta_wirft_und_wird_nicht_weggeklammert(
    unbrauchbar: str,
) -> None:
    """Gruen auch gegen die Vorfassung -- und trotzdem noetig.

    Dort fing ``stop_budget`` diese Werte ab, weil sie ungeprueft bis dorthin
    durchgereicht wurden. Seit die Praemisse alles Zu-Niedrige abklammert, kaeme eine
    -1,554 dort nie an: sie waere stillschweigend zur Nichtzahl geworden, und aus
    einem Defekt des Aufrufers waere ein Achselzucken. ``NaN`` waere im Vergleich mit
    der Praemisse sogar ein ``InvalidOperation`` statt einer Begruendung.

    Die Klammer gilt nur fuer formal gueltige Zahlen; die Form wirft weiterhin.
    """
    with pytest.raises(ValueError, match=MEASURED_COST_BPS_META_KEY):
        _autorisiere(
            RiskManager(), meta={MEASURED_COST_BPS_META_KEY: Decimal(unbrauchbar)}
        )


def test_annahmebasis_steht_sichtbar_in_jeder_autorisierung() -> None:
    """ROTER EICHFALL: ``cost_basis`` gab es nicht -- die Annahme war still.

    Wenn schon Tabelle, dann sichtbar: der Aufrufer bekommt die Basis mit dem
    Ergebnis, nicht als Fussnote in einer Datei, die er nicht liest.
    """
    angenommen = _autorisiere(RiskManager())
    assert angenommen.approved is True
    assert angenommen.detail["cost_basis"] == f"annahme {ANGENOMMEN_BPS} bp"
    gemessen = _autorisiere(RiskManager(), measured_cost_bps=GEMESSEN_BPS)
    assert gemessen.detail["cost_basis"] == f"gemessen {GEMESSEN_BPS} bp"


def test_policy_schalter_sperrt_den_ungemessenen_orderpfad() -> None:
    """ROTER EICHFALL: die Politik hatte keinen solchen Schalter.

    Der Betreiber, der nicht auf Annahmen handeln will, bekommt eine Sperre mit Grund
    statt einer Tabelle mit Schweigen.
    """
    auth = _autorisiere(RiskManager(RiskPolicy(require_measured_cost=True)))
    assert auth.approved is False
    assert auth.reason == "stop_budget_cost_not_measured"
    assert auth.detail["cost_basis"] == "annahme 0 bp"


def test_stop_auf_der_alten_annahmegrenze_wird_jetzt_gesperrt() -> None:
    """ROTER EICHFALL und zugleich das Ergebnis, das nicht weggeredet wird.

    Ein Stop, der gegen die angenommenen 0,65 bp (Untergrenze 6,5 bp) durchging,
    reisst gegen die gemessenen 1,554 bp (Untergrenze 15,54 bp) die Zusage
    ``max_cost_drag``. Die Sperre loest aus; die Zusage wird nicht gesenkt.
    """
    ohne_messung = _autorisiere(RiskManager(), stop_loss="1.09850")
    assert ohne_messung.approved is True  # so lief der scharfe Lauf

    mit_messung = _autorisiere(
        RiskManager(), stop_loss="1.09850", measured_cost_bps=GEMESSEN_BPS
    )
    assert mit_messung.approved is False
    assert mit_messung.reason == "stop_budget_below_cost_floor"
    assert mit_messung.detail["cost_floor_bps"] == "15.54"


# --------------------------------------------------------------------------- #
# 3) Die volle Kette: der Runner benutzt seine eigene Messung.                 #
# --------------------------------------------------------------------------- #
def _paper_run() -> Any:
    """Die volle Kette gegen das synthetische Demo-Terminal (``tools/paper_run.py``)."""
    tools = Path(__file__).resolve().parents[1] / "tools"
    spec = importlib.util.spec_from_file_location(
        "paper_run_kostenbasis", tools / "paper_run.py"
    )
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _schritt(report: Any, name: str) -> Any:
    treffer = [s for s in report.steps if s.name == name]
    assert treffer, f"Naht {name} fehlt in der Checkliste"
    return treffer[0]


def test_runner_setzt_den_stop_auf_die_gemessene_untergrenze() -> None:
    """ROTER EICHFALL: alt stand hier ``15.0bps -> stop=1.09835`` bei 0,15 Lot.

    Das synthetische Demo-Terminal stellt EURUSD 1,09990/1,10000 bei 7 USD Kommission
    je Lot -- gemessen 2,45 bp roundturn, Untergrenze also 24,5 bp. Alt band der
    Tiefe-Floor (15 bp), weil die angenommenen 0,65 bp nur 6,5 bp verlangten: der Stop
    lag zu eng und die Position war entsprechend zu gross.
    """
    report, _halt = _paper_run().run_paper("EURUSD")
    assert report.opened, [s for s in report.steps if not s.ok]
    assert _schritt(report, "stop-preis").detail == "24.5bps -> stop=1.09730"
    assert "gemessen" in _schritt(report, "kostentor").detail
    assert _schritt(report, "stop-budget").detail == (
        "[24.5, 333.3]bps (Kosten 2.45bp gemessen)"
    )
    assert _schritt(report, "sizing").detail == "volume=0.09"


def test_kostentor_steht_vor_dem_stop_preis() -> None:
    """ROTER EICHFALL: alt lag das Kostentor HINTER dem Stop-Preis.

    Genau daher stammte der Befund: die Messung lag dreissig Zeilen zu spaet vor, und
    das Budget griff derweil zur Tabelle. Die Reihenfolge ist hier die Sperre.
    """
    report, _halt = _paper_run().run_paper("EURUSD")
    namen = [s.name for s in report.steps]
    assert namen.index("kostentor") < namen.index("stop-preis")


def test_strikte_politik_laesst_die_volle_kette_trotzdem_durch() -> None:
    """ROTER EICHFALL fuer den ``meta``-Kanal ueber die Venue-Grenze hinweg.

    Mit ``require_measured_cost=True`` handelt nur noch, wer misst -- und
    ``submit_order`` faehrt die Risikoschicht ein ZWEITES Mal, ohne das Argument des
    Runners zu kennen. Oeffnet die Kette hier, dann ist die Messung wirklich bis in
    die zweite Pruefung gereist. Alt gab es weder Schalter noch Kanal.
    """
    modul = _paper_run()
    rm = RiskManager(RiskPolicy(require_measured_cost=True))
    venue = modul.build_paper_venue(rm)
    venue.adopt_book()
    report = run_signal(
        venue=venue,
        risk_manager=rm,
        admission=CriteriaVerdict(passed=True, results=()),
        symbol="EURUSD",
        side=Signal.LONG,
        config=RunnerConfig(
            cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
        ),
        now=modul._TS,
        client_order_id="k3-strikt",
    )
    assert report.opened, report.reject_reason
    assert _schritt(report, "stop-budget").detail.endswith("gemessen)")


def test_der_runner_rechnet_die_spanne_mit_der_politik_des_managers() -> None:
    """ROTER EICHFALL: der Runner rechnete die Untergrenze mit den Vorgabewerten.

    Dieselbe Rechnung stand an zwei Stellen: ``execution/runner.py`` rief
    ``stop_budget`` mit den Vorgabewerten der Signatur (``max_cost_drag=0.05``),
    ``execution/risk_manager.py`` mit den Werten der Politik. Nachgemessen an der
    Vorfassung: bei gemessenen 2,4545 bp verlangte der Runner 24,5 bp, eine Politik
    mit ``max_cost_drag=0.02`` unmittelbar danach 61,4 bp -- der Runner setzte den
    Stop auf seine eigene Zahl, und die Risikoschicht lehnte ihn Zeilen spaeter mit
    ``stop_budget_below_cost_floor`` ab. Die strengere Politik erzeugte also nicht
    den weiteren Stop, sondern gar keinen Handel; die Vorfassung endete hier mit
    ``opened=False``.

    Zweitens haengt hier die Rundung mit drin: gerechnet sind
    61.36363636363636363636363638 bp, gesetzt werden konnte auf dem Tick-Raster nur
    1.09325 -- wirksam ...636 bp, zwei Einheiten in der letzten Stelle ZU WENIG, und
    die Risikoschicht prueft hart auf ``>=``. Der Stop geht deshalb einen Tick weiter
    vom Markt weg (1.09324). Ohne diesen Schritt bliebe die Kette auch mit
    gleichgezogener Politik zu.
    """
    modul = _paper_run()
    rm = RiskManager(RiskPolicy(max_cost_drag=Decimal("0.02")))
    venue = modul.build_paper_venue(rm)
    venue.adopt_book()
    report = run_signal(
        venue=venue,
        risk_manager=rm,
        admission=CriteriaVerdict(passed=True, results=()),
        symbol="EURUSD",
        side=Signal.LONG,
        config=RunnerConfig(
            cost_gate=CostGate(max_roundturn_cost_fraction=Decimal("0.0005")),
        ),
        now=modul._TS,
        client_order_id="k3-politik",
    )
    assert report.opened, report.reject_reason
    assert _schritt(report, "stop-budget").detail == (
        "[61.4, 333.3]bps (Kosten 2.45bp gemessen)"
    )
    assert _schritt(report, "stop-preis").detail == "61.5bps -> stop=1.09324"
    # Und die Probe aufs Exempel: der GESETZTE Stop haelt die Untergrenze.
    budget = rm.stop_budget_for(
        asset_class=AssetClass.FX_MAJOR.value,
        leverage=5,
        measured_cost_bps=Decimal("2.454545454545454545454545455"),
    )
    wirksam = (
        (Decimal("1.10000") - Decimal("1.09324")) / Decimal("1.10000")
        * Decimal("10000")
    )
    assert budget.allows(wirksam)


def test_freigabe_ohne_kostenquote_wirft(monkeypatch: pytest.MonkeyPatch) -> None:
    """ROTER EICHFALL: alt gab es diese Pruefung nicht -- der Lauf eroeffnete weiter.

    Ein freigegebenes Kostentor ohne Zahl ist ein Widerspruch im Werkzeug, kein
    Marktzustand. Der Runner wirft, statt ausgerechnet dann ungemessen zu eroeffnen,
    wenn die Messung kaputt ist.
    """
    monkeypatch.setattr(
        runner_modul,
        "evaluate_cost_gate",
        lambda **_kwargs: CostGateDecision(True, None, None),
    )
    with pytest.raises(ValueError, match="Kostenquote"):
        _paper_run().run_paper("EURUSD")

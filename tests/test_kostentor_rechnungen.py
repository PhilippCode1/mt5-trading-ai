"""Die Rechnungen des Kostentors -- von Hand nachgerechnet.

Schwesterdatei zu ``test_kostentor_ampel.py``. Dort steht das Urteil, hier stehen die
Zahlen, auf denen es steht: K in Basispunkten, die Waehrungsumrechnung der Kommission,
``p*``, die Lesarten A-F, die Jahreskostenlast L, die Swap-Last und die Umkehrung nach
dem Stopabstand.

REGEL FUER DIESE DATEI: kein Erwartungswert wird aus der Umsetzung abgelesen. Jede Zahl
steht als Rechnung im Kommentar darueber, und die Eingaben sind ueberwiegend so gewaehlt,
dass die Rechnung ohne Rechner aufgeht (Preis 2,00, Kontrakt 100 000, ATR 20 bp). Wo
gegen die echten Projektzahlen geprueft wird, ist die Herkunft der Eingabe benannt.

Die Hausfehlerklasse dieses Repos steht in ``ABSCHLUSS-3a/09-EIGENE-FEHLER.md``:
eine Bedingung, die nicht ausloesen kann; eine fehlende Waehrungsumrechnung; eine
Einheitenverwechslung zwischen Punkten, Basispunkten und Prozent. Nach genau diesen
drei ist hier gesucht -- und zwei davon sind gefunden worden; sie stehen unten unter
"GEFUNDENE MAENGEL".
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from mt5_trading_ai.costs.broker_costs import (
    STATUS_BELEGT,
    STATUS_OHNE_SPREAD,
    InstrumentCost,
)
from mt5_trading_ai.costs.volatility import (
    STATUS_MEASURED,
    STATUS_NOT_MEASURED,
    AtrMeasurement,
)
from tools.kostentor import (
    HANDELSTAGE,
    M1_GELB_MAX,
    M1_GRUEN_MAX,
    M2_MAX_JAHRESLAST,
    KostentorError,
    Zeile,
    _ampel,
    _fx,
    _p_stern,
    _q,
    _zeile,
    bestes_p_je_instrument,
    einteilung,
    erste_zeile_je_instrument,
    gruene_je_broker,
    guenstigste_zeile_je_instrument,
    hebel_je_instrument,
    jahreslast,
    kreuzanteil,
    lesarten,
    m2_hebel,
    m2_urteil,
    stop_fuer_schwelle,
    swap_last_jahr,
)

REPO = Path(__file__).resolve().parents[1]

# --- Baukaesten ------------------------------------------------------------
# Runde Eingaben, damit jede Erwartung ohne Rechner nachvollziehbar ist.

#: Umrechnungskurse mit glatten Zahlen -- NICHT die gemessenen.
KURSE = {"EURUSD": 1.25, "GBPUSD": 1.5, "USDJPY": 150.0}


def kosten(
    *,
    quote_currency: str = "USD",
    spread_price: Decimal | None = Decimal("0.0002"),
    commission_round_turn: Decimal | None = Decimal("10"),
    commission_currency: str | None = "USD",
    commission_bps_round_turn: Decimal | None = None,
    contract_size: Decimal | None = Decimal("100000"),
    swap_bps_night_long: Decimal | None = None,
    status: str = STATUS_BELEGT,
    reason: str | None = None,
) -> InstrumentCost:
    return InstrumentCost(
        key="TEST", broker_symbol="TEST", status=status, reason=reason,
        quote_currency=quote_currency, spread_published=None, spread_unit=None,
        unit_in_price=None, spread_kind=None, spread_markup_factor=None,
        spread_price=spread_price, commission_round_turn=commission_round_turn,
        commission_currency=commission_currency,
        commission_bps_round_turn=commission_bps_round_turn,
        swap_long=None, swap_short=None, swap_unit=None,
        swap_bps_night_long=swap_bps_night_long, swap_bps_night_short=None,
        min_lot=None, contract_size=contract_size, tick_size=None,
        trading_hours=None, rollover=None, source_url="x", retrieved_on="x",
        quote=None, verification=None,
    )


def messung(
    *,
    price_median: float | None = 2.0,
    atr_median_bps: float | None = 20.0,
    atr_p25_bps: float | None = 10.0,
    spread_median_points: float | None = 3.0,
    point: float | None = 0.001,
    status: str = STATUS_MEASURED,
    reason: str | None = None,
) -> AtrMeasurement:
    return AtrMeasurement(
        symbol="TEST", status=status, reason=reason, bars=1000,
        window_start=None, window_end=None, atr_median_price=1.0, atr_p25_price=1.0,
        atr_median_bps=atr_median_bps, atr_p25_bps=atr_p25_bps,
        atr_median_price_roh=None, price_median=price_median,
        spread_median_points=spread_median_points, spread_p75_points=None,
        point=point, digits=None, contract_size=None, gap_bars=None,
    )


def zeile(**kwargs: object) -> Zeile:
    """Die Standardzeile: K = 2,0 bp, ATR50 = 20 bp, ATR25 = 10 bp."""
    felder: dict[str, object] = dict(
        instrument="TEST", broker="broker_a", rechenbar=True, grund=None,
        spread_bps=Decimal("1.0"), kommission_bps=Decimal("0.5"),
        slippage_bps=Decimal("0.5"), k_bps=Decimal("2.0"),
        atr_median_bps=Decimal("20"), atr_p25_bps=Decimal("10"),
        swap_bps_nacht=None, gemessener_spread_bps=None,
    )
    felder.update(kwargs)
    return Zeile(**felder)  # type: ignore[arg-type]


def rechne(
    *,
    kosten_eintrag: InstrumentCost | None = None,
    messung_eintrag: AtrMeasurement | None = None,
    slippage: Decimal | None = Decimal("0.5"),
) -> Zeile:
    return _zeile(
        "TEST",
        "broker_a",
        kosten_eintrag if kosten_eintrag is not None else kosten(),
        messung_eintrag if messung_eintrag is not None else messung(),
        {} if slippage is None else {"TEST": slippage},
        KURSE,
    )


# ===========================================================================
# 1. K in Basispunkten -- Spread, Kommission, Slippage
# ===========================================================================


def test_k_von_hand() -> None:
    """K = Spread + Kommission + Slippage, alles in Basispunkten des Nominals.

    Von Hand:
      Spread    = 0,0002 Preiseinheiten / 2,00 Preis x 10 000 = 1,0 bp
      Nominal   = 100 000 Kontrakt x 2,00 Preis               = 200 000 USD
      Kommission= 10 USD / 200 000 USD x 10 000               = 0,5 bp
      Slippage  = 0,5 bp (Annahme aus der Kostendatei)
      K         = 1,0 + 0,5 + 0,5                             = 2,0 bp
    """
    z = rechne()
    assert z.rechenbar
    assert z.spread_bps == Decimal("1.0")
    assert z.kommission_bps == Decimal("0.5")
    assert z.slippage_bps == Decimal("0.5")
    assert z.k_bps == Decimal("2.0")


def test_spread_wird_am_preis_gemessen_nicht_addiert() -> None:
    """Der doppelte Preis halbiert den Spread in Basispunkten.

    Von Hand: 0,0002 / 4,00 x 10 000 = 0,5 bp (statt 1,0 bp bei Preis 2,00).
    Ein Spread, der als Preiseinheit einfach uebernommen wuerde, bliebe gleich.
    """
    z = rechne(messung_eintrag=messung(price_median=4.0))
    assert z.spread_bps == Decimal("0.5")


def test_kommission_wird_in_die_notierungswaehrung_umgerechnet() -> None:
    """Die Hausfehlerklasse Nummer zwei: K ohne Waehrungsumrechnung.

    Ein in JPY notiertes Instrument mit einer Kommission in USD.
    Von Hand:
      Kommission = 10 USD x 150 JPY/USD                 = 1 500 JPY
      Nominal    = 100 000 Kontrakt x 200,00 JPY        = 20 000 000 JPY
      Kommission = 1 500 / 20 000 000 x 10 000          = 0,75 bp

    OHNE die Umrechnung stuenden dort 10 / 20 000 000 x 10 000 = 0,005 bp --
    Faktor 150 zu klein und damit ein zu billiges, schmeichelndes K. Genau dieser
    Fehler ist in ``ABSCHLUSS-3a/09-EIGENE-FEHLER.md`` Nr. 2 dokumentiert.
    """
    z = rechne(
        kosten_eintrag=kosten(quote_currency="JPY"),
        messung_eintrag=messung(price_median=200.0),
    )
    assert z.kommission_bps == Decimal("0.75")
    assert z.kommission_bps != Decimal("0.005"), "Umrechnung fehlt"


def test_prozentkommission_schlaegt_den_betrag_je_lot() -> None:
    """Ein veroeffentlichter Prozentsatz gewinnt gegen den Betrag je Lot.

    Beides steht in der Kostendatei (Aktien-CFD): 0,04 USD je Aktie und 20 bp
    Regelsatz je Round-Turn. Der Betrag ergaebe hier
    10 / 200 000 x 10 000 = 0,5 bp; der Prozentsatz 20 bp. Zwischen beiden liegt
    eine Groessenordnung, und es muss der Prozentsatz sein: er skaliert mit der
    Position, der Betrag tut es nicht.
    """
    z = rechne(kosten_eintrag=kosten(commission_bps_round_turn=Decimal("20")))
    assert z.kommission_bps == Decimal("20")
    # K = 1,0 Spread + 20 Kommission + 0,5 Slippage = 21,5 bp
    assert z.k_bps == Decimal("21.5")


def test_gemessener_spread_wird_von_punkten_in_preiseinheiten_gehoben() -> None:
    """Punkte gegen Preiseinheiten -- die Einheitenfalle.

    Von Hand: 3 Punkte x 0,001 Punktwert = 0,003 Preiseinheiten;
              0,003 / 2,00 x 10 000 = 15,0 bp.
    Wer die Punktzahl ohne ``point`` einsetzt, landet bei
    3 / 2,00 x 10 000 = 15 000 bp -- Faktor 1000.
    """
    z = rechne()
    assert z.gemessener_spread_bps == Decimal("15.0")


def test_ohne_punktwert_kein_gemessener_spread() -> None:
    """Fehlt ``point``, bleibt der gemessene Spread leer statt geraten."""
    z = rechne(messung_eintrag=messung(point=None))
    assert z.gemessener_spread_bps is None


@pytest.mark.parametrize(
    ("bau", "erwartet"),
    [
        (
            {"kosten_eintrag": kosten(status=STATUS_OHNE_SPREAD, reason="kein Spread")},
            "kein Spread",
        ),
        (
            {"messung_eintrag": messung(status=STATUS_NOT_MEASURED, reason="kein Sym")},
            "kein Sym",
        ),
        ({"messung_eintrag": messung(price_median=None)}, "Referenzpreis"),
        ({"kosten_eintrag": kosten(spread_price=None)}, "Spread oder Kontraktgroesse"),
        ({"slippage": None}, "Slippage-Annahme"),
        ({"messung_eintrag": messung(atr_p25_bps=None)}, "ATR-Kennzahlen"),
    ],
)
def test_jede_fehlende_eingabe_wird_ein_begruendetes_nein(
    bau: dict[str, object], erwartet: str
) -> None:
    """Kein Loch wird mit einer Ersatzzahl gefuellt -- jede Luecke wird begruendet.

    Das ist die Kernregel des Werkzeugs. Ein stiller Default waere hier eine Null,
    und eine Null in K heisst "kostenlos handeln".
    """
    z = rechne(**bau)  # type: ignore[arg-type]
    assert not z.rechenbar
    assert z.k_bps is None
    assert z.grund is not None and erwartet in z.grund


# ===========================================================================
# 2. Die Waehrungsumrechnung selbst
# ===========================================================================


@pytest.mark.parametrize(
    ("betrag", "von", "nach", "erwartet"),
    [
        # gleiche Waehrung: unveraendert
        ("10", "USD", "USD", "10"),
        # 10 USD x 150 JPY/USD = 1500 JPY
        ("10", "USD", "JPY", "1500"),
        # 1500 JPY / 150 JPY/USD = 10 USD
        ("1500", "JPY", "USD", "10"),
        # 10 EUR x 1,25 USD/EUR = 12,50 USD
        ("10", "EUR", "USD", "12.50"),
        # 12,50 USD / 1,25 USD/EUR = 10 EUR
        ("12.50", "USD", "EUR", "10"),
        # 10 GBP x 1,5 USD/GBP = 15 USD
        ("10", "GBP", "USD", "15"),
        # 10 EUR -> 12,50 USD -> x 150 = 1875 JPY  (ueber USD verkettet)
        ("10", "EUR", "JPY", "1875"),
    ],
)
def test_fx_von_hand(betrag: str, von: str, nach: str, erwartet: str) -> None:
    assert _fx(Decimal(betrag), von, nach, KURSE) == Decimal(erwartet)


def test_fx_scheitert_laut_statt_zu_raten() -> None:
    """Ein fehlender Kurs ist ein Fehler, kein Naeherungswert."""
    with pytest.raises(KostentorError, match="EURUSD"):
        _fx(Decimal("10"), "EUR", "USD", {"USDJPY": 150.0})
    with pytest.raises(KostentorError, match="CHF"):
        _fx(Decimal("10"), "CHF", "USD", KURSE)
    with pytest.raises(KostentorError, match="CHF"):
        _fx(Decimal("10"), "USD", "CHF", KURSE)


def test_fx_ist_in_beide_richtungen_umkehrbar() -> None:
    """Hin und zurueck muss denselben Betrag ergeben -- sonst ist eine Richtung
    verdreht (mal statt geteilt). Genau so sieht ein Kursfehler aus."""
    for waehrung in ("EUR", "GBP", "JPY"):
        hin = _fx(Decimal("1000"), "USD", waehrung, KURSE)
        zurueck = _fx(hin, waehrung, "USD", KURSE)
        assert _q(zurueck, "0.000001") == Decimal("1000.000000")


# ===========================================================================
# 3. p* und die Ampelschwellen
# ===========================================================================


def test_p_stern_von_hand() -> None:
    """p* = 0,5 + K / (2 x S).

    Von Hand: 0,5 + 2,0 / (2 x 20) = 0,5 + 0,05 = 0,55.
    Ein Stopabstand doppelt so weit halbiert den Aufschlag: 0,5 + 2/(2x40) = 0,525.
    """
    assert _p_stern(Decimal("2.0"), Decimal("20")) == Decimal("0.55")
    assert _p_stern(Decimal("2.0"), Decimal("40")) == Decimal("0.525")


def test_p_stern_haengt_nur_am_verhaeltnis_von_k_und_s() -> None:
    """Beide Groessen zehnfach: p* bleibt gleich. Das ist der Grund, warum die
    Rechnung ohne Waehrung auskommt -- aber nur, solange beide in derselben
    Einheit stehen."""
    assert _p_stern(Decimal("20"), Decimal("200")) == Decimal("0.55")


@pytest.mark.parametrize(
    ("p", "ampel"),
    [
        ("0.5599", "GRUEN"),
        ("0.56", "GRUEN"),      # die Schwelle selbst zaehlt noch als gruen
        ("0.5601", "GELB"),
        ("0.62", "GELB"),       # und hier ebenso
        ("0.6201", "ROT"),
    ],
)
def test_ampelschwellen_sind_einschliessend(p: str, ampel: str) -> None:
    assert _ampel(Decimal(p)) == ampel


def test_ampelschwellen_stehen_wo_der_massstab_sie_setzt() -> None:
    """56 % und 62 % aus §2 -- nicht nachtraeglich verschoben."""
    assert M1_GRUEN_MAX == Decimal("0.56")
    assert M1_GELB_MAX == Decimal("0.62")


# ===========================================================================
# 4. Die Lesarten-Tabelle A-F
# ===========================================================================


def test_lesarten_von_hand() -> None:
    """Die sechs Lesarten auf der Standardzeile.

    Eingaben: K = 2,0 bp (davon 1,0 Spread und 0,5 Slippage), gemessener Spread
    15,0 bp, Swap 4,0 bp je Nacht, ATR50 = 20 bp, ATR25 = 10 bp.

    Von Hand:
      A  wie gerechnet                        K = 2,0            S = 20
      B  gemessener statt veroeff. Spread     2,0 - 1,0 + 15,0   = 16,0   S = 20
      C  Slippage verdoppelt                  2,0 + 0,5          =  2,5   S = 20
      D  Swap zu 25 %                         2,0 + 4,0 x 0,25   =  3,0   S = 20
      E  ruhige Marktphase                    K = 2,0            S = 10
      F  B + C + D + E                        16,0 + 0,5 + 1,0   = 17,5   S = 10
    """
    z = zeile(
        gemessener_spread_bps=Decimal("15.0"), swap_bps_nacht=Decimal("-4.0")
    )
    v = lesarten(z)
    assert list(v) == ["A", "B", "C", "D", "E", "F"]
    assert v["A"] == (Decimal("2.0"), Decimal("20"))
    assert v["B"] == (Decimal("16.0"), Decimal("20"))
    assert v["C"] == (Decimal("2.5"), Decimal("20"))
    assert v["D"] == (Decimal("3.00"), Decimal("20"))
    assert v["E"] == (Decimal("2.0"), Decimal("10"))
    assert v["F"] == (Decimal("17.50"), Decimal("10"))


def test_lesart_b_ersetzt_den_spread_und_addiert_ihn_nicht() -> None:
    """Der Unterschied zwischen ersetzen und addieren ist hier 1,0 bp.

    Addiert waere B = 2,0 + 15,0 = 17,0 statt 16,0 -- der veroeffentlichte Spread
    stuende dann doppelt in K.
    """
    v = lesarten(zeile(gemessener_spread_bps=Decimal("15.0")))
    assert v["B"][0] == Decimal("16.0")
    assert v["B"][0] != Decimal("17.0")


def test_lesart_b_faellt_ohne_gemessenen_spread_auf_a_zurueck() -> None:
    """Ohne Messung bleibt B = A. Das ist zulaessig, WEIL die Ausgabe die Zeile
    danebenschreibt ('B ohne gemessenen Spread') -- die Luecke bleibt sichtbar."""
    v = lesarten(zeile(gemessener_spread_bps=None))
    assert v["B"] == v["A"]


def test_lesart_d_rechnet_ein_viertel_einer_swapnacht() -> None:
    """25 % der Trades kreuzen den Rollover bei 4 RT/Tag -- also 0,25 Naechte je
    Round-Turn. Von Hand: 2,0 + 4,0 x 0,25 = 3,0 bp."""
    v = lesarten(zeile(swap_bps_nacht=Decimal("-4.0")))
    assert v["D"][0] == Decimal("3.00")


def test_lesart_d_zaehlt_ein_swapguthaben_als_kosten() -> None:
    """``abs``: ein positiver Swap (Guthaben) senkt K nicht. Das ist die
    unschmeichelnde Richtung und damit richtig."""
    v = lesarten(zeile(swap_bps_nacht=Decimal("+4.0")))
    assert v["D"][0] == Decimal("3.00")


def test_lesart_f_ist_wirklich_b_und_c_und_d_und_e() -> None:
    """F muss die vier Einzelaufschlaege tragen, nicht drei davon.

    Von Hand: Spreadtausch (+14,0) + Slippage (+0,5) + Swap (+1,0) auf K,
    und der Stop faellt auf das 25. Perzentil.
    """
    z = zeile(
        gemessener_spread_bps=Decimal("15.0"), swap_bps_nacht=Decimal("-4.0")
    )
    v = lesarten(z)
    k_a = v["A"][0]
    aufschlag_b = v["B"][0] - k_a
    aufschlag_c = v["C"][0] - k_a
    aufschlag_d = v["D"][0] - k_a
    assert v["F"][0] == k_a + aufschlag_b + aufschlag_c + aufschlag_d
    assert v["F"][1] == v["E"][1]


def test_lesarten_verlangen_eine_rechenbare_zeile() -> None:
    with pytest.raises(KostentorError, match="nicht rechenbar"):
        lesarten(zeile(k_bps=None))


# --- GEFUNDENER MANGEL 1 ---------------------------------------------------


def test_lesart_d_setzt_einen_unbekannten_swap_still_auf_null() -> None:
    """MANGEL, festgeschrieben statt behoben: fail-open in Lesart D.

    Zwoelf der achtzehn rechenbaren Zeilen fuehren keinen Swap in Basispunkten --
    die Quelle veroeffentlicht ihn in 'Punkten je Lot' ohne den noetigen Pip-Wert.
    Lesart D behandelt diese Zeilen so, als waere der Swap NULL, nicht als
    'unbekannt'. Die Zeile sieht unter D damit genauso guenstig aus wie unter A.

    Das ist derselbe fail-open, den das Werkzeug an anderer Stelle ausdruecklich
    verbietet ("nicht bewertbar = nicht erfuellt"), und er traegt: unter Lesart D
    steht EURUSD im eingefrorenen Beleg nur deshalb als gruen, weil die drei
    gruenen EURUSD-Zeilen (ic_markets, tickmill, pepperstone) gar keinen Swap
    fuehren -- die einzige EURUSD-Zeile MIT Swap (admirals) faellt unter D von
    56,3 auf 57,9 % und ist nicht gruen.

    Nicht behoben, weil jede Behebung die eingefrorene Ausgabe verschoebe
    (ABSCHLUSS-3a/07-AUSGABEN/kostentor.txt). Dieser Test haelt den Mangel fest,
    damit er nicht ein zweites Mal nur im Dokument steht.
    """
    ohne_swap = lesarten(zeile(swap_bps_nacht=None))
    assert ohne_swap["D"] == ohne_swap["A"], (
        "Sobald ein unbekannter Swap nicht mehr als Null durchgeht, faellt dieser "
        "Test -- dann ist der Mangel behoben und der Test zu loeschen."
    )


# ===========================================================================
# 5. Jahreskostenlast L und das M2-Urteil
# ===========================================================================


def test_jahreslast_von_hand() -> None:
    """L = N x H x k mit k = K / 10 000.

    Von Hand: K = 2,0 bp -> k = 0,0002.
              N = 4 RT/Tag x 250 Handelstage = 1 000 Round-Turns
              L = 1 000 x 5 x 0,0002 = 1,0  ->  100 % des Eigenkapitals.
    """
    assert HANDELSTAGE == 250
    assert jahreslast(Decimal("2.0"), rt_pro_tag=4, hebel=5) == Decimal("1.0000")


def test_jahreslast_verwechselt_basispunkte_nicht_mit_prozent() -> None:
    """Die dritte Hausfehlerklasse: Basispunkte gegen Prozent.

    Von Hand: K = 100 bp ist 1 % des Nominals. Bei 1 RT/Tag, 250 Tagen und
    Hebel 1 sind das 250 x 1 % = 250 % des Eigenkapitals.

    Wer den Faktor 10 000 vergisst, landet bei 2 500 000 %; wer statt dessen
    durch 100 teilt (Prozent statt Basispunkte), bei 25 000 %.
    """
    last = jahreslast(Decimal("100"), rt_pro_tag=1, hebel=1)
    assert last == Decimal("2.5000")
    assert _q(last * 100, "0.1") == Decimal("250.0")


def test_jahreslast_skaliert_linear_in_beiden_groessen() -> None:
    """Doppelter Hebel = doppelte Last, doppelter Umschlag = doppelte Last."""
    grund = jahreslast(Decimal("2.0"), rt_pro_tag=2, hebel=1)
    assert jahreslast(Decimal("2.0"), rt_pro_tag=2, hebel=2) == grund * 2
    assert jahreslast(Decimal("2.0"), rt_pro_tag=4, hebel=1) == grund * 2


def test_jahreslast_weist_nullen_und_negatives_ab() -> None:
    """Fail-closed: ein Umschlag von 0 waere eine Jahreslast von 0 -- kostenloses
    Handeln, also genau der Rueckfall, den dieses Werkzeug ausschliesst."""
    with pytest.raises(KostentorError):
        jahreslast(Decimal("2.0"), rt_pro_tag=0, hebel=5)
    with pytest.raises(KostentorError):
        jahreslast(Decimal("2.0"), rt_pro_tag=4, hebel=0)


def test_m2_reisst_erst_ueber_fuenfzig_prozent() -> None:
    """Der Massstab sagt "ueber 50 %". Genau 50 % haelt.

    Von Hand: L = 1 000 x 5 x k = 0,5  <=>  k = 0,0001  <=>  K = 1,0 bp.
    Bei K = 1,0 bp muss die Zeile halten, bei K = 1,01 bp reissen.
    """
    assert M2_MAX_JAHRESLAST == Decimal("0.50")
    genau = jahreslast(Decimal("1.0"), rt_pro_tag=4, hebel=5)
    assert genau == Decimal("0.5000")

    gerissen, gehalten = m2_urteil([zeile(k_bps=Decimal("1.0"))])
    assert not gerissen and len(gehalten) == 1

    gerissen, gehalten = m2_urteil([zeile(k_bps=Decimal("1.01"))])
    assert len(gerissen) == 1 and not gehalten


def test_m2_deckelt_krypto_auf_hebel_zwei() -> None:
    """ESMA 2:1 fuer Krypto. Bei K = 2,0 bp entscheidet der Deckel das Urteil:

    Von Hand: Hebel 5 -> 1 000 x 5 x 0,0002 = 1,00 -> reisst.
              Hebel 2 -> 1 000 x 2 x 0,0002 = 0,40 -> haelt.
    Waere der Krypto-Deckel nicht gesetzt, stuende BTCUSD faelschlich als
    Reisser da -- und, schwerer wiegend, waere er zu HOCH gesetzt, stuende ein
    unzulaessiger Hebel in der Rechnung.
    """
    assert m2_hebel("BTCUSD") == 2
    assert m2_hebel("EURUSD") == 5
    assert hebel_je_instrument("BTCUSD") == (1, 2)
    assert hebel_je_instrument("NVDA") == (1, 2, 5)

    krypto = zeile(instrument="BTCUSD", k_bps=Decimal("2.0"))
    devise = zeile(instrument="EURUSD", k_bps=Decimal("2.0"))
    gerissen, gehalten = m2_urteil([krypto, devise])
    assert [n for n, _, _ in gerissen] == ["EURUSD"]
    assert [n for n, _, _ in gehalten] == ["BTCUSD"]
    assert gehalten[0][2] == Decimal("0.4000")


def test_m2_urteil_ueberspringt_nicht_rechenbare_zeilen() -> None:
    """Eine Zeile ohne K faellt aus dem Urteil, statt als 0 bp zu gelten."""
    gerissen, gehalten = m2_urteil([zeile(k_bps=None), zeile(k_bps=Decimal("2.0"))])
    assert len(gerissen) + len(gehalten) == 1


# ===========================================================================
# 6. Swap-Last und Kreuzanteil
# ===========================================================================


@pytest.mark.parametrize(
    ("rt", "anteil"),
    [
        (1, "1"),        # 24 h Haltedauer / 24 h = 100 %
        (2, "0.5"),      # 12 h / 24 h = 50 %
        (4, "0.25"),     #  6 h / 24 h = 25 %
        (8, "0.125"),    #  3 h / 24 h = 12,5 %
    ],
)
def test_kreuzanteil_von_hand(rt: int, anteil: str) -> None:
    """Mittlere Haltedauer 24/RT Stunden, davon der Anteil an einem 24-h-Tag."""
    assert kreuzanteil(rt) == Decimal(anteil)


def test_kreuzanteil_weist_einen_umschlag_von_null_ab() -> None:
    with pytest.raises(KostentorError):
        kreuzanteil(0)


def test_swap_last_von_hand() -> None:
    """Swap-Last im Jahr = N x Kreuzanteil x Swap/10 000.

    Von Hand bei 4,0 bp je Nacht und 4 RT/Tag:
      N = 1 000 Round-Turns, Kreuzanteil 25 %  ->  250 gekreuzte Naechte
      250 x 4,0 bp = 1 000 bp = 10 % des Nominals.
    """
    assert swap_last_jahr(Decimal("-4.0"), rt_pro_tag=4) == Decimal("0.100000")


def test_swap_last_ist_vom_umschlag_unabhaengig() -> None:
    """Mehr Round-Turns heisst kuerzer halten heisst seltener kreuzen. Uebrig
    bleiben immer 250 Naechte -- die Handelstage des Jahres.

    Faende sich hier eine Abhaengigkeit, waere entweder der Kreuzanteil oder die
    Zahl der Round-Turns doppelt gezaehlt.
    """
    werte = {swap_last_jahr(Decimal("-4.0"), rt_pro_tag=rt) for rt in (1, 2, 4, 8)}
    assert len(werte) == 1
    # Gegenprobe von Hand: 250 Naechte x 4,0 bp / 10 000 = 0,10
    assert werte.pop() == Decimal("0.100000")


def test_swap_last_zaehlt_ein_guthaben_nicht_gegen_die_kosten() -> None:
    assert swap_last_jahr(Decimal("+4.0"), rt_pro_tag=4) == Decimal("0.100000")


# --- GEFUNDENER MANGEL 2 ---------------------------------------------------


def _swap_zeilen() -> list[tuple[str, str, str, Decimal, Decimal]]:
    """(Broker, Symbol, Seite, veroeffentlichter Satz, eingetragene bp) fuer alle
    Zeilen, deren Einheit den Satz als Prozent ausweist."""
    roh = json.loads(
        (REPO / "config" / "broker_costs.json").read_text(encoding="utf-8")
    )
    out: list[tuple[str, str, str, Decimal, Decimal]] = []
    for broker_key, broker in roh["brokers"].items():
        for symbol, eintrag in broker["instruments"].items():
            einheit = str(eintrag.get("swap_unit") or "")
            if "Prozent" not in einheit:
                continue
            for seite in ("long", "short"):
                satz = eintrag.get(f"swap_{seite}")
                bps = eintrag.get(f"swap_bps_night_{seite}")
                if satz is None or bps is None:
                    continue
                out.append(
                    (broker_key, symbol, seite, Decimal(str(satz)), Decimal(str(bps)))
                )
    return out


def test_prozentsatz_wird_mit_hundert_in_basispunkte_gerechnet() -> None:
    """Die dritte Hausfehlerklasse, gefunden: Prozent gegen Basispunkte.

    1 % = 100 Basispunkte. Ein Jahressatz wird zusaetzlich durch 360 geteilt
    (so steht die Formel in der Kostendatei selbst, Feld ``swap_unit``).

    Von Hand fuer ic_markets_eu/BTCUSD: -20 % p.a. / 360 = -0,05556 % je Nacht
    = -5,5556 bp je Nacht. Eingetragen sind -0,5556 bp -- Faktor 10 zu klein und
    damit in die schmeichelnde Richtung.

    Gegenprobe ohne die Formel: admirals_eu fuehrt fuer dasselbe BTCUSD
    -5,583 bp je Nacht. Zwei EU-Broker, die sich beim Finanzierungssatz um Faktor
    10 unterscheiden, gibt es nicht.

    BERICHTIGT am 2026-08-18. Die drei Werte in ``config/broker_costs.json`` stehen
    jetzt richtig; dieser Fall lief bis dahin unter ``xfail(strict=True)``, damit der
    Marker beim Berichtigen zwangslaeufig auffliegt. Er ist aufgeflogen und geloescht.
    Auf die Ampeln wirkte der Fehler nicht (M1 bleibt gruen, M2 unveraendert) -- Swaps
    gehen nicht in K ein. Sichtbar war er in der Haltekostenrechnung: die Swap-Last auf
    NVDA stand mit 0,4 % des Eigenkapitals im Jahr statt der richtigen 4,1 %.
    """
    abweichungen: list[str] = []
    for broker_key, symbol, seite, satz, bps in _swap_zeilen():
        roh = json.loads(
            (REPO / "config" / "broker_costs.json").read_text(encoding="utf-8")
        )
        einheit = str(
            roh["brokers"][broker_key]["instruments"][symbol]["swap_unit"] or ""
        )
        teiler = Decimal(360) if "p.a." in einheit else Decimal(1)
        soll = satz / teiler * Decimal(100)
        if _q(soll, "0.0001") != _q(bps, "0.0001"):
            abweichungen.append(
                f"{broker_key}/{symbol}/{seite}: eingetragen {bps} bp, "
                f"aus {satz} % gerechnet {_q(soll, '0.0001')} bp"
            )
    assert not abweichungen, "; ".join(abweichungen)


# ===========================================================================
# 7. Gegenrechnung: Stopabstand fuer eine Schwelle
# ===========================================================================


def test_stop_fuer_schwelle_von_hand() -> None:
    """Nach S aufgeloest: S = K / (2 x (x - 0,5)).

    Von Hand bei K = 12 bp:
      x = 56 %:  12 / (2 x 0,06) = 12 / 0,12 = 100 bp   (= 8,33 x K)
      x = 62 %:  12 / (2 x 0,12) = 12 / 0,24 =  50 bp   (= 4,17 x K)
    """
    assert stop_fuer_schwelle(Decimal("12"), M1_GRUEN_MAX) == Decimal("100")
    assert stop_fuer_schwelle(Decimal("12"), M1_GELB_MAX) == Decimal("50")


def test_stop_fuer_schwelle_ist_die_umkehrung_von_p_stern() -> None:
    """Die Probe aufs Exempel: der errechnete Stopabstand trifft die Schwelle
    genau. Waere in der Aufloesung ein Faktor 2 verrutscht, kaeme hier 53 oder
    62 % heraus statt 56."""
    for k in ("0.85", "1.15", "23.07"):
        s = stop_fuer_schwelle(Decimal(k), M1_GRUEN_MAX)
        assert _q(_p_stern(Decimal(k), s), "0.000001") == Decimal("0.560000")


def test_stop_fuer_schwelle_weist_unerreichbare_schwellen_ab() -> None:
    """Bei CRV 1:1 und positiven Kosten ist p* strikt ueber 50 %. Eine Schwelle
    von 50 % waere mit keinem Stopabstand zu halten -- das ist ein Fehler und
    keine sehr grosse Zahl."""
    with pytest.raises(KostentorError, match="50"):
        stop_fuer_schwelle(Decimal("12"), Decimal("0.5"))
    with pytest.raises(KostentorError):
        stop_fuer_schwelle(Decimal("12"), Decimal("0.4"))


# ===========================================================================
# 8. Die Aggregation, aus der M1 sein Urteil zieht
# ===========================================================================


def _lage(*paare: tuple[str, str, str]) -> list[Zeile]:
    """(Instrument, Broker, K) -> Zeilen mit ATR50 = 20 bp.

    Bei ATR50 = 20 bp gilt p* = 0,5 + K/40. Die 56-%-Schwelle liegt damit genau
    bei K = 2,4 bp: K = 2,0 -> 55 % gruen, K = 3,0 -> 57,5 % gelb.
    """
    return [
        zeile(instrument=inst, broker=broker, k_bps=Decimal(k))
        for inst, broker, k in paare
    ]


def test_bestes_p_je_instrument_nimmt_den_guenstigsten_broker() -> None:
    """Von Hand: EURUSD bei 2,0 bp -> 55 %, bei 6,0 bp -> 65 %. Bestes ist 55 %."""
    zeilen = _lage(("EURUSD", "teuer", "6.0"), ("EURUSD", "billig", "2.0"))
    assert bestes_p_je_instrument(zeilen) == {"EURUSD": Decimal("0.55")}
    # Und die Gegenprobe: die teure Zeile allein ergaebe 65 %.
    assert bestes_p_je_instrument(zeilen[:1]) == {"EURUSD": Decimal("0.65")}


def test_gruene_je_broker_zaehlt_nicht_ueber_broker_hinweg() -> None:
    """Der Kern der strengen Lesart -- vorher nicht pruefbar, weil er in der
    Druckkaskade steckte.

    Drei Instrumente, drei Broker, jeder Broker traegt genau EINES davon gruen.
    Nach der lockeren Lesart waeren das drei gruene Instrumente und damit M1
    gruen. Nach der strengen ist es ein Konto, das es nicht gibt: kein Anbieter
    kommt ueber eins.
    """
    zeilen = _lage(
        ("EURUSD", "a", "2.0"), ("EURUSD", "b", "6.0"), ("EURUSD", "c", "6.0"),
        ("XAUUSD", "a", "6.0"), ("XAUUSD", "b", "2.0"), ("XAUUSD", "c", "6.0"),
        ("DE40", "a", "6.0"), ("DE40", "b", "6.0"), ("DE40", "c", "2.0"),
    )
    lage = einteilung(bestes_p_je_instrument(zeilen))
    assert lage.gruen == ["EURUSD", "XAUUSD", "DE40"], "lockere Lesart: drei gruene"

    je_broker = gruene_je_broker(zeilen)
    assert {k: sorted(v) for k, v in je_broker.items()} == {
        "a": ["EURUSD"], "b": ["XAUUSD"], "c": ["DE40"]
    }
    assert max(len(v) for v in je_broker.values()) == 1, (
        "kein einzelner Broker traegt mehr als ein gruenes Instrument"
    )


def test_einteilung_haelt_die_reihenfolge_des_universums() -> None:
    """Die Listen folgen §4, nicht der Reihenfolge der Kostendatei -- sonst
    haengt die Ausgabe an der Schluesselordnung einer JSON-Datei."""
    lage = einteilung(
        bestes_p_je_instrument(
            _lage(("NVDA", "a", "2.0"), ("EURUSD", "a", "2.0"), ("DE40", "a", "2.0"))
        )
    )
    assert lage.gruen == ["EURUSD", "DE40", "NVDA"]


def test_einteilung_trennt_gruen_gelb_rot_an_den_schwellen() -> None:
    """Von Hand bei ATR50 = 20 bp: K = 2,0 -> 55 % gruen; K = 3,0 -> 57,5 % gelb;
    K = 6,0 -> 65 % rot."""
    lage = einteilung(
        bestes_p_je_instrument(
            _lage(("EURUSD", "a", "2.0"), ("GBPJPY", "a", "3.0"), ("DE40", "a", "6.0"))
        )
    )
    assert lage.gruen == ["EURUSD"]
    assert lage.gelb == ["GBPJPY"]
    assert lage.rot == ["DE40"]


def test_ein_nicht_bewertbares_instrument_faellt_in_keinen_topf() -> None:
    """BTCUSD hat keine rechenbare Zeile. Es darf weder gruen noch rot noch gelb
    sein -- und es muss in ``nicht_bewertbar`` auftauchen, weil ``m1_ampel``
    genau daran die Bewertbarkeitsschwelle misst."""
    lage = einteilung(bestes_p_je_instrument(_lage(("EURUSD", "a", "2.0"))))
    assert "BTCUSD" in lage.nicht_bewertbar
    assert "BTCUSD" not in lage.gruen + lage.gelb + lage.rot
    assert lage.bewertbar == ["EURUSD"]


# --- GEFUNDENER MANGEL 3 ---------------------------------------------------


def test_die_randbedingung_rechnet_auf_der_ersten_statt_der_guenstigsten_zeile() -> None:
    """MANGEL, festgeschrieben statt behoben: zwei Grundlagen, eine Ueberschrift.

    Tabelle 5 weist die Kostenuntergrenze zweimal aus. Die obere Tabelle nimmt je
    Instrument die GUENSTIGSTE Zeile, die Randbedingungstabelle darunter die
    ZUERST auftretende -- also schlicht den ersten Broker in
    ``config/broker_costs.json``. Im eingefrorenen Beleg stehen dadurch fuer NVDA
    41,88 bp und 230,72 bp unter derselben Bezeichnung.

    Nicht behoben, weil die Ausgabe eingefroren ist. Dieser Test haelt fest, dass
    die beiden Funktionen verschiedene Zeilen liefern koennen; verschwindet der
    Unterschied, ist der Mangel behoben und der Test zu loeschen.
    """
    zeilen = _lage(("NVDA", "teuer", "23.07"), ("NVDA", "billig", "4.19"))
    assert erste_zeile_je_instrument(zeilen)["NVDA"].k_bps == Decimal("23.07")
    assert guenstigste_zeile_je_instrument(zeilen)["NVDA"].k_bps == Decimal("4.19")


def test_guenstigste_zeile_haelt_bei_gleichstand_die_erste() -> None:
    zeilen = _lage(("DE40", "a", "1.10"), ("DE40", "b", "1.10"))
    assert guenstigste_zeile_je_instrument(zeilen)["DE40"].broker == "a"


# ===========================================================================
# 9. Gegen die echten Projektzahlen
# ===========================================================================
# Die Eingaben stammen aus config/broker_costs.json und config/atr_measurements.json
# (beide versioniert). Sie stehen hier als Zahlen im Test, nicht als Dateizugriff --
# damit dieser Test auch dann noch etwas aussagt, wenn jemand die Dateien anfasst.


def test_eurusd_bei_ic_markets_von_hand() -> None:
    """Die Zeile, die Abbruchbedingung 1 mittraegt.

    Eingaben (Kostendatei / Messdatei):
      Spread 0,06 Pips x 0,0001 = 0,000006 Preiseinheiten
      Preis (Median) 1,16393 USD
      Kommission 7 USD je Round-Turn, Kontrakt 100 000, Notierung USD
      ATR50 = 10,03626437124091 bp

    Von Hand:
      Spread     = 0,000006 / 1,16393 x 10 000 = 0,05155 bp
      Nominal    = 100 000 x 1,16393           = 116 393 USD
      Kommission = 7 / 116 393 x 10 000        = 0,60141 bp
      K          = 0,05155 + 0,60141 + 0,5     = 1,15296 bp
      p*         = 0,5 + 1,15296 / (2 x 10,03626) = 0,5 + 0,05744 = 0,55744
                 = 55,7 %  ->  GRUEN, aber nur 0,3 Punkte unter der 56-%-Linie.
    """
    z = _zeile(
        "EURUSD",
        "ic_markets_eu",
        kosten(
            spread_price=Decimal("0.06") * Decimal("0.0001"),
            commission_round_turn=Decimal("7"),
        ),
        messung(price_median=1.16393, atr_median_bps=10.03626437124091),
        {"EURUSD": Decimal("0.5")},
        {},
    )
    assert z.k_bps is not None and z.atr_median_bps is not None
    assert _q(z.spread_bps or Decimal(0), "0.00001") == Decimal("0.05155")
    assert _q(z.kommission_bps or Decimal(0), "0.00001") == Decimal("0.60141")
    assert _q(z.k_bps, "0.00001") == Decimal("1.15296")

    p = _p_stern(z.k_bps, z.atr_median_bps)
    assert _q(p * 100, "0.1") == Decimal("55.7")
    assert _ampel(p) == "GRUEN"


def test_gbpjpy_kommission_ohne_umrechnung_waere_um_faktor_159_zu_klein() -> None:
    """Der Fall aus ``09-EIGENE-FEHLER.md`` Nr. 2, hier am Kostentor selbst.

    Eingaben: Kommission 7 USD, Notierung JPY, USDJPY = 159,317 (gemessen),
    Kontrakt 100 000, Preis (Median) 211,3765 JPY.

    Von Hand:
      Kommission = 7 x 159,317                    = 1 115,219 JPY
      Nominal    = 100 000 x 211,3765             = 21 137 650 JPY
      Kommission = 1 115,219 / 21 137 650 x 10 000 = 0,5276 bp

    Ohne Umrechnung: 7 / 21 137 650 x 10 000 = 0,0033 bp. Eine Kommission von
    0,003 bp gibt es bei keinem ECN-Broker -- das ist die Groesse, an der der
    Fehler damals auffiel.
    """
    z = _zeile(
        "GBPJPY",
        "ic_markets_eu",
        kosten(
            quote_currency="JPY",
            spread_price=Decimal("0.65") * Decimal("0.01"),
            commission_round_turn=Decimal("7"),
        ),
        messung(price_median=211.3765, atr_median_bps=11.72445565625625),
        {"GBPJPY": Decimal("1.0")},
        {"USDJPY": 159.317},
    )
    assert z.kommission_bps is not None
    assert _q(z.kommission_bps, "0.0001") == Decimal("0.5276")
    assert _q(z.kommission_bps, "0.0001") != Decimal("0.0033")
    # K = 0,3075 Spread + 0,5276 Kommission + 1,0 Slippage = 1,8351 bp
    assert z.k_bps is not None and _q(z.k_bps, "0.0001") == Decimal("1.8351")

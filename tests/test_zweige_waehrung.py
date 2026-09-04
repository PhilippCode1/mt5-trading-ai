"""Zweigdeckung ``risk/waehrung.py`` (A15): die fuenf Zweige, die die Suite nicht lief.

Gemessen vor diesen Tests (Beleg ``06-zweigdeckung-waehrung-rot.txt``): 13 von 18
Zweigen, 72,2 %. ``tests/eichfall_d3.py`` faehrt die Hauptpfade des Moduls; was fehlte,
waren die **Ablehnungen** und der Weg ohne Kurs -- also genau das, wofuer das Modul
gebaut wurde (D3: eine Zahl ohne Waehrung laesst sich mit jeder anderen Zahl
multiplizieren):

* 42 -> 43   ``__post_init__``: leere oder blanke Waehrung -> ``WaehrungsFehler``
* 46 -> Ausgang ``_gleich``: gleiche Waehrung -> kein Fehler (und damit ``__add__``,
  ``__sub__`` und ``mal``, deren Zeilen 54, 57, 58 und 61 nie liefen)
* 66 -> 67   ``umgerechnet``: Ziel- gleich Ausgangswaehrung -> ``self``, ohne Kurs
* 93 -> 95   ``kurs_aus_ticks``: Mittelkurs des direkten Paars <= 0 -> Kehrwertpfad
* 98 -> 100  ``kurs_aus_ticks``: auch der Mittelkurs des Gegenpaars <= 0 -> ``None``

Die zwei Zweige 91 -> 95 und 96 -> 100 (gar kein Tick) liefen bereits in
``eichfall_d3``; sie stehen hier mit, damit diese Datei die Tickquelle allein deckt --
gemessen ohne sie: 16 von 18 Zweigen aus dieser Datei allein, mit ihnen 18 von 18.

Jede Zusicherung, die einen Zweig traegt, unterscheidet ihn: sie prueft, was der Zweig
verhindert, nicht dass er durchlaufen wird. (Daneben stehen Zusicherungen, die einen
Fall lesbar machen, ohne einen Mutanten zu toeten -- die Gegenlese hat sieben davon
benannt; sie bleiben stehen, behaupten hier aber nichts.) Faellt der Zweig weg oder kippt der Vergleich, entsteht ein
anderes Ergebnis (ein Betrag ohne Waehrung, ein Kurs 0, ein negativer Kurs, eine
Division durch 0, ein doppelt umgerechneter Betrag) -- und der Test wird rot. Belegt
durch acht Gegenproben in einer Kopie (Beleg ``06-zweigdeckung-waehrung-rot.txt``).
Kein Datei- oder Netzzugriff; die Tickquelle ist ein Aufrufprotokoll im Speicher (A10).
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest
from mt5_trading_ai.risk.waehrung import Betrag, WaehrungsFehler, kurs_aus_ticks

# --- Bezugspunkt: ohne ihn bewiese ein roter Fall unten nur ein kaputtes Geruest ----


def test_bezugspunkt_ein_betrag_mit_waehrung_entsteht() -> None:
    b = Betrag(Decimal("2.50"), "USD")
    assert (b.wert, b.waehrung) == (Decimal("2.50"), "USD")


# --- Zweig 42 -> 43: ein Betrag ohne Waehrung entsteht nicht -----------------------


@pytest.mark.parametrize("ohne", ["", " ", "   ", "\t", "\n", " \t\n "])
def test_betrag_ohne_waehrung_entsteht_nicht(ohne: str) -> None:
    """D3 an seiner Wurzel: eine Zahl ohne Waehrung darf es gar nicht geben.

    Ohne diesen Zweig entstuende ``Betrag(1000, "")`` -- ein Wert, den ``_gleich``
    spaeter zwar noch anhaelt, dessen Herkunft dann aber niemand mehr benennen kann.
    """
    with pytest.raises(WaehrungsFehler, match="Betrag ohne Waehrung"):
        Betrag(Decimal("1000"), ohne)


def test_eine_waehrung_die_kein_text_ist_faellt_als_waehrungsfehler() -> None:
    """Zeile 42, erste Haelfte: ohne ``not self.waehrung`` waere ``None`` ein
    ``AttributeError`` -- ein Fehlertyp, den der Orderpfad nicht als
    ``WaehrungsFehler`` faengt. Gegenlese T6 (S2): die sechs blanken Zeichenketten
    unterscheiden diese Haelfte nicht."""
    for keine in (None, 0, ()):
        with pytest.raises(WaehrungsFehler, match="Betrag ohne Waehrung"):
            Betrag(Decimal("1"), keine)  # type: ignore[arg-type]


def test_der_fehler_nennt_seinen_grund_und_ist_ein_valueerror() -> None:
    """Der Zweig wirft nicht irgendetwas: Text und Typ sind der Beleg."""
    with pytest.raises(WaehrungsFehler) as exc:
        Betrag(Decimal("1000"), "")
    assert str(exc.value) == "Betrag ohne Waehrung"
    assert isinstance(exc.value, ValueError)


def test_die_waehrung_laesst_sich_auch_nachtraeglich_nicht_entfernen() -> None:
    """Der Zweig sitzt am Typ, nicht an einer Aufrufstelle: ``replace`` faellt auch."""
    b = Betrag(Decimal("1000"), "USD")
    with pytest.raises(WaehrungsFehler, match="Betrag ohne Waehrung"):
        dataclasses.replace(b, waehrung="")
    with pytest.raises(dataclasses.FrozenInstanceError):
        b.waehrung = ""
    assert b.waehrung == "USD"


def test_eine_nicht_getrimmte_waehrung_ist_eine_andere_waehrung() -> None:
    """Der Zweig lehnt nur Blankes ab; ``" USD "`` bleibt stehen -- und sperrt dann.

    Das ist die geschlossene Richtung: nicht getrimmt heisst fremd, fremd heisst
    ``WaehrungsFehler``. Ein Trimmen im Konstruktor waere die offene Richtung.
    """
    getrimmt = Betrag(Decimal("1"), " USD ")
    assert getrimmt.waehrung == " USD "
    assert getrimmt != Betrag(Decimal("1"), "USD")
    with pytest.raises(WaehrungsFehler):
        getrimmt + Betrag(Decimal("1"), "USD")


# --- Zweig 46 -> Ausgang: gleiche Waehrung rechnet, fremde nicht -------------------


def test_gleiche_waehrung_addiert_und_subtrahiert_ohne_kurs() -> None:
    """Zweig 46 -> Ausgang samt Zeilen 54, 57, 58: der Fall, in dem gerechnet wird.

    Kippt der Vergleich in ``_gleich`` (``!=`` -> ``==``), wirft schon die erste
    Zusicherung; vertauscht ``__add__``/``__sub__`` das Vorzeichen, treffen die Werte
    nicht mehr.
    """
    a = Betrag(Decimal("2.50"), "USD")
    b = Betrag(Decimal("0.25"), "USD")
    assert a + b == Betrag(Decimal("2.75"), "USD")
    assert a - b == Betrag(Decimal("2.25"), "USD")
    assert b - a == Betrag(Decimal("-2.25"), "USD")
    assert (a + b).waehrung == "USD"
    assert (a - b).waehrung == "USD"


def test_fremde_waehrungen_lassen_sich_weder_addieren_noch_subtrahieren() -> None:
    """Beide Operatoren gehen durch ``_gleich``; der Text nennt beide Waehrungen."""
    usd = Betrag(Decimal("100"), "USD")
    eur = Betrag(Decimal("100"), "EUR")
    with pytest.raises(WaehrungsFehler) as plus:
        usd + eur
    assert str(plus.value) == "USD und EUR lassen sich nicht ohne Kurs verrechnen"
    with pytest.raises(WaehrungsFehler) as minus:
        eur - usd
    assert str(minus.value) == "EUR und USD lassen sich nicht ohne Kurs verrechnen"


def test_mal_skaliert_den_wert_und_behaelt_die_waehrung() -> None:
    """Zeile 61: ``mal`` nimmt einen dimensionslosen Faktor, keine zweite Waehrung."""
    b = Betrag(Decimal("3"), "JPY")
    assert b.mal(Decimal("0.5")) == Betrag(Decimal("1.5"), "JPY")
    assert b.mal(Decimal("-2")) == Betrag(Decimal("-6"), "JPY")
    assert b.mal(Decimal("0")) == Betrag(Decimal("0"), "JPY")
    assert b == Betrag(Decimal("3"), "JPY")  # eingefroren: das Original bleibt


def test_zwei_betraege_lassen_sich_nicht_multiplizieren() -> None:
    """Der Satz aus D3 als Zusicherung: Betrag mal Betrag gibt es nicht."""
    b = Betrag(Decimal("3"), "USD")
    with pytest.raises(TypeError):
        b.mal(Betrag(Decimal("2"), "EUR"))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        b * Betrag(Decimal("2"), "EUR")
    with pytest.raises(TypeError):
        b * Decimal("2")  # auch der blanke Faktor braucht ``mal``


# --- Zweig 66 -> 67: gleiche Waehrung braucht keinen Kurs --------------------------


def test_gleiche_waehrung_gibt_denselben_betrag_zurueck_und_ignoriert_den_kurs() -> (
    None
):
    """Zweig 66 -> 67 und Zeile 67 -- die Reihenfolge der beiden Pruefungen ist der Sinn.

    Faellt der Zweig weg, sperrt ``None`` (fx_unverifiable) und ``Decimal("2")``
    verdoppelt den Betrag; steht die Kurspruefung davor, sperrt ``Decimal("0")``.
    Jeder dieser drei Faelle faellt hier auf.
    """
    b = Betrag(Decimal("7.25"), "USD")
    assert b.umgerechnet("USD", None) is b
    assert b.umgerechnet("USD", Decimal("2")) is b
    assert b.umgerechnet("USD", Decimal("0")) is b
    assert b.umgerechnet("USD", Decimal("-1.27")) is b
    assert b.wert == Decimal("7.25")


def test_mit_kurs_wechselt_der_betrag_die_waehrung() -> None:
    """Die Gegenrichtung von 66 -> 67: der Ergebnisbetrag traegt ``nach``, nicht ``self``."""
    umgerechnet = Betrag(Decimal("2"), "GBP").umgerechnet("USD", Decimal("1.27"))
    assert umgerechnet == Betrag(Decimal("2.54"), "USD")
    assert umgerechnet.waehrung == "USD"


def test_ohne_kurs_sperrt_die_umrechnung_und_nennt_den_grund() -> None:
    """Fehlender Wert sperrt (Regel 7): der Text traegt die Kennung des Orderpfads."""
    with pytest.raises(WaehrungsFehler) as exc:
        Betrag(Decimal("2"), "GBP").umgerechnet("USD", None)
    text = str(exc.value)
    assert "fx_unverifiable" in text
    assert "kein Kurs GBP->USD" in text
    assert "Betrag 2 GBP" in text


@pytest.mark.parametrize("kurs", ["0", "-0.0001", "-1.27"])
def test_ein_kurs_von_null_oder_darunter_ist_kein_kurs(kurs: str) -> None:
    """Ohne diese Pruefung entstuende ein Betrag von 0 oder ein negativer Betrag."""
    with pytest.raises(WaehrungsFehler, match="fx_unverifiable"):
        Betrag(Decimal("1000"), "GBP").umgerechnet("USD", Decimal(kurs))


# --- Zweige 93 -> 95 und 98 -> 100: ein Mittelkurs <= 0 ist kein Kurs --------------


class _Tick:
    """Was ``tick(symbol)`` liefert: ein Objekt mit ``bid`` und ``ask``."""

    def __init__(self, bid: float | str, ask: float | str) -> None:
        self.bid = bid
        self.ask = ask


class _Ticks:
    """Tickquelle mit Protokoll: welche Symbole wurden gefragt, in welcher Reihenfolge."""

    def __init__(self, **symbole: _Tick) -> None:
        self._symbole = symbole
        self.gefragt: list[str] = []

    def __call__(self, symbol: str) -> _Tick | None:
        self.gefragt.append(symbol)
        return self._symbole.get(symbol)


def test_gleiche_waehrung_fragt_kein_terminal() -> None:
    ticks = _Ticks()
    assert kurs_aus_ticks("USD", "USD", ticks) == Decimal("1")
    assert ticks.gefragt == []


def test_ein_tick_als_gleitkommazahl_wird_ueber_str_genau_gelesen() -> None:
    """Zeile 92 und 97: MetaTrader liefert ``bid``/``ask`` als ``float``. Ohne das
    ``str()`` traegt ``Decimal(1.2699)`` das Gleitkommarauschen mit, und der
    Mittelkurs lautet 1.270000000000000017763568394 statt 1.2700. Gegenlese T6 (S2):
    die Datei fuetterte nur Zeichenketten, an denen sich beides nicht unterscheidet."""
    direkt = _Ticks(GBPUSD=_Tick(1.2699, 1.2701))
    assert kurs_aus_ticks("GBP", "USD", direkt) == Decimal("1.2700")

    # Derselbe Fall ueber den Kehrwert (Zeile 97): 1 / 0.79, nicht 1 / 0.790000...36.
    kehr = _Ticks(EURCHF=_Tick(0.78, 0.80))
    assert kurs_aus_ticks("CHF", "EUR", kehr) == Decimal("1") / Decimal("0.79")


def test_eine_nicht_getrimmte_waehrung_fragt_das_terminal_statt_eins_zu_liefern() -> (
    None
):
    """Zeile 88 ``von == nach``: getrimmt verglichen waere " USD" gleich "USD" und der
    Kurs 1, ohne dass ein Tick gelesen wird. Dieselbe Regel wie fuer ``Betrag``:
    nicht getrimmt heisst fremd. Gegenlese T6 (S2)."""
    ticks = _Ticks()
    assert kurs_aus_ticks(" USD", "USD", ticks) is None
    assert ticks.gefragt == [" USDUSD", "USD USD"], ticks.gefragt


def test_direkter_tick_wird_genommen_und_das_gegenpaar_gar_nicht_erst_gefragt() -> None:
    ticks = _Ticks(GBPUSD=_Tick("1.2699", "1.2701"))
    assert kurs_aus_ticks("GBP", "USD", ticks) == Decimal("1.2700")
    assert ticks.gefragt == ["GBPUSD"]


def test_leerer_direkter_tick_faellt_auf_den_kehrwert_des_gegenpaars_zurueck() -> None:
    """Zweig 93 -> 95: ein Tick mit bid=ask=0 (Symbol ohne Quote) ist kein Kurs.

    Ohne den Zweig kaeme ``Decimal("0")`` heraus -- ein Kurs, mit dem der Orderpfad
    weiterrechnet, statt zu sperren. Hier kommt der Kehrwert 1/0,79 heraus.
    """
    ticks = _Ticks(GBPUSD=_Tick(0.0, 0.0), USDGBP=_Tick("0.78", "0.80"))
    kurs = kurs_aus_ticks("GBP", "USD", ticks)
    assert kurs == Decimal("1") / Decimal("0.79")
    assert kurs is not None and kurs > 0
    assert ticks.gefragt == ["GBPUSD", "USDGBP"]


def test_beide_ticks_leer_ergeben_keinen_kurs_und_der_sperrt() -> None:
    """Zweige 93 -> 95 und 98 -> 100: kein Mittelkurs > 0 -> ``None`` -> Sperre.

    Ohne Zweig 98 -> 100 rechnete die Zeile darunter ``Decimal("1") / 0`` -- statt
    ``None`` gaebe es eine Division durch Null, und statt der Sperre einen Absturz.
    """
    ticks = _Ticks(GBPUSD=_Tick(0.0, 0.0), USDGBP=_Tick(0.0, 0.0))
    kurs = kurs_aus_ticks("GBP", "USD", ticks)
    assert kurs is None
    assert ticks.gefragt == ["GBPUSD", "USDGBP"]
    with pytest.raises(WaehrungsFehler, match="fx_unverifiable"):
        Betrag(Decimal("1000"), "GBP").umgerechnet("USD", kurs)


def test_kein_tick_in_beiden_richtungen_ergibt_keinen_kurs() -> None:
    """Zweige 91 -> 95 und 96 -> 100: ein unbekanntes Symbol liefert ``None``.

    ``eichfall_d3`` faehrt diesen Fall ebenfalls; hier steht er, damit diese Datei die
    Tickquelle allein abdeckt -- und weil die Zusicherung ueber ``gefragt`` zeigt, dass
    beide Richtungen gefragt wurden, bevor gesperrt wird.
    """
    ticks = _Ticks()
    assert kurs_aus_ticks("GBP", "USD", ticks) is None
    assert ticks.gefragt == ["GBPUSD", "USDGBP"]


def test_ein_mittelkurs_unter_null_ist_in_beiden_richtungen_kein_kurs() -> None:
    """Dieselben Zweige mit negativem statt leerem Mittelkurs.

    Ohne die Zweige lieferte die Funktion -0,5 bzw. -4 -- ein negativer Kurs, der einen
    Verlust in einen Gewinn verwandelt.
    """
    ticks = _Ticks(GBPUSD=_Tick("-2.0", "1.0"), USDGBP=_Tick("-1.0", "0.5"))
    assert kurs_aus_ticks("GBP", "USD", ticks) is None
    assert ticks.gefragt == ["GBPUSD", "USDGBP"]

#!/usr/bin/env python3
"""Ist das vorregistrierte Sechs-Bedingungen-Tor auf dieser Reihe ueberhaupt erfuellbar?

DIE FRAGE
---------
Stufe 3 hat drei Hypothesen gegen das Tor gefahren, alle drei fielen durch. Die
Konfidenzintervalle schlossen dabei in **beide** Richtungen die Null ein -- die Daten
haben die Frage nicht aufgeloest. Die hoechste erreichte Trade-Zahl war 123 gegen eine
vorregistrierte Mindestzahl von 2.000.

Daraus folgt eine Frage, die **vor** jedem weiteren Versuch steht und die kein
Strategielauf beantwortet: verlangt Bedingung 3 eine Handelsfrequenz, bei der die
Sharpe-Bedingungen nach Kosten nicht mehr erreichbar sind? Wenn ja, ist das Tor auf
dieser Reihe unerfuellbar, und die drei Fehlschlaege belegen nicht das Fehlen eines
Vorteils, sondern die Unerfuellbarkeit des Maszstabs.

Nebenbei faellt dabei eine zweite Frage an, die keiner der bisherigen Berichte
gestellt hat: Bedingung 1 (Sharpe) und Bedingung 2 (Deflation) stehen auf **derselben**
Groesze, der Sharpe je Trade. Welche von beiden bindet, sagt keine der Schwellen von
sich aus. Das Werkzeug rechnet es aus.

WAS DIESES WERKZEUG NICHT IST
-----------------------------
Es faehrt **keinen** Backtest, prueft **keine** Hypothese, erzeugt **kein** Edge-Urteil
und verbraucht **keinen** Versuch. Es aendert **keine** Schwelle -- es liest sie und
rechnet aus, was sie verlangt. Es sucht keine bessere Parametrierung und erweitert den
Suchraum nicht; das verbietet der Auftrag nach dem Ergebnistor ausdruecklich.

DIE RECHNUNG
------------
Alle Eingangszahlen werden **gelesen**, keine wiederholt:

* ``min_trades`` und ``min_oos_sharpe``  <- ``backtest/edge.py::EdgeThresholds``
* ``OOS_FRACTION``                       <- ``tools/edge_test.py``
* die Bars                               <- ``load_verified_csv``, mit Pruefsumme
* die Kosten                             <- ``costs/model.py::order_roundturn_cost``,
  dieselbe Funktion, die der Backtest je Trade aufruft (kein zweites Kostenmodell)

Daraus::

    H     = OoS-Bars / min_trades              mittlere Haltedauer in Bars
    S_a   = min_oos_sharpe                     annualisierte Trade-Sharpe (Bedingung 1)
    S_1   = S_a / sqrt(Trades je Jahr)         Sharpe je Trade fuer Bedingung 1
    S_2   = Umkehrung der Deflation            Sharpe je Trade fuer Bedingung 2
    S_t   = max(S_1, S_2)                      die BINDENDE der beiden
    K     = Round-Turn-Kosten in bp            gemessen am Median-Kurs der Reihe
    m     = Mittel |Bewegung ueber H Bars|     gemessen, in bp
    s     = Streuung der VORZEICHENBEHAFTETEN  gemessen, in bp -- nicht die
            Bewegung ueber H Bars              Streuung der Betraege
    E     = S_t * s                            noetiger Netto-Erwartungswert je Trade
    f     = (E + K) / m                        ANTEIL der Bewegung, den eine Strategie
                                               im Mittel netto einfangen muss

``f`` ist die Antwort. ``f >= 1`` heiszt: das Tor verlangt mehr als die volle mittlere
Bewegung und ist unerfuellbar. Je naeher ``f`` an 1, desto weniger sagt ein Fehlschlag
ueber den Vorteil aus.

GEMESSEN WIRD AUF DEM IN-SAMPLE-BLOCK
-------------------------------------
Der Out-of-Sample-Block ist nach der Vorregistrierung „genau einmal angefasst".
Bewegung und Streuung werden deshalb auf den ersten ``1 - OOS_FRACTION`` gerechnet.
Der OoS-Block wird nur als **Gegenprobe auf Stationaritaet** ausgewiesen und geht in
keine Entscheidung ein.

Aufruf::

    python tools/torerfuellbarkeit.py --csv daten/reihen/EURUSD_H1.csv
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.edge import EdgeThresholds  # noqa: E402
from mt5_trading_ai.costs.model import (  # noqa: E402
    load_cost_fees,
    order_roundturn_cost,
)
from mt5_trading_ai.data.loader import FxSession, load_verified_csv  # noqa: E402
from mt5_trading_ai.gates.criteria import deflated_sharpe_ratio  # noqa: E402
from mt5_trading_ai.risk.stop_budget import breakeven_hit_rate  # noqa: E402
from mt5_trading_ai.venue.protocol import OrderSide  # noqa: E402

from tools.edge_test import OOS_FRACTION  # noqa: E402

#: Ein Jahr in Stunden. Kalendarisch, nicht in Handelsstunden -- die Spanne wird aus den
#: Zeitstempeln des ersten und letzten Bars gerechnet, nicht aus der Bar-Zahl, damit
#: Wochenendluecken nicht als Handelszeit zaehlen.
STUNDEN_JE_JAHR = 365.25 * 24


class TorFehler(RuntimeError):
    """Eine Eingangsgroesse fehlt oder ist unbrauchbar. Nie durch Ersatz gefuellt."""


def bewegung_bp(closes: list[float], horizont: int) -> tuple[float, float, int]:
    """Mittleres |Bewegungsmasz| und Streuung der VORZEICHENBEHAFTETEN Bewegung, in bp.

    Die beiden Groeszen beantworten zwei verschiedene Fragen und duerfen nicht
    verwechselt werden -- eine erste Fassung dieses Werkzeugs hat genau das getan:

    * ``m`` = Mittel von ``|Bewegung|``. Das ist, was ein Trade an Substanz vorfindet.
      Es steht im Nenner von ``f``.
    * ``s`` = Streuung der **vorzeichenbehafteten** Bewegung. Das ist, woran sich eine
      Sharpe misst: die Auszahlung eines Trades ist ``Richtung x Bewegung - K`` und
      streut mit der vorzeichenbehafteten Groesze, nicht mit ihrem Betrag. Die Streuung
      der Betraege ist eine dritte, hier unbrauchbare Zahl.

    Gerechnet wird auf ueberlappenden Fenstern. Das ist Absicht: die Frage lautet, wie
    weit sich der Kurs in dieser Zeitspanne typischerweise bewegt, und dafuer ist jede
    Startposition ein gueltiger Beobachtungspunkt. Fuer einen Signifikanztest waeren
    ueberlappende Fenster falsch -- hier wird keiner gerechnet.
    """
    if horizont < 1:
        raise TorFehler(
            f"Horizont {horizont} < 1 Bar -- die Mindest-Trade-Zahl verlangt mehr "
            "Trades als der Block Bars hat. Damit ist Bedingung 3 auf dieser Reihe "
            "arithmetisch unerfuellbar."
        )
    if len(closes) <= horizont:
        raise TorFehler(f"Block hat {len(closes)} Bars, Horizont ist {horizont}.")
    vorzeichenbehaftet = [
        (closes[i + horizont] - closes[i]) / closes[i] * 10_000.0
        for i in range(len(closes) - horizont)
    ]
    betraege = [abs(x) for x in vorzeichenbehaftet]
    return (
        statistics.fmean(betraege),
        statistics.pstdev(vorzeichenbehaftet),
        len(vorzeichenbehaftet),
    )


def roundturn_bp(
    *,
    symbol: str,
    kurs: float,
    spread_pips: Decimal,
    pip_size: Decimal,
    contract_size: Decimal,
    haltenaechte: int,
) -> tuple[float, dict[str, float]]:
    """Round-Turn-Kosten in bp des Nominals -- ueber die Funktion des Backtests.

    Kein zweites Kostenmodell: gerechnet wird mit ``order_roundturn_cost``, derselben
    Funktion, die ``run_backtest`` je Trade aufruft. Der Kurs ist der Median der Reihe,
    damit die Zahl nicht am Anfangs- oder Endkurs haengt.
    """
    fees = load_cost_fees(symbol)
    halb = spread_pips * pip_size / Decimal("2")
    mitte = Decimal(str(kurs))
    volumen = Decimal("1")
    aufschluesselung = order_roundturn_cost(
        fees=fees,
        contract_size=contract_size,
        pip_size=pip_size,
        bid=mitte - halb,
        ask=mitte + halb,
        side=OrderSide.BUY,
        volume=volumen,
        quote_currency="USD",
        holding_nights=haltenaechte,
    )
    nominal = float(mitte * contract_size * volumen)
    if nominal <= 0:
        raise TorFehler("Nominal <= 0 -- Kurs oder Kontraktgroesse unbrauchbar.")
    # ``CostBreakdown`` fuehrt positiv = Kosten; ``financing`` kann negativ sein
    # (Gutschrift). ``total`` ist die Summe der vier -- sie wird gelesen, nicht hier
    # noch einmal addiert, sonst gaebe es zwei Wahrheiten fuer dieselbe Zahl.
    teile = {
        "spread": float(aufschluesselung.spread),
        "kommission": float(aufschluesselung.commission),
        "slippage": float(aufschluesselung.slippage),
        "finanzierung": float(aufschluesselung.financing),
    }
    return float(aufschluesselung.total) / nominal * 10_000.0, {
        k: v / nominal * 10_000.0 for k, v in teile.items()
    }


def noetige_sharpe_fuer_dsr(*, ziel: float, beobachtungen: int, versuche: int) -> float:
    """Die Sharpe je Trade, ab der die Deflation ``ziel`` ueberschreitet.

    Umgekehrte Richtung derselben Funktion, die das Tor benutzt:
    ``deflated_sharpe_ratio`` bildet Sharpe -> DSR ab, hier wird die Umkehrung
    gesucht. Gerechnet wird per
    Intervallhalbierung statt geschlossen, damit **dieselbe** Funktion befragt wird, die
    auch urteilt -- eine eigene Formel waere eine zweite Wahrheit und koennte an der
    entscheidenden Stelle abweichen, ohne dass es auffiele.

    Die Abbildung ist in der Sharpe streng monoton wachsend; die Halbierung findet die
    Grenze deshalb eindeutig. Faellt selbst die obere Schranke nicht ueber das Ziel, ist
    das ein Befund und kein Ergebnis.
    """
    unten, oben = 0.0, 5.0
    if deflated_sharpe_ratio(
        observed_sharpe=oben, observations=beobachtungen, trials=versuche
    ) <= ziel:
        raise TorFehler(
            f"Selbst eine Sharpe je Trade von {oben} erreicht die Deflationsschwelle "
            f"{ziel} bei {beobachtungen} Beobachtungen und {versuche} Versuchen nicht. "
            "Bedingung 2 ist unter dieser Lage unerfuellbar."
        )
    for _ in range(200):
        mitte = (unten + oben) / 2
        if deflated_sharpe_ratio(
            observed_sharpe=mitte, observations=beobachtungen, trials=versuche
        ) > ziel:
            oben = mitte
        else:
            unten = mitte
    return oben


def spanne_jahre(erster: datetime, letzter: datetime) -> float:
    """Kalenderspanne eines Blocks in Jahren, aus den Zeitstempeln der Randbars."""
    stunden = (letzter - erster).total_seconds() / 3600.0
    if stunden <= 0:
        raise TorFehler("Blockspanne <= 0 -- Zeitstempel unbrauchbar.")
    return stunden / STUNDEN_JE_JAHR


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="Erfuellbarkeit des Sechs-Bedingungen-Tors"
    )
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--instrument", default="EURUSD")
    ap.add_argument("--timeframe", default="H1")
    ap.add_argument(
        "--kampagne", type=int, default=60,
        help="Zahl der vorregistrierten Kampagnenversuche fuer die Deflation "
             "(ABBRUCH.md §2; dieselbe Zahl, die edge_test als "
             "--campaign-trials bekommt)",
    )
    args = ap.parse_args()

    bars, pruefsumme = load_verified_csv(
        args.csv,
        instrument=args.instrument,
        timeframe=args.timeframe,
        session_predicate=FxSession(),
    )
    schwellen = EdgeThresholds()
    teiler = int(len(bars) * (1.0 - OOS_FRACTION))
    in_sample, oos = bars[:teiler], bars[teiler:]

    print("=" * 78)
    print("ERFUELLBARKEIT DES VORREGISTRIERTEN TORS -- kein Backtest, kein Versuch")
    print("=" * 78)
    print(
        f"Reihe        : {args.instrument} {args.timeframe}, {len(bars)} Bars "
        f"{bars[0].ts.date()}..{bars[-1].ts.date()}"
    )
    print(f"Pruefsumme   : {pruefsumme}")
    print(f"In-Sample    : {len(in_sample)} Bars -- hier wird gemessen")
    print(f"Out-of-Sample: {len(oos)} Bars ({OOS_FRACTION:.0%}) -- nur Gegenprobe")
    print()

    oos_jahre = spanne_jahre(oos[0].ts, oos[-1].ts)
    horizont = len(oos) // schwellen.min_trades
    trades_je_jahr = schwellen.min_trades / oos_jahre
    faktor = trades_je_jahr**0.5
    sharpe_je_trade = schwellen.min_oos_sharpe / faktor

    print("-" * 78)
    print("1) WAS BEDINGUNG 3 VERLANGT (gelesen aus EdgeThresholds)")
    print("-" * 78)
    print(f"Mindest-Trades im OoS-Block  : {schwellen.min_trades}")
    print(f"OoS-Bars                     : {len(oos)}")
    print(
        f"-> mittlere Haltedauer       : {len(oos) / schwellen.min_trades:.2f} Bars "
        f"= {len(oos) / schwellen.min_trades:.2f} Handelsstunden"
    )
    print(f"OoS-Kalenderspanne           : {oos_jahre:.3f} Jahre")
    print(f"-> Trades je Jahr            : {trades_je_jahr:.0f}")
    print()
    print("-" * 78)
    print("2) WAS BEDINGUNG 1 DARAUS MACHT")
    print("-" * 78)
    print(f"Geforderte Trade-Sharpe (annualisiert)  : {schwellen.min_oos_sharpe}")
    print(f"Annualisierungsfaktor sqrt(Trades/Jahr) : {faktor:.2f}")
    print(f"-> noetige Sharpe JE TRADE              : {sharpe_je_trade:.5f}")
    print()

    # Bedingung 2 steht auf derselben Groesze wie Bedingung 1 -- der Sharpe je Trade --,
    # nur ueber die Deflation. Welche der beiden bindet, entscheidet keine Meinung,
    # sondern die Rechnung. Sie wird hier gefahren, weil eine Doku, die „Sharpe >= 1,0"
    # als Anspruch nennt, den tatsaechlichen Anspruch verschweigt, falls Bedingung 2
    # mehr verlangt.
    dsr_je_trade = noetige_sharpe_fuer_dsr(
        ziel=schwellen.min_deflated_sharpe,
        beobachtungen=schwellen.min_trades,
        versuche=args.kampagne,
    )
    bindend, sharpe_bindend = (
        ("Bedingung 2 (Deflation)", dsr_je_trade)
        if dsr_je_trade > sharpe_je_trade
        else ("Bedingung 1 (Sharpe)", sharpe_je_trade)
    )
    print("-" * 78)
    print("2b) WAS BEDINGUNG 2 VERLANGT -- AN DERSELBEN GROESZE")
    print("-" * 78)
    ziel_dsr = schwellen.min_deflated_sharpe
    print(f"Geforderte Deflated Sharpe              : > {ziel_dsr}")
    print(f"Beobachtungen (= min_trades)            : {schwellen.min_trades}")
    print(f"Versuche der Kampagne                   : {args.kampagne}")
    print(f"-> noetige Sharpe JE TRADE              : {dsr_je_trade:.5f}")
    print(
        f"-> dasselbe annualisiert                : "
        f"{dsr_je_trade * faktor:.3f}  (Bedingung 1 nennt "
        f"{schwellen.min_oos_sharpe})"
    )
    print()
    print(f"==> BINDEND IST: {bindend}, Sharpe je Trade {sharpe_bindend:.5f}")
    if dsr_je_trade > sharpe_je_trade:
        print(
            f"    Bedingung 2 ist um den Faktor "
            f"{dsr_je_trade / sharpe_je_trade:.2f} strenger als Bedingung 1. Die in der"
        )
        print(
            f"    Doku genannte Schwelle {schwellen.min_oos_sharpe} ist damit nicht der"
            " wirksame Anspruch."
        )
    print()
    # Ab hier rechnet alles gegen die BINDENDE Bedingung. Gegen die schwaechere zu
    # rechnen waere die schmeichelnde Richtung.
    sharpe_je_trade = sharpe_bindend

    kurse = [float(b.close) for b in in_sample]
    median_kurs = statistics.median(kurse)
    # Bei einer Haltedauer unter einem Tag faellt in der Regel keine Nacht an.
    naechte = int(len(oos) / schwellen.min_trades) // 24
    k_bp, teile = roundturn_bp(
        symbol=args.instrument,
        kurs=median_kurs,
        spread_pips=Decimal("0.1"),
        pip_size=Decimal("0.0001"),
        contract_size=Decimal("100000"),
        haltenaechte=naechte,
    )
    print("-" * 78)
    print("3) WAS EIN TRADE KOSTET (order_roundturn_cost -- wie im Backtest)")
    print("-" * 78)
    print(f"Median-Kurs der Reihe : {median_kurs:.5f}")
    print(f"Gehaltene Naechte     : {naechte} (Haltedauer unter 24 h)")
    for name, wert in teile.items():
        print(f"  {name:<14}: {wert:8.4f} bp")
    print(f"  {'SUMME K':<14}: {k_bp:8.4f} bp des Nominals je Round-Turn")
    print()

    m_bp, s_bp, n = bewegung_bp(kurse, horizont)
    noetiger_ertrag = sharpe_je_trade * s_bp
    anteil = (noetiger_ertrag + k_bp) / m_bp

    print("-" * 78)
    print(f"4) WAS DER MARKT UEBER {horizont} BAR(S) HERGIBT (gemessen, In-Sample)")
    print("-" * 78)
    print(f"Fenster (ueberlappend)  : {n}")
    print(f"Mittel |Bewegung|       m : {m_bp:.4f} bp   (Substanz je Trade)")
    print(f"Streuung vorzeichenbeh. s : {s_bp:.4f} bp   (Nenner der Sharpe)")
    print(f"Verhaeltnis s/m           : {s_bp / m_bp:.3f}   "
          f"(Normalverteilung waere 1,253 -- daruber = schwerere Raender)")
    print()
    print("-" * 78)
    print("5) DIE ANTWORT")
    print("-" * 78)
    print(f"Noetiger Netto-Ertrag je Trade  E = S_t * s : {noetiger_ertrag:.4f} bp")
    print(f"Kosten je Trade                 K          : {k_bp:.4f} bp")
    brutto = noetiger_ertrag + k_bp
    print(f"Brutto noetig                   E + K      : {brutto:.4f} bp")
    print(f"Mittlere Bewegung               m          : {m_bp:.4f} bp")
    print()
    print(
        f"==> EINZUFANGENDER ANTEIL DER BEWEGUNG  f = (E+K)/m = {anteil:.4f} "
        f"= {anteil * 100:.1f} %"
    )
    print()
    if anteil >= 1.0:
        print("BEFUND: f >= 1. Das Tor verlangt mehr als die volle mittlere Bewegung")
        print("        des Horizonts. Auf dieser Reihe ist es nicht erfuellbar.")
    else:
        print("BEFUND: f < 1. Das Tor ist rechnerisch erfuellbar, verlangt aber, dass")
        print(
            f"        eine Strategie im Mittel {anteil * 100:.1f} % jeder "
            f"{horizont}-Bar-Bewegung netto einfaengt."
        )
    print()

    # Dieselbe Aussage als Trefferquote -- lesbarer als ein Anteil, und die Formel steht
    # bereits im Stand (``risk/stop_budget.py``). Sie wird gelesen, nicht wiederholt.
    # Unterstellt ist eine symmetrische Auszahlung +-m je Trade (1:1), also genau der
    # Fall, fuer den ``breakeven_hit_rate`` gebaut ist.
    p_null = breakeven_hit_rate(
        cost_bps=Decimal(str(k_bp)), stop_bps=Decimal(str(m_bp))
    )
    p_tor = breakeven_hit_rate(
        cost_bps=Decimal(str(k_bp + noetiger_ertrag)), stop_bps=Decimal(str(m_bp))
    )
    print("-" * 78)
    print("6) DASSELBE ALS TREFFERQUOTE (breakeven_hit_rate, 1:1 auf +-m)")
    print("-" * 78)
    print(f"Nur die Kosten decken        : {float(p_null) * 100:.2f} %")
    print(f"Das Tor nehmen               : {float(p_tor) * 100:.2f} %")
    print(
        f"-> Das Tor kostet gegenueber dem Nulldurchgang "
        f"{(float(p_tor) - float(p_null)) * 100:.2f} Prozentpunkte."
    )
    print()

    print("-" * 78)
    print("7) WOHER DIE KOSTEN KOMMEN -- und was davon gemessen ist")
    print("-" * 78)
    unbelegt = teile["slippage"]
    print(
        f"Slippage-Anteil an K : {unbelegt:.4f} von {k_bp:.4f} bp "
        f"= {unbelegt / k_bp * 100:.1f} %"
    )
    print("Herkunft der Slippage: config/broker_costs.json fuehrt sie als")
    print("                       'ANNAHME, keine Messung'. Der groesste Einzelposten")
    print("                       der Kostenrechnung ist damit nicht gemessen.")
    print()

    print("." * 78)
    print("GEGENPROBE STATIONARITAET (OoS-Block; geht in keine Entscheidung ein)")
    oos_kurse = [float(b.close) for b in oos]
    m_oos, s_oos, n_oos = bewegung_bp(oos_kurse, horizont)
    anteil_oos = (sharpe_je_trade * s_oos + k_bp) / m_oos
    print(
        f"  Mittel |Bewegung| : {m_oos:.4f} bp gegen {m_bp:.4f} bp In-Sample "
        f"({(m_oos / m_bp - 1) * 100:+.1f} %)"
    )
    print(
        f"  Streuung          : {s_oos:.4f} bp gegen {s_bp:.4f} bp In-Sample "
        f"({(s_oos / s_bp - 1) * 100:+.1f} %)"
    )
    p_oos = breakeven_hit_rate(
        cost_bps=Decimal(str(k_bp + sharpe_je_trade * s_oos)),
        stop_bps=Decimal(str(m_oos)),
    )
    print(f"  Fenster           : {n_oos}")
    print(
        f"  Dieselbe Rechnung auf dem OoS-Block ergaebe f = {anteil_oos:.4f} "
        f"= {anteil_oos * 100:.1f} % statt {anteil * 100:.1f} %."
    )
    print(f"  Als Trefferquote waeren das {float(p_oos) * 100:.2f} % statt "
          f"{float(p_tor) * 100:.2f} %.")
    print("  Der Block, an dem das Tor tatsaechlich urteilt, ist also der schwerere.")
    print("." * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

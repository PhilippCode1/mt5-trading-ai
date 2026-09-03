#!/usr/bin/env python3
"""Geprobter Wiederanlauf: uebersteht der Zustand einen harten Abbruch -- wirklich?

WARUM
-----
Stufe 10 des Auftrags verlangt einen **geprobten** Wiederanlauf. Das Wort traegt die
ganze Forderung: dass ein Halt einen Neustart ueberdauern *soll*, steht in mehreren
Modul-Docstrings dieses Standes. Ob er es tut, und ob er danach noch *wirkt*, hat vor
dieser Probe niemand am Stueck nachgesehen.

Die Probe faehrt den Wiederanlauf so, wie er im Ernstfall ablaeuft:

1. Ein Lauf setzt Zustand: Drawdown-Halt gelatcht, Tageszaehler hochgezaehlt, ein
   Sendeversuch ohne Antwort in der Schwebeakte vermerkt.
2. **Der Lauf endet hart** -- kein sauberes Herunterfahren, kein Aufraeumen. Genau der
   Fall, fuer den die Persistenz gebaut ist.
3. Ein **zweiter, frisch gebauter** Lauf oeffnet dieselben Dateien und wird gefragt, was
   er noch weiss -- und zwar nicht durch Nachsehen in einem Feld, sondern indem er eine
   Eroeffnung zu autorisieren versucht. Ein Halt, den man nur im Zustand sieht, der aber
   keine Order mehr aufhaelt, ist keiner.

Die Erholung ist dabei der Kern: Lauf 2 fragt mit **wieder vollem Konto** (10.000, der
Drawdown ist weg). Genau hier scheitert die naive Fassung -- sie faende nichts mehr zu
halten und liesse durch.

Was ABSICHTLICH nicht ueberdauert:

* **Das Buch.** Es wird beim Start vom Handelsplatz uebernommen (``adopt_book``). Eine
  gespeicherte Fassung waere eine zweite Wahrheit neben der des Brokers -- und bei
  Abweichung gewinnt immer der Broker, weil dort das Geld liegt.

Aufruf::

    python tools/wiederanlaufprobe.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.execution.risiko_zustand import DateiZustand  # noqa: E402
from mt5_trading_ai.execution.risk_manager import (  # noqa: E402
    RiskAuthorization,
    RiskManager,
)
from mt5_trading_ai.execution.schwebende_auftraege import (  # noqa: E402
    SchwebeAkte,
    SchwebenderAuftrag,
)
from mt5_trading_ai.venue.protocol import (  # noqa: E402
    AccountState,
    AssetClass,
    FeeSchedule,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
)

TS = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
KONTO = "50123456"
WAEHRUNG = "USD"


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


def _konto(equity: str) -> AccountState:
    return AccountState(
        account_id=KONTO,
        currency=WAEHRUNG,
        balance=Decimal(equity),
        equity=Decimal(equity),
        margin_used=Decimal("0"),
        margin_free=Decimal(equity),
        is_demo=True,
        ts=TS,
    )


def _order() -> OrderRequest:
    return OrderRequest(
        client_order_id="c-probe",
        symbol="EURUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=Decimal("0.01"),
        stop_loss=Decimal("1.09000"),
    )


def _autorisiere(
    rm: RiskManager, konto: AccountState, now: datetime
) -> RiskAuthorization:
    return rm.authorize_opening(
        instrument=_instrument(),
        request=_order(),
        account=konto,
        price=Decimal("1.10000"),
        spread_bps=Decimal("0.9"),
        leverage=5,
        now=now,
    )


def _lauf(zustandsdatei: Path) -> RiskManager:
    """Ein Prozessstart: ein frischer Manager auf derselben Zustandsdatei."""
    return RiskManager(
        zustand=DateiZustand(zustandsdatei), konto_id=KONTO, waehrung=WAEHRUNG
    )


def probe(ordner: Path) -> list[tuple[str, bool, str]]:
    """Faehrt die Probe. Rueckgabe: ``(Name, bestanden, Anmerkung)`` je Pruefung."""
    zustandsdatei = ordner / "risikozustand.json"
    schwebedatei = ordner / "schwebende_auftraege.json"
    ergebnisse: list[tuple[str, bool, str]] = []

    # --- Lauf 1: Zustand setzen, dann hart enden -------------------------------
    erster = _lauf(zustandsdatei)
    erster.observe_equity(TS, Decimal("10000"))
    erster.record_open_fill("EURUSD", TS)
    # 10.000 -> 8.000 sind 20 % Drawdown gegen eine Grenze von 10 %: latcht den Halt.
    eingebrochen = _autorisiere(erster, _konto("8000"), TS + timedelta(minutes=1))
    ergebnisse.append(
        (
            "Lauf 1: der Einbruch latcht ueberhaupt einen Halt",
            not eingebrochen.approved and eingebrochen.latch_halt,
            f"Grund: {eingebrochen.reason}",
        )
    )

    akte = SchwebeAkte(schwebedatei)
    akte.vermerken(
        SchwebenderAuftrag("open-EURUSD-probe", "Zeitablauf beim Senden", TS, "EURUSD")
    )
    # Kein sauberes Herunterfahren: ``erster`` wird schlicht fallengelassen.
    del erster

    # --- Lauf 2: frisch gebaut, dieselben Dateien, ERHOLTES Konto --------------
    zweiter = _lauf(zustandsdatei)
    ergebnisse.append(
        (
            "Risikozustand: Datei liegt auf der Platte",
            zustandsdatei.is_file(),
            str(zustandsdatei),
        )
    )
    ergebnisse.append(
        (
            "Risikozustand: dauerhaft, nicht fluechtig",
            zweiter.zustand_dauerhaft,
            "eine fluechtige Schicht verhaelt sich bis zum Neustart genau wie eine "
            "dauerhafte -- deshalb wird sie hier gefragt",
        )
    )

    erholt = _autorisiere(zweiter, _konto("10000"), TS + timedelta(hours=2))
    ergebnisse.append(
        (
            "Der Halt WIRKT nach dem Neustart -- bei erholtem Konto",
            not erholt.approved and erholt.latch_halt,
            f"Konto wieder bei 10.000, Antwort: approved={erholt.approved}, "
            f"reason={erholt.reason}",
        )
    )
    # ``reason`` ist ``str | None``. Ein fehlender Grund ist hier ein Durchfall und
    # kein Sonderfall: eine Ablehnung ohne Grund waere nach dem Neustart genau die
    # Auskunft, mit der niemand etwas anfangen kann.
    grund = erholt.reason or ""
    ergebnisse.append(
        (
            "Der Grund ueberdauert mit, nicht nur das Ja/Nein",
            "gelatcht" in grund or "drawdown" in grund,
            f"'{grund}' -- ohne Grund weiss der Mensch am Morgen nicht, wonach "
            f"er sehen soll",
        )
    )

    # --- Die Schwebeakte -------------------------------------------------------
    zweite_akte = SchwebeAkte(schwebedatei)
    befund = zweite_akte.laden()
    kennungen = [e.client_order_id for e in befund.eintraege]
    ergebnisse.append(
        (
            "Schwebeakte: dauerhaft, nicht fluechtig",
            zweite_akte.dauerhaft,
            str(schwebedatei),
        )
    )
    ergebnisse.append(
        (
            "Schwebeakte: der ungeklaerte Sendeversuch ueberdauert",
            kennungen == ["open-EURUSD-probe"],
            f"gelesen: {kennungen}",
        )
    )
    ergebnisse.append(
        (
            "Schwebeakte: der Grund ueberdauert unveraendert",
            bool(befund.eintraege)
            and befund.eintraege[0].grund == "Zeitablauf beim Senden",
            "der Grund sagt, wonach beim Broker zu sehen ist",
        )
    )

    # --- Was ABSICHTLICH nicht ueberdauert -------------------------------------
    liegengeblieben = sorted(p.name for p in ordner.iterdir())
    ergebnisse.append(
        (
            "Das Buch wird NICHT persistiert (Absicht, nicht Luecke)",
            all("buch" not in n for n in liegengeblieben),
            "es kommt beim Start vom Handelsplatz (adopt_book); eine gespeicherte "
            "Fassung waere eine zweite Wahrheit neben der des Brokers. "
            f"Liegt: {liegengeblieben}",
        )
    )

    # --- Der einzige Weg heraus ------------------------------------------------
    entfernt = zweite_akte.aufloesen(
        "open-EURUSD-probe", befund="Probe: beim Broker nachgesehen, keine Order"
    )
    ergebnisse.append(
        (
            "Aufloesung MIT Befund raeumt den Eintrag ab",
            entfernt and zweite_akte.laden().eintraege == (),
            "und sie ueberdauert ihrerseits: die Akte ist danach leer",
        )
    )
    ohne_befund_wirft = False
    try:
        zweite_akte.aufloesen("open-EURUSD-probe", befund="   ")
    except ValueError:
        ohne_befund_wirft = True
    ergebnisse.append(
        (
            "Aufloesung OHNE Befund wird abgewiesen",
            ohne_befund_wirft,
            "wer nichts hinschreibt, hat nichts nachgesehen",
        )
    )

    # --- Und der Halt bleibt, bis ein Mensch ihn freigibt ----------------------
    dritter = RiskManager(
        zustand=DateiZustand(zustandsdatei),
        konto_id=KONTO,
        waehrung=WAEHRUNG,
        manual_release_id="probe-freigabe-2026-08-20",
    )
    freigegeben = _autorisiere(dritter, _konto("10000"), TS + timedelta(hours=3))
    ergebnisse.append(
        (
            "Erst die menschliche Freigabe loest ihn -- und dann wirklich",
            freigegeben.approved,
            f"mit Freigabekennung: approved={freigegeben.approved}, "
            f"reason={freigegeben.reason!r}",
        )
    )
    return ergebnisse


def main() -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Geprobter Wiederanlauf")
    ap.add_argument(
        "--behalten", action="store_true", help="den Probeordner nicht loeschen"
    )
    args = ap.parse_args()

    ordner = Path(tempfile.mkdtemp(prefix="wiederanlaufprobe-"))
    print("=" * 78)
    print("WIEDERANLAUFPROBE - uebersteht der Zustand einen harten Abbruch?")
    print("=" * 78)
    print(f"Probeordner: {ordner}")
    print()
    try:
        ergebnisse = probe(ordner)
    finally:
        if not args.behalten:
            shutil.rmtree(ordner, ignore_errors=True)

    gefallen = []
    for name, bestanden, anmerkung in ergebnisse:
        print(f"  {'ok  ' if bestanden else 'ROT '} {name}")
        print(f"        {anmerkung}")
        if not bestanden:
            gefallen.append(name)

    print()
    print(
        f"{len(ergebnisse) - len(gefallen)} von {len(ergebnisse)} Pruefungen bestanden."
    )
    if gefallen:
        print()
        for name in gefallen:
            print(f"FEHLGESCHLAGEN - {name}", file=sys.stderr)
        print(
            "Ein Wiederanlauf, der Zustand verliert, verliert ihn im Ernstfall.",
            file=sys.stderr,
        )
        return 1
    print("ok - der Wiederanlauf haelt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

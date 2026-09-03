"""T6, D3: Betraege mit Waehrung; Umrechnungskurs vom Terminal, fehlend = Sperre (E-005).

Eigenes Patchskript (2026-09-03). Aendert risk/sizing.py (Waehrungen und Kurs sind
Pflichtangaben; Verlust am Stop wird in Kontowaehrung gerechnet), execution/
leverage_preflight.py (Marge in Margenwaehrung, umgerechnet), execution/runner.py
(Margendeckel ebenso), venue/protocol.py und venue/mt5.py (margin_currency vom Terminal,
Mt5Venue.kurs(), Kurse an Hebelklammer und Risikoschicht), execution/risk_manager.py
(quote_to_account_rate an size_position) und die Tests, die die Funktionen direkt rufen.

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/06-d3-umbau.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
NL = chr(10)


def patch(rel: str, pairs: list[tuple[str, str]]) -> None:
    p = REPO / rel
    s = p.read_text(encoding="utf-8")
    for alt, neu in pairs:
        assert s.count(alt) == 1, f"{rel}: Anker ({s.count(alt)}): {alt[:70]!r}"
        s = s.replace(alt, neu)
    p.write_text(s, encoding="utf-8", newline="")
    print(f"  gepatcht: {rel} ({len(pairs)} Stellen)")


def schon(rel: str, marker: str) -> bool:
    """Idempotenz: ein Abschnitt, dessen Marker schon in der Datei steht, wird uebersprungen."""
    if marker in (REPO / rel).read_text(encoding="utf-8"):
        print(f"  schon gepatcht: {rel}")
        return True
    return False


def main() -> int:
    if not schon("mt5_trading_ai/risk/sizing.py", "account_currency: str,"):
        sizing()
    if not schon("mt5_trading_ai/venue/protocol.py", "margin_currency: str | None = None"):
        protokoll()
    if not schon("mt5_trading_ai/execution/leverage_preflight.py", "margin_to_account_rate"):
        preflight()
    if not schon("mt5_trading_ai/execution/runner.py", "margin_to_account_rate"):
        runner()
    if not schon("mt5_trading_ai/venue/mt5.py", "def kurs("):
        venue()
    if not schon("mt5_trading_ai/execution/risk_manager.py", "quote_to_account_rate"):
        riskmanager()
    if not schon("tests/test_risk_sizing.py", "account_currency"):
        tests()
    return 0


def sizing() -> None:
    p = REPO / "mt5_trading_ai/risk/sizing.py"
    s = p.read_text(encoding="utf-8")
    alt = "    leverage: int | None," + NL + ") -> SizingResult:" + NL
    assert s.count(alt) == 1, "sizing Signatur"
    s = s.replace(
        alt,
        "    leverage: int | None," + NL
        + "    account_currency: str," + NL
        + "    quote_currency: str | None," + NL
        + "    quote_to_account_rate: Decimal | None," + NL
        + ") -> SizingResult:" + NL,
    )
    alt = '    """Positionsgroesse aus Risikoanteil und Stopabstand."""' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        '    """Positionsgroesse aus Risikoanteil und Stopabstand -- in Kontowaehrung (D3).' + NL
        + NL
        + "    Der Risikobetrag steht in ``account_currency``, der Stopabstand je Lot in" + NL
        + "    ``quote_currency``. ``quote_to_account_rate`` ist der Wert EINER Einheit der" + NL
        + "    Notierungswaehrung in Kontowaehrung; bei gleicher Waehrung wird er nicht" + NL
        + "    gebraucht, bei ungleicher ist ``None`` eine Sperre (``fx_unverifiable``)," + NL
        + "    keine stille 1 -- der Verlust am Stop laege sonst neben dem Budget" + NL
        + "    (Bewertung D3: +26 % fuer EURGBP auf einem USD-Konto)." + NL
        + '    """' + NL,
    )
    alt = "    if leverage is None:" + NL + '        reasons.append("leverage_no_trade")' + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        alt
        + "    kurs = _kurs_in_kontowaehrung(" + NL
        + "        account_currency, quote_currency, quote_to_account_rate" + NL
        + "    )" + NL
        + "    if kurs is None:" + NL
        + '        reasons.append("fx_unverifiable")' + NL,
    )
    alt = (
        "    stop_distance_price = price * stop_distance / Decimal(\"10000\")" + NL
        + "    raw_volume = risk_currency / (stop_distance_price * contract_size)" + NL
    )
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "    stop_distance_price = price * stop_distance / Decimal(\"10000\")" + NL
        + "    # Verlust am Stop je Lot, in KONTOWAEHRUNG: Notierungswaehrung * Kurs." + NL
        + "    assert kurs is not None  # oben als Grund erfasst" + NL
        + "    verlust_je_lot_konto = stop_distance_price * contract_size * kurs" + NL
        + "    raw_volume = risk_currency / verlust_je_lot_konto" + NL,
    )
    alt = "    notional = volume * contract_size * price" + NL
    assert s.count(alt) == 1
    s = s.replace(alt, "    notional = volume * contract_size * price * kurs  # in Kontowaehrung" + NL)
    # Rueckgabe: Kurs mitfuehren
    s = s.replace(
        "        leverage=leverage," + NL + "        reasons=tuple(dict.fromkeys(reasons))," + NL + "    )",
        "        leverage=leverage," + NL + "        reasons=tuple(dict.fromkeys(reasons))," + NL + "        fx_rate=kurs," + NL + "    )",
    )
    # SizingResult-Feld
    m = re.search(r"class SizingResult:\n(.*?)\n\n", s, flags=re.S)
    assert m, "SizingResult"
    block = m.group(0)
    assert "fx_rate" not in block
    neu_block = block.rstrip(NL) + NL + "    #: Kurs Notierungs- -> Kontowaehrung, mit dem gerechnet wurde (1 bei gleicher" + NL + "    #: Waehrung, None bei Ablehnung ohne Kurs). D3." + NL + "    fx_rate: Decimal | None = None" + NL + NL
    s = s.replace(block, neu_block)
    # Helfer
    alt = "def size_position(" + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "def _kurs_in_kontowaehrung(" + NL
        + "    account_currency: str, quote_currency: str | None, kurs: Decimal | None" + NL
        + ") -> Decimal | None:" + NL
        + '    """1 bei gleicher Waehrung; sonst der gegebene Kurs; None = nicht messbar (Sperre)."""' + NL
        + "    if not quote_currency:" + NL
        + "        return None" + NL
        + "    if quote_currency == account_currency:" + NL
        + '        return Decimal("1")' + NL
        + "    if kurs is None or kurs <= 0:" + NL
        + "        return None" + NL
        + "    return kurs" + NL
        + NL
        + NL
        + "def size_position(" + NL,
    )
    p.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: mt5_trading_ai/risk/sizing.py")



def protokoll() -> None:
    # --- protocol.py: Instrument.margin_currency -----------------------------------
    patch(
        "mt5_trading_ai/venue/protocol.py",
        [
            (
                "    fees: FeeSchedule" + NL + "    sessions: tuple[TradingSession, ...]" + NL,
                "    fees: FeeSchedule" + NL + "    sessions: tuple[TradingSession, ...]" + NL
                + "    #: Waehrung, in der der Broker die Marge rechnet (MT5 ``currency_margin``;" + NL
                + "    #: bei Devisen die Basiswaehrung). ``None`` = unbekannt -> Margenpruefung" + NL
                + "    #: sperrt (D3)." + NL
                + "    margin_currency: str | None = None" + NL,
            )
        ],
    )



def preflight() -> None:
    # --- leverage_preflight.py -----------------------------------------------------
    patch(
        "mt5_trading_ai/execution/leverage_preflight.py",
        [
            (
                "    requested_leverage: Any = None," + NL + "    policy: LeveragePolicy | None = None," + NL + ") -> LeveragePreflight:" + NL,
                "    requested_leverage: Any = None," + NL + "    policy: LeveragePolicy | None = None," + NL
                + "    margin_to_account_rate: Decimal | None = None," + NL
                + ") -> LeveragePreflight:" + NL,
            ),
            (
                "    notional = request.volume * instrument.contract_size * price" + NL
                + "    required_margin = notional / Decimal(wirksam)" + NL,
                "    # D3: die Marge entsteht in der MARGENWAEHRUNG des Instruments (bei Devisen die" + NL
                + "    # Basiswaehrung: Lots * Kontraktgroesse; sonst Lots * Kontraktgroesse * Kurs)" + NL
                + "    # und wird mit einem gegebenen Kurs in Kontowaehrung gebracht. Kein Kurs bei" + NL
                + "    # ungleicher Waehrung = keine Marge messbar = keine Order (fx_unverifiable)." + NL
                + "    margen_waehrung = instrument.margin_currency or instrument.base_currency" + NL
                + "    if margen_waehrung == instrument.base_currency:" + NL
                + "        margen_notional = request.volume * instrument.contract_size" + NL
                + "    elif margen_waehrung == instrument.quote_currency:" + NL
                + "        margen_notional = request.volume * instrument.contract_size * price" + NL
                + "    else:" + NL
                + "        margen_waehrung = None" + NL
                + "        margen_notional = Decimal(\"0\")" + NL
                + "    if margen_waehrung is None:" + NL
                + "        kurs: Decimal | None = None" + NL
                + "    elif margen_waehrung == account.currency:" + NL
                + "        kurs = Decimal(\"1\")" + NL
                + "    elif margin_to_account_rate is not None and margin_to_account_rate > 0:" + NL
                + "        kurs = margin_to_account_rate" + NL
                + "    else:" + NL
                + "        kurs = None" + NL
                + "    if kurs is None:" + NL
                + "        return LeveragePreflight(" + NL
                + "            approved=False," + NL
                + "            effective_leverage=wirksam," + NL
                + "            required_margin=None," + NL
                + '            reason="fx_unverifiable",' + NL
                + "            leverage=decision," + NL
                + "        )" + NL
                + "    required_margin = margen_notional * kurs / Decimal(wirksam)" + NL,
            ),
        ],
    )



def runner() -> None:
    # --- runner.py: Margendeckel ----------------------------------------------------
    patch(
        "mt5_trading_ai/execution/runner.py",
        [
            (
                "def _margen_deckel(" + NL
                + "    *, instrument: Instrument, account: AccountState, price: Decimal, plaetze: int" + NL
                + ") -> Decimal | None:" + NL,
                "def _margen_deckel(" + NL
                + "    *," + NL
                + "    instrument: Instrument," + NL
                + "    account: AccountState," + NL
                + "    price: Decimal," + NL
                + "    plaetze: int," + NL
                + "    margin_to_account_rate: Decimal | None," + NL
                + ") -> Decimal | None:" + NL,
            ),
            (
                "    anteil = account.margin_free / Decimal(plaetze) * _MARGEN_SICHERHEIT" + NL
                + "    je_lot = instrument.contract_size * price / Decimal(account.leverage)" + NL,
                "    anteil = account.margin_free / Decimal(plaetze) * _MARGEN_SICHERHEIT" + NL
                + "    # D3: Marge je Lot in Margenwaehrung, dann in Kontowaehrung (kein Kurs = kein" + NL
                + "    # Deckel; die Hebelklammer sperrt dann selbst mit fx_unverifiable)." + NL
                + "    margen_waehrung = instrument.margin_currency or instrument.base_currency" + NL
                + "    if margen_waehrung == instrument.base_currency:" + NL
                + "        je_lot_margen = instrument.contract_size" + NL
                + "    elif margen_waehrung == instrument.quote_currency:" + NL
                + "        je_lot_margen = instrument.contract_size * price" + NL
                + "    else:" + NL
                + "        return None" + NL
                + "    if margen_waehrung == account.currency:" + NL
                + '        kurs = Decimal("1")' + NL
                + "    elif margin_to_account_rate is not None and margin_to_account_rate > 0:" + NL
                + "        kurs = margin_to_account_rate" + NL
                + "    else:" + NL
                + "        return None" + NL
                + "    je_lot = je_lot_margen * kurs / Decimal(account.leverage)" + NL,
            ),
            (
                "    deckel = _margen_deckel(" + NL
                + "        instrument=instrument," + NL
                + "        account=account," + NL
                + "        price=ref," + NL
                + "        plaetze=config.max_concurrent_positions," + NL
                + "    )" + NL,
                "    deckel = _margen_deckel(" + NL
                + "        instrument=instrument," + NL
                + "        account=account," + NL
                + "        price=ref," + NL
                + "        plaetze=config.max_concurrent_positions," + NL
                + "        margin_to_account_rate=venue.kurs(" + NL
                + "            instrument.margin_currency or instrument.base_currency or \"\"," + NL
                + "            account.currency," + NL
                + "        )," + NL
                + "    )" + NL,
            ),
        ],
    )



def venue() -> None:
    # --- mt5.py -------------------------------------------------------------------
    m = REPO / "mt5_trading_ai/venue/mt5.py"
    s = m.read_text(encoding="utf-8")
    alt = "    stop_level_points: int" + NL + "    freeze_level_points: int" + NL + "    visible: bool" + NL
    assert s.count(alt) == 1, "Mt5Symbol"
    s = s.replace(alt, alt + "    #: MT5 ``currency_margin``; ``None`` = nicht gemeldet (D3)." + NL + "    margin_currency: str | None = None" + NL)
    alt = "            base_currency=sym.base_currency," + NL + "            quote_currency=sym.quote_currency," + NL + "            stop_level_points=sym.stop_level_points," + NL
    assert s.count(alt) == 1, "Instrument-Bau"
    s = s.replace(alt, "            base_currency=sym.base_currency," + NL + "            quote_currency=sym.quote_currency," + NL + "            margin_currency=sym.margin_currency," + NL + "            stop_level_points=sym.stop_level_points," + NL)
    alt = "            base_currency=str(info.currency_base) or None," + NL + "            quote_currency=str(info.currency_profit) or None," + NL
    assert s.count(alt) == 1, "_to_symbol"
    s = s.replace(alt, alt + '            margin_currency=str(getattr(info, "currency_margin", "") or "") or None,' + NL)
    # Mt5Venue.kurs()
    alt = "    def _enforce_leverage(self, instrument: Instrument, request: OrderRequest) -> int:" + NL
    assert s.count(alt) == 1
    s = s.replace(
        alt,
        "    def kurs(self, von: str, nach: str) -> Decimal | None:" + NL
        + '        """Wert einer Einheit ``von`` in ``nach`` aus den Ticks des Terminals (D3).' + NL
        + NL
        + "        Mittelkurs von ``VONNACH``, sonst Kehrwert von ``NACHVON``; gleiche Waehrung" + NL
        + "        = 1; kein Tick = ``None`` -- und ``None`` sperrt beim Aufrufer." + NL
        + '        """' + NL
        + "        if not von or not nach:" + NL
        + "            return None" + NL
        + "        return kurs_aus_ticks(von, nach, self._terminal.tick)" + NL
        + NL
        + alt,
    )
    alt = "            price=price," + NL + '            requested_leverage=request.meta.get("requested_leverage"),' + NL + "        )" + NL
    assert s.count(alt) == 1, "_enforce_leverage Aufruf"
    s = s.replace(
        alt,
        "            price=price," + NL
        + '            requested_leverage=request.meta.get("requested_leverage"),' + NL
        + "            margin_to_account_rate=self.kurs(" + NL
        + '                instrument.margin_currency or instrument.base_currency or "",' + NL
        + "                self.get_account().currency," + NL
        + "            )," + NL
        + "        )" + NL,
    )
    alt = "            spread_bps=spread_bps," + NL + "            leverage=leverage," + NL + "            now=account.ts," + NL + "        )" + NL
    assert s.count(alt) == 1, "_enforce_risk Aufruf"
    s = s.replace(
        alt,
        "            spread_bps=spread_bps," + NL
        + "            leverage=leverage," + NL
        + "            now=account.ts," + NL
        + '            quote_to_account_rate=self.kurs(instrument.quote_currency or "", account.currency),' + NL
        + "        )" + NL,
    )
    if "from mt5_trading_ai.risk.waehrung import kurs_aus_ticks" not in s:
        m2 = re.search(r"^from mt5_trading_ai\.[a-z_.]+ import", s, flags=re.M)
        assert m2, "Import-Anker mt5.py"
        s = s[: m2.start()] + "from mt5_trading_ai.risk.waehrung import kurs_aus_ticks" + NL + s[m2.start() :]
    m.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: mt5_trading_ai/venue/mt5.py (6 Stellen)")



def riskmanager() -> None:
    # --- risk_manager.py: Kurs an size_position durchreichen ------------------------
    r = REPO / "mt5_trading_ai/execution/risk_manager.py"
    s = r.read_text(encoding="utf-8")
    alt = "        measured_cost_bps: Decimal | None = None," + NL + "    ) -> RiskAuthorization:" + NL
    assert s.count(alt) == 1, "authorize_opening Signatur"
    s = s.replace(alt, "        measured_cost_bps: Decimal | None = None," + NL + "        quote_to_account_rate: Decimal | None = None," + NL + "    ) -> RiskAuthorization:" + NL)
    m3 = re.search(r"        sizing = size_position\(\n(.*?)\n        \)\n", s, flags=re.S)
    assert m3, "size_position-Aufruf"
    aufruf = m3.group(0)
    assert "account_currency" not in aufruf
    neu = aufruf.replace(
        NL + "        )" + NL,
        NL + "            account_currency=account.currency," + NL
        + "            quote_currency=instrument.quote_currency," + NL
        + "            quote_to_account_rate=quote_to_account_rate," + NL
        + "        )" + NL,
    )
    s = s.replace(aufruf, neu)
    r.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: mt5_trading_ai/execution/risk_manager.py (2 Stellen)")



def tests() -> None:
    # --- Tests: direkte Aufrufer ----------------------------------------------------
    patch(
        "tests/test_risk_sizing.py",
        [
            (
                '        "leverage": 5,' + NL + "    }" + NL + "    kwargs.update(overrides)" + NL,
                '        "leverage": 5,' + NL
                + '        "account_currency": "USD",' + NL
                + '        "quote_currency": "USD",' + NL
                + '        "quote_to_account_rate": None,' + NL
                + "    }" + NL + "    kwargs.update(overrides)" + NL,
            )
        ],
    )
    t = REPO / "tests/test_mt5_venue.py"
    s = t.read_text(encoding="utf-8")
    n = s.count("        requested_leverage=50," + NL + "    )")
    s = s.replace("        requested_leverage=50," + NL + "    )", "        requested_leverage=50," + NL + '        margin_to_account_rate=Decimal("1.10"),' + NL + "    )")
    t.write_text(s, encoding="utf-8", newline="")
    print(f"  gepatcht: tests/test_mt5_venue.py ({n} Preflight-Aufrufe)")
    patch(
        "tests/test_stufe9_tote_tore.py",
        [
            (
                '        price=Decimal("0"),' + NL + "        requested_leverage=5," + NL + "    )" + NL,
                '        price=Decimal("0"),' + NL + "        requested_leverage=5," + NL + '        margin_to_account_rate=Decimal("1"),' + NL + "    )" + NL,
            )
        ],
    )


if __name__ == "__main__":
    sys.exit(main())

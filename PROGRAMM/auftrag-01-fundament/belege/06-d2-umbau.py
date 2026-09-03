"""T6, D2: ein Schliessauftrag traegt sein Positionsticket im Typ (E-005).

Eigenes Patchskript (2026-09-03). Aendert venue/protocol.py (OrderRequest.position_ticket,
Pruefung im Konstruktor), venue/mt5.py (_reduces_position per Ticket und Seite,
_to_terminal_request, RealMt5Terminal.order_send verlangt und prueft das Ticket vor dem
Senden, modify_stops sendet symbol und laesst nicht gewuenschte Stops stehen,
emergency_flatten uebergibt das Ticket), tools/live_betrieb.py (_schliesse) und die
Testattrappe FakeMt5Terminal samt allen reduce_only-Stellen in den Tests (ausser
tests/test_stufe5_ausfuehrung.py und venue/smoke.py, die anderen Familien gehoeren).

Aufruf: python PROGRAMM/auftrag-01-fundament/belege/06-d2-umbau.py
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
        assert s.count(alt) == 1, f"{rel}: Anker nicht eindeutig ({s.count(alt)}): {alt[:70]!r}"
        s = s.replace(alt, neu)
    p.write_text(s, encoding="utf-8", newline="")
    print(f"  gepatcht: {rel} ({len(pairs)} Stellen)")


def main() -> int:
    # --- protocol.py -------------------------------------------------------------
    patch(
        "mt5_trading_ai/venue/protocol.py",
        [
            (
                '    reduce_only: bool = False' + NL
                + '    comment: str = ""' + NL
                + "    meta: dict[str, Any] = field(default_factory=dict)" + NL,
                '    reduce_only: bool = False' + NL
                + "    #: Das Ticket der Position, die ein reduzierender Auftrag abbaut. Ein" + NL
                + "    #: Schliessauftrag ohne Ticket ist nicht darstellbar (D2, E-005): der" + NL
                + "    #: Konstruktor weist ihn ab, der Handelsplatz sendet ihn nie." + NL
                + "    position_ticket: str | None = None" + NL
                + '    comment: str = ""' + NL
                + "    meta: dict[str, Any] = field(default_factory=dict)" + NL
                + NL
                + "    def __post_init__(self) -> None:" + NL
                + "        if self.reduce_only and not (self.position_ticket or '').strip():" + NL
                + "            raise ValueError(" + NL
                + '                f"{self.client_order_id}: reduce_only ohne position_ticket ist nicht "' + NL
                + '                "darstellbar -- eine Schliessung ohne Ticket wuerde auf einem "' + NL
                + '                "Hedging-Konto zur Gegenposition (D2)"' + NL
                + "            )" + NL,
            )
        ],
    )

    # --- mt5.py ------------------------------------------------------------------
    m = REPO / "mt5_trading_ai/venue/mt5.py"
    s = m.read_text(encoding="utf-8")

    # _reduces_position: Ticket und Seite statt Summe
    a = re.search(
        r"        opposite = sum\(\n.*?return opposite > 0 and request\.volume <= opposite\n",
        s,
        flags=re.S,
    )
    assert a, "_reduces_position"
    s = s.replace(
        a.group(0),
        NL.join(
            [
                "        # D2 (E-005): nicht die Summe der Gegenpositionen entscheidet, sondern GENAU",
                "        # die Position, deren Ticket der Auftrag traegt -- frisch beim Broker gelesen.",
                "        # Fehlt sie (Stop gefeuert, Handschliessung), ist die Order keine Schliessung",
                "        # und faellt durch alle Tore; das Terminal sendet sie ohnehin nicht (siehe",
                "        # ``RealMt5Terminal.order_send``).",
                "        ticket = request.position_ticket",
                "        if ticket is None:",
                "            return False",
                "        for pos in self.get_positions():",
                "            if pos.venue_position_id != ticket:",
                "                continue",
                "            return (",
                "                pos.symbol == request.symbol",
                "                and pos.side is not request.side",
                '                and Decimal("0") < request.volume <= pos.volume',
                "            )",
                "        return False",
                "",
            ]
        ),
    )
    # _to_terminal_request
    alt = '            "reduce_only": request.reduce_only,' + NL
    assert s.count(alt) == 1
    s = s.replace(alt, alt + '            "position_ticket": request.position_ticket,' + NL)
    # emergency_flatten
    alt = (
        "                        stop_loss=Decimal(\"0\")," + NL
        + "                        reduce_only=True," + NL
        + '                        comment="emergency-flatten",' + NL
    )
    assert s.count(alt) == 1, "emergency_flatten"
    s = s.replace(
        alt,
        "                        stop_loss=Decimal(\"0\")," + NL
        + "                        reduce_only=True," + NL
        + "                        position_ticket=position.venue_position_id," + NL
        + '                        comment="emergency-flatten",' + NL,
    )
    # RealMt5Terminal.order_send: Ticket verlangen und pruefen, sonst nicht senden
    b = re.search(
        r'        if request\.get\("reduce_only"\) and action == mt5\.TRADE_ACTION_DEAL:\n.*?'
        r'                    req\["position"\] = int\(pos\.ticket\)\n                    break\n',
        s,
        flags=re.S,
    )
    assert b, "order_send reduce_only block"
    s = s.replace(
        b.group(0),
        NL.join(
            [
                '        if request.get("reduce_only") and action == mt5.TRADE_ACTION_DEAL:',
                "            # D2 (E-005): eine Schliessung traegt ihr Ticket, oder sie wird nicht",
                "            # gesendet. Frueher wurde die Gegenposition hier per Symbol gesucht und",
                "            # bei leerem Treffer die Marktorder OHNE ``position`` geschickt -- auf",
                "            # einem Hedging-Konto eine neue Gegenposition ohne Stop, an allen Toren",
                "            # vorbei (Bewertung D2, nachgestellt in belege/03-nachstellung V2).",
                '            ticket_roh = request.get("position_ticket")',
                "            if not ticket_roh:",
                "                raise VenueUnavailableError(",
                '                    f"{symbol}: Schliessung ohne Positionsticket -- nicht gesendet"',
                "                )",
                "            ticket = int(ticket_roh)",
                "            roh = mt5.positions_get(ticket=ticket)",
                "            if roh is None:",
                "                raise VenueUnavailableError(",
                '                    f"{symbol}: der Positionsbestand ist nicht abfragbar -- welche "',
                '                    "Position geschlossen werden soll, ist damit unbekannt. Es wird "',
                '                    "nicht gesendet: eine Schliessung ohne Ticket wird auf einem "',
                '                    "Hedging-Konto zur Gegenposition."',
                "                )",
                "            want_long = not is_buy",
                '            buy_type = int(getattr(mt5, "POSITION_TYPE_BUY", 0))',
                "            treffer = [",
                "                pos",
                "                for pos in tuple(roh)",
                "                if int(pos.ticket) == ticket",
                "                and str(pos.symbol) == symbol",
                "                and (int(pos.type) == buy_type) == want_long",
                "            ]",
                "            if not treffer:",
                "                # Die Position ist zwischen Pruefung und Senden verschwunden (Stop",
                "                # gefeuert, Handschliessung). Nichts senden; der Aufrufer sieht",
                "                # ``position_vanished`` und der naechste Reconcile das Buch.",
                "                return Mt5SendResult(",
                "                    accepted=False,",
                "                    venue_order_id=None,",
                '                    filled_volume=Decimal("0"),',
                "                    average_price=None,",
                "                    ts=now,",
                '                    reason="position_vanished",',
                "                    retryable=False,",
                "                )",
                '            req["position"] = ticket',
                "",
            ]
        ),
    )
    # modify_stops: symbol mitsenden, nicht gewuenschte Stops stehen lassen
    alt = (
        '        req: dict[str, Any] = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket}' + NL
        + "        if stop_loss is not None:" + NL
        + '            req["sl"] = float(stop_loss)' + NL
        + "        if take_profit is not None:" + NL
        + '            req["tp"] = float(take_profit)' + NL
    )
    assert s.count(alt) == 1, "modify_stops"
    s = s.replace(
        alt,
        NL.join(
            [
                "        # V2b (Bewertung): der SLTP-Request nannte kein ``symbol`` und liess bei",
                "        # ``tp=None`` das Feld weg -- der Server loeschte damit den bestehenden",
                "        # Take-Profit. ``None`` heisst hier \"nicht anfassen\": der aktuelle Wert",
                "        # wird gelesen und mitgeschickt.",
                "        vorher = mt5.positions_get(ticket=ticket)",
                "        if not vorher:",
                "            return False  # Position weg oder Bestand nicht abfragbar: kein Beleg",
                "        aktuell = tuple(vorher)[0]",
                "        req: dict[str, Any] = {",
                '            "action": mt5.TRADE_ACTION_SLTP,',
                '            "position": ticket,',
                '            "symbol": str(aktuell.symbol),',
                '            "sl": float(stop_loss) if stop_loss is not None else float(aktuell.sl),',
                '            "tp": float(take_profit)',
                "            if take_profit is not None",
                '            else float(getattr(aktuell, "tp", 0.0) or 0.0),',
                "        }",
                "",
            ]
        ),
    )
    m.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: mt5_trading_ai/venue/mt5.py (5 Stellen)")

    # --- live_betrieb.py ---------------------------------------------------------
    patch(
        "tools/live_betrieb.py",
        [
            (
                '        stop_loss=Decimal("0"),  # bei reduce_only nicht geprueft -- kein Stop noetig' + NL
                + "        reduce_only=True," + NL
                + '        comment=f"live_betrieb: {grund}",' + NL,
                '        stop_loss=Decimal("0"),  # bei reduce_only nicht geprueft -- kein Stop noetig' + NL
                + "        reduce_only=True," + NL
                + "        position_ticket=lage.position_id,  # D2: Schliessung nur mit Ticket" + NL
                + '        comment=f"live_betrieb: {grund}",' + NL,
            )
        ],
    )

    # --- Testattrappe: FakeMt5Terminal.order_send prueft das Ticket ------------------
    t = REPO / "tests/test_mt5_venue.py"
    s = t.read_text(encoding="utf-8")
    alt = (
        '        volume = Decimal("0.10")' + NL
        + "        if isinstance(request, dict):" + NL
        + '            volume = Decimal(str(request["volume"]))' + NL
        + "        self.order_send_calls += 1" + NL
    )
    assert s.count(alt) == 1, "Fake.order_send"
    s = s.replace(
        alt,
        alt
        + "        if isinstance(request, dict) and request.get(\"reduce_only\"):" + NL
        + "            # D2: wie das echte Terminal -- ohne Treffer fuer das Ticket wird nichts" + NL
        + "            # gesendet, die Antwort lautet ``position_vanished``." + NL
        + '            gegen_long = request["side"] == "sell"' + NL
        + "            treffer = [" + NL
        + "                p" + NL
        + "                for p in self._positions" + NL
        + '                if p.ticket == request.get("position_ticket")' + NL
        + '                and p.symbol == request["symbol"]' + NL
        + "                and p.is_buy == gegen_long" + NL
        + "            ]" + NL
        + "            if not treffer:" + NL
        + "                return Mt5SendResult(" + NL
        + "                    accepted=False," + NL
        + "                    venue_order_id=None," + NL
        + '                    filled_volume=Decimal("0"),' + NL
        + "                    average_price=None," + NL
        + "                    ts=TS," + NL
        + '                    reason="position_vanished",' + NL
        + "                )" + NL,
    )
    t.write_text(s, encoding="utf-8", newline="")
    print("  gepatcht: tests/test_mt5_venue.py (Attrappe)")

    # --- reduce_only-Stellen in Tests: Ticket der Standardposition "t1" ------------------
    rx = re.compile(r"reduce_only=True(?=[,)\n\s])")
    gesamt = 0
    for rel in (
        "tests/test_mt5_venue.py",
        "tests/test_frische_am_orderpfad.py",
        "tests/test_idempotenz_am_broker.py",
        "tests/test_orderpfad_verdrahtung.py",
        "tests/test_private_sync.py",
        "tests/test_stufe10_betrieb.py",
        "tests/test_stufe4_risikokern.py",
    ):
        p = REPO / rel
        s = p.read_text(encoding="utf-8")
        s2, n = rx.subn('reduce_only=True, position_ticket="t1"', s)
        if n:
            p.write_text(s2, encoding="utf-8", newline="")
            gesamt += n
            print(f"  {rel}: {n} reduce_only-Stelle(n) mit Ticket")
    print(f"  Tests: {gesamt} Stellen; offen fuer andere Familien: tests/test_stufe5_ausfuehrung.py (1), mt5_trading_ai/venue/smoke.py (1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

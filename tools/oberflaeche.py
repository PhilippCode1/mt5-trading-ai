#!/usr/bin/env python3
"""Lesende Oberflaeche: der ganze Stand auf einer Seite, im Browser.

WAS SIE ZEIGT
-------------
Vier Dinge, die bisher nur im Terminal zu sehen waren:

1. **Konto und Verbindung** -- Equity, Marge, Demo-Wache, Frische-Latch.
2. **Offene Positionen** -- direkt vom Terminal, mit Stop, Alter und Ergebnis.
3. **Der laufende Betrieb** -- aus dem neuesten Journal: Takte, Eroeffnungen,
   Schliessungen mit Grund, und woran die abgelehnten Versuche scheiterten.
4. **Die Sperren** -- die letzte vollstaendige Checkliste der Orderkette,
   Naht fuer Naht.

Dazu die Marktseite: gemessener Spread je Instrument gegen den in
``config/broker_costs.json`` hinterlegten.

WAS SIE NICHT TUT
-----------------
Sie sendet nichts. ``RealMt5Terminal`` wird mit ``allow_write=False`` gebaut, und
das ist kein Schalter dieses Werkzeugs -- eine Seite zum Ansehen darf nicht
handeln koennen. Es gibt keinen Knopf, keine Formulare, keine Schreibpfade.

WARUM STANDARDBIBLIOTHEK
------------------------
Das Repo haelt seine Abhaengigkeiten knapp, und eine Oberflaeche ist kein Grund, ein
Webframework hereinzuholen. ``http.server`` genuegt fuer eine Seite, die auf dem eigenen
Rechner laeuft und alle paar Sekunden neu laedt.

Aufruf::

    python tools/oberflaeche.py              # http://127.0.0.1:8765
    python tools/oberflaeche.py --port 9000
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.kalender import SERVER_TZ_NAME  # noqa: E402
from mt5_trading_ai.costs.broker_costs import load_broker_costs  # noqa: E402
from mt5_trading_ai.execution.freshness import (  # noqa: E402
    MAX_SNAPSHOT_AGE,
    evaluate_account_freshness,
)
from mt5_trading_ai.venue.catalog import load_instrument_catalog  # noqa: E402
from mt5_trading_ai.venue.mt5 import Mt5Venue, RealMt5Terminal  # noqa: E402
from mt5_trading_ai.venue.protocol import VenueError  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
JOURNALE = REPO / "betrieb"
NEULADEN = 10  # Sekunden


# --------------------------------------------------------------------------
# Daten sammeln
# --------------------------------------------------------------------------
def _journal() -> tuple[Path | None, list[dict[str, Any]]]:
    if not JOURNALE.is_dir():
        return None, []
    dateien = sorted(JOURNALE.glob("journal-*.jsonl"))
    if not dateien:
        return None, []
    pfad = dateien[-1]
    zeilen: list[dict[str, Any]] = []
    for roh in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
        roh = roh.strip()
        if not roh:
            continue
        try:
            zeilen.append(json.loads(roh))
        except json.JSONDecodeError:
            continue
    return pfad, zeilen


def _lage() -> dict[str, Any]:
    """Alles, was die Seite braucht. Fehler werden gemeldet, nicht verschluckt."""
    stand: dict[str, Any] = {"jetzt": datetime.now(UTC), "fehler": None}
    pfad, zeilen = _journal()
    stand["journal_pfad"] = pfad
    stand["journal"] = zeilen

    terminal = RealMt5Terminal(allow_write=False, server_tz=SERVER_TZ_NAME)
    if not terminal.initialize():
        stand["fehler"] = "MT5-Terminal nicht erreichbar."
        return stand
    try:
        venue = Mt5Venue(
            name="oberflaeche", terminal=terminal,
            catalog=load_instrument_catalog(),
        )
        venue.connect()
        stand["konto"] = venue.get_account()
        stand["positionen"] = venue.get_positions()
        kosten = load_broker_costs()
        preise: list[dict[str, Any]] = []
        for symbol in sorted(load_instrument_catalog()):
            try:
                q = venue.get_quote(symbol)
            except VenueError as exc:
                preise.append({"symbol": symbol, "fehler": str(exc)})
                continue
            mitte = (q.bid + q.ask) / 2
            gemessen = (q.ask - q.bid) / mitte * Decimal("10000") if mitte > 0 else None
            modell = None
            for broker in kosten.brokers.values():
                zeile = broker.instruments.get(symbol)
                if zeile is None or not zeile.available or zeile.spread_price is None:
                    continue
                wert = zeile.spread_price / mitte * Decimal("10000")
                if modell is None or wert < modell:
                    modell = wert
            preise.append({"symbol": symbol, "bid": q.bid, "ask": q.ask,
                           "gemessen": gemessen, "modell": modell, "ts": q.ts})
        stand["preise"] = preise
    except VenueError as exc:
        stand["fehler"] = str(exc)
    finally:
        terminal.shutdown()
    return stand


# --------------------------------------------------------------------------
# Seite bauen
# --------------------------------------------------------------------------
def _e(wert: Any) -> str:
    return html.escape("—" if wert is None else str(wert))


def _zahl(wert: Any, stellen: int = 2) -> str:
    if wert is None:
        return "—"
    try:
        return f"{float(wert):,.{stellen}f}".replace(",", " ")
    except (TypeError, ValueError):
        return _e(wert)


def _abschnitt_konto(stand: dict[str, Any]) -> str:
    konto = stand.get("konto")
    if konto is None:
        return "<p class='leer'>Kein Kontostand — Terminal nicht erreichbar.</p>"
    jetzt = stand["jetzt"]
    # Gemessen wird die Frische des juengsten KURSSTEMPELS, nicht die des
    # Kontoschnappschusses. Zwei Gruende:
    #   * MetaTrader liefert ueberhaupt keinen Kontozeitstempel; ``account()`` setzt
    #     ihn selbst auf ``datetime.now(UTC)``. Ihn zu pruefen hiesse, die eigene Uhr
    #     gegen die eigene Uhr zu halten.
    #   * Die erste Fassung dieser Kachel tat genau das -- ``snapshot_ts=jetzt,
    #     now=jetzt``. Das Alter war per Konstruktion null, und die Kachel stand IMMER
    #     auf gruen. Eine Sicherheitsanzeige, die nicht rot werden kann, ist schlimmer
    #     als keine.
    # Der Kursstempel kommt vom Broker und ist damit ein echtes Lebenszeichen.
    stempel = [p["ts"] for p in (stand.get("preise") or []) if p.get("ts")]
    juengster = max(stempel) if stempel else None
    frische = evaluate_account_freshness(
        snapshot_ts=juengster or jetzt - timedelta(days=1), now=jetzt,
        connected=juengster is not None,
        max_age=MAX_SNAPSHOT_AGE, future_tolerance=timedelta(seconds=1),
    )
    demo = "Demokonto" if konto.is_demo else "LIVE-KONTO"
    klasse = "gut" if konto.is_demo else "krit"
    return f"""
    <div class="kacheln">
      <div class="kachel"><span class="etikett">Equity</span>
        <span class="wert">{_zahl(konto.equity)} {_e(konto.currency)}</span></div>
      <div class="kachel"><span class="etikett">Freie Marge</span>
        <span class="wert">{_zahl(konto.margin_free)}</span></div>
      <div class="kachel"><span class="etikett">Belegt</span>
        <span class="wert">{_zahl(konto.margin_used)}</span></div>
      <div class="kachel"><span class="etikett">Konto</span>
        <span class="wert {klasse}">{demo}</span>
        <span class="klein">{_e(konto.account_id)}</span></div>
      <div class="kachel"><span class="etikett">Kursfrische</span>
        <span class="wert {'gut' if frische.evaluable else 'krit'}">
          {'ok' if frische.evaluable else _e(frische.reason)}</span>
        <span class="klein">{frische.age.total_seconds():.1f} s alt ·
          Grenze {frische.max_age.total_seconds():.0f} s</span></div>
      <div class="kachel"><span class="etikett">Serverzeit</span>
        <span class="wert">{_e(SERVER_TZ_NAME)}</span>
        <span class="klein">gemessen, gedreht</span></div>
    </div>"""


def _abschnitt_positionen(stand: dict[str, Any]) -> str:
    pos = stand.get("positionen") or ()
    if not pos:
        return "<p class='leer'>Keine offenen Positionen. Das Konto ist flach.</p>"
    jetzt = stand["jetzt"]
    zeilen = []
    for p in pos:
        alter = (jetzt - p.opened_at).total_seconds() / 3600
        pnl = float(p.unrealised_pnl)
        zeilen.append(f"""
        <tr><td class="mono">{_e(p.symbol)}</td>
            <td>{_e(p.side.value.upper())}</td>
            <td class="zahl">{_zahl(p.volume, 2)}</td>
            <td class="zahl mono">{_e(p.entry_price)}</td>
            <td class="zahl mono">{_e(p.stop_loss)}</td>
            <td class="zahl">{alter:.2f} h</td>
            <td class="zahl {'gut' if pnl >= 0 else 'krit'}">{pnl:+.2f}</td></tr>""")
    return f"""
    <table><thead><tr><th>Instrument</th><th>Seite</th><th class="zahl">Volumen</th>
      <th class="zahl">Einstieg</th><th class="zahl">Stop</th>
      <th class="zahl">Alter</th>
      <th class="zahl">Ergebnis</th></tr></thead>
      <tbody>{''.join(zeilen)}</tbody></table>"""


def _abschnitt_lauf(stand: dict[str, Any]) -> str:
    zeilen = stand.get("journal") or []
    if not zeilen:
        return ("<p class='leer'>Kein Journal gefunden. "
                "Es läuft gerade kein Betrieb.</p>")
    nach_art: dict[str, list[dict[str, Any]]] = {}
    for z in zeilen:
        nach_art.setdefault(str(z.get("art")), []).append(z)
    start = (nach_art.get("start") or [{}])[0]
    ende = nach_art.get("ende") or []
    takte = nach_art.get("takt", [])
    versuche = nach_art.get("eroeffnungsversuch", [])
    auf = [v for v in versuche if v.get("eroeffnet")]
    zu = nach_art.get("geschlossen", [])
    halts = [t for t in takte if t.get("halt")]
    laeuft = not ende

    gruende: dict[str, int] = {}
    for v in versuche:
        if v.get("eroeffnet"):
            continue
        letzte = next(
            (s["naht"] for s in reversed(v.get("schritte") or []) if not s["ok"]),
            str(v.get("grund") or "?"),
        )
        schluessel = f"{letzte} — {v.get('grund')}"
        gruende[schluessel] = gruende.get(schluessel, 0) + 1
    grundzeilen = "".join(
        f"<tr><td class='zahl'>{n}×</td><td class='mono'>{_e(g)}</td></tr>"
        for g, n in sorted(gruende.items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2' class='leer'>keine Ablehnungen</td></tr>"

    zugruende: dict[str, int] = {}
    for z in zu:
        g = str(z.get("grund"))
        zugruende[g] = zugruende.get(g, 0) + 1
    zuzeilen = "".join(
        f"<tr><td class='zahl'>{n}×</td><td class='mono'>{_e(g)}</td></tr>"
        for g, n in sorted(zugruende.items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2' class='leer'>noch keine Schließung</td></tr>"

    zustand = ("<span class='marke gut'>läuft</span>" if laeuft
               else "<span class='marke'>beendet</span>")
    scharf = ("<span class='marke krit'>scharf</span>" if start.get("scharf")
              else "<span class='marke'>trocken</span>")
    return f"""
    <p>{zustand} {scharf}
      <span class="klein">Strategie {_e(start.get('strategie'))} ·
      Journal <span class="mono">{_e(stand['journal_pfad'].name
        if stand.get('journal_pfad') else '—')}</span></span></p>
    <div class="kacheln">
      <div class="kachel"><span class="etikett">Takte</span>
        <span class="wert">{len(takte)}</span></div>
      <div class="kachel"><span class="etikett">Eröffnet</span>
        <span class="wert gut">{len(auf)}</span>
        <span class="klein">von {len(versuche)} Versuchen</span></div>
      <div class="kachel"><span class="etikett">Geschlossen</span>
        <span class="wert">{len(zu)}</span></div>
      <div class="kachel"><span class="etikett">Takte im Halt</span>
        <span class="wert {'krit' if halts else 'gut'}">{len(halts)}</span></div>
    </div>
    <div class="zweispaltig">
      <div><h3>Woran Eröffnungen scheiterten</h3>
        <table><tbody>{grundzeilen}</tbody></table></div>
      <div><h3>Warum geschlossen wurde</h3>
        <table><tbody>{zuzeilen}</tbody></table></div>
    </div>"""


def _abschnitt_sperren(stand: dict[str, Any]) -> str:
    """Die letzte vollstaendige Checkliste -- die Kette, Naht fuer Naht."""
    zeilen = stand.get("journal") or []
    letzte = None
    for z in reversed(zeilen):
        if z.get("art") == "eroeffnungsversuch" and z.get("schritte"):
            letzte = z
            break
    if letzte is None:
        return "<p class='leer'>Noch kein Durchlauf der Orderkette im Journal.</p>"
    schritte = "".join(
        f"""<tr><td class="marke {'gut' if s['ok'] else 'krit'}">
              {'OK' if s['ok'] else 'HALT'}</td>
            <td class="mono">{_e(s['naht'])}</td>
            <td class="klein">{_e(s.get('detail'))}</td></tr>"""
        for s in letzte["schritte"]
    )
    kopf = (f"{_e(letzte.get('symbol'))} · {_e(letzte.get('signal'))} · "
            f"{_e(letzte.get('ts'))}")
    ergebnis = ("<span class='marke gut'>eröffnet</span>" if letzte.get("eroeffnet")
                else f"<span class='marke krit'>{_e(letzte.get('grund'))}</span>")
    return f"""<p class="klein">{kopf} {ergebnis}</p>
    <table><tbody>{schritte}</tbody></table>"""


def _abschnitt_preise(stand: dict[str, Any]) -> str:
    preise = stand.get("preise") or []
    if not preise:
        return "<p class='leer'>Keine Kurse.</p>"
    zeilen = []
    for p in preise:
        if p.get("fehler"):
            zeilen.append(f"""<tr><td class="mono">{_e(p['symbol'])}</td>
              <td colspan="4" class="klein">{_e(p['fehler'])}</td></tr>""")
            continue
        g, m = p.get("gemessen"), p.get("modell")
        if m is not None and g is not None and m > 0:
            faktor = float(g) / float(m)
            urteil = (f"<span class='{'gut' if faktor <= 1.2 else 'warn'}'>"
                      f"{faktor:.1f}× Modell</span>")
        else:
            urteil = "<span class='klein'>keine Kostenzeile</span>"
        zeilen.append(f"""<tr><td class="mono">{_e(p['symbol'])}</td>
          <td class="zahl mono">{_e(p['bid'])}</td>
          <td class="zahl mono">{_e(p['ask'])}</td>
          <td class="zahl">{_zahl(g)}</td>
          <td class="zahl">{_zahl(m)}</td><td>{urteil}</td></tr>""")
    return f"""<table><thead><tr><th>Instrument</th><th class="zahl">Bid</th>
      <th class="zahl">Ask</th><th class="zahl">Spread bp</th>
      <th class="zahl">Modell bp</th><th>Bewertung</th></tr></thead>
      <tbody>{''.join(zeilen)}</tbody></table>"""


STIL = """
:root{--grund:#f6f8f4;--feld:#fff;--feld2:#f0f4ee;--tinte:#12201a;--matt:#5e6e64;
--haar:#dce5dc;--gut:#166c3b;--warn:#9c6a12;--krit:#a63a28;
--mono:ui-monospace,"Cascadia Code","SF Mono",Menlo,Consolas,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,sans-serif}
@media (prefers-color-scheme:dark){:root{--grund:#0d130f;--feld:#141c16;--feld2:#101711;
--tinte:#e6efe8;--matt:#93a599;--haar:#243027;--gut:#4ec97e;--warn:#d9a441;--krit:#e2705c}}
*{box-sizing:border-box}
body{margin:0;background:var(--grund);color:var(--tinte);font-family:var(--sans);
line-height:1.5;padding:1.5rem}
.huelle{max-width:1180px;margin:0 auto}
h1{font-size:1.4rem;margin:0 0 .2rem}
h2{font-size:1.05rem;margin:2rem 0 .6rem;padding-bottom:.3rem;
border-bottom:1px solid var(--haar)}
h3{font-size:.85rem;margin:.8rem 0 .4rem;color:var(--matt);font-weight:600}
.kopfzeile{color:var(--matt);font-size:.85rem;margin-bottom:.4rem}
.kacheln{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem}
.kachel{background:var(--feld);border:1px solid var(--haar);border-radius:8px;
padding:.7rem .8rem;display:flex;flex-direction:column;gap:.15rem}
.etikett{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:var(--matt)}
.wert{font-size:1.15rem;font-weight:600;font-variant-numeric:tabular-nums}
.klein{font-size:.75rem;color:var(--matt)}
table{width:100%;border-collapse:collapse;background:var(--feld);
border:1px solid var(--haar);border-radius:8px;overflow:hidden;font-size:.85rem}
th{text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;
color:var(--matt);padding:.5rem .7rem;background:var(--feld2);font-weight:600}
td{padding:.45rem .7rem;border-top:1px solid var(--haar)}
.zahl{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:var(--mono);font-size:.82rem}
.gut{color:var(--gut)}.warn{color:var(--warn)}.krit{color:var(--krit)}
.marke{display:inline-block;padding:.05rem .45rem;border-radius:99px;font-size:.7rem;
font-weight:600;background:var(--feld2);border:1px solid var(--haar)}
.marke.gut{color:var(--gut)}.marke.krit{color:var(--krit)}
.leer{color:var(--matt);font-size:.85rem;padding:.6rem 0}
.zweispaltig{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
gap:1rem}
.hinweis{background:var(--feld2);border:1px solid var(--haar);border-left:3px solid
var(--warn);border-radius:6px;padding:.7rem .9rem;font-size:.83rem;margin:1rem 0}
.fuss{margin-top:2rem;padding-top:.8rem;border-top:1px solid var(--haar);
color:var(--matt);font-size:.75rem}
"""


def seite(stand: dict[str, Any]) -> str:
    fehler = stand.get("fehler")
    warnung = (f"<div class='hinweis'><b>Terminal:</b> {_e(fehler)}</div>"
               if fehler else "")
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{NEULADEN}">
<title>MT5 Trading AI — Stand</title><style>{STIL}</style></head><body>
<div class="huelle">
  <h1>MT5 Trading AI — Stand</h1>
  <p class="kopfzeile">{stand['jetzt']:%Y-%m-%d %H:%M:%S} UTC ·
    lädt alle {NEULADEN} s neu · <b>nur lesend</b>, diese Seite kann nicht handeln</p>
  {warnung}
  <div class="hinweis">
    <b>Keine zugelassene Strategie.</b> Sieben Ereignisstudien haben keine tragfähige
    Zwangslage gefunden; größter Bruttoeffekt 1,36 bp gegen 5,51 bp nötig. Was hier
    läuft, prüft die <i>Maschine</i>, nicht einen Vorteil.
    Urteil: <span class="mono">ABSCHLUSS-3a/05-URTEIL.md</span>
  </div>
  <h2>Konto und Verbindung</h2>{_abschnitt_konto(stand)}
  <h2>Offene Positionen</h2>{_abschnitt_positionen(stand)}
  <h2>Der laufende Betrieb</h2>{_abschnitt_lauf(stand)}
  <h2>Die Orderkette, Naht für Naht</h2>{_abschnitt_sperren(stand)}
  <h2>Kurse gegen Kostenmodell</h2>{_abschnitt_preise(stand)}
  <p class="fuss">Gebaut aus der Standardbibliothek, ohne Webframework.
    Das Terminal wird mit <span class="mono">allow_write=False</span> geöffnet —
    das ist kein Schalter dieses Werkzeugs.</p>
</div></body></html>"""


class Griff(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        try:
            inhalt = seite(_lage()).encode("utf-8")
        except Exception as exc:  # noqa: BLE001 - die Seite soll den Fehler zeigen
            inhalt = (f"<!doctype html><meta charset='utf-8'>"
                      f"<pre>Fehler beim Bauen der Seite:\n{html.escape(str(exc))}"
                      f"</pre>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(inhalt)))
        self.end_headers()
        self.wfile.write(inhalt)

    def log_message(self, *_args: Any) -> None:
        """Still. Jede Anfrage zu protokollieren macht die Konsole unlesbar."""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Lesende Oberflaeche (nur lokal)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--kein-browser", action="store_true")
    args = ap.parse_args()
    # Bewusst nur 127.0.0.1: die Seite zeigt Kontostand und Positionen und hat im
    # Netz nichts verloren.
    adresse = ("127.0.0.1", args.port)
    server = HTTPServer(adresse, Griff)
    url = f"http://{adresse[0]}:{adresse[1]}/"
    print(f"Oberflaeche laeuft: {url}")
    print("Nur lesend. Beenden mit Strg-C.")
    if not args.kein_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

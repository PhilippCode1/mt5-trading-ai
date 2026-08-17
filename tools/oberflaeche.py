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
import sys
import threading
import time
import webbrowser
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5_trading_ai.backtest.kalender import SERVER_TZ_NAME  # noqa: E402
from mt5_trading_ai.betrieb.journal import (  # noqa: E402
    JournalError,
    Lauf,
    durchgehende_equity,
    lies_alle,
)
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
def _neuester_lauf() -> Lauf | None:
    """Der zuletzt begonnene Lauf -- gelesen ueber den gemeinsamen Journal-Leser.

    Frueher parste diese Datei das Journal selbst und uebersprang unlesbare Zeilen
    stillschweigend. Der Leser in ``mt5_trading_ai/betrieb/journal.py`` ist getestet
    und meldet einen Defekt, statt ihn zu verschlucken.
    """
    laeufe = lies_alle(JOURNALE)
    if not laeufe:
        return None
    # Der LAUFENDE Lauf schlaegt den zuletzt begonnenen. Ein kurzer Testlauf nach dem
    # Start des Dauerbetriebs waere sonst der neueste, und die Seite zeigte einen
    # Lauf mit einem einzigen Takt statt des Betriebs, der gerade handelt.
    offen = [lauf for lauf in laeufe if not lauf.beendet]
    return offen[-1] if offen else laeufe[-1]


def _lage(venue: Mt5Venue) -> dict[str, Any]:
    """Alles, was die Seite braucht. Fehler werden gemeldet, nicht verschluckt.

    Nimmt ein **offenes** Venue entgegen. Frueher baute diese Funktion bei jedem
    Seitenaufruf eine neue Terminalsitzung auf und wieder ab -- gemessen 99 bis 136 ms
    je Aufruf, alle zehn Sekunden, dauerhaft. Die Sitzung haelt jetzt der
    :class:`Sammler`.
    """
    stand: dict[str, Any] = {"jetzt": datetime.now(UTC), "fehler": None}
    try:
        stand["lauf"] = _neuester_lauf()
    except JournalError as exc:
        stand["lauf"] = None
        stand["journalfehler"] = str(exc)
    stand["alle_laeufe"] = lies_alle(JOURNALE) if stand.get("lauf") else []
    try:
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
    return stand


class Sammler:
    """Haelt die Terminalsitzung offen und sammelt im Hintergrund.

    Ein Hintergrundfaden ist hier **die einzige Stelle**, die MetaTrader anfasst. Die
    Anfragen des Webservers lesen nur den letzten Schnappschuss unter einer Sperre.
    Das ist kein Geschwindigkeitstrick, sondern eine Notwendigkeit: die
    MetaTrader5-Bindung haelt eine Prozessverbindung, und sie aus mehreren Faeden zu
    bedienen waere ein Wettlauf.

    Faellt die Verbindung aus, bleibt der letzte Schnappschuss stehen und traegt sein
    Alter. Die Seite zeigt dann sichtbar veraltete Zahlen statt gar keine -- **und sie
    sagt, dass sie veraltet sind**. Eine Anzeige, die stillschweigend einfriert, ist
    gefaehrlicher als eine leere.
    """

    def __init__(self, *, takt: float) -> None:
        self._takt = takt
        self._sperre = threading.Lock()
        self._stand: dict[str, Any] | None = None
        self._gebaut: datetime | None = None
        self._dauer_ms = 0.0
        self._terminal: RealMt5Terminal | None = None
        self._venue: Mt5Venue | None = None
        self._aus = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._schleife, daemon=True).start()

    def stoppen(self) -> None:
        self._aus.set()

    def hole(self) -> tuple[dict[str, Any] | None, datetime | None, float]:
        with self._sperre:
            return self._stand, self._gebaut, self._dauer_ms

    def _verbinden(self) -> bool:
        if self._venue is not None and self._venue.is_healthy():
            return True
        if self._terminal is not None:
            try:
                self._terminal.shutdown()
            except Exception:  # noqa: BLE001 - Aufraeumen darf nichts werfen
                pass
        self._terminal = RealMt5Terminal(allow_write=False, server_tz=SERVER_TZ_NAME)
        if not self._terminal.initialize():
            self._venue = None
            return False
        self._venue = Mt5Venue(
            name="oberflaeche", terminal=self._terminal,
            catalog=load_instrument_catalog(),
        )
        self._venue.connect()
        return True

    def _schleife(self) -> None:
        while not self._aus.is_set():
            t0 = time.perf_counter()
            if not self._verbinden():
                with self._sperre:
                    if self._stand is None:
                        self._stand = {"jetzt": datetime.now(UTC),
                                       "fehler": "MT5-Terminal nicht erreichbar.",
                                       "lauf": None, "alle_laeufe": []}
                    else:
                        self._stand["fehler"] = "MT5-Terminal nicht erreichbar."
                self._aus.wait(self._takt)
                continue
            assert self._venue is not None
            try:
                stand = _lage(self._venue)
            except Exception as exc:  # noqa: BLE001 - der Faden darf nie sterben
                stand = {"jetzt": datetime.now(UTC), "fehler": str(exc),
                         "lauf": None, "alle_laeufe": []}
            with self._sperre:
                self._stand = stand
                self._gebaut = datetime.now(UTC)
                self._dauer_ms = (time.perf_counter() - t0) * 1000
            self._aus.wait(self._takt)


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


def _linienzug(
    punkte: list[tuple[datetime, Decimal]], *, titel: str, einheit: str = "",
    breite: int = 560, hoehe: int = 150,
) -> str:
    """Ein Linienzug als Inline-SVG. Ohne JavaScript, ohne Bibliothek.

    Serverseitig erzeugtes SVG reicht fuer alles, was diese Seite zeigen soll, und
    haelt die Abhaengigkeitsliste des Repos leer. Gemessen: rund 13 Zeichen je Punkt,
    also 1,7 KB fuer 70 Punkte -- bei zehn Sekunden Neuladeintervall unerheblich.

    Die Farben kommen aus den CSS-Variablen des Seitenstils, damit der Dunkelmodus
    ohne Zutun stimmt.
    """
    if len(punkte) < 2:
        return (f"<div class='diagramm'><h3>{_e(titel)}</h3>"
                f"<p class='leer'>Zu wenige Messpunkte ({len(punkte)}).</p></div>")
    rand_l, rand_r, rand_o, rand_u = 58, 8, 14, 20
    innen_b, innen_h = breite - rand_l - rand_r, hoehe - rand_o - rand_u
    werte = [float(w) for _, w in punkte]
    tiefe, hoch = min(werte), max(werte)
    spanne = hoch - tiefe or 1.0
    # Etwas Luft, damit die Linie nicht am Rand klebt.
    tiefe, hoch = tiefe - spanne * 0.08, hoch + spanne * 0.08
    spanne = hoch - tiefe

    def x(i: int) -> float:
        return rand_l + innen_b * i / (len(punkte) - 1)

    def y(wert: float) -> float:
        return rand_o + innen_h * (1 - (wert - tiefe) / spanne)

    gitter = []
    for anteil in (0.0, 0.5, 1.0):
        wert = tiefe + spanne * anteil
        yy = y(wert)
        gitter.append(
            f'<line x1="{rand_l}" y1="{yy:.1f}" x2="{breite - rand_r}" y2="{yy:.1f}" '
            f'stroke="var(--haar)" stroke-width="1"/>'
            f'<text x="{rand_l - 6}" y="{yy + 3:.1f}" text-anchor="end" '
            f'font-size="9" fill="var(--matt)">{wert:,.2f}</text>'.replace(",", " ")
        )
    linie = " ".join(f"{x(i):.1f},{y(w):.1f}" for i, w in enumerate(werte))
    farbe = "var(--gut)" if werte[-1] >= werte[0] else "var(--krit)"
    von, bis = punkte[0][0], punkte[-1][0]
    return f"""<div class="diagramm">
      <h3>{_e(titel)} <span class="klein">{len(punkte)} Punkte ·
        {werte[0]:,.2f} → {werte[-1]:,.2f} {_e(einheit)}</span></h3>
      <svg viewBox="0 0 {breite} {hoehe}" width="100%" height="{hoehe}"
           role="img" aria-label="{_e(titel)}">
        {''.join(gitter)}
        <polyline points="{linie}" fill="none" stroke="{farbe}" stroke-width="1.6"
                  stroke-linejoin="round"/>
        <text x="{rand_l}" y="{hoehe - 5}" font-size="9" fill="var(--matt)">
          {von:%H:%M}</text>
        <text x="{breite - rand_r}" y="{hoehe - 5}" font-size="9" text-anchor="end"
              fill="var(--matt)">{bis:%H:%M} UTC</text>
      </svg>
    </div>""".replace(",", " ")


def _kennzahlen(stand: dict[str, Any]) -> str:
    """Was aus dem Journal rechenbar ist und bisher nur darin lag.

    Alle vier Zahlen folgen aus dem erweiterten Protokoll. Sie standen schon in den
    Daten und wurden nur nicht gezeigt -- was der haeufigste Grund ist, warum eine
    Anzeige duenn wirkt.
    """
    lauf: Lauf | None = stand.get("lauf")
    if lauf is None:
        return ""
    reihe = lauf.equity_reihe()
    takte = lauf.art("takt")
    trades = [t for t in lauf.trades() if not t.offen]
    rechenbar = [t.ergebnis_bps for t in trades if t.ergebnis_bps is not None]

    # Drawdown seit Laufbeginn: groesster Ruecksetzer vom laufenden Hoechststand.
    tiefster = Decimal("0")
    spitze: Decimal | None = None
    for _, wert in reihe:
        spitze = wert if spitze is None or wert > spitze else spitze
        if spitze > 0:
            tiefster = min(tiefster, (wert - spitze) / spitze * Decimal("100"))
    im_halt = sum(1 for t in takte if t["halt"])
    halt_anteil = im_halt / len(takte) * 100 if takte else 0.0
    treffer = (sum(1 for w in rechenbar if w > 0) / len(rechenbar) * 100
               if rechenbar else None)
    schlimmster = min(rechenbar) if rechenbar else None

    def kachel(etikett: str, wert: str, klein: str, klasse: str = "") -> str:
        return (f'<div class="kachel"><span class="etikett">{etikett}</span>'
                f'<span class="wert {klasse}">{wert}</span>'
                f'<span class="klein">{klein}</span></div>')

    return "<div class='kacheln'>" + "".join([
        kachel("Drawdown", f"{float(tiefster):.3f} %",
               "groesster Ruecksetzer seit Laufbeginn",
               "krit" if tiefster < -1 else ""),
        kachel("Zeit im Halt", f"{halt_anteil:.0f} %",
               f"von {len(takte)} Takten", "krit" if halt_anteil > 0 else "gut"),
        kachel("Trefferanteil",
               "—" if treffer is None else f"{treffer:.0f} %",
               f"aus {len(rechenbar)} rechenbaren Trades"),
        kachel("Schlechtester Trade",
               "—" if schlimmster is None else f"{float(schlimmster):+.2f} bp",
               "Preisdifferenz, ohne Kosten",
               "krit" if schlimmster is not None and schlimmster < 0 else ""),
    ]) + "</div>"


def _abschnitt_verlauf(stand: dict[str, Any]) -> str:
    lauf: Lauf | None = stand.get("lauf")
    if lauf is None:
        return "<p class='leer'>Kein Journal.</p>"
    teile = [_linienzug(lauf.equity_reihe(), titel="Equity, dieser Lauf",
                        einheit="EUR")]
    alle = stand.get("alle_laeufe") or []
    if len(alle) > 1:
        ueber = [(ts, wert) for ts, wert, _ in durchgehende_equity(alle)]
        luecken = sum(1 for _, _, lk in durchgehende_equity(alle) if lk)
        teile.append(_linienzug(
            ueber, titel=f"Equity, alle {len(alle)} Läufe", einheit="EUR"))
        teile.append(
            f"<p class='klein'>{luecken} Lücken zwischen den Läufen. Dort lief die "
            "Schleife nicht — was in der Pause geschah, steht in keinem Journal.</p>"
        )
    for symbol in lauf.symbole_mit_kursen()[:2]:
        teile.append(_linienzug(lauf.kurs_reihe(symbol), titel=f"Kurs {symbol}"))
    return f"<div class='zweispaltig'>{''.join(teile)}</div>"


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
    lauf: Lauf | None = stand.get("lauf")
    if lauf is None:
        return "<p class='leer'>Kein Journal gefunden.</p>"
    takte = lauf.art("takt")
    versuche = lauf.art("eroeffnungsversuch")
    auf = [v for v in versuche if v["eroeffnet"]]
    trades = lauf.trades()
    zu = [t for t in trades if not t.offen]
    halts = [t for t in takte if t["halt"]]

    gruende: dict[str, int] = {}
    for v in versuche:
        if v["eroeffnet"]:
            continue
        letzte = next(
            (x["naht"] for x in reversed(v["schritte"] or []) if not x["ok"]),
            str(v["grund"] or "?"),
        )
        schluessel = f"{letzte} — {v['grund']}"
        gruende[schluessel] = gruende.get(schluessel, 0) + 1
    grundzeilen = "".join(
        f"<tr><td class='zahl'>{n}×</td><td class='mono'>{_e(g)}</td></tr>"
        for g, n in sorted(gruende.items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2' class='leer'>keine Ablehnungen</td></tr>"

    zugruende: dict[str, int] = {}
    for t in zu:
        zugruende[str(t.grund)] = zugruende.get(str(t.grund), 0) + 1
    zuzeilen = "".join(
        f"<tr><td class='zahl'>{n}×</td><td class='mono'>{_e(g)}</td></tr>"
        for g, n in sorted(zugruende.items(), key=lambda x: -x[1])
    ) or "<tr><td colspan='2' class='leer'>noch keine Schließung</td></tr>"

    start = lauf.start
    zustand = ("<span class='marke'>beendet</span>" if lauf.beendet
               else "<span class='marke gut'>läuft</span>")
    scharf = ("<span class='marke krit'>scharf</span>" if lauf.scharf
              else "<span class='marke'>trocken</span>")
    rechenbar = sum(1 for t in zu if t.vollstaendig)
    return f"""
    <p>{zustand} {scharf}
      <span class="klein">Strategie {_e(start['strategie'] if start else None)} ·
      Codestand <span class="mono">{_e(lauf.version)}</span> ·
      Journal <span class="mono">{_e(lauf.pfad.name)}</span></span></p>
    <div class="kacheln">
      <div class="kachel"><span class="etikett">Takte</span>
        <span class="wert">{len(takte)}</span></div>
      <div class="kachel"><span class="etikett">Eröffnet</span>
        <span class="wert gut">{len(auf)}</span>
        <span class="klein">von {len(versuche)} Versuchen</span></div>
      <div class="kachel"><span class="etikett">Trades zu</span>
        <span class="wert">{len(zu)}</span>
        <span class="klein">{rechenbar} rechenbar</span></div>
      <div class="kachel"><span class="etikett">Takte im Halt</span>
        <span class="wert {'krit' if halts else 'gut'}">{len(halts)}</span></div>
    </div>
    <div class="zweispaltig">
      <div><h3>Woran Eröffnungen scheiterten</h3>
        <table><tbody>{grundzeilen}</tbody></table></div>
      <div><h3>Warum geschlossen wurde</h3>
        <table><tbody>{zuzeilen}</tbody></table></div>
    </div>
    {_abschnitt_trades(trades)}"""


def _abschnitt_trades(trades: list[Any]) -> str:
    if not trades:
        return ""
    zeilen = []
    for t in trades[-10:]:
        erg = t.ergebnis_bps
        if erg is None:
            ergtext = "<span class='klein'>unvollständig</span>"
        else:
            ergtext = (f"<span class='{'gut' if erg >= 0 else 'krit'}'>"
                       f"{float(erg):+.2f} bp</span>")
        dauer = t.dauer_stunden
        zeilen.append(f"""<tr><td class="mono">{_e(t.symbol)}</td>
          <td>{'BUY' if t.ist_kauf else 'SELL'}</td>
          <td class="zahl">{_zahl(t.volumen)}</td>
          <td class="zahl mono">{_e(t.einstieg)}</td>
          <td class="zahl mono">{_e(t.ausstieg)}</td>
          <td class="zahl">{'offen' if dauer is None else f'{dauer:.2f} h'}</td>
          <td class="klein">{_e(t.grund)}</td>
          <td class="zahl">{ergtext}</td></tr>""")
    return f"""<h3>Die letzten Trades</h3>
    <table><thead><tr><th>Instrument</th><th>Seite</th><th class="zahl">Volumen</th>
      <th class="zahl">Einstieg</th><th class="zahl">Ausstieg</th>
      <th class="zahl">Dauer</th><th>Grund</th>
      <th class="zahl">Ergebnis</th></tr></thead>
      <tbody>{''.join(zeilen)}</tbody></table>
    <p class="klein">Das Ergebnis rechnet die Preisdifferenz — <b>ohne</b> Kommission
      und Swap. „Unvollständig“ heißt, dass ein Preis fehlt; es heißt nicht null.</p>"""


def _abschnitt_sperren(stand: dict[str, Any]) -> str:
    """Die letzte vollstaendige Checkliste -- die Kette, Naht fuer Naht."""
    lauf: Lauf | None = stand.get("lauf")
    if lauf is None:
        return "<p class='leer'>Kein Journal.</p>"
    letzte = next(
        (s for s in reversed(lauf.saetze)
         if s.art == "eroeffnungsversuch" and s["schritte"]), None
    )
    if letzte is None:
        return "<p class='leer'>Noch kein Durchlauf der Orderkette im Journal.</p>"
    schritte = "".join(
        f"""<tr><td class="marke {'gut' if x['ok'] else 'krit'}">
              {'OK' if x['ok'] else 'HALT'}</td>
            <td class="mono">{_e(x['naht'])}</td>
            <td class="klein">{_e(x.get('detail'))}</td></tr>"""
        for x in letzte["schritte"]
    )
    ergebnis = ("<span class='marke gut'>eröffnet</span>" if letzte["eroeffnet"]
                else f"<span class='marke krit'>{_e(letzte['grund'])}</span>")
    return f"""<p class="klein">{_e(letzte['symbol'])} · {_e(letzte['signal'])} ·
      {letzte.ts:%H:%M:%S} UTC {ergebnis}</p>
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
.hinweis.krit-rand{border-left-color:var(--krit)}
table{display:block;overflow-x:auto;white-space:nowrap}
.diagramm{background:var(--feld);border:1px solid var(--haar);border-radius:8px;
padding:.7rem .8rem}
.diagramm h3{margin:0 0 .3rem}
.verbindung{color:var(--krit);font-size:.8rem;min-height:1rem;margin:0 0 .3rem}
.fuss{margin-top:2rem;padding-top:.8rem;border-top:1px solid var(--haar);
color:var(--matt);font-size:.75rem}
"""


def seite(stand: dict[str, Any], *, jetzt: datetime | None = None) -> str:
    """Das Inhaltsfragment. ``jetzt`` ist die RENDERZEIT, nicht die Sammelzeit.

    Der Unterschied ist der Punkt: das Alter eines Schnappschusses misst sich daran,
    wie lange er beim Ansehen schon liegt. Gegen seine eigene Entstehungszeit gerechnet
    waere es per Konstruktion null -- derselbe Fehler wie in der ersten Fassung der
    Frische-Kachel. Die Uhr wird hereingereicht, damit sie pruefbar bleibt.
    """
    # Jeder Defekt gehoert AUF die Seite. Der Journalfehler wurde bisher zwar
    # gefangen und abgelegt, aber nirgends gezeigt -- die Seite meldete dann
    # "Kein Journal gefunden", wo "defektes Journal" richtig gewesen waere. Eine
    # Oberflaeche, die einen Fehler in eine harmlose Leermeldung verwandelt, ist
    # schlimmer als eine, die abstuerzt: man sieht ihr nicht an, dass sie luegt.
    stoerungen = [
        (etikett, stand.get(schluessel))
        for etikett, schluessel in (("Terminal", "fehler"),
                                    ("Journal", "journalfehler"))
        if stand.get(schluessel)
    ]
    warnung = "".join(
        f"<div class='hinweis krit-rand'><b>{etikett}:</b> {_e(text)}</div>"
        for etikett, text in stoerungen
    )
    alter = ""
    if stand.get("gebaut") is not None:
        sekunden = ((jetzt or datetime.now(UTC)) - stand["gebaut"]).total_seconds()
        klasse = "krit" if sekunden > 30 else "klein"
        alter = (f' · Stand <span class="{klasse}">{sekunden:.0f} s alt</span>'
                 f' (gesammelt in {stand.get("dauer_ms", 0):.0f} ms)')
    return f"""
  <p class="kopfzeile">{stand['jetzt']:%Y-%m-%d %H:%M:%S} UTC{alter} ·
    <b>nur lesend</b>, diese Seite kann nicht handeln</p>
  {warnung}
  <div class="hinweis">
    <b>Keine zugelassene Strategie.</b> Sieben Ereignisstudien haben keine tragfähige
    Zwangslage gefunden; größter Bruttoeffekt 1,36 bp gegen 5,51 bp nötig. Was hier
    läuft, prüft die <i>Maschine</i>, nicht einen Vorteil.
    Urteil: <span class="mono">ABSCHLUSS-3a/05-URTEIL.md</span>
  </div>
  <h2>Konto und Verbindung</h2>{_abschnitt_konto(stand)}
  <h2>Offene Positionen</h2>{_abschnitt_positionen(stand)}
  <h2>Kennzahlen</h2>{_kennzahlen(stand)}
  <h2>Verlauf</h2>{_abschnitt_verlauf(stand)}
  <h2>Der laufende Betrieb</h2>{_abschnitt_lauf(stand)}
  <h2>Die Orderkette, Naht für Naht</h2>{_abschnitt_sperren(stand)}
  <h2>Kurse gegen Kostenmodell</h2>{_abschnitt_preise(stand)}
  <p class="fuss">Gebaut aus der Standardbibliothek, ohne Webframework.
    Das Terminal wird mit <span class="mono">allow_write=False</span> geöffnet —
    das ist kein Schalter dieses Werkzeugs.</p>"""


#: Der einzige Skriptteil dieser Seite. Kein Framework, keine Bibliothek, kein
#: Bauwerkzeug -- zwanzig Zeilen, die den INHALT nachladen statt der ganzen Seite.
#:
#: Das ``<meta refresh>`` davor lud alle zehn Sekunden alles neu: die Scrollposition
#: sprang, eine Textauswahl ging verloren, die Diagramme flackerten. Bei einer Seite,
#: die man nebenher offen hat, ist genau das der Unterschied zwischen brauchbar und
#: laestig.
#:
#: Ohne JavaScript bleibt die Seite lesbar -- sie aktualisiert dann nur nicht, und der
#: ``<noscript>``-Hinweis sagt das. Bei verdecktem Fenster wird nicht geholt: eine
#: Anzeige, die niemand ansieht, muss den Rechner nicht beschaeftigen.
SKRIPT = """
(function () {
  var ziel = document.getElementById('inhalt');
  var marke = document.getElementById('verbindung');
  var laeuft = false;
  function hole() {
    if (laeuft || document.hidden) { return; }
    laeuft = true;
    fetch('/inhalt', {cache: 'no-store'})
      .then(function (a) { if (!a.ok) { throw new Error(a.status); } return a.text(); })
      .then(function (t) { ziel.innerHTML = t; marke.textContent = ''; })
      .catch(function (e) {
        marke.textContent = 'Seite nicht erreichbar (' + e.message + ')';
      })
      .then(function () { laeuft = false; });
  }
  setInterval(hole, TAKT);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { hole(); }
  });
})();
"""


def huelle(inhalt: str) -> str:
    """Die Seite drumherum. Wird genau einmal geladen und danach nicht mehr."""
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MT5 Trading AI — Stand</title><style>{STIL}</style></head><body>
<div class="huelle">
  <h1>MT5 Trading AI — Stand</h1>
  <p id="verbindung" class="verbindung"></p>
  <noscript><div class="hinweis krit-rand">Ohne JavaScript aktualisiert sich diese
    Seite nicht von selbst. Zum Auffrischen neu laden.</div></noscript>
  <main id="inhalt">{inhalt}</main>
</div>
<script>{SKRIPT.replace("TAKT", str(NEULADEN * 1000))}</script>
</body></html>"""


class Griff(BaseHTTPRequestHandler):
    """Zwei Wege: die Huelle einmal, den Inhalt so oft man will."""

    sammler: Sammler

    def _inhalt(self) -> str:
        stand, gebaut, dauer = self.sammler.hole()
        if stand is None:
            return ("<p class='leer'>Noch kein Schnappschuss — der Sammler "
                    "verbindet sich gerade.</p>")
        kopie = dict(stand)
        kopie["gebaut"] = gebaut
        kopie["dauer_ms"] = dauer
        return seite(kopie)

    def do_GET(self) -> None:  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        weg = self.path.split("?")[0]
        if weg not in ("/", "/index.html", "/inhalt"):
            self.send_error(404)
            return
        try:
            text = self._inhalt()
            roh = (text if weg == "/inhalt" else huelle(text)).encode("utf-8")
        except Exception as exc:  # noqa: BLE001 - die Seite soll den Fehler zeigen
            roh = (f"<div class='hinweis krit-rand'>Fehler beim Bauen der Seite: "
                   f"{html.escape(str(exc))}</div>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(roh)))
        self.end_headers()
        self.wfile.write(roh)

    def log_message(self, *_args: Any) -> None:
        """Still. Jede Anfrage zu protokollieren macht die Konsole unlesbar."""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Lesende Oberflaeche (nur lokal)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--kein-browser", action="store_true")
    ap.add_argument("--takt", type=float, default=5.0,
                    help="Sekunden zwischen zwei Sammellaeufen (Vorgabe 5)")
    args = ap.parse_args()

    # Der Sammler haelt die Terminalsitzung offen und ist der EINZIGE Faden, der
    # MetaTrader anfasst. Die Anfragen lesen nur seinen letzten Schnappschuss.
    sammler = Sammler(takt=args.takt)
    sammler.start()
    Griff.sammler = sammler

    # Bewusst nur 127.0.0.1: die Seite zeigt Kontostand und Positionen und hat im
    # Netz nichts verloren.
    adresse = ("127.0.0.1", args.port)
    server = HTTPServer(adresse, Griff)
    url = f"http://{adresse[0]}:{adresse[1]}/"
    print(f"Oberflaeche laeuft: {url}")
    print(f"Sammeltakt {args.takt:g} s, Anzeige laedt alle {NEULADEN} s nach.")
    print("Nur lesend. Beenden mit Strg-C.")
    if not args.kein_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        sammler.stoppen()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

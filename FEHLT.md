# FEHLT.md — die Leerstellen, die der nächste Auftrag füllt

*Was im Kern **nicht** ist. Dieser Auftrag hat den bewiesenen Kern herausgeloest; das
Fuellen der Leerstellen ist der naechste Auftrag (Teil 2). Nichts hier ist ein Mangel des
Kerns — es ist die bewusst gezogene Grenze. Die vollstaendige Einordnung mit Ankern steht in
`VERLUST.md`; diese Datei fasst zusammen, was gebaut werden muss, und in welcher Reihenfolge.*

---

## Die harte Reihenfolge-Regel

**Kein Ausfuehrungspfad, bevor der Fail-Closed-Apparat und die menschlichen Tore stehen.**
Die Risiko- und Sperrschicht ist da und geprueft, aber sie ist noch an **keinen** realen
Order-Pfad angeschlossen. Ein Anschluss ohne die Tore aus „Sicherheitsapparat" unten waere
genau die falsche Richtung.

---

## 1. Anbindung (venue)

- **ERLEDIGT:** `mt5_trading_ai/venue/mt5.py` implementiert `TradingVenue` (`Mt5Venue`) mit
  Vertragstest (`tests/test_mt5_venue.py`, 18 Faelle) — das Protokoll hat damit erstmals
  einen Test. Das Live-Freigabe-Tor ist verdrahtet (eroeffnende Live-Order nur mit
  vollstaendiger Freigabe). `RealMt5Terminal` bindet MetaTrader5 (lazy), Schreibpfad
  `allow_write=False` (fail-closed).
- **Instrumentenkatalog: ERLEDIGT** — `mt5_trading_ai/venue/catalog.py` +
  `config/instrument_catalog.json` (versioniert, fail-closed). Kosten/Zeiten darin sind
  indikativ und je Broker zu verifizieren; die Anlageklassen-Zuordnung steuert den Hebeldeckel.
- **Order-Lebenszyklus & Reconcile: ERLEDIGT** — `mt5_trading_ai/execution/reconcile.py`
  (Buch + Notional-Drift-Halt), in `Mt5Venue` verdrahtet (`reconcile()`, Global-Halt-Latch,
  `clear_halt()`).
- **Buch-Adoption beim Neustart: ERLEDIGT** — `PositionBook.adopt` / `Mt5Venue.adopt_book()`
  (explizit, ersetzt statt zusammenzufuehren; Latch bleibt manuell).
- **Offen:** Demo-Smoke-Test von `RealMt5Terminal` gegen ein echtes Terminal, dann bewusst
  `allow_write=True`; private WS-Sync (Order-/Positions-Ereignisse in Echtzeit statt Abruf).
- **Hebelklammer-Anschluss: ERLEDIGT** — `execution/leverage_preflight.py`, in
  `Mt5Venue.submit_order` bei jeder eroeffnenden Order verdrahtet. Offen bleibt nur, den
  geklammerten Hebel am realen Terminal je Symbol zu **setzen** (MT5-Symbol-Leverage).

## 2. Marktdaten

- Marktdatenstrom mit Orderbuch-CRC32-Pruefsumme, Sequenzluecken-Erkennung, REST-Nachzug nach
  Verbindungsabriss, Feed-Health-Ereignissen (aus `market-stream`, neu zu schreiben).

## 3. Kosten

- Family-aware Fee-/Funding-/Slippage-/Liquidations-Modell (aus `paper-broker`, neu zu schreiben).

## 4. Universum (Instrumentenkatalog)

- Instrumentenkatalog mit Fail-Closed-Pruefungen (Katalog/Metadaten/Family/Product-Type/
  Margin-Coin), an den die Hebelklammer die Anlageklasse bindet.

## 5. Strategie

- Signal-/Entscheidungslogik, Ensemble, Scoring (aus `signal-engine`, neu zu schreiben) —
  gefuehrt durch die vorregistrierten Kriterien und das Versuchsregister, die schon im Kern
  liegen (`mt5_trading_ai/gates/`).

## 6. Backtest-Maschine

- Eine Backtest-Maschine, die die Zeitreihen-Splits (`mt5_trading_ai/backtest/splits.py`) mit
  echten Daten fuettert — Purge/Embargo sind jetzt pflichtige Parameter, kein stiller Null-Default.

## 7. Sicherheitsapparat (Tore) — vor jedem Live-Pfad

Der Altbestand trug diese Fail-Closed-Sperren am Live-Order-Pfad. **Keine** kam mit (sie
haengt am echten Konto/Feed); **jede** muss stehen, bevor ein Ausfuehrungspfad entsteht.
Vollstaendige Liste mit Ankern in `VERLUST.md` §2b. Kern:

- **Kill-Switch** (arm/release, reduce-only-Pfad) und **Global-Halt-Latch**.
- **Runtime-Safety-Oracle** (Axiom-Checks → Global-Halt) und **Exchange-Readiness**
  (`WRITE_ORDER_ALLOWED_DEFAULT=False`, Zeitversatz-Deckel).
- **Live-Preflight** (Owner-Freigabe/Execution-Mode) und **exit_safety** (Reduce-Only).
- VPIN-Hard-Halt, Liquiditaets-/Slippage-Guard, Strategie-Config-Pruefsumme,
  Positions-Drift-Halt, Reconcile-Snapshot-Fail-Closed.
- portfolio_risk_controls (halt_new_entries/reduce_only/global_halt), uncertainty_gates,
  rejection_rules, pipeline_gates/health_map, secret_leak_guard.

## 8. Zwei konkrete offene Befunde (aus `VERLUST.md` §3)

1. **`portfolio_risk_state_unknown_or_stale`** verlangte im Altbestand `portfolio_risk_check_fresh`
   im Order-Trace, und **kein Produktionscode setzte den Schluessel** — der Guard blockierte
   damit jede eroeffnende Order. Beim Bau des Order-Pfads ist zu klaeren: wer setzt den
   Schluessel korrekt, und wie wird belegt, dass der Pfad je durchlaeuft?
2. **Anschluss der Hebelklammer — ERLEDIGT.** Das Modul (`mt5_trading_ai/risk/leverage.py`,
   Deckel ≤ 10) ist jetzt an den Order-Pfad gebunden: `execution/leverage_preflight.py`,
   aufgerufen in `Mt5Venue.submit_order`. Der Altbestand hatte 7/75-Defaults in
   `config/settings.py` und `paper-broker/config.py`; der Kern senkt die Obergrenze auf 10.
   **Offen bleibt Befund 1** (`portfolio_risk_check_fresh`): er gehoert an genau diesen
   Preflight, sobald der Portfolio-Risikozustand existiert.

---

## Menschliche Tore, die bleiben

Die mehrteilige Live-Freigabe (`mt5_trading_ai/execution/release.py`) ist da und rot-geprueft:
vier unabhaengige Schalter **und** eine nichtleere Freigabekennung, alle Defaults aus, „nicht
bewertbar = nicht erfuellt". Ein realer Order-Pfad darf diese Freigabe nicht umgehen. Reduce-
Only (Risikoabbau) bleibt ohne Freigabe moeglich, weil eine Sperre, die das Schliessen
verhindert, das Risiko erhoeht.

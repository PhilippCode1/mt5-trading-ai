# SPAETER — Befunde für danach (nicht im laufenden Paket)

*Kernregel 21: Ein Fund kommt nur dann in den laufenden Plan, wenn er sich am
fertigen Ergebnis zeigt oder das laufende Paket gefährdet. Alles andere steht hier
und wird bewusst später entschieden. Diese Liste ist kein Rückstand, den man
„abarbeitet" — jeder Punkt ist eine eigene Entscheidung.*

---

## S1 — Vier Risikomodule NICHT im Order-Pfad — ERLEDIGT (Abnahme-Paket 4)

**Erledigt:** Die vier bis dahin verwaisten Module sind jetzt über den neuen
`execution/risk_manager.py` (`RiskManager`) an den Order-Pfad verdrahtet und werden in
`Mt5Venue.submit_order` für jede **eröffnende Live-Order** gefahren (Demo-frei / Live-
Pflicht wie das Kostentor; fehlt der Manager auf Live → fail-closed `risk_unconfigured`).
Reihenfolge und Aufrufer:

- `risk/limits.py` (`evaluate_limits`) — Kill-Switch: Tagesverlust → Ablehnung,
  Drawdown → **`_halted`-Latch** gesetzt, Positionsdeckel, Gap-Sperre.
- `gates/evaluation.py` (`select_one`) — Drossel: Cooldown, Mindesthaltedauer,
  Tageskappen, gleichzeitige Positionen (der zweite zu schnelle Trade fällt).
- `risk/stop_budget.py` (`stop_budget`) + `risk/sizing.py` (`executable_stop_floor`) —
  Stop-Floor gegen Budget je Klasse/Hebel; Floor > Budget → `no_trade`.
- `risk/sizing.py` (`size_position`) — angefordertes Volumen > Budget-Volumen → Ablehnung.

Nachgewiesen am Order-Pfad (`tests/test_mt5_venue.py`): (a) Volumen über Budget →
Ablehnung; (b) Stop-Floor > Budget → `no_trade`; (c) Drawdown-Limit setzt `_halted` und
die nächste Eröffnung fällt am Global-Halt; (d) zu schneller zweiter Trade → Drossel.
Plus reine `RiskManager`-Einheitstests (`tests/test_risk_manager.py`).

**Entscheidung getroffen:** Die Prüfungen sitzen in der **Venue-Schicht** (letzte
Verteidigungslinie je Order), nicht in einer Manager-Schicht über dem Venue — der
`RiskManager` ist eine vom Venue gehaltene, injizierte Komponente (wie das Kostentor),
die den Zustand trägt, den das Venue nicht hat (Equity-Verlauf, Handelsfrequenz, offene
Positionen).

**Bewusst offen (in S12 vermerkt):** (i) Der Score-/Ein-Gewinner-Teil der Drossel
(`select_one` aus vielen Kandidaten) wird per Order mit einem Einzelkandidaten gefahren;
die Auswahl aus mehreren wird erst mit einer echten Bewertungsschleife wirksam. (ii) Die
Volatilität steht am Order-Pfad nicht je Bar bereit → im Stop-Floor mit 0 angesetzt
(Broker-Abstand, Tiefe, Spread binden weiter). (iii) Der Positions-Lebenszyklus ist netto je
Symbol geführt (kein lot-genaues Teil-Fill-Buch je Ticket).

## S2 — Kein Frische-Mechanismus am Halt-Latch (Befund 1, aus A0.3) — ERLEDIGT (Abnahme-Paket 7)

Früher war `reconcile()` rein betreiber-gerufen, kein Automatismus: ein Halt-Latch, den
niemand füllt, ist beliebig alt, und eine Eröffnung lief weiter, obwohl der letzte
Portfolio-Risiko-Check zu alt war.

**Geschlossen durch den Treiber-Loop (`execution/scheduler.py`, `SyncScheduler`):** Er
taktet je Intervall `observe_equity` → private Ereignisse → `check_sync(max_silence)` →
`reconcile()`, unabhängig vom Signal-Pfad. Stille (Strom länger als `max_silence` stumm),
Desync und Positions-Drift latchen den Global-Halt am Venue (`_halted`); der blockt jede
Eröffnung (`submit_order` wirft `global_halt`). Statt einer Alters-Prüfung je Eröffnung
setzt der Loop den Halt **proaktiv**, sobald die Frische reißt — dieselbe Sicherheits­eigen­schaft, kontinuierlich statt punktuell.

Zusätzlich die **Fail-open-Kante geschlossen**, die der §9-Review fand: `PrivateSync.is_stale`
gibt `False`, solange nie ein Ereignis kam (ein nie gestarteter Strom galt nicht als tot).
Der Scheduler kennt die Loop-Startzeit und latcht den Halt (`stream_never_started`), wenn
ein konfigurierter Strom bis `started_at + max_silence` kein einziges Ereignis lieferte
(`venue.latch_halt`, negativ gefahren in `test_paper_runner.py`).

## S3 — MASTERBERICHT §3 wiederholt Modul-Zeilenzahlen (Rule 9)

Die Tabellen in §3.1–3.5 führen je Modul eine Zeilenzahl, die auch in der
generierten `MODULES.md` steht — dieselbe Angabe an zwei Stellen. Das Zahlen-Tor
fängt sie derzeit nicht (Tabellenform „Modul | Zahl |"), aber sie driftet. Entweder
die Spalte entfernen und auf `MODULES.md` verweisen, oder aus dem Code erzeugen.

## S5 — Aktien-CFD-Kostenmodell (ad valorem), aus Paket-1-Review

Die `FeeSchedule` trägt fixe Beträge je Lot. Aktien-CFD-Kosten sind aber prozentual:
Kommission ad valorem (z. B. 0,1 %/Seite) und Swap als %-p.a. des Notionals (beide
preisabhängig). Das Kostenmodell **lehnt Aktien-CFDs derzeit fail-closed ab**
(`load_cost_fees`), statt sie mit der falschen Fixbetrag-Formel still falsch zu bepreisen.
Nachzurüsten, sobald Einzelaktien in den Backtest sollen: ein explizites Kostenmodell
(fixed vs. percentage) in `FeeSchedule` + Verzweigung im Modell. Nicht der Edge-Test-Fokus
(EURUSD), daher später.

**Bestätigt in Abnahme-Paket 3 (bewusste, begründete Nicht-Verdrahtung):** Der
`config/instrument_catalog.json` enthält **kein** EQUITY-Instrument (nur fx_major, fx_minor,
gold, crypto, index_major); die `load_cost_fees`-Ablehnung ist damit ein Wächter für eine
Klasse, die (noch) nicht gehandelt wird, kein aktiver Blocker. Der Wächter ist per Test
gesichert (`test_equity_is_rejected`). Das Pre-Trade-Kostentor am Order-Pfad (Paket 3) erbt
diese Sperre: eine EQUITY-Order käme gar nicht bis zur Kostenrechnung, weil `load_cost_fees`
sie vorher fail-closed abweist. Das ad-valorem-Modell wird erst bei Einzelaktien im Backtest
nötig — in diesem Plan bewusst nicht gebaut.

## S6 — Qualitätstor- und Session-Härtung (aus Paket-2-Review)

Die §9-Review des Datenladers fand mehrere Härtungspunkte über Paket 2 hinaus, nötig für
einen **Intraday**-Edge-Test:

**ERLEDIGT (Abnahme-Paket 1, Kalender):**
- **FX-Session für Intraday** (`FxSession`): Sonntagabend-Öffnung (DST-tolerant 21:00) bis
  Freitagabend, statt des Mo-Fr-Vorabfilters. Gültige Sonntagsbars werden nicht mehr als
  `outside_session` verworfen; die echte EURUSD-H1-Reihe besteht das Tor jetzt.
- **Feiertagskalender** (`DEFAULT_FX_HOLIDAYS`, Neujahr/Weihnachten): Feiertage senken die
  *erwartete* Bar-Zahl (`assess_bars(holidays=...)`, `_max_consecutive_gap`), damit eine
  ausgelassene Feiertags-Bar keine Scheinlücke/Block-Ausfall erzeugt — ohne dünne, echte
  Feiertagsbars als Fehler zu flaggen. Getestet in `tests/test_data_calendar.py`.

**OFFEN (Intraday-Vorarbeit, kein EURUSD-Blocker):**
- **Absolute Preis-Plausibilität** je Instrument (Band) + **Bar-zu-Bar-Return**-Check —
  alle Wertprüfungen sind bisher skaleninvariant/intrabar; eine flache Bar auf falschem
  Niveau (O=H=L=C=99 in einer ~1,1-Reihe) passiert das Tor.
- **Ausreißer/Nullvolumen als harte Fail-Gründe** (ab Quote), nicht nur informativ.
- **Hochpreisige Instrumente** (Index/Krypto > 2^31/Divisor) überlaufen selbst unsigned →
  Wertebereichsprüfung beim Dekodieren.

## S7 — Walk-Forward-Trainingsschritt + volle Kriterien-Integration — ERLEDIGT (Abnahme-Paket 2)

`run_walk_forward` nimmt jetzt einen **Fitter** `Callable[[Sequence[BarRow]], Strategy]`, der die
Trainings-Bars (expandierendes Fenster, `exclude_prior_test=False`, ohne Purge/Embargo-Band)
bekommt und die darauf bestimmte Strategie auf `test_idx` testet.

**Ehrlich zum Purge/Embargo (aus dem §9-Review dieses Pakets):** Nur der **Purge** (linke
Bandkante) greift im strikten Walk-Forward faktisch — er entfernt die testnahen Trainings-Bars,
gemessen als Schrumpfung des Trainingsfensters (`test_purge_shrinks_the_training_window`). Das
**Embargo** (rechte Bandkante, hinter dem Testblock) trifft hier per Konstruktion **keinen**
Trainings-Bar, weil Training nur Vergangenheit ist; es ist ein No-op, mit eigenem Test belegt
(`test_embargo_alone_does_not_change_the_training_window`) statt in einem gemeinsamen Test
maskiert. Die Leckfreiheit über die Fenstergrenze folgt aus Vergangenheits-Konstruktion + Purge,
**nicht** aus dem Embargo (das erst in `purged_kfold_embargo_indices` gatet). Fold 0 ohne
Training handelt nicht. Eine Fixparameter-Strategie ignoriert die Trainings-Bars (Fit = No-op,
korrekt für den nicht-optimierten Edge-Test). Ebenfalls erledigt: die volle
`evaluate_criteria`-Auswertung ist über `criteria_evidence(...)` an den Lauf gebunden und läuft
im Edge-Test als Zusatz-Report neben dem Sechs-Bedingungen-Tor.

## S4 — Halal-Konformität: mechanisch erledigt, fiqh-Grundfrage offen

**Mechanischer Teil erledigt** (BERICHT §12, `costs/halal.py` + `venue/halal.py`): swapfreie
Finanzierung ohne Zins (nie riba-Gutschrift, per Test gesichert) + Halal-Screen (fail-closed,
prüft swapfreies Konto / zinsfreie Margin / Instrument-Screen). Nachgewiesen: unter der
swapfreien Politik fällt die riba-Carry-Gutschrift von 160,06 auf 0,00 USD; Ergebnis am
Sechs-Bedingungen-Tor bleibt „kein Edge".

**Offen bleibt die fiqh-Grundentscheidung:** ob ein gehebelter CFD überhaupt zulässig ist
(gharar, fehlendes Eigentum, Termincharakter). Das entscheidet der Code bewusst **nicht** --
`screen_halal` setzt `requires_scholar_review` immer auf wahr (Kernregel 16, „nicht allein
entscheiden"). Braucht einen Gelehrten + Philipps Entscheidung, keine Codeänderung. Ebenso
offen: der swapfreie Admin-Gebühr-Satz ist eine Schätzung (Broker-Bestätigung), und die
Krypto-/Aktien-Geschäftsfeldprüfung ist markiert, aber nicht mit einer AAOIFI-Liste hinterlegt.

## S8 — Deflation auf die Trade-Level-Sharpe umstellen — ERLEDIGT (Abnahme-Paket 2)

`deflated_sharpe_for_report` deflationiert jetzt die **Trade**-Sharpe je Beobachtung
(`report.trade_sharpe_per_obs`, Beobachtungen = Trade-Anzahl) statt der Bar-Sharpe — dieselbe
Kennzahl, die das Sechs-Bedingungen-Tor (Bedingung 1) prüft. Unter 2 Trades ist keine Deflation
bestimmbar (Rückgabe 0). Damit sind gemessene und deflationierte Größe **konsistent** —
dieselbe Kennzahl wird bewertet und deflationiert. **Ehrlich (aus dem §9-Review):** ob die Zahl
dadurch strenger oder lockerer wird als bei der Bar-Sharpe, ist datenabhängig, nicht generell
strenger (im Teil-3-Lauf lag die Trade-Level-DSR sogar leicht über der Bar-Level-DSR). Der Gewinn
ist die Konsistenz, nicht garantierte Strenge. **Hinweis:** die in `BERICHT_TEIL3.md` genannten
Deflated-Sharpe-Werte (0,066 usw.) stammen aus dem Teil-3-Lauf mit der alten Bar-Level-Methode;
das Urteil (≪ 0,95, kein Edge) ist von der Umstellung unberührt.

## S9 — cost_stress skaliert keine Finanzierung/Swap (aus Paket-2-Review)

`stressed_spec` multipliziert nur die **Transaktionskosten** (Spread/Slippage/Kommission), nicht
die Finanzierung (Swap). Bewusst: Swap ist ein Zinssatz (kann als Carry Ertrag sein), kein
Ausführungs-Friction, und uniform × Faktor zu skalieren wäre kein sinnvoller Stress. Für die
aktuellen, **nicht** carry-tragenden Strategien (Intraday-MA/Mean-Reversion, meist flat über
Nacht) ist das folgenlos. **Zu entscheiden, sobald eine über Nacht getragene / carry-abhängige
Strategie in den Test soll:** ein eigenes Finanzierungs-Stressszenario (z. B. Swap-Satz-Aufschlag
oder adverse Roll), getrennt vom Transaktionskosten-Multiplikator.

## S10 — Pre-Trade-Kostentor nur gleich notiert; Kreuzwährung braucht Live-FX-Kurs (aus Paket-3-Review)

Das Pre-Trade-Kostentor (`execution/cost_gate.py`, Paket 3) prüft die reale Roundturn-Kostenquote
`friction/notional` **nur für gleich notierte Instrumente** (Notierungs- = Kontowährung, z. B.
EURUSD/GBPUSD/XAUUSD/BTCUSD auf USD-Konto → Umrechnungskurs 1). Grund (§9-Review): `friction` kommt
aus `order_roundturn_cost` in **Kontowährung** (Kommission nativ, Spread/Slippage per Kurs
umgerechnet), das `notional` bildet sich aus dem rohen Preis in **Notierungswährung**; nur bei
gleicher Währung stehen Zähler und Nenner in derselben Einheit und die Quote ist korrekt. Ein
kreuznotiertes Instrument (USDJPY→JPY, EURGBP→GBP auf USD-Konto) wird **fail-closed** abgewiesen
(`cost_unverifiable`), statt mit einem einzelnen Venue-Skalar-Kurs falsch gerechnet zu werden — ein
Skalar am Konto-Venue kann nicht gleichzeitig für USD- und JPY-notierte Paare stimmen.

**Nachzurüsten, sobald ein kreuznotiertes Instrument live gehandelt werden soll:** ein
**instrumentspezifischer** Umrechnungskurs Notierungs-→Kontowährung, live aus dem Terminal je
Symbol abgeleitet (nicht als statischer Skalar), an `evaluate_cost_gate` gereicht, mit dem das
**notional ebenfalls** in Kontowährung geführt wird. Bis dahin gilt: kreuznotiert = kein Live-Trade
durchs Kostentor. EURUSD (Edge-Test-Fokus) ist gleich notiert und voll abgedeckt.

## S11 — reduce_only umgeht alle Eröffnungs-Tore; Kostentor vertraut Broker-Daten (aus Paket-3-Review)

Zwei vorbestehende Vertrauensgrenzen, die der §9-Fix-Re-Check von Paket 3 benannte — **kein**
Defekt der neuen Kostentor-Logik, aber ehrlich zu vermerken:

- **`reduce_only`-Carve-out — ERLEDIGT (Abnahme-Paket 5, §9-Review).** Der §9-Review von Paket 5
  bestätigte, dass das blind vertraute `reduce_only`-Flag ein echtes **fail-open** war: eine als
  `reduce_only` markierte Order **ohne** Gegenposition eröffnete (kein No-Op) und umging damit alle
  Eröffnungs-Tore (Compliance, Risiko) **und** den Global-Halt. **Behoben:** `submit_order` überspringt
  die Tore jetzt nur noch, wenn die Order eine **tatsächlich offene Gegenposition abbaut**
  (`_reduces_position`: maßgeblich ist **ausschließlich** die autoritative Börsen-Gegenposition —
  `get_positions()` ist ein frischer Broker-Query, hedging-fähig, deckt auch serverseitige SL/TP-
  und externe Schließungen). Das lokale Netto-Buch trägt die Reduce-Autorisierung **nie**: es kann
  in beide Richtungen veralten. **Volumen-begrenzt:** nur wenn das Order-Volumen die Gegenposition
  **nicht überschreitet**, ist es reine Reduktion; ein Over-Fill flippt netto, und der Überschuss ist
  eine Eröffnung, die durch alle Tore muss (`test_reduce_only_over_fill_is_gated_as_opening`). Ein
  `reduce_only`-Flag ohne (oder gleichgerichtet/übergroß zu einer) Position fällt in den
  Eröffnungs-Zweig und wird regulär geprüft/abgelehnt
  (`test_live_reduce_only_without_position_is_gated_as_opening`). Drei Fix-Re-Check-Runden
  (Volumen-Klammer → Börsen-Autorität statt `max(Buch,Börse)` → Buch-Zweig ganz entfernt, weil
  Stille/Latenz `desync` nicht setzt). Der legitime Risikoabbau
  (echtes Schließen) passiert weiter ohne Freigabe, auch im Halt.
  **Offene, vorbestehende Randnotiz (kein fail-open, orthogonal):** Das Reduce-Gate summiert das
  gesamte Gegen-Brutto, während `RealMt5Terminal.order_send` nur das **erste** passende
  Gegen-Ticket adressiert. Auf einem **Hedging**-Konto mit mehreren Gegen-Tickets kann eine
  Reduce-Order, deren Volumen das erste Ticket übersteigt (aber ≤ Gesamt-Brutto), das Gate
  passieren und dennoch nur ein kleineres Einzel-Ticket treffen; das Überlauf-Verhalten ist
  broker-definiert. Das Netto-Exposure sinkt in jedem Fall (es ist ein Abbau), und das Verhalten ist
  unverändert aus der Zeit vor Paket 5. **Zu entscheiden, sobald Hedging-Konten in Betrieb gehen:**
  `order_send` über mehrere Gegen-Tickets iterieren oder das Gate auf das größte Einzel-Ticket
  klammern. Für Netting-Konten (ESMA-Retail-Norm) irrelevant.
- **Broker-Datenintegrität:** Das Kostentor liest `entry.fees` direkt aus dem Katalog und vertraut
  der vom Terminal gemeldeten `currency_profit` (= Notierungswährung). Ein falsch gemeldetes
  `currency_profit` oder eine 0-Kommission-Datenlücke (die `load_cost_fees` ablehnen würde, im
  direkten Venue-Katalogzugriff aber nicht erneut geprüft wird) kann das Tor nicht abfangen. **Zu
  entscheiden:** ob der Venue-Pfad dieselbe `load_cost_fees`-Sanität (Kommission-0 = Datenlücke)
  erzwingen soll, bevor eine Order gegen diese Gebühren bepreist wird.

## S12 — Risikoschicht: bewusst vereinfachte Teile (aus Paket-4-Verdrahtung)

Die Risikoschicht (S1) ist am Order-Pfad wirksam; drei Teile sind bewusst vereinfacht und
warten auf spätere Ausbaustufen — jeder eine eigene Entscheidung:

- **Drossel-Auswahl aus mehreren Kandidaten:** `gates/evaluation.py` `select_one` wählt aus
  einer Kandidatenmenge **einen** Trade. Am Venue-Order-Pfad existiert je Order genau **ein**
  Kandidat (der Auftrag), also greifen nur die Frequenz-Guards (Cooldown, Mindesthaltedauer,
  Tageskappen, Positionsdeckel). Der Ranglisten-/Ein-Gewinner-Teil wird erst wirksam, wenn eine
  echte **Bewertungsschleife** mehrere Kandidaten je Takt liefert (S2-nah). Bis dahin ist das
  „Bewerten ≠ Handeln" per Order-Frequenz durchgesetzt, nicht per Batch-Auswahl.
- **Volatilität im Stop-Floor:** `executable_stop_floor` nimmt eine `volatility_bps`. Am
  Order-Pfad steht die Bar-Volatilität je Order nicht bereit → mit 0 angesetzt; der Floor nimmt
  das Maximum, sodass Broker-Mindestabstand, Tiefe (unbekannt → 15 bps) und Spread weiter binden.
  Nachzurüsten: eine Volatilitätsquelle (z. B. ATR aus jüngsten Bars) an die Risikoschicht reichen.
- **Positions-Lebenszyklus:** `RiskManager.record_open_fill`/`record_close` schreiben offene
  Positionen mit Eröffnungszeit für Mindesthaltedauer/Deckel fort — **netto je Symbol** (Dedup
  beim Öffnen, `record_close` am Venue verdrahtet, wenn ein reduce_only-Fill das Symbol
  glattstellt; beide im §9-Review von Paket 4 nachgezogen). Das Glattstellen wird aus
  `pre_net + Fill` bestimmt (stromunabhängig, in Nicht-Strom- **und** Strom-Modus per Test belegt).
  Was bewusst **offen** bleibt: (a) ein **lot-genaues, teil-fill-fähiges** Positionsbuch je Ticket
  (das Netto-je-Symbol-Modell reicht für die Frequenz-/Deckel-Guards); (b) eine seltene
  **Strom-Latenz-Kante** — solange ein soeben abgesetzter Fill noch nicht in den privaten Strom
  gebucht ist, ist `pre_net` veraltet. Das kann **in beide Richtungen** kippen (ehrlich, aus dem
  Fix-Re-Check): meist **fail-closed** (ein Close, dessen Gegen-Eröffnung noch nicht gebucht ist,
  stellt scheinbar nicht glatt → Symbol bleibt im Deckel), im Pyramiding-Fall aber auch
  **fail-open** (gebuchte Position + noch ungebuchte Aufstockung, dann ein reduce_only, dessen
  `filled_volume` genau das bereits gebuchte Netto trifft → `record_close` entfernt das Symbol,
  obwohl real noch +Δ offen ist → Deckel **unterzählt**). Beide sind auf die Ereignis-Latenz
  begrenzt; ein Ticket-genaues, **stromgetriebenes** Positionsbuch behebt beide Richtungen —
  später zu entscheiden.

## S9 — Entartete Streuung in der Ereignisstudie sättigt die Deflation

**Gefunden:** 2026-08-19, Stufe 3 des Dauerauftrags. **Gemessen, nicht vermutet.**

`backtest/ereignisstudie.py` rechnet `sharpe = fmean(oos) / stdev(oos)` und schützt nur
gegen `stdev == 0`. Bei *fast* verschwindender Streuung wird der Wert beliebig groß — an
den synthetischen Reihen des Prüfstands gemessen **3,06 × 10¹³** —, und
`deflated_sharpe_ratio` sättigt darauf auf **1,0**, also maximale Bestätigung. Die
Schwelle des Standes ist 0,95.

Für die realen Läufe aus Paket 3a ist das folgenlos: der höchste dort gemessene DSR war
0,686. Der Mangel wirkt nur, wenn eine Reihe entartet — und dann in die schmeichelnde
Richtung, unbemerkt.

**Warum hier nicht behoben:** das ist ein Streuungs-, kein Einheitenproblem. Der Stand hat
für die Frage „reicht die Auflösung überhaupt" bereits ein eigenes Werkzeug
(`backtest/resolution.py`, `min_events_for_resolution`); die richtige Behebung hängt die
Studie dort an, statt eine zweite Plausibilitätsregel danebenzustellen. Das ist mehr als
eine Zeile und gehört zu dem, der die Statistik der Studie verantwortet.

Beleg: `AUFTRAG/stufen/03-simulator/belege/01-geldnahe-groessen.txt`.

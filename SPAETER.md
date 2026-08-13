# SPAETER — Befunde für danach (nicht im laufenden Paket)

*Kernregel 21: Ein Fund kommt nur dann in den laufenden Plan, wenn er sich am
fertigen Ergebnis zeigt oder das laufende Paket gefährdet. Alles andere steht hier
und wird bewusst später entschieden. Diese Liste ist kein Rückstand, den man
„abarbeitet" — jeder Punkt ist eine eigene Entscheidung.*

---

## S1 — Vier Risikomodule liegen NICHT im Order-Pfad (aus A0.2)

`Mt5Venue.submit_order` ruft in Folge: Idempotenz → Global-Halt → Stop-Pflicht
(nackter `stop_loss<=0`) → Live-Freigabe → Hebel-Preflight → Terminal. **Nicht**
aufgerufen werden:

- `risk/limits.py` — Tagesverlust, Drawdown-Halt, Positionsdeckel
- `risk/sizing.py` — Positionsgröße, Stop-Floor
- `risk/stop_budget.py` — Stop-Budget je Klasse
- `gates/evaluation.py` — Bewertungstor

Sie sind getestet, aber **verwaiste Inseln**: es gibt keinen Aufrufer, weil noch keine
Codezeile eine Handelsentscheidung trifft. Das ist dieselbe Fehlerklasse wie die alte
Hebelklammer (getestet, aber am Live-Pfad nie aufgerufen).

**Zu entscheiden (nicht jetzt):** Gehören diese Prüfungen in die Venue-Schicht (letzte
Verteidigungslinie je Order) oder in eine Risiko-Manager-Schicht **über** dem Venue
(die entscheidet, ob und mit welcher Größe überhaupt eingereicht wird)? Erst wenn ein
Aufrufer existiert (Signal-/Risiko-Schicht), wird die Verdrahtung sinnvoll. Bis dahin
darf niemand behaupten, diese Grenzen seien „am Order-Pfad aktiv".

## S2 — Kein Frische-Mechanismus am Halt-Latch (Befund 1, aus A0.3)

`reconcile()` ist betreiber-gerufen, kein Automatismus je Order. Ein Halt-Latch, den
niemand füllt, ist beliebig alt; es gibt keinen Zeitstempel + Maximalalter, der eine
Eröffnung blockiert, wenn der letzte Portfolio-Risiko-Check zu alt ist. Der frühere
`portfolio_risk_check_fresh` bleibt damit **offen**. Nachzurüsten: Frische-Pflicht
(Alter des letzten Reconcile < Grenze) als Vorbedingung jeder Eröffnung.

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

- **`reduce_only`-Carve-out:** `Mt5Venue.submit_order` überspringt für `reduce_only=True` **alle**
  Eröffnungs-Tore (Global-Halt, Stop-Pflicht, Live-Freigabe, Hebel-Preflight, **Kostentor**) —
  bewusst, weil Risikoabbau (Schließen) nicht an denselben Eröffnungs-Schranken hängen darf. Rand:
  `RealMt5Terminal.order_send` setzt bei `reduce_only` **ohne** passende Gegenposition kein
  `position`-Ticket und sendet dann einen normalen Deal — ein `reduce_only`-Missbrauch auf einer
  faktisch **eröffnenden** Order läge damit außerhalb aller Tore. **Zu entscheiden (nicht jetzt):**
  eine Vorbedingung, die `reduce_only` an eine real existierende Gegenposition bindet (Buch-/
  Positions-Check), bevor die Tore übersprungen werden.
- **Broker-Datenintegrität:** Das Kostentor liest `entry.fees` direkt aus dem Katalog und vertraut
  der vom Terminal gemeldeten `currency_profit` (= Notierungswährung). Ein falsch gemeldetes
  `currency_profit` oder eine 0-Kommission-Datenlücke (die `load_cost_fees` ablehnen würde, im
  direkten Venue-Katalogzugriff aber nicht erneut geprüft wird) kann das Tor nicht abfangen. **Zu
  entscheiden:** ob der Venue-Pfad dieselbe `load_cost_fees`-Sanität (Kommission-0 = Datenlücke)
  erzwingen soll, bevor eine Order gegen diese Gebühren bepreist wird.

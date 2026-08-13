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

## S7 — Walk-Forward-Trainingsschritt + volle Kriterien-Integration (aus Paket-3-Review)

Der Walk-Forward-Runner nutzt `splits.py` mit pflichtigem Purge/Embargo, aber ohne einen
Trainings-/Fit-Schritt je Fenster gaten Purge/Embargo noch nichts (sie schließen nur
Trainingsindizes aus, die eine zustandslose Strategie nicht hat). Nachzurüsten, sobald eine
lernende Strategie kommt (Paket 4/5): echter Fit auf `_train_idx`, Test auf `test_idx` — dann
greifen Purge/Embargo als Leckage-Kontrolle. Ebenso: die volle `evaluate_criteria`-Auswertung
(`BacktestEvidence` aus Report + positive_folds + deflated_sharpe + random_percentile) im
Edge-Test verdrahten — die Deflations-Bindung (`deflated_sharpe_for_report`) steht, die
Gesamt-Auswertung folgt in Paket 4.

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

## S8 — Deflation auf die Trade-Level-Sharpe umstellen (aus Paket-4b-Review)

`deflated_sharpe_for_report` deflationiert die **Bar**-Sharpe (`report.annualised_sharpe`,
Beobachtungen = Bars − 1), während das Sechs-Bedingungen-Tor (Bedingung 1) bewusst die
**Trade**-Sharpe prüft (ehrlich bei seltenem Handel). Im Mean-Reversion-Lauf folgenlos — beide
ergeben denselben Deflated Sharpe 0,066 —, aber bei einem größeren Signal würde die Bar-Sharpe
mit ihrer viel höheren Beobachtungszahl die Deflation überzeichnen. Nachzurüsten: die
Trade-Level-Sharpe mit Trade-Anzahl als Beobachtungen deflationieren, damit gemessene und
deflationierte Größe dieselbe sind.

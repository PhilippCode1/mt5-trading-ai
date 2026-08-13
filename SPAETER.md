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
einen **Intraday**-Edge-Test (Paket 3/4):
- **FX-Session am NY-17:00-Anker**, im Tor statt als Mo-Fr-UTC-Vorabfilter. Der aktuelle
  Filter verwirft den echten Sonntagabend-Balken und lässt geglättete Feiertagsbars als
  „present" durch; der `outside_session`-Check ist für Wochenenden dadurch wirkungslos.
- **Lückenquote gegen einen echten Handelstags-/Feiertagskalender** (nicht rohe Kalender-
  Wochentage) und zusätzlich pro Monat bucketen (die ursprüngliche Docstring-Zusage).
- **Absolute Preis-Plausibilität** je Instrument (Band) + **Bar-zu-Bar-Return**-Check —
  alle Wertprüfungen sind bisher skaleninvariant/intrabar; eine flache Bar auf falschem
  Niveau (O=H=L=C=99 in einer ~1,1-Reihe) passiert das Tor.
- **Ausreißer/Nullvolumen als harte Fail-Gründe** (ab Quote), nicht nur informativ.
- **Hochpreisige Instrumente** (Index/Krypto > 2^31/Divisor) überlaufen selbst unsigned →
  Wertebereichsprüfung beim Dekodieren.

Der jetzige Block-Ausfall-Check, die Instrument→Divisor-Tabelle (fail-closed) und die
Manifest-Prüfsumme decken die gröbsten Löcher; der Rest ist Intraday-Vorarbeit, kein
EURUSD-Tagesbar-Blocker.

## S7 — Walk-Forward-Trainingsschritt + volle Kriterien-Integration (aus Paket-3-Review)

Der Walk-Forward-Runner nutzt `splits.py` mit pflichtigem Purge/Embargo, aber ohne einen
Trainings-/Fit-Schritt je Fenster gaten Purge/Embargo noch nichts (sie schließen nur
Trainingsindizes aus, die eine zustandslose Strategie nicht hat). Nachzurüsten, sobald eine
lernende Strategie kommt (Paket 4/5): echter Fit auf `_train_idx`, Test auf `test_idx` — dann
greifen Purge/Embargo als Leckage-Kontrolle. Ebenso: die volle `evaluate_criteria`-Auswertung
(`BacktestEvidence` aus Report + positive_folds + deflated_sharpe + random_percentile) im
Edge-Test verdrahten — die Deflations-Bindung (`deflated_sharpe_for_report`) steht, die
Gesamt-Auswertung folgt in Paket 4.

## S4 — Halal-Konformität von Krypto-/CFD-Instrumenten (aus E2)

Mit E2 ist Krypto (2:1) im Katalog handelbar. CFDs allgemein und Übernacht-Swaps im
Besonderen berühren die Zins-/Riba-Frage (Kernregel 16). Bevor Krypto tatsächlich
gehandelt wird, braucht es eine Halal-Entscheidung (swapfreie Kontoform? Instrument
grundsätzlich zulässig?). Gehört inhaltlich zur Kostenrecherche R1.6 (Paket 1) und
ist dort mitzuentscheiden, nicht stillschweigend.

## S8 — Deflation auf die Trade-Level-Sharpe umstellen (aus Paket-4b-Review)

`deflated_sharpe_for_report` deflationiert die **Bar**-Sharpe (`report.annualised_sharpe`,
Beobachtungen = Bars − 1), während das Sechs-Bedingungen-Tor (Bedingung 1) bewusst die
**Trade**-Sharpe prüft (ehrlich bei seltenem Handel). Im Mean-Reversion-Lauf folgenlos — beide
ergeben denselben Deflated Sharpe 0,066 —, aber bei einem größeren Signal würde die Bar-Sharpe
mit ihrer viel höheren Beobachtungszahl die Deflation überzeichnen. Nachzurüsten: die
Trade-Level-Sharpe mit Trade-Anzahl als Beobachtungen deflationieren, damit gemessene und
deflationierte Größe dieselbe sind.

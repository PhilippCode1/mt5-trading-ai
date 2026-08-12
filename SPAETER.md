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

## S4 — Halal-Konformität von Krypto-/CFD-Instrumenten (aus E2)

Mit E2 ist Krypto (2:1) im Katalog handelbar. CFDs allgemein und Übernacht-Swaps im
Besonderen berühren die Zins-/Riba-Frage (Kernregel 16). Bevor Krypto tatsächlich
gehandelt wird, braucht es eine Halal-Entscheidung (swapfreie Kontoform? Instrument
grundsätzlich zulässig?). Gehört inhaltlich zur Kostenrecherche R1.6 (Paket 1) und
ist dort mitzuentscheiden, nicht stillschweigend.
